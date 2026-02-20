from __future__ import annotations

import re
from statistics import mean
from typing import Any

from video_translate.config import TranslateConfig
from video_translate.translate.contracts import TranslationOutputDocument
from video_translate.translate.glossary import contains_term


_TERMINAL_PUNCTUATION = {".", "!", "?"}
_PAUSE_PUNCTUATION = {",", ";", ":"}
_WORD_PATTERN = re.compile(r"[A-Za-z\u00C7\u011E\u0130\u00D6\u015E\u00DC\u00E7\u011F\u0131\u00F6\u015F\u00FC']+")
_TURKISH_CHARACTERS = set(
    "\u00E7\u011F\u0131\u00F6\u015F\u00FC\u00C7\u011E\u0130\u00D6\u015E\u00DC"
)
_TURKISH_STOPWORDS = {
    "ve",
    "bir",
    "bu",
    "da",
    "de",
    "icin",
    "ile",
    "ama",
    "gibi",
    "cok",
    "mi",
    "mu",
    "ne",
    "nasil",
    "evet",
    "hayir",
}
_LANGUAGE_MISMATCH_RATIO_THRESHOLD = 0.50


def _looks_like_turkish(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return True
    if any(char in _TURKISH_CHARACTERS for char in normalized):
        return True

    words = [token.lower() for token in _WORD_PATTERN.findall(normalized)]
    if not words:
        return False
    return any(word in _TURKISH_STOPWORDS for word in words)


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

    long_segment_count = 0
    long_segment_missing_terminal_count = 0
    long_segment_excessive_pause_count = 0
    fluency_issue_samples: list[dict[str, object]] = []
    if config.qa_check_long_segment_fluency:
        for segment in doc.segments:
            target_text = segment.target_text.strip()
            target_word_count = segment.target_word_count
            if target_word_count < config.qa_long_segment_word_threshold:
                continue
            long_segment_count += 1

            target_terminal = _terminal_punctuation(target_text)
            if target_terminal is None:
                long_segment_missing_terminal_count += 1
                if len(fluency_issue_samples) < 20:
                    fluency_issue_samples.append(
                        {
                            "segment_id": segment.id,
                            "issue": "missing_terminal_punctuation",
                            "target_word_count": target_word_count,
                        }
                    )

            pause_punct_count = sum(target_text.count(mark) for mark in _PAUSE_PUNCTUATION)
            if pause_punct_count > config.qa_long_segment_max_pause_punct:
                long_segment_excessive_pause_count += 1
                if len(fluency_issue_samples) < 20:
                    fluency_issue_samples.append(
                        {
                            "segment_id": segment.id,
                            "issue": "excessive_pause_punctuation",
                            "target_word_count": target_word_count,
                            "pause_punctuation_count": pause_punct_count,
                            "max_allowed": config.qa_long_segment_max_pause_punct,
                        }
                    )

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

    language_check_enabled = doc.target_language.strip().lower() == "tr"
    non_target_like_segment_count = 0
    non_target_like_segment_samples: list[dict[str, object]] = []
    non_empty_target_segment_count = 0
    if language_check_enabled:
        for segment in doc.segments:
            target_text = segment.target_text.strip()
            if not target_text:
                continue
            non_empty_target_segment_count += 1
            if _looks_like_turkish(target_text):
                continue
            non_target_like_segment_count += 1
            if len(non_target_like_segment_samples) < 20:
                non_target_like_segment_samples.append(
                    {
                        "segment_id": segment.id,
                        "target_text": target_text,
                    }
                )
    non_target_like_segment_ratio = (
        non_target_like_segment_count / non_empty_target_segment_count
        if non_empty_target_segment_count > 0
        else 0.0
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
    if (
        config.qa_check_long_segment_fluency
        and (long_segment_missing_terminal_count > 0 or long_segment_excessive_pause_count > 0)
    ):
        quality_flags.append("long_segment_fluency_issue_present")
    if (
        language_check_enabled
        and non_target_like_segment_ratio >= _LANGUAGE_MISMATCH_RATIO_THRESHOLD
    ):
        quality_flags.append("target_language_mismatch_suspected")

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
        "fluency_metrics": {
            "enabled": config.qa_check_long_segment_fluency,
            "long_segment_word_threshold": config.qa_long_segment_word_threshold,
            "long_segment_max_pause_punct": config.qa_long_segment_max_pause_punct,
            "long_segment_count": long_segment_count,
            "missing_terminal_count": long_segment_missing_terminal_count,
            "excessive_pause_count": long_segment_excessive_pause_count,
            "issue_samples": fluency_issue_samples,
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
        "language_consistency_metrics": {
            "enabled": language_check_enabled,
            "target_language": doc.target_language,
            "non_empty_target_segment_count": non_empty_target_segment_count,
            "non_target_like_segment_count": non_target_like_segment_count,
            "non_target_like_segment_ratio": non_target_like_segment_ratio,
            "mismatch_ratio_threshold": _LANGUAGE_MISMATCH_RATIO_THRESHOLD,
            "samples": non_target_like_segment_samples,
        },
        "quality_flags": quality_flags,
    }
