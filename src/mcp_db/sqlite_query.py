from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_ARTIFACTS_DIR = Path("artifacts")
DEFAULT_INLINE_ROW_THRESHOLD = 1000
DEFAULT_PREVIEW_ROWS_COUNT = 20


def validate_readonly_sql(sql: str) -> None:
    stripped = sql.strip()
    if not stripped:
        raise ValueError("SQL must not be empty")
    first_token = stripped.split(None, 1)[0].rstrip(";").lower()
    if first_token not in {"select", "with", "pragma"}:
        raise ValueError("Only read-only SQL is allowed")
    if first_token == "pragma":
        lowered = stripped.lower()
        if "=" in lowered or any(word in lowered for word in ["writable_schema", "journal_mode"]):
            raise ValueError("Only read-only SQL is allowed")


def query_sqlite_db_snapshot(
    snapshot_id: str,
    sql: str | None = None,
    artifacts_dir: Path | str = DEFAULT_ARTIFACTS_DIR,
    inline_row_threshold: int = DEFAULT_INLINE_ROW_THRESHOLD,
    preview_rows_count: int = DEFAULT_PREVIEW_ROWS_COUNT,
) -> dict[str, Any]:
    local_db_path = find_snapshot_db(Path(artifacts_dir), snapshot_id)
    uri = local_db_path.resolve().as_posix()
    with sqlite3.connect(f"file:{uri}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        if sql is None or not sql.strip():
            return {
                "status": "ok",
                "snapshot_id": snapshot_id,
                "local_db_path": str(local_db_path),
                "schema": read_schema(conn),
            }

        validate_readonly_sql(sql)
        rows, columns = execute_query(conn, sql)

    if len(rows) <= inline_row_threshold:
        return {
            "status": "ok",
            "snapshot_id": snapshot_id,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }

    result_file = write_query_result(Path(artifacts_dir), snapshot_id, rows)
    return {
        "status": "ok",
        "snapshot_id": snapshot_id,
        "columns": columns,
        "row_count": len(rows),
        "result_file": str(result_file),
        "preview_rows": rows[:preview_rows_count],
    }


def find_snapshot_db(artifacts_dir: Path, snapshot_id: str) -> Path:
    snapshot_dir = artifacts_dir / "db-snapshots" / snapshot_id
    candidates = sorted(snapshot_dir.glob("*.db"))
    if not candidates:
        raise FileNotFoundError(f"No .db file found for snapshot_id: {snapshot_id}")
    if len(candidates) > 1:
        raise ValueError(f"Multiple .db files found for snapshot_id: {snapshot_id}")
    return candidates[0]


def read_schema(conn: sqlite3.Connection) -> list[dict[str, object]]:
    table_rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    schema: list[dict[str, object]] = []
    for row in table_rows:
        table_name = row["name"]
        column_rows = conn.execute(f"PRAGMA table_info({quote_identifier(table_name)})").fetchall()
        schema.append(
            {
                "table": table_name,
                "columns": [
                    {"name": column["name"], "type": column["type"]}
                    for column in column_rows
                ],
            }
        )
    return schema


def execute_query(conn: sqlite3.Connection, sql: str) -> tuple[list[dict[str, Any]], list[str]]:
    cursor = conn.execute(sql)
    columns = [description[0] for description in cursor.description or []]
    rows = [dict(row) for row in cursor.fetchall()]
    return rows, columns


def write_query_result(artifacts_dir: Path, snapshot_id: str, rows: list[dict[str, Any]]) -> Path:
    result_dir = artifacts_dir / "query-results" / snapshot_id
    result_dir.mkdir(parents=True, exist_ok=True)
    result_file = result_dir / "query-001.jsonl"
    counter = 1
    while result_file.exists():
        counter += 1
        result_file = result_dir / f"query-{counter:03d}.jsonl"

    with result_file.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, default=str))
            handle.write("\n")
    return result_file


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'

