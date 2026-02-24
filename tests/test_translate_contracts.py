from video_translate.translate.contracts import (
    build_translation_input_document,
    build_translation_output_document,
    parse_translation_input_document,
    parse_translation_output_document,
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


def test_build_translation_input_document_includes_source_timing_hints() -> None:
    transcript_payload = {
        "language": "en",
        "segments": [
            {
                "id": 7,
                "start": 1.0,
                "end": 2.0,
                "text": "hello world",
                "words": [
                    {"word": "hello", "start": 1.1, "end": 1.4},
                    {"word": "world", "start": 1.45, "end": 1.82},
                ],
            }
        ],
    }

    doc = build_translation_input_document(
        transcript_payload=transcript_payload,
        target_language="tr",
    )

    segment = doc.segments[0]
    assert segment.id == 7
    assert segment.source_timing_hints is not None
    assert segment.source_timing_hints["has_word_timestamps"] is True
    assert segment.source_timing_hints["first_word_start"] == 1.1
    assert segment.source_timing_hints["last_word_end"] == 1.82
    assert round(segment.source_timing_hints["leading_silence_seconds"], 6) == 0.1
    assert round(segment.source_timing_hints["trailing_silence_seconds"], 6) == 0.18
    assert segment.source_timing_hints["word_count_from_timestamps"] == 2


def test_build_translation_output_document_preserves_source_timing_hints() -> None:
    input_doc = parse_translation_input_document(
        {
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
                    "source_timing_hints": {
                        "has_word_timestamps": True,
                        "first_word_start": 0.05,
                        "last_word_end": 0.92,
                        "leading_silence_seconds": 0.05,
                        "trailing_silence_seconds": 0.08,
                        "word_count_from_timestamps": 2,
                    },
                }
            ],
        }
    )
    output_doc = build_translation_output_document(
        input_doc=input_doc,
        translated_texts=["merhaba dunya"],
        backend="mock",
    )

    assert output_doc.segments[0].source_timing_hints is not None
    assert output_doc.segments[0].source_timing_hints["trailing_silence_seconds"] == 0.08


def test_build_and_parse_translation_output_document_with_tts_render_text_and_metadata() -> None:
    input_doc = parse_translation_input_document(
        {
            "schema_version": "1.0",
            "stage": "m2_translation_input",
            "generated_at_utc": "2026-02-23T10:00:00Z",
            "source_language": "en",
            "target_language": "tr",
            "segment_count": 1,
            "total_source_word_count": 2,
            "segments": [
                {
                    "id": 5,
                    "start": 0.0,
                    "end": 1.0,
                    "duration": 1.0,
                    "source_text": "Hello Microsoft",
                    "source_word_count": 2,
                }
            ],
        }
    )
    output_doc = build_translation_output_document(
        input_doc=input_doc,
        translated_texts=["Merhaba Microsoft"],
        backend="mock",
        tts_render_texts=["Merhaba Maykrosoft."],
        translation_unit_ids=[2],
        preserved_entities_list=[["Microsoft"]],
        translation_quality_hints_list=[{"split_method": "single"}],
    )

    payload = output_doc.to_dict()
    parsed = parse_translation_output_document(payload)
    segment = parsed.segments[0]
    assert segment.tts_render_text == "Merhaba Maykrosoft."
    assert segment.translation_unit_id == 2
    assert segment.preserved_entities == ["Microsoft"]
    assert segment.translation_quality_hints["split_method"] == "single"
