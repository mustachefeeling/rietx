"""v0.2 events stream, HTML viewer, live watch, and history merge/cherry-pick."""

import json
import urllib.request

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.history.events import EventStream, read_events
from pxrdref.strategy.staged import Stage
from tests.test_refine_synthetic import perturbed_models, synthesize


@pytest.fixture(scope="module")
def synthetic_pattern():
    return synthesize()


# ----------------------------------------------------------------------
# event stream
# ----------------------------------------------------------------------
def test_events_written_and_readable(tmp_path, synthetic_pattern):
    structure, ins = perturbed_models()
    log = tmp_path / "events.jsonl"
    ref = pr.Refinement(structure, ins, history=False)
    ref.fit(synthetic_pattern, events=log)

    events = read_events(log)
    kinds = [e.kind for e in events]
    assert kinds[0] == "fit_start"
    assert kinds[-1] == "fit_end"
    stages = [e.data["stage"] for e in events if e.kind == "stage_start"]
    assert stages == ["scale_bkg", "zero", "cell", "profile_w", "profile"]
    # per-iteration heartbeat really came from inside the solver
    evals = [e for e in events if e.kind == "eval"]
    assert len(evals) > 10
    assert all("cost" in e.data and e.data["cost"] >= 0 for e in evals)
    # timestamps are monotone
    ts = [e.t for e in events]
    assert all(b >= a for a, b in zip(ts, ts[1:]))
    # costs within a stage end lower than they start
    for e in events:
        if e.kind == "stage_end":
            assert e.data["cost_final"] <= e.data["cost_initial"] * (1 + 1e-12)


def test_events_callback_no_file(synthetic_pattern):
    structure, ins = perturbed_models()
    seen = []
    ref = pr.Refinement(structure, ins, history=False)
    ref.fit(synthetic_pattern, events=seen.append)
    assert any(e["kind"] == "eval" for e in seen)
    assert seen[-1]["kind"] == "fit_end"
    assert seen[-1]["data"]["rwp"] < 0.2


def test_event_stream_hot_loop_is_plain_json(tmp_path):
    stream = EventStream(path=tmp_path / "e.jsonl")
    stream.emit("eval", stage="s", n_eval=1, cost=1.5)
    stream.close()
    line = (tmp_path / "e.jsonl").read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert parsed["record"] == "event"
    assert parsed["data"] == {"stage": "s", "n_eval": 1, "cost": 1.5}


# ----------------------------------------------------------------------
# plotly HTML viewer
# ----------------------------------------------------------------------
def test_write_html_self_contained(tmp_path, synthetic_pattern):
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)

    out = tmp_path / "fit.html"
    from pxrdref.viz import write_html
    write_html(result, str(out))
    html = out.read_text(encoding="utf-8")
    assert "plotly" in html.lower()
    assert "scattergl" in html.lower()
    # self-contained: no external <script src=…> tag (the embedded plotly
    # bundle *mentions* URLs inside its own JS string constants — harmless)
    import re
    assert not re.search(r"<script[^>]+src=", html)
    assert out.stat().st_size > 1_000_000       # plotly.js embedded


def test_minmax_decimation_keeps_peaks():
    from pxrdref.viz.html import _minmax_decimate
    tt = np.linspace(0, 100, 50_001)
    y = np.zeros_like(tt)
    y[25_000] = 1e6                             # a single sharp spike
    tt_d, (y_d,) = _minmax_decimate(tt, [y], max_points=2_000)
    assert len(tt_d) <= 2_100
    assert y_d.max() == 1e6, "decimation dropped the peak top"


# ----------------------------------------------------------------------
# live session + watch server
# ----------------------------------------------------------------------
def test_live_session_and_watch_server(tmp_path, synthetic_pattern):
    from pxrdref.viz.live import LiveSession
    from pxrdref.watch import serve

    structure, ins = perturbed_models()
    live = tmp_path / "live"
    ref = pr.Refinement(structure, ins, history=False)
    ref.fit(synthetic_pattern, events=LiveSession(live))

    assert (live / "fit.html").exists()
    assert (live / "events.jsonl").exists()
    status = json.loads((live / "status.json").read_text(encoding="utf-8"))
    assert status["stage"] == "profile"          # last stage of the plan
    assert status["rwp"] < 0.2

    server = serve(live, port=0, block=False)    # port 0 → ephemeral
    try:
        port = server.server_address[1]
        index = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/", timeout=5).read().decode()
        assert "pxrdref watch" in index and "events.jsonl" in index
        page = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/fit.html", timeout=5).read()
        assert b"plotly" in page.lower()
        tail = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/events.jsonl", timeout=5).read()
        assert b'"fit_end"' in tail
    finally:
        server.shutdown()
        server.server_close()


