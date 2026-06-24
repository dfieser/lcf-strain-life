# Low Cycle Fatigue (LCF) — Analysis Notes

These notes define the **generalized analysis pipeline** our tool automates. The aim is *not* to
reproduce any specific paper or material; it is to let any scientist feed in their own LCF test data
and get the standard reduced quantities, fitted parameters, and plots back.

> **Convention: use true stress and true strain throughout.**
> All equations, fits, and energy integrals below assume true stress (σ) and true strain (ε), not
> engineering values. If a user supplies engineering data, convert before any analysis:
> - True strain: `ε_true = ln(1 + ε_eng)`
> - True stress: `σ_true = σ_eng · (1 + ε_eng)`
>
> (Valid up to necking / uniform deformation; for fully reversed LCF the per-cycle loops are used
> directly, but the conversion still applies to any engineering-referenced input.)

---

## 1. Inputs (what a user provides)

For each LCF test, run at a given **strain amplitude** (Δε/2), the analysis needs:

- **Hysteresis data** — true stress σ vs. true strain ε, sampled through each cycle (at minimum the
  cycles needed for: first loop, peak-hardened loop, and half-life loop).
- **Per-cycle peak stresses** — max (tension) and min (compression) stress for each cycle.
- **Reversals to failure**, `2N_f` (i.e., `2 × N_f`), for each test.
- **Young's modulus**, `E`, for the material (or derive from the elastic slope of a loop).

A complete study is several such tests at different strain amplitudes; the parameter fits (§4–6)
require **at least 2 amplitudes**, and are only meaningful with 3+.

---

## 2. Cyclic energy density (hysteresis loop area)

Energy dissipated per cycle = area enclosed by one true stress–strain loop:

$$W=\oint \sigma(\varepsilon)\,d\varepsilon$$

Computed numerically as the closed-loop integral (e.g., shoelace / trapezoidal area of the ordered
loop points).

**Unit handling — must be explicit.** The result is energy density (J/m³). Report in **MJ/m³**.
Watch the input units:

- σ in **Pa**, ε **dimensionless (fraction)** → W in **J/m³** → ÷10⁶ for MJ/m³.
- σ in **GPa**, ε in **percent** → raw product is **10× MJ/m³** (since 10⁹ Pa × 0.01 = 10⁷ J/m³),
  so multiply the integral by 10 to get MJ/m³.

The safe path: normalize all inputs to SI (Pa, fraction) at ingestion, integrate, then convert once.

**Reported energy metrics per test:**
- Peak-hardened energy density (max over cycles).
- Half-life (steady-state) energy density.
- Difference (half-life − peak-hardened), with sign indicating net softening (−) or hardening (+).
- Report mean ± std when replicate specimens exist.

---

## 3. Cyclic response curves

From per-cycle peak stresses (no fitting required):

- **Hardening/softening curve** — max and min stress vs. cycle number. Shows cyclic hardening then
  softening to failure.
- **Tension/compression asymmetry ratio**, `R_TC` — `|σ_max,tension| / |σ_max,compression|` vs.
  cycle number. LCF runs fully reversed at strain ratio `R = ε_min/ε_max = -1`; an `R_TC ≠ 1`
  quantifies asymmetric deformation and a nonzero mean stress (see §4.1, Morrow).

---

## 4. Strain–life: total, elastic, and plastic

Total strain amplitude splits into elastic + plastic contributions (Basquin + Coffin-Manson):

