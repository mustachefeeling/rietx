"""WP-1960: the spherical-harmonics texture block, its table entries and its refusals."""

import typing

import numpy as np
import pytest

import rietx as rx
from rietx.model.preferred_orientation import TEXTURE_SAMPLE_PSI_DEG
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.params.vector import ParameterTable
from rietx.refine import _unsupported_phase_paths, mode_fixed_path
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import EmissionLine, Geometry, Instrument, Source
from rietx.schemas.structure import (
    Atom,
    Cell,
    Phase,
    PreferredOrientation,
    SphericalHarmonicTexture,
    Structure,
)


def _cell(a, c, gamma=90.0):
    p = Parameter
    return Cell(a=p(value=a), b=p(value=a), c=p(value=c), alpha=p(value=90.0),
                beta=p(value=90.0), gamma=p(value=gamma))


def _phase(space_group="P -3 m 1", cell=None, **kw):
    cell = cell or _cell(3.15, 4.77, 120.0)
    p = Parameter
    return Phase(name="x", space_group=space_group, cell=cell,
                 atoms=[Atom(label="Mg", species="Mg", x=p(value=0.0), y=p(value=0.0),
                             z=p(value=0.0))], **kw)


def _table(phase):
    instrument = Instrument(source=Source(lines=[EmissionLine(wavelength=1.540598)]))
    return ParameterTable(Structure(phases=[phase]), instrument)


def _texture_rows(table):
    return {e.path: e for e in table.entries if ".texture." in e.path}


# ------------------------------------------------------------------ the schema
def test_the_block_round_trips_through_json():
    phase = _phase(texture=SphericalHarmonicTexture(order=4, coefficients={
        "c2_0": Parameter(value=0.31, vary=True), "c4_3": Parameter(value=-0.05)}))
    again = Phase.model_validate_json(phase.model_dump_json())
    assert again == phase
    assert again.texture.coefficients["c2_0"].vary is True


@pytest.mark.parametrize("order", [0, 1, 3, 7, -2])
def test_an_odd_or_absent_order_is_refused(order):
    with pytest.raises(ValueError, match="even and at least 2"):
        SphericalHarmonicTexture(order=order)


@pytest.mark.parametrize("name", ["c3_0", "c4_5", "c6_0", "c0_0", "C4_0", "c4-4", "c4_m4"])
def test_a_malformed_name_is_refused(name):
    with pytest.raises(ValueError, match="c<l>_<n>"):
        SphericalHarmonicTexture(order=4, coefficients={name: Parameter(value=0.0)})


def test_a_phase_declares_one_orientation_model():
    with pytest.raises(ValueError, match="both preferred_orientation and texture"):
        _phase(preferred_orientation=PreferredOrientation(axis=(0, 0, 1)),
               texture=SphericalHarmonicTexture(order=2))


# ------------------------------------------------------------------- the table
def test_every_allowed_term_gets_an_entry_held_at_zero():
    rows = _texture_rows(_table(_phase(texture=SphericalHarmonicTexture(order=6))))
    # -3m1 to order 6: one term at l = 2, two at l = 4, three at l = 6
    assert list(rows) == [f"phases.0.texture.{n}" for n in
                          ("c2_0", "c4_0", "c4_3", "c6_0", "c6_3", "c6_6")]
    assert all(e.value == 0.0 and not e.vary for e in rows.values())


def test_a_declared_coefficient_keeps_its_value_and_flag():
    block = SphericalHarmonicTexture(order=4, coefficients={
        "c2_0": Parameter(value=0.4, vary=True)})
    rows = _texture_rows(_table(_phase(texture=block)))
    assert rows["phases.0.texture.c2_0"].value == 0.4
    assert rows["phases.0.texture.c2_0"].vary
    assert not rows["phases.0.texture.c4_3"].vary


def test_a_term_the_laue_class_forbids_is_refused_by_name():
    # -3m1 carries sin 3β at l = 4 as c4_3; -3 adds c4_neg3, which -3m1 does not have
    block = SphericalHarmonicTexture(order=4, coefficients={"c4_neg3": Parameter(value=0.1)})
    with pytest.raises(ValueError, match=r"c4_neg3 is not a term .* c2_0, c4_0, c4_3"):
        _table(_phase(texture=block))


