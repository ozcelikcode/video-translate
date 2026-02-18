from __future__ import annotations

from statistics import mean
from typing import Any

from video_translate.config import TTSConfig
from video_translate.tts.contracts import TTSOutputDocument


def build_m3_qa_report(
    doc: TTSOutputDocument,
    config: TTSConfig,
    *,
    postfit_padding_segments: int = 0,
    postfit_trim_segments: int = 0,
    postfit_total_padded_seconds: float = 0.0,
    postfit_total_trimmed_seconds: float = 0.0,
) -> dict[str, Any]:
    absolute_deltas = [abs(segment.duration_delta) for segment in doc.segments]
    target_total_duration = sum(max(0.0, float(segment.target_duration)) for segment in doc.segments)
    postfit_modified_segments = max(0, int(postfit_padding_segments)) + max(0, int(postfit_trim_segments))
    postfit_segment_ratio = (
        postfit_modified_segments / doc.segment_count if doc.segment_count > 0 else 0.0
    )
    postfit_adjusted_seconds = max(0.0, float(postfit_total_padded_seconds)) + max(
        0.0, float(postfit_total_trimmed_seconds)
    )
    postfit_seconds_ratio = (
        postfit_adjusted_seconds / target_total_duration if target_total_duration > 0.0 else 0.0
    )
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
    if postfit_segment_ratio > config.qa_max_postfit_segment_ratio:
        quality_flags.append("postfit_segment_ratio_above_max")
    if postfit_seconds_ratio > config.qa_max_postfit_seconds_ratio:
        quality_flags.append("postfit_seconds_ratio_above_max")

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
        "postfit_metrics": {
            "max_segment_ratio": config.qa_max_postfit_segment_ratio,
            "max_seconds_ratio": config.qa_max_postfit_seconds_ratio,
            "target_total_duration_seconds": target_total_duration,
            "modified_segment_count": postfit_modified_segments,
            "modified_segment_ratio": postfit_segment_ratio,
            "total_adjusted_seconds": postfit_adjusted_seconds,
            "adjusted_seconds_ratio": postfit_seconds_ratio,
            "padding_segments": max(0, int(postfit_padding_segments)),
            "trim_segments": max(0, int(postfit_trim_segments)),
            "total_padded_seconds": max(0.0, float(postfit_total_padded_seconds)),
            "total_trimmed_seconds": max(0.0, float(postfit_total_trimmed_seconds)),
        },
        "quality_flags": quality_flags,
    }
