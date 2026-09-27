"""WP-1470 — a structure figure drawn in Python, without a browser.

Two halves.  The **scene corpus** holds the Python copy of the structure
viewer's scene rules equal to the TypeScript original: this module writes
``tests/data/gui/scene_cases.json`` from :mod:`rietx.viz.figure3d.scene` and
``gui/src/lib/structure3d.test.ts`` replays every case against ``buildScene``,
``shownPolyhedra``, ``lookFrom`` and ``axisView``.  The fixture is committed
because vitest runs where this package is not installed, so the check here is
``test_gui_fnmatch.py``'s: regenerate, compare, and fail naming the file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rietx.gui import structure3d as s3
from rietx.schemas.structure import AnisoU, Atom, Cell, Phase, Structure
from rietx.viz.figure3d import scene as sc

DATA = Path(__file__).parent / "data"
FIXTURE = DATA / "gui" / "scene_cases.json"


def _p(value: float) -> dict:
    return {"value": value}


def _monoclinic(**atom_kw) -> Structure:
    """P2₁/c, β = 110°: axes not orthogonal, a general position and a centre."""
    cell = Cell(a=_p(5.0), b=_p(9.0), c=_p(7.0),
                alpha=_p(90.0), beta=_p(110.0), gamma=_p(90.0))
    atoms = [Atom(label="C1", species="C", x=_p(0.12), y=_p(0.23), z=_p(0.34), **atom_kw),
             Atom(label="O1", species="O", x=_p(0.0), y=_p(0.0), z=_p(0.0))]
    return Structure(phases=[Phase(name="mono", space_group="P 1 21/c 1",
                                   cell=cell, atoms=atoms)])


def _rutile() -> Structure:
    """P4₂/mnm with an anisotropic Ti: octahedra, most of them centred on an
    image outside the cell, at 28 kB of payload against LaB6's 64."""
    cell = Cell(a=_p(4.594), b=_p(4.594), c=_p(2.959),
                alpha=_p(90.0), beta=_p(90.0), gamma=_p(90.0))
    atoms = [Atom(label="Ti1", species="Ti", x=_p(0.0), y=_p(0.0), z=_p(0.0),
                  aniso=AnisoU.from_values([0.006, 0.006, 0.004, 0.0005, 0.0, 0.0])),
             Atom(label="O1", species="O", x=_p(0.3049), y=_p(0.3049), z=_p(0.0))]
    return Structure(phases=[Phase(name="rutile", space_group="P 42/m n m",
                                   cell=cell, atoms=atoms)])


def _payloads() -> dict[str, dict]:
    """Four payloads, chosen for the rules each one reaches, and small.

    Rutile has images outside the cell, anisotropic rings and polyhedra drawn
    by default; at a bond tolerance of 0.8 it has no bonds and 34 atoms that
    are there only as a polyhedron's vertices.  The two monoclinic cells have
    one and two axes that are not positive, which reach both branches of
    ``drawable``'s floor.
    """
    one_bad = AnisoU.from_values([0.02, 0.03, -0.01, 0.0, 0.0, 0.004])
    two_bad = AnisoU.from_values([0.02, -0.01, -0.01, 0.0, 0.0, 0.0])
    return {
        "rutile": s3.build(_rutile()),
        "rutile_vertex_only": s3.build(_rutile(), bond_tolerance=0.8),
        "mono_one_flat": s3.build(_monoclinic(aniso=one_bad)),
        "mono_two_flat": s3.build(_monoclinic(aniso=two_bad)),
    }


def _round(value):
    """Twelve significant figures: the replay compares at 1e-9, and the file
    is a third the size of one written at seventeen."""
    if isinstance(value, float):
        return float(f"{value:.12g}")
    if isinstance(value, list):
        return [_round(v) for v in value]
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    return value


def _cases(payloads: dict[str, dict]) -> tuple[list, list]:
    scenes, shown = [], []
    for name, geo in payloads.items():
        species = sorted({site["species"] for site in geo["sites"]})
        default = sc.shown_polyhedra(geo, True)
        everything = list(range(len(geo["polyhedra"])))
        formulas = sorted({sc.polyhedron_formula(geo, p) for p in geo["polyhedra"]})
        options = [
            {"mode": "ball", "polyhedra": default},
            {"mode": "ball", "polyhedra": everything},
            {"mode": "ellipsoid", "exaggeration": 1.7, "cell": "#3a7d44"},
            {"mode": "ball", "hidden": species[:1], "showBoundary": False,
             "polyhedra": sc.shown_polyhedra(geo, True, hidden=species[:1],
                                             show_boundary=False)},
        ]
        # rutile draws every polyhedron by default, and a repeated case is
        # 40 kB that tests nothing new
        options = [o for k, o in enumerate(options) if o not in options[:k]]
        for opt in options:
            scene = sc.build_scene(
                geo, opt["mode"], hidden=opt.get("hidden", ()),
                show_boundary=opt.get("showBoundary", True),
                exaggeration=opt.get("exaggeration", 1.0),
                polyhedra=opt.get("polyhedra", ()), cell=opt.get("cell", sc.CELL_INK))
            scenes.append({"payload": name, "options": opt, "scene": scene})
        toggles = [{"on": True}, {"on": False},
                   {"on": True, "hidden": species[:1]},
                   {"on": True, "showBoundary": False}]
        if formulas:
            toggles.append({"on": True, "formulas": {formulas[0]: not
                            any(p["drawn_by_default"] for p in geo["polyhedra"]
                                if sc.polyhedron_formula(geo, p) == formulas[0])}})
        for t in toggles:
            shown.append({"payload": name, **t, "shown": sc.shown_polyhedra(
                geo, t["on"], t.get("formulas"), t.get("hidden", ()),
                t.get("showBoundary", True))})
    return scenes, shown


