"""WP-1502 — an extent beyond one cell, the periodic identity and what reads it.

The oracle for a block is the thing it stands in for: the same crystal as a P1
cell of that size, built from scratch by the ordinary single-cell search.  The
block is the one cell's result translated, never searched again, so agreeing
with that search on atoms, bonds and polyhedra is the whole claim.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3
from rietx.schemas.structure import Atom, Cell, Parameter, Phase, Structure
from rietx.viz import component, keep, periodicity, plane, render_structure, select, sphere
from tests.test_render_structure import DATA, _save
from tests.test_structure3d import MEASURED, measured

BIG = 10 ** 6


def _row(name: str) -> Structure:
    return measured(next(r for r in MEASURED if r["name"] == name))


@pytest.fixture(scope="module")
def nac():
    return structure_from_cif(str(DATA / "cod_1000236.cif"), aniso=True)


def _p(value: float) -> Parameter:
    return Parameter(value=float(value))


def supercell(structure: Structure, n: tuple[int, int, int]) -> Structure:
    """``structure`` as a P1 phase over ``n`` cells: every image, written out."""
    g = s3.build(structure)
    cell = structure.phases[0].cell
    orbit = {a["image"][0]: a for a in g["atoms"] if not a["boundary"]}
    atoms = []
    for t in itertools.product(*map(range, n)):
        for o in sorted(orbit):
            site = g["sites"][orbit[o]["site"]]
            x, y, z = (np.array(orbit[o]["frac"]) + t) / np.array(n)
            atoms.append(Atom(label=f"{site['label']}_{len(atoms)}", species=site["species"],
                              x=_p(x), y=_p(y), z=_p(z), occ=_p(site["occ"])))
    big = Cell(a=_p(cell.a.value * n[0]), b=_p(cell.b.value * n[1]), c=_p(cell.c.value * n[2]),
               alpha=_p(cell.alpha.value), beta=_p(cell.beta.value), gamma=_p(cell.gamma.value))
    return Structure(phases=[Phase(name="P1", space_group="P 1", cell=big, atoms=atoms)])


def _key(point) -> tuple:
    """A position to 1e-4 Å.  Shifted off the rounding ties first, since a
    coordinate of 2.29685 lands either side of one by the last bit of its
    arithmetic, and two builds of one crystal do not agree to it."""
    return tuple(np.round(np.asarray(point, dtype=np.float64) + 1.2345e-5, 4))


def _atoms(g: dict) -> set:
    return {_key(a["pos"]) for a in g["atoms"]}


def _bonds(g: dict) -> set:
    return {tuple(sorted((_key(b["a"]), _key(b["b"])))) for b in g["bonds"]}


def _polyhedra(g: dict) -> set:
    pos = [a["pos"] for a in g["atoms"]]
    return {(_key(pos[p["center"]]), tuple(sorted(_key(pos[v]) for v in p["vertices"])))
            for p in g["polyhedra"]}


@pytest.mark.parametrize("name, n", [
    ("NAC", (2, 2, 2)), ("LaB6", (3, 2, 2)), ("gypsum CaSO4.2H2O", (2, 1, 2)),
    ("quartz SiO2", (2, 2, 1)), ("rutile TiO2", (2, 3, 1))])
def test_a_block_is_the_crystal_built_as_a_p1_cell_of_that_size(name, n):
    """Atoms, bonds and polyhedra agree as sets of positions, in cells that are
    cubic, hexagonal and monoclinic."""
    st = _row(name)
    got = s3.build(st, extent=tuple((0, m) for m in n), max_atoms=BIG)
    ref = s3.build(supercell(st, n), max_atoms=BIG)
    assert _atoms(got) == _atoms(ref)
    assert _bonds(got) == _bonds(ref)
    assert _polyhedra(got) == _polyhedra(ref)
    assert got["extent"] == [list(m) for m in ((0, n[0]), (0, n[1]), (0, n[2]))]


def test_nac_two_by_two_by_two_counts_each_atom_once(nac):
    """672 atoms in the box, 24 of them's face duplicates (the cell's own rule),
    and the 1064 a P1 expansion draws: the 1480 of a tiled cell counted every
    face atom once per neighbouring cell."""
    g = s3.build(nac, extent=((0, 2),) * 3, max_atoms=BIG)
    assert sum(not a["boundary"] for a in g["atoms"]) == 672
    assert g["n_cell"] == 696
    assert len(g["atoms"]) == 1064
    assert len(s3.build(supercell(nac, (2, 2, 2)), max_atoms=BIG)["atoms"]) == 1064
    # each image of one atom is named once
    assert len({(a["image"][0], *a["image"][1]) for a in g["atoms"]}) == len(g["atoms"])


@pytest.mark.parametrize("row", MEASURED, ids=[row["name"] for row in MEASURED])
def test_the_one_cell_is_the_identity_of_the_translation(row):
    """Translating the cell over the extent (0, 1)³ gives the cell back."""
    g = s3.build(measured(row))
    again = s3._tile(g, s3.DEFAULT_EXTENT, s3.MAX_ATOMS * 100, 0.0)
    assert _atoms(again) == _atoms(g)
    assert _bonds(again) == _bonds(g)
    assert _polyhedra(again) == _polyhedra(g)
    assert s3.build(measured(row), extent=((0, 1),) * 3) == g


@pytest.mark.parametrize("extent", [None, ((0, 2), (0, 1), (0, 3)), ((-1, 1), (0, 2), (2, 3))])
def test_every_atom_sits_where_its_image_says_and_every_bond_ends_on_atoms(nac, extent):
    g = s3.build(nac, extent=extent, max_atoms=BIG)
    basis = np.asarray(g["lattice"]).T
    cell = s3.build(nac)
    home = {a["image"][0]: np.array(a["frac"]) - a["image"][1] for a in cell["atoms"]}
    pos = np.array([a["pos"] for a in g["atoms"]])
    for a in g["atoms"]:
        o, n = a["image"]
        assert np.allclose(a["frac"], home[o] + n, atol=1e-12)
        assert np.allclose(a["pos"], basis @ np.array(a["frac"]), atol=1e-12)
    for b in g["bonds"]:
        assert np.allclose(pos[b["i"]], b["a"])
        # the one cell's ``j`` is an image of the far end, a block's is the atom there
        assert extent is None or np.allclose(pos[b["j"]], b["b"])
    assert len({_key(p) for p in pos}) == len(pos)


def test_an_extent_frame_and_its_note(nac):
    g = s3.build(nac, extent=((0, 2), (0, 1), (-1, 1)), max_atoms=BIG)
    a = g["lattice"][0][0]
    assert np.allclose(np.array(g["corners"]).max(axis=0) - np.array(g["corners"]).min(axis=0),
                       [2 * a, a, 2 * a])
    assert "extent 2×1×2" in g["note"] and f"{len(g['atoms'])} atoms" in g["note"]
    assert s3.build(nac)["note"] == ""


def test_an_extent_is_three_pairs_of_whole_cells_and_the_block_obeys_the_cap(nac):
    for bad in (2, ((0, 2),) * 2, ((0, 2), (0, 2), (0, 1.5)), ((0, 2), (0, 2), (1, 1)),
                ((0, 2), (0, 2), (True, 2))):
        with pytest.raises(ValueError, match="extent"):
            s3.build(nac, extent=bad)
    with pytest.raises(ValueError, match="max_atoms"):
        s3.build(nac, extent=((0, 2),) * 3)


def test_three_cells_a_side_build_in_no_more_than_a_moment(nac):
    """A runaway guard, not a timer: the dense search over 3143 atoms was 27
    matrices of 3143².  The measured range is in WP-1502's handover."""
    import time
    start = time.perf_counter()
    g = s3.build(nac, extent=((0, 3),) * 3, max_atoms=BIG)
    assert time.perf_counter() - start < 5.0
    assert len(g["atoms"]) > 3000


