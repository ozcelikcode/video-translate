from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from video_translate.asr.whisper import transcribe_audio
from video_translate.config import AppConfig
from video_translate.ingest.audio import normalize_audio_for_asr
from video_translate.ingest.subtitles import build_normalized_subtitle_payload
from video_translate.ingest.youtube import download_youtube_source, download_youtube_subtitles
from video_translate.io import create_run_paths, write_json, write_srt, write_transcript_json
from video_translate.models import M1Artifacts
from video_translate.pipeline.transcript_fusion import fuse_transcript_with_subtitles
from video_translate.preflight import PreflightReport
from video_translate.qa.m1_report import build_m1_qa_report

M1ProgressHook = Callable[[str], None]


def _build_run_manifest(
    *,
    source_url: str,
    config: AppConfig,
    artifacts: M1Artifacts,
    preflight_report: PreflightReport | None,
    requested_max_video_height: int | None = None,
    subtitles_normalized_json: Path | None = None,
    subtitle_summary: dict[str, object] | None = None,
    fusion_summary: dict[str, object] | None = None,
    runtime_diagnostics: dict[str, object] | None = None,
    timings_seconds: dict[str, float] | None = None,
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "stage": "m1",
        "created_at_utc": datetime.now(tz=UTC).isoformat(),
        "source_url": source_url,
        "ingest_options": {
            "requested_max_video_height": requested_max_video_height,
        },
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
            "subtitles_normalized_json": str(subtitles_normalized_json) if subtitles_normalized_json else None,
        },
    }
    if subtitle_summary:
        manifest["subtitle_summary"] = subtitle_summary
    if fusion_summary:
        manifest["fusion_summary"] = fusion_summary
    if runtime_diagnostics:
        manifest["runtime_diagnostics"] = runtime_diagnostics
    if timings_seconds:
        manifest["timings_seconds"] = timings_seconds
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
    max_video_height: int | None = None,
    use_youtube_subtitles: bool = True,
    allow_auto_subtitles: bool = True,
    subtitle_mode: str = "hybrid",
) -> M1Artifacts:
    effective_workspace = workspace_dir or config.pipeline.workspace_dir
    paths = create_run_paths(effective_workspace, run_id)
    stage_timings: dict[str, float] = {}
    subtitles_normalized_json: Path | None = None
    normalized_subtitle_payload: dict[str, object] | None = None

    if progress_hook is not None:
        progress_hook("M1: YouTube indiriliyor...")
    download_start = datetime.now(tz=UTC)
    download = download_youtube_source(
        url=source_url,
        output_dir=paths.input_dir,
        yt_dlp_bin=config.tools.yt_dlp,
        max_video_height=max_video_height,
    )
    stage_timings["download_source"] = (datetime.now(tz=UTC) - download_start).total_seconds()

    if use_youtube_subtitles and getattr(config, "ingest", None) is not None:
        subtitles_cfg = config.ingest.subtitles
        if subtitles_cfg.enabled:
            if progress_hook is not None:
                progress_hook("M1: YouTube altyazilari indiriliyor (varsa)...")
            subtitles_start = datetime.now(tz=UTC)
            subtitle_download_result = download_youtube_subtitles(
                url=source_url,
                output_dir=paths.input_dir / "subtitles",
                yt_dlp_bin=config.tools.yt_dlp,
                languages=subtitles_cfg.languages,
                subtitle_format=subtitles_cfg.format,
                allow_auto_subtitles=allow_auto_subtitles and subtitles_cfg.allow_auto,
            )
            stage_timings["download_subtitles"] = (
                datetime.now(tz=UTC) - subtitles_start
            ).total_seconds()
            manual_path = subtitle_download_result.get("manual")
            auto_path = subtitle_download_result.get("auto")
            normalized_subtitle_payload = build_normalized_subtitle_payload(
                manual_path=manual_path if isinstance(manual_path, Path) else None,
                auto_path=auto_path if isinstance(auto_path, Path) else None,
            )
            subtitles_normalized_json = paths.output_transcript_dir / "subtitles.en.normalized.json"
            write_json(subtitles_normalized_json, normalized_subtitle_payload)

    if progress_hook is not None:
        progress_hook("M1: Ses normalize ediliyor...")
    normalize_start = datetime.now(tz=UTC)
    normalized_audio = normalize_audio_for_asr(
        ffmpeg_bin=config.tools.ffmpeg,
        input_media=download.media_path,
        output_wav=paths.work_audio_dir / "source_16k_mono.wav",
        sample_rate=config.pipeline.audio_sample_rate,
        channels=config.pipeline.audio_channels,
        codec=config.pipeline.audio_codec,
    )
    stage_timings["normalize_audio"] = (datetime.now(tz=UTC) - normalize_start).total_seconds()

    if progress_hook is not None:
        progress_hook("M1: ASR basladi (ilk calismada model indirilebilir)...")

    def _on_asr_segment(index: int) -> None:
        if progress_hook is None:
            return
        if index <= 3 or index % 8 == 0:
            progress_hook(f"M1: ASR segment cozuluyor... ({index})")

    def _on_asr_progress(msg: str) -> None:
        if progress_hook is not None:
            progress_hook(msg)

    asr_start = datetime.now(tz=UTC)
    transcript_doc = transcribe_audio(
        normalized_audio,
        config.asr,
        on_segment_collected=_on_asr_segment,
        on_progress=_on_asr_progress,
    )
    stage_timings["asr_transcribe"] = (datetime.now(tz=UTC) - asr_start).total_seconds()

    if normalized_subtitle_payload is not None:
        if progress_hook is not None:
            progress_hook("M1: ASR + altyazi hibrit transcript birlestiriliyor...")
        manual_payload = normalized_subtitle_payload.get("manual", {})
        auto_payload = normalized_subtitle_payload.get("auto", {})
        manual_cues = manual_payload.get("cues", []) if isinstance(manual_payload, dict) else []
        auto_cues = auto_payload.get("cues", []) if isinstance(auto_payload, dict) else []
        if not isinstance(manual_cues, list):
            manual_cues = []
        if not isinstance(auto_cues, list):
            auto_cues = []
        transcript_doc = fuse_transcript_with_subtitles(
            transcript=transcript_doc,
            manual_cues=manual_cues,
            auto_cues=auto_cues,
            subtitle_mode=subtitle_mode,
            use_subtitles=use_youtube_subtitles,
            allow_auto_subtitles=allow_auto_subtitles,
        )
    transcript_json = paths.output_transcript_dir / "transcript.en.json"
    if progress_hook is not None:
        progress_hook("M1: Transcript yaziliyor...")
    transcript_write_start = datetime.now(tz=UTC)
    write_transcript_json(transcript_json, transcript_doc)
    stage_timings["write_transcript_json"] = (
        datetime.now(tz=UTC) - transcript_write_start
    ).total_seconds()

    transcript_srt: Path | None = None
    if emit_srt:
        srt_start = datetime.now(tz=UTC)
        transcript_srt = paths.output_transcript_dir / "transcript.en.srt"
        write_srt(transcript_srt, transcript_doc.segments)
        stage_timings["write_transcript_srt"] = (datetime.now(tz=UTC) - srt_start).total_seconds()

    qa_report = paths.output_qa_dir / "m1_qa_report.json"
    qa_start = datetime.now(tz=UTC)
    write_json(qa_report, build_m1_qa_report(transcript_doc))
    stage_timings["write_qa_report"] = (datetime.now(tz=UTC) - qa_start).total_seconds()
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
            requested_max_video_height=max_video_height,
            subtitles_normalized_json=subtitles_normalized_json,
            subtitle_summary=(
                transcript_doc.subtitle_summary if isinstance(transcript_doc.subtitle_summary, dict) else None
            ),
            fusion_summary=(
                transcript_doc.fusion_summary if isinstance(transcript_doc.fusion_summary, dict) else None
            ),
            runtime_diagnostics=(
                transcript_doc.runtime_diagnostics if isinstance(transcript_doc.runtime_diagnostics, dict) else None
            ),
            timings_seconds=stage_timings,
        ),
    )
    return artifacts
