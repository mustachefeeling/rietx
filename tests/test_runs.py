"""WP-1401 — discovering and reading run directories.

Almost every case here is a fixture directory rather than a fit: the reader's
job is to survive whatever is on disk, and what is on disk is cheaper to write
than to earn. The exception is the last test, which runs a real refinement
through :class:`~rietx.viz.live.LiveSession` so the reader is exercised against
a format a writer really produces rather than one this file invented.
"""

from __future__ import annotations

import fcntl
import io
import json
import shutil
import socket
import threading
from pathlib import Path

import pytest

from rietx import runs


def _write_run(directory: Path, *, events: str = "", status: dict | None = None,
               meta: dict | None = None, lock: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / runs.EVENTS_FILE).write_text(events, encoding="utf-8")
    if status is not None:
        (directory / runs.STATUS_FILE).write_text(json.dumps(status),
                                                  encoding="utf-8")
    if meta is not None:
        (directory / runs.META_FILE).write_text(json.dumps(meta),
                                                encoding="utf-8")
    if lock:
        (directory / runs.LOCK_FILE).write_text("", encoding="utf-8")
    return directory


def _event_line(kind: str, t: float = 1.0, **data) -> str:
    return json.dumps({"record": "event", "v": "2", "t": t, "kind": kind,
                       "data": data}) + "\n"


# ----------------------------------------------------------------------
# discovery
# ----------------------------------------------------------------------
def test_empty_directory_holds_no_runs(tmp_path):
    assert runs.discover(tmp_path) == []


def test_a_directory_with_a_log_is_a_legacy_run(tmp_path):
    """Every run directory in the tree today has no meta.json, and must stay
    visible forever rather than being read as malformed."""
    _write_run(tmp_path / "live", events=_event_line("fit_start"))
    (found,) = runs.discover(tmp_path)
    assert found.legacy is True
    assert found.meta is None
    assert found.label == "live"
    assert found.created > 0        # synthesized from the log's mtime


def test_meta_supplies_label_and_created(tmp_path):
    _write_run(tmp_path / "r", events=_event_line("fit_start"),
               meta={"label": "the overnight ramp", "created": 1234.0})
    (found,) = runs.discover(tmp_path)
    assert found.legacy is False
    assert found.label == "the overnight ramp"
    assert found.created == 1234.0


def test_a_project_is_descended_only_to_its_live_dir(tmp_path):
    """A .rex project is history and exports besides its log, and walking the
    rest is work that can find nothing."""
    project = tmp_path / "sample.rex"
    _write_run(project / "live", events=_event_line("fit_start"))
    (project / "exports").mkdir()
    (project / "exports" / "deep").mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")

    (found,) = runs.discover(tmp_path)
    assert found.path == project / "live"
    # "live" names every project's log and so names none of them
    assert found.label == "sample.rex"


def test_a_run_directory_is_not_descended(tmp_path):
    """One run is one directory; anything below it belongs to that run."""
    outer = _write_run(tmp_path / "r", events=_event_line("fit_start"))
    _write_run(outer / "nested", events=_event_line("fit_start"))
    assert [r.path for r in runs.discover(tmp_path)] == [outer]


def test_root_that_is_itself_a_run(tmp_path):
    """`rietx watch ./live-dir` must keep working: a directory argument that
    *is* a run resolves to that one run."""
    _write_run(tmp_path, events=_event_line("fit_start"))
    (found,) = runs.discover(tmp_path)
    assert found.path == tmp_path


def test_depth_cap_bounds_the_walk(tmp_path):
    deep = tmp_path / "a" / "b" / "c" / "d" / "run"
    _write_run(deep, events=_event_line("fit_start"))
    assert runs.discover(tmp_path, max_depth=2) == []
    assert len(runs.discover(tmp_path, max_depth=8)) == 1


def test_count_cap_bounds_the_walk(tmp_path):
    for i in range(6):
        _write_run(tmp_path / f"r{i}", events=_event_line("fit_start"))
    assert len(runs.discover(tmp_path, max_runs=3)) == 3


def test_pruned_directories_are_never_walked(tmp_path):
    for name in (".git", "node_modules", "__pycache__", ".venv"):
        _write_run(tmp_path / name / "live", events=_event_line("fit_start"))
    assert runs.discover(tmp_path) == []


