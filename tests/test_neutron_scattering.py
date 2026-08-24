"""Bound coherent neutron scattering lengths.

The tests worth having here are the ones that pin the three ways neutron
scattering differs from X-ray, because each one breaks an assumption the X-ray
path is entitled to make: b can be negative, b depends on isotope, and the
table is thermal-only. A test that merely re-read a number out of the file it
was loaded from would pin nothing.
"""

from __future__ import annotations

import math

import pytest

from rietx.crystallography.neutron import (
    RESONANT_ABSORBERS,
    b_coh,
    is_resonant_absorber,
    normalize_species,
    properties,
)


# Values quoted from Sears (1992) Neutron News 3(3), 26-37 / International
# Tables C Table 4.4.4.1. Written out here rather than read from the data file
# so that a corrupted or truncated table fails this test instead of agreeing
# with itself.
@pytest.mark.parametrize("species, expected_fm", [
    ("Al", 3.449),      # the BT-1 Al2O3 standard, with O below
    ("O", 5.803),
    ("Cr", 3.635),
    ("V", -0.3824),     # negative, and near-null: the standard sample can
    ("Ti", -3.438),     # negative
    ("Mn", -3.73),      # negative
    ("H", -3.7390),     # negative, natural abundance
    ("2H", 6.671),      # positive, and a different nucleus
])
def test_tabulated_scattering_lengths(species, expected_fm):
    assert b_coh(species) == pytest.approx(expected_fm, abs=5e-4)


def test_scattering_length_may_be_negative():
    """A 180-degree phase shift, not an error state.

    Anything that takes abs() or sqrt() of a single species' amplitude is wrong
    for neutrons, so the sign has to survive the lookup.
    """
    assert b_coh("V") < 0.0
    assert b_coh("Ti") < 0.0
    assert b_coh("Mn") < 0.0
    assert b_coh("Li") < 0.0
    assert b_coh("Al") > 0.0          # and the common case is still positive


def test_isotope_is_the_identity_not_the_element():
    """b(1H) and b(2H) differ in sign, which is why deuteration is routine.

    This is the opposite convention to dispersion.normalize_element, where an
    ion resolves to its element because f'/f'' is a core-level effect. Here the
    nucleus *is* the scatterer, so the mass number must not be discarded.
    """
    assert b_coh("1H") < 0.0
    assert b_coh("2H") > 0.0
    assert b_coh("H") * b_coh("D") < 0.0
    # and the natural-abundance average is not either isotope
    assert b_coh("H") != pytest.approx(b_coh("2H"), abs=1e-3)


def test_ionic_charge_is_discarded_but_mass_number_is_kept():
    """Both charge spellings, since TOPAS writes sign-first."""
    assert normalize_species("Fe3+") == "Fe"
    assert normalize_species("Fe+3") == "Fe"
    assert normalize_species("O2-") == "O"
    assert normalize_species("O-2") == "O"
    assert b_coh("Fe3+") == b_coh("Fe")
    # a mass number selects a different nucleus and must survive
    assert normalize_species("2H") == "2H"
    assert normalize_species("D") == "2H"
    assert normalize_species("157Gd") == "157Gd"


def test_vanadium_is_the_standard_can():
    """Near-null coherent, overwhelmingly incoherent.

    This is *why* a V can contributes a smooth background and almost no Bragg
    peaks, and it is the quantitative form of that folklore.
    """
    v = properties("V")
    assert abs(v["b_coh_fm"]) < 0.5
    assert v["xs_inc_barn"] > 100.0 * v["xs_coh_barn"]


def test_hydrogen_is_the_incoherent_problem():
    """The reason deuterated samples exist, stated as a number."""
    h = properties("H")
    d = properties("2H")
    assert h["xs_inc_barn"] > 10.0 * d["xs_inc_barn"]


def test_resonant_absorbers_are_flagged():
    """Thermal b is incomplete, not wrong, for these — a fence not an oversight."""
    assert is_resonant_absorber("Gd")
    assert is_resonant_absorber("157Gd")
    assert is_resonant_absorber("Cd")
    assert not is_resonant_absorber("Al")
    assert not is_resonant_absorber("O")
    # every listed absorber must resolve through the same normalisation
    for species in RESONANT_ABSORBERS:
        assert is_resonant_absorber(species)


def test_unknown_species_raises_naming_it():
    """A missing species is a modelling error the caller must see.

    Never a substituted zero: that would delete a site from the structure
    factor without changing the shape of anything.
    """
    with pytest.raises(KeyError, match="Xx"):
        b_coh("Xx")
    with pytest.raises(KeyError):
        b_coh("")
    with pytest.raises(KeyError):
        b_coh("Zz9")


def test_untabulated_species_raises_rather_than_returning_nan():
    """The source writes '---' for several heavy elements; nan must not leak."""
    untabulated = [s for s in ("Po", "At", "Rn", "Fr", "Ac", "Pu")
                   if not math.isfinite(properties(s)["b_coh_fm"])]
    assert untabulated, "expected at least one '---' row to exercise this"
    for species in untabulated:
        with pytest.raises(KeyError, match="not tabulated"):
            b_coh(species)


def test_table_covers_the_acceptance_datasets():
    """Every species in the CW-neutron acceptance set resolves.

    Al2O3 (BT-1 SRM 1976a), Cr2WO6 (BT-1), PbPdO2 (BT-1), ZrW2O8 (APDW),
    Ba2FeSbSe5 (LLB G4.1).
    """
    for species in ("Al", "O", "Cr", "W", "Pb", "Pd", "Zr", "Ba", "Fe", "Sb", "Se"):
        assert math.isfinite(b_coh(species))
