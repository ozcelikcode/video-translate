from pathlib import Path

from video_translate.config import (
    ASRConfig,
    AppConfig,
    PipelineConfig,
    TTSConfig,
    ToolConfig,
    TranslateConfig,
    TranslateTransformersConfig,
)
from video_translate.models import M1Artifacts
from video_translate.pipeline.m1 import _build_run_manifest
from video_translate.preflight import PreflightReport, ToolCheck


def test_build_run_manifest_contains_core_fields() -> None:
    config = AppConfig(
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
            qa_fail_on_flags=False,
            qa_allowed_flags=(),
        ),
    )
    artifacts = M1Artifacts(
        run_root=Path("runs/demo"),
        source_media=Path("runs/demo/input/source.mp4"),
        normalized_audio=Path("runs/demo/work/audio/source_16k_mono.wav"),
        transcript_json=Path("runs/demo/output/transcript/transcript.en.json"),
        transcript_srt=Path("runs/demo/output/transcript/transcript.en.srt"),
        qa_report=Path("runs/demo/output/qa/m1_qa_report.json"),
        run_manifest=Path("runs/demo/run_manifest.json"),
    )
    preflight = PreflightReport(
        python_version="3.12.8",
        yt_dlp=ToolCheck(name="yt-dlp", command="yt-dlp", path="/bin/yt-dlp"),
        ffmpeg=ToolCheck(name="ffmpeg", command="ffmpeg", path="/bin/ffmpeg"),
        faster_whisper_available=True,
        translate_backend="mock",
        transformers_available=None,
        sentencepiece_available=None,
        torch_available=None,
        tts_backend="mock",
        espeak=None,
    )

    manifest = _build_run_manifest(
        source_url="https://example.com/video",
        config=config,
        artifacts=artifacts,
        preflight_report=preflight,
    )

    assert manifest["stage"] == "m1"
    assert manifest["source_url"] == "https://example.com/video"
    assert manifest["artifacts"] is not None
    assert manifest["preflight"] is not None
    artifacts_payload = manifest["artifacts"]
    assert isinstance(artifacts_payload, dict)
    assert Path(str(artifacts_payload["qa_report"])) == Path("runs/demo/output/qa/m1_qa_report.json")
