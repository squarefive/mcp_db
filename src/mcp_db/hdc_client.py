from __future__ import annotations

import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from typing import Callable


Runner = Callable[..., CompletedProcess[str]]


class HdcError(RuntimeError):
    pass


class HdcClient:
    def __init__(self, runner: Runner | None = None) -> None:
        self._runner = runner or subprocess.run

    def run(self, args: list[str]) -> str:
        command = ["hdc", *args]
        result = self._runner(command, capture_output=True, text=True)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "hdc command failed"
            raise HdcError(message)
        return result.stdout

    def check_shell(self, device_id: str) -> None:
        self.run(["-t", device_id, "shell", "pwd"])

    def exists(self, device_id: str, remote_path: str) -> bool:
        try:
            self.run(["-t", device_id, "shell", f"ls -la {remote_path}"])
        except HdcError:
            return False
        return True

    def recv(self, device_id: str, remote_path: str, local_path: Path) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self.run(["-t", device_id, "file", "recv", remote_path, str(local_path)])

