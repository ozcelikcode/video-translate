from __future__ import annotations

from pathlib import Path

from video_translate.models import DownloadResult
from video_translate.utils.subprocess_utils import run_command


def build_yt_dlp_command(yt_dlp_bin: str, url: str, output_template: Path) -> list[str]:
    return [
        yt_dlp_bin,
        "--no-playlist",
        "--no-progress",
        "--write-info-json",
        "--output",
        str(output_template),
        url,
    ]


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


def download_youtube_source(url: str, output_dir: Path, yt_dlp_bin: str) -> DownloadResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = output_dir / "source.%(ext)s"
    command = build_yt_dlp_command(yt_dlp_bin=yt_dlp_bin, url=url, output_template=output_template)
    run_command(command)

    media_path = _discover_downloaded_media(output_dir)
    info_json_path = output_dir / "source.info.json"
    return DownloadResult(
        source_url=url,
        media_path=media_path,
        info_json_path=info_json_path if info_json_path.exists() else None,
    )

