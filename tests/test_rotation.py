"""Rotation mathematics (WP-1801): `crystallography/rotation.py`.

Every formula is Solà, Deray & Atchuthan (2018, arXiv:1812.01537); the
oracles here are independent of the formulas they check: a 60-digit Decimal
series for the small-angle coefficients, central finite differences and jax
forward-mode autodiff for ∂R/∂δω, and the group axioms (orthonormality,
associativity, R(qa·qb) = R(qa)·R(qb)) for the conventions.
"""

from __future__ import annotations

import math
from decimal import Decimal, localcontext

import numpy as np
import pytest

from rietx.crystallography import rotation as rt

EPS = np.finfo(np.float64).eps
RNG_SEED = 20260930


def _random_vectors(n, max_angle, seed=RNG_SEED):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, 3))
    v /= np.linalg.norm(v, axis=1)[:, None]
    return v * rng.uniform(0.0, max_angle, size=(n, 1))


def _random_quaternions(n, seed=RNG_SEED):
    rng = np.random.default_rng(seed)
    q = rng.normal(size=(n, 4))
    return q / np.linalg.norm(q, axis=1)[:, None]


def _decimal_coefficients(theta_sq: float):
    """(A, B, C) at θ² by their Maclaurin series in 60-digit Decimal arithmetic."""
    with localcontext() as ctx:
        ctx.prec = 60
        t2 = Decimal(theta_sq)
        powers = [Decimal(1)]
        for _ in range(39):
            powers.append(powers[-1] * t2)
        return tuple(
            float(sum((-1) ** k * powers[k] / Decimal(math.factorial(2 * k + start))
                      for k in range(40)))
            for start in (1, 2, 3))


def _central_fd(omega, r0, h=1e-5):
    out = []
    for k in range(3):
        d = np.zeros(3)
        d[k] = h
        out.append((rt.matrix_from_vector(omega + d) @ r0
                    - rt.matrix_from_vector(omega - d) @ r0) / (2 * h))
    return np.stack(out)


# --- the small-angle branch -------------------------------------------------


def test_coefficients_match_a_60_digit_series_on_both_sides_of_the_threshold():
    """A, B, C against an exact evaluation from 1e-9 rad to 1 rad.

    Bars from the module docstring: A and B lose nothing to cancellation on
    either branch; C's closed form loses ~6ε/θ², about 1e-14 relative just
    above the threshold, and that is where its bar sits.
    """
    t = rt.SERIES_THRESHOLD
    thetas = np.concatenate([np.geomspace(1e-9, 1.0, 600),
                             [t * (1 - 1e-15), t, t * (1 + 1e-15), 0.0]])
    worst = np.zeros(3)
    for theta in thetas:
        theta_sq = float(theta) ** 2
        got = np.array([float(c) for c in rt._coefficients(np.float64(theta_sq))])
        want = np.array(_decimal_coefficients(theta_sq))
        worst = np.maximum(worst, np.abs(got - want) / want)
    assert worst[0] < 1e-15 and worst[1] < 1e-15, worst
    assert worst[2] < 1.5e-14, worst


# --- ∂R/∂δω -----------------------------------------------------------------


def test_jacobian_matches_central_differences_on_100_random_vectors():
    """∂(Exp(ω)·R₀)/∂ω_k against central FD, < 1e-9, R₀ random too."""
    omegas = _random_vectors(100, np.pi * 0.95)
    r0s = [rt.matrix_from_vector(w) for w in _random_vectors(100, np.pi, seed=1)]
    worst = max(float(np.max(np.abs(rt.d_matrix_d_vector(w, r0) - _central_fd(w, r0))))
                for w, r0 in zip(omegas, r0s))
    assert worst < 1e-9, worst


@pytest.mark.parametrize("theta", [0.0, 1e-12, 1e-8, 1e-6, rt.SERIES_THRESHOLD * (1 - 1e-12),
                                   rt.SERIES_THRESHOLD * (1 + 1e-12)])
def test_jacobian_near_zero_and_across_the_series_threshold(theta):
    """At and around ω = 0, where every stage's anchored increment starts."""
    axis = np.array([0.36, -0.48, 0.8])
    r0 = rt.matrix_from_vector([0.4, -1.1, 2.0])
    w = theta * axis
    jac = rt.d_matrix_d_vector(w, r0)
    assert np.max(np.abs(jac - _central_fd(w, r0))) < 1e-9
    if theta == 0.0:   # [e_k]×·R₀ exactly
        want = np.stack([rt.skew(np.eye(3)[k]) @ r0 for k in range(3)])
        assert np.array_equal(jac, want)


