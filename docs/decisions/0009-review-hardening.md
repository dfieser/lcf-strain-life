# ADR-0009: Robustness hardening from the critical review

**Status:** Accepted · **Date:** 2026-06-24

## Context
After the initial build (114 tests green, golden-validated), a three-part critical
review was run: web-verification of the physics, web-verification of API currency,
and an adversarial code audit. The physics (13/13 formulas) and API usage were
confirmed correct; the code audit surfaced robustness gaps where functions returned
`inf`/`complex`/invalid-JSON or silently-wrong values instead of failing clearly.

## Decision
Adopt **fail-loud, valid-output** behavior across the boundary functions:

- **Valid JSON always.** `store.to_jsonable` maps non-finite floats (NaN/Inf) to
  `null` and all `json.dumps` use `allow_nan=False`. Rationale: a 2-point regression
  legitimately yields NaN standard errors; bare `NaN` tokens are invalid JSON and
  break strict MCP clients.
- **Noise-aware cycle detection.** `find_turning_points` gains an amplitude gate;
  `reduce_cycles` applies a 2%-of-range default and warns on implausibly dense
  reversals.
- **Robust failure criterion.** The stabilized reference is the max (cyclically
  hardened) peak, searched only after that cycle; non-positive references are rejected.
- **Guarded formulas.** Morrow / modified-Morrow raise when `σ_m ≥ σ'_f`;
  `transition_reversals` requires positive `σ'_f, ε'_f, E`; Basquin life-inverse
  validates positive inputs; life inversion asserts a decreasing curve (`b, c < 0`);
  `check_consistency` degrades to `masing_ok=False` (no raise) when undefined.
- **Input validation.** Ingestion rejects NaN rows and warns on non-monotonic time
  (toggle via `validate=`).
- **Store integrity & concurrency.** Injective Parquet filenames (hash suffix);
  SQLite `WAL` + `busy_timeout`.
- **Precision.** Walker steel-γ intercept corrected to the primary-source value
  `0.8818` (Dowling 2009 / 4th ed. Eq. 9.20).

## Consequences
- Bad inputs/degenerate fits now produce clear `ValueError`s or documented `NaN→null`,
  never silent wrong numbers or client-breaking output.
- +21 regression tests encode each fixed failure mode (135 total, all passing).

## Source
Critical-review findings (physics/API/code audits), 2026-06-24. Supersedes nothing;
hardens decisions in ADR-0003, ADR-0004, ADR-0005, ADR-0006, ADR-0007.