def test_an_order_with_no_term_names_the_lowest_that_has_one():
    cubic = _phase("P m -3 m", _cell(4.2, 4.2), texture=SphericalHarmonicTexture(order=2))
    with pytest.raises(ValueError, match="lowest order that allows one is 4"):
        _table(cubic)


def test_writing_back_fills_in_the_terms_the_block_left_out():
    phase = _phase(texture=SphericalHarmonicTexture(order=4))
    table = _table(phase)
    table.entries[table._paths["phases.0.texture.c4_3"]].value = -0.07
    structure = Structure(phases=[phase.model_copy(deep=True)])
    table.apply_to_models(structure, Instrument(
        source=Source(lines=[EmissionLine(wavelength=1.540598)])))
    written = structure.phases[0].texture.coefficients
    assert sorted(written) == ["c2_0", "c4_0", "c4_3"]
    assert written["c4_3"].value == -0.07


@pytest.mark.parametrize("mode, fixed", [("rietveld", False), ("lebail", True),
                                         ("pawley", True)])
def test_an_intensity_model_force_fixes_the_coefficients(mode, fixed):
    assert mode_fixed_path("phases.0.texture.c2_0", mode) is fixed
    assert mode_fixed_path("phases.0.texture.c4_neg3", mode) is fixed


# ------------------------------------------------------------- the forward model
def test_the_sample_angle_covers_every_geometry():
    kinds = set(typing.get_args(Geometry.model_fields["kind"].annotation))
    assert set(TEXTURE_SAMPLE_PSI_DEG) == kinds


def _textured_state():
    from tests.test_cross_backend import _state_texture

    return _state_texture()[:2]


def test_each_texture_column_is_exact_at_a_whole_unit_step():
    """The branch oracle: the intensity is linear in C, so a difference quotient
    in physical units has no truncation error at any step (root CLAUDE.md)."""
    model, table = _textured_state()
    theta = np.array([table.entries[table._paths[q]].value for q in table.free_paths])
    jac = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    checked = 0
    for c, path in enumerate(table.free_paths):
        if ".texture." not in path:
            continue
        step = theta.copy()
        step[c] += 1.0
        quotient = residual(step) - r0
        assert np.max(np.abs(jac[:, c] - quotient)) <= 1e-9 * np.max(np.abs(quotient)), path
        checked += 1
    assert checked == 4


def test_zero_coefficients_are_bit_identical_to_no_block():
    grid = np.arange(15.0, 95.0, 0.02)
    with_block = _phase(texture=SphericalHarmonicTexture(order=6))
    without = _phase()
    ins = Instrument.bragg_brentano()
    y_with = rx.Refinement(Structure(phases=[with_block]), ins).predict(grid)
    y_without = rx.Refinement(Structure(phases=[without]), ins).predict(grid)
    assert np.array_equal(np.asarray(y_with), np.asarray(y_without))


def test_the_absent_phase_hold_reaches_the_coefficients():
    """WP-1301's hold selects by column reach under ``phases.{ip}.``, scale aside."""
    model, table = _textured_state()
    held = _unsupported_phase_paths(model, table, support=np.array([0.0]))
    assert {p for p in table.free_paths if ".texture." in p} <= set(held)
    assert "phases.0.scale" not in held


#: One phase per Laue class the recovery runs over, each with the terms it allows to order 4.
_RECOVERY = {
    "m-3m": ("P m -3 m", (4.2, 4.2, 4.2, 90.0, 90.0, 90.0), {"c4_1": 0.4}),
    "6/mmm": ("P 6/m m m", (3.1, 3.1, 5.0, 90.0, 90.0, 120.0),
              {"c2_0": 0.5, "c4_0": -0.2}),
    # brucite's O, not Mg alone: hkl and khl overlap exactly in -3m1 and c4_3's
    # sin 3β takes opposite signs on them, so with equal |F|² the term cancels
    # within every pair and only roundoff is left to fit
    "-3m1": ("P -3 m 1", (3.147, 3.147, 4.769, 90.0, 90.0, 120.0),
             {"c2_0": 0.8, "c4_0": 0.3, "c4_3": -0.15}),
    "mmm": ("P m m m", (3.6, 4.4, 5.2, 90.0, 90.0, 90.0),
            {"c2_0": 0.4, "c2_2": -0.25, "c4_0": 0.1, "c4_2": 0.08, "c4_4": -0.12}),
    "2/m": ("P 1 2/m 1", (4.1, 3.6, 5.3, 90.0, 104.0, 90.0),
            {"c2_neg2": 0.15, "c2_0": 0.45, "c2_2": -0.2, "c4_0": 0.1, "c4_2": 0.05}),
}