def test_a_symlink_loop_terminates(tmp_path):
    real = tmp_path / "a"
    _write_run(real / "run", events=_event_line("fit_start"))
    (real / "loop").symlink_to(tmp_path, target_is_directory=True)

    found = runs.discover(tmp_path)          # must return, not spin
    assert [r.path for r in found] == [real / "run"]


def test_runs_come_back_newest_first(tmp_path):
    _write_run(tmp_path / "old", events=_event_line("fit_start"),
               meta={"created": 10.0})
    _write_run(tmp_path / "new", events=_event_line("fit_start"),
               meta={"created": 99.0})
    assert [r.label for r in runs.discover(tmp_path)] == ["new", "old"]


def test_run_ids_are_stable_and_distinct(tmp_path):
    _write_run(tmp_path / "a", events=_event_line("fit_start"))
    _write_run(tmp_path / "b", events=_event_line("fit_start"))
    first = {r.label: r.run_id for r in runs.discover(tmp_path)}
    second = {r.label: r.run_id for r in runs.discover(tmp_path)}
    assert first == second
    assert len(set(first.values())) == 2
    # an id never has to be turned back into a path
    assert all(c in "0123456789abcdef" for c in first["a"])


def test_discover_opens_exactly_two_files_per_run(tmp_path, monkeypatch):
    """A web page polls this. The event log is stat'd and never opened here;
    tail_events opens it, on demand, from an offset."""
    for i in range(3):
        _write_run(tmp_path / f"r{i}", events=_event_line("fit_start"),
                   status={"stage": "cell"})

    opened: list[str] = []
    real_open = io.open

    def counting_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(io, "open", counting_open)
    monkeypatch.setattr("builtins.open", counting_open)
    found = runs.discover(tmp_path)

    assert len(found) == 3
    assert len(opened) == 6, opened
    assert all(Path(p).name in (runs.META_FILE, runs.STATUS_FILE)
               for p in opened), opened


def test_a_cached_walk_opens_two_files_per_changed_run(tmp_path, monkeypatch):
    """The budget above, once a viewer is polling (WP-1427).

    A walk re-reads what it read a second ago, so the cache turns an unchanged
    run into the stats it was going to do anyway. The budget it replaces the
    old one with is per *changed* run, and a run nothing touched is zero files.
    """
    for i in range(3):
        _write_run(tmp_path / f"r{i}", events=_event_line("fit_start"),
                   status={"stage": "cell"})

    opened: list[str] = []
    real_open = io.open

    def counting_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    cache: dict = {}
    runs.discover(tmp_path, cache=cache)              # warm, uncounted

    monkeypatch.setattr(io, "open", counting_open)
    monkeypatch.setattr("builtins.open", counting_open)
    again = runs.discover(tmp_path, cache=cache)
    assert len(again) == 3
    assert opened == [], opened

    # one run writes its status, as a live fit does every cadence
    (tmp_path / "r1" / runs.STATUS_FILE).write_text(
        json.dumps({"stage": "biso", "rwp": 0.2}), encoding="utf-8")
    opened.clear()
    moved = runs.discover(tmp_path, cache=cache)
    assert len(opened) == 2, opened
    assert {Path(p).parent.name for p in opened} == {"r1"}
    assert next(r.status.stage for r in moved if r.path.name == "r1") == "biso"


def test_the_cache_notices_every_file_a_row_is_built_from(tmp_path):
    """A cached row cannot outlive a write to anything it reflects.

    Three files and two flags go into a row, so all five are in the key. The
    snapshot flag is the one a reader would miss: a run gains its picture at
    its first stage boundary, and a row that still said ``has_snapshot: false``
    would leave the page drawing nothing for as long as the fit ran.
    """
    d = _write_run(tmp_path / "r", events=_event_line("fit_start"),
                   status={"stage": "cell"})
    cache: dict = {}
    (before,) = runs.discover(tmp_path, cache=cache)
    assert before.has_snapshot is False

    (d / runs.SNAPSHOT_FILE).write_text("{}", encoding="utf-8")
    (after,) = runs.discover(tmp_path, cache=cache)
    assert after.has_snapshot is True

    # and the log growing is a row change too: `size_bytes` is off its stat
    with open(d / runs.EVENTS_FILE, "a", encoding="utf-8") as fh:
        fh.write(_event_line("fit_end"))
    (grown,) = runs.discover(tmp_path, cache=cache)
    assert grown.size_bytes > after.size_bytes


