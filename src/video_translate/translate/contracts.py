from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class TranslationInputSegment:
    id: int
    start: float
    end: float
    duration: float
    source_text: str
    source_word_count: int
    source_timing_hints: dict[str, Any] | None = None


@dataclass(frozen=True)
class TranslationInputDocument:
    schema_version: str
    stage: str
    generated_at_utc: str
    source_language: str
    target_language: str
    segment_count: int
    total_source_word_count: int
    segments: list[TranslationInputSegment]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TranslationOutputSegment:
    id: int
    start: float
    end: float
    duration: float
    source_text: str
    target_text: str
    source_word_count: int
    target_word_count: int
    length_ratio: float | None
    source_timing_hints: dict[str, Any] | None = None
    tts_render_text: str | None = None
    translation_unit_id: int | None = None
    preserved_entities: list[str] | None = None
    translation_quality_hints: dict[str, Any] | None = None


@dataclass(frozen=True)
class TranslationOutputDocument:
    schema_version: str
    stage: str
    generated_at_utc: str
    backend: str
    source_language: str
    target_language: str
    segment_count: int
    total_source_word_count: int
    total_target_word_count: int
    segments: list[TranslationOutputSegment]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _count_words(text: str) -> int:
    return len([part for part in text.split() if part.strip()])


