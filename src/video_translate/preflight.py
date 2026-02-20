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
    translate_backend: str
    transformers_available: bool | None
    sentencepiece_available: bool | None
    torch_available: bool | None
    tts_backend: str
    espeak: ToolCheck | None

    @property
    def ok(self) -> bool:
        base_ok = self.yt_dlp.ok and self.ffmpeg.ok and self.faster_whisper_available
        translate_ok = True
        if self.translate_backend == "transformers" and self.transformers_available is not None:
            translate_ok = (
                bool(self.transformers_available)
                and bool(self.sentencepiece_available)
                and bool(self.torch_available)
            )
        tts_ok = True
        if self.tts_backend == "espeak" and self.espeak is not None:
            tts_ok = self.espeak is not None and self.espeak.ok
        return base_ok and translate_ok and tts_ok


def _resolve_espeak_toolcheck(espeak_bin: str) -> ToolCheck:
    configured = espeak_bin.strip() or "espeak"
    candidates = [configured]
    lowered = configured.lower()
    if lowered == "espeak":
        candidates.append("espeak-ng")
    elif lowered == "espeak-ng":
        candidates.append("espeak")

    seen: set[str] = set()
    for command in candidates:
        key = command.lower()
        if key in seen:
            continue
        seen.add(key)
        path = shutil.which(command)
        if path is not None:
            return ToolCheck(name="espeak", command=command, path=path)
    return ToolCheck(name="espeak", command=configured, path=None)


def run_preflight(
    *,
    yt_dlp_bin: str,
    ffmpeg_bin: str,
    translate_backend: str = "mock",
    tts_backend: str = "mock",
    espeak_bin: str = "espeak",
    check_translate_backend: bool = False,
    check_tts_backend: bool = False,
) -> PreflightReport:
    yt_dlp_path = shutil.which(yt_dlp_bin)
    ffmpeg_path = shutil.which(ffmpeg_bin)
    faster_whisper_available = importlib.util.find_spec("faster_whisper") is not None
    backend = translate_backend.strip().lower()
    tts = tts_backend.strip().lower()

    transformers_available: bool | None = None
    sentencepiece_available: bool | None = None
    torch_available: bool | None = None
    if check_translate_backend and backend == "transformers":
        transformers_available = importlib.util.find_spec("transformers") is not None
        sentencepiece_available = importlib.util.find_spec("sentencepiece") is not None
        torch_available = importlib.util.find_spec("torch") is not None
    espeak: ToolCheck | None = None
    if check_tts_backend and tts == "espeak":
        espeak = _resolve_espeak_toolcheck(espeak_bin)

    return PreflightReport(
        python_version=sys.version.split()[0],
        yt_dlp=ToolCheck(name="yt-dlp", command=yt_dlp_bin, path=yt_dlp_path),
        ffmpeg=ToolCheck(name="ffmpeg", command=ffmpeg_bin, path=ffmpeg_path),
        faster_whisper_available=faster_whisper_available,
        translate_backend=backend,
        transformers_available=transformers_available,
        sentencepiece_available=sentencepiece_available,
        torch_available=torch_available,
        tts_backend=tts,
        espeak=espeak,
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
    if report.translate_backend == "transformers" and report.transformers_available is not None:
        if not report.transformers_available:
            errors.append("Python package 'transformers' is not installed.")
        if not report.sentencepiece_available:
            errors.append("Python package 'sentencepiece' is not installed.")
        if not report.torch_available:
            errors.append("Python package 'torch' is not installed.")
    if report.tts_backend == "espeak":
        if report.espeak is None or not report.espeak.ok:
            command = report.espeak.command if report.espeak is not None else "espeak"
            errors.append(f"Missing espeak executable on PATH (configured command: '{command}').")
    return errors
