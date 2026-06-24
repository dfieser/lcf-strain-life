# ADR-0008: MCP — official `mcp` SDK (FastMCP), pinned `>=1.27,<2`

**Status:** Accepted · **Date:** 2026-06-24

## Context
The agent-facing surface is an MCP server. The official Python SDK is mid-transition: v1.x is in
maintenance, v2 is in alpha (stable targeted 2026-07-27).

## Decision
- Depend on the **official `mcp` SDK**, pinned **`>=1.27,<2`** (avoids the in-flux v2 alpha;
  current installed: 1.28.0).
- Use the **bundled FastMCP** decorator API (`mcp.server.fastmcp.FastMCP`) — no extra dependency.
- **Transport:** `stdio` for local Claude Code / Claude Desktop use (Streamable HTTP is the
  remote option if needed later).
- **Large arrays:** never pass thousands of samples as inline JSON; use **file paths / Parquet**
  or split `content` (compact summary to the model) vs `structuredContent` (full payload).
- **compute/save/recall:** compute tools save to the store; recall tools and **MCP resources**
  (`lcf://results/{test_id}`) read back. Resources behave like read-only GET endpoints.
- Tools are narrow and clearly named; inputs validated with pydantic; errors returned as clear
  text. Tested locally with the MCP Inspector (`mcp dev`).

## Consequences
- Stable build target now; clean upgrade path when v2 stabilizes (revisit in a new ADR).

## Source
Deep-research reference §4, §12 (all version-stamped, accessed 2026-06-24).
