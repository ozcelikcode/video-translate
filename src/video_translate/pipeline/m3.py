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
from video_translate.utils.subprocess_utils import CommandExecutionError, run_command


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


def _pad_wav_silence_to_duration(wav_path: Path, target_duration: float) -> float:
    with wave.open(str(wav_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        raw_frames = wav_file.readframes(frame_count)
        comp_type = wav_file.getcomptype()
        comp_name = wav_file.getcompname()
    if sample_rate <= 0:
        return 0.0
    current_duration = frame_count / sample_rate
    if target_duration <= current_duration:
        return current_duration
    target_frames = int(round(target_duration * sample_rate))
    missing_frames = max(0, target_frames - frame_count)
    if missing_frames <= 0:
        return current_duration
    silence_frame = b"\x00" * sample_width * channels
    padded_frames = raw_frames + (silence_frame * missing_frames)
    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.setcomptype(comp_type, comp_name)
        wav_file.writeframes(padded_frames)
    return target_frames / sample_rate


def _wav_duration_seconds(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as wav_file:
        frame_count = wav_file.getnframes()
        sample_rate = wav_file.getframerate()
    if sample_rate <= 0:
        return 0.0
    return frame_count / sample_rate


def _safe_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _boundary_hint_float(segment: Any, key: str) -> float:
    boundary_hints = getattr(segment, "boundary_hints", None)
    if not isinstance(boundary_hints, dict):
        return 0.0
    parsed = _safe_float(boundary_hints.get(key))
    if parsed is None:
        return 0.0
    return max(0.0, parsed)


def _boundary_risk_score(segment: Any) -> float:
    boundary_hints = getattr(segment, "boundary_hints", None)
    if not isinstance(boundary_hints, dict):
        return 0.0
    parsed = _safe_float(boundary_hints.get("boundary_cut_risk_score"))
    if parsed is None:
        return 0.0
    return max(0.0, min(1.0, parsed))


def _choose_effective_slot_duration(*, segment: Any, config: AppConfig, synthesized_duration: float) -> tuple[float, float]:
    base_duration = max(0.0, float(segment.duration))
    if not config.tts.boundary_stabilization_enabled:
        return base_duration, 0.0
    if synthesized_duration <= base_duration + max(0.0, float(config.tts.max_duration_delta_seconds)):
        return base_duration, 0.0
    left_budget = _boundary_hint_float(segment, "can_borrow_left_gap_seconds")
    right_budget = _boundary_hint_float(segment, "can_borrow_right_gap_seconds")
    total_budget = min(
        max(0.0, float(config.tts.boundary_max_gap_borrow_seconds)),
        max(0.0, right_budget) + max(0.0, left_budget),
    )
    if total_budget <= 0.0:
        return base_duration, 0.0
    return base_duration + total_budget, total_budget


def _synthesize_with_retry(
    *,
    backend: Any,
    segment: Any,
    output_wav: Path,
    sample_rate: int,
    slot_target_duration: float,
    config: AppConfig,
    initial_duration: float | None = None,
) -> tuple[float, int]:
    duration = (
        float(initial_duration)
        if initial_duration is not None
        else backend.synthesize_to_wav(
            text=segment.target_text,
            output_wav=output_wav,
            target_duration=segment.duration,
            sample_rate=sample_rate,
        )
    )
    if (
        not config.tts.boundary_stabilization_enabled
        or not config.tts.boundary_retry_risky_segments
        or config.tts.boundary_retry_max_passes <= 0
    ):
        return duration, 0
    if _boundary_risk_score(segment) < 0.45:
        return duration, 0

    tolerance = max(0.0, float(config.tts.max_duration_delta_seconds))
    if duration <= slot_target_duration + tolerance:
        return duration, 0

    best_duration = duration
    best_path = output_wav
    retry_passes = 0
    current_target = max(0.05, float(segment.duration))
    for pass_index in range(config.tts.boundary_retry_max_passes):
        current_target = max(
            0.05,
            min(
                current_target,
                float(segment.duration) - (0.03 * (pass_index + 1)),
            ),
        )
        retry_wav = output_wav.with_name(f"{output_wav.stem}.retry_{pass_index+1}.wav")
        retry_duration = backend.synthesize_to_wav(
            text=segment.target_text,
            output_wav=retry_wav,
            target_duration=current_target,
            sample_rate=sample_rate,
        )
        retry_passes += 1

        best_overshoot = best_duration - slot_target_duration
        retry_overshoot = retry_duration - slot_target_duration
        is_better = False
        if retry_overshoot <= tolerance and best_overshoot > tolerance:
            is_better = True
        elif abs(retry_overshoot) < abs(best_overshoot):
            is_better = True
        elif retry_duration < best_duration and retry_overshoot > tolerance:
            is_better = True

        if is_better:
            if best_path != output_wav and best_path.exists():
                best_path.unlink(missing_ok=True)
            best_path = retry_wav
            best_duration = retry_duration
        else:
            retry_wav.unlink(missing_ok=True)

    if best_path != output_wav and best_path.exists():
        if output_wav.exists():
            output_wav.unlink(missing_ok=True)
        best_path.replace(output_wav)
    return best_duration, retry_passes


def _build_atempo_filter_chain(tempo_factor: float) -> str:
    if tempo_factor <= 0.0:
        raise ValueError("Tempo factor must be > 0.")
    factors: list[float] = []
    remaining = float(tempo_factor)
    while remaining > 2.0 + 1e-9:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5 - 1e-9:
        factors.append(0.5)
        remaining /= 0.5
    remaining = max(0.5, min(2.0, remaining))
    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def _tempo_fit_wav_to_duration(
    *,
    ffmpeg_bin: str,
    wav_path: Path,
    target_duration: float,
    tolerance_seconds: float,
) -> float:
    if target_duration <= 0.0:
        return _wav_duration_seconds(wav_path)

    with wave.open(str(wav_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()

    current_duration = _wav_duration_seconds(wav_path)
    if current_duration <= 0.0:
        return current_duration
    if current_duration <= target_duration + max(0.0, tolerance_seconds):
        return current_duration

    tempo_factor = current_duration / target_duration
    if tempo_factor <= 1.0:
        return current_duration

    temp_output = wav_path.with_name(f"{wav_path.stem}.tempofit.wav")
    if temp_output.exists():
        temp_output.unlink()

    command = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(wav_path),
        "-vn",
        "-filter:a",
        _build_atempo_filter_chain(tempo_factor),
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(temp_output),
    ]
    timeout_seconds = max(30.0, min(300.0, current_duration * 20.0))
    try:
        run_command(command, timeout_seconds=timeout_seconds)
    except CommandExecutionError:
        if temp_output.exists():
            temp_output.unlink(missing_ok=True)
        return current_duration

    if not temp_output.exists():
        return current_duration
    temp_output.replace(wav_path)
    return _wav_duration_seconds(wav_path)


def _trim_wav_to_duration(wav_path: Path, target_duration: float) -> float:
    with wave.open(str(wav_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        raw_frames = wav_file.readframes(frame_count)
        comp_type = wav_file.getcomptype()
        comp_name = wav_file.getcompname()
    if sample_rate <= 0:
        return 0.0
    current_duration = frame_count / sample_rate
    if target_duration >= current_duration:
        return current_duration
    target_frames = int(round(target_duration * sample_rate))
    target_frames = max(1, target_frames)
    if target_frames >= frame_count:
        return current_duration
    bytes_per_frame = sample_width * channels
    trimmed_frames = raw_frames[: target_frames * bytes_per_frame]
    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.setcomptype(comp_type, comp_name)
        wav_file.writeframes(trimmed_frames)
    return target_frames / sample_rate


def _trim_wav_to_duration_energy_aware(
    wav_path: Path,
    target_duration: float,
    *,
    lookback_ms: int,
) -> tuple[float, bool]:
    with wave.open(str(wav_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        raw_frames = wav_file.readframes(frame_count)
        comp_type = wav_file.getcomptype()
        comp_name = wav_file.getcompname()
    if sample_rate <= 0:
        return 0.0, False
    current_duration = frame_count / sample_rate
    if target_duration >= current_duration:
        return current_duration, False
    if channels != 1 or sample_width != 2 or lookback_ms <= 0:
        return _trim_wav_to_duration(wav_path, target_duration), False

    target_frame = max(1, min(frame_count, int(round(target_duration * sample_rate))))
    lookback_frames = max(1, int(round(sample_rate * (lookback_ms / 1000.0))))
    search_start = max(1, target_frame - lookback_frames)
    search_end = min(frame_count - 1, target_frame)
    samples = [value[0] for value in struct.iter_unpack("<h", raw_frames)]
    if not samples:
        return _trim_wav_to_duration(wav_path, target_duration), False

    best_cut_frame = target_frame
    best_score: tuple[int, int, int] | None = None
    for frame_index in range(search_start, search_end + 1):
        current = samples[frame_index]
        previous = samples[frame_index - 1]
        zero_crossing = int(not ((previous <= 0 < current) or (previous >= 0 > current)))
        amplitude = abs(current)
        distance = abs(target_frame - frame_index)
        score = (zero_crossing, amplitude, distance)
        if best_score is None or score < best_score:
            best_score = score
            best_cut_frame = frame_index

    best_cut_frame = max(1, min(frame_count, best_cut_frame))
    bytes_per_frame = sample_width * channels
    trimmed_frames = raw_frames[: best_cut_frame * bytes_per_frame]
    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.setcomptype(comp_type, comp_name)
        wav_file.writeframes(trimmed_frames)
    return best_cut_frame / sample_rate, True


def _schedule_playback_windows(
    *,
    input_doc: Any,
    synthesized_durations: list[float],
    config: AppConfig,
) -> tuple[list[float], list[float], dict[str, float | int]]:
    scheduled_starts: list[float] = []
    scheduled_ends: list[float] = []
    start_delay_applied_segments = 0
    total_start_delay_seconds = 0.0
    max_start_delay_seconds = 0.0
    residual_collision_count = 0
    residual_collision_max_seconds = 0.0
    if not input_doc.segments:
        return scheduled_starts, scheduled_ends, {
            "start_delay_applied_segments": 0,
            "total_start_delay_seconds": 0.0,
            "max_start_delay_seconds": 0.0,
            "residual_boundary_collision_count": 0,
            "residual_boundary_collision_max_seconds": 0.0,
        }

    prev_end = 0.0
    for index, (segment, duration) in enumerate(zip(input_doc.segments, synthesized_durations, strict=True)):
        canonical_start = float(segment.start)
        left_gap_budget = (
            min(
                max(0.0, float(config.tts.boundary_max_gap_borrow_seconds)),
                _boundary_hint_float(segment, "can_borrow_left_gap_seconds"),
            )
            if config.tts.boundary_stabilization_enabled
            else 0.0
        )
        overshoot = max(0.0, float(duration) - float(segment.duration))
        applied_advance = 0.0
        if config.tts.boundary_stabilization_enabled and index > 0 and left_gap_budget > 0.0 and overshoot > 0.0:
            free_left_space = max(0.0, canonical_start - prev_end)
            applied_advance = min(overshoot, left_gap_budget, free_left_space)

        proposed_start = canonical_start - applied_advance
        collision = max(0.0, prev_end - proposed_start) if index > 0 else 0.0
        allowed_delay = (
            max(0.0, float(config.tts.boundary_max_start_delay_seconds))
            if config.tts.boundary_stabilization_enabled
            else 0.0
        )
        applied_delay = min(collision, allowed_delay)
        if applied_delay > 1e-9:
            start_delay_applied_segments += 1
            total_start_delay_seconds += applied_delay
            max_start_delay_seconds = max(max_start_delay_seconds, applied_delay)

        scheduled_start = proposed_start + applied_delay
        residual_collision = max(0.0, prev_end - scheduled_start) if index > 0 else 0.0
        if residual_collision > 1e-6:
            residual_collision_count += 1
            residual_collision_max_seconds = max(residual_collision_max_seconds, residual_collision)
        scheduled_end = scheduled_start + float(duration)
        scheduled_starts.append(scheduled_start)
        scheduled_ends.append(scheduled_end)
        prev_end = scheduled_end

    return scheduled_starts, scheduled_ends, {
        "start_delay_applied_segments": start_delay_applied_segments,
        "total_start_delay_seconds": total_start_delay_seconds,
        "max_start_delay_seconds": max_start_delay_seconds,
        "residual_boundary_collision_count": residual_collision_count,
        "residual_boundary_collision_max_seconds": residual_collision_max_seconds,
    }


def _apply_fade_envelope(
    samples: list[int],
    *,
    fade_in_samples: int,
    fade_out_samples: int,
) -> list[int]:
    if not samples:
        return samples
    adjusted = list(samples)
    fade_in_count = max(0, min(len(adjusted), fade_in_samples))
    fade_out_count = max(0, min(len(adjusted), fade_out_samples))
    for index in range(fade_in_count):
        gain = (index + 1) / max(1, fade_in_count)
        adjusted[index] = int(adjusted[index] * gain)
    for offset in range(fade_out_count):
        index = len(adjusted) - fade_out_count + offset
        gain = (fade_out_count - offset) / max(1, fade_out_count)
        adjusted[index] = int(adjusted[index] * gain)
    return adjusted


def _build_stitched_preview_wav(
    *,
    output_doc: TTSOutputDocument,
    preview_wav_path: Path,
    config: AppConfig | None = None,
) -> tuple[Path, dict[str, int]]:
    mixed: list[int] = []
    detected_sample_rate: int | None = None
    crossfade_applied_boundaries = 0
    previous_end_frame: int | None = None
    for segment in output_doc.segments:
        audio_path = Path(segment.audio_path)
        sample_rate, samples = _read_wav_mono_pcm16(audio_path)
        if detected_sample_rate is None:
            detected_sample_rate = sample_rate
        elif sample_rate != detected_sample_rate:
            raise ValueError(
                "All segment WAV files must share the same sample rate for preview stitching."
            )

        fade_in_ms = int(getattr(config.tts, "boundary_fade_in_ms", 0)) if config else 0
        fade_out_ms = int(getattr(config.tts, "boundary_fade_out_ms", 0)) if config else 0
        if config and config.tts.boundary_stabilization_enabled:
            fade_in_samples = int(round(sample_rate * max(0, fade_in_ms) / 1000.0))
            fade_out_samples = int(round(sample_rate * max(0, fade_out_ms) / 1000.0))
            samples = _apply_fade_envelope(
                samples,
                fade_in_samples=fade_in_samples,
                fade_out_samples=fade_out_samples,
            )
        scheduled_start = segment.scheduled_start if segment.scheduled_start is not None else segment.start
        start_frame = max(0, int(round(float(scheduled_start) * sample_rate)))
        crossfade_frames = 0
        if previous_end_frame is not None and start_frame < previous_end_frame:
            crossfade_limit_ms = int(getattr(config.tts, "boundary_crossfade_ms", 0)) if config else 0
            overlap_frames = previous_end_frame - start_frame
            overlap_limit = int(round(sample_rate * max(0, crossfade_limit_ms) / 1000.0))
            if overlap_frames > 0 and (overlap_limit <= 0 or overlap_frames <= overlap_limit):
                crossfade_applied_boundaries += 1
                crossfade_frames = overlap_frames
        end_frame = start_frame + len(samples)
        if end_frame > len(mixed):
            mixed.extend([0] * (end_frame - len(mixed)))
        for index, sample in enumerate(samples):
            mixed_index = start_frame + index
            if crossfade_frames > 0 and index < crossfade_frames:
                fade_in = (index + 1) / max(1, crossfade_frames)
                fade_out = 1.0 - fade_in
                mixed[mixed_index] = int((mixed[mixed_index] * fade_out) + (sample * fade_in))
            else:
                mixed[mixed_index] += sample
        previous_end_frame = end_frame

    if detected_sample_rate is None:
        detected_sample_rate = 24000
    if not mixed:
        mixed = [0]
    _write_wav_mono_pcm16(preview_wav_path, detected_sample_rate, mixed)
    return preview_wav_path, {
        "crossfade_applied_boundaries": crossfade_applied_boundaries,
    }


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
    fit_strategies: list[str] = []
    duration_padding_applied = 0
    total_padded_seconds = 0.0
    duration_trim_applied = 0
    total_trimmed_seconds = 0.0
    duration_tempofit_applied = 0
    total_tempofit_adjusted_seconds = 0.0
    energy_trim_applied_segments = 0
    total_energy_trimmed_seconds = 0.0
    hard_trim_fallback_segments = 0
    retry_applied_segments = 0
    retry_total_passes = 0
    gap_borrow_applied_segments = 0
    total_gap_borrowed_seconds = 0.0
    duration_tolerance = max(0.0, float(config.tts.max_duration_delta_seconds))
    for segment in input_doc.segments:
        output_wav = segment_audio_dir / f"seg_{segment.id:06d}.wav"
        synthesized_duration = backend.synthesize_to_wav(
            text=segment.target_text,
            output_wav=output_wav,
            target_duration=segment.duration,
            sample_rate=config.tts.sample_rate,
        )
        slot_target_duration, _gap_borrow_budget = _choose_effective_slot_duration(
            segment=segment,
            config=config,
            synthesized_duration=synthesized_duration,
        )
        fit_strategy = "none"
        retry_duration, retry_passes = _synthesize_with_retry(
            backend=backend,
            segment=segment,
            output_wav=output_wav,
            sample_rate=config.tts.sample_rate,
            slot_target_duration=slot_target_duration,
            config=config,
            initial_duration=synthesized_duration,
        )
        if retry_passes > 0:
            retry_total_passes += retry_passes
            if abs(retry_duration - synthesized_duration) > 1e-6:
                retry_applied_segments += 1
                fit_strategy = "retry"
            synthesized_duration = retry_duration

        fit_target_duration = max(float(segment.duration), float(slot_target_duration))
        duration_delta = synthesized_duration - segment.duration
        if duration_delta < -duration_tolerance:
            padded_duration = _pad_wav_silence_to_duration(output_wav, segment.duration)
            if padded_duration > synthesized_duration:
                duration_padding_applied += 1
                total_padded_seconds += padded_duration - synthesized_duration
                synthesized_duration = padded_duration
        elif synthesized_duration > fit_target_duration + duration_tolerance:
            tempofit_duration = _tempo_fit_wav_to_duration(
                ffmpeg_bin=config.tools.ffmpeg,
                wav_path=output_wav,
                target_duration=fit_target_duration,
                tolerance_seconds=duration_tolerance,
            )
            if tempofit_duration < synthesized_duration:
                duration_tempofit_applied += 1
                total_tempofit_adjusted_seconds += synthesized_duration - tempofit_duration
                synthesized_duration = tempofit_duration
                fit_strategy = "tempo_fit"

            if (
                config.tts.boundary_stabilization_enabled
                and config.tts.boundary_energy_trim_enabled
                and (synthesized_duration - fit_target_duration) > duration_tolerance
            ):
                energy_trim_duration, _energy_used = _trim_wav_to_duration_energy_aware(
                    output_wav,
                    fit_target_duration,
                    lookback_ms=config.tts.boundary_energy_trim_lookback_ms,
                )
                if energy_trim_duration < synthesized_duration:
                    energy_trim_applied_segments += 1
                    total_energy_trimmed_seconds += synthesized_duration - energy_trim_duration
                    synthesized_duration = energy_trim_duration
                    fit_strategy = "energy_trim"

            if (
                config.tts.boundary_hard_trim_fallback_enabled
                and (synthesized_duration - fit_target_duration) > duration_tolerance
            ):
                trimmed_duration = _trim_wav_to_duration(output_wav, fit_target_duration)
                if trimmed_duration < synthesized_duration:
                    duration_trim_applied += 1
                    total_trimmed_seconds += synthesized_duration - trimmed_duration
                    synthesized_duration = trimmed_duration
                    hard_trim_fallback_segments += 1
                    fit_strategy = "hard_trim"

        borrowed_used_seconds = 0.0
        if fit_target_duration > float(segment.duration) + 1e-9:
            borrowed_used_seconds = min(
                fit_target_duration - float(segment.duration),
                max(0.0, synthesized_duration - float(segment.duration)),
            )
            if borrowed_used_seconds > 1e-9:
                gap_borrow_applied_segments += 1
                total_gap_borrowed_seconds += borrowed_used_seconds

        segment_audio_paths.append(output_wav)
        synthesized_durations.append(synthesized_duration)
        fit_strategies.append(fit_strategy)
    synth_seconds = perf_counter() - synth_start

    schedule_start = perf_counter()
    scheduled_starts, scheduled_ends, schedule_metrics = _schedule_playback_windows(
        input_doc=input_doc,
        synthesized_durations=synthesized_durations,
        config=config,
    )
    schedule_seconds = perf_counter() - schedule_start

    stabilization_applied_flags = [
        (
            fit_strategy != "none"
            or abs(scheduled_start_value - float(segment.start)) > 1e-6
        )
        for segment, fit_strategy, scheduled_start_value in zip(
            input_doc.segments, fit_strategies, scheduled_starts, strict=True
        )
    ]

    build_output_start = perf_counter()
    output_doc = build_tts_output_document(
        input_doc=input_doc,
        backend=backend.name,
        sample_rate=config.tts.sample_rate,
        segment_audio_paths=segment_audio_paths,
        synthesized_durations=synthesized_durations,
        scheduled_starts=scheduled_starts,
        scheduled_ends=scheduled_ends,
        stabilization_applied_flags=stabilization_applied_flags,
        fit_strategies=fit_strategies,
    )
    build_output_seconds = perf_counter() - build_output_start

    stitch_start = perf_counter()
    stitched_preview_wav = output_json_path.parent / f"tts_preview_stitched.{output_doc.language}.wav"
    stitched_preview_wav, stitch_metrics = _build_stitched_preview_wav(
        output_doc=output_doc,
        preview_wav_path=stitched_preview_wav,
        config=config,
    )
    stitch_seconds = perf_counter() - stitch_start

    stabilization_metrics = {
        "retry_applied_segments": retry_applied_segments,
        "retry_total_passes": retry_total_passes,
        "gap_borrow_applied_segments": gap_borrow_applied_segments,
        "total_gap_borrowed_seconds": total_gap_borrowed_seconds,
        "start_delay_applied_segments": int(schedule_metrics["start_delay_applied_segments"]),
        "total_start_delay_seconds": float(schedule_metrics["total_start_delay_seconds"]),
        "max_start_delay_seconds": float(schedule_metrics["max_start_delay_seconds"]),
        "crossfade_applied_boundaries": int(stitch_metrics.get("crossfade_applied_boundaries", 0)),
        "energy_trim_applied_segments": energy_trim_applied_segments,
        "total_energy_trimmed_seconds": total_energy_trimmed_seconds,
        "hard_trim_fallback_segments": hard_trim_fallback_segments,
        "residual_boundary_collision_count": int(schedule_metrics["residual_boundary_collision_count"]),
        "residual_boundary_collision_max_seconds": float(schedule_metrics["residual_boundary_collision_max_seconds"]),
    }

    qa_start = perf_counter()
    qa_report = build_m3_qa_report(
        output_doc,
        config.tts,
        postfit_padding_segments=duration_padding_applied,
        postfit_trim_segments=duration_trim_applied,
        postfit_total_padded_seconds=total_padded_seconds,
        postfit_total_trimmed_seconds=total_trimmed_seconds,
        stabilization_metrics=stabilization_metrics,
    )
    qa_seconds = perf_counter() - qa_start

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    qa_report_json_path.parent.mkdir(parents=True, exist_ok=True)
    run_manifest_json_path.parent.mkdir(parents=True, exist_ok=True)
    write_start = perf_counter()
    write_json(output_json_path, output_doc.to_dict())
    write_json(qa_report_json_path, qa_report)
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
                "schedule_playback_windows": schedule_seconds,
                "build_output_contract": build_output_seconds,
                "build_stitched_preview": stitch_seconds,
                "build_qa_report": qa_seconds,
                "write_outputs": write_seconds,
                "total_pipeline": total_seconds,
            },
            "duration_postfit": {
                "silence_padding_applied_segments": duration_padding_applied,
                "total_padded_seconds": total_padded_seconds,
                "tempo_fit_applied_segments": duration_tempofit_applied,
                "total_tempo_fit_adjusted_seconds": total_tempofit_adjusted_seconds,
                "energy_trim_applied_segments": energy_trim_applied_segments,
                "total_energy_trimmed_seconds": total_energy_trimmed_seconds,
                "trim_applied_segments": duration_trim_applied,
                "total_trimmed_seconds": total_trimmed_seconds,
            },
            "stabilization": stabilization_metrics,
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
