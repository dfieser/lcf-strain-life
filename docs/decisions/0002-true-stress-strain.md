# ADR-0002: Use true stress / true strain throughout

**Status:** Accepted · **Date:** 2026-06-24

## Context
Raw LCF data from test machines is usually **engineering** stress/strain. LCF involves large
plastic strains where engineering and true values diverge meaningfully.

## Decision
- All internal computation uses **true stress (σ)** and **true strain (ε)**.
- Convert at ingestion: `ε_true = ln(1 + ε_eng)`, `σ_true = σ_eng·(1 + ε_eng)`, with
  `σ_eng = F / A`.
- The conversion is valid up to necking. For cyclic per-loop data it is applied per sample.
- Units: stress in **MPa**, strain dimensionless, E in MPa. `b`, `c` are **negative**.

## Consequences
- A single normalization step owns the eng-to-true conversion. Everything downstream assumes true.
- Inputs that are already true must be flagged so we don't double-convert.

## Source
Deep-research reference §1 (units/sign), §10 (eng vs true). ISO 12106 §3.3.
Project rule: `memory/use-true-stress-strain.md`.
