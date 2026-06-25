"""Elevated-temperature fatigue: frequency effects and creep-fatigue.

Three capabilities (ADR-0010, research section 4):

1. Frequency-modified Coffin-Manson, where the plastic strain-life coefficient
   scales with cyclic frequency, ``C_f = C_o * (f/f_ref)**(k-1)``.
2. Linear time-fraction creep-fatigue damage, ``D = sum(n/N_f) + sum(t/t_r)``,
   with a bilinear creep-fatigue interaction (D-diagram) envelope check.
3. Temperature-dependent strain-life constants stored as a table and
   interpolated, linear in temperature for the exponents and the modulus,
   log-linear for the coefficients.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "frequency_modified_coefficient",
    "frequency_modified_plastic_strain",
    "frequency_modified_reversals",
    "CreepFatigueResult",
    "creep_fatigue_damage",
    "creep_fatigue_envelope_allowable",
    "creep_fatigue_envelope_check",
    "interpolate_constants",
]


def frequency_modified_coefficient(eps_f_coeff: float, *, frequency: float,
                                   k: float, freq_ref: float = 1.0) -> float:
    """Frequency-modified Coffin-Manson coefficient ``C_f = C_o*(f/f_ref)**(k-1)``.

    Reduces to ``C_o`` at the reference frequency. The exponent ``k`` is material
    specific and sets the strength of the frequency effect.
    """
    return eps_f_coeff * (frequency / freq_ref) ** (k - 1.0)


def frequency_modified_plastic_strain(reversals, eps_f_coeff: float, c: float, *,
                                      frequency: float, k: float,
                                      freq_ref: float = 1.0):
    """Plastic strain amplitude from the frequency-modified Coffin-Manson law."""
    tn = np.asarray(reversals, dtype=np.float64)
    c_f = frequency_modified_coefficient(eps_f_coeff, frequency=frequency, k=k, freq_ref=freq_ref)
    return c_f * tn**c


def frequency_modified_reversals(plastic_strain_amp, eps_f_coeff: float, c: float, *,
                                 frequency: float, k: float, freq_ref: float = 1.0) -> float:
    """Invert the frequency-modified Coffin-Manson law for reversals to failure."""
    c_f = frequency_modified_coefficient(eps_f_coeff, frequency=frequency, k=k, freq_ref=freq_ref)
    return float((float(plastic_strain_amp) / c_f) ** (1.0 / c))


@dataclass
class CreepFatigueResult:
    """Linear time-fraction creep-fatigue damage summary."""

    d_fatigue: float
    d_creep: float
    d_total: float
    failed: bool
    envelope: float


def creep_fatigue_damage(cycle_counts, fatigue_lives, hold_times, rupture_times,
                         *, envelope: float = 1.0) -> CreepFatigueResult:
    """Linear time-fraction (Robinson) plus Miner creep-fatigue damage.

    ``D = sum(n_i/N_f,i) + sum(t_j/t_r,j)``. Failure when ``D`` reaches the
    envelope value, 1.0 by default. The fatigue and creep terms are independent
    lists, so a block may have any number of cycle levels and hold periods.
    """
    n = np.asarray(cycle_counts, dtype=np.float64)
    nf = np.asarray(fatigue_lives, dtype=np.float64)
    t = np.asarray(hold_times, dtype=np.float64)
    tr = np.asarray(rupture_times, dtype=np.float64)
    if np.any(nf <= 0) or np.any(tr <= 0):
        raise ValueError("fatigue lives and rupture times must be positive")
    d_f = float(np.sum(n / nf))
    d_c = float(np.sum(t / tr))
    d_total = d_f + d_c
    return CreepFatigueResult(
        d_fatigue=d_f, d_creep=d_c, d_total=d_total,
        failed=d_total >= envelope, envelope=envelope,
    )


def creep_fatigue_envelope_allowable(d_fatigue: float, knee_f: float, knee_c: float) -> float:
    """Allowable creep damage on the bilinear D-diagram for a given fatigue damage.

    The envelope runs from (1, 0) through the material knee (knee_f, knee_c) to
    (0, 1). Returns the creep-damage value on that boundary at ``d_fatigue``.
    """
    if d_fatigue <= knee_f:
        # segment from (0, 1) to (knee_f, knee_c)
        frac = d_fatigue / knee_f if knee_f > 0 else 0.0
        return 1.0 + frac * (knee_c - 1.0)
    if d_fatigue >= 1.0:
        return 0.0
    # segment from (knee_f, knee_c) to (1, 0)
    frac = (d_fatigue - knee_f) / (1.0 - knee_f)
    return knee_c + frac * (0.0 - knee_c)


def creep_fatigue_envelope_check(d_fatigue: float, d_creep: float, *,
                                 knee: tuple[float, float] = (0.3, 0.3)) -> dict:
    """Check a (D_fatigue, D_creep) point against the bilinear D-diagram envelope.

    Returns the allowable creep damage at this fatigue damage, whether the point
    is safe (on or inside the envelope), and the margin (allowable minus actual).
    """
    allowable = creep_fatigue_envelope_allowable(d_fatigue, knee[0], knee[1])
    return {
        "allowable_creep": allowable,
        "safe": bool(d_creep <= allowable and d_fatigue <= 1.0),
        "margin": allowable - d_creep,
    }


def interpolate_constants(table, temperature: float, *, log_coeffs: bool = True) -> dict:
    """Interpolate temperature-dependent strain-life constants.

    ``table`` is a mapping with a ``T`` sequence and any of ``E``, ``sigma_f``,
    ``b``, ``eps_f``, ``c``. Exponents and the modulus interpolate linearly in
    temperature. Coefficients interpolate log-linearly when ``log_coeffs`` is
    True. Temperatures outside the table clamp to the nearest end.
    """
    T = np.asarray(table["T"], dtype=np.float64)
    order = np.argsort(T)
    T = T[order]
    out: dict = {}
    coeff_keys = {"sigma_f", "eps_f", "K"}
    for key, values in table.items():
        if key == "T":
            continue
        v = np.asarray(values, dtype=np.float64)[order]
        if log_coeffs and key in coeff_keys:
            out[key] = float(10.0 ** np.interp(temperature, T, np.log10(v)))
        else:
            out[key] = float(np.interp(temperature, T, v))
    return out
