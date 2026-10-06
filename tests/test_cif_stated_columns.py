"""What a CIF row states, read as stated: a multiplicity, a zero B, a zero occupancy.

Two readers' silences, both wrong *models* rather than wrong fits.  A site
quoted to four decimals with each coordinate rounded on its own can sit 2e-4
from its special position (the 6e site of rhombohedral-axes hematite,
x + y = 1.5002), which the orbit tolerance (1e-4) reads as a general position:
twice the oxygen, absorbed by a displacement parameter, with the file's own
``_atom_site_symmetry_multiplicity 6`` beside it.  And a stated
``_atom_site_B_iso_or_equiv 0.000`` or occupancy 0 was read as "absent", giving
0.5 Å² and 1.

Everything is synthetic: an R-3c oxide of the corundum type, with coordinates
made up to reproduce the mechanism, not a database record.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.symmetry import get_spacegroup, site_orbit

CELL = """data_corundum_type
_cell_length_a 5.4300
_cell_length_b 5.4300
_cell_length_c 5.4300
_cell_angle_alpha 55.300
_cell_angle_beta 55.300
_cell_angle_gamma 55.300
_symmetry_space_group_name_H-M 'R -3 c :R'
"""

#: Fe on 4c (x, x, x); O on 6e (x, 1/2 - x, 1/4), its y rounded on its own:
#: 0.6870 + 0.8132 = 1.5002, which is 2e-4 from the position.
FE = ("Fe1", "Fe", "0.1054", "0.1054", "0.1054")
O_ROUNDED = ("O1", "O", "0.6870", "0.8132", "0.2500")
O_EXACT = ("O1", "O", "0.6870", "0.8130", "0.2500")
O_FAR = ("O1", "O", "0.3000", "0.1000", "0.2000")


def _cif(rows, extra=None):
    """A CIF whose atom loop is label, type, x, y, z plus the named columns.

    ``extra`` is ``{tag: [value per row]}``."""
    extra = extra or {}
    head = ["_atom_site_label", "_atom_site_type_symbol", "_atom_site_fract_x",
            "_atom_site_fract_y", "_atom_site_fract_z", *extra]
    body = [" ".join((*row, *(extra[tag][i] for tag in extra)))
            for i, row in enumerate(rows)]
    return CELL + "loop_\n" + "\n".join(head) + "\n" + "\n".join(body) + "\n"


def _read(tmp_path, text):
    path = tmp_path / "s.cif"
    path.write_text(text, encoding="utf-8")
    found: list = []
    return rx.Structure.from_cif(path, diagnostics=found).phases[0], found


def _multiplicity(phase, label):
    atom = next(a for a in phase.atoms if a.label == label)
    return site_orbit(get_spacegroup(phase.space_group),
                      np.array([atom.x.value, atom.y.value, atom.z.value])
                      ).multiplicity


MULT = "_atom_site_symmetry_multiplicity"


def test_a_stated_multiplicity_puts_a_rounded_site_on_its_position(tmp_path):
    phase, found = _read(tmp_path, _cif([FE, O_ROUNDED], {MULT: ["4", "6"]}))
    assert _multiplicity(phase, "O1") == 6
    assert _multiplicity(phase, "Fe1") == 4
    o = next(a for a in phase.atoms if a.label == "O1")
    assert (o.x.value + o.y.value) % 1.0 == pytest.approx(0.5, abs=1e-12)
    assert o.z.value == 0.25
    [snap] = [d for d in found if d.code == "SITE_SNAPPED_TO_SPECIAL_POSITION"]
    assert snap.level == "warning" and snap.where == ["phases.0.atoms.1"]
    assert "O1" in snap.message and "multiplicity 6" in snap.message


def test_without_a_stated_multiplicity_nothing_moves(tmp_path):
    """The negative arm: the column is what does the work.  Without it the
    2e-4 site is a general position, as it always was, and the stored
    coordinates are the file's."""
    phase, found = _read(tmp_path, _cif([FE, O_ROUNDED]))
    assert _multiplicity(phase, "O1") == 12
    o = next(a for a in phase.atoms if a.label == "O1")
    assert (o.x.value, o.y.value) == (0.687, 0.8132)
    assert not [d for d in found if "SNAPPED" in d.code]


def test_a_wyckoff_symbol_states_the_multiplicity_too(tmp_path):
    wy = "_atom_site_Wyckoff_symbol"
    phase, _ = _read(tmp_path, _cif([FE, O_ROUNDED], {wy: ["4c", "6e"]}))
    assert _multiplicity(phase, "O1") == 6


def test_a_site_already_on_its_position_and_a_general_site_are_untouched(tmp_path):
    exact, found = _read(tmp_path, _cif([FE, O_EXACT], {MULT: ["4", "6"]}))
    assert not [d for d in found if "SNAPPED" in d.code]
    general, found = _read(tmp_path, _cif([FE, O_FAR], {MULT: ["4", "12"]}))
    assert _multiplicity(general, "O1") == 12
    assert not found or not [d for d in found
                             if d.code in ("SITE_SNAPPED_TO_SPECIAL_POSITION",
                                           "CIF_SITE_MULTIPLICITY_DISAGREES")]


def test_a_stated_multiplicity_the_coordinates_cannot_reach_is_named(tmp_path):
    """The file says 6 and the site is nowhere near a 6e position: nothing is
    moved, and the disagreement is reported rather than resolved."""
    phase, found = _read(tmp_path, _cif([FE, O_FAR], {MULT: ["4", "6"]}))
    assert _multiplicity(phase, "O1") == 12
    [d] = [d for d in found if d.code == "CIF_SITE_MULTIPLICITY_DISAGREES"]
    assert d.where == ["phases.0.atoms.1"]
    assert "file 6, computed 12" in d.message


# ------------------------------------------------------ a stated zero is a value


def test_a_stated_zero_b_and_a_stated_zero_occupancy_are_read_as_stated(tmp_path):
    cols = {"_atom_site_B_iso_or_equiv": ["0.000(75)", "0.400"],
            "_atom_site_occupancy": ["1.0", "0.0"]}
    phase, _ = _read(tmp_path, _cif([FE, O_EXACT], cols))
    fe, o = phase.atoms
    assert fe.biso.value == 0.0
    assert o.occ.value == 0.0


def test_an_absent_b_and_an_absent_occupancy_keep_their_defaults(tmp_path):
    """The other side of the same test: no column, no statement."""
    phase, _ = _read(tmp_path, _cif([FE, O_EXACT]))
    assert all(a.biso.value == pytest.approx(0.5) for a in phase.atoms)
    assert all(a.occ.value == 1.0 for a in phase.atoms)


def test_a_null_b_is_not_a_statement(tmp_path):
    cols = {"_atom_site_B_iso_or_equiv": ["?", "0.400"]}
    phase, _ = _read(tmp_path, _cif([FE, O_EXACT], cols))
    assert phase.atoms[0].biso.value == pytest.approx(0.5)
    assert phase.atoms[1].biso.value == pytest.approx(0.4)
