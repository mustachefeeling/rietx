"""Sequential (in-situ / parametric) refinement of a series — WP-0505.

Two synthetic series carry these tests, both built from the LaB6 model that
``test_refine_synthetic`` uses:

``thermal_series``
    a clean linear cell expansion — the only place where the *true* trajectory
    is known, so it is where the trajectory machinery is actually validated.
``jump_series``
    a nearly flat series with one step far larger than its own scatter, which
    is what the discontinuity fence exists to find.

The chain's fences (reseed, discontinuity, path dependence) never alter a
fitted value, so every test here asserts on the reported diagnostics and on
values that were fitted independently of them.
"""

import json
from typing import get_args

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.optimize.cancel import CancelToken
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.results import RefinedParameter, Statistics
from rietx.schemas.sequential import SeriesEntry, SeriesResult
from rietx.sequential import (
    SequentialRefinement,
    _better,
    _carry_into,
    _collapse,
    _discontinuity_diagnostics,
    _labels_for,
    _path_dependence_diagnostics,
    _reseed_needed,
    refine_sequential,
)
from rietx.strategy import staged
from tests.test_schemas import make_lab6

WAVELENGTH = 0.4139
A0 = 4.15660
TRUE_ZERO = 0.008
TRUE_W = 2.5e-4
TRUE_SCALE = 5e-4
TRUE_BKG = [40.0, -6.0, 1.5]

#: fractional cell expansion per step of the thermal series.  0.05 % shifts a
#: 20° peak by ~0.01°, comparable with the ~0.016° FWHM here, so successive
#: patterns are within each other's capture range — a series a warm start can
#: legitimately walk.
RAMP = 5e-4
#: temperatures the ramp is labelled with (the series coordinate)
TEMPERATURES = [300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0]


