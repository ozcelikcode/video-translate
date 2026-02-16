from __future__ import annotations

from statistics import mean
from typing import Any

from video_translate.config import TranslateConfig
from video_translate.translate.contracts import TranslationOutputDocument
from video_translate.translate.glossary import contains_term


_TERMINAL_PUNCTUATION = {".", "!", "?"}


def _terminal_punctuation(text: str) -> str | None:
    normalized = text.strip()
    if not normalized:
        return None
    # Handle ellipsis variants first.
    if normalized.endswith("..."):
        return "."
    last_char = normalized[-1]
    if last_char in _TERMINAL_PUNCTUATION:
        return last_char
    return None


def build_m2_qa_report(
    doc: TranslationOutputDocument,
    config: TranslateConfig,
    *,
    glossary: dict[str, str] | None = None,
) -> dict[str, Any]:
    empty_target_count = sum(1 for segment in doc.segments if not segment.target_text.strip())
    ratios = [segment.length_ratio for segment in doc.segments if segment.length_ratio is not None]
    low_ratio_count = sum(1 for ratio in ratios if ratio < config.min_length_ratio)
    high_ratio_count = sum(1 for ratio in ratios if ratio > config.max_length_ratio)

    punctuation_mismatch_count = 0
    source_terminal_count = 0
    target_terminal_count = 0
    if config.qa_check_terminal_punctuation:
        for segment in doc.segments:
            source_terminal = _terminal_punctuation(segment.source_text)
            target_terminal = _terminal_punctuation(segment.target_text)
            if source_terminal is not None:
                source_terminal_count += 1
            if target_terminal is not None:
                target_terminal_count += 1
            if source_terminal != target_terminal:
                punctuation_mismatch_count += 1

    glossary_map = glossary or {}
    expected_term_count = 0
    matched_term_count = 0
    missed_term_count = 0
    term_miss_samples: list[dict[str, object]] = []
    for segment in doc.segments:
        for source_term, target_term in glossary_map.items():
            if contains_term(
                segment.source_text,
                source_term,
                case_sensitive=config.glossary_case_sensitive,
            ):
                expected_term_count += 1
                if contains_term(
                    segment.target_text,
                    target_term,
                    case_sensitive=config.glossary_case_sensitive,
                ):
                    matched_term_count += 1
                else:
                    missed_term_count += 1
                    if len(term_miss_samples) < 20:
                        term_miss_samples.append(
                            {
                                "segment_id": segment.id,
                                "source_term": source_term,
                                "expected_target_term": target_term,
                            }
                        )

    quality_flags: list[str] = []
    if empty_target_count > 0:
        quality_flags.append("empty_target_segments_present")
    if low_ratio_count > 0:
        quality_flags.append("length_ratio_below_min_present")
    if high_ratio_count > 0:
        quality_flags.append("length_ratio_above_max_present")
    if config.qa_check_terminal_punctuation and punctuation_mismatch_count > 0:
        quality_flags.append("terminal_punctuation_mismatch_present")
    if missed_term_count > 0:
        quality_flags.append("glossary_term_miss_present")

    return {
        "stage": "m2",
        "backend": doc.backend,
        "source_language": doc.source_language,
        "target_language": doc.target_language,
        "segment_metrics": {
            "count": doc.segment_count,
            "empty_target_count": empty_target_count,
        },
        "length_ratio_metrics": {
            "min_threshold": config.min_length_ratio,
            "max_threshold": config.max_length_ratio,
            "avg_ratio": mean(ratios) if ratios else None,
            "min_ratio": min(ratios) if ratios else None,
            "max_ratio": max(ratios) if ratios else None,
            "below_min_count": low_ratio_count,
            "above_max_count": high_ratio_count,
        },
        "word_metrics": {
            "total_source_word_count": doc.total_source_word_count,
            "total_target_word_count": doc.total_target_word_count,
        },
        "punctuation_metrics": {
            "enabled": config.qa_check_terminal_punctuation,
            "source_terminal_count": source_terminal_count,
            "target_terminal_count": target_terminal_count,
            "mismatch_count": punctuation_mismatch_count,
        },
        "terminology_metrics": {
            "glossary_path": str(config.glossary_path) if config.glossary_path else None,
            "glossary_case_sensitive": config.glossary_case_sensitive,
            "expected_term_count": expected_term_count,
            "matched_term_count": matched_term_count,
            "missed_term_count": missed_term_count,
            "match_ratio": (matched_term_count / expected_term_count) if expected_term_count > 0 else None,
            "miss_samples": term_miss_samples,
        },
        "quality_flags": quality_flags,
    }
