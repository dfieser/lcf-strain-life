# ADR-0010: Phase 2 engineering layer and method defaults

**Status:** Accepted · **Date:** 2026-06-24

## Context
Phase 2 extends the material-level strain-life core toward component life:
variable-amplitude loading, cumulative damage, notch local-strain, statistics
and design curves, and elevated-temperature creep-fatigue. The methods come from
the Phase 2 research reference in `docs/design`.

## Decision
New modules, each reusing the Phase 1 fits, life inversion, mean-stress, and
metrics rather than reimplementing them: `counting`, `damage`, `notch`, `stats`,
`hightemp`, `multiaxial`, and `spectrum`. Recommended defaults:

- Cumulative damage: Palmgren-Miner with a critical sum of 1.0. Switch to the
  Double Linear Damage Rule for strong sequence effects, or 0.5 for out-of-phase
  code work.
- Notch rule: Neuber by default, conservative. Glinka is available when Neuber
  is too conservative and the plastic zone is small.
- Mean stress for variable amplitude: SWT by default, no extra constant needed.
  Morrow and Walker are available.
- Design curve: the standard one-sided Owen tolerance factor for the chosen
  reliability and confidence, applied as mean minus k times s.
- Creep-fatigue: linear time-fraction summation with a bilinear D-diagram
  envelope.
- Multiaxial is a survey-only stub. The critical-plane parameters and a plane
  search exist, the tensor engine is deferred to Phase 3.

Every finished capability is exposed as an MCP tool. The multiaxial stub is not,
because it is not a finished capability.

## Consequences
Phase 1 behavior is unchanged. New optional metadata fields, temperature, Kt,
Kf, frequency, hold time, default to None. No heavy new dependencies were added,
rainflow and the statistics are implemented in-house on numpy and scipy.

## Source
Phase 2 research reference, `docs/design/IMPLEMENTATION_REFERENCE_PHASE2.md`,
sections 1 through 8.
