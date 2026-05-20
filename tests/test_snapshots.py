from pathlib import Path

import pytest

from mcp_db.snapshots import pull_harmony_sqlite_db, resolve_remote_db_path


def test_db_path_takes_priority_over_template() -> None:
    path = resolve_remote_db_path(
        bundle_name="com.example.app",
        db_name="ignored.db",
        db_path="/custom/path/app.db",
    )

    assert path == "/custom/path/app.db"


def test_builds_default_harmony_database_path() -> None:
    path = resolve_remote_db_path(
        bundle_name="com.example.app",
        db_name="app.db",
        db_path=None,
    )

    assert path == "/data/app/el2/100/database/com.example.app/entry/rdb/app.db"


def test_requires_bundle_and_db_name_without_db_path() -> None:
    with pytest.raises(ValueError, match="bundle_name and db_name"):
        resolve_remote_db_path(bundle_name=None, db_name="app.db", db_path=None)


class FakeHdcClient:
    def __init__(self) -> None:
        self.received: list[tuple[str, Path]] = []

    def check_shell(self, device_id: str) -> None:
        assert device_id == "device-1"

    def exists(self, device_id: str, remote_path: str) -> bool:
        assert device_id == "device-1"
        return not remote_path.endswith("-shm")

    def recv(self, device_id: str, remote_path: str, local_path: Path) -> None:
        assert device_id == "device-1"
        local_path.write_text("db", encoding="utf-8")
        self.received.append((remote_path, local_path))


def test_pull_snapshot_pulls_main_db_and_optional_files(tmp_path: Path) -> None:
    client = FakeHdcClient()

    result = pull_harmony_sqlite_db(
        device_id="device-1",
        bundle_name="com.example.app",
        db_name="app.db",
        db_path=None,
        artifacts_dir=tmp_path,
        hdc_client=client,
        now=lambda: "20260519-173000",
    )

    assert result["status"] == "ok"
    assert result["snapshot_id"] == "20260519-173000-app"
    assert result["remote_db_path"] == "/data/app/el2/100/database/com.example.app/entry/rdb/app.db"
    assert result["local_db_path"].endswith("app.db")
    assert result["pulled_files"] == ["app.db", "app.db-wal", "app.db-dwr"]
    assert result["warnings"] == ["Optional file not found: app.db-shm"]
    assert len(client.received) == 3

