# lcf-strain-life documentation

An AI-agent-native toolkit for fatigue analysis of materials. A Python library
and an MCP server that take strain-controlled fatigue test data, reduce it,
fit the standard models, and predict life, all callable by AI agents.

## Pages

- [Installation](installation.md): set up the library and the MCP server.
- [Usage](usage.md): worked examples for every capability, library and MCP.
- [Theory](theory.md): the fatigue methods and where each is defined.
- [API reference](api.md): the public functions, grouped by module.
- [Agent usage guide](AGENT_USAGE.md): how an AI agent drives the MCP tools.

## Reference and design

- [Equations and labels](reference/Equations_and_Labels.md)
- [Analysis notes](reference/LCF_Analysis_Notes.md)
- [Workflow](design/WORKFLOW.md)
- [Decision records](decisions/README.md)

## What it covers

| Area | Capability |
|---|---|
| Strain-life | Basquin, Coffin-Manson, Ramberg-Osgood fits, transition life |
| Mean stress | Morrow, modified Morrow, SWT, Walker |
| Variable amplitude | ASTM E1049 rainflow with preserved indices, spectrum life |
| Cumulative damage | Palmgren-Miner, Double Linear Damage Rule, Corten-Dolan |
| Notch | Neuber and Glinka local-strain, Kt, Kf, notch sensitivity |
| Statistics | E739 regression, confidence and prediction intervals, R-C design curves, censored fits |
| Elevated temperature | frequency-modified Coffin-Manson, time-fraction creep-fatigue, D-diagram |
| Multiaxial | critical-plane parameters, survey only |

## Conventions

All analysis uses true stress and true strain. Stress is in MPa, strain is a
dimensionless fraction, and the fatigue exponents b and c are negative.
