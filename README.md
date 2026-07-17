# lcf-strain-life

[![tests](https://github.com/dfieser/lcf-strain-life/actions/workflows/tests.yml/badge.svg)](https://github.com/dfieser/lcf-strain-life/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/lcf-strain-life)](https://pypi.org/project/lcf-strain-life/)
[![DOI](https://zenodo.org/badge/1279652018.svg)](https://doi.org/10.5281/zenodo.21222820)

**[Readme](README.md)** | **[Physics Review](docs/PHYSICS_REVIEW.md)** | **[Agent Usage](docs/AGENT_USAGE.md)** | **[Changelog](CHANGELOG.md)** | **[MIT License](LICENSE)**

An **AI-agent-native toolkit for fatigue analysis of materials**. It is a Python library plus an **MCP server**, so AI agents can run the whole analysis by calling tools.

Provide your own strain-controlled fatigue test data and get the standardized reduction, fitted material constants, life predictions, and plots. Results are reproducible and are saved for recall.

> **Why this exists:** plenty of fatigue software exists, but none is built for AI agents to drive directly. The agent-native design over MCP is the point. Every capability is reachable through tools an agent can call.

> **Convention:** all analysis uses true stress and true strain. Engineering input is converted at ingestion. The fatigue exponents `b` and `c` are negative throughout.

---

## What it does

| Stage | What happens |
|---|---|
| Ingest and normalize | raw `time, strain, force` plus parameters become true stress-strain, reading the delimited exports labs actually produce, with ASTM E606 metadata and one-call batch analysis of a whole test series |
| Cycle reduction | peak and valley per cycle, half-life cycle, cycles-to-failure `N_f` |
| Per-cycle metrics | stress amplitude, plastic strain amplitude, mean stress, T/C ratio, hysteresis energy |
| Strain-life fits | Basquin, Coffin-Manson, Ramberg-Osgood, transition life |
| Constant estimation | five published methods estimate the constants from tensile properties or hardness when no fatigue data exists |
| Mean stress | Morrow, modified Morrow, SWT, Walker corrections |
| Variable amplitude | rainflow, level-crossing, and peak counting (ASTM E1049), racetrack filter, spectrum life, and a Masing-memory local-strain engine (strain or load-input Neuber) validated against published SAE datasets |
| Damage | Miner, DLDR, Corten-Dolan, Woehler knee variants including Haibach |
| Notch and multiaxial | Neuber and Glinka local strain, tensor critical-plane search (Fatemi-Socie, Brown-Miller, SWT) |
| Statistics | design curves with runout handling, outlier screening, Dixon-Mood staircase, A/B-basis values, the random fatigue limit model |
| High temperature | frequency-modified Coffin-Manson, time-fraction creep-fatigue |
| Surface | FKM roughness factor, and the FKM size-factor formula |
| Interchange and reports | versioned material documents, pyLife and py-fatigue adapters, one-call markdown lab reports |
| Provenance | every method maps to its published source through the citations registry |
| Save and recall | results persisted per test or material, recalled without recomputation, rendered as plots |

The toolkit is general purpose and material agnostic. It focuses on strain-life and per-cycle evolution, which the established stress-based high-cycle libraries such as pyLife, py-fatigue, and fatpack do not cover. It is input compatible with their pandas data shapes.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -e ".[mcp,dev]"
```

Requires Python 3.11 or newer.

## Quick start, library

```python
import lcf

# fit strain-life constants from per-test reduced data, here SAE 1137
fit = lcf.fit_strain_life(
    total_strain_amp=[0.009, 0.007, 0.005, 0.003, 0.002, 0.00175],
    stress_amp=[553, 522, 464, 405, 350, 319],         # MPa, half-life
    reversals=[4234, 7398, 14768, 77104, 437498, 3327958],
    E=208000,                                           # MPa
    min_plastic_strain=5e-4,   # exclude near-runout points from the plastic branch
)
print(fit.coffin_manson.eps_f, fit.coffin_manson.c)   # about 1.11, -0.62
print(fit.basquin.sigma_f, fit.basquin.b)             # about 1073 MPa, -0.084
print(fit.transition_reversals)                        # about 22,000 reversals
```

## Quick start, MCP server

The MCP server is the point of this project: it is how an AI agent drives the
whole analysis by calling tools.

```bash
lcf-mcp                # runs the stdio MCP server
# or
python -m lcf
```

Register with Claude Code or Claude Desktop over stdio:

```json
{ "mcpServers": {
    "lcf": { "command": "lcf-mcp" } } }
```

## Quick start, graphical interface (no code)

A secondary, optional interface for people who do not program and are not
using an AI agent. The agent-native MCP server above is the primary way to
use this toolkit. The graphical app is a thin convenience layer over the same
library functions, adding no capability the tools do not already expose.

It is a guided local app in the browser: upload test files or type in reduced
data, fit the constants, predict life, export plots and a report. Everything
runs on your machine and no data leaves it.

```bash
pip install "lcf-strain-life[gui]"
lcf-gui
```

The `gui` extra ships with the next PyPI release. Until then, install from a
clone of this repository with `pip install -e ".[gui]"`.

The app walks through the workflow in order: analyze raw test files, fit
strain-life constants, predict life, estimate constants when no fatigue data
exists, and export. A bundled published example dataset (SAE 1137) lets you
try the whole flow without any files.

A standalone Windows exe (no Python needed) is attached to GitHub releases
starting with the next release. Download it, double-click, and the app opens
in the browser. Two honest caveats: the exe unpacks itself on every launch,
so starting takes a while, and it is currently unsigned, so Windows
SmartScreen will warn on first run. Choose "More info", then "Run anyway".

## Documentation

- **[docs/PHYSICS_REVIEW.md](docs/PHYSICS_REVIEW.md)** is the science-only physics record: every equation defined and cited, no software detail. [docs/PHYSICS_REVIEW.pdf](docs/PHYSICS_REVIEW.pdf) is the same content typeset with a reviewer sign-off table, the file to share with a materials scientist for review.
- [examples/](examples) holds runnable scripts: a strain-life fit and a machine-style CSV ingestion.
- [docs/AGENT_USAGE.md](docs/AGENT_USAGE.md) describes the MCP tools and the compute, save, recall pattern for AI agents using the toolkit.
- [CHANGELOG.md](CHANGELOG.md) is the chronological log of changes.

## Project layout

```
src/lcf/            core library and MCP server
tests/              unit tests including golden-value validation, SAE 1137
examples/           runnable example scripts
docs/               the physics PDF and the agent usage guide
```

## Authors and citation

David Fieser and Hugh Shortt. Both authors contributed equally to this
project. To cite the software, use the "Cite this repository" button on
GitHub or [CITATION.cff](CITATION.cff).

## License

MIT. See [LICENSE](LICENSE).