def _views(payloads: dict[str, dict]) -> dict:
    pairs = [((1, 0, 0), (0, 0, 1)), ((0, 0, 1), (0, 1, 0)), ((1, 2, 3), (0, 0, 1)),
             ((-2, 0.5, 1), (1, 1, 0)), ((0, 0, 1), (0, 0, 1))]   # up ∥ eye: degenerate
    return {
        "look_from": [{"eye": list(e), "up": list(u), "rotation": sc.look_from(e, u)}
                      for e, u in pairs],
        "opening": sc.opening_view(),
        "axis": [{"payload": name, "axis": k, "rotation": sc.axis_view(geo, k)}
                 for name, geo in payloads.items() for k in range(3)],
    }


def _corpus() -> dict:
    payloads = _payloads()
    scenes, shown = _cases(payloads)
    return _round({
        "note": ("Written by tests/test_render_structure.py from "
                 "rietx.viz.figure3d.scene; replayed by "
                 "gui/src/lib/structure3d.test.ts.  Do not edit."),
        "constants": {
            "LOOK": sc.LOOK, "STICK_RADIUS": sc.STICK_RADIUS,
            "STICK_OF_SEMI_AXIS": sc.STICK_OF_SEMI_AXIS, "STICK_FLOOR": sc.STICK_FLOOR,
            "FLAT_AXIS": sc.FLAT_AXIS, "CELL_WIDTH_PX": sc.CELL_WIDTH_PX,
            "EDGE_WIDTH_PX": sc.EDGE_WIDTH_PX, "POLY_ALPHA": sc.POLY_ALPHA,
        },
        "payloads": payloads,
        "scenes": scenes,
        "shown": shown,
        "views": _views(payloads),
    })


def _dump(corpus: dict) -> str:
    return json.dumps(corpus, separators=(",", ":"), ensure_ascii=False) + "\n"


def test_the_committed_scene_corpus_is_current():
    """Regenerate and compare, the fnmatch corpus's rule one artefact over."""
    text = _dump(_corpus())
    if not FIXTURE.is_file() or FIXTURE.read_text(encoding="utf-8") != text:
        FIXTURE.write_text(text, encoding="utf-8")
        raise AssertionError(
            f"{FIXTURE.relative_to(DATA.parent.parent)} was stale and has been "
            "rewritten; commit it, and run `npm --prefix gui test` (the vitest "
            "replay reads the committed copy, and node never runs this suite)")


def test_the_corpus_reaches_every_rule_it_exists_for():
    """A corpus that never hides a species or floors an axis proves nothing
    about the code that does."""
    corpus = json.loads(FIXTURE.read_text(encoding="utf-8"))
    scenes = [c["scene"] for c in corpus["scenes"]]
    payloads = corpus["payloads"]
    assert any(a.get("vertex_only") for g in payloads.values() for a in g["atoms"])
    assert any(a["npd"] for g in payloads.values() for a in g["atoms"])
    # a floored axis is FLAT_AXIS long, in both of drawable's branches
    lengths = [sum(a["shape"][3 * r + c] ** 2 for r in range(3)) ** 0.5
               for s in scenes for a in s["atoms"] for c in range(3)]
    assert any(abs(v - sc.FLAT_AXIS) < 1e-12 for v in lengths)
    assert any(s["faces"] for s in scenes)
    assert any(a["rings"] for s in scenes for a in s["atoms"])
    shown = [c["shown"] for c in corpus["shown"] if c["on"]]
    whole = [len(corpus["payloads"][c["payload"]]["polyhedra"]) for c in corpus["shown"]
             if c["on"]]
    assert any(0 < len(s) < n for s, n in zip(shown, whole))   # a strict subset
    assert any(len(s) == n > 0 for s, n in zip(shown, whole))
    assert any(not s and n for s, n in zip(shown, whole))       # all switched off


@pytest.mark.parametrize("axis, up", [(0, 2), (1, 2), (2, 1)])
def test_an_axis_view_keeps_c_up_unless_it_looks_down_c(axis, up):
    """D12's convention: c up down a and down b, b up down c."""
    geo = _payloads()["mono_one_flat"]
    rotation = sc.axis_view(geo, axis)
    lattice = geo["lattice"]
    screen_y = rotation[3:6]
    toward = rotation[6:9]
    norm = sum(v * v for v in lattice[axis]) ** 0.5
    assert all(abs(toward[i] - lattice[axis][i] / norm) < 1e-12 for i in range(3))
    assert sum(screen_y[i] * lattice[up][i] for i in range(3)) > 0
