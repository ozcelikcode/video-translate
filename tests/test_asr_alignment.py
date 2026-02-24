from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from video_translate.asr.whisper import transcribe_audio
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
        self.text = "hello microsoft"
        self.words = [
            _DummyWord("hello", 0.00, 0.45, 0.95),
            _DummyWord("microsoft", 0.45, 0.95, 0.90),
        ]


class _DummyInfo:
    def __init__(self) -> None:
        self.language = "en"
        self.language_probability = 0.99
        self.duration = 1.0


def _asr_config() -> ASRConfig:
    return ASRConfig(
        model="small",
        device="cpu",
        compute_type="int8",
        beam_size=5,
        language="en",
        word_timestamps=True,
        vad_filter=True,
        fallback_on_oom=True,
        fallback_model="small",
        fallback_device="cpu",
        fallback_compute_type="int8",
        alignment_backend="none",
    )


def test_transcribe_audio_applies_whisperx_alignment_when_enabled(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    class FakeModel:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def transcribe(self, *args: Any, **kwargs: Any) -> tuple[list[_DummySegment], _DummyInfo]:
            return ([_DummySegment()], _DummyInfo())

    class _FakeWhisperXModule:
        @staticmethod
        def load_audio(path: str) -> str:
            return path

        @staticmethod
        def load_align_model(language_code: str, device: str) -> tuple[str, dict[str, Any]]:
            assert language_code == "en"
            assert device == "cpu"
            return ("align-model", {"language": language_code})

        @staticmethod
        def align(
            segments: list[dict[str, Any]],
            align_model: str,
            align_metadata: dict[str, Any],
            audio: Any,
            device: str,
            return_char_alignments: bool = False,
        ) -> dict[str, Any]:
            assert len(segments) == 1
            assert align_model == "align-model"
            assert device == "cpu"
            return {
                "segments": [
                    {
                        "id": 0,
                        "start": 0.02,
                        "end": 0.98,
                        "text": "hello microsoft",
                        "words": [
                            {"word": "hello", "start": 0.05, "end": 0.40, "score": 0.88},
                            {"word": "microsoft", "start": 0.43, "end": 0.92, "score": 0.86},
                        ],
                    }
                ]
            }

    monkeypatch.setattr("faster_whisper.WhisperModel", FakeModel)
    monkeypatch.setitem(sys.modules, "whisperx", _FakeWhisperXModule())

    result = transcribe_audio(
        tmp_path / "audio.wav",
        replace(_asr_config(), alignment_backend="whisperx"),
    )

    assert result.runtime_diagnostics is not None
    assert result.runtime_diagnostics["alignment_backend"] == "whisperx"
    assert result.runtime_diagnostics["alignment_applied"] is True
    assert result.runtime_diagnostics["alignment_error"] is None
    assert result.runtime_diagnostics["alignment_refined_segment_count"] == 1
    assert result.runtime_diagnostics["alignment_device_used"] == "cpu"

    assert len(result.segments) == 1
    assert result.segments[0].start == 0.02
    assert result.segments[0].end == 0.98
    assert result.segments[0].words[0].start == 0.05
    assert result.segments[0].words[1].end == 0.92


def test_transcribe_audio_whisperx_alignment_failure_falls_back_gracefully(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    class FakeModel:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def transcribe(self, *args: Any, **kwargs: Any) -> tuple[list[_DummySegment], _DummyInfo]:
            return ([_DummySegment()], _DummyInfo())

    class _FailingWhisperXModule:
        @staticmethod
        def load_audio(path: str) -> str:
            return path

        @staticmethod
        def load_align_model(language_code: str, device: str) -> tuple[str, dict[str, Any]]:
            return ("align-model", {})

        @staticmethod
        def align(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("alignment failed")

    monkeypatch.setattr("faster_whisper.WhisperModel", FakeModel)
    monkeypatch.setitem(sys.modules, "whisperx", _FailingWhisperXModule())

    result = transcribe_audio(
        tmp_path / "audio.wav",
        replace(_asr_config(), alignment_backend="whisperx"),
    )

    assert result.runtime_diagnostics is not None
    assert result.runtime_diagnostics["alignment_backend"] == "whisperx"
    assert result.runtime_diagnostics["alignment_applied"] is False
    assert "alignment failed" in str(result.runtime_diagnostics["alignment_error"])
    # Original faster-whisper timings are preserved on failure.
    assert result.segments[0].start == 0.0
    assert result.segments[0].end == 1.0
    assert result.segments[0].words[0].start == 0.0