def _simulate(a: float, *, seed: int, biso: float = 0.4) -> rx.PatternData:
    """One pattern of the series at cell edge ``a``, with Poisson noise."""
    structure = make_lab6()
    for name in ("a", "b", "c"):
        getattr(structure.phases[0].cell, name).value = a
    for atom in structure.phases[0].atoms:
        atom.biso.value = biso
    structure.phases[0].scale.value = TRUE_SCALE
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = TRUE_ZERO
    ins.profile.w.value = TRUE_W
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in TRUE_BKG])

    tt = np.arange(3.0, 24.0, 0.005)
    blank = rx.PatternData(two_theta=tt.tolist(),
                           intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _start_models():
    """The starting model: cell 0.1 % off, no zero shift, flat background."""
    structure = make_lab6()
    for name in ("a", "b", "c"):
        getattr(structure.phases[0].cell, name).value = A0 * 1.001
    structure.phases[0].scale.value = TRUE_SCALE * 1.5
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = 0.0
    ins.profile.w.value = TRUE_W * 1.5
    ins.background = BackgroundChebyshev.with_terms(3)
    return structure, ins


@pytest.fixture(scope="module")
def thermal_patterns():
    """A 7-pattern ramp: a expands linearly by RAMP per step."""
    return [_simulate(A0 * (1.0 + RAMP * k), seed=11 + k)
            for k in range(len(TEMPERATURES))]


@pytest.fixture(scope="module")
def thermal_series(thermal_patterns):
    structure, ins = _start_models()
    return refine_sequential(thermal_patterns, structure, ins,
                             x=TEMPERATURES, x_label="T (K)",
                             labels=[f"{int(t)}K" for t in TEMPERATURES],
                             plan="mccusker_default")


@pytest.fixture(scope="module")
def jump_patterns():
    """Six patterns at one cell, then a step 20× the series' own scatter.

    The step (2e-3 Å) is far below the peak capture range, so *both* the warm
    and the cold fit find it easily — the discontinuity fence is about the
    trajectory, not about whether an individual fit succeeded.
    """
    flat = [_simulate(A0, seed=31 + k) for k in range(3)]
    stepped = [_simulate(A0 + 2e-3, seed=41 + k) for k in range(3)]
    return flat + stepped


# -- the trajectory: recovered against a known truth ----------------------

def test_series_recovers_the_injected_thermal_expansion(thermal_series):
    """The headline: the fitted a(T) reproduces the injected linear ramp.

    Checked as a *slope*, not point by point: the series was generated with a
    constant fractional expansion per step, and recovering that coefficient is
    what an in-situ user takes away.
    """
    assert len(thermal_series) == len(TEMPERATURES)
    assert all(e.status == "converged" for e in thermal_series)

    traj = thermal_series.trajectory("phases.0.cell.a")
    x, value, sd = traj.arrays()
    assert traj.x_label == "T (K)"
    assert np.allclose(x, TEMPERATURES)
    assert np.all(np.isfinite(sd)) and np.all(sd > 0)

    # injected: a(T) = A0·(1 + RAMP·k), one k per 100 K
    truth = A0 * (1.0 + RAMP * np.arange(len(TEMPERATURES)))
    assert np.allclose(value, truth, atol=max(5 * float(sd.max()), 1e-4))

    slope = np.polyfit(x, value, 1)[0]
    expected = A0 * RAMP / 100.0          # Å per K
    assert slope == pytest.approx(expected, rel=0.05)


def test_tied_cell_edges_travel_with_the_series(thermal_series):
    """Cubic b, c are tied to a, so they must appear in every trajectory."""
    a = thermal_series.trajectory("phases.0.cell.a")
    for name in ("b", "c"):
        other = thermal_series.trajectory(f"phases.0.cell.{name}")
        assert len(other) == len(a)
        assert np.allclose(other.arrays()[1], a.arrays()[1])
    # ... and `paths()` keeps them: tied is not the same as undetermined
    assert "phases.0.cell.b" in thermal_series.paths()
    assert "phases.0.cell.b" not in thermal_series.paths(varied_only=True)


def test_series_axis_defaults_to_the_pattern_index(thermal_patterns):
    """No coordinate given ⇒ the axis is the index, and x_label says so."""
    structure, ins = _start_models()
    series = refine_sequential(thermal_patterns[:2], structure, ins)
    assert series.x_label == "index"
    assert series.x == [0.0, 1.0]
    assert series.labels == ["p000", "p001"]


def test_labels_are_made_unique():
    """Labels become history file names, so duplicates cannot be tolerated."""
    blank = [rx.PatternData(two_theta=[1.0, 2.0], intensity=[1.0, 1.0])
             for _ in range(3)]
    assert _labels_for(blank, ["a", "a", "b"]) == ["a", "a_1", "b"]
    with pytest.raises(ValueError, match="labels has 2 entries"):
        _labels_for(blank, ["a", "b"])


# -- warm-start mechanics -------------------------------------------------

def test_carry_globs_move_only_matching_paths():
    """`carry` is per-parameter, and a narrow glob must not break a tie."""
    start_s, start_i = _start_models()
    fitted_s, fitted_i = _start_models()
    for name in ("a", "b", "c"):
        getattr(fitted_s.phases[0].cell, name).value = A0 * 1.02
    fitted_i.profile.w.value = 9e-4
    fitted_i.zero_shift.value = 0.02

    _carry_into(start_s, start_i, (fitted_s, fitted_i), ["instrument.profile.*"])
    assert start_i.profile.w.value == pytest.approx(9e-4)
    assert start_i.zero_shift.value == pytest.approx(0.0)      # not carried
    assert start_s.phases[0].cell.a.value == pytest.approx(A0 * 1.001)

    # carrying only `cell.a` must still leave b and c equal to it: the cubic
    # tie is re-derived from its source rather than left at the old value
    _carry_into(start_s, start_i, (fitted_s, fitted_i), ["phases.*.cell.a"])
    cell = start_s.phases[0].cell
    assert cell.a.value == pytest.approx(A0 * 1.02)
    assert cell.b.value == pytest.approx(cell.a.value)
    assert cell.c.value == pytest.approx(cell.a.value)


def test_collapse_unions_the_plans_turn_on_globs():
    plan = rx.RefinementPlan.mccusker_structural()
    single = _collapse(plan)
    assert len(single.stages) == 1
    for stage in plan.stages:
        for glob in stage.turn_on:
            assert glob in single.stages[0].turn_on
    # seeds survive the compression, so the protocol is the same one
    assert single.stages[0].seed == max(s.seed for s in plan.stages)


def test_refit_single_agrees_with_refit_stages(thermal_patterns):
    """The compressed refit reaches the same cell — it is a speed knob, not a
    different protocol.  The iteration counts are reported, never asserted:
    which one is cheaper is a measurement (see the WP acceptance)."""
    patterns = thermal_patterns[:4]
    staged = refine_sequential(*(patterns, *_start_models()), refit="stages")
    single = refine_sequential(*(patterns, *_start_models()), refit="single")

    a_staged = np.asarray(staged.trajectory("phases.0.cell.a").value)
    a_single = np.asarray(single.trajectory("phases.0.cell.a").value)
    sd = np.nanmax(staged.trajectory("phases.0.cell.a").arrays()[2])
    assert np.allclose(a_staged, a_single, atol=5 * sd)
    print(f"\niterations: stages={staged.n_iterations} single={single.n_iterations}")


# -- the reseed fence -----------------------------------------------------

def test_reseed_decision_uses_the_median_not_the_previous():
    """One bad pattern must not ratchet the threshold and let its successors
    through, which is exactly what comparing against the previous Rwp would do."""
    good = _fake_result(0.10)
    assert not _reseed_needed(good, [], 1.25)
    assert not _reseed_needed(good, [0.09, 0.10, 0.11], 1.25)
    assert _reseed_needed(_fake_result(0.30), [0.09, 0.10, 0.11], 1.25)
    # a single outlier already accepted does not move a median
    assert _reseed_needed(_fake_result(0.30), [0.09, 0.10, 0.11, 0.90], 1.25)
    # divergence always reseeds, whatever the Rwp
    assert _reseed_needed(_fake_result(0.01, status="diverged"), [0.10], 1.25)


def test_better_prefers_convergence_then_rwp():
    assert _better(_fake_result(0.10), _fake_result(0.20))
    assert not _better(_fake_result(0.20), _fake_result(0.10))
    # a converged fit beats a diverged one even at a worse Rwp
    assert _better(_fake_result(0.30), _fake_result(0.05, status="diverged"))


def test_reseed_records_both_fits_and_emits_a_diagnostic(thermal_patterns):
    """End-to-end through the reseed branch, forced by a threshold no fit can
    clear (any Rwp above the running median triggers it).  What is asserted is
    the *bookkeeping*: the kept fit is the better one, the rejected warm Rwp is
    still reported, and the iterations of both count against the series."""
    structure, ins = _start_models()
    series = SequentialRefinement(structure, ins).fit(
        thermal_patterns[:3], reseed_factor=1.0)
    assert len(series) == 3
    for entry in series:
        if entry.reseeded:
            assert entry.rwp_warm is not None
            assert entry.statistics.rwp <= entry.rwp_warm
    reseeded = [e for e in series if e.reseeded]
    codes = [d.code for d in series.diagnostics]
    assert codes.count("SEQUENTIAL_RESEED") == len(reseeded)
    if reseeded:
        assert all("did not come from its neighbour" in d.suggestion
                   for d in series.diagnostics if d.code == "SEQUENTIAL_RESEED")


def test_a_well_behaved_series_reseeds_nothing(thermal_series):
    assert not any(e.reseeded for e in thermal_series)
    assert "SEQUENTIAL_RESEED" not in [d.code for d in thermal_series.diagnostics]
    # ... and no pattern climbed past its first rung: the first is cold because
    # it has no predecessor, every other one is the collapsed warm refit
    assert [e.rung for e in thermal_series] == ["cold"] + ["warm"] * 6
    assert all(len(e.rungs_tried) == 1 for e in thermal_series)


# -- the escalation ladder (WP-1051) --------------------------------------

def test_the_ladder_is_the_rungs_in_order_and_never_repeats_one():
    """Three rungs from a collapsed warm refit, **two** from a staged one.

    Under ``refit="stages"`` the first rung already *is* the staged plan from
    the warm state, so the middle rung would re-run an identical plan from an
    identical starting point — a deterministic repeat the series would pay a
    whole fit for.
    """
    from rietx.sequential import RUNGS, _ladder

    base = rx.RefinementPlan.mccusker_default()
    collapsed = _collapse(base)

    single = _ladder(base, collapsed)
    assert [name for name, _, _ in single] == ["warm", "warm_staged", "cold"]
    assert [plan for _, plan, _ in single] == [collapsed, base, base]
    assert [warm for _, _, warm in single] == [True, True, False]

    stages = _ladder(base, base)
    assert [name for name, _, _ in stages] == ["warm_staged", "cold"]
    assert [plan for _, plan, _ in stages] == [base, base]

    # the names are the vocabulary the schema and the panels quote
    assert set(RUNGS) == {name for name, _, _ in single}


def _dictate(runner, script):
    """Force what each attempt *reports*, leaving the fits themselves real.

    ``script`` maps a pattern label to the ``(status, rwp)`` its successive
    rungs will come back with; the last pair repeats if the ladder climbs
    further.  Every model, tree and node in the series is still the real one —
    what is stubbed is the verdict the chain reasons about, which is the only
    way to make "which rung ran" a deterministic assertion: with real Rwps two
    patterns of the same material differ by Poisson noise, so whether the fence
    fires on the third pattern is a coin flip.
    """
    real = runner._fit_one
    seen: dict[str, int] = {}

    def dictated(*args, **kw):
        ref, result = real(*args, **kw)
        label = args[1]
        if label in script:
            attempts = script[label]
            k = min(seen.get(label, 0), len(attempts) - 1)
            seen[label] = seen.get(label, 0) + 1
            result.status, result.statistics.rwp = attempts[k]
        return ref, result

    runner._fit_one = dictated
    return runner


def test_the_ladder_stops_at_the_first_rung_that_works(thermal_patterns):
    """Warm-staged rescues the pattern, so the cold rung never runs.

    The whole point of the middle rung: the warm start is worth ~1.8× fewer
    iterations than a cold staged refit, and discarding it was never shown to
    be necessary.  The bookkeeping has to say so — ``rung`` names the attempt
    the values came from, ``rungs_tried`` says it was not the only one, and
    ``reseeded`` stays **False** because a staged refit from the warm state is
    still warm-started, so the chain is unbroken here.
    """
    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins),
                      {"p000": [("converged", 0.10)],
                       "p001": [("converged", 0.30), ("converged", 0.10)]})
    series = runner.fit(thermal_patterns[:2], plan=_CHEAP, reseed_factor=1.0)

    rescued = series[1]
    assert rescued.rungs_tried == ["warm", "warm_staged"]
    assert rescued.rung == "warm_staged"
    assert rescued.reseeded is False
    assert rescued.rwp_warm == pytest.approx(0.30)      # the rejected attempt
    assert rescued.statistics.rwp == pytest.approx(0.10)
    # no fence fires: the chain was never broken, only re-walked
    assert "SEQUENTIAL_RESEED" not in [d.code for d in series.diagnostics]
    # both attempts are charged to the pattern (the n_iterations contract)
    assert rescued.n_iterations > series[0].n_iterations


