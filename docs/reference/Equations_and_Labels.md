# LCF Equations & Labels

The canonical reference mapping each LCF equation to its **symbols**, **units**, and the
**code labels** (variable / parameter names) used throughout the Python library and the MCP server.
Keep names here identical to the implementation so the math, the library API, and the agent-facing
tool arguments all line up.

> **Convention:** all analysis uses **true stress (σ)** and **true strain (ε)**. Internal units
> are **MPa** for stress/modulus and **dimensionless (fraction)** for strain — so a hysteresis
> loop area comes out directly in MJ/m³ (see `lcf.units`). Convert engineering inputs at ingestion:
> `eps_true = ln(1 + eps_eng)`, `sigma_true = sigma_eng * (1 + eps_eng)`.

---

## 1. Symbol → label dictionary

| Symbol | Quantity | Code label | Unit (internal) | Unit (reported) |
|---|---|---|---|---|
| σ | true stress | `stress` | Pa | MPa |
| ε | true strain | `strain` | — | — (or %) |
| Δε_t/2 | total strain amplitude | `total_strain_amp` | — | % |
| Δε_e/2 | elastic strain amplitude | `elastic_strain_amp` | — | % |
| Δε_p/2 | plastic strain amplitude | `plastic_strain_amp` | — | % |
| Δσ/2 | stress amplitude | `stress_amp` | Pa | MPa |
| σ_m | mean stress (Morrow) | `mean_stress` | Pa | MPa |
| R | strain ratio (ε_min/ε_max; −1 fully reversed) | `strain_ratio` | — | — |
| R_TC | tension/compression peak-stress ratio | `tc_ratio` | — | — |
| N_f | cycles to failure | `cycles_to_failure` | — | — |
| 2N_f | reversals to failure | `reversals_to_failure` | — | — |
| E | Young's modulus | `youngs_modulus` | Pa | GPa |
| W | cyclic energy density | `energy_density` | J/m³ | MJ/m³ |
| σ'_f | fatigue strength coefficient | `fatigue_strength_coeff` | Pa | MPa |
| b | fatigue strength exponent | `fatigue_strength_exp` | — | — |
| ε'_f | fatigue ductility coefficient | `fatigue_ductility_coeff` | — | — |
| c | fatigue ductility exponent | `fatigue_ductility_exp` | — | — |
| K' | cyclic strength coefficient | `cyclic_strength_coeff` | Pa | MPa |
| n' | cyclic strain-hardening exponent | `cyclic_hardening_exp` | — | — |
| R² | fit goodness | `r_squared` | — | — |

---

## 2. Equations

### E1 — Cyclic energy density (hysteresis loop area)

$$W=\oint \sigma(\varepsilon)\,d\varepsilon$$

- **Inputs:** ordered loop points `stress[]`, `strain[]` (one closed cycle).
- **Output:** `energy_density` (J/m³ → report MJ/m³).
- **Label note:** computed per cycle; summarized as `energy_peak_hardened`, `energy_half_life`,
  `energy_delta` (= half_life − peak_hardened).
- **Library:** `energy.loop_area(strain, stress)` (per-cycle via `metrics.per_cycle_metrics`)

### E2 — Total strain–life (Basquin + Coffin-Manson)

