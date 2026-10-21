"""What a joint fit reports about itself (WP-1341, issue #252).

A joint refinement used to converge and leave nothing to inspect: no event
log, no convergence figure, no report.  These tests hold each piece the WP
added.  The fixture is test_multi_histogram's synthetic LaB6 pair at two
wavelengths, so no number here is a claim about a specimen.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from rietx import MultiHistogramRefinement, Refinement, Stage, runs
from rietx.history.events import as_event_stream, read_events
from rietx.optimize.cancel import CancelToken, RefinementCancelled
from rietx.optimize.statistics import MAX_SHIFT_CONVERGED
from rietx.params.multi import SharingMap
from rietx.strategy.staged import RefinementPlan
from tests.test_multi_histogram import (
    _broadened,
    _width_plan,
    _width_start,
    perturbed_inputs,
    synthesize,
)

OUT = Path(__file__).parent / "output"
LAMS = (0.41390, 0.71070)

# the module fixtures below are shared, so the module stays on one worker
# (tests/CLAUDE.md § Shared fixtures and xdist groups)
pytestmark = pytest.mark.xdist_group("joint-report")

TURN_ON = ["phases.*.scale", "instrument.background.*", "phases.*.cell.*",
           "instrument.zero_shift"]


@pytest.fixture(scope="module")
def two_patterns():
    return [
        synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                   bkg=[40.0, -6.0, 1.5], seed=1),
        synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                   bkg=[70.0, 5.0, -2.0], seed=2),
    ]


def _plot(result, stem: str) -> None:
    OUT.mkdir(exist_ok=True)
    for h in range(len(result.histograms)):
        result.for_histogram(h).plot(OUT / f"{stem}_h{h}.png")


# ---------------------------------------------------- the convergence figure --
@pytest.mark.parametrize("solver", ["lm", "trf"])
def test_a_joint_fit_measures_how_far_it_was_still_moving(two_patterns, solver):
    """McCusker §7's quantity on both branches, now on the joint θ.

    Measured 2026-10-12 on this fixture: converged 5e-7 to 2.2e-3 across both
    drivers, unit and 1:4 weights; starved to one iteration, 4.0 (LM) and 17.9
    (TRF).  Both sides clear the 0.1 band by 40× or more, so neither assertion
    senses where a solver happened to stop.
    """
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments, solver=solver)
    done = ref.fit(two_patterns, plan="mccusker_default", weights=[1.0, 4.0])
    assert done.status == "converged"
    shift = done.statistics.max_shift_over_esd
    assert shift is not None and shift < MAX_SHIFT_CONVERGED
    _plot(done, f"joint_report_shift_{solver}")

    # whole-fit: the per-histogram statistics have no writer for it, and the
    # view that keeps the joint stages carries the joint figure beside them
    for h, hist in enumerate(done.histograms):
        assert hist.statistics.max_shift_over_esd is None
        assert done.for_histogram(h).statistics.max_shift_over_esd == shift
    assert f"max|Δθ|/esd={shift:.3f}" in str(done)

    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments, solver=solver)
    starved = ref.fit(two_patterns, plan=RefinementPlan(
        stages=[Stage("starved", turn_on=TURN_ON, max_iter=1)]))
    assert starved.status == "max_iter"
    assert starved.statistics.max_shift_over_esd > MAX_SHIFT_CONVERGED


# ------------------------------------------------------------- the event log --
def test_a_joint_event_log_partitions_by_histogram(two_patterns, tmp_path):
    """Issue #252's first ask: an event log a reader can split by histogram.

    The joint solve is one solve, so each kind is emitted once per fit, stage
    or evaluation, and a per-histogram fact rides in a ``histograms`` row
    stamped with its ``histogram_index``.
    """
    progress = io.StringIO()
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(two_patterns, plan="mccusker_default",
                     events=tmp_path / "joint.jsonl", progress=progress)
    _plot(result, "joint_report_events")
    log = [(e.kind, e.data) for e in read_events(tmp_path / "joint.jsonl")]
    kinds = [k for k, _ in log]
    n_stages = len(result.stages)
    assert kinds[0] == "fit_start" and kinds[-1] == "fit_end"
    assert kinds.count("stage_start") == kinds.count("stage_end") == n_stages
    assert kinds.count("eval") > n_stages

    by_hist: dict[int, list[dict]] = {0: [], 1: []}
    for kind, data in log:
        if kind == "eval":
            continue
        assert data["n_histograms"] == 2, kind
        rows = data["histograms"]
        assert [r["histogram_index"] for r in rows] == [0, 1], kind
        if kind == "stage_end":
            for r in rows:
                by_hist[r["histogram_index"]].append(r)
    for h, rows in by_hist.items():
        assert len(rows) == n_stages
        # the last stage's reading is the answer's, from the same models
        assert rows[-1]["rwp"] == result.histograms[h].statistics.rwp

    start = log[0][1]
    assert start["n_points"] == sum(r["n_points"] for r in start["histograms"])
    ends = [d for k, d in log if k == "stage_end"]
    assert ends[-1]["rwp"] == log[-1][1]["rwp"] == result.statistics.rwp

    # an eval's values align with the most recent stage_start's free paths,
    # and those split by histogram on their ``hist.<h>.`` scope
    free, last = None, None
    for kind, data in log:
        if kind == "stage_start":
            free = data["free_paths"]
        elif kind == "eval":
            assert len(data["values"]) == len(free)
            last = data
    owned = {h: [p for p in free if p.startswith(f"hist.{h}.")] for h in (0, 1)}
    assert "hist.0.instrument.zero_shift" in owned[0]
    assert "hist.1.instrument.zero_shift" in owned[1]
    assert "phases.0.cell.a" in free            # shared, so bare
    values = dict(zip(free, last["values"], strict=True))
    assert values["phases.0.cell.a"] == pytest.approx(
        result.parameter("phases.0.cell.a").value, rel=1e-6)

    # ``progress=`` reads the same stream: one line per stage
    assert len(progress.getvalue().splitlines()) == n_stages


def test_a_monitoring_hook_that_raises_is_the_callers_to_see(two_patterns):
    """``history/events.py``'s rule: a callback's exception propagates."""
    def hook(event):
        if event["kind"] == "stage_end":
            raise RuntimeError("the caller's own bug")

    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    with pytest.raises(RuntimeError, match="the caller's own bug"):
        ref.fit(two_patterns, plan="mccusker_default", events=hook)


def test_a_raised_joint_fit_closes_the_stream_it_built(two_patterns, tmp_path,
                                                       monkeypatch):
    """A stream built from a path is the fit's to close, on every exit."""
    import rietx.multi as multi_mod

    built = []

    def capture(events):
        stream = as_event_stream(events)
        built.append(stream)
        return stream

    def fail(*_args, **_kw):
        raise RuntimeError("after the last stage")

    monkeypatch.setattr(multi_mod, "as_event_stream", capture)
    monkeypatch.setattr(MultiHistogramRefinement, "_build_result", fail)
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    with pytest.raises(RuntimeError, match="after the last stage"):
        ref.fit(two_patterns, plan=RefinementPlan(stages=[
            Stage("scale+bkg", ["phases.*.scale", "instrument.background.*"])]),
            events=tmp_path / "joint.jsonl")
    (stream,) = built
    assert stream._fh is None


