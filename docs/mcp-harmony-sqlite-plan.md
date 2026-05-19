# HarmonyOS SQLite MCP 工具实施方案

## 工作区与分支

- 工作区：`D:\project\ai\mcp_db`
- 工作分支：`feature/harmony-sqlite-mcp`

## 背景

项目目标是实现一个通用 MCP 工具集，用于从 HarmonyOS 设备拉取指定 SQLite 数据库快照，并让 AI 基于本地快照查询数据库结构或执行只读 SQL。

工具不绑定具体业务数据库，不内置 `security_tool.db`、`log_entries`、`event_type` 等业务语义。

## 目的

第一版实现两个 MCP 工具：

- `pull_harmony_sqlite_db`：从 HarmonyOS 设备拉取 SQLite 数据库快照。
- `query_sqlite_db_snapshot`：查询本地 SQLite 快照；未传 SQL 时返回 schema，传 SQL 时执行只读 SQL。

## 修改文件范围

文档阶段：

- 修改：`AGENTS.md`
- 创建：`docs/mcp-harmony-sqlite-plan.md`

代码阶段：

- 创建：`pyproject.toml`
- 创建：`src/mcp_db/__init__.py`
- 创建：`src/mcp_db/server.py`
- 创建：`src/mcp_db/hdc_client.py`
- 创建：`src/mcp_db/snapshots.py`
- 创建：`src/mcp_db/sqlite_query.py`
- 创建：`tests/test_snapshots.py`
- 创建：`tests/test_sqlite_query.py`
- 创建：`tests/test_hdc_client.py`

不修改其他文件。

## 工具 1：pull_harmony_sqlite_db

输入：

```json
{
  "device_id": "3QC0124905000019",
  "bundle_name": "com.huawei.securitytool",
  "db_name": "security_tool.db",
  "db_path": null
}
```

字段含义：

- `device_id`：目标 HarmonyOS 设备 ID。
- `bundle_name`：应用包名。仅当 `db_path` 为空时使用。
- `db_name`：数据库文件名。仅当 `db_path` 为空时使用。
- `db_path`：设备上的数据库完整路径。传入后优先使用，不再拼接默认路径。

路径规则：

```text
if db_path is provided:
    remote_db_path = db_path
else:
    remote_db_path = /data/app/el2/100/database/{bundle_name}/entry/rdb/{db_name}
```

业务逻辑：

1. 检查设备 shell 可用。
2. 解析远端数据库路径。
3. 检查远端主 `.db` 文件存在。
4. 创建本地快照目录：`artifacts/db-snapshots/<snapshot_id>`。
5. 拉取主 `.db` 文件。
6. 尝试拉取 `.db-wal`、`.db-shm`、`.db-dwr`。
7. 主库失败则返回错误；附属文件失败只记录 `warnings`。

输出：

```json
{
  "status": "ok",
  "snapshot_id": "20260519-173000-security_tool",
  "device_id": "3QC0124905000019",
  "remote_db_path": "/data/app/el2/100/database/com.huawei.securitytool/entry/rdb/security_tool.db",
  "snapshot_dir": "artifacts/db-snapshots/20260519-173000-security_tool",
  "local_db_path": "artifacts/db-snapshots/20260519-173000-security_tool/security_tool.db",
  "pulled_files": ["security_tool.db", "security_tool.db-wal"],
  "warnings": ["Optional file not found: security_tool.db-shm"]
}
```

## 工具 2：query_sqlite_db_snapshot

输入：

```json
{
  "snapshot_id": "20260519-173000-security_tool",
  "sql": null
}
```

字段含义：

- `snapshot_id`：`pull_harmony_sqlite_db` 返回的本地快照 ID。
- `sql`：可选。为空时返回表结构；有值时执行只读 SQL。

业务逻辑：

1. 根据 `snapshot_id` 定位本地快照目录和 `.db` 文件。
2. 使用 Python `sqlite3` 只读打开数据库。
3. `sql` 为空时返回 schema。
4. `sql` 有值时仅允许只读 SQL：`SELECT`、`WITH`、安全 `PRAGMA`。
5. 小结果直接返回 `rows`。
6. 大结果保存到 `artifacts/query-results/<snapshot_id>/<query_id>.jsonl`，返回 `result_file` 和 `preview_rows`。

无 SQL 输出：

```json
{
  "status": "ok",
  "snapshot_id": "20260519-173000-security_tool",
  "local_db_path": "artifacts/db-snapshots/20260519-173000-security_tool/security_tool.db",
  "schema": [
    {
      "table": "log_entries",
      "columns": [
        {"name": "id", "type": "INTEGER"},
        {"name": "timestamp", "type": "INTEGER"}
      ]
    }
  ]
}
```

