"""Multiaxial fatigue, survey-only stub (ADR-0010, research section 5).

This module provides the critical-plane damage-parameter functions and a plane
search interface, enough to evaluate a parameter once the plane quantities are
known. It does NOT yet compute plane quantities from a full stress and strain
tensor history with a rotating-plane search. That, with shear strain-life
constants and tensor input, is the first Phase 3 item.

Parameters:
- Fatemi-Socie, shear based, for shear-cracking ductile metals.
- Brown-Miller, combined shear and normal strain on the maximum-shear plane.
- Smith-Watson-Topper multiaxial, for tensile-cracking materials.
- von Mises equivalent strain, for proportional-loading screening only.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "fatemi_socie",
    "brown_miller",
    "swt_multiaxial",
    "von_mises_equivalent_strain",
    "critical_plane_search",
]


def fatemi_socie(shear_strain_amp, sigma_n_max, *, sigma_y: float, k: float = 1.0) -> float:
    """Fatemi-Socie parameter ``(dgamma_max/2)(1 + k*sigma_n_max/sigma_y)``.

    ``shear_strain_amp`` is the maximum shear strain amplitude on the critical
    plane, ``sigma_n_max`` the maximum normal stress on that plane. The normal
    stress term captures extra hardening under non-proportional loading.
    """
    if sigma_y <= 0:
        raise ValueError("sigma_y must be positive")
    return float(shear_strain_amp * (1.0 + k * sigma_n_max / sigma_y))


def brown_miller(shear_strain_amp, normal_strain_amp, *, S: float = 1.0) -> float:
    """Brown-Miller parameter ``dgamma_max/2 + S*deps_n`` on the max-shear plane."""
    return float(shear_strain_amp + S * normal_strain_amp)


def swt_multiaxial(sigma_n_max, normal_strain_amp) -> float:
    """Multiaxial SWT parameter ``sigma_n_max * deps_1/2`` on the max-principal plane."""
    return float(sigma_n_max * normal_strain_amp)


def von_mises_equivalent_strain(eps_x, eps_y, eps_z,
                                gamma_xy=0.0, gamma_yz=0.0, gamma_zx=0.0) -> float:
    """von Mises equivalent strain for proportional-loading screening.

    Incompressible form. For a uniaxial state with transverse strains ``-0.5*eps``
    this returns ``eps``. Cannot represent non-proportional or mean-stress
    effects, so use it only for proportional screening.
    """
    normal = (eps_x - eps_y) ** 2 + (eps_y - eps_z) ** 2 + (eps_z - eps_x) ** 2
    shear = 1.5 * (gamma_xy**2 + gamma_yz**2 + gamma_zx**2)
    return float(np.sqrt(2.0) / 3.0 * np.sqrt(normal + shear))


def critical_plane_search(parameter_fn, *, angles=None) -> dict:
    """Search candidate plane angles for the one that maximizes a damage parameter.

    ``parameter_fn`` maps a plane angle in degrees to the damage parameter on
    that plane. Returns the critical angle, the maximum parameter, and the full
    swept arrays. This is the plane-search interface, the per-angle plane
    quantities are supplied by the caller until the Phase 3 tensor engine exists.
    """
    if angles is None:
        angles = np.arange(0.0, 180.0, 1.0)
    angles = np.asarray(angles, dtype=np.float64)
    values = np.array([parameter_fn(float(a)) for a in angles], dtype=np.float64)
    k = int(np.argmax(values))
    return {
        "critical_angle": float(angles[k]),
        "max_parameter": float(values[k]),
        "angles": angles,
        "values": values,
    }
