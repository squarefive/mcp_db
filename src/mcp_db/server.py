from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_db.snapshots import pull_harmony_sqlite_db as pull_snapshot
from mcp_db.sqlite_query import query_sqlite_db_snapshot as query_snapshot


mcp = FastMCP("harmony-sqlite-db")


@mcp.tool()
def pull_harmony_sqlite_db(
    device_id: str,
    bundle_name: str | None = None,
    db_name: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    try:
        return pull_snapshot(
            device_id=device_id,
            bundle_name=bundle_name,
            db_name=db_name,
            db_path=db_path,
        )
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool()
def query_sqlite_db_snapshot(snapshot_id: str, sql: str | None = None) -> dict[str, Any]:
    try:
        return query_snapshot(snapshot_id=snapshot_id, sql=sql)
    except Exception as exc:
        return {"status": "error", "snapshot_id": snapshot_id, "message": str(exc)}


if __name__ == "__main__":
    mcp.run()

