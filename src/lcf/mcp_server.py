"""MCP server exposing the LCF analysis tools (ADR-0008).

Thin wrappers over :class:`lcf.service.LcfService`. Tools are narrow and clearly
named. Large per-cycle data is persisted to the store and recalled on demand
rather than returned inline. Run with ``lcf-mcp`` or ``python -m lcf``.

The store directory comes from the ``LCF_STORE_DIR`` environment variable
(default ``.lcfstore``).
"""

from __future__ import annotations

import os

from . import labio
from .service import LcfService
from .store import dumps

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "The MCP SDK is not installed. Install the optional extra:\n"
        '    pip install "lcf-strain-life[mcp]"'
    ) from exc

mcp = FastMCP("lcf-strain-life")
_service = LcfService(os.environ.get("LCF_STORE_DIR", ".lcfstore"))


@mcp.tool()
def analyze_test_timeseries(
    name: str,
    time: list[float],
    strain: list[float],
    force: list[float],
    area: float,
    E: float | None = None,
    R: float = -1.0,
    already_true: bool = False,
    failure_pct: float = 30.0,
    material: str | None = None,
) -> dict:
    """Reduce one strain-controlled test from a (time, strain, force) series.

    Converts engineering -> true stress/strain (unless already_true), detects
    cycles, computes per-cycle metrics, and returns the stabilized (half-life)
    summary. The full per-cycle table is saved to the store under ``name`` and
    can be recalled with ``recall_result(name, "per_cycle")``.

    Use this for small inline series; for large data use ``analyze_test_csv``.
    """
    return _service.analyze_timeseries(
        name, time, strain, force, area, E=E, R=R, already_true=already_true,
        failure_pct=failure_pct, material=material,
    )


@mcp.tool()
def analyze_test_csv(
    name: str,
    csv_path: str,
    area: float,
    column_map: dict[str, str] | None = None,
    E: float | None = None,
    R: float = -1.0,
    already_true: bool = False,
    failure_pct: float = 30.0,
    material: str | None = None,
) -> dict:
    """Reduce one test from a CSV file (preferred for large series).

    ``column_map`` maps source column names to the canonical ``time``/``strain``/
    ``force`` (e.g. {"Axial Strain": "strain"}). Returns the half-life summary
    and persists the per-cycle table under ``name``.
    """
    return _service.analyze_csv(
        name, csv_path, area, column_map=column_map, E=E, R=R,
        already_true=already_true, failure_pct=failure_pct, material=material,
    )


@mcp.tool()
def analyze_test_series(
    directory: str,
    area: float | None = None,
    pattern: str = "*.csv",
    E: float | None = None,
    R: float = -1.0,
    already_true: bool = False,
    failure_pct: float = 30.0,
    material: str | None = None,
    strain_unit: str | None = None,
    force_unit: str | None = None,
    stress_unit: str | None = None,
    min_plastic_strain: float | None = None,
) -> dict:
    """Analyze a directory of lab exports as one strain-life test series.

    One call: reads every file matching ``pattern`` (auto-detecting delimiter,
    header row, column names, and unit suffixes such as percent strain or kN
    force), reduces each test, persists each summary under its file stem, and
    fits the strain-life constants across the series under ``material``.
    Returns per-test summaries, the fit, notes, and per-file errors. Files
    that cannot be read are reported in ``errors`` without stopping the rest.
    Run ``preview_lab_file`` first if unsure how a file will be interpreted.
    """
    return _service.analyze_series(
        directory, area, pattern=pattern, E=E, R=R, already_true=already_true,
        failure_pct=failure_pct, material=material, strain_unit=strain_unit,
        force_unit=force_unit, stress_unit=stress_unit,
        min_plastic_strain=min_plastic_strain,
    )


