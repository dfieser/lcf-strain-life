# ADR-0001: Package architecture: single package, src layout, library + MCP server

**Status:** Accepted · **Date:** 2026-06-24

## Context
The project ships two things: a reusable scientific **library**, the analysis, and an **MCP
server** that exposes it to AI agents. We must decide how to package them.

## Decision
- **One installable distribution** `lcf-strain-life`, import package **`lcf`**, using the
  **`src/` layout** (`src/lcf/`).
- The MCP server lives **inside** the same package (`lcf.mcp_server`) and is an optional concern.
  MCP is an **optional dependency** (`pip install lcf-strain-life[mcp]`) so the library can be
  used with no MCP dependency at all.
- A console-script entry point `lcf-mcp` and a `python -m lcf` entry both launch the server.
- Build backend: **hatchling**.

## Consequences
- The science is usable standalone (import `lcf`) in notebooks/pipelines without MCP.
- A single version, test suite, and CHANGELOG cover both surfaces.
- `requires-python >= 3.11`, driven by NumPy ≥ 2.x.

## Source
Deep-research reference §4 (packaging), §12 (MCP). Project scope: `docs/design/WORKFLOW.md`.
