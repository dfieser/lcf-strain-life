"""Standard LCF plots (matplotlib).

Figures are built with :class:`matplotlib.figure.Figure` directly (no pyplot
global state / GUI), so these work headless in the MCP server and in tests.
Every function returns a ``Figure``, use :func:`savefig` to write a PNG.

Plot set follows IMPLEMENTATION_REFERENCE §9: strain-life (with elastic/plastic/
total branches + transition), Coffin-Manson, Basquin, Ramberg-Osgood cyclic
stress-strain, hysteresis loops, peak/valley vs cycle, and energy vs cycle.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib.figure import Figure

from . import schema, stats
from .fits import StrainLifeFit
from .life import elastic_strain_life, plastic_strain_life
from .hightemp import creep_fatigue_envelope_allowable
from .metrics import PerCycleMetrics
from .stats import LogLifeFit

__all__ = [
    "savefig",
    "plot_strain_life",
    "plot_coffin_manson",
    "plot_basquin",
    "plot_cyclic_stress_strain",
    "plot_hysteresis",
    "plot_peak_valley",
    "plot_energy",
    "plot_design_curve",
    "plot_creep_fatigue_diagram",
    "plot_rainflow_histogram",
]


def savefig(fig: Figure, path: str | Path, *, dpi: int = 150) -> Path:
    """Save a figure to ``path`` (PNG) and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path


def _life_range(reversals=None, lo=1e1, hi=1e8):
    if reversals is not None and len(reversals):
        r = np.asarray(reversals, dtype=float)
        lo = min(lo, r.min() / 3.0)
        hi = max(hi, r.max() * 3.0)
    return np.logspace(np.log10(lo), np.log10(hi), 200)


def plot_strain_life(fit: StrainLifeFit, *, reversals=None, total_strain_amp=None) -> Figure:
    """Strain-life curve: elastic + plastic + total branches on log-log axes."""
    fig = Figure(figsize=(6, 4.5))
    ax = fig.subplots()
    tn = _life_range(reversals)
    el = elastic_strain_life(tn, fit.basquin.sigma_f, fit.basquin.b, fit.E)
    pl = plastic_strain_life(tn, fit.coffin_manson.eps_f, fit.coffin_manson.c)
    tot = el + pl
    ax.loglog(tn, el, "--", label="elastic (Basquin)", color="tab:blue")
    ax.loglog(tn, pl, "--", label="plastic (Coffin-Manson)", color="tab:red")
    ax.loglog(tn, tot, "-", label="total", color="black")
    nt = fit.transition_reversals
    if np.isfinite(nt):
        ax.axvline(nt, color="gray", ls=":", lw=1)
        ax.annotate(rf"$2N_t\approx${nt:,.0f}", xy=(nt, tot.min()), color="gray", fontsize=8)
    if reversals is not None and total_strain_amp is not None:
        ax.scatter(reversals, total_strain_amp, color="black", zorder=5, label="data")
    ax.set_xlabel("Reversals to failure, $2N_f$")
    ax.set_ylabel(r"Strain amplitude, $\Delta\varepsilon/2$")
    ax.set_title("Strain-life")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    return fig


def _loglog_fit_plot(x, y, coeff, exponent, xlabel, ylabel, title) -> Figure:
    fig = Figure(figsize=(6, 4.5))
    ax = fig.subplots()
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    ax.scatter(x, y, color="black", zorder=5, label="data")
    xs = _life_range(x, lo=x.min(), hi=x.max())
    ax.loglog(xs, coeff * xs**exponent, "-", color="tab:blue",
              label=f"fit: {coeff:.3g}·x^{exponent:.3g}")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    return fig


def plot_coffin_manson(plastic_strain_amp, reversals, fit) -> Figure:
    """Coffin-Manson plot: plastic strain amplitude vs reversals (log-log)."""
    return _loglog_fit_plot(
        reversals, plastic_strain_amp, fit.eps_f, fit.c,
        "Reversals to failure, $2N_f$", r"Plastic strain amplitude, $\Delta\varepsilon_p/2$",
        "Coffin-Manson",
    )


def plot_basquin(stress_amp, reversals, fit) -> Figure:
    """Basquin plot: stress amplitude vs reversals (log-log)."""
    return _loglog_fit_plot(
        reversals, stress_amp, fit.sigma_f, fit.b,
        "Reversals to failure, $2N_f$", r"Stress amplitude, $\Delta\sigma/2$ (MPa)",
        "Basquin",
    )


def plot_cyclic_stress_strain(fit_ro, E: float, *, sigma_max: float = 800.0,
                              monotonic=None) -> Figure:
    """Ramberg-Osgood cyclic stress-strain curve (optionally vs a monotonic curve)."""
    fig = Figure(figsize=(6, 4.5))
    ax = fig.subplots()
    sigma = np.linspace(0.0, sigma_max, 200)
    eps = sigma / E + (sigma / fit_ro.K) ** (1.0 / fit_ro.n)
    ax.plot(eps, sigma, "-", color="tab:blue", label="cyclic (Ramberg-Osgood)")
    if monotonic is not None:
        me, msig = monotonic
        ax.plot(me, msig, "--", color="tab:gray", label="monotonic")
    ax.set_xlabel(r"True strain, $\varepsilon$")
    ax.set_ylabel(r"True stress, $\sigma$ (MPa)")
    ax.set_title("Cyclic stress-strain")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    return fig