def test_cli_help_and_html(tmp_path, synthetic_pattern):
    from pxrdref.cli import main
    assert main(["--help"]) == 0

    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins, history=False)
    result = ref.fit(synthetic_pattern)
    src = tmp_path / "result.json"
    src.write_text(result.model_dump_json(), encoding="utf-8")
    out = tmp_path / "out.html"
    assert main(["html", str(src), str(out)]) == 0
    assert out.exists() and out.stat().st_size > 1_000_000


# ----------------------------------------------------------------------
# history: merge + cherry-pick
# ----------------------------------------------------------------------
def test_merge_combines_disjoint_branches(synthetic_pattern):
    """Branch A refines zero only, branch B refines the cell only; the merge
    must carry BOTH refined values and record two parents."""
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(synthetic_pattern, plan=pr.RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"])]))
    base_id = ref.result_.node_id

    # branch A: zero only
    a = ref.branch(base_id)
    a.run_stage(synthetic_pattern, Stage("zero", ["instrument.zero_shift"]))
    zero_a = a.fitted_instrument.zero_shift.value
    a_id = a.result_.node_id

    # branch B: cell only
    b = ref.branch(base_id)
    b.run_stage(synthetic_pattern, Stage("cell", ["phases.*.cell.*"]))
    cell_b = b.fitted_structure.phases[0].cell.a.value
    b_id = b.result_.node_id
    assert b.fitted_instrument.zero_shift.value != pytest.approx(zero_a)

    merge_id = b.merge(a_id, prefer="ours")
    assert b.fitted_instrument.zero_shift.value == pytest.approx(zero_a)
    assert b.fitted_structure.phases[0].cell.a.value == pytest.approx(cell_b)

    node = ref.history[merge_id]
    assert node.action.kind == "merge"
    assert set(node.parents) == {a_id, b_id}
    assert ref.history.common_ancestor(a_id, b_id) == base_id

    # a merged state is a state like any other: it must refine onward
    result = b.run_stage(synthetic_pattern,
                         Stage("both", ["instrument.zero_shift", "phases.*.cell.*"]))
    assert result.status == "converged"


def test_merge_conflict_takes_preferred_side(synthetic_pattern):
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(synthetic_pattern, plan=pr.RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"])]))
    base_id = ref.result_.node_id

    a = ref.branch(base_id)
    a.run_stage(synthetic_pattern, Stage("zero", ["instrument.zero_shift"]),
                two_theta_limits=(4.0, 20.0))
    zero_a = a.fitted_instrument.zero_shift.value

    b = ref.branch(base_id)
    b.run_stage(synthetic_pattern, Stage("zero", ["instrument.zero_shift"]))
    zero_b = b.fitted_instrument.zero_shift.value
    assert zero_a != pytest.approx(zero_b, abs=0.0)

    b.merge(a.result_.node_id, prefer="theirs")
    assert b.fitted_instrument.zero_shift.value == pytest.approx(zero_a)


def test_cherry_pick_replays_a_stage_action(synthetic_pattern):
    structure, ins = perturbed_models()
    ref = pr.Refinement(structure, ins)
    ref.fit(synthetic_pattern, plan=pr.RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("zero", ["instrument.zero_shift"]),
    ]))
    zero_node = ref.result_.node_id             # last stage = zero
    root_children = ref.history.children(ref.history.root.id)
    base_id = root_children[0].id               # after scale_bkg

    other = ref.branch(base_id)
    before = other.fitted_instrument.zero_shift.value
    result = other.cherry_pick(zero_node, synthetic_pattern)
    assert result.status == "converged"
    assert other.fitted_instrument.zero_shift.value != pytest.approx(before)
    picked = ref.history[result.node_id]
    assert picked.action.kind == "stage"
    assert picked.action.turn_on == ["instrument.zero_shift"]
    assert picked.parents == [base_id]

    with pytest.raises(ValueError, match="stage"):
        other.cherry_pick(ref.history.root.id, synthetic_pattern)
