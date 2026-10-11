"""The profile interval behind :meth:`rietx.refine.Refinement.profile_interval`.

A refined parameter's esd is the curvature of χ² at the converged point, and
read as an interval it is symmetric by construction.  On a bound it is no
interval at all: the estimate has no symmetric sampling distribution on the
boundary of the parameter space, and the likelihood-ratio statistic there is
the mixture ½χ²₀ + ½χ²₁ (Self & Liang, 1987, J. Am. Statist. Assoc. 82,
605).  WP-1929 kept such a row's value and marginal esd and flagged
it (``RefinedParameter.at_bound``, ``FLOOR_HIT``); this is the number a caller
who needs one asks for.

**The profile interval** (Venzon & Moolgavkar, 1988, Appl. Statist. 37, 87):
pin the parameter at v, refit everything else, and read the data's χ² there.
The interval is every v whose Δχ² from the fit stays under a threshold.  Each
pinned refit is the constrained hypothesis of Hamilton's test with one
constraint (Hamilton, 1965, Acta Cryst. 18, 502), so the threshold is a χ²₁
quantile c, scaled by the fit's χ²_red and the square of its Bérar-Lelann
factor f (Bérar & Lelann, 1991, J. Appl. Cryst. 24, 1) exactly as
``fraction_profile`` scales it and as every reported esd is.  On a quadratic
profile the two-sided interval is then the fitted value ± √c esd.

- **Interior row**: two-sided, c = χ²₁ quantile at ``level`` (3.84 at 95 %),
  one end on each side.
- **Row on its bound**: one-sided.  The bound is one end.  The other is where
  Δχ² reaches c = χ²₁ quantile at 2·``level`` − 1 (2.71 at 95 %), because
  under Self & Liang's mixture P(T > c) = ½·P(χ²₁ > c).

**The ends are found by bracketing and Brent's method on the profile itself**
(Brent, 1973, *Algorithms for Minimization without Derivatives*, ch. 4;
``scipy.optimize.brentq``) rather than by Venzon & Moolgavkar's Newton
iteration on the augmented system, which needs second derivatives of the
whole model.  Each side steps outward from the fitted value by 1, 2, 4, …
esd until Δχ² passes the threshold or the step reaches the parameter's own
limit, which is reported as that side's end.  Each refit starts where the
previous one on its side finished.  ``max_refits`` caps each side, and a side
that runs out, or whose refit raises, has no end and says why.

**A pinned value is refitted until its χ² settles.**  A stage sizes its peak
windows at compile, from where it starts, and keeps them (root CLAUDE.md,
frozen-per-stage discreteness).  Pin BT-1's Lorentzian ``x`` one esd below
the fit and ``y`` leaves its floor of 0 inside the refit, on windows sized for
``y`` = 0: Δχ² 28.3 after one refit, 16.9 after a second at the same value,
against a threshold of 30.3 (WP-1929, macOS arm64).  So a probe refits again
while χ² falls, and keeps the lowest it reached.  The windows also make the
profile a function with steps in it: on that fit some pinned values
alternate between two compiles 0.2-3 χ² apart, about a tenth of the
threshold, and that sets how precise an end is there whatever ``xtol`` says.

**Read-only by construction**, as ``fraction_profile`` is: every refit runs on
a branch (or on a copy of the models where the caller disabled history), with
``telemetry=False``, and the history's HEAD is put back.
"""

from __future__ import annotations

import math

from ..schemas.interval import (
    PARAMETER_INTERVAL_CHI2_TOL,
    PARAMETER_INTERVAL_LEVEL,
    PARAMETER_INTERVAL_MAX_REFITS,
    PARAMETER_INTERVAL_SETTLE_RUNS,
    PARAMETER_INTERVAL_XTOL,
    IntervalStop,
    ParameterInterval,
    ParameterIntervalPoint,
)
from .fraction_profile import data_chi2, head_restored
from .staged import Stage


def interval_quantile(level: float, one_sided: bool) -> float:
    """The χ²₁ quantile c a profile interval's Δχ² threshold is scaled from.

    Two-sided, c is χ²₁'s ``level`` point, the Δχ² a pinned refit is tested
    at (Hamilton, 1965, Acta Cryst. 18, 502).  One-sided, for an estimate on
    the boundary of the parameter space, the statistic is ½χ²₀ + ½χ²₁ (Self &
    Liang, 1987, J. Am. Statist. Assoc. 82, 605), so P(T > c) = 1 − level
    gives c at χ²₁'s 2·level − 1 point: 2.706 at 95 %, against 3.841.
    """
    from scipy.stats import chi2

    if not 0.0 < level < 1.0:
        raise ValueError(f"a confidence level lies strictly between 0 and 1, "
                         f"not {level!r}")
    q = 2.0 * level - 1.0 if one_sided else level
    if q <= 0.0:
        raise ValueError(
            f"a one-sided interval at level {level:g} is the bound alone: the "
            "statistic puts half its mass on the bound, so a level of 0.5 or "
            "below needs no refit at all")
    return float(chi2.ppf(q, 1))


class _SideStopped(Exception):
    """One side of the interval stopped without an end, and why."""

    def __init__(self, stop: IntervalStop):
        super().__init__(stop)
        self.stop = stop


def _refined_row(refinement, result, path: str):
    """The last fit's row for ``path``, refusing a path that was not free in it.

    The reason is the one :attr:`ParameterRow.held_because` gives, so a tied
    row names its sources the way ``set_values`` does.
    """
    row = next((p for p in result.parameters if p.path == path), None)
    if row is not None and row.vary:
        return row
    current = next((r for r in refinement.parameters() if r.path == path), None)
    if current is None:
        raise ValueError(f"unknown parameter path {path!r}")
    why = current.held_because
    if why:
        raise ValueError(f"{path!r} cannot be pinned and profiled on its own "
                         f"({why})")
    raise ValueError(f"{path!r} was not free in the last fit, so the fit is no "
                     "minimum along it to profile from; free it and fit again")