def _recovery_phase(space_group, cell, coefficients, *, vary):
    p = Parameter
    lengths = dict(zip(("a", "b", "c", "alpha", "beta", "gamma"), cell))
    return Phase(name="t", space_group=space_group,
                 cell=Cell(**{k: p(value=v) for k, v in lengths.items()}),
                 scale=p(value=1e-3),
                 atoms=[Atom(label="Mg", species="Mg", x=p(value=0.0), y=p(value=0.0),
                             z=p(value=0.0), biso=p(value=0.5))]
                 + ([Atom(label="O", species="O", x=p(value=1 / 3), y=p(value=2 / 3),
                          z=p(value=0.22), biso=p(value=0.8))]
                    if space_group == "P -3 m 1" else []),
                 texture=SphericalHarmonicTexture(order=4, coefficients={
                     k: p(value=v if not vary else 0.0, vary=vary)
                     for k, v in coefficients.items()}))


@pytest.mark.parametrize("geometry", ["bragg_brentano", "debye_scherrer"])
@pytest.mark.parametrize("label", sorted(_RECOVERY))
def test_noise_free_coefficients_are_recovered_from_zero(label, geometry):
    space_group, cell, truth = _RECOVERY[label]
    ins = (Instrument.bragg_brentano() if geometry == "bragg_brentano"
           else Instrument.debye_scherrer(1.540598))
    grid = np.arange(10.0, 120.0, 0.02)
    y = np.asarray(rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=False)]), ins).predict(grid)) + 20.0
    data = rx.PatternData(two_theta=grid.tolist(), intensity=y.tolist())
    fit = rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=True)]), ins.model_copy(deep=True))
    result = fit.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("texture", ["phases.*.scale", "instrument.background.c*",
                             "phases.*.texture.*"])]))
    got = {r.path.rsplit(".", 1)[1]: r.value for r in result.parameters
           if ".texture." in r.path}
    for name, value in truth.items():
        assert got[name] == pytest.approx(value, rel=1e-6), name


# -------------------------------------------------------- positivity and the record
def test_the_inequality_rows_reproduce_p_at_the_start():
    from rietx.optimize.least_squares import texture_positivity_inequalities

    model, table = _textured_state()
    x0 = table.x0()
    (block,) = texture_positivity_inequalities(model, table, x0)
    values = table.decode(x0)
    cell = tuple(values[f"phases.0.cell.{k}"] for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    p = np.asarray(model._texture_factors(0, values, cell))
    assert np.allclose(block.T @ x0 + block.c, p, rtol=0, atol=1e-12)


def _negative_density_case(solver):
    """A strongly platy specimen (March-Dollase r = 0.4 along c) fitted at order 2.

    Two terms cannot follow a density that steep, and the best order-2 fit
    wants P < 0 on the (hk0) reflections, so the default driver must stop at
    the face P = 0 there and TRF need not.
    """
    space_group, cell, _ = _RECOVERY["6/mmm"]
    ins = Instrument.bragg_brentano()
    grid = np.arange(10.0, 120.0, 0.02)
    platy = _recovery_phase(space_group, cell, {}, vary=False).model_copy(update={
        "texture": None,
        "preferred_orientation": PreferredOrientation(axis=(0, 0, 1),
                                                      r=Parameter(value=0.4))})
    y = np.asarray(rx.Refinement(Structure(phases=[platy]), ins).predict(grid))
    data = rx.PatternData(two_theta=grid.tolist(), intensity=(y + 50.0).tolist())
    start = _recovery_phase(space_group, cell, {}, vary=False).model_copy(update={
        "texture": SphericalHarmonicTexture(order=2, coefficients={
            "c2_0": Parameter(value=0.0, vary=True)})})
    fit = rx.Refinement(Structure(phases=[start]), ins.model_copy(deep=True),
                        solver=solver)
    return fit.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("texture", ["phases.*.scale", "instrument.background.c*",
                             "phases.*.texture.*"])]))


