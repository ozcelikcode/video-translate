from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from video_translate.config import ASRConfig
from video_translate.models import TranscriptDocument, TranscriptSegment, WordTimestamp


def _is_probable_oom_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "out of memory" in message
        or "cuda error" in message
        or "cudnn_status_alloc_failed" in message
        # Missing CUDA runtime libraries on Windows/Linux should also trigger
        # CPU fallback when fallback_on_oom is enabled.
        or "cublas64_" in message
        or "cudart64_" in message
        or "libcublas" in message
        or "libcudart" in message
        or "cannot be loaded" in message and "cublas" in message
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


def _transcribe_and_collect(
    *,
    audio_path: Path,
    model_name: str,
    device: str,
    compute_type: str,
    asr_config: ASRConfig,
    on_segment_collected: Callable[[int], None] | None = None,
) -> tuple[list[Any], Any]:
    segments_iter, info = _transcribe_with_settings(
        audio_path=audio_path,
        model_name=model_name,
        device=device,
        compute_type=compute_type,
        asr_config=asr_config,
    )
    # faster-whisper returns a generator that can raise at iteration time.
    # Force evaluation here so fallback logic can catch runtime failures.
    collected: list[Any] = []
    for index, item in enumerate(segments_iter, start=1):
        collected.append(item)
        if on_segment_collected is not None:
            on_segment_collected(index)
    return collected, info


def transcribe_audio(
    audio_path: Path,
    asr_config: ASRConfig,
    on_segment_collected: Callable[[int], None] | None = None,
) -> TranscriptDocument:
    try:
        raw_segments, info = _transcribe_and_collect(
            audio_path=audio_path,
            model_name=asr_config.model,
            device=asr_config.device,
            compute_type=asr_config.compute_type,
            asr_config=asr_config,
            on_segment_collected=on_segment_collected,
        )
    except Exception as exc:  # noqa: BLE001
        # Primary ASR run failed. If fallback is enabled and fallback settings
        # differ from primary settings, retry on fallback path.
        can_retry_with_fallback = (
            asr_config.fallback_on_oom
            and (
                asr_config.device != asr_config.fallback_device
                or asr_config.compute_type != asr_config.fallback_compute_type
                or asr_config.model != asr_config.fallback_model
            )
        )
        if not can_retry_with_fallback:
            raise
        # Keep stricter error classification for same-device retries.
        if (
            asr_config.device == asr_config.fallback_device
            and not _is_probable_oom_error(exc)
        ):
            raise
        raw_segments, info = _transcribe_and_collect(
            audio_path=audio_path,
            model_name=asr_config.fallback_model,
            device=asr_config.fallback_device,
            compute_type=asr_config.fallback_compute_type,
            asr_config=asr_config,
            on_segment_collected=on_segment_collected,
        )

    segments: list[TranscriptSegment] = []
    for segment in raw_segments:
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
