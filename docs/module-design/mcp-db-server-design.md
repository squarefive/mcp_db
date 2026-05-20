---
module: "mcp_db_server"
title: "HarmonyOS SQLite MCP 工具"
language: "Python"
last_updated: "2026-05-20"
---

# HarmonyOS SQLite MCP 工具设计文档

> **[AI 阅读契约]**
> 本文档为该模块的上下文核心。在协助修改或生成本模块代码时，请严格参考此文档中的**业务流**与**文件结构**，切勿脱离现有模块边界。代码逻辑必须服从文档设计。

## 1. 模块背景
- **业务痛点/需求**: 需要一个通用 MCP 工具集，从 HarmonyOS 设备拉取指定 SQLite 数据库快照，并让 MCP 客户端基于本地快照检查 schema 或执行只读 SQL 查询。
- **核心价值**: 为 MCP 客户端提供安全、结构化、可复用的 HarmonyOS SQLite 数据库快照获取与查询能力。

## 2. 功能概览介绍
- **核心功能**:
  1. 通过 `pull_harmony_sqlite_db` 从 HarmonyOS 设备拉取 SQLite 数据库快照。
  2. 支持显式 `db_path`，或基于 `bundle_name` 与 `db_name` 生成默认远端数据库路径。
  3. 拉取主 `.db` 文件，并尝试拉取 `.db-wal`、`.db-shm`、`.db-dwr` 附属文件。
  4. 通过 `query_sqlite_db_snapshot` 检查本地快照 schema。
  5. 对本地 SQLite 快照执行只读 SQL，并按结果大小返回内联数据或 JSONL 结果文件。
- **边界说明**:
  - ✅ **包含**: HarmonyOS 设备数据库快照拉取、本地快照定位、SQLite schema 读取、只读 SQL 查询、大结果 JSONL 落盘、MCP 工具入口参数归一化和结构化返回。
  - ❌ **不包含**: 数据库写入、设备文件删除、任意 SQL 执行平台、业务专用数据库语义、Web UI、非 SQLite 数据库支持。

## 3. 核心业务流

### 场景 1：从 HarmonyOS 设备拉取 SQLite 快照
- **触发源**: `MCP 客户端调用 pull_harmony_sqlite_db`
- **执行流程**:
  1. `参数归一化` -> `server.py` 去除字符串参数首尾空白，并将空字符串可选参数转为 `None`。
  2. `解析远端数据库路径` -> `snapshots.py` 优先使用 `db_path`；否则按 `/data/app/el2/100/database/{bundle_name}/entry/rdb/{db_name}` 生成路径。
     - ➔ **[异常分支: 缺少 bundle_name 或 db_name]**: 抛出参数错误，并由 MCP 工具入口返回 `status: error`。
  3. `检查设备 shell` -> `hdc_client.py` 执行 `hdc -t {device_id} shell pwd`。
     - ➔ **[异常分支: hdc 命令失败]**: 抛出 `HdcError`，并返回错误信息。
  4. `检查主库存在` -> 通过 `hdc shell ls -la {remote_db_path}` 判断远端主 `.db` 文件是否存在。
     - ➔ **[异常分支: 主库不存在]**: 返回 `status: error`，不创建成功快照。
  5. `创建快照目录` -> 在 `artifacts/db-snapshots/{snapshot_id}` 下创建本地目录。
  6. `拉取数据库文件` -> 拉取主 `.db` 文件，并尝试拉取 `.db-wal`、`.db-shm`、`.db-dwr`。
     - ➔ **[异常分支: 主库拉取失败]**: 返回 `status: error`。
     - ➔ **[分支: 附属文件不存在或拉取失败]**: 记录 `warnings`，不阻断主流程。
  7. `返回快照信息` -> 返回 `snapshot_id`、`remote_db_path`、`snapshot_dir`、`local_db_path`、`pulled_files` 和 `warnings`。

