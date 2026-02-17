import types

from pytest import MonkeyPatch

from video_translate.preflight import PreflightReport, preflight_errors, run_preflight


def test_run_preflight_success(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("video_translate.preflight.shutil.which", lambda command: f"/bin/{command}")
    monkeypatch.setattr(
        "video_translate.preflight.importlib.util.find_spec",
        lambda _: types.SimpleNamespace(name="faster_whisper"),
    )

    report = run_preflight(
        yt_dlp_bin="yt-dlp",
        ffmpeg_bin="ffmpeg",
        tts_backend="mock",
        check_tts_backend=True,
    )

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


def test_run_preflight_transformers_backend_checks_extra_packages(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("video_translate.preflight.shutil.which", lambda command: f"/bin/{command}")

    def fake_find_spec(name: str) -> object | None:
        if name in {"faster_whisper", "transformers"}:
            return types.SimpleNamespace(name=name)
        return None

    monkeypatch.setattr("video_translate.preflight.importlib.util.find_spec", fake_find_spec)

    report = run_preflight(
        yt_dlp_bin="yt-dlp",
        ffmpeg_bin="ffmpeg",
        translate_backend="transformers",
        check_translate_backend=True,
    )
    errors = preflight_errors(report)

    assert not report.ok
    assert "sentencepiece" in " ".join(errors)
    assert "torch" in " ".join(errors)


def test_run_preflight_espeak_backend_checks_binary(monkeypatch: MonkeyPatch) -> None:
    def fake_which(command: str) -> str | None:
        if command in {"yt-dlp", "ffmpeg"}:
            return f"/bin/{command}"
        return None

    monkeypatch.setattr("video_translate.preflight.shutil.which", fake_which)
    monkeypatch.setattr(
        "video_translate.preflight.importlib.util.find_spec",
        lambda _: types.SimpleNamespace(name="faster_whisper"),
    )

    report = run_preflight(
        yt_dlp_bin="yt-dlp",
        ffmpeg_bin="ffmpeg",
        tts_backend="espeak",
        espeak_bin="espeak",
        check_tts_backend=True,
    )
    errors = preflight_errors(report)

    assert not report.ok
    assert "Missing espeak executable" in " ".join(errors)
