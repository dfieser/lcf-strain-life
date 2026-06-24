# LCF Strain-Life Analysis Tool — Authoritative Implementation Reference

This is the single implementation reference for building a material-agnostic Python LCF strain-life tool (core library + MCP server). All analysis uses true stress/true strain; b and c are negative throughout. All API/library facts are version-stamped (access date **2026-06-24**). Sources are cited inline; where sources conflict or a value could not be verified verbatim, this is stated explicitly.

## Table of Contents
1. Standards and authoritative data-reduction conventions
2. The strain-life model set: formulas, fitting, pitfalls
3. Cycle detection and segmentation for strain-controlled data
4. Model Context Protocol (MCP) current Python implementation guide
5. Python fatigue ecosystem data models and interop
6. Numerical implementation idioms (SciPy/NumPy/pandas)
7. Input file formats from real LCF test machines
8. Persistence / save & recall layer
9. Standard LCF plots and conventions
10. Engineering stress-strain fundamentals & typical curves
11. Validation datasets and reference material constants
12. Implementation decisions & open-question recommendations

---

## SECTION 1 — Standards and authoritative data-reduction conventions

**ASTM E606/E606M-21** "Standard Test Method for Strain-Controlled Fatigue Testing" (current edition E606/E606M-21, store.astm.org/e0606_e0606m-21.html, accessed 2026-06-24) is the governing US method for strain-controlled (LCF) testing. The standard requires that cyclic total strain be measured and cyclic plastic strain be determined; either may be used to characterize fatigue. Data correlations (cyclic stress/strain vs life; cyclic stress vs cyclic plastic strain from hysteresis loops) are taken "at some fraction (often half) of material life" (ASTM E606/E606M-21 scope text).

**ISO 12106:2017** "Metallic materials — Fatigue testing — Axial-strain-controlled method" (iso.org/standard/64687.html) specifies constant-amplitude strain control at uniform temperature, including R = −1 and other ratios as a guide. The widely circulated **ISO 12106:2003** text gives the precise definitions still used: §3.3 strain is *true total strain* ε = ∫dL/L, with the note that "at true strain values less than 10 %, ε is approximated by the engineering strain ΔL/Lo"; §3.9 amplitude = half the range; §3.7 mean = one-half the algebraic sum of max and min; §3.10 fatigue life Nf = number of cycles to achieve failure, and "the failure criterion used shall be reported with the results" (failure criteria in §7.8).

**ASTM E739** "Statistical Analysis of Linear or Linearized Stress-Life (S-N) and Strain-Life (ε-N) Fatigue Data." **Critical currency note:** E739-10(2015) was the active practice, but **E739-23 was withdrawn in January 2024 with no replacement** because, per ASTM (store.astm.org/e0739-23.html), "many of the methods used in the guide have become outdated, and there is concern about the methods being used outside their field of applicability." The guide covers only relationships approximable by a straight line on appropriate (log) coordinates over a specific interval, and explicitly recommends against (a) extrapolating outside the test interval, or (b) estimating life below approximately the 5th percentile (P ≈ 0.05). **Practical consequence:** the linearized per-branch regression remains good engineering practice, but the tool should not present E739 as a current standard — cite it as withdrawn-but-widely-used.

**Stabilized / half-life cycle (definition + competing conventions).** Because materials harden or soften during cycling, material properties are characterized at the *stabilized* hysteresis loop, conventionally taken at **half-life (N = 0.5·Nf)** (ASTM E606; ISO 12106 practice as summarized by ZwickRoell, zwickroell.com LCF page). The recommended recording protocol (ZwickRoell/testXpert summary of E606/ISO 12106): record *every* loop at the start (rapid transient), store at logarithmic intervals (every 100th or 1000th) through the stabilized range, and record every cycle again near end of test. Selection rule for "stabilized": the half-life loop is the default; for non-stabilizing materials, report the loop at the explicitly stated fraction of life.

**Plastic strain amplitude Δεp/2 — two conventions.** (a) Loop *width at zero stress* (measured directly off the stabilized loop); (b) *computed* Δεp/2 = Δεt/2 − Δσ/(2E). The **computed form is the practical standard default** because the measured zero-stress width is sensitive to loop noise and to small modulus/zero offsets; the two agree for a Masing material. The Williams/Lee/Rilly SAE 1137 dataset (Section 11) uses the computed form (elastic amp = stress amp / E; plastic = total − elastic).

**Reversals vs cycles.** One cycle = two reversals; strain-life is expressed in reversals 2Nf. For a controlled constant-amplitude waveform, each cycle is exactly one closed loop = two reversals, so reversal counting is trivial peak-valley counting on the command waveform (no rainflow needed for constant amplitude).

