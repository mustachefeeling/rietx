"""A site whose own images coincide is one atom on every route, not only a CIF read (#1007).

``site_orbit`` snaps a site within ``SITE_TOL`` (1e-4, fractional) of a special
position, and on a mirror that is 5e-5 of the coordinate, because the test
compares the 2δ displacement.  PbSO₄'s S2 (``tests/data/gsas2_pbso4.gpx``, Pnma
4c on the mirror at y = ¼) moved 6e-5 off it is a general position: two images
0.0006 Å apart, 8 S in a cell of 4.  #765 merged such twins for a CIF read; here
the same rule (``symmetry.site_twin_merge``, 0.02 Å) runs where every route
builds a ``Phase`` and where ``phase_zmv`` counts raw coordinates.

Each test checks what is independent of the code under test: the multiplicity
International Tables gives the Wyckoff position, the composition the published
structure has, and the prediction of the same structure stated on its special
position.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.symmetry import (
    TWIN_DISTANCE,
    resolve_group,
    site_orbit,
    site_twin_merge,
)
from rietx.io.projects.gsas2 import read_gsas2_gpx, to_structure
from rietx.optimize.qpa import phase_zmv
from rietx.refine import _symmetry_silence_diagnostics
from rietx.schemas import Atom, Cell, Parameter, Phase, Structure

DATA = Path(__file__).parent / "data"


@pytest.fixture(scope="module")
def pbso4() -> Phase:
    return to_structure(read_gsas2_gpx(DATA / "gsas2_pbso4.gpx")).phases[0]


def _moved(phase: Phase, label: str, **shift) -> Phase:
    """``phase`` rebuilt with one atom's coordinates shifted, as a document edit is."""
    doc = phase.model_dump()
    for atom in doc["atoms"]:
        if atom["label"] == label:
            for axis, d in shift.items():
                atom[axis]["value"] += d
    return Phase.model_validate(doc)


def _counts(phase: Phase) -> dict[str, float]:
    atoms = [(a.species, a.x.value, a.y.value, a.z.value, a.occ.value)
             for a in phase.atoms]
    return phase_zmv(phase.space_group, phase.cell.lengths_angles(),
                     atoms).element_counts


def _multiplicity(phase: Phase, label: str) -> int:
    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    (a,) = [a for a in phase.atoms if a.label == label]
    return site_orbit(sg, np.array([a.x.value, a.y.value, a.z.value])).multiplicity


def _codes(structure: Structure) -> list[str]:
    return [d.code for d in _symmetry_silence_diagnostics(structure)]


@pytest.mark.parametrize("dy", [6e-5, 1e-4, 1e-3])
def test_issue_reproducer_counts_four_sulfur(pbso4, dy):
    """#1007's reproducer, verbatim in its core: raw coordinates into ``phase_zmv``."""
    atoms = [(a.species, a.x.value, a.y.value + (dy if a.label == "S2" else 0),
              a.z.value, a.occ.value) for a in pbso4.atoms]
    c = phase_zmv(pbso4.space_group, pbso4.cell.lengths_angles(), atoms).element_counts
    assert (c["Pb"], c["S"], c["O"]) == (4, 4, 16)      # PbSO₄, Z = 4


@pytest.mark.parametrize("dy", [6e-5, 1e-4, 1e-3])
def test_a_phase_built_with_the_site_off_the_mirror_holds_it_on(pbso4, dy):
    phase = _moved(pbso4, "S2", y=dy)
    (s2,) = [a for a in phase.atoms if a.label == "S2"]
    assert s2.y.value == pytest.approx(0.25, abs=1e-12)
    assert _multiplicity(phase, "S2") == 4                # Pnma 4c
    assert _counts(phase)["S"] == 4
    (merge,) = phase._site_twin_merges
    assert (merge.label, merge.before, merge.after) == ("S2", 8, 4)
    # the two images are 2·dy·b apart, which is what the record says
    assert merge.gap == pytest.approx(2 * dy * pbso4.cell.b.value, rel=1e-6)
    structure = Structure(phases=[phase])
    assert _codes(structure).count("SITE_TWINS_MERGED") == 1


@pytest.mark.parametrize("dy", [4e-3, 1e-2])
def test_images_further_apart_than_the_twin_distance_stay_general(pbso4, dy):
    """The negative arm: 2·dy·b = 0.043 Å and 0.108 Å are real offsets."""
    assert 2 * dy * pbso4.cell.b.value > TWIN_DISTANCE
    phase = _moved(pbso4, "S2", y=dy)
    (s2,) = [a for a in phase.atoms if a.label == "S2"]
    assert s2.y.value == pytest.approx(0.25 + dy, abs=1e-15)
    assert _multiplicity(phase, "S2") == 8
    assert _counts(phase)["S"] == 8
    assert not phase._site_twin_merges
    assert "SITE_TWINS_MERGED" not in _codes(Structure(phases=[phase]))