def test_a_cancelled_joint_stage_is_abandoned(two_patterns):
    """The cooperative cancel, one rank out: the stage in flight leaves no
    trace, and the working state is the last completed stage's."""
    # one tolerance for every stage, so the two-stage prefix below solves its
    # stages exactly as the three-stage plan does (WP-1123's schedule would
    # run "zero" at 1e-6 here and at 1e-9 there)
    plan = RefinementPlan(stages=[
        Stage("scale+bkg", turn_on=["phases.*.scale", "instrument.background.*"]),
        Stage("zero", turn_on=["instrument.zero_shift"]),
        Stage("cell", turn_on=["phases.*.cell.*"]),
    ], intermediate_ftol=None)
    token = CancelToken()
    log: list[dict] = []

    def hook(event):
        log.append(event)
        data = event["data"]
        if event["kind"] == "eval" and data["stage"] == "cell" and data["n_eval"] == 3:
            token.cancel()

    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    with pytest.raises(RefinementCancelled) as info:
        ref.fit(two_patterns, plan=plan, events=hook, cancel=token)
    exc = info.value
    assert exc.stage == "cell"
    assert [s.name for s in exc.completed_stages] == ["scale+bkg", "zero"]
    assert exc.node_id is None
    assert ref.result_ is None
    tail = [(e["kind"], e["data"].get("status")) for e in log[-2:]]
    assert tail == [("stage_end", "cancelled"), ("fit_end", "cancelled")]

    # the same two stages run to completion land exactly where the cancel left
    structure, instruments = perturbed_inputs()
    done = MultiHistogramRefinement(structure, instruments)
    # the declared stages' working state; the closing stage is tests/test_closing_stage.py's
    done.fit(two_patterns, plan=RefinementPlan(stages=plan.stages[:2],
                                               intermediate_ftol=None,
                                               closing_window_tol=None))
    for h in (0, 1):
        assert (ref.fitted_structures[h].model_dump()
                == done.fitted_structures[h].model_dump())
        assert (ref.fitted_instruments[h].model_dump()
                == done.fitted_instruments[h].model_dump())


