from video_translate.translate.contracts import (
    build_translation_output_document,
    parse_translation_input_document,
)


def test_parse_translation_input_document() -> None:
    payload = {
        "schema_version": "1.0",
        "stage": "m2_translation_input",
        "generated_at_utc": "2026-02-16T10:00:00Z",
        "source_language": "en",
        "target_language": "tr",
        "segment_count": 1,
        "total_source_word_count": 2,
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 1.0,
                "duration": 1.0,
                "source_text": "hello world",
                "source_word_count": 2,
            }
        ],
    }

    doc = parse_translation_input_document(payload)
    assert doc.stage == "m2_translation_input"
    assert doc.source_language == "en"
    assert doc.target_language == "tr"
    assert len(doc.segments) == 1


def test_build_translation_output_document() -> None:
    input_doc = parse_translation_input_document(
        {
            "schema_version": "1.0",
            "stage": "m2_translation_input",
            "generated_at_utc": "2026-02-16T10:00:00Z",
            "source_language": "en",
            "target_language": "tr",
            "segment_count": 2,
            "total_source_word_count": 4,
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 1.0,
                    "duration": 1.0,
                    "source_text": "hello world",
                    "source_word_count": 2,
                },
                {
                    "id": 1,
                    "start": 1.0,
                    "end": 2.0,
                    "duration": 1.0,
                    "source_text": "good morning",
                    "source_word_count": 2,
                },
            ],
        }
    )

    output_doc = build_translation_output_document(
        input_doc=input_doc,
        translated_texts=["merhaba dunya", "gunaydin"],
        backend="mock",
    )

    assert output_doc.stage == "m2_translation_output"
    assert output_doc.backend == "mock"
    assert output_doc.segment_count == 2
    assert output_doc.total_source_word_count == 4
    assert output_doc.total_target_word_count == 3
