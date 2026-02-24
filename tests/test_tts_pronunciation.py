import json
from pathlib import Path

from video_translate.tts.text_normalizer import load_pronunciation_lexicon, normalize_tts_text


def test_load_pronunciation_lexicon_supports_list_format(tmp_path: Path) -> None:
    lexicon_path = tmp_path / "pronunciation.tr.json"
    lexicon_path.write_text(
        json.dumps(
            [
                {
                    "source_term": "Microsoft",
                    "match_mode": "word",
                    "replacement_text_tr": "Maykrosoft",
                    "piper_raw_phonemes": "m aj k r o s o f t",
                    "enabled": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    entries = load_pronunciation_lexicon(lexicon_path)
    assert len(entries) == 1
    assert entries[0]["source_term"] == "Microsoft"


def test_normalize_tts_text_applies_lexicon_and_backend_specific_override() -> None:
    text, metrics = normalize_tts_text(
        text="Microsoft burada",
        backend_name="espeak",
        lexicon_entries=[
            {
                "source_term": "Microsoft",
                "match_mode": "word",
                "replacement_text_tr": "Maykrosoft",
                "espeak_override_text": "Maykrosoft",
                "priority": 1,
            }
        ],
        auto_brand_rules_enabled=False,
        backend_specific_overrides_enabled=True,
    )
    assert "Maykrosoft" in text
    assert metrics["lexicon_hit_count"] >= 1


def test_normalize_tts_text_auto_brand_rules_handle_acronyms() -> None:
    text, metrics = normalize_tts_text(
        text="GPU ve AI Microsoft",
        backend_name="piper",
        lexicon_entries=[],
        auto_brand_rules_enabled=True,
        backend_specific_overrides_enabled=True,
    )
    assert metrics["auto_rule_hit_count"] >= 1
    assert "Maykrosoft" in text or "[[" in text

