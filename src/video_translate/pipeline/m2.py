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
from video_translate.translate.entities import (
    count_preserved_entity_hits,
    load_preserved_entities,
    mask_entities_for_translation,
    restore_masked_entities,
)
from video_translate.translate.glossary import apply_glossary, load_glossary
from video_translate.translate.punctuation import build_tts_render_text, restore_target_punctuation
from video_translate.translate.regroup import (
    build_translation_units,
    expand_unit_translations_to_segments,
)


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
    regroup_start = perf_counter()
    translation_units = build_translation_units(
        input_doc,
        enabled=getattr(config.translate, "regroup_enabled", True),
        max_segments=max(1, int(getattr(config.translate, "regroup_max_segments", 4))),
        gap_threshold_seconds=max(
            0.0,
            float(getattr(config.translate, "regroup_gap_threshold_seconds", 0.65)),
        ),
    )
    regroup_seconds = perf_counter() - regroup_start

    entities = (
        load_preserved_entities(getattr(config.translate, "entities_path", None))
        if getattr(config.translate, "apply_entity_preservation", True)
        else []
    )
    entity_mask_start = perf_counter()
    unit_source_texts = [unit.source_text for unit in translation_units]
    masked_unit_texts: list[str] = []
    unit_placeholder_maps: list[dict[str, str]] = []
    unit_preserved_entities: list[list[str]] = []
    for unit_text in unit_source_texts:
        masked_text, placeholder_map, preserved = mask_entities_for_translation(unit_text, entities)
        masked_unit_texts.append(masked_text)
        unit_placeholder_maps.append(placeholder_map)
        unit_preserved_entities.append(preserved)
    entity_mask_seconds = perf_counter() - entity_mask_start

    unique_texts, text_to_unique_index = _build_unique_text_index(masked_unit_texts)
    translate_start = perf_counter()
    translated_unique_texts = backend.translate_batch(
        unique_texts,
        source_language=input_doc.source_language,
        target_language=input_doc.target_language,
        batch_size=config.translate.batch_size,
    )
    translate_seconds = perf_counter() - translate_start
    translated_unit_masked_texts = [translated_unique_texts[index] for index in text_to_unique_index]
    entity_restore_start = perf_counter()
    translated_unit_texts = [
        restore_masked_entities(text, placeholder_map)
        for text, placeholder_map in zip(
            translated_unit_masked_texts, unit_placeholder_maps, strict=True
        )
    ]
    entity_restore_seconds = perf_counter() - entity_restore_start
    split_back_start = perf_counter()
    translated_texts, translation_unit_ids, translation_quality_hints, translation_unit_metrics = (
        expand_unit_translations_to_segments(
            input_doc=input_doc,
            units=translation_units,
            translated_unit_texts=translated_unit_texts,
        )
    )
    split_back_seconds = perf_counter() - split_back_start
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

    punctuation_start = perf_counter()
    normalized_target_texts: list[str] = []
    tts_render_texts: list[str | None] = []
    preserved_entities_per_segment: list[list[str] | None] = []
    entity_expected_total = 0
    entity_matched_total = 0
    entity_miss_samples: list[dict[str, Any]] = []
    punctuation_terminal_restored_count = 0
    punctuation_pause_added_count = 0
    tts_render_changed_count = 0
    for index, (segment, translated_text) in enumerate(zip(input_doc.segments, translated_texts, strict=True)):
        canonical_text = translated_text.strip()
        punctuation_hints: dict[str, Any] = {}
        if getattr(config.translate, "punctuation_restore_enabled", True):
            canonical_text, punctuation_hints = restore_target_punctuation(
                source_text=segment.source_text,
                target_text=canonical_text,
            )
        tts_render_text: str | None = None
        tts_hints: dict[str, Any] = {}
        if getattr(config.translate, "generate_tts_render_text", True):
            tts_render_text, tts_hints = build_tts_render_text(
                target_text=canonical_text,
                source_text=segment.source_text,
            )
        normalized_target_texts.append(canonical_text)
        tts_render_texts.append(tts_render_text)
        if punctuation_hints.get("terminal_restored"):
            punctuation_terminal_restored_count += 1
        if punctuation_hints.get("pause_punctuation_added"):
            punctuation_pause_added_count += 1
        if tts_hints.get("tts_render_text_changed"):
            tts_render_changed_count += 1

        expected_count, matched_count, matched_entities = count_preserved_entity_hits(
            source_text=segment.source_text,
            target_text=canonical_text,
            entities=entities,
        )
        entity_expected_total += expected_count
        entity_matched_total += matched_count
        preserved_entities_per_segment.append(matched_entities or None)
        if expected_count > matched_count and len(entity_miss_samples) < 20:
            entity_miss_samples.append(
                {
                    "segment_id": segment.id,
                    "source_text": segment.source_text,
                    "target_text": canonical_text,
                }
            )

        hints = dict(translation_quality_hints[index] or {})
        hints.update(punctuation_hints)
        hints.update(
            {
                "tts_render_text_changed": bool(tts_hints.get("tts_render_text_changed")),
                "tts_terminal_forced": bool(tts_hints.get("tts_terminal_forced")),
            }
        )
        if expected_count > 0:
            hints["preserved_entity_expected_count"] = expected_count
            hints["preserved_entity_matched_count"] = matched_count
        translation_quality_hints[index] = hints
    punctuation_seconds = perf_counter() - punctuation_start

    output_contract_start = perf_counter()
    output_doc = build_translation_output_document(
        input_doc=input_doc,
        translated_texts=normalized_target_texts,
        backend=backend.name,
        tts_render_texts=tts_render_texts,
        translation_unit_ids=translation_unit_ids,
        preserved_entities_list=preserved_entities_per_segment,
        translation_quality_hints_list=translation_quality_hints,
    )
    output_contract_seconds = perf_counter() - output_contract_start

    qa_start = perf_counter()
    qa_report = build_m2_qa_report(
        output_doc,
        config.translate,
        glossary=glossary,
        translation_unit_metrics=translation_unit_metrics,
        entity_preservation_metrics={
            "enabled": bool(getattr(config.translate, "apply_entity_preservation", True)),
            "entities_path": (
                str(getattr(config.translate, "entities_path", ""))
                if getattr(config.translate, "entities_path", None)
                else None
            ),
            "configured_entity_count": len(entities),
            "expected_entity_hits": entity_expected_total,
            "matched_entity_hits": entity_matched_total,
            "missed_entity_hits": max(0, entity_expected_total - entity_matched_total),
            "match_ratio": (
                (entity_matched_total / entity_expected_total)
                if entity_expected_total > 0
                else None
            ),
            "miss_samples": entity_miss_samples,
        },
        punctuation_restoration_metrics={
            "enabled": bool(getattr(config.translate, "punctuation_restore_enabled", True)),
            "terminal_restored_count": punctuation_terminal_restored_count,
            "pause_punctuation_added_count": punctuation_pause_added_count,
            "tts_render_text_changed_count": tts_render_changed_count,
            "tts_render_text_present_ratio": (
                sum(1 for item in tts_render_texts if item and item.strip()) / len(tts_render_texts)
                if tts_render_texts
                else 0.0
            ),
        },
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
                "regroup_translation_units": regroup_seconds,
                "entity_masking": entity_mask_seconds,
                "entity_restore": entity_restore_seconds,
                "split_back_units_to_segments": split_back_seconds,
                "glossary_postprocess": glossary_seconds,
                "punctuation_and_tts_render_text": punctuation_seconds,
                "build_output_contract": output_contract_seconds,
                "build_qa_report": qa_seconds,
                "write_outputs": write_seconds,
                "total_pipeline": total_seconds,
            },
            "translation_units": translation_unit_metrics,
            "entity_preservation": {
                "configured_entity_count": len(entities),
                "expected_entity_hits": entity_expected_total,
                "matched_entity_hits": entity_matched_total,
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
