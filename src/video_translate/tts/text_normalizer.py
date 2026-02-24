from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*")


def load_pronunciation_lexicon(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = []
    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        raw_items = []
        for key, value in payload.items():
            if isinstance(value, dict):
                raw_items.append({"source_term": key, **value})
            else:
                raw_items.append({"source_term": key, "replacement_text_tr": value})
    else:
        return []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        source_term = str(raw.get("source_term", "")).strip()
        if not source_term or not bool(raw.get("enabled", True)):
            continue
        entries.append(
            {
                "source_term": source_term,
                "match_mode": str(raw.get("match_mode", "word")).strip().lower() or "word",
                "replacement_text_tr": str(raw.get("replacement_text_tr", "")).strip() or None,
                "piper_raw_phonemes": str(raw.get("piper_raw_phonemes", "")).strip() or None,
                "espeak_override_text": str(raw.get("espeak_override_text", "")).strip() or None,
                "priority": int(raw.get("priority", 100)),
                "enabled": True,
            }
        )
    entries.sort(key=lambda item: (int(item["priority"]), -len(str(item["source_term"]))))
    return entries


def _compile_entry_pattern(entry: dict[str, Any]) -> re.Pattern[str]:
    source = str(entry["source_term"])
    mode = str(entry.get("match_mode", "word"))
    if mode == "regex":
        return re.compile(source, flags=re.IGNORECASE)
    if mode == "exact":
        return re.compile(rf"^{re.escape(source)}$", flags=re.IGNORECASE)
    return re.compile(rf"\b{re.escape(source)}\b", flags=re.IGNORECASE)


def _auto_brand_rules(text: str, backend_name: str) -> tuple[str, int]:
    replacements: list[tuple[str, str]] = [
        ("Microsoft", "Maykrosoft"),
        ("Windows", "Vindovs"),
        ("GitHub", "GitHab"),
        ("YouTube", "Yutub"),
        ("OpenAI", "Open Ey Ay"),
        ("NVIDIA", "Envidya"),
    ]
    result = text
    hit_count = 0
    for source, target in replacements:
        if re.search(rf"\b{re.escape(source)}\b", result, flags=re.IGNORECASE):
            result = re.sub(rf"\b{re.escape(source)}\b", target, result, flags=re.IGNORECASE)
            hit_count += 1

    # Acronym reading heuristic (e.g., CPU, GPU, AI)
    def _acronym_repl(match: re.Match[str]) -> str:
        token = match.group(0)
        if len(token) < 2 or len(token) > 6 or not token.isupper():
            return token
        mapping = {
            "A": "A",
            "B": "Be",
            "C": "Ce",
            "D": "De",
            "E": "E",
            "F": "Fe",
            "G": "Ce",
            "H": "Ha",
            "I": "Ay",
            "J": "Ce",
            "K": "Ka",
            "L": "El",
            "M": "Em",
            "N": "En",
            "O": "O",
            "P": "Pe",
            "Q": "Kyu",
            "R": "Ar",
            "S": "Es",
            "T": "Te",
            "U": "Yu",
            "V": "Vi",
            "W": "Dablıyu",
            "X": "Eks",
            "Y": "Vay",
            "Z": "Zed",
        }
        return " ".join(mapping.get(ch, ch) for ch in token)

    acronym_result = re.sub(r"\b[A-Z]{2,6}\b", _acronym_repl, result)
    if acronym_result != result:
        hit_count += 1
    return acronym_result, hit_count


def normalize_tts_text(
    *,
    text: str,
    backend_name: str,
    lexicon_entries: list[dict[str, Any]],
    auto_brand_rules_enabled: bool,
    backend_specific_overrides_enabled: bool,
) -> tuple[str, dict[str, Any]]:
    if not text.strip():
        return text, {
            "lexicon_hit_count": 0,
            "auto_rule_hit_count": 0,
            "unresolved_foreign_token_samples": [],
        }
    result = text
    lexicon_hits = 0
    for entry in lexicon_entries:
        pattern = _compile_entry_pattern(entry)
        backend_specific_replacement: str | None = None
        if backend_specific_overrides_enabled:
            if backend_name == "piper" and entry.get("piper_raw_phonemes"):
                backend_specific_replacement = f"[[{entry['piper_raw_phonemes']}]]"
            elif backend_name == "espeak" and entry.get("espeak_override_text"):
                backend_specific_replacement = str(entry["espeak_override_text"])
        replacement = backend_specific_replacement or entry.get("replacement_text_tr") or entry["source_term"]
        updated, count = pattern.subn(str(replacement), result)
        if count > 0:
            result = updated
            lexicon_hits += count

    auto_rule_hits = 0
    if auto_brand_rules_enabled:
        result, auto_rule_hits = _auto_brand_rules(result, backend_name)

    unresolved_tokens: list[str] = []
    for token in _WORD_RE.findall(result):
        if len(unresolved_tokens) >= 8:
            break
        if any(ch in token for ch in "çğıöşüÇĞİÖŞÜ"):
            continue
        if token.isdigit():
            continue
        # Ignore already phoneme-tagged piper chunks.
        if token.startswith("[[") or token.endswith("]]"):
            continue
        if token.lower() in {"ve", "bir", "ama", "merhaba"}:
            continue
        if re.fullmatch(r"[A-Z]{1,2}", token):
            continue
        if re.search(r"[A-Z]", token):
            unresolved_tokens.append(token)

    return result, {
        "lexicon_hit_count": lexicon_hits,
        "auto_rule_hit_count": auto_rule_hits,
        "unresolved_foreign_token_samples": unresolved_tokens,
    }

