from __future__ import annotations

import subprocess
from pathlib import Path


class CommandExecutionError(RuntimeError):
    def __init__(self, command: list[str], returncode: int, stderr: str) -> None:
        joined = " ".join(command)
        super().__init__(f"Command failed ({returncode}): {joined}\n{stderr.strip()}")
        self.command = command
        self.returncode = returncode
        self.stderr = stderr


def run_command(
    command: list[str],
    cwd: Path | None = None,
    input_text: str | None = None,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
            input=input_text,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_label = (
            f"{int(timeout_seconds)}s"
            if timeout_seconds is not None
            else "timeout"
        )
        stderr_text = ""
        if isinstance(exc.stderr, str):
            stderr_text = exc.stderr.strip()
        elif exc.stderr is not None:
            try:
                stderr_text = exc.stderr.decode("utf-8", errors="replace").strip()
            except Exception:  # noqa: BLE001
                stderr_text = str(exc.stderr)
        message = f"Command timed out after {timeout_label}."
        if stderr_text:
            message = f"{message}\n{stderr_text}"
        raise CommandExecutionError(command, -9, message) from exc
    if result.returncode != 0:
        raise CommandExecutionError(command, result.returncode, result.stderr)
    return result
