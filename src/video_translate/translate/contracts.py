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


def _count_words(text: str) -> int:
    return len([part for part in text.split() if part.strip()])


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
        segments.append(
            TranslationInputSegment(
                id=segment_id,
                start=start,
                end=end,
                duration=duration,
                source_text=source_text,
                source_word_count=source_word_count,
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