def _walk(refinement, data, path: str, start: float, sign: int, limit: float,
          step: float, cut: float, chi2_fit: float, budget: int,
          points: list[ParameterIntervalPoint]) -> tuple[float | None, IntervalStop]:
    """One side: bracket the root by doubling steps, then solve it with Brent."""
    from scipy.optimize import brentq

    if start == limit:
        return limit, "bound"            # already on this side's limit
    trial = refinement._trial()
    trial.set_vary([path], False)
    measured = {start: 0.0}             # the fit itself, by definition
    settled = PARAMETER_INTERVAL_CHI2_TOL * cut
    spent = 0

    def delta(v: float) -> float:
        nonlocal spent
        if v in measured:
            return measured[v]
        if spent >= budget:
            raise _SideStopped("refits")
        trial.set_values({path: v})
        best, last, runs, error = None, None, 0, None
        # refit until χ² stops falling: a refit ends on the peak windows its
        # start compiled (PARAMETER_INTERVAL_SETTLE_RUNS has the measurement)
        while runs < PARAMETER_INTERVAL_SETTLE_RUNS and spent < budget:
            spent += 1
            runs += 1
            try:
                r = trial.run_stage(data, Stage(f"interval:{path}", []),
                                    telemetry=False)
            except Exception as exc:  # an unmeasurable point ends the side
                error = str(exc)
                break
            chi2 = data_chi2(r.statistics)
            if best is None or chi2 < best[0]:
                best = (chi2, r)
            if last is not None and last - chi2 <= settled:
                break
            last = chi2
        if best is None:
            points.append(ParameterIntervalPoint(value=v, runs=runs, error=error))
            raise _SideStopped("error")
        chi2, r = best
        points.append(ParameterIntervalPoint(
            value=v, runs=runs, chi2=chi2, delta_chi2=chi2 - chi2_fit,
            status=r.stages[-1].status if r.stages else r.status,
            error=error, node_id=r.node_id))
        if error is not None:
            raise _SideStopped("error")
        measured[v] = chi2 - chi2_fit
        return measured[v]

    try:
        inner, k = start, 0
        while True:
            v = start + sign * 2.0 ** k * step
            reached = v <= limit if sign < 0 else v >= limit
            if reached:
                v = limit
            if delta(v) >= cut:
                break
            if reached:
                return limit, "bound"
            inner, k = v, k + 1
        a, b = sorted((inner, v))
        root = float(brentq(lambda x: delta(x) - cut, a, b,
                            xtol=PARAMETER_INTERVAL_XTOL * step))
        # brentq returns a point it evaluated, so this is a lookup: the end is
        # always one of ``points``, and its Δχ² can be read there
        delta(root)
        return root, "threshold"
    except _SideStopped as stopped:
        return None, stopped.stop


def profile_interval(refinement, data, path: str, *,
                     level: float = PARAMETER_INTERVAL_LEVEL,
                     max_refits: int = PARAMETER_INTERVAL_MAX_REFITS
                     ) -> ParameterInterval:
    """Pin ``path`` outward from the fit on each open side, refit, solve for the ends.

    See :meth:`rietx.refine.Refinement.profile_interval`, which is this.
    """
    result = refinement.result_
    if result is None:
        raise RuntimeError("run a fit before profiling a parameter")
    if isinstance(max_refits, bool) or not isinstance(max_refits, int) or max_refits < 1:
        raise ValueError(f"max_refits is a whole number of refits per side, at "
                         f"least 1, not {max_refits!r}")
    row = _refined_row(refinement, result, path)
    if row.stderr is None or not (math.isfinite(row.stderr) and row.stderr > 0.0):
        raise ValueError(
            f"{path!r} has no esd from the last fit, so there is no scale to step "
            "the profile in: the residual does not move along it, and a "
            "direction the data does not see has no interval")
    entry = next(e for e in refinement._working_table().entries if e.path == path)
    lo, hi = float(entry.lo), float(entry.hi)

    one_sided = row.at_bound is True
    quantile = interval_quantile(level, one_sided)
    stats = result.statistics
    inflation = stats.esd_inflation if stats.esd_inflation is not None else 1.0
    cut = quantile * stats.chi2 * inflation ** 2
    chi2_fit = data_chi2(stats)
    # the bound a flagged row sits on: under TRF its value only comes close
    on_upper = hi - row.value < row.value - lo

    points: list[ParameterIntervalPoint] = []
    ends: dict[int, tuple[float | None, IntervalStop]] = {}
    with head_restored(refinement):
        for sign, limit in ((-1, lo), (1, hi)):
            if one_sided and (sign > 0) == on_upper:
                ends[sign] = (limit, "bound")
                continue
            ends[sign] = _walk(refinement, data, path, row.value, sign, limit,
                               row.stderr, cut, chi2_fit, max_refits, points)

    lowest = min([chi2_fit, *(p.chi2 for p in points if p.chi2 is not None)])
    (lower, lower_stop), (upper, upper_stop) = ends[-1], ends[1]
    return ParameterInterval(
        path=path, value=row.value, stderr=row.stderr, at_bound=row.at_bound,
        level=level, one_sided=one_sided, quantile=quantile,
        delta_chi2_cut=cut, lower=lower, upper=upper,
        lower_stop=lower_stop, upper_stop=upper_stop,
        chi2_fit=chi2_fit, chi2_lowest=lowest,
        fit_is_minimum=chi2_fit - lowest <= PARAMETER_INTERVAL_CHI2_TOL * cut,
        points=points, n_refits=sum(p.runs for p in points))
