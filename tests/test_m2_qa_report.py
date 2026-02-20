from pathlib import Path

from video_translate.config import TranslateConfig, TranslateTransformersConfig
from video_translate.qa.m2_report import build_m2_qa_report
from video_translate.translate.contracts import (
    build_translation_output_document,
    parse_translation_input_document,
)


def _translate_config() -> TranslateConfig:
    return TranslateConfig(
        backend="mock",
        source_language="en",
        target_language="tr",
        batch_size=8,
        min_length_ratio=0.5,
        max_length_ratio=1.8,
        glossary_path=Path("configs/glossary.en-tr.json"),
        glossary_case_sensitive=False,
        apply_glossary_postprocess=True,
        qa_check_terminal_punctuation=True,
        qa_check_long_segment_fluency=True,
        qa_long_segment_word_threshold=6,
        qa_long_segment_max_pause_punct=2,
        qa_fail_on_flags=False,
        qa_allowed_flags=(),
        transformers=TranslateTransformersConfig(
            model_id="facebook/m2m100_418M",
            device=-1,
            max_new_tokens=256,
            source_lang_code=None,
            target_lang_code=None,
        ),
    )


def test_build_m2_qa_report_with_glossary_and_punctuation_flags() -> None:
    input_doc = parse_translation_input_document(
        {
            "schema_version": "1.0",
            "stage": "m2_translation_input",
            "generated_at_utc": "2026-02-16T10:00:00Z",
            "source_language": "en",
            "target_language": "tr",
            "segment_count": 2,
            "total_source_word_count": 5,
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 1.0,
                    "duration": 1.0,
                    "source_text": "Open source is great.",
                    "source_word_count": 4,
                },
                {
                    "id": 1,
                    "start": 1.0,
                    "end": 2.0,
                    "duration": 1.0,
                    "source_text": "Dataset?",
                    "source_word_count": 1,
                },
            ],
        }
    )
    output_doc = build_translation_output_document(
        input_doc=input_doc,
        translated_texts=[
            "acik kaynak harika?",
            "veri kumesi.",
        ],
        backend="mock",
    )
    report = build_m2_qa_report(
        output_doc,
        _translate_config(),
        glossary={
            "open source": "acik kaynak",
            "dataset": "veri kumesi",
        },
    )

    punctuation_metrics = report["punctuation_metrics"]
    assert isinstance(punctuation_metrics, dict)
    assert punctuation_metrics["mismatch_count"] == 2

    terminology_metrics = report["terminology_metrics"]
    assert isinstance(terminology_metrics, dict)
    assert terminology_metrics["expected_term_count"] == 2
    assert terminology_metrics["matched_term_count"] == 2

    flags = report["quality_flags"]
    assert isinstance(flags, list)
    assert "terminal_punctuation_mismatch_present" in flags


def test_build_m2_qa_report_long_segment_fluency_flags() -> None:
    input_doc = parse_translation_input_document(
        {
            "schema_version": "1.0",
            "stage": "m2_translation_input",
            "generated_at_utc": "2026-02-16T10:00:00Z",
            "source_language": "en",
            "target_language": "tr",
            "segment_count": 1,
            "total_source_word_count": 10,
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 4.0,
                    "duration": 4.0,
                    "source_text": "This is a longer source sentence for quality checks.",
                    "source_word_count": 9,
                }
            ],
        }
    )
    output_doc = build_translation_output_document(
        input_doc=input_doc,
        translated_texts=[
            "bu daha uzun bir ceviri metni, cok fazla ara duraklama, ritmi bozuyor, akiciligi dusuruyor",
        ],
        backend="mock",
    )
    report = build_m2_qa_report(output_doc, _translate_config(), glossary={})

    fluency_metrics = report["fluency_metrics"]
    assert isinstance(fluency_metrics, dict)
    assert fluency_metrics["long_segment_count"] == 1
    assert fluency_metrics["missing_terminal_count"] == 1
    assert fluency_metrics["excessive_pause_count"] == 1

    flags = report["quality_flags"]
    assert isinstance(flags, list)
    assert "long_segment_fluency_issue_present" in flags


def test_build_m2_qa_report_flags_target_language_mismatch_for_tr() -> None:
    input_doc = parse_translation_input_document(
        {
            "schema_version": "1.0",
            "stage": "m2_translation_input",
            "generated_at_utc": "2026-02-16T10:00:00Z",
            "source_language": "en",
            "target_language": "tr",
            "segment_count": 2,
            "total_source_word_count": 6,
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 1.0,
                    "duration": 1.0,
                    "source_text": "This is an example.",
                    "source_word_count": 4,
                },
                {
                    "id": 1,
                    "start": 1.0,
                    "end": 2.0,
                    "duration": 1.0,
                    "source_text": "It should be Turkish.",
                    "source_word_count": 4,
                },
            ],
        }
    )
    output_doc = build_translation_output_document(
        input_doc=input_doc,
        translated_texts=[
            "This is still English.",
            "Another English sentence.",
        ],
        backend="mock",
    )

    report = build_m2_qa_report(output_doc, _translate_config(), glossary={})
    language_metrics = report["language_consistency_metrics"]
    assert isinstance(language_metrics, dict)
    assert language_metrics["enabled"] is True
    assert language_metrics["non_target_like_segment_count"] == 2
    assert language_metrics["non_target_like_segment_ratio"] == 1.0

    flags = report["quality_flags"]
    assert isinstance(flags, list)
    assert "target_language_mismatch_suspected" in flags


def test_build_m2_qa_report_does_not_flag_language_mismatch_when_tr_text_present() -> None:
    input_doc = parse_translation_input_document(
        {
            "schema_version": "1.0",
            "stage": "m2_translation_input",
            "generated_at_utc": "2026-02-16T10:00:00Z",
            "source_language": "en",
            "target_language": "tr",
            "segment_count": 2,
            "total_source_word_count": 6,
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 1.0,
                    "duration": 1.0,
                    "source_text": "This is an example.",
                    "source_word_count": 4,
                },
                {
                    "id": 1,
                    "start": 1.0,
                    "end": 2.0,
                    "duration": 1.0,
                    "source_text": "It should be Turkish.",
                    "source_word_count": 4,
                },
            ],
        }
    )
    output_doc = build_translation_output_document(
        input_doc=input_doc,
        translated_texts=[
            "bu bir testtir.",
            "ve gayet anlasilir bir metindir.",
        ],
        backend="mock",
    )

    report = build_m2_qa_report(output_doc, _translate_config(), glossary={})
    language_metrics = report["language_consistency_metrics"]
    assert isinstance(language_metrics, dict)
    assert language_metrics["non_target_like_segment_count"] == 0
    assert language_metrics["non_target_like_segment_ratio"] == 0.0

    flags = report["quality_flags"]
    assert isinstance(flags, list)
    assert "target_language_mismatch_suspected" not in flags
