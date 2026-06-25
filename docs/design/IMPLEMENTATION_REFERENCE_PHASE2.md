# Phase 2 Engineering Reference: Variable-Amplitude, Damage, Notch, Statistics, Elevated-Temperature, and Multiaxial Survey for the LCF Strain-Life Tool

Reference date: 2026-06-24. All library and standard facts are version-stamped. Anything that may change after this date is flagged.

## Table of Contents
1. Variable-amplitude loading and order-preserving cycle counting
2. Cumulative damage
2a. Notch effects and local-strain approach
3. Statistical analysis and uncertainty (post-E739)
4. Elevated-temperature, creep-fatigue, and TMF
5. Multiaxial fatigue (survey only)
6. Python ecosystem, algorithms, and API currency
7. Mapping to existing architecture
8. Implementation decisions, module map, and Phase-3 candidates

---

## 1. Variable-amplitude loading and order-preserving cycle counting

### 1.1 Standard
Rainflow counting is specified in ASTM E1049-85, "Standard Practices for Cycle Counting in Fatigue Analysis," current reapproval E1049-85(2017) (store.astm.org/e1049-85r17.html, accessed 2026-06-24). It defines level-crossing, peak, simple-range, range-pair, and rainflow methods. The Downing and Socie (1982) algorithm is the one embodied in E1049. Rychlik (1987) gave the method a rigorous mathematical definition (International Journal of Fatigue, 1987).

### 1.2 Algorithm (three-point, E1049 form)
1. Reduce the history to turning points (peaks/valleys); discard non-turning points.
2. Read successive points; track three consecutive ranges. Let X be the most recent range, Y the previous range.
3. If X >= Y and Y contains the starting point, count Y as a half cycle and discard its first point.
4. If X >= Y and Y does not contain the start, count Y as a full cycle and discard both interior points.
5. Continue; whatever remains is the residue, counted as half cycles.

Material memory: closed loops correspond to interior hysteresis loops; the larger enclosing range "remembers" its path across the smaller closed loops. Residue handling: E1049 leaves residual half cycles; common practice closes the residue by concatenating the residue with a copy of itself (repeating-history assumption) so the largest range closes as a full cycle. State this assumption explicitly in the tool. (Standard-mandated: the counting rules. Common practice: the residue-doubling closure.)

### 1.3 Index preservation (critical for per-cycle evolution)
To retain per-cycle stress/strain evolution you must keep the original sample indices of each counted cycle's turning points.
- `rainflow` (PyPI, v3.2.0, released 2023-04-17, MIT, requires Python >=3.7): `extract_cycles(series)` yields `(rng, mean, count, i_start, i_end)` tuples. The `i_start`/`i_end` are indices into the input series. This is the simplest index-preserving option (pypi.org/project/rainflow, accessed 2026-06-24).
- pyLife (readthedocs, stable 2.3.0; latest 2.3.1, accessed 2026-06-24): `ThreePointDetector` and `FourPointDetector` report sample index; pair with `FullRecorder`, which "records additionally to the from and to values also the indices of the loop turning points in the original time series, so that additional data like temperature during the loop or dwell times can be looked up." `FKMDetector` (Clormann and Seeger, recommended by FKM) does NOT report sample index. NaN values are dropped before turn detection and invalidate indices, so clean NaNs first. pyLife is Apache-2.0; the docs note the pylife-1.x API survives only as discouraged wrappers, so target the 2.x API.
- fatpack (PyPI v0.7.8, requires numpy, MIT): `find_rainflow_ranges` and `find_rainflow_matrix`; four-point algorithm. Maintenance flagged Inactive as of 21 June 2025 (snyk.io advisor, accessed 2026-06-24). Returns ranges/cycles but index preservation is weaker than the two above.

Recommendation: use `rainflow.extract_cycles` as the default index-preserving counter (it is one library-specific feature, well tested, MIT). Use pyLife when chunked/streaming counting or the FKM detector is needed.

### 1.4 Bridging counted history to strain-life
For each counted cycle i with local stress turning points (from index-preserved counting):
- strain amplitude Δε_i/2 from the two turning strains;
- mean stress σ_m,i = (σ_max,i + σ_min,i)/2;
- apply a mean-stress correction (Section 2.3) to get an equivalent fully-reversed amplitude;
- invert the strain-life curve for N_f,i (reuse Phase 1 life solver);
- accumulate damage (Section 2).

