"""Variable-amplitude life from a real SAE service load history.

Downloads one of the SAE Fatigue Design and Evaluation committee load
histories (transmission, bracket, or suspension) from the committee's public
archive at fde.uwaterloo.ca, scales it to a chosen peak strain, and runs the
Masing memory simulation to a damage-per-block and blocks-to-failure result.

The histories are distributed by the FD&E committee under the GNU GPL and are
fetched at run time rather than bundled. The scaling here is a demonstration
choice, not the original test loading, and the material constants below are
representative steel values. The variable-amplitude engine is experimental,
see the notes it returns.

Run from the repo root with the project installed and internet access:

    python examples/variable_amplitude_sae.py [transmission|bracket|suspension]
"""

from __future__ import annotations

import sys
import urllib.request

from lcf import simulate

BASE = "https://fde.uwaterloo.ca/Fde/Loads/Keyhole/{}.txt"

# Representative steel constants for the demonstration. Replace with your
# material's fitted values for real work.
E = 200000.0        # MPa
K_PRIME = 1650.0    # MPa
N_PRIME = 0.15
SIGMA_F = 900.0     # MPa
B = -0.10
EPS_F = 0.60
C = -0.55

PEAK_STRAIN = 0.008  # the history's largest excursion is scaled to this


def fetch_history(name: str) -> list[float]:
    """Download an FD&E history and parse it, keeping its GPL header intact."""
    url = BASE.format(name)
    print(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=30) as fh:
        text = fh.read().decode("utf-8", errors="replace")
    values = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # occasional progress markers look like "-112 : 1500"
        values.append(float(line.split(":")[0]))
    return values


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "suspension"
    raw = fetch_history(name)
    scale = PEAK_STRAIN / max(abs(v) for v in raw)
    history = [v * scale for v in raw]
    print(f"{name}: {len(raw)} points, peak strain scaled to {PEAK_STRAIN}")

    out = simulate.variable_amplitude_life(
        history, E=E, K_prime=K_PRIME, n_prime=N_PRIME,
        sigma_f=SIGMA_F, b=B, eps_f=EPS_F, c=C,
    )

    total = sum(lp["count"] for lp in out["loops"])
    print(f"\nclosed loops: {total:.0f} ({out['n_loops']} unique)")
    print(f"damage per block: {out['damage_per_block']:.4g}")
    print(f"blocks to failure: {out['blocks_to_failure']:.1f}")
    print("\nfive most damaging loops:")
    for lp in out["loops"][:5]:
        print(f"  strain amp {lp['strain_amp']:.5f}, mean stress "
              f"{lp['stress_mean']:7.1f} MPa, count {lp['count']:5.1f}, "
              f"damage {lp['damage']:.3g}")
    print("\nnotes:")
    for note in out["notes"]:
        print(f"  - {note}")


if __name__ == "__main__":
    main()
