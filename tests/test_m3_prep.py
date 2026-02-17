import json
from pathlib import Path

from video_translate.pipeline.m3_prep import prepare_m3_tts_input


def test_prepare_m3_tts_input_from_translation_output(tmp_path: Path) -> None:
    translation_output = tmp_path / "output" / "translate" / "translation_output.en-tr.json"
    translation_output.parent.mkdir(parents=True, exist_ok=True)
    translation_output.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "stage": "m2_translation_output",
                "generated_at_utc": "2026-02-17T10:00:00Z",
                "backend": "mock",
                "source_language": "en",
                "target_language": "tr",
                "segment_count": 1,
                "total_source_word_count": 2,
                "total_target_word_count": 2,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 1.5,
                        "duration": 1.5,
                        "source_text": "hello world",
                        "target_text": "merhaba dunya",
                        "source_word_count": 2,
                        "target_word_count": 2,
                        "length_ratio": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_json = tmp_path / "output" / "tts" / "tts_input.tr.json"

    generated = prepare_m3_tts_input(
        translation_output_json_path=translation_output,
        output_json_path=output_json,
        target_language="tr",
    )

    assert generated == output_json
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["stage"] == "m3_tts_input"
    assert payload["segment_count"] == 1
    segment = payload["segments"][0]
    assert segment["target_text"] == "merhaba dunya"
