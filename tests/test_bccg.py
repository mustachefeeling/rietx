"""Bound-constrained conjugate gradient solver (WP-0601, Coelho 2005).

The anchor the paper itself supplies: with bounds inactive and the removal
scheme off, BCCG must reproduce the unconstrained solution.  Everything else
here pins the three modifications that make it *not* textbook CG — including
the one place where the paper's printed formula and its prose disagree.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.optimize import bccg


def _spd(n: int, cond: float, seed: int = 0) -> np.ndarray:
    """A symmetric positive-definite matrix with a prescribed condition number."""
    rng = np.random.default_rng(seed)
    q, _ = np.linalg.qr(rng.standard_normal((n, n)))
    eig = np.logspace(0.0, -np.log10(cond), n)
    return q @ np.diag(eig) @ q.T


def _rel_error(x: np.ndarray, x_ref: np.ndarray) -> float:
    return float(np.linalg.norm(x - x_ref) / max(np.linalg.norm(x_ref), 1e-300))


def _system(n: int, cond: float, seed: int = 7):
    A = _spd(n, cond=cond, seed=seed)
    b = np.random.default_rng(seed + 1).standard_normal(n)
    return A, b, np.linalg.solve(A, b)


@pytest.mark.parametrize(("n", "cond"), [(1, 1.0), (5, 1e2), (40, 1e3), (60, 1e6)])
def test_cg_core_matches_direct_solve(n, cond):
    """Coelho's sanity anchor: no bounds, no removal ⇒ the exact solution.

    Run with the two published *stopping* rules relaxed, because they are what
    makes the shipped solve deliberately inexact (see the next test); this
    isolates the conjugate-gradient core itself.
    """
    A, b, ref = _system(n, cond)
    out = bccg.solve(A, b, removal=False, damping="off",
                     tol=1e-24, k_max_rule=False, max_iter=40 * n + 40)
    assert _rel_error(out.x, ref) < 1e-9
    assert out.n_clamped == 0 and out.n_dropped == 0


def _decrease_captured(A: np.ndarray, b: np.ndarray, x: np.ndarray,
                       x_star: np.ndarray) -> float:
    """Fraction of the available decrease in φ(x) = ½xᵀAx − bᵀx that ``x`` takes.

    This, not ‖x − x*‖, is what an LM inner solve owes its caller: the outer
    loop re-measures the true cost at the trial point, so a step that captures
    most of the modelled decrease is a good step even when it is far from the
    exact solution in parameter space.
    """
    def phi(v):
        return 0.5 * float(v @ A @ v) - float(b @ v)
    return (phi(np.zeros_like(x)) - phi(x)) / (phi(np.zeros_like(x)) - phi(x_star))


def test_published_termination_is_deliberately_inexact():
    """The shipped defaults stop ~1e-3 short in x while taking ~all of φ.

    s is a *squared* residual norm, so ``s_k < 1e-4·s_0`` means ‖Ax−b‖ fell
    100×.  The outer LM loop re-measures the true cost at the trial point, so
    a machine-precision inner solve would be wasted work — the paper says as
    much ("the minimization of |Ax − b| … is not adhered to").
    """
    A, b, ref = _system(40, 1e3)
    cheap = bccg.solve(A, b, removal=False)
    exact = bccg.solve(A, b, removal=False, damping="off",
                       tol=1e-24, k_max_rule=False, max_iter=2000)
    assert 1e-6 < _rel_error(cheap.x, ref) < 1e-2   # close, nowhere near exact
    assert cheap.n_iterations < exact.n_iterations
    assert _decrease_captured(A, b, cheap.x, ref) > 0.999


def test_damping_readings_under_the_published_rules():
    """Which reading of their equation (1) actually solves the system.

    The paper prints ``Max`` and describes ``Min``; this is the measurement
    that settles it for us rather than an argument from the prose.  With no
    removals, ``Max`` is *bit-identical* to no damping at all — the
    amplification branch needs k+1 > N_k, which the k_max rule then forbids —
    while the prose reading stalls two orders of magnitude short.
    """
    A, b, ref = _system(60, 1e2)
    errs = {d: _rel_error(bccg.solve(A, b, removal=False, damping=d).x, ref)
            for d in bccg._DAMPINGS}
    assert errs["max"] == pytest.approx(errs["off"], rel=1e-12)
    assert errs["min"] > 100 * errs["off"]


def test_printed_damping_hurts_once_removal_shrinks_the_loop():
    """Why the shipped default is ``"off"`` rather than the printed formula.

    Removal is what makes k+1 > N_k reachable inside k_max, and that is where
    the printed ``Max`` stops being a no-op and starts amplifying α past the
    exact line minimiser.  Measured on a dense N = 40 system: 1.000 → 0.62 of
    the available decrease.  ``"off"`` matches the printed formula everywhere
    the printed formula is safe, without that failure mode.
    """
    A, b, ref = _system(40, 1e3)
    amplified = bccg.solve(A, b, removal=True, damping="max")
    plain = bccg.solve(A, b, removal=True, damping="off")
    assert amplified.n_dropped > 0
    assert _decrease_captured(A, b, plain.x, ref) > 0.99
    assert _decrease_captured(A, b, amplified.x, ref) < 0.9


def test_printed_damping_is_safe_only_because_of_the_k_max_rule():
    """``Max`` amplifies α once k+1 > N_k, and unchecked that diverges.

    Measured: with the k_max rule lifted, the printed formula leaves the
    solution *further* from the truth than the zero vector, while the prose
    reading merely converges slowly.  So the two published stopping rules are
    not an optimisation on top of the step rule — they are what makes it safe,
    and neither may be relaxed without the other.
    """
    A, b, ref = _system(60, 1e2)
    loose = dict(removal=False, tol=1e-24, k_max_rule=False, max_iter=1200)
    amplified = bccg.solve(A, b, damping="max", **loose)
    damped = bccg.solve(A, b, damping="min", **loose)
    undamped = bccg.solve(A, b, damping="off", **loose)

    assert _rel_error(amplified.x, ref) > 1e-2
    assert _rel_error(damped.x, ref) < 1e-4
    assert _rel_error(undamped.x, ref) < 1e-9


def test_removal_scheme_is_cheap_and_harmless():
    """Equation (2) drops converged directions; the answer must survive it.

    A block-diagonal system is the case the paper singles out: the easy block
    converges and leaves the loop while the hard block carries on.

    Measured cost of the scheme on this system: it drops ‖x − x*‖ accuracy by
    ~30× (3.5e-3 → 1.1e-1) while still capturing >99 % of the modelled
    decrease.  That is the paper's own trade — "increases the number of
    refinement iterations in a marginal sense, while speeding up the solution
    of the normal equations" — and it is only sound because the outer loop
    re-measures the true cost.
    """
    easy = _spd(20, cond=1.5, seed=1)
    hard = _spd(20, cond=1e4, seed=2)
    A = np.block([[easy, np.zeros((20, 20))], [np.zeros((20, 20)), hard]])
    b = np.random.default_rng(11).standard_normal(40)
    ref = np.linalg.solve(A, b)

    with_removal = bccg.solve(A, b, removal=True)
    without = bccg.solve(A, b, removal=False)

    assert with_removal.n_dropped > 0
    assert with_removal.n_active_avg < without.n_active_avg
    assert _decrease_captured(A, b, with_removal.x, ref) > 0.99
    assert _rel_error(with_removal.x, ref) > _rel_error(without.x, ref)


def test_bounds_are_enforced_and_reported():
    """A bound the unconstrained solution violates is respected exactly."""
    A, b, free = _system(10, 1e3, seed=5)

    # bound the three largest components at half their free value
    lo = np.full(10, -np.inf)
    hi = np.full(10, np.inf)
    for i in np.argsort(-np.abs(free))[:3]:
        if free[i] > 0:
            hi[i] = 0.5 * free[i]
        else:
            lo[i] = 0.5 * free[i]

    out = bccg.solve(A, b, lo=lo, hi=hi)
    assert np.all(out.x >= lo - 1e-12)
    assert np.all(out.x <= hi + 1e-12)
    assert out.n_clamped > 0
    assert set(out.clamped) <= set(range(10))


def test_inactive_bounds_change_nothing():
    """Bounds the solution never reaches must not perturb it."""
    A, b, _ = _system(15, 1e4, seed=9)
    ref = bccg.solve(A, b, removal=False).x
    wide = bccg.solve(A, b, lo=np.full(15, -1e6), hi=np.full(15, 1e6),
                      removal=False)
    assert wide.n_clamped == 0
    assert _rel_error(wide.x, ref) < 1e-12


def test_zero_diagonal_column_is_survivable():
    """A parameter with an identically zero Jacobian column must not divide by 0.

    This is the dead-softplus-gradient case (WP-0310): the column is zero, so
    A_ii = 0 and b_i = 0, and the parameter simply never moves.
    """
    A = _spd(6, cond=1e3, seed=4)
    A[2, :] = 0.0
    A[:, 2] = 0.0
    b = np.array([1.0, -0.5, 0.0, 2.0, 0.3, -1.2])
    out = bccg.solve(A, b)
    assert np.isfinite(out.x).all()
    assert out.x[2] == 0.0


def test_empty_system():
    out = bccg.solve(np.zeros((0, 0)), np.zeros(0))
    assert out.x.shape == (0,)
    assert out.n_iterations == 0


def test_rejects_unknown_damping():
    with pytest.raises(ValueError, match="damping"):
        bccg.solve(np.eye(2), np.ones(2), damping="sometimes")
