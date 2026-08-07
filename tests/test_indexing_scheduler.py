"""WP-1042 — the system-major scheduler.

Deterministic throughout: stub engines drive the unit order and the mid-run
stop, and the deferred-probe rows empty the search domain with a volume window
— a *logic* device — so nothing here is a load sensor (tests/CLAUDE.md).  The
wall-clock behaviour of a binding ceiling stays where WP-1037 put it, in
``test_indexing_ceiling.py``.
"""

from __future__ import annotations

import pytest

from pxrdref.indexing import engines as engines_mod
from pxrdref.indexing import index_pattern
from pxrdref.indexing.engines import (
    EngineResult,
    SearchSpec,
    merge_engine_units,
)
from pxrdref.optimize.cancel import CancelToken
from pxrdref.schemas.common import Diagnostic
from tests.test_indexing_engines import synthetic_peaks

pytestmark = pytest.mark.xdist_group("indexing-scheduler")


@pytest.fixture(scope="module")
def cubic_peaks():
    """Exact cubic positions, 150° range — the same 30-line list the ceiling
    tests use, enough for the quality gate."""
    peaks, cell = synthetic_peaks("cubic", two_theta_max=150.0)
    assert len(peaks.usable()) >= 20
    return peaks, cell


def _stub(name, log, *, cancel_on=None, token=None):
    """A registered-contract engine that records (engine, system) and claims
    what it entered — the scheduler restricts ``spec.systems`` to one system
    per unit, and the stub asserts that contract by reading ``systems[0]``."""
    def run(peaks, *, spec, quality=None, cancel=None, progress=None):
        assert len(spec.systems) == 1
        system = spec.systems[0]
        log.append((name, system))
        if cancel_on == (name, system) and token is not None:
            token.cancel()
        result = EngineResult(engine=name)
        result.systems_searched = (system,)
        result.search_complete[system] = True
        result.stats[f"{system}.seconds"] = 0.0
        return result
    return run


def _patch_registry(monkeypatch, stubs):
    monkeypatch.setattr(engines_mod, "_REGISTRY", dict(stubs))
    monkeypatch.setattr(engines_mod, "_DESCRIPTIONS",
                        {name: "stub" for name in stubs})


# ----------------------------------------------------------------------
# the schedule
# ----------------------------------------------------------------------
def test_units_run_system_major(cubic_peaks, monkeypatch):
    """Every engine finishes one system before any engine starts the next —
    the whole WP in one list equality."""
    peaks, _cell = cubic_peaks
    log: list = []
    _patch_registry(monkeypatch, {"e1": _stub("e1", log),
                                  "e2": _stub("e2", log)})
    res = index_pattern(peaks, spec=SearchSpec(
        systems=("cubic", "tetragonal", "monoclinic")))
    assert log == [("e1", "cubic"), ("e2", "cubic"),
                   ("e1", "tetragonal"), ("e2", "tetragonal"),
                   ("e1", "monoclinic"), ("e2", "monoclinic")]
    assert res.engines_run == ["e1", "e2"]
    assert res.search_complete == {"cubic": True, "tetragonal": True,
                                   "monoclinic": True}


def test_a_mid_system_stop_reads_truncated_not_complete(cubic_peaks,
                                                        monkeypatch):
    """The strict completeness rule: a system one engine never entered while
    the others finished it reads incomplete.  Before WP-1042 it read "searched
    to completion" — the engines that entered it had finished — and nothing in
    the result named the engine whose silence there was not evidence."""
    peaks, _cell = cubic_peaks
    log: list = []
    token = CancelToken()
    _patch_registry(monkeypatch, {
        "e1": _stub("e1", log),
        "e2": _stub("e2", log, cancel_on=("e2", "tetragonal"), token=token),
        "e3": _stub("e3", log)})
    res = index_pattern(peaks, spec=SearchSpec(
        systems=("cubic", "tetragonal", "monoclinic")), cancel=token)
    # e3 never entered tetragonal, and monoclinic was never reached at all
    assert log == [("e1", "cubic"), ("e2", "cubic"), ("e3", "cubic"),
                   ("e1", "tetragonal"), ("e2", "tetragonal")]
    assert res.systems_searched == ["cubic", "tetragonal"]
    assert res.search_complete == {"cubic": True, "tetragonal": False}
    # a user cancellation is never a budget statement (WP-1037's rule holds)
    assert "INDEX_BUDGET_EXHAUSTED" not in {d.code for d in res.diagnostics}


