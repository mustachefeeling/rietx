"""What a joint fit reports about itself (WP-1341, issue #252).

A joint refinement used to converge and leave nothing to inspect: no event
log, no convergence figure, no report.  These tests hold each piece the WP
added.  The fixture is test_multi_histogram's synthetic LaB6 pair at two
wavelengths, so no number here is a claim about a specimen.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from rietx import MultiHistogramRefinement, Stage
from rietx.optimize.statistics import MAX_SHIFT_CONVERGED
from rietx.strategy.staged import RefinementPlan
from tests.test_multi_histogram import perturbed_inputs, synthesize

OUT = Path(__file__).parent / "output"

TURN_ON = ["phases.*.scale", "instrument.background.*", "phases.*.cell.*",
           "instrument.zero_shift"]


@pytest.fixture(scope="module")
def two_patterns():
    return [
        synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                   bkg=[40.0, -6.0, 1.5], seed=1),
        synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                   bkg=[70.0, 5.0, -2.0], seed=2),
    ]


def _plot(result, stem: str) -> None:
    OUT.mkdir(exist_ok=True)
    for h in range(len(result.histograms)):
        result.for_histogram(h).plot(OUT / f"{stem}_h{h}.png")


# ---------------------------------------------------- the convergence figure --
@pytest.mark.parametrize("solver", ["lm", "trf"])
def test_a_joint_fit_measures_how_far_it_was_still_moving(two_patterns, solver):
    """McCusker §7's quantity on both branches, now on the joint θ.

    Measured 2026-10-12 on this fixture: converged 5e-7 to 2.2e-3 across both
    drivers, unit and 1:4 weights; starved to one iteration, 4.0 (LM) and 17.9
    (TRF).  Both sides clear the 0.1 band by 40× or more, so neither assertion
    senses where a solver happened to stop.
    """
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments, solver=solver)
    done = ref.fit(two_patterns, plan="mccusker_default", weights=[1.0, 4.0])
    assert done.status == "converged"
    shift = done.statistics.max_shift_over_esd
    assert shift is not None and shift < MAX_SHIFT_CONVERGED
    _plot(done, f"joint_report_shift_{solver}")

    # whole-fit: the per-histogram statistics have no writer for it, and the
    # view that keeps the joint stages carries the joint figure beside them
    for h, hist in enumerate(done.histograms):
        assert hist.statistics.max_shift_over_esd is None
        assert done.for_histogram(h).statistics.max_shift_over_esd == shift
    assert f"max|Δθ|/esd={shift:.3f}" in str(done)

    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments, solver=solver)
    starved = ref.fit(two_patterns, plan=RefinementPlan(
        stages=[Stage("starved", turn_on=TURN_ON, max_iter=1)]))
    assert starved.status == "max_iter"
    assert starved.statistics.max_shift_over_esd > MAX_SHIFT_CONVERGED