def test_a_recorded_joint_fit_is_one_run(two_patterns, tmp_path):
    """Every fit records itself, and a joint fit is one job (WP-1403)."""
    was = runs.set_enabled(True)
    try:
        structure, instruments = perturbed_inputs()
        ref = MultiHistogramRefinement(structure, instruments)
        result = ref.fit(two_patterns, plan="mccusker_default",
                         telemetry=tmp_path, label="joint LaB6")
    finally:
        runs.set_enabled(was)
    (run,) = runs.discover(tmp_path)
    assert run.status is not None and run.status.state == "done"
    assert run.status.rwp == pytest.approx(result.statistics.rwp)
    assert run.meta is not None and run.meta.label == "joint LaB6"
    summary = (run.path / runs.SUMMARY_FILE).read_text(encoding="utf-8")
    assert summary == str(result)
    # the live view draws one pattern, so a joint run writes no picture
    assert not (run.path / runs.SNAPSHOT_FILE).exists()


# ---------------------------------------------------------------- the report --
def test_each_histogram_gets_its_own_report(two_patterns):
    """Layers 0-2 per histogram, off that histogram's model and curves."""
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    with pytest.raises(RuntimeError, match="fit"):
        ref.report(0)
    result = ref.fit(two_patterns, plan="mccusker_default")
    _plot(result, "joint_report_layers")
    with pytest.raises(IndexError):
        ref.report(2)
    for h in (0, 1):
        report = ref.report(h, plan="mccusker_default")
        assert report.layer1_available
        assert report.unmatched == []       # one phase, every peak ticked
        assert report.rwp == result.histograms[h].statistics.rwp
        # the background section reads this histogram's own screen, which
        # the joint result carries ``hist.<h>.``-scoped
        mine = {k.split(".", 2)[2]: v for k, v in
                result.identifiability.background_absorption.items()
                if k.startswith(f"hist.{h}.")}
        assert mine
        assert (result.for_histogram(h).identifiability.background_absorption
                == mine)
        assert report.background.worst_absorption == max(mine.values())


