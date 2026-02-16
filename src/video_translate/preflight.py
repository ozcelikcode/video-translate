from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCheck:
    name: str
    command: str
    path: str | None

    @property
    def ok(self) -> bool:
        return self.path is not None


@dataclass(frozen=True)
class PreflightReport:
    python_version: str
    yt_dlp: ToolCheck
    ffmpeg: ToolCheck
    faster_whisper_available: bool

    @property
    def ok(self) -> bool:
        return self.yt_dlp.ok and self.ffmpeg.ok and self.faster_whisper_available


def run_preflight(*, yt_dlp_bin: str, ffmpeg_bin: str) -> PreflightReport:
    yt_dlp_path = shutil.which(yt_dlp_bin)
    ffmpeg_path = shutil.which(ffmpeg_bin)
    faster_whisper_available = importlib.util.find_spec("faster_whisper") is not None

    return PreflightReport(
        python_version=sys.version.split()[0],
        yt_dlp=ToolCheck(name="yt-dlp", command=yt_dlp_bin, path=yt_dlp_path),
        ffmpeg=ToolCheck(name="ffmpeg", command=ffmpeg_bin, path=ffmpeg_path),
        faster_whisper_available=faster_whisper_available,
    )


def preflight_errors(report: PreflightReport) -> list[str]:
    errors: list[str] = []
    if not report.yt_dlp.ok:
        errors.append(
            f"Missing yt-dlp executable on PATH (configured command: '{report.yt_dlp.command}')."
        )
    if not report.ffmpeg.ok:
        errors.append(
            f"Missing ffmpeg executable on PATH (configured command: '{report.ffmpeg.command}')."
        )
    if not report.faster_whisper_available:
        errors.append("Python package 'faster_whisper' is not installed.")
    return errors

