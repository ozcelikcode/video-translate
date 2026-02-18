from video_translate.config import TTSConfig
from video_translate.qa.m3_report import build_m3_qa_report
from video_translate.tts.contracts import TTSOutputDocument, TTSOutputSegment


def _tts_config() -> TTSConfig:
    return TTSConfig(
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
        max_duration_delta_seconds=0.05,
        qa_max_postfit_segment_ratio=0.60,
        qa_max_postfit_seconds_ratio=0.35,
        qa_fail_on_flags=False,
        qa_allowed_flags=(),
    )


def test_build_m3_qa_report_flags_duration_and_empty_text() -> None:
    doc = TTSOutputDocument(
        schema_version="1.0",
        stage="m3_tts_output",
        generated_at_utc="2026-02-17T10:00:00Z",
        backend="mock",
        language="tr",
        sample_rate=24000,
        segment_count=2,
        segments=[
            TTSOutputSegment(
                id=0,
                start=0.0,
                end=1.0,
                target_duration=1.0,
                synthesized_duration=1.2,
                duration_delta=0.2,
                target_text="merhaba",
                audio_path="seg_000000.wav",
            ),
            TTSOutputSegment(
                id=1,
                start=1.0,
                end=2.0,
                target_duration=1.0,
                synthesized_duration=1.0,
                duration_delta=0.0,
                target_text="",
                audio_path="seg_000001.wav",
            ),
        ],
    )
    report = build_m3_qa_report(doc, _tts_config())
    assert report["stage"] == "m3"
    assert report["duration_metrics"]["out_of_tolerance_count"] == 1
    flags = report["quality_flags"]
    assert "duration_out_of_tolerance_present" in flags
    assert "empty_tts_text_present" in flags


def test_build_m3_qa_report_flags_excessive_postfit_adjustment() -> None:
    doc = TTSOutputDocument(
        schema_version="1.0",
        stage="m3_tts_output",
        generated_at_utc="2026-02-18T10:00:00Z",
        backend="mock",
        language="tr",
        sample_rate=24000,
        segment_count=2,
        segments=[
            TTSOutputSegment(
                id=0,
                start=0.0,
                end=1.0,
                target_duration=1.0,
                synthesized_duration=1.0,
                duration_delta=0.0,
                target_text="merhaba",
                audio_path="seg_000000.wav",
            ),
            TTSOutputSegment(
                id=1,
                start=1.0,
                end=2.0,
                target_duration=1.0,
                synthesized_duration=1.0,
                duration_delta=0.0,
                target_text="dunya",
                audio_path="seg_000001.wav",
            ),
        ],
    )
    report = build_m3_qa_report(
        doc,
        _tts_config(),
        postfit_padding_segments=2,
        postfit_trim_segments=0,
        postfit_total_padded_seconds=1.0,
        postfit_total_trimmed_seconds=0.0,
    )
    flags = report["quality_flags"]
    assert "postfit_segment_ratio_above_max" in flags
    assert "postfit_seconds_ratio_above_max" in flags
