# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Detailed design notes and decision records are kept in the maintainers'
workspace outside the public repository.

## [Unreleased]

### Added
- `fit_design_curve` now reports the fitted amplitude interval under
  `amplitude_range` and a `warnings` list of machine-readable
  `{"code", "message"}` flags. A `design_amplitude` outside the fitted
  interval raises the `extrapolation` flag, following E739's own caveat
  against extrapolating outside the interval of testing. This starts the
  move from prose-only notes to caution flags an agent can branch on,
  prompted by an external critical assessment.
- Enforced code-quality gates. Ruff (default rules) and mypy with the
  pydantic plugin run over the package in CI, and the test job now fails
  if line coverage drops below 85 percent (86 percent when the gate was
  added). The dev extra installs ruff, mypy, and pytest-cov. The fifteen
  pre-existing ruff findings (unused imports, statements joined with
  semicolons, an f-string without placeholders) and thirty-two mypy
  findings were fixed. One annotation fix is behavioral in type terms
  only: `labio.read_series` now accepts any sequence of paths, not only a
  list.

### Changed
- The README no longer claims that established libraries do not cover
  strain-life. pyLife and reliability implement strain-life equations, the
  claim was overstated. The differentiation is now stated precisely:
  reduction of raw strain-controlled lab exports, per-cycle evolution, and
  the agent-native MCP interface.

### Fixed
- The result store leaked one SQLite connection per operation. The sqlite3
  context manager commits or rolls back but never closes, so every
  save/recall/list left an open handle behind. Connections are now closed
  explicitly. Found through ResourceWarnings surfaced by the new coverage
  run.
- A code review of the graphical interface surfaced eight state-handling
  defects, now all fixed and covered by tests. The displayed fit is dropped
  when the table or fit options change so the shown constants can never
  disagree with the visible data, and a Clear fit control was added. The
  predict page lets a user choose between a fit and an estimate when both
  exist, instead of the fit permanently shadowing the estimate. The ingest
  banner reports the true per-batch outcome and no longer shows success when
  every file failed, analyzed tests can be removed so a wrong file stops
  feeding the fit, the exported markdown report escapes pipe characters in
  user text, non-finite constants render as "not finite" and are flagged in
  the report, estimate inputs pass raw values so a zero yields the precise
  domain error, and the launcher only writes streamlit's global credentials
  file in the frozen build, not for pip users. An adversarial multi-agent
  review of the fixes then caught two more: the staleness check reset the
  fit options on page switches and wrongly cleared a valid fit (fixed by
  mirroring the options into session state), and the ingest guard checked
  the wrong key so a valid stress-only lab file was rejected (the reader
  normalizes a stress column to the canonical ``stress_eng`` role).
- The desktop exe opened a console showing streamlit's interactive
  first-run "enter your email" onboarding prompt, dead on arrival for a
  double-click user. Two-part fix: the launcher now writes streamlit's
  credentials file with an empty email on first run, exactly as streamlit
  does when the prompt is left blank, never touching an existing file, and
  the exe is now built windowed so no console appears at all. The launcher
  also gives streamlit a null output sink because a windowed app has no
  stdout/stderr. Found by the maintainer on a real double-click. The gap
  in verification, every earlier check ran the server with a headless
  override that skips the onboarding prompt, is closed by a new check that
  launches the exe against a fresh empty user profile with no overrides.

### Added
- A graphical no-code interface, `lcf.gui`, for researchers who do not
  program. Installed with `pip install lcf-strain-life[gui]` and started
  with `lcf-gui`, it serves a guided local Streamlit app: analyze raw lab
  exports, fit the strain-life constants, predict life with optional Morrow
  or SWT correction, estimate constants from monotonic properties, and
  export plots, tables, and a markdown report. The GUI is a thin layer over
  the same library functions the MCP server calls, with no duplicated
  science, and it runs entirely on the local machine with Streamlit
  telemetry disabled at launch. Covered by pure-logic tests and headless
  AppTest flows in `tests/test_gui.py`.
- A bundled example dataset module, `lcf.datasets`, holding the published
  SAE 1137 reduced data with its citation in one place. The README example,
  the demo script, and the GUI all source from it. The test-suite copy in
  `tests/conftest.py` stays independent on purpose, a golden reference must
  not come from the code it validates.
