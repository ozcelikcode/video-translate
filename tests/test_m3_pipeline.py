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
from video_translate.pipeline.m3 import run_m3_pipeline


def _build_app_config(tts_fail_on_flags: bool = False) -> AppConfig:
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
            min_length_ratio=0.5,
            max_length_ratio=1.8,
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
            qa_fail_on_flags=tts_fail_on_flags,
            qa_allowed_flags=(),
        ),
    )


def test_run_m3_pipeline_with_mock_backend(tmp_path: Path) -> None:
    tts_input = tmp_path / "output" / "tts" / "tts_input.tr.json"
    tts_input.parent.mkdir(parents=True, exist_ok=True)
    tts_input.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "stage": "m3_tts_input",
                "generated_at_utc": "2026-02-17T10:00:00Z",
                "language": "tr",
                "segment_count": 1,
                "total_target_word_count": 2,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 1.0,
                        "duration": 1.0,
                        "target_text": "merhaba dunya",
                        "target_word_count": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_json = tmp_path / "output" / "tts" / "tts_output.tr.json"
    qa_report_json = tmp_path / "output" / "qa" / "m3_qa_report.json"
    run_manifest_json = tmp_path / "run_m3_manifest.json"

    artifacts = run_m3_pipeline(
        tts_input_json_path=tts_input,
        output_json_path=output_json,
        qa_report_json_path=qa_report_json,
        run_manifest_json_path=run_manifest_json,
        config=_build_app_config(),
    )

    assert artifacts.tts_output_json == output_json
    assert artifacts.qa_report_json == qa_report_json
    assert artifacts.stitched_preview_wav.exists()
    output_payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert output_payload["stage"] == "m3_tts_output"
    segment = output_payload["segments"][0]
    assert Path(segment["audio_path"]).exists()

    manifest_payload = json.loads(run_manifest_json.read_text(encoding="utf-8"))
    assert manifest_payload["stage"] == "m3"
    assert Path(manifest_payload["outputs"]["stitched_preview_wav"]).exists()
    assert manifest_payload["qa_gate"]["enabled"] is False


def test_run_m3_pipeline_fails_when_qa_gate_blocks_flags(tmp_path: Path) -> None:
    tts_input = tmp_path / "output" / "tts" / "tts_input.tr.json"
    tts_input.parent.mkdir(parents=True, exist_ok=True)
    tts_input.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "stage": "m3_tts_input",
                "generated_at_utc": "2026-02-17T10:00:00Z",
                "language": "tr",
                "segment_count": 1,
                "total_target_word_count": 0,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 0.01,
                        "duration": 0.01,
                        "target_text": "",
                        "target_word_count": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_json = tmp_path / "output" / "tts" / "tts_output.tr.json"
    qa_report_json = tmp_path / "output" / "qa" / "m3_qa_report.json"
    run_manifest_json = tmp_path / "run_m3_manifest.json"

    with pytest.raises(RuntimeError, match="M3 QA gate failed"):
        run_m3_pipeline(
            tts_input_json_path=tts_input,
            output_json_path=output_json,
            qa_report_json_path=qa_report_json,
            run_manifest_json_path=run_manifest_json,
            config=_build_app_config(tts_fail_on_flags=True),
        )

    manifest_payload = json.loads(run_manifest_json.read_text(encoding="utf-8"))
    assert manifest_payload["qa_gate"]["enabled"] is True
    assert manifest_payload["qa_gate"]["passed"] is False