### 1.5 VALIDATION (regression golden data)
**Golden A — classic ASTM-style sequence.** Input series `[-2, 1, -3, 5, -1, 3, -4, 4, -2]`. This sequence appears in the `ffpack` docs (`astmRainflowCounting`) and the `pawelkn/rainflow` C++ port (github.com, accessed 2026-06-24). The C++ port with a 2.0 bin returns: {range 2: 0.0}, {4: 2.0}, {6: 0.5}, {8: 1.0}, {10: 0.5}, each cycle carrying `start_index` and `end_index`. Use the exact library output for the chosen version as the regression baseline and pin the library version.

**Golden B — Tom Irvine / vibrationdata worked example** (vibrationdata.com/tutorials2/rainflow_counting_revB.pdf, Rev B, 2018-10-04, accessed 2026-06-24), explicitly an implementation of the ASTM E1049 example. Path cycles:

| Path | Cycles | Range | Peak | Valley | Mean |
|------|--------|-------|------|--------|------|
| A-B | 0.5 | 3 | 1 | -2 | -0.5 |
| B-C | 0.5 | 4 | 1 | -3 | -1 |
| C-D | 0.5 | 8 | 5 | -3 | 1 |
| D-G | 0.5 | 9 | 5 | -4 | 0.5 |
| E-F | 1.0 | 4 | 3 | -1 | 1 |
| G-H | 0.5 | 8 | 4 | -4 | 0 |
| H-I | 0.5 | 6 | 4 | -2 | 1 |

Binned totals: range 9 → 0.5; range 8 → 1.0; range 6 → 0.5; range 4 → 1.5; range 3 → 0.5. Exact ranges, counts, and means usable as a regression fixture (E-F is counted as one full cycle because it contains part of F-G).

---

## 2. Cumulative damage

### 2.1 Palmgren-Miner linear rule
D = Σ (n_i / N_f,i). Failure assumed at D = 1. Applied to strain-life by computing N_f,i per counted cycle from the (mean-corrected) strain-life curve. Empirically the critical sum at failure scatters: Miner's own tests gave 0.61 to 1.45, and Engineers Edge ("Miner's Rule Linear Damage Rule," engineersedge.com, accessed 2026-06-24) adds that "other researchers have shown variations as large as 0.18 to 23.0, with most results tending to fall between 0.5 and 2.0." Quadco Engineering's Palmgren-Miner overview (quadco.engineering, accessed 2026-06-24) states the typical range is "about 0.7 to 2.2, depending on the material, load spectrum and environmental conditions."

Design-code allowable damage sums (standard-mandated, distinct from the empirical scatter above):
- IIW/Eurocode 3: allowable damage sum is 1 for in-phase loading and 0.5 for out-of-phase loading, per Ng et al., Fatigue Fract. Eng. Mater. Struct. 47(7):2616-2649 (2024), doi:10.1111/ffe.14319 ("IIW is 1 for in-phase fatigue loading and 0.5 for out-of-phase fatigue loading").
- DNV RP-C203: fatigue damage is summed using Miner's rule, typically requiring ΣD_i ≤ 1.0 (DNV RP-C203 summary, accessed 2026-06-24).

Key limitation: load-sequence insensitivity. Miner's rule treats high-low and low-high orderings identically, while real damage is order-dependent.

### 2.2 Nonlinear / sequence-sensitive models
**Double Linear Damage Rule (Manson-Halford, 1981)** (NTRS 19810049119; Springer Int. J. Fracture, doi:10.1007/BF00053519, accessed 2026-06-24). Splits life into Phase I and Phase II, each summed linearly. Phase I is summed using Phase-I lives until ΣnI/NI = 1, then Phase II until ΣnII/NII = 1, when failure occurs. The knee point depends on the life ratio N1,f/N2,f, not on a physical crack-initiation/propagation split (the authors later dropped that interpretation). Requires no extra material constants beyond the S-N/ε-N curve, which makes it the most practical sequence-sensitive option.

**Damage Curve Approach (Manson-Halford)**: a single nonlinear equation, D = Σ (n_i/N_f,i)^(α_i) where the exponent depends on the life level; failure when D = 1.

**Corten-Dolan**: a modified power-law summation for sequence effects.

**FKM elementary/consequent Miner** variants modify treatment of cycles below the fatigue limit (relevant only when a fatigue limit is modeled; LCF strain-life usually has none).

