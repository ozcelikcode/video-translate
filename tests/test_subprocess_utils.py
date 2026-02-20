import subprocess
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


def test_run_command_timeout_raises_command_execution_error(monkeypatch: Any) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> SimpleNamespace:
        del args, kwargs
        raise subprocess.TimeoutExpired(cmd="ffmpeg -i x y", timeout=5.0, stderr="still running")

    monkeypatch.setattr("video_translate.utils.subprocess_utils.subprocess.run", fake_run)

    with pytest.raises(CommandExecutionError, match="timed out"):
        run_command(["ffmpeg", "-i", "x", "y"], timeout_seconds=5.0)
