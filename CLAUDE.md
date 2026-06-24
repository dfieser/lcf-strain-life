# CLAUDE.md

Instructions for any AI agent working in this repository. Read this before writing code or docs.

## Mandatory writing style

These rules apply to everything you write in this project. That covers READMEs, documentation, code comments, docstrings, commit messages, decision records, changelog entries, and chat replies.

1. Never use em dashes. Rewrite the sentence with a period, a comma, or a colon.
2. Never use semicolons in prose. Use two sentences, or a comma.
3. Avoid unnecessary parentheses. Prefer a comma or a separate sentence. Keep them only where they clearly help, for example a unit label such as MPa or a file path.
4. Write plainly. Prefer short sentences. Cut filler.

These rules govern prose. They do not change Python syntax. Hyphens are fine, only em dashes are banned.

## What this project is

An automated, AI-agent-native toolkit for fatigue analysis of materials. It ships as a Python library and an MCP server, so AI agents can run the full analysis by calling tools rather than by hand.

## The novelty, do not lose it

This project exists to be used by AI agents first. The novelty is an agent-native interface to fatigue analysis over MCP. If the agent focus is dropped, the project loses its reason to exist. Every capability must be reachable and useful through the MCP tools and the library API that an agent can call. When you add a feature, expose it as an MCP tool and keep its inputs and outputs agent friendly.

## Scope, stay broad

The toolkit is general purpose and material agnostic. It must serve many materials and many fatigue workflows, not one alloy family and not one industry. The source manuscript that seeded the equations is provenance only. Do not narrow the goal to high-entropy alloys or to any single material.

## Dev workflow

The virtual environment is in .venv on Python 3.13. Run the test suite with:

    ./.venv/Scripts/python.exe -m pytest

Validate scientific changes against the golden datasets in tests. Keep every change covered by a test. Record major decisions as an ADR in docs/decisions and add a line to CHANGELOG.md.
