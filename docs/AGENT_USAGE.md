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

### simulate_variable_amplitude
Life for a repeating variable-amplitude strain history block. Simulates the
cyclic stress response with material memory (Masing branches, rainflow
consistent closure), computes each closed loop's life with the chosen mean
stress model (`swt` default, `morrow`, or `none`), and Miner-sums the damage.
Inputs: `strain_history` (raw series or turning points), `E`, `K_prime`,
`n_prime`, and the four strain-life constants. Returns the loop table sorted
by damage, damage per block, and blocks to failure. Assumes stabilized cyclic
properties, mean stress relaxation and ratcheting are not modeled. Validation
against the published Conle SAE smooth-specimen dataset: within 2x of
experiment on two of three service histories, about 3x non-conservative on
the third, all leaning non-conservative. Reproduce it with
`examples/validate_sae_conle.py` and verify against your own data.

### analyze_staircase
Estimate the fatigue limit from a staircase (up-and-down) test, Dixon-Mood
method per ISO 12107. Inputs: `stress_levels` in test order, `failed` flags,
optional `step` (inferred from the sequence when omitted). Returns the mean
and standard deviation of the fatigue strength, per-level counts, and notes.
When the Dixon-Mood variability statistic is below 0.3 the standard deviation
is the approximate 0.53 step fallback and the result says so.

### compute_basis_value
A- or B-basis value, the one-sided lower tolerance bound mean minus k times
std with the exact Owen factor. B-basis is 90 percent reliability at 95
percent confidence, A-basis is 99/95, following MMPDS practice. Pass raw
`samples` or `mean`, `std`, and `n`. Assumes normality in the analyzed units.

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

### fit_random_fatigue_limit
Fit the Pascual-Meeker random fatigue limit model to S-N data with runouts:
each specimen's fatigue limit varies unit to unit, so the curve flattens
naturally near the limit and runouts carry real information. Inputs: stress
amplitudes, lives, runout flags. Returns the five ML estimates, the log
likelihood, and a convergence flag. Needs at least 10 observations and 6
failures. The notes state the validation status honestly.

### compute_roughness_factor
FKM surface roughness factor K_R from Rz (micrometres) and Rm (MPa) for the
seven FKM material groups. Multiply a stress-based fatigue strength by K_R.
Capped at 1.0 for polished surfaces. Strain-life constants are not corrected
directly by this factor.

### compute_size_factor
FKM technological size factor K_d,m for an effective diameter d_eff (mm),
with the material constants a_dm and d_eff_N supplied by the caller from
their licensed FKM guideline (the tables are copyrighted and not bundled).
1.0 at or below the reference diameter, lower above it. Multiply a
stress-based fatigue or tensile strength by it. The logarithmic formula is
a verified published relation.

### search_critical_plane_tensor
Find the critical plane from strain (and stress) tensor component histories
sampled over one cycle. Scans plane normals over a hemisphere grid, resolves
each plane's engineering shear amplitude (longest chord, valid for
non-proportional paths), normal strain amplitude, and maximum normal stress,
and returns the plane maximizing `fatemi_socie`, `brown_miller`, or `swt`.
Fatemi-Socie and SWT need the stress history. Amplitudes come from the given
cycle's path, per-plane rainflow of long histories is not implemented.

### generate_report
One-call markdown fatigue report of everything stored under a key, with
provenance hashes and the source citation for every method that appears.
Also written to `<store>/reports/<key>.md`.

### export_material and import_material
Exchange strain-life constants. `export_material` emits the versioned
`lcf-strain-life/material@1` JSON document (MPa, strain fraction, reversals,
provenance block), or with `fmt="pylife"` the Basquin line in pyLife
WoehlerCurve conventions (shape-compatible, the knee is a representation
choice). `import_material` validates a document and refuses unknown
versions and unit systems with the reason.

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