@mcp.tool()
def preview_lab_file(path: str, delimiter: str | None = None) -> dict:
    """Report how a lab export file would be read, without analyzing it.

    Returns the detected header row, delimiter, the resolved time/strain/
    force/stress columns with their units and conversion factors, the row
    count, and notes (for example a strain column that looks like percent).
    Use this before ``analyze_test_csv`` or ``analyze_test_series`` when the
    file layout is uncertain.
    """
    return labio.preview_lab_file(path, delimiter=delimiter)


@mcp.tool()
def fit_strain_life(
    total_strain_amp: list[float],
    stress_amp: list[float],
    reversals: list[float],
    E: float,
    plastic_strain_amp: list[float] | None = None,
    min_plastic_strain: float | None = None,
    refine_nonlinear: bool = False,
    material: str | None = None,
) -> dict:
    """Fit strain-life constants from per-test reduced data.

    Returns Basquin (σ'_f, b), Coffin-Manson (ε'_f, c), Ramberg-Osgood (K', n'),
    the transition life, and a Masing consistency check. ``min_plastic_strain``
    excludes near-runout points from the plastic branch. If ``material`` is
    given, the fit is saved for recall.
    """
    return _service.fit_strain_life(
        total_strain_amp, stress_amp, reversals, E,
        plastic_strain_amp=plastic_strain_amp, min_plastic_strain=min_plastic_strain,
        refine_nonlinear=refine_nonlinear, material=material,
    )


@mcp.tool()
def predict_life(
    total_strain_amp: float, sigma_f: float, b: float, eps_f: float, c: float, E: float
) -> dict:
    """Predict reversals and cycles to failure for a total strain amplitude.

    Inverts the combined Basquin + Coffin-Manson strain-life equation.
    """
    return _service.predict_life(total_strain_amp, sigma_f, b, eps_f, c, E)


@mcp.tool()
def mean_stress_equivalent_stress(
    stress_amp: float,
    mean_stress: float,
    model: str = "swt",
    sigma_f: float | None = None,
    gamma: float | None = None,
    sigma_u: float | None = None,
) -> dict:
    """Equivalent fully-reversed stress amplitude under a mean-stress model.

    ``model`` is one of none, morrow, swt, walker. Morrow needs ``sigma_f``;
    Walker needs ``gamma`` (or ``sigma_u`` to estimate it for steel).
    """
    return _service.mean_stress_equivalent_stress(
        stress_amp, mean_stress, model, sigma_f=sigma_f, gamma=gamma, sigma_u=sigma_u
    )


@mcp.tool()
def count_rainflow(name: str, strain_history: list[float],
                   close_residue: bool = False,
                   gate: float | None = None) -> dict:
    """Rainflow count a strain history (ASTM E1049), preserving cycle indices.

    Saves the full per-cycle table under ``name`` (recall with
    ``recall_result(name, "rainflow")``) and returns a compact summary. Set
    ``close_residue`` to treat the history as repeating. A non-None ``gate``
    first drops swings smaller than the gate with the racetrack filter, which
    condenses long noisy histories.
    """
    return _service.count_rainflow(name, strain_history,
                                   close_residue=close_residue, gate=gate)


@mcp.tool()
def count_level_crossings(name: str, series: list[float],
                          levels: list[float] | None = None,
                          ref: float = 0.0) -> dict:
    """Level-crossing count of a history (ASTM E1049 section 5.2).

    Counts positive-slope crossings at and above ``ref`` and negative-slope
    crossings below it. ``levels`` defaults to 32 evenly spaced levels over
    the signal. Saves the level table under ``name`` (quantity
    ``level_crossings``) and returns a summary.
    """
    return _service.count_level_crossings(name, series, levels=levels, ref=ref)


@mcp.tool()
def count_peaks(name: str, series: list[float], ref: float = 0.0) -> dict:
    """Peak and valley count of a history (ASTM E1049 section 5.3).

    Counts peaks at and above ``ref`` and valleys below it. Saves the table
    under ``name`` (quantity ``peaks``) and returns a summary.
    """
    return _service.count_peaks(name, series, ref=ref)


