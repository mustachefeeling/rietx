"""Run control: single-stage telemetry, progress fields, cancellation.

WP-1006.  The GUI is the reason these exist, but nothing here is GUI-shaped:
a token, an exception carrying what completed, and two more event fields.
"""

from __future__ import annotations

import pytest

import rietx as pr
from rietx.history.events import (
    EVENT_SCHEMA_VERSION,
    EventKind,
    read_events,
)
from rietx.optimize.cancel import CancelToken, RefinementCancelled
from tests.test_refine_synthetic import perturbed_models, synthesize

PLAN = pr.RefinementPlan(stages=[
    pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=30),
    pr.Stage("zero", ["instrument.zero_shift"], max_iter=30),
    pr.Stage("cell", ["phases.*.cell.*"], max_iter=30),
])


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture
def ref():
    structure, ins = perturbed_models()
    return pr.Refinement(structure, ins)


def collect(events: list) -> dict[str, list[dict]]:
    """Group emitted event dicts by kind."""
    out: dict[str, list[dict]] = {}
    for e in events:
        out.setdefault(e["kind"], []).append(e["data"])
    return out


# ------------------------------------------------------------------ streaming
def test_run_stage_streams_events(ref, pattern):
    """Interactive single-stage work was the one blind path."""
    seen: list[dict] = []
    ref.run_stage(pattern, PLAN.stages[0], events=seen.append)
    by_kind = collect(seen)
    assert by_kind["stage_start"] and by_kind["eval"] and by_kind["stage_end"]
    assert by_kind["stage_start"][0]["stage"] == "scale_bkg"
    assert by_kind["stage_end"][0]["status"] in {"converged", "max_iter"}
    # a single stage is stage 1 of 1 — the field is there either way, so a
    # client renders progress without knowing which verb it called
    assert by_kind["stage_start"][0] == dict(by_kind["stage_start"][0],
                                             index=1, n_stages=1)
    # ...and no fit_start/fit_end: run_stage is a stage, not a run
    assert "fit_start" not in by_kind and "fit_end" not in by_kind


def test_run_stage_writes_a_readable_log(ref, pattern, tmp_path):
    path = tmp_path / "events.jsonl"
    ref.run_stage(pattern, PLAN.stages[0], events=path)
    records = read_events(path)
    assert [r.kind for r in records][:1] == ["stage_start"]
    assert all(r.v == EVENT_SCHEMA_VERSION for r in records)


def test_stage_start_carries_progress(ref, pattern):
    seen: list[dict] = []
    ref.fit(pattern, plan=PLAN, events=seen.append)
    starts = collect(seen)["stage_start"]
    assert [d["index"] for d in starts] == [1, 2, 3]
    assert {d["n_stages"] for d in starts} == {3}
    assert [d["stage"] for d in starts] == [s.name for s in PLAN.stages]


def test_progress_fields_are_additive_not_a_version_bump(ref, pattern):
    """The rule the note in history/events.py states, made executable.

    A reader that knows only the pre-WP-1006 fields must still parse every
    line — which is what makes an added field compatible and a bumped version
    unnecessary.

    The version is asserted against the live constant rather than a literal.  It
    pinned ``"1"`` until WP-1024, which is what a *correct* bump looks like from
    this test's side: the constant moved because ``index_start``/``index_end`` are
    new **kinds** (see :func:`test_a_new_kind_is_what_the_version_is_for`), and
    this test's own subject — added fields on ``stage_start`` — never moved it.
    A literal here would fail on every legitimate bump and so would train the
    next session to edit the assertion rather than to ask which rule applied.
    """
    seen: list[dict] = []
    ref.run_stage(pattern, PLAN.stages[0], events=seen.append)
    assert all(e["v"] == EVENT_SCHEMA_VERSION for e in seen)
    old_reader_keys = {"stage", "turn_on", "freed", "n_free", "n_points"}
    start = collect(seen)["stage_start"][0]
    assert old_reader_keys <= set(start)  # nothing it knew about was removed


def test_a_new_kind_is_what_the_version_is_for():
    """The other side of the same rule: the kind set and the version move together.

    ``EventKind`` is a closed Literal, and WP-1006 deliberately did *not* add an
    ``"index"`` kind in advance — a kind nothing emits is an untested guess about
    a loop that does not exist.  WP-1024 built the loop (``index_pattern``) and
    added the pair, so the constant is ``"2"``.  Pinning both here means a future
    session cannot add a kind without deciding about the version, which is the
    failure the note in ``history/events.py`` was written against.
    """
    from typing import get_args

    kinds = set(get_args(EventKind))
    assert {"index_start", "index_end"} <= kinds
    assert EVENT_SCHEMA_VERSION == "2"


def test_readers_validate_the_envelope_not_the_payload(tmp_path):
    """The other half of the additivity rule: a key nobody knows still parses.

    ``data`` is an open dict, so a log written by a newer version — or by a
    future run kind — reads back on an older reader instead of failing
    validation.  That is what makes an added field a non-event.
    """
    from rietx.history.events import EventStream

    path = tmp_path / "events.jsonl"
    with EventStream(path=path) as stream:
        stream.emit("stage_start", stage="x", index=1, n_stages=1,
                    engine="dichotomy", not_a_field_anyone_knows=[1, 2])
    (record,) = read_events(path)
    assert record.data["not_a_field_anyone_knows"] == [1, 2]