### 场景 2：检查本地 SQLite 快照 schema
- **触发源**: `MCP 客户端调用 query_sqlite_db_snapshot，sql 为空`
- **执行流程**:
  1. `参数归一化` -> `server.py` 去除 `snapshot_id` 首尾空白，并将空 SQL 转为 `None`。
  2. `定位快照数据库` -> `sqlite_query.py` 在 `artifacts/db-snapshots/{snapshot_id}` 下查找唯一 `.db` 文件。
     - ➔ **[异常分支: 无 .db 文件]**: 抛出 `FileNotFoundError`，并由 MCP 工具入口返回 `status: error`。
     - ➔ **[异常分支: 多个 .db 文件]**: 抛出 `ValueError`，并由 MCP 工具入口返回 `status: error`。
  3. `只读打开数据库` -> 使用 `sqlite3.connect("file:{path}?mode=ro", uri=True)` 打开本地数据库。
  4. `读取 schema` -> 查询非 `sqlite_%` 系统表，并通过 `PRAGMA table_info` 读取字段名和字段类型。
  5. `返回 schema` -> 返回 `status`、`snapshot_id`、`local_db_path` 和 `schema`。

### 场景 3：执行只读 SQL 查询
- **触发源**: `MCP 客户端调用 query_sqlite_db_snapshot，sql 非空`
- **执行流程**:
  1. `定位并只读打开快照数据库` -> 与 schema 检查流程一致。
  2. `校验 SQL 类型` -> `validate_readonly_sql` 仅允许 `SELECT`、`WITH`、安全 `PRAGMA`。
     - ➔ **[异常分支: 写入或危险 SQL]**: 抛出 `ValueError`，并由 MCP 工具入口返回 `status: error`。
  3. `执行查询` -> 使用 SQLite cursor 执行 SQL，并将结果行转换为字典列表。
  4. `结果规模判定` -> 结果行数不超过阈值时直接返回 `rows`。
     - ➔ **[分支: 大结果]**: 写入 `artifacts/query-results/{snapshot_id}/query-XXX.jsonl`，返回 `result_file` 和 `preview_rows`。
  5. `返回查询结果` -> 返回 `columns`、`row_count`，以及内联结果或结果文件路径。

## 4. 代码文件、核心对象及契约说明

### `src/mcp_db/server.py`
- **状态**: 已实现
- **文件职责**: 定义 FastMCP 服务实例、MCP 工具入口、参数归一化和统一错误返回。

#### `optional_text(value)`
- **类型**: 内部函数
- **职责**: 去除字符串首尾空白，并将空字符串归一化为 `None`。
- **输入契约**:
  - `value`: `str`，待归一化文本。
- **输出契约**:
  - `str | None`: 非空文本返回 `str`，空文本返回 `None`。
- **错误/异常**:
  - 无主动抛出的业务异常。
- **调用约束**: 仅用于 MCP 工具入口参数归一化。

#### `pull_harmony_sqlite_db(device_id, bundle_name, db_name, db_path)`
- **类型**: 对外入口 / MCP 工具
- **职责**: 从 HarmonyOS 设备拉取 SQLite 数据库快照，返回本地快照位置和拉取结果。
- **输入契约**:
  - `device_id`: `str`，必填，目标 HarmonyOS 设备 ID。
  - `bundle_name`: `str`，可选；当 `db_path` 为空时必填，用于拼接默认远端数据库路径。
  - `db_name`: `str`，可选；当 `db_path` 为空时必填，用于拼接默认远端数据库路径和生成快照 ID。
  - `db_path`: `str`，可选；有值时优先作为完整远端数据库路径。
- **输出契约**:
  - 成功：`status`、`snapshot_id`、`device_id`、`remote_db_path`、`snapshot_dir`、`local_db_path`、`pulled_files`、`warnings`。
  - 失败：`status: error`、`message`；部分底层错误会同时返回 `device_id`、`remote_db_path`。
- **错误/异常**:
  - `bundle_name` 或 `db_name` 缺失：当 `db_path` 为空时触发，返回 `status: error`。
  - `hdc` 命令失败：返回 `status: error` 和底层错误信息。
  - 远端主 `.db` 文件不存在：返回 `status: error`。
  - 主库拉取失败：返回 `status: error`。
- **调用约束**:
  - 所有字符串参数会先 `strip()`。
  - `bundle_name`、`db_name`、`db_path` 为空字符串时会归一化为 `None`。
  - `db_path` 有值时优先使用，不再拼接默认路径。
  - 主 `.db` 文件必须存在并成功拉取；`.db-wal`、`.db-shm`、`.db-dwr` 缺失或拉取失败只记录 `warnings`。
  - 返回的 `snapshot_id` 用于后续调用 `query_sqlite_db_snapshot`。
