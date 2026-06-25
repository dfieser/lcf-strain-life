# AGENTS.md

Guidance for AI agents working on this repository. This is the cross-tool
companion to CLAUDE.md. Both carry the same rules, this one is the canonical
source. Keep it short and precise.

## Project overview

`lcf` is an AI-agent-native toolkit for fatigue analysis of materials. It ships
as a Python library and an MCP server, so agents can run the full analysis by
calling tools. The package covers low cycle fatigue strain-life analysis,
variable-amplitude loading, cumulative damage, notch local-strain, statistics
and design curves, and elevated-temperature creep-fatigue.

## The novelty, do not lose it

The project exists to be used by AI agents first. Every capability must be
reachable and useful through the MCP tools and the library API. When you add a
feature, expose it as an MCP tool and keep its inputs and outputs agent friendly.

## Scope, stay broad

General purpose and material agnostic. Serve many materials and many fatigue
workflows, not one alloy family. The source manuscripts that seeded the
equations are provenance only. Do not narrow the goal to one material.

## Setup

```
py -3.13 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[mcp,dev]"
```

Python 3.11 or newer. No heavy new dependencies beyond numpy, scipy, pandas,
matplotlib, pydantic, pyarrow, and the optional mcp SDK.

## Build and test commands

```
./.venv/Scripts/python.exe -m pytest                 # full suite
./.venv/Scripts/python.exe -m pytest tests/test_fits.py -q   # one module
./.venv/Scripts/python.exe -m pytest -W error::DeprecationWarning -W error::FutureWarning
```

Every change must keep the suite green. Scientific changes must be validated
against the golden datasets already in tests, for example SAE 1137 and the ASTM
E1049 rainflow example.

## Conventions

- Writing style, mandatory. No em dashes, no semicolons in prose, no unnecessary
  parentheses. This applies to code comments, docstrings, commit messages, and
  docs. Hyphens are fine.
- Use true stress and true strain everywhere. Convert engineering input at
  ingestion.
- Internal units are MPa for stress and modulus, dimensionless fraction for
  strain. The fatigue exponents b and c are negative.
- Reuse the Phase 1 fits, life inversion, mean-stress, and metrics. Do not
  reimplement the Ramberg-Osgood curve or the strain-life solver.
- Results that cross the MCP or store boundary must be valid JSON. Map non-finite
  floats to null with `lcf.store.to_jsonable`.
- Record each major decision as an ADR in `docs/decisions` and add a line to
  `CHANGELOG.md`.

## Running the MCP server

```
lcf-mcp            # stdio transport
python -m lcf      # same entry point
```

The store directory comes from the `LCF_STORE_DIR` environment variable and
defaults to `.lcfstore`.

## Repository layout

```
src/lcf/            library and MCP server
tests/              unit tests including golden-value validation
docs/reference/     equations, physics, symbol tables
docs/design/        workflow and the research-derived implementation references
docs/decisions/     ADRs, the decision log
```

## Commit and PR guidance

Use Conventional Commit prefixes, for example `feat(phase2):` or `fix:`. Keep
commits scoped to one logical change with its tests. Do not push or open a pull
request unless asked.
