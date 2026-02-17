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
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_json_path, doc.to_dict())
    return output_json_path