def test_the_cache_is_pruned_to_what_the_walk_found(tmp_path):
    """A viewer polls a directory where runs come and go, for days."""
    for name in ("a", "b"):
        _write_run(tmp_path / name, events=_event_line("fit_start"))
    cache: dict = {}
    runs.discover(tmp_path, cache=cache)
    assert len(cache) == 2

    shutil.rmtree(tmp_path / "b")
    runs.discover(tmp_path, cache=cache)
    assert {p.name for p in cache} == {"a"}


def test_a_walk_with_no_cache_is_what_it_always_was(tmp_path):
    """The default is no cache, and the answer is the same either way."""
    for i in range(3):
        _write_run(tmp_path / f"r{i}", events=_event_line("fit_start"),
                   status={"stage": "cell"})
    plain = runs.discover(tmp_path)
    cached = runs.discover(tmp_path, cache={})
    assert [r.as_dict() for r in plain] == [r.as_dict() for r in cached]


def test_a_broken_sidecar_costs_progress_not_the_run(tmp_path):
    """A truncated status.json is what a crash leaves behind; losing the whole
    run from the list is the worse answer."""
    directory = _write_run(tmp_path / "r", events=_event_line("fit_start"))
    (directory / runs.STATUS_FILE).write_text('{"stage": "cel',
                                              encoding="utf-8")
    (found,) = runs.discover(tmp_path)
    assert found.status is None


def test_a_status_from_a_newer_writer_is_not_refused(tmp_path):
    """A run directory outlives the version that wrote it, so an unknown key
    must not cost the file (the EventRecord.data rule, one layer out)."""
    _write_run(tmp_path / "r", events=_event_line("fit_start"),
               status={"stage": "cell", "rwp": 0.1, "some_future_field": 42})
    (found,) = runs.discover(tmp_path)
    assert found.status is not None
    assert found.status.stage == "cell"


# ----------------------------------------------------------------------
# liveness
# ----------------------------------------------------------------------
def _one(tmp_path) -> runs.Run:
    return runs.discover(tmp_path)[0]


def test_a_held_lock_reads_running(tmp_path):
    directory = _write_run(tmp_path / "r", events=_event_line("fit_start"),
                           status={"state": "running", "pid": 1}, lock=True)
    handle = open(directory / runs.LOCK_FILE, "r+b")   # the lock, not the text
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert runs.liveness_of(_one(tmp_path)).state == "running"
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def test_a_released_lock_under_a_running_status_reads_abandoned(tmp_path):
    """A third answer, not a rounding of the other two."""
    _write_run(tmp_path / "r", events=_event_line("fit_start"),
               status={"state": "running", "pid": 1}, lock=True)
    live = runs.liveness_of(_one(tmp_path))
    assert live.state == "abandoned"
    assert "lock is free" in live.evidence


def test_a_terminal_state_outranks_the_lock(tmp_path):
    """The writer's own last word beats every inference below it."""
    _write_run(tmp_path / "r", events=_event_line("fit_end"),
               status={"state": "done", "pid": 1}, lock=True)
    assert runs.liveness_of(_one(tmp_path)).state == "done"


@pytest.mark.parametrize("state", ["done", "failed", "cancelled"])
def test_every_terminal_state_survives_the_round_trip(tmp_path, state):
    _write_run(tmp_path / "r", events="", status={"state": state})
    assert runs.liveness_of(_one(tmp_path)).state == state


def test_a_foreign_host_reads_unknown(tmp_path):
    """A pid on another machine names one of our own processes."""
    _write_run(tmp_path / "r", events=_event_line("fit_start"),
               status={"state": "running", "pid": 1, "host": "some-other-box"})
    live = runs.liveness_of(_one(tmp_path))
    assert live.state == "unknown"
    assert "another host" in live.evidence


def test_our_own_host_is_not_foreign(tmp_path):
    _write_run(tmp_path / "r", events=_event_line("fit_start"),
               status={"state": "running", "pid": 1,
                       "host": socket.gethostname()})
    assert runs.liveness_of(_one(tmp_path)).state != "unknown"


