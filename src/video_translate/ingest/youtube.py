from __future__ import annotations

from pathlib import Path

from video_translate.models import DownloadResult
from video_translate.utils.subprocess_utils import CommandExecutionError, run_command

SUPPORTED_VIDEO_HEIGHT_OPTIONS = (480, 720, 1080, 1440, 2160)


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
    write_info_json: bool = True,
    skip_download: bool = False,
    write_subtitles: bool = False,
    write_auto_subtitles: bool = False,
    subtitle_languages: tuple[str, ...] | list[str] | None = None,
    subtitle_format: str | None = None,
    convert_subtitles_to: str | None = None,
) -> list[str]:
    validated_height = _validate_max_video_height(max_video_height)
    command = [
        yt_dlp_bin,
        "--no-playlist",
        "--no-progress",
    ]
    if write_info_json:
        command.append("--write-info-json")
    if skip_download:
        command.append("--skip-download")
    if write_subtitles:
        command.append("--write-subs")
    if write_auto_subtitles:
        command.append("--write-auto-subs")
    normalized_subtitle_languages = [
        str(item).strip()
        for item in (subtitle_languages or [])
        if str(item).strip()
    ]
    if normalized_subtitle_languages:
        command.extend(["--sub-langs", ",".join(normalized_subtitle_languages)])
    if subtitle_format:
        command.extend(["--sub-format", str(subtitle_format).strip()])
    if convert_subtitles_to:
        command.extend(["--convert-subs", str(convert_subtitles_to).strip()])
    command.extend(["--output", str(output_template)])
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


def _discover_downloaded_subtitles(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    return sorted(
        [
            p
            for p in output_dir.rglob("*")
            if p.is_file()
            and p.suffix.lower() in {".vtt", ".srt"}
            and not p.name.endswith(".part")
            and not p.name.endswith(".ytdl")
        ]
    )


def download_youtube_subtitles(
    *,
    url: str,
    output_dir: Path,
    yt_dlp_bin: str,
    timeout_seconds: float | None = 600.0,
    languages: tuple[str, ...] = ("en", "en-*"),
    subtitle_format: str = "vtt",
    allow_auto_subtitles: bool = True,
) -> dict[str, Path | list[Path] | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manual_dir = output_dir / "manual"
    auto_dir = output_dir / "auto"
    manual_dir.mkdir(parents=True, exist_ok=True)
    auto_dir.mkdir(parents=True, exist_ok=True)

    manual_error: str | None = None
    auto_error: str | None = None
    try:
        run_command(
            build_yt_dlp_command(
                yt_dlp_bin=yt_dlp_bin,
                url=url,
                output_template=manual_dir / "source.%(ext)s",
                write_info_json=False,
                skip_download=True,
                write_subtitles=True,
                write_auto_subtitles=False,
                subtitle_languages=languages,
                subtitle_format=subtitle_format,
            ),
            timeout_seconds=timeout_seconds,
        )
    except CommandExecutionError as exc:
        manual_error = str(exc)
    if allow_auto_subtitles:
        try:
            run_command(
                build_yt_dlp_command(
                    yt_dlp_bin=yt_dlp_bin,
                    url=url,
                    output_template=auto_dir / "source.%(ext)s",
                    write_info_json=False,
                    skip_download=True,
                    write_subtitles=False,
                    write_auto_subtitles=True,
                    subtitle_languages=languages,
                    subtitle_format=subtitle_format,
                ),
                timeout_seconds=timeout_seconds,
            )
        except CommandExecutionError as exc:
            auto_error = str(exc)

    manual_files = _discover_downloaded_subtitles(manual_dir)
    auto_files = _discover_downloaded_subtitles(auto_dir)
    # Prefer English-specific files first when multiple variants exist.
    def _rank_sub(path: Path) -> tuple[int, int, str]:
        name = path.name.lower()
        score = 0
        if ".en" in name or name.startswith("en."):
            score -= 5
        if ".orig" in name:
            score += 1
        return (score, len(name), name)

    manual_selected = sorted(manual_files, key=_rank_sub)[0] if manual_files else None
    auto_selected = sorted(auto_files, key=_rank_sub)[0] if auto_files else None
    return {
        "manual": manual_selected,
        "auto": auto_selected,
        "manual_candidates": manual_files,
        "auto_candidates": auto_files,
        "manual_error": manual_error,
        "auto_error": auto_error,
    }


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