- **示例**:
  ```json
  {
    "input": {
      "device_id": "3QC0124905000019",
      "bundle_name": "com.huawei.securitytool",
      "db_name": "security_tool.db",
      "db_path": ""
    },
    "success": {
      "status": "ok",
      "snapshot_id": "20260519-173000-security_tool",
      "device_id": "3QC0124905000019",
      "remote_db_path": "/data/app/el2/100/database/com.huawei.securitytool/entry/rdb/security_tool.db",
      "snapshot_dir": "artifacts/db-snapshots/20260519-173000-security_tool",
      "local_db_path": "artifacts/db-snapshots/20260519-173000-security_tool/security_tool.db",
      "pulled_files": ["security_tool.db", "security_tool.db-wal"],
      "warnings": ["Optional file not found: security_tool.db-shm"]
    },
    "error": {
      "status": "error",
      "message": "Remote database file does not exist."
    }
  }
  ```

#### `query_sqlite_db_snapshot(snapshot_id, sql)`
- **类型**: 对外入口 / MCP 工具
- **职责**: 检查或查询本地 SQLite 快照；空 SQL 返回 schema，非空 SQL 执行只读查询。
- **输入契约**:
  - `snapshot_id`: `str`，必填，由 `pull_harmony_sqlite_db` 成功返回。
  - `sql`: `str`，可选；为空时返回 schema，非空时必须是只读 SQL。
- **输出契约**:
  - Schema 查询：`status`、`snapshot_id`、`local_db_path`、`schema`。
  - 小结果查询：`status`、`snapshot_id`、`columns`、`rows`、`row_count`。
  - 大结果查询：`status`、`snapshot_id`、`columns`、`row_count`、`result_file`、`preview_rows`。
  - 失败：`status: error`、`snapshot_id`、`message`。
- **错误/异常**:
  - 快照目录下无 `.db` 文件：返回 `status: error`。
  - 快照目录下存在多个 `.db` 文件：返回 `status: error`。
  - SQL 为空但被直接传入底层校验：抛出并返回 SQL 不能为空的错误。
  - 非只读 SQL 或危险 `PRAGMA`：返回 `status: error`。
  - SQLite 打开或查询失败：返回 `status: error` 和底层错误信息。
- **调用约束**:
  - `snapshot_id` 会先 `strip()`。
  - `sql` 会先 `strip()`；空字符串归一化为 `None`。
  - 只读 SQL 仅允许 `SELECT`、`WITH`、安全 `PRAGMA`。
  - 查询结果行数不超过内联阈值时返回 `rows`。
  - 查询结果超过内联阈值时写入 `artifacts/query-results/{snapshot_id}/query-XXX.jsonl`，并返回 `preview_rows`。
- **示例**:
  ```json
  {
    "input_schema": {
      "snapshot_id": "20260519-173000-security_tool",
      "sql": ""
    },
    "schema_success": {
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
    },
    "small_result_success": {
      "status": "ok",
      "snapshot_id": "20260519-173000-security_tool",
      "columns": ["id", "timestamp"],
      "rows": [
        {"id": 1, "timestamp": 1710000000}
      ],
      "row_count": 1
    },
    "large_result_success": {
      "status": "ok",
      "snapshot_id": "20260519-173000-security_tool",
      "columns": ["id", "timestamp"],
      "row_count": 25000,
      "result_file": "artifacts/query-results/20260519-173000-security_tool/query-001.jsonl",
      "preview_rows": [
        {"id": 1, "timestamp": 1710000000}
      ]
    },
    "error": {
      "status": "error",
      "snapshot_id": "20260519-173000-security_tool",
      "message": "Only read-only SQL is allowed"
    }
  }
  ```

### `src/mcp_db/hdc_client.py`
- **状态**: 已实现
- **文件职责**: 封装 HarmonyOS `hdc` 命令执行、设备 shell 检查、远端文件存在性检查和文件拉取。

#### `HdcError`
- **类型**: 内部异常
- **职责**: 表示 `hdc` 命令执行失败。
- **输入契约**: 继承 `RuntimeError` 的异常消息。
- **输出契约**: 作为异常向上抛出。
- **错误/异常**: 无额外封装。
- **调用约束**: 由 `HdcClient.run` 在命令返回码非 0 时抛出。

