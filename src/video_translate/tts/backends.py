from __future__ import annotations

import math
import shutil
import wave
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from video_translate.config import TTSConfig
from video_translate.utils.subprocess_utils import run_command


class TTSBackend:
    name: str

    def synthesize_to_wav(
        self,
        *,
        text: str,
        output_wav: Path,
        target_duration: float,
        sample_rate: int,
    ) -> float:
        raise NotImplementedError


@dataclass(frozen=True)
class MockTTSBackend(TTSBackend):
    base_tone_hz: int
    min_segment_seconds: float
    amplitude: int = 5000
    name: str = "mock"

    def synthesize_to_wav(
        self,
        *,
        text: str,
        output_wav: Path,
        target_duration: float,
        sample_rate: int,
    ) -> float:
        duration = max(float(target_duration), self.min_segment_seconds)
        frame_count = max(1, int(round(duration * sample_rate)))
        tone_hz = float(self.base_tone_hz + (len(text) % 40))
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_wav), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            raw_frames = bytearray()
            for index in range(frame_count):
                sample = int(self.amplitude * math.sin(2.0 * math.pi * tone_hz * index / sample_rate))
                raw_frames.extend(sample.to_bytes(2, byteorder="little", signed=True))
            wav_file.writeframes(bytes(raw_frames))
        return frame_count / sample_rate


def _wav_duration_seconds(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as wav_file:
        frame_count = wav_file.getnframes()
        sample_rate = wav_file.getframerate()
    if sample_rate <= 0:
        return 0.0
    return frame_count / sample_rate


@dataclass(frozen=True)
class EspeakTTSBackend(TTSBackend):
    espeak_bin: str
    voice: str
    speed_wpm: int
    pitch: int
    min_segment_seconds: float
    adaptive_rate_enabled: bool
    adaptive_rate_min_wpm: int
    adaptive_rate_max_wpm: int
    adaptive_rate_max_passes: int
    adaptive_rate_tolerance_seconds: float
    name: str = "espeak"

    def synthesize_to_wav(
        self,
        *,
        text: str,
        output_wav: Path,
        target_duration: float,
        sample_rate: int,
    ) -> float:
        safe_text = text.strip()
        if not safe_text:
            safe_text = " "
        output_wav.parent.mkdir(parents=True, exist_ok=True)

        def synthesize_once(speed_wpm: int) -> float:
            command = [
                self.espeak_bin,
                "-v",
                self.voice,
                "-s",
                str(speed_wpm),
                "-p",
                str(self.pitch),
                "-w",
                str(output_wav),
                safe_text,
            ]
            run_command(command)
            return _wav_duration_seconds(output_wav)

        current_speed_wpm = max(
            self.adaptive_rate_min_wpm,
            min(self.adaptive_rate_max_wpm, self.speed_wpm),
        )
        duration = synthesize_once(current_speed_wpm)
        if (
            not self.adaptive_rate_enabled
            or target_duration <= 0.0
            or self.adaptive_rate_max_passes <= 0
        ):
            return duration

        for _ in range(self.adaptive_rate_max_passes):
            delta = duration - target_duration
            if abs(delta) <= self.adaptive_rate_tolerance_seconds:
                break
            ratio = duration / target_duration
            proposed_speed_wpm = int(round(current_speed_wpm * ratio))
            if proposed_speed_wpm == current_speed_wpm:
                proposed_speed_wpm = current_speed_wpm + (6 if delta > 0 else -6)
            proposed_speed_wpm = max(
                self.adaptive_rate_min_wpm,
                min(self.adaptive_rate_max_wpm, proposed_speed_wpm),
            )
            if proposed_speed_wpm == current_speed_wpm:
                break
            current_speed_wpm = proposed_speed_wpm
            duration = synthesize_once(current_speed_wpm)
        return duration


@dataclass(frozen=True)
class PiperTTSBackend(TTSBackend):
    piper_bin: str
    model_path: Path
    config_path: Path | None
    speaker_id: int | None
    length_scale: float
    noise_scale: float
    noise_w: float
    min_segment_seconds: float
    name: str = "piper"

    def synthesize_to_wav(
        self,
        *,
        text: str,
        output_wav: Path,
        target_duration: float,
        sample_rate: int,
    ) -> float:
        safe_text = text.strip()
        if not safe_text:
            safe_text = " "
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.piper_bin,
            "--model",
            str(self.model_path),
            "--output_file",
            str(output_wav),
            "--length_scale",
            f"{self.length_scale:.4f}",
            "--noise_scale",
            f"{self.noise_scale:.4f}",
            "--noise_w",
            f"{self.noise_w:.4f}",
        ]
        if self.config_path is not None:
            command.extend(["--config", str(self.config_path)])
        if self.speaker_id is not None:
            command.extend(["--speaker", str(self.speaker_id)])
        # Piper Windows launcher is a Python script; enforce UTF-8 stdin decoding.
        run_command(
            command,
            input_text=safe_text + "\n",
            env_overrides={
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
            },
        )
        duration = _wav_duration_seconds(output_wav)
        return max(duration, self.min_segment_seconds)


def _resolve_espeak_bin(configured_bin: str) -> str:
    configured = configured_bin.strip() or "espeak"
    candidates = [configured]
    lowered = configured.lower()
    if lowered == "espeak":
        candidates.append("espeak-ng")
    elif lowered == "espeak-ng":
        candidates.append("espeak")

    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        resolved = _resolve_command_path(candidate)
        if resolved is not None:
            return resolved
    return configured


def _resolve_piper_bin(configured_bin: str) -> str:
    configured = configured_bin.strip() or "piper"
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
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        resolved = _resolve_command_path(candidate)
        if resolved is not None:
            return resolved
    return configured


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


def build_tts_backend(config: TTSConfig) -> TTSBackend:
    backend = config.backend.strip().lower()
    if backend == "mock":
        return MockTTSBackend(
            base_tone_hz=config.mock_base_tone_hz,
            min_segment_seconds=config.min_segment_seconds,
        )
    if backend == "espeak":
        return EspeakTTSBackend(
            espeak_bin=_resolve_espeak_bin(config.espeak_bin),
            voice=config.espeak_voice,
            speed_wpm=config.espeak_speed_wpm,
            pitch=config.espeak_pitch,
            min_segment_seconds=config.min_segment_seconds,
            adaptive_rate_enabled=config.espeak_adaptive_rate_enabled,
            adaptive_rate_min_wpm=config.espeak_adaptive_rate_min_wpm,
            adaptive_rate_max_wpm=config.espeak_adaptive_rate_max_wpm,
            adaptive_rate_max_passes=config.espeak_adaptive_rate_max_passes,
            adaptive_rate_tolerance_seconds=config.espeak_adaptive_rate_tolerance_seconds,
        )
    if backend == "piper":
        if config.piper_model_path is None:
            raise ValueError("tts.piper_model_path is required when tts.backend='piper'.")
        return PiperTTSBackend(
            piper_bin=_resolve_piper_bin(config.piper_bin),
            model_path=config.piper_model_path,
            config_path=config.piper_config_path,
            speaker_id=config.piper_speaker,
            length_scale=config.piper_length_scale,
            noise_scale=config.piper_noise_scale,
            noise_w=config.piper_noise_w,
            min_segment_seconds=config.min_segment_seconds,
        )
    raise ValueError(
        f"Unsupported TTS backend: '{config.backend}'. Supported backends: mock, espeak, piper."
    )
