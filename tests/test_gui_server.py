"""WP-1008 — the GUI session model and its HTTP surface.

Against a **real** server on an ephemeral port, because the things that break in
a server are the things a direct call to the session cannot see: header checks,
query parsing, status codes, a streaming response that never ends.  One real
refinement runs in the module fixture (a synthetic LaB6 pattern under the real
``mccusker_default`` preset, well under a second) and everything that needs a
fitted state shares it.

The **state machine** is tested with the refinement stubbed instead, and that is
deliberate: "does a mutating verb 409 while a stage is in flight" is a question
about the session's lock and its worker, and answering it against a real fit
would mean racing a solver — a test that passes because it won a race is not a
test.  Cancellation *of a real fit* is WP-1006's ground (``test_run_control``);
what is new here is that the HTTP verb reaches the token and the run record says
what the run left behind.
"""

from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

import pytest

import pxrdref as pr
from pxrdref.gui import ROUTES, GuiSession, build_server
from pxrdref.gui.session import RESERVED_ROUTES
from pxrdref.history.events import read_events
from tests.test_project import _write_xye
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("gui-server")

OUT = Path(__file__).parent / "output"


# ----------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def pattern_file(tmp_path_factory):
    return _write_xye(tmp_path_factory.mktemp("gui-data") / "synth.xye", synthesize())


@pytest.fixture(scope="module")
def state_dir(tmp_path_factory):
    """A recent-projects store that is never the user's real home."""
    return tmp_path_factory.mktemp("gui-state")


def _project(root: Path, pattern_file: Path, **kw) -> pr.Project:
    structure, ins = perturbed_models()
    return pr.Project.create(root, pattern=pattern_file, structure=structure,
                            instrument=ins, plan="mccusker_default", **kw)


def _open(session: GuiSession, root: Path, pattern_file: Path, **kw) -> pr.Project:
    """Create a project and open it in ``session``, returning **its** object.

    Returning ``session.project`` rather than what ``create`` handed back is the
    point: ``open`` re-reads the directory, so the created object is a second,
    immediately stale view of the same files — and asserting against it passes by
    accident for as long as the two agree.
    """
    _project(root, pattern_file, **kw)
    session.project_open({"path": str(root)})
    return session.project


def _start(session: GuiSession):
    """Serve ``session`` on an ephemeral port; the poll interval is the teardown
    cost, and 0.5 s × every fixture in this module would dominate its runtime."""
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02},
                     daemon=True).start()
    return httpd


class Client:
    """A tiny HTTP client: returns ``(status, payload)`` and keeps no state."""

    def __init__(self, port: int) -> None:
        self.port = port

    def request(self, method: str, path: str, body: dict | None = None,
                headers: dict | None = None) -> tuple[int, dict]:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=60)
        payload = None if body is None else json.dumps(body).encode()
        head = {"Host": f"127.0.0.1:{self.port}"}
        if payload is not None:
            head["Content-Type"] = "application/json"
        head.update(headers or {})
        try:
            conn.request(method, path, body=payload, headers=head)
            response = conn.getresponse()
            raw = response.read()
            try:
                return response.status, json.loads(raw)
            except ValueError:
                return response.status, {"raw": raw.decode("utf-8", "replace")}
        finally:
            conn.close()

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body or {}, **kw)

    def patch(self, path, body):
        return self.request("PATCH", path, body)

    def put(self, path, body):
        return self.request("PUT", path, body)


@pytest.fixture
def blank(state_dir):
    """A server with no project open — the state the app boots in."""
    session = GuiSession(state_dir=state_dir)
    httpd = _start(session)
    try:
        yield session, Client(httpd.server_address[1])
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture(scope="module")
def fitted(tmp_path_factory, pattern_file, state_dir):
    """One real refinement driven end-to-end over HTTP, shared by the readers."""
    project = _project(tmp_path_factory.mktemp("gui-fit") / "sample.pxrd", pattern_file)
    session = GuiSession(project, state_dir=state_dir)
    httpd = _start(session)
    client = Client(httpd.server_address[1])

    status, run = client.post("/api/run", {"kind": "fit"})
    assert status == 200, run
    assert run["state"] == "running"
    _wait_idle(client)
    state = client.get("/api/run/state")[1]
    assert state["run"]["status"] == "converged", state
    # the visual gate the numbers cannot be (CLAUDE.md, Tests)
    OUT.mkdir(exist_ok=True)
    project.refinement.result_.plot(path=str(OUT / "gui_server_fit.png"))
    try:
        yield session, client, project
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()


