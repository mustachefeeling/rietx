"""WP-1401 — the ``rietx watch`` app: the run list, and the routes under it.

``watch.py`` is transport, so these tests are about what the routes send.
What they send it *about* is :mod:`rietx.runs`, tested next door.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest

from rietx import runs
from rietx.watch import main, serve


@contextmanager
def _served(directory: Path):
    server = serve(directory, port=0, block=False)   # port 0 → ephemeral
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _get(url: str) -> bytes:
    return urllib.request.urlopen(url, timeout=5).read()


def _json(url: str):
    return json.loads(_get(url).decode("utf-8"))


def _event_line(kind: str, t: float = 1.0, **data) -> str:
    return json.dumps({"record": "event", "v": "2", "t": t, "kind": kind,
                       "data": data}) + "\n"


def _make_run(directory: Path, *, events: str = "", status: dict | None = None,
              snapshot: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / runs.EVENTS_FILE).write_text(events, encoding="utf-8")
    if status is not None:
        (directory / runs.STATUS_FILE).write_text(json.dumps(status),
                                                  encoding="utf-8")
    if snapshot:
        (directory / runs.SNAPSHOT_FILE).write_text(
            "<html>plotly goes here</html>", encoding="utf-8")
    return directory


# ----------------------------------------------------------------------
# the page
# ----------------------------------------------------------------------
def test_index_is_served(tmp_path):
    with _served(tmp_path) as base:
        page = _get(base + "/").decode()
    assert "rietx watch" in page
    assert "api/runs" in page
    # polling stops when nobody is looking
    assert "document.hidden" in page and "visibilitychange" in page


def test_the_page_reports_the_root_it_scanned(tmp_path):
    """An empty list must not read as "no runs exist"."""
    with _served(tmp_path) as base:
        page = _get(base + "/").decode()
        payload = _json(base + "/api/runs")
    assert "scanned " in page
    assert payload["root"] == str(tmp_path.resolve())
    assert payload["runs"] == []


# ----------------------------------------------------------------------
# /api/runs
# ----------------------------------------------------------------------
def test_api_runs_lists_every_run_with_its_liveness(tmp_path):
    _make_run(tmp_path / "one", events=_event_line("fit_start"),
              status={"stage": "cell", "rwp": 0.11})
    _make_run(tmp_path / "two", events=_event_line("fit_start"))

    with _served(tmp_path) as base:
        payload = _json(base + "/api/runs")

    assert len(payload["runs"]) == 2
    labels = {r["label"] for r in payload["runs"]}
    assert labels == {"one", "two"}
    for row in payload["runs"]:
        assert row["liveness"]["state"] == "unknown"    # legacy, no lock
        assert row["liveness"]["evidence"]              # always says why
        assert row["legacy"] is True


def test_a_project_run_carries_the_gui_command(tmp_path):
    """A command a human copies, not a verb this app performs."""
    _make_run(tmp_path / "sample.rex" / "live",
              events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
    assert row["label"] == "sample.rex"
    assert row["gui_command"] == "rietx gui sample.rex"


def test_a_plain_run_offers_no_gui_command(tmp_path):
    _make_run(tmp_path / "live-dir", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
    assert row["gui_command"] is None


def test_a_directory_that_is_a_run_opens_straight_onto_it(tmp_path):
    """`rietx watch ./live-dir` keeps working unchanged."""
    _make_run(tmp_path, events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        payload = _json(base + "/api/runs")
    assert len(payload["runs"]) == 1
    assert payload["single_run_id"] == payload["runs"][0]["run_id"]


def test_a_scanned_tree_has_no_single_run(tmp_path):
    _make_run(tmp_path / "only", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        payload = _json(base + "/api/runs")
    assert payload["single_run_id"] is None


# ----------------------------------------------------------------------
# /api/run/<id>
# ----------------------------------------------------------------------
def test_one_run_by_id(tmp_path):
    _make_run(tmp_path / "r", events=_event_line("fit_start"),
              status={"stage": "profile", "rwp": 0.08, "gof": 1.3})
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        one = _json(f"{base}/api/run/{row['run_id']}")
    assert one["label"] == "r"
    assert one["status"]["stage"] == "profile"
    assert one["liveness"]["state"] == "unknown"


def test_an_unknown_id_is_404_not_a_traversal(tmp_path):
    """An id is looked up in what the walk offered, never decoded into a path."""
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        for bogus in ("deadbeef", "..", "%2e%2e%2fetc"):
            with pytest.raises(urllib.error.HTTPError) as excinfo:
                _get(f"{base}/api/run/{bogus}")
            assert excinfo.value.code == 404


def test_an_unknown_subroute_is_404(tmp_path):
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            _get(f"{base}/api/run/{row['run_id']}/nonsense")
    assert excinfo.value.code == 404


# ----------------------------------------------------------------------
# /api/run/<id>/events
# ----------------------------------------------------------------------
def test_events_tail_is_incremental(tmp_path):
    """The whole-file refetch the old page did is what this replaces."""
    directory = _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        stem = f"{base}/api/run/{row['run_id']}/events"

        first = _json(stem + "?offset=0")
        assert [e["kind"] for e in first["events"]] == ["fit_start"]
        assert first["offset"] > 0 and first["reset"] is False

        again = _json(f"{stem}?offset={first['offset']}&inode={first['inode']}")
        assert again["events"] == []
        assert again["offset"] == first["offset"]

        with open(directory / runs.EVENTS_FILE, "a", encoding="utf-8") as fh:
            fh.write(_event_line("stage_start", stage="cell"))
        more = _json(f"{stem}?offset={first['offset']}&inode={first['inode']}")
        assert [e["kind"] for e in more["events"]] == ["stage_start"]
        assert more["events"][0]["data"]["stage"] == "cell"


def test_a_truncated_log_tells_the_client_to_clear_its_pane(tmp_path):
    directory = _make_run(tmp_path / "r",
                          events=_event_line("fit_start") * 4)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        stem = f"{base}/api/run/{row['run_id']}/events"
        first = _json(stem + "?offset=0")

        # a second run in the same directory: LiveSession truncates the log
        (directory / runs.EVENTS_FILE).write_text(_event_line("stage_start"),
                                                  encoding="utf-8")
        after = _json(f"{stem}?offset={first['offset']}&inode={first['inode']}")
    assert after["reset"] is True
    assert [e["kind"] for e in after["events"]] == ["stage_start"]


def test_a_junk_offset_does_not_break_the_route(tmp_path):
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        stem = f"{base}/api/run/{row['run_id']}/events"
        payload = _json(stem + "?offset=banana")
    assert [e["kind"] for e in payload["events"]] == ["fit_start"]


def test_a_bad_line_is_counted_over_the_wire(tmp_path):
    _make_run(tmp_path / "r",
              events=_event_line("fit_start") + "not json\n"
                     + _event_line("fit_end"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        payload = _json(f"{base}/api/run/{row['run_id']}/events?offset=0")
    assert payload["bad_lines"] == 1
    assert len(payload["events"]) == 2


# ----------------------------------------------------------------------
# /api/run/<id>/snapshot
# ----------------------------------------------------------------------
def test_the_snapshot_is_served_for_the_iframe(tmp_path):
    _make_run(tmp_path / "r", events=_event_line("fit_start"), snapshot=True)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        assert row["has_snapshot"] is True
        body = _get(f"{base}/api/run/{row['run_id']}/snapshot")
    assert b"plotly goes here" in body


def test_a_run_with_no_snapshot_says_so_rather_than_erroring_out(tmp_path):
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        assert row["has_snapshot"] is False
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            _get(f"{base}/api/run/{row['run_id']}/snapshot")
    assert excinfo.value.code == 404


# ----------------------------------------------------------------------
# the CLI, and what already linked at the bare names
# ----------------------------------------------------------------------
def test_the_directory_argument_is_optional(monkeypatch, tmp_path):
    """No argument scans the working directory."""
    seen = {}

    def fake_serve(directory, *, port, open_browser):
        seen.update(directory=directory, port=port)

    monkeypatch.setattr("rietx.watch.serve", fake_serve)
    main([])
    assert seen["directory"] is None and seen["port"] == 8899
    main(["somewhere", "--port", "1234"])
    assert seen["directory"] == "somewhere" and seen["port"] == 1234


def test_serve_defaults_to_the_working_directory(tmp_path, monkeypatch):
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    monkeypatch.chdir(tmp_path)
    with _served(None) as base:
        payload = _json(base + "/api/runs")
    assert payload["root"] == str(tmp_path.resolve())
    assert len(payload["runs"]) == 1


def test_serve_refuses_a_path_that_is_not_a_directory(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError):
        serve(missing, port=0, block=False)


def test_the_bare_static_names_still_resolve(tmp_path):
    """Anything already linking at fit.html or events.jsonl keeps working."""
    _make_run(tmp_path, events=_event_line("fit_start"), snapshot=True,
              status={"stage": "cell", "rwp": 0.1})
    with _served(tmp_path) as base:
        assert b"plotly goes here" in _get(base + "/fit.html")
        assert b'"fit_start"' in _get(base + "/events.jsonl")
        assert json.loads(_get(base + "/status.json"))["stage"] == "cell"
