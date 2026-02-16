from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_glossary(glossary_path: Path | None) -> dict[str, str]:
    if glossary_path is None:
        return {}
    if not glossary_path.exists():
        raise FileNotFoundError(f"Glossary file not found: {glossary_path}")

    payload = json.loads(glossary_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Glossary JSON must be an object of source->target terms.")

    glossary: dict[str, str] = {}
    for key, value in payload.items():
        source = str(key).strip()
        target = str(value).strip()
        if source and target:
            glossary[source] = target
    return glossary


def _term_pattern(term: str) -> str:
    escaped = re.escape(term)
    # Keep multi-word terms strict on word boundaries at edges.
    return rf"\b{escaped}\b"


def apply_glossary(
    text: str,
    glossary: dict[str, str],
    *,
    case_sensitive: bool,
) -> str:
    if not glossary or not text.strip():
        return text

    result = text
    flags = 0 if case_sensitive else re.IGNORECASE
    for source_term in sorted(glossary.keys(), key=len, reverse=True):
        target_term = glossary[source_term]
        result = re.sub(_term_pattern(source_term), target_term, result, flags=flags)
    return result


def contains_term(text: str, term: str, *, case_sensitive: bool) -> bool:
    if not text.strip() or not term.strip():
        return False
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.search(_term_pattern(term), text, flags=flags) is not None

