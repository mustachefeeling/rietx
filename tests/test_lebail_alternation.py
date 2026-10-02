"""WP-1323: the Le Bail alternation has a stop rule, and the package owns it.

The pattern is 11-BM LaB6 + cBN, Le Bail scaffolds, ``profile_only``.  It is the
in-tree stand-in for issue #210's multi-phase lab pattern, and it shows the same
three shapes depending on where the cells start: the exact cells give a pass 2
that is *worse* than pass 1, +0.3 % converges, and +2 % never settles.  The
per-pass numbers each test quotes are the hand loop's, measured before the
alternation moved into ``fit`` (WP-1323 handover).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

import rietx as rx
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.plan import PlanSpec
from rietx.schemas.structure import lebail_scaffold
from rietx.strategy.staged import resolve_plan

DATA = Path(__file__).parent / "data"
PATTERN = DATA / "11BM_LaB6_cBN_mg2044.xye"
LIMITS = (5.1, 50.0)
CODE = "LEBAIL_ALTERNATION_STOPPED"


@pytest.fixture(scope="module")
def pattern():
    if not PATTERN.exists():
        pytest.skip("11-BM LaB6+cBN dataset not present")
    return rx.read_pattern(PATTERN)


def _refinement(cell_scale: float) -> rx.Refinement:
    lab6 = lebail_scaffold("P m -3 m", [4.1569 * cell_scale] * 3 + [90.0] * 3,
                           name="LaB6")
    cbn = lebail_scaffold("F -4 3 m", [3.6165 * cell_scale] * 3 + [90.0] * 3,
                          name="cBN")
    ins = rx.Instrument.debye_scherrer(wavelength=0.41368)
    ins.source.dispersion = None
    ins.profile.w.value = 2e-5
    ins.profile.x.value = 2e-3
    ins.background = BackgroundChebyshev.with_terms(8)
    return rx.Refinement(rx.Structure(phases=[lab6.phases[0], cbn.phases[0]]),
                         ins, history=False)


def _plan(passes: int):
    return dataclasses.replace(resolve_plan("profile_only", "lebail"),
                               lebail_passes=passes)


def _fit(ref, data, passes: int):
    return ref.fit(data, mode="lebail", plan=_plan(passes),
                   two_theta_limits=LIMITS, telemetry=False)


def _stop(result):
    found = [d for d in result.diagnostics if d.code == CODE]
    assert len(found) == 1
    return found[0]


def _plot(result, name):
    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / name))


def test_one_pass_is_the_plain_fit_and_says_nothing(pattern):
    """``lebail_passes=1`` is every fit made before the field: no loop, no row."""
    plain = _refinement(1.0).fit(data=pattern, mode="lebail",
                                 plan="profile_only", two_theta_limits=LIMITS,
                                 telemetry=False)
    one = _fit(_refinement(1.0), pattern, 1)
    assert one.statistics.rwp == plain.statistics.rwp
    assert not [d for d in one.diagnostics if d.code == CODE]


def test_a_pass_that_comes_back_worse_stops_the_loop_and_pass_one_is_kept(pattern):
    """Exact cells: the hand loop read 16.821 then 16.907 and sat there."""
    ref = _refinement(1.0)
    result = _fit(ref, pattern, 8)
    stop = _stop(result)
    assert stop.level == "warning"
    assert "did not lower Rwp" in stop.message
    assert "pass 1 of 2 was kept" in stop.message
    assert result.statistics.rwp == pytest.approx(0.16821, abs=2e-5)
    assert stop.value == result.statistics.rwp
    assert "16.821, 16.907" in stop.message
    assert CODE in str(result)              # the termination view carries it
    _plot(result, "lebail_alternation_exact.png")


def test_a_converging_run_is_not_cut_short_and_ends_at_a_fixed_point(pattern):
    """+0.3 % cells: 16.987, 16.969, 16.967 and nothing more to gain."""
    result = _fit(_refinement(1.003), pattern, 8)
    stop = _stop(result)
    assert stop.level == "info"
    assert "fixed point" in stop.message
    assert "pass 3 of 3 was kept" in stop.message
    assert result.statistics.rwp == pytest.approx(0.16967, abs=2e-5)
    _plot(result, "lebail_alternation_converged.png")


def test_the_cap_is_a_cap_and_says_it_truncated(pattern):
    """Two passes of a run that was still falling: truncated, not finished."""
    result = _fit(_refinement(1.003), pattern, 2)
    stop = _stop(result)
    assert stop.level == "warning"
    assert "cap of 2 passes" in stop.message
    assert "pass 2 of 2 was kept" in stop.message


@pytest.mark.slow       # ~40-80 s: the +2 % start wanders through four passes
def test_the_state_the_loop_keeps_is_the_state_a_hand_loop_would_continue_from(pattern):
    """Restoring the best pass must not hand the next ``fit`` a start the hand
    loop never had.  Seeding the restored intensities does exactly that: the
    +2 % start measured 254.09 % against the loop's 194.56 % on pass 4."""
    ref = _refinement(1.02)
    result = _fit(ref, pattern, 8)
    stop = _stop(result)
    assert "pass 3 of 4 was kept" in stop.message
    assert result.statistics.rwp == pytest.approx(1.75104, abs=1e-4)
    nxt = ref.fit(pattern, mode="lebail", plan="profile_only",
                  two_theta_limits=LIMITS, telemetry=False)
    assert nxt.statistics.rwp == pytest.approx(1.94562, abs=1e-4)
    _plot(result, "lebail_alternation_wander_kept.png")


def test_the_field_crosses_the_mirror_both_ways_and_refuses_zero():
    plan = _plan(5)
    spec = PlanSpec.from_plan(plan)
    assert spec.lebail_passes == 5
    assert spec.to_plan().lebail_passes == 5
    assert PlanSpec.model_validate(spec.model_dump(mode="json")).lebail_passes == 5
    with pytest.raises(ValueError):
        PlanSpec(stages=[], lebail_passes=0)