def test_the_cold_rung_is_reached_only_when_the_warm_ones_fail(thermal_patterns):
    """All three rungs, in order, and the cold one wins — the pre-WP-1051 path.

    ``reseeded`` and ``SEQUENTIAL_RESEED`` mean exactly what they meant before
    the ladder existed: the kept values did not come from the neighbour.
    """
    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins),
                      {"p000": [("converged", 0.10)],
                       "p001": [("converged", 0.30), ("converged", 0.28),
                                ("converged", 0.05)]})
    series = runner.fit(thermal_patterns[:2], plan=_CHEAP, reseed_factor=1.0)

    entry = series[1]
    assert entry.rungs_tried == ["warm", "warm_staged", "cold"]
    assert entry.rung == "cold"
    assert entry.reseeded is True
    assert entry.rwp_warm == pytest.approx(0.30)        # the *first* attempt
    assert [d.code for d in series.diagnostics] == ["SEQUENTIAL_RESEED"]


def test_a_rung_that_came_back_worse_is_not_kept(thermal_patterns):
    """Keep-best across all attempts, and the fence judges the best so far.

    A rung is an attempt, not a commitment: if the escalation lands worse than
    what it was escalating from, the earlier fit stands — and because the fence
    is then asked about *that* fit rather than the last one, the ladder keeps
    climbing instead of stopping on an improvement that never happened.
    """
    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins),
                      {"p000": [("converged", 0.10)],
                       "p001": [("converged", 0.30), ("converged", 0.90),
                                ("converged", 0.95)]})
    series = runner.fit(thermal_patterns[:2], plan=_CHEAP, reseed_factor=1.0)

    entry = series[1]
    assert entry.rungs_tried == ["warm", "warm_staged", "cold"]
    assert entry.rung == "warm"                       # the best of the three
    assert entry.statistics.rwp == pytest.approx(0.30)
    assert entry.reseeded is False and entry.rwp_warm == pytest.approx(0.30)


