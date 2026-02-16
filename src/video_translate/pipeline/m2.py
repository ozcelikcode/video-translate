from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from video_translate.config import AppConfig
from video_translate.io import write_json
from video_translate.qa.m2_report import build_m2_qa_report
from video_translate.translate.backends import build_translation_backend
from video_translate.translate.contracts import (
    build_translation_output_document,
    parse_translation_input_document,
)
from video_translate.translate.glossary import apply_glossary, load_glossary


@dataclass(frozen=True)
class M2Artifacts:
    translation_input_json: Path
    translation_output_json: Path
    qa_report_json: Path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def run_m2_pipeline(
    *,
    translation_input_json_path: Path,
    output_json_path: Path,
    qa_report_json_path: Path,
    config: AppConfig,
    target_language_override: str | None = None,
) -> M2Artifacts:
    if not translation_input_json_path.exists():
        raise FileNotFoundError(f"Translation input JSON not found: {translation_input_json_path}")

    input_payload = _read_json(translation_input_json_path)
    input_doc = parse_translation_input_document(input_payload)

    target_language = target_language_override or config.translate.target_language
    if input_doc.target_language != target_language:
        input_doc = parse_translation_input_document(
            {
                **input_doc.to_dict(),
                "target_language": target_language,
            }
        )

    backend = build_translation_backend(config.translate)
    glossary = load_glossary(config.translate.glossary_path)
    source_texts = [segment.source_text for segment in input_doc.segments]
    translated_texts = backend.translate_batch(
        source_texts,
        source_language=input_doc.source_language,
        target_language=input_doc.target_language,
        batch_size=config.translate.batch_size,
    )
    if config.translate.apply_glossary_postprocess and glossary:
        translated_texts = [
            apply_glossary(
                text,
                glossary,
                case_sensitive=config.translate.glossary_case_sensitive,
            )
            for text in translated_texts
        ]
    output_doc = build_translation_output_document(
        input_doc=input_doc,
        translated_texts=translated_texts,
        backend=backend.name,
    )
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    qa_report_json_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_json_path, output_doc.to_dict())
    write_json(
        qa_report_json_path,
        build_m2_qa_report(
            output_doc,
            config.translate,
            glossary=glossary,
        ),
    )

    return M2Artifacts(
        translation_input_json=translation_input_json_path,
        translation_output_json=output_json_path,
        qa_report_json=qa_report_json_path,
    )
