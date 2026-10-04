"""A B_iso of any value reads as stated, and nothing bounds it by default.

Readers once built B_iso bounded at 0 and 25 Å², so one published site
outside that range refused the whole file: COD 4335638, CH₃NH₃PbI₃ (Stoumpos,
Malliakas & Kanatzidis 2013), carries its methylammonium C at U_iso = 0.34 Å²,
a B_iso of 26.8 Å².  PR #663 widened the bound to the file's value.  WP-1534
removed the default bound (decided 2026-10-04): FullProf, TOPAS and GSAS-II
bound no displacement parameter by default, the scale-B hold now stops the
walk the bound stood in for, and ``BISO_NEGATIVE`` and
``BISO_UNUSUALLY_LARGE`` warn on the value.
"""

from __future__ import annotations

import math

import pytest

import rietx as rx
from rietx.crystallography.cif import structure_from_cif

EIGHT_PI_SQ = 8.0 * math.pi ** 2

#: A rock-salt cell with one site above the old ceiling, one below zero and
#: one inside, as a disordered cation, a light atom refined slightly negative
#: and an ordinary site would be.
CIF = """\
data_bounds
_cell_length_a 6.0
_cell_length_b 6.0
_cell_length_c 6.0
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'F m -3 m'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_U_iso_or_equiv
_atom_site_occupancy
C1 C 0.25 0.25 0.25 0.34 1
O1 O 0.5 0.5 0.5 -0.002 1
Na1 Na 0 0 0 0.012 1
"""


def test_cif_keeps_every_biso_as_stated_and_unbounded(tmp_path):
    path = tmp_path / "bounds.cif"
    path.write_text(CIF, encoding="utf-8")
    diagnostics = []
    atoms = {a.label: a for a in
             structure_from_cif(path, diagnostics=diagnostics).phases[0].atoms}

    for label, u in (("C1", 0.34), ("O1", -0.002), ("Na1", 0.012)):
        assert atoms[label].biso.value == pytest.approx(u * EIGHT_PI_SQ)
        assert (atoms[label].biso.min, atoms[label].biso.max) == (-math.inf, math.inf)
        assert atoms[label].biso.unit == "A^2"
    # nothing was repaired, so a reader has nothing to say about B
    assert not [d for d in diagnostics if "BISO" in d.code]


def test_the_default_biso_is_unbounded():
    atom = rx.Atom(label="Fe1", species="Fe", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))
    assert (atom.biso.value, atom.biso.min, atom.biso.max, atom.biso.unit) == (
        0.5, -math.inf, math.inf, "A^2")
    # issue #204's value, which PR #206's inherited bound refused
    walked = rx.Atom(label="Fe1", species="Fe", x=rx.Parameter(value=0.0),
                     y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                     biso=rx.Parameter(value=-165.0, vary=True))
    assert walked.biso.value == -165.0


def test_a_bound_the_caller_states_still_binds():
    with pytest.raises(ValueError):
        rx.Atom(label="Fe1", species="Fe", x=rx.Parameter(value=0.0),
                y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                biso=rx.Parameter(value=30.0, min=0.0, max=25.0))
