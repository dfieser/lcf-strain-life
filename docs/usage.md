# Usage

Worked examples for the main capabilities. All values use true stress in MPa
and strain as a dimensionless fraction, life in reversals unless a function
says cycles. The numbers in the first example are the published SAE 1137
dataset bundled in `lcf.datasets`.

## Fit strain-life constants

```python
import lcf

fit = lcf.fit_strain_life(
    total_strain_amp=[0.009, 0.007, 0.005, 0.003, 0.002, 0.00175],
    stress_amp=[553, 522, 464, 405, 350, 319],
    reversals=[4234, 7398, 14768, 77104, 437498, 3327958],
    E=208000,
    min_plastic_strain=5e-4,
)
print(fit.coffin_manson.eps_f, fit.coffin_manson.c)
print(fit.transition_reversals)
```

## Predict life

```python
two_nf = lcf.predict_reversals(fit, 0.004)
```

## Mean-stress correction

```python
sar = lcf.equivalent_fully_reversed_stress(400.0, 120.0, "swt")
```

## Rainflow count a variable-amplitude history

```python
cycles = lcf.count_rainflow([-2, 1, -3, 5, -1, 3, -4, 4, -2])
print(cycles[["range", "mean", "count", "i_start", "i_end"]])
```

## Spectrum life

```python
res = lcf.spectrum_life(
    strain_history, stress_history,
    sigma_f=1000, b=-0.09, eps_f=0.5, c=-0.6, E=200000,
    mean_stress_method="swt", rule="miner",
)
print(res.blocks_to_failure, res.cycles_to_failure)
```

## Cumulative damage

```python
d = lcf.miner(counts=[100, 200], lives=[1e4, 1e5])
print(d.damage, d.blocks_to_failure)
```

## Notch local-strain life

```python
out = lcf.notch_local_life(
    100.0, Kt=2.53, E=207000, K=1240, n=0.27,
    sigma_f=886, b=-0.14, eps_f=0.28, c=-0.5, method="neuber",
)
print(out["local_strain_amp"], out["reversals"])
```

## Design curve with reliability and confidence

```python
fit = lcf.fit_log_life(amplitude, life)
design = lcf.design_life(fit, 0.005, reliability=0.90, confidence=0.90)
```

## Runouts by maximum likelihood, not deletion

```python
ml = lcf.fit_log_life_censored(amplitude, life, censored)
print(ml.slope, ml.se_slope, ml.aic)

bound = lcf.design_life_ml(
    amplitude, life, censored,
    at_amplitude=0.005, reliability=0.90, confidence=0.90,
)
print(bound["design_life"], bound["median_life"])

report = lcf.compare_runout_handling(
    amplitude, life, censored, at_amplitude=0.005,
)
print(report["design_life_ratio"])
```

The [statistics page](statistics.md) explains these methods and their
caveats.

## Creep-fatigue

```python
r = lcf.creep_fatigue_damage(
    cycle_counts=[900], fatigue_lives=[1000],
    hold_times=[90], rupture_times=[100],
)
print(r.d_fatigue, r.d_creep, r.failed)
```

## Interchange and validation

```python
from lcf import interchange

doc = interchange.export_material(
    name="SAE 1005", E=207000, sigma_f=886, b=-0.14, eps_f=0.28, c=-0.5,
    K_prime=1240, n_prime=0.27, source="Lee et al. 2005",
)
verdict = interchange.validate_document(doc)
```

See the [interchange specification](INTERCHANGE.md) and the
[seed collection](data.md).

## Plots

```python
from lcf import plots
fig = plots.plot_strain_life(fit, reversals=[...], total_strain_amp=[...])
plots.savefig(fig, "strain_life.png")
```

## MCP server

Start `lcf-mcp` and call the tools from an MCP client. The
[agent usage guide](AGENT_USAGE.md) documents the full tool list and the
compute, save, recall pattern.

## No-code interface

`lcf-gui` starts a Streamlit app that runs the same service layer: paste or
upload data, fit, predict, and export without writing code.
