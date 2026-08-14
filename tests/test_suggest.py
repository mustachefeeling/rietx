"""WP-1050 `Refinement.suggest()`: one-parameter gains, gates, and the
misfit-injection cases that keep it from handing back a confident singleton."""

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.optimize.statistics import block_projection_r2, one_parameter_gains
from rietx.schemas.suggest import (
    SUGGEST_MIN_GAIN,
    CandidateGroup,
    ParameterCandidate,
    SuggestionResult,
)
from rietx.strategy.suggest import SUGGEST_SEED_SOFTPLUS
from tests.test_fitreport_layers import _report_for, _result_for, _truth


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
# build_suggestion — synthetic matrices with planted structure
# ----------------------------------------------------------------------
def _build(jac, r, free, cands, chi2_red=1.0, **kw):
    from rietx.strategy.suggest import Candidate, build_suggestion
    return build_suggestion(
        jac, r, free,
        [Candidate(path=p, index=i, dp_du=d, **extra)
         for p, i, d, extra in cands],
        chi2_red=chi2_red, **kw)


def _planted(seed=31, m=200, n_free=3, n_cand=4, signal=None):
    """Random free block + candidates, residual carrying `signal` of cand 0."""
    rng = np.random.default_rng(seed)
    jac = rng.standard_normal((m, n_free + n_cand))
    r = rng.standard_normal(m)
    if signal:
        r += signal * jac[:, n_free] / np.linalg.norm(jac[:, n_free])
    return jac, r


def test_build_planted_signal_wins_resolved():
    """The candidate whose direction the residual contains ranks first."""
    jac, r = _planted(signal=30.0)
    res = _build(jac, r, [0, 1, 2],
                 [(f"c{i}", 3 + i, 1.0, {}) for i in range(4)])
    best = res.best_or_none()
    assert best is not None and best.path == "c0"
    assert res.groups[0].resolved and res.groups[0].gain > res.noise_floor
    assert res.n_evaluated == 4 and not res.skipped


def test_build_collinear_pair_is_one_unresolved_group():
    """Two candidates sharing a direction come back as a tie, not a winner."""
    rng = np.random.default_rng(37)
    m = 200
    jac = rng.standard_normal((m, 5))
    jac[:, 4] = jac[:, 3] + 1e-4 * rng.standard_normal(m)
    r = rng.standard_normal(m) + 30.0 * jac[:, 3] / np.linalg.norm(jac[:, 3])
    res = _build(jac, r, [0, 1, 2],
                 [("instrument.profile.w", 3, 1.0, {}),
                  ("phases.0.gauss_size", 4, 1.0, {})])
    assert res.best_or_none() is None
    assert len(res.groups) == 1 and not res.groups[0].resolved
    assert {pc.path for pc in res.groups[0].members} == {
        "instrument.profile.w", "phases.0.gauss_size"}
    # the joint gain is what the data measures: ≈ either single gain, never ≈ 2×
    singles = [pc.gain for pc in res.groups[0].members]
    assert res.groups[0].gain == pytest.approx(max(singles), rel=0.05)


def test_build_absorbed_candidate_never_wins():
    """A candidate the free block can imitate is non-separable, whatever its
    apparent gain — the 1/(1−R²) blow-up must not buy it the top slot."""
    rng = np.random.default_rng(41)
    m = 200
    jac = rng.standard_normal((m, 5))
    jac[:, 3] = jac[:, 0] + 0.05 * rng.standard_normal(m)   # ≈ in span(F)
    r = rng.standard_normal(m) + 5.0 * jac[:, 0] / np.linalg.norm(jac[:, 0])
    res = _build(jac, r, [0, 1, 2],
                 [("absorbed", 3, 1.0, {}), ("clean", 4, 1.0, {})])
    assert [pc.path for pc in res.non_separable] == ["absorbed"]
    assert res.non_separable[0].absorption > 0.95
    assert all(pc.path != "absorbed"
               for g in res.groups for pc in g.members)


def test_build_converged_suggests_nothing():
    """r ⟂ every column: groups empty, best None, summary says converged."""
    rng = np.random.default_rng(43)
    jac = rng.standard_normal((150, 5))
    q, _ = np.linalg.qr(jac)
    r = rng.standard_normal(150)
    r -= q @ (q.T @ r)
    res = _build(jac, r, [0, 1], [(f"c{i}", 2 + i, 1.0, {}) for i in range(3)])
    assert res.groups == [] and res.best_or_none() is None
    assert "converged" in res.summary


def test_build_zero_column_skipped_seed_reported():
    jac, r = _planted(signal=30.0)
    jac[:, 4] = 0.0
    r += 25.0 * jac[:, 5] / np.linalg.norm(jac[:, 5])   # seeded one has signal too
    res = _build(jac, r, [0, 1, 2],
                 [("c0", 3, 1.0, {}),
                  ("dead.path", 4, 1.0, {}),
                  ("seeded.path", 5, 0.02,
                   {"seeded": True, "seed_value": 1e-3})])
    assert res.skipped == ["dead.path"]
    assert res.n_evaluated == 2
    by_path = {pc.path: pc for g in res.groups for pc in g.members}
    assert by_path["seeded.path"].seeded
    assert by_path["seeded.path"].seed_value == 1e-3


