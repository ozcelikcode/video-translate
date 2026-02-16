import json
from pathlib import Path

from video_translate.pipeline.m2_prep import prepare_m2_translation_input


def test_prepare_m2_translation_input_writes_contract(tmp_path: Path) -> None:
    transcript_path = tmp_path / "output" / "transcript" / "transcript.en.json"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        json.dumps(
            {
                "language": "en",
                "language_probability": 0.99,
                "duration": 12.0,
                "segments": [
                    {"id": 0, "start": 0.0, "end": 2.0, "text": "hello world"},
                    {"id": 1, "start": 3.0, "end": 6.5, "text": "this is a test"},
                ],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "output" / "translate" / "translation_input.en-tr.json"

    written = prepare_m2_translation_input(
        transcript_json_path=transcript_path,
        output_json_path=output_path,
        target_language="tr",
    )

    assert written == output_path
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["stage"] == "m2_translation_input"
    assert payload["source_language"] == "en"
    assert payload["target_language"] == "tr"
    assert payload["segment_count"] == 2
    assert payload["total_source_word_count"] == 6
