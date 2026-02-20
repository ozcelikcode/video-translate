import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from video_translate.utils.subprocess_utils import CommandExecutionError, run_command


def test_run_command_passes_timeout_to_subprocess(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        del args
        captured["timeout"] = kwargs.get("timeout")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("video_translate.utils.subprocess_utils.subprocess.run", fake_run)

    result = run_command(["echo", "ok"], cwd=Path("."), timeout_seconds=12.0)
    assert result.returncode == 0
    assert captured["timeout"] == 12.0


def test_run_command_uses_utf8_text_mode(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        del args
        captured["encoding"] = kwargs.get("encoding")
        captured["errors"] = kwargs.get("errors")
        captured["text"] = kwargs.get("text")
        captured["input"] = kwargs.get("input")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("video_translate.utils.subprocess_utils.subprocess.run", fake_run)

    result = run_command(["cmd", "/c", "echo"], input_text="merhaba")
    assert result.returncode == 0
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert captured["text"] is True
    assert captured["input"] == "merhaba"


def test_run_command_timeout_raises_command_execution_error(monkeypatch: Any) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        del args, kwargs
        raise subprocess.TimeoutExpired(cmd="ffmpeg -i x y", timeout=5.0, stderr="still running")

    monkeypatch.setattr("video_translate.utils.subprocess_utils.subprocess.run", fake_run)

    with pytest.raises(CommandExecutionError, match="timed out"):
        run_command(["ffmpeg", "-i", "x", "y"], timeout_seconds=5.0)


def test_run_command_handles_non_ascii_input_text() -> None:
    echo_stdin_script = (
        "import sys;"
        "data = sys.stdin.buffer.read();"
        "sys.stdout.buffer.write(data)"
    )
    payload = "\u4f60\u597d, ger\u00e7ekten"
    result = run_command([sys.executable, "-c", echo_stdin_script], input_text=payload)
    assert result.stdout == payload