#### `HdcClient(runner)`
- **类型**: 内部类
- **职责**: 封装设备通信命令，支持注入 runner 以便测试。
- **输入契约**:
  - `runner`: 可选 callable，默认使用 `subprocess.run`。
- **输出契约**:
  - `HdcClient`: 可执行 `run`、`check_shell`、`exists`、`recv` 的客户端实例。
- **错误/异常**:
  - 底层命令失败时通过 `HdcError` 表达。
- **调用约束**: 所有实际设备通信都通过 `hdc` 命令完成。

#### `HdcClient.run(args)`
- **类型**: 内部函数
- **职责**: 执行 `hdc` 命令并返回 stdout。
- **输入契约**:
  - `args`: `list[str]`，不包含开头 `hdc` 的命令参数。
- **输出契约**:
  - `str`: 命令 stdout。
- **错误/异常**:
  - 返回码非 0 时抛出 `HdcError`。
- **调用约束**: 使用 `capture_output=True` 和 `text=True`。

#### `HdcClient.check_shell(device_id)`
- **类型**: 内部函数
- **职责**: 检查目标设备 shell 是否可用。
- **输入契约**:
  - `device_id`: `str`，目标设备 ID。
- **输出契约**: 无返回值。
- **错误/异常**:
  - shell 检查失败时抛出 `HdcError`。
- **调用约束**: 执行 `hdc -t {device_id} shell pwd`。

#### `HdcClient.exists(device_id, remote_path)`
- **类型**: 内部函数
- **职责**: 检查设备侧路径是否存在。
- **输入契约**:
  - `device_id`: `str`，目标设备 ID。
  - `remote_path`: `str`，设备侧路径。
- **输出契约**:
  - `bool`: 路径存在返回 `True`，检查失败返回 `False`。
- **错误/异常**:
  - 捕获 `HdcError` 并转换为 `False`。
- **调用约束**: 执行 `hdc -t {device_id} shell ls -la {remote_path}`。

#### `HdcClient.recv(device_id, remote_path, local_path)`
- **类型**: 内部函数
- **职责**: 创建本地目录并从设备拉取文件。
- **输入契约**:
  - `device_id`: `str`，目标设备 ID。
  - `remote_path`: `str`，设备侧文件路径。
  - `local_path`: `Path`，本地保存路径。
- **输出契约**: 无返回值。
- **错误/异常**:
  - 拉取失败时抛出 `HdcError`。
- **调用约束**: 执行 `hdc -t {device_id} file recv {remote_path} {local_path}`。

### `src/mcp_db/snapshots.py`
- **状态**: 已实现
- **文件职责**: 负责远端数据库路径解析、快照 ID 生成、快照目录创建、主库与附属文件拉取，以及快照结果组装。

#### `resolve_remote_db_path(bundle_name, db_name, db_path)`
- **类型**: 内部函数
- **职责**: 解析设备侧数据库路径。
- **输入契约**:
  - `bundle_name`: `str | None`，应用包名。
  - `db_name`: `str | None`，数据库文件名。
  - `db_path`: `str | None`，完整远端路径。
- **输出契约**:
  - `str`: 设备侧数据库完整路径。
- **错误/异常**:
  - `db_path` 为空且缺少 `bundle_name` 或 `db_name` 时抛出 `ValueError`。
- **调用约束**: `db_path` 优先；否则使用 HarmonyOS 默认数据库路径模板。

#### `default_now()`
- **类型**: 内部函数
- **职责**: 生成快照 ID 使用的时间戳。
- **输入契约**: 无。
- **输出契约**:
  - `str`: `YYYYMMDD-HHMMSS` 格式时间戳。
- **错误/异常**: 无主动抛出的业务异常。
- **调用约束**: 使用本地系统时间。

#### `build_snapshot_id(timestamp, db_name)`
- **类型**: 内部函数
- **职责**: 基于时间戳和数据库文件名生成安全快照 ID。
- **输入契约**:
  - `timestamp`: `str`，时间戳。
  - `db_name`: `str`，数据库文件名。
- **输出契约**:
  - `str`: `{timestamp}-{safe_stem}` 格式快照 ID。
- **错误/异常**: 无主动抛出的业务异常。
- **调用约束**: 文件名 stem 中非安全字符会替换为 `-`。

