from pathlib import Path

import pytest

from video_translate.config import TTSConfig
from video_translate.tts.backends import EspeakTTSBackend, MockTTSBackend, build_tts_backend


def _base_tts_config(backend: str) -> TTSConfig:
    return TTSConfig(
        backend=backend,
        sample_rate=24000,
        min_segment_seconds=0.12,
        mock_base_tone_hz=220,
        espeak_bin="espeak",
        espeak_voice="tr",
        espeak_speed_wpm=165,
        espeak_pitch=50,
        espeak_adaptive_rate_enabled=True,
        espeak_adaptive_rate_min_wpm=120,
        espeak_adaptive_rate_max_wpm=260,
        espeak_adaptive_rate_max_passes=3,
        espeak_adaptive_rate_tolerance_seconds=0.06,
        max_duration_delta_seconds=0.08,
        qa_max_postfit_segment_ratio=0.60,
        qa_max_postfit_seconds_ratio=0.35,
        qa_fail_on_flags=False,
        qa_allowed_flags=(),
    )


def test_build_tts_backend_mock() -> None:
    backend = build_tts_backend(_base_tts_config("mock"))
    assert isinstance(backend, MockTTSBackend)


def test_build_tts_backend_espeak() -> None:
    backend = build_tts_backend(_base_tts_config("espeak"))
    assert isinstance(backend, EspeakTTSBackend)


def test_build_tts_backend_espeak_prefers_espeak_ng_when_espeak_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_which(command: str) -> str | None:
        if command == "espeak-ng":
            return "/bin/espeak-ng"
        return None

    monkeypatch.setattr("video_translate.tts.backends.shutil.which", fake_which)
    backend = build_tts_backend(_base_tts_config("espeak"))
    assert isinstance(backend, EspeakTTSBackend)
    assert backend.espeak_bin == "espeak-ng"


def test_build_tts_backend_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unsupported TTS backend"):
        build_tts_backend(_base_tts_config("invalid"))


def test_espeak_backend_builds_command_and_writes_wav(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    backend = EspeakTTSBackend(
        espeak_bin="espeak",
        voice="tr",
        speed_wpm=165,
        pitch=50,
        min_segment_seconds=0.12,
        adaptive_rate_enabled=True,
        adaptive_rate_min_wpm=120,
        adaptive_rate_max_wpm=260,
        adaptive_rate_max_passes=3,
        adaptive_rate_tolerance_seconds=0.06,
    )
    output_wav = tmp_path / "seg.wav"
    captured_commands: list[list[str]] = []

    def fake_run_command(command: list[str]) -> None:
        captured_commands.append(command)
        # write a tiny valid wav via mock backend for duration parse
        mock_backend = MockTTSBackend(base_tone_hz=220, min_segment_seconds=0.12)
        mock_backend.synthesize_to_wav(
            text="merhaba",
            output_wav=output_wav,
            target_duration=0.2,
            sample_rate=24000,
        )

    monkeypatch.setattr("video_translate.tts.backends.run_command", fake_run_command)
    duration = backend.synthesize_to_wav(
        text="merhaba dunya",
        output_wav=output_wav,
        target_duration=0.5,
        sample_rate=24000,
    )

    assert output_wav.exists()
    assert duration > 0.0
    assert captured_commands
    command = captured_commands[-1]
    assert isinstance(command, list)
    assert command[0] == "espeak"
    assert "-v" in command
    assert "-w" in command


def test_espeak_backend_adaptive_rate_retries_until_tolerance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    backend = EspeakTTSBackend(
        espeak_bin="espeak",
        voice="tr",
        speed_wpm=165,
        pitch=50,
        min_segment_seconds=0.12,
        adaptive_rate_enabled=True,
        adaptive_rate_min_wpm=120,
        adaptive_rate_max_wpm=260,
        adaptive_rate_max_passes=3,
        adaptive_rate_tolerance_seconds=0.04,
    )
    output_wav = tmp_path / "seg_adaptive.wav"
    captured_speeds: list[int] = []
    scripted_durations = [0.95, 0.53, 0.51]

    def fake_run_command(command: list[str]) -> None:
        speed_index = command.index("-s") + 1
        captured_speeds.append(int(command[speed_index]))
        duration = scripted_durations[min(len(captured_speeds) - 1, len(scripted_durations) - 1)]
        mock_backend = MockTTSBackend(base_tone_hz=220, min_segment_seconds=0.12)
        mock_backend.synthesize_to_wav(
            text="ornek",
            output_wav=output_wav,
            target_duration=duration,
            sample_rate=24000,
        )

    monkeypatch.setattr("video_translate.tts.backends.run_command", fake_run_command)
    duration = backend.synthesize_to_wav(
        text="ornek metin",
        output_wav=output_wav,
        target_duration=0.50,
        sample_rate=24000,
    )

    assert output_wav.exists()
    assert len(captured_speeds) >= 2
    assert captured_speeds[-1] > captured_speeds[0]
    assert captured_speeds[-1] <= 260
    assert duration <= 0.53