def test_the_default_driver_holds_p_at_the_reflections():
    result = _negative_density_case("lm")
    (row,) = result.texture
    assert row.min_p_reflections >= -1e-9
    assert row.texture_index > 1.0


def test_trf_goes_negative_and_the_guard_says_so():
    result = _negative_density_case("trf")
    (row,) = result.texture
    assert row.min_p_reflections < -0.1
    (diag,) = [d for d in result.diagnostics if d.code == "TEXTURE_NOT_POSITIVE"]
    assert diag.where == ["phases.0.texture"]
    assert diag.value == pytest.approx(row.min_p_sphere)
    assert "goes below zero" in diag.message


def test_the_record_matches_its_definition():
    space_group, cell, truth = _RECOVERY["mmm"]
    ins = Instrument.bragg_brentano()
    grid = np.arange(10.0, 120.0, 0.02)
    y = np.asarray(rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=False)]), ins).predict(grid)) + 20.0
    fit = rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=True)]), ins.model_copy(deep=True))
    result = fit.fit(rx.PatternData(two_theta=grid.tolist(), intensity=y.tolist()),
                     plan=rx.RefinementPlan(stages=[
                         rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
                         rx.Stage("texture", ["phases.*.scale", "instrument.background.c*",
                                              "phases.*.texture.*"])]))
    (row,) = result.texture
    expected = 1.0 + sum(v * v / (2 * int(k[1:].split("_")[0]) + 1) for k, v in truth.items())
    assert row.name == "t"
    assert row.texture_index == pytest.approx(expected, rel=1e-6)
    assert row.min_p_sphere <= row.min_p_reflections
    assert not [d for d in result.diagnostics if d.code == "TEXTURE_NOT_POSITIVE"]


def test_the_structural_plan_frees_a_declared_block_with_march_dollase():
    from rietx.strategy.staged import PLAN_PRESETS

    (stage,) = [st for st in PLAN_PRESETS["mccusker_structural"]().stages
                if "phases.*.preferred_orientation.r" in st.turn_on]
    table = _table(_phase(texture=SphericalHarmonicTexture(order=4)))
    assert table.set_vary(stage.turn_on, True) == [
        "phases.0.texture.c2_0", "phases.0.texture.c4_0", "phases.0.texture.c4_3"]


@pytest.mark.parametrize("label", ["-3m1", "mmm"])
def test_poisson_noise_recovers_the_coefficients_within_three_esd(label):
    space_group, cell, truth = _RECOVERY[label]
    ins = Instrument.bragg_brentano()
    grid = np.arange(10.0, 120.0, 0.02)
    clean = np.asarray(rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=False)]), ins).predict(grid)) + 20.0
    counts = np.random.default_rng(1960).poisson(clean).astype(float)
    fit = rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=True)]), ins.model_copy(deep=True))
    result = fit.fit(rx.PatternData(two_theta=grid.tolist(), intensity=counts.tolist()),
                     plan=rx.RefinementPlan(stages=[
                         rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
                         rx.Stage("texture", ["phases.*.scale", "instrument.background.c*",
                                              "phases.*.texture.*"])]))
    rows = {r.path.rsplit(".", 1)[1]: r for r in result.parameters if ".texture." in r.path}
    for name, value in truth.items():
        assert abs(rows[name].value - value) < 3.0 * rows[name].stderr, name


def test_a_nearly_symmetric_cell_builds_the_same_terms():
    """The table accepts a fixed angle 1e-3° off and a tied length at any stored
    value; the basis is built on the cell the symmetry demands (review, WP-1960)."""
    off = _phase(cell=_cell(3.15, 4.77, 120.0005), texture=SphericalHarmonicTexture(order=6))
    exact = _phase(texture=SphericalHarmonicTexture(order=6))
    assert list(_texture_rows(_table(off))) == list(_texture_rows(_table(exact)))
