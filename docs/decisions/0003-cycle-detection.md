# ADR-0003: Cycle detection — peak-valley for constant amplitude, index-preserving rainflow for irregular

**Status:** Accepted · **Date:** 2026-06-24

## Context
We must segment a continuous `(t, ε, σ)` stream into individual cycles **while preserving cycle
order**, because per-cycle evolution (hardening/softening, peak/valley drift, energy per cycle)
is the tool's differentiator. Standard rainflow (ASTM E1049-85) collapses the signal into a
histogram and **discards order**, so it cannot be used as-is.

## Decision
- **Constant-amplitude, fully-reversed** strain control (the common LCF case): segment by
  **peak-valley (turning-point) detection** on the strain/command waveform. Each
  peak→valley→peak defines one closed loop; order is preserved trivially.
- **Irregular / variable-amplitude** histories: use **index-preserving rainflow** — an
  implementation that reports original sample indices (pyLife `FullRecorder`, or
  `rainflow.extract_cycles` with `i_start`/`i_end`) — then re-order loops in time and compute
  per-cycle metrics.
- v0.1 implements the constant-amplitude path; the rainflow path is a documented extension point.

## Consequences
- Clean separation: detection produces an **ordered per-cycle table**, our primary internal form.
- Reuses the established rainflow engines rather than reimplementing E1049.

## Source
Deep-research reference §3, §5. `docs/design/WORKFLOW.md` open questions.
