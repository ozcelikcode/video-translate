import types

from pytest import MonkeyPatch

from pathlib import Path

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


def test_run_preflight_piper_backend_checks_binary_and_model(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    def fake_which(command: str) -> str | None:
        if command in {"yt-dlp", "ffmpeg"}:
            return f"/bin/{command}"
        return None

    monkeypatch.setattr("video_translate.preflight.shutil.which", fake_which)
    monkeypatch.setattr("video_translate.preflight._project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "video_translate.preflight.importlib.util.find_spec",
        lambda _: types.SimpleNamespace(name="faster_whisper"),
    )

    report = run_preflight(
        yt_dlp_bin="yt-dlp",
        ffmpeg_bin="ffmpeg",
        tts_backend="piper",
        piper_bin="piper",
        piper_model_path=Path("models/piper/tr_TR-dfki-medium.onnx"),
        check_tts_backend=True,
    )
    errors = preflight_errors(report)

    assert not report.ok
    joined = " ".join(errors)
    assert "Missing piper executable" in joined
    assert "Piper model file not found" in joined


def test_run_preflight_piper_backend_passes_with_binary_and_model(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    model_path = tmp_path / "tr_TR-dfki-medium.onnx"
    model_path.write_bytes(b"x")

    def fake_which(command: str) -> str | None:
        if command in {"yt-dlp", "ffmpeg", "piper"}:
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
        tts_backend="piper",
        piper_bin="piper",
        piper_model_path=model_path,
        check_tts_backend=True,
    )
    errors = preflight_errors(report)

    assert report.ok
    assert errors == []


def test_run_preflight_espeak_backend_accepts_espeak_ng_fallback(monkeypatch: MonkeyPatch) -> None:
    def fake_which(command: str) -> str | None:
        if command in {"yt-dlp", "ffmpeg"}:
            return f"/bin/{command}"
        if command == "espeak-ng":
            return "/bin/espeak-ng"
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

    assert report.ok
    assert errors == []
    assert report.espeak is not None
    assert report.espeak.command == "espeak-ng"


def test_run_preflight_piper_backend_finds_local_venv_binary(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    local_piper = tmp_path / ".venv" / "Scripts" / "piper.exe"
    local_piper.parent.mkdir(parents=True, exist_ok=True)
    local_piper.write_text("piper", encoding="utf-8")
    model_path = tmp_path / "models" / "piper" / "tr_TR-dfki-medium.onnx"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_bytes(b"model")

    def fake_which(command: str) -> str | None:
        if command in {"yt-dlp", "ffmpeg"}:
            return f"/bin/{command}"
        return None

    monkeypatch.setattr("video_translate.preflight.shutil.which", fake_which)
    monkeypatch.setattr("video_translate.preflight._project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "video_translate.preflight.importlib.util.find_spec",
        lambda _: types.SimpleNamespace(name="faster_whisper"),
    )

    report = run_preflight(
        yt_dlp_bin="yt-dlp",
        ffmpeg_bin="ffmpeg",
        tts_backend="piper",
        piper_bin="piper",
        piper_model_path=model_path,
        check_tts_backend=True,
    )

    assert report.ok
    assert report.piper is not None
    assert report.piper.path == str(local_piper)