def test_build_gradient_physical_units():
    """gradient = 2(Jᵀr)_j / dp_du, sign preserved."""
    jac, r = _planted(signal=30.0)
    dp_du = 0.25
    res = _build(jac, r, [0, 1, 2], [("c0", 3, dp_du, {})])
    expected = 2.0 * float(jac[:, 3] @ r) / dp_du
    pc = res.groups[0].members[0]
    assert pc.gradient == pytest.approx(expected, rel=1e-12)


def test_build_action_kind_cross_reference():
    """Two-way fnmatch against Layer-2 action paths, first match wins."""
    class FakeAction:
        def __init__(self, kind, paths):
            self.kind, self.parameter_paths = kind, paths

    jac, r = _planted(signal=30.0)
    res = _build(jac, r, [0, 1, 2],
                 [("instrument.zero_shift", 3, 1.0, {}),
                  ("phases.0.cell.a", 4, 1.0, {})],
                 actions=[FakeAction("refine_zero_shift",
                                     ["instrument.zero_shift"]),
                          FakeAction("refine_cell", ["phases.*.cell.*"])])
    by_path = {pc.path: pc for g in res.groups for pc in g.members}
    assert by_path["instrument.zero_shift"].action_kind == "refine_zero_shift"
    if "phases.0.cell.a" in by_path:          # only if it cleared the floor
        assert by_path["phases.0.cell.a"].action_kind == "refine_cell"


def test_build_top_n_truncates_groups():
    rng = np.random.default_rng(47)
    m = 300
    jac = rng.standard_normal((m, 8))
    r = rng.standard_normal(m)
    for k in range(2, 8):                     # every candidate carries signal
        r += 20.0 * jac[:, k] / np.linalg.norm(jac[:, k])
    res = _build(jac, r, [0, 1], [(f"c{i}", 2 + i, 1.0, {}) for i in range(6)],
                 top_n=2)
    assert len(res.groups) == 2
    assert res.n_evaluated == 6


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


# ----------------------------------------------------------------------
# misfit injection — the layers suite's truth fixture, one planted cause
# each.  The module fixture is shared, so the whole file pins one worker.
# ----------------------------------------------------------------------
pytestmark = pytest.mark.xdist_group("suggest")


@pytest.fixture(scope="module")
def truth():
    return _truth()


def _refinement(truth, free=("phases.*.scale", "instrument.background.*")):
    """A Refinement at the truth state (deep-copied by __init__) + the data."""
    structure, ins, data = truth
    r = rx.Refinement(structure, ins)
    r.set_vary(["*"], False)
    for glob in free:
        r.set_vary([glob])
    return r, data


def _member_paths(res):
    return [m.path for g in res.groups for m in g.members]


def test_converged_state_suggests_nothing(truth):
    """Negative control: at the truth values nothing clears the floor.

    Calibration recorded in SUGGEST_MIN_GAIN's comment: the largest converged
    gain measured here is 5.7 against a floor of 9.10 (χ²_red 1.011)."""
    r, data = _refinement(truth)
    res = r.suggest(data)
    assert res.groups == [] and res.best_or_none() is None
    assert res.chi2_red == pytest.approx(1.0, abs=0.1)
    assert "converged" in res.summary
    assert res.n_evaluated > 10  # it looked, and found nothing — not vice versa


def test_injected_zero_shift_ranks_top_as_its_honest_tie(truth):
    """A 0.02° zero shift puts {zero_shift, sample_displacement} on top —
    unresolved, because at these weights the two are not separable, which is
    the tie Toby's per-derivative ranking would have silently broken."""
    r, data = _refinement(truth)
    r.instrument.zero_shift.value = 0.02
    res = r.suggest(data, exclude=["instrument.geometry.axial_*"])
    assert not any("axial" in p for p in _member_paths(res))
    top = res.groups[0]
    assert {m.path for m in top.members} == {
        "instrument.zero_shift", "instrument.geometry.sample_displacement"}
    assert not top.resolved and res.best_or_none() is None
    assert top.gain > 100 * res.noise_floor  # ~4 orders above a converged state


def test_zero_shift_layer2_agreement_recorded(truth):
    """The FitReport's refine_zero_shift action lands on the candidate — and
    every recorded kind is in the Layer-2 vocabulary: ``action_kind`` is a
    plain str because schemas cannot import report, so this meta-assertion
    (``typing.get_args(ActionKind)``) is what pins it."""
    from typing import get_args

    from rietx.report.schemas import ActionKind

    structure, ins, data = truth
    r, _ = _refinement(truth)
    r.instrument.zero_shift.value = 0.02
    report = _report_for(r.structure, r.instrument, data)
    assert "refine_zero_shift" in [a.kind for a in report.suggested_actions]
    res = r.suggest(data, report=report,
                    exclude=["instrument.geometry.axial_*"])
    by_path = {m.path: m for g in res.groups for m in g.members}
    assert by_path["instrument.zero_shift"].action_kind == "refine_zero_shift"
    vocabulary = get_args(ActionKind)
    for m in by_path.values():
        assert m.action_kind is None or m.action_kind in vocabulary