# ----------------------------------------------------------------------
# what reads the identity
# ----------------------------------------------------------------------

def _first(g: dict, element: str) -> int:
    return next(k for k, a in enumerate(g["atoms"][:g["n_cell"]])
                if g["sites"][a["site"]]["element"] == element)


@pytest.mark.parametrize("extent", [None, ((0, 2),) * 3], ids=["one cell", "2x2x2"])
def test_a_motifs_periodicity_is_the_dimension_of_its_lattice(nac, extent):
    """Rutile's edge-sharing chain is 1, gypsum's Ca–O–S layer 2, a carbonate
    group 0 and NAC's framework 3, whether the block is one cell or eight."""
    def build(st):
        return s3.build(st, extent=extent, max_atoms=BIG)

    rutile = build(_row("rutile TiO2"))
    chain = component(rutile, _first(rutile, "Ti"), via="edges")
    assert periodicity(rutile, chain) == 1

    gypsum = build(_row("gypsum CaSO4.2H2O"))
    layer = component(gypsum, _first(gypsum, "Ca"), via="bonds")
    assert periodicity(gypsum, layer) == 2

    calcite = build(_row("calcite CaCO3"))
    carbon = _first(calcite, "C")
    group = sphere(calcite, carbon, 1.5)
    assert group.sum() == 4 and periodicity(calcite, group) == 0
    assert periodicity(calcite, component(calcite, carbon, via="bonds")) == 3

    g = build(nac)
    assert periodicity(g, component(g, _first(g, "Na"), via="bonds")) == 3
    assert periodicity(g, np.zeros(len(g["atoms"]), dtype=bool)) == 0
    # a Ti and one O bonded to it close on themselves; the octahedron does not,
    # since two of its O are one atom of the cell a lattice vector apart, which
    # is the chain's bridge
    ti = _first(rutile, "Ti")
    bond = next(b for b in rutile["bonds"] if b["i"] == ti)
    pair = np.zeros(len(rutile["atoms"]), dtype=bool)
    pair[[bond["i"], bond["j"]]] = True
    assert periodicity(rutile, pair) == 0
    octahedron = next(p for p in rutile["polyhedra"] if p["center"] == ti)
    whole = np.zeros(len(rutile["atoms"]), dtype=bool)
    whole[[octahedron["center"], *octahedron["vertices"]]] = True
    assert periodicity(rutile, whole) == 1
    with pytest.raises(ValueError, match="boolean"):
        periodicity(g, [True])


