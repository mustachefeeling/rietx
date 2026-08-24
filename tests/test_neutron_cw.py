"""Constant-wavelength neutron refinement: the source, the amplitude, the fit.

The tests that matter are the ones that would pass for an X-ray source too if
the radiation were being ignored. So each one below turns on something that is
*different* about neutrons — a Q-independent amplitude, a negative one, K = 1,
an absent dispersion channel — rather than merely checking that a fit runs.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.lattice import d_spacings
from rietx.crystallography.scattering import f0
from rietx.crystallography.structure_factor import (
    compile_phase_sites,
    structure_factors_squared,
)
from rietx.crystallography.symmetry import generate_reflections
from rietx.model.corrections import lorentz_polarization
from rietx.schemas.instrument import NeutronSource

CORUNDUM_CELL = (4.758877, 4.758877, 12.992880, 90.0, 90.0, 120.0)


def corundum() -> rx.Phase:
    """Al2O3, the NIST SRM 1976a standard: two sites, both special positions."""
    P = rx.Parameter
    a, _, c, *_ = CORUNDUM_CELL
    return rx.Phase(
        name="Al2O3", space_group="R-3c:H",
        cell=rx.Cell(a=P(value=a), b=P(value=a), c=P(value=c),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=120.0)),
        atoms=[
            rx.Atom(label="Al", species="Al", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=0.35216), biso=P(value=0.3)),
            rx.Atom(label="O", species="O", x=P(value=0.30642), y=P(value=0.0),
                    z=P(value=0.25), biso=P(value=0.3)),
        ])


# --------------------------------------------------------------- the source ---
def test_neutron_source_pins_the_polarisation_term():
    """K = 1 is the whole reason no new correction code is needed.

    Lp = [K + (1 - K)cos^2 2th]/(sin^2 th cos th) collapses to the bare Lorentz
    factor at K = 1, and that factor is geometry, not radiation.
    """
    source = NeutronSource(wavelength=2.0780)
    assert source.polarization.value == 1.0
    assert not source.polarization.vary

    tt = np.array([10.0, 45.0, 90.0, 140.0])
    bare = 1.0 / (np.sin(np.radians(tt / 2)) ** 2 * np.cos(np.radians(tt / 2)))
    assert lorentz_polarization(tt, 1.0) == pytest.approx(bare, rel=1e-15)
    # and the term is not vacuous: an unpolarised X-ray beam differs materially
    assert not np.allclose(lorentz_polarization(tt, 0.5), bare, rtol=1e-3)


def test_neutron_source_has_no_dispersion_channel():
    source = NeutronSource(wavelength=2.0780)
    assert source.dispersion is None
    assert source.primary_wavelength == pytest.approx(2.0780)
    assert len(source.lines) == 1          # one line, weight structurally 1
    assert not source.lines[0].weight.vary


def test_instrument_union_discriminates_on_kind():
    neutron = rx.Instrument.constant_wavelength_neutron(2.0780)
    xray = rx.Instrument.debye_scherrer(0.4139)
    assert neutron.source.kind == "neutron_cw"
    assert xray.source.kind == "xray_cw"
    # both round-trip through JSON under the discriminated union
    for inst in (neutron, xray):
        again = rx.Instrument.model_validate_json(inst.model_dump_json())
        assert again.source.kind == inst.source.kind


def test_profile_seed_helper_sets_both_width_terms():
    inst = rx.Instrument.constant_wavelength_neutron(2.0780, fwhm_deg=0.4)
    assert inst.profile.w.value == pytest.approx((0.4 / 2) ** 2)
    assert inst.profile.x.value == pytest.approx(0.4)


# ------------------------------------------------------------ the amplitude ---
def test_scattering_length_is_frozen_on_the_phase():
    sites = compile_phase_sites(corundum(), neutron=True)
    assert sites.b_coh is not None
    assert sites.b_coh == pytest.approx([3.449, 5.803], abs=5e-4)
    assert compile_phase_sites(corundum()).b_coh is None       # X-ray default


def test_neutron_amplitude_is_q_independent_and_xray_is_not():
    """The discriminating property, tested directly on the amplitudes.

    An X-ray form factor falls off with Q because the electron cloud has
    spatial extent; a nucleus is a point scatterer, so b does not.
    """
    k = np.linspace(0.05, 0.45, 12)                # sin(theta)/lambda
    f_xray = f0("Al", k)
    assert f_xray[0] > 1.5 * f_xray[-1]            # real falloff across the range
    # b is one number; the module returns it without a k argument at all
    from rietx.crystallography.neutron import b_coh
    assert b_coh("Al") == pytest.approx(3.449, abs=5e-4)


def test_negative_scattering_length_still_gives_positive_intensity():
    """Vanadium: b < 0, and |F|^2 must not go with it."""
    P = rx.Parameter
    cell = (3.024, 3.024, 3.024, 90.0, 90.0, 90.0)
    v = rx.Phase(
        name="V", space_group="Im-3m",
        cell=rx.Cell(a=P(value=cell[0]), b=P(value=cell[1]), c=P(value=cell[2]),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        atoms=[rx.Atom(label="V", species="V", x=P(value=0.0), y=P(value=0.0),
                       z=P(value=0.0), biso=P(value=0.5))])
    sites = compile_phase_sites(v, neutron=True)
    assert sites.b_coh[0] < 0.0
    refl = generate_reflections("Im-3m", cell, 2.0780, 120.0, 5.0)
    hkl = np.asarray(refl.hkl)
    f2 = structure_factors_squared(
        hkl, d_spacings(hkl, *cell), sites,
        np.zeros((1, 3)), np.array([1.0]), np.array([0.5]))
    assert (f2 >= 0.0).all()
    assert f2.max() > 0.0


def test_neutron_and_anomalous_dispersion_are_mutually_exclusive():
    """Different radiations, different units (fm against electrons)."""
    with pytest.raises(ValueError, match="anomalous dispersion"):
        compile_phase_sites(corundum(), f_anom={"Al": 0j, "O": 0j}, neutron=True)


def test_unknown_species_refuses_at_compile_rather_than_returning_zero():
    P = rx.Parameter
    bogus = rx.Phase(
        name="X", space_group="P1",
        cell=rx.Cell(a=P(value=5.0), b=P(value=5.0), c=P(value=5.0),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        atoms=[rx.Atom(label="Q", species="Xx", x=P(value=0.0), y=P(value=0.0),
                       z=P(value=0.0))])
    with pytest.raises(KeyError, match="Xx"):
        compile_phase_sites(bogus, neutron=True)


# ------------------------------------------------------------------ the fit ---
def test_xray_only_diagnostic_stays_quiet_for_neutrons():
    """DISPERSION_NEGLECTED would advise restoring a correction that does not
    exist for this radiation."""
    from rietx.refine import _dispersion_diagnostics  # noqa: PLC0415

    structure = rx.Structure(phases=[corundum()])
    neutron = rx.Instrument.constant_wavelength_neutron(2.0780)
    xray = rx.Instrument.debye_scherrer(1.5406)
    xray = xray.model_copy(update={
        "source": xray.source.model_copy(update={"dispersion": None})})

    assert _dispersion_diagnostics(structure, neutron) == []
    # and the diagnostic is not simply dead: declining it on an X-ray source
    # still says so, which is what makes the neutron silence a decision
    codes = {d.code for d in _dispersion_diagnostics(structure, xray)}
    assert "DISPERSION_NEGLECTED" in codes


def _seeded_width(inst: rx.Instrument, fwhm_deg: float) -> rx.Instrument:
    """Same profile on both instruments, so only the amplitude differs."""
    profile = inst.profile.model_copy(update={
        "w": inst.profile.w.model_copy(update={"value": (fwhm_deg / 2) ** 2}),
        "x": inst.profile.x.model_copy(update={"value": fwhm_deg}),
    })
    return inst.model_copy(update={"profile": profile})


def _y_calc(structure: rx.Structure, instrument: rx.Instrument,
            two_theta: np.ndarray) -> np.ndarray:
    """y_calc at the stored values, through the same seam a fit uses."""
    from rietx.model.forward import compile_model  # noqa: PLC0415
    from rietx.params.vector import ParameterTable  # noqa: PLC0415

    pattern = rx.PatternData(two_theta=two_theta.tolist(),
                             intensity=np.ones_like(two_theta).tolist())
    model = compile_model(structure, instrument, pattern)
    table = ParameterTable(structure, instrument)
    return model.evaluate(table.decode(table.x0()))


def test_neutron_intensities_are_not_the_xray_ones():
    """The test that would fail if the radiation were being ignored.

    For corundum the two amplitudes rank the atoms in *opposite* order —
    f_Al(0) = 13 > f_O(0) = 8 electrons, while b_Al = 3.449 fm < b_O = 5.803 fm
    — so oxygen dominates a neutron pattern and aluminium an X-ray one. The
    relative intensities must therefore reorder, not merely rescale.
    """
    tt = np.arange(15.0, 100.0, 0.02)
    structure = rx.Structure(phases=[corundum()])
    n = _y_calc(structure, rx.Instrument.constant_wavelength_neutron(
        1.5406, fwhm_deg=0.3), tt)
    x = _y_calc(structure, _seeded_width(
        rx.Instrument.debye_scherrer(1.5406), 0.3), tt)

    assert np.isfinite(n).all() and (n >= 0.0).all()
    assert n.max() > 0.0
    # same wavelength and same profile, so the peaks sit at the same 2theta;
    # what changes is which of them is tallest
    assert np.argmax(n) != np.argmax(x), (
        "neutron and X-ray patterns peak on the same reflection — the "
        "scattering amplitude is not reaching the structure factor")


def test_hexagonal_cell_ties_survive_a_neutron_source():
    """The cell constraints come from the space group, not the radiation."""
    ref = rx.Refinement(rx.Structure(phases=[corundum()]),
                        rx.Instrument.constant_wavelength_neutron(2.0780))
    paths = {row.path for row in ref.parameters()}
    assert "phases.0.cell.a" in paths
    # b follows a in a hexagonal setting, so it is tied rather than free
    b_row = next(r for r in ref.parameters() if r.path == "phases.0.cell.b")
    assert not b_row.refinable
    gamma = next(r for r in ref.parameters() if r.path == "phases.0.cell.gamma")
    assert math.isclose(gamma.value, 120.0)
