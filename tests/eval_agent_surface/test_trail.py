"""The projection's two attribution rules, and the shim's target list.

Everything here is a committed fixture or a subprocess: no LLM, no network, no
refinement.  What is pinned is the *harness contract* — that a run's bill and
its refinement seconds come out the way PROTOCOL.md 1.1 says they do — because
both rules were learned by getting them wrong, and neither survives being
remembered rather than asserted.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.eval_agent_surface import trail

FIXTURE = Path(__file__).parent / "fixture_trail"
HARNESS = Path(__file__).parent


def _rows():
    return trail.load(FIXTURE / "transcript.jsonl")


def _trace_rows():
    return trail.load(FIXTURE / "trace.jsonl")


def test_usage_is_summed_once_per_message_id():
    """A thinking block and its tool_use are two records of one API call.

    The fixture's `msg_A` is written twice with the same usage, which is what
    the harness does.  Summing per record over-counts — by 151/90 on the
    2026-08-27 audit's first pass, 23.9 M against a true 14.6 M — so the test
    computes the wrong answer too and asserts they differ.
    """
    rows = _rows()
    bill = trail.usage(rows)

    naive = sum(r["message"]["usage"]["cache_read_input_tokens"]
                for r in rows if r.get("type") == "assistant")

    assert bill.api_calls == 4
    assert bill.cache_read == 50_000 + 60_000 + 70_000 + 80_000
    assert naive == bill.cache_read + 50_000
    assert bill.output_tokens == 60 + 30 + 25 + 500  # last record of msg_A wins
    assert bill.models == {"claude-opus-5": 4}


def test_a_tool_call_carries_its_timing_size_and_error_flag():
    calls = trail.tool_calls(_rows())
    assert [c.tool for c in calls] == ["Bash", "Bash", "Bash"]
    assert [c.offset for c in calls] == [2.0, 5.0, 30.0]
    assert [c.duration for c in calls] == [1.0, 20.0, 2.0]
    assert [c.error for c in calls] == [False, False, True]
    assert calls[0].out_chars == len("host.cif\nramp_00_25C.xye\n")


def test_a_call_whose_result_never_arrived_answers_neither_way():
    """A session can end with a call in flight; `False` would be a lie."""
    rows = [r for r in _rows()
            if not (r.get("type") == "user" and r["message"]["content"][0]
                    .get("tool_use_id") == "call_3")]
    unanswered = [c for c in trail.tool_calls(rows) if c.index == 3][0]
    assert unanswered.error is None
    assert unanswered.out_chars is None
    assert unanswered.duration is None
    assert " ? " in unanswered.line()


def test_fit_seconds_come_from_the_trace_and_not_from_the_command_head():
    """The rule the campaign's projection could not follow.

    The fixture's fit ran inside a backgrounded driver script, so no command
    head names a fit and no grep over the transcript could find one.  The shim
    timed it from inside the process, which is the only place the fact exists.
    """
    calls = trail.tool_calls(_rows())
    assert not any("fit" in c.head or "refine" in c.head for c in calls)

    seen = trail.trace(_trace_rows())
    assert seen.fit_calls == 1
    assert seen.fit_seconds == 12.5


def test_nested_calls_are_counted_once_at_depth_zero():
    """`refine_sequential` *is* `SequentialRefinement.fit` one frame down.

    Both are traced, so a sum over names would report 24.9 s for a 12.5 s fit.
    `calls` still counts the inner one — R2 asks which surfaces were reached,
    and the inner name is one of them — while `seconds` holds depth-0 only.
    """
    seen = trail.trace(_trace_rows())
    assert seen.calls["SequentialRefinement.fit"] == 1
    assert seen.outer["SequentialRefinement.fit"] == 0
    assert seen.seconds.get("SequentialRefinement.fit", 0.0) == 0.0
    assert seen.seconds["refine_sequential"] == 12.5


def test_the_per_process_floor_is_summed_over_every_traced_process():
    seen = trail.trace(_trace_rows())
    assert seen.processes == 2
    assert seen.import_seconds == 1.9 + 1.8
    assert seen.process_wall == 20.0 + 2.5
    assert seen.floor_share == (1.9 + 1.8) / (20.0 + 2.5)


def test_allowlisted_keyword_values_survive_into_the_projection():
    """R11's three sub-rows are values, not keyword names."""
    seen = trail.trace(_trace_rows())
    assert seen.kwargs["SeriesResult.summary"]["deliverable=series"] == 1
    assert seen.kwargs["refine_sequential"]["verify_discontinuities=True"] == 1
    assert seen.kwargs["refine_sequential"]["direction=both"] == 1
    assert seen.kwargs["refine_sequential"]["carry"] == 1  # a name, never a value


def test_an_unresolved_target_is_reported_rather_than_swallowed():
    seen = trail.trace(_trace_rows())
    assert seen.missing == {"Refinement.nonesuch"}


def test_render_runs_over_both_files():
    text = trail.render(_rows(), _trace_rows())
    assert "4 API calls" in text
    assert "refinement 12.5 s in 1 fit calls" in text
    assert "targets that did not resolve: Refinement.nonesuch" in text


def test_every_shim_target_resolves_against_this_build(tmp_path):
    """The guard that would have caught `SequentialRefinement.run`'s rename.

    A stale target and an unreached surface look identical in the log, so the
    shim reports what it could not resolve and this asserts the list is empty.
    Run in a subprocess: the shim patches `rietx` globally and appends to a log,
    neither of which belongs in the suite's own interpreter.
    """
    log = tmp_path / "trace.jsonl"
    env = dict(os.environ, RIETX_SURFACE_LOG=str(log),
               PYTHONPATH=os.pathsep.join([str(HARNESS), os.environ.get("PYTHONPATH", "")]))
    proc = subprocess.run(
        [sys.executable, "-c", "import rietx_surface_trace, rietx; rietx.capabilities()"],
        env=env, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr

    rows = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    imports = [r for r in rows if r.get("event") == "import"]
    assert len(imports) == 1
    assert imports[0]["missing"] == [], (
        "shim targets that no longer resolve — a renamed or deleted surface "
        "would otherwise be scored as one no agent reached"
    )
    assert imports[0]["import_dt"] > 0
    assert any(r.get("name") == "capabilities" for r in rows)
    assert [r for r in rows if r.get("event") == "exit"], "atexit did not fire"
