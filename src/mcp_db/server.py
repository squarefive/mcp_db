from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_db.snapshots import pull_harmony_sqlite_db as pull_snapshot
from mcp_db.sqlite_query import query_sqlite_db_snapshot as query_snapshot


mcp = FastMCP("harmony-sqlite-db")


def optional_text(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


@mcp.tool()
def pull_harmony_sqlite_db(
    device_id: str,
    bundle_name: str = "",
    db_name: str = "",
    db_path: str = "",
) -> dict[str, Any]:
    """
    Pull a SQLite database snapshot from a HarmonyOS device.

    Use this tool first when the user wants to inspect or query a SQLite
    database inside a HarmonyOS app. The tool copies the remote database to a
    local snapshot directory and also tries to copy related SQLite files such as
    -wal, -shm, and -dwr when they exist.

    Path resolution:
    - If db_path is provided, it is used as the full remote database path.
    - Otherwise bundle_name and db_name are required, and the remote path is
      built as:
      /data/app/el2/100/database/{bundle_name}/entry/rdb/{db_name}

    Returns snapshot_id, local_db_path, pulled_files, and warnings. Use the
    returned snapshot_id with query_sqlite_db_snapshot.
    """
    try:
        return pull_snapshot(
            device_id=device_id.strip(),
            bundle_name=optional_text(bundle_name),
            db_name=optional_text(db_name),
            db_path=optional_text(db_path),
        )
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@mcp.tool()
def query_sqlite_db_snapshot(snapshot_id: str, sql: str = "") -> dict[str, Any]:
    """
    Inspect or query a local SQLite snapshot created by pull_harmony_sqlite_db.

    Use this tool after pull_harmony_sqlite_db returns a snapshot_id. If sql is
    empty or omitted, the tool returns the database schema so the Agent can
    learn table and column names before writing SQL.

    If sql is provided, it must be read-only SQL such as SELECT, WITH, or safe
    PRAGMA. Small result sets are returned inline as rows. Large result sets are
    written to a local JSONL file, and the response returns result_file plus
    preview_rows.

    Typical flow:
    1. Call this tool without sql to inspect schema.
    2. Generate read-only SQL from the returned schema.
    3. Call this tool again with sql to get query results.
    """
    try:
        return query_snapshot(snapshot_id=snapshot_id.strip(), sql=optional_text(sql))
    except Exception as exc:
        return {"status": "error", "snapshot_id": snapshot_id, "message": str(exc)}


if __name__ == "__main__":
    mcp.run()