def test_a_status_with_no_state_reads_unknown_not_running(tmp_path):
    """Today's LiveSession status.json carries no state at all. A defaulted
    "running" would be an answer about a process that may have died months
    ago (WP-1076)."""
    _write_run(tmp_path / "r", events=_event_line("fit_start"),
               status={"stage": "cell", "rwp": 0.1, "gof": 1.2})
    run = _one(tmp_path)
    assert run.status is not None
    assert run.status.state is None
    assert runs.liveness_of(run).state == "unknown"


def test_a_missing_lock_file_is_not_a_free_lock(tmp_path):
    """No lock file means no writer ever made the claim; a free lock file means
    a writer made it and is gone."""
    _write_run(tmp_path / "r", events=_event_line("fit_start"),
               status={"state": "running", "pid": 999_999})
    live = runs.liveness_of(_one(tmp_path))
    assert live.state == "abandoned"
    assert "999999" in live.evidence       # the pid fallback, not the lock


def test_the_heartbeat_is_reported_and_never_decides(tmp_path):
    """An alive process is evidence; a clock is not."""
    directory = _write_run(tmp_path / "r", events=_event_line("fit_start"),
                           status={"state": "running", "pid": 1,
                                   "heartbeat": 0.0}, lock=True)
    handle = open(directory / runs.LOCK_FILE, "r+b")   # the lock, not the text
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        live = runs.liveness_of(_one(tmp_path), now=1_000_000.0)
        assert live.state == "running"          # despite an ancient heartbeat
        assert live.heartbeat_age == 1_000_000.0
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def test_a_legacy_run_reads_unknown_and_says_so(tmp_path):
    _write_run(tmp_path / "r", events=_event_line("fit_start"))
    live = runs.liveness_of(_one(tmp_path))
    assert live.state == "unknown"
    assert "legacy" in live.evidence


def test_two_readers_do_not_see_each_other(tmp_path):
    """The probe is shared, so one reader is never the other's live writer.

    An exclusive probe is itself a held lock while it runs: two ``rietx watch``
    tabs, or two threads of one server answering ``/api/runs``, would each
    report the other as a process still writing the fit.
    """
    directory = _write_run(tmp_path / "r", events=_event_line("fit_start"),
                           status={"state": "running", "pid": 1}, lock=True)
    path = directory / runs.LOCK_FILE
    seen = []
    ready, go = threading.Event(), threading.Event()

    def other_reader():
        handle = open(path, "rb")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            ready.set()
            go.wait(5)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    thread = threading.Thread(target=other_reader)
    thread.start()
    try:
        assert ready.wait(5)
        seen.append(runs._probe_lock(path))
    finally:
        go.set()
        thread.join(5)
    assert seen == ["free"]                     # not "held": that is a reader


def test_a_lock_file_this_user_cannot_write_is_still_probed(tmp_path):
    """flock needs an open descriptor, not a writable one. Asking for write
    access loses the answer on a run owned by somebody else."""
    directory = _write_run(tmp_path / "r", events=_event_line("fit_start"),
                           status={"state": "running", "pid": 1}, lock=True)
    path = directory / runs.LOCK_FILE
    path.chmod(0o444)
    handle = open(path, "rb")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert runs.liveness_of(_one(tmp_path)).state == "running"
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
        path.chmod(0o644)


def test_a_state_from_a_newer_writer_costs_the_state_and_not_the_row(tmp_path):
    """``state`` is an open vocabulary. A closed ``Literal`` would fail the
    whole file, so the row would lose the stage and the Rwp it can read."""
    _write_run(tmp_path / "r", events=_event_line("fit_start"),
               status={"stage": "cell", "rwp": 0.1, "state": "paused",
                       "pid": 999_999})
    run = _one(tmp_path)
    assert run.status is not None and run.status.stage == "cell"
    assert run.status.state == "paused"
    # not in RUN_STATES, so it makes no claim; the pid is what answers
    assert "paused" not in runs.RUN_STATES
    assert runs.liveness_of(run).state == "abandoned"


