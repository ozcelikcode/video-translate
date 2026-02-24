from video_translate.models import TranscriptDocument, TranscriptSegment
from video_translate.pipeline.transcript_fusion import fuse_transcript_with_subtitles


def test_fuse_transcript_with_subtitles_recovers_short_missing_greeting() -> None:
    transcript = TranscriptDocument(
        language="en",
        language_probability=0.9,
        duration=5.0,
        segments=[
            TranscriptSegment(id=0, start=1.0, end=2.0, text="everyone", words=[]),
        ],
    )
    manual_cues = [
        {"start": 0.0, "end": 0.6, "text": "hello"},
        {"start": 1.0, "end": 2.0, "text": "hello everyone"},
    ]

    fused = fuse_transcript_with_subtitles(
        transcript=transcript,
        manual_cues=manual_cues,
        auto_cues=[],
        subtitle_mode="hybrid",
        use_subtitles=True,
        allow_auto_subtitles=True,
    )

    assert len(fused.segments) >= 2
    assert any(seg.text.lower().startswith("hello") for seg in fused.segments)
    assert fused.subtitle_summary is not None
    assert fused.fusion_summary is not None
    assert fused.fusion_summary["subtitle_only_recovered_segments"] >= 1


def test_fuse_transcript_with_subtitles_keeps_asr_when_disabled() -> None:
    transcript = TranscriptDocument(
        language="en",
        language_probability=0.9,
        duration=2.0,
        segments=[TranscriptSegment(id=0, start=0.0, end=1.0, text="hello", words=[])],
    )
    fused = fuse_transcript_with_subtitles(
        transcript=transcript,
        manual_cues=[{"start": 0.0, "end": 1.0, "text": "merhaba"}],
        auto_cues=[],
        use_subtitles=False,
    )
    assert fused.segments[0].text == "hello"