def _normalize_optional_timing_hints(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        normalized[str(key)] = item
    return normalized or None


def _normalize_optional_dict(value: object) -> dict[str, Any] | None:
    if value is None or not isinstance(value, dict):
        return None
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        normalized[str(key)] = item
    return normalized or None


def _normalize_optional_list_of_str(value: object) -> list[str] | None:
    if value is None or not isinstance(value, list):
        return None
    normalized = [str(item).strip() for item in value if str(item).strip()]
    return normalized or None


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _safe_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_source_timing_hints_from_transcript_segment(raw_segment: dict[str, Any]) -> dict[str, Any] | None:
    words_raw = raw_segment.get("words", None)
    if not isinstance(words_raw, list) or not words_raw:
        return None
    starts: list[float] = []
    ends: list[float] = []
    for raw_word in words_raw:
        if not isinstance(raw_word, dict):
            continue
        start = _safe_float(raw_word.get("start"))
        end = _safe_float(raw_word.get("end"))
        if start is not None:
            starts.append(start)
        if end is not None:
            ends.append(end)
    if not starts or not ends:
        return {
            "has_word_timestamps": False,
            "word_count_from_timestamps": 0,
        }
    segment_start = _safe_float(raw_segment.get("start"))
    segment_end = _safe_float(raw_segment.get("end"))
    first_word_start = min(starts)
    last_word_end = max(ends)
    leading_silence = (
        max(0.0, first_word_start - segment_start)
        if segment_start is not None
        else None
    )
    trailing_silence = (
        max(0.0, segment_end - last_word_end)
        if segment_end is not None
        else None
    )
    return {
        "has_word_timestamps": True,
        "first_word_start": first_word_start,
        "last_word_end": last_word_end,
        "leading_silence_seconds": leading_silence,
        "trailing_silence_seconds": trailing_silence,
        "word_count_from_timestamps": min(len(starts), len(ends)),
    }


def build_translation_input_document(
    *,
    transcript_payload: dict[str, Any],
    target_language: str,
) -> TranslationInputDocument:
    source_language_raw = transcript_payload.get("language", "en")
    source_language = str(source_language_raw).strip() or "en"
    segments_payload = transcript_payload.get("segments", [])
    if not isinstance(segments_payload, list):
        raise ValueError("Transcript payload field 'segments' must be a list.")

    segments: list[TranslationInputSegment] = []
    for raw in segments_payload:
        if not isinstance(raw, dict):
            raise ValueError("Each transcript segment must be an object.")

        segment_id = int(raw.get("id", len(segments)))
        start = float(raw.get("start", 0.0))
        end = float(raw.get("end", start))
        duration = max(0.0, end - start)
        source_text = str(raw.get("text", "")).strip()
        source_word_count = _count_words(source_text)
        source_timing_hints = _build_source_timing_hints_from_transcript_segment(raw)
        segments.append(
            TranslationInputSegment(
                id=segment_id,
                start=start,
                end=end,
                duration=duration,
                source_text=source_text,
                source_word_count=source_word_count,
                source_timing_hints=source_timing_hints,
            )
        )

    return TranslationInputDocument(
        schema_version="1.0",
        stage="m2_translation_input",
        generated_at_utc=datetime.now(tz=UTC).isoformat(),
        source_language=source_language,
        target_language=target_language,
        segment_count=len(segments),
        total_source_word_count=sum(segment.source_word_count for segment in segments),
        segments=segments,
    )


def parse_translation_input_document(payload: dict[str, Any]) -> TranslationInputDocument:
    stage = str(payload.get("stage", "")).strip()
    if stage != "m2_translation_input":
        raise ValueError("Expected stage 'm2_translation_input'.")

    source_language = str(payload.get("source_language", "")).strip()
    target_language = str(payload.get("target_language", "")).strip()
    if not source_language or not target_language:
        raise ValueError("Input contract requires source_language and target_language.")

    segments_payload = payload.get("segments", [])
    if not isinstance(segments_payload, list):
        raise ValueError("Input contract field 'segments' must be a list.")

    segments: list[TranslationInputSegment] = []
    for raw in segments_payload:
        if not isinstance(raw, dict):
            raise ValueError("Each input segment must be an object.")
        source_text = str(raw.get("source_text", "")).strip()
        segments.append(
            TranslationInputSegment(
                id=int(raw.get("id", len(segments))),
                start=float(raw.get("start", 0.0)),
                end=float(raw.get("end", 0.0)),
                duration=max(0.0, float(raw.get("duration", 0.0))),
                source_text=source_text,
                source_word_count=int(raw.get("source_word_count", _count_words(source_text))),
                source_timing_hints=_normalize_optional_timing_hints(raw.get("source_timing_hints")),
            )
        )

    return TranslationInputDocument(
        schema_version=str(payload.get("schema_version", "1.0")),
        stage=stage,
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        source_language=source_language,
        target_language=target_language,
        segment_count=int(payload.get("segment_count", len(segments))),
        total_source_word_count=int(
            payload.get(
                "total_source_word_count",
                sum(segment.source_word_count for segment in segments),
            )
        ),
        segments=segments,
    )


def _length_ratio(source_word_count: int, target_word_count: int) -> float | None:
    if source_word_count <= 0:
        return None
    return target_word_count / source_word_count


def build_translation_output_document(
    *,
    input_doc: TranslationInputDocument,
    translated_texts: list[str],
    backend: str,
    tts_render_texts: list[str | None] | None = None,
    translation_unit_ids: list[int | None] | None = None,
    preserved_entities_list: list[list[str] | None] | None = None,
    translation_quality_hints_list: list[dict[str, Any] | None] | None = None,
) -> TranslationOutputDocument:
    if len(translated_texts) != len(input_doc.segments):
        raise ValueError(
            "Translated text count does not match input segment count: "
            f"{len(translated_texts)} != {len(input_doc.segments)}"
        )
    if tts_render_texts is not None and len(tts_render_texts) != len(input_doc.segments):
        raise ValueError("TTS render text count must match input segment count.")
    if translation_unit_ids is not None and len(translation_unit_ids) != len(input_doc.segments):
        raise ValueError("Translation unit id count must match input segment count.")
    if preserved_entities_list is not None and len(preserved_entities_list) != len(input_doc.segments):
        raise ValueError("Preserved entities count must match input segment count.")
    if (
        translation_quality_hints_list is not None
        and len(translation_quality_hints_list) != len(input_doc.segments)
    ):
        raise ValueError("Translation quality hints count must match input segment count.")

    output_segments: list[TranslationOutputSegment] = []
    if tts_render_texts is None:
        tts_render_texts = [None] * len(input_doc.segments)
    if translation_unit_ids is None:
        translation_unit_ids = [None] * len(input_doc.segments)
    if preserved_entities_list is None:
        preserved_entities_list = [None] * len(input_doc.segments)
    if translation_quality_hints_list is None:
        translation_quality_hints_list = [None] * len(input_doc.segments)

    for (
        source_segment,
        translated_text,
        tts_render_text,
        translation_unit_id,
        preserved_entities,
        translation_quality_hints,
    ) in zip(
        input_doc.segments,
        translated_texts,
        tts_render_texts,
        translation_unit_ids,
        preserved_entities_list,
        translation_quality_hints_list,
        strict=True,
    ):
        normalized_target = translated_text.strip()
        normalized_tts_render = (
            str(tts_render_text).strip()
            if tts_render_text is not None and str(tts_render_text).strip()
            else None
        )
        target_word_count = _count_words(normalized_target)
        output_segments.append(
            TranslationOutputSegment(
                id=source_segment.id,
                start=source_segment.start,
                end=source_segment.end,
                duration=source_segment.duration,
                source_text=source_segment.source_text,
                target_text=normalized_target,
                source_word_count=source_segment.source_word_count,
                target_word_count=target_word_count,
                length_ratio=_length_ratio(source_segment.source_word_count, target_word_count),
                source_timing_hints=(
                    dict(source_segment.source_timing_hints)
                    if source_segment.source_timing_hints is not None
                    else None
                ),
                tts_render_text=normalized_tts_render,
                translation_unit_id=int(translation_unit_id) if translation_unit_id is not None else None,
                preserved_entities=(
                    [item for item in (preserved_entities or []) if str(item).strip()]
                    if preserved_entities is not None
                    else None
                ),
                translation_quality_hints=(
                    dict(translation_quality_hints)
                    if translation_quality_hints is not None
                    else None
                ),
            )
        )

    return TranslationOutputDocument(
        schema_version="1.0",
        stage="m2_translation_output",
        generated_at_utc=datetime.now(tz=UTC).isoformat(),
        backend=backend,
        source_language=input_doc.source_language,
        target_language=input_doc.target_language,
        segment_count=len(output_segments),
        total_source_word_count=sum(segment.source_word_count for segment in output_segments),
        total_target_word_count=sum(segment.target_word_count for segment in output_segments),
        segments=output_segments,
    )


def parse_translation_output_document(payload: dict[str, Any]) -> TranslationOutputDocument:
    stage = str(payload.get("stage", "")).strip()
    if stage != "m2_translation_output":
        raise ValueError("Expected stage 'm2_translation_output'.")

    source_language = str(payload.get("source_language", "")).strip()
    target_language = str(payload.get("target_language", "")).strip()
    backend = str(payload.get("backend", "")).strip()
    if not source_language or not target_language or not backend:
        raise ValueError("Output contract requires backend, source_language, and target_language.")

    segments_payload = payload.get("segments", [])
    if not isinstance(segments_payload, list):
        raise ValueError("Output contract field 'segments' must be a list.")

    segments: list[TranslationOutputSegment] = []
    for raw in segments_payload:
        if not isinstance(raw, dict):
            raise ValueError("Each output segment must be an object.")
        source_text = str(raw.get("source_text", "")).strip()
        target_text = str(raw.get("target_text", "")).strip()
        target_word_count = int(raw.get("target_word_count", _count_words(target_text)))
        segments.append(
            TranslationOutputSegment(
                id=int(raw.get("id", len(segments))),
                start=float(raw.get("start", 0.0)),
                end=float(raw.get("end", 0.0)),
                duration=max(0.0, float(raw.get("duration", 0.0))),
                source_text=source_text,
                target_text=target_text,
                source_word_count=int(raw.get("source_word_count", _count_words(source_text))),
                target_word_count=target_word_count,
                length_ratio=(
                    None
                    if raw.get("length_ratio") is None
                    else float(raw.get("length_ratio"))
                ),
                source_timing_hints=_normalize_optional_timing_hints(raw.get("source_timing_hints")),
                tts_render_text=_normalize_optional_text(raw.get("tts_render_text")),
                translation_unit_id=(
                    int(raw.get("translation_unit_id"))
                    if raw.get("translation_unit_id") is not None
                    else None
                ),
                preserved_entities=_normalize_optional_list_of_str(raw.get("preserved_entities")),
                translation_quality_hints=_normalize_optional_dict(raw.get("translation_quality_hints")),
            )
        )

    return TranslationOutputDocument(
        schema_version=str(payload.get("schema_version", "1.0")),
        stage=stage,
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        backend=backend,
        source_language=source_language,
        target_language=target_language,
        segment_count=int(payload.get("segment_count", len(segments))),
        total_source_word_count=int(
            payload.get("total_source_word_count", sum(segment.source_word_count for segment in segments))
        ),
        total_target_word_count=int(
            payload.get("total_target_word_count", sum(segment.target_word_count for segment in segments))
        ),
        segments=segments,
    )
