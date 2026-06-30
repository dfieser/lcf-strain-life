"""Read a machine-style CSV and run the full single-test analysis.

This mirrors a real test-machine export: a short metadata header block, then a
column header row, then the data. It shows the ingestion path that a user with an
Instron or MTS file would take, end to end, and writes a hysteresis plot.

Run from the repo root with the project installed:

    python examples/csv_ingestion_demo.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import lcf
from lcf import plots
from lcf.models import TestMetadata

OUT = Path(__file__).parent / "output"


def write_sample_csv(path: Path) -> None:
    """Write a small machine-style CSV with a metadata header block."""
    area = 50.0          # mm^2
    eps_amp = 0.006      # engineering strain amplitude
    stress_amp = 420.0   # MPa
    n_cycles = 8
    samples_per_cycle = 200
    periods = n_cycles + 1
    n = periods * samples_per_cycle + 1
    theta = np.linspace(0.0, 2.0 * np.pi * periods, n)
    time = np.linspace(0.0, float(periods), n)
    strain = eps_amp * np.sin(theta)
    stress = stress_amp * np.sin(theta - 0.3)      # phase lag opens the loop
    force = stress * area                          # N, since MPa times mm^2 is N

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("# Test machine export, simulated\n")
        f.write("# Specimen: SAMPLE-1, area 50 mm^2\n")
        f.write("# Control: axial strain, R = -1\n")
        f.write("Time (s),Axial Strain (mm/mm),Axial Force (N)\n")
        for t, e, fo in zip(time, strain, force):
            f.write(f"{t:.5f},{e:.6e},{fo:.3f}\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "sample_test.csv"
    write_sample_csv(csv_path)
    print("Wrote sample machine-style file:", csv_path)

    meta = TestMetadata(name="SAMPLE-1", area=50.0, E=200000.0, material="SAMPLE")
    test = lcf.read_csv(
        csv_path,
        metadata=meta,
        column_map={
            "Time (s)": "time",
            "Axial Strain (mm/mm)": "strain",
            "Axial Force (N)": "force",
        },
        skiprows=3,        # skip the three metadata header lines
    )
    print("Ingested samples:", len(test))

    analysis = lcf.analyze_test(test)
    s = analysis.summary
    print("\nHalf-life summary")
    print("  cycles detected:        %d" % s["n_cycles"])
    print("  stress amplitude:       %.1f MPa" % s["stress_amp"])
    print("  total strain amplitude: %.5f" % s["total_strain_amp"])
    print("  plastic strain amp:     %.5f" % s["plastic_strain_amp"])
    print("  mean stress:            %.1f MPa" % s["mean_stress"])
    print("  energy at half-life:    %.3f MJ/m^3" % s["energy_half_life"])

    fig = plots.plot_hysteresis(test, analysis.reduced, cycles=[1, analysis.reduced.half_life_cycle])
    path = plots.savefig(fig, OUT / "sample_hysteresis.png")
    print("\nWrote", path)


if __name__ == "__main__":
    main()
