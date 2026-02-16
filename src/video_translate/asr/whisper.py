from __future__ import annotations

from pathlib import Path
from typing import Any

from video_translate.config import ASRConfig
from video_translate.models import TranscriptDocument, TranscriptSegment, WordTimestamp


def _is_probable_oom_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "out of memory" in message
        or "cuda error" in message
        or "cudnn_status_alloc_failed" in message
    )


def _transcribe_with_settings(
    *,
    audio_path: Path,
    model_name: str,
    device: str,
    compute_type: str,
    asr_config: ASRConfig,
) -> tuple[Any, Any]:
    from faster_whisper import WhisperModel  # Imported lazily for startup speed.

    model = WhisperModel(
        model_size_or_path=model_name,
        device=device,
        compute_type=compute_type,
    )
    return model.transcribe(
        str(audio_path),
        language=asr_config.language,
        beam_size=asr_config.beam_size,
        word_timestamps=asr_config.word_timestamps,
        vad_filter=asr_config.vad_filter,
    )


def transcribe_audio(audio_path: Path, asr_config: ASRConfig) -> TranscriptDocument:
    try:
        segments_iter, info = _transcribe_with_settings(
            audio_path=audio_path,
            model_name=asr_config.model,
            device=asr_config.device,
            compute_type=asr_config.compute_type,
            asr_config=asr_config,
        )
    except Exception as exc:  # noqa: BLE001
        if not asr_config.fallback_on_oom or not _is_probable_oom_error(exc):
            raise
        segments_iter, info = _transcribe_with_settings(
            audio_path=audio_path,
            model_name=asr_config.fallback_model,
            device=asr_config.fallback_device,
            compute_type=asr_config.fallback_compute_type,
            asr_config=asr_config,
        )

    segments: list[TranscriptSegment] = []
    for segment in segments_iter:
        words: list[WordTimestamp] = []
        raw_words: list[Any] | None = getattr(segment, "words", None)
        if raw_words:
            for raw_word in raw_words:
                words.append(
                    WordTimestamp(
                        word=str(raw_word.word),
                        start=float(raw_word.start),
                        end=float(raw_word.end),
                        probability=float(raw_word.probability),
                    )
                )
        segments.append(
            TranscriptSegment(
                id=int(segment.id),
                start=float(segment.start),
                end=float(segment.end),
                text=str(segment.text).strip(),
                words=words,
            )
        )

    return TranscriptDocument(
        language=str(info.language),
        language_probability=float(info.language_probability),
        duration=float(getattr(info, "duration", 0.0)),
        segments=segments,
    )
