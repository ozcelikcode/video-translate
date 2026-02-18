import json
from pathlib import Path

import pytest

from video_translate.config import (
    ASRConfig,
    AppConfig,
    PipelineConfig,
    TTSConfig,
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
            qa_check_long_segment_fluency=True,
            qa_long_segment_word_threshold=14,
            qa_long_segment_max_pause_punct=3,
            qa_fail_on_flags=False,
            qa_allowed_flags=(),
            transformers=TranslateTransformersConfig(
                model_id="facebook/m2m100_418M",
                device=-1,
                max_new_tokens=256,
                source_lang_code=None,
                target_lang_code=None,
            ),
        ),
        tts=TTSConfig(
            backend="mock",
            sample_rate=24000,
            min_segment_seconds=0.12,
            mock_base_tone_hz=220,
            espeak_bin="espeak",
            espeak_voice="tr",
            espeak_speed_wpm=165,
            espeak_pitch=50,
            espeak_adaptive_rate_enabled=True,
            espeak_adaptive_rate_min_wpm=120,
            espeak_adaptive_rate_max_wpm=260,
            espeak_adaptive_rate_max_passes=3,
            espeak_adaptive_rate_tolerance_seconds=0.06,
            max_duration_delta_seconds=0.08,
            qa_max_postfit_segment_ratio=0.60,
            qa_max_postfit_seconds_ratio=0.35,
            qa_fail_on_flags=False,
            qa_allowed_flags=(),
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
                "total_source_word_count": 4,
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
                        "source_text": "hello world",
                        "source_word_count": 2,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    output_json = tmp_path / "output" / "translate" / "translation_output.en-tr.json"
    qa_report_json = tmp_path / "output" / "qa" / "m2_qa_report.json"
    run_manifest_json = tmp_path / "run_m2_manifest.json"
    config = _build_app_config()

    artifacts = run_m2_pipeline(
        translation_input_json_path=translation_input,
        output_json_path=output_json,
        qa_report_json_path=qa_report_json,
        run_manifest_json_path=run_manifest_json,
        config=config,
    )

    assert artifacts.translation_output_json == output_json
    assert artifacts.qa_report_json == qa_report_json
    assert artifacts.run_manifest_json == run_manifest_json

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

    manifest_payload = json.loads(run_manifest_json.read_text(encoding="utf-8"))
    assert manifest_payload["stage"] == "m2"
    assert "timings_seconds" in manifest_payload
    assert "speed" in manifest_payload
    assert manifest_payload["speed"]["translation_reuse_count"] == 1
    assert "qa_gate" in manifest_payload


def test_run_m2_pipeline_fails_when_qa_gate_blocks_flags(tmp_path: Path) -> None:
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
        ),
        encoding="utf-8",
    )
    output_json = tmp_path / "output" / "translate" / "translation_output.en-tr.json"
    qa_report_json = tmp_path / "output" / "qa" / "m2_qa_report.json"
    run_manifest_json = tmp_path / "run_m2_manifest.json"

    config = _build_app_config()
    config = AppConfig(
        tools=config.tools,
        pipeline=config.pipeline,
        asr=config.asr,
        translate=TranslateConfig(
            backend=config.translate.backend,
            source_language=config.translate.source_language,
            target_language=config.translate.target_language,
            batch_size=config.translate.batch_size,
            min_length_ratio=1.10,
            max_length_ratio=config.translate.max_length_ratio,
            glossary_path=config.translate.glossary_path,
            glossary_case_sensitive=config.translate.glossary_case_sensitive,
            apply_glossary_postprocess=config.translate.apply_glossary_postprocess,
            qa_check_terminal_punctuation=config.translate.qa_check_terminal_punctuation,
            qa_check_long_segment_fluency=config.translate.qa_check_long_segment_fluency,
            qa_long_segment_word_threshold=config.translate.qa_long_segment_word_threshold,
            qa_long_segment_max_pause_punct=config.translate.qa_long_segment_max_pause_punct,
            qa_fail_on_flags=True,
            qa_allowed_flags=(),
            transformers=config.translate.transformers,
        ),
        tts=config.tts,
    )

    with pytest.raises(RuntimeError, match="M2 QA gate failed"):
        run_m2_pipeline(
            translation_input_json_path=translation_input,
            output_json_path=output_json,
            qa_report_json_path=qa_report_json,
            run_manifest_json_path=run_manifest_json,
            config=config,
        )

    manifest_payload = json.loads(run_manifest_json.read_text(encoding="utf-8"))
    assert manifest_payload["qa_gate"]["enabled"] is True
    assert manifest_payload["qa_gate"]["passed"] is False
