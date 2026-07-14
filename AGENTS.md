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

## Honesty, mandatory

Be completely honest and never overpromise, in docs, claims, commit messages,
and replies. Never claim a capability the code does not have. Report failures
as failures. State the source for every equation and dataset, everything used
must be publishable and citable. Label unvalidated results as unvalidated.

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
- Add a line to `CHANGELOG.md` for each notable change. Detailed decision records,
  design notes, and research notes are kept in the workspace `dev/` folder one
  level above this repository, at `../dev`. Developer material never enters the
  public repository.
- Any change to an equation, a default, or a citation must regenerate the physics
  PDF with `pdflatex docs/PHYSICS_REVIEW.tex`. That is the physics record a domain
  specialist reviews.

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
examples/           runnable example scripts
docs/               the physics PDF and the agent usage guide
website/               landing page and setup guide, published to GitHub Pages
../dev/             workspace-level design notes and decision records, outside the repo
```

## Website design rules (website/)

The landing page and setup guide live in `website/`, plain HTML and CSS with one
small vanilla JS file. No build step and no framework. These rules exist so the
site never reads as machine-generated. Follow them for any change under `website/`.

Hard rules:
- No CSS gradients of any kind, linear, radial, or conic, including gradient
  masks and gradient text. Use solid colors and tiled SVG textures instead.
- No Tailwind or any utility-class framework. No shadcn or copied component kits.
- No colored left-border cards. Use a full border with a small square indicator.
- No glassmorphism, no backdrop-filter, no heavy blurred shadows.
- No purple or blue-to-purple accent. The accent is the teal in the tokens.
- No Inter or Space Grotesk. Type is the system sans plus a monospace utility
  face, a deliberate pairing.
- The hero is left-aligned and asymmetric, never a centered hero with a vague
  headline. Headlines say what the tool does for a fatigue engineer.
- No emoji as icons, section markers, or the favicon. The favicon is
  `assets/favicon.svg`.
- Radii stay small and technical. Chips and tags are rectangular, not pills.
- Real content only. Real plots from `examples/output`, real numbers from the
  validated examples, no fabricated screenshots or logos.

Quality bars: accessible (semantic landmarks, keyboard support, visible focus,
alt text, WCAG contrast, reduced motion), responsive, self-contained (local
assets only, no CDN or external fonts), both themes given equal care through the
design tokens.

Supported MCP clients to name in the setup guide: Claude Desktop, Cursor, VS Code
in Copilot agent mode (its config key is `servers`, not `mcpServers`), and Google
Antigravity. The universal launch command is `uvx --from "lcf-strain-life[mcp]" lcf-mcp`.

Full rationale and the sources behind these tells are in
`../dev/docs/design/site-design-rules.md`.

## Commit and PR guidance

Use Conventional Commit prefixes, for example `feat(phase2):` or `fix:`. Keep
commits scoped to one logical change with its tests. Do not push or open a pull
request unless asked.
