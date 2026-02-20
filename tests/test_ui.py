import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_translate.models import M1Artifacts
from video_translate.pipeline.delivery import FinalDeliveryArtifacts
from video_translate.pipeline.m2 import M2Artifacts
from video_translate.pipeline.m3 import M3Artifacts
from video_translate.preflight import PreflightReport, ToolCheck
from video_translate.ui import UIM3Request, execute_m3_run
from video_translate.ui import UIYoutubeRequest, _html_page, _resolve_download_path, execute_youtube_dub_run


def test_execute_m3_run_prepare_and_m3(tmp_path: Path) -> None:
    run_root = tmp_path / "run_ui"
    translation_output = run_root / "output" / "translate" / "translation_output.en-tr.json"
    translation_output.parent.mkdir(parents=True, exist_ok=True)
    translation_output.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "stage": "m2_translation_output",
                "generated_at_utc": "2026-02-17T10:00:00Z",
                "backend": "mock",
                "source_language": "en",
                "target_language": "tr",
                "segment_count": 1,
                "total_source_word_count": 2,
                "total_target_word_count": 2,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 1.0,
                        "duration": 1.0,
                        "source_text": "hello world",
                        "target_text": "merhaba dunya",
                        "source_word_count": 2,
                        "target_word_count": 2,
                        "length_ratio": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = execute_m3_run(
        UIM3Request(
            run_root=run_root,
            config_path=None,
            target_lang="tr",
            prepare_input=True,
            translation_output_json=translation_output,
            tts_input_json=None,
        )
    )

    assert result["ok"] is True
    artifacts = result["artifacts"]
    assert Path(artifacts["tts_input_json"]).exists()
    assert Path(artifacts["tts_output_json"]).exists()
    assert Path(artifacts["qa_report_json"]).exists()
    assert Path(artifacts["run_manifest_json"]).exists()
    assert Path(artifacts["stitched_preview_wav"]).exists()
    assert result["output_dir"].endswith("output")
    assert len(result["downloadables"]) >= 5
    assert isinstance(result["segment_preview"], list)


