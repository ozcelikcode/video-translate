from __future__ import annotations

from statistics import mean
from typing import Any

from video_translate.models import TranscriptDocument


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0.0:
        return None
    return numerator / denominator


def build_m1_qa_report(doc: TranscriptDocument) -> dict[str, Any]:
    segment_count = len(doc.segments)
    segment_durations = [max(0.0, segment.end - segment.start) for segment in doc.segments]
    speech_duration = sum(segment_durations)
    empty_segment_count = sum(1 for segment in doc.segments if not segment.text.strip())

    words = [word for segment in doc.segments for word in segment.words]
    has_word_timestamps = bool(words)
    if words:
        word_count = len(words)
        probabilities = [word.probability for word in words]
    else:
        # Fallback when word timestamps are disabled or not available.
        word_count = sum(len(segment.text.split()) for segment in doc.segments)
        probabilities = []

    low_conf_threshold = 0.60
    low_conf_word_count = sum(1 for p in probabilities if p < low_conf_threshold)
    low_conf_word_ratio = _safe_ratio(float(low_conf_word_count), float(word_count))

    quality_flags: list[str] = []
    if segment_count == 0:
        quality_flags.append("no_segments")
    if empty_segment_count > 0:
        quality_flags.append("empty_segments_present")
    if low_conf_word_ratio is not None and low_conf_word_ratio > 0.20:
        quality_flags.append("high_low_confidence_word_ratio")

    return {
        "stage": "m1",
        "transcript_language": doc.language,
        "language_probability": doc.language_probability,
        "duration_seconds": doc.duration,
        "segment_metrics": {
            "count": segment_count,
            "empty_count": empty_segment_count,
            "avg_duration_seconds": mean(segment_durations) if segment_durations else 0.0,
            "speech_duration_seconds": speech_duration,
            "speech_coverage_ratio": _safe_ratio(speech_duration, doc.duration),
        },
        "word_metrics": {
            "has_word_timestamps": has_word_timestamps,
            "count": word_count,
            "low_confidence_threshold": low_conf_threshold,
            "low_confidence_count": low_conf_word_count,
            "low_confidence_ratio": low_conf_word_ratio,
            "avg_probability": mean(probabilities) if probabilities else None,
            "min_probability": min(probabilities) if probabilities else None,
            "max_probability": max(probabilities) if probabilities else None,
        },
        "quality_flags": quality_flags,
    }

