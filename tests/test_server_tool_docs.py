from mcp_db.server import pull_harmony_sqlite_db, query_sqlite_db_snapshot


def test_pull_tool_docstring_explains_snapshot_flow() -> None:
    doc = pull_harmony_sqlite_db.__doc__ or ""

    assert "Pull a SQLite database snapshot from a HarmonyOS device." in doc
    assert "db_path" in doc
    assert "bundle_name" in doc
    assert "query_sqlite_db_snapshot" in doc


def test_query_tool_docstring_explains_schema_and_readonly_sql() -> None:
    doc = query_sqlite_db_snapshot.__doc__ or ""

    assert "Inspect or query a local SQLite snapshot" in doc
    assert "schema" in doc
    assert "read-only SQL" in doc
    assert "result_file" in doc