def test_an_expired_ceiling_names_every_engine_and_system(cubic_peaks,
                                                          monkeypatch):
    """The deterministic end of the budget path: a pre-expired ceiling runs
    nothing, and the diagnostic partitions the request exactly."""
    peaks, _cell = cubic_peaks
    log: list = []
    _patch_registry(monkeypatch, {"e1": _stub("e1", log)})
    res = index_pattern(peaks, spec=SearchSpec(
        systems=("cubic", "tetragonal"), total_budget_seconds=1e-9))
    assert log == []
    assert res.engines_run == [] and res.systems_searched == []
    exhausted = next(d for d in res.diagnostics
                     if d.code == "INDEX_BUDGET_EXHAUSTED")
    assert "engines not run: e1" in exhausted.where
    assert "not reached: cubic, tetragonal" in exhausted.where


# ----------------------------------------------------------------------
# the fold
# ----------------------------------------------------------------------
def test_merge_engine_units_folds_disjoint_systems():
    u1 = EngineResult(engine="e", systems_searched=("cubic",),
                      search_complete={"cubic": True},
                      stats={"cubic.seconds": 1.0, "candidates.raw": 3.0,
                             "sigma_sys_deg": 0.05})
    u2 = EngineResult(engine="e", systems_searched=("tetragonal",),
                      search_complete={"tetragonal": False},
                      stats={"tetragonal.seconds": 2.0, "candidates.raw": 4.0,
                             "sigma_sys_deg": 0.05})
    merged = merge_engine_units([u1, u2])
    assert merged.engine == "e"
    assert merged.systems_searched == ("cubic", "tetragonal")
    assert merged.search_complete == {"cubic": True, "tetragonal": False}
    # summed, not last-write-wins: each unit counted its own harvest
    assert merged.stats["candidates.raw"] == 7.0
    assert merged.stats["sigma_sys_deg"] == 0.05
    assert merged.stats["cubic.seconds"] == 1.0


def test_merge_engine_units_dedups_diagnostics_and_refuses_misuse():
    same = dict(level="info", code="X", message="same words")
    u1 = EngineResult(engine="e", diagnostics=[Diagnostic(**same)])
    u2 = EngineResult(engine="e", diagnostics=[Diagnostic(**same)])
    assert len(merge_engine_units([u1, u2]).diagnostics) == 1
    with pytest.raises(ValueError):
        merge_engine_units([])
    with pytest.raises(ValueError):
        merge_engine_units([EngineResult(engine="a"),
                            EngineResult(engine="b")])


# ----------------------------------------------------------------------
# the deferred probe
# ----------------------------------------------------------------------
def test_probe_false_skips_the_in_engine_probe(cubic_peaks, monkeypatch):
    """The engine half of the deferral: ``probe=False`` suppresses the
    in-engine ask even on an empty harvest; the default keeps it."""
    import pxrdref.indexing.trial_error as te

    peaks, _cell = cubic_peaks
    calls: list = []
    monkeypatch.setattr(te, "_dominant_zone_probe",
                        lambda *a, **k: calls.append(1))
    # a volume window that admits no cell: the harvest is empty by logic
    spec = SearchSpec(systems=("cubic",), max_volume=15.5)
    res = te.search_trial_error(peaks, spec=spec, probe=False)
    assert not res.candidates and calls == []
    te.search_trial_error(peaks, spec=spec)
    assert calls == [1]


def test_the_scheduler_asks_the_probe_once_over_entered_systems(
        cubic_peaks, monkeypatch):
    """The scheduler half: per-system units silence their own probes, and the
    run asks once at the end — over the systems the engine entered, only when
    the merged harvest is empty."""
    import pxrdref.indexing.trial_error as te

    peaks, _cell = cubic_peaks
    calls: list = []

    def fake_probe(peaks_, spec_, q_all, sigma, tt_all, tt_max, systems,
                   quality, cancel, *, progress=None):
        calls.append(tuple(systems))
        return None

    monkeypatch.setattr(te, "_dominant_zone_probe", fake_probe)
    res = index_pattern(peaks, engines=("trial_error",),
                        spec=SearchSpec(systems=("cubic", "tetragonal"),
                                        max_volume=15.5))
    assert res.candidates == []
    assert calls == [("cubic", "tetragonal")]
    assert "trial_error.probe.seconds" in res.engine_stats