- A desktop build recipe, `scripts/build_gui_app.py`, freezing the same
  `lcf.gui` launcher into a single PyInstaller one-file exe dropped at the
  repository root, and a `windows-app` job in the publish workflow that
  builds it with that same script on each version tag and attaches the exe
  to the GitHub release. One-file is a deliberate choice for a single
  double-clickable artifact, accepting slower startup because the exe
  unpacks itself on every launch. The build excludes packages the GUI can
  never reach, numba/llvmlite, plotly, cryptography, tkinter, the AVIF
  codec, and the MCP server with its pywin32 chain, each exclusion
  documented with its measured size in the build script. That cut the exe
  from 182 MB to 119 MB and startup from about 11 to about 7 seconds,
  measured on Windows 11. The exe still exceeds GitHub's 100 MB file limit
  so it is gitignored, not committed. The build is unsigned for now
  and SmartScreen will warn on first run, the README says so. The workflow
  job first runs on the next tag push.
- The random fatigue limit fit is now benchmarked against the published
  Pascual-Meeker result. The laminate-panel dataset (Shimokawa and
  Hamaguchi 1987, 125 specimens, obtained from the public GPL SMRD.data R
  package) is bundled as a golden test, and the fitter reproduces the 1999
  Technometrics normal-normal fit exactly: log-likelihood -86.221, beta0
  30.272, beta1 -5.100, mu_gamma 5.366, matching Table 1 to the digit. The
  validation status changes from implementation-grade to published-fit
  reproduction everywhere it is stated.
- Cycle-dependent mean stress relaxation and ratcheting, a new
  `lcf.cyclic_evolution` module. Mean stress relaxation under strain control
  (sigma_m(N) = sigma_m1 N^b_r) and ratcheting strain accumulation under
  stress control (eps_r = C N^p) with power-law fitters, plus the ratcheting
  ductility-exhaustion life penalty on the Coffin-Manson plastic line. Three
  new MCP tools: `fit_mean_stress_relaxation`, `fit_ratcheting_law`,
  `ratcheting_penalized_life`. These forms were reconstructed from the
  collaborator notes of 2026-07-08 (whose inline equations were lost in
  transfer) and match the standard published forms of Jhansale-Topper,
  Morrow-Sinclair, Xia-Kujawski-Ellyin, and Kapoor, cited in the registry.
  Every result carries a note that the formulation is reconstructed and
  pending the collaborator's confirmation. Validation is internal
  consistency and fitter-recovery of known constants. The physics record
  and PDF now document these forms.
- FKM technological size factor K_d,m in `lcf.surface`, exposed as
  `compute_size_factor`. Reduces the tensile strength (and stress-based
  fatigue strength) for components thicker than the reference specimen, by
  the logarithmic FKM formula with the 0.7686 coefficient, verified against
  two independent open sources. Only the formula is implemented: the
  per-material constant tables are copyrighted FKM data and are not
  bundled (the same rule that excludes NIMS, MMPDS, and Boller-Seeger
  tables), so the caller supplies a_dm and d_eff_N from a licensed copy of
  the guideline. The formula's mathematical properties (unity at the
  reference diameter, monotonic decrease, exact closed form) are the
  tested behavior.
- Load-input (notched member) mode for the variable-amplitude engine,
  completing the P3 done-criterion. `simulate_variable_amplitude` and the
  library now accept a nominal stress history with Kt: the initial
  loading follows Neuber's rule on the cyclic curve and every branch the
  modified Neuber rule on the doubled curve, reusing the notch module's
  solvers, so loops carry the local notch-root strain and stress.
  Validated against the SAE keyhole benchmark (AE-6, 1977, inputs and
  results recovered from the Internet Archive copy of the offline
  eFatigue benchmark page): the constant-amplitude RQC-100 case (CR1)
  predicts within 4 percent of the benchmark's own strain-life
  calculation and conservatively against the crack-based experimental
  life, and the Man-Ten suspension variable-amplitude case (SM2)
  predicts within a factor of two of the three experimental lives, with
  Morrow at 0.85x. Reproducible with `examples/validate_sae_keyhole.py`,
  golden-tested (CR1 inline, SM2 gated on `LCF_FDE_DATA_DIR`), physics
  record updated and PDF regenerated.
