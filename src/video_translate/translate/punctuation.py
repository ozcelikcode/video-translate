from __future__ import annotations

import re
from typing import Any


_TERMINAL_PUNCT = (".", "!", "?")
_PAUSE_INSERT_RE = re.compile(r"\b(ama|fakat|ancak|ve|çünkü|bu yüzden)\b", flags=re.IGNORECASE)


def _source_terminal(source_text: str) -> str | None:
    normalized = source_text.strip()
    if not normalized:
        return None
    if normalized.endswith("..."):
        return "."
    for punct in _TERMINAL_PUNCT:
        if normalized.endswith(punct):
            return punct
    return None


def restore_target_punctuation(
    *,
    source_text: str,
    target_text: str,
) -> tuple[str, dict[str, Any]]:
    normalized_target = target_text.strip()
    if not normalized_target:
        return normalized_target, {"terminal_restored": False, "pause_punctuation_added": False}

    hints: dict[str, Any] = {
        "terminal_restored": False,
        "pause_punctuation_added": False,
    }
    source_terminal = _source_terminal(source_text)
    if source_terminal and not normalized_target.endswith(_TERMINAL_PUNCT):
        normalized_target = normalized_target.rstrip(" ,;:") + source_terminal
        hints["terminal_restored"] = True
    elif not source_terminal and len(normalized_target.split()) >= 10 and not normalized_target.endswith(_TERMINAL_PUNCT):
        normalized_target = normalized_target + "."
        hints["terminal_restored"] = True

    if "," not in normalized_target and len(normalized_target.split()) >= 9:
        punctuated = _PAUSE_INSERT_RE.sub(lambda m: f", {m.group(1)}", normalized_target, count=1)
        punctuated = punctuated.replace(", ,", ",")
        if punctuated != normalized_target:
            normalized_target = punctuated
            hints["pause_punctuation_added"] = True
    normalized_target = re.sub(r"\s+([,;:.!?])", r"\1", normalized_target)
    normalized_target = re.sub(r"\s{2,}", " ", normalized_target).strip()
    return normalized_target, hints


def build_tts_render_text(
    *,
    target_text: str,
    source_text: str,
) -> tuple[str, dict[str, Any]]:
    canonical_target, hints = restore_target_punctuation(source_text=source_text, target_text=target_text)
    tts_render_text = canonical_target
    # TTS-friendly small tweaks without changing meaning.
    tts_render_text = tts_render_text.replace("...", ".")
    tts_render_text = re.sub(r"\s{2,}", " ", tts_render_text).strip()
    if tts_render_text and tts_render_text[-1] not in ".!?":
        tts_render_text = tts_render_text + "."
        hints = {**hints, "tts_terminal_forced": True}
    else:
        hints = {**hints, "tts_terminal_forced": False}
    hints["tts_render_text_changed"] = tts_render_text != target_text.strip()
    return tts_render_text, hints

