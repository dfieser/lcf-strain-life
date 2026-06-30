# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Detailed design notes and decision records are kept in the local `dev/` folder, which is not part of the public repository.

## [Unreleased]

### Added: examples, packaging, release
- `examples/csv_ingestion_demo.py` reads a machine-style CSV header block and runs
  the full single-test analysis, with a matching test, exercising the real-data path.
- `docs/PHYSICS_REVIEW.pdf`, a single science-only document with every equation
  defined and cited, for review by a materials specialist.
- PEP 561 `py.typed` marker, expanded PyPI classifiers and project URLs, build
  validated with `twine check`.
- `CITATION.cff` and `.zenodo.json` for citation and a Zenodo DOI on release.
- GitHub Actions: `tests.yml` (matrix on Python 3.11 to 3.13) and `publish.yml`
  (PyPI via Trusted Publishing on a `v*` tag push, current action versions).
- `RELEASING.md` with the semantic-versioning scheme and the release process.
  README status badges.

### Changed: repository reorganized for a clean public repo
- Developer and AI-process material (research references, decision records,
  design notes, scratch) moved to a local `dev/` folder that is not committed.
  Agent memory is no longer tracked. The public repository now contains the
  library, tests, examples, the physics PDF, and the agent usage guide.

### Added: Phase 2 engineering layer
- `counting`: in-house ASTM E1049 rainflow with preserved cycle indices and a
  repeat-history closure. Validated against the ASTM worked example.
- `damage`: Palmgren-Miner, Double Linear Damage Rule with the Manson-Halford
  knee, and Corten-Dolan. Validated against Golden C and D.
- `notch`: Neuber and Glinka local-strain solvers, Kt/Kf/q, and end-to-end notch
  life. Validated against the SAE 1005 example (Golden E).
- `stats`: E739 log-life regression, confidence and prediction intervals, Owen
  R-C design curves, and a right-censored maximum-likelihood fit. The Owen factor
  matches standard tables.
- `hightemp`: frequency-modified Coffin-Manson, time-fraction creep-fatigue with
  a D-diagram envelope, and temperature-dependent constant interpolation.
- `multiaxial`: critical-plane parameters and a plane-search interface, survey only.
- `spectrum`: end-to-end variable-amplitude life, counting to mean correction to
  damage.
- Six new MCP tools, Phase 2 plots, optional metadata fields, and expanded public API.
- Agent-facing docs: `AGENTS.md`, `docs/AGENT_USAGE.md`, and `llms.txt`.
- 217 tests passing, pyflakes clean, clean under deprecation and future warnings.

### Added: tooling & docs
- Repository scaffolding: `pyproject.toml` (hatchling, src layout), MIT `LICENSE`,
  `README.md`, `.gitignore`, `.gitattributes`, this changelog, and the ADR decision log.
- Python 3.13 development virtual environment. Dependency stack verified
  (numpy 2.5, scipy 1.18, pandas 3.0, matplotlib 3.11, pydantic 2.13, pyarrow 24, mcp 1.28).
- ADR-0001 through ADR-0008 capturing the core design decisions derived from the
  deep-research implementation reference.

### Added: core library (`lcf`)
- `units`: engineering-to-true and true-to-engineering stress/strain conversions. MPa+fraction convention
  gives loop area in MJ/m³ directly.
- `schema` + `models`: canonical column vocabulary. Pydantic `TestMetadata`,
  `AnalysisParams`, `MeanStressModel`.
- `ingest`: `from_timeseries` / `from_dataframe` / `read_csv` produce a normalized `TestRun`.
- `cycles`: turning-point detection, ordered per-cycle reduction, half-life,
  configurable %-load-drop failure criterion (`N_f`).
- `energy`: shoelace closed-loop area, direction-independent.
- `metrics`: per-cycle stress/strain amplitudes, mean stress, T/C ratio, plastic
  strain in computed form, and energy. Modulus estimation fallback.
- `fits`: Basquin, Coffin-Manson, Ramberg-Osgood (log-log regression), transition
  life, Masing consistency check, optional nonlinear refinement, `min_plastic_strain`
  filter for the plastic branch.
- `meanstress`: equivalent fully-reversed stress (none/Morrow/SWT/Walker), Morrow and
  modified-Morrow strain-life curves, SWT parameter curve, Dowling steel-γ estimate.
- `life`: model curves and bracketed life inversion (total-strain, Basquin, SWT).
- `pipeline`: `analyze_test`, `analyze_material`, `fit_from_summary`.
- `plots`: headless matplotlib figures for the standard LCF plot set.
- `store`: content-addressed SQLite + Parquet + PNG persistence with SHA-256 cache.

### Added: MCP server
- `service`: MCP-free compute/save/recall orchestration (`LcfService`).
- `mcp_server`: FastMCP tools plus `lcf://results/{key}/{quantity}` resource.
  `lcf-mcp` console script and `python -m lcf` entry point (stdio transport).

### Validation
- Golden-value tests reproduce published SAE 1137 strain-life constants
  (Williams, Lee & Rilly 2003): c ≈ -0.62, ε'f ≈ 1.1, transition ≈ 22,000 reversals.

### Hardened (critical review, ADR-0009)
- Three-part review: web-verified physics, web-verified API currency, adversarial
  code audit. Physics 13/13 and API usage confirmed correct.
- Non-finite floats (NaN/Inf) serialize as JSON `null` (`allow_nan=False`). This fixes
  invalid JSON from 2-point fits that could break strict MCP clients.
- Noise-aware turning-point detection (amplitude gate + density warning).
- Robust failure-criterion reference (max peak, post-peak search, positive-only).
- Guards on Morrow/modified-Morrow (σ_m ≥ σ'f), `transition_reversals`, Basquin
  life-inverse, life inversion (decreasing-curve), and `check_consistency`.
- Ingest validation (NaN rows rejected, non-monotonic time warned).
- Store: injective Parquet filenames. SQLite WAL + busy_timeout.
- Walker steel-γ intercept corrected to 0.8818 (Dowling 2009).
- 135 tests passing, clean under `-W error::DeprecationWarning,FutureWarning`.

### Notes
- The scoping and analysis specifications authored during development are kept in the local
  `dev/` folder, out of the public repository.
- Finding: the Coffin-Manson plastic branch must exclude near-runout points where plastic
  strain is at noise level. This is captured via the `min_plastic_strain` parameter and a test.
