# LCF Analysis Workflow

How data moves through the tool, from a scientist's raw test file to saved, recallable results.
This organizes *what happens, in what order, and what gets stored*. The math for each step lives in
[../reference/Equations_and_Labels.md](../reference/Equations_and_Labels.md) and
[../reference/LCF_Analysis_Notes.md](../reference/LCF_Analysis_Notes.md).

---

## Inputs

**Raw data**: a table (xy / time-series) for one test, typically with columns:

| Column | Symbol | Notes |
|---|---|---|
| time | t | sampling timeline |
| strain | ε_eng | engineering strain (most common raw form) |
| force | F | load cell reading |

**Known parameters**: scalars supplied with the test:

| Parameter | Symbol | Typical |
|---|---|---|
| cross-sectional area | A | required (to get stress from force) |
| Young's modulus | E | given, or fit from elastic slope |
| gauge length | L₀ | optional |
| strain ratio | R | usually -1 (fully reversed) |

> Raw data is assumed **engineering** stress/strain and is converted to **true** at ingestion.

---

## Input compatibility (pyLife / py-fatigue)

We want users coming from the established Python fatigue ecosystem to drop their data in with
minimal reshaping. Conventions to mirror:

- **pandas as the core container.** Both [pyLife](https://pylife.readthedocs.io) and
  [py-fatigue](https://owi-lab.github.io/py_fatigue/) standardize on `pandas.Series`/`DataFrame`.
  We do too.
- **A `from_timeseries(time, data, …)`-style constructor**, matching py-fatigue's
  `CycleCount.from_timeseries(time, data, name, timestamp, …)`. We accept `(time, strain, force)`
  columns, they accept `(time, signal)`.
- **Reuse their hysteresis-loop column vocabulary** so a load collective drops in:
  `from` / `to` (or `range` / `mean`), with derived `amplitude`, `mean`/`meanstress`, `R`,
  `cycles` (pyLife `.load_collective` accessor names).
- **Metadata on each dataset**: `name`, `units` (default **MPa**, the field convention in both
  tools), `timestamp`.
- **Also accept pre-counted input** (a `from_collective` / `from_rainflow` path) for users arriving
  from those tools.

**Important difference, why we can't just reuse them.** pyLife and py-fatigue are *stress-based,
high-cycle/durability* tools: irregular load → ASTM E1049-85 rainflow → load **collective/histogram**
→ S-N curve → Miner damage. Rainflow **collapses the signal into a histogram and discards cycle
order.** Our strain-controlled LCF analysis needs the opposite, namely *per-cycle evolution* (peak/valley
stress vs. cycle, hardening/softening, half-life loop, N_f). So we adopt their **input shapes** but
keep an **ordered per-cycle table** as our primary internal form, and we add the strain-life fits
(Coffin-Manson / Basquin / Ramberg-Osgood) neither library provides.

---

## The flow

```
 raw table (t, ε_eng, F)  +  params (A, E, ...)
        │
        ▼
 [1] INGEST & NORMALIZE
     • stress      σ_eng = F / A
     • eng → true  ε = ln(1+ε_eng),  σ = σ_eng·(1+ε_eng)
        │
        ▼
 [2] CYCLE REDUCTION
     • detect cycles from the strain waveform
     • per cycle: peak (max) stress, valley (min) stress, peak/valley strain
     • count cycles; identify half-life cycle; determine N_f (failure)
        │
        ▼
 [3] PER-CYCLE METRICS
     • stress amplitude Δσ/2, plastic strain amplitude Δε_p/2
     • mean stress σ_m, T/C ratio R_TC
     • cyclic energy density W (loop area)
        │
        ▼
 [4] MULTI-TEST FITS  (needs ≥2–3 strain amplitudes)
     • Coffin-Manson (ε'_f, c)   • Basquin (σ'_f, b)
     • Ramberg-Osgood (K', n')   • Morrow mean-stress correction
        │
        ▼
 [5] SAVE RESULTS  →  recall later without recomputing
```

---

## Stages

### 1. Ingest & normalize
Turn the raw table into clean true stress-strain.
- `stress = force / area`
- engineering → true: `ε = ln(1+ε_eng)`, `σ = σ_eng·(1+ε_eng)`
- Store the normalized true σ-ε-t series as the dataset for this test.

### 2. Cycle reduction
Segment the continuous series into individual cycles and pull out the headline numbers.
- **Number of cycles**: count strain reversals.
- **Peak stress / valley stress**: max (tension) and min (compression) per cycle.
- **Half-life cycle**: the cycle at N_f/2, used as the "stable" representative loop.
- **N_f (cycles to failure)**: from a failure criterion (e.g. load/stress drop below a threshold of the stabilized value).

These are the quantities a user most often wants to recall directly.

### 3. Per-cycle metrics
Derived from the reduced cycles (see equations doc for formulas):
- stress amplitude `Δσ/2`, plastic strain amplitude `Δε_p/2`
- mean stress `σ_m = (σ_max+σ_min)/2`, tension/compression ratio `R_TC`
- cyclic energy density `W` (hysteresis loop area), reported at peak-hardened and half-life

### 4. Multi-test fits
Run once several tests at different strain amplitudes exist:
- **Coffin-Manson** → `ε'_f, c` · **Basquin** → `σ'_f, b`
- **Ramberg-Osgood** → `K', n'` · **Morrow** mean-stress correction
- Consistency checks (`n' ≈ b/c`, etc.) flag bad fits.

---

## Compute, save, recall

This is the core interaction model from the working notes:

- **Machine agents compute** each quantity with a dedicated function (per the
  [pipeline → tool mapping](../reference/LCF_Analysis_Notes.md#10-pipeline-tool-mapping)).
- **Results are saved** keyed to the test, so they don't have to be recomputed.
- **Users / agents recall** saved quantities on demand, e.g.:
  - "number of cycles for test A"
  - "peak stress vs cycle for test A"
  - "valley stress at half-life"
  - "fitted Coffin-Manson parameters for this material"

```
compute_*  →  writes result to store (keyed by test + quantity)
recall_*   →  reads result back (recompute only if missing/stale)
```

The persistence/recall layer (storage format, identifiers, caching/invalidation) and the concrete
MCP tool surface are **still to be designed**. See open questions below.

---

## Open questions (to design next)

- **Failure criterion** for N_f: fixed load-drop %, or user-supplied?
- **Cycle detection**: rely on the controlled strain waveform (reversal counting) or a general
  rainflow method for irregular data?
- **Storage backend**: where/how saved results live (per-test files vs a small database).
- **Identifiers**: how tests/datasets/materials are named and grouped for recall.
- **Result invalidation**: when inputs or parameters change, which cached results recompute.
