from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WordTimestamp:
    word: str
    start: float
    end: float
    probability: float


@dataclass(frozen=True)
class TranscriptSegment:
    id: int
    start: float
    end: float
    text: str
    words: list[WordTimestamp]


@dataclass(frozen=True)
class TranscriptDocument:
    language: str
    language_probability: float
    duration: float
    segments: list[TranscriptSegment]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DownloadResult:
    source_url: str
    media_path: Path
    info_json_path: Path | None


@dataclass(frozen=True)
class M1Artifacts:
    run_root: Path
    source_media: Path
    normalized_audio: Path
    transcript_json: Path
    transcript_srt: Path | None
    qa_report: Path
    run_manifest: Path
