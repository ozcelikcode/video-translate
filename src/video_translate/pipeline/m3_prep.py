from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from video_translate.io import write_json
from video_translate.tts.contracts import build_tts_input_document_from_translation_output


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _tail_risk_from_text(text: str) -> float:
    normalized = text.strip()
    if not normalized:
        return 0.0
    risk = 0.0
    if normalized.endswith("-"):
        risk += 0.55
    if normalized.endswith(("...", "…")):
        risk += 0.30
    if normalized.endswith((",", ";", ":", "ve", "ama")):
        risk += 0.18
    last_char = normalized[-1]
    if last_char not in {".", "!", "?"}:
        risk += 0.22
    return min(1.0, risk)


def _head_risk_from_text(text: str) -> float:
    normalized = text.strip()
    if not normalized:
        return 0.0
    risk = 0.0
    first_char = normalized[0]
    if first_char.isalpha() and first_char.islower():
        risk += 0.32
    if normalized.startswith((",", ".", ":", ";", "-", "—")):
        risk += 0.25
    if normalized.split(" ", 1)[0].lower() in {"ve", "ama", "veya", "ya", "da"}:
        risk += 0.18
    return min(1.0, risk)


def _safe_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timing_hint_float(segment_payload: dict[str, Any], key: str) -> float | None:
    hints = segment_payload.get("source_timing_hints")
    if not isinstance(hints, dict):
        return None
    return _safe_float(hints.get(key))


def _build_boundary_hints(segments_payload: list[dict[str, Any]]) -> None:
    for index, current in enumerate(segments_payload):
        prev_segment = segments_payload[index - 1] if index > 0 else None
        next_segment = segments_payload[index + 1] if index + 1 < len(segments_payload) else None

        current_start = _safe_float(current.get("start")) or 0.0
        current_end = _safe_float(current.get("end")) or current_start
        prev_end = (_safe_float(prev_segment.get("end")) if prev_segment else None)
        next_start = (_safe_float(next_segment.get("start")) if next_segment else None)

        gap_from_prev = (
            max(0.0, current_start - prev_end) if prev_end is not None else None
        )
        gap_to_next = (
            max(0.0, next_start - current_end) if next_start is not None else None
        )

        trailing_prev_silence = (
            _timing_hint_float(prev_segment, "trailing_silence_seconds") if prev_segment else None
        )
        leading_current_silence = _timing_hint_float(current, "leading_silence_seconds")
        trailing_current_silence = _timing_hint_float(current, "trailing_silence_seconds")
        leading_next_silence = (
            _timing_hint_float(next_segment, "leading_silence_seconds") if next_segment else None
        )

        left_gap_budget = gap_from_prev if gap_from_prev is not None else 0.0
        right_gap_budget = gap_to_next if gap_to_next is not None else 0.0
        if trailing_prev_silence is not None:
            left_gap_budget = min(left_gap_budget, max(0.0, trailing_prev_silence + 0.06))
        if leading_current_silence is not None:
            left_gap_budget = min(left_gap_budget, max(0.0, left_gap_budget + leading_current_silence))
        if trailing_current_silence is not None:
            right_gap_budget = min(right_gap_budget, max(0.0, right_gap_budget + trailing_current_silence))
        if leading_next_silence is not None:
            right_gap_budget = min(right_gap_budget, max(0.0, right_gap_budget + leading_next_silence))

        current_text = str(current.get("target_text", ""))
        prev_text = str(prev_segment.get("target_text", "")) if prev_segment else ""
        next_text = str(next_segment.get("target_text", "")) if next_segment else ""

        continuation_risk_prev = 0.0
        if prev_segment is not None:
            continuation_risk_prev = min(1.0, _tail_risk_from_text(prev_text) + _head_risk_from_text(current_text))
            if gap_from_prev is not None and gap_from_prev <= 0.12:
                continuation_risk_prev = min(1.0, continuation_risk_prev + 0.20)

        continuation_risk_next = 0.0
        if next_segment is not None:
            continuation_risk_next = min(1.0, _tail_risk_from_text(current_text) + _head_risk_from_text(next_text))
            if gap_to_next is not None and gap_to_next <= 0.12:
                continuation_risk_next = min(1.0, continuation_risk_next + 0.20)

        current["boundary_hints"] = {
            "gap_from_prev_seconds": gap_from_prev,
            "gap_to_next_seconds": gap_to_next,
            "can_borrow_left_gap_seconds": max(0.0, left_gap_budget),
            "can_borrow_right_gap_seconds": max(0.0, right_gap_budget),
            "continuation_risk_prev": continuation_risk_prev,
            "continuation_risk_next": continuation_risk_next,
            "boundary_cut_risk_score": max(continuation_risk_prev, continuation_risk_next),
        }


def prepare_m3_tts_input(
    *,
    translation_output_json_path: Path,
    output_json_path: Path,
    target_language: str | None = None,
) -> Path:
    if not translation_output_json_path.exists():
        raise FileNotFoundError(
            f"Translation output JSON not found: {translation_output_json_path}"
        )
    payload = _read_json(translation_output_json_path)
    doc = build_tts_input_document_from_translation_output(
        translation_output_payload=payload,
        target_language_override=target_language,
    )
    output_payload = doc.to_dict()
    raw_segments = output_payload.get("segments", [])
    if isinstance(raw_segments, list):
        _build_boundary_hints([segment for segment in raw_segments if isinstance(segment, dict)])
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_json_path, output_payload)
    return output_json_path
