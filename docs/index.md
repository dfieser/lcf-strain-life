# lcf-strain-life

An AI-agent-native toolkit for low cycle fatigue strain-life analysis. A
Python library and an MCP server that take strain-controlled fatigue test
data, reduce it cycle by cycle, fit the standard models, predict life, and
persist every result for recall. Every capability is callable by a human or
by an AI agent through the same service layer.

- [Install](installation.md), then walk the [usage examples](usage.md) or
  the [SAE 1137 tutorial](tutorials/sae1137.md), which reproduces a
  published dataset end to end.
- [PyPI package](https://pypi.org/project/lcf-strain-life/), source on
  [GitHub](https://github.com/dfieser/lcf-strain-life), archived releases
  with DOI
  [10.5281/zenodo.21222820](https://doi.org/10.5281/zenodo.21222820).

## What it covers

| Area | Capability |
|---|---|
| Ingestion | Machine CSV and lab exports, batch series, engineering to true conversion |
| Cycle reduction | Turning points, per-cycle metrics, hysteresis energy, half-life reduction |
| Strain-life | Basquin, Coffin-Manson, Ramberg-Osgood fits, transition life, Masing check |
| Mean stress | Morrow, modified Morrow, SWT, Walker |
| Variable amplitude | ASTM E1049 rainflow with preserved indices, local-strain simulation with material memory |
| Cumulative damage | Palmgren-Miner, Double Linear Damage Rule, Corten-Dolan |
| Notch | Neuber and Glinka local strain, Kt, Kf, notch sensitivity |
| Statistics | E739-style regression, confidence and prediction intervals, Owen design curves, censored maximum likelihood with lognormal or Weibull scatter, profile-likelihood design bounds, outlier screening, staircase, random fatigue limit |
| Elevated temperature | Frequency-modified Coffin-Manson, time-fraction creep-fatigue, D-diagram |
| Cyclic evolution | Mean stress relaxation and ratcheting power laws |
| Multiaxial | Critical-plane parameters and tensor plane search |
| Interchange | Versioned open formats for constants, test records, and collections, with JSON Schemas |
| Interfaces | Python library, 41 MCP tools, no-code Streamlit GUI |

## The open data effort

The toolkit defines and validates open [interchange formats](INTERCHANGE.md)
for strain-life data, ships a citable [seed collection](data.md), and
accepts [contributions](CONTRIBUTING-DATA.md). The goal is a FAIR,
redistributable strain-life dataset with per-cycle evolution, something no
open fatigue database currently provides.

## Statistics after E739

ASTM E739 was withdrawn in 2024. Alongside the classical linearized methods
the toolkit implements the maximum-likelihood layer its replacement effort
points to: censored fits that keep runouts, uncertainty on every estimate,
and profile-likelihood design bounds. The [statistics page](statistics.md)
explains what changed and why it matters.

## Conventions, fixed

True stress and true strain everywhere. Stress in MPa, strain as a
dimensionless fraction, life in reversals, exponents b and c negative.
Every method traces to a citable source, see the
[physics review](PHYSICS_REVIEW.md) and the `get_citations` tool.

## Honesty policy

Documentation never claims a capability the code lacks, results carry
machine-readable warnings, unvalidated paths are labeled, and every equation
and dataset cites its source. When something is approximate, the output says
so.
