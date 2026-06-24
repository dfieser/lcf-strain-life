---
name: input-compat-pylife-pyfatigue
description: Make LCF tool input-compatible with pyLife and py-fatigue data shapes
metadata:
  type: reference
---

The LCF tool should be input-compatible with the two established Python fatigue libraries so users can drop data in with minimal reshaping.

- **pyLife** by Bosch, https://pylife.readthedocs.io. Uses pandas Series and DataFrame with registered signal accessors. LoadCollective columns are `from`/`to` or `range`/`mean`. The `.load_collective` accessor derives `amplitude`, `meanstress`, `R`, and `cycles`. WoehlerCurve is a Series with `k_1`, `ND`, `SD`, and optionally `k_2`, `TN`, `TS`.
- **py-fatigue** by OWI-Lab, https://owi-lab.github.io/py_fatigue/. `CycleCount.from_timeseries(time, data, mean_bin_width, range_bin_width, name, timestamp)` runs ASTM E1049-85 rainflow. `from_rainflow(dict)` rebuilds from a binned matrix. Units are typically MPa.

Decisions captured in docs/design/WORKFLOW.md: use a pandas core container, a `from_timeseries(time, data, ...)` constructor, reuse their loop column vocabulary, attach name, units, and timestamp metadata with units defaulting to MPa, and accept pre-counted input.

**Key boundary:** both are stress-based high-cycle durability tools, rainflow then S-N then Miner, and their rainflow step discards cycle order. Our strain-controlled LCF needs per-cycle evolution, meaning peak and valley versus cycle, half-life, and N_f, plus the strain-life fits Coffin-Manson, Basquin, and Ramberg-Osgood that neither library provides. That is our differentiator. See [[project-scope-lcf-automation]] and [[use-true-stress-strain]].
