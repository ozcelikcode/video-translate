from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_preserved_entities(path: Path | None) -> list[str]:
    if path is None:
        return []
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    items: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            source = str(key).strip()
            enabled = True if not isinstance(value, bool) else bool(value)
            if source and enabled:
                items.append(source)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    items.append(text)
            elif isinstance(item, dict):
                text = str(item.get("source_term", "")).strip()
                enabled = bool(item.get("enabled", True))
                if text and enabled:
                    items.append(text)
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return sorted(deduped, key=len, reverse=True)


def mask_entities_for_translation(
    text: str,
    entities: list[str],
) -> tuple[str, dict[str, str], list[str]]:
    if not text.strip() or not entities:
        return text, {}, []
    result = text
    placeholder_map: dict[str, str] = {}
    preserved: list[str] = []
    placeholder_index = 0
    for entity in entities:
        pattern = re.compile(rf"\b{re.escape(entity)}\b", flags=re.IGNORECASE)

        def _repl(match: re.Match[str]) -> str:
            nonlocal placeholder_index
            original = match.group(0)
            placeholder = f"VTPRESERVE{placeholder_index}TOKEN"
            placeholder_index += 1
            placeholder_map[placeholder] = original
            preserved.append(original)
            return placeholder

        result = pattern.sub(_repl, result)
    return result, placeholder_map, preserved


def restore_masked_entities(text: str, placeholder_map: dict[str, str]) -> str:
    if not placeholder_map:
        return text
    result = text
    for placeholder, original in placeholder_map.items():
        result = result.replace(placeholder, original)
    return result


def count_preserved_entity_hits(
    *,
    source_text: str,
    target_text: str,
    entities: list[str],
) -> tuple[int, int, list[str]]:
    expected = 0
    matched = 0
    matched_entities: list[str] = []
    for entity in entities:
        if not re.search(rf"\b{re.escape(entity)}\b", source_text, flags=re.IGNORECASE):
            continue
        expected += 1
        if re.search(rf"\b{re.escape(entity)}\b", target_text, flags=re.IGNORECASE):
            matched += 1
            matched_entities.append(entity)
    return expected, matched, matched_entities

