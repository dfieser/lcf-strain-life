# Project Overview

We are building an AI-agent-native toolkit for fatigue analysis of materials. A scientist or an AI agent provides test data, and the tool runs the full analysis on its own. It ships as a Python library and as an MCP server, so AI agents can drive every step by calling tools.

## Why it is different

Plenty of fatigue software exists. What does not exist is a fatigue toolkit built for AI agents to use directly. That is our novelty. The whole tool is reachable over MCP, so an agent can ingest data, reduce cycles, fit models, predict life, and recall results through a conversation. The agent focus is the heart of the project, not an extra feature.

## What it does

The toolkit takes raw fatigue test data and automatically:

- Cleans and standardizes it, using true stress and true strain.
- Reduces the data cycle by cycle and tracks how the material hardens and softens.
- Fits the standard fatigue models and predicts fatigue life.
- Saves results so an agent or a user can recall them later without recomputing.

## Who and what it is for

It is general purpose and material agnostic. It is meant to serve many materials and many fatigue workflows across research and engineering, not a single alloy or industry. Today it covers low cycle fatigue strain-life analysis. It is growing toward component life under realistic loading, statistical design values, and high temperature behavior.

## Why it matters

It turns a slow, manual, error prone workflow into something an AI agent can run from start to finish, and something any scientist can reproduce with their own data in minutes.

---

New to the project? The plain-language and technical references live in [docs/reference](docs/reference). Design notes are in [docs/design](docs/design).
