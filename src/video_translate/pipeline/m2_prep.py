from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from video_translate.io import write_json
from video_translate.translate.contracts import build_translation_input_document


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def prepare_m2_translation_input(
    *,
    transcript_json_path: Path,
    output_json_path: Path,
    target_language: str = "tr",
) -> Path:
    if not transcript_json_path.exists():
        raise FileNotFoundError(f"Transcript JSON not found: {transcript_json_path}")

    transcript_payload = _read_json(transcript_json_path)
    doc = build_translation_input_document(
        transcript_payload=transcript_payload,
        target_language=target_language,
    )
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_json_path, doc.to_dict())
    return output_json_path

