import json
from pathlib import Path

from video_translate.translate.glossary import apply_glossary, contains_term, load_glossary


def test_load_glossary_reads_json_mapping(tmp_path: Path) -> None:
    glossary_path = tmp_path / "glossary.json"
    glossary_path.write_text(
        json.dumps(
            {
                "machine learning": "makine ogrenmesi",
                "open source": "acik kaynak",
            }
        ),
        encoding="utf-8",
    )

    glossary = load_glossary(glossary_path)

    assert glossary["machine learning"] == "makine ogrenmesi"
    assert glossary["open source"] == "acik kaynak"


def test_apply_glossary_rewrites_terms_case_insensitive() -> None:
    text = "Machine Learning is part of open source AI."
    glossary = {
        "machine learning": "makine ogrenmesi",
        "open source": "acik kaynak",
    }

    rewritten = apply_glossary(text, glossary, case_sensitive=False)

    assert "makine ogrenmesi" in rewritten
    assert "acik kaynak" in rewritten
    assert contains_term(rewritten, "makine ogrenmesi", case_sensitive=False)