- Random fatigue limit model, completing the P2 statistics scope. New
  `lcf.rfl` module fits the Pascual-Meeker normal-normal model by maximum
  likelihood: each specimen's fatigue limit is unit-to-unit random, the
  S-N curve flattens naturally near the limit, and runouts enter the
  likelihood as censored observations including the probability that the
  limit sits above the test stress. The marginal integral is evaluated by
  Gauss-Legendre quadrature, vectorized per stress level. Validation
  status, stated in every result: the likelihood is cross-checked against
  brute-force adaptive integration, and the fitter recovers known
  parameters from data simulated at the published laminate-panel test
  design (five levels, 25 specimens, censoring). It is not yet benchmarked
  against the published fit itself because those raw datasets (Shimokawa
  and Hamaguchi 1987, Shen 1994) are not openly published. Exposed as the
  `fit_random_fatigue_limit` MCP tool, physics record and PDF updated.
- FKM surface roughness factor. New `lcf.surface` module computes K_R from
  Rz and Rm for the seven FKM material groups, with the formula and
  constants verified against an open engineering reference and its
  published worked example (steel, Rm 600 MPa, Rz 100, K_R = 0.79) as a
  golden test. Capped at 1.0 for polished surfaces, applies to
  stress-based fatigue strengths, and the result says that strain-life
  constants are not corrected directly. Exposed as the
  `compute_roughness_factor` MCP tool. The FKM technological size factor
  stays deferred, its constants were not available from a verifiable open
  source.
- The pyLife and py-fatigue adapters are now round-trip verified against
  the installed libraries (pyLife 2.3.1, py-fatigue 2.1.1, development
  test dependencies only): real WoehlerCurve and SNCurve objects built
  from our exports reproduce the Basquin inversion to nine digits.
  `export_material` gains `fmt="py_fatigue"` (slope/intercept
  conventions). New `labio.read_fde_history` parses the SAE FD and E
  committee history format (comments, one value per line, progress
  markers), shared by the examples and tested.

- Tensor critical-plane search (P5 of the adopted build plan). New
  `lcf.criticalplane` module takes strain and stress tensor component
  histories over one cycle, scans plane normals over a hemisphere grid,
  resolves each plane's engineering shear amplitude by the longest-chord
  rule (meaningful for non-proportional paths), normal strain amplitude,
  and peak normal stress, and maximizes Fatemi-Socie, Brown-Miller, or
  SWT through the existing survey functions. Validated against exact
  closed forms for uniaxial loading with Poisson contraction and pure
  torsion. Exposed as the `search_critical_plane_tensor` MCP tool. The
  multiaxial module is no longer survey-only and its registry notes say
  what the search does and does not cover.
- Report generation and material interchange (P4 of the adopted build
  plan). `generate_report` assembles everything stored under a key into a
  markdown lab report with provenance hashes and the source citation for
  every method that appears, returned, recallable, and written to
  `<store>/reports/`. `lcf.interchange` defines the versioned
  `lcf-strain-life/material@1` JSON document for strain-life constants
  (there is no de facto standard for this exchange), with
  `export_material` and `import_material` MCP tools that refuse unknown
  versions and unit systems, plus a pyLife WoehlerCurve adapter
  (shape-compatible with pyLife's documented conventions and exactly
  round-tripping, not integration-tested against an installed pyLife).
  The py-fatigue and VMAP adapters are deferred until real round-trips
  can be verified. 13 new tests.
- Published-case validation of the variable-amplitude engine against the
  Conle SAE smooth-specimen dataset (MSc thesis, University of Waterloo,
  1974, GPL data distributed by the SAE FD and E committee at
  fde.uwaterloo.ca): strain-controlled tests of SAE10B20 steel under the
  full transmission, bracket, and suspension histories at 0.010 peak
  strain. Predictions land within a factor of two of experiment for the
  transmission and bracket histories and about a factor of three,
  non-conservative, for suspension, all three leaning non-conservative,
  consistent with the documented scatter of linear-damage local-strain
  predictions on this program. The engine's blanket experimental label is
  replaced by this concrete evidence statement everywhere it appears.
  Reproducible with `examples/validate_sae_conle.py`, regression-guarded
  by prediction-band tests gated on `LCF_FDE_DATA_DIR`.
