"""A stage starts a freed softplus row sitting on its floor a short way inside.

WP-1930, issue #832 and #836 item 3.  At the floor the softplus slope is
1e-12, so whether the solver ever lifts the row is decided by rounding: on
LaB₆ + cBN one platform reached χ²_red 9.69 and the other 12.48.  The seed is
sized by unit (``FLOOR_SEEDS``); a floor row with no size is reported.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx
from rietx.params.vector import FLOOR_SEEDS, SOFTPLUS_FLOOR_VALUE, ParameterTable
from rietx.schemas.instrument import HumpComponent
from tests import test_multi_histogram as tm
from tests.test_refine_synthetic import perturbed_models, synthesize

OUT = Path(__file__).parent / "output"

PROFILE = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=10),
    rx.Stage("profile", ["instrument.profile.x", "instrument.profile.y"], max_iter=10),
])


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


def _with_a_flat_hump():
    """The synthetic models with a hump whose height starts on its floor."""
    structure, ins = perturbed_models()
    ins.extra_components = [HumpComponent(
        position=rx.Parameter(value=30.0, unit="deg"),
        fwhm=rx.Parameter(value=6.0, min=1.0, unit="deg"),
        height=rx.Parameter(value=0.0, min=0.0, unit="counts",
                            transform="softplus"))]
    return structure, ins


def test_each_unit_starts_at_its_own_size():
    structure, ins = perturbed_models()
    assert ins.profile.y.value == 0.0 and ins.profile.x.value > 1e-4
    table = ParameterTable(structure, ins)
    seeded, unseeded = table.seed_floor([
        "instrument.profile.y", "phases.0.gauss_size", "phases.0.extinction",
        "instrument.profile.x", "instrument.profile.u", "phases.0.scale"])
    assert seeded == {"instrument.profile.y": FLOOR_SEEDS["deg"],
                      "phases.0.gauss_size": FLOOR_SEEDS["deg^2"],
                      "phases.0.extinction": FLOOR_SEEDS["um^2"]}
    assert unseeded == []
    # a variance is seeded at the square, so it adds the same width
    assert FLOOR_SEEDS["deg^2"] == pytest.approx(FLOOR_SEEDS["deg"] ** 2)
    values = {e.path: e.value for e in table.entries}
    for path, value in seeded.items():
        assert values[path] == value
    # a start somebody chose is left alone, as is an identity row at zero
    assert values["instrument.profile.x"] == ins.profile.x.value
    assert values["instrument.profile.u"] == 0.0


@pytest.mark.parametrize("value, lifted", [
    (0.0, True), (1e-12, True), (3e-11, True), (SOFTPLUS_FLOOR_VALUE, True),
    (10 * SOFTPLUS_FLOOR_VALUE, False), (1e-4, False)])
def test_only_a_row_on_its_floor_is_lifted(value, lifted):
    """Issue #832's two floor values, 1e-12 and 3e-11, both count as on it."""
    structure, ins = perturbed_models()
    ins.profile.y.value = value
    seeded, _ = ParameterTable(structure, ins).seed_floor(["instrument.profile.y"])
    assert bool(seeded) is lifted


def test_a_box_narrower_than_the_seed_takes_half_its_width():
    structure, ins = perturbed_models()
    ins.profile.y.max = 0.02
    seeded, _ = ParameterTable(structure, ins).seed_floor(["instrument.profile.y"])
    assert seeded == {"instrument.profile.y": 0.01}


def test_a_unit_with_no_size_is_left_and_named():
    structure, ins = _with_a_flat_hump()
    table = ParameterTable(structure, ins)
    path = "instrument.extra_components.0.height"
    seeded, unseeded = table.seed_floor([path])
    assert seeded == {} and unseeded == [path]
    assert {e.path: e.value for e in table.entries}[path] == 0.0


