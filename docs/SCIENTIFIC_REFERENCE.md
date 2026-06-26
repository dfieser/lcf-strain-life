# Scientific reference and validation

A single, maintained record of the physics this toolkit implements. It is meant
for review by a materials or fatigue specialist. Every equation is defined with
its symbols, units, sign conventions, defaults, assumptions, a citation, and a
pointer to the code and the test that checks it.

How to review: read each section, confirm the equation and its defaults match
accepted practice, and record your verdict in the sign-off table at the end. The
research-derived implementation references in `docs/design` carry the original
access-dated source URLs if you want to trace a citation further.

Document status: kept in sync with the code. Last updated 2026-06-26. When an
equation, default, or citation changes, this page must be updated in the same
change.

## Conventions

- True stress and true strain are used everywhere. Engineering input is converted
  at ingestion.
- Stress and modulus are in MPa. Strain is a dimensionless fraction, not a
  percent. Life is in reversals `2N_f`, where one cycle is two reversals.
- The fatigue strength exponent `b` and the fatigue ductility exponent `c` are
  negative.

| Symbol | Meaning | Unit |
|---|---|---|
| σ, ε | true stress, true strain | MPa, dimensionless |
| Δσ/2, Δε/2 | stress amplitude, total strain amplitude | MPa, dimensionless |
| Δε_e/2, Δε_p/2 | elastic, plastic strain amplitude | dimensionless |
| σ_m, σ_max | mean stress, maximum stress | MPa |
| E | Young's modulus | MPa |
| σ'_f, b | fatigue strength coefficient, exponent | MPa, dimensionless |
| ε'_f, c | fatigue ductility coefficient, exponent | dimensionless |
| K', n' | cyclic strength coefficient, strain-hardening exponent | MPa, dimensionless |
| 2N_f | reversals to failure | dimensionless |
| W | cyclic energy density | MJ/m³ |
| K_t, K_f, q | stress concentration, fatigue notch factor, notch sensitivity | dimensionless |

---

## 1. True stress and strain

$$\varepsilon = \ln(1+e), \qquad \sigma = \sigma_\text{eng}(1+e), \qquad \sigma_\text{eng}=F/A_0$$

Valid up to necking. `e` is engineering strain, `A_0` the original area.
Code: `lcf.units`. Test: `tests/test_units.py`.
Reference: Dowling, Mechanical Behavior of Materials, 4th ed., Chapter 4.

## 2. Cyclic stress-strain, Ramberg-Osgood