def test_a_bond_is_followed_to_the_atom_at_its_far_end(nac):
    """``j`` is an image of the far end, and a cut that kept the atom ``j`` but
    not the far end drew a stick ending in mid-air."""
    g = s3.build(nac)
    inverse = np.linalg.inv(np.asarray(g["lattice"]).T)
    home = {a["image"][0]: np.array(a["frac"]) - a["image"][1] for a in g["atoms"]}
    at = {(a["image"][0], *a["image"][1]): k for k, a in enumerate(g["atoms"])}
    moved = 0
    for b in g["bonds"]:
        o = g["atoms"][b["j"]]["image"][0]
        n = np.rint(inverse @ np.array(b["b"]) - home[o]).astype(int)
        far = at[(o, *n)]
        moved += far != b["j"]
        assert np.allclose(g["atoms"][far]["pos"], b["b"])
    assert moved > 0
    cut = keep(g, select(g, element="Na") & ~select(g, boundary=True))
    pos = {_key(a["pos"]) for a in cut["atoms"]}
    assert all(_key(b["b"]) in pos and _key(b["a"]) in pos for b in cut["bonds"])


def test_a_slab_keeps_whole_polyhedra_and_no_bond_ends_in_mid_air():
    """A (001) slab of fluorapatite one cell thick, cut from a 2×2×3 block."""
    fap = structure_from_cif(str(DATA / "fluorapatite.cif"))
    g = s3.build(fap, extent=((0, 2), (0, 2), (0, 3)), max_atoms=BIG)
    slab = plane(g, (0, 0, 1), 1.0, width=1.0)
    bare = keep(g, slab)
    whole = keep(g, slab, complete=True)
    centred = {p["center"] for p in g["polyhedra"] if slab[p["center"]]}
    assert centred
    assert len(whole["polyhedra"]) > len(bare["polyhedra"])
    assert len(whole["polyhedra"]) >= len(centred)
    for out in (bare, whole):
        pos = {_key(a["pos"]) for a in out["atoms"]}
        assert all(_key(b["a"]) in pos and _key(b["b"]) in pos for b in out["bonds"])
    _save(render_structure(whole, size=600), "extent_fluorapatite_001_slab")


def test_a_two_by_two_by_one_block_of_nac_is_drawn(nac):
    g = s3.build(nac, extent=((0, 2), (0, 2), (0, 1)), max_atoms=BIG)
    _save(render_structure(g, size=600), "extent_nac_2x2x1")
    assert len(g["polyhedra"]) > 34
