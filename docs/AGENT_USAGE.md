# Agent usage guide

How an AI agent drives the `lcf` MCP server. This describes the tools, their
units, and the compute, save, recall pattern. Start the server with `lcf-mcp`.

## Capabilities at a glance

- Reduce a strain-controlled test from raw data to per-cycle metrics and a
  half-life summary.
- Fit the strain-life constants, Basquin, Coffin-Manson, Ramberg-Osgood.
- Estimate strain-life constants from monotonic properties when no fatigue
  test data exists, five published methods with citations and guardrails.
- Predict life for a strain amplitude, with or without a mean-stress correction.
- Count a variable-amplitude history with rainflow, level crossing, or peak
  counting, condense it with the racetrack filter, and predict spectrum life.
- Convert a nominal notch stress to local stress, strain, and life.
- Fit a statistical design curve with reliability and confidence, and flag
  outliers in fatigue data while respecting runouts.
- Evaluate Woehler-line lives with original, elementary, or Haibach knee
  treatment, and sum damage with Miner, DLDR, or Corten-Dolan.
- Evaluate critical-plane multiaxial parameters from known plane quantities.
- Sum time-fraction creep-fatigue damage with a D-diagram check, and invert
  the frequency-modified Coffin-Manson law.
- Render stored results as PNG plots.
- Look up the published citation behind any method with `get_citations`.

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
`spectrum_life`, `notch_local`, `design_curve`, `creep_fatigue`,
`estimated_constants`, `level_crossings`, `peaks`, and the `plot_*` entries
written by `render_plot`.

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

### analyze_test_series
Analyze a whole directory of lab exports in one call. The reader auto-detects
the delimiter, the header row beneath machine preamble blocks, the column
names through a synonym table (MTS TestSuite and Instron style delimited
exports among others), and unit suffixes in the headers: percent strain, kN
force, ksi stress. Each test is reduced and saved under its file stem, then
the strain-life constants are fitted across the series and saved under
`material`. Unreadable files are reported in `errors` without stopping the
rest. A strain column with no unit marking whose values look like percent is
refused with instructions, pass `strain_unit` to decide. Dedicated parsers
for proprietary vendor formats are not implemented, delimited exports only.

### preview_lab_file
Report how a lab export would be read before committing to an analysis: the
detected header row, delimiter, resolved columns, units, conversion factors,
row count, and notes.

### predict_life
Reversals and cycles to failure for a `total_strain_amp`, given the four
strain-life constants and `E`.

### mean_stress_equivalent_stress
Equivalent fully-reversed stress for a cycle. Inputs: `stress_amp`, `mean_stress`
in MPa, `model` one of none, morrow, swt, walker. Morrow needs `sigma_f`, Walker
needs `gamma` or `sigma_u` to estimate it for steel.

### estimate_strain_life_constants
Estimate the four strain-life constants when no fatigue test data exists.
Inputs: `method` (medians, the recommended default, uniform_material_law,
universal_slopes, modified_universal_slopes, or hardness), `material_class`,
and the monotonic properties the method needs (`Su`, `E`, `HB`, `RA`). Every
result carries the citation of the source and validity warnings. These are
screening estimates, not a substitute for test data.

### count_rainflow
Rainflow count a `strain_history` (ASTM E1049), preserving cycle indices. Saves
the per-cycle table. Set `close_residue` true to treat the history as repeating.
A non-None `gate` first drops swings smaller than the gate (racetrack filter).

### count_level_crossings and count_peaks
Level-crossing and peak counting per ASTM E1049 sections 5.2 and 5.3. Both
save their tables under `name`.

### compute_spectrum_life
Variable-amplitude life from aligned `strain_history` and `stress_history`.
Inputs include the four constants and `E`, `mean_stress_method` (none, morrow,
swt), and `rule` (miner or dldr). Returns damage per block and blocks and cycles
to failure.

### compute_damage
Cumulative damage for a counted block. Inputs: `counts` and `lives` lists,
`rule` (miner, dldr, or corten_dolan), `d_crit`. Corten-Dolan additionally
needs `stresses` and `d_exponent`. Returns damage and blocks to failure.

### compute_sn_life
Allowable cycles from a one-slope Woehler line with a knee at `(sd, nd)` and
slope `k`. `variant` selects the treatment below the knee: original (infinite
life, serialized as null), elementary, or haibach (fictitious slope 2k-1).
Feed the lives into `compute_damage`.

### compute_notch_local
Local notch stress, strain, and life from a `nominal_amp` in MPa and `Kt`.
Inputs include `E`, cyclic `K` and `n`, and the four strain-life constants.
`method` is neuber (default) or glinka.

### fit_design_curve
Fit a strain-life regression, life is the dependent variable. Inputs:
`amplitude` and `life_values` lists, `reliability`, `confidence`, optional
`censored` flags for runouts, optional `design_amplitude`. Returns the fit, the
Owen factor, and the design life.

### flag_outliers
Screen strain-life or stress-life data for outliers before fitting. Inputs:
`amplitude` and `life_values` lists, optional `censored` flags. Runouts are
censored data, not outliers, and are never tested. Returns generalized ESD
outlier indices, influence diagnostics (Cook's distance, leverage,
studentized residuals), warnings, and the citations. Nothing is deleted, the
agent decides what to do with flagged points.

### compute_creep_fatigue
Time-fraction creep-fatigue damage. Inputs: `cycle_counts`, `fatigue_lives`,
`hold_times`, `rupture_times`, `envelope`. Returns fatigue and creep damage and
whether the point is inside the D-diagram envelope.

### compute_frequency_modified_life
Reversals to failure from the frequency-modified Coffin-Manson law in the
coefficient form. Inputs: `plastic_strain_amp`, `eps_f_coeff`, `c`,
`frequency`, `k`, optional `freq_ref`.

### compute_multiaxial_parameter and search_critical_plane
Evaluate a critical-plane damage parameter (fatemi_socie, brown_miller, swt,
von_mises) from known plane quantities, or search supplied per-angle arrays
for the critical plane. There is no tensor plane-search engine yet, the plane
quantities come from the caller.

### render_plot
Render a stored result as a PNG. `kind` is one of rainflow_histogram,
peak_valley, energy, strain_life. Run the corresponding compute tool first,
the data comes from the store. Returns the file path.

### get_citations
The published source behind every method, optionally filtered by topic. The
resource `lcf://citations` exposes the same registry.

## Example

A typical flow for fitting and predicting:

1. `fit_strain_life(total_strain_amp=[...], stress_amp=[...], reversals=[...], E=208000, min_plastic_strain=0.0005, material="SAE1137")`
2. Read back the fit with `recall_result("SAE1137", "strain_life_fit")`.
3. `predict_life(total_strain_amp=0.004, sigma_f=..., b=..., eps_f=..., c=..., E=208000)`