@pytest.mark.parametrize("gap", [1e-3, 1e-6])
def test_jacobian_near_pi(gap):
    """Exp is smooth through |ω| = π; only Log is not, so ∂R/∂δω must hold there."""
    axis = np.array([2.0, -1.0, 2.0]) / 3.0
    w = (np.pi - gap) * axis
    r0 = rt.matrix_from_vector([0.2, 0.3, -0.1])
    assert np.max(np.abs(rt.d_matrix_d_vector(w, r0) - _central_fd(w, r0))) < 1e-9


def test_jacobian_matches_jax_autodiff_and_stays_finite_at_zero():
    """jax autodiff of `matrix_from_vector`, forward and reverse: an oracle with no step.

    It also checks the `where` construction.  A closed form evaluated at θ = 0
    puts 0/0 into the unselected branch; forward mode never reads that branch's
    tangent, but reverse mode multiplies its cotangent 0 by the NaN, so
    ``jacrev`` is the half of this test that can see it.
    """
    pytest.importorskip("jax")
    import jax

    from rietx.backend import traced
    from rietx.backend.api import resolve_backend

    xp = resolve_backend("jax")
    points = [np.zeros(3), np.array([1e-9, 0.0, 0.0]),
              np.array([0.1, -0.2, 0.05]), np.array([0.3, 1.2, -2.0]),
              np.array([0.0, 0.0, np.pi - 1e-6])]
    with traced.active(xp):
        for w in points:
            analytic = np.asarray(rt.d_matrix_d_vector(xp.asarray(w)))
            for mode in (jax.jacfwd, jax.jacrev):
                auto = np.moveaxis(np.asarray(mode(rt.matrix_from_vector)(xp.asarray(w))),
                                   2, 0)
                assert np.isfinite(auto).all(), (mode.__name__, w)
                assert np.max(np.abs(auto - analytic)) < 1e-14, (mode.__name__, w)


def test_record_side_maps_trace_on_jax_and_log_of_exp_has_the_identity_jacobian():
    """The quaternion maps and Log in backend ops (WP-1801's task line), traced.

    Each agrees with its numpy evaluation, and ∂Log(Exp(ω))/∂ω = I for |ω| < π,
    in both autodiff modes, at ω = 0, at |ω| = 1e-8 (the Log series branch)
    and near π: a map with a 0/0 in an unselected branch returns NaN there.
    """
    pytest.importorskip("jax")
    import jax

    from rietx.backend import traced
    from rietx.backend.api import resolve_backend

    xp = resolve_backend("jax")
    points = [np.zeros(3), np.array([1e-8, 0.0, 0.0]), np.array([0.3, 1.2, -2.0]),
              (np.pi - 1e-3) * np.array([2.0, -1.0, 2.0]) / 3.0]
    u = np.array([-2.0, 1.0, 2.0]) / 3.0
    half_turn = 2.0 * np.outer(u, u) - np.eye(3)
    want = {"log_exp": [rt.vector_from_matrix(rt.matrix_from_vector(w)) for w in points],
            "q": [rt.quaternion_from_vector(w) for w in points],
            "tie": rt.vector_from_matrix(half_turn)}
    with traced.active(xp):
        for w, lw, qw in zip(points, want["log_exp"], want["q"]):
            got = np.asarray(rt.vector_from_matrix(rt.matrix_from_vector(xp.asarray(w))))
            assert np.max(np.abs(got - lw)) < 1e-15, w
            assert np.max(np.abs(np.asarray(rt.quaternion_from_vector(xp.asarray(w))) - qw)) \
                < 1e-15, w
            for mode in (jax.jacfwd, jax.jacrev):
                jac = np.asarray(mode(lambda v: rt.vector_from_matrix(
                    rt.matrix_from_vector(v)))(xp.asarray(w)))
                assert np.isfinite(jac).all(), (mode.__name__, w)
                assert np.max(np.abs(jac - np.eye(3))) < 1e-9, (mode.__name__, w)
                dq = np.asarray(mode(rt.quaternion_from_vector)(xp.asarray(w)))
                assert np.isfinite(dq).all(), (mode.__name__, w)
        assert np.array_equal(np.asarray(rt.vector_from_matrix(xp.asarray(half_turn))),
                              want["tie"])
        # at a half-turn ‖v‖ = 1, where arcsin' is infinite: only the masked
        # argument keeps its NaN out of the selected arccos branch
        assert np.isfinite(np.asarray(jax.jacrev(rt.vector_from_matrix)(
            xp.asarray(half_turn)))).all()


# --- round trips --------------------------------------------------------------


def test_vector_matrix_vector_round_trip_within_8_ulp():
    """|ω| < π: Log(Exp(ω)) = ω to 8·ε absolute (measured 3·ε on these 2000)."""
    omegas = np.concatenate([_random_vectors(2000, np.pi * 0.999),
                             [np.zeros(3), [1e-300, 0.0, 0.0], [0.0, 1e-9, -1e-9],
                              [2e-3, 0.0, 0.0], [0.0, 5e-4, -5e-4],
                              [0.0, 0.0, np.pi - 1e-9]]])
    # np.max, not max(): Python's max() drops a NaN that is not the first item
    worst = float(np.max([np.abs(rt.vector_from_matrix(rt.matrix_from_vector(w)) - w)
                          for w in omegas]))
    assert worst <= 8 * EPS, worst / EPS


