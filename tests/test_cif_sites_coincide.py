"""``structure_from_cif`` never counts one atom twice.

Two ways a file states one atom as two, both found by the 2026-10-06 MAGNDATA
import sweep in files that read with no diagnostic, and both doubling a site's
contribution to every structure factor:

* a special position printed off by its rounding — the 6h site (x, 2x, ¼) of
  P6₃/mmc as (0.828, 0.657, ¼), 1e-3 off, beyond the 1e-4 snap — so every
  image of the site has a twin a few thousandths of an ångström away;
* one orbit listed as two sites, the second an image of the first.

Each test uses a hand-written file and checks what is independent of the
code under test: the orbit size the tables give (6 for 6h), and the
prediction of the same structure stated once.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography import magcif
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.symmetry import resolve_group, site_orbit

_HEX = """data_hex
_cell_length_a 5.0
_cell_length_b 5.0
_cell_length_c 8.0
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 120
_symmetry_space_group_name_H-M 'P 63/m m c'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Co1 Co {x} {y} 0.25 1
"""


def _orbit(structure, j=0) -> int:
    phase = structure.phases[0]
    a = phase.atoms[j]
    group = resolve_group(phase.space_group, phase.symmetry_operations)
    return site_orbit(group, np.array([a.x.value, a.y.value, a.z.value])).multiplicity


def test_a_special_position_printed_off_by_its_rounding_is_read_on_it(tmp_path):
    path = tmp_path / "hex.cif"
    path.write_text(_HEX.format(x="0.828", y="0.657"), encoding="utf-8")
    diagnostics: list = []
    structure = structure_from_cif(path, diagnostics=diagnostics)
    assert _orbit(structure) == 6                  # 6h, International Tables
    a = structure.phases[0].atoms[0]
    resid = 2 * a.x.value - a.y.value
    assert abs(resid - round(resid)) < 1e-12     # periodic: -1e-16 is 0, not 1 - 1e-16
    (hit,) = [d for d in diagnostics if d.code == "CIF_SITE_TWINS_MERGED"]
    assert hit.value < 0.02


def test_a_general_position_is_left_where_it_is(tmp_path):
    """The negative arm: 0.1 Å off the special position is a real offset."""
    path = tmp_path / "hex.cif"
    path.write_text(_HEX.format(x="0.828", y="0.676"), encoding="utf-8")
    diagnostics: list = []
    structure = structure_from_cif(path, diagnostics=diagnostics)
    assert _orbit(structure) == 12
    assert not [d for d in diagnostics if d.code == "CIF_SITE_TWINS_MERGED"]


_ROCKSALT = """data_rocksalt
_cell_length_a 4.2
_cell_length_b 4.2
_cell_length_c 4.2
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
_atom_site_occupancy
Ni1 Ni 0 0 0 1
O1 O 0.5 0.5 0.5 1
{extra}"""


def _predict(structure):
    ref = rx.Refinement(structure, rx.Instrument.constant_wavelength_neutron(1.5),
                        history=False)
    return np.asarray(ref.predict(np.arange(10.0, 120.0, 0.05)))


def test_an_orbit_listed_twice_is_counted_once(tmp_path):
    once = tmp_path / "once.cif"
    once.write_text(_ROCKSALT.format(extra=""), encoding="utf-8")
    twice = tmp_path / "twice.cif"
    twice.write_text(_ROCKSALT.format(extra="Ni2 Ni 0.5 0.5 0.0001 1\n"),
                     encoding="utf-8")
    diagnostics: list = []
    read = structure_from_cif(twice, diagnostics=diagnostics)
    assert [a.label for a in read.phases[0].atoms] == ["Ni1", "O1"]
    assert [d.code for d in diagnostics].count("CIF_SITE_LISTED_TWICE") == 1
    a, b = _predict(structure_from_cif(once)), _predict(read)
    assert np.max(np.abs(a - b)) / np.max(a) < 1e-12


def test_an_orbit_listed_twice_with_two_occupancies_is_refused(tmp_path):
    path = tmp_path / "twice.cif"
    path.write_text(_ROCKSALT.format(extra="Ni2 Ni 0.5 0.5 0.0001 0.8\n"),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="overfill one position"):
        structure_from_cif(path)


_MNF2 = """data_mnf2
_cell_length_a 4.8734
_cell_length_b 4.8734
_cell_length_c 3.3099
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_parent_space_group.name_H-M_alt 'P 42/m n m'
_parent_space_group.child_transform_Pp_abc 'a,b,c;0,0,0'
loop_
_space_group_symop_magn_operation.id
_space_group_symop_magn_operation.xyz
1 x,y,z,+1
2 -x,-y,z,+1
3 -y+1/2,x+1/2,z+1/2,-1
4 y+1/2,-x+1/2,z+1/2,-1
5 -x+1/2,y+1/2,-z+1/2,+1
6 x+1/2,-y+1/2,-z+1/2,+1
7 y,x,-z,-1
8 -y,-x,-z,-1
9 -x,-y,-z,+1
10 x,y,-z,+1
11 y+1/2,-x+1/2,-z+1/2,-1
12 -y+1/2,x+1/2,-z+1/2,-1
13 x+1/2,-y+1/2,z+1/2,+1
14 -x+1/2,y+1/2,z+1/2,+1
15 -y,-x,z,-1
16 y,x,z,-1
loop_
_space_group_symop_magn_centering.id
_space_group_symop_magn_centering.xyz
1 x,y,z,+1
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Mn1 Mn 0 0 0 1
Mn2 Mn 0.5 0.5 0.5001 1
F1 F 0.305 0.305 0 1
loop_
_atom_site_moment.label
_atom_site_moment.crystalaxis_x
_atom_site_moment.crystalaxis_y
_atom_site_moment.crystalaxis_z
Mn1 0 0 4.6
Mn2 0 0 {m2}
"""


def test_a_magnetic_site_listed_twice_with_its_image_moment_is_counted_once(tmp_path):
    """Mn2 is the body-centre image of Mn1 under the primed 4₂, and its stated
    moment, −4.6 along c, is that image's: one orbit, listed twice."""
    path = tmp_path / "mnf2.mcif"
    path.write_text(_MNF2.format(m2="-4.6"), encoding="utf-8")
    diagnostics: list = []
    read = structure_from_cif(path, diagnostics=diagnostics)
    assert [a.label for a in read.phases[0].atoms] == ["Mn1", "F1"]
    assert "CIF_SITE_LISTED_TWICE" in [d.code for d in diagnostics]