$$\varepsilon = \frac{\sigma}{E} + \left(\frac{\sigma}{K'}\right)^{1/n'},
\qquad
\Delta\varepsilon = \frac{\Delta\sigma}{E} + 2\left(\frac{\Delta\sigma}{2K'}\right)^{1/n'}$$

The second form is the doubled hysteresis branch (Massing). Fit by linear
regression of `log(Δσ/2)` on `log(Δε_p/2)`.
Code: `lcf.fits.fit_ramberg_osgood`. Test: `tests/test_fits.py`.
Reference: Ramberg and Osgood 1943, NACA TN 902. Dowling 4th ed. Eq. 14.12.

## 3. Strain-life

Basquin, elastic branch:
$$\frac{\Delta\sigma}{2} = \sigma'_f (2N_f)^{b}, \qquad \frac{\Delta\varepsilon_e}{2} = \frac{\sigma'_f}{E}(2N_f)^{b}$$

Coffin-Manson, plastic branch:
$$\frac{\Delta\varepsilon_p}{2} = \varepsilon'_f (2N_f)^{c}$$

Total strain-life:
$$\frac{\Delta\varepsilon}{2} = \frac{\sigma'_f}{E}(2N_f)^{b} + \varepsilon'_f (2N_f)^{c}$$

Transition life, where elastic and plastic amplitudes are equal:
$$2N_t = \left(\frac{\varepsilon'_f E}{\sigma'_f}\right)^{1/(b-c)}$$

Compatibility (Masing), checked and flagged, not forced:
$$n' = \frac{b}{c}, \qquad K' = \frac{\sigma'_f}{(\varepsilon'_f)^{b/c}}$$

The plastic branch is fit over the low cycle regime, excluding near-runout points
whose plastic strain is at measurement noise level.
Code: `lcf.fits`, `lcf.life`. Tests: `tests/test_fits.py`, `tests/test_life.py`.
References: Basquin 1910. Coffin 1954. Manson 1953. Dowling 4th ed. Eq. 14.3 to 14.6.

## 4. Mean-stress corrections

Morrow, elastic term shifted by the mean stress:
$$\frac{\Delta\varepsilon}{2} = \frac{\sigma'_f-\sigma_m}{E}(2N_f)^{b} + \varepsilon'_f (2N_f)^{c}$$

Modified Morrow, both terms shifted:
$$\frac{\Delta\varepsilon}{2} = \frac{\sigma'_f-\sigma_m}{E}(2N_f)^{b} + \varepsilon'_f\left(\frac{\sigma'_f-\sigma_m}{\sigma'_f}\right)^{c/b}(2N_f)^{c}$$

Smith-Watson-Topper:
$$\sigma_{max}\,\frac{\Delta\varepsilon}{2} = \frac{(\sigma'_f)^2}{E}(2N_f)^{2b} + \sigma'_f \varepsilon'_f (2N_f)^{b+c}, \qquad \sigma_{ar} = \sqrt{\sigma_{max}\,\sigma_a}$$

Walker, with the equivalent fully-reversed amplitude:
$$\sigma_{ar} = \sigma_{max}^{\,1-\gamma}\,\sigma_a^{\,\gamma}, \qquad \gamma_{steel} = 0.8818 - 2.00\times10^{-4}\,\sigma_u$$

Morrow equivalent fully-reversed amplitude:
$$\sigma_{ar} = \frac{\sigma_a}{1 - \sigma_m/\sigma'_f}$$

Default for variable amplitude is SWT, no extra constant needed. Walker `γ` is in
`(0, 1]`, and `γ = 0.5` recovers SWT.
Code: `lcf.meanstress`, `lcf.life`. Tests: `tests/test_meanstress.py`.
References: Morrow 1968. Smith, Watson, Topper 1970, J. Materials 5(4):767-778.
Walker 1970. Dowling, Calhoun, Arcari 2009, Fatigue Fract. Eng. Mater. Struct.
(steel γ). Dowling 4th ed. Eq. 9.18 to 9.21.

## 5. Hysteresis energy and cyclic response

Plastic strain energy density per cycle is the closed loop area:
$$W = \oint \sigma\,d\varepsilon$$

Computed by the shoelace polygon area on the ordered loop points. With stress in
MPa and strain a fraction, the area is in MJ/m³ directly. Tension-compression
asymmetry is `R_TC = |σ_max| / |σ_min|`.
Code: `lcf.energy`, `lcf.metrics`. Tests: `tests/test_energy.py`, `tests/test_metrics.py`.

## 6. Variable amplitude, rainflow counting

Three-point rainflow counting per ASTM E1049, preserving the original sample
indices of every counted cycle so per-cycle evolution is retained. An optional
repeat-history closure rotates the reversal sequence to the global maximum.
Code: `lcf.counting`. Test: `tests/test_counting.py`.
References: ASTM E1049-85(2017). Downing and Socie 1982. Matsuishi and Endo 1968.

## 7. Cumulative damage

Palmgren-Miner, the default, failure at the critical sum:
$$D = \sum_i \frac{n_i}{N_{f,i}}, \qquad D_{crit} = 1 \text{ by default}$$

Double Linear Damage Rule, Manson-Halford, with the knee fraction of Phase I life
referenced to the longest life in the spectrum:
$$f_I = 0.35\left(\frac{N_f}{N_{long}}\right)^{0.25}, \qquad N_I = N_f f_I, \quad N_{II} = N_f(1-f_I)$$

Phase I accumulates to `D_crit`, then Phase II accumulates to `D_crit`.

Corten-Dolan:
$$N = \frac{N_{f,1}}{\sum_i \alpha_i (\sigma_i/\sigma_1)^{d}}$$

where `σ_1` is the maximum stress, `N_{f,1}` its life, `α_i` the cycle fractions,
and `d` the Corten-Dolan exponent. When `d` equals the inverse S-N slope this
reduces exactly to Miner.
Code: `lcf.damage`. Test: `tests/test_damage.py`.
References: Palmgren 1924. Miner 1945. Manson and Halford 1981, Int. J. Fracture
17:169-192. Corten and Dolan 1956.

## 8. Notch local-strain approach

Neuber, combined with the cyclic Ramberg-Osgood curve:
$$\frac{(K_t S)^2}{E} = \sigma\,\varepsilon, \qquad \text{range form } \frac{(K_t \Delta S)^2}{E} = \Delta\sigma\,\Delta\varepsilon$$

Glinka, equivalent strain energy density:
$$\frac{(K_t S)^2}{2E} = \frac{\sigma^2}{2E} + \frac{\sigma}{n'+1}\left(\frac{\sigma}{K'}\right)^{1/n'}$$

Fatigue notch factor and notch sensitivity:
$$K_f^{Peterson} = 1 + \frac{K_t-1}{1+a/r}, \quad K_f^{Neuber} = 1 + \frac{K_t-1}{1+\sqrt{\beta/r}}, \quad q = \frac{K_f-1}{K_t-1}$$

Neuber is the default and is conservative. Glinka predicts a lower local strain.
Code: `lcf.notch`. Test: `tests/test_notch.py`.
References: Neuber 1961, J. Appl. Mech. 28:544-550. Molski and Glinka 1981,
Mater. Sci. Eng. 50:93-100. Peterson 1974. Dowling 4th ed. Chapter 14.

## 9. Statistics and design curves

Linearized regression, life as the dependent variable:
$$\log_{10} N = A + B \log_{10}(\Delta\varepsilon/2)$$

Confidence interval on the mean line and prediction interval for a future point
use the residual standard error and the Student t quantile, with the variance
factor `1/n + (x-\bar x)^2/S_{xx}` for confidence and `1 + 1/n + (x-\bar x)^2/S_{xx}`
for prediction. The one-sided tolerance factor `k` is the Owen factor from the
noncentral t. The design (reliability-confidence) life is the mean reduced by
`k·s` in log life. Right-censored runouts are handled by maximum likelihood, not
deletion.
Code: `lcf.stats`. Test: `tests/test_stats.py`.
References: ASTM E739-10(2015), withdrawn 2024, used as the de facto reference.
Owen 1963, Technometrics. Williams, Lee, Rilly 2003, Int. J. Fatigue 25:427-436.

## 10. Elevated temperature

Frequency-modified Coffin-Manson coefficient (Solomon and Engelmaier coefficient
form):
$$C_f = C_o\left(\frac{f}{f_{ref}}\right)^{k-1}, \qquad \frac{\Delta\varepsilon_p}{2} = C_f (2N_f)^{c}$$

Linear time-fraction creep-fatigue damage:
$$D = \sum_i \frac{n_i}{N_{f,i}} + \sum_j \frac{t_j}{t_{r,j}}$$

checked against a bilinear creep-fatigue interaction envelope (D-diagram) from
`(1,0)` through a material knee to `(0,1)`. Strain-life constants are interpolated
in temperature, linearly for exponents and the modulus, log-linearly for
coefficients.
Code: `lcf.hightemp`. Test: `tests/test_hightemp.py`.
References: Coffin 1971, Metall. Trans. 2:3105. Robinson 1952 (time fraction).
ASTM E2714-13(2020). ASME and RCC-MR creep-fatigue envelopes.

## 11. Multiaxial, survey only

Critical-plane parameters, provided for evaluation once the plane quantities are
known. The tensor engine and rotating-plane search are deferred to a later phase.
$$P_{FS} = \frac{\Delta\gamma_{max}}{2}\left(1 + k\frac{\sigma_{n,max}}{\sigma_y}\right), \quad
P_{BM} = \frac{\Delta\gamma_{max}}{2} + S\,\Delta\varepsilon_n, \quad
P_{SWT} = \sigma_{n,max}\frac{\Delta\varepsilon_1}{2}$$

Code: `lcf.multiaxial`. Test: `tests/test_multiaxial.py`.
References: Fatemi and Socie 1988, Fatigue Fract. Eng. Mater. Struct. 11(3):149-165.
Brown and Miller 1973. Smith, Watson, Topper 1970. Socie and Marquis 2000,
Multiaxial Fatigue, SAE.

---

## Validation evidence

Each row is a published worked example reproduced by an automated test. The
numbers are checked on every test run.

| What is validated | Source | Expected | Test |
|---|---|---|---|
| Coffin-Manson c, ε'_f, transition | Williams, Lee, Rilly 2003 (SAE 1137) | c ≈ −0.62, ε'_f ≈ 1.1, 2N_t ≈ 22,000 | `test_fits.py` |
| Rainflow cycles and binned totals | ASTM E1049 worked example | exact path table | `test_counting.py` |
| Miner block life | Lee et al. (Golden D) | 0.057 per block, 17.5 blocks | `test_damage.py` |
| DLDR two-phase life | Lee et al. (Golden C) | 11.5 blocks | `test_damage.py` |
| Manson-Halford knee | NASA TM (Golden) | Phase I life ≈ 111 | `test_damage.py` |
| Neuber local stress, strain, life | Lee et al. 2005 (SAE 1005) | σ ≈ 182 MPa, ε ≈ 0.00170, 2N_f ≈ 1.08e5 | `test_notch.py` |
| Owen one-sided tolerance factor | standard tables | k(10, R90, C95) = 2.355 | `test_stats.py` |
| Design-curve reduction | Williams, Lee, Rilly 2003 | R90C90 ≈ 22,300 from R50 23,700 | `test_stats.py` |
| Creep-fatigue time fraction | ANL (Golden H) | sum of fatigue and creep fractions | `test_hightemp.py` |

## Assumptions and limitations

- True stress-strain conversion is valid up to necking.
- The plastic strain amplitude uses the computed form `Δε_t/2 − Δσ/(2E)`.
- Miner ignores load sequence. Use the DLDR for strong high-low ordering.
- The Manson-Halford phase split uses the standard knee constants 0.35 and 0.25.
- Neuber tends to overestimate and Glinka to underestimate local strain, the
  measured value usually lies between them.
- The Owen factor returned is the standard one-sided tolerance factor. The
  Williams design-curve value uses a separate construction, documented in the
  stats tests.
- The multiaxial module is survey-only. It is not exposed as an MCP tool.
- Some cited constants from secondary sources are flagged as unverified in the
  research references, for example Man-Ten K' and n'.

## Defaults and their justification

| Choice | Default | Why |
|---|---|---|
| Failure criterion | 30% load drop from the half-life peak | matches the SAE 1137 validation set, common practice |
| Mean stress for spectra | SWT | parameter-free, robust |
| Notch rule | Neuber | conservative |
| Damage rule | Miner, D_crit = 1 | standard baseline |
| Plastic-branch fit floor | exclude near-runout points | the plastic line is only meaningful in the low cycle regime |

## Standards referenced and status

| Standard | Topic | Status |
|---|---|---|
| ASTM E606 | strain-controlled fatigue testing | current |
| ISO 12106 | axial strain-controlled method | current |
| ASTM E1049 | rainflow cycle counting | current |
| ASTM E739 | statistical analysis of fatigue data | withdrawn 2024, used as de facto |
| ASTM E2714 | creep-fatigue testing | current |

## Reviewer sign-off

Reviewer name and date at the top, then a verdict per section. Suggested verdicts:
OK, OK with note, or needs change.

| Section | Verdict | Reviewer note |
|---|---|---|
| 1 True stress and strain | | |
| 2 Ramberg-Osgood | | |
| 3 Strain-life | | |
| 4 Mean-stress corrections | | |
| 5 Energy and cyclic response | | |
| 6 Rainflow counting | | |
| 7 Cumulative damage | | |
| 8 Notch local-strain | | |
| 9 Statistics and design curves | | |
| 10 Elevated temperature | | |
| 11 Multiaxial survey | | |
| Validation evidence | | |
| Defaults | | |

## Maintenance

This page is part of the source of truth for the science. Any change to an
equation, a default, or a citation must update this page in the same commit, and
the matching test must still pass. Citations here are at author, year, and venue
level. The access-dated source URLs are in the research references under
`docs/design`.
