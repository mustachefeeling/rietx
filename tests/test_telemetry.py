"""WP-1403 — a fit nobody asked to record records itself.

The premise is a measurement, not a preference. WP-1322 gave three independent
subagents a benchmarking task and no instructions about how to drive rietx; all
three found and read the packaged skill in full, and all three wrote
``history=False``. Reconstructing timing from their own transcripts afterwards
recovered 2.7-16.6 % coverage and nothing from inside a solve. Documenting the
knob harder is the fix that had already been tried, and an agent cannot switch
off by accident what it never had to switch on.

So the assertions here are mostly about what recording must **never** cost:
a fit that carries on when the directory is read-only, a caller's exception
that still reaches them, and a suite that grows no directories at all. The one
positive claim — the four files land and the watcher lists them — is the
acceptance, and it is asserted through ``runs.discover`` rather than by
building paths, because "the watcher lists it" is the thing that was promised.

Recording is **off** for the suite (``conftest``), so every test that wants it
takes the ``recording`` fixture. ``test_the_suite_itself_records_nothing`` is
the meta-test for the other direction: without it the suite would grow hundreds
of run directories the first time somebody changed the default.
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

import pytest

import rietx as rx
from rietx import runs
from rietx._about import RUNS_DIR_NAME, STATE_DIR_NAME, TELEMETRY_ENV
from rietx.history.events import EventStream, read_events
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("telemetry")


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture
def recording():
    """Switch recording on for one test, and put it back.

    ``runs.set_enabled`` rather than the environment: it is the seam that
    exists for this, it mirrors ``model.compiled.set_enabled``, and it cannot
    leak into another xdist worker the way an ``os.environ`` write can.
    """
    was = runs.set_enabled(True)
    runs._PRUNED = False
    runs._WARNED = False
    try:
        yield
    finally:
        runs.set_enabled(was)


def _fit(pattern, **kw):
    structure, ins = perturbed_models()
    return rx.Refinement(structure, ins, history=False).fit(pattern, **kw)


# ----------------------------------------------------------------------
# the acceptance
# ----------------------------------------------------------------------
def test_a_plain_fit_in_an_empty_directory_is_a_run_the_watcher_lists(
        tmp_path, monkeypatch, pattern, recording):
    """WP-1403's acceptance, asserted the way it is written."""
    monkeypatch.chdir(tmp_path)
    result = _fit(pattern)

    (run,) = runs.discover(tmp_path)
    assert run.path.parent == tmp_path / STATE_DIR_NAME / RUNS_DIR_NAME
    assert runs.RUN_ID_RE.match(run.path.name)
    assert run.legacy is False

    for name in (runs.EVENTS_FILE, runs.META_FILE, runs.STATUS_FILE,
                 runs.SNAPSHOT_FILE, runs.SUMMARY_FILE):
        assert (run.path / name).is_file(), name

    assert run.meta is not None and run.meta.record == runs.RECORD_TAG
    assert run.meta.cwd == str(tmp_path)
    assert run.status is not None
    assert run.status.state == "done"
    assert run.status.error is None
    assert run.status.pid == os.getpid()
    assert run.status.rwp == pytest.approx(result.statistics.rwp)
    assert runs.liveness_of(run).state == "done"


def test_the_root_hides_itself_from_git(tmp_path, monkeypatch, pattern,
                                        recording):
    """A fit inside somebody's repository does not turn up in their status."""
    monkeypatch.chdir(tmp_path)
    _fit(pattern)
    root = tmp_path / STATE_DIR_NAME / RUNS_DIR_NAME
    assert (root / runs.GITIGNORE_FILE).read_text().strip() == "*"


def test_summary_is_the_termination_view_and_not_a_report(
        tmp_path, monkeypatch, pattern, recording):
    """``str(result)``, never ``ref.summary()`` — the expensive half (WP-1335)."""
    monkeypatch.chdir(tmp_path)
    result = _fit(pattern)
    (run,) = runs.discover(tmp_path)
    assert (run.path / runs.SUMMARY_FILE).read_text() == str(result)


def test_the_status_rwp_is_the_last_stage_end_in_the_log(
        tmp_path, monkeypatch, pattern, recording):
    """A projection, never a computation.

    The final ``rwp`` comes off ``fit_end`` — the fitted result's own number —
    and the stage before it off the last ``stage_end``. Both are copied from
    the event that carried them, so the file and the log cannot disagree.
    """
    monkeypatch.chdir(tmp_path)
    _fit(pattern)
    (run,) = runs.discover(tmp_path)
    log = read_events(run.path / runs.EVENTS_FILE)
    ends = [e for e in log if e.kind == "fit_end"]
    assert len(ends) == 1
    assert run.status.rwp == pytest.approx(ends[0].data["rwp"])
    assert run.status.gof == pytest.approx(ends[0].data["gof"])

    stage_ends = [e for e in log if e.kind == "stage_end"]
    assert stage_ends, "a staged plan emitted no stage_end"
    assert run.status.stage == stage_ends[-1].data["stage"]