### 2.3 Mean-stress correction per counted cycle (apply BEFORE damage)
Reuse Phase 1 corrections. For each counted cycle convert (σ_a, σ_m) to an equivalent fully-reversed amplitude or directly into a corrected life:
- Morrow: ε_a = ((σ'f − σ_m)/E)(2N)^b + ε'f(2N)^c
- SWT: σ_max · ε_a = (σ'f²/E)(2N)^(2b) + σ'f ε'f (2N)^(b+c)
- Walker with the Dowling steel γ estimate (Phase 1).
Then compute n_i/N_f,i and sum.

### 2.4 VALIDATION (worked spectrum example)
**Golden C — DLDR two-level worked example** (ScienceDirect "Miner Linear Damage Rule" topic page, from Lee et al. "Fatigue Testing and Analysis," accessed 2026-06-24): a two-block history gives Phase I damage per block 0.2134 and Phase II damage per block 0.1463, so blocks to complete Phase I = 1/0.2134 = 4.7 and Phase II = 1/0.1463 = 6.8, total = 11.5 blocks to failure. This is a citable, exact DLDR regression fixture.

**Golden D — simple Miner block example** (ScienceDirect Palmgren-Miner overview, accessed 2026-06-24): a three-week loading block produced cumulative damage 0.057 per block, so 1/0.057 = 17.7 blocks (about 53 weeks) to failure. Use as a Miner regression check.

---

## 2a. Notch effects and local-strain approach

### 2a.1 Neuber's rule
Neuber: Kt² = Kσ · Kε, equivalently (for nominally elastic loading) (Kt·S)²/E = σ·ε, where S is nominal stress and σ, ε are local notch stress and strain. Combined with the cyclic Ramberg-Osgood curve ε = σ/E + (σ/K')^(1/n'):

σ·[σ/E + (σ/K')^(1/n')] = (Kt·S)²/E

a single nonlinear equation in σ, solved by Newton iteration; then ε from Ramberg-Osgood. For ranges (hysteresis branch), use the doubled curve: Δε = Δσ/E + 2(Δσ/(2K'))^(1/n') with (Kt·ΔS)²/E = Δσ·Δε (modified Neuber for reversals). Altair's FEMFAT note (altair.com, accessed 2026-06-24) records that for one steel case (Kt/α = 2.15, notch radius 0.7 mm) the Neuber method gives useful local-stress results up to about 0.6% plastic strain, beyond which a nonlinear material law is preferred; Neuber is recommended for localized plastification only.

### 2a.2 Glinka ESED rule
Glinka (Molski-Glinka) equivalent strain energy density: the strain energy density at the notch root computed elastically equals that computed elastic-plastically. For the monotonic curve:

(Kt·S)²/(2E) = σ²/(2E) + (σ/(n'+1))·(σ/K')^(1/n')

Glinka generally predicts lower local strain than Neuber. Neuber "normally overestimates the notch root strains, while the ESED method tends to underestimate" them (ScienceDirect, doi:10.1016/S0142-1123(03)00245-7; Wiley ffe.13540, accessed 2026-06-24); measured strains usually lie between the two. Mathematically, Neuber's rule is the special case of ESED in which plastic-strain-energy dissipation at the notch root is neglected.

When to prefer: Neuber for localized plasticity and a conservative estimate; Glinka/ESED when Neuber is too conservative and the plastic zone is small and embedded in elastic material. Recommended default: Neuber, with ESED available as an option.

### 2a.3 Kt, Kf, notch sensitivity q
- Kt: theoretical (elastic) stress concentration factor (geometry only).
- Kf: fatigue notch factor (effect on fatigue strength), Kf <= Kt.
- q = (Kf − 1)/(Kt − 1), notch sensitivity, 0 <= q <= 1.
- Peterson: Kf = 1 + (Kt − 1)/(1 + a/r), with a a material constant and r notch radius.
- Neuber: Kf = 1 + (Kt − 1)/(1 + sqrt(β/r)), with β a material length.
Peterson a and Neuber β correlate with ultimate strength for steels.

### 2a.4 Full workflow
nominal load history → (Kt, Neuber/Glinka + Ramberg-Osgood, with memory) → local stress-strain history → rainflow on local strain → per-cycle (Δε/2, σ_m) → mean-stress correction → strain-life N_f → Miner/DLDR damage. (This is the chain Topper, Morrow, and Wetzel established and that Dowling's 2005 ASIP paper formalizes with (Kt·S)²/E = σ·ε plus the strain-life equation; asipcon.com/.../0330_Dowling.pdf, accessed 2026-06-24.)

### 2a.5 VALIDATION (worked Neuber example)
**Golden E — SAE 1005 constants (verified verbatim)** from Lee, Pan, Hathaway, Barkey, "Fatigue Testing and Analysis: Theory and Practice," Elsevier Butterworth-Heinemann 2005, Ch. 5 worked notched-plate example (indexed at sciencedirect.com/topics/engineering/notched-plate, accessed 2026-06-24): E = 207,000 MPa, Su = 320 MPa, K' = 1240 MPa, n' = 0.27, σ'f = 886 MPa, b = −0.14, ε'f = 0.28, c = −0.5, plate Kt = 2.53.

Computed self-contained regression case (R = −1, nominal amplitude S = 100 MPa, computed by this reference from those verified constants):
- Neuber constant (Kt·S)²/E = (253)²/207000 = 0.3092 MPa
- Solve σ·(σ/E + (σ/K')^(1/n')) = 0.3092 → local σ_a ≈ 182 MPa, ε_a ≈ 0.00170
- Strain-life (886/207000)·(2N)^−0.14 + 0.28·(2N)^−0.5 = 0.00170 → 2N_f ≈ 1.08e5 reversals, N_f ≈ 5.4e4 cycles.

Flag: the local σ, ε, and life here are computed by this reference from the verified published input constants, not transcribed from the book's tables. Lock them as a self-consistent regression baseline (recompute with your solver to the same tolerance). The input constant set (E, Su, K', n', σ'f, b, ε'f, c, Kt) is confirmed verbatim and safe to hard-code.

**Golden F — eFatigue SAE keyhole anchor** (efatigue.com/benchmarks/SAE_keyhole, accessed 2026-06-24): Man-Ten steel (E = 203,000 MPa, σ'f = 915 MPa, b = −0.095, ε'f = 0.26, c = −0.47), Kt = 3, with nominal-stress relation S(MPa) = 11.2·P(kN). Specimen CR1 at nominal S = 149 MPa → strain-life prediction 211,000 cycles (stress-life 418,000; experimental 605,000 cycles to a 2.5 mm crack; FEM-based strain-life 217,100). Use as an end-to-end anchor that bundles SWT mean-stress handling. Note eFatigue does not publish K'/n' for Man-Ten; commonly used SAE/Landgraf cyclic values are K' ≈ 1162 MPa, n' ≈ 0.193, which must be verified against Landgraf/Mitchell/Endo before locking as expected outputs.

Additional verified set for a second material — RQC-100 (eFatigue): E = 203,000 MPa, σ'f = 1160 MPa, b = −0.075, ε'f = 1.06, c = −0.75.

---

## 3. Statistical analysis and uncertainty (post-E739)

### 3.1 Standard status
ASTM E739, "Standard Guide for Statistical Analysis of Linear or Linearized Stress-Life (S-N) and Strain-Life (ε-N) Fatigue Data," last edition E739-23, was WITHDRAWN in 2024 (ASTM E08.04 subcommittee jurisdiction page; store.astm.org/standards/e739, accessed 2026-06-24). A reapproval-with-editorial-change work item WK83149 exists. As of 2026-06-24 there is no superseding ASTM standard; the withdrawn E739-23 text remains the de facto reference for the linearized regression method, and ASME BPV design-curve practice (factor of 20 on life, or 2 to 2.5 on stress, whichever is more conservative) is the standard-mandated alternative in pressure-vessel work (NRC NUREG/CR-6815; Wiley ffe.14545, accessed 2026-06-24). Flag: confirm whether WK83149 reapproves E739 after 2026-06-24.

### 3.2 Regression treatment
E739 fits log(life) as the dependent variable on log(stress or strain): ln N = A + B·ln(Δε/2). Life is the random/dependent variable (this is the correct orientation; do not regress stress on life). Watch heteroscedasticity (scatter varies along the curve); E739 assumes constant variance of log-life within the fitted interval. Do not extrapolate beyond the tested interval and do not estimate below about the fifth percentile (E739 §1.1 caution, retained verbatim in the withdrawn text). Best practice (Williams et al., below) restricts each linear regression to one regime: LCF/plastic-dominant for the ductility parameters (ε'f, c), HCF/elastic-dominant for the strength parameters (σ'f, b), split at the transition life.

### 3.3 Confidence vs prediction intervals
- Confidence interval: on the fitted line (mean response).
- Prediction interval: on a future single observation (wider).
Compute via standard linear-regression formulas using the residual standard error s and t quantiles; the interval half-width scales with sqrt(1/n + (x−x̄)²/Sxx) for confidence and sqrt(1 + 1/n + (x−x̄)²/Sxx) for prediction.

### 3.4 Design curves and R90C90/R95C90
Design value = mean − k·s where k is a one-sided tolerance factor (Owen). R90C90 = 90% reliability (survival) with 90% confidence; R95C90 = 95% reliability, 90% confidence. The Owen one-sided tolerance factor depends on n, the reliability, and the confidence. Shen and Wirsching modified the Owen tolerance limit for fatigue design curves to handle nonlinear heteroscedastic data with runouts (ASME J. Eng. Mater. Technol. 118(4):535, 1996, accessed 2026-06-24). The Tridello review (Wiley ffe.14545, 2025, accessed 2026-06-24) confirms the combined Owen one-sided-tolerance-limit-plus-staircase method as a current R90C90 design-curve practice.

### 3.5 VALIDATION (published fitted curve + design values)
**Golden G — Williams, Lee, Rilly, "A practical method for statistical analysis of strain-life fatigue data," Int. J. Fatigue 25 (2003) 427-436, doi:10.1016/S0142-1123(02)00119-6** (accessed 2026-06-24). For SAE 1137 steel, sample size n = 8, the Owen tolerance factor K = 2.608 and the regression standard error s = 0.03011; total strain-life R50 = 23,700 reversals and R90C90 = 22,300 reversals. This is a complete, citable design-curve regression fixture. The same paper fixes the plastic-strain-amplitude threshold at 0.0005 mm/mm (below which data are dropped for measurement error) and recommends a minimum of 20 uniaxial specimens over a strain range 0.01-0.001 mm/mm. The paper aligns with but refines ASTM E739-91.

### 3.6 Censored data (runouts)
E739 itself does not treat runouts. Recommended: maximum-likelihood estimation with right-censored observations (random fatigue-limit model, Pascual-Meeker), or the Shen-Wirsching modified-Owen approach, which explicitly accommodates runouts and heteroscedastic data. Implement via survival/MLE (lifelines, or a custom scipy MLE), not by deleting runouts.

### 3.7 Sample-size / replicate guidance
E739 gave percent-replication and per-level specimen guidance keyed to test type (preliminary, research, design allowables). Current practice (Williams et al.) recommends a minimum of 20 specimens for a sound statistical strain-life fit.

---

## 4. Elevated-temperature, creep-fatigue, and TMF

### 4.1 Frequency-modified Coffin-Manson (Coffin 1971)
Coffin introduced a frequency term into the plastic strain-life relation (Coffin, Metallurgical Transactions 2, 1971, pp. 3105-3113). In the form used in the unified creep-fatigue literature (ScienceDirect "A unified equation for creep-fatigue," doi:10.1016/j.ijfatigue.2014.05.012, accessed 2026-06-24): the Coffin-Manson ductility coefficient becomes a function of cyclic frequency, C_f = C_o · f^(k−1), so Δε_p/2 = C_f (2N_f)^β0 with β0 only a weak function of frequency for eutectic SnPb solder. Lower frequency and longer hold reduce life at high temperature. Temperature and frequency dependence enter through the coefficients and exponents. Solomon, Shi, Engelmaier, and Jing variants embed temperature in the coefficient and/or exponent (IntechOpen "A Unified Creep-Fatigue Equation," accessed 2026-06-24).

### 4.2 Creep-fatigue interaction
ASTM E2714-13(2020), "Standard Test Method for Creep-Fatigue Testing," is current as of 2026-06-24 (astm.org/Standards/E2714.htm). A revision work item WK97543 is in progress (removes the E467 dynamic-force-verification requirement, keeping E4 verification, aligning with E2368-25). E2714 notes there is no single standard prescribing creep-fatigue procedure; it sits alongside E606, ISO 12106, ISO 12111, and E2368.

Linear time-fraction (Robinson) plus Miner damage summation:

D_total = D_fatigue + D_creep = Σ (n_i/N_f,i) + Σ (t_j/t_r,j)

failure when D_total reaches the code envelope value (ANL-19/13, publications.anl.gov/anlpubs/2019/04/151507.pdf; ScienceDirect "Linear Damage Accumulation," accessed 2026-06-24). Ductility-exhaustion (British R5) is the main alternative. The creep-fatigue interaction (D-diagram) plots (D_f, D_c); inside the bilinear envelope passes, outside fails; ASME and RCC-MR use different intersection points per material. The linear rule does not distinguish tensile from compressive holds; for many materials compressive holds cause no creep damage, so the method is then conservative. Dwell time increases the creep fraction.

### 4.3 TMF
ASTM E2368-24/25, "Standard Practice for Strain Controlled Thermomechanical Fatigue Testing," and ISO 12111:2011 (strain-controlled TMF of uniaxial metallic specimens) are current (astm.org; iso.org; zwickroell.com; instron.com, accessed 2026-06-24). In-phase (IP): maximum mechanical strain coincides with maximum temperature (creep-dominated). Out-of-phase (OP): maximum strain at minimum temperature (often more damaging for many alloys, fatigue/oxidation-driven). TMF life is generally lower than isothermal LCF at the same mechanical strain range. Common life model: Neu-Sehitoglu damage summation, D = D_fatigue + D_creep + D_oxidation. Strain-life constants become temperature-dependent: store σ'f(T), ε'f(T), b(T), c(T), E(T) as tables and interpolate (linear in T, or in log space for the coefficients).

### 4.4 VALIDATION (creep-fatigue / temperature-dependent constants)
**Golden H — time-fraction worked structure** (ANL-19/13, accessed 2026-06-24; also USPTO 7949479 impeller example): total fractional damage = n1/N1 + n2/N2 + n3/N3 + t4/H4 + t5/H5 + t6/H6, failure when the sum exceeds 1. Use as a structural regression fixture for the time-fraction summation. For 304 stainless steel the linear rule is shown conservative (measured lives exceed calculated; ScienceDirect "Linear Damage Accumulation," accessed 2026-06-24).

**Temperature-dependent constants fixture** — Hastelloy X Coffin-Manson parameters tested at 430, 650, and 816 C with loading frequencies 0.001 and 10 cpm (Sente Software, "Modelling the strain-life relationship," sentesoftware.co.uk, accessed 2026-06-24): at 650 C, 0.001 cpm the strain amplitude is 0.02% at 100 cycles and 0.0005% at 1,000,000 cycles; b and c are held temperature-independent there while the frequency effect is strong at 650 and 816 C and weak at 430 C. Use as a temperature/frequency interpolation fixture.

---

## 5. Multiaxial fatigue (survey only)

### 5.1 Critical-plane strain-life methods
- **Fatemi-Socie (FS)** (Fatigue Fract. Eng. Mater. Struct. 11(3):149-165, 1988): shear-based, for shear-cracking (Mode II) materials. Parameter (Δγ_max/2)(1 + k·σ_n,max/σ_y), correlated to a shear strain-life curve. The normal-stress term captures additional cyclic hardening under non-proportional loading. Required inputs: maximum shear strain amplitude, maximum normal stress on that plane, σ_y, and the material constant k. Correlated 1045 HR steel and Inconel 718 axial-torsional data within a factor of about two.
- **Brown-Miller / Kandil-Brown-Miller** (Fatigue Fract. Eng. Mater. Struct. 1(2):217-229, 1979): Δγ_max/2 + S·Δε_n on the maximum-shear plane, correlated via a Coffin-Manson-type curve. Wang-Brown (1993) extended it with a Morrow-type mean-stress correction and made it path-independent for variable amplitude.
- **Smith-Watson-Topper (multiaxial)** (J. Mater. 5(4):767-778, 1970): σ_n,max · Δε_1/2 on the maximum-principal-strain plane; for tensile (Mode I) cracking materials.

### 5.2 Equivalent-strain approaches
von Mises or maximum-shear equivalent strain reduces multiaxial to uniaxial. Simple but cannot handle non-proportional loading or normal-stress/mean-stress effects, and gives no crack-plane information. Use only for proportional-loading screening.

### 5.3 Recommendation for a later phase
Implement Fatemi-Socie first (best general coverage for ductile metals, handles non-proportional hardening), then SWT for brittle/tensile-cracking materials. Required additional inputs: full stress and strain tensors (or multiaxial channels), a plane search over candidate angles, shear strain-life constants (τ'f, γ'f, b0, c0) or estimates from the axial constants, σ_y, and the FS constant k. Note that FS, WB, and Findley each carry one or more extra material constants that vary with life and require fitting (MDPI Materials 10(8):923, accessed 2026-06-24). Reference text: Socie and Marquis, "Multiaxial Fatigue" (SAE, 2000).

---

## 6. Python ecosystem, algorithms, and API currency

### 6.1 Libraries (version-stamped 2026-06-24)
| Library | Version | License | Coverage | Index-preserving rainflow |
|---|---|---|---|---|
| rainflow | 3.2.0 (2023-04-17) | MIT | E1049 counting | Yes (`extract_cycles` i_start/i_end) |
| pyLife | 2.3.0 stable / 2.3.1 latest | Apache-2.0 | counting, mean-stress, damage, Wöhler/load histograms | Yes (ThreePoint/FourPoint + FullRecorder) |
| fatpack | 0.7.8 | MIT | counting, endurance curves, Miner sum | Partial; maintenance Inactive (2025) |
| ffpack | 0.x active | OSI-approved | ASTM counting, Palmgren-Miner (and "naive") damage, load-sequence generation | Counting yes |

Recommendation: use `rainflow` for simple index-preserving counting; use pyLife where the richer recorder/histogram, chunked counting, or FKM detector is wanted. Implement Neuber/Glinka, DLDR, statistics, and creep-fatigue in-house (no single library covers them well). pyLife requires Python >= 3.9 / pandas >= 2.2 but the docs strongly recommend Python >= 3.11 and pandas 3.0.

### 6.2 Numerical methods
- Neuber root-finding: `scipy.optimize.brentq` (robust, bracketed) or `newton` on f(σ) = σ(σ/E + (σ/K')^(1/n')) − (Kt·S)²/E; bracket σ in (0, Kt·S). Glinka uses the same bracket on its energy equation.
- Damage accumulation: vectorize with numpy; compute the N_f array per cycle, then D = Σ n_i/N_f,i; for DLDR, run two vectorized passes (Phase I lives, then Phase II lives).
- Interval estimation: statsmodels OLS for confidence/prediction intervals; scipy.stats for t and Owen factors; custom MLE or lifelines for censored fits.

### 6.3 Core scientific stack (2026-06-24)
- NumPy: 2.4.1 (2026-01-10) is the latest stable feature line; 2.5.0 published 2026-06-21 adds CPython 3.14 wheels (numpy.org/news; pypi.org/project/numpy, accessed 2026-06-24).
- pandas: 3.0.x stable (3.0.0 released 2026-01-21), with a PyArrow-backed string dtype default and copy-on-write; 2.3 (2025-06-05) is the prior line (pandas.pydata.org, accessed 2026-06-24).
- SciPy: 1.16.0 (2025-06-22) current; 1.17.0 expected 2026-01-10 (scientific-python.org SPEC 0, accessed 2026-06-24).
These are materially newer than typical pins; the pandas 3.0 string-dtype and copy-on-write changes can break code that checks for object dtype or mutates views, so test against 3.0 explicitly.

### 6.4 MCP SDK currency
As of 2026-06-24 the stable line is MCP Python SDK v1.x; latest published is mcp 1.28.0 (pypi.org/project/mcp, accessed 2026-06-24). v2 is in alpha: v2.0.0a1 published 2026-06-11; beta targeted 2026-06-30; stable v2 targeted 2026-07-27; the MCP spec release candidate is dated 2026-07-28 and contains breaking changes (github.com/modelcontextprotocol/python-sdk; modelcontextprotocol blog via contextstudios.ai, accessed 2026-06-24). Installers do not select pre-releases unless explicitly pinned. v2 replaces the `FastMCP` class with a new `McpServer` class and moves to stateless protocol routing.

Decision on the `mcp>=1.27,<2` pin: KEEP it. The official README explicitly recommends adding a `<2` upper bound (example `mcp>=1.27,<2`) before stable v2 lands, and v1.x remains recommended for production. Because stable v2 (2026-07-27) and the breaking spec (2026-07-28) both fall AFTER 2026-06-24, do not move to v2 in Phase 2. Plan a separate migration branch pinned to a v2 pre-release. For a FastMCP stdio server, `mcp.run(transport="stdio")` and `@mcp.tool()` with Pydantic schema inference remain valid in v1.x; structured output is on by default for tools whose return-type annotation classifies as structured and can be suppressed with `structured_output=False` on the decorator (unstructured results are still returned for backward compatibility). Flag: re-verify after 2026-07-27 whether v2 is stable and whether the pin should move; expect to migrate `FastMCP` → `McpServer`.

---

## 7. Mapping to existing architecture

### 7.1 New modules (reuse Phase 1 fits/life/meanstress/metrics)
- `counting/` (or `rainflow/`): wraps `rainflow.extract_cycles` with index preservation; residue closure (repeat-history); returns per-cycle (range, mean, i_start, i_end, σ_max, σ_min).
- `damage/`: Miner, DLDR (Manson-Halford), Corten-Dolan; takes counted cycles + strain-life curve + mean-stress option; returns D, blocks/cycles to failure.
- `notch/`: Neuber and Glinka solvers (scipy root-finding) on the cyclic Ramberg-Osgood curve; Kt/Kf/q (Peterson, Neuber); nominal→local history with material memory.
- `stats/`: E739-style log-life regression, confidence/prediction intervals, Owen R90C90/R95C90 design curves (Shen-Wirsching), censored MLE.
- `hightemp/`: frequency-modified Coffin-Manson; time-fraction creep-fatigue summation with D-diagram envelope; temperature-dependent constant tables + interpolation.
- `multiaxial/` (stub): FS/BM/SWT damage-parameter functions and a plane-search interface (survey only this phase).

### 7.2 New MCP tools (compute/save/recall pattern)
- `count_rainflow(history, options)` → cycles table with indices; plus `save_rainflow`, `recall_rainflow`.
- `compute_damage(cycles, curve, mean_stress_method, rule)` → D, life; persist.
- `compute_notch_local(nominal_history, Kt, cyclic_props, method)` → local stress-strain history; persist.
- `fit_design_curve(data, reliability, confidence, censoring)` → constants + intervals + R90C90 values; persist.
- `compute_creep_fatigue(cycles, holds, temp_props)` → D_f, D_c, envelope check; persist.

### 7.3 Schema changes
Add: temperature (per-cycle or per-history), a nominal-vs-local stress flag, Kt/Kf, cyclic K'/n' if not already present, hold-time/frequency fields, and (for the multiaxial stub) optional multiaxial channels (σ_xx, σ_yy, τ_xy or the full tensor). Keep the uniaxial path as the default so Phase 1 behavior is unchanged.

---

## 8. Implementation decisions, module map, and Phase-3 candidates

### 8.1 Recommended defaults (and switch conditions)
- Damage model: Palmgren-Miner with D_crit = 1 default. Switch to DLDR (Manson-Halford) when the spectrum has strong high-low ordering or when validation shows non-conservative Miner predictions; drop D_crit to 0.5 for out-of-phase / code-driven work (IIW, EC3, DNV).
- Notch rule: Neuber default (conservative). Switch to Glinka/ESED when Neuber is overly conservative and plasticity is small and embedded, or above ~0.6% local plastic strain consider a full nonlinear law.
- Design-curve method: Owen one-sided tolerance factor (Shen-Wirsching modified) for R90C90. Switch to ASME factor-of-20-on-life / 2-on-stress for pressure-vessel code compliance.
- Censored data: maximum-likelihood with right-censoring; never delete runouts.
- Creep-fatigue: linear time-fraction (Robinson + Miner) summation with a material D-diagram envelope. Switch to ductility-exhaustion (R5) for low-creep-ductility alloys or where the linear rule is known non-conservative.
- Mean stress: SWT default for variable amplitude (robust, no extra constant); Morrow/Walker available; switch to Walker when a fitted γ exists for the material.

### 8.2 Module/tool map
As in Section 7. Reuse Phase 1 fits (Basquin σ'f,b; Coffin-Manson ε'f,c; Ramberg-Osgood K',n'), life inversion, mean-stress corrections, and per-cycle metrics throughout.

### 8.3 Phase-3 ranked candidates
1. Full multiaxial critical-plane (Fatemi-Socie first, then SWT/Brown-Miller) with plane search and tensor input.
2. Probabilistic/Bayesian strain-life fitting with full uncertainty propagation to life.
3. Full TMF life model (Neu-Sehitoglu) with oxidation and creep damage terms.
4. Crack-growth (E647-style da/dN) coupling for total-life prediction.
5. Variable-temperature per-cycle interpolation integrated directly into counting.

### 8.4 Currency flags to re-check after 2026-06-24
- MCP v2 stable (targeted 2026-07-27) and breaking spec RC (2026-07-28): plan the FastMCP → McpServer migration and revisit the `<2` pin.
- ASTM E739 reapproval status (work item WK83149).
- ASTM E2714 revision (work item WK97543).
- NumPy 2.5.0 (2026-06-21) / SciPy 1.17 / pandas 3.0 compatibility under the chosen pins.

---

### Source-class notes (standard-mandated vs common-practice vs one-library-specific)
- Standard-mandated: ASTM E1049 counting rules; E2714/E2368/ISO 12111 test methods; ASME BPV design-curve factors; IIW/EC3/DNV allowable damage sums.
- Common-practice (not standard-mandated): residue-doubling closure; SWT-default mean-stress; Neuber-default notch rule; DLDR for sequence effects; Shen-Wirsching Owen design curves; linear time-fraction creep-fatigue.
- One-library-specific: `rainflow.extract_cycles` i_start/i_end; pyLife FullRecorder index recording and detector taxonomy; fatpack TriLinearEnduranceCurve; FastMCP `@mcp.tool()` structured-output behavior.
- Conflicts/uncertainty flagged in-text: Man-Ten K'/n' (unverified, ~1162 MPa / 0.193); Golden E local σ/ε/life computed (not transcribed); E739 future reapproval; MCP v2 timing; the Miner critical-sum scatter range differs by source (0.61-1.45, 0.5-2.0, 0.7-2.2, extremes 0.18-23.0).