# API reference

The public functions, grouped by module. Import them from the top-level package,
for example `import lcf` then `lcf.fit_strain_life(...)`. Full signatures and
units are in each function docstring.

## lcf.units
Engineering to true conversions: `eng_to_true_strain`, `eng_to_true_stress`,
`stress_from_force`, and the inverse conversions.

## lcf.ingest
`from_timeseries`, `from_dataframe`, `read_csv`, and `normalize` build a
normalized `TestRun`.

## lcf.cycles
`reduce_cycles`, `find_turning_points`, `find_failure_cycle`, and the
`ReducedCycles` container.

## lcf.metrics and lcf.energy
`per_cycle_metrics`, `estimate_modulus`, `loop_area`, `shoelace_area`.

## lcf.fits
`fit_strain_life`, `fit_basquin`, `fit_coffin_manson`, `fit_ramberg_osgood`,
`transition_reversals`, `check_consistency`, and the fit result containers.

## lcf.meanstress
`equivalent_fully_reversed_stress`, `morrow_strain_life`,
`modified_morrow_strain_life`, `walker_gamma_steel`.

## lcf.life
`total_strain_life`, `predict_reversals`, `predict_reversals_from_total_strain`,
`predict_reversals_basquin`, `predict_reversals_swt`, `predict_reversals_morrow`.

## lcf.counting
`count_rainflow`, `extract_cycles`, `reversals`, `mean_stress_per_cycle`.

## lcf.damage
`miner`, `dldr`, `corten_dolan`, `manson_halford_phase_lives`, `DamageResult`.

## lcf.notch
`neuber_local`, `glinka_local`, `notch_local_life`, `kf_peterson`, `kf_neuber`,
`notch_sensitivity`.

## lcf.stats
`fit_log_life`, `fit_log_life_censored`, `predict_life`, `confidence_interval`,
`prediction_interval`, `owen_tolerance_factor`, `design_life`.

## lcf.hightemp
`frequency_modified_plastic_strain`, `frequency_modified_reversals`,
`creep_fatigue_damage`, `creep_fatigue_envelope_check`, `interpolate_constants`.

## lcf.multiaxial
`fatemi_socie`, `brown_miller`, `swt_multiaxial`, `von_mises_equivalent_strain`,
`critical_plane_search`.

## lcf.spectrum
`spectrum_life`, `SpectrumResult`.

## lcf.pipeline
`analyze_test`, `analyze_material`, `fit_from_summary`.

## lcf.plots
`plot_strain_life`, `plot_coffin_manson`, `plot_basquin`,
`plot_cyclic_stress_strain`, `plot_hysteresis`, `plot_peak_valley`,
`plot_energy`, `plot_design_curve`, `plot_creep_fatigue_diagram`,
`plot_rainflow_histogram`, `savefig`.

## lcf.store and lcf.service
`LcfStore` and `LcfService` provide the compute, save, recall layer used by the
MCP server.
