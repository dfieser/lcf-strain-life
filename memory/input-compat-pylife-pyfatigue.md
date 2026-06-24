---
name: input-compat-pylife-pyfatigue
description: Make LCF tool input-compatible with pyLife and py-fatigue data shapes
metadata:
  type: reference
---

The LCF tool should be input-compatible with the two established Python fatigue libraries so users can drop data in with minimal reshaping:
- **pyLife** (Bosch, https://pylife.readthedocs.io) — pandas Series/DataFrame with registered "signal accessors". LoadCollective columns `from`/`to` (or `range`/`mean`); `.load_collective` accessor derives `amplitude`, `meanstress`, `R`, `cycles`. WoehlerCurve = Series with `k_1`, `ND`, `SD` (+ `k_2`, `TN`, `TS`).
- **py-fatigue** (OWI-Lab, https://owi-lab.github.io/py_fatigue/) — `CycleCount.from_timeseries(time, data, mean_bin_width, range_bin_width, name, timestamp)` runs ASTM E1049-85 rainflow; `from_rainflow(dict)` rebuilds from binned matrix. Units typically MPa.

Decisions captured in docs/design/WORKFLOW.md: use pandas core container, a `from_timeseries(time, data,...)` constructor, reuse their loop column vocabulary, attach name/units(MPa)/timestamp metadata, accept pre-counted input.

**Key boundary:** both are stress-based high-cycle/durability tools (rainflow → S-N → Miner) and their rainflow step DISCARDS cycle order. Our strain-controlled LCF needs per-cycle evolution (peak/valley vs cycle, half-life, N_f) and strain-life fits (Coffin-Manson/Basquin/Ramberg-Osgood) that neither library provides — that is our differentiator. See [[project-scope-lcf-automation]] and [[use-true-stress-strain]].
