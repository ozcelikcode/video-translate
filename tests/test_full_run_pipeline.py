from pathlib import Path
from types import SimpleNamespace

from video_translate.models import M1Artifacts
from video_translate.pipeline.full_run import run_full_dub_pipeline
from video_translate.pipeline.m2 import M2Artifacts
from video_translate.pipeline.m3 import M3Artifacts
from video_translate.preflight import PreflightReport, ToolCheck


def _fake_config() -> SimpleNamespace:
    return SimpleNamespace(
        tools=SimpleNamespace(yt_dlp="yt-dlp", ffmpeg="ffmpeg"),
        translate=SimpleNamespace(backend="mock", target_language="tr"),
        tts=SimpleNamespace(backend="mock", espeak_bin="espeak"),
    )


def _fake_preflight() -> PreflightReport:
    return PreflightReport(
        python_version="3.12.0",
        yt_dlp=ToolCheck(name="yt-dlp", command="yt-dlp", path="yt-dlp"),
        ffmpeg=ToolCheck(name="ffmpeg", command="ffmpeg", path="ffmpeg"),
        faster_whisper_available=True,
        translate_backend="mock",
        transformers_available=None,
        sentencepiece_available=None,
        torch_available=None,
        tts_backend="mock",
        espeak=None,
    )


def test_run_full_dub_pipeline_runs_m1_m2_m3(tmp_path: Path, monkeypatch) -> None:
    run_root = tmp_path / "run"
    transcript_json = run_root / "output" / "transcript" / "transcript.en.json"
    m2_input = run_root / "output" / "translate" / "translation_input.en-tr.json"
    m2_output = run_root / "output" / "translate" / "translation_output.en-tr.json"
    m2_qa = run_root / "output" / "qa" / "m2_qa_report.json"
    m2_manifest = run_root / "run_m2_manifest.json"
    m3_input = run_root / "output" / "tts" / "tts_input.tr.json"
    m3_output = run_root / "output" / "tts" / "tts_output.tr.json"
    m3_qa = run_root / "output" / "qa" / "m3_qa_report.json"
    m3_manifest = run_root / "run_m3_manifest.json"
    m3_preview = run_root / "output" / "tts" / "tts_preview_stitched.tr.wav"
    calls: list[str] = []

    monkeypatch.setattr("video_translate.pipeline.full_run.run_preflight", lambda **_: _fake_preflight())
    monkeypatch.setattr("video_translate.pipeline.full_run.preflight_errors", lambda *_: [])

    def _fake_m1(**_kwargs):
        calls.append("m1")
        transcript_json.parent.mkdir(parents=True, exist_ok=True)
        transcript_json.write_text("{}", encoding="utf-8")
        source_media = run_root / "input" / "source.mp4"
        source_media.parent.mkdir(parents=True, exist_ok=True)
        source_media.write_bytes(b"")
        normalized_audio = run_root / "work" / "audio" / "source.wav"
        normalized_audio.parent.mkdir(parents=True, exist_ok=True)
        normalized_audio.write_bytes(b"")
        qa_report = run_root / "output" / "qa" / "m1_qa_report.json"
        qa_report.parent.mkdir(parents=True, exist_ok=True)
        qa_report.write_text("{}", encoding="utf-8")
        run_manifest = run_root / "run_manifest.json"
        run_manifest.write_text("{}", encoding="utf-8")
        return M1Artifacts(
            run_root=run_root,
            source_media=source_media,
            normalized_audio=normalized_audio,
            transcript_json=transcript_json,
            transcript_srt=None,
            qa_report=qa_report,
            run_manifest=run_manifest,
        )

    monkeypatch.setattr("video_translate.pipeline.full_run.run_m1_pipeline", _fake_m1)
    monkeypatch.setattr(
        "video_translate.pipeline.full_run.prepare_m2_translation_input",
        lambda **_: calls.append("prepare_m2") or m2_input,
    )

    def _fake_m2(**_kwargs):
        calls.append("m2")
        m2_output.parent.mkdir(parents=True, exist_ok=True)
        m2_output.write_text("{}", encoding="utf-8")
        m2_qa.parent.mkdir(parents=True, exist_ok=True)
        m2_qa.write_text("{}", encoding="utf-8")
        m2_manifest.write_text("{}", encoding="utf-8")
        return M2Artifacts(
            translation_input_json=m2_input,
            translation_output_json=m2_output,
            qa_report_json=m2_qa,
            run_manifest_json=m2_manifest,
        )

    monkeypatch.setattr("video_translate.pipeline.full_run.run_m2_pipeline", _fake_m2)
    monkeypatch.setattr(
        "video_translate.pipeline.full_run.prepare_m3_tts_input",
        lambda **_: calls.append("prepare_m3") or m3_input,
    )

    def _fake_m3(**_kwargs):
        calls.append("m3")
        m3_output.parent.mkdir(parents=True, exist_ok=True)
        m3_output.write_text("{}", encoding="utf-8")
        m3_qa.parent.mkdir(parents=True, exist_ok=True)
        m3_qa.write_text("{}", encoding="utf-8")
        m3_manifest.write_text("{}", encoding="utf-8")
        m3_preview.parent.mkdir(parents=True, exist_ok=True)
        m3_preview.write_bytes(b"")
        return M3Artifacts(
            tts_input_json=m3_input,
            tts_output_json=m3_output,
            qa_report_json=m3_qa,
            run_manifest_json=m3_manifest,
            stitched_preview_wav=m3_preview,
        )

    monkeypatch.setattr("video_translate.pipeline.full_run.run_m3_pipeline", _fake_m3)

    artifacts = run_full_dub_pipeline(
        source_url="https://www.youtube.com/watch?v=abc123",
        config=_fake_config(),
        use_m3_closure=False,
    )

    assert artifacts.run_root == run_root
    assert artifacts.m3_closure_report_json is None
    assert calls == ["m1", "prepare_m2", "m2", "prepare_m3", "m3"]


