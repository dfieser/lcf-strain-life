# lcf-strain-life

An **AI-agent-native toolkit for fatigue analysis of materials**. It is a Python library plus an **MCP server**, so AI agents can run the whole analysis by calling tools.

Provide your own strain-controlled fatigue test data and get the standardized reduction, fitted material constants, life predictions, and plots. Results are reproducible and are saved for recall.

> **Why this exists:** plenty of fatigue software exists, but none is built for AI agents to drive directly. The agent-native design over MCP is the point. Every capability is reachable through tools an agent can call.

> **Convention:** all analysis uses true stress and true strain. Engineering input is converted at ingestion. The fatigue exponents `b` and `c` are negative throughout.

---

## What it does

| Stage | What happens |
|---|---|
| Ingest and normalize | raw `time, strain, force` plus parameters become true stress-strain |
| Cycle reduction | peak and valley per cycle, half-life cycle, cycles-to-failure `N_f` |
| Per-cycle metrics | stress amplitude, plastic strain amplitude, mean stress, T/C ratio, hysteresis energy |
| Strain-life fits | Basquin, Coffin-Manson, Ramberg-Osgood, transition life |
| Mean stress | Morrow, modified Morrow, SWT, Walker corrections |
| Save and recall | results persisted per test or material, recalled without recomputation |

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

## Documentation

- [docs/reference](docs/reference) holds the equations, symbols, and physics.
- [docs/design/WORKFLOW.md](docs/design/WORKFLOW.md) describes the data flow and the compute, save, recall model.
- [docs/decisions](docs/decisions) holds the Architecture Decision Records, one per major design choice.
- [CHANGELOG.md](CHANGELOG.md) is the chronological log of changes.

## For AI agents

This toolkit is built to be driven by AI agents over MCP.

- [docs/AGENT_USAGE.md](docs/AGENT_USAGE.md): the MCP tools, their units, and the compute, save, recall pattern, for agents using the tool.
- [AGENTS.md](AGENTS.md): guidance for agents working on the repository, with CLAUDE.md as the Claude Code companion.
- [llms.txt](llms.txt): a machine-readable index of the docs.

## Project layout

```
src/lcf/            core library and MCP server
tests/              unit tests including golden-value validation, SAE 1137
docs/reference/     equations, physics, symbol tables
docs/design/        workflow and research-derived implementation reference
docs/decisions/     ADRs, the decision log
```

## License

MIT. See [LICENSE](LICENSE).