def test_an_unrecovered_pattern_seeds_nothing_and_joins_no_median(
        thermal_patterns, tmp_path):
    """The hygiene criterion: a doubly-failed pattern is stepped over.

    Pattern 1 is dictated to diverge on every rung at an Rwp *far below* the
    series — which is what makes the median half of this testable.  If the
    failure joined ``accepted_rwp`` the median would fall from 0.10 to 0.0505
    and pattern 2, at exactly 0.10, would escalate for no reason; quarantined,
    the median stays 0.10, ``0.10 > 1.0 × 0.10`` is false, and pattern 2 fits
    once.  The seeding half is read off the history note, which names the node
    each pattern's starting values actually came from.
    """
    structure, ins = _start_models()
    runner = _dictate(
        SequentialRefinement(structure, ins, history=tmp_path / "h"),
        {"p000": [("converged", 0.10)],
         "p001": [("diverged", 0.001)],
         "p002": [("converged", 0.10)]})
    series = runner.fit(thermal_patterns[:3], plan=_CHEAP, reseed_factor=1.0)

    failed = series[1]
    assert failed.status == "diverged"
    assert failed.rungs_tried == ["warm", "warm_staged", "cold"]   # all of them
    unrecovered = [d for d in series.diagnostics
                   if d.code == "SEQUENTIAL_UNRECOVERED"]
    assert len(unrecovered) == 1
    assert unrecovered[0].level == "warning"
    assert unrecovered[0].where == ["p001"]
    assert "seeded no successor" in unrecovered[0].message

    # the median never saw it: pattern 2 fitted once, against a median of 0.10
    assert series[2].rungs_tried == ["warm"]

    # ... and neither did the warm start: pattern 2 chains from pattern 0
    roots = [t.root for t in runner.trees_]
    assert roots[2].notes["series_warm_start_node"] == series[0].node_id
    assert roots[2].notes["series_warm_start_tree"] == series[0].tree_id
    # the failure is still reported in full — it was measured, and dropping it
    # would make the trajectory look like a shorter series
    assert len(series) == 3 and failed.statistics is not None


def test_every_rung_writes_its_own_history_log(thermal_patterns, tmp_path):
    """One header per file, which the cold restart used to break.

    Three attempts on one pattern are three separate fits of the same data —
    same ``tree_id``, since that is the data fingerprint — and the JSONL format
    is append-only, so sharing a file would interleave two trees' nodes under
    whichever header was written last.  Same reason the backward pass has its
    own suffix.
    """
    structure, ins = _start_models()
    runner = _dictate(
        SequentialRefinement(structure, ins, history=tmp_path / "h"),
        {"a": [("converged", 0.10)],
         "b": [("converged", 0.30), ("converged", 0.28), ("converged", 0.05)]})
    runner.fit(thermal_patterns[:2], plan=_CHEAP, labels=["a", "b"],
               reseed_factor=1.0)

    for name in ("a.jsonl", "b.jsonl", "b.warm_staged.jsonl", "b.cold.jsonl"):
        log = tmp_path / "h" / name
        assert log.exists(), name
        text = log.read_text(encoding="utf-8").replace(" ", "")
        assert text.count('"record":"header"') == 1, name
        assert rx.RefinementTree.load(log).header.tree_id
    # the kept fit is the cold one, and its log is the one the entry names
    assert not (tmp_path / "h" / "a.cold.jsonl").exists()


