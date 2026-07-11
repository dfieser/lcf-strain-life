"""Reproduce the SAE keyhole benchmark cases, notched member, load input.

The load-input validation behind the variable-amplitude engine's evidence
note. The SAE Fatigue Design and Evaluation committee's keyhole program
(documented in SAE AE-6, Wetzel ed., 1977) tested a notched member under
the committee's service histories. The eFatigue benchmark page documented
the analysis inputs and results, the site is offline and the page survives
on the Internet Archive:

    web.archive.org/web/20251215150910/
        https://www.efatigue.com/benchmarks/SAE_keyhole/SAE_keyhole.html

From that page: nominal stress S(MPa) = 11.2 P(kN), Kt = 3, the committee
material constants below, and two fully documented cases:

- CR1, RQC-100, constant amplitude at +-13.3 kN: experimental life 605,000
  cycles to a 2.5 mm crack, the benchmark's own strain-life calculation
  211,000 cycles (initiation methods run conservative against a
  crack-length-based life).
- SM2, Man-Ten, suspension history at 26.7 kN peak (nominal scale 299 MPa):
  experimental 1750, 2240, and 1410 blocks, the benchmark's own calculation
  2892 blocks.

K' and n' come from Wu, Zhang, Paraschivoiu, Materials 17 (2024) 4521,
CC BY 4.0. The suspension history downloads from the committee's public
archive at run time (GPL). Run it yourself:

    python examples/validate_sae_keyhole.py
"""

from __future__ import annotations

import math
import urllib.request

from lcf import labio, simulate

MANTEN = dict(E=203000.0, sigma_f=915.0, b=-0.095, eps_f=0.26, c=-0.47,
              K_prime=1200.6, n_prime=0.2)
RQC100 = dict(E=203000.0, sigma_f=1160.0, b=-0.075, eps_f=1.06, c=-0.75,
              K_prime=1131.6, n_prime=0.1)
KT = 3.0
MPA_PER_KN = 11.2

HISTORY_URL = "https://fde.uwaterloo.ca/Fde/Loads/Keyhole/suspension.txt"


def main() -> None:
    print("CR1: RQC-100 keyhole, constant amplitude +-13.3 kN "
          f"(nominal +-{MPA_PER_KN * 13.3:.0f} MPa, Kt {KT:g})")
    out = simulate.variable_amplitude_life(
        nominal_stress_history=[MPA_PER_KN * 13.3, -MPA_PER_KN * 13.3],
        Kt=KT, **RQC100,
    )
    print(f"  our SWT prediction: {out['blocks_to_failure']:,.0f} cycles")
    print("  benchmark's strain-life calculation: 211,000 cycles")
    print("  experimental (2.5 mm crack): 605,000 cycles")

    print("\nSM2: Man-Ten keyhole, suspension history, 26.7 kN peak "
          "(nominal scale 299 MPa)")
    with urllib.request.urlopen(HISTORY_URL, timeout=30) as fh:
        text = fh.read().decode("utf-8", errors="replace")
    vals = labio.read_fde_history(text)
    scale = 299.0 / max(abs(v) for v in vals)
    nominal = [v * scale for v in vals]
    exp = [1750.0, 2240.0, 1410.0]
    geo_mean = math.exp(sum(math.log(v) for v in exp) / len(exp))
    for model in ("swt", "morrow"):
        out = simulate.variable_amplitude_life(
            nominal_stress_history=nominal, Kt=KT,
            mean_stress_model=model, **MANTEN,
        )
        blocks = out["blocks_to_failure"]
        print(f"  our {model} prediction: {blocks:,.0f} blocks "
              f"(pred/exp geo-mean = {blocks / geo_mean:.2f})")
    print(f"  benchmark's calculation: 2,892 blocks")
    print(f"  experimental: {exp} blocks (geo-mean {geo_mean:,.0f})")


if __name__ == "__main__":
    main()
