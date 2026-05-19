from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol


DEFAULT_DB_PATH_TEMPLATE = "/data/app/el2/100/database/{bundle_name}/entry/rdb/{db_name}"
DEFAULT_ARTIFACTS_DIR = Path("artifacts")


class HdcLike(Protocol):
    def check_shell(self, device_id: str) -> None:
        ...

    def exists(self, device_id: str, remote_path: str) -> bool:
        ...

    def recv(self, device_id: str, remote_path: str, local_path: Path) -> None:
        ...


def resolve_remote_db_path(
    bundle_name: str | None,
    db_name: str | None,
    db_path: str | None,
) -> str:
    if db_path:
        return db_path
    if not bundle_name or not db_name:
        raise ValueError("bundle_name and db_name are required when db_path is empty")
    return DEFAULT_DB_PATH_TEMPLATE.format(bundle_name=bundle_name, db_name=db_name)


def default_now() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def build_snapshot_id(timestamp: str, db_name: str) -> str:
    stem = Path(db_name).stem
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", stem).strip("-") or "database"
    return f"{timestamp}-{safe_stem}"


def pull_harmony_sqlite_db(
    device_id: str,
    bundle_name: str | None = None,
    db_name: str | None = None,
    db_path: str | None = None,
    artifacts_dir: Path | str = DEFAULT_ARTIFACTS_DIR,
    hdc_client: HdcLike | None = None,
    now: Callable[[], str] = default_now,
) -> dict[str, object]:
    if hdc_client is None:
        from mcp_db.hdc_client import HdcClient

        hdc_client = HdcClient()

    remote_db_path = resolve_remote_db_path(bundle_name, db_name, db_path)
    resolved_db_name = db_name or Path(remote_db_path).name

    hdc_client.check_shell(device_id)
    if not hdc_client.exists(device_id, remote_db_path):
        return {
            "status": "error",
            "device_id": device_id,
            "remote_db_path": remote_db_path,
            "message": "Remote database file does not exist.",
        }

    snapshot_id = build_snapshot_id(now(), resolved_db_name)
    snapshot_dir = Path(artifacts_dir) / "db-snapshots" / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    pulled_files: list[str] = []
    warnings: list[str] = []

    for suffix, required in [("", True), ("-wal", False), ("-shm", False), ("-dwr", False)]:
        current_remote_path = f"{remote_db_path}{suffix}"
        filename = f"{Path(remote_db_path).name}{suffix}"
        local_path = snapshot_dir / filename

        if not required and not hdc_client.exists(device_id, current_remote_path):
            warnings.append(f"Optional file not found: {filename}")
            continue

        try:
            hdc_client.recv(device_id, current_remote_path, local_path)
        except Exception as exc:
            if required:
                return {
                    "status": "error",
                    "device_id": device_id,
                    "remote_db_path": remote_db_path,
                    "message": str(exc),
                }
            warnings.append(f"Optional file not pulled: {filename}: {exc}")
            continue

        pulled_files.append(filename)

    return {
        "status": "ok",
        "snapshot_id": snapshot_id,
        "device_id": device_id,
        "remote_db_path": remote_db_path,
        "snapshot_dir": str(snapshot_dir),
        "local_db_path": str(snapshot_dir / Path(remote_db_path).name),
        "pulled_files": pulled_files,
        "warnings": warnings,
    }