def test_a_restart_stamps_which_rung_it_is(thermal_patterns):
    """One added ``data`` key, on restarts only — and not one new ``EventKind``.

    ``series_rung`` has to appear on the escalation attempts and *not* on a
    pattern's first one: the first pattern of a chain runs the cold rung without
    being a restart, so stamping it would relabel an ordinary cold start as a
    rescue — and ``series_cold``, which WP-1016 defined as exactly that, would
    change meaning.  A changed meaning is an ``EVENT_SCHEMA_VERSION`` bump; an
    added field is not.
    """
    from rietx.history.events import EVENT_SCHEMA_VERSION, EventKind

    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins),
                      {"p000": [("converged", 0.10)],
                       "p001": [("converged", 0.30), ("converged", 0.28),
                                ("converged", 0.05)]})
    seen = []
    runner.fit(thermal_patterns[:2], plan=_CHEAP, reseed_factor=1.0,
               events=seen.append)

    assert {e["v"] for e in seen} == {EVENT_SCHEMA_VERSION}
    assert {e["kind"] for e in seen} <= set(get_args(EventKind))
    starts = [e["data"] for e in seen if e["kind"] == "fit_start"]
    assert [(d["series_index"], d.get("series_rung")) for d in starts] == [
        (0, None), (1, None), (1, "warm_staged"), (1, "cold")]
    # ``series_cold`` stays what it was: present, and true, on a cold restart
    assert [d.get("series_cold") for d in starts] == [None, None, None, True]


def test_a_cancel_mid_ladder_keeps_the_best_complete_attempt(thermal_patterns):
    """A rung that never finished is not evidence against the one that did.

    WP-1016's rule for the cold restart, one rung generalised: the abandoned
    attempt left no node and no commit, so what stands is the best *complete*
    fit of that pattern, and the walk ends there.
    """
    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins, history=True),
                      {"p000": [("converged", 0.10)],
                       "p001": [("converged", 0.30)]})
    token = CancelToken()

    def watch(event):
        if event["kind"] == "fit_start" and event["data"].get("series_rung"):
            token.cancel()

    series = runner.fit(thermal_patterns[:3], plan=_CHEAP, reseed_factor=1.0,
                        events=watch, cancel=token)

    assert len(series) == 2                      # pattern 2 was never started
    kept = series[1]
    assert kept.rungs_tried == ["warm"] and kept.rung == "warm"
    assert kept.statistics.rwp == pytest.approx(0.30)
    assert kept.node_id is not None              # a complete fit, with a node
    assert "SEQUENTIAL_CANCELLED" in [d.code for d in series.diagnostics]


# -- the discontinuity fence ---------------------------------------------

def test_discontinuity_is_flagged_and_the_value_is_left_alone(jump_patterns):
    structure, ins = _start_models()
    series = refine_sequential(jump_patterns, structure, ins)
    jumps = [d for d in series.diagnostics
             if d.code == "SEQUENTIAL_DISCONTINUITY"
             and d.where == ["phases.0.cell.a"]]
    assert len(jumps) == 1
    assert "either the specimen genuinely changed" in jumps[0].suggestion

    # nothing was smoothed: the fitted step is still the injected one
    value = np.asarray(series.trajectory("phases.0.cell.a").value)
    assert value[3] - value[2] == pytest.approx(2e-3, abs=3e-4)


def _synthetic_series(path: str, values, stderr) -> SeriesResult:
    return SeriesResult(entries=[
        SeriesEntry(index=k, label=f"p{k}", parameters=[
            RefinedParameter(path=path, value=v, stderr=s)])
        for k, (v, s) in enumerate(zip(values, stderr, strict=True))])


def test_an_inert_parameter_cannot_carry_a_discontinuity():
    """Regression for a measured false positive, and for why the σ test alone
    cannot catch it: a softplus coefficient dying on its floor has dp/du → 0,
    so its esd collapses *with* its value and every step is formally
    astronomically significant.  ``instrument.profile.y`` on the synthetic ramp
    came back with a median step of 4e-16, one step of 1.3e-11 and σ ≈ 4e-55."""
    inert = _synthetic_series(
        "instrument.profile.y",
        [1e-16, 2e-16, 1.3e-11, 1.4e-11, 1.5e-11, 1.6e-11],
        [4e-55] * 6)
    assert _discontinuity_diagnostics(inert) == []

    # the same shape at a physical magnitude is still reported
    real = _synthetic_series(
        "phases.0.cell.a",
        [4.1566, 4.15661, 4.15962, 4.15963, 4.15964, 4.15965],
        [1e-5] * 6)
    assert [d.code for d in _discontinuity_diagnostics(real)] == [
        "SEQUENTIAL_DISCONTINUITY"]


def test_path_dependence_ignores_numerically_identical_chains():
    """Two chains agreeing to 1e-60 are agreeing, whatever the σ ratio says."""
    forward = _synthetic_series("instrument.profile.y",
                                [2.2e-74, 1e-60, 1e-60], [1e-70] * 3)
    backward = _synthetic_series("instrument.profile.y",
                                 [2.1e-60, 1e-60, 1e-60], [1e-70] * 3)
    assert _path_dependence_diagnostics(forward, backward) == []

    moved = _synthetic_series("phases.0.cell.a", [4.1566, 4.1570, 4.1574],
                              [1e-5] * 3)
    shifted = _synthetic_series("phases.0.cell.a", [4.1576, 4.1570, 4.1574],
                                [1e-5] * 3)
    assert [d.code for d in _path_dependence_diagnostics(moved, shifted)] == [
        "SEQUENTIAL_PATH_DEPENDENT"]


