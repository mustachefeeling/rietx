"""WP-2002 — the defaults the audit table calls answer-invariant change no number.

``rietx._audit`` tiers a default ``invariant`` only where a test shows the
answer does not move with it.  The observation channels of ``fit``,
``run_stage`` and ``refine`` (an event stream, a progress stream, a cancel
token nobody sets, a label, the run recorder, the per-stage reports, a
history tree) are that class: each is switched on here against a fit with
every channel at its default, and the answer is asserted equal to the bit.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

import rietx as rx
from rietx import runs
from rietx._about import RUNS_DIR_NAME, STATE_DIR_NAME
from rietx.optimize.cancel import CancelToken
from rietx.strategy.staged import resolve_plan
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("telemetry")

PLAN = "mccusker_default"


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


def _answer(result):
    return ([(p.path, p.value, p.stderr) for p in result.parameters],
            result.statistics.rwp, np.asarray(result.y_calc))


def _same(a, b):
    assert a[0] == b[0]
    assert a[1] == b[1]
    assert np.array_equal(a[2], b[2])


def _fit(pattern, **kw):
    structure, ins = perturbed_models()
    return _answer(rx.Refinement(structure, ins, history=False).fit(pattern, plan=PLAN, **kw))


def _stage(pattern, **kw):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    stage = resolve_plan(PLAN, "rietveld").stages[0]
    return _answer(ref.run_stage(pattern, stage, **kw))


@pytest.fixture(scope="module")
def baseline(pattern):
    return _fit(pattern)


@pytest.fixture
def recording(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    was = runs.set_enabled(True)
    try:
        yield
    finally:
        runs.set_enabled(was)


def _recorded(tmp_path):
    """How many runs the recorder wrote under the working directory: a test
    whose recorder never ran would compare two unrecorded fits and pass."""
    root = tmp_path / STATE_DIR_NAME / RUNS_DIR_NAME
    return len(list(root.glob(f"*/{runs.META_FILE}")))


@pytest.mark.parametrize("channel", ["events", "progress", "cancel", "label",
                                     "stage_reports"])
def test_a_fit_observed_is_the_fit_unobserved(pattern, baseline, tmp_path, channel):
    kw = {"events": tmp_path / "events.jsonl", "progress": io.StringIO(),
          "cancel": CancelToken(), "label": "observed", "stage_reports": True}
    _same(_fit(pattern, **{channel: kw[channel]}), baseline)


def test_a_recorded_fit_is_the_fit_unrecorded(pattern, baseline, tmp_path, recording):
    _same(_fit(pattern), baseline)
    assert _recorded(tmp_path) == 1


def test_a_stage_observed_is_the_stage_unobserved(pattern, tmp_path, recording):
    plain = _stage(pattern, telemetry=False)
    assert _recorded(tmp_path) == 0
    _same(_stage(pattern, events=tmp_path / "events.jsonl", cancel=CancelToken(),
                 label="observed"), plain)
    assert _recorded(tmp_path) == 1


def test_refine_observed_with_a_history_tree_is_refine_without(pattern, baseline,
                                                               tmp_path, recording):
    structure, ins = perturbed_models()
    _same(_answer(rx.refine(pattern, structure, ins, plan=PLAN, history=True,
                            events=tmp_path / "events.jsonl", cancel=CancelToken(),
                            label="observed")), baseline)
    assert _recorded(tmp_path) == 1
