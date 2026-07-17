"""End-to-end demo: fit strain-life constants, predict life, save, and plot.

Uses the published SAE 1137 dataset (Williams, Lee & Rilly 2003). Run from the
repo root with the project installed:

    python examples/strain_life_demo.py

Writes a strain-life plot to ``examples/output/strain_life.png`` and a small
result store under ``examples/output/.lcfstore``.
"""

from __future__ import annotations

from pathlib import Path

import lcf
from lcf import plots
from lcf.service import LcfService

OUT = Path(__file__).parent / "output"

# --- published SAE 1137 per-test reduced data, from the bundled dataset -----
from lcf.datasets import SAE1137_E as E, sae1137_reduced

_sae = sae1137_reduced()
total_strain_amp = _sae["total_strain_amp"].tolist()
stress_amp = _sae["stress_amp"].tolist()               # MPa, half-life
reversals = _sae["reversals"].tolist()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) Fit the strain-life models (exclude near-runout points from the plastic branch)
    fit = lcf.fit_strain_life(
        total_strain_amp, stress_amp, reversals, E, min_plastic_strain=5e-4
    )
    print("Coffin-Manson:  eps_f = %.3f   c = %.3f" % (fit.coffin_manson.eps_f, fit.coffin_manson.c))
    print("Basquin:        sigma_f = %.0f MPa   b = %.4f" % (fit.basquin.sigma_f, fit.basquin.b))
    print("Ramberg-Osgood: K' = %.0f MPa   n' = %.4f" % (fit.ramberg_osgood.K, fit.ramberg_osgood.n))
    print("Transition life 2Nt = %.0f reversals" % fit.transition_reversals)
    print("Masing-consistent:", fit.consistency.masing_ok)

    # 2) Predict life at a new strain amplitude
    two_nf = lcf.predict_reversals(fit, 0.004)
    print("\nPredicted life at Delta_eps/2 = 0.004: %.0f reversals (%.0f cycles)"
          % (two_nf, two_nf / 2))

    # 3) Mean-stress correction (SWT) for a cycle with tensile mean
    sar = lcf.equivalent_fully_reversed_stress(400.0, 120.0, "swt")
    print("SWT equivalent fully-reversed stress (sa=400, sm=120): %.1f MPa" % sar)

    # 4) Save the fit via the service/store, then recall it
    svc = LcfService(OUT / ".lcfstore")
    svc.fit_strain_life(total_strain_amp, stress_amp, reversals, E,
                        min_plastic_strain=5e-4, material="SAE1137")
    rec = svc.recall("SAE1137", "strain_life_fit")
    print("\nRecalled fit for material:", rec["key"], "-> c =", rec["value"]["coffin_manson"]["c"])

    # 5) Plot the strain-life curve with the data
    fig = plots.plot_strain_life(fit, reversals=reversals, total_strain_amp=total_strain_amp)
    path = plots.savefig(fig, OUT / "strain_life.png")
    print("\nWrote", path)


if __name__ == "__main__":
    main()