def test_a_magnetic_site_listed_twice_with_another_moment_is_refused(tmp_path):
    """+4.6 on the body centre contradicts the primed operation that puts −4.6
    there: one position, two moments."""
    path = tmp_path / "mnf2.mcif"
    path.write_text(_MNF2.format(m2="4.6"), encoding="utf-8")
    with pytest.raises(magcif.MagCifError, match="two moments"):
        structure_from_cif(path)


_ROCKSALT_LABELLED = _ROCKSALT.replace("O1 O 0.5", "O1 O1 0.5")


def test_paths_name_the_site_they_are_about_after_a_site_is_dropped(tmp_path):
    """Ni2 goes, so O1 is atom 1 of the phase and not atom 2 of the file."""
    path = tmp_path / "twice.cif"
    path.write_text(_ROCKSALT_LABELLED.format(extra="").replace(
        "O1 O1", "Ni2 Ni 0.5 0.5 0.0001 1\nO1 O1"), encoding="utf-8")
    diagnostics: list = []
    atoms = structure_from_cif(path, diagnostics=diagnostics).phases[0].atoms
    assert [a.label for a in atoms] == ["Ni1", "O1"]
    (twice,) = [d for d in diagnostics if d.code == "CIF_SITE_LISTED_TWICE"]
    assert twice.where == ["phases.0.atoms.0"]
    (species,) = [d for d in diagnostics if d.code == "CIF_SPECIES_NORMALISED"]
    assert species.where == ["phases.0.atoms.1.species"]


def test_paths_name_the_site_after_the_magnetic_pass_drops_one(tmp_path):
    path = tmp_path / "mnf2.mcif"
    text = _MNF2.format(m2="-4.6").replace("F1 F 0.305", "F1 F1 0.305")
    path.write_text(text, encoding="utf-8")
    diagnostics: list = []
    atoms = structure_from_cif(path, diagnostics=diagnostics).phases[0].atoms
    assert [a.label for a in atoms] == ["Mn1", "F1"]
    (species,) = [d for d in diagnostics if d.code == "CIF_SPECIES_NORMALISED"]
    assert species.where == ["phases.0.atoms.1.species"]


_WITH_B_AND_DISORDER = (_ROCKSALT.split("{extra}")[0]
    .replace("_atom_site_occupancy\n",
             "_atom_site_occupancy\n_atom_site_U_iso_or_equiv\n"
             "_atom_site_disorder_assembly\n_atom_site_disorder_group\n")
    .replace("Ni1 Ni 0 0 0 1", "Ni1 Ni 0 0 0 1 0.005 . .")
    .replace("O1 O 0.5 0.5 0.5 1", "O1 O 0.5 0.5 0.5 1 0.005 . ."))


