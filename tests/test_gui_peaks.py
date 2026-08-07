"""WP-1027 — the peak picker's verbs and the indexing panel's gate.

Against a **real** server on an ephemeral port, like ``test_gui_server``,
because what this WP adds is wire surface: the verbs must round-trip as HTTP
with their console echoes intact, a stored list must be *refused* against the
wrong pattern at the route (not merely in a docstring), and the adopt gate must
hold at the server so no UI path can leak past it.

The `.pxt` peaks-block fixed point lives in ``test_textdoc`` beside the other
fixed-point properties; the engine's own editing semantics (carry of `origin`
and `excluded` across a refit, group windows, ghost-recompute scoping) are
asserted here through the verbs, which is the only door a client has.
"""

from __future__ import annotations

import json
import shutil
import threading
import time
from http.client import HTTPConnection

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.gui import GuiSession, build_server
from pxrdref.refine import _VERSION
from pxrdref.schemas.common import Provenance
from pxrdref.schemas.indexing import (
    INDEX_REFUTING_CAVEATS,
    PEAK_UNUSABLE_FLAGS,
    CellCandidate,
    IndexingResult,
)
from tests.test_project import _write_xye
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("gui-peaks")


# ----------------------------------------------------------------------
# fixtures — one live server over one project, module-scoped
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def pattern_file(tmp_path_factory):
    return _write_xye(tmp_path_factory.mktemp("peaks-data") / "synth.xye",
                      synthesize())


@pytest.fixture(scope="module")
def served(tmp_path_factory, pattern_file):
    structure, instrument = perturbed_models()
    root = tmp_path_factory.mktemp("peaks-proj") / "p.pxrd"
    project = pr.Project.create(root, pattern=pattern_file,
                                structure=structure, instrument=instrument)
    session = GuiSession(project,
                         state_dir=tmp_path_factory.mktemp("peaks-state"))
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever,
                     kwargs={"poll_interval": 0.02}, daemon=True).start()
    yield session, project, httpd.server_address[1]
    session.close()
    httpd.shutdown()


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    def request(self, method: str, path: str, body: dict | None = None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=60)
        payload = None if body is None else json.dumps(body).encode()
        try:
            conn.request(method, path, body=payload,
                         headers={"Host": f"127.0.0.1:{self.port}",
                                  **({"Content-Type": "application/json"}
                                     if payload else {})})
            response = conn.getresponse()
            return response.status, json.loads(response.read() or b"{}")
        finally:
            conn.close()

    def get(self, path: str):
        return self.request("GET", path)

    def post(self, path: str, body: dict | None = None):
        return self.request("POST", path, body or {})


@pytest.fixture(scope="module")
def client(served):
    return Client(served[2])


