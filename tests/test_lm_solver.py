"""Bounded Levenberg-Marquardt driver (WP-0601, Coelho 2018 + 2005).

The load-bearing test here is :func:`test_ru_is_one_on_a_linear_model`: the
λ schedule is fed ``r_u = ΔS_t/ΔS``, and the paper's printed ``ΔS_t = Δpᵀb``
has a sign that makes ``r_u < 0`` for every descent step.  The identity
``r_u ≡ 1`` on an exactly linear model is the only way to know the schedule is
receiving the quantity its constants (0.4, 1, 10) were tuned against.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.optimize import least_squares as scipy_lsq

from rietx.optimize import lm


# ----------------------------------------------------------------------
# problems
# ----------------------------------------------------------------------
def _linear_problem(n_data=40, n_par=4, seed=0):
    """r(θ) = Xθ − y — exactly quadratic S, so the GN step is exact."""
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n_data, n_par))
    y = rng.standard_normal(n_data)

    def residual(theta):
        return X @ theta - y

    def jacobian(theta):
        return X

    return residual, jacobian, np.linalg.lstsq(X, y, rcond=None)[0]


def _rosenbrock():
    """Classic non-quadratic pair; S = 100(x₂−x₁²)² + (1−x₁)², minimum (1, 1)."""
    def residual(t):
        return np.array([10.0 * (t[1] - t[0] ** 2), 1.0 - t[0]])

    def jacobian(t):
        return np.array([[-20.0 * t[0], 10.0], [-1.0, 0.0]])

    return residual, jacobian, np.array([1.0, 1.0])


def _exponential_problem(seed=3):
    """y = a·exp(b·x) + c — the shape a peak-height/width pair really has."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 3.0, 60)
    truth = np.array([2.5, -0.8, 0.4])
    y = truth[0] * np.exp(truth[1] * x) + truth[2]
    y = y + 0.01 * rng.standard_normal(len(x))

    def residual(t):
        return t[0] * np.exp(t[1] * x) + t[2] - y

    def jacobian(t):
        e = np.exp(t[1] * x)
        return np.column_stack([e, t[0] * x * e, np.ones_like(x)])

    return residual, jacobian, truth


_UNBOUNDED = (np.full(4, -np.inf), np.full(4, np.inf))


# ----------------------------------------------------------------------
# the sign calibration
# ----------------------------------------------------------------------
def test_ru_is_one_on_a_linear_model(monkeypatch):
    """ΔS_t = −Δθᵀb, verified against the exact-quadratic identity r_u ≡ 1.

    With r(θ+Δ) = r + JΔ: S(θ+Δ) = S − 2Δᵀb + ΔᵀAΔ, and at the exact
    Gauss-Newton step Δ = A⁻¹b that is S − Δᵀb.  So ΔS = −Δᵀb = ΔS_t exactly,
    and any other sign or factor shows up here immediately.  The paper's
    printed ``ΔS_t = Δpᵀb`` would give −1.
    """
    seen: list[float] = []
    real = lm._next_lambda

    def spy(lam, r_u, q):
        if r_u is not None:
            seen.append(r_u)
        return real(lam, r_u, q)

    monkeypatch.setattr(lm, "_next_lambda", spy)

    residual, jacobian, ref = _linear_problem()
    out = lm.minimize(residual, jacobian, np.zeros(4),
                      lo=_UNBOUNDED[0], hi=_UNBOUNDED[1])

    assert np.allclose(out.x, ref, atol=1e-9)
    assert seen, "no accepted step was scored"
    # the first step is taken at λ = 0, i.e. the exact GN step on an exactly
    # quadratic S — the identity has to hold to round-off there
    assert seen[0] == pytest.approx(1.0, abs=1e-9)


