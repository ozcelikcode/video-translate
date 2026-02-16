import types

from pytest import MonkeyPatch

from video_translate.preflight import PreflightReport, preflight_errors, run_preflight


def test_run_preflight_success(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("video_translate.preflight.shutil.which", lambda command: f"/bin/{command}")
    monkeypatch.setattr(
        "video_translate.preflight.importlib.util.find_spec",
        lambda _: types.SimpleNamespace(name="faster_whisper"),
    )

    report = run_preflight(yt_dlp_bin="yt-dlp", ffmpeg_bin="ffmpeg")

    assert isinstance(report, PreflightReport)
    assert report.ok
    assert preflight_errors(report) == []


def test_run_preflight_missing_dependencies(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("video_translate.preflight.shutil.which", lambda _: None)
    monkeypatch.setattr("video_translate.preflight.importlib.util.find_spec", lambda _: None)

    report = run_preflight(yt_dlp_bin="yt-dlp", ffmpeg_bin="ffmpeg")
    errors = preflight_errors(report)

    assert not report.ok
    assert len(errors) == 3
