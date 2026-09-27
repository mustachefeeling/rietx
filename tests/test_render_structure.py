"""WP-1470 — a structure figure drawn in Python, without a browser.

Two halves.  The **scene corpus** holds the Python copy of the structure
viewer's scene rules equal to the TypeScript original: this module writes
``tests/data/gui/scene_cases.json`` from :mod:`rietx.viz.figure3d.scene` and
``gui/src/lib/structure3d.test.ts`` replays every case against ``buildScene``,
``shownPolyhedra``, ``lookFrom`` and ``axisView``.  The fixture is committed
because vitest runs where this package is not installed, so the check here is
``test_gui_fnmatch.py``'s one step removed: replay the rules over the committed
payloads, compare, and fail naming the file.
"""

from __future__ import annotations

import functools
import json
import struct
import zlib
from pathlib import Path

import numpy as np
import pytest

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3
from rietx.model import compiled
from rietx.schemas.structure import AnisoU, Atom, Cell, Phase, Structure
from rietx.viz import render_structure
from rietx.viz.figure3d import raster, views
from rietx.viz.figure3d import scene as sc
from rietx.viz.figure3d.render import _png
from rietx.viz.theme import TOKENS

DATA = Path(__file__).parent / "data"
FIXTURE = DATA / "gui" / "scene_cases.json"
OUTPUT = Path(__file__).parent / "output" / "figure3d"


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


@functools.cache
def _payloads() -> dict[str, dict]:
    """Four payloads, chosen for the rules each one reaches, and small.
    Built once a process and shared, so a caller reads them and never edits.

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


def _corpus(payloads: dict[str, dict] | None = None) -> dict:
    """The corpus over ``payloads``, or over fresh ones rounded as the file
    holds them, so the scenes written are the scenes the file's payloads give."""
    payloads = _round(_payloads()) if payloads is None else payloads
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


#: A tenth of the replay's bar: ``structure3d.test.ts`` compares at 1e-9 of
#: max(1, |value|).  The committed file sits 5.5e-12 from its own replay, which
#: is the rounding of its payloads to twelve figures.
DRIFT = 1e-10


def _fields(value, where: str = "") -> set[str]:
    """Every field name ``value`` carries, by path, with a list's elements pooled."""
    if isinstance(value, dict):
        return {p for k, v in value.items()
                for p in {f"{where}.{k}"} | _fields(v, f"{where}.{k}")}
    if isinstance(value, list):
        return {p for v in value for p in _fields(v, f"{where}[]")}
    return set()


def _drift(ours, theirs, where: str = "corpus") -> str | None:
    """The first place two corpora differ, where floats within :data:`DRIFT` agree."""
    if isinstance(theirs, float) and isinstance(ours, float):
        if abs(ours - theirs) <= DRIFT * max(1.0, abs(theirs)):
            return None
    elif isinstance(theirs, list) and isinstance(ours, list) and len(ours) == len(theirs):
        return next(filter(None, (_drift(a, b, f"{where}[{k}]")
                                  for k, (a, b) in enumerate(zip(ours, theirs)))), None)
    elif isinstance(theirs, dict) and isinstance(ours, dict) and ours.keys() == theirs.keys():
        return next(filter(None, (_drift(ours[k], v, f"{where}.{k}")
                                  for k, v in theirs.items())), None)
    elif ours == theirs:
        return None
    return f"{where}: {str(ours)[:60]} against {str(theirs)[:60]}"


def test_the_committed_scene_corpus_is_current():
    """The rules replayed over the committed payloads, never over rebuilt ones.

    The payloads are the corpus's inputs.  ``structure3d.build`` breaks ties in
    distance on the last bit, and rutile's octahedron is all ties, so its vertex
    and face order moves with the platform while the picture does not.  Rebuilt,
    the file matched on the Mac that wrote it and failed on every Linux job.
    Over a fixed payload the rules are pure python.  A new case or a new payload
    field still rewrites the file, through the field names, which do not move.
    """
    committed = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.is_file() else {}
    payloads = committed.get("payloads", {})
    if _fields(payloads) != _fields(_payloads()):
        where = "corpus.payloads: a case or a field was added or removed"
        rewrite = _corpus()
    else:
        # a rule moved and the payloads did not: keep the committed ones, or
        # the rewrite carries this platform's vertex order as well
        rewrite = _corpus(payloads)
        where = _drift(json.loads(_dump(rewrite)), committed)
    if where:
        FIXTURE.write_text(_dump(rewrite), encoding="utf-8")
        raise AssertionError(
            f"{FIXTURE.relative_to(DATA.parent.parent)} was stale at {where}, and has "
            "been rewritten; commit it, and run `npm --prefix gui test` (the vitest "
            "replay reads the committed copy, and node never runs this suite)")


