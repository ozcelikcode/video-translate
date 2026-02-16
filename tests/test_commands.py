from pathlib import Path

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