def test_run_full_dub_pipeline_with_m3_closure(tmp_path: Path, monkeypatch) -> None:
    run_root = tmp_path / "run"
    transcript_json = run_root / "output" / "transcript" / "transcript.en.json"
    m2_input = run_root / "output" / "translate" / "translation_input.en-tr.json"
    m2_output = run_root / "output" / "translate" / "translation_output.en-tr.json"
    m2_qa = run_root / "output" / "qa" / "m2_qa_report.json"
    m2_manifest = run_root / "run_m2_manifest.json"
    m3_output = run_root / "output" / "tts" / "tts_output.tr.json"
    m3_qa = run_root / "output" / "qa" / "m3_qa_report.json"
    m3_manifest = run_root / "run_m3_manifest.json"
    m3_preview = run_root / "output" / "tts" / "tts_preview_stitched.tr.wav"
    closure_report = run_root / "benchmarks" / "m3_closure_report.json"

    monkeypatch.setattr("video_translate.pipeline.full_run.run_preflight", lambda **_: _fake_preflight())
    monkeypatch.setattr("video_translate.pipeline.full_run.preflight_errors", lambda *_: [])

    def _fake_m1(**_kwargs):
        transcript_json.parent.mkdir(parents=True, exist_ok=True)
        transcript_json.write_text("{}", encoding="utf-8")
        source_media = run_root / "input" / "source.mp4"
        source_media.parent.mkdir(parents=True, exist_ok=True)
        source_media.write_bytes(b"")
        normalized_audio = run_root / "work" / "audio" / "source.wav"
        normalized_audio.parent.mkdir(parents=True, exist_ok=True)
        normalized_audio.write_bytes(b"")
        qa_report = run_root / "output" / "qa" / "m1_qa_report.json"
        qa_report.parent.mkdir(parents=True, exist_ok=True)
        qa_report.write_text("{}", encoding="utf-8")
        run_manifest = run_root / "run_manifest.json"
        run_manifest.write_text("{}", encoding="utf-8")
        return M1Artifacts(
            run_root=run_root,
            source_media=source_media,
            normalized_audio=normalized_audio,
            transcript_json=transcript_json,
            transcript_srt=None,
            qa_report=qa_report,
            run_manifest=run_manifest,
        )

    monkeypatch.setattr("video_translate.pipeline.full_run.run_m1_pipeline", _fake_m1)
    monkeypatch.setattr("video_translate.pipeline.full_run.prepare_m2_translation_input", lambda **_: m2_input)
    monkeypatch.setattr(
        "video_translate.pipeline.full_run.run_m2_pipeline",
        lambda **_: M2Artifacts(
            translation_input_json=m2_input,
            translation_output_json=m2_output,
            qa_report_json=m2_qa,
            run_manifest_json=m2_manifest,
        ),
    )
    monkeypatch.setattr(
        "video_translate.pipeline.full_run.run_m3_closure_workflow",
        lambda **_: SimpleNamespace(
            m3_artifacts=M3Artifacts(
                tts_input_json=run_root / "output" / "tts" / "tts_input.tr.json",
                tts_output_json=m3_output,
                qa_report_json=m3_qa,
                run_manifest_json=m3_manifest,
                stitched_preview_wav=m3_preview,
            ),
            closure_report_json=closure_report,
        ),
    )

    artifacts = run_full_dub_pipeline(
        source_url="https://www.youtube.com/watch?v=abc123",
        config=_fake_config(),
        use_m3_closure=True,
    )

    assert artifacts.run_root == run_root
    assert artifacts.m3_closure_report_json == closure_report