def test_the_corpus_reaches_every_rule_it_exists_for():
    """A corpus that never hides a species or floors an axis proves nothing
    about the code that does."""
    corpus = json.loads(FIXTURE.read_text(encoding="utf-8"))
    scenes = [c["scene"] for c in corpus["scenes"]]
    payloads = corpus["payloads"]
    assert any(a.get("vertex_only") for g in payloads.values() for a in g["atoms"])
    assert any(a["npd"] for g in payloads.values() for a in g["atoms"])
    # a floored axis is FLAT_AXIS long, in both of drawable's branches: one
    # flat axis (mono_one_flat) and two (mono_two_flat)
    floored = {case["payload"] for case in corpus["scenes"] for a in case["scene"]["atoms"]
               for c in range(3)
               if abs(sum(a["shape"][3 * r + c] ** 2 for r in range(3)) ** 0.5
                      - sc.FLAT_AXIS) < 1e-12}
    assert {"mono_one_flat", "mono_two_flat"} <= floored
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


# ----------------------------------------------------------------------
# the renderer
# ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def nac():
    return structure_from_cif(str(DATA / "cod_1000236.cif"), aniso=True)


def _save(fig, name):
    """Every picture a test draws is written for looking at (tests/CLAUDE.md)."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _png(OUTPUT / f"{name}.png", fig.image, None)


def _one_atom(payload: dict) -> dict:
    """A payload's first atom alone: no bonds, no frame, no polyhedra.  A dict
    edited and handed back is the customisation route D10 promises."""
    geo = dict(payload)
    geo["atoms"] = [dict(payload["atoms"][0], boundary=False)]
    geo["bonds"], geo["polyhedra"], geo["edges"] = [], [], []
    return geo


def _general_ellipsoid() -> dict:
    return s3.build(_monoclinic(
        aniso=AnisoU.from_values([0.03, 0.012, 0.02, 0.004, -0.003, 0.006])))


@pytest.mark.skipif(not compiled.available(), reason="numba does not import here")
@pytest.mark.parametrize("kw", [
    {"mode": "ball", "polyhedra": True, "atom_labels": True},
    {"mode": "ellipsoid", "background": None, "outline": True},
])
def test_the_two_paths_draw_the_same_bits_in_any_banding(nac, kw, monkeypatch):
    """The kernel and its numpy oracle call no library function, so the bar
    between them is the bit (D1), and a band boundary moves nothing: the
    outline reads across one through its halo."""
    was = compiled.set_enabled(True)
    try:
        whole = render_structure(nac, size=240, **kw).image
        monkeypatch.setattr(raster, "BAND_SAMPLES", 2000)      # dozens of bands
        banded = render_structure(nac, size=240, **kw).image
        compiled.set_enabled(False)
        oracle = render_structure(nac, size=240, **kw).image
    finally:
        compiled.set_enabled(was)
    assert np.array_equal(whole, banded)
    assert np.array_equal(whole, oracle)
    assert (whole[..., 3] > 0).sum() > 5000


def test_the_numpy_path_is_what_runs_with_the_tier_switched_off(nac):
    was = compiled.set_enabled(False)
    try:
        fig = render_structure(nac, size=160)
    finally:
        compiled.set_enabled(was)
    assert (fig.image[..., 3] > 0).sum() > 1000


def test_two_renders_are_identical(nac):
    a = render_structure(nac, size=200, mode="ellipsoid").image
    b = render_structure(nac, size=200, mode="ellipsoid").image
    assert np.array_equal(a, b)


def test_a_balls_silhouette_is_its_radius_in_pixels():
    geo = _one_atom(_general_ellipsoid())
    fig = render_structure(geo, size=400, axis_labels=False, background=None)
    _save(fig, "one_ball")
    r = geo["ball_fraction"] * geo["sites"][0]["radius"] * fig.pixels_per_angstrom
    area = (fig.image[..., 3] >= 128).sum()
    assert abs(np.sqrt(area / np.pi) - r) < 0.5


def test_an_ellipsoids_silhouette_is_the_exact_projected_ellipse():
    """Its half-extents are the norms of the first two rows of R·k·T, and its
    area π·√det of that 2 × 3 block times its transpose."""
    geo = _one_atom(_general_ellipsoid())
    fig = render_structure(geo, mode="ellipsoid", view=[1, 2, 3], size=400,
                           axis_labels=False, background=None)
    _save(fig, "one_ellipsoid")
    M = np.asarray(fig.rotation) @ (np.asarray(geo["atoms"][0]["ellipsoid"]) * geo["scale"])
    ppa = fig.pixels_per_angstrom
    inside = fig.image[..., 3] >= 128
    ys, xs = np.nonzero(inside)
    assert abs((xs.max() - xs.min() + 1) - 2 * np.linalg.norm(M[0]) * ppa) < 1.5
    assert abs((ys.max() - ys.min() + 1) - 2 * np.linalg.norm(M[1]) * ppa) < 1.5
    A = M[:2]
    assert abs(inside.sum() / (np.pi * np.sqrt(np.linalg.det(A @ A.T)) * ppa ** 2) - 1) < 0.01


def test_a_cubic_cell_seen_down_c_is_a_square():
    lab6 = structure_from_cif(str(DATA / "cod_1000055.cif"))
    fig = render_structure(lab6, view="c", hidden=["La", "B"], axis_labels=False,
                           size=300, background=None)
    _save(fig, "lab6_frame_down_c")
    ys, xs = np.nonzero(fig.image[..., 3] > 0)
    assert abs((xs.max() - xs.min()) - (ys.max() - ys.min())) <= 1
    h, w = fig.image.shape[:2]
    assert fig.image[h // 2, w // 2, 3] == 0            # a frame, not a filled square


def test_a_transparent_background_is_straight_alpha_with_no_fringe(nac):
    """Alpha is zero outside the structure, and the transparent picture
    composited over white is the white picture, to a level (D7)."""
    clear = render_structure(nac, size=240, background=None, polyhedra=True).image
    white = render_structure(nac, size=240, polyhedra=True).image
    assert clear[0, 0, 3] == 0 and clear[-1, -1, 3] == 0
    assert (clear[..., :3][clear[..., 3] == 0] == 0).all()
    a = clear[..., 3:].astype(float) / 255
    over = clear[..., :3].astype(float) * a + 255 * (1 - a)
    # the straight colour and the alpha each round to a level, and the white
    # picture rounds once more
    assert np.abs(over - white[..., :3]).max() <= 1.5
    assert (white[..., 3] == 255).all()


def test_a_polyhedron_leaves_a_translucent_pixel():
    fig = render_structure(s3.build(_rutile()), hidden=["O"], size=300, background=None,
                           axis_labels=False)
    _save(fig, "rutile_faces")
    # a pixel inside a closed polyhedron sees a back face and a front face
    alpha = fig.image[..., 3].astype(int)
    level = round((1 - (1 - sc.POLY_ALPHA) ** 2) * 255)
    assert ((alpha > level - 3) & (alpha < level + 3)).sum() > 500


def test_a_non_positive_tensor_draws_no_nan():
    geo = s3.build(_monoclinic(aniso=AnisoU.from_values([0.02, -0.01, -0.01, 0.0, 0.0, 0.0])))
    was = compiled.set_enabled(False)
    try:
        with np.errstate(invalid="raise", divide="raise"):
            fig = render_structure(geo, mode="ellipsoid", size=200, background=None)
    finally:
        compiled.set_enabled(was)
    assert (fig.image[..., 3] > 0).sum() > 200


def test_the_png_carries_its_chunks_and_the_array(tmp_path, nac):
    fig = render_structure(nac, size=120, background=None, path=tmp_path / "nac.png", dpi=300)
    data = (tmp_path / "nac.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    chunks, at, order = {}, 8, []
    while at < len(data):
        n = struct.unpack(">I", data[at:at + 4])[0]
        kind = data[at + 4:at + 8]
        body = data[at + 8:at + 8 + n]
        # a wrong CRC is a file every decoder refuses
        assert struct.unpack(">I", data[at + 8 + n:at + 12 + n])[0] \
            == zlib.crc32(kind + body) & 0xFFFFFFFF, kind
        chunks[kind] = chunks.get(kind, b"") + body
        order.append(kind)
        at += 12 + n
    assert order[0] == b"IHDR" and order[-1] == b"IEND"
    w, h, depth, colour = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    assert (w, h, depth, colour) == (fig.image.shape[1], fig.image.shape[0], 8, 6)
    assert chunks[b"sRGB"] == b"\x00"
    assert struct.unpack(">IIB", chunks[b"pHYs"]) == (11811, 11811, 1)   # 300 dpi
    rows = np.frombuffer(zlib.decompress(chunks[b"IDAT"]), dtype=np.uint8).reshape(h, 1 + 4 * w)
    assert (rows[:, 0] == 0).all()
    assert np.array_equal(rows[:, 1:].reshape(h, w, 4), fig.image)
    assert fig.path == str(tmp_path / "nac.png")


def test_a_jpeg_is_refused(tmp_path, nac):
    with pytest.raises(ValueError, match="PNG only"):
        render_structure(nac, path=tmp_path / "nac.jpg")


def test_a_switch_that_switches_nothing_is_refused(nac):
    """A formula the phase lacks, like ``hidden=``'s unknown species, would
    look like success; so would a dpi of zero in the file."""
    with pytest.raises(ValueError, match="AlF₆"):
        render_structure(nac, size=100, polyhedra={"AlF6": False})
    with pytest.raises(ValueError, match="dpi"):
        render_structure(nac, size=100, dpi=0)


# ----------------------------------------------------------------------
# views (D12)
# ----------------------------------------------------------------------

def test_the_rotation_drawn_round_trips(nac):
    fig = render_structure(nac, view=[1, 2, 0], turn="20y,-10x", size=160)
    again = render_structure(nac, view=fig.rotation, size=160)
    assert np.array_equal(fig.image, again.image)


def test_down_001_and_the_001_normal_on_a_cubic_cell_are_the_c_view(nac):
    """Compared as rotations: NAC's lattice carries 6e-16 Å off the diagonal,
    so c* leans 6e-17 from c and a bit-identical image would be luck."""
    c = render_structure(nac, view="c", size=160).rotation
    for view in ([0, 0, 1], {"hkl": (0, 0, 1)}):
        assert np.allclose(render_structure(nac, view=view, size=160).rotation, c,
                           rtol=0, atol=1e-12)


def test_a_turn_is_ases_rotation_about_the_screen():
    """'90x' tips the top toward the viewer: down c with b up becomes b toward
    the viewer with c down (``ase.utils.rotate``'s signs)."""
    geo = _payloads()["rutile"]
    R = views.resolve(geo, "c", turn="90x")
    b = np.asarray(geo["lattice"][1]) / np.linalg.norm(geo["lattice"][1])
    c = np.asarray(geo["lattice"][2]) / np.linalg.norm(geo["lattice"][2])
    assert np.allclose(R @ b, [0, 0, 1], atol=1e-12)
    assert np.allclose(R @ c, [0, -1, 0], atol=1e-12)
    assert not np.allclose(views.ase_rotation("50x,40z"), views.ase_rotation("40z,50x"))


def test_the_default_up_is_c_and_never_the_view():
    geo = _payloads()["mono_one_flat"]
    R = views.resolve(geo, [1, 1, 0])
    assert R[1] @ np.asarray(geo["lattice"][2]) > 0
    R = views.resolve(geo, [0.1, 0, 1])                   # nearest c: b up
    assert R[1] @ np.asarray(geo["lattice"][1]) > 0
    with pytest.raises(ValueError, match="parallel"):
        views.resolve(geo, "a", up=[2, 0, 0])
    with pytest.raises(ValueError, match="view= takes"):
        views.resolve(geo, "down the middle")
    with pytest.raises(ValueError, match="rotation"):
        views.resolve(geo, [[1, 0, 0], [0, 1, 0], [0, 0, -1]])


# ----------------------------------------------------------------------
# output and options
# ----------------------------------------------------------------------

def test_size_is_the_long_side_or_the_frame(nac):
    assert max(render_structure(nac, size=300).image.shape[:2]) == 300
    assert render_structure(nac, size=(320, 180)).image.shape[:2] == (180, 320)
    with pytest.raises(ValueError, match="supersample"):
        render_structure(nac, supersample=5)
    with pytest.raises(ValueError, match="mode"):
        render_structure(nac, mode="wireframe")


def test_the_anchors_say_where_each_atom_and_letter_landed(nac):
    fig = render_structure(_one_atom(_general_ellipsoid()), size=300, background=None)
    (atom,) = fig.atoms
    assert fig.image[round(atom["y"]), round(atom["x"]), 3] == 255
    fig = render_structure(nac, size=300)
    assert [letter["text"] for letter in fig.letters] == ["a", "b", "c"]
    h, w = fig.image.shape[:2]
    assert all(0 <= t["x"] < w and 0 <= t["y"] < h for t in fig.letters)


def test_the_options_reach_the_picture(nac):
    base = render_structure(nac, size=200)
    no_na = render_structure(nac, size=200, hidden=["Na"]).atoms
    assert no_na and not any(a["species"].startswith("Na") for a in no_na)
    assert render_structure(nac, size=200, hidden="Na1+").atoms == no_na
    with pytest.raises(ValueError, match="no such species"):
        render_structure(nac, size=200, hidden=["Nb"])
    assert not any(a["boundary"] for a in render_structure(nac, size=200,
                                                           boundary=False).atoms)
    off = render_structure(nac, size=200, polyhedra=False)
    assert not np.array_equal(off.image, base.image)
    assert np.array_equal(render_structure(nac, size=200, polyhedra={"AlF₆": False}).image,
                          off.image)
    assert tuple(render_structure(nac, size=200, background="black").image[0, 0]) \
        == (0, 0, 0, 255)
    outlined = render_structure(nac, size=200, outline=True)
    assert (outlined.image[..., :3].sum(-1) < base.image[..., :3].sum(-1)).sum() > 500
    # the outline marks surfaces: the frame keeps its accent (it once went black)
    accent = np.asarray(sc.rgb(TOKENS["light"]["--accent"])) * 255

    def framed(img):
        return (np.abs(img[..., :3].astype(float) - accent).max(-1) < 10).sum()

    assert framed(outlined.image) > 0.9 * framed(base.image) > 50
    # a larger surface covers more of the frame, whether by probability or by
    # a drawing scale
    ink = [(render_structure(nac, size=200, mode="ellipsoid", axis_labels=False,
                             background=None, **kw).image[..., 3] > 0).sum()
           for kw in ({}, {"probability": 0.9}, {"exaggeration": 1.5})]
    assert ink[1] > ink[0] and ink[2] > ink[0]
    with pytest.raises(ValueError, match="build the geometry"):
        render_structure(s3.build(nac), probability=0.9)


# ----------------------------------------------------------------------
# letters (D8)
# ----------------------------------------------------------------------

def test_the_font_ships_with_its_acknowledgement():
    from importlib import resources

    doc = json.loads(resources.files("rietx.data").joinpath("hershey_simplex.json")
                     .read_text(encoding="utf-8"))
    assert "Hershey" in doc["acknowledgement"] and "NTIS" in doc["licence"]
    assert len(doc["glyphs"]) == 95


def test_the_letters_are_drawn_in_the_accent_at_their_anchors(nac):
    fig = render_structure(nac, size=600)
    accent = np.asarray(sc.rgb(TOKENS["light"]["--accent"])) * 255
    for letter in fig.letters:
        x, y = round(letter["x"]), round(letter["y"])
        # a negative start would wrap to the far edge
        patch = fig.image[max(y - 8, 0):y + 9, max(x - 8, 0):x + 9, :3]
        patch = patch.reshape(-1, 3).astype(float)
        assert (np.abs(patch - accent).max(axis=1) < 12).any(), letter
    bare = render_structure(nac, size=600, axis_labels=False)
    assert bare.letters == [] and not np.array_equal(bare.image, fig.image)
    # the labels widen the frame to hold them, so count their ink rather than
    # differencing two frames
    labelled = render_structure(nac, size=600, atom_labels=True)
    ink = np.asarray(sc.rgb(TOKENS["light"]["--fg"])) * 255

    def inked(image):
        return int((np.abs(image[..., :3].astype(float) - ink).max(axis=-1) < 12).sum())

    assert inked(labelled.image) - inked(fig.image) > 1000
    _save(labelled, "nac_atom_labels")
