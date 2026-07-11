"""Variable-amplitude local strain simulation with material memory (ADR-0016).

Walks a strain reversal history through the cyclic stress-strain response:
the initial loading follows the Ramberg-Osgood cyclic curve from zero to the
first (rotated, largest) reversal, every subsequent branch follows the
doubled Masing curve from its reversal origin, and material memory follows
the same stack rule as three-point rainflow counting: when an excursion from
the current reversal covers the previous branch range, the interior loop
closes and the path continues on the outer branch as if the interruption
never happened.

For damage the history is treated as a repeating block, rotated to the
global maximum and wrapped so every reversal closes, the same convention as
:func:`lcf.counting.extract_cycles` with ``close_residue=True``. Per-loop
life comes from the existing solvers in :mod:`lcf.life`, SWT by default.

Model limits, stated plainly: stabilized cyclic properties are assumed
throughout, and cycle-dependent mean stress relaxation and ratcheting are
not modeled. Predictions have not yet been validated against a published
variable-amplitude dataset and are labeled experimental until they are.

References: Masing, Proc. 2nd Int. Congress for Applied Mechanics, Zurich,
1926 (the doubled branch). Dowling, Mechanical Behavior of Materials, 4th
ed., ch. 14 (the local strain approach). ASTM E1049 (the memory rule).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import optimize

from . import counting, life

__all__ = [
    "ClosedLoop",
    "HysteresisSimulation",
    "simulate_hysteresis",
    "variable_amplitude_life",
]

_CLOSE_TOL = 1e-12


@dataclass
class ClosedLoop:
    """One closed (or, in raw mode, half-counted) hysteresis loop."""

    strain_amp: float
    strain_mean: float
    stress_amp: float
    stress_mean: float
    stress_max: float
    count: float          # 1.0 closed loop, 0.5 unclosed half cycle


@dataclass
class HysteresisSimulation:
    """Simulated stress-strain response of a strain reversal history."""

    loops: list[ClosedLoop]
    path: list[tuple[float, float]]   # (strain, stress) at each reversal state
    notes: list[str] = field(default_factory=list)


def _check_positive(**params) -> None:
    for name, value in params.items():
        if not (np.isfinite(value) and value > 0):
            raise ValueError(f"{name} must be positive and finite, got {value}")


def _cyclic_stress(strain: float, E: float, K: float, n: float) -> float:
    """Invert the Ramberg-Osgood cyclic curve, sign-symmetric."""
    if strain == 0.0:
        return 0.0
    mag = abs(strain)
    upper = E * mag  # elastic line bounds the stress from above
    s = optimize.brentq(
        lambda x: x / E + (x / K) ** (1.0 / n) - mag, 0.0, upper
    )
    return float(np.sign(strain) * s)


def _branch_stress_range(strain_range: float, E: float, K: float, n: float) -> float:
    """Invert the doubled (Masing) branch for a strain range."""
    if strain_range == 0.0:
        return 0.0
    upper = E * strain_range
    return float(optimize.brentq(
        lambda x: x / E + 2.0 * (x / (2.0 * K)) ** (1.0 / n) - strain_range,
        0.0, upper,
    ))


def _loop(e0, s0, e1, s1, count) -> ClosedLoop:
    return ClosedLoop(
        strain_amp=abs(e1 - e0) / 2.0,
        strain_mean=(e0 + e1) / 2.0,
        stress_amp=abs(s1 - s0) / 2.0,
        stress_mean=(s0 + s1) / 2.0,
        stress_max=max(s0, s1),
        count=count,
    )


def simulate_hysteresis(
    strain_history,
    *,
    E: float,
    K_prime: float,
    n_prime: float,
    close_residue: bool = True,
) -> HysteresisSimulation:
    """Simulate the cyclic stress response of a strain history.

    ``strain_history`` may be a raw sampled series, it is reduced to turning
    points first. With ``close_residue=True`` (the default, and the damage
    convention) the reversal sequence is rotated to the global maximum and
    wrapped, treating the history as one repeating block so every reversal
    closes into a full loop. With ``close_residue=False`` the original order
    is kept, unclosed reversals are reported as half cycles, and the
    ``path`` traces the stress state reversal by reversal for inspection.
    """
    _check_positive(E=E, K_prime=K_prime, n_prime=n_prime)
    pts = [v for _, v in counting.reversals(strain_history)]
    if len(pts) < 2:
        raise ValueError(
            f"need at least 2 turning points to simulate, got {len(pts)}. "
            "Provide a strain history with at least one reversal."
        )

    if close_residue:
        kmax = int(np.argmax(pts))
        rotated = pts[kmax:] + pts[:kmax] + [pts[kmax]]
        seq = [v for _, v in counting._reduce_points(list(enumerate(rotated)))]
    else:
        seq = pts

    loops: list[ClosedLoop] = []
    notes: list[str] = []
    stack: list[tuple[float, float]] = [(seq[0], _cyclic_stress(seq[0], E, K_prime, n_prime))]
    path: list[tuple[float, float]] = [stack[0]]

    for e_new in seq[1:]:
        while len(stack) >= 2:
            e1, s1 = stack[-1]
            e0, s0 = stack[-2]
            prior = abs(e1 - e0)
            if abs(e_new - e1) < prior - _CLOSE_TOL * max(1.0, prior):
                break
            if len(stack) == 2 and not close_residue:
                # the range contains the start of an unrotated history:
                # E1049 counts it as a half cycle and drops the oldest point
                loops.append(_loop(e0, s0, e1, s1, 0.5))
                stack.pop(-2)
            else:
                loops.append(_loop(e0, s0, e1, s1, 1.0))
                stack.pop()
                stack.pop()
        if stack:
            e_o, s_o = stack[-1]
            ds = _branch_stress_range(abs(e_new - e_o), E, K_prime, n_prime)
            s_new = s_o + float(np.sign(e_new - e_o)) * ds
        else:
            # everything closed back to the largest tip, reload on the
            # cyclic curve (only reachable in the rotated mode)
            s_new = _cyclic_stress(e_new, E, K_prime, n_prime)
        stack.append((e_new, s_new))
        path.append((e_new, s_new))

    if not close_residue and len(stack) > 1:
        for k in range(len(stack) - 1):
            e0, s0 = stack[k]
            e1, s1 = stack[k + 1]
            loops.append(_loop(e0, s0, e1, s1, 0.5))
        notes.append(
            f"{len(stack) - 1} unclosed reversal(s) counted as half cycles. "
            "Use close_residue=True to treat the history as a repeating block."
        )

    return HysteresisSimulation(loops=loops, path=path, notes=notes)


def variable_amplitude_life(
    strain_history,
    *,
    E: float,
    K_prime: float,
    n_prime: float,
    sigma_f: float,
    b: float,
    eps_f: float,
    c: float,
    mean_stress_model: str = "swt",
) -> dict:
    """Blocks to failure for a repeating strain history block.

    Simulates the stress response with material memory, aggregates the
    closed loops, computes each loop's life with the chosen mean-stress
    model (``swt`` from the loop's maximum stress, ``morrow`` from its mean
    stress, ``none`` for the uncorrected curve), and Miner-sums the damage.
    ``blocks_to_failure`` is None when no loop is damaging.
    """
    model = str(mean_stress_model).strip().lower()
    if model not in ("swt", "morrow", "none"):
        raise ValueError(
            f"unknown mean_stress_model {mean_stress_model!r}, "
            "use 'swt', 'morrow', or 'none'"
        )
    sim = simulate_hysteresis(
        strain_history, E=E, K_prime=K_prime, n_prime=n_prime, close_residue=True
    )

    grouped: dict[tuple, dict] = {}
    for lp in sim.loops:
        key = (round(lp.strain_amp, 12), round(lp.strain_mean, 12))
        if key in grouped:
            grouped[key]["count"] += lp.count
        else:
            grouped[key] = {
                "strain_amp": lp.strain_amp, "strain_mean": lp.strain_mean,
                "stress_amp": lp.stress_amp, "stress_mean": lp.stress_mean,
                "stress_max": lp.stress_max, "count": lp.count,
            }

    notes = list(sim.notes)
    damage = 0.0
    n_nondamaging = 0
    for g in grouped.values():
        cycles_to_failure = None
        try:
            if g["strain_amp"] <= 0.0:
                reversals = None
            elif model == "swt":
                if g["stress_max"] <= 0.0:
                    reversals = None
                else:
                    reversals = life.predict_reversals_swt(
                        g["stress_max"], g["strain_amp"],
                        sigma_f, b, eps_f, c, E,
                    )
            elif model == "morrow":
                reversals = life.predict_reversals_morrow(
                    g["strain_amp"], g["stress_mean"],
                    sigma_f, b, eps_f, c, E,
                )
            else:
                reversals = life.predict_reversals_from_total_strain(
                    g["strain_amp"], sigma_f, b, eps_f, c, E,
                )
        except ValueError:
            reversals = None  # below the solver bracket, effectively non-damaging
        if reversals is not None and np.isfinite(reversals) and reversals > 0:
            cycles_to_failure = reversals / 2.0
            g["damage"] = g["count"] / cycles_to_failure
            damage += g["damage"]
        else:
            n_nondamaging += 1
            g["damage"] = 0.0
        g["cycles_to_failure"] = cycles_to_failure

    if n_nondamaging:
        notes.append(
            f"{n_nondamaging} loop(s) assigned no damage: no tensile peak "
            "stress under SWT, or the amplitude is below the life-solver "
            "range."
        )
    notes.append(
        "stabilized cyclic properties assumed, mean stress relaxation and "
        "ratcheting are not modeled."
    )

    loops = sorted(grouped.values(), key=lambda g: -g["damage"])
    return {
        "mean_stress_model": model,
        "n_loops": len(loops),
        "loops": loops,
        "damage_per_block": damage,
        "blocks_to_failure": (1.0 / damage) if damage > 0 else None,
        "notes": notes,
    }
