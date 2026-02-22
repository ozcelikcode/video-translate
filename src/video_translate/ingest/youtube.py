from __future__ import annotations

from pathlib import Path

from video_translate.models import DownloadResult
from video_translate.utils.subprocess_utils import run_command

SUPPORTED_VIDEO_HEIGHT_OPTIONS = (720, 1080, 1440, 2160)


def _validate_max_video_height(max_video_height: int | None) -> int | None:
    if max_video_height is None:
        return None
    normalized = int(max_video_height)
    if normalized not in SUPPORTED_VIDEO_HEIGHT_OPTIONS:
        supported = ", ".join(str(value) for value in SUPPORTED_VIDEO_HEIGHT_OPTIONS)
        raise ValueError(
            f"Unsupported YouTube video height '{normalized}'. Supported values: {supported}."
        )
    return normalized


def build_yt_dlp_command(
    yt_dlp_bin: str,
    url: str,
    output_template: Path,
    *,
    max_video_height: int | None = None,
) -> list[str]:
    validated_height = _validate_max_video_height(max_video_height)
    command = [
        yt_dlp_bin,
        "--no-playlist",
        "--no-progress",
        "--write-info-json",
        "--output",
        str(output_template),
    ]
    if validated_height is not None:
        command.extend(
            [
                "--format",
                f"bestvideo*[height<={validated_height}]+bestaudio/best[height<={validated_height}]",
            ]
        )
    command.append(url)
    return command


def _discover_downloaded_media(input_dir: Path) -> Path:
    candidates = [
        p
        for p in input_dir.iterdir()
        if p.is_file()
        and not p.name.endswith(".part")
        and not p.name.endswith(".ytdl")
        and p.suffix not in {".json", ".description", ".txt"}
    ]
    if not candidates:
        raise FileNotFoundError(f"No media file found in {input_dir}")
    return max(candidates, key=lambda p: p.stat().st_size)


def download_youtube_source(
    url: str,
    output_dir: Path,
    yt_dlp_bin: str,
    timeout_seconds: float | None = 3600.0,
    max_video_height: int | None = None,
) -> DownloadResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = output_dir / "source.%(ext)s"
    command = build_yt_dlp_command(
        yt_dlp_bin=yt_dlp_bin,
        url=url,
        output_template=output_template,
        max_video_height=max_video_height,
    )
    run_command(command, timeout_seconds=timeout_seconds)

    media_path = _discover_downloaded_media(output_dir)
    info_json_path = output_dir / "source.info.json"
    return DownloadResult(
        source_url=url,
        media_path=media_path,
        info_json_path=info_json_path if info_json_path.exists() else None,
    )