@mcp.tool()
def compute_sn_life(stress_amp: list[float], k: float, sd: float, nd: float,
                    variant: str = "original") -> dict:
    """Allowable cycles from a one-slope Woehler (S-N) line with a knee.

    Above the knee (sd, nd) the line is N = nd*(s/sd)**-k. Below the knee the
    treatment follows ``variant``: original (infinite life, serialized as
    null), elementary (slope k continues), or haibach (fictitious slope 2k-1,
    Haibach 1970). Feed the lives into compute_damage for spectrum damage of
    stress-based collectives.
    """
    return _service.compute_sn_life(stress_amp, k=k, sd=sd, nd=nd,
                                    variant=variant)


@mcp.tool()
def compute_spectrum_life(
    strain_history: list[float],
    stress_history: list[float],
    sigma_f: float,
    b: float,
    eps_f: float,
    c: float,
    E: float,
    mean_stress_method: str = "swt",
    rule: str = "miner",
    name: str | None = None,
) -> dict:
    """Variable-amplitude life from aligned strain and stress histories.

    Rainflow counts the strain, applies a per-cycle mean-stress correction
    (none, morrow, swt), inverts the strain-life curve for each cycle, and sums
    damage (miner or dldr). Returns damage per block and blocks and cycles to
    failure. Persists the per-cycle table if ``name`` is given.
    """
    return _service.compute_spectrum_life(
        strain_history, stress_history, sigma_f=sigma_f, b=b, eps_f=eps_f, c=c, E=E,
        mean_stress_method=mean_stress_method, rule=rule, name=name,
    )


@mcp.tool()
def compute_damage(counts: list[float], lives: list[float], rule: str = "miner",
                   d_crit: float = 1.0, stresses: list[float] | None = None,
                   d_exponent: float | None = None) -> dict:
    """Cumulative damage for a counted block (miner, dldr, or corten_dolan).

    ``counts`` and ``lives`` are aligned per-cycle cycle-counts and lives to
    failure. Corten-Dolan additionally needs the per-level ``stresses`` and the
    material exponent ``d_exponent``. Returns damage, blocks to failure, and
    cycles to failure.
    """
    return _service.compute_damage(counts, lives, rule=rule, d_crit=d_crit,
                                   stresses=stresses, d_exponent=d_exponent)


@mcp.tool()
def compute_notch_local(
    nominal_amp: float,
    Kt: float,
    E: float,
    K: float,
    n: float,
    sigma_f: float,
    b: float,
    eps_f: float,
    c: float,
    method: str = "neuber",
    name: str | None = None,
) -> dict:
    """Local notch stress, strain, and life from a nominal stress amplitude.

    Uses Neuber (default) or Glinka on the cyclic Ramberg-Osgood curve, then the
    strain-life solver. ``K`` and ``n`` are the cyclic strength coefficient and
    exponent.
    """
    return _service.compute_notch_local(
        nominal_amp, Kt, E=E, K=K, n=n, sigma_f=sigma_f, b=b, eps_f=eps_f, c=c,
        method=method, name=name,
    )


@mcp.tool()
def fit_design_curve(
    amplitude: list[float],
    life_values: list[float],
    reliability: float = 0.90,
    confidence: float = 0.90,
    censored: list[bool] | None = None,
    design_amplitude: float | None = None,
    material: str | None = None,
) -> dict:
    """Fit a strain-life regression and report design (reliability-confidence) life.

    Life is the dependent variable (E739 style). Right-censored runouts are
    handled by maximum likelihood when ``censored`` flags are given. If
    ``design_amplitude`` is set, returns the median and the R-C design life
    there using the Owen tolerance factor. When the data contain replicate
    amplitude levels, the result includes the E739 lack-of-fit F test under
    ``lack_of_fit`` (a significant F means the straight line does not
    represent the data, whatever r squared says).

    The result carries machine-readable caution flags under ``warnings``,
    each ``{"code", "message"}``. Surface every warning to the user. In
    particular ``code == "extrapolation"`` means the requested
    ``design_amplitude`` lies outside the fitted interval
    (``amplitude_range``) and the predicted life is unreliable, per E739's
    own caveat against extrapolation.
    """
    return _service.fit_design_curve(
        amplitude, life_values, reliability=reliability, confidence=confidence,
        censored=censored, design_amplitude=design_amplitude, material=material,
    )


