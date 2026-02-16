import json
from pathlib import Path

from video_translate.config import (
    ASRConfig,
    AppConfig,
    PipelineConfig,
    ToolConfig,
    TranslateConfig,
    TranslateTransformersConfig,
)
from video_translate.pipeline.m2 import run_m2_pipeline


def _build_app_config() -> AppConfig:
    return AppConfig(
        tools=ToolConfig(yt_dlp="yt-dlp", ffmpeg="ffmpeg"),
        pipeline=PipelineConfig(
            workspace_dir=Path("runs"),
            audio_sample_rate=16000,
            audio_channels=1,
            audio_codec="pcm_s16le",
        ),
        asr=ASRConfig(
            model="medium",
            device="auto",
            compute_type="default",
            beam_size=5,
            language="en",
            word_timestamps=True,
            vad_filter=True,
            fallback_on_oom=True,
            fallback_model="small",
            fallback_device="cpu",
            fallback_compute_type="int8",
        ),
        translate=TranslateConfig(
            backend="mock",
            source_language="en",
            target_language="tr",
            batch_size=8,
            min_length_ratio=0.50,
            max_length_ratio=1.80,
            glossary_path=None,
            glossary_case_sensitive=False,
            apply_glossary_postprocess=True,
            qa_check_terminal_punctuation=True,
            transformers=TranslateTransformersConfig(
                model_id="Helsinki-NLP/opus-mt-en-tr",
                device=-1,
                max_new_tokens=256,
            ),
        ),
    )


def test_run_m2_pipeline_with_mock_backend(tmp_path: Path) -> None:
    translation_input = tmp_path / "output" / "translate" / "translation_input.en-tr.json"
    translation_input.parent.mkdir(parents=True, exist_ok=True)
    translation_input.write_text(
        json.dumps(
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
                        "end": 2.0,
                        "duration": 2.0,
                        "source_text": "hello world",
                        "source_word_count": 2,
                    },
                    {
                        "id": 1,
                        "start": 3.0,
                        "end": 5.0,
                        "duration": 2.0,
                        "source_text": "this is a test",
                        "source_word_count": 4,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    output_json = tmp_path / "output" / "translate" / "translation_output.en-tr.json"
    qa_report_json = tmp_path / "output" / "qa" / "m2_qa_report.json"
    config = _build_app_config()

    artifacts = run_m2_pipeline(
        translation_input_json_path=translation_input,
        output_json_path=output_json,
        qa_report_json_path=qa_report_json,
        config=config,
    )

    assert artifacts.translation_output_json == output_json
    assert artifacts.qa_report_json == qa_report_json

    output_payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert output_payload["stage"] == "m2_translation_output"
    assert output_payload["backend"] == "mock"
    assert output_payload["segment_count"] == 2

    qa_payload = json.loads(qa_report_json.read_text(encoding="utf-8"))
    assert qa_payload["stage"] == "m2"
    assert qa_payload["backend"] == "mock"
    assert "quality_flags" in qa_payload
    assert "punctuation_metrics" in qa_payload
    assert "terminology_metrics" in qa_payload