def test_lambda_schedule_branches():
    """Coelho (2018) equation (9), branch by branch."""
    # (i) failed step: 10·max(λ, 0.1)
    assert lm._next_lambda(0.0, None, 0.0) == pytest.approx(1.0)
    assert lm._next_lambda(5.0, None, 0.0) == pytest.approx(50.0)
    # (iii) good step at or under the quadratic prediction: m_u·λ/2
    assert lm._next_lambda(2.0, 1.0, 0.0) == pytest.approx(1.0)
    assert lm._next_lambda(2.0, 0.1, 0.0) == pytest.approx(0.4)   # m_u floored at 0.4
    # (iv) good step that overshoots: m_u(λ + ½) − ½ — damping although S fell
    assert lm._next_lambda(0.0, 2.0, 0.0) == pytest.approx(0.5)
    assert lm._next_lambda(1.0, 3.0, 0.0) == pytest.approx(4.0)
    # m_u capped at 10
    assert lm._next_lambda(0.0, 1e6, 0.0) == pytest.approx(4.5)
    # (ii) the rare Q_u > 5 branch: λ/10 even though the step was good
    assert lm._next_lambda(20.0, 3.0, 6.0) == pytest.approx(2.0)


def test_overshoot_damps_even_though_the_step_lowered_s():
    """The whole novelty of λ_new: λ rises after a *successful* step.

    Condition (iv) fires when r_u > 1, i.e. the linear prediction promised more
    than the step delivered — the step went too far.  λ_std would only ever cut
    λ here, so the shorter step it needs never happens.
    """
    assert lm._next_lambda(0.0, 5.0, 0.0) > 0.0


# ----------------------------------------------------------------------
# it actually minimises
# ----------------------------------------------------------------------
def test_linear_problem_converges_in_one_step():
    residual, jacobian, ref = _linear_problem()
    out = lm.minimize(residual, jacobian, np.zeros(4),
                      lo=_UNBOUNDED[0], hi=_UNBOUNDED[1])
    assert np.allclose(out.x, ref, atol=1e-10)
    assert out.status > 0


def test_a_start_at_the_minimum_is_converged():
    """Nothing downhill on the first outer iteration is convergence, as on any
    later one (WP-1937; it was ``status = -1``, read as "diverged")."""
    residual, jacobian, ref = _linear_problem()
    out = lm.minimize(residual, jacobian, ref.copy(),
                      lo=_UNBOUNDED[0], hi=_UNBOUNDED[1])
    assert out.status > 0
    assert out.termination in {"exhausted_fp64", "no_descent"}


def test_a_non_finite_start_is_refused_not_converged():
    """With first-iteration "diverged" gone, a nan cost would reject every
    trial and read as convergence; the start is refused instead, as TRF does."""
    def residual(t):
        return np.array([t[0] - 1.0, np.nan])

    def jacobian(t):
        return np.array([[1.0], [0.0]])

    with pytest.raises(ValueError, match="not finite"):
        lm.minimize(residual, jacobian, np.zeros(1),
                    lo=np.full(1, -np.inf), hi=np.full(1, np.inf))


def test_the_budget_is_in_residual_evaluations():
    """``max_nfev`` caps what scipy's ``max_nfev`` caps: residual evaluations,
    the initial one included."""
    residual, jacobian, _ = _rosenbrock()
    calls = []

    def counting(t):
        calls.append(t)
        return residual(t)

    out = lm.minimize(counting, jacobian, np.array([-1.2, 1.0]),
                      lo=np.full(2, -np.inf), hi=np.full(2, np.inf), max_nfev=7)
    assert out.nfev == len(calls) == 7
    assert out.status == 0
    assert out.termination == "max_nfev"


@pytest.mark.parametrize("start", [[-1.2, 1.0], [2.0, 2.0], [0.0, 0.0]])
def test_rosenbrock(start):
    residual, jacobian, ref = _rosenbrock()
    out = lm.minimize(residual, jacobian, np.array(start, dtype=float),
                      lo=np.full(2, -np.inf), hi=np.full(2, np.inf),
                      max_nfev=1600)
    assert np.allclose(out.x, ref, atol=1e-5)


