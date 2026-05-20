from pathlib import Path
from subprocess import CompletedProcess

import pytest

from mcp_db.hdc_client import HdcClient, HdcError


def test_check_shell_runs_pwd() -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        calls.append(command)
        return CompletedProcess(command, 0, stdout="/\n", stderr="")

    client = HdcClient(runner=fake_run)

    client.check_shell("device-1")

    assert calls == [["hdc", "-t", "device-1", "shell", "pwd"]]


def test_exists_returns_false_when_ls_fails() -> None:
    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(command, 1, stdout="", stderr="No such file")

    client = HdcClient(runner=fake_run)

    assert client.exists("device-1", "/missing.db") is False


def test_recv_wraps_hdc_file_recv(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        calls.append(command)
        return CompletedProcess(command, 0, stdout="", stderr="")

    client = HdcClient(runner=fake_run)
    local_path = tmp_path / "app.db"

    client.recv("device-1", "/remote/app.db", local_path)

    assert calls == [["hdc", "-t", "device-1", "file", "recv", "/remote/app.db", str(local_path)]]


def test_run_raises_on_failure() -> None:
    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(command, 1, stdout="", stderr="failed")

    client = HdcClient(runner=fake_run)

    with pytest.raises(HdcError, match="failed"):
        client.check_shell("device-1")