@mcp.tool()
def simulate_variable_amplitude(
    strain_history: list[float] | None = None,
    E: float = 0.0,
    K_prime: float = 0.0,
    n_prime: float = 0.0,
    sigma_f: float = 0.0,
    b: float = 0.0,
    eps_f: float = 0.0,
    c: float = 0.0,
    mean_stress_model: str = "swt",
    nominal_stress_history: list[float] | None = None,
    Kt: float | None = None,
    name: str | None = None,
) -> dict:
    """Life for a repeating variable-amplitude history block.

    Give either ``strain_history`` (local strain, smooth specimen) or
    ``nominal_stress_history`` with ``Kt`` (notched member: the local
    response comes from Neuber's rule at every branch). Simulates the
    cyclic response with material memory (Masing branches,
    rainflow-consistent loop closure), computes each closed loop's life
    with the chosen mean-stress model (swt from the loop's peak stress,
    morrow from its mean, none for the uncorrected curve), and Miner-sums
    the damage. Returns the loop table sorted by damage, damage per block,
    and blocks to failure. Assumes stabilized cyclic properties, mean
    stress relaxation and ratcheting are not modeled. Validation evidence
    travels in the notes: smooth-specimen predictions within 2x on two of
    three published SAE histories, the notched keyhole case within 4
    percent of the benchmark reference calculation at constant amplitude
    and within 2x of experiment under the suspension history.
    """
    return _service.simulate_variable_amplitude(
        strain_history, E=E, K_prime=K_prime, n_prime=n_prime,
        sigma_f=sigma_f, b=b, eps_f=eps_f, c=c,
        mean_stress_model=mean_stress_model,
        nominal_stress_history=nominal_stress_history, Kt=Kt, name=name,
    )


@mcp.tool()
def search_critical_plane_tensor(
    parameter: str,
    eps_xx: list[float],
    eps_yy: list[float],
    eps_zz: list[float],
    gamma_xy: list[float],
    gamma_yz: list[float],
    gamma_zx: list[float],
    sig_xx: list[float] | None = None,
    sig_yy: list[float] | None = None,
    sig_zz: list[float] | None = None,
    tau_xy: list[float] | None = None,
    tau_yz: list[float] | None = None,
    tau_zx: list[float] | None = None,
    sigma_y: float | None = None,
    k: float = 0.3,
    S: float = 1.0,
    grid_deg: float = 10.0,
    name: str | None = None,
) -> dict:
    """Find the critical plane from strain (and stress) tensor histories.

    Give component histories sampled over one cycle: normal strains, and
    ENGINEERING shear strains (gamma). The tool scans plane normals over a
    hemisphere grid, resolves each plane's shear amplitude (longest chord,
    valid for non-proportional paths), normal strain amplitude, and maximum
    normal stress, and returns the plane maximizing the chosen parameter:
    fatemi_socie (needs the stress history and sigma_y), brown_miller
    (strains only), or swt (needs the stress history). Amplitudes come from
    the given cycle's path, per-plane rainflow of long histories is not
    implemented. Saved under ``name`` for recall when given.
    """
    return _service.search_critical_plane_tensor(
        parameter, eps_xx=eps_xx, eps_yy=eps_yy, eps_zz=eps_zz,
        gamma_xy=gamma_xy, gamma_yz=gamma_yz, gamma_zx=gamma_zx,
        sig_xx=sig_xx, sig_yy=sig_yy, sig_zz=sig_zz,
        tau_xy=tau_xy, tau_yz=tau_yz, tau_zx=tau_zx,
        sigma_y=sigma_y, k=k, S=S, grid_deg=grid_deg, name=name,
    )


