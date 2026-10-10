"""Bounded Levenberg-Marquardt driver — the alternative to scipy's TRF.

Gauss-Newton normal equations with the adaptive Marquardt constant of Coelho,
A. A. (2018). *J. Appl. Cryst.* **51**, 428-435 ("Optimum Levenberg-Marquardt
constant determination for nonlinear least-squares"), each damped step solved
exactly inside the parameter box by bounded-variable least squares (Stark, P.
B. & Parker, R. L. (1995). *Comput. Statist.* **10**, 129-141; WP-1937).  The
paper pairs the schedule with the bound-constrained conjugate gradient of
:mod:`.bccg` (Coelho 2005), which this driver used for every step until
WP-1937 and still uses above :data:`BVLS_MAX_COLUMNS`, where only a Pawley
block reaches.
Independent implementation from the papers; TOPAS is closed source and none of
it was consulted.

Why a second driver at all, given scipy TRF is the reference and stays the
default: **constraint vocabulary**.  ``scipy.optimize.least_squares`` speaks
only boxes on individual parameters.  This driver adds

* boxes enforced *inside* the linear solve rather than after it, and
* **linear inequalities on functionals of θ** — rows ``T·θ ≥ 0`` — which is
  the shape the Stephens anisotropic-strain positivity cone has, and which no
  box can express (see :class:`LinearInequality`).

It is not a speed play.  The normal-equation solve is a minority of this
package's runtime — ``derivative_bases`` costs ~2× the forward evaluation, and
Coelho's own N = 1325 case drops the *solve* from 484 s to 2.86 s while the
whole refinement only drops 2441 s → 1785 s — so a solver that halved every
solve would buy ≈1.25× overall.

Conventions, which must match :mod:`.least_squares` exactly or λ is meaningless:

* the residual is ``r = √w·(y_obs − y_calc)`` and ``J = ∂r/∂θ``, so the paper's
  objective ``S = rᵀr`` is our χ² and ``LSQOutcome.cost_*`` is scipy's ½·rᵀr;
* ``A = JᵀJ``, ``b = −Jᵀr`` — exactly Coelho's equation (6), whose ``b`` is
  ``−½∇S``;
* λ is added after the diagonal pre-conditioner ``A_ii = 1``, which is what
  makes it dimensionless and lets the published constants transfer.

**The sign of ΔS_t.**  The paper's equation (9) defines ``r_u = ΔS_t/ΔS`` with
``ΔS_t = Δpᵀb``.  Taken literally with its own ``b`` that is positive for a
descent step while ΔS < 0, so every good step would report ``r_u < 0`` — which
contradicts its Table 1 (``r_u ≈ 1.003`` on a near-quadratic step), its §1.2
claim that ``S_t(p+Δp) = S(p+Δp)`` for quadratic S, and its Fig. 10
distribution ("almost all of the iterations have r_u < 1").  The
self-consistent reading is

    ΔS_t = −Δθᵀb

for which an exactly linear model gives ``r_u ≡ 1``: with ``r(θ+Δ) = r + JΔ``,
``S(θ+Δ) = S − 2Δᵀb + ΔᵀAΔ``, and at the exact Gauss-Newton step ``Δ = A⁻¹b``
this is ``S − Δᵀb``, so ``ΔS = −Δᵀb = ΔS_t``.  That identity is the calibration
test (``tests/test_lm_solver.py::test_ru_is_one_on_a_linear_model``) and the
only way to know the schedule is being fed the quantity its constants were
tuned for.

**Where the two drivers can part company on the answer** (WP-1113): on a
protocol whose width stages walk a degenerate valley into a stage that opens
a *new* basin — the QPA cpd-2 protocol, where per-phase size/strain × U,V,W,
X,Y are near-degenerate and the texture stage's March-Dollase basin is only
downhill from some points of that valley — the two drivers stop at different,
locally equivalent valley points, and the LM's can be one from which the
texture basin is unreachable (Rwp 0.245 against TRF's 0.133, brucite 76
against 38 wt %).  Measured to be a *genuine local minimum*, not a driver
defect: a TRF polish from the LM's exact state stays at Rwp 0.244.  Basin
selection on a shared degeneracy is path luck, not driver quality — but the
reference protocols were tuned under TRF, so on a texture-bearing staged plan
prefer the default driver or re-validate the answer (the case lives in
``examples/bench_solver.py``).

**The cost is always a fresh fp64 residual evaluation**, never an extrapolation
from the same reduced-precision quantities that built the columns.  That is
what lets a backend compute Jacobian columns in fp32 and still land on the
fp64 answer (WP-0403/0408: an all-fp32-column Apple-GPU refinement lands
3.5e-8 Å from numpy fp64 *because the driver re-measures each step against an
fp64 cost*).  ``require_fp64`` guards the normal-equation assembly, where
cond(JᵀJ) = cond(J)² makes reduced precision unrecoverable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.optimize import lsq_linear

from ..backend.linalg64 import require_fp64, to_host_fp64
from . import bccg

#: λ schedule constants, Coelho (2018) equation (9).  λ starts at 0 (pure
#: Gauss-Newton) and is dimensionless because the system is pre-conditioned.
_LAMBDA_FAIL_FLOOR = 0.1     # failed step → λ ← 10·max(λ, 0.1)
_LAMBDA_FAIL_FACTOR = 10.0
_M_LO, _M_HI = 0.4, 10.0     # m_u = Limit(r_u, 0.4, 10)
_Q_WINDOW = 10               # Q_u sums the last ten overshoot signs …
_Q_TRIGGER = 5               # … and λ/10 fires only above this

#: inner (Levenberg-Marquardt) iterations per outer iteration before giving up.
#: λ grows by 10× per failure from a floor of 0.1, so this reaches λ ≈ 1e14 —
#: far into steepest-descent territory; if nothing downhill exists there, none
#: exists.
_INNER_MAX = 18
#: consecutive outer iterations below ``ftol`` that count as converged.  One
#: small step is a small step; three running is convergence (Coelho's rule).
_CONVERGED_RUNS = 3
#: relative floor on the *predicted* decrease −Δθᵀb.  Below this the step
#: cannot be measured against S in fp64 (S is a sum of ~10⁴ squares, so its
#: own resolution is ~1e-16·S), and a "failed" step is then a measurement
#: artefact rather than information about the objective.  Without this floor a
#: stall costs the full inner budget — measured on the SRM 660c protocol, λ
#: ramping to 3.6e27 while every trial step underflowed the cost difference.
_PREDICTED_FLOOR = 1e-12

#: fraction-to-the-boundary factor for linear-inequality rows: a step is
#: truncated to 99.5 % of the distance to the constraint surface, so iterates
#: stay strictly feasible and can still move tangentially next iteration.
#: A step truncated to *exactly* the boundary would stall there.
_FEASIBLE_FRACTION = 0.995
#: relative slack below which a linear-inequality row counts as *active* and is
#: treated as an equality for the step (see ``LinearInequality.project_step``).
_ACTIVE_TOL = 1e-9
#: eigenvalues of the equilibrated normal matrix below this × (number of
#: residual rows) × λmax are discarded from the step: the scale of the
#: rounding error in one entry of JᵀJ (see :func:`_solve_step`).
_EIGEN_CUT_PER_ROW = float(np.finfo(np.float64).eps)
#: Largest system the step solves exactly by BVLS; above it the step is
#: BCCG's (:func:`_solve_step`).  Measured on Pawley-shaped systems (one
#: banded column per reflection plus 13 dense ones, macOS arm64, WP-1937):
#: a BVLS solve costs 2-34 ms at 128 columns, 0.13-0.8 s at 400, 1.5-11 s at
#: 1000 and 10-177 s at 2000, the range spanning few to most intensities on
#: their floor.  BCCG costs at most 22 ms at every size, and reaches a model
#: value 5-22 % short of the exact minimum.  Every table-only stage in the
#: acceptance fits is far below the cut, so only a Pawley block crosses it;
#: on NAC's (142 columns) the two steps reach the same answer.
BVLS_MAX_COLUMNS = 128


@dataclass(frozen=True)
class LinearInequality:
    """Rows ``T·θ + c ≥ 0`` the solver must keep satisfied.

    This is the piece published BCCG explicitly cannot do: its §4 states that a
    constraint which is a function of several parameters "cannot be handled in
    the loop — a restraint which modifies the A matrix is necessary".  Rather
    than turn the constraint into a soft restraint (which would let it be
    violated whenever the data pull hard enough — the present behaviour, and
    the reason no Stephens S_HKL is quotable today), the step is truncated
    short of the constraint surface, which keeps *every* iterate feasible.

    A box is the special case ``T = ±I``; it is not routed through here,
    because the step solves boxes exactly (:func:`_solve_step`) where
    truncation stops short of them.  Coelho (2005) measured the same gap for
    bounds inside the solve against bounds applied after it (Pawley, Rwp 3.901
    in 16 iterations against 4.351 in 84).  Truncation is the fallback for rows
    a box cannot express.

    ``T`` is (n_rows, n_free) and frozen for the whole least-squares run — the
    same frozen-per-stage discipline the hkl list and window ranges follow.
    """

    T: np.ndarray
    c: np.ndarray
    #: what the rows mean, for diagnostics ("phases.0.microstrain" …)
    label: str = ""

    def violated(self, theta: np.ndarray) -> np.ndarray:
        return (self.T @ theta + self.c) < 0.0

    def slack(self, theta: np.ndarray) -> np.ndarray:
        return self.T @ theta + self.c

    def project_step(self, theta: np.ndarray, step: np.ndarray) -> np.ndarray:
        """Remove the components of ``step`` that press into *active* rows.

        Truncation alone is not enough, and this is the failure it fixes: once
        an iterate reaches the constraint surface, a step with any inward
        component gets scaled by τ ≈ 0 — which also kills the part of the step
        running *along* the surface, so the solve stalls on the boundary and
        reports failure at the first outer iteration.  Measured on brucite,
        whose strain refinement drives straight onto the cone: without this the
        constrained fit terminates as "diverged" at Rwp 0.191 against the
        unconstrained 0.179.

        So rows already at the surface *and* being closed further are treated
        as equalities for this step: the step is projected onto their null
        space (least squares, since the active rows are generally dependent —
        the Stephens cone has 43 rows over 4 free DOFs).  What survives is
        motion tangent to the active surface, which is what a constrained
        optimiser is supposed to keep.  Rows not yet active are handled by
        :meth:`max_feasible_fraction` afterwards.
        """
        g0 = self.slack(theta)
        scale = max(float(np.max(np.abs(g0))), 1.0)
        active = g0 <= _ACTIVE_TOL * scale
        if not np.any(active):
            return step
        rows = self.T[active]
        inward = (rows @ step) < 0.0
        if not np.any(inward):
            return step
        Tb = rows[inward]
        # minimum-norm correction: step ← step − Tbᵀ (Tb Tbᵀ)⁺ Tb step
        lam, *_ = np.linalg.lstsq(Tb @ Tb.T, Tb @ step, rcond=None)
        return step - Tb.T @ lam

    def max_feasible_fraction(self, theta: np.ndarray, step: np.ndarray) -> float:
        """Largest τ ∈ (0, 1] with ``T·(θ + τ·step) + c ≥ 0``, times 0.995.

        Rows the step moves *away* from the surface (or parallel to it) never
        bind, so only negative ``T·step`` entries can truncate.
        """
        g0 = self.T @ theta + self.c
        dg = self.T @ step
        closing = dg < 0.0
        if not np.any(closing):
            return 1.0
        # τ_i is where row i reaches zero; a row already at/below zero (numerical
        # slack from a previous truncation) gives τ_i ≤ 0 and would stall the
        # solve, so it is floored at 0 and reported by ``violated``.
        with np.errstate(divide="ignore", invalid="ignore"):
            tau = np.where(closing, -g0 / dg, np.inf)
        tau_min = float(np.min(np.maximum(tau, 0.0)))
        return min(1.0, _FEASIBLE_FRACTION * tau_min)


@dataclass
class LMOutcome:
    """What :func:`minimize` returns — deliberately scipy-``OptimizeResult``-shaped
    so :func:`.least_squares.run_least_squares` can consume either driver."""

    x: np.ndarray
    fun: np.ndarray            # residual at x (fp64, freshly evaluated)
    jac: np.ndarray            # Jacobian at x
    cost: float                # ½·rᵀr, scipy's convention
    #: residual evaluations, the initial one included — scipy's ``nfev``, and
    #: the unit both drivers' budget is in (WP-1937)
    nfev: int
    njev: int
    n_outer: int
    #: >0 converged, 0 budget spent.  Never negative: like scipy's TRF, which
    #: returns −1 only from MINPACK's ``method="lm"``, this driver accepts only
    #: steps that lower S, so a run that found nothing downhill stopped at a
    #: point it could not improve rather than diverging from one (WP-1937)
    status: int
    lambda_final: float = 0.0
    n_bound_hits: int = 0
    n_truncated: int = 0       # steps shortened by a linear-inequality row
    #: inner iterations burned on a point where the linearised model promised
    #: descent the true objective did not deliver (a corner, not a minimum)
    n_stalled: int = 0
    #: which criterion ended the run (WP-1113), the LM half of
    #: :data:`~.least_squares._TRF_TERMINATION`'s vocabulary:
    #: ``ftol_runs`` (relative decrease under ftol for three consecutive outer
    #: iterations — Coelho's rule), ``exhausted_fp64`` (every remaining step
    #: promises less than fp64 can measure against S, a zero step included:
    #: the bounded model's minimum is the current point), ``no_descent`` (the
    #: inner loop found nothing downhill even at large λ), ``max_nfev`` (the
    #: evaluation budget, TRF's token for the same stop).
    termination: str = "max_nfev"
    #: the bounds that hold the returned point, scipy's ``active_mask``
    #: convention (−1 lower, +1 upper, 0 neither) and exact: the variable sits
    #: *on* the bound, the step having landed it there, and the gradient at
    #: the returned point pushes it outward, so its multiplier is positive
    #: (WP-1937).  Exact up to :data:`BVLS_MAX_COLUMNS`; above it the step is
    #: BCCG's, which can leave a variable just off its bound and so out of
    #: this set.  scipy's TRF reports the same field within ``xtol`` of a
    #: bound whatever the gradient, its iterates being strictly feasible.
    active_mask: np.ndarray | None = None


def _clip_to_bounds(x: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    return np.clip(x, lo, hi)


def _next_lambda(lam: float, r_u: float | None, q: float) -> float:
    """Coelho (2018) equation (9).

    ``r_u is None`` marks a failed step (ΔS ≥ 0), condition (i).  The three
    remaining branches all apply to steps that *lowered* S, and the novelty is
    condition (iv): damping although S dropped, because a step that overshoots
    the minimum still lowers S while wasting most of its length.
    """
    if r_u is None:                                     # (i) ΔS ≥ 0
        return _LAMBDA_FAIL_FACTOR * max(lam, _LAMBDA_FAIL_FLOOR)
    if q > _Q_TRIGGER:                                  # (ii) rare: mostly overshoots
        return lam / _LAMBDA_FAIL_FACTOR
    m_u = min(max(r_u, _M_LO), _M_HI)
    if m_u <= 1.0:                                      # (iii) at or under prediction
        return 0.5 * m_u * lam
    return m_u * (lam + 0.5) - 0.5                      # (iv) overshoot → damp


def minimize(residual: Callable[[np.ndarray], np.ndarray],
             jacobian: Callable[[np.ndarray], np.ndarray],
             x0: np.ndarray, *,
             lo: np.ndarray, hi: np.ndarray,
             max_nfev: int = 400,
             ftol: float = 1e-9,
             inequalities: list[LinearInequality] | None = None,
             callback: Callable[[np.ndarray, float], None] | None = None,
             on_trial: Callable[[np.ndarray, float, bool, float, float],
                                None] | None = None,
             ) -> LMOutcome:
    """Minimise ``S(θ) = r(θ)ᵀr(θ)`` subject to ``lo ≤ θ ≤ hi`` (and ``T·θ+c ≥ 0``).

    Two nested loops, exactly Coelho (2018) Fig. 1: the outer one recomputes A
    and b at an accepted point; the inner one raises λ until a step lowers S.
    ``max_nfev`` caps residual evaluations, the initial one included, which is
    what scipy's ``max_nfev`` caps, so one budget means one thing on both
    drivers (WP-1937).  The inner loop is also bounded on its own, so a point
    with nothing downhill cannot spin.

    Termination: relative decrease in S below ``ftol`` for three consecutive
    outer iterations (Coelho's own criterion — a single small step is not
    convergence, it is a small step), or an inner loop that cannot find any
    downhill step even at large λ.  Both are convergence, including at the
    first outer iteration: a stage that starts at its minimum has nothing
    downhill to find.

    ``callback(x, cost)`` fires on each *accepted* point; ``on_trial(x_try,
    cost, accepted, lam, step_norm)`` fires once per trial the residual
    actually measured (WP-1113), with ``cost = ½·rᵀr`` at the trial, the λ
    that produced the step, and the norm of the *taken* step — after
    projection, inequality truncation and the box clamp.  A trial the linear
    model discards unevaluated (no descent promised, or a promise under the
    fp64 floor) never reaches the residual and never fires it.
    """
    x = _clip_to_bounds(np.asarray(x0, dtype=np.float64).copy(), lo, hi)
    ineqs = list(inequalities or [])

    r = residual(x)
    require_fp64(r, "least-squares residual")
    if not np.all(np.isfinite(r)):
        # scipy's TRF refuses the same start in the same words.  Run on, every
        # trial compares against S = nan and is rejected, which now reads as
        # convergence rather than the first-iteration "diverged" it was.
        raise ValueError("Residuals are not finite in the initial point.")
    s = float(r @ r)
    n_fev, n_jev = 1, 0
    lam = 0.0
    signs: list[int] = []
    small_runs = 0
    n_truncated = 0
    n_stalled = 0
    status = 0
    n_outer = 0
    termination = "max_nfev"

    while n_fev < max_nfev:
        n_outer += 1
        J = jacobian(x)
        n_jev += 1
        # invariant 2: cond(JᵀJ) = cond(J)², so the normal equations are the one
        # step that can never run below fp64 whatever built the columns
        Jh = to_host_fp64(J)
        A = Jh.T @ Jh
        b = -(Jh.T @ r)

        accepted = False
        exhausted = False
        spent = False
        for _inner in range(_INNER_MAX):
            step, side = _solve_step(A, b, lam, x, lo, hi, n_rows=len(r))
            if not np.any(step):
                # the model's minimum over the box is where we stand
                exhausted = True
                break
            solved = step
            for iq in ineqs:
                step = iq.project_step(x, step)
            tau = min((iq.max_feasible_fraction(x, step) for iq in ineqs), default=1.0)
            if tau < 1.0:
                step = tau * step
                n_truncated += 1
            floor = -_PREDICTED_FLOOR * max(abs(s), 1.0)
            x_try = _clip_to_bounds(x + step, lo, hi)
            if step is solved:
                # a variable the solve put on a bound lands on it exactly:
                # (lo − x)·d/d need not round back to lo − x, and the active
                # set is read as x == bound
                x_try = np.where(side < 0, lo, np.where(side > 0, hi, x_try))
            step = x_try - x            # the *taken* step, after every clamp
            promise = -float(step @ b)
            if promise >= 0.0:
                # Not a descent direction *for the model* — which is a
                # statement about the model, not the objective.  The exact
                # bounded solve cannot return one, since Δ = 0 is feasible and
                # its model value is zero.  The inequality projection can, and
                # so could BCCG's truncated CG before WP-1937 (measured on
                # brucite: ‖Δ‖ ≈ 2e10 promising +1.7e5).  Either is what λ
                # exists for: damp and retry.
                lam = _next_lambda(lam, None, 0.0)
                continue
            if promise > floor:
                # a genuine descent direction, but promising less than fp64 can
                # measure against S: trying it would sample rounding noise, and
                # every further λ increase promises less still
                exhausted = True
                break
            if n_fev >= max_nfev:
                spent = True
                break
            r_try = residual(x_try)
            n_fev += 1
            s_try = float(r_try @ r_try)
            ds = s_try - s
            if on_trial is not None:
                on_trial(x_try, 0.5 * s_try, bool(ds < 0.0), float(lam),
                         float(np.linalg.norm(step)))
            if ds < 0.0:
                # ΔS_t = −Δθᵀb (see module docstring — the paper drops this sign)
                ds_t = -float(step @ b)
                r_u = ds_t / ds
                signs.append(1 if r_u > 1.0 else -1)
                q = min(max(sum(signs[-_Q_WINDOW:]), 0), 10)
                lam = _next_lambda(lam, r_u, q)
                rel = -ds / max(abs(s), 1e-300)
                x, r, s = x_try, r_try, s_try
                accepted = True
                if callback is not None:
                    callback(x, 0.5 * s)
                small_runs = small_runs + 1 if rel < ftol else 0
                break
            lam = _next_lambda(lam, None, 0.0)
        if spent:
            break
        if not accepted:
            # No downhill step exists that the cost can resolve.  That is
            # convergence, on the first outer iteration as on any later one,
            # since a stage can start at its minimum (WP-1937; it reported
            # "diverged" before, and a series quarantines on that word) — and
            # *not* always because a minimum was reached: an objective with a
            # corner (the FCJ profile at S/L = H/L is one, and the default
            # instrument starts both apertures equal) presents a linearised
            # model that promises descent in a direction the true function
            # climbs.  ``n_stalled`` records it; the correlation guard reports
            # the degeneracy.  TRF says ``xtol`` at the same point.
            n_stalled = _INNER_MAX if not exhausted else 0
            status = 1
            termination = "exhausted_fp64" if exhausted else "no_descent"
            break
        if small_runs >= _CONVERGED_RUNS:
            status = 1
            termination = "ftol_runs"
            break

    # J must be the Jacobian *at the returned point* — covariance_estimates
    # reads it together with ``fun``, and a stale one silently mis-scales
    # every esd.  Re-evaluating at an already-visited θ is nearly free: the
    # FCJ node memo (WP-0605) keys on exact input equality.
    J = jacobian(x)
    n_jev += 1
    at_bounds = (np.isclose(x, lo) & np.isfinite(lo)) | (np.isclose(x, hi) & np.isfinite(hi))
    n_bound_hits = int(np.count_nonzero(at_bounds))
    # ½∇S = Jᵀr: positive means S falls as the variable decreases
    half_grad = to_host_fp64(J).T @ r
    active = np.zeros(len(x), dtype=np.int8)
    active[(x == lo) & (half_grad > 0.0)] = -1
    active[(x == hi) & (half_grad < 0.0)] = 1
    return LMOutcome(x=x, fun=r, jac=J, cost=0.5 * s, nfev=n_fev, njev=n_jev,
                     n_outer=n_outer, status=status, lambda_final=lam,
                     n_bound_hits=n_bound_hits, n_truncated=n_truncated,
                     n_stalled=n_stalled, termination=termination,
                     active_mask=active)


def _solve_step(A: np.ndarray, b: np.ndarray, lam: float, x: np.ndarray,
                lo: np.ndarray, hi: np.ndarray, *, n_rows: int
                ) -> tuple[np.ndarray, np.ndarray]:
    """One damped Gauss-Newton step, solved exactly inside the box (WP-1937).

    Minimises the model ``½ΔᵀA_λΔ − bᵀΔ`` subject to ``lo − x ≤ Δ ≤ hi − x``.
    λ rides on the *pre-conditioned* diagonal (A_ii = 1), so adding ``lam`` to
    a copy of A scaled to unit diagonal is the same thing as Marquardt's
    multiplicative form and keeps the published constants meaningful.

    The bounded quadratic is handed to bounded-variable least squares (Stark &
    Parker 1995, ``scipy.optimize.lsq_linear(method="bvls")``) as the square
    system ``R = Λ^½Vᵀ``, ``c = Λ^-½Vᵀb`` from the eigendecomposition of the
    equilibrated A, for which ``‖RΔ − c‖² = ΔᵀAΔ − 2bᵀΔ + const``.  BVLS is an
    active-set method: a variable it holds is *on* its bound, never near it,
    and its solve is exact rather than the truncated CG of :mod:`.bccg`.  That
    is the case scipy's TRF cannot handle — several widths pressed on zero
    together, where its interior scaling crawls (WP-1929's grid).

    **The eigenvalue cut** (:data:`_EIGEN_CUT_PER_ROW`): A is formed as JᵀJ,
    so each equilibrated entry is an inner product over m = ``n_rows`` terms
    of two unit-norm columns, and carries a rounding error up to
    γₘ = m·u/(1 − m·u) with u = ε/2 (Higham 2002, §3.1).  An eigenvalue below
    ``m·ε·λmax`` is at that error's scale, so its direction is discarded and
    the step there is zero, BVLS solving the remaining rank-deficient system
    to minimum norm.  The cut binds only near λ = 0: a damped system has every
    eigenvalue at or above λ.

    **Above** :data:`BVLS_MAX_COLUMNS` the step is BCCG's, inexact and fast.
    scipy's BVLS refactors the free set from scratch at each active-set change,
    so its cost grows as n³ times the number of changes, and a Pawley block
    appends one column per reflection.

    Returns the step and which bound each variable was solved onto (−1 lower,
    +1 upper, 0 neither), so the caller can land those variables *exactly* on
    the bound the solve chose.  BCCG reports none.
    """
    n = len(b)
    d = np.sqrt(np.maximum(np.diag(A), 0.0))
    d = np.where(d > 0.0, d, 1.0)
    if n > BVLS_MAX_COLUMNS:
        out = bccg.solve(A + lam * np.diag(d * d), b, lo=lo - x, hi=hi - x)
        return out.x, np.zeros(n, dtype=np.int8)
    inv_d = 1.0 / d
    A_s = A * np.outer(inv_d, inv_d)
    A_s[np.diag_indices(n)] += lam
    b_s = b * inv_d
    w, V = np.linalg.eigh(A_s)
    w_max = float(w[-1]) if n else 0.0
    keep = w > _EIGEN_CUT_PER_ROW * max(n_rows, n) * w_max
    side = np.zeros(n, dtype=np.int8)
    if w_max <= 0.0 or not np.any(keep):
        return np.zeros(n), side
    root = np.sqrt(w[keep])
    Vk = V[:, keep]
    R = root[:, None] * Vk.T
    c = (Vk.T @ b_s) / root
    lb, ub = (lo - x) * d, (hi - x) * d
    out = lsq_linear(R, c, bounds=(lb, ub), method="bvls")
    side[out.active_mask < 0] = -1
    side[out.active_mask > 0] = 1
    return out.x * inv_d, side