#### `pull_harmony_sqlite_db(device_id, bundle_name, db_name, db_path, artifacts_dir, hdc_client, now)`
- **类型**: 内部函数
- **职责**: 编排设备检查、远端文件检查、快照目录创建、数据库文件拉取和结果返回。
- **输入契约**:
  - `device_id`: `str`，目标设备 ID。
  - `bundle_name`: `str | None`，应用包名。
  - `db_name`: `str | None`，数据库文件名。
  - `db_path`: `str | None`，完整远端路径。
  - `artifacts_dir`: `Path | str`，本地 artifacts 根目录。
  - `hdc_client`: `HdcLike | None`，设备通信客户端。
  - `now`: callable，返回快照时间戳。
- **输出契约**:
  - `dict[str, object]`: 成功或失败的结构化结果。
- **错误/异常**:
  - 参数解析错误向上抛出，由 MCP 工具入口转换为错误返回。
  - 主库不存在或主库拉取失败时返回 `status: error`。
- **调用约束**: 附属文件拉取失败只记录 `warnings`。

### `src/mcp_db/sqlite_query.py`
- **状态**: 已实现
- **文件职责**: 负责本地 SQLite 快照定位、只读 SQL 校验、schema 读取、查询执行和大结果 JSONL 写入。

#### `validate_readonly_sql(sql)`
- **类型**: 内部函数
- **职责**: 校验 SQL 非空，并限制为只读语句。
- **输入契约**:
  - `sql`: `str`，待执行 SQL。
- **输出契约**: 无返回值。
- **错误/异常**:
  - SQL 为空、非 `SELECT` / `WITH` / `PRAGMA`，或危险 `PRAGMA` 时抛出 `ValueError`。
- **调用约束**: `PRAGMA` 不允许包含 `=`、`writable_schema`、`journal_mode`。

#### `query_sqlite_db_snapshot(snapshot_id, sql, artifacts_dir, inline_row_threshold, preview_rows_count)`
- **类型**: 内部函数
- **职责**: 打开本地快照数据库；无 SQL 时返回 schema，有 SQL 时执行只读查询并按结果大小返回。
- **输入契约**:
  - `snapshot_id`: `str`，本地快照 ID。
  - `sql`: `str | None`，可选 SQL。
  - `artifacts_dir`: `Path | str`，artifacts 根目录。
  - `inline_row_threshold`: `int`，内联返回最大行数。
  - `preview_rows_count`: `int`，大结果预览行数。
- **输出契约**:
  - `dict[str, Any]`: schema、小结果或大结果结构。
- **错误/异常**:
  - 快照定位、SQL 校验、SQLite 查询错误向上抛出，由 MCP 工具入口转换为错误返回。
- **调用约束**: SQLite 使用只读 URI 模式打开。

#### `find_snapshot_db(artifacts_dir, snapshot_id)`
- **类型**: 内部函数
- **职责**: 在快照目录下查找唯一 `.db` 文件。
- **输入契约**:
  - `artifacts_dir`: `Path`，artifacts 根目录。
  - `snapshot_id`: `str`，本地快照 ID。
- **输出契约**:
  - `Path`: 唯一 `.db` 文件路径。
- **错误/异常**:
  - 无 `.db` 文件时抛出 `FileNotFoundError`。
  - 多个 `.db` 文件时抛出 `ValueError`。
- **调用约束**: 仅扫描 `artifacts/db-snapshots/{snapshot_id}` 下的 `*.db`。

#### `read_schema(conn)`
- **类型**: 内部函数
- **职责**: 读取用户表及其字段名、字段类型。
- **输入契约**:
  - `conn`: `sqlite3.Connection`，已打开连接。
- **输出契约**:
  - `list[dict[str, object]]`: 表结构列表。
- **错误/异常**:
  - SQLite 查询错误向上抛出。
- **调用约束**: 过滤 `sqlite_%` 系统表。

#### `execute_query(conn, sql)`
- **类型**: 内部函数
- **职责**: 执行 SQL 并返回行数据和列名。
- **输入契约**:
  - `conn`: `sqlite3.Connection`，已打开连接。
  - `sql`: `str`，已通过只读校验的 SQL。
- **输出契约**:
  - `tuple[list[dict[str, Any]], list[str]]`: 行数据和列名。
- **错误/异常**:
  - SQLite 查询错误向上抛出。
