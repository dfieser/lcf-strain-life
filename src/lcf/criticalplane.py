"""Tensor critical-plane search (ADR-0018, P5).

Given strain (and optionally stress) tensor component histories sampled
over one cycle, scan candidate plane normals over a hemisphere grid,
resolve the per-plane quantities, and evaluate a critical-plane parameter
through the existing survey functions in :mod:`lcf.multiaxial`.

Conventions: strains are true strains, shear inputs and outputs are
ENGINEERING shear (gamma), stresses in MPa. The plane normal is
``n = (sin(phi) cos(theta), sin(phi) sin(theta), cos(phi))`` with theta
scanned over [0, 180) and phi over [0, 90] degrees. Per plane, the normal
strain amplitude is half the range of ``n . eps . n``, the shear amplitude
is half the longest chord of the in-plane shear vector path (meaningful for
non-proportional paths too), and the maximum normal stress is the maximum
of ``n . sigma . n`` over the cycle.

Scope, stated plainly: amplitudes come from the given cycle's path. Per
plane rainflow counting of long multiaxial histories is not implemented.

References: Fatemi and Socie 1988. Brown and Miller 1973. Socie and
Marquis, Multiaxial Fatigue, SAE, 2000.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import multiaxial

__all__ = ["PlaneResult", "resolve_plane", "search_critical_plane_tensor"]

_MAX_SAMPLES = 500


@dataclass
class PlaneResult:
    """Quantities and parameter value on one plane."""

    theta_deg: float
    phi_deg: float
    shear_strain_amp: float      # engineering shear amplitude
    normal_strain_amp: float
    sigma_n_max: float | None
    parameter: float


def _tensor_history(xx, yy, zz, xy, yz, zx, *, shear_is_engineering: bool):
    """Stack component histories into an (n, 3, 3) symmetric tensor array."""
    comps = [np.asarray(v, dtype=np.float64) for v in (xx, yy, zz, xy, yz, zx)]
    n = comps[0].size
    for c in comps:
        if c.size != n:
            raise ValueError(
                "all component histories must have the same length, got "
                f"{[c.size for c in comps]}"
            )
        if not np.all(np.isfinite(c)):
            raise ValueError("component histories contain NaN or inf")
    if n < 2:
        raise ValueError("need at least 2 samples over the cycle")
    if n > _MAX_SAMPLES:
        raise ValueError(
            f"history has {n} samples, the longest-chord search is O(n^2), "
            f"resample the cycle to at most {_MAX_SAMPLES} points"
        )
    half = 0.5 if shear_is_engineering else 1.0
    t = np.zeros((n, 3, 3))
    t[:, 0, 0], t[:, 1, 1], t[:, 2, 2] = comps[0], comps[1], comps[2]
    t[:, 0, 1] = t[:, 1, 0] = half * comps[3]
    t[:, 1, 2] = t[:, 2, 1] = half * comps[4]
    t[:, 0, 2] = t[:, 2, 0] = half * comps[5]
    return t


def _normal(theta_deg: float, phi_deg: float) -> np.ndarray:
    th, ph = np.radians(theta_deg), np.radians(phi_deg)
    return np.array(
        [np.sin(ph) * np.cos(th), np.sin(ph) * np.sin(th), np.cos(ph)]
    )


def resolve_plane(eps: np.ndarray, n: np.ndarray) -> tuple[float, float, np.ndarray]:
    """Resolve one plane: (engineering shear amp, normal strain amp, eps_n(t)).

    ``eps`` is the (m, 3, 3) tensor history. The shear amplitude is half the
    longest chord of the tangential (in-plane) strain-vector path times two,
    which turns the tensor measure into engineering shear.
    """
    traction = eps @ n                        # (m, 3)
    eps_n = traction @ n                      # (m,)
    tangential = traction - np.outer(eps_n, n)  # (m, 3), tensor shear vector
    # longest chord of the path, O(m^2)
    diffs = tangential[:, None, :] - tangential[None, :, :]
    chord = float(np.sqrt((diffs ** 2).sum(axis=2)).max())
    shear_amp_engineering = chord  # (chord/2 tensor amplitude) * 2
    normal_amp = float((eps_n.max() - eps_n.min()) / 2.0)
    return shear_amp_engineering, normal_amp, eps_n


def search_critical_plane_tensor(
    *,
    parameter: str,
    eps_xx,
    eps_yy,
    eps_zz,
    gamma_xy,
    gamma_yz,
    gamma_zx,
    sig_xx=None,
    sig_yy=None,
    sig_zz=None,
    tau_xy=None,
    tau_yz=None,
    tau_zx=None,
    sigma_y: float | None = None,
    k: float = 0.3,
    S: float = 1.0,
    grid_deg: float = 10.0,
) -> dict:
    """Scan plane normals and return the plane maximizing the parameter.

    ``parameter`` is ``fatemi_socie``, ``brown_miller``, or ``swt``.
    Fatemi-Socie and SWT need the stress history for the normal stress on
    the plane, Brown-Miller works from strains alone.
    """
    if parameter not in ("fatemi_socie", "brown_miller", "swt"):
        raise ValueError(
            "parameter must be fatemi_socie, brown_miller, or swt"
        )
    if not 0.5 <= grid_deg <= 45.0:
        raise ValueError("grid_deg must be between 0.5 and 45 degrees")
    eps = _tensor_history(eps_xx, eps_yy, eps_zz, gamma_xy, gamma_yz,
                          gamma_zx, shear_is_engineering=True)
    sig = None
    needs_stress = parameter in ("fatemi_socie", "swt")
    if needs_stress:
        if sig_xx is None:
            raise ValueError(
                f"{parameter} needs the stress history (sig_xx..tau_zx) for "
                "the normal stress on the plane"
            )
        sig = _tensor_history(sig_xx, sig_yy, sig_zz, tau_xy, tau_yz,
                              tau_zx, shear_is_engineering=False)
        if sig.shape != eps.shape:
            raise ValueError("stress and strain histories must align")
    sigma_y_val = 0.0
    if parameter == "fatemi_socie":
        if sigma_y is None or sigma_y <= 0:
            raise ValueError("fatemi_socie requires a positive sigma_y")
        sigma_y_val = float(sigma_y)

    best: PlaneResult | None = None
    thetas = np.arange(0.0, 180.0, grid_deg)
    phis = np.arange(0.0, 90.0 + 1e-9, grid_deg)
    for phi in phis:
        for theta in thetas:
            n = _normal(theta, phi)
            shear_amp, normal_amp, _ = resolve_plane(eps, n)
            sn_max = None
            if sig is not None:
                sn_max = float(((sig @ n) @ n).max())
            if parameter == "fatemi_socie":
                value = multiaxial.fatemi_socie(
                    shear_amp, sn_max, sigma_y=sigma_y_val, k=k
                )
            elif parameter == "brown_miller":
                value = multiaxial.brown_miller(shear_amp, normal_amp, S=S)
            else:
                value = multiaxial.swt_multiaxial(sn_max, normal_amp)
            if best is None or value > best.parameter:
                best = PlaneResult(
                    theta_deg=float(theta), phi_deg=float(phi),
                    shear_strain_amp=shear_amp, normal_strain_amp=normal_amp,
                    sigma_n_max=sn_max, parameter=float(value),
                )
    assert best is not None
    return {
        "parameter": parameter,
        "critical_plane": {
            "theta_deg": best.theta_deg, "phi_deg": best.phi_deg,
        },
        "shear_strain_amp": best.shear_strain_amp,
        "normal_strain_amp": best.normal_strain_amp,
        "sigma_n_max": best.sigma_n_max,
        "value": best.parameter,
        "grid_deg": float(grid_deg),
        "notes": [
            "amplitudes are resolved from the given cycle's path, per-plane "
            "rainflow counting of long histories is not implemented",
            "shear quantities are engineering shear amplitudes "
            "(delta gamma / 2), passed to the parameter functions per the "
            "lcf.multiaxial conventions",
        ],
    }
