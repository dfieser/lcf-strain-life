# Agent usage guide

How an AI agent drives the `lcf` MCP server. This describes the tools, their
units, and the compute, save, recall pattern. Start the server with `lcf-mcp`.

## Capabilities at a glance

- Reduce a strain-controlled test from raw data to per-cycle metrics and a
  half-life summary.
- Fit the strain-life constants, Basquin, Coffin-Manson, Ramberg-Osgood.
- Predict life for a strain amplitude, with or without a mean-stress correction.
- Count a variable-amplitude history with rainflow and predict spectrum life.
- Convert a nominal notch stress to local stress, strain, and life.
- Fit a statistical design curve with reliability and confidence.
- Sum time-fraction creep-fatigue damage with a D-diagram check.

## Units and conventions

- Stress and modulus in MPa. Strain dimensionless, a fraction not a percent.
- All analysis uses true stress and true strain.
- The fatigue exponents b and c are negative.
- Results are JSON with non-finite values mapped to null.

## Compute, save, recall

Compute tools take a `name` or `material` argument. When given, the full result
is saved to the store and can be read back later.

- `recall_result(key, quantity)` returns a saved result.
- `list_results(key)` lists what is stored.
- The resource `lcf://results/{key}/{quantity}` exposes a saved result as JSON.

Quantities include `summary`, `per_cycle`, `strain_life_fit`, `rainflow`,
`spectrum_life`, `notch_local`, `design_curve`, and `creep_fatigue`.

## Tools

### fit_strain_life
Fit constants from per-test reduced data. Inputs: `total_strain_amp` list,
`stress_amp` list in MPa at half-life, `reversals` list (2N_f), `E` in MPa,
optional `min_plastic_strain` to drop near-runout points from the plastic branch.
Returns Basquin, Coffin-Manson, Ramberg-Osgood constants, transition life, and a
Masing consistency flag.

### analyze_test_timeseries and analyze_test_csv
Reduce one test from a `(time, strain, force)` series or a CSV file. Inputs
include `area` in mm squared and optional `E`. Returns the half-life summary and
saves the per-cycle table under `name`.

### predict_life
Reversals and cycles to failure for a `total_strain_amp`, given the four
strain-life constants and `E`.

### mean_stress_equivalent_stress
Equivalent fully-reversed stress for a cycle. Inputs: `stress_amp`, `mean_stress`
in MPa, `model` one of none, morrow, swt, walker. Morrow needs `sigma_f`, Walker
needs `gamma` or `sigma_u` to estimate it for steel.

### count_rainflow
Rainflow count a `strain_history` (ASTM E1049), preserving cycle indices. Saves
the per-cycle table. Set `close_residue` true to treat the history as repeating.

### compute_spectrum_life
Variable-amplitude life from aligned `strain_history` and `stress_history`.
Inputs include the four constants and `E`, `mean_stress_method` (none, morrow,
swt), and `rule` (miner or dldr). Returns damage per block and blocks and cycles
to failure.

### compute_damage
Cumulative damage for a counted block. Inputs: `counts` and `lives` lists,
`rule` (miner or dldr), `d_crit`. Returns damage and blocks to failure.

### compute_notch_local
Local notch stress, strain, and life from a `nominal_amp` in MPa and `Kt`.
Inputs include `E`, cyclic `K` and `n`, and the four strain-life constants.
`method` is neuber (default) or glinka.

### fit_design_curve
Fit a strain-life regression, life is the dependent variable. Inputs:
`amplitude` and `life_values` lists, `reliability`, `confidence`, optional
`censored` flags for runouts, optional `design_amplitude`. Returns the fit, the
Owen factor, and the design life.

### compute_creep_fatigue
Time-fraction creep-fatigue damage. Inputs: `cycle_counts`, `fatigue_lives`,
`hold_times`, `rupture_times`, `envelope`. Returns fatigue and creep damage and
whether the point is inside the D-diagram envelope.

## Example

A typical flow for fitting and predicting:

1. `fit_strain_life(total_strain_amp=[...], stress_amp=[...], reversals=[...], E=208000, min_plastic_strain=0.0005, material="SAE1137")`
2. Read back the fit with `recall_result("SAE1137", "strain_life_fit")`.
3. `predict_life(total_strain_amp=0.004, sigma_f=..., b=..., eps_f=..., c=..., E=208000)`
