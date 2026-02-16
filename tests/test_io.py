from pathlib import Path

from video_translate.io import _format_srt_time, create_run_paths


def test_format_srt_time() -> None:
    assert _format_srt_time(0.0) == "00:00:00,000"
    assert _format_srt_time(1.234) == "00:00:01,234"
    assert _format_srt_time(3723.045) == "01:02:03,045"


def test_create_run_paths_creates_expected_structure(tmp_path: Path) -> None:
    paths = create_run_paths(tmp_path, run_id="demo_run")
    assert paths.root == tmp_path / "demo_run"
    assert paths.input_dir.exists()
    assert paths.work_audio_dir.exists()
    assert paths.output_transcript_dir.exists()
    assert paths.output_qa_dir.exists()
    assert paths.logs_dir.exists()
