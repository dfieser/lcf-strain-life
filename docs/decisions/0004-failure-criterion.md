# ADR-0004: Failure criterion — configurable % load-drop (default 30%)

**Status:** Accepted · **Date:** 2026-06-24

## Context
`N_f` (cycles to failure) depends on a chosen failure criterion. Neither ASTM E606 nor
ISO 12106 mandates a single value — both require the criterion be **chosen and reported**.

## Decision
- Default failure criterion: a **percent load-drop from the stabilized (half-life) peak tensile
  load**, **configurable**, defaulting to **30%** (matching the SAE 1137 golden dataset used for
  validation; published programs span ~10–50%).
- The chosen criterion is **always persisted and reported** with results.
- Alternative criteria (modulus-drop, specimen separation) are out of scope for v0.1 but the
  API keeps the criterion pluggable.

## Consequences
- Reproducible `N_f`: a result is only meaningful alongside its recorded criterion.
- The 30% default lets validation tests reproduce published `2N_f` values.

## Source
Deep-research reference §1 (failure criterion), §11 (SAE 1137, 30% load drop), §12.