def test_log_at_exactly_pi_picks_the_tie_break_sign():
    """±πu are one rotation; Log returns the one whose first nonzero component is > 0."""
    for u in (np.array([1.0, 0.0, 0.0]), np.array([0.0, -1.0, 0.0]),
              np.array([-2.0, 1.0, 2.0]) / 3.0):
        r = 2.0 * np.outer(u, u) - np.eye(3)       # Exp(πu), exactly symmetric
        w = rt.vector_from_matrix(r)
        assert abs(np.linalg.norm(w) - np.pi) < 4 * EPS
        assert w[np.flatnonzero(np.abs(w) > 1e-12)[0]] > 0
        assert min(np.max(np.abs(w - np.pi * u)), np.max(np.abs(w + np.pi * u))) < 8 * EPS


def test_vector_beyond_pi_returns_the_equivalent_vector_inside_the_ball():
    u = np.array([0.0, 0.6, 0.8])
    w = rt.vector_from_matrix(rt.matrix_from_vector(1.5 * np.pi * u))
    assert np.max(np.abs(w - (-0.5 * np.pi * u))) < 8 * EPS


def test_quaternion_matrix_quaternion_round_trip_within_4_ulp():
    """Canonical q → R(q) → q to 4·ε absolute (measured 1.5·ε), ties included."""
    qs = [rt.canonical_quaternion(q) for q in _random_quaternions(2000)]
    qs += [np.array([1.0, 0.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0, 0.0]),
           np.array([0.0, 0.0, 0.6, 0.8]), rt.canonical_quaternion([1e-12, 0.6, -0.8, 0.0])]
    worst = max(float(np.max(np.abs(rt.quaternion_from_matrix(rt.matrix_from_quaternion(q))
                                    - q / np.linalg.norm(q)))) for q in qs)
    assert worst <= 4 * EPS, worst / EPS


def test_vector_quaternion_vector_round_trip_within_8_ulp():
    """|ω| < π: Log_q(Exp_q(ω)) = ω on its own, at the vector round trip's
    8·ε (measured 4·ε on these 2000; #578 review, follow-up 2)."""
    omegas = np.concatenate([_random_vectors(2000, np.pi * 0.999),
                             [np.zeros(3), [1e-300, 0.0, 0.0], [0.0, 1e-9, -1e-9],
                              [2e-3, 0.0, 0.0], [0.0, 5e-4, -5e-4],
                              [0.0, 0.0, np.pi - 1e-9]]])
    # np.max, not max(): a NaN (the 0/0 the series branch exists for) must fail
    worst = float(np.max([np.abs(rt.vector_from_quaternion(rt.quaternion_from_vector(w)) - w)
                          for w in omegas]))
    assert worst <= 8 * EPS, worst / EPS


@pytest.mark.parametrize("drift", [9e-10, -9e-10])
def test_a_quaternion_the_unit_check_passes_gives_a_matrix_the_matrix_check_passes(drift):
    """RᵀR scales as ‖q‖⁴, so an unnormalised R(q) at ‖q‖ − 1 = 9e-10 was refused
    at 3.6e-9 by the same tolerance on the way back (#578 review, follow-up 1)."""
    for q in (np.array([1.0, 0.0, 0.0, 0.0]), np.array([0.5, 0.5, -0.5, 0.5])):
        r = rt.matrix_from_quaternion((1.0 + drift) * q)
        assert np.max(np.abs(r.T @ r - np.eye(3))) < 4 * EPS
        assert np.max(np.abs(rt.quaternion_from_matrix(r) - q)) < 4 * EPS
    with pytest.raises(ValueError, match="unit quaternion"):
        rt.matrix_from_quaternion((1.0 + 2 * rt.UNIT_TOLERANCE) * q)


def test_quaternion_from_vector_agrees_with_the_matrix_route():
    """Eq. (132) and eq. (134) are one rotation: R(Exp_q(ω)) = Exp_R(ω)."""
    for w in _random_vectors(200, 3 * np.pi):
        assert np.max(np.abs(rt.matrix_from_quaternion(rt.quaternion_from_vector(w))
                             - rt.matrix_from_vector(w))) < 1e-14


# --- canonical form -----------------------------------------------------------