- **调用约束**: 调用前必须完成只读 SQL 校验。

#### `write_query_result(artifacts_dir, snapshot_id, rows)`
- **类型**: 内部函数
- **职责**: 将大结果写入递增编号的 JSONL 文件。
- **输入契约**:
  - `artifacts_dir`: `Path`，artifacts 根目录。
  - `snapshot_id`: `str`，本地快照 ID。
  - `rows`: `list[dict[str, Any]]`，查询结果行。
- **输出契约**:
  - `Path`: 写入的 JSONL 文件路径。
- **错误/异常**:
  - 文件系统写入错误向上抛出。
- **调用约束**: 文件名从 `query-001.jsonl` 开始，已存在时递增编号。

#### `quote_identifier(identifier)`
- **类型**: 内部函数
- **职责**: 对 SQLite 标识符进行双引号转义。
- **输入契约**:
  - `identifier`: `str`，表名或字段名。
- **输出契约**:
  - `str`: 可用于 SQL 标识符位置的双引号转义文本。
- **错误/异常**: 无主动抛出的业务异常。
- **调用约束**: 用于 `PRAGMA table_info` 的表名转义。

### `src/mcp_db/__init__.py`
- **状态**: 已实现
- **文件职责**: Python 包初始化文件。

#### 包初始化
- **类型**: 配置
- **职责**: 标记 `mcp_db` 为 Python 包。
- **输入契约**: 无。
- **输出契约**: 无公开函数或类。
- **错误/异常**: 无。
- **调用约束**: 不承载业务逻辑。

### `scripts/start_mcp_inspector.ps1`
- **状态**: 已实现
- **文件职责**: 启动 MCP Inspector 的辅助脚本。

#### PowerShell 脚本入口
- **类型**: 配置
- **职责**: 用于本地调试 MCP server。
- **输入契约**: 由脚本内部环境和参数约定决定。
- **输出契约**: 启动 MCP Inspector 相关进程和日志。
- **错误/异常**: PowerShell 或外部命令失败时由脚本执行环境报告。
- **调用约束**: 仅用于本地调试，不属于 MCP 工具运行时业务逻辑。

## 5. 周边模块 (内部依赖)
- **依赖的模块 (Upstream)**:
  - `mcp_db.hdc_client`: 提供 HarmonyOS 设备通信、路径检查和文件拉取能力。
  - `mcp_db.snapshots`: 提供数据库快照拉取和快照元信息组装能力。
  - `mcp_db.sqlite_query`: 提供本地 SQLite 快照查询、schema 读取和结果落盘能力。
- **被依赖的模块 (Downstream)**:
  - `mcp_db.server`: 对 MCP 客户端暴露 `pull_harmony_sqlite_db` 和 `query_sqlite_db_snapshot` 两个工具。
  - `tests`: 依赖各模块的可注入边界和结构化返回验证行为。

## 6. 使用的接口 (系统/外部接口)
- **外部 API**:
  - 暂无第三方 HTTP API。
- **系统/硬件接口**:
  - `hdc`: 用于检查 HarmonyOS 设备 shell、判断远端文件是否存在、从设备拉取数据库文件。
  - 本地文件系统: 用于创建 `artifacts/db-snapshots/` 快照目录和 `artifacts/query-results/` 查询结果目录。
- **中间件/存储**:
  - SQLite 数据库文件: 使用 Python 标准库 `sqlite3` 以只读模式打开本地 `.db` 快照，并读取 schema 或执行只读 SQL。
  - JSONL 结果文件: 大结果写入 `artifacts/query-results/{snapshot_id}/query-XXX.jsonl`。
- **框架/运行时接口**:
  - FastMCP: 用于创建 MCP server 并注册工具。
  - Python 标准库: 使用 `subprocess` 执行 `hdc`，使用 `pathlib` 管理路径，使用 `json` 写入 JSONL。

## 7. 测试设计
- [x] **用例 1 (主流程)**:
  - **场景**: 设备数据库路径解析与快照拉取成功。
  - **前置条件**: 注入可控的 fake HDC client。
  - **操作步骤**: 调用 `pull_harmony_sqlite_db`，传入 `device_id`、`bundle_name`、`db_name` 和测试 artifacts 目录。
  - **预期结果**: 返回 `status: ok`、正确的 `snapshot_id`、远端路径、本地路径、已拉取文件和可选文件 warning。
  - **测试实现**: `tests/test_snapshots.py`