def test_injected_w_error_resolved_and_identity_pairs_tie(truth):
    """A W error yields a *resolved* W winner, while the exact-identity pair
    (instrument X vs phase lor_size — both Lorentzian FWHM/cosθ) comes back
    as one unresolved group whatever the injection."""
    r, data = _refinement(truth)
    r.instrument.profile.w.value = 6e-3
    res = r.suggest(data)
    best = res.best_or_none()
    assert best is not None and best.path == "instrument.profile.w"
    ties = [{m.path for m in g.members} for g in res.groups if not g.resolved]
    assert {"instrument.profile.x", "phases.0.lor_size"} in ties


def test_candidate_absorbed_by_free_set_is_not_a_winner(truth):
    """With U,V,W free, gauss_size (variance ∝ 1/cos² = U+W's span) is
    non-separable: whatever it would fit, the free set already reaches."""
    r, data = _refinement(truth, free=(
        "phases.*.scale", "instrument.background.*", "instrument.profile.u",
        "instrument.profile.v", "instrument.profile.w"))
    r.instrument.profile.w.value = 6e-3
    res = r.suggest(data)
    absorbed = {p.path: p for p in res.non_separable}
    assert "phases.0.gauss_size" in absorbed
    assert absorbed["phases.0.gauss_size"].absorption > 0.95
    assert "phases.0.gauss_size" not in _member_paths(res)


def test_softplus_floor_candidate_found_with_seeded_flag(truth):
    """An X error must surface lor_size even though it sits at the softplus
    floor where its unseeded column is fp noise — via the second, seeded
    probe build, reported as seeded=True from the stage seed."""
    r, data = _refinement(truth)
    r.instrument.profile.x.value = 9e-3
    res = r.suggest(data)
    top = res.groups[0]
    assert {m.path for m in top.members} == {
        "instrument.profile.x", "phases.0.lor_size"}
    lor = next(m for m in top.members if m.path == "phases.0.lor_size")
    assert lor.seeded and lor.seed_value == SUGGEST_SEED_SOFTPLUS
    assert not top.resolved  # the identity pair again — never a fake winner


def test_suggest_is_read_only(truth):
    """No history node, no model/value/vary/result mutation, no leaked seed."""
    r, data = _refinement(truth)
    r.instrument.profile.x.value = 9e-3   # forces the seeded second build
    before_vals = {row.path: row.value for row in r.parameters()}
    before_vary = {row.path: row.vary for row in r.parameters()}
    free_before = list(r._free_paths)
    r.suggest(data)
    assert r.history is None and r.result_ is None and r._model is None
    assert list(r._free_paths) == free_before
    assert {row.path: row.value for row in r.parameters()} == before_vals
    assert {row.path: row.vary for row in r.parameters()} == before_vary
    # the seed went into probe copies, never into the working models
    assert r.structure.phases[0].lor_size.value == 0.0


def test_lebail_mode_fixed_paths_never_enumerate(truth):
    """In Le Bail mode no .atoms./.scale/.source.lines. path is a candidate,
    and everything refinable-but-held was either scored or skipped."""
    r, data = _refinement(truth, free=("instrument.background.*",))
    res = r.suggest(data, mode="lebail")
    reported = (_member_paths(res) + [p.path for p in res.non_separable]
                + res.skipped)
    assert reported and not any(
        ".atoms." in p or p.endswith(".scale") or ".source.lines." in p
        for p in reported)
    held = [row for row in r.parameters(mode="lebail")
            if row.refinable and not row.vary]
    assert res.n_evaluated + len(res.skipped) == len(held)


def test_include_glob_limits_enumeration(truth):
    r, data = _refinement(truth)
    r.instrument.zero_shift.value = 0.02
    res = r.suggest(data, include="instrument.geometry.*")
    reported = (_member_paths(res) + [p.path for p in res.non_separable]
                + res.skipped)
    assert reported and all(p.startswith("instrument.geometry.") for p in reported)


def test_injected_states_render_for_inspection(truth):
    """obs/calc/diff PNGs of every planted state to tests/output/ (gitignored),
    full range + a low-angle zoom — a summary number hides locally-bad fits."""
    from pathlib import Path

    from rietx.viz.plots import plot_result

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    structure, ins, data = truth

    def injected(**edits):
        instrument = ins.model_copy(deep=True)
        for attr, value in edits.items():
            if attr == "zero_shift":
                instrument.zero_shift.value = value
            else:
                getattr(instrument.profile, attr).value = value
        return instrument

    cases = {
        "suggest_truth": ins,
        "suggest_zero_shift": injected(zero_shift=0.02),
        "suggest_w_error": injected(w=6e-3),
        "suggest_x_error": injected(x=9e-3),
    }
    for name, instrument in cases.items():
        result, _, _ = _result_for(structure, instrument, data)
        plot_result(result, path=str(out / f"{name}.png"))
        plot_result(result, path=str(out / f"{name}_zoom.png"),
                    two_theta_range=(18.0, 45.0))
        assert (out / f"{name}.png").exists()
