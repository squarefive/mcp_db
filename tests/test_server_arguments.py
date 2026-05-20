from typing import Any

import mcp_db.server as server


def test_pull_tool_normalizes_empty_optional_strings(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_pull_snapshot(**kwargs: Any) -> dict[str, str]:
        captured.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(server, "pull_snapshot", fake_pull_snapshot)

    result = server.pull_harmony_sqlite_db(
        device_id=" device-1 ",
        bundle_name=" com.example.app ",
        db_name=" app.db ",
        db_path="",
    )

    assert result == {"status": "ok"}
    assert captured == {
        "device_id": "device-1",
        "bundle_name": "com.example.app",
        "db_name": "app.db",
        "db_path": None,
    }


def test_query_tool_normalizes_empty_sql(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_query_snapshot(**kwargs: Any) -> dict[str, str]:
        captured.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(server, "query_snapshot", fake_query_snapshot)

    result = server.query_sqlite_db_snapshot(snapshot_id=" snapshot-1 ", sql="   ")

    assert result == {"status": "ok"}
    assert captured == {
        "snapshot_id": "snapshot-1",
        "sql": None,
    }


def test_tool_annotations_use_plain_strings_for_inspector_inputs() -> None:
    assert server.pull_harmony_sqlite_db.__annotations__ == {
        "device_id": "str",
        "bundle_name": "str",
        "db_name": "str",
        "db_path": "str",
        "return": "dict[str, Any]",
    }
    assert server.query_sqlite_db_snapshot.__annotations__ == {
        "snapshot_id": "str",
        "sql": "str",
        "return": "dict[str, Any]",
    }