- [x] **用例 2 (边界值)**:
  - **场景**: 显式 `db_path` 优先于默认路径模板。
  - **前置条件**: 同时提供 `bundle_name`、`db_name` 和 `db_path`。
  - **操作步骤**: 调用 `resolve_remote_db_path`。
  - **预期结果**: 返回显式 `db_path`。
  - **测试实现**: `tests/test_snapshots.py`
- [x] **用例 3 (异常类)**:
  - **场景**: 未提供 `db_path` 时缺少 `bundle_name` 或 `db_name`。
  - **前置条件**: `db_path` 为空。
  - **操作步骤**: 调用 `resolve_remote_db_path`。
  - **预期结果**: 抛出包含 `bundle_name and db_name` 的 `ValueError`。
  - **测试实现**: `tests/test_snapshots.py`
- [x] **用例 4 (设备通信)**:
  - **场景**: HDC shell 检查、文件存在性检查、文件拉取和失败抛错。
  - **前置条件**: 注入 fake subprocess runner。
  - **操作步骤**: 调用 `HdcClient.check_shell`、`exists`、`recv` 和失败路径。
  - **预期结果**: 命令参数符合预期；失败时抛出 `HdcError` 或返回 `False`。
  - **测试实现**: `tests/test_hdc_client.py`
- [x] **用例 5 (schema 查询)**:
  - **场景**: SQL 为空时返回 SQLite schema。
  - **前置条件**: 测试目录下存在包含 `logs` 表的 SQLite 快照。
  - **操作步骤**: 调用 `query_sqlite_db_snapshot(snapshot_id, sql=None)`。
  - **预期结果**: 返回表名、字段名和字段类型。
  - **测试实现**: `tests/test_sqlite_query.py`
- [x] **用例 6 (只读查询)**:
  - **场景**: 执行合法 `SELECT` 查询。
  - **前置条件**: 测试 SQLite 快照存在并包含数据。
  - **操作步骤**: 调用 `query_sqlite_db_snapshot` 并传入 `SELECT id, name FROM logs ORDER BY id`。
  - **预期结果**: 返回列名、行数据和 `row_count`。
  - **测试实现**: `tests/test_sqlite_query.py`
- [x] **用例 7 (安全类)**:
  - **场景**: 拒绝写入 SQL。
  - **前置条件**: 输入 `DELETE FROM logs`。
  - **操作步骤**: 调用 `validate_readonly_sql`。
  - **预期结果**: 抛出只允许只读 SQL 的 `ValueError`。
  - **测试实现**: `tests/test_sqlite_query.py`
- [x] **用例 8 (大结果)**:
  - **场景**: 查询结果超过内联阈值。
  - **前置条件**: 将 `inline_row_threshold` 设置为小于结果行数。
  - **操作步骤**: 调用 `query_sqlite_db_snapshot`。
  - **预期结果**: 返回 `result_file`、`preview_rows`，并写入 JSONL 文件。
  - **测试实现**: `tests/test_sqlite_query.py`
- [x] **用例 9 (MCP 工具入口)**:
  - **场景**: MCP 工具入口归一化空字符串参数，并保留 Inspector 友好的字符串注解。
  - **前置条件**: monkeypatch 底层快照和查询函数。
  - **操作步骤**: 调用 `server.pull_harmony_sqlite_db` 和 `server.query_sqlite_db_snapshot`。
  - **预期结果**: 可选空字符串转为 `None`，类型注解保持普通字符串参数。
  - **测试实现**: `tests/test_server_arguments.py`
- [x] **用例 10 (工具说明文档)**:
  - **场景**: MCP 工具 docstring 说明快照流程、schema、只读 SQL 和结果文件。
  - **前置条件**: 导入 MCP 工具函数。
  - **操作步骤**: 读取工具函数 `__doc__`。
  - **预期结果**: docstring 包含关键使用说明。
  - **测试实现**: `tests/test_server_tool_docs.py`

## 8. 变更日志
| 版本 | 日期 | 修改人 | 变更内容简述 |
|---|---|---|---|
| 1.0.0 | 2026-05-20 | Codex | 初始化模块设计，按已实现源码和测试补充文件职责、业务流和测试设计 |
