"""The aberrations a geometry has and could not express."""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx

CODE = "CAPILLARY_OFFSET_UNAVAILABLE"


def _corundum() -> rx.Structure:
    P = rx.Parameter
    return rx.Structure(phases=[rx.Phase(
        name="Al2O3", space_group="R-3c:H",
        cell=rx.Cell(a=P(value=4.7589), b=P(value=4.7589), c=P(value=12.9929),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=120.0)),
        atoms=[
            rx.Atom(label="Al", species="Al", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=0.35216), biso=P(value=0.3)),
            rx.Atom(label="O", species="O", x=P(value=0.30642), y=P(value=0.0),
                    z=P(value=0.25), biso=P(value=0.3)),
        ])])


def _flat_pattern() -> rx.PatternData:
    tt = np.arange(20.0, 90.0, 0.05)
    return rx.PatternData(two_theta=tt.tolist(),
                          intensity=np.full(tt.size, 100.0).tolist())


def _codes(instrument: rx.Instrument) -> set[str]:
    result = rx.refine(_flat_pattern(), _corundum(), instrument,
                       plan="profile_only")
    return {d.code for d in result.diagnostics}


def test_a_capillary_without_a_radius_says_the_offsets_were_unavailable():
    """The offsets are correctly held — the diagnostic is that "held" and
    "measured to be zero" are different statements (WP-1073)."""
    assert CODE in _codes(
        rx.Instrument.constant_wavelength_neutron(2.0780, fwhm_deg=0.4))


def test_declaring_the_radius_silences_it():
    """The condition is the missing field, not the geometry."""
    assert CODE not in _codes(rx.Instrument.constant_wavelength_neutron(
        2.0780, fwhm_deg=0.4, goniometer_radius_mm=1711.0))


def test_a_flat_plate_is_not_told_about_a_capillary_aberration():
    """Keyed on the geometry that *has* the eq (4) offsets, not on any
    instrument missing any field."""
    assert CODE not in _codes(rx.Instrument.bragg_brentano(radiation="CuKa"))


def test_it_reads_the_gate_off_the_table_rather_than_the_geometry():
    """The claim in the code: a locked offset entry on a capillary *is* the
    radius being absent, so the diagnostic and the parameter table cannot
    disagree about whether the aberration was available.

    Asserted rather than described, because a second opinion here is exactly
    the drift the docstring says it avoids.
    """
    from rietx.params.vector import ParameterTable

    structure = _corundum()
    for radius, expect_locked in ((None, True), (1711.0, False)):
        instrument = rx.Instrument.constant_wavelength_neutron(
            2.0780, fwhm_deg=0.4, goniometer_radius_mm=radius)
        table = ParameterTable(structure, instrument)
        locked = {e.path for e in table.entries if e.locked}
        got = "instrument.geometry.capillary_offset_along_beam" in locked
        assert got is expect_locked
        assert (CODE in _codes(instrument)) is expect_locked


@pytest.mark.parametrize("field", ["goniometer_radius_mm"])
def test_the_diagnostic_names_the_field_that_opens_the_door(field):
    """A diagnostic that cannot be acted on is noise."""
    result = rx.refine(_flat_pattern(), _corundum(),
                       rx.Instrument.constant_wavelength_neutron(2.0780, fwhm_deg=0.4),
                       plan="profile_only")
    hit = next(d for d in result.diagnostics if d.code == CODE)
    assert hit.where == [f"instrument.geometry.{field}"]
    assert field in (hit.suggestion or "")
    assert hit.level == "info"
