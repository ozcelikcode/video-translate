import json
import wave
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
            qa_max_postfit_segment_ratio=0.60,
            qa_max_postfit_seconds_ratio=0.35,
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


def test_run_m3_pipeline_pads_short_segments_with_silence(tmp_path: Path, monkeypatch) -> None:
    tts_input = tmp_path / "output" / "tts" / "tts_input.tr.json"
    tts_input.parent.mkdir(parents=True, exist_ok=True)
    tts_input.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "stage": "m3_tts_input",
                "generated_at_utc": "2026-02-18T10:00:00Z",
                "language": "tr",
                "segment_count": 1,
                "total_target_word_count": 1,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 1.0,
                        "duration": 1.0,
                        "target_text": "merhaba",
                        "target_word_count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_json = tmp_path / "output" / "tts" / "tts_output.tr.json"
    qa_report_json = tmp_path / "output" / "qa" / "m3_qa_report.json"
    run_manifest_json = tmp_path / "run_m3_manifest.json"

    class _ShortBackend:
        name = "short"

        def synthesize_to_wav(self, *, text: str, output_wav: Path, target_duration: float, sample_rate: int) -> float:
            frame_count = int(round(0.2 * sample_rate))
            output_wav.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output_wav), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(b"\x00\x00" * frame_count)
            return frame_count / sample_rate

    monkeypatch.setattr("video_translate.pipeline.m3.build_tts_backend", lambda *_: _ShortBackend())

    run_m3_pipeline(
        tts_input_json_path=tts_input,
        output_json_path=output_json,
        qa_report_json_path=qa_report_json,
        run_manifest_json_path=run_manifest_json,
        config=_build_app_config(),
    )

    output_payload = json.loads(output_json.read_text(encoding="utf-8"))
    segment = output_payload["segments"][0]
    assert segment["synthesized_duration"] >= 0.99
    manifest_payload = json.loads(run_manifest_json.read_text(encoding="utf-8"))
    assert manifest_payload["duration_postfit"]["silence_padding_applied_segments"] == 1


def test_run_m3_pipeline_trims_long_segments(tmp_path: Path, monkeypatch) -> None:
    tts_input = tmp_path / "output" / "tts" / "tts_input.tr.json"
    tts_input.parent.mkdir(parents=True, exist_ok=True)
    tts_input.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "stage": "m3_tts_input",
                "generated_at_utc": "2026-02-18T10:00:00Z",
                "language": "tr",
                "segment_count": 1,
                "total_target_word_count": 1,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 0.5,
                        "duration": 0.5,
                        "target_text": "merhaba",
                        "target_word_count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_json = tmp_path / "output" / "tts" / "tts_output.tr.json"
    qa_report_json = tmp_path / "output" / "qa" / "m3_qa_report.json"
    run_manifest_json = tmp_path / "run_m3_manifest.json"

    class _LongBackend:
        name = "long"

        def synthesize_to_wav(self, *, text: str, output_wav: Path, target_duration: float, sample_rate: int) -> float:
            frame_count = int(round(1.0 * sample_rate))
            output_wav.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output_wav), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(b"\x00\x00" * frame_count)
            return frame_count / sample_rate

    monkeypatch.setattr("video_translate.pipeline.m3.build_tts_backend", lambda *_: _LongBackend())

    run_m3_pipeline(
        tts_input_json_path=tts_input,
        output_json_path=output_json,
        qa_report_json_path=qa_report_json,
        run_manifest_json_path=run_manifest_json,
        config=_build_app_config(),
    )

    output_payload = json.loads(output_json.read_text(encoding="utf-8"))
    segment = output_payload["segments"][0]
    assert segment["synthesized_duration"] <= 0.51
    manifest_payload = json.loads(run_manifest_json.read_text(encoding="utf-8"))
    assert manifest_payload["duration_postfit"]["trim_applied_segments"] == 1


def test_run_m3_pipeline_fails_when_postfit_ratio_exceeds_limit(tmp_path: Path, monkeypatch) -> None:
    tts_input = tmp_path / "output" / "tts" / "tts_input.tr.json"
    tts_input.parent.mkdir(parents=True, exist_ok=True)
    tts_input.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "stage": "m3_tts_input",
                "generated_at_utc": "2026-02-18T10:00:00Z",
                "language": "tr",
                "segment_count": 1,
                "total_target_word_count": 1,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 1.0,
                        "duration": 1.0,
                        "target_text": "merhaba",
                        "target_word_count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_json = tmp_path / "output" / "tts" / "tts_output.tr.json"
    qa_report_json = tmp_path / "output" / "qa" / "m3_qa_report.json"
    run_manifest_json = tmp_path / "run_m3_manifest.json"

    class _ShortBackend:
        name = "short"

        def synthesize_to_wav(self, *, text: str, output_wav: Path, target_duration: float, sample_rate: int) -> float:
            frame_count = int(round(0.2 * sample_rate))
            output_wav.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output_wav), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(b"\x00\x00" * frame_count)
            return frame_count / sample_rate

    monkeypatch.setattr("video_translate.pipeline.m3.build_tts_backend", lambda *_: _ShortBackend())

    config = _build_app_config(tts_fail_on_flags=True)
    config = AppConfig(
        tools=config.tools,
        pipeline=config.pipeline,
        asr=config.asr,
        translate=config.translate,
        tts=TTSConfig(
            backend=config.tts.backend,
            sample_rate=config.tts.sample_rate,
            min_segment_seconds=config.tts.min_segment_seconds,
            mock_base_tone_hz=config.tts.mock_base_tone_hz,
            espeak_bin=config.tts.espeak_bin,
            espeak_voice=config.tts.espeak_voice,
            espeak_speed_wpm=config.tts.espeak_speed_wpm,
            espeak_pitch=config.tts.espeak_pitch,
            espeak_adaptive_rate_enabled=config.tts.espeak_adaptive_rate_enabled,
            espeak_adaptive_rate_min_wpm=config.tts.espeak_adaptive_rate_min_wpm,
            espeak_adaptive_rate_max_wpm=config.tts.espeak_adaptive_rate_max_wpm,
            espeak_adaptive_rate_max_passes=config.tts.espeak_adaptive_rate_max_passes,
            espeak_adaptive_rate_tolerance_seconds=config.tts.espeak_adaptive_rate_tolerance_seconds,
            max_duration_delta_seconds=config.tts.max_duration_delta_seconds,
            qa_max_postfit_segment_ratio=0.10,
            qa_max_postfit_seconds_ratio=0.10,
            qa_fail_on_flags=True,
            qa_allowed_flags=(),
        ),
    )

    with pytest.raises(RuntimeError, match="M3 QA gate failed"):
        run_m3_pipeline(
            tts_input_json_path=tts_input,
            output_json_path=output_json,
            qa_report_json_path=qa_report_json,
            run_manifest_json_path=run_manifest_json,
            config=config,
        )

    qa_payload = json.loads(qa_report_json.read_text(encoding="utf-8"))
    assert "postfit_segment_ratio_above_max" in qa_payload["quality_flags"]