- `examples/variable_amplitude_sae.py`: runs the variable-amplitude engine
  on a real SAE Fatigue Design and Evaluation committee service load
  history (transmission, bracket, or suspension). The histories are GPL
  licensed by the FD&E committee and are downloaded from their public
  archive at run time rather than bundled. The example prints the loop
  table, damage per block, blocks to failure, and the engine's honesty
  notes. All three histories, up to 5936 points, simulate in under half a
  second.
- Variable-amplitude strain-life, experimental (first slice of P3 of the
  adopted build plan). New `lcf.simulate` module walks a repeating strain
  history block through the cyclic stress response: Ramberg-Osgood initial
  loading, doubled Masing branches, and material memory by the rainflow
  closure rule, so sequence effects enter through the simulated loop mean
  stresses. Per-loop life reuses the existing SWT, Morrow, and uncorrected
  solvers, Miner-summed to blocks to failure. Exposed as the
  `simulate_variable_amplitude` MCP tool. Validated for internal
  consistency: constant amplitude reproduces the closed-form solvers, the
  closed loops match rainflow counting, and an interrupting cycle leaves
  the outer branch exactly where it would have been. Labeled experimental
  everywhere it appears until it reproduces a published variable-amplitude
  dataset, and the model limits are stated in every result: stabilized
  cyclic properties, no mean stress relaxation, no ratcheting. 14 new
  tests.
- Staircase fatigue-limit analysis and basis values (first slice of P2 of
  the adopted build plan). New `lcf.staircase` module implements the
  Dixon-Mood method per ISO 12107 with the published validity bound: below
  a variability statistic of 0.3 the standard deviation falls back to the
  approximate 0.53 step value and the result is flagged. Golden-validated
  against the published S34MnV worked example (mean 282 MPa, standard
  deviation 10.6 MPa). `lcf.stats` gains `basis_value` (A-basis and
  B-basis one-sided tolerance bounds through the exact Owen factor,
  validated against the standard table values 2.355 and 3.981 at n=10)
  and `lack_of_fit` (the E739-style F test, available whenever the data
  contain replicate amplitude levels, and reported in every uncensored
  `fit_design_curve` result). Two new MCP tools, `analyze_staircase` and
  `compute_basis_value`, and 19 new tests. The random fatigue limit model
  is deferred until a validated reference dataset is in hand, per the
  honesty rule.
- Lab-export ingestion and one-call series analysis (P1 of the adopted build
  plan). A new `lcf.labio` module reads the delimited files fatigue labs
  actually produce: it auto-detects the delimiter and the header row beneath
  machine preamble blocks, resolves column names through a synonym table
  (MTS TestSuite and Instron style exports among others), converts unit
  suffixes (percent strain, kN force, ksi stress), tolerates a units row
  under the header and decimal-comma files, and refuses ambiguous or
  unmarked-percent input with actionable messages instead of guessing. A
  `stress_eng` column now satisfies ingestion without a force column.
  Exposed as two new MCP tools: `analyze_test_series` (directory in,
  per-test summaries plus a fitted strain-life curve out, per-file errors
  collected without stopping the series) and `preview_lab_file` (how a file
  would be read, before analyzing it). 18 new tests cover the readers, the
  refusal guards, and the batch path.
- ASTM E606 specimen and test-condition metadata. `TestMetadata` gains an
  optional nested `SpecimenMetadata` (specimen geometry, control mode,
  strain rate, environment, machine, extensometer, standard, and so on, all
  optional). It is carried into stored summaries and recorded in the
  citation registry as `e606_reporting`. Test summaries now also carry the
  strain ratio `R`.
