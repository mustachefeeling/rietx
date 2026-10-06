"""``write_topas_inp(free=, scale=)``: what the written file refines, how its
numbers are tied, and the scale in TOPAS's convention (#722, #721 item 3).

A plan *replaces* the vary flags per stage, so after a plan-driven fit the
models carry ``vary=False`` everywhere while the fit's free set lives in
``Refinement.parameters()``. The tests below build that state directly and
check that the file states the free set, the ties and the scale, and that the
default (no new keyword) writes exactly what it wrote before.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.io.projects.topas import from_structure
from rietx.io.projects.topas_refined import (
    NEUTRON_SCALE_FACTOR,
    Affine,
    RefinedSet,
    number,
    topas_scale_factor,
)
from tests.topas_export_cases import case_nacl_neutron, nacl

DATA = Path(__file__).parent / "data"


def _pnma():
    """A synthetic Pnma phase: one general and one mirror site, as a plan leaves
    it (every stored flag False)."""
    from rietx.schemas.common import Parameter as P
    from rietx.schemas.structure import Atom, Cell, Phase

    def at(label, sp, xyz):
        return Atom(label=label, species=sp, x=P(value=xyz[0]), y=P(value=xyz[1]),
                    z=P(value=xyz[2]), biso=P(value=0.7, min=0.0, max=25.0))
    return Phase(name="synthetic Pnma", space_group="P n m a",
                 cell=Cell(a=P(value=10.0), b=P(value=6.0), c=P(value=5.0),
                           alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
                 atoms=[at("A1", "Ba", (0.17, 0.02, 0.38)),
                        at("B1", "Fe", (0.10, 0.25, 0.66)),
                        at("B2", "Fe", (0.30, 0.25, 0.16))],
                 scale=P(value=0.01, min=0.0, transform="softplus"))


def _ref():
    ref = rx.Refinement(rx.Structure(phases=[_pnma()]),
                        rx.Instrument.constant_wavelength_neutron(2.4), history=False)
    ref.set_vary(["phases.0.scale", "phases.0.cell.*", "phases.0.atoms.*.dof.*",
                  "phases.0.atoms.*.biso"], True)
    return ref


def _site(text, label):
    return next(ln for ln in text.splitlines() if ln.strip().startswith(f"site {label} "))


def test_a_plan_driven_fit_writes_no_refine_flag_by_default():
    """The gap #722 reports, pinned: the models carry the input's flags."""
    ref = _ref()
    text = from_structure(ref.fitted_structure)
    assert "@" not in text
    assert sum(1 for p in ref.parameters() if p.vary) > 10


def test_free_writes_every_parameter_the_fit_freed():
    ref = _ref()
    text = from_structure(ref.fitted_structure, free=ref)
    free = {r.path for r in ref.parameters() if r.vary}
    assert "phases.0.atoms.0.dof.0" in free
    a1 = _site(text, "A1")
    # a coordinate refined through its site-symmetry DOF is named after itself
    assert re.search(r"\bx A1_x 0\.17\b", a1) and re.search(r"\by A1_y 0\.02\b", a1)
    b1 = _site(text, "B1")
    assert "y ! 0.25" in b1                      # the mirror holds y
    assert "beq B1_biso 0.7 min 0 max 25" in b1  # rietx's bounds travel
    assert re.search(r"scale p0_scale 0\.01\b", text)
    assert re.search(r"\ba p0_cell_a 10\.0\b", text)


def test_a_free_set_of_paths_is_enough_without_ties():
    ref = _ref()
    paths = [r.path for r in ref.parameters() if r.vary]
    text = from_structure(ref.fitted_structure, free=paths)
    assert re.search(r"beq A1_biso 0\.7", text)
    assert "scale p0_scale" in text


