"""WP-1050 `Refinement.suggest()`: one-parameter gains, gates, and the
misfit-injection cases that keep it from handing back a confident singleton."""

import numpy as np
import pytest
from pydantic import ValidationError

from pxrdref.optimize.statistics import block_projection_r2, one_parameter_gains
from pxrdref.schemas.suggest import (
    SUGGEST_MIN_GAIN,
    CandidateGroup,
    ParameterCandidate,
    SuggestionResult,
)


# ----------------------------------------------------------------------
# one_parameter_gains — brute-force property tests against explicit lstsq
# ----------------------------------------------------------------------
def _ssr(design, r):
    """min ‖r − A β‖² by explicit lstsq — the brute-force reference."""
    if design.shape[1] == 0:
        return float(r @ r)
    beta, *_ = np.linalg.lstsq(design, r, rcond=None)
    resid = r - design @ beta
    return float(resid @ resid)


@pytest.mark.parametrize("seed", range(8))
def test_gain_equals_lstsq_ssr_drop(seed):
    """Δχ²_j == SSR(F) − SSR([F | j]) on random matrices, every candidate."""
    rng = np.random.default_rng(seed)
    m, n_free, n_cand = 120, 5, 7
    jac = rng.standard_normal((m, n_free + n_cand))
    r = rng.standard_normal(m)
    block = list(range(n_free))
    targets = [(n_free + i, f"cand.{i}") for i in range(n_cand)]
    gains = one_parameter_gains(jac, r, block, targets)
    F = jac[:, block]
    for k, path in targets:
        expected = _ssr(F, r) - _ssr(np.column_stack([F, jac[:, k]]), r)
        assert gains[path] == pytest.approx(expected, rel=1e-9, abs=1e-12)


@pytest.mark.parametrize("seed", range(4))
def test_joint_gain_equals_lstsq_ssr_drop(seed):
    """A list-of-columns target scores the SSR drop of freeing the group."""
    rng = np.random.default_rng(100 + seed)
    m, n_free = 90, 4
    jac = rng.standard_normal((m, n_free + 3))
    r = rng.standard_normal(m)
    block = list(range(n_free))
    group = [n_free, n_free + 1, n_free + 2]
    gains = one_parameter_gains(jac, r, block, [(group, "grp")])
    F = jac[:, block]
    expected = _ssr(F, r) - _ssr(np.column_stack([F, jac[:, group]]), r)
    assert gains["grp"] == pytest.approx(expected, rel=1e-9, abs=1e-12)


def test_gain_scale_invariant():
    """Rescaling a candidate column (any dp/du) leaves its gain unchanged."""
    rng = np.random.default_rng(7)
    jac = rng.standard_normal((80, 6))
    r = rng.standard_normal(80)
    block, target = [0, 1, 2], [(5, "p")]
    base = one_parameter_gains(jac, r, block, target)["p"]
    scaled = jac.copy()
    scaled[:, 5] *= 3.7e-6
    assert one_parameter_gains(scaled, r, block, target)["p"] == pytest.approx(
        base, rel=1e-9)


def test_gain_empty_block_is_raw_score():
    """No free columns: nothing projected out, gain = (jᵀr)²/(jᵀj)."""
    rng = np.random.default_rng(11)
    jac = rng.standard_normal((50, 2))
    r = rng.standard_normal(50)
    gains = one_parameter_gains(jac, r, [], [(0, "a"), (1, "b")])
    for k, key in [(0, "a"), (1, "b")]:
        j = jac[:, k]
        assert gains[key] == pytest.approx(float(j @ r) ** 2 / float(j @ j),
                                           rel=1e-12)


def test_gain_zero_norm_column_skipped_absorbed_scores_zero():
    """Raw-zero column: absent (no leverage).  In-span column: exactly 0.0."""
    rng = np.random.default_rng(13)
    jac = rng.standard_normal((60, 4))
    jac[:, 2] = 0.0                                   # dead column
    jac[:, 3] = 2.0 * jac[:, 0] - jac[:, 1]           # inside span(F)
    r = rng.standard_normal(60)
    gains = one_parameter_gains(jac, r, [0, 1], [(2, "dead"), (3, "absorbed")])
    assert "dead" not in gains
    assert gains["absorbed"] == pytest.approx(0.0, abs=1e-16)