def _wait_idle(client: Client, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, frame = client.get("/api/run/state")
        if frame["state"] == "idle":
            return frame
        time.sleep(0.05)
    raise AssertionError("run never returned to idle")


# ----------------------------------------------------------------------
# the verbs, through the wire
# ----------------------------------------------------------------------
def test_the_peak_verbs_round_trip_with_their_echoes(served, client):
    _, project, _ = served

    # before any pick: no list, but the raw pattern is there to draw — the
    # state an indexing project starts in
    status, empty = client.get("/api/peaks")
    assert status == 200 and empty["peaks"] is None
    assert len(empty["pattern"]["two_theta"]) > 100
    assert sorted(PEAK_UNUSABLE_FLAGS) == empty["unusable_flags"]

    status, picked = client.post("/api/peaks", {})
    assert status == 200
    assert picked["api_call"] == "session.pick_peaks(shoulders=True)"
    n = picked["n_total"]
    assert n >= 10 and picked["n_usable"] <= n
    assert (project.path / "peaks.json").is_file()
    # every group curve is drawable state: window, fit, residual strip
    assert picked["groups"] and all(
        len(g["two_theta"]) == len(g["y_fit"]) == len(g["delta"])
        for g in picked["groups"])

    # add — between the first two lines, which lands in fresh window territory
    # or an existing group; either way the component is the human's
    tts = [p["two_theta"] for p in picked["peaks"]]
    target = round((tts[0] + tts[1]) / 2, 3)
    status, added = client.post("/api/peaks/add", {"two_theta": target})
    assert status == 200 and added["n_total"] == n + 1
    assert added["api_call"] == f"session.add_peak({target:g})"
    manual = [p for p in added["peaks"] if p["origin"] == "manual"]
    assert len(manual) == 1

    # move — the drag verb; the landed position is fitted, hence *near* the ask
    i = manual[0]["index"]
    ask = manual[0]["two_theta"] + 0.03
    status, moved = client.post("/api/peaks/move",
                                {"index": i, "two_theta": ask})
    assert status == 200
    assert moved["api_call"] == f"session.move_peak({i}, {ask:g})"
    edited = [p for p in moved["peaks"] if p["origin"] == "edited"]
    assert len(edited) == 1
    assert abs(edited[0]["two_theta"] - ask) < 0.05

    # flag off and back on — excluded is the caller's decision, and the
    # overrule direction strips the unusable marks
    status, flagged = client.post("/api/peaks/flag",
                                  {"index": 0, "use_for_indexing": False})
    assert status == 200
    assert flagged["peaks"][0]["flags"] == ["excluded"]
    assert flagged["peaks"][0]["usable"] is False
    assert flagged["n_usable"] == moved["n_usable"] - 1
    _, restored = client.post("/api/peaks/flag",
                              {"index": 0, "use_for_indexing": True})
    assert restored["peaks"][0]["usable"] is True

    # an excluded mark survives its group's refit: the human owns it
    _, flagged = client.post("/api/peaks/flag",
                             {"index": 0, "use_for_indexing": False})
    g0 = flagged["peaks"][0]["group"]
    status, refit = client.post("/api/peaks/refit", {"group": g0})
    assert status == 200
    assert refit["api_call"] == f"session.refit_group({g0})"
    survivors = [p for p in refit["peaks"] if p["group"] == g0]
    assert survivors and "excluded" in survivors[0]["flags"]
    client.post("/api/peaks/flag", {"index": 0, "use_for_indexing": True})

    # remove — back to where the add left off
    j = [p for p in refit["peaks"] if p["origin"] == "edited"][0]["index"]
    status, removed = client.post("/api/peaks/remove", {"index": j})
    assert status == 200 and removed["n_total"] == n
    assert removed["api_call"] == f"session.remove_peak({j})"

    # a bad index is a 404 naming the list's size, not a 500
    status, refused = client.post("/api/peaks/remove", {"index": 10_000})
    assert status == 404 and refused["error"]["code"] == "NOT_FOUND"


def test_a_peak_list_keyed_to_one_pattern_is_refused_against_another(
        served, tmp_path_factory):
    """The `data_fingerprint` key is a refusal, not a decoration."""
    _, project, _ = served
    assert (project.path / "peaks.json").is_file()

    other = synthesize()
    other.intensity = np.asarray(other.intensity) * 1.07 + 3.0
    other_file = _write_xye(tmp_path_factory.mktemp("peaks-b") / "other.xye",
                            other)
    structure, instrument = perturbed_models()
    root = tmp_path_factory.mktemp("peaks-b-proj") / "b.pxrd"
    b = pr.Project.create(root, pattern=other_file, structure=structure,
                          instrument=instrument)
    shutil.copyfile(project.path / "peaks.json", b.path / "peaks.json")

    session = GuiSession(b, state_dir=tmp_path_factory.mktemp("peaks-b-state"))
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever,
                     kwargs={"poll_interval": 0.02}, daemon=True).start()
    try:
        status, payload = Client(httpd.server_address[1]).get("/api/peaks")
        assert status == 409
        assert payload["error"]["code"] == "PEAKS_WRONG_PATTERN"
        assert "different pattern" in payload["error"]["message"]
    finally:
        session.close()
        httpd.shutdown()