def test_tie_equal_is_one_name_written_twice():
    """§ 2.3: 'parameters with names that are the same must have the same value'."""
    ref = _ref()
    ref.tie_equal(["phases.0.atoms.1.biso", "phases.0.atoms.2.biso"])
    text = from_structure(ref.fitted_structure, free=ref)
    assert "beq B1_biso 0.7" in _site(text, "B1")
    assert "beq B1_biso 0.7" in _site(text, "B2")


def test_an_affine_tie_is_an_equation_over_its_source():
    ref = _ref()
    ref.tie("phases.0.atoms.2.biso", "phases.0.atoms.1.biso", scale=2.0, offset=-0.7)
    text = from_structure(ref.fitted_structure, free=ref)
    assert "beq = 2.0*B1_biso - 0.7;" in _site(text, "B2")
    assert "beq B1_biso 0.7" in _site(text, "B1")   # the source, carried where it is


def test_the_default_writes_byte_for_byte_what_it_wrote_before():
    ref = _ref()
    plain = from_structure(ref.fitted_structure)
    assert plain == from_structure(ref.fitted_structure, free=None, scale=None)
    assert "p0_scale" not in plain and "' scale:" not in plain


def test_scale_topas_needs_the_radiation():
    ref = _ref()
    with pytest.raises(ValueError, match="instrument"):
        from_structure(ref.fitted_structure, scale="topas")
    with pytest.raises(ValueError, match="'rietx' or 'topas'"):
        from_structure(ref.fitted_structure, scale="fullprof", free=ref)


def test_the_scale_is_written_in_topas_units_and_says_so():
    ref = _ref()
    text = from_structure(ref.fitted_structure, free=ref, scale="topas",
                          instrument=rx.Instrument.constant_wavelength_neutron(2.4))
    assert re.search(r"scale p0_scale 1\.0\b", text)       # 0.01 × 100
    assert "rietx Phase.scale x 100.0" in text
    rietx_units = from_structure(ref.fitted_structure, free=ref, scale="rietx")
    assert "NOT TOPAS's convention" in rietx_units


def test_the_scale_constants():
    assert topas_scale_factor(rx.Instrument.constant_wavelength_neutron(2.0)) == 100.0
    xray = rx.Instrument.bragg_brentano(radiation="CuKa")
    assert topas_scale_factor(xray) == pytest.approx(xray.source.polarization.value)


def test_the_neutron_constant_reproduces_topas_own_intensity():
    """TOPAS-64 v6's Y_calc at zero cycles for our NaCl case
    (``topas_export_cases.case_nacl_neutron``, scale written × 100):
    rietx's ``predict()`` at the rietx scale equals it to 0.06 % in the median
    (TOPAS integrates whole Lorentzian tails where rietx's windows hold 98 % of
    the area). A wrong constant is off by a factor of 100."""
    ref, _ = case_nacl_neutron()
    x, y_topas = np.loadtxt(DATA / "topas_export_nacl_neutron_ycalc.txt", unpack=True)
    y_rietx = np.asarray(ref.predict(x))
    ratio = np.median(y_topas / y_rietx)
    assert abs(ratio - 1.0) < 0.01
    assert NEUTRON_SCALE_FACTOR == 100.0


def test_a_signed_zero_is_written_as_zero():
    assert number(-0.0) == "0" and number(0.0) == "0"
    assert number(0.25) == "0.25"
    with pytest.raises(ValueError, match="does not parse"):
        number(float("nan"))


def test_the_name_of_a_path():
    refined = RefinedSet(None, rx.Structure(phases=[nacl()]))
    assert refined.name("phases.0.atoms.1.biso") == "Cl_biso"
    assert refined.name("phases.0.scale") == "p0_scale"
    assert refined.name("instrument.profile.u") == "prof_u"
    assert refined.name("instrument.geometry.axial_hl") == "geom_axial_hl"


def test_affine_arithmetic():
    a = Affine({"p": 1.0}, 0.5) * 2.0 + Affine({"p": -2.0, "q": 1.0}, 1.0)
    assert a.terms == {"q": 1.0} and a.const == 2.0