@mcp.tool()
def fit_random_fatigue_limit(
    stress: list[float],
    life: list[float],
    censored: list[bool] | None = None,
    name: str | None = None,
) -> dict:
    """Fit the random fatigue limit model to S-N data with runouts.

    Pascual-Meeker normal-normal form: each specimen's fatigue limit varies
    unit to unit, so the S-N curve flattens naturally near the limit and
    runouts carry real information. Give stress amplitudes, lives (be
    consistent, cycles or reversals), and runout flags. Returns the five ML
    estimates (beta0, beta1, sigma, mu_gamma, sigma_gamma of the log
    fatigue limit), the log likelihood, and a convergence flag. Needs at
    least 10 observations and 6 failures. Validation status is in the
    notes: implementation-validated (likelihood cross-check, simulated
    parameter recovery), not yet benchmarked against the published
    laminate-panel fit, its raw data are not openly published.
    """
    return _service.fit_random_fatigue_limit(
        stress, life, censored, name=name
    )


@mcp.tool()
def fit_mean_stress_relaxation(
    cycles: list[float], mean_stresses: list[float], name: str | None = None
) -> dict:
    """Fit the cycle-dependent mean stress relaxation power law.

    Strain-controlled asymmetric cycling relaxes the mean stress toward zero
    as sigma_m(N) = sigma_m1 * N**b_r. Give measured (cycle, mean stress)
    pairs, get sigma_m1 and the relaxation exponent b_r (<= 0). Reconstructed
    from collaborator notes matching the standard published form, the notes
    say so.
    """
    return _service.fit_mean_stress_relaxation(cycles, mean_stresses, name=name)


@mcp.tool()
def fit_ratcheting_law(
    cycles: list[float], ratchet_strains: list[float], name: str | None = None
) -> dict:
    """Fit the ratcheting strain accumulation power law eps_r = C * N**p.

    Stress-controlled asymmetric cycling accumulates strain in the mean
    direction. Give measured (cycle, accumulated strain) pairs, get C and the
    ratcheting exponent p. Reconstructed from collaborator notes matching the
    standard published form.
    """
    return _service.fit_ratcheting_law(cycles, ratchet_strains, name=name)


@mcp.tool()
def ratcheting_penalized_life(
    plastic_strain_amp: float, eps_r: float, eps_f: float, c: float
) -> dict:
    """Coffin-Manson life with the ratcheting ductility-exhaustion penalty.

    Solves plastic_strain_amp = (eps_f - eps_r) * (2Nf)**c, the plastic
    strain-life line with the fatigue ductility reduced by the accumulated
    ratcheting strain eps_r. Returns reversals and cycles. Reconstructed from
    collaborator notes, see the notes for the validation status.
    """
    return _service.ratcheting_penalized_life(
        plastic_strain_amp, eps_r, eps_f=eps_f, c=c
    )


@mcp.tool()
def compute_roughness_factor(
    Rz: float, Rm: float, material_group: str = "steel"
) -> dict:
    """FKM surface roughness factor K_R.

    ``Rz`` is the surface roughness in micrometres (DIN 4768), ``Rm`` the
    tensile strength in MPa, ``material_group`` one of steel, cast_steel,
    nodular_cast_iron, malleable_cast_iron, grey_cast_iron,
    wrought_aluminium, cast_aluminium. Multiply a stress-based fatigue
    strength by K_R. Capped at 1.0 for polished surfaces. Strain-life
    constants are not corrected directly by this factor.
    """
    return _service.compute_roughness_factor(
        Rz, Rm, material_group=material_group
    )


