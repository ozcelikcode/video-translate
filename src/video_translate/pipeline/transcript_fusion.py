from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from video_translate.models import TranscriptDocument, TranscriptSegment


_NORMALIZE_TEXT_RE = re.compile(r"[^a-z0-9\u00e7\u011f\u0131\u00f6\u015f\u00fc\s]+", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")


def _normalize_text_for_match(text: str) -> str:
    normalized = text.strip().lower()
    normalized = _NORMALIZE_TEXT_RE.sub(" ", normalized)
    normalized = _SPACE_RE.sub(" ", normalized).strip()
    return normalized


def _token_count(text: str) -> int:
    return len([part for part in text.split() if part.strip()])


def _overlap_seconds(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def _best_overlapping_cue(
    *,
    segment: TranscriptSegment,
    cues: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, float, float]:
    best_cue: dict[str, Any] | None = None
    best_overlap = 0.0
    best_score = 0.0
    seg_duration = max(0.001, segment.end - segment.start)
    for cue in cues:
        try:
            cue_start = float(cue.get("start", 0.0))
            cue_end = float(cue.get("end", cue_start))
        except (TypeError, ValueError):
            continue
        overlap = _overlap_seconds(segment.start, segment.end, cue_start, cue_end)
        if overlap <= 0.0:
            continue
        cue_duration = max(0.001, cue_end - cue_start)
        overlap_ratio = overlap / max(seg_duration, cue_duration)
        # Score favors overlap and mild length agreement.
        score = overlap_ratio
        cue_text = str(cue.get("text", "")).strip()
        if cue_text:
            length_gap = abs(_token_count(cue_text) - _token_count(segment.text))
            score -= min(0.15, length_gap * 0.02)
        if score > best_score:
            best_score = score
            best_overlap = overlap
            best_cue = cue
    if best_cue is None:
        return None, 0.0, 0.0
    seg_duration = max(0.001, segment.end - segment.start)
    return best_cue, best_overlap, best_overlap / seg_duration


def _choose_segment_text(
    *,
    current_text: str,
    subtitle_text: str,
    subtitle_mode: str,
    overlap_ratio: float,
) -> tuple[str, str]:
    asr_text = current_text.strip()
    sub_text = subtitle_text.strip()
    if not sub_text:
        return asr_text, "asr"
    if subtitle_mode == "subtitle_primary":
        return sub_text, "subtitle"
    if subtitle_mode == "asr_primary":
        return (asr_text or sub_text), ("asr" if asr_text else "subtitle")

    # hybrid
    if not asr_text:
        return sub_text, "subtitle"
    asr_norm = _normalize_text_for_match(asr_text)
    sub_norm = _normalize_text_for_match(sub_text)
    if asr_norm == sub_norm:
        return asr_text, "fused"
    asr_tokens = _token_count(asr_text)
    sub_tokens = _token_count(sub_text)
    if overlap_ratio >= 0.50 and sub_tokens >= asr_tokens + 1:
        return sub_text, "fused"
    if asr_tokens <= 1 and sub_tokens >= 2 and overlap_ratio >= 0.30:
        return sub_text, "fused"
    return asr_text, "fused"


def _recover_subtitle_only_segments(
    *,
    existing_segments: list[TranscriptSegment],
    cues: list[dict[str, Any]],
    source_label: str,
    next_segment_id: int,
) -> list[TranscriptSegment]:
    recovered: list[TranscriptSegment] = []
    for cue in cues:
        text = str(cue.get("text", "")).strip()
        if not text:
            continue
        try:
            cue_start = float(cue.get("start", 0.0))
            cue_end = float(cue.get("end", cue_start))
        except (TypeError, ValueError):
            continue
        if cue_end <= cue_start:
            continue
        # Skip cues already substantially covered by an existing segment.
        covered = False
        for seg in existing_segments:
            overlap = _overlap_seconds(seg.start, seg.end, cue_start, cue_end)
            cue_duration = max(0.001, cue_end - cue_start)
            if overlap / cue_duration >= 0.55:
                covered = True
                break
        if covered:
            continue
        recovered.append(
            TranscriptSegment(
                id=next_segment_id + len(recovered),
                start=cue_start,
                end=cue_end,
                text=text,
                words=[],
                source_evidence=source_label,
                subtitle_text=text,
                subtitle_source=source_label,
                fusion_score=1.0,
                subtitle_overlap_ratio=1.0,
            )
        )
    return recovered


def fuse_transcript_with_subtitles(
    *,
    transcript: TranscriptDocument,
    manual_cues: list[dict[str, Any]] | None,
    auto_cues: list[dict[str, Any]] | None,
    subtitle_mode: str = "hybrid",
    use_subtitles: bool = True,
    allow_auto_subtitles: bool = True,
) -> TranscriptDocument:
    if not use_subtitles:
        return transcript
    manual_cues = manual_cues or []
    auto_cues = auto_cues or []
    if not manual_cues and not auto_cues:
        return transcript

    normalized_mode = subtitle_mode.strip().lower() if subtitle_mode else "hybrid"
    if normalized_mode not in {"hybrid", "subtitle_primary", "asr_primary"}:
        normalized_mode = "hybrid"

    fused_segments: list[TranscriptSegment] = []
    matched_manual = 0
    matched_auto = 0
    fused_count = 0
    asr_only_count = 0
    subtitle_only_recovered_count = 0

    for segment in transcript.segments:
        best_manual, _, manual_overlap_ratio = _best_overlapping_cue(segment=segment, cues=manual_cues)
        best_auto, _, auto_overlap_ratio = _best_overlapping_cue(segment=segment, cues=auto_cues) if allow_auto_subtitles else (None, 0.0, 0.0)

        selected_cue: dict[str, Any] | None = None
        selected_source: str | None = None
        selected_overlap_ratio = 0.0
        if best_manual is not None:
            selected_cue = best_manual
            selected_source = "subtitle_manual"
            selected_overlap_ratio = manual_overlap_ratio
            matched_manual += 1
        elif best_auto is not None:
            selected_cue = best_auto
            selected_source = "subtitle_auto"
            selected_overlap_ratio = auto_overlap_ratio
            matched_auto += 1

        if selected_cue is None:
            asr_only_count += 1
            fused_segments.append(
                replace(
                    segment,
                    source_evidence=segment.source_evidence or "asr",
                    subtitle_text=segment.subtitle_text,
                    subtitle_source=segment.subtitle_source,
                    fusion_score=segment.fusion_score,
                    subtitle_overlap_ratio=segment.subtitle_overlap_ratio,
                )
            )
            continue

        subtitle_text = str(selected_cue.get("text", "")).strip()
        chosen_text, chosen_source_kind = _choose_segment_text(
            current_text=segment.text,
            subtitle_text=subtitle_text,
            subtitle_mode=normalized_mode,
            overlap_ratio=selected_overlap_ratio,
        )
        if chosen_source_kind != "asr":
            fused_count += 1
        source_evidence = (
            selected_source
            if chosen_source_kind == "subtitle"
            else ("fused" if chosen_source_kind == "fused" else "asr")
        )
        fused_segments.append(
            replace(
                segment,
                text=chosen_text,
                source_evidence=source_evidence,
                subtitle_text=subtitle_text,
                subtitle_source=selected_source,
                fusion_score=selected_overlap_ratio,
                subtitle_overlap_ratio=selected_overlap_ratio,
            )
        )

    preferred_recovery_cues = manual_cues if manual_cues else (auto_cues if allow_auto_subtitles else [])
    preferred_source = "subtitle_manual" if manual_cues else "subtitle_auto"
    recovered = _recover_subtitle_only_segments(
        existing_segments=fused_segments,
        cues=preferred_recovery_cues,
        source_label=preferred_source,
        next_segment_id=max((seg.id for seg in fused_segments), default=-1) + 1,
    )
    subtitle_only_recovered_count = len(recovered)
    if recovered:
        fused_segments.extend(recovered)
        fused_segments.sort(key=lambda seg: (seg.start, seg.end, seg.id))
        fused_segments = [
            replace(seg, id=index)
            for index, seg in enumerate(fused_segments)
        ]

    subtitle_summary = {
        "subtitle_present": bool(manual_cues or auto_cues),
        "subtitle_manual_present": bool(manual_cues),
        "subtitle_auto_present": bool(auto_cues),
        "manual_cue_count": len(manual_cues),
        "auto_cue_count": len(auto_cues),
        "matched_manual_segments": matched_manual,
        "matched_auto_segments": matched_auto,
    }
    total_segments = len(fused_segments)
    fused_or_subtitle_segments = sum(
        1
        for seg in fused_segments
        if (seg.source_evidence or "asr") in {"fused", "subtitle_manual", "subtitle_auto"}
    )
    fusion_summary = {
        "subtitle_mode": normalized_mode,
        "segment_count_after_fusion": total_segments,
        "fused_segment_count": fused_count,
        "asr_only_segments": asr_only_count,
        "subtitle_only_recovered_segments": subtitle_only_recovered_count,
        "subtitle_asr_alignment_coverage_ratio": (
            fused_or_subtitle_segments / total_segments if total_segments > 0 else 0.0
        ),
    }
    return TranscriptDocument(
        language=transcript.language,
        language_probability=transcript.language_probability,
        duration=transcript.duration,
        segments=fused_segments,
        subtitle_summary=subtitle_summary,
        fusion_summary=fusion_summary,
        runtime_diagnostics=transcript.runtime_diagnostics,
    )

