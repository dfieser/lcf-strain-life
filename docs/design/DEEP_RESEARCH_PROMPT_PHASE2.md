<!--
This file IS the Phase-2 prompt. Paste everything below the line into your deep
research agent. It is self-contained (no repo access assumed). Output is a single
markdown document. It deliberately builds ON the Phase-1 reference (already
implemented) and must NOT re-derive the basics covered there.
-->

---

# Deep Research Task (Phase 2): From Material Strain-Life Data to Component Life — Variable Amplitude, Notches, Statistics, and High Temperature

## Who is asking and why this matters

Your output will be consumed by **Claude Code, an AI coding agent**, as the *single authoritative reference* for the **next phase** of an existing, working Low Cycle Fatigue (LCF) strain-life tool (Python library + MCP server). I implement directly against the facts, formulas, numbers, and citations you provide. Optimize for **precision, density, and verifiability** — no marketing, no filler, no restating textbook basics I already have.

Deliver **one single, self-contained Markdown document.**

### What already exists (Phase 1 — do NOT re-derive these)

A validated v0.1 already implements, in Python (numpy/scipy/pandas/pydantic/matplotlib) with an MCP server:

- **True stress/strain** convention and engineering→true conversion.
- **Cycle reduction** for constant-amplitude strain control (turning-point detection, half-life, %-load-drop `N_f`).
- **Per-cycle metrics**: stress/mean/total/elastic/plastic amplitudes, T/C ratio, hysteresis energy (shoelace loop area).
- **Strain-life fits**: Basquin (σ′f, b), Coffin-Manson (ε′f, c), Ramberg-Osgood (K′, n′), transition life, Masing consistency check — log-log regression + optional nonlinear refinement.
- **Mean-stress corrections** (single cycle): Morrow, modified Morrow, SWT, Walker (γ incl. Dowling steel estimate).
- **Life prediction**: invert the combined strain-life curve; Basquin and SWT life solvers.
- **Persistence** (SQLite + Parquet) compute/save/recall, and **plots** (strain-life, Coffin-Manson, Basquin, cyclic stress-strain, hysteresis, peak/valley, energy).
- Golden-validated against published SAE 1137 data (c≈−0.62, ε′f≈1.1, transition≈22k reversals).

**So: assume all of the above is done and correct.** Phase 2 is the engineering layer that sits on top, plus statistical rigor and elevated-temperature scope.

### Weight your effort toward my blind spots (priority order)

1. **HIGH — Validation data I must not invent.** Worked numeric examples *with inputs and answers* for each new method (a rainflow count of a standard sequence; a Miner-damage spectrum→life calculation; a Neuber notch local-strain→life calculation; a design-curve / confidence-interval calculation). These become regression tests. Cite each.
2. **HIGH — Current method/standard status.** Especially the **statistics** area: ASTM E739 was *withdrawn (Jan 2024)*; tell me what current standards/methods replace it and the modern recommended practice. Also current status of creep-fatigue (E2714) and any TMF standards.
3. **HIGH — Software/library currency since 2026-06-24.** Re-verify the MCP Python SDK (is v2 stable now? — v2 stable was targeted 2026-07-27; if released, what changes for a FastMCP server and our `mcp>=1.27,<2` pin?), and current Python rainflow/fatigue libraries with versions.
4. **MEDIUM — Method formulas and conventions** (signs, factors, where each applies, recommended defaults).

For every non-obvious claim give an **inline citation**: source name, URL, version/date, and your access date. Prefer ASTM/ISO, peer-reviewed literature, authoritative texts (Dowling; Stephens *Metal Fatigue in Engineering*; Socie & Marquis *Multiaxial Fatigue*), and official library docs. Flag conflicts/uncertainty explicitly and distinguish *standard-mandated* vs *common-practice* vs *one-library-specific*.

### Scope boundaries (keep me focused)
- Still **uniaxial strain-life** at the core, **material-agnostic**, feeding the **same library + MCP architecture**. Stress-life/HCF-durability remains secondary.
- **Multiaxial fatigue is a SURVEY-ONLY section** this phase (enough to scope a future phase), not full depth.
- Don't re-cover the Phase-1 basics listed above except where a Phase-2 method modifies them.

---

## Required sections and research questions

Use the numbered structure below, a table of contents, and a final "Implementation decisions, module map, and Phase-3 candidates" section. Lead each section with concrete facts/formulas/tables, then the validation data.

### 1. Variable-amplitude loading & order-preserving cycle counting
- **Rainflow (ASTM E1049-85)**: give the precise algorithm and, critically, how to **preserve original cycle order / sample indices** so per-cycle evolution is retained (our differentiator). Confirm which current Python libraries expose index-preserving rainflow (pyLife `FullRecorder`, `rainflow` `extract_cycles` i_start/i_end, fatpack) — with **current versions**.
- **Material memory effect** and residue handling: how the load-history memory rule works, and how residual half-cycles are closed (E1049 residue rules).
- How to bridge a counted variable-amplitude history to the **strain-life** model (per-cycle Δε/2, mean stress per cycle).
- **Validation:** the standard E1049 example sequence (or a widely-published one) with its exact rainflow count (ranges/means/counts) so I can regression-test the counter.

