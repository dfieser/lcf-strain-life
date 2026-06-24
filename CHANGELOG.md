# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Major design decisions are recorded as ADRs in [docs/decisions/](docs/decisions/).

## [Unreleased]

### Added — tooling & docs
- Repository scaffolding: `pyproject.toml` (hatchling, src layout), MIT `LICENSE`,
  `README.md`, `.gitignore`, `.gitattributes`, this changelog, and the ADR decision log.
- Python 3.13 development virtual environment; dependency stack verified
  (numpy 2.5, scipy 1.18, pandas 3.0, matplotlib 3.11, pydantic 2.13, pyarrow 24, mcp 1.28).
- ADR-0001 through ADR-0008 capturing the core design decisions derived from the
  deep-research implementation reference.

### Added — core library (`lcf`)
- `units`: engineering↔true stress/strain conversions; MPa+fraction convention
  (loop area in MJ/m³ directly).
- `schema` + `models`: canonical column vocabulary; pydantic `TestMetadata`,
  `AnalysisParams`, `MeanStressModel`.
- `ingest`: `from_timeseries` / `from_dataframe` / `read_csv` → normalized `TestRun`.
- `cycles`: turning-point detection, ordered per-cycle reduction, half-life,
  configurable %-load-drop failure criterion (`N_f`).
- `energy`: shoelace closed-loop area (direction-independent).
- `metrics`: per-cycle stress/strain amplitudes, mean stress, T/C ratio, plastic
  strain (computed form), energy; modulus estimation fallback.
- `fits`: Basquin, Coffin-Manson, Ramberg-Osgood (log-log regression), transition
  life, Masing consistency check, optional nonlinear refinement, `min_plastic_strain`
  filter for the plastic branch.
- `meanstress`: equivalent fully-reversed stress (none/Morrow/SWT/Walker), Morrow &
  modified-Morrow strain-life curves, SWT parameter curve, Dowling steel-γ estimate.
- `life`: model curves and bracketed life inversion (total-strain, Basquin, SWT).
- `pipeline`: `analyze_test`, `analyze_material`, `fit_from_summary`.
- `plots`: headless matplotlib figures for the standard LCF plot set.
- `store`: content-addressed SQLite + Parquet + PNG persistence with SHA-256 cache.

### Added — MCP server
- `service`: MCP-free compute/save/recall orchestration (`LcfService`).
- `mcp_server`: FastMCP tools + `lcf://results/{key}/{quantity}` resource;
  `lcf-mcp` console script and `python -m lcf` entry point (stdio transport).

### Validation
- Golden-value tests reproduce published SAE 1137 strain-life constants
  (Williams, Lee & Rilly 2003): c ≈ −0.62, ε'f ≈ 1.1, transition ≈ 22,000 reversals.
- 114 tests passing.

### Notes
- Pre-existing documentation (`docs/reference/`, `docs/design/`) authored during the
  scoping phase is retained as the analytical specification.
- Finding: the Coffin-Manson plastic branch must exclude near-runout points (plastic
  strain at noise level); captured via the `min_plastic_strain` parameter and a test.