**Failure criterion / Nf.** There is **no single standard-mandated value** — both E606 and ISO 12106 require the criterion be chosen and *reported*. The most commonly used default is a **load-drop of a fixed percentage from the stabilized (e.g. half-life) peak tensile load**; modulus-drop and complete specimen separation are alternatives. Published programs commonly use values in the 10–50% range; the Williams/Lee/Rilly SAE 1137 program used a **30% load drop**. Recommend defaulting to a configurable percent load-drop and always persisting the chosen value with results.

**Sign and unit conventions.** b and c are negative. Stresses in MPa, strains dimensionless, E in MPa. σ'f and K' carry MPa; b, c, n', ε'f are dimensionless (ε'f is a strain).

---

## SECTION 2 — The strain-life model set: formulas, fitting, pitfalls

**Total strain-life (Coffin-Manson + Basquin superposition):**

  Δε/2 = (σ'f/E)·(2Nf)^b + ε'f·(2Nf)^c

- **Basquin (elastic):** Δεe/2 = (σ'f/E)·(2Nf)^b ; equivalently Δσ/2 = σ'f·(2Nf)^b
- **Coffin-Manson (plastic):** Δεp/2 = ε'f·(2Nf)^c
- **Elastic strain identity (exact):** Δεe/2 = Δσ/(2E)
- **Ramberg-Osgood (cyclic stress-strain):** ε = σ/E + (σ/K')^(1/n')
- **Hysteresis-loop form:** Δε = Δσ/E + 2·(Δσ/(2K'))^(1/n')

(All forms confirmed against the `reliability` library PoF documentation, reliability.readthedocs.io, and Lv et al. 2016 — see below.)

**Fitting methodology.** Per the (now withdrawn but standard-practice) ASTM E739 linearized approach, the standard fit is a **log-log linear least-squares regression on each branch separately**: regress log(Δεe/2) on log(2Nf) → slope b, intercept = log(σ'f/E); regress log(Δεp/2) on log(2Nf) → slope c, intercept = log(ε'f). E739 formally assigns life as the dependent variable for S-N work, but engineering strain-life practice regresses strain (or stress) on life; document which orientation you use. **Recommended pipeline:** do the per-branch linear fit first (robust, gives the four constants and initial guesses), then optionally refine with **nonlinear least squares on the combined total-strain curve** (`scipy.optimize.curve_fit`) seeded by those guesses. No special weighting is mandated; if used, weight by data density across the life range.

**Elastic/plastic transition life 2Nt** (where elastic = plastic strain amplitude):

  2Nt = (ε'f·E / σ'f)^(1/(b−c))

Below 2Nt plastic strain dominates (LCF regime); above it elastic dominates. Use 2Nt to annotate the strain-life plot and to decide which branch governs a given life.

**Masing vs non-Masing and compatibility relations.** Compatibility requires n' = b/c and K' = σ'f / (ε'f)^(b/c). Many real materials are non-Masing (the stabilized loops are not geometrically similar; e.g. ASTM A516 Gr 70 does not show Masing behavior, while G8.8/G10.9 bolt steels do). **Recommended default: fit K' and n' independently** from the stabilized cyclic stress-strain data, AND separately compute the b/c-derived values, then flag when they diverge materially. Do not silently force compatibility.

**Goodness-of-fit and uncertainty.** Report per-branch R²; report confidence intervals on slope/intercept (Student-t on the regression, per E739 methodology); for nonlinear fits, derive standard errors from sqrt(diag(pcov)). Honor E739's cautions: no extrapolation beyond the tested interval; do not estimate below ~5th percentile.

**Mean-stress corrections (exact forms, verified against `reliability` PoF docs):**
- **Morrow:** Δε/2 = ((σ'f − σm)/E)·(2Nf)^b + ε'f·(2Nf)^c
- **Modified Morrow (Morrow on both terms):** Δε/2 = ((σ'f − σm)/E)·(2Nf)^b + ε'f·((σ'f − σm)/σ'f)^(c/b)·(2Nf)^c
- **Smith-Watson-Topper (SWT):** σmax·εa·E (= Δε/2·σmax·E) on the left, with right side σ'f²·(2Nf)^2b + σ'f·ε'f·E·(2Nf)^(b+c); equivalently Δε/2 = (σ'f²/(σmax·E))·(2Nf)^2b + (σ'f·ε'f/σmax)·(2Nf)^(b+c)
- **Walker:** equivalent fully-reversed amplitude σar = σmax^(1−γ)·σa^γ (Lv et al. 2016, eq. 7).

**Walker exponent γ.** Obtained by fitting fatigue data at *multiple* mean-stress (R) levels so the corrected data collapse onto a single curve (Lv et al., J. Mech. Sci. Tech. 30(3) 2016, 1129–1137). When **γ = 0.5, Walker reduces exactly to SWT**. When no zero-mean or multi-R data exist, γ can be estimated for steels: **Dowling, Calhoun & Arcari (2009) give γ = γ0 − a·σu with γ0 = 0.883 and a = 2×10⁻⁴ MPa⁻¹ for steels** (as reproduced by Tiryakioğlu 2017, PMC5744336). Lv et al. (2016, eq. 9) alternatively propose γ = 0.5 ± (σu − σo)/(σu + σo) from yield σo and ultimate σu; their Table 1 lists measured γ values (e.g. SAE 1015 0.735, SAE 4130 Norm 0.690, 7075-T6 ≈ 0.415–0.477, Ti-6Al-4V 0.543).

**Recommended default mean-stress correction.** Use **SWT** as the general default (parameter-free, robust); per **Dowling, FFEMS 32 (2009) 1004–1019, "for precipitation-hardened aluminium alloys in the 2000 and 7000 series, an estimate of γ = 0.5 may be applied, so that the method becomes similar to that of Smith, Watson and Topper."** Offer **Morrow** when a reliable σ'f / true fracture strength is available, and **Walker** (most accurate) when multi-R data exist. Per **Dowling, Calhoun & Arcari, FFEMS 32 (2009) 163–179, the Goodman relationship is highly inaccurate and the Morrow method should not be used for aluminium alloys unless the true fracture strength is employed**; Walker/SWT are most accurate for general use.

**Hysteresis loop energy.** Plastic strain energy density per cycle = the closed loop area ∮σ dε (units MPa·(dimensionless) = MJ/m³). Distinguish *plastic* strain energy density (loop area) from *total* strain energy density (loop area plus the elastic triangles). The closed line integral equals the signed enclosed area; take the absolute value (sign depends on traversal direction). Energy-based life models relate plastic strain energy density to life: ΔWp = W'f·(2Nf)^d (power law, analogous to Coffin-Manson on energy).

---

## SECTION 3 — Cycle detection and segmentation for strain-controlled data

**Constant-amplitude, fully-reversed strain control.** Segment the continuous (t, ε, σ) stream by **peak-valley (turning-point) detection on the command/strain waveform**: each adjacent peak→valley→peak triple defines one closed loop. This preserves cycle ordering, so per-cycle evolution (hardening/softening, peak/valley stress drift, energy per cycle) is retained — which is exactly the tool's differentiator. Rainflow is unnecessary for constant amplitude (each cycle has identical range).

**Irregular / variable-amplitude histories.** Rainflow (ASTM E1049-85) is the appropriate method for cycle **detection**. To use rainflow for detection only while preserving per-cycle evolution, use an implementation that **reports the original sample indices** of each closed loop, then re-order loops in time and compute per-cycle metrics. Established libraries that expose this:
- **pyLife** `FullRecorder` records, in addition to the from/to values, the indices of loop turning points in the original time series (so temperature, dwell time, etc. can be looked up). Detectors: `ThreePointDetector` and `FourPointDetector` (both report sample index), `FKMDetector` (Clormann & Seeger algorithm, FKM-recommended, does *not* report index). Detectors are chunkable (resumable on new data chunks). (pyLife rainflow module docs, pylife.readthedocs.io, v2.3.x, accessed 2026-06-24.)
- **`rainflow`** (PyPI, iamlikeme, v3.2.0, ASTM E1049-85): `extract_cycles(series)` yields `(rng, mean, count, i_start, i_end)` — the i_start/i_end give the indices needed to preserve order.
- **fatpack** (MIT): `find_reversals`, `find_rainflow_cycles`, `find_rainflow_matrix`.

**Peak-valley extraction, loop closure, de-noising.** Standard preprocessing (per MATLAB/SDC Verifier rainflow practice and pyLife): (1) reduce to turning points (peak-valley filter — removes intermediate points that carry no fatigue information); (2) hysteresis-gate filter (drop micro-cycles below a threshold set as % of max range or absolute value); (3) optional Butterworth bandpass (`scipy.signal`) and running-statistics spike removal, as in pyLife `clean_timeseries`. Loop closure for a repeated constant-amplitude command is implicit per cycle; for irregular data, residual half-cycles remain after rainflow (handle per E1049 residue rules).

---

## SECTION 4 — Model Context Protocol (MCP) current Python implementation guide

*Treat as time-sensitive; all facts version-stamped, accessed 2026-06-24.*

**Official SDK.** PyPI package **`mcp`** (repo modelcontextprotocol/python-sdk, MIT license, requires Python ≥3.10). Current 1.x release observed on PyPI is **mcp 1.28.0**. The SDK is transitioning to a v2 line: the README states **v2 is in alpha, "targeting a beta on 2026-06-30 and a stable v2 on 2026-07-27," and advises pinning `mcp>=1.27,<2`** until v2 stabilizes; v1.x is in maintenance mode (critical fixes/security only). Install: `uv add "mcp[cli]"` or `pip install "mcp[cli]"`. The `[cli]` extra provides the `mcp` CLI used for `mcp dev` (hot-reload local testing) and `mcp install`.

**FastMCP.** FastMCP 1.0 was incorporated into the official SDK and is importable as `mcp.server.fastmcp.FastMCP`. A separate standalone **PrefectHQ/fastmcp** project also exists (current 3.x, e.g. fastmcp 3.4.2; v3.0 introduced components/providers/transforms). **For a single, minimal dependency, use the official SDK's bundled FastMCP** unless you specifically need standalone v2/v3 features.

**Minimal, complete, copy-pasteable server:**
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("lcf-strain-life")

@mcp.tool()
def fit_strain_life(strain_amp: list[float], stress_amp: list[float],
                    reversals: list[float], E: float) -> dict:
    """Fit Basquin + Coffin-Manson constants from per-test strain-life data.

    Args:
        strain_amp: total strain amplitude per test (mm/mm)
        stress_amp: stabilized (half-life) stress amplitude per test (MPa)
        reversals:  reversals to failure 2Nf per test
        E:          Young's modulus (MPa)
    """
    # ... per-branch log-log regression ...
    return {"sigma_f": ..., "b": ..., "eps_f": ..., "c": ...}

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**Declaring inputs/outputs.** Type hints + pydantic models are auto-converted to JSON Schema; the function docstring becomes the tool description. The SDK supports **structured output**: a tool's return-type annotation classifies the result as structured content; this can be suppressed with `structured_output=False` on the `@tool` decorator. Unstructured (text) results are also returned for backward compatibility with older spec/FastMCP versions.

**Passing numerical arrays (thousands of stress/strain samples).** Three patterns, in order of preference for large data:
1. **Inline JSON arrays** — simplest, but consumes model context tokens; only for small arrays. Claude Code warns when tool output exceeds **10,000 tokens** (raise via `MAX_MCP_OUTPUT_TOKENS`).
2. **File paths / MCP resources** — recommended for large arrays: write Parquet/CSV to disk and pass the path or a resource URI.
3. **Split content vs structuredContent** — per the MCP `CallToolResult` design, `content` goes to the model (use for a compact text summary + a download URL) and `structuredContent` goes to the client only (full payload, zero model tokens). This is the idiomatic way to return thousands of rows without flooding context (futuresearch.ai analysis).

**Returning rich artifacts (plots/images, tables).** Return base64 PNG as `ImageContent` for hysteresis-loop / strain-life plots, or (preferred for large images) write the PNG to disk/resource and return its path/URI. Return tabular results as structured dicts/lists, or as a resource URI pointing to a Parquet/CSV.

**Stateful servers / persistence (compute / save / recall).** Use an in-memory dict for session-scoped caching; for cross-call persistence write to SQLite/Parquet keyed by test/material and expose stored datasets and results as **MCP resources**, e.g. `@mcp.resource("lcf://results/{test_id}")`. The compute tool saves; a recall tool or the resource reads back. Resources behave like read-only GET endpoints that load data into context on demand.

**Transports & client config.** Two relevant transports: **stdio** (local child process; Claude Desktop's default) and **Streamable HTTP** (for remote servers). **Streamable HTTP was introduced in MCP spec revision 2025-03-26 and replaced the deprecated HTTP+SSE transport.** Claude Desktop config file: macOS `~/Library/Application Support/Claude/claude_desktop_config.json`; Windows `%APPDATA%\Claude\claude_desktop_config.json`. Claude Code uses a project-scoped `.mcp.json` (or `claude mcp add`) and supports a per-server `timeout` field in milliseconds (overrides `MCP_TOOL_TIMEOUT`; values below 1000 ms are ignored; default per-call wall-clock is ~28 h when unset). Standard config shape (mcpServers object):
```json
{ "mcpServers": {
    "lcf": { "command": "uv",
             "args": ["run", "python", "-m", "lcf_tool.mcp_server"] } } }
```

**Best practices / gotchas.** Keep tools narrow and clearly named (the protocol has no built-in tool versioning today — embed a version in the name on breaking changes, e.g. `fit_strain_life_v2`); validate all inputs with pydantic; surface errors as clear text messages rather than exceptions; for long computations respect the per-server timeout; test locally with the **MCP Inspector** (`mcp dev server.py`, then connect at the printed localhost URL). Note Claude Code's **tool search** defers tool schemas until needed, so many tools cost little context.

**Packaging a single installable package (library + server).** Use `pyproject.toml` with a console-script entry point plus a `__main__.py` so the server runs via `python -m`:
```toml
[project.scripts]
lcf-mcp = "lcf_tool.mcp_server:main"
```

---

## SECTION 5 — Python fatigue ecosystem data models and interop

**pyLife (Bosch).** Current 2.x (docs span 2.0.0–2.3.1; data-model docs 2.1.1). Stores data in pandas. Load collectives and rainflow matrices are represented as a pandas Series/DataFrame with a **MultiIndex of `pandas.IntervalIndex`** whose levels are named **`from` and `to`** (with range/mean variants); a 2-D rainflow matrix is one-dimensional from a data-structure view (each element = loop occurrence frequency). Detector+recorder architecture (chunkable): detectors `ThreePointDetector`, `FourPointDetector`, `FKMDetector`; recorders `LoopValueRecorder` (from/to only) and `FullRecorder` (from/to + original-series turning-point indices). **pyLife fits Wöhler/SN curves** (its data-fitting module is for SN parameters); it does **NOT** provide Coffin-Manson / Basquin / Ramberg-Osgood strain-life LCF fitting.

**py-fatigue (OWI-Lab, VUB).** **py-fatigue v2.0.1** (D'Antuono, Weijtjens & Devriendt 2022, OWI-Lab; docs 2.0.4), **GPL-3.0**; v2 lives on the `develop` branch and supports Python 3.10–3.13 (64-bit only); v1.x supported Python 3.8–3.10 (per github.com/OWI-Lab/py_fatigue). Main class **`CycleCount`** with constructors **`CycleCount.from_timeseries(...)`** and **`CycleCount.from_rainflow(...)`**. Documented attributes/methods include `stress_amplitude`, `min_stress`, `max_stress`, `mean_stress_correction()`, `full_cycles`, `half_cycles`, `residuals`, `min_max_sequence`, `time_sequence`, `bin_centers`/`bin_edges`, `to_df()`, `as_dict()`, `summary()`, `plot_histogram()`, `plot_residuals_sequence()`, `plot_half_cycles_sequence()`. Rainflow per ASTM E1049-85 (`binned_rainflow`, defaults: range_bin_width 0.05, mean_bin_width 10.0). **py-fatigue does stress-life (SN) + crack growth (Paris) damage**; it does **NOT** provide strain-life LCF.

**fatpack (Gunnstein).** MIT license. `find_rainflow_ranges`, `find_reversals(y, k=...)`, `find_rainflow_cycles`, `find_rainflow_matrix`, `concatenate_reversals`; endurance curves + Miner sum. No strain-life LCF.

**rainflow (PyPI, iamlikeme).** v3.2.0, ASTM E1049-85; `count_cycles`, `extract_cycles` → `(rng, mean, count, i_start, i_end)`.

**reliability (Python).** `PoF.stress_strain_life_parameters_from_data` (fits K, n from Ramberg-Osgood; σ'f, ε'f, b, c from Coffin-Manson when stress+strain+cycles supplied) and `PoF.strain_life_diagram` (implements Ramberg-Osgood, Coffin-Manson, Morrow, modified Morrow, SWT). This is the **closest existing strain-life implementation** and is a useful oracle for cross-checking your fits.

**Differentiator and what to reuse.** None of pyLife / py-fatigue / fatpack provide per-cycle LCF evolution + Coffin-Manson/Basquin/Ramberg-Osgood multi-test fitting — that is this tool's niche. **Reuse:** their rainflow engines (especially pyLife `FullRecorder` for index-preserving detection), pandas containers and the `from`/`to`/`range`/`mean`/`amplitude`/`mean_stress` vocabulary, and their matplotlib/plotly plotting.

---

## SECTION 6 — Numerical implementation idioms (SciPy/NumPy/pandas)

**Loop area integration.** `numpy.trapezoid` is the current name. **`numpy.trapz` was deprecated in NumPy 2.0 (2023-08-18) and removed in NumPy 2.4.0** — confirmed by the NumPy 2.4.0 Release Notes: "numpy.trapz — deprecated since NumPy 2.0 (2023-08-18). Use numpy.trapezoid or scipy.integrate functions instead"; the runtime failure on 2.4.0 is `AttributeError: module 'numpy' has no attribute 'trapz'`. Use `numpy.trapezoid(y, x)` (NumPy ≥2.0) or, for cross-version safety, **`scipy.integrate.trapezoid`**. `scipy.integrate.simpson` is more accurate for smooth data but is ill-suited to a noisy, self-intersecting closed loop. For a closed hysteresis loop the most robust area is the **shoelace polygon formula** on the ordered (ε, σ) vertices: A = 0.5·|Σ (ε_i·σ_{i+1} − ε_{i+1}·σ_i)|. The closed line integral ∮σ dε equals the signed enclosed area; the sign depends on traversal direction, so take the absolute value. **Do not sort the points** — integrate around the loop in acquisition order to handle non-monotonic, self-intersecting paths correctly.

**Power-law fits.** Log-log linear via `scipy.stats.linregress` (returns slope, intercept, r, stderr) or `numpy.polyfit(x, y, 1)`; native nonlinear via `scipy.optimize.curve_fit` (returns popt and covariance; standard errors = sqrt(diag(pcov))). **Pitfall — log-transform bias:** least squares in log space minimizes *relative* error and over-weights small values; for final published coefficients prefer `curve_fit` on the native power-law form, using the log-fit results as initial guesses. Recover σ'f from the elastic intercept as σ'f = E·10^(intercept) (or exp, depending on log base); recover ε'f directly from the plastic intercept.

**Young's modulus estimation when E not supplied.** Fit the elastic portion of the stabilized loop: linear regression of σ vs ε over the initial linear segment of a reversal (typically the first ~20–40% of the reversal); slope = E. Use robust regression or restrict to the clearly linear region to avoid contaminating E with early plasticity.

---

## SECTION 7 — Input file formats from real LCF test machines

**MTS TestSuite.** Exports synchronized time-series signals (e.g. load, displacement, axial strain) as delimited text/CSV, typically with a metadata header block; project/run files are `.tsproj`, and data-export formats are user-configurable. Column names follow user-defined signal names (commonly Time, Axial Force, Axial Strain). (MTS TestSuite user guides, mts.com.)

**Instron Bluehill.** CSV export with a header metadata block followed by a column header row and a units sub-row, then data (Time, Extension, Load, Strain/Tensile strain).

**Generic CSV/TSV.** time, strain, force columns, often with a units row beneath the header.

**Recommended canonical internal input schema** (pandas DataFrame; mirrors pyLife `from`/`to` and py-fatigue vocabulary):

| Column | Units | dtype | Required | Notes |
|---|---|---|---|---|
| `time` | s | float64 | yes | monotonic |
| `strain` | mm/mm (engineering) | float64 | yes | raw eng strain at ingestion |
| `force` | N | float64 | yes | raw load |
| `strain_true` | mm/mm | float64 | derived | ln(1+strain) |
| `stress_eng` | MPa | float64 | derived | force/area |
| `stress_true` | MPa | float64 | derived | stress_eng·(1+strain) |
| `temperature` | °C | float64 | optional | |
| `cycle_index` | – | int64 | optional | assigned by segmentation |

Scalar metadata (per test): `area` (mm²), `E` (MPa), `R` (strain ratio), `gauge_length` (mm). Perform the true-stress/true-strain conversion at ingestion: ε_true = ln(1+ε_eng), σ_true = σ_eng·(1+ε_eng).

---

## SECTION 8 — Persistence / save & recall layer

Options and trade-offs:
- **Parquet** — columnar, typed, compressed; best for large per-cycle tables.
- **HDF5** — hierarchical, holds mixed scalars + tables, but a heavier dependency and more failure modes.
- **JSON** — human-readable; ideal for small fitted-parameter sets and metadata.
- **SQLite** — relational, transactional, indexable; ideal for keying/recall across many tests/materials.

**Recommended default:** **SQLite catalog + Parquet per-cycle tables + PNG artifacts on disk.** One SQLite row per test/material holds the scalars, the fitted constants (as a JSON column), the path to the per-cycle Parquet file, the path(s) to plot PNGs, and an input hash. Keep large per-cycle DataFrames in Parquet (path referenced from SQLite); never blob images into the DB.

**Caching / invalidation.** Compute a content hash (e.g. `hashlib.sha256`) over (raw input bytes + analysis parameters: failure criterion %, mean-stress model, fit options). Store the hash with the result; recompute only when the hash changes (content-addressed cache). This makes save/recall deterministic and avoids stale results when inputs or parameters change.

---

## SECTION 9 — Standard LCF plots and conventions

- **Strain-life curve:** Δε/2 vs 2Nf on **log-log** axes; overlay three lines — elastic (σ'f/E)(2Nf)^b, plastic ε'f(2Nf)^c, and total — and mark the transition point 2Nt.
- **Coffin-Manson plot:** log(Δεp/2) vs log(2Nf), linear fit (slope c, intercept ε'f).
- **Basquin plot:** log(Δσ/2) vs log(2Nf), linear fit (slope b, intercept σ'f).
- **Ramberg-Osgood cyclic stress-strain curve:** σ vs ε (linear axes); overlay the **monotonic** tensile curve vs the **cyclic** curve to reveal hardening vs softening.
- **Hysteresis loops:** σ vs ε on linear axes; show a single stabilized loop, overlaid multi-amplitude loops, and first-cycle vs half-life loop.
- **Peak/valley stress vs cycle:** σmax and σmin vs N (linear or semi-log N) — the cyclic hardening/softening trace.
- **Energy density vs cycle:** ΔWp (loop area) vs N.

matplotlib idioms: `ax.set_xscale('log'); ax.set_yscale('log')` for life plots; `ax.plot(eps, sig)` (acquisition order, no sorting) for loops; annotate 2Nt with `ax.axvline`.

---

## SECTION 10 — Engineering stress-strain fundamentals & typical curves

Monotonic tensile test: engineering σ = F/A0, e = ΔL/L0. True stress σ = σ_eng·(1+e); true strain ε = ln(1+e). These conversions are **valid up to necking** (onset of UTS); beyond necking the uniform-deformation assumption fails and true stress requires correction. E is the initial linear slope. Yield strength = 0.2% offset (Rp0.2). UTS = maximum engineering stress. Ductility = elongation or reduction-in-area at fracture. Typical metal curve: linear elastic → yield → strain hardening to UTS → necking → fracture.

**Monotonic ↔ cyclic relationship.** Plot the monotonic and cyclic stress-strain curves together: if the **cyclic curve lies above** the monotonic → cyclic **hardening**; if **below** → cyclic **softening** (ASTM E606 notes this comparison reveals whether hardness, yield, ultimate, and strain-hardening exponent increase, decrease, or stay constant under cyclic straining). Rules of thumb: σ'f ≈ true fracture strength; ε'f ≈ true fracture ductility (approximately); compatibility n' ≈ b/c. Materials with a high monotonic strain-hardening exponent tend to harden cyclically; heavily cold-worked / high-strength materials tend to soften (Manson/Smith-Watson-Topper guidance). These are estimates only — measure cyclic constants where possible.

---

## SECTION 11 — Validation datasets and reference material constants

*Numbers below are transcribed from cited sources; sources disagree by heat — do not average across sources. Use each value with its citation.*

### Golden worked dataset — SAE 1137 carbon steel (recommended regression-test source)

C. R. Williams, Y.-L. Lee, J. T. Rilly (DaimlerChrysler), "A practical method for statistical analysis of strain–life fatigue data," *International Journal of Fatigue* 25 (2003) 427–436, DOI 10.1016/S0142-1123(02)00119-6 (Tables 4 & 5). Strain-controlled per ASTM E606-92, R = −1, failure = **30% load drop**. This source is ideal for golden-value testing because raw → derived → fitted are all published.

Selected per-test derived rows — *total strain amplitude (mm/mm) | half-life stress amplitude (MPa) | E (MPa) | 2Nf (reversals) | elastic strain amp | plastic strain amp*:

| Δε/2 | σa (MPa) | E (MPa) | 2Nf | Δεe/2 | Δεp/2 |
|---|---|---|---|---|---|
| 0.00900 | 553 | 208229 | 4234 | 0.002656 | 0.006344 |
| 0.00700 | 522 | 206850 | 7398 | 0.002523 | 0.004477 |
| 0.00500 | 464 | 208919 | 14768 | 0.002221 | 0.002779 |
| 0.00300 | 405 | 210297 | 77104 | 0.001925 | 0.001075 |
| 0.00200 | 350 | 210298 | 437498 | 0.001663 | 0.000337 |
| 0.00175 | 319 | 206161 | 3327958 | 0.001548 | 0.000202 |

Fitted constants from this dataset: **c = −0.6207**; **ε'f = 1.104** (median; R90C90 design value ε'f = 0.9870); plastic-branch regression intercept 0.06933, slope −1.611, R² = 0.9942; **transition ≈ 22,000 reversals**; **E ≈ 208,000–209,000 MPa**. (σ'f and b are directly recomputable from the published Table 5 elastic data; K' and n' are not separately tabulated in this paper.)

### Tabulated cyclic/fatigue constants for common metals (cite per material)

**eFatigue.com / SAE AE-6 (Wetzel 1977), SAE keyhole benchmark page:**
- **Man-Ten steel (hot rolled):** E = 203,000 MPa; σys = 325 MPa; Su = 565 MPa; σ'f = 915 MPa; b = −0.095; ε'f = 0.26; c = −0.47
- **RQC-100 steel (roller Q&T):** E = 203,000 MPa; σys = 565 MPa; Su = 820 MPa; σ'f = 1160 MPa; b = −0.075; ε'f = 1.06; c = −0.75

**MIT 2.002 OpenCourseWare (Anand & Parks 2004, "Defect-Free Fatigue," Table 3)** — σ'f (MPa), b, ε'f, c (no E/K'/n'):
- **RQC-100:** σ'f = 938; b = −0.0648; ε'f = 0.66; c = −0.69
- **SAE 4340 (Q&T):** σ'f = 1655; b = −0.076; ε'f = 0.73; c = −0.62
- **2024-T351 Al:** σ'f = 1100; b = −0.124; ε'f = 0.22; c = −0.59
- **2024-T4 Al:** σ'f = 1015; b = −0.11; ε'f = 0.21; c = −0.52
- **7075-T6 Al:** σ'f = 1315; b = −0.126; ε'f = 0.19; c = −0.52

**Dowling, *Mechanical Behavior of Materials*, Table 9.1** (σo, σu, σ'f in MPa, b):
- **AISI 4340 (aircraft quality):** σo = 1103; σu = 1172; σ'f = 1758; b = −0.0977
- **2024-T4 Al:** σo = 303; σu = 476; σ'f = 900; b = −0.102
- **Man-Ten:** σo = 322; σu = 557; σ'f = 1089; b = −0.113

**2024-T351 with K'/n' (MDPI *Materials*, PMC6982211):** K' = 1518.1 MPa; n' = 0.1702; σ'f = 1489.8 MPa; b = −0.157; ε'f = 0.4931; c = −1.01 (a different heat — use for cross-checking only).

**SAE 1045 (primary open source):** JoDean Morrow, "Low cycle fatigue behavior of quenched and tempered SAE 1045 steel," Univ. of Illinois TAM Report R277 (hdl.handle.net/2142/111998, openly downloadable via IDEALS): b between −0.07 and −0.08; c between −0.6 and −1.0; σ'f ≈ true fracture strength; the full per-test tables are in that PDF.

**Authoritative print compilations (paywalled; for obtaining per-heat golden values including K'/n'):** **SAE J1099_201808** "Technical Report on Low Cycle Fatigue Properties Ferrous and Non-Ferrous Materials" (saemobilus.sae.org); **Chr. Boller & T. Seeger, *Materials Data for Cyclic Loading*** (Elsevier, Parts A–E + Supplement 1, 1987–1990; Part B Low-Alloy Steels ISBN 978-0-444-42871-4) — each datasheet gives chemical composition, monotonic + cyclic stress-strain curves, strain-life curve, and the SWT parameter-life curve.

**Conflicts flagged (do NOT average — pick one source per material and cite it):** RQC-100 σ'f = 1160 MPa (eFatigue/Wetzel) vs 938 MPa (Dowling/MIT); Man-Ten σ'f = 915 MPa (eFatigue) vs 1089 MPa (Dowling 9.1); 2024-T351 σ'f = 1100 MPa (Dowling/MIT) vs 1489.8 MPa (MDPI heat). eFatigue also shows a minor internal inconsistency for RQC-100 yield (565 MPa in table vs 770 MPa in prose).

**Open raw cyclic (time, strain, force) records:** the University of Illinois IDEALS TAM reports (SAE 1045 and others) are openly downloadable and contain per-test data tables.

---

## SECTION 12 — Implementation decisions & open-question recommendations

- **Failure criterion %:** default to a **configurable percent load-drop from the stabilized (half-life) peak load**; document the chosen value (a common published choice is 30%, as in the SAE 1137 golden dataset). Always persist and report the criterion. (No standard mandates a single value; both E606 and ISO 12106 require it be reported.)
- **Cycle-detection method:** **peak-valley turning-point detection** for constant-amplitude strain control (preserves order); **index-preserving rainflow** (pyLife `FullRecorder`, or `rainflow.extract_cycles` using i_start/i_end) for irregular histories, re-ordered in time to retain per-cycle evolution.
- **Masing / compatibility handling:** **fit K' and n' independently** from stabilized cyclic data; additionally compute the b/c-derived n' and K', and flag divergence (non-Masing). Do not force compatibility.
- **Mean-stress correction default:** **SWT** as the general default; offer **Morrow** (when σ'f / true fracture strength is reliable) and **Walker** (most accurate, when multi-R data exist; γ = 0.5 recovers SWT, and γ ≈ 0.883 − 2×10⁻⁴·σu for steels per Dowling et al. 2009).
- **Storage backend:** **SQLite catalog + Parquet per-cycle tables + PNG artifacts on disk**, with **SHA-256 input-hash** cache invalidation over (raw input + analysis parameters).
- **Canonical input schema:** pandas DataFrame with `time`, `strain`, `force` required and true-stress/true-strain derived at ingestion (ε_true = ln(1+ε_eng), σ_true = σ_eng·(1+ε_eng)); scalars `area`, `E`, `R`, `gauge_length`; mirror pyLife `from`/`to` and py-fatigue vocabulary.
- **NumPy integration call:** use `numpy.trapezoid` (NumPy ≥2.0; `trapz` removed in 2.4.0) or `scipy.integrate.trapezoid` for cross-version safety; prefer the **shoelace polygon area** for closed-loop energy.
- **MCP:** depend on the official **`mcp`** SDK pinned **`>=1.27,<2`** (v2 stable targeted 2026-07-27); use the bundled FastMCP decorator API; **stdio** for local Claude Desktop/Claude Code use and **Streamable HTTP** for remote; pass large arrays via resources/file paths or `structuredContent`, never large inline JSON; expose stored results as MCP resources for the compute/save/recall pattern; test with the MCP Inspector (`mcp dev`).