$$\frac{\Delta\varepsilon_t}{2}=\frac{\Delta\varepsilon_e}{2}+\frac{\Delta\varepsilon_p}{2}
=\frac{\sigma'_f}{E}\,(2N_f)^{b}+\varepsilon'_f\,(2N_f)^{c}$$

- `Δε_e/2` = elastic strain amplitude = (Δσ/2)/E
- `Δε_p/2` = plastic strain amplitude = (Δε_t/2) − (Δε_e/2)  *(measured from the loop width)*

This master curve is assembled from the four fitted constants below.

### 4.1 Morrow mean-stress correction

When a cycle carries a nonzero mean stress `σ_m = (σ_max + σ_min)/2` (e.g. from a T/C asymmetry,
`R_TC ≠ 1`, even at strain ratio `R = -1`), Morrow's relation corrects the elastic (Basquin)
term by shifting `σ'_f` by `σ_m`:

$$\frac{\Delta\varepsilon_t}{2}=\frac{\sigma'_f-\sigma_m}{E}\,(2N_f)^{b}+\varepsilon'_f\,(2N_f)^{c}$$

- Reduces to the base equation when `σ_m = 0`.
- Tensile mean stress (`σ_m > 0`) shortens life; compressive (`σ_m < 0`) extends it.
- The plastic (Coffin-Manson) term is left unchanged, assuming mean stress relaxes in the
  high-plasticity regime and chiefly affects the longer-life elastic contribution.

---

## 5. Coffin-Manson fit (plastic branch)

$$\frac{\Delta\varepsilon_p}{2}=\varepsilon'_f\,(2N_f)^{c}$$

**Fit:** linear regression of `log(Δε_p/2)` vs. `log(2N_f)`.
- slope → `c` (fatigue ductility exponent, negative)
- intercept → `ε'_f` (fatigue ductility coefficient) = `10^intercept`

Outputs: `ε'_f`, `c`, R².

---

## 6. Basquin fit (elastic branch)

$$\frac{\Delta\sigma}{2}=\frac{\Delta\varepsilon_e}{2}\cdot E=\sigma'_f\,(2N_f)^{b}$$

**Fit:** linear regression of `log(Δσ/2)` vs. `log(2N_f)`.
- slope → `b` (fatigue strength exponent, negative)
- intercept → `σ'_f` (fatigue strength coefficient) = `10^intercept`

Outputs: `σ'_f`, `b`, R².

---

## 7. Ramberg–Osgood (cyclic stress–strain curve)

Describes the stabilized (half-life) stress–strain shape across amplitudes:

$$\Delta\varepsilon_t=\frac{\Delta\sigma}{E}+\left(\frac{\Delta\sigma}{K'}\right)^{1/n'}$$

Fit via the linearized plastic form:

$$\log\!\left(\frac{\Delta\sigma}{2}\right)=n'\log\!\left(\frac{\Delta\varepsilon_p}{2}\right)+\log(K')
\qquad\Longleftrightarrow\qquad
\frac{\Delta\sigma}{2}=K'\left(\frac{\Delta\varepsilon_p}{2}\right)^{n'}$$

**Fit:** linear regression of `log(Δσ/2)` vs. `log(Δε_p/2)`.
- slope → `n'` (cyclic strain-hardening exponent)
- intercept → `K'` (cyclic strength coefficient) = `10^intercept`

Outputs: `K'`, `n'`, R².

---

## 8. Built-in consistency checks

These hold when the fitted parameters are mutually consistent — good automatic validity flags:

- `n' ≈ b / c`
- `K' ≈ σ'_f / (ε'_f)^{(b/c)}`

The tool should compute both the directly-fitted and the relation-derived values and flag
disagreement beyond a tolerance.

---

## 9. Symbol reference

| Symbol | Meaning | Units |
|---|---|---|
| σ, ε | true stress, true strain | Pa, — |
| Δε_t/2 | total strain amplitude | — |
| Δε_e/2 | elastic strain amplitude | — |
| Δε_p/2 | plastic strain amplitude | — |
| Δσ/2 | stress amplitude | Pa |
| σ_m | mean stress (Morrow) | Pa |
| R | strain ratio (ε_min/ε_max; −1 fully reversed) | — |
| R_TC | tension/compression peak-stress ratio | — |
| 2N_f | reversals to failure | — |
| E | Young's modulus | Pa |
| W | cyclic energy density | MJ/m³ |
| σ'_f, b | fatigue strength coefficient, exponent (Basquin) | Pa, — |
| ε'_f, c | fatigue ductility coefficient, exponent (Coffin-Manson) | —, — |
| K', n' | cyclic strength coefficient, strain-hardening exponent (Ramberg–Osgood) | Pa, — |

---

## 10. Pipeline → tool mapping

| Step | Function | Inputs → Outputs |
|---|---|---|
| Unit/engineering→true conversion | `normalize_inputs` | raw σ–ε (any units, eng or true) → SI true σ–ε |
| Loop energy (§2) | `compute_cyclic_energy_density` | loop σ–ε → W per cycle; peak/half-life/Δ summary |
| Cyclic response (§3) | `cyclic_response_curves` | per-cycle peak stresses → hardening curve, T/C ratio |
| Coffin-Manson (§5) | `fit_coffin_manson` | (Δε_p/2, 2N_f) → ε'_f, c, R² |
| Basquin (§6) | `fit_basquin` | (Δσ/2, 2N_f) → σ'_f, b, R² |
| Strain–life (§4) | `predict_strain_life` | fitted params → Δε_t/2 vs. 2N_f; life at given amplitude |
| Morrow correction (§4.1) | `morrow_correction` | fitted params + σ_m → mean-stress-corrected Δε_t/2; life |
| Ramberg–Osgood (§7) | `fit_ramberg_osgood` | (Δσ/2, Δε_p/2) → K', n', R² |
| Consistency checks (§8) | `validate_parameters` | fitted params → flags |
