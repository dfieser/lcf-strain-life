# ADR-0006: Mean-stress correction default: SWT

**Status:** Accepted · **Date:** 2026-06-24

## Context
Nonzero mean stress (e.g. from tension/compression asymmetry) shifts fatigue life. Several
corrections exist: Morrow, modified Morrow, Smith-Watson-Topper (SWT), and Walker.

## Decision
- **Default: SWT**, a parameter-free, robust general choice.
- Also provide **Morrow** and **modified Morrow**, used when a reliable σ′f / true fracture
  strength is available, and **Walker**, most accurate when multi-R data exist.
- **Walker exponent γ:** fit from multi-R data when available. `γ = 0.5` recovers SWT exactly.
  For steels with no multi-R data, estimate `γ ≈ 0.8818 − 2.00×10⁻⁴·σ_u` (Dowling et al. 2009).
  For 2000/7000-series aluminium, `γ ≈ 0.5`, which is approximately SWT.
- Caution surfaced in output: Morrow is unreliable for aluminium unless true fracture strength
  is used (Dowling et al. 2009). The Goodman relation is not offered.

## Consequences
- Sensible default with no extra inputs. More accurate options available when data supports them.

## Source
Deep-research reference §2 (mean-stress forms, γ), §12.
