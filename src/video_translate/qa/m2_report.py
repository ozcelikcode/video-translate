from __future__ import annotations

from statistics import mean
from typing import Any

from video_translate.config import TranslateConfig
from video_translate.translate.contracts import TranslationOutputDocument


def build_m2_qa_report(doc: TranslationOutputDocument, config: TranslateConfig) -> dict[str, Any]:
    empty_target_count = sum(1 for segment in doc.segments if not segment.target_text.strip())
    ratios = [segment.length_ratio for segment in doc.segments if segment.length_ratio is not None]
    low_ratio_count = sum(1 for ratio in ratios if ratio < config.min_length_ratio)
    high_ratio_count = sum(1 for ratio in ratios if ratio > config.max_length_ratio)

    quality_flags: list[str] = []
    if empty_target_count > 0:
        quality_flags.append("empty_target_segments_present")
    if low_ratio_count > 0:
        quality_flags.append("length_ratio_below_min_present")
    if high_ratio_count > 0:
        quality_flags.append("length_ratio_above_max_present")

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
        "quality_flags": quality_flags,
    }