# ----------------------------------------------------------------------
# tailing
# ----------------------------------------------------------------------
def test_tail_reads_from_an_offset(tmp_path):
    log = tmp_path / runs.EVENTS_FILE
    log.write_text(_event_line("fit_start") + _event_line("stage_start"),
                   encoding="utf-8")

    first = runs.tail_events(log)
    assert [e["kind"] for e in first.events] == ["fit_start", "stage_start"]
    assert first.offset == log.stat().st_size

    # nothing new
    second = runs.tail_events(log, first.offset, inode=first.inode)
    assert second.events == [] and second.offset == first.offset

    with open(log, "a", encoding="utf-8") as fh:
        fh.write(_event_line("fit_end"))
    third = runs.tail_events(log, second.offset, inode=second.inode)
    assert [e["kind"] for e in third.events] == ["fit_end"]


def test_a_torn_last_line_is_carried_forward_unparsed(tmp_path):
    """A writer flushes per event, but a flush is not an atomic write."""
    log = tmp_path / runs.EVENTS_FILE
    whole = _event_line("fit_start")
    log.write_text(whole + '{"record":"event","kind":"sta', encoding="utf-8")

    tail = runs.tail_events(log)
    assert [e["kind"] for e in tail.events] == ["fit_start"]
    assert tail.offset == len(whole)         # stops before the fragment
    assert tail.bad_lines == 0               # a fragment is not a bad line

    # completing the line delivers it whole, exactly once
    log.write_text(whole + _event_line("stage_start"), encoding="utf-8")
    rest = runs.tail_events(log, tail.offset, inode=tail.inode)
    assert [e["kind"] for e in rest.events] == ["stage_start"]


def test_a_bad_line_is_counted_not_raised(tmp_path):
    """One corrupt line must not cost a viewer the other ten thousand."""
    log = tmp_path / runs.EVENTS_FILE
    log.write_text(_event_line("fit_start") + "}not json{\n"
                   + _event_line("fit_end"), encoding="utf-8")
    tail = runs.tail_events(log)
    assert [e["kind"] for e in tail.events] == ["fit_start", "fit_end"]
    assert tail.bad_lines == 1


def test_truncation_resets_the_cursor(tmp_path):
    """LiveSession truncates the log on construction, so a viewer watching a
    directory across two runs sees exactly this."""
    log = tmp_path / runs.EVENTS_FILE
    log.write_text(_event_line("fit_start") * 5, encoding="utf-8")
    first = runs.tail_events(log)

    log.write_text(_event_line("stage_start"), encoding="utf-8")   # new run
    second = runs.tail_events(log, first.offset, inode=first.inode)
    assert second.reset is True
    assert [e["kind"] for e in second.events] == ["stage_start"]


def test_a_replaced_log_resets_the_cursor(tmp_path):
    """Same size, different inode: an offset that still fits is still wrong."""
    log = tmp_path / runs.EVENTS_FILE
    log.write_text(_event_line("fit_start", t=1.0), encoding="utf-8")
    first = runs.tail_events(log)

    replacement = tmp_path / "other"
    replacement.write_text(_event_line("fit_start", t=1.0) * 2,
                           encoding="utf-8")
    replacement.replace(log)

    second = runs.tail_events(log, first.offset, inode=first.inode)
    assert second.reset is True
    assert len(second.events) == 2


def test_a_capped_tail_keeps_the_newest_and_counts_what_it_dropped(tmp_path):
    """``max_events`` is a tailing viewer's cap, and it is honest about it.

    The pane it exists for holds a fixed number of lines, so every event before
    those is work with no reader. Dropping them *before* the JSON parse is
    where the saving is (WP-1427).
    """
    log = tmp_path / "events.jsonl"
    log.write_text("".join(
        json.dumps({"record": "event", "v": "2", "t": float(i),
                    "kind": "eval", "data": {"i": i}}) + "\n"
        for i in range(500)), encoding="utf-8")

    whole = runs.tail_events(log)
    capped = runs.tail_events(log, max_events=10)

    assert len(whole.events) == 500 and whole.skipped == 0
    assert len(capped.events) == 10
    assert capped.skipped == 490
    assert [e["data"]["i"] for e in capped.events] == list(range(490, 500))
    # the offset walks over everything read, or the next poll re-reads the
    # events this one deliberately dropped, forever
    assert capped.offset == whole.offset


