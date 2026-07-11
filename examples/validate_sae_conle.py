"""Reproduce the Conle SAE smooth-specimen variable-amplitude tests.

The validation case behind the variable-amplitude engine's evidence note.
Downloads the three SAE Fatigue Design and Evaluation committee histories
(GPL, fde.uwaterloo.ca), scales them so the +-999 history peak equals the
0.010 strain of the tests, runs the Masing memory engine with the SAE10B20
f512 constants from Conle's own GPL data file, and compares blocks to
failure against the experimental values from his thesis.

Sources, all public:
- Histories: fde.uwaterloo.ca/Fde/Loads/Keyhole/{name}.txt, GPL v2+.
- Constants: fde.uwaterloo.ca/Fde/Materials/Steel/BoronSteel/
  sae10B20_f512_fitted.html, GPL v2+. K' 118.0 ksi, n' 0.0586,
  sigma_f' 123.2 ksi, b -0.0437, eps_f' 2.0907, c -0.7450, E 30000 ksi.
  Ref: F. A. Conle, MSc thesis, University of Waterloo, March 1974.
- Experimental blocks: the committee's published summary of Conle's Table 2
  (smooth specimens, strain control, full-length histories, peak 0.010),
  fde.uwaterloo.ca/Fde/Loads/Keyhole/faconle2.html.

Result as of 2026-07-11: transmission and bracket predict within a factor
of two of the experimental geometric mean, suspension is about three times
non-conservative, and all three lean non-conservative, consistent with the
documented scatter of linear-damage local-strain predictions on this
program. Run it yourself:

    python examples/validate_sae_conle.py
"""

from __future__ import annotations

import math
import urllib.request

from lcf import labio, simulate

KSI = 6.894757  # MPa per ksi

E = 30000.0 * KSI
K_PRIME = 118.0 * KSI
N_PRIME = 0.0586
SIGMA_F = 123.2 * KSI
B = -0.0437
EPS_F = 2.0907
C = -0.7450

PEAK_STRAIN = 0.010

#: Experimental blocks to failure, Conle thesis Table 2, full histories.
EXPERIMENTS = {
    "transmission": [50.0, 38.0],
    "bracket": [4.39, 4.63],
    "suspension": [50.3, 73.8, 83.8],
}

BASE = "https://fde.uwaterloo.ca/Fde/Loads/Keyhole/{}.txt"


def fetch_history(name: str) -> list[float]:
    with urllib.request.urlopen(BASE.format(name), timeout=30) as fh:
        text = fh.read().decode("utf-8", errors="replace")
    return labio.read_fde_history(text)


def main() -> None:
    print(f"{'history':13s} {'experimental':>20s} {'predicted SWT':>14s} "
          f"{'pred/exp':>9s}")
    for name, exp in EXPERIMENTS.items():
        raw = fetch_history(name)
        scale = PEAK_STRAIN / max(abs(v) for v in raw)
        out = simulate.variable_amplitude_life(
            [v * scale for v in raw], E=E, K_prime=K_PRIME, n_prime=N_PRIME,
            sigma_f=SIGMA_F, b=B, eps_f=EPS_F, c=C,
        )
        pred = out["blocks_to_failure"]
        geo_mean = math.exp(sum(math.log(v) for v in exp) / len(exp))
        print(f"{name:13s} {str(exp):>20s} {pred:14.1f} {pred / geo_mean:9.2f}")
    print(
        "\nA ratio of 1.0 is a perfect prediction, above 1.0 is"
        " non-conservative. The experimental scatter within one history is"
        " itself up to 1.7x."
    )


if __name__ == "__main__":
    main()
