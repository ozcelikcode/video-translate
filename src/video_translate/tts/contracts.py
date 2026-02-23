from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TTSInputSegment:
    id: int
    start: float
    end: float
    duration: float
    target_text: str
    target_word_count: int
    source_timing_hints: dict[str, Any] | None = None
    boundary_hints: dict[str, Any] | None = None


@dataclass(frozen=True)
class TTSInputDocument:
    schema_version: str
    stage: str
    generated_at_utc: str
    language: str
    segment_count: int
    total_target_word_count: int
    segments: list[TTSInputSegment]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TTSOutputSegment:
    id: int
    start: float
    end: float
    target_duration: float
    synthesized_duration: float
    duration_delta: float
    target_text: str
    audio_path: str
    scheduled_start: float | None = None
    scheduled_end: float | None = None
    stabilization_applied: bool = False
    fit_strategy: str = "none"


@dataclass(frozen=True)
class TTSOutputDocument:
    schema_version: str
    stage: str
    generated_at_utc: str
    backend: str
    language: str
    sample_rate: int
    segment_count: int
    segments: list[TTSOutputSegment]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _count_words(text: str) -> int:
    return len([part for part in text.split() if part.strip()])


def _normalize_optional_dict(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        normalized[str(key)] = item
    return normalized or None


def build_tts_input_document_from_translation_output(
    *,
    translation_output_payload: dict[str, Any],
    target_language_override: str | None = None,
) -> TTSInputDocument:
    stage = str(translation_output_payload.get("stage", "")).strip()
    if stage != "m2_translation_output":
        raise ValueError("Expected stage 'm2_translation_output'.")

    language = str(translation_output_payload.get("target_language", "")).strip()
    if target_language_override is not None:
        language = target_language_override.strip() or language
    if not language:
        raise ValueError("Translation output requires target language.")

    segments_payload = translation_output_payload.get("segments", [])
    if not isinstance(segments_payload, list):
        raise ValueError("Translation output field 'segments' must be a list.")

    segments: list[TTSInputSegment] = []
    for raw in segments_payload:
        if not isinstance(raw, dict):
            raise ValueError("Each translation output segment must be an object.")
        target_text = str(raw.get("target_text", "")).strip()
        segments.append(
            TTSInputSegment(
                id=int(raw.get("id", len(segments))),
                start=float(raw.get("start", 0.0)),
                end=float(raw.get("end", 0.0)),
                duration=max(0.0, float(raw.get("duration", 0.0))),
                target_text=target_text,
                target_word_count=int(raw.get("target_word_count", _count_words(target_text))),
                source_timing_hints=_normalize_optional_dict(raw.get("source_timing_hints")),
                boundary_hints=_normalize_optional_dict(raw.get("boundary_hints")),
            )
        )

    return TTSInputDocument(
        schema_version="1.0",
        stage="m3_tts_input",
        generated_at_utc=datetime.now(tz=UTC).isoformat(),
        language=language,
        segment_count=len(segments),
        total_target_word_count=sum(segment.target_word_count for segment in segments),
        segments=segments,
    )


def parse_tts_input_document(payload: dict[str, Any]) -> TTSInputDocument:
    stage = str(payload.get("stage", "")).strip()
    if stage != "m3_tts_input":
        raise ValueError("Expected stage 'm3_tts_input'.")

    language = str(payload.get("language", "")).strip()
    if not language:
        raise ValueError("TTS input requires language.")

    segments_payload = payload.get("segments", [])
    if not isinstance(segments_payload, list):
        raise ValueError("TTS input field 'segments' must be a list.")

    segments: list[TTSInputSegment] = []
    for raw in segments_payload:
        if not isinstance(raw, dict):
            raise ValueError("Each TTS input segment must be an object.")
        target_text = str(raw.get("target_text", "")).strip()
        start = float(raw.get("start", 0.0))
        end = float(raw.get("end", start))
        duration = max(0.0, float(raw.get("duration", end - start)))
        segments.append(
            TTSInputSegment(
                id=int(raw.get("id", len(segments))),
                start=start,
                end=end,
                duration=duration,
                target_text=target_text,
                target_word_count=int(raw.get("target_word_count", _count_words(target_text))),
                source_timing_hints=_normalize_optional_dict(raw.get("source_timing_hints")),
                boundary_hints=_normalize_optional_dict(raw.get("boundary_hints")),
            )
        )

    return TTSInputDocument(
        schema_version=str(payload.get("schema_version", "1.0")),
        stage=stage,
        generated_at_utc=str(payload.get("generated_at_utc", "")),
        language=language,
        segment_count=int(payload.get("segment_count", len(segments))),
        total_target_word_count=int(
            payload.get(
                "total_target_word_count",
                sum(segment.target_word_count for segment in segments),
            )
        ),
        segments=segments,
    )


def build_tts_output_document(
    *,
    input_doc: TTSInputDocument,
    backend: str,
    sample_rate: int,
    segment_audio_paths: list[Path],
    synthesized_durations: list[float],
    scheduled_starts: list[float] | None = None,
    scheduled_ends: list[float] | None = None,
    stabilization_applied_flags: list[bool] | None = None,
    fit_strategies: list[str] | None = None,
) -> TTSOutputDocument:
    if len(segment_audio_paths) != len(input_doc.segments):
        raise ValueError("Audio path count must match segment count.")
    if len(synthesized_durations) != len(input_doc.segments):
        raise ValueError("Synthesized duration count must match segment count.")
    if scheduled_starts is not None and len(scheduled_starts) != len(input_doc.segments):
        raise ValueError("Scheduled start count must match segment count.")
    if scheduled_ends is not None and len(scheduled_ends) != len(input_doc.segments):
        raise ValueError("Scheduled end count must match segment count.")
    if stabilization_applied_flags is not None and len(stabilization_applied_flags) != len(input_doc.segments):
        raise ValueError("Stabilization flag count must match segment count.")
    if fit_strategies is not None and len(fit_strategies) != len(input_doc.segments):
        raise ValueError("Fit strategy count must match segment count.")

    segments: list[TTSOutputSegment] = []
    if scheduled_starts is None:
        scheduled_starts = [segment.start for segment in input_doc.segments]
    if scheduled_ends is None:
        scheduled_ends = [
            float(start) + float(duration)
            for start, duration in zip(scheduled_starts, synthesized_durations, strict=True)
        ]
    if stabilization_applied_flags is None:
        stabilization_applied_flags = [False] * len(input_doc.segments)
    if fit_strategies is None:
        fit_strategies = ["none"] * len(input_doc.segments)

    for segment, audio_path, synthesized_duration, scheduled_start, scheduled_end, stabilization_applied, fit_strategy in zip(
        input_doc.segments,
        segment_audio_paths,
        synthesized_durations,
        scheduled_starts,
        scheduled_ends,
        stabilization_applied_flags,
        fit_strategies,
        strict=True,
    ):
        segments.append(
            TTSOutputSegment(
                id=segment.id,
                start=segment.start,
                end=segment.end,
                target_duration=segment.duration,
                synthesized_duration=synthesized_duration,
                duration_delta=synthesized_duration - segment.duration,
                target_text=segment.target_text,
                audio_path=str(audio_path),
                scheduled_start=float(scheduled_start),
                scheduled_end=float(scheduled_end),
                stabilization_applied=bool(stabilization_applied),
                fit_strategy=str(fit_strategy),
            )
        )

    return TTSOutputDocument(
        schema_version="1.0",
        stage="m3_tts_output",
        generated_at_utc=datetime.now(tz=UTC).isoformat(),
        backend=backend,
        language=input_doc.language,
        sample_rate=sample_rate,
        segment_count=len(segments),
        segments=segments,
    )