- The physics record now defines the stress ratio R and the strain ratio, a
  table of the loading configurations from fully reversed through
  compression-compression, and the control-mode context for the mean-stress
  corrections: mean stress relaxation under strain control, ratcheting under
  stress control, and which correction suits which case. The record states
  plainly that cycle-dependent relaxation and ratcheting evolution models are
  not implemented and that the corrections apply to the stabilized cycle.
  Integrated from collaborator notes by Hugh Shortt, background sources:
  Morrow and Sinclair 1958, Jhansale and Topper 1973, Xia, Kujawski and
  Ellyin 1996. Both `docs/PHYSICS_REVIEW.md` and the typeset PDF are updated.

### Fixed
- The Ramberg-Osgood branch solver could fail on tiny strain ranges for
  materials with very low cyclic hardening (the plastic term underflows
  and the elastic bracket bound rounds below the target). The bracket now
  carries a one-part-per-billion margin. Found running the real SAE
  suspension history with the Conle SAE10B20 constants, covered by a
  regression test.
- Two citation registry corrections found while verifying every project
  citation against publisher records. The Walker entry cited Dowling's SAE
  paper by the wrong number, 2004-01-0227, the verified number is
  2004-01-2227, and the 2009 Dowling, Calhoun, and Arcari paper is now named
  alongside it. The log-life regression entry now cites the published Meeker
  et al., Statistical Science 41 (2026) 1-27, instead of only the arXiv
  preprint it superseded.
- The Modified Morrow and Smith-Watson-Topper equations in
  `docs/PHYSICS_REVIEW.md` now render correctly on GitHub. A continuation line
  that began with `+` was read as a Markdown list item, which broke the math
  block and mangled the rest of the equation. The `+` now sits at the end of
  the previous line. The math is unchanged. A new test, `test_docs_math.py`,
  guards against the pattern returning.

## [0.1.1] - 2026-07-06

- The version now has a single source of truth, `__version__` in
  `src/lcf/__init__.py`. pyproject.toml reads it at build time through hatch
  dynamic versioning, and new tests fail CI if CITATION.cff or the changelog
  drift from it.

## [0.1.0] - 2026-07-06

First public release, on PyPI as `lcf-strain-life` and archived on Zenodo.

### Added: Phase 3, estimation, data quality, counting parity, provenance
- `estimate`: strain-life constant estimation from monotonic properties, five
  published methods with validity guardrails: the Meggiolaro-Castro medians
  method (2004, recommended default), the Baeumel-Seeger Uniform Material Law
  (1990), Manson's universal slopes (1965), the Muralidharan-Manson modified
  universal slopes (1988, steels only), and the Roessle-Fatemi hardness method
  (2000, steels only). Each result carries its citation and warnings. Exposed
  as the `estimate_strain_life_constants` MCP tool.
- `stats`: Grubbs single-outlier test and the generalized ESD test, validated
  against the NIST/Rosner worked example, plus regression influence
  diagnostics (leverage, studentized residuals, Cook's distance). Exposed as
  the `flag_outliers` MCP tool, which treats runouts as censored data, never
  as outliers.
- `counting`: racetrack (gate) filter for history condensation, level-crossing
  counting (ASTM E1049 5.2), and peak counting (ASTM E1049 5.3). New
  `count_level_crossings` and `count_peaks` MCP tools, and a `gate` option on
  `count_rainflow`.
- `damage`: `sn_curve_life` for Woehler lines with a knee, with original,
  elementary, and Haibach (fictitious slope 2k-1) treatments below the knee.
  Exposed as the `compute_sn_life` MCP tool.
- `citations`: a machine-readable registry mapping every method in the package
  to its published source, exposed as the `get_citations` MCP tool and the
  `lcf://citations` resource.
- MCP exposure for capabilities that previously had no tool: multiaxial
  critical-plane parameters (`compute_multiaxial_parameter`,
  `search_critical_plane`), the frequency-modified Coffin-Manson law
  (`compute_frequency_modified_life`), Corten-Dolan through `compute_damage`,
  and PNG rendering of stored results (`render_plot`).
- The physics record gained sections for constant estimation, outlier
  screening, counting extensions, and the S-N knee variants.

### Changed
- `CITATION.cff`, `.zenodo.json`, `pyproject.toml`, and `LICENSE` now credit
  both authors, David Fieser and Hugh Shortt, with ORCIDs.
- The release process document moved to the maintainers' workspace.

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
