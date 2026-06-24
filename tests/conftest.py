"""Shared test fixtures.

Two kinds of fixtures:

* ``synthetic_cyclic``: a deterministic elliptical hysteresis signal with known
  analytic answers (peak/valley, mean, loop area), for testing ingestion, cycle
  reduction, and per-cycle metrics.
* ``sae1137``: published per-test reduced strain-life data (Williams, Lee &
  Rilly, *Int. J. Fatigue* 25 (2003) 427-436), for golden-value validation of
  the strain-life fits. See docs/design/IMPLEMENTATION_REFERENCE.md §11.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest


# --------------------------------------------------------------------------- #
# Synthetic elliptical-loop signal
# --------------------------------------------------------------------------- #
@dataclass
class SyntheticCyclic:
    time: np.ndarray
    strain: np.ndarray          # engineering strain (== true here, small values)
    force: np.ndarray           # N
    area: float                 # mm^2
    n_cycles: int
    eps_amp: float              # strain amplitude
    stress_amp: float           # MPa
    phase_lag: float            # radians (controls loop openness)
    samples_per_cycle: int

    @property
    def energy_per_cycle(self) -> float:
        """Analytic enclosed area of one elliptical loop = π·σa·εa·sin(δ) (MJ/m³)."""
        return np.pi * self.stress_amp * self.eps_amp * np.sin(self.phase_lag)


def _make_synthetic(
    n_cycles=8, eps_amp=0.01, stress_amp=400.0, phase_lag=0.35,
    samples_per_cycle=720, area=50.0,
) -> SyntheticCyclic:
    # Generate (n_cycles + 1) full sine periods so that peak-to-peak segmentation
    # yields exactly ``n_cycles`` complete closed loops (the first/last partial
    # half-oscillations are not counted). strain = εa sin(theta).
    periods = n_cycles + 1
    n = periods * samples_per_cycle + 1
    theta = np.linspace(0.0, 2.0 * np.pi * periods, n)
    strain = eps_amp * np.sin(theta)
    stress = stress_amp * np.sin(theta - phase_lag)  # MPa, lag opens the loop
    force = stress * area  # N (since stress in MPa == N/mm^2, force = stress*area)
    time = np.linspace(0.0, float(periods), n)
    return SyntheticCyclic(
        time=time, strain=strain, force=force, area=area, n_cycles=n_cycles,
        eps_amp=eps_amp, stress_amp=stress_amp, phase_lag=phase_lag,
        samples_per_cycle=samples_per_cycle,
    )


@pytest.fixture
def synthetic_cyclic() -> SyntheticCyclic:
    return _make_synthetic()


@pytest.fixture
def make_synthetic():
    """Factory so individual tests can vary parameters."""
    return _make_synthetic


# --------------------------------------------------------------------------- #
# SAE 1137 golden strain-life dataset (Williams, Lee & Rilly 2003)
# --------------------------------------------------------------------------- #
@dataclass
class GoldenStrainLife:
    total_strain_amp: np.ndarray
    stress_amp: np.ndarray           # MPa, half-life
    E: np.ndarray                    # MPa, per test
    reversals: np.ndarray            # 2Nf
    elastic_strain_amp: np.ndarray
    plastic_strain_amp: np.ndarray
    # Published reference constants (Williams/Lee/Rilly, life-on-strain orientation)
    ref: dict = field(default_factory=dict)


@pytest.fixture
def sae1137() -> GoldenStrainLife:
    return GoldenStrainLife(
        total_strain_amp=np.array([0.00900, 0.00700, 0.00500, 0.00300, 0.00200, 0.00175]),
        stress_amp=np.array([553.0, 522.0, 464.0, 405.0, 350.0, 319.0]),
        E=np.array([208229.0, 206850.0, 208919.0, 210297.0, 210298.0, 206161.0]),
        reversals=np.array([4234.0, 7398.0, 14768.0, 77104.0, 437498.0, 3327958.0]),
        elastic_strain_amp=np.array([0.002656, 0.002523, 0.002221, 0.001925, 0.001663, 0.001548]),
        plastic_strain_amp=np.array([0.006344, 0.004477, 0.002779, 0.001075, 0.000337, 0.000202]),
        ref={
            "c": -0.6207,           # fatigue ductility exponent (published median)
            "eps_f": 1.104,         # fatigue ductility coefficient (published median)
            "transition_reversals": 22000.0,  # approx
            "E_nominal": 208000.0,
        },
    )