def test_canonical_form_is_idempotent_to_the_bit():
    qs = list(_random_quaternions(500)) + [
        np.array([-0.0, -0.6, 0.8, 0.0]), np.array([0.0, 0.0, -1.0, 0.0]),
        np.array([-1.0, 0.0, 0.0, 0.0]), np.array([0.0, -0.0, 0.0, -1.0])]
    for q in qs:
        once = rt.canonical_quaternion(q)
        assert once.tobytes() == rt.canonical_quaternion(once).tobytes(), q
        assert once.tobytes() == rt.canonical_quaternion(-once).tobytes(), q


def test_canonical_form_has_w_nonnegative_and_the_tie_broken_positive():
    for q in _random_quaternions(500):
        assert rt.canonical_quaternion(q)[0] > 0.0
    assert rt.canonical_quaternion([0.0, 0.0, -0.6, 0.8]).tolist() == [0.0, 0.0, 0.6, -0.8]
    assert rt.canonical_quaternion([-0.0, -1.0, 0.0, 0.0]).tobytes() == \
        np.array([0.0, 1.0, 0.0, 0.0]).tobytes()
    with pytest.raises(ValueError, match="zero quaternion"):
        rt.canonical_quaternion([0.0, 0.0, 0.0, 0.0])


# --- the group ------------------------------------------------------------------


def test_matrices_are_orthonormal_with_determinant_one():
    omegas = np.concatenate([_random_vectors(500, 10 * np.pi),
                             [np.zeros(3), [1e-200, 0.0, 0.0], [0.0, np.pi, 0.0]]])
    for w in omegas:
        r = rt.matrix_from_vector(w)
        assert np.max(np.abs(r.T @ r - np.eye(3))) < 1e-14, w
        assert abs(np.linalg.det(r) - 1.0) < 1e-14, w


def test_composition_is_associative_and_matches_the_matrix_product():
    """R(qa·qb) = R(qa)·R(qb) pins the Hamilton convention against eq. (138)."""
    qa, qb, qc = (_random_quaternions(300, seed=s) for s in (1, 2, 3))
    for a, b, c in zip(qa, qb, qc):
        left = rt.quaternion_product(rt.quaternion_product(a, b), c)
        right = rt.quaternion_product(a, rt.quaternion_product(b, c))
        assert np.max(np.abs(left - right)) < 1e-15
        assert np.max(np.abs(rt.matrix_from_quaternion(rt.quaternion_product(a, b))
                             - rt.matrix_from_quaternion(a) @ rt.matrix_from_quaternion(b))) < 1e-14
    for wa, wb, wc in zip(*(_random_vectors(100, np.pi, seed=s) for s in (4, 5, 6))):
        ab_c = rt.compose_vectors(rt.compose_vectors(wa, wb), wc)
        a_bc = rt.compose_vectors(wa, rt.compose_vectors(wb, wc))
        assert np.max(np.abs(rt.matrix_from_vector(ab_c) - rt.matrix_from_vector(a_bc))) < 1e-14
        assert np.max(np.abs(rt.matrix_from_vector(rt.compose_vectors(wa, wb))
                             - rt.matrix_from_vector(wa) @ rt.matrix_from_vector(wb))) < 1e-14


def test_exp_of_log_is_the_matrix():
    """Exp(Log(R)) = R, including the identity and half-turns."""
    rs = [rt.matrix_from_quaternion(rt.canonical_quaternion(q))
          for q in _random_quaternions(1000, seed=7)]
    u = np.array([2.0, -1.0, 2.0]) / 3.0
    rs += [np.eye(3), 2.0 * np.outer(u, u) - np.eye(3),
           rt.matrix_from_vector((np.pi - 1e-9) * u), rt.matrix_from_vector(1e-10 * u)]
    for r in rs:
        assert np.max(np.abs(rt.matrix_from_vector(rt.vector_from_matrix(r)) - r)) < 1e-14


def test_wrong_objects_are_refused():
    with pytest.raises(ValueError, match="unit quaternion"):
        rt.matrix_from_quaternion([1.0, 0.1, 0.0, 0.0])
    with pytest.raises(ValueError, match="improper"):
        rt.quaternion_from_matrix(-np.eye(3))
    with pytest.raises(ValueError, match="orthonormal"):
        rt.quaternion_from_matrix(np.diag([1.0, 1.0, 1.1]))


def test_left_jacobian_is_full_rank_through_pi_and_singular_only_at_two_pi():
    """The module docstring's claim: transverse singular values |sin(θ/2)|/(θ/2)."""
    u = np.array([0.36, -0.48, 0.8])
    for theta in (0.0, 1e-6, 0.7, np.pi, 5.0, 2 * np.pi):
        sv = np.linalg.svd(rt.left_jacobian(theta * u), compute_uv=False)
        transverse = 1.0 if theta == 0.0 else abs(np.sin(theta / 2)) / (theta / 2)
        assert np.allclose(np.sort(sv), np.sort([1.0, transverse, transverse]),
                           rtol=0, atol=1e-14), theta