def test_matches_scipy_trf_on_a_nonlinear_fit():
    """Same minimum as the reference driver, from the same start."""
    residual, jacobian, truth = _exponential_problem()
    x0 = np.array([1.0, -0.3, 0.0])
    lo, hi = np.full(3, -np.inf), np.full(3, np.inf)

    ours = lm.minimize(residual, jacobian, x0.copy(), lo=lo, hi=hi, max_nfev=800)
    theirs = scipy_lsq(residual, x0.copy(), jac=jacobian, method="trf",
                       ftol=1e-12, xtol=1e-12, gtol=1e-12)

    assert ours.cost == pytest.approx(theirs.cost, rel=1e-6)
    assert np.allclose(ours.x, theirs.x, rtol=1e-4, atol=1e-6)
    assert np.allclose(ours.x, truth, rtol=0.05)


def test_returns_jacobian_and_residual_at_the_returned_point():
    """``covariance_estimates`` reads both; a stale one mis-scales every esd."""
    residual, jacobian, _ = _exponential_problem()
    out = lm.minimize(residual, jacobian, np.array([1.0, -0.3, 0.0]),
                      lo=np.full(3, -np.inf), hi=np.full(3, np.inf))
    assert np.allclose(out.fun, residual(out.x))
    assert np.allclose(out.jac, jacobian(out.x))
    assert out.cost == pytest.approx(0.5 * float(out.fun @ out.fun))


# ----------------------------------------------------------------------
# constraints
# ----------------------------------------------------------------------
def test_bounds_are_never_violated():
    residual, jacobian, free = _linear_problem(seed=2)
    lo = np.full(4, -np.inf)
    hi = np.full(4, np.inf)
    # bind the two largest components well inside their free values
    for i in np.argsort(-np.abs(free))[:2]:
        if free[i] > 0:
            hi[i] = 0.5 * free[i]
        else:
            lo[i] = 0.5 * free[i]

    out = lm.minimize(residual, jacobian, np.zeros(4), lo=lo, hi=hi, max_nfev=800)
    assert np.all(out.x >= lo - 1e-12)
    assert np.all(out.x <= hi + 1e-12)
    assert out.n_bound_hits > 0
    # and the constrained optimum is worse than the free one, as it must be
    assert out.cost > 0.5 * float(residual(free) @ residual(free)) - 1e-12


def test_linear_inequality_keeps_every_iterate_feasible():
    """T·θ + c ≥ 0 on a functional of θ — what a box cannot express.

    Constrain θ₀ + θ₁ ≥ 0 on a problem whose unconstrained solution violates
    it, and check the returned point is feasible and sits on the boundary.
    """
    residual, jacobian, free = _linear_problem(seed=4)
    T = np.zeros((1, 4))
    T[0, 0] = T[0, 1] = 1.0
    offset = -(free[0] + free[1]) / 2.0    # the free solution violates it
    cone = lm.LinearInequality(T=T, c=np.array([offset]), label="test")
    assert cone.violated(free)[0]

    out = lm.minimize(residual, jacobian, np.zeros(4),
                      lo=np.full(4, -np.inf), hi=np.full(4, np.inf),
                      inequalities=[cone], max_nfev=1200)

    assert not cone.violated(out.x).any()
    assert out.n_truncated > 0
    # active constraint: the solution is pushed onto (just inside) the surface
    assert float((T @ out.x + cone.c)[0]) < 1e-3