def test_mutating_peak_verbs_refuse_while_a_run_is_in_flight(served, client):
    session, _, _ = served
    with session._cond:
        session._state = "running"
    try:
        status, payload = client.post("/api/peaks/add", {"two_theta": 12.0})
        assert status == 409
        assert payload["error"]["code"] == "RUN_IN_FLIGHT"
        # the read stays open — it serves a project artifact, not the model
        assert client.get("/api/peaks")[0] == 200
    finally:
        with session._cond:
            session._state = "idle"


# ----------------------------------------------------------------------
# indexing: the run machine, the answer, the gate
# ----------------------------------------------------------------------
def test_index_rides_the_run_state_machine(served, client):
    # Flag the list down to four usable lines — below MIN_LINES_PER_DOF in
    # every system — so the quality gate still abstains and the run completes
    # in one poll.  Since WP-1043 a short-but-searchable list (this pattern's
    # 15 usable lines included) is *searched* over the systems its line count
    # supports; that path belongs to the acceptance suite, not to the run
    # machine, and unbudgeted it would outlive every timeout here.
    _, doc = client.get("/api/peaks")
    usable = [p["index"] for p in doc["peaks"] if p["usable"]]
    assert len(usable) > 4
    for i in usable[4:]:
        status, _flagged = client.post(
            "/api/peaks/flag", {"index": i, "use_for_indexing": False})
        assert status == 200

    status, frame = client.post("/api/index", {})
    assert status == 200 and frame["run"]["kind"] == "index"
    frame = _wait_idle(client)
    # the flagged-down list abstains at the quality gate — abstention is a
    # *result*, and the machine must report a completed run, not a failure
    assert frame["run"]["status"] == "completed"
    assert frame["run"]["node_id"] is None  # an indexing run commits no node

    status, answer = client.get("/api/index/result")
    assert status == 200
    assert answer["refuting_caveats"] == sorted(INDEX_REFUTING_CAVEATS)
    assert isinstance(answer["result"]["candidates"], list)
    assert len(answer["adopt"]) == len(answer["result"]["candidates"])

    # nothing to adopt on an abstained result — and the refusal is addressed
    status, refused = client.post("/api/index/adopt", {"candidate": 0})
    assert status in (404, 409)


def _candidate(confidence: str, caveats: list[str]) -> CellCandidate:
    return CellCandidate(
        cell=(4.1568, 4.1568, 4.1568, 90.0, 90.0, 90.0),
        cell_esd=(1e-4,) * 3 + (0.0,) * 3,
        system="cubic", centring="P", lattice_group="P m -3 m",
        volume=71.8, n_indexed=20, n_lines=20,
        confidence=confidence, confidence_caveats=caveats)


def _answer(*candidates: CellCandidate) -> IndexingResult:
    return IndexingResult(
        candidates=list(candidates), engines_run=["dichotomy", "trial_error"],
        systems_searched=["cubic"], validated=True, wavelength=1.5406,
        n_usable_lines=20,
        provenance=Provenance(package_version=_VERSION,
                              created_utc="2026-07-31T00:00:00Z"))


def test_adopt_is_gated_on_best_or_none_server_side(served, client):
    """The acceptance criterion: no UI path adopts what the gate refuses.

    The medium candidate is the *normal* real-data outcome
    (``shift_allowance_assumed``), so this is the state the panel lives in —
    the server's ``adopt`` arm must say no, and the route must refuse with the
    same words, because the button and the route are one answer.
    """
    session, project, _ = served
    medium = _candidate("medium", ["shift_allowance_assumed"])
    with session._cond:
        session._index_result = _answer(medium)

    status, answer = client.get("/api/index/result")
    assert status == 200
    assert answer["adopt"] == [{
        "allowed": False,
        "why": answer["adopt"][0]["why"],
    }]
    assert "medium" in answer["adopt"][0]["why"]
    assert "best_or_none" in answer["adopt"][0]["why"]

    status, refused = client.post("/api/index/adopt", {"candidate": 0})
    assert status == 409
    assert refused["error"]["code"] == "ADOPT_GATED"
    assert "medium" in refused["error"]["message"]

    # two high candidates: still no singleton, still no adoption
    with session._cond:
        session._index_result = _answer(_candidate("high", []),
                                        _candidate("high", []))
    _, answer = client.get("/api/index/result")
    assert [a["allowed"] for a in answer["adopt"]] == [False, False]
    assert client.post("/api/index/adopt", {"candidate": 0})[0] == 409