def test_a_uniform_ramp_is_not_a_discontinuity(thermal_series):
    """A steady trend has every step at the median step, so the robust test
    passes it — which is the point of measuring against the series' own scatter
    rather than against the esds (in a real ramp every step is many σ)."""
    assert "SEQUENTIAL_DISCONTINUITY" not in [d.code
                                              for d in thermal_series.diagnostics]


# -- the path-dependence fence -------------------------------------------

@pytest.mark.slow
def test_forward_and_backward_chains_agree_on_a_clean_series(thermal_patterns):
    """Each pattern of a well-conditioned series reaches its own minimum
    whichever neighbour it started from, so no parameter is path-dependent."""
    structure, ins = _start_models()
    series = refine_sequential(thermal_patterns[:5], structure, ins,
                               direction="both")
    assert series.direction == "both"
    assert [d.code for d in series.diagnostics
            if d.code == "SEQUENTIAL_PATH_DEPENDENT"] == []
    # the backward chain is kept, and reported in series order
    assert [e.index for e in series.entries] == [0, 1, 2, 3, 4]


# -- reporting surfaces ---------------------------------------------------

def test_series_result_json_round_trip(thermal_series):
    text = thermal_series.model_dump_json()
    back = SeriesResult.model_validate(json.loads(text))
    assert len(back) == len(thermal_series)
    assert back.x_label == thermal_series.x_label
    assert back.labels == thermal_series.labels
    assert (back.trajectory("phases.0.cell.a").value
            == thermal_series.trajectory("phases.0.cell.a").value)
    # summaries, not curves: a series must never carry N patterns of y_obs
    assert "y_obs" not in text


def test_write_csv(thermal_series, tmp_path):
    out = tmp_path / "series.csv"
    thermal_series.write_csv(out, paths=["phases.0.cell.a"])
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].split(",") == ["index", "label", "T (K)", "status", "rung",
                                   "rwp", "gof", "phases.0.cell.a",
                                   "phases.0.cell.a_esd"]
    assert len(lines) == len(thermal_series) + 1
    assert lines[1].split(",")[1] == "300K"


def test_the_rung_reaches_json_the_table_and_the_plot(tmp_path):
    """The bookkeeping is only useful where a reader will meet it.

    Built by hand rather than fitted: what is under test is that the three
    reporting surfaces carry the ladder's answer, not that the ladder produces
    one (the tests above do that), and a synthetic series can hold the two rows
    that matter — a rescued point and one nothing rescued — side by side.
    """
    import matplotlib.pyplot as plt

    series = SeriesResult(entries=[
        SeriesEntry(index=0, label="p0", rung="cold", rungs_tried=["cold"],
                    statistics=Statistics(rwp=0.1, rp=0.1, rexp=0.05, chi2=1.0,
                                          gof=1.0, n_points=10,
                                          n_free_parameters=1),
                    parameters=[RefinedParameter(path="phases.0.cell.a",
                                                 value=4.0, stderr=1e-4)]),
        SeriesEntry(index=1, label="p1", rung="cold", reseeded=True,
                    rwp_warm=0.4, rungs_tried=["warm", "warm_staged", "cold"],
                    parameters=[RefinedParameter(path="phases.0.cell.a",
                                                 value=4.1, stderr=1e-4)]),
        SeriesEntry(index=2, label="p2", status="diverged", rung="warm",
                    rungs_tried=["warm", "warm_staged", "cold"],
                    parameters=[RefinedParameter(path="phases.0.cell.a",
                                                 value=9.9, stderr=1e-4)]),
    ])

    back = SeriesResult.model_validate(json.loads(series.model_dump_json()))
    assert [e.rung for e in back] == ["cold", "cold", "warm"]
    assert back[2].rungs_tried == ["warm", "warm_staged", "cold"]

    header, rows = back.to_table(paths=["phases.0.cell.a"])
    assert header[3:5] == ["status", "rung"]
    assert [row[4] for row in rows] == ["cold", "cold", "warm"]

    # the diverged point is crossed out, the rescued one ringed: a ring means
    # "good fit, different starting model", a cross means "not a measurement"
    fig = back.plot(["phases.0.cell.a"])
    markers = [line.get_marker() for line in fig.axes[0].lines]
    assert markers.count("x") == 1 and markers.count("o") >= 1
    fig.savefig(tmp_path / "traj.png")
    plt.close("all")
    assert (tmp_path / "traj.png").stat().st_size > 5_000


def test_plot_trajectory_writes_a_png(thermal_series, tmp_path):
    import matplotlib.pyplot as plt

    out = tmp_path / "trajectory.png"
    thermal_series.plot(["phases.0.cell.a", "instrument.profile.w"], path=out)
    plt.close("all")
    assert out.exists() and out.stat().st_size > 5_000


def test_qpa_trajectory(thermal_series):
    traj = thermal_series.qpa_trajectory("LaB6")
    assert len(traj) == len(thermal_series)
    # single phase ⇒ 100 wt % at every point
    assert np.allclose(traj.arrays()[1], 100.0)


# -- history --------------------------------------------------------------