@pytest.mark.parametrize("copy, field", [
    ("Ni2 Ni 0.5 0.5 0.0001 1 0.02 . .\n", "isotropic B"),
    ("Ni2 Ni 0.5 0.5 0.0001 1 0.005 A 1\n", "disorder"),
])
def test_a_copy_that_differs_in_displacement_or_disorder_is_refused(
        tmp_path, copy, field):
    """Not dropped unread: B and the disorder group are things a copy can state."""
    path = tmp_path / "twice.cif"
    path.write_text(_WITH_B_AND_DISORDER + copy, encoding="utf-8")
    with pytest.raises(ValueError, match=f"differ in {field}"):
        structure_from_cif(path)


def test_a_copy_that_states_the_same_displacement_is_still_dropped(tmp_path):
    """The positive arm of the two above."""
    path = tmp_path / "twice.cif"
    path.write_text(_WITH_B_AND_DISORDER + "Ni2 Ni 0.5 0.5 0.0001 1 0.005 . .\n",
                    encoding="utf-8")
    atoms = structure_from_cif(path).phases[0].atoms
    assert [a.label for a in atoms] == ["Ni1", "O1"]


def test_two_quoted_occupancies_summing_to_just_over_one_are_not_an_overfill(tmp_path):
    """0.523 + 0.481 = 1.004: a refined split of one position, read as before."""
    path = tmp_path / "split.cif"
    path.write_text(_ROCKSALT.replace("Ni1 Ni 0 0 0 1", "Ni1 Ni 0 0 0 0.523")
                    .format(extra="Ni2 Ni 0.5 0.5 0.0001 0.481\n"),
                    encoding="utf-8")
    diagnostics: list = []
    atoms = structure_from_cif(path, diagnostics=diagnostics).phases[0].atoms
    assert [a.label for a in atoms] == ["Ni1", "O1", "Ni2"]
    assert not [d for d in diagnostics if d.code == "CIF_SITE_LISTED_TWICE"]


def test_one_diagnostics_list_across_two_reads_keeps_the_first_reads_paths(tmp_path):
    """``_locate`` rewrites this call's rows, never the ones the caller already holds."""
    first = tmp_path / "first.cif"
    first.write_text(_ROCKSALT_LABELLED.format(extra="").replace(
        "O1 O1", "Ni2 Ni 0.5 0.5 0.0001 1\nO1 O1"), encoding="utf-8")
    second = tmp_path / "second.cif"
    second.write_text(_ROCKSALT.format(extra=""), encoding="utf-8")
    diagnostics: list = []
    structure_from_cif(first, diagnostics=diagnostics)
    (before,) = [d for d in diagnostics if d.code == "CIF_SITE_LISTED_TWICE"]
    assert before.where == ["phases.0.atoms.0"]
    structure_from_cif(second, diagnostics=diagnostics)
    (after,) = [d for d in diagnostics if d.code == "CIF_SITE_LISTED_TWICE"]
    assert after.where == ["phases.0.atoms.0"]


def test_a_merged_site_that_is_then_dropped_points_at_the_site_it_repeats(tmp_path):
    path = tmp_path / "hex2.cif"
    path.write_text(_HEX.format(x="0.828", y="0.656")
                    + "Co2 Co 0.828 0.657 0.25 1\n", encoding="utf-8")
    diagnostics: list = []
    atoms = structure_from_cif(path, diagnostics=diagnostics).phases[0].atoms
    assert [a.label for a in atoms] == ["Co1"]
    merged = [d for d in diagnostics if d.code == "CIF_SITE_TWINS_MERGED"]
    assert merged and all(d.where == ["phases.0.atoms.0"] for d in merged)


def test_a_copy_that_differs_in_anisotropic_displacement_is_refused(tmp_path):
    aniso = ("loop_\n_atom_site_aniso_label\n_atom_site_aniso_U_11\n"
             "_atom_site_aniso_U_22\n_atom_site_aniso_U_33\n"
             "_atom_site_aniso_U_12\n_atom_site_aniso_U_13\n_atom_site_aniso_U_23\n")
    text = (_ROCKSALT.format(extra="Ni2 Ni 0.5 0.5 0.0001 1\n") + aniso
            + "Ni1 0.005 0.005 0.005 0 0 0\nNi2 0.007 0.005 0.003 0 0 0\n"
              "O1 0.005 0.005 0.005 0 0 0\n")
    path = tmp_path / "twice.cif"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="differ in anisotropic displacement"):
        structure_from_cif(path, aniso=True)
