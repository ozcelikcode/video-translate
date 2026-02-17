from __future__ import annotations

import json
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from video_translate.config import AppConfig
from video_translate.io import write_json
from video_translate.qa.m3_report import build_m3_qa_report
from video_translate.tts.backends import build_tts_backend
from video_translate.tts.contracts import (
    TTSOutputDocument,
    build_tts_output_document,
    parse_tts_input_document,
)


@dataclass(frozen=True)
class M3Artifacts:
    tts_input_json: Path
    tts_output_json: Path
    qa_report_json: Path
    run_manifest_json: Path
    stitched_preview_wav: Path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _blocked_quality_flags(qa_report: dict[str, Any], allowed_flags: tuple[str, ...]) -> list[str]:
    allowed = set(allowed_flags)
    raw_flags = qa_report.get("quality_flags", [])
    if not isinstance(raw_flags, list):
        return []
    normalized = [str(flag) for flag in raw_flags]
    return [flag for flag in normalized if flag not in allowed]


def _read_wav_mono_pcm16(path: Path) -> tuple[int, list[int]]:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        raw = wav_file.readframes(frame_count)
    if channels != 1:
        raise ValueError(f"Preview stitch only supports mono WAV segments: {path}")
    if sample_width != 2:
        raise ValueError(f"Preview stitch only supports 16-bit PCM WAV segments: {path}")
    samples = [value[0] for value in struct.iter_unpack("<h", raw)]
    return sample_rate, samples


def _write_wav_mono_pcm16(path: Path, sample_rate: int, samples: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frame_blob = b"".join(
            int(max(-32768, min(32767, sample))).to_bytes(2, byteorder="little", signed=True)
            for sample in samples
        )
        wav_file.writeframes(frame_blob)


def _build_stitched_preview_wav(*, output_doc: TTSOutputDocument, preview_wav_path: Path) -> Path:
    mixed: list[int] = []
    detected_sample_rate: int | None = None
    for segment in output_doc.segments:
        audio_path = Path(segment.audio_path)
        sample_rate, samples = _read_wav_mono_pcm16(audio_path)
        if detected_sample_rate is None:
            detected_sample_rate = sample_rate
        elif sample_rate != detected_sample_rate:
            raise ValueError(
                "All segment WAV files must share the same sample rate for preview stitching."
            )

        start_frame = max(0, int(round(float(segment.start) * sample_rate)))
        end_frame = start_frame + len(samples)
        if end_frame > len(mixed):
            mixed.extend([0] * (end_frame - len(mixed)))
        for index, sample in enumerate(samples):
            mixed_index = start_frame + index
            mixed[mixed_index] += sample

    if detected_sample_rate is None:
        detected_sample_rate = 24000
    if not mixed:
        mixed = [0]
    _write_wav_mono_pcm16(preview_wav_path, detected_sample_rate, mixed)
    return preview_wav_path


def run_m3_pipeline(
    *,
    tts_input_json_path: Path,
    output_json_path: Path,
    qa_report_json_path: Path,
    run_manifest_json_path: Path,
    config: AppConfig,
) -> M3Artifacts:
    pipeline_start = perf_counter()
    if not tts_input_json_path.exists():
        raise FileNotFoundError(f"TTS input JSON not found: {tts_input_json_path}")

    read_start = perf_counter()
    input_payload = _read_json(tts_input_json_path)
    input_doc = parse_tts_input_document(input_payload)
    read_seconds = perf_counter() - read_start

    backend = build_tts_backend(config.tts)
    segment_audio_dir = output_json_path.parent / "segments"
    segment_audio_dir.mkdir(parents=True, exist_ok=True)

    synth_start = perf_counter()
    segment_audio_paths: list[Path] = []
    synthesized_durations: list[float] = []
    for segment in input_doc.segments:
        output_wav = segment_audio_dir / f"seg_{segment.id:06d}.wav"
        synthesized_duration = backend.synthesize_to_wav(
            text=segment.target_text,
            output_wav=output_wav,
            target_duration=segment.duration,
            sample_rate=config.tts.sample_rate,
        )
        segment_audio_paths.append(output_wav)
        synthesized_durations.append(synthesized_duration)
    synth_seconds = perf_counter() - synth_start

    build_output_start = perf_counter()
    output_doc = build_tts_output_document(
        input_doc=input_doc,
        backend=backend.name,
        sample_rate=config.tts.sample_rate,
        segment_audio_paths=segment_audio_paths,
        synthesized_durations=synthesized_durations,
    )
    build_output_seconds = perf_counter() - build_output_start

    qa_start = perf_counter()
    qa_report = build_m3_qa_report(output_doc, config.tts)
    qa_seconds = perf_counter() - qa_start

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    qa_report_json_path.parent.mkdir(parents=True, exist_ok=True)
    run_manifest_json_path.parent.mkdir(parents=True, exist_ok=True)
    write_start = perf_counter()
    write_json(output_json_path, output_doc.to_dict())
    write_json(qa_report_json_path, qa_report)
    stitched_preview_wav = output_json_path.parent / f"tts_preview_stitched.{output_doc.language}.wav"
    _build_stitched_preview_wav(output_doc=output_doc, preview_wav_path=stitched_preview_wav)
    write_seconds = perf_counter() - write_start

    blocked_flags = _blocked_quality_flags(qa_report, config.tts.qa_allowed_flags)
    qa_gate_passed = not blocked_flags
    total_seconds = perf_counter() - pipeline_start
    write_json(
        run_manifest_json_path,
        {
            "stage": "m3",
            "backend": backend.name,
            "inputs": {
                "tts_input_json": str(tts_input_json_path),
            },
            "outputs": {
                "tts_output_json": str(output_json_path),
                "qa_report_json": str(qa_report_json_path),
                "segment_audio_dir": str(segment_audio_dir),
                "stitched_preview_wav": str(stitched_preview_wav),
            },
            "timings_seconds": {
                "read_input": read_seconds,
                "synthesize_segments": synth_seconds,
                "build_output_contract": build_output_seconds,
                "build_qa_report": qa_seconds,
                "write_outputs": write_seconds,
                "total_pipeline": total_seconds,
            },
            "qa_gate": {
                "enabled": config.tts.qa_fail_on_flags,
                "passed": qa_gate_passed,
                "allowed_flags": list(config.tts.qa_allowed_flags),
                "blocked_flags": blocked_flags,
            },
        },
    )
    if config.tts.qa_fail_on_flags and not qa_gate_passed:
        raise RuntimeError(
            "M3 QA gate failed. Blocked quality flags: " + ", ".join(blocked_flags)
        )

    return M3Artifacts(
        tts_input_json=tts_input_json_path,
        tts_output_json=output_json_path,
        qa_report_json=qa_report_json_path,
        run_manifest_json=run_manifest_json_path,
        stitched_preview_wav=stitched_preview_wav,
    )