@mcp.tool()
def compute_size_factor(d_eff: float, a_dm: float, d_eff_N: float) -> dict:
    """FKM technological size factor K_d,m for tensile strength.

    ``d_eff`` is the effective diameter in mm. ``a_dm`` and ``d_eff_N`` are
    the material constants from the caller's licensed FKM guideline (tables
    3.2.1 and 3.2.2), which are copyrighted and not bundled here. Returns
    K_d,m, 1.0 at or below the reference diameter and lower above it.
    Multiply a stress-based fatigue or tensile strength by it. The
    logarithmic formula is a verified published relation.
    """
    return _service.compute_size_factor(d_eff, a_dm=a_dm, d_eff_N=d_eff_N)


@mcp.tool()
def generate_report(key: str) -> dict:
    """One-call markdown fatigue report of everything stored under a key.

    Assembles summaries, fits, design curves, staircase, basis values, and
    variable-amplitude results with their provenance hashes and the source
    citations for every method that appears. Returns the markdown, stores
    it for recall, and writes ``<store>/reports/<key>.md``.
    """
    return _service.generate_report(key)


@mcp.tool()
def export_material(
    name: str,
    E: float,
    sigma_f: float,
    b: float,
    eps_f: float,
    c: float,
    K_prime: float | None = None,
    n_prime: float | None = None,
    source: str | None = None,
    fmt: str = "lcf",
    nd_cycles: float = 1.0e6,
) -> dict:
    """Export strain-life constants as an interchange document.

    ``fmt='lcf'`` gives the versioned lcf-strain-life/material@1 JSON
    document (MPa, strain fraction, reversals, with provenance).
    ``fmt='pylife'`` expresses the Basquin line in pyLife WoehlerCurve
    conventions (k_1, ND, SD, TN, TS) and ``fmt='py_fatigue'`` in py-fatigue
    SNCurve conventions (slope, intercept). Both adapters are round-trip
    verified against the installed libraries in the development test suite
    (pyLife 2.3.1, py-fatigue 2.1.1), the knee ND is a representation choice.
    """
    return _service.export_material(
        name, E, sigma_f, b, eps_f, c, K_prime=K_prime, n_prime=n_prime,
        source=source, fmt=fmt, nd_cycles=nd_cycles,
    )


@mcp.tool()
def import_material(doc: dict) -> dict:
    """Validate an lcf-strain-life material document and return the constants.

    Refuses unknown schemas, versions, and unit systems with the reason,
    rather than guessing.
    """
    return _service.import_material(doc)


@mcp.tool()
def analyze_staircase(
    stress_levels: list[float],
    failed: list[bool],
    step: float | None = None,
    name: str | None = None,
) -> dict:
    """Estimate the fatigue limit from a staircase (up-and-down) test.

    Dixon-Mood method per ISO 12107. Give each specimen's stress level in
    test order and whether it failed before the target life. Returns the mean
    and standard deviation of the fatigue strength, the counts per level, and
    plain-language notes. The step is inferred from the sequence unless
    given. When the Dixon-Mood variability statistic is below 0.3 the
    standard deviation is the approximate 0.53*step fallback and the result
    says so. Saved under ``name`` for recall when given.
    """
    return _service.analyze_staircase(
        stress_levels, failed, step=step, name=name,
    )


@mcp.tool()
def compute_basis_value(
    samples: list[float] | None = None,
    mean: float | None = None,
    std: float | None = None,
    n: int | None = None,
    basis: str = "B",
    name: str | None = None,
) -> dict:
    """A- or B-basis value: the one-sided lower tolerance bound mean - k*std.

    B-basis is the 95 percent confidence bound on the 10th percentile,
    A-basis on the 1st percentile, following MMPDS practice, with the exact
    Owen k factor. Pass raw ``samples``, or ``mean``, ``std`` (sample, ddof
    1), and ``n`` directly. Assumes normality in the analyzed units. Saved
    under ``name`` for recall when given.
    """
    return _service.compute_basis_value(
        samples, mean=mean, std=std, n=n, basis=basis, name=name,
    )


