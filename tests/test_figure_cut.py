"""WP-1501 — cut and keep: a figure of part of the structure.

``keep`` renumbers ``atoms`` indices in ``bonds`` and ``polyhedra`` in one
place, so the tests that matter are the ones over every phase the polyhedra
suite measured: every index in range, every surviving bond and polyhedron
pointing at surviving atoms, and an all-true mask changing nothing.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3
from rietx.viz import component, keep, plane, recolour, render_structure, select, sphere
from rietx.viz.figure3d.cut import COMPLETE
from tests.test_render_structure import DATA, _rutile, _save
from tests.test_structure3d import MEASURED, measured


@pytest.fixture(scope="module")
def nac():
    return structure_from_cif(str(DATA / "cod_1000236.cif"), aniso=True)


def _consistent(g: dict) -> None:
    """Every index in range, and every bond or polyhedron joining atoms of the figure."""
    n, nb = len(g["atoms"]), len(g["bonds"])
    for b in g["bonds"]:
        assert 0 <= b["i"] < n and 0 <= b["j"] < n
        # ``b`` is the far end's image, not necessarily atom ``j``'s own position
        assert np.allclose(b["a"], g["atoms"][b["i"]]["pos"])
    for p in g["polyhedra"]:
        assert 0 <= p["center"] < n and all(0 <= v < n for v in p["vertices"])
        assert all(0 <= k < nb for k in p["bonds"])
        # a polyhedron's bonds are found by position, so their ``i`` and ``j`` may be
        # periodic twins of its centre and vertices: range is all that can be held
        assert all(0 <= v < len(p["vertices"]) for face in p["faces"] for v in face)


@pytest.mark.parametrize("row", MEASURED, ids=[row["name"] for row in MEASURED])
def test_keep_renumbers_every_index_on_the_measured_phases(row):
    g = s3.build(measured(row))
    rng = np.random.default_rng(7)
    _consistent(keep(g, np.ones(len(g["atoms"]), dtype=bool)))
    for fraction in (0.9, 0.5):
        mask = rng.random(len(g["atoms"])) < fraction
        for complete in COMPLETE:
            out = keep(g, mask, complete=complete)
            _consistent(out)
            assert len(out["atoms"]) >= mask.sum()
    assert keep(g, np.zeros(len(g["atoms"]), dtype=bool))["atoms"] == []


def test_an_all_true_mask_changes_nothing(nac):
    g = s3.build(nac)
    same = keep(g, np.ones(len(g["atoms"]), dtype=bool))
    assert same["atoms"] == g["atoms"] and same["bonds"] == g["bonds"]
    assert same["polyhedra"] == g["polyhedra"] and same["note"] == g["note"]
    assert np.array_equal(render_structure(g, size=200).image,
                          render_structure(same, size=200).image)


def test_keep_does_not_edit_its_input(nac):
    g = s3.build(nac)
    before = repr(g)
    keep(g, ~select(g, label="F2"), complete=True)
    recolour(g, select(g, element="Na"), "#ff0000")
    assert repr(g) == before


def test_nac_without_f2_by_mask_and_completed(nac):
    g = s3.build(nac)
    cut = keep(g, ~select(g, label="F2"))
    fig = render_structure(cut, size=400)
    _save(fig, "cut_nac_without_f2")
    assert len(fig.atoms) == 113
    assert "polyhedra cut" in cut["note"] and "bonds cut" in cut["note"]
    assert not any(a["label"] == "F2" for a in fig.atoms)
    whole = keep(g, ~select(g, label="F2"), complete=True)
    _consistent(whole)
    drawn = render_structure(whole, size=400)
    assert len(drawn.atoms) > 113 and "polyhedra cut" not in whole["note"]
    # completing re-adds far ends of F2's neighbours' bonds, so F2 itself returns
    assert any(a["label"] == "F2" for a in drawn.atoms)


def test_a_110_slab_of_nac_with_complete(nac):
    g = s3.build(nac)
    slab = keep(g, plane(g, (1, 1, 0), 0.5, width=0.5), complete=True)
    _consistent(slab)
    _save(render_structure(slab, size=400), "cut_nac_110_slab")
    assert 0 < len(slab["atoms"]) < len(g["atoms"])


def test_a_window_completes_its_polyhedra_alone():
    """YBa₂Cu₃O₇ one period long in a and two cells in b (issue #667).  The
    window holds 44 atoms.  ``complete=True`` adds 80, and 50 of them are far
    ends of cut bonds that are no kept polyhedron's vertex, hanging off the
    window's edge.  ``complete="polyhedra"`` adds the vertices alone."""
    st = structure_from_cif(str(DATA / "cod_9007744.cif"))
    g = s3.build(st, extent=((-1, 2), (-1, 3), (-1, 2)), max_atoms=10_000)
    frac = np.array([a["frac"] for a in g["atoms"]])
    e = 1e-3
    window = ((frac[:, 0] >= -e) & (frac[:, 0] < 1 - e) & (frac[:, 1] >= -e)
              & (frac[:, 1] <= 2 + e) & (frac[:, 2] >= -e) & (frac[:, 2] <= 1 + e))
    inside = set(np.flatnonzero(window).tolist())
    vertices = {v for p in g["polyhedra"] if window[p["center"]] for v in p["vertices"]}
    assert window.sum() == 44
    both = keep(g, window, complete=True)
    polys = keep(g, window, complete="polyhedra")
    bonds = keep(g, window, complete="bonds")
    for out in (both, polys, bonds):
        _consistent(out)
    assert len(both["atoms"]) == 44 + 80
    assert len(polys["atoms"]) == len(inside | vertices) == 44 + 30
    assert len(polys["atoms"]) < len(bonds["atoms"]) <= len(both["atoms"])
    # every polyhedron centred in the window is drawn whole, and nothing else was added
    assert len(polys["polyhedra"]) == sum(bool(window[p["center"]]) for p in g["polyhedra"])
    _save(render_structure(polys, view="a", size=500), "cut_ybco_window_polyhedra")
    _save(render_structure(both, view="a", size=500), "cut_ybco_window_both")
    with pytest.raises(ValueError, match="complete"):
        keep(g, window, complete="vertices")


def test_site_masks_refuse_a_name_the_phase_lacks(nac):
    g = s3.build(nac)
    with pytest.raises(ValueError, match="no such label.*'F1'"):
        select(g, label="Zz")
    with pytest.raises(ValueError, match="no such species"):
        select(g, species="Na")
    with pytest.raises(ValueError, match="sites 0 to 5"):
        select(g, site=9)
    assert select(g, element="F").sum() == sum(
        g["sites"][a["site"]]["element"] == "F" for a in g["atoms"])
    both = select(g, species="F1-", boundary=False)
    assert both.sum() < select(g, species="F1-").sum()


def test_a_bad_mask_is_refused(nac):
    g = s3.build(nac)
    with pytest.raises(ValueError, match="boolean array"):
        keep(g, [True, False])
    with pytest.raises(ValueError, match="boolean array"):
        keep(g, np.arange(len(g["atoms"])))


def test_a_plane_keeps_the_origin_side_in_d_spacings():
    cubic = structure_from_cif(str(DATA / "cod_1000055.cif"))
    g = s3.build(cubic)
    frac = np.array([a["frac"] for a in g["atoms"]])
    for hkl, dist in (((1, 0, 0), 1), ((1, 1, 0), 1), ((1, 1, 1), 0.5)):
        expected = frac @ np.array(hkl) <= dist + 1e-9
        assert np.array_equal(plane(g, hkl, dist), expected)
    assert np.array_equal(plane(g, (1, 0, 0), 1, inverse=True), ~plane(g, (1, 0, 0), 1))
    a = g["cell"][0]
    assert np.array_equal(plane(g, (1, 0, 0), a, units="angstrom"), plane(g, (1, 0, 0), 1))
    slab = plane(g, (1, 0, 0), 0.25, width=0.5)
    assert np.array_equal(slab, (frac[:, 0] >= 0.25 - 1e-9) & (frac[:, 0] <= 0.75 + 1e-9))
    with pytest.raises(ValueError, match="units"):
        plane(g, (1, 0, 0), 1, units="nm")
    with pytest.raises(ValueError, match="not all zero"):
        plane(g, (0, 0, 0), 1)


def test_a_plane_distance_is_along_the_normal_in_a_skewed_cell():
    """d-spacing through the metric, not the cell edge: monoclinic (100) at d."""
    from tests.test_render_structure import _monoclinic
    g = s3.build(_monoclinic())
    a, beta = g["cell"][0], np.radians(g["cell"][4])
    d100 = a * np.sin(beta)
    by_angstrom = plane(g, (1, 0, 0), 0.6 * d100, units="angstrom")
    assert np.array_equal(by_angstrom, plane(g, (1, 0, 0), 0.6))


def test_a_sphere_takes_an_index_or_a_point(nac):
    g = s3.build(nac)
    pos = np.array([a["pos"] for a in g["atoms"]])
    by_index = sphere(g, 0, 3.0)
    by_point = sphere(g, pos[0], 3.0)
    assert np.array_equal(by_index, by_point) and by_index[0]
    assert np.array_equal(by_index, np.linalg.norm(pos - pos[0], axis=1) <= 3.0)
    with pytest.raises(ValueError, match="atoms 0 to"):
        sphere(g, 10_000, 3.0)
    with pytest.raises(ValueError, match="Cartesian point"):
        sphere(g, (1.0, 2.0), 3.0)


def test_rutile_edge_sharing_is_a_chain_and_nac_bonds_are_the_cell(nac):
    r = s3.build(_rutile())
    ti = next(i for i, a in enumerate(r["atoms"])
              if r["sites"][a["site"]]["element"] == "Ti" and not a["boundary"])
    edges = component(r, ti, via="edges")
    corners = component(r, ti, via="corners")
    faces = component(r, ti, via="faces")
    assert faces.sum() < edges.sum() < corners.sum() <= len(r["atoms"])
    assert (edges <= corners).all() and (faces <= edges).all()
    centres = {p["center"] for p in r["polyhedra"]}
    chain = [i for i in np.flatnonzero(edges) if i in centres]
    assert len(chain) > 1
    _save(render_structure(keep(r, edges), size=400), "cut_rutile_edge_chain")
    with pytest.raises(ValueError, match="via"):
        component(r, ti, via="hops")
    # an atom no polyhedron holds has no piece joined by corners
    lone = next(i for i in range(len(r["atoms"]))
                if not any(i == p["center"] or i in p["vertices"] for p in r["polyhedra"]))
    with pytest.raises(ValueError, match="in no polyhedron"):
        component(r, lone, via="corners")

    g = s3.build(nac)
    whole = component(g, 0, via="bonds")
    # every atom of the cell is one piece by bonds; the rest are images, the
    # polyhedra's far vertices, that no bond reaches
    assert whole[select(g, boundary=False)].all()
    assert whole[[b["i"] for b in g["bonds"]]].all()


def test_recolour_paints_part_of_a_site_and_its_polyhedra(nac):
    g = s3.build(nac)
    al = select(g, element="Al") & ~select(g, boundary=True)
    pick = np.flatnonzero(al)[:1]
    one = np.zeros(len(g["atoms"]), dtype=bool)
    one[pick] = True
    out = recolour(g, one, "#ff0000")
    _consistent(out)
    assert len(out["sites"]) == len(g["sites"]) + 1
    fig = render_structure(out, size=400)
    _save(fig, "cut_nac_one_recoloured")
    base = render_structure(g, size=400)
    assert fig.palette["Al1 (recoloured)"] == "#ff0000"
    assert fig.palette["Al1"] == base.palette["Al1"]
    assert not np.array_equal(fig.image, base.image)
    # the polyhedron round the painted atom took the colour, the rest kept theirs
    painted = [p for p in out["polyhedra"] if out["sites"][p["site"]].get("recoloured")]
    assert len(painted) == 1 and painted[0]["center"] == pick[0]
    white = recolour(g, one, "White")
    assert white["sites"][-1]["color"] == "#ffffff"


def test_a_site_colour_the_scene_would_grey_is_refused(nac):
    g = s3.build(nac)
    g["sites"][0]["color"] = "red"
    with pytest.raises(ValueError, match=r"sites\[0\] \(Ca1\).*#rrggbb"):
        render_structure(g, size=100)
    g["sites"][0]["color"] = "White"
    fig = render_structure(g, size=100)
    assert fig.palette["Ca1"] == "#ffffff"
    with pytest.raises(ValueError, match="#rrggbb"):
        recolour(s3.build(nac), np.ones(len(g["atoms"]), dtype=bool), "red")


def test_review_fixes_hold(nac):
    """Found by the WP-1501 review: each was a wrong answer that looked like one."""
    g = s3.build(nac)
    with pytest.raises(ValueError):
        plane(g, (1, 1, 0), float("nan"))
    # a vertex is shared by octahedra that touch only at a corner, so by edges or
    # faces it names no single piece; a centre does
    vertex = next(v for p in g["polyhedra"] for v in p["vertices"])
    centre = g["polyhedra"][0]["center"]
    with pytest.raises(ValueError):
        component(g, vertex, via="faces")
    assert component(g, centre, via="faces")[centre]
    # two recolours of one site in two colours are two legend entries
    first = np.zeros(len(g["atoms"]), dtype=bool)
    second = first.copy()
    al = np.flatnonzero(select(g, element="Al") & ~select(g, boundary=True))
    first[al[0]], second[al[1]] = True, True
    out = recolour(recolour(g, first, "#ff0000"), second, "#0000ff")
    colours = set(render_structure(out, size=100).palette.values())
    assert {"#ff0000", "#0000ff"} <= colours


def test_hidden_a_label_names_the_mask_route(nac):
    with pytest.raises(ValueError, match=r"keep\(g, ~select\(g, label='F2'\)\)"):
        render_structure(nac, hidden=["F2"], size=100)
    with pytest.raises(ValueError, match="no such species or element") as e:
        render_structure(nac, hidden=["Zz"], size=100)
    assert "site label" not in str(e.value)
