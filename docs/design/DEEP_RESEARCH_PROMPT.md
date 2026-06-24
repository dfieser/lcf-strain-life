<!--
This file IS the prompt. Paste everything below the line into your deep research agent.
It is self-contained (no repo access assumed). Output is a single markdown document.
-->

---

# Deep Research Task: Implementation Reference for a Low Cycle Fatigue (LCF) Analysis Tool

## Who is asking and why this matters

Your output will be consumed by **Claude Code, an AI coding agent**, as the *single authoritative reference* for building a software project. I am not a human skimming for an overview — I will implement directly against the facts, numbers, code patterns, and citations you provide. Optimize for **precision, density, and verifiability**, not readability or narrative. No marketing, no filler, no hedging prose.

Deliver **one single, self-contained Markdown document**.

### Weight your effort toward my blind spots

I have strong general knowledge of the textbook fatigue equations and of NumPy/SciPy/pandas basics — you can be brief there. Spend your research budget where I am weak or unreliable:

1. **Time-sensitive API specifics.** My training has a cutoff; library and SDK APIs may have changed. I need *current, version-stamped* facts — especially the **Model Context Protocol (MCP) Python SDK**.
2. **Things I must not invent.** **Numerical validation data** (real worked examples and published material constants with their source) so I can write tests with known-correct answers. I cannot fabricate these reliably; you must source them with citations.
3. **Convention and edge-case correctness.** Where the standards or the field have specific conventions (signs, units, definitions, failure criteria, fitting procedure) that are easy to get subtly wrong.

For each major claim, give an **inline citation**: source name, URL, and version/date (plus your access date). Prefer primary/authoritative sources: ASTM/ISO standards, official SDK/library documentation, peer-reviewed literature, and official data compilations. When sources conflict or you are uncertain, **say so explicitly** and present the options. Distinguish clearly between *standard-mandated*, *common practice*, and *one-library-specific* conventions.

---

## Project context (what is being built)

A **general-purpose, material-agnostic Python tool** that automates Low Cycle Fatigue (LCF) strain-life analysis so any researcher can drop in their own test data and reproduce a standardized analysis. It ships as:

- a **core Python library** (the science), and
- an **MCP server** wrapping it so AI agents can call the analysis conversationally.

**Interaction model — "compute, save, recall":** dedicated functions compute each quantity, results are persisted keyed to a test, and users/agents recall stored quantities later without recomputation.