def _wait_idle(client: Client, timeout: float = 120.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get("/api/run/state")[1]
        if state["state"] == "idle":
            return state
        time.sleep(0.02)
    raise AssertionError("run did not finish")


# ----------------------------------------------------------------------
# the surface itself
# ----------------------------------------------------------------------
def test_capabilities_is_the_package_answer_verbatim(blank):
    """One authority: the route must not paraphrase ``pxrdref.capabilities()``."""
    _, client = blank
    status, payload = client.get("/api/capabilities")
    assert status == 200
    assert payload == pr.capabilities().model_dump(mode="json")


def test_version_and_recent_work_without_a_project(blank):
    _, client = blank
    status, payload = client.get("/api/version")
    assert status == 200 and payload["package_version"] == pr.capabilities(
    ).package_version
    assert payload["project"] is None
    assert client.get("/api/recent")[0] == 200


def test_project_verbs_refuse_before_a_project_is_open(blank):
    """``NO_PROJECT`` rather than a 500 or an empty table."""
    _, client = blank
    for method, path in (("GET", "/api/params"), ("GET", "/api/plan"),
                         ("GET", "/api/history"), ("GET", "/api/result"),
                         ("POST", "/api/run"), ("GET", "/api/project")):
        status, payload = client.request(method, path, {} if method == "POST" else None)
        assert status == 409, (path, status, payload)
        assert payload["error"]["code"] == "NO_PROJECT"


def test_host_header_is_checked(blank):
    """A page on another origin must not be able to drive this server."""
    _, client = blank
    status, payload = client.get("/api/version",
                                 headers={"Host": "pxrdref.example.com"})
    assert status == 403
    assert payload["error"]["code"] == "FORBIDDEN_HOST"
    # …and the rebinding case, where Host *is* loopback but the page is not
    status, payload = client.get("/api/version",
                                 headers={"Origin": "http://evil.example"})
    assert status == 403


def test_reserved_routes_answer_404_naming_their_work_package(blank):
    _, client = blank
    status, payload = client.get("/api/textdoc")
    assert status == 404
    assert payload["error"]["code"] == "NOT_IMPLEMENTED"
    assert "WP-1009" in payload["error"]["message"]
    status, payload = client.post("/api/index")
    assert status == 404 and "WP-1024" in payload["error"]["message"]


def test_no_route_is_declared_twice(blank):
    """A path may be live or reserved, never both — a 404 that shadows a verb."""
    assert not set(ROUTES) & set(RESERVED_ROUTES)


def test_the_placeholder_page_and_plotly_are_served(blank):
    _, client = blank
    status, payload = client.get("/")
    assert status == 200 and "pxrdref gui" in payload["raw"]
    status, payload = client.get("/plotly.js")
    assert status == 200 and len(payload["raw"]) > 1000
    assert client.get("/assets/nope.js")[0] == 404


def test_asset_paths_cannot_escape_the_static_directory(blank):
    _, client = blank
    status, _ = client.get("/../../../../etc/passwd")
    assert status in (400, 404)


# ----------------------------------------------------------------------
# project lifecycle
# ----------------------------------------------------------------------
def test_new_open_and_recent_round_trip(blank, tmp_path, pattern_file):
    session, client = blank
    structure, ins = perturbed_models()
    root = tmp_path / "made_over_http.pxrd"
    status, payload = client.post("/api/project/new", {
        "path": str(root), "pattern": str(pattern_file),
        "structure": structure.model_dump(mode="json"),
        "instrument": ins.model_dump(mode="json"),
        "plan": "mccusker_default", "ui": {"disclosure": "simple"}})
    assert status == 200, payload
    assert payload["data"]["has_sigma"] is True      # the file's esds, not Poisson
    assert payload["doc"]["ui"] == {"disclosure": "simple"}
    assert payload["n_nodes"] == 1 and payload["head"] == "n0000"

    # a fresh session opens what the first one wrote, and remembers it
    other = GuiSession(state_dir=session.state_dir)
    assert other.project_open({"path": str(root)})["path"] == str(root)
    assert str(root) in [entry["path"] for entry in other.recent()]

    status, payload = client.post("/api/project/open", {"path": str(tmp_path)})
    assert status == 400 and payload["error"]["code"] == "PROJECT_ERROR"


def test_new_refuses_an_instrument_it_would_have_to_guess(blank, tmp_path,
                                                          pattern_file):
    """A default anode would put a wavelength nobody chose into every cell."""
    _, client = blank
    structure, _ = perturbed_models()
    status, payload = client.post("/api/project/new", {
        "path": str(tmp_path / "no_instrument.pxrd"),
        "pattern": str(pattern_file),
        "structure": structure.model_dump(mode="json")})
    assert status == 400
    assert payload["error"]["where"] == ["instrument"]


def test_open_surfaces_the_binding_message_it_refused_on(blank, tmp_path,
                                                          pattern_file):
    """Seven refusals, seven remedies — the GUI is where one gets read."""
    _, client = blank
    root = tmp_path / "edited.pxrd"
    _project(root, pattern_file)
    copied = root / pattern_file.name
    copied.write_text(copied.read_text(encoding="utf-8") + "90.0 1.0 1.0\n",
                      encoding="utf-8")
    status, payload = client.post("/api/project/open", {"path": str(root)})
    assert status == 400
    assert "has changed since the project was created" in payload["error"]["message"]
    assert "sha256" in payload["error"]["message"]


def test_settings_persist_without_anyone_pressing_save(blank, tmp_path,
                                                       pattern_file):
    """The close dialog has nothing to confirm, so a settings verb must save."""
    session, client = blank
    root = tmp_path / "settings.pxrd"
    _open(session, root, pattern_file)

    status, payload = client.post("/api/project", {
        "mode": "lebail", "two_theta_limits": [5.0, 20.0],
        "excluded_regions": [[8.0, 8.5]], "ui": {"panel": "params"}})
    assert status == 200, payload
    assert payload["doc"]["mode"] == "lebail"
    assert payload["doc"]["excluded_regions"] == [[8.0, 8.5]]

    on_disk = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert on_disk["mode"] == "lebail"
    assert on_disk["two_theta_limits"] == [5.0, 20.0]
    assert on_disk["ui"] == {"panel": "params"}
    # the mask reached the pattern too, not just the document
    assert session.project.data.excluded_regions == [(8.0, 8.5)]

    # a ui key set to null is dropped rather than stored as null
    assert client.post("/api/project", {"ui": {"panel": None}})[1]["doc"]["ui"] == {}
    assert client.post("/api/project", {"nonsense": 1})[0] == 400


def test_plan_selection_and_the_preset_it_matches(blank, tmp_path, pattern_file):
    session, client = blank
    _open(session, tmp_path / "plan.pxrd", pattern_file)
    status, payload = client.get("/api/plan")
    assert status == 200
    assert payload["preset"] == "mccusker_default"   # derived, not stored
    assert payload["selected"] is True
    n_stages = len(payload["plan"]["stages"])

    status, payload = client.put("/api/plan", {"preset": "profile_only"})
    assert status == 200 and payload["preset"] == "profile_only"

    edited = payload["plan"]
    edited["stages"] = edited["stages"][:1]
    status, payload = client.put("/api/plan", {"plan": edited})
    assert status == 200
    assert payload["preset"] is None and len(payload["plan"]["stages"]) == 1
    assert n_stages > 1

    assert client.put("/api/plan", {"preset": "no_such_plan"})[0] == 400
    assert client.put("/api/plan", {"plan": {"stages": []}})[0] == 400
    assert client.get("/api/plans")[1]["plans"][0]["when_to_use"]


# ----------------------------------------------------------------------
# parameters
# ----------------------------------------------------------------------
def test_params_exposes_why_each_held_row_is_held(fitted):
    _, client, project = fitted
    status, payload = client.get("/api/params")
    assert status == 200
    rows = {r["path"]: r for r in payload["parameters"]}
    assert len(rows) == len(project.refinement.parameters())
    assert payload["live"] is False and payload["n_free"] > 0

    # the three reasons a row can be held, each spelled out in the payload
    tied = [r for r in rows.values() if r["tie"] is not None]
    locked = [r for r in rows.values() if r["locked"]]
    assert tied and locked
    for row in (*tied, *locked):
        assert row["refinable"] is False and row["held_because"]
    # …and esds from the fit are merged into the same listing
    assert any(r["esd"] for r in rows.values())


def test_editing_a_tied_path_is_refused_by_naming_its_sources(fitted):
    """WP-1004's rule, now over HTTP: ``b`` follows ``a`` on a cubic cell."""
    _, client, _ = fitted
    status, payload = client.patch("/api/params",
                                   {"values": {"phases.0.cell.b": 4.2}})
    assert status == 400
    assert "phases.0.cell.a" in payload["error"]["message"]
    assert payload["error"]["where"] == ["phases.0.cell.b"]


def test_values_and_vary_commit_their_own_history_nodes(blank, tmp_path,
                                                        pattern_file):
    session, client = blank
    project = _open(session, tmp_path / "edits.pxrd", pattern_file)
    before = len(project.history)

    status, payload = client.patch("/api/params", {
        "values": {"phases.0.cell.a": 4.163},
        "vary": {"phases.*.cell.*": True, "phases.0.cell.a": False}})
    assert status == 200, payload
    assert payload["changed"]["values"] == ["phases.0.cell.a"]
    assert payload["changed"]["vary"]["phases.0.cell.a"] == ["phases.0.cell.a"]

    rows = {r["path"]: r for r in payload["parameters"]}
    assert rows["phases.0.cell.a"]["value"] == pytest.approx(4.163)
    # a cubic tie followed the edit (WP-1004's refresh_ties)
    assert rows["phases.0.cell.c"]["value"] == pytest.approx(4.163)
    assert rows["phases.0.cell.a"]["vary"] is False

    kinds = [n.action.kind for n in project.history.nodes.values()]
    assert kinds[before:] == ["set_value", "set_vary", "set_vary"]
    # every one of them is on disk already — saving is about settings
    reopened = pr.Project.open(project.path)
    assert len(reopened.history) == len(project.history)
    assert reopened.refinement.structure.phases[0].cell.a.value == pytest.approx(4.163)


def test_a_whole_model_patch_records_an_edit_node(blank, tmp_path, pattern_file):
    session, client = blank
    project = _open(session, tmp_path / "edit_model.pxrd", pattern_file)
    instrument = client.get("/api/instrument")[1]["instrument"]
    instrument["zero_shift"]["value"] = 0.02
    status, payload = client.patch("/api/instrument", {"instrument": instrument,
                                                       "label": "zero guess"})
    assert status == 200, payload
    assert payload["instrument"]["zero_shift"]["value"] == 0.02
    node = project.history[payload["node_id"]]
    assert node.action.kind == "edit_model" and node.label == "zero guess"

    status, payload = client.patch("/api/structure", {"structure": {"phases": []}})
    assert status == 400 and payload["error"]["where"]


# ----------------------------------------------------------------------
# running
# ----------------------------------------------------------------------
def test_a_real_run_streams_its_events_to_disk_and_to_followers(fitted):
    """The GUI and ``pxrdref watch`` are two views of one stream."""
    session, client, project = fitted
    log = project.live_dir / "events.jsonl"
    assert log.is_file()
    kinds = [record.kind for record in read_events(log)]
    assert kinds[0] == "fit_start" and kinds[-1] == "fit_end"
    assert "stage_start" in kinds and "eval" in kinds

    # the ring buffer replayed the same run, seq-numbered and monotone
    status, payload = client.get("/api/events?poll=1&since=0")
    assert status == 200
    seqs = [e["seq"] for e in payload["events"]]
    assert seqs == sorted(seqs) and payload["next"] == seqs[-1]
    assert payload["oldest"] == seqs[0]
    assert [e["kind"] for e in payload["events"]][-1] == "fit_end"

    # …and ?since= is a real replay cursor, not a hint
    half = seqs[len(seqs) // 2]
    later = client.get(f"/api/events?poll=1&since={half}")[1]["events"]
    assert [e["seq"] for e in later] == [s for s in seqs if s > half]


def test_result_carries_no_curves_and_the_window_serves_them(fitted):
    _, client, project = fitted
    status, payload = client.get("/api/result")
    assert status == 200
    result = payload["result"]
    assert "two_theta" not in result and "y_obs" not in result
    assert result["statistics"]["rwp"] < 0.2
    n_points = result["curves"]["n_points"]
    assert n_points == len(project.data.two_theta)

    status, window = client.get("/api/result/window")
    assert status == 200
    assert window["n_total"] == n_points
    # max_points is a budget, not a ceiling: three curves' per-bucket extrema
    # over max_points//2 buckets can exceed it, and n_returned is the truth
    assert 0 < window["n_returned"] <= 3 * (window["max_points"] // 2) + 2
    assert len(window["two_theta"]) == window["n_returned"]
    assert len(window["delta"]) == window["n_returned"]

    lo, hi = 8.0, 12.0
    zoom = client.get(f"/api/result/window?lo={lo}&hi={hi}&max_points=200")[1]
    assert zoom["n_total"] < n_points
    assert lo <= zoom["two_theta"][0] and zoom["two_theta"][-1] <= hi
    # ticks are clipped to the window, and every emission line is in them
    assert all(lo <= t <= hi for ticks in zoom["ticks"].values() for t in ticks)
    assert zoom["ticks"]

    empty = client.get("/api/result/window?lo=200&hi=210")[1]
    assert empty["n_returned"] == 0 and empty["two_theta"] == []


def test_report_and_history_read_the_fitted_session(fitted):
    session, client, project = fitted
    status, payload = client.get("/api/report")
    assert status == 200
    report = payload["report"]
    assert report["summary"] and report["thresholds_version"]
    assert report["rwp"] == pytest.approx(
        project.refinement.result_.statistics.rwp)

    status, payload = client.get("/api/history")
    assert status == 200
    assert payload["head"] == project.refinement._head_id
    assert payload["n_nodes"] == len(project.history)
    stage_nodes = [n for n in payload["nodes"] if n["kind"] == "stage"]
    assert stage_nodes and all(n["rwp"] is not None for n in stage_nodes)
    # a node's equivalent API call travels with it, so the log doubles as a script
    assert stage_nodes[0]["api_call"].startswith("ref.run_stage(")
    # …and no node ships its ~10 kB of structure/instrument state
    assert "state" not in payload["nodes"][0]

    ids = [n["id"] for n in payload["nodes"]][:2]
    rows = client.get(f"/api/history/compare?ids={','.join(ids)}")[1]["rows"]
    assert [r["id"] for r in rows] == ids
    diff = client.get(f"/api/history/diff?a={ids[0]}&b={ids[1]}")[1]["diff"]
    assert diff and all(len(pair) == 2 for pair in diff.values())
    assert client.get("/api/history/diff?a=n0000")[0] == 400
    assert client.get("/api/history/diff?a=n0000&b=nope")[0] == 404


def test_checkout_moves_the_working_state_and_branch_names_the_fork(
        blank, tmp_path, pattern_file):
    """Its own project, because a checkout discards the result — see below."""
    session, client = blank
    project = _open(session, tmp_path / "checkout.pxrd", pattern_file)
    for turn_on in (["phases.*.scale", "instrument.background.*"],
                    ["instrument.zero_shift"]):
        client.post("/api/run", {"kind": "stage",
                                 "stage": {"name": "s", "turn_on": turn_on}})
        _wait_idle(client)
    head_before = project.refinement._head_id
    root = project.history.root.id
    assert client.get("/api/result")[0] == 200

    status, payload = client.post("/api/history/checkout", {"node_id": root})
    assert status == 200 and payload["head"] == root
    assert project.refinement._head_id == root
    # …and the fitted curves went with it: they described the values a checkout
    # just replaced, so a GUI must re-run before it can export or report again
    assert client.get("/api/result")[1]["error"]["code"] == "NO_RESULT"
    assert client.get("/api/report")[0] == 409

    status, payload = client.post("/api/history/branch",
                                  {"node_id": head_before, "name": "best-so-far"})
    assert status == 200
    assert payload["head"] == head_before and payload["name"] == "best-so-far"
    assert project.history.refs["best-so-far"] == head_before
    tagged = [n for n in client.get("/api/history")[1]["nodes"]
              if "best-so-far" in n["tags"]]
    assert [n["id"] for n in tagged] == [head_before]

    status, payload = client.post("/api/history/annotate",
                                  {"node_id": head_before, "label": "keeper",
                                   "notes": {"why": "lowest Rwp"}})
    assert status == 200
    assert project.history[head_before].notes == {"why": "lowest Rwp"}
    assert client.post("/api/history/checkout", {"node_id": "n9999"})[0] == 404


def test_exports_land_in_the_project_and_cannot_escape_it(fitted, tmp_path):
    _, client, project = fitted
    for kind, suffix in (("cif", ".cif"), ("reflections", ".csv"),
                         ("html", ".html"), ("result_json", ".json")):
        status, payload = client.post(f"/api/export/{kind}")
        assert status == 200, (kind, payload)
        written = Path(payload["path"])
        assert written.parent == project.exports_dir
        assert written.suffix == suffix and payload["bytes"] > 0

    # Le Bail has no weight fractions; saying so beats writing an empty table
    status, payload = client.post("/api/export/qpa")
    assert status in (200, 409)

    status, payload = client.post("/api/export/cif",
                                  {"filename": "../../escaped.cif"})
    assert status == 400 and payload["error"]["where"] == ["filename"]
    assert not (tmp_path / "escaped.cif").exists()
    assert client.post("/api/export/nonsense")[0] == 404


# ----------------------------------------------------------------------
# the run state machine (refinement stubbed — see the module docstring)
# ----------------------------------------------------------------------
@pytest.fixture
def blocked(blank, tmp_path, pattern_file, monkeypatch):
    """A session whose "fit" blocks until the test releases it."""
    session, client = blank
    _open(session, tmp_path / "blocked.pxrd", pattern_file)
    started, release = threading.Event(), threading.Event()
    seen: dict = {}

    def fake_fit(*, plan=None, events=None, cancel=None, **kw):
        seen["cancel"] = cancel
        events.emit("fit_start", mode="rietveld", stages=["stub"], n_points=1)
        events.emit("stage_start", stage="stub", index=1, n_stages=1)
        started.set()
        while not release.wait(0.01):
            if cancel is not None and cancel.is_set():
                raise pr.RefinementCancelled(
                    "cancelled", stage="stub", completed_stages=[],
                    node_id=session.project.refinement._head_id)
        raise RuntimeError("stub blew up")

    monkeypatch.setattr(session.project, "fit", fake_fit)
    yield session, client, started, release, seen
    release.set()


def test_mutating_verbs_refuse_while_a_run_is_in_flight(blocked):
    session, client, started, release, _ = blocked
    assert client.post("/api/run", {"kind": "fit"})[1]["state"] == "running"
    assert started.wait(5)

    for method, path, body in (
            ("PATCH", "/api/params", {"values": {"phases.0.cell.a": 4.16}}),
            ("PATCH", "/api/params", {"vary": {"phases.*.cell.*": True}}),
            ("POST", "/api/project", {"mode": "lebail"}),
            ("PUT", "/api/plan", {"preset": "profile_only"}),
            ("POST", "/api/run", {"kind": "fit"}),
            ("POST", "/api/history/checkout", {"node_id": "n0000"}),
            # deliberately an *invalid* body: the state refusal has to outrank
            # the body complaint, or the user debugs the wrong thing
            ("PATCH", "/api/structure", {"structure": {"phases": []}}),
            ("POST", "/api/export/cif", {}),
            ("GET", "/api/report", None)):
        status, payload = client.request(method, path, body)
        assert status == 409, (path, status, payload)
        assert payload["error"]["code"] == "RUN_IN_FLIGHT", (path, payload)

    # reads stay open, and say the values are mid-run
    params = client.get("/api/params")[1]
    assert params["live"] is True
    assert client.get("/api/history")[0] == 200

    release.set()
    _wait_idle(client)
    # …and now the same verb goes through
    assert client.post("/api/project", {"mode": "rietveld"})[0] == 200


def test_a_failed_run_ends_the_state_machine_and_says_why(blocked):
    session, client, started, release, _ = blocked
    client.post("/api/run", {"kind": "fit"})
    assert started.wait(5)
    release.set()
    state = _wait_idle(client)
    assert state["run"]["status"] == "failed"
    assert state["run"]["error"]["code"] == "RUN_FAILED"
    assert "stub blew up" in state["run"]["error"]["message"]
    # a failure emits no fit_end, which is exactly why the state travels beside
    # the events rather than as one of them
    events = client.get("/api/events?poll=1")[1]["events"]
    assert [e["kind"] for e in events] == ["fit_start", "stage_start"]
    assert events[-1]["data"]["index"] == 1


def test_cancel_reaches_the_token_and_the_record_says_where_state_stands(blocked):
    session, client, started, _release, seen = blocked
    client.post("/api/run", {"kind": "fit"})
    assert started.wait(5)

    status, payload = client.post("/api/cancel")
    assert status == 200 and payload["state"] == "cancelling"
    assert seen["cancel"].is_set()
    state = _wait_idle(client)
    assert state["run"]["status"] == "cancelled"
    assert state["run"]["stage"] == "stub"
    # the node the working state stands at — what a "resume" button checks out
    assert state["run"]["node_id"] == session.project.refinement._head_id
    assert client.post("/api/cancel")[1]["error"]["code"] == "NOT_RUNNING"


def test_progress_needs_no_bookkeeping_beyond_the_events(blocked):
    """``stage_start`` carries 1-based ``index``/``n_stages`` (WP-1006)."""
    session, client, started, release, _ = blocked
    client.post("/api/run", {"kind": "fit"})
    assert started.wait(5)
    state = client.get("/api/run/state")[1]
    assert state["run"]["stage"] == "stub"
    assert state["run"]["stage_index"] == 1 and state["run"]["n_stages"] == 1
    assert state["run"]["elapsed"] >= 0.0
    release.set()
    _wait_idle(client)


def test_sse_delivers_events_then_the_terminal_state(blocked):
    """A follower learns the run ended even though nothing emitted ``fit_end``."""
    session, client, started, release, _ = blocked
    conn = HTTPConnection("127.0.0.1", client.port, timeout=30)
    conn.request("GET", "/api/events?since=0",
                 headers={"Host": f"127.0.0.1:{client.port}"})
    response = conn.getresponse()
    assert response.status == 200
    assert response.headers["Content-Type"].startswith("text/event-stream")

    client.post("/api/run", {"kind": "fit"})
    assert started.wait(5)
    release.set()

    names, payloads = [], []
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            line = response.fp.readline().decode()
            if line.startswith("event: "):
                names.append(line[7:].strip())
            elif line.startswith("data: "):
                payloads.append(json.loads(line[6:]))
                if names[-1] == "state" and payloads[-1].get("state") == "idle" \
                        and payloads[-1]["run"]["status"]:
                    break
    finally:
        conn.close()

    assert "event" in names and "state" in names
    kinds = [p["kind"] for p, n in zip(payloads, names) if n == "event"]
    assert kinds[:2] == ["fit_start", "stage_start"]
    assert payloads[-1]["run"]["status"] == "failed"


def test_a_single_stage_run_goes_through_the_same_machinery(blank, tmp_path,
                                                            pattern_file):
    session, client = blank
    project = _open(session, tmp_path / "one_stage.pxrd", pattern_file)
    status, payload = client.post("/api/run", {
        "kind": "stage",
        "stage": {"name": "scale_bkg",
                  "turn_on": ["phases.*.scale", "instrument.background.*"]}})
    assert status == 200, payload
    assert payload["run"]["kind"] == "stage" and payload["run"]["n_stages"] == 1
    state = _wait_idle(client)
    assert state["run"]["status"] in ("converged", "max_iter")
    assert state["run"]["rwp"] is not None
    assert project.history[state["run"]["node_id"]].action.kind == "stage"
    assert client.post("/api/run", {"kind": "wander"})[0] == 400
    assert client.post("/api/run", {"kind": "stage"})[0] == 400


def test_shutdown_stops_the_server(state_dir):
    session = GuiSession(state_dir=state_dir)
    httpd = build_server(session, port=0)
    thread = threading.Thread(target=httpd.serve_forever,
                              kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    client = Client(httpd.server_address[1])
    assert client.post("/api/shutdown")[1]["stopping"] is True
    thread.join(timeout=10)
    assert not thread.is_alive()
    httpd.server_close()


def test_a_busy_port_falls_back_instead_of_refusing_to_start(state_dir):
    """A second window is the ordinary case, not an error."""
    first = build_server(GuiSession(state_dir=state_dir), port=0)
    port = first.server_address[1]
    try:
        second = build_server(GuiSession(state_dir=state_dir), port=port)
        try:
            assert second.server_address[1] != port
        finally:
            second.server_close()
    finally:
        first.server_close()