小结果输出：

```json
{
  "status": "ok",
  "snapshot_id": "20260519-173000-security_tool",
  "columns": ["id", "timestamp"],
  "rows": [
    {"id": 1, "timestamp": 1710000000}
  ],
  "row_count": 1
}
```

大结果输出：

```json
{
  "status": "ok",
  "snapshot_id": "20260519-173000-security_tool",
  "columns": ["id", "timestamp"],
  "row_count": 25000,
  "result_file": "artifacts/query-results/20260519-173000-security_tool/query-001.jsonl",
  "preview_rows": [
    {"id": 1, "timestamp": 1710000000}
  ]
}
```

## 执行步骤

### 步骤 1：文档落地并提交

输入：本方案内容。

输出：`docs/mcp-harmony-sqlite-plan.md` 和 `AGENTS.md` 索引。

验收标准：

- 文档包含两个工具的输入、输出、字段含义和业务逻辑。
- 文档明确 `db_path` 优先，否则按默认模板拼接。
- 文档明确大结果保存本地文件。
- 文档提交到 Git。

### 步骤 2：初始化 Python 项目骨架

输入：已提交的方案文档。

输出：`pyproject.toml`、`src/mcp_db`、`tests`。

验收标准：

- `pytest` 可运行。
- 依赖包含 `fastmcp` 和 `pytest`。
- 不包含业务专用数据库逻辑。

### 步骤 3：实现路径解析和快照目录规则

输入：`bundle_name`、`db_name`、可选 `db_path`。

输出：远端数据库路径、本地快照目录。

验收标准：

- `db_path` 有值时优先使用。
- `db_path` 为空时必须有 `bundle_name + db_name`。
- 快照目录生成到 `artifacts/db-snapshots/<snapshot_id>`。

伪代码：

```python
def resolve_remote_db_path(bundle_name, db_name, db_path):
    if db_path:
        return db_path
    if not bundle_name or not db_name:
        raise ValueError("bundle_name and db_name are required when db_path is empty")
    return f"/data/app/el2/100/database/{bundle_name}/entry/rdb/{db_name}"
```

### 步骤 4：实现 hdc 封装

输入：`device_id`、远端路径、本地路径。

输出：命令执行结果或错误。

验收标准：

- 可以检查设备 shell 是否可用。
- 可以检查远端文件是否存在。
- 可以拉取主 `.db`。
- 附属文件拉取失败可转成 warning。

伪代码：

```python
def run_hdc(args):
    result = subprocess.run(["hdc", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise HdcError(result.stderr)
    return result.stdout
```

### 步骤 5：实现 pull_harmony_sqlite_db

输入：`device_id`、`bundle_name`、`db_name`、`db_path`。

输出：`snapshot_id`、`remote_db_path`、`snapshot_dir`、`local_db_path`、`pulled_files`、`warnings`。

验收标准：

- 主库不存在返回错误。
- 主库拉取成功返回 `status: ok`。
- 可选附属文件失败不影响成功。

### 步骤 6：实现 schema 查询

输入：`snapshot_id`、`sql=None`。

输出：表名和列信息。

验收标准：

- 只读打开 SQLite。
- 返回表名和列名、列类型。

伪代码：

```python
def get_schema(conn):
    tables = query("SELECT name FROM sqlite_master WHERE type='table'")
    for table in tables:
        columns = query(f"PRAGMA table_info({quoted_table})")
```

### 步骤 7：实现只读 SQL 查询

输入：`snapshot_id`、`sql`。

输出：小结果返回 `rows`，大结果写文件。

验收标准：

- 允许 `SELECT`、`WITH`、安全 `PRAGMA`。
- 拒绝写入或危险 SQL。
- 大结果写入 JSONL 文件。

伪代码：

```python
def validate_readonly_sql(sql):
    first = sql.strip().split()[0].lower()
    if first not in {"select", "with", "pragma"}:
        raise ValueError("Only read-only SQL is allowed")
```

### 步骤 8：清理腐败代码

输入：实施过程中产生的临时脚本、探索代码、未使用函数。

输出：干净代码树。

验收标准：

- 不提交临时 debug 脚本。
- 不保留未调用的探索函数。
- 不保留硬编码 `security_tool.db` 的业务逻辑。

### 步骤 9：验证和提交代码

输入：完整实现。

输出：测试通过，代码提交。

验收标准：

- `pytest` 通过。
- 真机路径 `/data/app/el2/100/database/com.huawei.securitytool/entry/rdb/security_tool.db` 可用于集成验证。
- 提交代码变更。