def test_one_tree_per_pattern_cross_linked(thermal_patterns, tmp_path):
    """A tree is pinned to one pattern by its data fingerprint, so the series
    is N trees; the chain is recorded as notes on each root node."""
    structure, ins = _start_models()
    series = SequentialRefinement(structure, ins, history=tmp_path / "hist")
    series.fit(thermal_patterns[:3], labels=["t0", "t1", "t2"])

    for name in ("t0", "t1", "t2"):
        assert (tmp_path / "hist" / f"{name}.jsonl").exists()
    trees = series.trees_
    assert len({t.header.tree_id for t in trees}) == 3       # distinct patterns

    roots = [t.root for t in trees]
    assert "series_warm_start_node" not in roots[0].notes    # the cold start
    for k in (1, 2):
        assert roots[k].notes["series_position"] == str(k)
        assert roots[k].notes["series_warm_start_tree"] == trees[k - 1].header.tree_id
        assert roots[k].notes["series_warm_start_node"] is not None

    # each entry points at its own tree, and a reloaded log agrees
    reloaded = rx.RefinementTree.load(tmp_path / "hist" / "t1.jsonl")
    assert reloaded.header.tree_id == series.result_[1].tree_id
    assert reloaded.root.notes["series_label"] == "t1"


def test_the_backward_pass_writes_its_own_logs(thermal_patterns, tmp_path):
    """A verification chain must not append to the reported chain's log.

    The JSONL format is append-only by design, so two headers in one file would
    make the reload ambiguous — ``direction="both"`` writes the backward pass
    to ``<label>.backward.jsonl``."""
    structure, ins = _start_models()
    series = SequentialRefinement(structure, ins, history=tmp_path / "h")
    series.fit(thermal_patterns[:2], labels=["a", "b"], direction="both")

    for name in ("a", "b"):
        forward = tmp_path / "h" / f"{name}.jsonl"
        assert forward.exists()
        assert (tmp_path / "h" / f"{name}.backward.jsonl").exists()
        # exactly one header record, so the log is unambiguously reloadable
        headers = [line for line in forward.read_text(encoding="utf-8").splitlines()
                   if '"record":"header"' in line.replace(" ", "")]
        assert len(headers) == 1
        assert rx.RefinementTree.load(forward).header.tree_id


# -- Le Bail --------------------------------------------------------------

@pytest.mark.slow
def test_lebail_series_carries_extracted_intensities(thermal_patterns):
    """Le Bail intensities are path-dependent state outside θ; a series must
    carry them pattern to pattern rather than re-seeding flat every time."""
    structure, ins = _start_models()
    series = refine_sequential(thermal_patterns[:3], structure, ins,
                               mode="lebail")
    assert series.mode == "lebail"
    assert all(e.status == "converged" for e in series)
    assert all(e.qpa is None for e in series)      # Le Bail scales are degenerate

    a = np.asarray(series.trajectory("phases.0.cell.a").value)
    truth = A0 * (1.0 + RAMP * np.arange(3))
    assert np.allclose(a, truth, atol=2e-4)


# -- argument validation --------------------------------------------------

def test_argument_validation(thermal_patterns):
    structure, ins = _start_models()
    seq = SequentialRefinement(structure, ins)
    with pytest.raises(ValueError, match="at least one pattern"):
        seq.fit([])
    with pytest.raises(ValueError, match="refit must be"):
        seq.fit(thermal_patterns[:1], refit="nope")
    with pytest.raises(ValueError, match="direction must be"):
        seq.fit(thermal_patterns[:1], direction="sideways")
    with pytest.raises(ValueError, match="x has 2 entries"):
        seq.fit(thermal_patterns[:1], x=[1.0, 2.0])
    with pytest.raises(ValueError, match="unknown plan preset"):
        seq.fit(thermal_patterns[:1], plan="does_not_exist")


def _fake_result(rwp: float, *, status: str = "converged"):
    """A minimal RefinementResult standing in for a fit, for the guard units."""
    from rietx.schemas.common import Provenance
    from rietx.schemas.results import RefinementResult

    return RefinementResult(
        status=status, mode="rietveld", parameters=[],
        statistics=Statistics(rwp=rwp, rp=rwp, rexp=0.05, chi2=1.0, gof=1.0,
                              n_points=10, n_free_parameters=1),
        provenance=Provenance(package_version="test"))


def test_series_entry_lookup_helpers():
    entry = SeriesEntry(index=0, parameters=[
        RefinedParameter(path="phases.0.cell.a", value=4.0, stderr=1e-4)])
    assert entry.value("phases.0.cell.a") == 4.0
    assert entry.stderr("phases.0.cell.a") == pytest.approx(1e-4)
    assert entry.value("nope") is None and entry.stderr("nope") is None


# ----------------------------------------------------------------------
# telemetry and cancellation (WP-1016)
# ----------------------------------------------------------------------
#: A one-stage plan freeing the one parameter these tests care about.  The
#: chain's *answers* are the tests above; what is under test here is the stream
#: and the token, so the fits are as cheap as they can be.
_CHEAP = staged.RefinementPlan(stages=[
    staged.Stage("quick", ["phases.*.scale"], max_iter=5)])