### 2. Cumulative damage
- **Palmgren-Miner linear rule** applied to strain-life (Σ nᵢ/Nfᵢ = D), the critical-damage-sum convention (D=1 vs scatter), and its known limitations (load-sequence insensitivity).
- **Nonlinear / sequence-sensitive models**: double-linear damage rule (Manson-Halford), Corten-Dolan, and any current recommended damage model — formulas, parameters, when to use, recommended default.
- How mean-stress correction (Morrow/SWT/Walker) is applied **per counted cycle** before computing damage.
- **Validation:** a worked spectrum-loading example (a block/variable history → per-cycle damage → predicted blocks/cycles to failure) with the published answer.

### 2a. Notch effects & the local-strain approach
- **Neuber's rule** and **Glinka's ESED (equivalent strain energy density)** rule: exact forms relating nominal stress to local notch stress/strain via Kt (and the cyclic stress-strain / Ramberg-Osgood curve we already fit). When each is preferred.
- **Stress concentration vs fatigue notch factor**: Kt, Kf, notch sensitivity q; **Kf estimation** (Peterson, Neuber relations) with the material constants involved.
- The full **nominal-load → local strain history → strain-life damage** workflow.
- **Validation:** a worked Neuber (or Glinka) notch example — given Kt, nominal stress, and material constants, the published local stress/strain and predicted life.

### 3. Statistical analysis & uncertainty (post-E739)
- ASTM E739 is **withdrawn**; what is the **current recommended practice** and any replacement standard/guide for linearized strain-life statistics? Summarize.
- **Confidence vs prediction intervals** on the fitted constants and on the strain-life curve; the correct regression treatment (which variable is dependent; heteroscedasticity).
- **Design curves**: mean − k·σ, and the **R90C90 / R95C90** (reliability-confidence) design-value methodology — exact factors and how to compute them.
- **Censored data (runouts)**: maximum-likelihood handling of suspended/runout tests in strain-life (or stress-life) fitting; recommended method.
- **Sample-size / replicate guidance** (what E739 recommended and current practice).
- **Validation:** a dataset with the published fitted curve **and** its confidence/prediction intervals or design-curve values, so I can regression-test the statistics.

### 4. Elevated-temperature, creep-fatigue, and thermomechanical fatigue (TMF)
*(The source domain of this project is high-temperature alloys, so this is in-scope.)*
- **Frequency-modified Coffin-Manson** (Coffin) and other time/frequency-dependent strain-life forms — formulas and parameters.
- **Creep-fatigue interaction**: ASTM E2714 (current status), the **time-fraction (linear damage summation)** and **ductility-exhaustion** approaches, and the creep-fatigue **damage diagram** (envelope). Dwell-time effects.
- **TMF**: in-phase vs out-of-phase, how TMF life differs from isothermal LCF, and the common life models (e.g., damage-summation / Neu-Sehitoglu overview at a citable level).
- How temperature enters our existing constants (temperature-dependent σ′f, ε′f, b, c, E) and how to store/interpolate them.
- **Validation:** any worked creep-fatigue (time-fraction) life example or tabulated temperature-dependent strain-life constants for a common alloy, cited.

### 5. Multiaxial fatigue — SURVEY ONLY (to scope a later phase)
- Brief, citable survey of **critical-plane** strain-life methods: **Fatemi-Socie**, **Brown-Miller**, **Smith-Watson-Topper (multiaxial)** — the damage parameters and what inputs they need.
- Equivalent-strain (von Mises / max shear) approaches and their limits.
- A recommendation: which method(s) a future phase should implement first, and what additional inputs/data they require. **Do not go deep** — one section, enough to plan.

### 6. Python ecosystem, algorithms & API currency (re-verify; version-stamp)
- Current maintained Python libraries for: rainflow counting, cumulative damage, notch/local-strain, and fatigue statistics — names, **versions**, licenses, what they do/don't cover vs. our needs, and what is reusable.
- Recommended **numerical methods** for the new pieces (e.g., Neuber's rule root-finding with the Ramberg-Osgood curve; damage accumulation vectorization; interval estimation in scipy/statsmodels).
- **MCP SDK currency:** is `mcp` v2 stable now (was targeted 2026-07-27)? If so, what changes for a `FastMCP` stdio server and structured output, and should the `mcp>=1.27,<2` pin move? Re-verify numpy/scipy/pandas latest if materially changed.

### 7. Mapping to the existing architecture
- Propose the **new modules** and where they sit (suggested: `rainflow`/`counting`, `damage`, `notch`, `stats`, `hightemp`, and a `multiaxial` stub), reusing existing `fits`/`life`/`meanstress`/`metrics`.
- Propose the **new MCP tools** (names, inputs/outputs) following the existing compute/save/recall pattern, and what new persisted quantities they produce.
- Note any changes needed to the canonical input schema (e.g., temperature, nominal-vs-local stress, multiaxial channels).

---

## Output requirements (recap)
- **One** self-contained Markdown document; table of contents; the numbered sections above.
- Inline citations (source, URL, version/date, access date) for every non-obvious claim; **version-stamp** all library/SDK facts and flag anything that changed since 2026-06-24.
- Concrete over abstract: exact formulas (watch signs/factors), real function signatures, copy-pasteable snippets, numeric tables **with units**.
- For each major method, give a **"recommended default"** and the conditions under which to switch.
- Provide **validation/golden data** for §1, §2, §2a, §3 at minimum (the regression-test anchors I cannot invent).
- End with **"Implementation decisions, module map, and Phase-3 candidates"**: a concrete recommended default for each open question (damage model, Neuber vs Glinka, design-curve method, censored-data method, creep-fatigue approach), the proposed module/tool map, and a short ranked list of what a Phase 3 should tackle (e.g., full multiaxial).
