from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from video_translate.asr.whisper import transcribe_audio
from video_translate.config import AppConfig
from video_translate.ingest.audio import normalize_audio_for_asr
from video_translate.ingest.youtube import download_youtube_source
from video_translate.io import create_run_paths, write_json, write_srt, write_transcript_json
from video_translate.models import M1Artifacts
from video_translate.preflight import PreflightReport
from video_translate.qa.m1_report import build_m1_qa_report

M1ProgressHook = Callable[[str], None]


def _build_run_manifest(
    *,
    source_url: str,
    config: AppConfig,
    artifacts: M1Artifacts,
    preflight_report: PreflightReport | None,
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "stage": "m1",
        "created_at_utc": datetime.now(tz=UTC).isoformat(),
        "source_url": source_url,
        "config": {
            "tools": asdict(config.tools),
            "pipeline": {
                "workspace_dir": str(config.pipeline.workspace_dir),
                "audio_sample_rate": config.pipeline.audio_sample_rate,
                "audio_channels": config.pipeline.audio_channels,
                "audio_codec": config.pipeline.audio_codec,
            },
            "asr": asdict(config.asr),
        },
        "artifacts": {
            "run_root": str(artifacts.run_root),
            "source_media": str(artifacts.source_media),
            "normalized_audio": str(artifacts.normalized_audio),
            "transcript_json": str(artifacts.transcript_json),
            "transcript_srt": str(artifacts.transcript_srt) if artifacts.transcript_srt else None,
            "qa_report": str(artifacts.qa_report),
        },
    }
    if preflight_report is not None:
        manifest["preflight"] = {
            "python_version": preflight_report.python_version,
            "yt_dlp": asdict(preflight_report.yt_dlp),
            "ffmpeg": asdict(preflight_report.ffmpeg),
            "faster_whisper_available": preflight_report.faster_whisper_available,
            "ok": preflight_report.ok,
        }
    return manifest


def run_m1_pipeline(
    *,
    source_url: str,
    config: AppConfig,
    workspace_dir: Path | None = None,
    run_id: str | None = None,
    emit_srt: bool = True,
    preflight_report: PreflightReport | None = None,
    progress_hook: M1ProgressHook | None = None,
) -> M1Artifacts:
    effective_workspace = workspace_dir or config.pipeline.workspace_dir
    paths = create_run_paths(effective_workspace, run_id)

    if progress_hook is not None:
        progress_hook("M1: YouTube indiriliyor...")
    download = download_youtube_source(
        url=source_url,
        output_dir=paths.input_dir,
        yt_dlp_bin=config.tools.yt_dlp,
    )

    if progress_hook is not None:
        progress_hook("M1: Ses normalize ediliyor...")
    normalized_audio = normalize_audio_for_asr(
        ffmpeg_bin=config.tools.ffmpeg,
        input_media=download.media_path,
        output_wav=paths.work_audio_dir / "source_16k_mono.wav",
        sample_rate=config.pipeline.audio_sample_rate,
        channels=config.pipeline.audio_channels,
        codec=config.pipeline.audio_codec,
    )

    if progress_hook is not None:
        progress_hook("M1: ASR basladi (ilk calismada model indirilebilir)...")

    def _on_asr_segment(index: int) -> None:
        if progress_hook is None:
            return
        if index <= 3 or index % 8 == 0:
            progress_hook(f"M1: ASR segment cozuluyor... ({index})")

    transcript_doc = transcribe_audio(
        normalized_audio,
        config.asr,
        on_segment_collected=_on_asr_segment,
    )
    transcript_json = paths.output_transcript_dir / "transcript.en.json"
    if progress_hook is not None:
        progress_hook("M1: Transcript yaziliyor...")
    write_transcript_json(transcript_json, transcript_doc)

    transcript_srt: Path | None = None
    if emit_srt:
        transcript_srt = paths.output_transcript_dir / "transcript.en.srt"
        write_srt(transcript_srt, transcript_doc.segments)

    qa_report = paths.output_qa_dir / "m1_qa_report.json"
    write_json(qa_report, build_m1_qa_report(transcript_doc))
    if progress_hook is not None:
        progress_hook("M1: QA raporu yazildi.")

    run_manifest = paths.root / "run_manifest.json"
    artifacts = M1Artifacts(
        run_root=paths.root,
        source_media=download.media_path,
        normalized_audio=normalized_audio,
        transcript_json=transcript_json,
        transcript_srt=transcript_srt,
        qa_report=qa_report,
        run_manifest=run_manifest,
    )
    write_json(
        run_manifest,
        _build_run_manifest(
            source_url=source_url,
            config=config,
            artifacts=artifacts,
            preflight_report=preflight_report,
        ),
    )
    return artifacts
