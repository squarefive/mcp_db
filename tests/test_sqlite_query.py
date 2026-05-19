import json
import sqlite3
from pathlib import Path

import pytest

from mcp_db.sqlite_query import query_sqlite_db_snapshot, validate_readonly_sql


def create_snapshot(tmp_path: Path, snapshot_id: str = "snapshot-1") -> Path:
    snapshot_dir = tmp_path / "db-snapshots" / snapshot_id
    snapshot_dir.mkdir(parents=True)
    db_path = snapshot_dir / "sample.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE logs (id INTEGER PRIMARY KEY, name TEXT)")
        conn.executemany("INSERT INTO logs (name) VALUES (?)", [("a",), ("b",), ("c",)])
    return db_path


def test_returns_schema_when_sql_is_empty(tmp_path: Path) -> None:
    create_snapshot(tmp_path)

    result = query_sqlite_db_snapshot(snapshot_id="snapshot-1", sql=None, artifacts_dir=tmp_path)

    assert result["status"] == "ok"
    assert result["snapshot_id"] == "snapshot-1"
    assert result["schema"] == [
        {
            "table": "logs",
            "columns": [
                {"name": "id", "type": "INTEGER"},
                {"name": "name", "type": "TEXT"},
            ],
        }
    ]


def test_executes_readonly_select(tmp_path: Path) -> None:
    create_snapshot(tmp_path)

    result = query_sqlite_db_snapshot(
        snapshot_id="snapshot-1",
        sql="SELECT id, name FROM logs ORDER BY id",
        artifacts_dir=tmp_path,
    )

    assert result["status"] == "ok"
    assert result["columns"] == ["id", "name"]
    assert result["rows"] == [
        {"id": 1, "name": "a"},
        {"id": 2, "name": "b"},
        {"id": 3, "name": "c"},
    ]
    assert result["row_count"] == 3


def test_rejects_write_sql() -> None:
    with pytest.raises(ValueError, match="Only read-only SQL"):
        validate_readonly_sql("DELETE FROM logs")


def test_writes_large_results_to_jsonl(tmp_path: Path) -> None:
    create_snapshot(tmp_path)

    result = query_sqlite_db_snapshot(
        snapshot_id="snapshot-1",
        sql="SELECT id, name FROM logs ORDER BY id",
        artifacts_dir=tmp_path,
        inline_row_threshold=2,
        preview_rows_count=1,
    )

    assert result["status"] == "ok"
    assert result["columns"] == ["id", "name"]
    assert result["row_count"] == 3
    assert result["preview_rows"] == [{"id": 1, "name": "a"}]
    result_file = Path(result["result_file"])
    assert result_file.exists()
    lines = result_file.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"id": 1, "name": "a"},
        {"id": 2, "name": "b"},
        {"id": 3, "name": "c"},
    ]

