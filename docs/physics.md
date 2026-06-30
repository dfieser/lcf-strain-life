# Physics and equations

The fatigue mechanics behind the toolkit, stated plainly. Each section gives the
equation, what it means, and the source. There is no software detail here.

A printable, science-only version is the PDF at
[PHYSICS_REVIEW.pdf](reference/PHYSICS_REVIEW.pdf). It carries a reviewer sign-off
table.

## Conventions

All analysis uses true stress and true strain. Stress and modulus are in MPa.
Strain is a dimensionless fraction. Life is given in reversals $2N_f$, where one
cycle is two reversals. The fatigue strength exponent $b$ and the fatigue
ductility exponent $c$ are negative.

## True stress and strain

Engineering stress $\sigma_\text{eng}=F/A_0$ and engineering strain $e$ convert
to true values by

$$\varepsilon = \ln(1+e), \qquad \sigma = \sigma_\text{eng}(1+e).$$

Valid up to necking. Source: Dowling, Mechanical Behavior of Materials, 4th ed.

## Cyclic stress-strain, Ramberg-Osgood

$$\varepsilon = \frac{\sigma}{E} + \left(\frac{\sigma}{K'}\right)^{1/n'},
\qquad
\Delta\varepsilon = \frac{\Delta\sigma}{E} + 2\left(\frac{\Delta\sigma}{2K'}\right)^{1/n'}.$$

The second form is the doubled hysteresis branch. Source: Ramberg and Osgood
1943 (NACA TN 902), Dowling 4th ed. Eq. 14.12.

## Strain-life

The elastic part follows Basquin and the plastic part follows Coffin-Manson,
summed to the total strain-life curve.

$$\frac{\Delta\sigma}{2} = \sigma'_f (2N_f)^{b},
\qquad
\frac{\Delta\varepsilon_p}{2} = \varepsilon'_f (2N_f)^{c},$$

$$\frac{\Delta\varepsilon}{2} = \frac{\sigma'_f}{E}(2N_f)^{b} + \varepsilon'_f (2N_f)^{c},
\qquad
2N_t = \left(\frac{\varepsilon'_f E}{\sigma'_f}\right)^{1/(b-c)}.$$

The transition life $2N_t$ is where the elastic and plastic amplitudes are equal.
Compatibility, checked but not forced, predicts $n' = b/c$ and
$K' = \sigma'_f/(\varepsilon'_f)^{b/c}$. The plastic line is fit over the low cycle
regime. Source: Basquin 1910, Coffin 1954, Manson 1953, Dowling 4th ed. Eq. 14.3
to 14.6.

## Mean-stress corrections

A nonzero mean stress shifts life. Morrow shifts the elastic term, SWT is
parameter free, and Walker uses a fitted exponent.

$$\frac{\Delta\varepsilon}{2} = \frac{\sigma'_f-\sigma_m}{E}(2N_f)^{b} + \varepsilon'_f (2N_f)^{c}
\quad\text{(Morrow)},$$

$$\sigma_{max}\,\frac{\Delta\varepsilon}{2} = \frac{(\sigma'_f)^2}{E}(2N_f)^{2b}
+ \sigma'_f \varepsilon'_f (2N_f)^{b+c}
\quad\text{(SWT)},$$

$$\sigma_{ar} = \sigma_{max}^{\,1-\gamma}\,\sigma_a^{\,\gamma},
\qquad
\gamma_{steel} = 0.8818 - 2.00\times10^{-4}\,\sigma_u
\quad\text{(Walker)}.$$

With $\gamma=0.5$ Walker reduces to SWT. Source: Morrow 1968, Smith Watson Topper
1970, Walker 1970, Dowling Calhoun Arcari 2009.

## Hysteresis energy

The plastic strain energy density dissipated per cycle is the area enclosed by
one stress-strain loop,

$$W = \oint \sigma\,d\varepsilon.$$

## Variable amplitude, rainflow counting

Irregular histories are reduced to closed cycles by rainflow counting, which
pairs reversals into hysteresis loops while preserving their order in time.
Source: ASTM E1049-85(2017), Downing and Socie 1982, Matsuishi and Endo 1968.

## Cumulative damage

Palmgren-Miner sums cycle count over life and fails at a critical sum, the
default being one.

$$D = \sum_i \frac{n_i}{N_{f,i}}.$$

The Double Linear Damage Rule of Manson and Halford adds sequence sensitivity
through a Phase I life fraction referenced to the longest life in the spectrum,
$f_I = 0.35\,(N_f/N_{long})^{0.25}$. Source: Palmgren 1924, Miner 1945, Manson and
Halford 1981.

## Notch local-strain approach

Neuber and Glinka convert a nominal notch stress to the local stress and strain
using the cyclic curve, then the strain-life curve gives notch life.

$$\frac{(K_t S)^2}{E} = \sigma\,\varepsilon \quad\text{(Neuber)},
\qquad
\frac{(K_t S)^2}{2E} = \frac{\sigma^2}{2E} + \frac{\sigma}{n'+1}\left(\frac{\sigma}{K'}\right)^{1/n'} \quad\text{(Glinka)}.$$

Neuber tends to overestimate and Glinka to underestimate the local strain, and
the measured value usually lies between them. Source: Neuber 1961, Molski and
Glinka 1981.

## Statistics and design curves

Life is the dependent variable in the linearized regression
$\log_{10} N = A + B \log_{10}(\Delta\varepsilon/2)$. A reliability and confidence
design curve is the mean reduced by $k\,s$, where $k$ is the one-sided Owen
tolerance factor and $s$ the residual standard error. Runouts are handled by
maximum likelihood rather than deletion. Source: ASTM E739 (withdrawn 2024, used
as the de facto reference), Owen 1963, Williams Lee Rilly 2003.

## Elevated temperature

At high temperature, life depends on frequency and hold time. The
frequency-modified Coffin-Manson coefficient captures the frequency effect, and
creep-fatigue damage sums a fatigue fraction and a creep time fraction.

$$D = \sum_i \frac{n_i}{N_{f,i}} + \sum_j \frac{t_j}{t_{r,j}}.$$

The point is checked against a bilinear creep-fatigue interaction envelope.
Source: Coffin 1971, Robinson 1952, ASTM E2714-13(2020).

## Multiaxial, survey only

Critical-plane parameters are provided for evaluation. The full plane search is
planned for a later phase.

$$P_{FS} = \frac{\Delta\gamma_{max}}{2}\left(1 + k\frac{\sigma_{n,max}}{\sigma_y}\right),
\qquad
P_{SWT} = \sigma_{n,max}\frac{\Delta\varepsilon_1}{2}.$$

Source: Fatemi and Socie 1988, Smith Watson Topper 1970.

## Going deeper

The full engineering version, with the code function and the test that checks
each equation plus the validation evidence, is the
[Scientific reference](SCIENTIFIC_REFERENCE.md).
