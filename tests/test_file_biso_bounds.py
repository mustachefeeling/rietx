"""A published B_iso outside the starting bounds still reads.

Every reader used to build B_iso as a parameter bounded at 0 and 25 Å², and a
value outside its bounds fails validation, so one such site refused the whole
file.  COD 4335638, CH₃NH₃PbI₃ (Stoumpos, Malliakas & Kanatzidis 2013), carries
its methylammonium C at U_iso = 0.34 Å², a B_iso of 26.8 Å².  The readers now
widen the bound to the value.
"""

from __future__ import annotations

import math

import pytest

from rietx.crystallography.cif import structure_from_cif
from rietx.schemas.structure import BISO_BOUNDS, biso_bounds

EIGHT_PI_SQ = 8.0 * math.pi ** 2

#: A rock-salt cell with one site above the bound, one below zero and one
#: inside, as a disordered cation, a light atom refined slightly negative and
#: an ordinary site would be.
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


@pytest.mark.parametrize("value, expected", [
    (2.0, BISO_BOUNDS),
    (26.8, (0.0, 26.8)),
    (-0.16, (-0.16, 25.0)),
])
def test_bounds_widen_to_hold_the_value(value, expected):
    bounds = biso_bounds(value)
    assert (bounds["min"], bounds["max"]) == pytest.approx(expected)


def test_cif_with_a_biso_outside_the_bounds_reads(tmp_path):
    path = tmp_path / "bounds.cif"
    path.write_text(CIF, encoding="utf-8")
    atoms = {a.label: a for a in structure_from_cif(path).phases[0].atoms}

    assert atoms["C1"].biso.value == pytest.approx(0.34 * EIGHT_PI_SQ)
    assert atoms["C1"].biso.max == pytest.approx(0.34 * EIGHT_PI_SQ)
    assert atoms["O1"].biso.value == pytest.approx(-0.002 * EIGHT_PI_SQ)
    assert atoms["O1"].biso.min == pytest.approx(-0.002 * EIGHT_PI_SQ)
    assert (atoms["Na1"].biso.min, atoms["Na1"].biso.max) == BISO_BOUNDS


def test_the_widening_is_reported_once_naming_every_site(tmp_path):
    """A reader says that it widened a bound, as root CLAUDE.md asks of a
    repair: one diagnostic for the file, every widened site in ``where``."""
    path = tmp_path / "bounds.cif"
    path.write_text(CIF, encoding="utf-8")
    diagnostics = []
    structure_from_cif(path, diagnostics=diagnostics)

    widened = [d for d in diagnostics if d.code == "BISO_BOUND_WIDENED"]
    assert len(widened) == 1
    labels = [a.label for a in structure_from_cif(path).phases[0].atoms]
    assert widened[0].where == [f"phases.0.atoms.{labels.index(name)}.biso"
                                for name in labels if name in ("C1", "O1")]
    assert widened[0].level == "warning"
    assert "not a physical displacement" in widened[0].message
    assert "O1" in widened[0].message.split("B < 0 on")[1]


def test_a_file_inside_the_bounds_reports_no_widening(tmp_path):
    path = tmp_path / "inside.cif"
    path.write_text(CIF.replace("0.34", "0.02").replace("-0.002", "0.01"),
                    encoding="utf-8")
    diagnostics = []
    structure_from_cif(path, diagnostics=diagnostics)
    assert "BISO_BOUND_WIDENED" not in [d.code for d in diagnostics]