def test_execute_youtube_dub_run_full_chain(tmp_path: Path, monkeypatch) -> None:
    run_root = tmp_path / "run_full"
    downloads_dir = tmp_path / "downloads" / run_root.name
    final_video = downloads_dir / "video_dubbed.tr.mp4"
    quality_summary = downloads_dir / "quality_summary.tr.json"
    transcript_json = run_root / "output" / "transcript" / "transcript.en.json"
    transcript_json.parent.mkdir(parents=True, exist_ok=True)
    transcript_json.write_text("{}", encoding="utf-8")

    m2_input = run_root / "output" / "translate" / "translation_input.en-tr.json"
    m2_output = run_root / "output" / "translate" / "translation_output.en-tr.json"
    m2_qa = run_root / "output" / "qa" / "m2_qa_report.json"
    m2_manifest = run_root / "run_m2_manifest.json"
    m3_input = run_root / "output" / "tts" / "tts_input.tr.json"
    m3_output = run_root / "output" / "tts" / "tts_output.tr.json"
    m3_qa = run_root / "output" / "qa" / "m3_qa_report.json"
    m3_manifest = run_root / "run_m3_manifest.json"
    m3_preview = run_root / "output" / "tts" / "tts_preview_stitched.tr.wav"

    def _fake_preflight(*args, **kwargs):  # noqa: ANN002, ANN003
        return PreflightReport(
            python_version="3.12.0",
            yt_dlp=ToolCheck(name="yt-dlp", command="yt-dlp", path="yt-dlp"),
            ffmpeg=ToolCheck(name="ffmpeg", command="ffmpeg", path="ffmpeg"),
            faster_whisper_available=True,
            translate_backend="mock",
            transformers_available=None,
            sentencepiece_available=None,
            torch_available=None,
            tts_backend="espeak",
            espeak=ToolCheck(name="espeak", command="espeak", path="espeak"),
        )

    def _fake_m1(*args, **kwargs):  # noqa: ANN002, ANN003
        media = run_root / "input" / "source.mp4"
        media.parent.mkdir(parents=True, exist_ok=True)
        media.write_bytes(b"")
        norm = run_root / "work" / "audio" / "source.wav"
        norm.parent.mkdir(parents=True, exist_ok=True)
        norm.write_bytes(b"")
        qa = run_root / "output" / "qa" / "m1_qa_report.json"
        qa.parent.mkdir(parents=True, exist_ok=True)
        qa.write_text("{}", encoding="utf-8")
        manifest = run_root / "run_manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        return M1Artifacts(
            run_root=run_root,
            source_media=media,
            normalized_audio=norm,
            transcript_json=transcript_json,
            transcript_srt=None,
            qa_report=qa,
            run_manifest=manifest,
        )

    def _fake_prepare_m2(*args, **kwargs):  # noqa: ANN002, ANN003
        m2_input.parent.mkdir(parents=True, exist_ok=True)
        m2_input.write_text("{}", encoding="utf-8")
        return m2_input

    def _fake_run_m2(*args, **kwargs):  # noqa: ANN002, ANN003
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

    def _fake_prepare_m3(*args, **kwargs):  # noqa: ANN002, ANN003
        m3_input.parent.mkdir(parents=True, exist_ok=True)
        m3_input.write_text("{}", encoding="utf-8")
        return m3_input

    def _fake_run_m3(*args, **kwargs):  # noqa: ANN002, ANN003
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

    def _fake_deliver(*args, **kwargs):  # noqa: ANN002, ANN003
        downloads_dir.mkdir(parents=True, exist_ok=True)
        final_video.write_bytes(b"")
        quality_summary.write_text("{}", encoding="utf-8")
        return FinalDeliveryArtifacts(
            downloads_dir=downloads_dir,
            dubbed_video_mp4=final_video,
            quality_summary_json=quality_summary,
            cleanup_performed=True,
        )

    fake_config = SimpleNamespace(
        tools=SimpleNamespace(yt_dlp="yt-dlp", ffmpeg="ffmpeg"),
        translate=SimpleNamespace(backend="mock", target_language="tr"),
        tts=SimpleNamespace(backend="espeak", espeak_bin="espeak"),
    )
    monkeypatch.setattr("video_translate.ui.load_config", lambda *_: fake_config)
    monkeypatch.setattr("video_translate.ui.run_preflight", _fake_preflight)
    monkeypatch.setattr("video_translate.ui.preflight_errors", lambda *_: [])
    monkeypatch.setattr("video_translate.ui.run_m1_pipeline", _fake_m1)
    monkeypatch.setattr("video_translate.ui.prepare_m2_translation_input", _fake_prepare_m2)
    monkeypatch.setattr("video_translate.ui.run_m2_pipeline", _fake_run_m2)
    monkeypatch.setattr("video_translate.ui.prepare_m3_tts_input", _fake_prepare_m3)
    monkeypatch.setattr("video_translate.ui.run_m3_pipeline", _fake_run_m3)
    monkeypatch.setattr("video_translate.ui.deliver_final_video", _fake_deliver)

    progress_events: list[tuple[int, str]] = []

    result = execute_youtube_dub_run(
        UIYoutubeRequest(
            source_url="https://www.youtube.com/watch?v=abc123",
            config_path=None,
            workspace_dir=tmp_path,
            downloads_dir=tmp_path / "downloads",
            run_id="demo_run",
            emit_srt=True,
            target_lang="tr",
            run_m3=True,
            cleanup_intermediate=True,
        ),
        progress_hook=lambda percent, phase: progress_events.append((percent, phase)),
    )

    assert result["ok"] is True
    assert result["run_root"] == str(run_root)
    assert result["output_dir"] == str(downloads_dir)
    assert result["downloadables"] == [str(final_video)]
    assert result["stages"]["delivery"]["dubbed_video_mp4"] == str(final_video)
    assert result["stages"]["m3"] is not None
    assert progress_events
    assert progress_events[-1][0] == 100
    assert any(percent >= 70 for percent, _ in progress_events)


def test_execute_youtube_dub_run_rejects_mock_tts_backend(monkeypatch) -> None:
    fake_config = SimpleNamespace(
        tools=SimpleNamespace(yt_dlp="yt-dlp", ffmpeg="ffmpeg"),
        translate=SimpleNamespace(backend="mock", target_language="tr"),
        tts=SimpleNamespace(backend="mock", espeak_bin="espeak"),
    )
    monkeypatch.setattr("video_translate.ui.load_config", lambda *_: fake_config)
    with pytest.raises(RuntimeError, match="tts.backend='mock'"):
        execute_youtube_dub_run(
            UIYoutubeRequest(
                source_url="https://www.youtube.com/watch?v=abc123",
                config_path=None,
                workspace_dir=None,
                downloads_dir=None,
                run_id=None,
                emit_srt=True,
                target_lang="tr",
                run_m3=True,
                cleanup_intermediate=True,
            )
        )


def test_html_page_contains_visible_youtube_controls() -> None:
    html = _html_page()
    assert "Video Translate Studio" in html
    assert "YouTube URL" in html
    assert "Downloads Dir" in html
    assert "YouTube'dan Dublaj Baslat" in html
    assert "Ara dosyalari temizle" in html
    assert "Ana Is Akisi" in html
    assert "CLI Kullanim Komutlari" in html
    assert "video-translate run-dub --url" in html
    assert "Cikti klasoru" in html
    assert "Indirilebilir Dosyalar" in html
    assert "Ilerleme: %0 - Hazir." in html


def test_resolve_download_path_accepts_project_file() -> None:
    path = _resolve_download_path("README.md")
    assert path.name == "README.md"


def test_resolve_download_path_rejects_outside_project_root(tmp_path: Path) -> None:
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("blocked", encoding="utf-8")
    with pytest.raises(ValueError):
        _resolve_download_path(str(outside_file))
