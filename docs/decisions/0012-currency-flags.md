# ADR-0012: Currency flags to re-check after 2026-06-24

**Status:** Accepted · **Date:** 2026-06-24

## Context
Several standards and libraries were in flux at the time of the Phase 2 research.
Recording them here so a future session knows what to re-verify.

## Decision
Keep the current choices and re-check the following items after the dates shown.

- MCP Python SDK. Stay on v1.x pinned `mcp>=1.27,<2`. v2 was in alpha with a
  stable target of 2026-07-27 and a breaking spec release candidate on
  2026-07-28. v2 replaces the FastMCP class with a new McpServer class. After
  2026-07-27, evaluate v2 on a migration branch and revisit the pin.
- ASTM E739 (statistics) was withdrawn in 2024 with no replacement. A reapproval
  work item WK83149 exists. We use the withdrawn linearized method as the de
  facto reference. Re-check whether WK83149 reapproves it.
- ASTM E2714 (creep-fatigue) is current with a revision work item WK97543 in
  progress. Re-check on the next revision.
- Scientific stack. We target numpy 2.x, scipy 1.16 or newer, pandas 3.0. These
  are newer than typical pins. Keep testing under them, the pandas 3.0
  copy-on-write and string-dtype changes are the main risk.

## Consequences
No code change now. This is a maintenance checklist. Phase 1 ADR-0008 already
records the MCP pin decision, this ADR adds the standards and stack items.

## Source
Phase 2 research reference sections 3.1, 4.2, 6.3, 6.4, and 8.4.