def test_joint_gain_rank_deficient_group_never_overcounts():
    """A duplicated column adds no span, so the group gain equals the single's."""
    rng = np.random.default_rng(17)
    jac = rng.standard_normal((70, 5))
    jac = np.column_stack([jac, jac[:, 4]])           # column 5 == column 4
    r = rng.standard_normal(70)
    block = [0, 1, 2]
    single = one_parameter_gains(jac, r, block, [(4, "j")])["j"]
    joint = one_parameter_gains(jac, r, block, [([4, 5], "grp")])["grp"]
    assert joint == pytest.approx(single, rel=1e-9)


def test_gain_at_linear_minimum_is_zero():
    """r ⟂ span(F ∪ j) — a converged linear fit — scores ≈ 0 everywhere."""
    rng = np.random.default_rng(19)
    jac = rng.standard_normal((100, 4))
    r = rng.standard_normal(100)
    q, _ = np.linalg.qr(jac)
    r = r - q @ (q.T @ r)                             # orthogonal to all columns
    gains = one_parameter_gains(jac, r, [0, 1], [(2, "a"), (3, "b")])
    assert gains["a"] == pytest.approx(0.0, abs=1e-20)
    assert gains["b"] == pytest.approx(0.0, abs=1e-20)


# ----------------------------------------------------------------------
# schemas — round-trip, forbid, and the best_or_none gate
# ----------------------------------------------------------------------
def _candidate(path="instrument.zero_shift", gain=120.0, **kw):
    return ParameterCandidate(path=path, gain=gain, gradient=-3.4e2, **kw)


def _result(groups, **kw):
    kw.setdefault("chi2_red", 2.5)
    kw.setdefault("noise_floor", SUGGEST_MIN_GAIN * 2.5)
    kw.setdefault("summary", "test")
    return SuggestionResult(groups=groups, **kw)


def test_suggestion_result_json_round_trip():
    res = _result(
        [CandidateGroup(members=[_candidate(action_kind="refine_zero_shift")],
                        gain=120.0, resolved=True),
         CandidateGroup(members=[_candidate("instrument.profile.w", 40.0),
                                 _candidate("phases.0.gauss_size", 38.0,
                                            seeded=True, seed_value=1e-3)],
                        gain=41.0, resolved=False)],
        non_separable=[_candidate("phases.0.scale", 5.0, absorption=0.99)],
        skipped=["phases.0.extinction"], n_evaluated=5)
    back = SuggestionResult.model_validate_json(res.model_dump_json())
    assert back == res
    assert back.groups[1].members[1].seed_value == 1e-3


def test_suggestion_schemas_forbid_extras():
    for cls, kwargs in [
        (ParameterCandidate, dict(path="p", gain=1.0, gradient=0.0)),
        (CandidateGroup, dict(members=[_candidate()], gain=1.0, resolved=True)),
        (SuggestionResult, dict(chi2_red=1.0, noise_floor=9.0, summary="s")),
    ]:
        with pytest.raises(ValidationError):
            cls(**kwargs, unexpected=1)


def test_candidate_group_needs_a_member():
    with pytest.raises(ValidationError):
        CandidateGroup(members=[], gain=0.0, resolved=True)


def test_best_or_none_gates():
    """Empty list and unresolved-top both refuse; a resolved top answers."""
    assert _result([]).best_or_none() is None
    tie = CandidateGroup(members=[_candidate(), _candidate("instrument.profile.w")],
                         gain=50.0, resolved=False)
    assert _result([tie]).best_or_none() is None
    win = CandidateGroup(members=[_candidate()], gain=120.0, resolved=True)
    best = _result([win, tie]).best_or_none()
    assert best is not None and best.path == "instrument.zero_shift"


def test_pairwise_r2_via_nuisance_matches_projected_correlation():
    """The grouping gate's statistic: block_projection_r2 with the free set as
    nuisance is exactly ρ² between the two projected columns."""
    rng = np.random.default_rng(23)
    jac = rng.standard_normal((80, 5))
    free = [0, 1, 2]
    r2 = block_projection_r2(jac, [3], [(4, "b")], nuisance=free)["b"]
    q, _ = np.linalg.qr(jac[:, free])
    a = jac[:, 3] - q @ (q.T @ jac[:, 3])
    b = jac[:, 4] - q @ (q.T @ jac[:, 4])
    rho2 = float(a @ b) ** 2 / (float(a @ a) * float(b @ b))
    assert r2 == pytest.approx(rho2, rel=1e-12)
