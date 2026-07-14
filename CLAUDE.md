# CLAUDE.md

Instructions for Claude Code working in this repository. The full, cross-tool
contributor guidance lives in [AGENTS.md](AGENTS.md). Read it. The mandatory
writing style below is repeated here because it is critical.

## Mandatory writing style

These rules apply to everything you write in this project. That covers READMEs, documentation, code comments, docstrings, commit messages, decision records, changelog entries, and chat replies.

1. Never use em dashes. Rewrite the sentence with a period, a comma, or a colon.
2. Never use semicolons in prose. Use two sentences, or a comma.
3. Avoid unnecessary parentheses. Prefer a comma or a separate sentence. Keep them only where they clearly help, for example a unit label such as MPa or a file path.
4. Write plainly. Prefer short sentences. Cut filler.

These rules govern prose. They do not change Python syntax. Hyphens are fine, only em dashes are banned.

## Honesty, mandatory

Be completely honest and never overpromise. This governs everything: documentation, README claims, docstrings, commit messages, changelog entries, and replies to the maintainer.

1. Never claim a capability the code does not have. If a feature is partial, say exactly what works and what does not.
2. Report failures as failures. If tests fail, say so with the output. If something was skipped, say it was skipped.
3. State the source and method for every equation and dataset. This project is upfront about its methods and sources, and everything it uses must be publishable and citable.
4. Do not soften uncertainty. If a result is unvalidated or an implementation is untested against a golden value, label it that way.

## What this project is

An automated, AI-agent-native toolkit for fatigue analysis of materials. It ships as a Python library and an MCP server, so AI agents can run the full analysis by calling tools rather than by hand.

## The novelty, do not lose it

This project exists to be used by AI agents first. The novelty is an agent-native interface to fatigue analysis over MCP. If the agent focus is dropped, the project loses its reason to exist. Every capability must be reachable and useful through the MCP tools and the library API that an agent can call. When you add a feature, expose it as an MCP tool and keep its inputs and outputs agent friendly.

## Scope, stay broad

The toolkit is general purpose and material agnostic. It must serve many materials and many fatigue workflows, not one alloy family and not one industry. The source manuscript that seeded the equations is provenance only. Do not narrow the goal to high-entropy alloys or to any single material.

## Dev workflow

The virtual environment is in .venv on Python 3.13. Run the test suite with:

    ./.venv/Scripts/python.exe -m pytest

Validate scientific changes against the golden datasets in tests. Keep every change covered by a test. Add a line to CHANGELOG.md for notable changes. Detailed decision records, design notes, and research notes live in the workspace dev folder one level above this repository, at `..\dev`. That folder is developer material and never enters the public repository. Any change to an equation, a default, or a citation must regenerate docs/PHYSICS_REVIEW.tex, the physics record for specialist review.

## Website

The landing page and setup guide are in `website/`, plain HTML and CSS with no build step. Before editing anything there, read the mandatory design rules in [AGENTS.md](AGENTS.md) under "Website design rules". They forbid the patterns that make a site look machine-generated, for example gradients, Tailwind, colored left-border cards, glassmorphism, purple accents, Inter, centered heroes, and emoji icons. Full rationale is in `..\dev\docs\design\site-design-rules.md`.
