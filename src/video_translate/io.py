from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from video_translate.models import TranscriptDocument, TranscriptSegment


@dataclass(frozen=True)
class RunPaths:
    root: Path
    input_dir: Path
    work_audio_dir: Path
    output_transcript_dir: Path
    output_qa_dir: Path
    logs_dir: Path


def create_run_paths(workspace_dir: Path, run_id: str | None) -> RunPaths:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    selected_run_id = run_id or f"m1_{timestamp}"
    root = workspace_dir / selected_run_id
    paths = RunPaths(
        root=root,
        input_dir=root / "input",
        work_audio_dir=root / "work" / "audio",
        output_transcript_dir=root / "output" / "transcript",
        output_qa_dir=root / "output" / "qa",
        logs_dir=root / "logs",
    )
    for directory in (
        paths.root,
        paths.input_dir,
        paths.work_audio_dir,
        paths.output_transcript_dir,
        paths.output_qa_dir,
        paths.logs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=False)
    return paths


def write_transcript_json(path: Path, doc: TranscriptDocument) -> None:
    path.write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _format_srt_time(seconds: float) -> str:
    total_ms = int(max(seconds, 0.0) * 1000)
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(path: Path, segments: list[TranscriptSegment]) -> None:
    lines: list[str] = []
    for idx, segment in enumerate(segments, start=1):
        lines.append(str(idx))
        lines.append(f"{_format_srt_time(segment.start)} --> {_format_srt_time(segment.end)}")
        lines.append(segment.text.strip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