def test_the_stage_number_is_read_off_index_and_never_counted(
        tmp_path, monkeypatch, pattern, recording):
    """WP-1301's trap: a released phase emits a *second* ``stage_start``.

    A counter would say "stage 6 of 5" the first time that happens. This
    asserts the mechanism rather than waiting for a phase release: the status
    agrees with the last ``stage_start``'s own ``index``, whatever the number
    of ``stage_start`` events was.
    """
    monkeypatch.chdir(tmp_path)
    _fit(pattern)
    (run,) = runs.discover(tmp_path)
    starts = [e for e in read_events(run.path / runs.EVENTS_FILE)
              if e.kind == "stage_start"]
    assert run.status.index == starts[-1].data["index"]
    assert run.status.n_stages == starts[-1].data["n_stages"]
    assert run.status.index <= run.status.n_stages


def test_run_stage_records_a_run_with_a_picture(tmp_path, monkeypatch, pattern,
                                                recording):
    """One stage driven on its own is a run, and it has a snapshot (WP-1402)."""
    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    ref.run_stage(pattern, rx.Stage(name="background",
                                    turn_on=["instrument.background.*"]))
    (run,) = runs.discover(tmp_path)
    assert run.has_snapshot is True
    payload = json.loads((run.path / runs.SNAPSHOT_FILE).read_text())
    assert payload["stage"] == "background"
    assert payload["y_calc"] and payload["two_theta"]


# ----------------------------------------------------------------------
# declining
# ----------------------------------------------------------------------
def test_telemetry_false_writes_nothing(tmp_path, monkeypatch, pattern,
                                        recording):
    monkeypatch.chdir(tmp_path)
    _fit(pattern, telemetry=False)
    assert list(tmp_path.rglob("*")) == []


