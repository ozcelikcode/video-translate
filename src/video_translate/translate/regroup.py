from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from video_translate.translate.contracts import TranslationInputDocument, TranslationInputSegment


_SPLIT_BOUNDARY_RE = re.compile(r"(?<=[.!?;,:])\s+")


@dataclass(frozen=True)
class TranslationUnit:
    unit_id: int
    segment_indexes: list[int]
    start: float
    end: float
    source_text: str


def _ends_with_terminal(text: str) -> bool:
    normalized = text.strip()
    return bool(normalized) and normalized.endswith((".", "!", "?"))


def build_translation_units(
    input_doc: TranslationInputDocument,
    *,
    enabled: bool = True,
    max_segments: int = 4,
    gap_threshold_seconds: float = 0.65,
) -> list[TranslationUnit]:
    if not enabled or not input_doc.segments:
        return [
            TranslationUnit(
                unit_id=index,
                segment_indexes=[index],
                start=segment.start,
                end=segment.end,
                source_text=segment.source_text.strip(),
            )
            for index, segment in enumerate(input_doc.segments)
        ]

    units: list[TranslationUnit] = []
    current_indexes: list[int] = []
    current_text_parts: list[str] = []
    unit_start = 0.0
    unit_end = 0.0
    for index, segment in enumerate(input_doc.segments):
        if not current_indexes:
            current_indexes = [index]
            current_text_parts = [segment.source_text.strip()]
            unit_start = segment.start
            unit_end = segment.end
            continue

        prev_segment = input_doc.segments[current_indexes[-1]]
        gap = max(0.0, float(segment.start) - float(prev_segment.end))
        prev_text = prev_segment.source_text.strip()
        should_split = False
        if len(current_indexes) >= max_segments:
            should_split = True
        elif _ends_with_terminal(prev_text):
            should_split = True
        elif gap > gap_threshold_seconds:
            should_split = True

        if should_split:
            units.append(
                TranslationUnit(
                    unit_id=len(units),
                    segment_indexes=list(current_indexes),
                    start=unit_start,
                    end=unit_end,
                    source_text=" ".join(part for part in current_text_parts if part).strip(),
                )
            )
            current_indexes = [index]
            current_text_parts = [segment.source_text.strip()]
            unit_start = segment.start
            unit_end = segment.end
        else:
            current_indexes.append(index)
            current_text_parts.append(segment.source_text.strip())
            unit_end = segment.end

    if current_indexes:
        units.append(
            TranslationUnit(
                unit_id=len(units),
                segment_indexes=list(current_indexes),
                start=unit_start,
                end=unit_end,
                source_text=" ".join(part for part in current_text_parts if part).strip(),
            )
        )
    return units


def _duration_weighted_token_split(text: str, durations: list[float]) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return ["" for _ in durations]
    tokens = [token for token in normalized.split() if token.strip()]
    if len(durations) == 1:
        return [normalized]
    if not tokens:
        return ["" for _ in durations]

    total_duration = sum(max(0.001, d) for d in durations)
    if total_duration <= 0.0:
        total_duration = float(len(durations))
    target_counts: list[int] = []
    remaining_tokens = len(tokens)
    remaining_duration = total_duration
    for idx, duration in enumerate(durations):
        if idx == len(durations) - 1:
            count = remaining_tokens
        else:
            ratio = max(0.001, duration) / max(0.001, remaining_duration)
            count = max(1, int(round(remaining_tokens * ratio)))
            max_allowed = remaining_tokens - (len(durations) - idx - 1)
            count = min(count, max_allowed)
        target_counts.append(count)
        remaining_tokens -= count
        remaining_duration -= max(0.001, duration)

    parts: list[str] = []
    cursor = 0
    for count in target_counts:
        chunk = tokens[cursor : cursor + count]
        cursor += count
        parts.append(" ".join(chunk).strip())
    if cursor < len(tokens):
        parts[-1] = (parts[-1] + " " + " ".join(tokens[cursor:])).strip()
    return parts


def split_unit_translation_to_segments(
    *,
    translated_text: str,
    segments: list[TranslationInputSegment],
) -> tuple[list[str], str]:
    count = len(segments)
    normalized = translated_text.strip()
    if count == 0:
        return [], "empty"
    if count == 1:
        return [normalized], "single"
    if not normalized:
        return ["" for _ in range(count)], "empty"

    punct_parts = [part.strip() for part in _SPLIT_BOUNDARY_RE.split(normalized) if part.strip()]
    if len(punct_parts) == count:
        return punct_parts, "punctuation_split"

    durations = [max(0.05, float(seg.duration)) for seg in segments]
    duration_parts = _duration_weighted_token_split(normalized, durations)
    if len(duration_parts) < count:
        duration_parts.extend([""] * (count - len(duration_parts)))
    duration_parts = duration_parts[:count]
    for idx, part in enumerate(duration_parts):
        if part.strip():
            continue
        duration_parts[idx] = normalized if count == 1 else (segments[idx].source_text.strip() or normalized)
    return duration_parts, "duration_split"


def expand_unit_translations_to_segments(
    *,
    input_doc: TranslationInputDocument,
    units: list[TranslationUnit],
    translated_unit_texts: list[str],
) -> tuple[list[str], list[int | None], list[dict[str, Any] | None], dict[str, Any]]:
    if len(units) != len(translated_unit_texts):
        raise ValueError("Unit translation count must match unit count.")
    translated_texts: list[str] = ["" for _ in input_doc.segments]
    unit_ids: list[int | None] = [None for _ in input_doc.segments]
    quality_hints: list[dict[str, Any] | None] = [None for _ in input_doc.segments]
    split_method_counts: dict[str, int] = {}
    multi_segment_unit_count = 0
    for unit, unit_translation in zip(units, translated_unit_texts, strict=True):
        segment_list = [input_doc.segments[index] for index in unit.segment_indexes]
        if len(segment_list) > 1:
            multi_segment_unit_count += 1
        parts, split_method = split_unit_translation_to_segments(
            translated_text=unit_translation,
            segments=segment_list,
        )
        split_method_counts[split_method] = split_method_counts.get(split_method, 0) + 1
        for local_idx, segment_index in enumerate(unit.segment_indexes):
            part = parts[local_idx].strip() if local_idx < len(parts) else ""
            if not part and unit_translation.strip():
                part = unit_translation.strip()
            translated_texts[segment_index] = part
            unit_ids[segment_index] = unit.unit_id
            quality_hints[segment_index] = {
                "split_method": split_method,
                "unit_segment_count": len(unit.segment_indexes),
            }
    metrics = {
        "unit_count": len(units),
        "multi_segment_unit_count": multi_segment_unit_count,
        "avg_segments_per_unit": (len(input_doc.segments) / len(units)) if units else 0.0,
        "split_method_counts": split_method_counts,
    }
    return translated_texts, unit_ids, quality_hints, metrics

