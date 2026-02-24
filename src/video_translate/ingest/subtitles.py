from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any


_TIMESTAMP_RE = re.compile(
    r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})[.,](?P<ms>\d{3})"
)
_TIMESTAMP_SHORT_RE = re.compile(
    r"(?P<m>\d{1,2}):(?P<s>\d{2})[.,](?P<ms>\d{3})"
)
_TAG_RE = re.compile(r"<[^>]+>")
_MULTISPACE_RE = re.compile(r"\s+")


def _parse_timestamp(raw: str) -> float | None:
    text = raw.strip()
    match = _TIMESTAMP_RE.fullmatch(text)
    if match:
        return (
            int(match.group("h")) * 3600
            + int(match.group("m")) * 60
            + int(match.group("s"))
            + (int(match.group("ms")) / 1000.0)
        )
    match_short = _TIMESTAMP_SHORT_RE.fullmatch(text)
    if match_short:
        return (
            int(match_short.group("m")) * 60
            + int(match_short.group("s"))
            + (int(match_short.group("ms")) / 1000.0)
        )
    return None


def _clean_subtitle_text(text: str) -> str:
    value = html.unescape(text)
    value = _TAG_RE.sub("", value)
    value = value.replace("\ufeff", "")
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    # Remove leading speaker labels like "Speaker: ..." when obvious.
    if len(lines) == 1:
        candidate = lines[0]
        if ":" in candidate:
            head, tail = candidate.split(":", 1)
            if 1 <= len(head.strip()) <= 24 and head.strip().replace(" ", "").isalpha():
                candidate = tail.strip() or candidate
        lines = [candidate]
    normalized = " ".join(lines)
    normalized = _MULTISPACE_RE.sub(" ", normalized).strip()
    return normalized


def _parse_vtt_lines(lines: list[str]) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    index = 0
    if lines and lines[0].strip().upper().startswith("WEBVTT"):
        index = 1
    current_text_lines: list[str] = []
    current_start: float | None = None
    current_end: float | None = None

    def flush() -> None:
        nonlocal current_text_lines, current_start, current_end
        if current_start is None or current_end is None:
            current_text_lines = []
            current_start = None
            current_end = None
            return
        text = _clean_subtitle_text("\n".join(current_text_lines))
        if text:
            cues.append(
                {
                    "start": float(current_start),
                    "end": float(current_end),
                    "duration": max(0.0, float(current_end) - float(current_start)),
                    "text": text,
                }
            )
        current_text_lines = []
        current_start = None
        current_end = None

    while index < len(lines):
        line = lines[index].rstrip("\n")
        stripped = line.strip()
        if not stripped:
            flush()
            index += 1
            continue
        if "-->" in stripped:
            flush()
            left, right = [part.strip() for part in stripped.split("-->", 1)]
            right_time = right.split(" ", 1)[0].strip()
            current_start = _parse_timestamp(left)
            current_end = _parse_timestamp(right_time)
            index += 1
            continue
        # Skip cue IDs and NOTE lines.
        if stripped.upper().startswith("NOTE") and current_start is None:
            index += 1
            continue
        if current_start is None and stripped.isdigit():
            index += 1
            continue
        current_text_lines.append(line)
        index += 1
    flush()
    return cues


def parse_subtitle_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Subtitle file not found: {path}")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    cues = _parse_vtt_lines(lines)
    # If parsing as VTT yields nothing, try a very permissive SRT-style pass
    # (same parser works for SRT timestamps too, so usually unnecessary).
    return cues


def build_normalized_subtitle_payload(
    *,
    manual_path: Path | None,
    auto_path: Path | None,
) -> dict[str, Any]:
    manual_cues = parse_subtitle_file(manual_path) if manual_path else []
    auto_cues = parse_subtitle_file(auto_path) if auto_path else []
    return {
        "stage": "m1_subtitles_normalized",
        "manual": {
            "path": str(manual_path) if manual_path else None,
            "cue_count": len(manual_cues),
            "cues": manual_cues,
        },
        "auto": {
            "path": str(auto_path) if auto_path else None,
            "cue_count": len(auto_cues),
            "cues": auto_cues,
        },
    }