def plot_hysteresis(test, reduced, cycles=None) -> Figure:
    """Hysteresis loop(s): true stress vs true strain for selected cycle(s)."""
    fig = Figure(figsize=(5.5, 5))
    ax = fig.subplots()
    strain = test.data[schema.COL_STRAIN_TRUE].to_numpy()
    stress = test.data[schema.COL_STRESS_TRUE].to_numpy()
    tbl = reduced.table
    if cycles is None:
        cycles = [1, reduced.half_life_cycle]
    for cyc in cycles:
        row = tbl.loc[tbl["cycle"] == cyc]
        if row.empty:
            continue
        i0 = int(row["idx_loop_start"].iloc[0])
        i1 = int(row["idx_loop_end"].iloc[0])
        ax.plot(strain[i0 : i1 + 1], stress[i0 : i1 + 1], label=f"cycle {cyc}")
    ax.axhline(0, color="gray", lw=0.5)
    ax.axvline(0, color="gray", lw=0.5)
    ax.set_xlabel(r"True strain, $\varepsilon$")
    ax.set_ylabel(r"True stress, $\sigma$ (MPa)")
    ax.set_title("Hysteresis loops")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    return fig


def plot_peak_valley(metrics: PerCycleMetrics) -> Figure:
    """Peak (tension) and valley (compression) stress vs cycle (hardening/softening)."""
    fig = Figure(figsize=(6, 4.5))
    ax = fig.subplots()
    tbl = metrics.table
    ax.plot(tbl["cycle"], tbl["stress_max"], label="peak (tension)", color="tab:red")
    ax.plot(tbl["cycle"], tbl["stress_min"], label="valley (compression)", color="tab:blue")
    ax.axvline(metrics.half_life_cycle, color="gray", ls=":", lw=1, label="half-life")
    ax.set_xlabel("Cycle")
    ax.set_ylabel(r"Stress (MPa)")
    ax.set_title("Cyclic hardening / softening")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    return fig


def plot_energy(metrics: PerCycleMetrics) -> Figure:
    """Hysteresis energy density vs cycle."""
    fig = Figure(figsize=(6, 4.5))
    ax = fig.subplots()
    tbl = metrics.table
    ax.plot(tbl["cycle"], tbl["energy_density"], color="tab:green")
    ax.axvline(metrics.half_life_cycle, color="gray", ls=":", lw=1, label="half-life")
    ax.set_xlabel("Cycle")
    ax.set_ylabel(r"Energy density (MJ/m$^3$)")
    ax.set_title("Cyclic energy density")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    return fig


def plot_design_curve(fit: LogLifeFit, amplitudes=None, *, reliability: float = 0.90,
                      confidence: float = 0.90) -> Figure:
    """Strain-life design curve: median life, prediction band, and the R-C curve."""
    fig = Figure(figsize=(6, 4.5))
    ax = fig.subplots()
    if amplitudes is None:
        lo = 10.0 ** (fit.x_mean - 1.0)
        hi = 10.0 ** (fit.x_mean + 1.0)
        amplitudes = np.logspace(np.log10(lo), np.log10(hi), 100)
    amplitudes = np.asarray(amplitudes, dtype=np.float64)
    median = stats.predict_life(fit, amplitudes)
    plo, phi = stats.prediction_interval(fit, amplitudes, confidence)
    design = np.array([
        stats.design_life(fit, a, reliability=reliability, confidence=confidence)
        for a in amplitudes
    ])
    ax.loglog(median, amplitudes, "-", color="black", label="median (R50)")
    ax.loglog(plo, amplitudes, ":", color="gray", label="prediction band")
    ax.loglog(phi, amplitudes, ":", color="gray")
    ax.loglog(design, amplitudes, "--", color="tab:red",
              label=f"design R{int(reliability*100)}C{int(confidence*100)}")
    ax.set_xlabel("Life, N")
    ax.set_ylabel(r"Strain amplitude, $\Delta\varepsilon/2$")
    ax.set_title("Strain-life design curve")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    return fig


def plot_creep_fatigue_diagram(d_fatigue: float, d_creep: float, *,
                               knee: tuple[float, float] = (0.3, 0.3)) -> Figure:
    """Creep-fatigue interaction (D-diagram): the bilinear envelope and the point."""
    fig = Figure(figsize=(5, 5))
    ax = fig.subplots()
    df = np.linspace(0.0, 1.0, 200)
    allow = np.array([creep_fatigue_envelope_allowable(x, knee[0], knee[1]) for x in df])
    ax.plot(df, allow, "-", color="tab:blue", label="envelope")
    ax.scatter([d_fatigue], [d_creep], color="tab:red", zorder=5, label="point")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Fatigue damage $D_f$")
    ax.set_ylabel("Creep damage $D_c$")
    ax.set_title("Creep-fatigue interaction")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    return fig


def plot_rainflow_histogram(cycles) -> Figure:
    """Bar chart of counted cycle range against total count from a rainflow table."""
    fig = Figure(figsize=(6, 4.5))
    ax = fig.subplots()
    grouped = cycles.groupby("range")["count"].sum()
    ranges = grouped.index.to_numpy()
    ax.bar(ranges, grouped.to_numpy(),
           width=0.6 * (np.ptp(ranges) / max(len(grouped), 1) + 1e-9),
           color="tab:purple")
    ax.set_xlabel("Range")
    ax.set_ylabel("Cycle count")
    ax.set_title("Rainflow range histogram")
    ax.grid(True, alpha=0.3)
    return fig
