"""WP-1468 — a CIF's disorder groups reach the structure and leave it again.

``_atom_site_disorder_assembly`` and ``_atom_site_disorder_group`` say which
sites are occupied together (the CIF core dictionary).  The fit has no use for
them, and the structure viewer does, so the schema carries them as the file
states them and the writer puts them back.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from rietx.crystallography.cif import structure_from_cif, structure_to_cif
from rietx.schemas.structure import Structure

DATA = Path(__file__).parent / "data"

#: A perchlorate disordered over two orientations, as SHELXL writes PART 1 and
#: PART 2 at 0.6 and 0.4, beside an ordered K.  The file's own numbers are
#: built here: Cl–O 1.43 Å, the second orientation the first turned 77° about
#: c.  That puts each O 1.45 Å from its twin, inside the O–O bond cutoff and
#: 61° apart round Cl, so only the groups can say the two never coexist.
_CORNERS = np.array([(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]) / math.sqrt(3.0)


def _turn(degrees: float) -> np.ndarray:
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def perchlorate_cif() -> str:
    rows = ["K1 K 0.1 0.1 0.1 1 . .", "Cl1 Cl 0.5 0.5 0.5 1 . ."]
    for group, occ, turn in (("1", 0.6, np.eye(3)), ("2", 0.4, _turn(77.0))):
        for k, corner in enumerate(_CORNERS):
            x, y, z = 0.5 + 1.43 * (turn @ corner) / 10.0
            label = f"O{k + 1}{'AB'[int(group) - 1]}"
            rows.append(f"{label} O {x:.5f} {y:.5f} {z:.5f} {occ} A {group}")
    return "\n".join([
        "data_perchlorate",
        "_cell_length_a 10", "_cell_length_b 10", "_cell_length_c 10",
        "_cell_angle_alpha 90", "_cell_angle_beta 90", "_cell_angle_gamma 90",
        "_symmetry_space_group_name_H-M 'P 1'",
        "loop_", "_atom_site_label", "_atom_site_type_symbol",
        "_atom_site_fract_x", "_atom_site_fract_y", "_atom_site_fract_z",
        "_atom_site_occupancy", "_atom_site_disorder_assembly",
        "_atom_site_disorder_group", *rows, ""])


@pytest.fixture
def perchlorate(tmp_path) -> Structure:
    path = tmp_path / "perchlorate.cif"
    path.write_text(perchlorate_cif(), encoding="utf-8")
    return structure_from_cif(str(path))


def test_the_reader_keeps_each_sites_assembly_and_group(perchlorate):
    """A null is an ordered site; a stated code arrives as the string it was."""
    atoms = {a.label: a for a in perchlorate.phases[0].atoms}
    assert (atoms["K1"].disorder_assembly, atoms["K1"].disorder_group) == (None, None)
    assert (atoms["O1A"].disorder_assembly, atoms["O1A"].disorder_group) == ("A", "1")
    assert (atoms["O4B"].disorder_assembly, atoms["O4B"].disorder_group) == ("A", "2")


def test_the_writer_puts_them_back(perchlorate, tmp_path):
    path = tmp_path / "again.cif"
    structure_to_cif(perchlorate, str(path))
    again = structure_from_cif(str(path))
    assert ([(a.label, a.disorder_assembly, a.disorder_group) for a in again.phases[0].atoms]
            == [(a.label, a.disorder_assembly, a.disorder_group)
                for a in perchlorate.phases[0].atoms])


def test_an_ordered_structure_is_written_without_the_columns(tmp_path):
    """The columns are written only when a site declares one, so an ordered
    structure's file is what the writer wrote before WP-1468."""
    path = tmp_path / "lab6.cif"
    structure_to_cif(structure_from_cif(str(DATA / "cod_1000055.cif")), str(path))
    assert "disorder" not in path.read_text(encoding="utf-8")


def test_the_json_round_trip_keeps_them(perchlorate):
    again = Structure.model_validate_json(perchlorate.model_dump_json())
    assert again == perchlorate


def test_a_tag_spelt_in_another_case_is_still_read(tmp_path):
    """CIF tags are case-insensitive, and a gate matching one spelling had let
    ``_atom_site_Disorder_Group`` drop every group without a word."""
    path = tmp_path / "mixed.cif"
    path.write_text(perchlorate_cif()
                    .replace("_atom_site_disorder_assembly", "_Atom_Site_Disorder_Assembly")
                    .replace("_atom_site_disorder_group", "_atom_site_Disorder_Group"),
                    encoding="utf-8")
    atoms = {a.label: a for a in structure_from_cif(str(path)).phases[0].atoms}
    assert (atoms["O1A"].disorder_assembly, atoms["O1A"].disorder_group) == ("A", "1")


def test_a_cif_reads_from_a_pathlib_path_as_from_a_str():
    """gemmi's readers take a ``str`` only; ``Structure.from_cif`` took a
    ``pathlib.Path`` into a bare ``TypeError`` wrapped as "could not be read"."""
    import rietx as rx
    path = Path(__file__).parent / "data" / "cod_1000055.cif"
    from_path = rx.Structure.from_cif(path)
    from_str = rx.Structure.from_cif(str(path))
    assert from_path.model_dump() == from_str.model_dump()
