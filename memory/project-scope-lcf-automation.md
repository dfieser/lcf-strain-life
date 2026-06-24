---
name: project-scope-lcf-automation
description: What the fatigue analysis project is and is not
metadata:
  type: project
---

This project builds an AI-agent-native toolkit for fatigue analysis of materials, shipped as a Python library plus an MCP server. The whole point is that AI agents run the analysis by calling tools. That agent-native design is the novelty. If it is lost, the project has no reason to exist.

Scope is broad and material agnostic. It must serve many materials and many fatigue workflows, not one alloy family. v0.1 implements low cycle fatigue strain-life analysis. Phase 2 extends toward component life, variable amplitude loading, statistics, and high temperature. The source manuscript that seeded the equations is provenance only. Do not narrow the goal to high-entropy alloys.

Repo: github.com/dfieser/lcf-strain-life. Analysis reference in docs/reference. Design notes in docs/design. Decisions in docs/decisions. Style and positioning are hardcoded in CLAUDE.md and [[writing-style]]. See [[use-true-stress-strain]].