**Design decisions already made (do not re-litigate; research to support them):**
- **All analysis uses true stress / true strain.** Raw input is usually *engineering*; convert at ingestion via `ε_true = ln(1+ε_eng)`, `σ_true = σ_eng·(1+ε_eng)`.
- **pandas is the core data container**, and the tool should be **input-compatible with the `pyLife` and `py-fatigue` ecosystems** (mirror their data shapes/vocabulary).
- Typical raw input: a time series table of `(time, strain, force)` plus scalar parameters (cross-sectional area, Young's modulus, strain ratio R, gauge length).
- The analysis pipeline: **ingest/normalize → cycle reduction → per-cycle metrics → multi-test strain-life fits → save/recall.**
- Models in scope: **Basquin** (elastic strain-life), **Coffin-Manson** (plastic strain-life), **Ramberg-Osgood** (cyclic stress-strain curve), **Morrow** (and other mean-stress corrections), **hysteresis loop energy density**, **cyclic hardening/softening** and **tension/compression asymmetry**.

**Explicitly OUT of scope** (do not spend budget here, except where noted as a boundary): high-cycle fatigue durability workflows (S-N/Wöhler → Miner damage accumulation), fracture-mechanics crack-growth (Paris law), and any specific alloy's materials-science narrative. **Boundary note:** rainflow counting (ASTM E1049) is out of scope *as a primary method* (it discards cycle order, which we need), but **is** relevant to one open question — see §3 below.

---

## Required sections and research questions

Structure the output with the numbered sections below, a table of contents, and a final "Implementation decisions & open-question recommendations" section. Within each section, lead with the concrete facts/tables/code I need.

### 1. Standards and authoritative data-reduction conventions
- Summarize the **data-reduction requirements** relevant to constant-amplitude, strain-controlled LCF from: **ASTM E606/E606M** (strain-controlled fatigue testing), **ASTM E739** (statistical analysis of linearized stress-life and strain-life fatigue data), and **ISO 12106**. Cite specific clauses where possible.
- Give the **precise, standard definitions** (and any competing conventions) for:
  - **Stabilized / half-life cycle** — how it is defined and selected.
  - **Plastic strain amplitude (Δε_p/2)** — measured as loop width at zero stress vs. computed as `Δε_t/2 − Δσ/(2E)`; which is standard, and the practical difference.
  - **Reversals vs. cycles** (2N_f vs N_f) and reversal counting for a controlled waveform.
  - **Failure criterion / N_f** — load-drop percentage conventions (e.g., X% drop from stabilized peak load), modulus-drop, and alternatives. Give the **commonly used default %**.
- Note standard **sign conventions** (b, c negative) and **units conventions** used in practice.

### 2. The strain-life model set — formulas, fitting, and pitfalls
- Restate the canonical equations with consistent symbols: total strain-life (Basquin + Coffin-Manson superposition), Basquin, Coffin-Manson, Ramberg-Osgood (and its linearized plastic form). Confirm the exact algebraic forms and the relationship `Δε_e/2 = Δσ/(2E)`.
- **Fitting methodology** (this is where I most need rigor):
  - Per ASTM E739, is the standard fit a **log-log linear least-squares** regression on each branch, or **nonlinear least squares** on the combined curve? What is the recommended dependent/independent variable assignment and any required **weighting**?
  - How is the **elastic/plastic transition life (2N_t)** computed and used?
  - **Masing vs. non-Masing** behavior and the **compatibility relations** `n' = b/c` and `K' = σ'_f/(ε'_f)^(b/c)`: are these *enforced* or *checked*? When do real materials violate them, and should K'/n' be fit **independently** or **derived**? Recommend a default.
  - Goodness-of-fit and uncertainty: R², confidence intervals on coefficients/exponents per E739, and outlier handling.
- **Mean-stress corrections:** give exact formulas and the typical use/default for **Morrow**, **modified Morrow**, **Smith-Watson-Topper (SWT)**, and **Walker** (including how the Walker exponent γ is obtained). State which is recommended as a default and why.
- **Hysteresis energy:** numerical convention for loop **area** (`∮σ dε`); the distinction between **plastic strain energy density** and total; unit handling; and (briefly) note any **energy-based life models** (e.g., plastic strain energy vs. life) in case we extend.

### 3. Cycle detection and segmentation for strain-controlled data
- For **constant-amplitude, fully-reversed** strain control, what is the standard way to segment the continuous `(t, ε, σ)` stream into individual cycles and extract per-cycle peak/valley? (Reversal/peak-valley detection on the command waveform.)
- For **irregular/variable-amplitude** strain histories, would **rainflow (ASTM E1049-85)** be the appropriate cycle-detection method *even though we keep order*? Describe how rainflow could be used for **detection only** while preserving per-cycle evolution, and whether established libraries expose that. (This resolves an open design question.)
- Practical algorithms/library functions for peak-valley extraction, hysteresis-loop closure, and de-noising of lab data.

### 4. Model Context Protocol (MCP) — current Python implementation guide  ⟵ HIGH PRIORITY
Treat this as possibly-changed-since-my-cutoff and report **current** facts with **version numbers and dates**:
- The **official MCP Python SDK**: current package name, version, install command, and the canonical **server** authoring pattern (the FastMCP-style decorator API or its current equivalent). Provide a **minimal but complete, copy-pasteable server example** defining a tool.
- How tools declare **inputs and outputs**: type hints / **pydantic** models → JSON schema, docstrings → tool descriptions, and the current support for **structured output** / structured content.
- **Passing numerical arrays** (e.g., thousands of stress/strain samples) through MCP tool calls: recommended patterns (inline JSON arrays vs. file paths vs. resources), and any size/serialization limits.
- **Returning rich artifacts**: how to return **plots/images** (e.g., PNG of a hysteresis loop or strain-life curve) and tabular results from a tool, per the current spec.
- **Stateful servers / persistence**: idiomatic patterns for a server that **saves results and recalls them** across calls (our compute/save/recall model) — session/state handling, and using **MCP resources** to expose stored datasets/results.
- **Transports** (stdio vs. streamable HTTP) and how an MCP server is **configured and consumed by Claude Code / Claude Desktop** today (config file location and shape).
- Current **best practices and known gotchas**: tool granularity/naming, error reporting, input validation, long-running computations, and testing an MCP server locally (inspector/tooling).
- Briefly note the **packaging** convention for a single installable package exposing both a library and an MCP server entry point (e.g., `pyproject.toml`, console-script / `__main__`).

### 5. Python fatigue ecosystem — data models and interop  ⟵ verify current
- For **pyLife** (Bosch) and **py-fatigue** (OWI-Lab), and also **fatpack** and any other maintained options: current **version, license, scope**, and **exact data-model details** I must mirror:
  - pandas **signal-accessor / column vocabulary** for load collectives and hysteresis loops (`from`/`to`, `range`/`mean`, `amplitude`, `meanstress`, `R`, `cycles`), Wöhler/curve object fields, and the **constructor signatures** (e.g., `CycleCount.from_timeseries(...)`, `from_rainflow(...)`).
  - Confirm these names/signatures against **current docs** (mine may be stale) and flag any changes.
- Explicitly map **what these libraries do and do NOT provide for strain-life LCF**, confirming our differentiator (per-cycle evolution + Coffin-Manson/Basquin/Ramberg-Osgood fits). Note anything reusable (e.g., their rainflow, their plotting, their data containers).

### 6. Numerical implementation idioms (SciPy / NumPy / pandas)
For each computation, give the **specific recommended function(s) and signature(s)**, plus gotchas:
- Loop **area integration**: `numpy.trapezoid`/`trapz` vs `scipy.integrate.simpson` for a closed, possibly noisy loop; handling of non-monotonic, self-intersecting paths; sign of the closed integral.
- **Power-law fits**: log-log `scipy.stats.linregress` / `numpy.polyfit` vs `scipy.optimize.curve_fit` on the native form; how to recover coefficients and their standard errors; pitfalls of log-transform bias.
- **Elastic-slope / Young's-modulus** estimation from loop data when E is not supplied.
- Confirm the **current** function names (e.g., `numpy.trapezoid` deprecation/rename status) with version notes.

### 7. Input file formats from real LCF test machines
- Typical **export formats and column schemas** from common systems (e.g., MTS TestSuite, Instron Bluehill, generic CSV/TSV): usual column names, units, headers/metadata blocks, sampling conventions, and how raw `(time, strain, force/load)` is represented.
- Recommend a **canonical internal input schema** (column names, units, dtypes, required vs optional) that can ingest these with minimal user reshaping and aligns with the pyLife/py-fatigue conventions in §5.

### 8. Persistence / "save & recall" layer
- Idiomatic, lightweight options for persisting computed results keyed by test/material in scientific-Python tooling: **Parquet, HDF5, JSON, SQLite** — with trade-offs for our case (mixed scalars, per-cycle tables, fitted-parameter sets, and small plot artifacts).
- Recommended **caching / invalidation** pattern so a stored result is recomputed only when its inputs/parameters change (e.g., input hashing). Give a concrete recommended default.

### 9. Standard LCF plots and conventions
- The **canonical plot set** and how each is conventionally drawn (axes, linear/log scales, what is overlaid):
  - Strain-life curve (Δε/2 vs 2N_f, log-log, with **elastic + plastic + total** lines and the transition point).
  - Coffin-Manson and Basquin log-log fit plots.
  - Ramberg-Osgood **cyclic stress-strain curve** (and monotonic vs. cyclic overlay).
  - **Hysteresis loops** (single and overlaid multi-amplitude; first vs half-life).
  - **Peak/valley stress vs. cycle** (hardening/softening), and **energy density vs. cycle**.
- Brief matplotlib idioms for these, if helpful.

### 10. Engineering stress-strain fundamentals & typical curves (monotonic context)
- A concise reference on the **monotonic tensile test**: engineering vs. true stress-strain (formulas, validity limit at necking), determination of **elastic modulus, yield strength (0.2% offset), UTS, ductility**, and the **typical shape** of metal stress-strain curves.
- How **monotonic** properties relate to **cyclic** ones: **cyclic hardening vs. softening** (and how to tell from monotonic-vs-cyclic curve comparison), and any rules of thumb relating monotonic strength/ductility to the cyclic fatigue coefficients. This grounds the LCF analysis in the basic engineering analysis a user will expect.

### 11. Validation datasets and reference material constants  ⟵ HIGH PRIORITY (cannot be invented)
I need **known-correct numbers to test against**. Provide as much as you can, each fully cited:
- At least one (ideally several) **fully worked numeric example** of strain-life data reduction: the **input** (strain amplitudes, corresponding stress amplitudes, plastic strain amplitudes, reversals-to-failure for each test) **and** the **resulting fitted constants** (σ'_f, b, ε'_f, c, K', n', E). These become golden-value regression tests — exact numbers and units matter.
- **Tabulated cyclic/fatigue properties** for common engineering metals (e.g., steels, aluminum alloys) from authoritative compilations such as **SAE J1099**, **Boller & Seeger (Materials Data for Cyclic Loading)**, **MMPDS**, **ASM Handbook**, or `pyLife`/`py-fatigue` example datasets: list E, σ'_f, b, ε'_f, c, K', n' with the source for each.
- If any **open datasets** of raw cyclic `(time, strain, force)` LCF records exist publicly, point to them (with license).
- Clearly label every number with **units** and its **citation**; do not synthesize or interpolate values.

---

## Output requirements (recap)
- **One** self-contained Markdown document with a table of contents and the numbered sections above.
- Inline citations (source, URL, version/date, access date) for every non-obvious claim; **version-stamp** all API/library facts and flag anything that may have changed recently.
- Concrete over abstract: real function signatures, copy-pasteable code, numeric tables with units.
- Call out conflicts, uncertainty, and the *type* of each convention (standard vs. common-practice vs. library-specific).
- End with **"Implementation decisions & open-question recommendations"** giving a concrete recommended default for each open question (failure criterion %, cycle-detection method, Masing/compatibility handling, mean-stress correction default, storage backend, canonical input schema).
