# ADR-0007: Persistence: SQLite catalog + Parquet + PNG + SHA-256 cache

**Status:** Accepted · **Date:** 2026-06-24

## Context
The interaction model is **compute, save, recall**: results must be persisted per test/material
and recalled without recomputation, and recomputed only when inputs/parameters change.

## Decision
- **SQLite catalog**: one row per (test/material, quantity) holding scalars, fitted constants
  (JSON column), an **input hash**, and **paths** to large artifacts.
- **Parquet** for large per-cycle tables (referenced by path from SQLite).
- **PNG** plot artifacts on disk. Paths are referenced from SQLite, and images are never blobbed into the DB.
- **Cache invalidation:** a **SHA-256** content hash over raw input bytes plus analysis parameters
  (failure-criterion %, mean-stress model, fit options). Recompute only when the hash changes
  (content-addressed cache).
- The store lives under a configurable directory (default a project-local `.lcfstore/`).

## Consequences
- Deterministic save/recall. Stale results impossible when inputs/params change.
- Keyed recall of common quantities, for example "peak stress vs cycle for test A" or "Coffin-Manson params".

## Source
Deep-research reference §8, §12. `docs/design/WORKFLOW.md` (compute/save/recall).