# --------------------------------------------------------------- cancellation
class TripAt:
    """Set a token after ``n`` residual evaluations, counting them all."""

    def __init__(self, token: CancelToken, n: int):
        self.token, self.n, self.n_eval = token, n, 0
        self.after_trip = 0

    def __call__(self, event: dict) -> None:
        if event["kind"] != "eval":
            return
        self.n_eval += 1
        if self.token.is_set():
            self.after_trip += 1
        elif self.n_eval >= self.n:
            self.token.cancel()


def test_cancel_stops_within_two_further_evals(ref, pattern):
    token = CancelToken()
    trip = TripAt(token, 5)
    with pytest.raises(RefinementCancelled):
        ref.fit(pattern, plan=PLAN, events=trip, cancel=token)
    # the check precedes the evaluation, so the very next one raises before
    # emitting anything — the WP's bar was ≤2 and there is room to spare
    assert trip.after_trip == 0, "cancellation is checked at eval boundaries"


@pytest.mark.parametrize("solver", ["trf", "lm"])
def test_cancel_reports_what_completed(pattern, solver):
    """The caller must learn where the working state stands, on both drivers."""
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins, solver=solver)
    token = CancelToken()
    # let the first stage finish, then cancel inside the second
    state = {"stage": None}

    def watch(event: dict) -> None:
        if event["kind"] == "stage_start":
            state["stage"] = event["data"]["stage"]
        if event["kind"] == "eval" and state["stage"] == "zero":
            token.cancel()

    with pytest.raises(RefinementCancelled) as err:
        ref.fit(pattern, plan=PLAN, events=watch, cancel=token)
    exc = err.value
    assert exc.stage == "zero"
    assert [s.name for s in exc.completed_stages] == ["scale_bkg"]
    # the working state is the last completed node, and it is a checkout target
    assert exc.node_id is not None
    assert ref.history[exc.node_id].action.name == "scale_bkg"


def test_cancelled_stage_leaves_no_node_and_no_commit(ref, pattern):
    token = CancelToken()

    def watch(event: dict) -> None:
        if event["kind"] == "eval":
            token.cancel()

    ref.fit(pattern, plan=pr.RefinementPlan(stages=PLAN.stages[:1]))
    n_nodes, head = len(ref.history), ref.history.head
    before = ref.structure.phases[0].cell.a.value

    with pytest.raises(RefinementCancelled):
        ref.run_stage(pattern, PLAN.stages[2], events=watch, cancel=token)
    assert len(ref.history) == n_nodes, "an abandoned stage records no node"
    assert ref.history.head == head
    assert ref.structure.phases[0].cell.a.value == before


def test_cancelled_stage_does_not_leave_its_seed_behind(ref, pattern):
    """A seeding stage writes to the models *before* solving.

    Extinction starts at exactly 0 and the stage lifts it off the softplus
    dead-gradient floor; that write happens at the recompile, before the first
    residual evaluation.  Abandoning the stage has to undo it, or a cancelled
    run leaves a parameter at a value nobody chose.
    """
    token = CancelToken()

    def watch(event: dict) -> None:
        if event["kind"] == "eval":
            token.cancel()

    assert ref.structure.phases[0].extinction.value == 0.0
    with pytest.raises(RefinementCancelled):
        ref.run_stage(pattern,
                      pr.Stage("extinction", ["phases.*.extinction"], seed=1e-3),
                      events=watch, cancel=token)
    assert ref.structure.phases[0].extinction.value == 0.0


def test_cancel_emits_stage_end_and_fit_end(ref, pattern):
    token = CancelToken()
    seen: list[dict] = []

    def watch(event: dict) -> None:
        seen.append(event)
        if event["kind"] == "eval":
            token.cancel()

    with pytest.raises(RefinementCancelled):
        ref.fit(pattern, plan=PLAN, events=watch, cancel=token)
    by_kind = collect(seen)
    assert by_kind["stage_end"][-1]["status"] == "cancelled"
    assert by_kind["fit_end"][-1]["status"] == "cancelled"
    # no result exists, so no rwp is reported — readers use .get, not unpacking
    assert "rwp" not in by_kind["fit_end"][-1]


def test_an_unset_token_costs_nothing_semantically(ref, pattern):
    """Passing a token that is never set must not change the answer."""
    result = ref.fit(pattern, plan=PLAN, cancel=CancelToken())
    structure, ins = perturbed_models()
    plain = pr.Refinement(structure, ins).fit(pattern, plan=PLAN)
    assert result.statistics.rwp == plain.statistics.rwp
    assert (result.parameters[0].value, result.parameters[0].path) == (
        plain.parameters[0].value, plain.parameters[0].path)


def test_token_is_reusable(ref, pattern):
    token = CancelToken()
    token.cancel()
    assert token.is_set() and bool(token)
    with pytest.raises(RefinementCancelled):
        ref.fit(pattern, plan=PLAN, cancel=token)
    token.reset()
    assert not token.is_set()
    assert ref.fit(pattern, plan=PLAN, cancel=token).statistics.rwp > 0


def test_a_deadline_serves_as_a_fit_cancel_token(ref, pattern):
    """WP-1037: the indexing ``Deadline`` duck-types ``CancelToken`` at every
    consumer, including the solver's ``.is_set()`` read here — which is the
    property that puts a Le Bail validation inside the whole-run ceiling with
    no solver changes.  An expired one cancels the fit; an unexpired one costs
    nothing (the same claim ``test_an_unset_token_costs_nothing`` makes for
    the real token)."""
    from rietx.indexing.engines import Deadline

    with pytest.raises(RefinementCancelled):
        ref.fit(pattern, plan=PLAN, cancel=Deadline(1e-9))
    result = ref.fit(pattern, plan=PLAN, cancel=Deadline(3600.0))
    assert result.statistics.rwp > 0