def test_an_uncapped_tail_is_what_it_always_was(tmp_path):
    """The default is no cap. A library function that dropped events unasked
    would be deciding what somebody else's log says."""
    log = tmp_path / "events.jsonl"
    log.write_text("".join(
        json.dumps({"record": "event", "v": "2", "t": float(i),
                    "kind": "eval", "data": {}}) + "\n"
        for i in range(50)), encoding="utf-8")
    tail = runs.tail_events(log)
    assert len(tail.events) == 50
    assert tail.skipped == 0


def test_a_cap_larger_than_the_log_drops_nothing(tmp_path):
    log = tmp_path / "events.jsonl"
    log.write_text(json.dumps({"record": "event", "v": "2", "t": 1.0,
                               "kind": "fit_start", "data": {}}) + "\n",
                   encoding="utf-8")
    tail = runs.tail_events(log, max_events=2000)
    assert len(tail.events) == 1
    assert tail.skipped == 0


def test_tailing_a_missing_log_is_empty_not_an_error(tmp_path):
    tail = runs.tail_events(tmp_path / "nope.jsonl", 0)
    assert tail.events == [] and tail.reset is False


def test_an_empty_log_yields_nothing(tmp_path):
    log = tmp_path / runs.EVENTS_FILE
    log.write_text("", encoding="utf-8")
    tail = runs.tail_events(log)
    assert tail.events == [] and tail.offset == 0


# ----------------------------------------------------------------------
# the CLI view
# ----------------------------------------------------------------------
def test_module_main_prints_the_scanned_root(tmp_path, capsys):
    """An empty list must not read as "no runs exist"."""
    assert runs.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "scanned" in out and str(tmp_path.resolve()) in out
    assert "no runs found" in out


def test_module_main_lists_a_run(tmp_path, capsys):
    _write_run(tmp_path / "live", events=_event_line("fit_start"),
               status={"stage": "profile", "rwp": 0.0821})
    assert runs.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "live" in out and "profile" in out
    # a percentage, as the watcher page and the GUI print one (WP-1424); the
    # fraction is the report layers' form, for quoting into prose
    assert "8.21%" in out and "0.0821" not in out
    assert "1 run(s)" in out


def test_module_main_names_a_series_member_by_its_pattern(tmp_path, capsys):
    """The text twin of the page's run column, and the same defect.

    Every run of a batch is called after the directory it was launched from,
    so a column of labels names nothing. The series label is the one fact in
    the record that separates runs by the work rather than by the clock, and
    the CLI table takes it for the same reason the page does (WP-1424).
    """
    for i, pattern in enumerate(("cpd-1a", "cpd-1b")):
        _write_run(tmp_path / f"run-{i}", events=_event_line("fit_start"),
                   status={"stage": "cell", "rwp": 0.1734,
                           "series_label": pattern})
    assert runs.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "cpd-1a" in out and "cpd-1b" in out
    assert "17.34%" in out


# ----------------------------------------------------------------------
# against a format a writer really produces
# ----------------------------------------------------------------------
def test_reads_a_directory_a_real_live_session_wrote(tmp_path):
    """The reader is built against a live format, not an invented one."""
    import rietx as rx
    from rietx.viz.live import LiveSession
    from tests.test_refine_synthetic import perturbed_models, synthesize

    structure, instrument = perturbed_models()
    project = tmp_path / "sample.rex"
    live = project / "live"
    rx.Refinement(structure, instrument, history=False).fit(
        synthesize(), events=LiveSession(live))

    (found,) = runs.discover(tmp_path)
    assert found.path == live
    assert found.label == "sample.rex"       # not "live"
    assert found.legacy is True              # nothing writes meta.json yet
    assert found.has_snapshot is True        # LiveSession wrote snapshot.json
    assert found.has_legacy_snapshot is False   # and no fit.html, since 1402
    assert found.status is not None
    assert found.status.stage == "profile"   # the plan's last stage
    assert found.status.state is None        # and it declares no state
    assert runs.liveness_of(found).state == "unknown"

    tail = runs.tail_events(live / runs.EVENTS_FILE)
    kinds = [e["kind"] for e in tail.events]
    assert kinds[0] == "fit_start" and kinds[-1] == "fit_end"
    assert tail.bad_lines == 0
    assert tail.offset == (live / runs.EVENTS_FILE).stat().st_size
