from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
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
    run_manifest_json: Path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _build_unique_text_index(texts: list[str]) -> tuple[list[str], list[int]]:
    unique_texts: list[str] = []
    unique_lookup: dict[str, int] = {}
    text_to_unique_index: list[int] = []
    for text in texts:
        key = text.strip()
        index = unique_lookup.get(key)
        if index is None:
            index = len(unique_texts)
            unique_lookup[key] = index
            unique_texts.append(text)
        text_to_unique_index.append(index)
    return unique_texts, text_to_unique_index


def _blocked_quality_flags(qa_report: dict[str, Any], allowed_flags: tuple[str, ...]) -> list[str]:
    allowed = set(allowed_flags)
    raw_flags = qa_report.get("quality_flags", [])
    if not isinstance(raw_flags, list):
        return []
    normalized = [str(flag) for flag in raw_flags]
    return [flag for flag in normalized if flag not in allowed]


def run_m2_pipeline(
    *,
    translation_input_json_path: Path,
    output_json_path: Path,
    qa_report_json_path: Path,
    run_manifest_json_path: Path,
    config: AppConfig,
    target_language_override: str | None = None,
) -> M2Artifacts:
    pipeline_start = perf_counter()
    if not translation_input_json_path.exists():
        raise FileNotFoundError(f"Translation input JSON not found: {translation_input_json_path}")

    read_start = perf_counter()
    input_payload = _read_json(translation_input_json_path)
    input_doc = parse_translation_input_document(input_payload)
    read_seconds = perf_counter() - read_start

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
    unique_texts, text_to_unique_index = _build_unique_text_index(source_texts)
    translate_start = perf_counter()
    translated_unique_texts = backend.translate_batch(
        unique_texts,
        source_language=input_doc.source_language,
        target_language=input_doc.target_language,
        batch_size=config.translate.batch_size,
    )
    translate_seconds = perf_counter() - translate_start
    translated_texts = [translated_unique_texts[index] for index in text_to_unique_index]
    if config.translate.apply_glossary_postprocess and glossary:
        glossary_start = perf_counter()
        translated_texts = [
            apply_glossary(
                text,
                glossary,
                case_sensitive=config.translate.glossary_case_sensitive,
            )
            for text in translated_texts
        ]
        glossary_seconds = perf_counter() - glossary_start
    else:
        glossary_seconds = 0.0

    output_contract_start = perf_counter()
    output_doc = build_translation_output_document(
        input_doc=input_doc,
        translated_texts=translated_texts,
        backend=backend.name,
    )
    output_contract_seconds = perf_counter() - output_contract_start

    qa_start = perf_counter()
    qa_report = build_m2_qa_report(
        output_doc,
        config.translate,
        glossary=glossary,
    )
    qa_seconds = perf_counter() - qa_start

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    qa_report_json_path.parent.mkdir(parents=True, exist_ok=True)
    run_manifest_json_path.parent.mkdir(parents=True, exist_ok=True)
    write_start = perf_counter()
    write_json(output_json_path, output_doc.to_dict())
    write_json(qa_report_json_path, qa_report)
    write_seconds = perf_counter() - write_start
    blocked_flags = _blocked_quality_flags(qa_report, config.translate.qa_allowed_flags)
    qa_gate_passed = not blocked_flags
    total_seconds = perf_counter() - pipeline_start
    write_json(
        run_manifest_json_path,
        {
            "stage": "m2",
            "backend": backend.name,
            "inputs": {
                "translation_input_json": str(translation_input_json_path),
            },
            "outputs": {
                "translation_output_json": str(output_json_path),
                "qa_report_json": str(qa_report_json_path),
            },
            "speed": {
                "source_segment_count": len(source_texts),
                "unique_source_text_count": len(unique_texts),
                "translation_reuse_count": len(source_texts) - len(unique_texts),
            },
            "timings_seconds": {
                "read_input": read_seconds,
                "translate_backend": translate_seconds,
                "glossary_postprocess": glossary_seconds,
                "build_output_contract": output_contract_seconds,
                "build_qa_report": qa_seconds,
                "write_outputs": write_seconds,
                "total_pipeline": total_seconds,
            },
            "qa_gate": {
                "enabled": config.translate.qa_fail_on_flags,
                "passed": qa_gate_passed,
                "allowed_flags": list(config.translate.qa_allowed_flags),
                "blocked_flags": blocked_flags,
            },
        },
    )
    if config.translate.qa_fail_on_flags and not qa_gate_passed:
        raise RuntimeError(
            "M2 QA gate failed. Blocked quality flags: " + ", ".join(blocked_flags)
        )

    return M2Artifacts(
        translation_input_json=translation_input_json_path,
        translation_output_json=output_json_path,
        qa_report_json=qa_report_json_path,
        run_manifest_json=run_manifest_json_path,
    )