def test_a_coordinate_assigned_after_construction_is_merged_by_the_refinement(pbso4):
    """A hand edit on a built object never re-validates the phase; the fit's copy does."""
    structure = Structure(phases=[pbso4.model_copy(deep=True)])
    (s2,) = [a for a in structure.phases[0].atoms if a.label == "S2"]
    s2.y.value = 0.25 + 1e-4                       # after the Structure was built
    assert _multiplicity(structure.phases[0], "S2") == 8
    ref = rx.Refinement(structure, rx.Instrument.constant_wavelength_neutron(1.5),
                        history=False)
    assert _multiplicity(ref.structure.phases[0], "S2") == 4
    assert "SITE_TWINS_MERGED" in _codes(ref.structure)
    assert s2.y.value == 0.25 + 1e-4                     # the caller's object is untouched


def _predict(structure: Structure) -> np.ndarray:
    ref = rx.Refinement(structure, rx.Instrument.constant_wavelength_neutron(1.5),
                        history=False)
    return np.asarray(ref.predict(np.arange(10.0, 120.0, 0.05)))


def test_predict_on_the_merged_site_equals_the_site_stated_on_the_mirror(pbso4):
    on = Structure(phases=[pbso4])
    off = Structure(phases=[_moved(pbso4, "S2", y=1e-4)])
    a, b = _predict(on), _predict(off)
    assert np.max(np.abs(a - b)) / np.max(a) < 1e-12


def _phase(group: str, cell, xyz, *, occ: float = 1.0) -> Phase:
    return Phase(
        name="p", space_group=group,
        cell=Cell(**{k: Parameter(value=v) for k, v in
                     zip(("a", "b", "c", "alpha", "beta", "gamma"), cell, strict=True)}),
        atoms=[Atom(label="X", species="Fe", x=Parameter(value=xyz[0]),
                    y=Parameter(value=xyz[1]), z=Parameter(value=xyz[2]),
                    occ=Parameter(value=occ), biso=Parameter(value=0.5))])


# group, cell, the Wyckoff position (ITA vol. A) and its multiplicity, a point
# 1e-4 off it that SITE_TOL leaves general, and the point it is
@pytest.mark.parametrize("group, cell, stated, special, mult, general", [
    # 2-fold axis: C2/c 4e (0, y, ¼)
    ("C 1 2/c 1", (10.0, 8.0, 9.0, 90, 105, 90),
     (1e-4, 0.3, 0.25 - 1e-4), (0.0, 0.3, 0.25), 4, 8),
    # 3-fold axis: Pa-3 8c (x, x, x)
    ("P a -3", (6.0, 6.0, 6.0, 90, 90, 90),
     (0.1, 0.1 + 1e-4, 0.1 - 1e-4), (0.1, 0.1, 0.1), 8, 24),
    # inversion centre: P-1 1a (0, 0, 0)
    ("P -1", (5.0, 6.0, 7.0, 80, 85, 95),
     (1e-4, -1e-4, 2e-4), (0.0, 0.0, 0.0), 1, 2),
])
def test_a_site_near_an_axis_or_a_centre_lands_on_its_wyckoff_position(
        group, cell, stated, special, mult, general):
    sg = resolve_group(group, None)
    assert site_orbit(sg, np.array(stated)).multiplicity == general  # beyond SITE_TOL
    phase = _phase(group, cell, stated)
    a = phase.atoms[0]
    got = np.array([a.x.value, a.y.value, a.z.value])
    d = got - np.array(special)
    assert np.max(np.abs(d - np.round(d))) < 1e-12
    assert _multiplicity(phase, "X") == mult
    (merge,) = phase._site_twin_merges
    assert (merge.before, merge.after) == (general, mult)


def test_a_split_site_is_left_split():
    """Images 0.2 Å apart at half occupancy are a split site, never twins."""
    dy = 0.1 / 8.0                                         # 2·dy·b = 0.2 Å
    phase = _phase("P n m a", (7.0, 8.0, 6.0, 90, 90, 90),
                   (0.1, 0.25 + dy, 0.3), occ=0.5)
    assert phase.atoms[0].y.value == 0.25 + dy
    assert _multiplicity(phase, "X") == 8
    assert not phase._site_twin_merges


def test_the_cif_route_reports_on_its_own_channel_only(tmp_path):
    """A CIF read merges and says ``CIF_SITE_TWINS_MERGED``; the phase has nothing left."""
    path = tmp_path / "hex.cif"
    path.write_text("""data_hex
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
Co1 Co 0.828 0.657 0.25 1
""", encoding="utf-8")
    diagnostics: list = []
    structure = structure_from_cif(path, diagnostics=diagnostics)
    assert [d.code for d in diagnostics].count("CIF_SITE_TWINS_MERGED") == 1
    assert not structure.phases[0]._site_twin_merges
    assert "SITE_TWINS_MERGED" not in _codes(structure)


