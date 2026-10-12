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

from rietx import MultiHistogramRefinement, Stage, runs
from rietx.history.events import read_events
from rietx.optimize.cancel import CancelToken, RefinementCancelled
from rietx.optimize.statistics import MAX_SHIFT_CONVERGED
from rietx.strategy.staged import RefinementPlan
from tests.test_multi_histogram import perturbed_inputs, synthesize

OUT = Path(__file__).parent / "output"

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
    done.fit(two_patterns, plan=RefinementPlan(stages=plan.stages[:2],
                                               intermediate_ftol=None))
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