def test_the_env_switch_writes_nothing_and_outranks_the_keyword(
        tmp_path, monkeypatch, pattern):
    """There is deliberately no ``telemetry=`` that argues back.

    Somebody who set the variable wants their disk left alone everywhere, so a
    library call that could override them would make the switch a suggestion.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(TELEMETRY_ENV, "0")
    monkeypatch.setattr(runs, "_ENABLED", None)
    assert runs.enabled() is False
    _fit(pattern, telemetry=str(tmp_path / "named"))
    assert list(tmp_path.rglob("*")) == []


def test_the_suite_itself_records_nothing(tmp_path, monkeypatch, pattern):
    """The meta-test conftest's ``setdefault`` exists for.

    Without it the suite grows a run directory per fit — in whatever directory
    pytest was launched from — the first time somebody changes the default.
    This deliberately takes **no** ``recording`` fixture: it asserts the
    suite's own environment.
    """
    assert os.environ.get(TELEMETRY_ENV) == "0"
    monkeypatch.chdir(tmp_path)
    _fit(pattern)
    assert list(tmp_path.rglob("*")) == [], (
        "a fit under the suite's environment left files behind")


# ----------------------------------------------------------------------
# composition: the caller keeps everything they asked for
# ----------------------------------------------------------------------
def test_a_callers_path_still_gets_a_complete_log_and_the_recorder_its_own(
        tmp_path, monkeypatch, pattern, recording):
    """Two logs, both complete, neither one a truncation of the other."""
    monkeypatch.chdir(tmp_path)
    mine = tmp_path / "mine.jsonl"
    _fit(pattern, events=mine)

    (run,) = runs.discover(tmp_path)
    theirs = [e.kind for e in read_events(mine)]
    ours = [e.kind for e in read_events(run.path / runs.EVENTS_FILE)]
    assert theirs[0] == "fit_start" and theirs[-1] == "fit_end"
    assert ours == theirs, "the two logs recorded different runs"
    assert "eval" in ours


def test_a_callers_event_stream_keeps_its_identity(tmp_path, monkeypatch,
                                                   pattern, recording):
    """``fit`` closes its stream only ``if stream is not events``.

    That identity test is why ``sequential._SeriesStream`` is a subclass, and
    nothing here may disturb it: a caller who passed a stream still owns it,
    and still finds it open afterwards.
    """
    monkeypatch.chdir(tmp_path)
    seen = []
    stream = EventStream(callback=seen.append)
    _fit(pattern, events=stream)
    assert stream._fh is None          # never had a file; never closed by us
    assert [e["kind"] for e in seen][0] == "fit_start"
    assert [e["kind"] for e in seen][-1] == "fit_end"

    (run,) = runs.discover(tmp_path)
    ours = [e.kind for e in read_events(run.path / runs.EVENTS_FILE)]
    assert ours == [e["kind"] for e in seen]


def test_a_callers_callback_exception_still_propagates(tmp_path, monkeypatch,
                                                       pattern, recording):
    """``events.py``'s rule is untouched: a monitoring hook that crashes the
    refinement is a bug you want to see, not swallow.

    Direction one of two. The recorder is attached unasked and latches its own
    failures; a callback reached through ``events=`` is the caller's code and
    runs outside every try block in the recorder.
    """
    monkeypatch.chdir(tmp_path)

    class Boom(RuntimeError):
        pass

    def hostile(event):
        if event["kind"] == "stage_end":
            raise Boom("the caller's hook")

    with pytest.raises(Boom):
        _fit(pattern, events=hostile)


def test_a_latched_recorder_still_runs_the_callers_callback(
        tmp_path, monkeypatch, pattern, recording):
    """Direction two: the recorder giving up costs the caller nothing."""
    monkeypatch.chdir(tmp_path)
    seen = []
    stream = EventStream(callback=seen.append)
    recorder = runs.attach(stream, stream, telemetry=str(tmp_path / "t"))
    assert recorder is not None
    recorder._latch(OSError("disk went away"), "testing")
    assert recorder.error is not None

    stream.emit("fit_start", mode="rietveld")
    stream.emit("fit_end", status="converged")
    assert [e["kind"] for e in seen] == ["fit_start", "fit_end"]


def test_a_read_only_directory_declines_and_the_fit_still_returns(
        tmp_path, monkeypatch, pattern, recording):
    """The whole point. A fit that dies over a directory nobody requested is
    the package breaking a working call for its own convenience.

    This is the failure *before* a recorder exists — choosing the root and
    making the directory happen in ``attach``, where no latch can reach them.
    The first version of this test found exactly that hole: the
    ``PermissionError`` propagated and took the fit with it.
    """
    monkeypatch.chdir(tmp_path)
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o500)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = _fit(pattern, telemetry=str(blocked / "runs"))
    finally:
        blocked.chmod(0o700)

    assert result.status == "converged"
    assert result.statistics.rwp < 0.2
    messages = [str(w.message) for w in caught
                if str(w.message).startswith("telemetry ")]
    assert len(messages) == 1, messages          # one a process, not one a run
    assert TELEMETRY_ENV in messages[0]          # and it says how to stop it


def test_a_recorder_that_breaks_mid_run_latches_and_says_why(
        tmp_path, monkeypatch, pattern, recording):
    """The failure *after* the directory exists: the latch proper.

    Its reason reaches ``status.json``, because a latch that went quiet would
    be WP-1076's field whose empty state reads as an answer — a run that
    stopped recording would look like one that recorded everything.
    """
    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)

    stream = EventStream()
    recorder = runs.attach(stream, stream, telemetry=str(tmp_path / "t"))
    assert recorder is not None
    recorder._fh = None                      # what a vanished mount looks like
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = ref.fit(pattern, events=stream)
        recorder.close()

    assert result.status == "converged"
    assert recorder.error is not None
    status = json.loads((recorder.dir / runs.STATUS_FILE).read_text())
    assert status["error"] == recorder.error
    assert status["state"] == "running"      # it never got to say otherwise


# ----------------------------------------------------------------------
# attach exactly once
# ----------------------------------------------------------------------
def test_a_series_records_one_run_and_not_one_per_pattern(
        tmp_path, monkeypatch, pattern, recording):
    """A 60-pattern series would otherwise make 60 directories for one job.

    Each pattern's fit is handed a **fresh** ``_SeriesStream`` wrapping the one
    stream the series owns, so the stamp has to be looked for through the
    ``_inner`` chain rather than on the object handed in.
    """
    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()
    series = rx.SequentialRefinement(structure, ins, history=False)
    series.fit([pattern, pattern, pattern], x=[300.0, 400.0, 500.0], x_label="T")

    found = runs.discover(tmp_path)
    assert len(found) == 1, [str(r.path) for r in found]
    starts = [e for e in read_events(found[0].path / runs.EVENTS_FILE)
              if e.kind == "fit_start"]
    assert len(starts) == 3
    assert [e.data["series_index"] for e in starts] == [0, 1, 2]


def test_attach_declines_when_one_is_already_in_the_chain():
    """The stamp, on its own, without a fit to produce one."""

    class Wrapper(EventStream):
        def __init__(self, inner):
            super().__init__()
            self._inner = inner

    outer = EventStream()
    first = runs.attach(outer, outer, telemetry="unused")
    assert first is None or True     # attach may be disabled; force the path
    assert runs._already_recorded(outer) == (first is not None)

    setattr(outer, runs._STAMP, object())
    assert runs._already_recorded(outer) is True
    assert runs._already_recorded(Wrapper(outer)) is True
    assert runs._already_recorded(Wrapper(Wrapper(outer))) is True
    assert runs._already_recorded(EventStream()) is False
    assert runs._already_recorded(None) is False


def test_the_chain_walk_survives_a_cycle():
    """Telemetry must never hang a fit, and a cycle here would."""
    a, b = EventStream(), EventStream()
    a._inner, b._inner = b, a
    assert runs._already_recorded(a) is False


# ----------------------------------------------------------------------
# retention
# ----------------------------------------------------------------------
def _stub_run(root: Path, name: str, *, created: float, state="done",
              meta=True, size=1000) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / runs.EVENTS_FILE).write_text("x" * size, encoding="utf-8")
    if meta:
        (d / runs.META_FILE).write_text(
            json.dumps({"record": runs.RECORD_TAG, "created": created}),
            encoding="utf-8")
    if state is not None:
        (d / runs.STATUS_FILE).write_text(json.dumps({"state": state}),
                                          encoding="utf-8")
    return d


NOW = 1_800_000_000.0
DAY = 86400.0


def test_retention_takes_the_oldest_terminal_runs_until_it_is_under(tmp_path):
    root = tmp_path / "runs"
    made = [_stub_run(root, f"2026010{i + 1}-120000-{i}",
                      created=NOW - 30 * DAY + i) for i in range(5)]
    removed = runs.prune(root, max_bytes=3500, now=NOW)
    assert [p.name for p in removed] == [made[0].name, made[1].name]
    assert sorted(p.name for p in root.iterdir()) == [m.name for m in made[2:]]


def test_a_batch_still_running_loses_nothing(tmp_path):
    """The design this rule exists for.

    "Keep the newest N" would delete run 1 of a 200-candidate batch while the
    batch was still running, and a batch is one of the cases recording exists
    for.
    """
    root = tmp_path / "runs"
    for i in range(200):
        _stub_run(root, f"20260101-1200{i:02d}-{i}", created=NOW - 60,
                  size=10_000)
    assert runs.prune(root, max_bytes=1000, now=NOW) == []
    assert len(list(root.iterdir())) == 200


def test_a_root_over_the_ceiling_with_nothing_old_enough_warns_and_keeps(
        tmp_path):
    root = tmp_path / "runs"
    for i in range(3):
        _stub_run(root, f"2026010{i + 1}-120000-{i}", created=NOW - 60)
    runs._WARNED = False
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert runs.prune(root, max_bytes=1, now=NOW) == []
    assert len(list(root.iterdir())) == 3
    assert len(caught) == 1 and "Keeping it" in str(caught[0].message)


@pytest.mark.parametrize("why,kw,name", [
    ("legacy: no meta.json", {"meta": False}, "20260101-120000-1"),
    ("still running", {"state": "running"}, "20260102-120000-2"),
    ("no state recorded", {"state": None}, "20260103-120000-3"),
    ("not a run-id name", {}, "important-data"),
])
def test_what_is_never_pruned(tmp_path, why, kw, name):
    """Each of these survives a ceiling of one byte and a month of age."""
    root = tmp_path / "runs"
    spared = _stub_run(root, name, created=NOW - 30 * DAY, **kw)
    doomed = _stub_run(root, "20251201-120000-9", created=NOW - 60 * DAY)
    runs._WARNED = False
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        removed = runs.prune(root, max_bytes=1, now=NOW)
    assert spared.exists(), why
    assert not doomed.exists(), "the prune did not run at all"
    assert [p.name for p in removed] == [doomed.name]


def test_a_meta_without_the_record_tag_is_never_pruned(tmp_path):
    """The interlock the tag is declared for."""
    root = tmp_path / "runs"
    spared = _stub_run(root, "20260101-120000-1", created=NOW - 30 * DAY)
    (spared / runs.META_FILE).write_text(json.dumps({"created": NOW - 30 * DAY}),
                                         encoding="utf-8")
    runs._WARNED = False
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        runs.prune(root, max_bytes=1, now=NOW)
    assert spared.exists()


def test_a_run_one_level_deeper_is_out_of_reach(tmp_path):
    """The direct-child guard, which is what bounds the blast radius."""
    root = tmp_path / "runs"
    nested = _stub_run(root / "sub", "20260101-120000-1", created=NOW - 30 * DAY)
    runs._WARNED = False
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        runs.prune(root, max_bytes=1, now=NOW)
    assert nested.exists()