def test_a_rigid_body_atom_is_left_to_the_body(pbso4):
    """A body owns its atoms' positions; the merge never moves one."""
    from rietx.crystallography.bodies import body_from_atoms

    off = pbso4.model_copy(deep=True)
    (s2,) = [a for a in off.atoms if a.label == "S2"]
    s2.y.value = 0.25 + 1e-4                       # assigned: not yet merged
    body = body_from_atoms(off, ["S2", "O3", "O4"], "frag")
    doc = off.model_dump()
    doc["rigid_bodies"] = [body.model_dump()]
    phase = Phase.model_validate(doc)
    (s2,) = [a for a in phase.atoms if a.label == "S2"]
    assert s2.y.value == 0.25 + 1e-4
    assert not phase._site_twin_merges


def test_site_twin_merge_takes_a_six_tuple_or_a_gemmi_cell():
    import gemmi

    sg = resolve_group("P n m a", None)
    xyz = (0.1, 0.25 + 1e-4, 0.3)
    a = site_twin_merge(sg, (7.0, 8.0, 6.0, 90, 90, 90), xyz)
    b = site_twin_merge(sg, gemmi.UnitCell(7.0, 8.0, 6.0, 90, 90, 90), xyz)
    assert a is not None and b is not None
    assert a.gap == pytest.approx(2e-4 * 8.0) and a.gap == b.gap
    assert np.array_equal(a.position, b.position)


def _s2_off_the_mirror(text: str, y: str) -> str:
    """A written project file with only S2's y edited, as a hand edit would."""
    out = text.replace("0.0651619194267896 0.25 ", f"0.0651619194267896 {y} ", 1)
    out = out.replace("x @ 0.0651619194267896 y @ 0.25 ",
                      f"x @ 0.0651619194267896 y @ {y} ", 1)
    assert out != text
    return out


def test_a_fullprof_file_with_the_site_off_the_mirror_reads_four_sulfur(pbso4, tmp_path):
    """``Occ`` is m/M: S2's 0.5 is a 4c site, and the reader's ratio must say so."""
    from rietx.io.projects.fullprof import (
        read_fullprof_pcr,
        write_fullprof_pcr,
    )
    from rietx.io.projects.fullprof import to_structure as pcr_to_structure

    written = tmp_path / "on.pcr"
    write_fullprof_pcr(Structure(phases=[pbso4]), written)
    edited = tmp_path / "off.pcr"
    edited.write_text(_s2_off_the_mirror(written.read_text(encoding="utf-8"),
                                         "0.2501"), encoding="utf-8")
    phase = pcr_to_structure(read_fullprof_pcr(edited)).phases[0]
    assert [a.occ.value for a in phase.atoms] == [1.0] * 5
    assert _counts(phase)["S"] == 4
    assert [m.label for m in phase._site_twin_merges] == ["S2"]


def test_a_topas_file_with_the_site_off_the_mirror_reads_four_sulfur(pbso4, tmp_path):
    from rietx.io.projects import topas

    path = tmp_path / "off.inp"
    path.write_text(_s2_off_the_mirror(topas.from_structure(Structure(phases=[pbso4])),
                                       "0.2501"), encoding="utf-8")
    phase = topas.to_structure(topas.read_topas_inp(path)).phases[0]
    assert _counts(phase) == {"Pb": 4, "S": 4, "O": 16}
    assert [m.label for m in phase._site_twin_merges] == ["S2"]


def test_a_merged_phase_round_trips_unchanged(pbso4):
    """After the move the document states the special position, and says nothing more."""
    phase = _moved(pbso4, "S2", y=1e-4)
    again = Phase.model_validate_json(phase.model_dump_json())
    assert again.model_dump() == phase.model_dump()
    assert not again._site_twin_merges


def test_the_distance_decides_not_the_fractional_reach():
    """b = 20 Å, a = 5 Å: 2·dy = 0.003 is inside the 0.02/5 reach, 2·dy·b = 0.06 Å is not."""
    dy = 1.5e-3
    phase = _phase("P n m a", (5.0, 20.0, 6.0, 90, 90, 90), (0.1, 0.25 + dy, 0.3))
    assert 2 * dy < TWIN_DISTANCE / 5.0 and 2 * dy * 20.0 > TWIN_DISTANCE
    assert phase.atoms[0].y.value == 0.25 + dy
    assert _multiplicity(phase, "X") == 8
    assert not phase._site_twin_merges