def test_adopting_the_one_high_candidate_is_a_model_edit(served, client):
    session, project, _ = served
    with session._cond:
        session._index_result = _answer(_candidate("high", []))

    _, answer = client.get("/api/index/result")
    assert answer["adopt"] == [{"allowed": True, "why": ""}]

    head_before = project.refinement._head_id
    status, adopted = client.post("/api/index/adopt", {"candidate": 0})
    assert status == 200
    assert adopted["api_call"] == "session.adopt_candidate(0)"
    assert adopted["node_id"] and adopted["node_id"] != head_before
    # a bare cell is a Le Bail scaffold: dummy atom, absence-free group, and
    # the document's mode follows — a Rietveld fit over it is not offered
    assert adopted["mode"] == "lebail"
    phase = adopted["structure"]["phases"][0]
    assert phase["space_group"] == "P m -3 m"
    assert len(phase["atoms"]) == 1
    node = project.history.nodes[adopted["node_id"]]
    assert node.action.kind == "edit_model"
    assert "adopted indexed cell" in (node.label or "")


# ----------------------------------------------------------------------
# the extinction screen (WP-1025 served)
# ----------------------------------------------------------------------
def test_extinction_screen_rides_the_run_machine_and_ranks_classes(
        served, client):
    """A real ``determine_extinction_symbol`` run over the wire.

    The injected candidate is the synthetic pattern's **true** cell (LaB6,
    cubic P), so the screen is meaningful and cheap: one profile fit, then one
    Le Bail per cubic-P class.  Deliberately *not* gated on the adopt verdict
    — a screen is how a ``medium`` candidate (the normal real-data outcome)
    gets its space-group question answered before anything is at stake.
    """
    session, _, _ = served
    with session._cond:
        session._index_result = _answer(
            _candidate("medium", ["shift_allowance_assumed"]))
        session._extinction = None

    # nothing has run yet — and the refusal says what to POST
    status, refused = client.get("/api/index/extinction")
    assert status == 409
    assert refused["error"]["code"] == "NO_EXTINCTION_RESULT"

    # a candidate the result does not have is addressed, not silently clamped
    status, refused = client.post("/api/index/extinction", {"candidate": 7})
    assert status == 404

    status, frame = client.post("/api/index/extinction", {"candidate": 0})
    assert status == 200 and frame["run"]["kind"] == "extinction"
    frame = _wait_idle(client, timeout=180.0)
    assert frame["run"]["status"] == "completed"
    assert frame["run"]["node_id"] is None  # a screen commits nothing

    status, answer = client.get("/api/index/extinction")
    assert status == 200
    assert answer["candidate"] == 0
    screen = answer["result"]
    assert screen["n_classes"] >= 2  # cubic P has more than one class
    assert screen["n_screened"] >= 1
    ranked = screen["candidates"]
    assert ranked, "the screen must rank classes, not conclude nothing"
    for cls in ranked:
        # every class lists *all* its space groups — the shape rule: the
        # extinction symbol is measurable, one space group is not
        assert isinstance(cls["space_groups"], list) and cls["space_groups"]
    # the served best is the package's own gate, or None — never a local pick
    if answer["best"] is not None:
        assert 0 <= answer["best"] < len(ranked)
        assert not ranked[answer["best"]]["refuted"]


def test_extinction_screen_is_cleared_when_the_candidates_renumber(
        served, client):
    """A new indexing run renumbers the candidates; a kept screen would be
    served against the wrong cell — the same staleness rule as peaks.json."""
    status, _ = client.get("/api/index/extinction")
    assert status == 200  # the previous test's screen is still there

    status, _ = client.post("/api/index", {})
    assert status == 200
    _wait_idle(client, timeout=120.0)

    status, refused = client.get("/api/index/extinction")
    assert status == 409
    assert refused["error"]["code"] == "NO_EXTINCTION_RESULT"
