from __future__ import annotations

from statistics import mean
from typing import Any

from video_translate.config import TTSConfig
from video_translate.tts.contracts import TTSOutputDocument


def build_m3_qa_report(doc: TTSOutputDocument, config: TTSConfig) -> dict[str, Any]:
    absolute_deltas = [abs(segment.duration_delta) for segment in doc.segments]
    out_of_tolerance_count = sum(
        1
        for delta in absolute_deltas
        if delta > config.max_duration_delta_seconds
    )
    empty_text_count = sum(1 for segment in doc.segments if not segment.target_text.strip())

    quality_flags: list[str] = []
    if out_of_tolerance_count > 0:
        quality_flags.append("duration_out_of_tolerance_present")
    if empty_text_count > 0:
        quality_flags.append("empty_tts_text_present")

    return {
        "stage": "m3",
        "backend": doc.backend,
        "language": doc.language,
        "segment_metrics": {
            "count": doc.segment_count,
            "empty_text_count": empty_text_count,
        },
        "duration_metrics": {
            "max_duration_delta_seconds": config.max_duration_delta_seconds,
            "mean_abs_delta_seconds": mean(absolute_deltas) if absolute_deltas else 0.0,
            "max_abs_delta_seconds": max(absolute_deltas) if absolute_deltas else 0.0,
            "out_of_tolerance_count": out_of_tolerance_count,
        },
        "quality_flags": quality_flags,
    }