def test_a_cancelled_second_fit_leaves_the_first_report_alone(two_patterns):
    """The report reads what its own fit left, never the working table.

    A cancelled fit puts the table back where its stage found it and keeps
    the previous result, so a report reading the live table paired the
    second fit's values with the first fit's models.
    """
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments)
    ref.fit(two_patterns, plan="mccusker_default")
    before = ref.report(0).model_dump()

    token = CancelToken()

    def hook(event):
        data = event["data"]
        if event["kind"] == "stage_start" and data["stage"] == "zero":
            token.cancel()       # read at the second stage's first evaluation

    with pytest.raises(RefinementCancelled):
        ref.fit(two_patterns, plan="mccusker_default", weights=[1.0, 4.0],
                events=hook, cancel=token)
    assert ref.report(0).model_dump() == before


def test_a_view_spells_its_own_rows_as_a_single_fit_does(two_patterns):
    """A per-histogram structural row reaches the report under its bare name.

    ``build_report`` looks parameters up by bare path (the moment arm's esds,
    Layer 2's freed-parameter rows), so a view carrying ``hist.1.…`` missed
    them, and carried histogram 0's rows beside its own.
    """
    biso = "phases.0.atoms.0.biso"
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(
        structure, instruments,
        sharing=SharingMap(per_histogram=["phases.*.atoms.*.biso"]))
    result = ref.fit(two_patterns, plan=RefinementPlan(stages=[
        Stage("scale+bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("zero", ["instrument.zero_shift"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("width", ["instrument.profile.w"]),
        Stage("b", [biso])]))
    assert result.status == "converged"
    assert all(hr.statistics.rwp < 0.12 for hr in result.histograms)
    _plot(result, "joint_report_view_rows")
    rows = {p.path: p for p in result.parameters}
    assert {f"hist.0.{biso}", f"hist.1.{biso}"} <= set(rows)
    for h in (0, 1):
        view = {p.path: p for p in result.for_histogram(h).parameters}
        assert view[biso] == rows[f"hist.{h}.{biso}"].model_copy(
            update={"path": biso})
        assert not [p for p in view if p.startswith("hist.")]
        assert "phases.0.cell.b" in view          # a shared (tied) row stays bare
    # a negative index counts from the end, and past either end is refused
    assert result.for_histogram(-1).parameters == result.for_histogram(1).parameters
    for bad in (2, -3):
        with pytest.raises(IndexError):
            result.for_histogram(bad)


@pytest.fixture(scope="module")
def size_patterns():
    """test_multi_histogram's WP-1131 pair: one 400 Å specimen, two λ."""
    return [_broadened("lor_size", LAMS[0], 3.0, 24.0, seed=1)[0],
            _broadened("lor_size", LAMS[1], 5.0, 42.0, seed=2)[0]]


def _size(block) -> float:
    (term,) = [t for t in block.terms if t.path.endswith("lor_size")]
    return term.value


def test_the_specimen_size_is_reported_once(size_patterns):
    """One specimen, one size: the same block in every histogram's report.

    Measured 2026-10-12: the joint fit reads 408.82(4.86) Å; the two solo
    arms read 408.71(8.05) and 409.20(6.43) Å.  The joint block is read off
    the shared column at histogram 0's λ, so both reports quote its
    coefficient, never histogram 1's λ-scaled copy.
    """
    structure, _ = _width_start(LAMS[0])
    instruments = [_width_start(lam)[1] for lam in LAMS]
    ref = MultiHistogramRefinement(structure, instruments)
    result = ref.fit(size_patterns, plan=_width_plan("lor_size"))
    _plot(result, "joint_report_size")
    joint = result.microstructure[0]
    reports = [ref.report(h) for h in (0, 1)]
    for report in reports:
        (block,) = report.microstructure
        assert [t.coefficient for t in block.terms] == [
            t.coefficient for t in joint.terms]
        assert _size(block) == _size(joint)

    for h, (pattern, lam) in enumerate(zip(size_patterns, LAMS, strict=True)):
        s, ins = _width_start(lam)
        solo = Refinement(s, ins, history=False).fit(
            pattern, plan=_width_plan("lor_size"))
        solo.plot(OUT / f"joint_report_size_solo_h{h}.png")
        assert _size(joint) == pytest.approx(_size(solo.microstructure[0]),
                                             rel=0.005)


# ------------------------------------------- STAGE_PATH_NOT_FREE, jointly --
def _codes(result, code):
    return [d for d in result.diagnostics if d.code == code]


def _one_stage(patterns, turn_on, *, sharing=None):
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments, sharing=sharing)
    return ref.fit(patterns, plan=RefinementPlan(stages=[
        Stage("only", ["phases.*.scale", *turn_on], max_iter=5)]))


