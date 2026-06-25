# ADR-0011: In-house index-preserving rainflow counting

**Status:** Accepted · **Date:** 2026-06-24

## Context
Variable-amplitude analysis needs ASTM E1049 rainflow counting. The research
recommended the `rainflow` PyPI package, which preserves cycle indices. We must
choose between depending on it and implementing the counter in-house.

## Decision
Implement the three-point algorithm in-house in `lcf.counting`. It preserves the
original sample indices of every counted cycle, which is what lets the rest of
the toolkit recover per-cycle stress and strain evolution rather than a
histogram. Reasons: no external dependency, full control over index handling,
and the counter is small and fully validated.

## Consequences
The counter is validated against the ASTM E1049 worked example, the Golden A and
B fixtures, reproducing the cycles, means, counts, and binned totals exactly. A
repeat-history closure rotates the reversal sequence to the global maximum, a
standard treatment, available behind a flag. Input is rejected if it contains
NaN or infinity.

## Source
Phase 2 research reference section 1, ASTM E1049-85(2017).