def test_inactive_inequality_changes_nothing():
    residual, jacobian, _ = _exponential_problem()
    x0 = np.array([1.0, -0.3, 0.0])
    lo, hi = np.full(3, -np.inf), np.full(3, np.inf)
    free = lm.minimize(residual, jacobian, x0.copy(), lo=lo, hi=hi, max_nfev=800)

    T = np.zeros((1, 3))
    T[0, 0] = 1.0
    slack = lm.LinearInequality(T=T, c=np.array([1e6]), label="slack")
    constrained = lm.minimize(residual, jacobian, x0.copy(), lo=lo, hi=hi,
                              inequalities=[slack], max_nfev=800)

    assert constrained.n_truncated == 0
    assert np.allclose(constrained.x, free.x)


def test_empty_parameter_vector():
    def residual(theta):
        return np.array([1.0, 2.0])

    def jacobian(theta):
        return np.zeros((2, 0))

    out = lm.minimize(residual, jacobian, np.zeros(0),
                      lo=np.zeros(0), hi=np.zeros(0))
    assert out.x.shape == (0,)
    assert out.cost == pytest.approx(2.5)


def test_residual_must_be_fp64():
    """Invariant 2 at the driver boundary: a reduced-precision residual raises."""
    def residual(theta):
        return np.zeros(3, dtype=np.float32)

    def jacobian(theta):
        return np.zeros((3, 2))

    with pytest.raises(TypeError, match="fp64"):
        lm.minimize(residual, jacobian, np.zeros(2),
                    lo=np.full(2, -np.inf), hi=np.full(2, np.inf))


def test_callback_sees_every_accepted_point():
    seen = []
    residual, jacobian, _ = _exponential_problem()
    lm.minimize(residual, jacobian, np.array([1.0, -0.3, 0.0]),
                lo=np.full(3, -np.inf), hi=np.full(3, np.inf),
                callback=lambda x, cost: seen.append(cost))
    assert len(seen) >= 2
    assert seen == sorted(seen, reverse=True)   # accepted steps only ⇒ monotone


# ----------------------------------------------------------------------
# the bounded step (WP-1937): exact, and on its bound rather than near it
# ----------------------------------------------------------------------
def _kkt_violation(A, b, step, lo, hi):
    """Largest breach of the bounded quadratic's optimality conditions.

    The model is ½ΔᵀAΔ − bᵀΔ, so its gradient is g = AΔ − b: zero on a free
    variable, ≥ 0 on one held at its lower bound, ≤ 0 at its upper.
    """
    g = A @ step - b
    at_lo = np.isclose(step, lo, rtol=0.0, atol=1e-12)
    at_hi = np.isclose(step, hi, rtol=0.0, atol=1e-12)
    free = ~(at_lo | at_hi)
    return max(np.max(np.abs(g[free]), initial=0.0),
               np.max(-g[at_lo], initial=0.0),
               np.max(g[at_hi], initial=0.0))


@pytest.mark.parametrize("seed", range(5))
def test_step_is_the_exact_minimiser_of_the_bounded_model(seed):
    """The step satisfies the bounded quadratic's KKT conditions to round-off,
    where BCCG stopped once ‖AΔ − b‖² had fallen 10⁴-fold."""
    rng = np.random.default_rng(seed)
    J = rng.standard_normal((60, 6)) @ np.diag([1e3, 1.0, 1.0, 1e-2, 5.0, 1.0])
    A = J.T @ J
    b = rng.standard_normal(6) * np.sqrt(np.diag(A))
    x = np.zeros(6)
    lo = np.array([-np.inf, -0.1, 0.0, -np.inf, -1e-3, 0.0])
    hi = np.array([np.inf, 0.1, np.inf, 1e-3, np.inf, 0.0 + 1e-9])
    step, side = lm._solve_step(A, b, 0.0, x, lo, hi, n_rows=60)
    assert np.all(step >= lo - 1e-15) and np.all(step <= hi + 1e-15)
    scale = np.max(np.abs(b))
    assert _kkt_violation(A, b, step, lo, hi) < 1e-9 * scale
    assert np.any(side != 0), "the case was meant to bind at least one bound"


