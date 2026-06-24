# lcf-strain-life

Material-agnostic **Low Cycle Fatigue (LCF) strain-life analysis** — a core Python library
plus an **MCP server** so AI agents can run the full analysis conversationally.

Drop in your own strain-controlled fatigue test data and get the standardized reduction,
fitted material constants, life predictions, and plots — reproducibly, with results saved
for recall.

> **Convention:** all analysis uses **true stress / true strain** (engineering input is
> converted at ingestion). The fatigue exponents `b` and `c` are negative throughout.

---

## What it does

| Stage | What happens |
|---|---|
| **Ingest & normalize** | raw `(time, strain, force)` + params → true stress–strain |
| **Cycle reduction** | peak/valley per cycle, half-life cycle, cycles-to-failure `N_f` |
| **Per-cycle metrics** | stress amplitude, plastic strain amplitude, mean stress, T/C ratio, hysteresis energy |
| **Strain-life fits** | Basquin (σ′f, b), Coffin-Manson (ε′f, c), Ramberg-Osgood (K′, n′), transition life |
| **Mean-stress** | Morrow, modified Morrow, SWT, Walker corrections |
| **Save & recall** | results persisted per test/material; recalled without recomputation |

The tool is **strain-life / per-cycle-evolution focused** — the niche that the established,
stress-based, high-cycle Python libraries (`pyLife`, `py-fatigue`, `fatpack`) do not cover.
It is *input-compatible* with their pandas data shapes.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -e ".[mcp,dev]"
```

Requires Python ≥ 3.11.

## Quick start (library)

```python
import lcf

# fit strain-life constants from per-test reduced data (SAE 1137)
fit = lcf.fit_strain_life(
    total_strain_amp=[0.009, 0.007, 0.005, 0.003, 0.002, 0.00175],
    stress_amp=[553, 522, 464, 405, 350, 319],         # MPa, half-life
    reversals=[4234, 7398, 14768, 77104, 437498, 3327958],
    E=208000,                                           # MPa
    min_plastic_strain=5e-4,   # exclude near-runout points from the plastic branch
)
print(fit.coffin_manson.eps_f, fit.coffin_manson.c)   # ~1.11, -0.62
print(fit.basquin.sigma_f, fit.basquin.b)             # ~1073 MPa, -0.084
print(fit.transition_reversals)                        # ~22,000 reversals
```

## Quick start (MCP server)

```bash
lcf-mcp                # runs the stdio MCP server
# or
python -m lcf
```

Register with Claude Code / Claude Desktop (stdio):

```json
{ "mcpServers": {
    "lcf": { "command": "lcf-mcp" } } }
```

## Documentation

- **[docs/reference/](docs/reference/)** — the equations, symbols, and physics (LaTeX + notes).
- **[docs/design/WORKFLOW.md](docs/design/WORKFLOW.md)** — data flow and the compute/save/recall model.
- **[docs/decisions/](docs/decisions/)** — Architecture Decision Records (ADRs): every major
  design choice and its rationale.
- **[CHANGELOG.md](CHANGELOG.md)** — chronological log of changes.

## Project layout

```
src/lcf/            core library + MCP server
tests/              unit tests incl. golden-value validation (SAE 1137)
docs/reference/     equations, physics, symbol tables
docs/design/        workflow & research-derived implementation reference
docs/decisions/     ADRs (the decision log)
```

## License

MIT — see [LICENSE](LICENSE).
