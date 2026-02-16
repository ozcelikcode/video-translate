from video_translate.models import TranscriptDocument, TranscriptSegment, WordTimestamp
from video_translate.qa.m1_report import build_m1_qa_report


def test_build_m1_qa_report_with_word_timestamps() -> None:
    doc = TranscriptDocument(
        language="en",
        language_probability=0.99,
        duration=10.0,
        segments=[
            TranscriptSegment(
                id=0,
                start=0.0,
                end=3.0,
                text="hello world",
                words=[
                    WordTimestamp(word="hello", start=0.0, end=1.0, probability=0.95),
                    WordTimestamp(word="world", start=1.0, end=2.0, probability=0.55),
                ],
            ),
            TranscriptSegment(
                id=1,
                start=4.0,
                end=7.0,
                text="this is a test",
                words=[
                    WordTimestamp(word="this", start=4.0, end=4.5, probability=0.90),
                    WordTimestamp(word="is", start=4.5, end=5.0, probability=0.91),
                    WordTimestamp(word="a", start=5.0, end=5.2, probability=0.92),
                    WordTimestamp(word="test", start=5.2, end=6.0, probability=0.93),
                ],
            ),
        ],
    )

    report = build_m1_qa_report(doc)

    assert report["stage"] == "m1"
    assert report["transcript_language"] == "en"
    segment_metrics = report["segment_metrics"]
    assert isinstance(segment_metrics, dict)
    assert segment_metrics["count"] == 2
    assert segment_metrics["speech_duration_seconds"] == 6.0
    assert segment_metrics["speech_coverage_ratio"] == 0.6

    word_metrics = report["word_metrics"]
    assert isinstance(word_metrics, dict)
    assert word_metrics["has_word_timestamps"] is True
    assert word_metrics["count"] == 6
    assert word_metrics["low_confidence_count"] == 1
    assert report["quality_flags"] == []


def test_build_m1_qa_report_without_word_timestamps() -> None:
    doc = TranscriptDocument(
        language="en",
        language_probability=0.91,
        duration=0.0,
        segments=[
            TranscriptSegment(id=0, start=0.0, end=0.0, text="", words=[]),
            TranscriptSegment(id=1, start=1.0, end=2.0, text="single line", words=[]),
        ],
    )

    report = build_m1_qa_report(doc)

    word_metrics = report["word_metrics"]
    assert isinstance(word_metrics, dict)
    assert word_metrics["has_word_timestamps"] is False
    assert word_metrics["count"] == 2
    assert word_metrics["avg_probability"] is None

    flags = report["quality_flags"]
    assert isinstance(flags, list)
    assert "empty_segments_present" in flags
