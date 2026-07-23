# Statistics after E739

ASTM E739, the guide for statistical analysis of linearized stress-life and
strain-life data, was withdrawn in January 2024 with no published
replacement. The active ASTM replacement effort, work item WK88010, states
why: the legacy methods cannot handle censored data, runouts, or nonlinear
regression. Its technical basis is the maximum-likelihood framework of
Meeker, Escobar, Pascual and coauthors, arXiv:2212.04550.

lcf-strain-life implements both layers and says which is which.

## The classical layer

Everything the withdrawn E739 and common design practice prescribe:

- The linearized regression with life as the dependent variable,
  \(\log_{10} N = A + B \log_{10}(\varepsilon_a)\), `fit_log_life`.
- Confidence and prediction intervals on the fitted line.
- The lack-of-fit F test when replicate levels exist.
- One-sided tolerance design curves, mean minus k times sigma with the exact
  Owen factor, `design_life`, and MMPDS-style A and B basis values.
- Outlier screening, Grubbs and generalized ESD, with influence
  diagnostics.
- Staircase fatigue-limit analysis, Dixon-Mood per ISO 12107.

These remain correct for complete samples inside the tested interval, and
E739's own caveat is enforced: predictions outside the fitted amplitude
range carry an extrapolation warning.

## The maximum-likelihood layer

What the replacement effort points to, implemented and labeled:

### Censored fits that keep runouts

`fit_log_life_censored` fits the same line by maximum likelihood. Observed
failures contribute the density, runouts contribute the survival
probability. Nothing is deleted. The life scatter is lognormal by default,
Weibull, smallest extreme value on log life, as an option, and AIC is
reported so the two can be compared. Every fit carries standard errors from
the observed information, the log likelihood, and a convergence flag.

### Design bounds without the complete-sample assumption

The Owen factor assumes a complete normal sample. With runouts that
assumption is false. `design_life_ml` gives the one-sided lower confidence
bound on the life quantile by profile likelihood, Venzon and Moolgavkar
1988, or by the Wald method. On complete samples it agrees closely with the
Owen bound, that agreement is a test in the suite, and with censoring it
remains meaningful where the Owen construction does not.

### The full curve, not just a line

E739 restricted itself to linearized fits. `fit_strain_life_censored` fits
the combined Basquin plus Coffin-Manson curve

\[
\varepsilon_a = \frac{\sigma_f'}{E}(2N_f)^b + \varepsilon_f'(2N_f)^c
\]

directly by censored maximum likelihood with lognormal life scatter.

An honest caveat is intrinsic to that model: the four constants are
strongly correlated when inferred from total strain alone, and on sparse
data the elastic exponent can collapse toward zero. The fitted curve is
well determined inside the tested strain range even then. The result
reports standard errors and a `weak_identifiability` warning, and the
branch-wise linear fits remain the method of choice when separated elastic
and plastic strains are available.

### Quantifying what deletion did

`compare_runout_handling` fits the same data three ways, runouts deleted
with the Owen factor, censored ML with the Owen factor, censored ML with
the profile bound, and reports the design-life ratios. Whether deletion was
optimistic or pessimistic depends on the data. The point is that the
difference becomes a number instead of a habit.

### Random fatigue limit

For stress-life data with a fatigue limit, `fit_rfl` implements the
Pascual-Meeker random fatigue limit model, validated by exact reproduction
of the published laminate-panel fit.

## Choosing a method

| Situation | Use |
|---|---|
| Complete sample, linear range | `fit_log_life` plus `design_life` |
| Runouts present | `fit_log_life_censored` plus `design_life_ml` |
| Combined curve needed, or censoring with curvature | `fit_strain_life_censored` |
| Fatigue limit suspected | `fit_rfl` |
| Deciding lognormal versus Weibull | compare `aic` of the censored fits |

## Sources

Methods and their citations are registered in `lcf.citations` and rendered
in the [physics review](PHYSICS_REVIEW.md). The statistics layer follows
Meeker, Escobar, Pascual et al., arXiv:2212.04550, Meeker and Escobar,
Statistical Methods for Reliability Data, Wiley 1998, Owen 1963 and 1968,
Venzon and Moolgavkar 1988, Pascual and Meeker 1999, and the withdrawn
ASTM E739-23 for the classical layer.
