# ADR-0005: Fitting methodology: per-branch log-log fit, independent K′/n′, flag non-Masing

**Status:** Accepted · **Date:** 2026-06-24

## Context
The strain-life constants (σ′f, b, ε′f, c) and cyclic stress-strain constants (K′, n′) must be
fit from multi-amplitude data. ASTM E739, the linearized practice, was **withdrawn Jan 2024**
without replacement, but its per-branch linear regression remains standard engineering practice.
Real materials may be **non-Masing**, so the compatibility relations (`n′ = b/c`,
`K′ = σ′f/(ε′f)^(b/c)`) do not always hold.

## Decision
- **Primary fit:** per-branch **log-log linear least-squares**:
  - Basquin: `log(Δσ/2)` vs `log(2N_f)` → b (slope), σ′f (from intercept).
  - Coffin-Manson: `log(Δε_p/2)` vs `log(2N_f)` → c (slope), ε′f (from intercept).
  - Ramberg-Osgood: `log(Δσ/2)` vs `log(Δε_p/2)` → n′ (slope), K′ (from intercept).
- **Optional refinement:** nonlinear least squares on the combined total-strain curve
  (`scipy.optimize.curve_fit`) seeded by the linear-fit constants.
- **K′ and n′ are fit independently** from stabilized cyclic data. The b/c-derived values are
  **also computed** and **divergence is flagged** (non-Masing). Compatibility is never silently
  forced.
- Report per-branch **R²** and coefficient standard errors. Honor E739 cautions: no
  extrapolation beyond the tested interval, and do not estimate below the ~5th percentile.
- Cite E739 as **withdrawn-but-widely-used**, not as a current standard.

## Consequences
- Robust, transparent constants with goodness-of-fit. Non-Masing behavior surfaced, not hidden.

## Source
Deep-research reference §2 (fitting, Masing), §6 (log-transform bias), §12.
