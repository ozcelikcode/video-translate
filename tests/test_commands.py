from pathlib import Path

import pytest

from video_translate.ingest.audio import build_ffmpeg_normalize_command
from video_translate.ingest.youtube import build_yt_dlp_command


def test_build_yt_dlp_command_contains_expected_flags() -> None:
    command = build_yt_dlp_command(
        yt_dlp_bin="yt-dlp",
        url="https://example.com/video",
        output_template=Path("runs/test/source.%(ext)s"),
    )
    assert command[:5] == ["yt-dlp", "--no-playlist", "--no-progress", "--write-info-json", "--output"]
    assert command[-1] == "https://example.com/video"


def test_build_yt_dlp_command_with_resolution_cap_adds_format_filter() -> None:
    command = build_yt_dlp_command(
        yt_dlp_bin="yt-dlp",
        url="https://example.com/video",
        output_template=Path("runs/test/source.%(ext)s"),
        max_video_height=1080,
    )
    assert "--format" in command
    format_index = command.index("--format")
    assert "height<=1080" in command[format_index + 1]


def test_build_yt_dlp_command_rejects_unsupported_resolution() -> None:
    with pytest.raises(ValueError, match="Unsupported YouTube video height"):
        build_yt_dlp_command(
            yt_dlp_bin="yt-dlp",
            url="https://example.com/video",
            output_template=Path("runs/test/source.%(ext)s"),
            max_video_height=999,
        )


def test_build_ffmpeg_normalize_command_structure() -> None:
    command = build_ffmpeg_normalize_command(
        ffmpeg_bin="ffmpeg",
        input_media=Path("input/source.mp4"),
        output_wav=Path("work/audio/source.wav"),
        sample_rate=16000,
        channels=1,
        codec="pcm_s16le",
    )
    assert command[0] == "ffmpeg"
    assert "-ar" in command
    assert "16000" in command
    assert Path(command[-1]) == Path("work/audio/source.wav")
