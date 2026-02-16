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


def run_command(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CommandExecutionError(command, result.returncode, result.stderr)
    return result

