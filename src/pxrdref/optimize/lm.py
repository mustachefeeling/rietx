"""Bounded Levenberg-Marquardt driver — the alternative to scipy's TRF.

Gauss-Newton normal equations with the adaptive Marquardt constant of Coelho,
A. A. (2018). *J. Appl. Cryst.* **51**, 428-435 ("Optimum Levenberg-Marquardt
constant determination for nonlinear least-squares"), solved by the
bound-constrained conjugate gradient of :mod:`.bccg` (Coelho 2005).
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
    because BCCG's in-loop clamping handles boxes better than truncation does
    (the paper's own Pawley measurement: Rwp 3.901 in 16 iterations vs 4.351 in
    84).  Truncation is the fallback for rows a box cannot express.

    ``T`` is (n_rows, n_free) and frozen for the whole least-squares run — the
    same frozen-per-stage discipline the hkl list and window ranges follow.
    """

    T: np.ndarray
    c: np.ndarray
    #: what the rows mean, for diagnostics ("phases.0.microstrain" …)
    label: str = ""

    def violated(self, theta: np.ndarray) -> np.ndarray:
        return (self.T @ theta + self.c) < 0.0

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
    nfev: int
    njev: int
    n_outer: int
    status: int                # >0 converged, 0 max_iter, <0 diverged
    lambda_final: float = 0.0
    n_bound_hits: int = 0
    n_truncated: int = 0       # steps shortened by a linear-inequality row
    #: inner iterations burned on a point where the linearised model promised
    #: descent the true objective did not deliver (a corner, not a minimum)
    n_stalled: int = 0


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
             max_iter: int = 100,
             ftol: float = 1e-9,
             inequalities: list[LinearInequality] | None = None,
             callback: Callable[[np.ndarray, float], None] | None = None,
             ) -> LMOutcome:
    """Minimise ``S(θ) = r(θ)ᵀr(θ)`` subject to ``lo ≤ θ ≤ hi`` (and ``T·θ+c ≥ 0``).

    Two nested loops, exactly Coelho (2018) Fig. 1: the outer one recomputes A
    and b at an accepted point; the inner one raises λ until a step lowers S.
    ``max_iter`` bounds the outer loop; the inner loop is bounded separately so
    a hopeless point cannot spin forever.

    Termination: relative decrease in S below ``ftol`` for three consecutive
    outer iterations (Coelho's own criterion — a single small step is not
    convergence, it is a small step), or an inner loop that cannot find any
    downhill step even at large λ.
    """
    x = _clip_to_bounds(np.asarray(x0, dtype=np.float64).copy(), lo, hi)
    ineqs = list(inequalities or [])

    r = residual(x)
    require_fp64(r, "least-squares residual")
    s = float(r @ r)
    n_fev, n_jev = 1, 0
    lam = 0.0
    signs: list[int] = []
    small_runs = 0
    n_truncated = 0
    n_stalled = 0
    status = 0
    n_outer = 0

    for outer in range(max_iter):
        n_outer = outer + 1
        J = jacobian(x)
        n_jev += 1
        # invariant 2: cond(JᵀJ) = cond(J)², so the normal equations are the one
        # step that can never run below fp64 whatever built the columns
        Jh = to_host_fp64(J)
        A = Jh.T @ Jh
        b = -(Jh.T @ r)

        accepted = False
        exhausted = False
        for _inner in range(_INNER_MAX):
            step = _solve_step(A, b, lam, x, lo, hi)
            if not np.any(step):
                break
            tau = min((iq.max_feasible_fraction(x, step) for iq in ineqs), default=1.0)
            if tau < 1.0:
                step = tau * step
                n_truncated += 1
            x_try = _clip_to_bounds(x + step, lo, hi)
            step = x_try - x            # the *taken* step, after every clamp
            if -float(step @ b) > -_PREDICTED_FLOOR * max(abs(s), 1.0):
                # the step promises less than fp64 can measure on this cost:
                # trying it would only sample rounding noise, and every further
                # λ increase promises less still
                exhausted = True
                break
            r_try = residual(x_try)
            n_fev += 1
            s_try = float(r_try @ r_try)
            ds = s_try - s
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
        if not accepted:
            # No downhill step exists that the cost can resolve.  That is
            # convergence once we have moved at all — and *not* always because
            # a minimum was reached: an objective with a corner (the FCJ
            # profile at S/L = H/L is one, and the default instrument starts
            # both apertures equal) presents a linearised model that promises
            # descent in a direction the true function climbs.  ``n_stalled``
            # records it; the correlation guard reports the degeneracy.
            n_stalled = _INNER_MAX if not exhausted else 0
            status = 1 if outer > 0 else -1
            break
        if small_runs >= _CONVERGED_RUNS:
            status = 1
            break
    else:
        status = 0                            # ran out of outer iterations

    # J must be the Jacobian *at the returned point* — covariance_estimates
    # reads it together with ``fun``, and a stale one silently mis-scales
    # every esd.  Re-evaluating at an already-visited θ is nearly free: the
    # FCJ node memo (WP-0605) keys on exact input equality.
    J = jacobian(x)
    n_jev += 1
    at_bounds = (np.isclose(x, lo) & np.isfinite(lo)) | (np.isclose(x, hi) & np.isfinite(hi))
    n_bound_hits = int(np.count_nonzero(at_bounds))
    return LMOutcome(x=x, fun=r, jac=J, cost=0.5 * s, nfev=n_fev, njev=n_jev,
                     n_outer=n_outer, status=status, lambda_final=lam,
                     n_bound_hits=n_bound_hits, n_truncated=n_truncated,
                     n_stalled=n_stalled)


def _solve_step(A: np.ndarray, b: np.ndarray, lam: float, x: np.ndarray,
                lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """One damped Gauss-Newton step, bounds enforced inside the CG loop.

    λ rides on the *pre-conditioned* diagonal (A_ii = 1), so adding ``lam`` to
    a copy of A scaled to unit diagonal is the same thing as Marquardt's
    multiplicative form and keeps the published constants meaningful.  BCCG
    bounds the *step*, so the parameter box ``lo ≤ x + Δ ≤ hi`` becomes
    ``lo − x ≤ Δ ≤ hi − x``.
    """
    d = np.sqrt(np.maximum(np.diag(A), 0.0))
    d = np.where(d > 0.0, d, 1.0)
    A_lam = A + lam * np.diag(d * d)
    out = bccg.solve(A_lam, b, lo=lo - x, hi=hi - x)
    return out.x
