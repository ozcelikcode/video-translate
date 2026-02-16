from __future__ import annotations

from pathlib import Path

from video_translate.utils.subprocess_utils import run_command


def build_ffmpeg_normalize_command(
    ffmpeg_bin: str,
    input_media: Path,
    output_wav: Path,
    sample_rate: int,
    channels: int,
    codec: str,
) -> list[str]:
    return [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_media),
        "-vn",
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-c:a",
        codec,
        str(output_wav),
    ]


def normalize_audio_for_asr(
    ffmpeg_bin: str,
    input_media: Path,
    output_wav: Path,
    sample_rate: int,
    channels: int,
    codec: str,
) -> Path:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    command = build_ffmpeg_normalize_command(
        ffmpeg_bin=ffmpeg_bin,
        input_media=input_media,
        output_wav=output_wav,
        sample_rate=sample_rate,
        channels=channels,
        codec=codec,
    )
    run_command(command)
    if not output_wav.exists():
        raise FileNotFoundError(f"Expected normalized audio was not created: {output_wav}")
    return output_wav

