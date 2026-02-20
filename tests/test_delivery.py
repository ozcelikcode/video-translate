import json
import subprocess
from pathlib import Path

from video_translate.pipeline.delivery import (
    build_video_merge_command,
    deliver_final_video,
)


def test_build_video_merge_command_contains_expected_flags(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    dubbed = tmp_path / "dubbed.wav"
    output = tmp_path / "video_dubbed.tr.mp4"
    command = build_video_merge_command(
        ffmpeg_bin="ffmpeg",
        source_video=source,
        dubbed_audio=dubbed,
        output_mp4=output,
    )
    assert command[0] == "ffmpeg"
    assert "-filter_complex" in command
    assert "[1:a]apad[aud]" in command
    assert "-shortest" in command
    assert str(output) == command[-1]


def test_deliver_final_video_writes_outputs_and_cleans_run_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_root = tmp_path / "runs" / "run_001"
    source = run_root / "input" / "source.mp4"
    dubbed = run_root / "output" / "tts" / "tts_preview_stitched.tr.wav"
    m1_qa = run_root / "output" / "qa" / "m1_qa_report.json"
    m2_qa = run_root / "output" / "qa" / "m2_qa_report.json"
    m3_qa = run_root / "output" / "qa" / "m3_qa_report.json"
    run_manifest = run_root / "run_manifest.json"
    for path in (source, dubbed, m1_qa, m2_qa, m3_qa, run_manifest):
        path.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    dubbed.write_bytes(b"audio")
    run_manifest.write_text("{}", encoding="utf-8")
    m1_qa.write_text(json.dumps({"quality_flags": []}), encoding="utf-8")
    m2_qa.write_text(json.dumps({"quality_flags": []}), encoding="utf-8")
    m3_qa.write_text(json.dumps({"quality_flags": []}), encoding="utf-8")

    def _fake_run_command(command: list[str], cwd: Path | None = None):  # noqa: ANN001
        output_path = Path(command[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"mp4")
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("video_translate.pipeline.delivery.run_command", _fake_run_command)
    monkeypatch.setattr("video_translate.pipeline.delivery.PROJECT_ROOT", tmp_path)

    artifacts = deliver_final_video(
        run_root=run_root,
        source_video=source,
        dubbed_audio=dubbed,
        ffmpeg_bin="ffmpeg",
        target_lang="tr",
        downloads_root=tmp_path / "downloads",
        cleanup_intermediate=True,
    )

    assert artifacts.dubbed_video_mp4.exists()
    assert artifacts.quality_summary_json.exists()
    summary = json.loads(artifacts.quality_summary_json.read_text(encoding="utf-8"))
    assert summary["qa"]["overall_passed"] is True
    assert artifacts.cleanup_performed is True
    assert not run_root.exists()


def test_deliver_final_video_carries_quality_flags_without_cleanup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_root = tmp_path / "runs" / "run_002"
    source = run_root / "input" / "source.mp4"
    dubbed = run_root / "output" / "tts" / "tts_preview_stitched.tr.wav"
    m2_qa = run_root / "output" / "qa" / "m2_qa_report.json"
    run_manifest = run_root / "run_manifest.json"
    for path in (source, dubbed, m2_qa, run_manifest):
        path.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"video")
    dubbed.write_bytes(b"audio")
    run_manifest.write_text("{}", encoding="utf-8")
    m2_qa.write_text(json.dumps({"quality_flags": ["glossary_miss"]}), encoding="utf-8")

    def _fake_run_command(command: list[str], cwd: Path | None = None):  # noqa: ANN001
        output_path = Path(command[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"mp4")
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("video_translate.pipeline.delivery.run_command", _fake_run_command)
    monkeypatch.setattr("video_translate.pipeline.delivery.PROJECT_ROOT", tmp_path)

    artifacts = deliver_final_video(
        run_root=run_root,
        source_video=source,
        dubbed_audio=dubbed,
        ffmpeg_bin="ffmpeg",
        target_lang="tr",
        downloads_root=tmp_path / "downloads",
        cleanup_intermediate=False,
    )

    summary = json.loads(artifacts.quality_summary_json.read_text(encoding="utf-8"))
    assert summary["qa"]["overall_passed"] is False
    assert summary["qa"]["m2_quality_flags"] == ["glossary_miss"]
    assert run_root.exists()
