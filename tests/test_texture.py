"""WP-1960: the spherical-harmonics texture block, its table entries and its refusals."""

import pytest

from rietx.params.vector import ParameterTable
from rietx.refine import mode_fixed_path
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import EmissionLine, Instrument, Source
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
