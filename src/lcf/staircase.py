"""Staircase (up-and-down) fatigue-limit analysis, Dixon-Mood method.

The staircase test estimates the mean and standard deviation of the fatigue
strength at a fixed life: each specimen is tested one step above or below the
previous level depending on whether the previous specimen survived. The
Dixon-Mood estimator analyzes the counts of the less frequent event on the
level grid (ADR-0015).

With the event counts ``n_i`` on level index ``i`` (0 at the lowest level
where the event occurred), ``A = sum(i*n_i)``, ``B = sum(i^2*n_i)``,
``N = sum(n_i)``:

* mean = X0 + d*(A/N - 1/2) when the analysis uses failures, ``+ 1/2`` for
  survivals, with d the step.
* std = 1.62*d*((N*B - A^2)/N^2 + 0.029) when the variability statistic
  ``(N*B - A^2)/N^2`` is at least 0.3. Below that bound the estimate is
  unreliable and the 0.53*d fallback is reported, flagged approximate.

References: Dixon and Mood, J. Amer. Statist. Assoc. 43 (1948) 109-126.
ISO 12107:2012. Validated against the S34MnV worked example of Ekaputra,
Dewa, Haryadi and Kim, Open Engineering 10 (2020) 394-400.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

__all__ = ["StaircaseResult", "dixon_mood"]

#: Below this value of (N*B - A^2)/N^2 the Dixon-Mood std is unreliable.
RATIO_BOUND = 0.3


@dataclass
class StaircaseResult:
    """Dixon-Mood staircase estimate of the fatigue-strength distribution."""

    mean: float                  # mean fatigue strength (input stress units)
    std: float                   # standard deviation estimate
    step: float                  # step size d
    event: str                   # "failure" or "survival", the analyzed event
    n_specimens: int
    n_events: int                # N, count of the analyzed (less frequent) event
    a: float                     # Dixon-Mood A
    b: float                     # Dixon-Mood B
    ratio: float                 # (N*B - A^2)/N^2 variability statistic
    ratio_ok: bool               # True when ratio >= RATIO_BOUND
    counts: dict = field(default_factory=dict)   # level -> [n_total, n_failed]
    notes: list[str] = field(default_factory=list)


def dixon_mood(stress_levels, failed, *, step: float | None = None) -> StaircaseResult:
    """Dixon-Mood analysis of an up-and-down test sequence.

    Parameters
    ----------
    stress_levels : sequence of float
        Stress (or strain) level of each specimen, in test order.
    failed : sequence of bool
        True where the specimen failed before the target life, False for a
        survival (runout).
    step : float, optional
        Step size d. If omitted it is inferred from the level sequence, and
        the consecutive levels must then differ by one constant step.
    """
    levels = np.asarray(stress_levels, dtype=np.float64)
    fail = np.asarray(failed, dtype=bool)
    if levels.shape != fail.shape:
        raise ValueError(
            f"stress_levels and failed must have equal length, got "
            f"{levels.size} and {fail.size}."
        )
    n_fail = int(fail.sum())
    n_surv = int((~fail).sum())
    if n_fail == 0 or n_surv == 0:
        raise ValueError(
            "the staircase needs both outcomes present. Got "
            f"{n_fail} failure(s) and {n_surv} survival(s). Check the failed "
            "flags, or widen the test around the fatigue limit."
        )

    diffs = np.abs(np.diff(levels))
    diffs = diffs[diffs > 0]
    if step is None:
        if diffs.size == 0:
            raise ValueError("cannot infer the step from a single level, pass step=")
        step = float(diffs[0])
    if diffs.size and not np.allclose(diffs, step, rtol=1e-6, atol=0.0):
        raise ValueError(
            f"consecutive levels do not move by one constant step. Seen level "
            f"moves {sorted(set(np.round(diffs, 9)))}, expected the step "
            f"{step:g} everywhere. An up-and-down test uses a fixed step, pass "
            "step= explicitly if the grid is right and the data are noisy."
        )

    notes: list[str] = []
    up_down_violations = 0
    for i in range(levels.size - 1):
        expected = levels[i] + (-step if fail[i] else step)
        if not np.isclose(levels[i + 1], expected, rtol=1e-6):
            up_down_violations += 1
    if up_down_violations:
        notes.append(
            f"{up_down_violations} transition(s) do not follow the up-down rule "
            "(down after a failure, up after a survival). The counts are "
            "analyzed as given, verify the sequence."
        )

    # Analyze the less frequent event (ties analyze failures).
    use_failures = n_fail <= n_surv
    event_mask = fail if use_failures else ~fail
    event_levels = levels[event_mask]
    x0 = float(event_levels.min())
    idx = np.round((event_levels - x0) / step).astype(int)
    n_events = int(event_mask.sum())
    a_stat = float(idx.sum())
    b_stat = float((idx ** 2).sum())
    ratio = (n_events * b_stat - a_stat ** 2) / n_events ** 2
    half = -0.5 if use_failures else 0.5
    mean = x0 + step * (a_stat / n_events + half)

    ratio_ok = ratio >= RATIO_BOUND
    if ratio_ok:
        std = 1.62 * step * (ratio + 0.029)
    else:
        std = 0.53 * step
        notes.append(
            f"variability statistic (N*B - A^2)/N^2 = {ratio:.3g} is below the "
            f"{RATIO_BOUND} validity bound, the standard deviation uses the "
            "0.53*step fallback and is approximate (Dixon-Mood, ISO 12107)."
        )

    counts: dict = {}
    for lv in np.unique(levels):
        at = levels == lv
        counts[float(lv)] = [int(at.sum()), int((fail & at).sum())]

    return StaircaseResult(
        mean=float(mean), std=float(std), step=float(step),
        event="failure" if use_failures else "survival",
        n_specimens=int(levels.size), n_events=n_events,
        a=a_stat, b=b_stat, ratio=float(ratio), ratio_ok=ratio_ok,
        counts=counts, notes=notes,
    )
