# AGENTS.md

## Project Overview

This project implements an MCP tool for pulling database files from HarmonyOS devices and analyzing the data according to user-supplied conditions.

The project is currently in initialization only. Do not implement runtime code, command wrappers, database analysis logic, or tests until the user explicitly asks for implementation.

## Preferred Implementation Route

Use the following stack when implementation begins:

- Python
- FastMCP
- sqlite3 from the Python standard library
- HarmonyOS `hdc` for device communication and database file transfer

## Intended Capabilities

The future MCP server should support:

- Pulling database files from a HarmonyOS device.
- Opening local SQLite database files.
- Inspecting database tables and schemas.
- Running condition-based analysis over database records.
- Returning structured analysis results to MCP clients.

## Development Guidelines

- Keep the project focused on MCP tooling for HarmonyOS database retrieval and analysis.
- Prefer small, testable Python modules with clear boundaries.
- Keep device communication, database access, and MCP tool definitions separated.
- Use `sqlite3` unless there is a confirmed need for another database library.
- Treat `hdc` availability, connected devices, missing files, invalid SQL inputs, and unreadable databases as expected error cases.
- Avoid broad refactors or extra framework setup unless they directly support the requested task.

## Documentation-First Design Rule

Any change that affects module behavior, public tool contracts, file responsibilities, data flow, system interfaces, or test acceptance expectations must update the relevant module design document before implementation code is changed.

The design document update must be committed first as a standalone Git commit. After that documentation commit exists, implementation changes may proceed in a separate commit.

This rule applies to:

- New MCP tools or changed tool parameters.
- Changes to return structures or error semantics.
- Changes to device communication, snapshot storage, SQLite query behavior, or result persistence.
- Changes that add, remove, split, or repurpose module files.
- Changes that alter required test coverage or acceptance behavior.

This rule does not apply to:

- Typo fixes.
- Formatting-only changes.
- Comments that do not change behavior.
- Test-only maintenance that does not change expected behavior.
- Fixes that only bring implementation back into alignment with an already accurate design document.

When the design and code disagree, treat the module design document as the source of intended behavior. Either update and commit the design first, or explicitly state that the code fix is restoring conformance to the existing design.

## Project Rules Index

The project follows four local rules adapted from `multica-ai/andrej-karpathy-skills`.

- [项目规则](docs/ai-development-paradigms/project-rules.md)

## AI Development Paradigms Index

All documents that define conventions for AI-assisted development paradigms must be stored under `docs/ai-development-paradigms/`.

- [核心开发范式 (Core Development Paradigms)](docs/ai-development-paradigms/core-development-paradigms.md)
- [项目规则](docs/ai-development-paradigms/project-rules.md)

## Module Design Index

Module design documents and templates are stored under `docs/module-design/`.

- [模块设计文档模板](docs/module-design/module-design.template.md)
- [HarmonyOS SQLite MCP 工具设计文档](docs/module-design/mcp-db-server-design.md)

## Current Status

The first MCP tool implementation exists under `src/mcp_db/`, with tests under `tests/`. Future changes should keep implementation aligned with the module design document.