@mcp.tool()
def flag_outliers(
    amplitude: list[float],
    life_values: list[float],
    censored: list[bool] | None = None,
    alpha: float = 0.05,
    max_outliers: int | None = None,
) -> dict:
    """Flag statistical outliers in strain-life or stress-life data.

    Runouts marked in ``censored`` are suspended tests, not outliers, and are
    excluded from testing. Residuals of the log-log life regression are
    screened with the generalized ESD test (Rosner 1983), and Cook's distance
    and leverage flag influential points. Use this before fitting a design
    curve to check data quality. All indices refer to the input order.
    """
    return _service.flag_outliers(
        amplitude, life_values, censored=censored, alpha=alpha,
        max_outliers=max_outliers,
    )


@mcp.tool()
def compute_creep_fatigue(
    cycle_counts: list[float],
    fatigue_lives: list[float],
    hold_times: list[float],
    rupture_times: list[float],
    envelope: float = 1.0,
    name: str | None = None,
) -> dict:
    """Time-fraction creep-fatigue damage with a D-diagram envelope check.

    Returns the fatigue damage, creep damage, total, and whether the point lies
    inside the bilinear creep-fatigue interaction envelope.
    """
    return _service.compute_creep_fatigue(
        cycle_counts, fatigue_lives, hold_times, rupture_times, envelope=envelope, name=name,
    )


@mcp.tool()
def estimate_strain_life_constants(
    method: str,
    material_class: str = "steel",
    Su: float | None = None,
    E: float | None = None,
    HB: float | None = None,
    RA: float | None = None,
    material: str | None = None,
) -> dict:
    """Estimate strain-life constants from monotonic properties, no test data.

    Use this when no strain-controlled fatigue data exists. ``method`` is one
    of medians (recommended default, Meggiolaro-Castro 2004),
    uniform_material_law (Baeumel-Seeger 1990), universal_slopes (Manson 1965),
    modified_universal_slopes (Muralidharan-Manson 1988, steels only), or
    hardness (Roessle-Fatemi 2000, steels only, from Brinell hardness).

    Required inputs by method: medians needs Su. uniform_material_law needs Su
    and E (material_class steel or aluminum_titanium). universal_slopes and
    modified_universal_slopes need Su, E, RA (reduction in area, fraction).
    hardness needs HB and E. Units are MPa. Every result carries the citation
    of the source and validity warnings. These are screening estimates, not a
    substitute for test data. Saved under ``material`` if given.
    """
    return _service.estimate_constants(
        method, material_class=material_class, Su=Su, E=E, HB=HB, RA=RA,
        material=material,
    )


@mcp.tool()
def compute_multiaxial_parameter(
    parameter: str,
    shear_strain_amp: float | None = None,
    normal_strain_amp: float | None = None,
    sigma_n_max: float | None = None,
    sigma_y: float | None = None,
    k: float = 0.3,
    S: float = 1.0,
    eps_x: float | None = None,
    eps_y: float | None = None,
    eps_z: float | None = None,
    gamma_xy: float = 0.0,
    gamma_yz: float = 0.0,
    gamma_zx: float = 0.0,
) -> dict:
    """Evaluate a critical-plane damage parameter from known plane quantities.

    ``parameter`` is one of fatemi_socie, brown_miller, swt, von_mises.
    fatemi_socie needs shear_strain_amp, sigma_n_max, sigma_y (and optional k).
    brown_miller needs shear_strain_amp, normal_strain_amp (and optional S).
    swt needs sigma_n_max, normal_strain_amp. von_mises needs the strain
    components and is valid for proportional-loading screening only. The plane
    quantities must be known already, there is no tensor plane-search engine.
    """
    return _service.compute_multiaxial_parameter(
        parameter, shear_strain_amp=shear_strain_amp,
        normal_strain_amp=normal_strain_amp, sigma_n_max=sigma_n_max,
        sigma_y=sigma_y, k=k, S=S, eps_x=eps_x, eps_y=eps_y, eps_z=eps_z,
        gamma_xy=gamma_xy, gamma_yz=gamma_yz, gamma_zx=gamma_zx,
    )


