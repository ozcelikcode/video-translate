from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath


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
    piper: ToolCheck | None = None
    piper_model_path: str | None = None
    piper_model_exists: bool | None = None

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
        if self.tts_backend == "piper":
            tts_ok = (
                self.piper is not None
                and self.piper.ok
                and self.piper_model_exists is True
            )
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
        path = _resolve_command_path(command)
        if path is not None:
            return ToolCheck(name="espeak", command=command, path=path)
    return ToolCheck(name="espeak", command=configured, path=None)


def _resolve_piper_toolcheck(piper_bin: str) -> ToolCheck:
    configured = piper_bin.strip() or "piper"
    candidates = [configured]
    if configured.lower() != "piper":
        candidates.append("piper")
    root = _project_root()
    candidates.extend(
        [
            str(root / ".venv" / "Scripts" / "piper.exe"),
            str(root / ".venv" / "bin" / "piper"),
        ]
    )

    seen: set[str] = set()
    for command in candidates:
        key = command.lower()
        if key in seen:
            continue
        seen.add(key)
        path = _resolve_command_path(command)
        if path is not None:
            return ToolCheck(name="piper", command=command, path=path)
    return ToolCheck(name="piper", command=configured, path=None)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_explicit_path(command: str) -> bool:
    return "/" in command or "\\" in command or command.lower().endswith(".exe")


def _has_windows_drive(command: str) -> bool:
    return bool(PureWindowsPath(command).drive)


def _resolve_command_path(command: str) -> str | None:
    normalized = command.strip()
    if not normalized:
        return None
    if _is_explicit_path(normalized):
        candidate = Path(normalized)
        if not candidate.is_absolute() and not _has_windows_drive(normalized):
            candidate = _project_root() / candidate
        if candidate.exists() and candidate.is_file():
            return str(candidate)
        return None
    return shutil.which(normalized)


def run_preflight(
    *,
    yt_dlp_bin: str,
    ffmpeg_bin: str,
    translate_backend: str = "mock",
    tts_backend: str = "mock",
    espeak_bin: str = "espeak",
    piper_bin: str = "piper",
    piper_model_path: Path | None = None,
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
    piper: ToolCheck | None = None
    piper_model_path_text: str | None = None
    piper_model_exists: bool | None = None
    if check_tts_backend and tts == "espeak":
        espeak = _resolve_espeak_toolcheck(espeak_bin)
    if check_tts_backend and tts == "piper":
        piper = _resolve_piper_toolcheck(piper_bin)
        if piper_model_path is not None:
            resolved_model_path = piper_model_path.resolve()
            piper_model_path_text = str(resolved_model_path)
            piper_model_exists = resolved_model_path.exists() and resolved_model_path.is_file()
        else:
            piper_model_exists = False

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
        piper=piper,
        piper_model_path=piper_model_path_text,
        piper_model_exists=piper_model_exists,
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
    if report.tts_backend == "piper":
        if report.piper is None or not report.piper.ok:
            command = report.piper.command if report.piper is not None else "piper"
            errors.append(f"Missing piper executable on PATH (configured command: '{command}').")
        if report.piper_model_exists is not True:
            target = report.piper_model_path or "tts.piper_model_path"
            errors.append(f"Piper model file not found: '{target}'.")
    return errors
