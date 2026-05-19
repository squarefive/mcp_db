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

## Project Rules Index

The project follows four local rules adapted from `multica-ai/andrej-karpathy-skills`.

- [项目规则](docs/project-rules.md)

## Current Status

Initialized with project guidance only. No implementation files have been created yet.
