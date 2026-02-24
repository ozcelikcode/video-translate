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


def _transcribe_and_collect(
    *,
    audio_path: Path,
    model_name: str,
    device: str,
    compute_type: str,
    asr_config: ASRConfig,
    on_segment_collected: Callable[[int], None] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> tuple[list[Any], Any]:
    if on_progress:
        on_progress(f"M1: '{model_name}' ASR modeli yukleniyor (gerekirse indirilecek)...")

    from faster_whisper import WhisperModel  # Imported lazily for startup speed.

    model = WhisperModel(
        model_size_or_path=model_name,
        device=device,
        compute_type=compute_type,
    )

    if on_progress:
        on_progress("M1: Model yuklendi. VAD (sessizlik) analizi ve ilk isleme basliyor...")

    segments_iter, info = model.transcribe(
        str(audio_path),
        language=asr_config.language,
        beam_size=asr_config.beam_size,
        word_timestamps=asr_config.word_timestamps,
        vad_filter=asr_config.vad_filter,
    )

    if on_progress:
        on_progress("M1: ASR analiz basliyor...")

    # faster-whisper returns a generator that can raise at iteration time.
    # Force evaluation here so fallback logic can catch runtime failures.
    collected: list[Any] = []
    for index, item in enumerate(segments_iter, start=1):
        collected.append(item)
        if on_segment_collected is not None:
            on_segment_collected(index)
    return collected, info


def _safe_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_alignment_device(device: str) -> str:
    normalized = (device or "").strip().lower()
    if normalized.startswith("cuda"):
        return "cuda"
    if normalized.startswith("cpu"):
        return "cpu"
    return "cpu"


def _build_aligned_words(raw_words: object, fallback_words: list[WordTimestamp]) -> list[WordTimestamp]:
    if not isinstance(raw_words, list):
        return fallback_words

    aligned_words: list[WordTimestamp] = []
    for index, raw_word in enumerate(raw_words):
        if not isinstance(raw_word, dict):
            continue
        text = str(raw_word.get("word", "")).strip()
        if not text:
            continue
        start_raw = raw_word.get("start")
        end_raw = raw_word.get("end")
        if start_raw is None or end_raw is None:
            # WhisperX can emit punctuation tokens without timings.
            continue
        try:
            start = float(start_raw)
            end = float(end_raw)
        except (TypeError, ValueError):
            continue
        if end < start:
            continue

        score_raw = raw_word.get("score", raw_word.get("probability", None))
        fallback_probability = (
            fallback_words[index].probability if index < len(fallback_words) else 1.0
        )
        probability = _safe_float(score_raw, fallback_probability)
        aligned_words.append(
            WordTimestamp(
                word=text,
                start=start,
                end=end,
                probability=probability,
            )
        )

    return aligned_words or fallback_words


def _apply_whisperx_alignment(
    *,
    audio_path: Path,
    segments: list[TranscriptSegment],
    language_code: str,
    preferred_device: str,
) -> tuple[list[TranscriptSegment], dict[str, Any]]:
    # Imported lazily to keep startup cost low and preserve optional dependency behavior.
    import whisperx  # type: ignore

    align_device = _normalize_alignment_device(preferred_device)
    audio_for_alignment: Any
    if hasattr(whisperx, "load_audio"):
        audio_for_alignment = whisperx.load_audio(str(audio_path))
    else:
        audio_for_alignment = str(audio_path)

    try:
        align_model, align_metadata = whisperx.load_align_model(
            language_code=language_code,
            device=align_device,
        )
    except Exception:
        if align_device == "cpu":
            raise
        align_device = "cpu"
        align_model, align_metadata = whisperx.load_align_model(
            language_code=language_code,
            device=align_device,
        )

    whisperx_input_segments = [
        {
            "id": segment.id,
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
        }
        for segment in segments
    ]

    try:
        aligned_result = whisperx.align(
            whisperx_input_segments,
            align_model,
            align_metadata,
            audio_for_alignment,
            align_device,
            return_char_alignments=False,
        )
    except TypeError:
        # Older versions may not support return_char_alignments kwarg.
        aligned_result = whisperx.align(
            whisperx_input_segments,
            align_model,
            align_metadata,
            audio_for_alignment,
            align_device,
        )

    raw_aligned_segments = (
        aligned_result.get("segments")
        if isinstance(aligned_result, dict)
        else None
    )
    if not isinstance(raw_aligned_segments, list):
        raise RuntimeError("WhisperX alignment returned invalid segment payload.")

    rebuilt_segments: list[TranscriptSegment] = []
    refined_segment_count = 0
    refined_word_count = 0
    segment_count_mismatch = len(raw_aligned_segments) != len(segments)

    for index, base_segment in enumerate(segments):
        raw_segment = raw_aligned_segments[index] if index < len(raw_aligned_segments) else None
        if not isinstance(raw_segment, dict):
            rebuilt_segments.append(base_segment)
            continue

        new_start = _safe_float(raw_segment.get("start"), base_segment.start)
        new_end = _safe_float(raw_segment.get("end"), base_segment.end)
        if new_end < new_start:
            new_start, new_end = base_segment.start, base_segment.end

        new_text = str(raw_segment.get("text", base_segment.text)).strip() or base_segment.text
        raw_words = raw_segment.get("words", raw_segment.get("word_segments", None))
        new_words = _build_aligned_words(raw_words, base_segment.words)

        if (
            abs(new_start - base_segment.start) > 1e-6
            or abs(new_end - base_segment.end) > 1e-6
            or len(new_words) != len(base_segment.words)
            or any(
                abs(new_words[i].start - base_segment.words[i].start) > 1e-6
                or abs(new_words[i].end - base_segment.words[i].end) > 1e-6
                for i in range(min(len(new_words), len(base_segment.words)))
            )
        ):
            refined_segment_count += 1
        refined_word_count += len(new_words)

        rebuilt_segments.append(
            TranscriptSegment(
                id=base_segment.id,
                start=new_start,
                end=new_end,
                text=new_text,
                words=new_words,
                source_evidence=base_segment.source_evidence,
                subtitle_text=base_segment.subtitle_text,
                subtitle_source=base_segment.subtitle_source,
                fusion_score=base_segment.fusion_score,
                subtitle_overlap_ratio=base_segment.subtitle_overlap_ratio,
            )
        )

    diagnostics = {
        "alignment_device_used": align_device,
        "alignment_refined_segment_count": refined_segment_count,
        "alignment_refined_word_count": refined_word_count,
        "alignment_segment_count_mismatch": segment_count_mismatch,
    }
    return rebuilt_segments, diagnostics


def transcribe_audio(
    audio_path: Path,
    asr_config: ASRConfig,
    on_segment_collected: Callable[[int], None] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> TranscriptDocument:
    used_fallback = False
    actual_model = asr_config.model
    actual_device = asr_config.device
    actual_compute_type = asr_config.compute_type
    try:
        raw_segments, info = _transcribe_and_collect(
            audio_path=audio_path,
            model_name=asr_config.model,
            device=asr_config.device,
            compute_type=asr_config.compute_type,
            asr_config=asr_config,
            on_segment_collected=on_segment_collected,
            on_progress=on_progress,
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
            
        if on_progress:
            on_progress(f"M1: ASR ilk deneme basarisiz. Fallback devrede ({asr_config.fallback_device})...")

        used_fallback = True
        actual_model = asr_config.fallback_model
        actual_device = asr_config.fallback_device
        actual_compute_type = asr_config.fallback_compute_type
        raw_segments, info = _transcribe_and_collect(
            audio_path=audio_path,
            model_name=asr_config.fallback_model,
            device=asr_config.fallback_device,
            compute_type=asr_config.fallback_compute_type,
            asr_config=asr_config,
            on_segment_collected=on_segment_collected,
            on_progress=on_progress,
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

    alignment_backend = (getattr(asr_config, "alignment_backend", "none") or "none").strip().lower()
    alignment_applied = False
    alignment_error: str | None = None
    alignment_diagnostics: dict[str, Any] = {}
    if alignment_backend == "whisperx":
        if on_progress:
            on_progress("M1: WhisperX hizalama denemesi (opsiyonel)...")
        try:
            segments, alignment_diagnostics = _apply_whisperx_alignment(
                audio_path=audio_path,
                segments=segments,
                language_code=str(info.language),
                preferred_device=actual_device,
            )
            alignment_applied = True
            if on_progress:
                on_progress("M1: WhisperX hizalama uygulandi (word timing refine).")
        except Exception as exc:  # noqa: BLE001
            alignment_error = str(exc)
            if on_progress:
                on_progress("M1: WhisperX hizalama kullanilamadi, faster-whisper zamanlariyla devam ediliyor.")

    return TranscriptDocument(
        language=str(info.language),
        language_probability=float(info.language_probability),
        duration=float(getattr(info, "duration", 0.0)),
        segments=segments,
        runtime_diagnostics={
            "model_used": actual_model,
            "device_used": actual_device,
            "compute_type_used": actual_compute_type,
            "fallback_used": used_fallback,
            "alignment_backend": alignment_backend,
            "alignment_applied": alignment_applied,
            "alignment_error": alignment_error,
            **alignment_diagnostics,
        },
    )