def test_a_fit_records_what_each_stage_seeded(pattern):
    structure, ins = perturbed_models()
    result = rx.Refinement(structure, ins, history=False).fit(pattern, plan=PROFILE)
    assert [s.seeded for s in result.stages] == [
        {}, {"instrument.profile.y": FLOOR_SEEDS["deg"]}]
    assert [s.floor_unseeded for s in result.stages] == [[], []]
    assert not [d for d in result.diagnostics if d.code == "SOFTPLUS_FREED_AT_FLOOR"]
    assert result.parameter("instrument.profile.y").value > SOFTPLUS_FLOOR_VALUE
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / "floor_seed_profile.png"))
    import matplotlib.pyplot as plt

    plt.close("all")


def test_a_stage_seed_is_recorded_too(pattern):
    """``Stage.seed`` lifts every softplus row below it, x included (#499)."""
    structure, ins = perturbed_models()
    plan = rx.RefinementPlan(stages=[
        PROFILE.stages[0],
        rx.Stage("profile", ["instrument.profile.x", "instrument.profile.y"],
                 max_iter=10, seed=0.01)])
    result = rx.Refinement(structure, ins, history=False).fit(pattern, plan=plan)
    assert result.stages[1].seeded == {"instrument.profile.x": 0.01,
                                       "instrument.profile.y": 0.01}


def test_a_floor_row_with_no_seed_is_a_diagnostic(pattern):
    structure, ins = _with_a_flat_hump()
    path = "instrument.extra_components.0.height"
    plan = rx.RefinementPlan(stages=[
        PROFILE.stages[0],
        rx.Stage("hump", [path], max_iter=5),
        rx.Stage("again", [path], max_iter=5)])
    result = rx.Refinement(structure, ins, history=False).fit(pattern, plan=plan)
    assert result.stages[1].floor_unseeded == [path]
    found = [d for d in result.diagnostics if d.code == "SOFTPLUS_FREED_AT_FLOOR"]
    assert len(found) == 1 and found[0].where == [path]
    # the second stage finds it on its floor again only if it never moved
    names = [s.name for s in result.stages if s.floor_unseeded]
    assert ("stage 'hump'" if names == ["hump"] else "stages 'hump', 'again'"
            ) in found[0].message


def test_run_stage_seeds_and_reports_too(pattern):
    """``run_stage`` builds its own ``StageResult``: the second call site."""
    structure, ins = _with_a_flat_hump()
    ref = rx.Refinement(structure, ins, history=False)
    path = "instrument.extra_components.0.height"
    result = ref.run_stage(pattern, rx.Stage(
        "both", ["instrument.profile.y", path], max_iter=5))
    assert result.stages[-1].seeded == {"instrument.profile.y": FLOOR_SEEDS["deg"]}
    assert result.stages[-1].floor_unseeded == [path]
    assert [d.where for d in result.diagnostics
            if d.code == "SOFTPLUS_FREED_AT_FLOOR"] == [[path]]


def test_a_joint_fit_seeds_each_histograms_row():
    patterns = [
        tm.synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                      bkg=[40.0, -6.0, 1.5], seed=1),
        tm.synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                      bkg=[70.0, 5.0, -2.0], seed=2)]
    structure, instruments = tm.perturbed_inputs()
    result = rx.refine_multi(patterns, structure, instruments, plan=PROFILE)
    seeded = result.stages[1].seeded
    assert len(seeded) == 2, seeded
    assert all(p.endswith("instrument.profile.y") for p in seeded)
    assert set(seeded.values()) == {FLOOR_SEEDS["deg"]}
    assert result.stages[1].floor_unseeded == []


def test_a_stored_stage_record_says_nobody_looked():
    """WP-1076's rule: a result from before the fields may have freed a floor
    row, so the default is ``None`` rather than an empty answer."""
    old = rx.StageResult.model_validate_json(
        '{"name": "cell", "status": "converged", "n_iterations": 3, '
        '"cost_initial": 2.0, "cost_final": 1.0}')
    assert old.seeded is None and old.floor_unseeded is None
