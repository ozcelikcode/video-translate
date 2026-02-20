from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_translate.io import write_json
from video_translate.utils.subprocess_utils import run_command

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class FinalDeliveryArtifacts:
    downloads_dir: Path
    dubbed_video_mp4: Path
    quality_summary_json: Path
    cleanup_performed: bool


def build_video_merge_command(
    *,
    ffmpeg_bin: str,
    source_video: Path,
    dubbed_audio: Path,
    output_mp4: Path,
) -> list[str]:
    # Keep original timeline and pad dubbed audio when needed, then render mp4.
    return [
        ffmpeg_bin,
        "-y",
        "-i",
        str(source_video),
        "-i",
        str(dubbed_audio),
        "-filter_complex",
        "[1:a]apad[aud]",
        "-map",
        "0:v:0",
        "-map",
        "[aud]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(output_mp4),
    ]


def _read_json_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return payload


def _extract_quality_flags(payload: dict[str, Any] | None) -> list[str]:
    if payload is None:
        return []
    raw = payload.get("quality_flags", [])
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw]


def _build_quality_summary(
    *,
    run_root: Path,
    target_lang: str,
    dubbed_video_mp4: Path,
) -> dict[str, Any]:
    m1_report = _read_json_optional(run_root / "output" / "qa" / "m1_qa_report.json")
    m2_report = _read_json_optional(run_root / "output" / "qa" / "m2_qa_report.json")
    m3_report = _read_json_optional(run_root / "output" / "qa" / "m3_qa_report.json")
    m1_flags = _extract_quality_flags(m1_report)
    m2_flags = _extract_quality_flags(m2_report)
    m3_flags = _extract_quality_flags(m3_report)
    return {
        "stage": "final_delivery",
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "run_id": run_root.name,
        "target_language": target_lang,
        "final_video_mp4": str(dubbed_video_mp4),
        "qa": {
            "overall_passed": not (m1_flags or m2_flags or m3_flags),
            "m1_quality_flags": m1_flags,
            "m2_quality_flags": m2_flags,
            "m3_quality_flags": m3_flags,
        },
    }


def _resolve_downloads_root(downloads_root: Path) -> Path:
    if downloads_root.is_absolute():
        resolved = downloads_root.resolve()
    else:
        resolved = (PROJECT_ROOT / downloads_root).resolve()
    if resolved != PROJECT_ROOT and PROJECT_ROOT not in resolved.parents:
        raise ValueError("downloads_root must stay under project root.")
    return resolved


def cleanup_run_workspace(run_root: Path) -> None:
    resolved = run_root.resolve()
    marker_paths = (
        resolved / "run_manifest.json",
        resolved / "run_m2_manifest.json",
        resolved / "run_m3_manifest.json",
    )
    if not any(marker.exists() for marker in marker_paths):
        raise ValueError(f"Refusing cleanup. Run markers not found: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def deliver_final_video(
    *,
    run_root: Path,
    source_video: Path,
    dubbed_audio: Path,
    ffmpeg_bin: str,
    target_lang: str,
    downloads_root: Path = Path("downloads"),
    cleanup_intermediate: bool = True,
) -> FinalDeliveryArtifacts:
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")
    if not source_video.exists():
        raise FileNotFoundError(f"Source video not found: {source_video}")
    if not dubbed_audio.exists():
        raise FileNotFoundError(f"Dubbed audio not found: {dubbed_audio}")

    resolved_downloads_root = _resolve_downloads_root(downloads_root)
    downloads_dir = resolved_downloads_root / run_root.name
    downloads_dir.mkdir(parents=True, exist_ok=True)
    dubbed_video_mp4 = downloads_dir / f"video_dubbed.{target_lang}.mp4"
    command = build_video_merge_command(
        ffmpeg_bin=ffmpeg_bin,
        source_video=source_video,
        dubbed_audio=dubbed_audio,
        output_mp4=dubbed_video_mp4,
    )
    run_command(command)
    if not dubbed_video_mp4.exists():
        raise FileNotFoundError(f"Final dubbed video was not created: {dubbed_video_mp4}")

    quality_summary_json = downloads_dir / f"quality_summary.{target_lang}.json"
    summary_payload = _build_quality_summary(
        run_root=run_root,
        target_lang=target_lang,
        dubbed_video_mp4=dubbed_video_mp4,
    )
    write_json(quality_summary_json, summary_payload)

    if cleanup_intermediate:
        cleanup_run_workspace(run_root)

    return FinalDeliveryArtifacts(
        downloads_dir=downloads_dir,
        dubbed_video_mp4=dubbed_video_mp4,
        quality_summary_json=quality_summary_json,
        cleanup_performed=cleanup_intermediate,
    )