@pytest.mark.parametrize("path, says", [
    # test_params_surface's four, on the same LaB6: B on 6f, La on 1a
    ("phases.0.atoms.1.x", "follows phases.0.atoms.1.dof.0"),
    ("phases.0.atoms.1.y", "is fixed by symmetry or by the model"),
    ("phases.0.atoms.0.z", "is fixed by symmetry or by the model"),
    ("phases.0.cell.b", "follows phases.0.cell.a"),
])
def test_a_joint_plan_naming_a_fixed_literal_says_so(two_patterns, path, says):
    """Issue #803: one finding per path, naming its stage and its histograms.

    The rows are shared, so both tables hold them fixed and the finding is
    one.  ``STAGE_FREED_NOTHING`` stays silent: the literal matched a row in
    both histograms, which is that check's "reached".
    """
    result = _one_stage(two_patterns, [path])
    assert path not in result.stages[0].freed
    (found,) = _codes(result, "STAGE_PATH_NOT_FREE")
    assert found.level == "warning" and found.where == [path]
    assert found.message == (f"Stage 'only' asked for {path}, which {says}, so "
                             "nothing was freed for it in every histogram.")
    if path == "phases.0.cell.b":
        assert found.suggestion.startswith("Free phases.0.cell.a instead")
    assert not _codes(result, "STAGE_PATH_UNKNOWN")
    assert not _codes(result, "STAGE_FREED_NOTHING")


@pytest.mark.parametrize("turn_on", [
    ["phases.0.atoms.1.dof.*"],
    ["phases.*.atoms.*.x"],
    ["instrument.geometry.sample_displacement"],
    ["phases.0.cell.a", "phases.0.cell.b"],
], ids=["dof-glob", "pattern", "instrument-literal", "tie-beside-source"])
def test_a_joint_plan_that_frees_what_it_names_stays_silent(two_patterns, turn_on):
    """#789's silence cases, jointly.  The fifth, a user's own tie, cannot
    arise: a joint fit has no tie verb."""
    result = _one_stage(two_patterns, turn_on)
    assert not _codes(result, "STAGE_PATH_NOT_FREE")


def test_a_per_histogram_row_is_reported_on_its_own_histogram(two_patterns):
    """A cell made per-histogram is one row per table.  A scoped literal
    addresses one of them, and a bare one both, as ``set_vary`` reads them."""
    sharing = SharingMap(per_histogram=["phases.0.cell.*"])
    scoped = _one_stage(two_patterns, ["hist.1.phases.0.cell.b"], sharing=sharing)
    (found,) = _codes(scoped, "STAGE_PATH_NOT_FREE")
    assert found.where == ["hist.1.phases.0.cell.b"]
    assert found.message.endswith("in histogram 1.")
    assert found.suggestion.startswith("Free hist.1.phases.0.cell.a instead")

    bare = _one_stage(two_patterns, ["phases.0.cell.b"], sharing=sharing)
    assert sorted(d.where[0] for d in _codes(bare, "STAGE_PATH_NOT_FREE")) == [
        "hist.0.phases.0.cell.b", "hist.1.phases.0.cell.b"]