def test_a_rank_deficient_system_gets_a_finite_minimum_norm_step():
    """Two identical columns: A is singular at λ = 0, and the cut discards the
    null direction rather than stepping along it without limit."""
    rng = np.random.default_rng(7)
    J = rng.standard_normal((40, 3))
    J = np.column_stack([J, J[:, 0]])
    A, b = J.T @ J, J.T @ rng.standard_normal(40)
    inf = np.full(4, np.inf)
    step, _ = lm._solve_step(A, b, 0.0, np.zeros(4), -inf, inf, n_rows=40)
    assert np.all(np.isfinite(step))
    assert step[0] == pytest.approx(step[3], rel=1e-9)
    assert np.allclose(A @ step, b, atol=1e-9 * np.max(np.abs(b)))


def test_widths_pressed_on_zero_together_reach_the_bound_exactly():
    """Several non-negative terms whose free optimum is negative, coupled
    through near-collinear columns — WP-1929's QARR shape in miniature.  The
    driver lands each on 0.0 exactly, and the residual's descent direction
    points out of the box there."""
    rng = np.random.default_rng(11)
    x_axis = np.linspace(-3.0, 3.0, 200)
    basis = np.column_stack([np.exp(-(x_axis / w) ** 2) for w in (1.0, 1.05, 1.1, 1.15)])
    basis = np.column_stack([basis, np.ones_like(x_axis)])
    truth = np.array([0.0, 0.0, 0.0, 0.0, 1.0])
    y = basis @ truth - 0.05 * basis[:, 1] + 0.001 * rng.standard_normal(len(x_axis))
    # floors at awkward values, so that x + (lo − x) computed through the
    # step's scaling need not round back to lo
    floor = np.array([0.1, 1.0 / 3.0, 0.7, 2.0 / 7.0])

    def residual(t):
        return basis @ np.concatenate([t[:4] - floor, t[4:]]) - y

    def jacobian(t):
        return basis

    lo = np.concatenate([floor, [-np.inf]])
    hi = np.full(5, np.inf)
    out = lm.minimize(residual, jacobian, np.array([0.9, 0.9, 0.9, 0.9, 0.5]),
                      lo=lo, hi=hi, max_nfev=200)
    assert out.status > 0
    pinned = out.x[:4] == floor
    assert pinned.sum() >= 2
    grad = basis.T @ residual(out.x)       # ½∇S
    assert np.all(grad[:4][pinned] > 0.0)  # S would fall only below the bound
    # and nothing is left a rounding error above its floor
    assert np.all(pinned | (out.x[:4] - floor > 1e-9))
    # the active set is exactly the pinned floors
    assert out.active_mask.tolist() == [-1 if p else 0 for p in pinned] + [0]


def test_a_block_above_the_bvls_cut_takes_the_bccg_step(monkeypatch):
    """A Pawley-sized system is solved by BCCG, inside the same box; BVLS's
    cost grows as n³ per active-set change (``BVLS_MAX_COLUMNS``)."""
    from rietx.optimize import bccg

    n = lm.BVLS_MAX_COLUMNS + 1
    rng = np.random.default_rng(5)
    J = rng.standard_normal((3 * n, n))
    A, b = J.T @ J, J.T @ rng.standard_normal(3 * n)
    lo, hi = np.zeros(n), np.full(n, np.inf)
    calls = []
    real = bccg.solve
    monkeypatch.setattr(bccg, "solve", lambda *a, **k: calls.append(1) or real(*a, **k))
    step, side = lm._solve_step(A, b, 0.0, np.zeros(n), lo, hi, n_rows=3 * n)
    assert calls and not side.any()
    assert np.all(step >= 0.0)
    calls.clear()
    small, _ = lm._solve_step(A[:-1, :-1], b[:-1], 0.0, np.zeros(n - 1),
                              lo[:-1], hi[:-1], n_rows=3 * n)
    assert not calls and np.all(small >= 0.0)