def test_unique_labels_disambiguates_by_position():
    """Two files with the same basename is an ordinary series.

    Split out of ``_labels_for`` because a caller that *offers* the labels before
    the run has to show the ones the run will use — a panel displaying the name
    that was typed would be displaying a name that names nothing (WP-1016).
    """
    from rietx.sequential import unique_labels

    assert unique_labels(["a", "b", "a", "a"]) == ["a", "b", "a_2", "a_3"]
    assert unique_labels([]) == []
    # and ``_labels_for`` is that function, not a second copy of the rule
    assert _labels_for([None, None, None], ["x", "x", "y"]) == ["x", "x_1", "y"]


def test_every_patterns_events_carry_its_place_in_the_series():
    """Per-pattern telemetry, and not one new ``EventKind``.

    ``data`` is an open dict on both sides, so five added fields on existing
    kinds is an additive change and ``EVENT_SCHEMA_VERSION`` does not move — the
    rule, and the reason a bump would make the version useless as a
    compatibility signal, are in ``history/events.py``.
    """
    from rietx.history.events import EVENT_SCHEMA_VERSION, EventKind

    patterns = [_simulate(A0 * (1 + RAMP * i), seed=500 + i) for i in range(2)]
    structure, ins = _start_models()
    seen = []
    series = SequentialRefinement(structure, ins).fit(
        patterns, plan=_CHEAP, labels=["lo", "hi"], events=seen.append)

    assert len(series) == 2
    kinds = {e["kind"] for e in seen}
    assert kinds <= set(get_args(EventKind))          # nothing new was invented
    assert {"fit_start", "fit_end", "stage_start", "stage_end"} <= kinds
    assert {e["v"] for e in seen} == {EVENT_SCHEMA_VERSION}

    # every event, not only the fit pair: an ``eval`` from pattern 1 has to be
    # attributable too, or a progress bar cannot tell the two patterns apart
    assert all("series_index" in e["data"] for e in seen)
    starts = [e["data"] for e in seen if e["kind"] == "fit_start"]
    assert [(d["series_index"], d["series_label"]) for d in starts] == [
        (0, "lo"), (1, "hi")]
    assert {d["series_n"] for d in starts} == {2}
    assert {d["series_pass"] for d in starts} == {"forward"}
    # the stamp does not displace the event's own fields
    assert starts[0]["mode"] == "rietveld" and starts[0]["n_points"] == len(
        patterns[0].two_theta)


def test_a_backward_pass_is_the_same_patterns_walked_again():
    """``series_index`` is the pattern's place in the *series*, not in the walk.

    Which is what makes the two chains comparable frame by frame — and
    ``series_pass`` is then the only thing that distinguishes the verification
    pass from a restart, which a counter running 1…N…1 otherwise reads as.
    """
    patterns = [_simulate(A0 * (1 + RAMP * i), seed=600 + i) for i in range(2)]
    structure, ins = _start_models()
    seen = []
    SequentialRefinement(structure, ins).fit(
        patterns, plan=_CHEAP, labels=["lo", "hi"], direction="both",
        events=seen.append)

    walked = [(e["data"]["series_index"], e["data"]["series_pass"])
              for e in seen if e["kind"] == "fit_start"]
    assert walked == [(0, "forward"), (1, "forward"),
                      (1, "backward"), (0, "backward")]


def test_a_cancelled_series_returns_what_it_completed():
    """The rule one level up, not an exception to it.

    ``Refinement.fit`` abandons the stage in flight and raises; a *series* is N
    separate refinements, so the patterns already walked are finished fits with
    committed nodes — raising here would throw them away.  What must not happen
    is silence: a short ``entries`` list is indistinguishable from a shorter
    series that ran to completion, so ``SEQUENTIAL_CANCELLED`` says how far it
    got.
    """
    patterns = [_simulate(A0 * (1 + RAMP * i), seed=700 + i) for i in range(3)]
    structure, ins = _start_models()
    token = CancelToken()

    def watch(event):
        if event["kind"] == "fit_end" and event["data"]["series_index"] == 0:
            token.cancel()

    runner = SequentialRefinement(structure, ins, history=True)
    series = runner.fit(patterns, plan=_CHEAP, events=watch, cancel=token)

    assert len(series) == 1
    assert len(runner.results_) == 1 and len(runner.trees_) == 1
    assert [d.code for d in series.diagnostics] == ["SEQUENTIAL_CANCELLED"]
    assert "after 1 of 3 patterns" in series.diagnostics[0].message
    # the completed pattern is a real fit with a real node
    assert series[0].node_id and series[0].statistics is not None


def test_a_cancelled_chain_does_not_run_the_verification_pass():
    """The comparison is between two *complete* chains; half of one says nothing."""
    patterns = [_simulate(A0 * (1 + RAMP * i), seed=800 + i) for i in range(3)]
    structure, ins = _start_models()
    token = CancelToken()
    passes = []

    def watch(event):
        if event["kind"] == "fit_start":
            passes.append(event["data"]["series_pass"])
        if event["kind"] == "fit_end" and event["data"]["series_index"] == 1:
            token.cancel()

    runner = SequentialRefinement(structure, ins)
    series = runner.fit(patterns, plan=_CHEAP, direction="both", events=watch,
                        cancel=token)

    assert set(passes) == {"forward"}
    assert runner.backward_ is None
    assert [d.code for d in series.diagnostics] == ["SEQUENTIAL_CANCELLED"]
    assert not any(d.code == "SEQUENTIAL_PATH_DEPENDENT"
                   for d in series.diagnostics)
