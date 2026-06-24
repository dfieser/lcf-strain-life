# Architecture Decision Records (ADRs)

This is the project's **decision log**. Each ADR records one significant decision: its context,
the choice made, the consequences, and the source/rationale. ADRs are immutable once accepted;
to change a decision, add a new ADR that supersedes the old one.

Format: lightweight [MADR](https://adr.github.io/madr/)-style.

| # | Title | Status |
|---|---|---|
| [0001](0001-package-architecture.md) | Package architecture: single package, src layout, library + MCP server | Accepted |
| [0002](0002-true-stress-strain.md) | Use true stress/strain throughout | Accepted |
| [0003](0003-cycle-detection.md) | Cycle detection: peak-valley + index-preserving rainflow | Accepted |
| [0004](0004-failure-criterion.md) | Failure criterion: configurable % load-drop (default 30%) | Accepted |
| [0005](0005-fitting-methodology.md) | Fitting: per-branch log-log fit, independent K′/n′, flag non-Masing | Accepted |
| [0006](0006-mean-stress-correction.md) | Mean-stress correction default: SWT | Accepted |
| [0007](0007-persistence.md) | Persistence: SQLite catalog + Parquet + PNG + SHA-256 cache | Accepted |
| [0008](0008-mcp-sdk.md) | MCP: official `mcp` SDK (FastMCP), pinned `>=1.27,<2` | Accepted |
| [0009](0009-review-hardening.md) | Robustness hardening from the critical review | Accepted |

All decisions derive from the [deep-research implementation reference](../design/IMPLEMENTATION_REFERENCE.md)
(Section 12) and the scoping docs in `docs/`.
