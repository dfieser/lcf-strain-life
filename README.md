<img src="https://raw.githubusercontent.com/dfieser/lcf-strain-life/main/docs/assets/banner.png" alt="lcf-strain-life. Strain-life fatigue analysis, built for AI agents. Python library, MCP server, open data formats." width="100%">

<!-- mcp-name: io.github.dfieser/lcf-strain-life -->

# lcf-strain-life

[![tests](https://github.com/dfieser/lcf-strain-life/actions/workflows/tests.yml/badge.svg)](https://github.com/dfieser/lcf-strain-life/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/lcf-strain-life)](https://pypi.org/project/lcf-strain-life/)
[![DOI](https://zenodo.org/badge/1279652018.svg)](https://doi.org/10.5281/zenodo.21222820)

**[Website](https://dfieser.github.io/lcf-strain-life/)** | **[Documentation](https://dfieser.github.io/lcf-strain-life/docs/)** | **[Wiki](https://github.com/dfieser/lcf-strain-life/wiki)** | **[Physics Review](docs/PHYSICS_REVIEW.md)** | **[Changelog](CHANGELOG.md)** | **[MIT License](LICENSE)**

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
| Statistics | design curves, censored maximum likelihood with lognormal or Weibull scatter, profile-likelihood design bounds, outlier screening, Dixon-Mood staircase, A/B-basis values, the random fatigue limit model |
| High temperature | frequency-modified Coffin-Manson, time-fraction creep-fatigue |
| Surface | FKM roughness factor, and the FKM size-factor formula |
| Interchange and reports | versioned material documents, pyLife and py-fatigue adapters, one-call markdown lab reports |
| Provenance | every method maps to its published source through the citations registry |
| Save and recall | results persisted per test or material, recalled without recomputation, rendered as plots |

The toolkit is general purpose and material agnostic. It centers on strain-life reduction of raw strain-controlled test data and per-cycle evolution, end to end from lab exports. Other open libraries cover parts of this ground. pyLife and reliability implement strain-life equations, and py-fatigue and fatpack cover cycle counting and stress-life. None of them focus on reducing raw LCF test data or on driving the analysis from an AI agent. It is input compatible with the pandas data shapes of pyLife and py-fatigue.

## Install

```bash
pip install "lcf-strain-life[mcp]"
```

Requires Python 3.11 or newer. The base package is the library alone. The
`mcp` extra adds the MCP server and the `gui` extra adds the no-code
graphical interface.

To work on the source instead, clone this repository and install in a
virtual environment with `pip install -e ".[mcp,dev]"`.

## Quick start, MCP server

The MCP server is the point of this project: it is how an AI agent drives
the whole analysis by calling tools.

<img src="https://raw.githubusercontent.com/dfieser/lcf-strain-life/main/docs/assets/agent_workflow.png" alt="Diagram. An AI agent, any MCP client, talks to the lcf MCP server over stdio. The server exposes 41 tools such as analyze_test_csv, fit_strain_life, predict_life, count_rainflow, fit_design_curve, generate_report, get_citations, and recall_result. Results are saved to the .lcfstore directory and recalled without recomputation." width="100%">

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

Without installing anything first, any MCP client can also launch the
server through uv:

```bash
uvx --from "lcf-strain-life[mcp]" lcf-mcp
```

The [setup guide](https://dfieser.github.io/lcf-strain-life/get-started.html)
walks through Claude Desktop, Cursor, VS Code, and Google Antigravity. The
[agent usage guide](docs/AGENT_USAGE.md) documents every tool with its units
and the compute, save, recall pattern.

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

That call produces this fit. The figure is built by the library from the
six published SAE 1137 tests in the snippet above.

<img src="https://raw.githubusercontent.com/dfieser/lcf-strain-life/main/docs/assets/strain_life_sae1137.png" alt="Strain-life plot for SAE 1137. Six measured points lie on the fitted total strain amplitude curve. The teal dashed elastic Basquin branch and the amber dashed plastic Coffin-Manson branch cross at the transition life of 22,362 reversals." width="100%">

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

<img src="https://raw.githubusercontent.com/dfieser/lcf-strain-life/main/docs/assets/gui_fit_results.png" alt="Screenshot of the lcf-gui app. The fit page shows the fitted constants table for SAE 1137, including sigma_f of 1072.82 MPa, b of -0.084, eps_f of 1.106, c of -0.620, K of 1335.8 MPa, n of 0.175, and the transition life, next to the strain-life plot and the cyclic stress-strain curve." width="100%">

The app walks through the workflow in order: analyze raw test files, fit
strain-life constants, predict life, estimate constants when no fatigue data
exists, and export. A bundled published example dataset (SAE 1137) lets you
try the whole flow without any files.

A standalone Windows exe (no Python needed) is attached to
[GitHub releases](https://github.com/dfieser/lcf-strain-life/releases)
starting with v0.2.0. Download it, double-click, and the app opens in the
browser. Two honest caveats. The exe unpacks itself on every launch, so
starting takes a while. It is currently unsigned, so Windows SmartScreen
warns on first run. Choose "More info", then "Run anyway".

## Documentation

- **[The documentation site](https://dfieser.github.io/lcf-strain-life/docs/)** renders installation, usage, a tutorial reproducing a published SAE 1137 analysis, the statistics guide, and the API reference.
- **[The wiki](https://github.com/dfieser/lcf-strain-life/wiki)** covers practical setup, client configuration, validation status, an FAQ, and troubleshooting.
- **[docs/PHYSICS_REVIEW.md](docs/PHYSICS_REVIEW.md)** is the science-only physics record: every equation defined and cited, no software detail. [docs/PHYSICS_REVIEW.pdf](docs/PHYSICS_REVIEW.pdf) is the same content typeset with a reviewer sign-off table, the file to share with a materials scientist for review.
- [examples/](examples) holds runnable scripts: a strain-life fit and a machine-style CSV ingestion.
- [docs/AGENT_USAGE.md](docs/AGENT_USAGE.md) describes the MCP tools and the compute, save, recall pattern for AI agents using the toolkit.
- [CHANGELOG.md](CHANGELOG.md) is the chronological log of changes.

## Open data

The toolkit defines versioned, machine-readable interchange formats for
strain-life data, specified in [docs/INTERCHANGE.md](docs/INTERCHANGE.md)
with JSON Schemas in [docs/schemas/](docs/schemas). A citable seed
collection ships at
[docs/data/seed_collection.json](docs/data/seed_collection.json), six
published SAE 1137 tests and three verified constant sets. Every value is
re-tabulated from its cited source. It is a schema-reference seed, not yet
a database at scale. Contributions of strain-controlled data, especially
with per-cycle evolution, are welcome under the rules in
[docs/CONTRIBUTING-DATA.md](docs/CONTRIBUTING-DATA.md), and `lcf-validate`
checks any document from the command line.

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) covers the dev setup, the test suite,
and the ground rules. Scientific changes must pass the golden-value tests,
and honest claims are a hard requirement everywhere. Data contributions
follow [docs/CONTRIBUTING-DATA.md](docs/CONTRIBUTING-DATA.md).

## Project layout

```
src/lcf/            core library and MCP server
tests/              unit tests including golden-value validation, SAE 1137
examples/           runnable example scripts
docs/               documentation site sources, physics PDF, interchange
                    spec, JSON Schemas, seed data, and README figures
website/            the landing page, plain HTML and CSS
```

## Authors and citation

David Fieser and Hugh Shortt. Both authors contributed equally to this
project. To cite the software, use the "Cite this repository" button on
GitHub or [CITATION.cff](CITATION.cff).

## License

MIT. See [LICENSE](LICENSE).
