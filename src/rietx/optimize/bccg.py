"""Bound-constrained conjugate gradient solve of the normal equations.

Coelho, A. A. (2005). *J. Appl. Cryst.* **38**, 455-461 — "A bound constrained
conjugate gradient solution method as applied to crystallographic refinement
problems".  Independent implementation from the paper; TOPAS is closed source
and none of it was consulted (ATTRIBUTION.md, DESIGN.md "Locked decisions").

Solves ``A x = b`` for symmetric positive semi-definite ``A`` — here the
Gauss-Newton normal matrix JᵀJ (+λ on the diagonal) — by conjugate gradients
(Hestenes & Stiefel 1952; Polak 1971 form) with four modifications, all of
which exist to *terminate the CG loop early on ill-conditioned systems* rather
than to converge harder:

1. **Box bounds inside the loop.**  A parameter that would violate a bound is
   clamped to it and removed from the CG loop for the rest of *this* solve —
   never from the least-squares process, and reinstated on the next call.  This
   is the modification that changes answers rather than timings: the paper's
   Pawley case reaches Rwp 3.901 in 16 iterations with in-loop clamping against
   4.351 in 84 when the same bounds are applied *after* an unconstrained solve.
2. **Early-iteration step damping**, their equation (1) — printed as
   ``α = Max[(k+1)/N_k, 1]·s_k/(p·q)``, and the one place where the paper's
   formula and its own prose disagree.  See ``_alpha``: the reading is a
   selectable option here because it was *measured* rather than argued.
3. **Small-contribution removal**, their equation (2): a parameter with
   ``200·r_i²·N_k < s_0`` for six consecutive iterations leaves the loop.  On a
   block-diagonal system this lets converged blocks drop out and the rest carry
   on — the measured 3.30 s → 1.31 s on their Pawley refinement, at identical
   Rwp.
4. **Termination** at ``k_max`` = (k of the last removal) + N_k, or when
   ``s_k < 1e-4·s_0`` three iterations running.

With no active bounds and ``removal=False`` this reduces to textbook CG, and so
must reproduce a direct solve — the anchor
``tests/test_bccg.py::test_unconstrained_matches_direct_solve``.

The system is diagonally pre-conditioned to A_ii = 1 before any of this, which
is also what makes the Levenberg-Marquardt λ of :mod:`.lm` dimensionless.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: their equation (2) constant — a parameter contributing less than
#: ``s_0 / (200·N_k)`` to the residual is a candidate for removal …
_SMALL_FACTOR = 200.0
#: … once it has met that condition this many iterations running.
_SMALL_RUNS = 6
#: their §2 termination: s_k below this fraction of s_0 for three iterations.
#: Note what this buys — s is a *squared* residual norm, so 1e-4 stops once
#: ‖Ax−b‖ has fallen 100×, which on a cond ≈ 1e3 system leaves ~1e-3 relative
#: error in x.  That is deliberate: the linear solve is inexact and the outer
#: Levenberg-Marquardt loop re-measures the real cost at the trial point, so
#: paying for a machine-precision step is wasted work.  The paper is explicit
#: that "the minimization of |Ax − b| for all parameters is not adhered to".
_CONVERGED_FRACTION = 1e-4
_CONVERGED_RUNS = 3


@dataclass
class BCCGResult:
    """Solution plus the loop diagnostics the paper reports (its Figs. 5-7)."""

    x: np.ndarray
    n_iterations: int
    #: parameters clamped to a bound inside the loop (their N_k,lim)
    n_clamped: int = 0
    #: parameters dropped by the small-contribution rule (their N_k,small)
    n_dropped: int = 0
    #: why the loop stopped — "converged" | "k_max" | "exhausted"
    status: str = "converged"
    #: average number of parameters still in the loop, over the iterations run
    #: (their N_k,avg — the statistic that shows why BCCG is cheap)
    n_active_avg: float = 0.0
    #: indices whose value was clamped to a bound (the caller may want to know
    #: which directions the box is holding; ``lm`` reports them as bound hits)
    clamped: list[int] = field(default_factory=list)


#: Readings of Coelho (2005) equation (1), ``α = f[(k+1)/N_k, 1]·s_k/(p·q)``.
#:
#: The paper prints ``f = Max``; its text says the factor "reduces the original
#: α in the early iterations … allow[ing] for small changes in parameters that
#: would otherwise be removed [by] violation of the bounding constraints",
#: which describes ``Min``.  Neither is obviously the transcription error, and
#: neither survives measurement:
#:
#: * ``"min"`` matches the prose and is a *hard* damper — at N = 1325 (their
#:   largest system) it scales the first step by 1/1325, which cannot be
#:   reconciled with their reported "around ten CG iterations regardless of N".
#:   Measured, it captures 0.003-0.72 of the available decrease in the
#:   quadratic model where the undamped step captures ~1.
#: * ``"max"`` is the printed formula.  It is exactly a no-op while k+1 ≤ N_k
#:   — which is *most* of the loop, since the k_max rule stops at
#:   (last removal) + N_k.  Where it is not a no-op it is harmful: once the
#:   removal schemes shed parameters, k+1 > N_k *amplifies* α past the exact
#:   line minimiser, and the captured decrease falls from 1.000 to 0.62
#:   (dense, N = 40) and 0.87 (block-diagonal).  Unchecked — with the k_max
#:   rule lifted — it diverges outright.
#:
#: So the shipped default is ``"off"``: identical to the printed formula
#: everywhere the printed formula is safe, and free of its one active failure
#: mode.  Both readings stay available, and `tests/test_bccg.py` pins the
#: numbers above, because "we picked the other word" is not something to
#: discover later from a bad fit.
_DAMPINGS = ("max", "min", "off")


def _alpha(k: int, n_active: int, s_k: float, pq: float, damping: str) -> float:
    """Step length of their equation (1) under the chosen reading."""
    ratio = (k + 1) / max(n_active, 1)
    if damping == "min":
        factor = min(ratio, 1.0)
    elif damping == "max":
        factor = max(ratio, 1.0)
    else:
        factor = 1.0
    return factor * s_k / pq


def solve(A: np.ndarray, b: np.ndarray, *,
          x0: np.ndarray | None = None,
          lo: np.ndarray | None = None,
          hi: np.ndarray | None = None,
          removal: bool = True,
          damping: str = "off",
          tol: float = _CONVERGED_FRACTION,
          k_max_rule: bool = True,
          max_iter: int | None = None) -> BCCGResult:
    """BCCG solve of ``A x = b`` with optional per-element bounds on ``x``.

    ``A`` must be symmetric positive semi-definite and is used only through
    matrix-vector products.  ``lo``/``hi`` bound the *solution vector* — in
    :mod:`.lm` that is the parameter step's landing point mapped back to a step
    bound, since the paper bounds parameters and CG solves for the step.

    The diagonal pre-conditioner (A_ii = 1) is applied here rather than by the
    caller: a zero diagonal entry (a parameter with an identically zero
    Jacobian column — a dead softplus gradient, a locked direction) would divide
    by zero, so those entries keep scale 1 and, with b_i = 0, simply never move.

    ``tol`` and ``k_max_rule`` expose the two published stopping rules so a test
    can separate "the CG core is exact" from "the published termination is
    deliberately cheap"; both defaults are Coelho's and neither should be
    changed by ordinary callers.
    """
    if damping not in _DAMPINGS:
        raise ValueError(f"damping must be one of {_DAMPINGS}, got {damping!r}")
    A = np.asarray(A, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    n = len(b)
    if n == 0:
        return BCCGResult(np.zeros(0), 0)

    # --- diagonal pre-conditioner: solve for y = D·x with (D⁻¹AD⁻¹)y = D⁻¹b
    d = np.sqrt(np.maximum(np.diag(A), 0.0))
    d = np.where(d > 0.0, d, 1.0)
    As = A / np.outer(d, d)
    bs = b / d
    lo_s = None if lo is None else np.asarray(lo, dtype=np.float64) * d
    hi_s = None if hi is None else np.asarray(hi, dtype=np.float64) * d

    x = np.zeros(n) if x0 is None else np.asarray(x0, dtype=np.float64) * d
    # r = b − Ax; with the x = 0 start this is the paper's ``r = b``
    r = bs - As @ x if x0 is not None else bs.copy()
    p = r.copy()
    s_prev = 0.0
    s_0 = float(r @ r)
    if s_0 == 0.0:
        return BCCGResult(x / d, 0)

    active = np.ones(n, dtype=bool)
    small_runs = np.zeros(n, dtype=int)
    clamped: list[int] = []
    n_dropped = 0
    converged_runs = 0
    last_removal = 0
    active_counts: list[int] = []
    status = "exhausted"
    hard_cap = n * 4 + 20 if max_iter is None else max_iter

    k = 0
    while k < hard_cap:
        n_active = int(active.sum())
        if n_active == 0:
            status = "converged"
            break
        active_counts.append(n_active)
        s_k = float(r[active] @ r[active])
        if s_k <= 0.0:
            status = "converged"
            break
        # 2) Polak update, restricted to the parameters still in the loop
        if k > 0 and s_prev > 0.0:
            p = np.where(active, r + (s_k / s_prev) * p, 0.0)
        else:
            p = np.where(active, r, 0.0)
        # 3) q = Ap  4) α
        q = As @ p
        pq = float(p @ q)
        if pq <= 0.0:
            # A is singular (or numerically so) along p: no useful step left
            status = "converged"
            break
        alpha = _alpha(k, n_active, s_k, pq, damping)

        # 5) x = x + αp, with the bounds enforced *in* the loop
        x_new = np.where(active, x + alpha * p, x)
        if lo_s is not None or hi_s is not None:
            below = np.zeros(n, dtype=bool) if lo_s is None else (x_new < lo_s) & active
            above = np.zeros(n, dtype=bool) if hi_s is None else (x_new > hi_s) & active
            if below.any() or above.any():
                if lo_s is not None:
                    x_new = np.where(below, lo_s, x_new)
                if hi_s is not None:
                    x_new = np.where(above, hi_s, x_new)
                hit = below | above
                active &= ~hit
                clamped.extend(np.flatnonzero(hit).tolist())
                last_removal = k
        x = x_new

        # 7) r = r − αq, then the small-contribution removal of equation (2)
        r = np.where(active, r - alpha * q, 0.0)
        if removal:
            n_now = max(int(active.sum()), 1)
            small = active & (_SMALL_FACTOR * r * r * n_now < s_0)
            small_runs = np.where(small, small_runs + 1, 0)
            drop = small_runs >= _SMALL_RUNS
            if drop.any():
                active &= ~drop
                r = np.where(active, r, 0.0)
                n_dropped += int(drop.sum())
                last_removal = k

        s_prev = s_k
        k += 1

        # termination: s_k below 1e-4·s_0 three times running, or k_max
        s_now = float(r[active] @ r[active]) if active.any() else 0.0
        converged_runs = converged_runs + 1 if s_now < tol * s_0 else 0
        if converged_runs >= _CONVERGED_RUNS or s_now == 0.0:
            status = "converged"
            break
        if k_max_rule and k > last_removal + max(int(active.sum()), 1):
            status = "k_max"
            break

    return BCCGResult(
        x=x / d, n_iterations=k, n_clamped=len(clamped), n_dropped=n_dropped,
        status=status,
        n_active_avg=float(np.mean(active_counts)) if active_counts else 0.0,
        clamped=sorted(set(clamped)),
    )