$$\frac{\Delta\varepsilon_t}{2}=\frac{\sigma'_f}{E}\,(2N_f)^{b}+\varepsilon'_f\,(2N_f)^{c}$$

- **Inputs:** `fatigue_strength_coeff`, `fatigue_strength_exp`, `youngs_modulus`,
  `fatigue_ductility_coeff`, `fatigue_ductility_exp`, `reversals_to_failure`.
- **Output:** `total_strain_amp` (and split `elastic_strain_amp`, `plastic_strain_amp`).
- **Library:** `life.total_strain_life(...)`, `life.predict_life(total_strain_amp, ...)`

### E2b — Morrow mean-stress correction

$$\frac{\Delta\varepsilon_t}{2}=\frac{\sigma'_f-\sigma_m}{E}\,(2N_f)^{b}+\varepsilon'_f\,(2N_f)^{c}
\qquad \sigma_m=\frac{\sigma_{max}+\sigma_{min}}{2}$$

Corrects the elastic (Basquin) term for a nonzero mean stress `mean_stress` ($\sigma_m$, taken
from the stabilized/half-life loop). Tensile $\sigma_m$ shortens life; compressive extends it.
Reduces to E2 when $\sigma_m = 0$.

- **Inputs:** E2 inputs + `mean_stress`.
- **Output:** `total_strain_amp` (mean-stress-corrected); `predict_life(...)`.
- **Library:** `life.morrow_strain_life(...)`, `life.mean_stress(stress_max, stress_min)`

### E3 — Coffin-Manson (plastic branch)

$$\frac{\Delta\varepsilon_p}{2}=\varepsilon'_f\,(2N_f)^{c}$$

- **Fit:** linear regression of `log(plastic_strain_amp)` vs `log(reversals_to_failure)`.
- **Outputs:** `fatigue_ductility_coeff` (= 10^intercept), `fatigue_ductility_exp` (= slope),
  `r_squared`.
- **Library:** `fits.fit_coffin_manson(plastic_strain_amp, reversals_to_failure)`

### E4 — Basquin (elastic branch)

$$\frac{\Delta\sigma}{2}=\frac{\Delta\varepsilon_e}{2}\,E=\sigma'_f\,(2N_f)^{b}$$

- **Fit:** linear regression of `log(stress_amp)` vs `log(reversals_to_failure)`.
- **Outputs:** `fatigue_strength_coeff` (= 10^intercept), `fatigue_strength_exp` (= slope),
  `r_squared`.
- **Library:** `fits.fit_basquin(stress_amp, reversals_to_failure)`

### E5 — Ramberg–Osgood (cyclic stress–strain)

$$\Delta\varepsilon_t=\frac{\Delta\sigma}{E}+\left(\frac{\Delta\sigma}{K'}\right)^{1/n'}$$

Linearized fitting form:

$$\frac{\Delta\sigma}{2}=K'\left(\frac{\Delta\varepsilon_p}{2}\right)^{n'}
\;\Longleftrightarrow\;
\log\!\left(\tfrac{\Delta\sigma}{2}\right)=n'\log\!\left(\tfrac{\Delta\varepsilon_p}{2}\right)+\log K'$$

- **Fit:** linear regression of `log(stress_amp)` vs `log(plastic_strain_amp)`.
- **Outputs:** `cyclic_strength_coeff` (= 10^intercept), `cyclic_hardening_exp` (= slope),
  `r_squared`.
- **Library:** `fits.fit_ramberg_osgood(stress_amp, plastic_strain_amp)`

### E6 — Tension/compression asymmetry

$$R_{TC}=\frac{|\sigma_{max,tension}|}{|\sigma_{max,compression}|}$$

- **Inputs:** per-cycle `stress_max`, `stress_min`.
- **Output:** `tc_ratio` vs cycle; plus `stress_max`/`stress_min` hardening curves.
- **Note:** LCF runs fully reversed at strain ratio `R = ε_min/ε_max = -1`; `R_TC ≠ 1`
  reflects a nonzero mean stress (see E2b).
- **Library:** `metrics.per_cycle_metrics(...)` (adds `r_tc`, `stress_max`, `stress_min` columns)

---

## 3. Derived relations (consistency checks)

When all parameters are mutually consistent these hold — used as automatic validity flags:

$$n' \approx \frac{b}{c} \qquad K' \approx \frac{\sigma'_f}{(\varepsilon'_f)^{\,b/c}}$$

- **Library:** `fits.check_consistency(...)` → returns deviations + `masing_ok` flag.

---

## 4. Unit-conversion reference

| From | To | Factor / formula |
|---|---|---|
| strain (fraction) | strain (%) | × 100 |
| stress Pa | stress MPa | ÷ 1e6 |
| stress Pa | stress GPa | ÷ 1e9 |
| energy J/m³ | energy MJ/m³ | ÷ 1e6 |
| σ[GPa]·ε[%] product | MJ/m³ | × 10 |
| engineering strain | true strain | `ln(1 + eps_eng)` |
| engineering stress | true stress | `sigma_eng * (1 + eps_eng)` |
