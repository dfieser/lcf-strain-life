# Contributing

Thanks for considering a contribution. This page covers code contributions.
Data contributions follow [docs/CONTRIBUTING-DATA.md](docs/CONTRIBUTING-DATA.md).

## Dev setup

```bash
git clone https://github.com/dfieser/lcf-strain-life.git
cd lcf-strain-life
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -e ".[mcp,dev]"
```

Python 3.11 or newer. No heavy new dependencies beyond numpy, scipy,
pandas, matplotlib, pydantic, pyarrow, and the optional mcp SDK.

## Tests

```bash
python -m pytest
```

Every change must keep the suite green. Validate scientific changes
against the golden datasets already in the tests, for example the SAE 1137
strain-life values and the ASTM E1049 rainflow example. New capability
needs a test, ideally against a published value.

## Ground rules

1. Honesty is mandatory. Never claim a capability the code does not have.
   Label unvalidated results as unvalidated. State the source for every
   equation and dataset.
2. Everything used must be publishable and citable. New methods register
   their source in the citations registry.
3. Every capability must also be reachable through the MCP tools. The
   agent-native interface is the point of the project.
4. Use true stress and true strain internally. Stress and modulus in MPa,
   strain as a dimensionless fraction, exponents b and c negative.
5. Results that cross the MCP or store boundary must be valid JSON.
6. Any change to an equation, a default, or a citation must regenerate
   the physics record, `docs/PHYSICS_REVIEW.tex`.
7. Add a line to [CHANGELOG.md](CHANGELOG.md) for each notable change.

## Style

Plain, direct prose in docs, comments, and commit messages. No em dashes,
no semicolons in prose. Commits use Conventional Commit prefixes, for
example `feat:`, `fix:`, or `docs:`, scoped to one logical change with its
tests. Lint and type-check with `ruff check` and `mypy` before pushing.

## Reporting problems

Open an [issue](https://github.com/dfieser/lcf-strain-life/issues) with
the version, a minimal reproduction, and what you expected. For suspected
scientific errors, please cite the source you checked against. That is the
fastest kind of report to act on.
