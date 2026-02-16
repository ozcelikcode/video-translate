from pathlib import Path
from typing import Any

from video_translate.asr.whisper import _is_probable_oom_error, transcribe_audio
from video_translate.config import ASRConfig


class _DummyWord:
    def __init__(self, word: str, start: float, end: float, probability: float) -> None:
        self.word = word
        self.start = start
        self.end = end
        self.probability = probability


class _DummySegment:
    def __init__(self) -> None:
        self.id = 0
        self.start = 0.0
        self.end = 1.0
        self.text = "hello"
        self.words = [_DummyWord("hello", 0.0, 1.0, 0.9)]


class _DummyInfo:
    def __init__(self) -> None:
        self.language = "en"
        self.language_probability = 0.99
        self.duration = 1.0


def _asr_config() -> ASRConfig:
    return ASRConfig(
        model="small",
        device="cuda",
        compute_type="int8_float16",
        beam_size=5,
        language="en",
        word_timestamps=True,
        vad_filter=True,
        fallback_on_oom=True,
        fallback_model="small",
        fallback_device="cpu",
        fallback_compute_type="int8",
    )


def test_is_probable_oom_error_detects_cuda_messages() -> None:
    assert _is_probable_oom_error(RuntimeError("CUDA out of memory"))
    assert _is_probable_oom_error(RuntimeError("cuDNN_STATUS_ALLOC_FAILED"))
    assert not _is_probable_oom_error(RuntimeError("some different error"))


def test_transcribe_audio_falls_back_on_oom(monkeypatch: Any, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str]] = []

    def fake_transcribe_with_settings(**kwargs: Any) -> tuple[list[_DummySegment], _DummyInfo]:
        calls.append((kwargs["model_name"], kwargs["device"], kwargs["compute_type"]))
        if len(calls) == 1:
            raise RuntimeError("CUDA out of memory")
        return ([_DummySegment()], _DummyInfo())

    monkeypatch.setattr(
        "video_translate.asr.whisper._transcribe_with_settings",
        fake_transcribe_with_settings,
    )

    result = transcribe_audio(tmp_path / "audio.wav", _asr_config())

    assert len(calls) == 2
    assert calls[0][1] == "cuda"
    assert calls[1][1] == "cpu"
    assert result.language == "en"
    assert len(result.segments) == 1
