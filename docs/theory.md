# Theory

A short tour of the methods. The full equations, symbols, and units are in
[Equations and labels](reference/Equations_and_Labels.md) and
[Analysis notes](reference/LCF_Analysis_Notes.md).

## Strain-life

Total strain amplitude splits into elastic and plastic parts. The elastic part
follows Basquin and the plastic part follows Coffin-Manson, summed to give the
strain-life curve. The transition life is where the two parts are equal. The
cyclic stress-strain shape follows Ramberg-Osgood. All three are fit by log-log
regression, with the plastic branch limited to the low cycle regime.

## Mean stress

A nonzero mean stress shifts life. The toolkit provides Morrow, modified Morrow,
Smith-Watson-Topper, and Walker. SWT is the default for variable amplitude
because it needs no extra constant.

## Variable amplitude

Irregular histories are reduced to cycles by ASTM E1049 rainflow counting. The
counter preserves the original sample indices, so per-cycle stress and strain
evolution is retained rather than collapsed into a histogram.

## Cumulative damage

Palmgren-Miner sums cycle-count over life and is the default. The Double Linear
Damage Rule and Corten-Dolan add sequence and load-level sensitivity. The
critical damage sum is configurable, for example 0.5 for some code-driven work.

## Notch effects

A notch concentrates stress. Neuber and Glinka convert a nominal stress to the
local notch stress and strain using the cyclic stress-strain curve, then the
strain-life curve gives notch life. Neuber is conservative, Glinka is less so,
and the measured strain usually lies between them.

## Statistics

Fatigue data scatters. The toolkit fits the linearized regression with life as
the dependent variable, reports confidence and prediction intervals, and builds
reliability-confidence design curves with the Owen tolerance factor. Runouts are
handled by maximum likelihood rather than deletion.

## Elevated temperature

At high temperature, life depends on frequency and hold time. The
frequency-modified Coffin-Manson coefficient captures the frequency effect.
Creep-fatigue damage sums a fatigue fraction and a creep time fraction, checked
against a bilinear interaction envelope. Strain-life constants can be stored as
a function of temperature and interpolated.

## Multiaxial

A survey-only stub provides the Fatemi-Socie, Brown-Miller, and SWT critical-plane
parameters and a plane-search interface. Full tensor input and a rotating-plane
search are planned for a later phase.