@mcp.tool()
def search_critical_plane(
    parameter: str,
    angles: list[float],
    shear_strain_amp: list[float] | None = None,
    normal_strain_amp: list[float] | None = None,
    sigma_n_max: list[float] | None = None,
    sigma_y: float | None = None,
    k: float = 0.3,
    S: float = 1.0,
) -> dict:
    """Find the candidate plane angle that maximizes a damage parameter.

    Supply per-angle plane quantities as aligned arrays, one entry per angle in
    ``angles`` (degrees). ``parameter`` is fatemi_socie, brown_miller, or swt.
    Returns the critical angle, the maximum parameter, and per-angle values.
    """
    return _service.search_critical_plane(
        parameter, angles, shear_strain_amp,
        normal_strain_amp=normal_strain_amp, sigma_n_max=sigma_n_max,
        sigma_y=sigma_y, k=k, S=S,
    )


@mcp.tool()
def compute_frequency_modified_life(
    plastic_strain_amp: float,
    eps_f_coeff: float,
    c: float,
    frequency: float,
    k: float,
    freq_ref: float = 1.0,
) -> dict:
    """Reversals to failure from the frequency-modified Coffin-Manson law.

    Uses the Solomon and Engelmaier coefficient form, where frequency scales
    the ductility coefficient: C_f = C_o*(f/f_ref)**(k-1). Useful for
    elevated-temperature fatigue where cycle frequency matters.
    """
    return _service.compute_frequency_modified_life(
        plastic_strain_amp, eps_f_coeff, c, frequency=frequency, k=k,
        freq_ref=freq_ref,
    )


@mcp.tool()
def render_plot(key: str, kind: str) -> dict:
    """Render a stored result as a PNG plot and return the file path.

    ``kind`` is one of rainflow_histogram, peak_valley, energy, strain_life.
    The data comes from the store, so run the corresponding compute tool first:
    count_rainflow for rainflow_histogram, analyze_test_timeseries or
    analyze_test_csv for peak_valley and energy, fit_strain_life (with a
    material name) for strain_life.
    """
    return _service.render_plot(key, kind)


@mcp.tool()
def get_citations(topic: str | None = None) -> dict:
    """The published source behind every method in this toolkit.

    Returns the citation registry, optionally filtered by a topic substring
    (for example "rainflow", "morrow", or "outlier"). Use this to cite the
    methods behind any result, every computational method here traces to a
    published paper or standard.
    """
    from .citations import get_citations as _get

    return _get(topic)


@mcp.tool()
def recall_result(key: str, quantity: str) -> dict:
    """Recall a previously computed result (e.g. a test summary or a fit).

    ``quantity`` is one of ``summary``, ``per_cycle``, ``strain_life_fit``.
    Returns the stored value plus any artifact paths, or an error message.
    """
    rec = _service.recall(key, quantity)
    if rec is None:
        return {"error": f"no result for key={key!r}, quantity={quantity!r}"}
    return rec


@mcp.tool()
def list_results(key: str | None = None) -> list[dict]:
    """List stored results (optionally filtered to one test/material key)."""
    return _service.list_results(key)


@mcp.resource("lcf://citations")
def citations_resource() -> str:
    """The full citation registry as JSON."""
    from .citations import CITATIONS

    return dumps(CITATIONS, indent=2)


@mcp.resource("lcf://results/{key}/{quantity}")
def result_resource(key: str, quantity: str) -> str:
    """Expose a stored result as a readable resource (JSON)."""
    rec = _service.recall(key, quantity)
    return dumps(rec if rec is not None else {"error": "not found"}, indent=2)


def main() -> None:
    """Console entry point: run the stdio MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
