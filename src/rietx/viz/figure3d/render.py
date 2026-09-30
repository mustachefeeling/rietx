"""``render_structure``: the structure viewer's picture as an array (WP-1470).

The geometry is the GUI's (``rietx.gui.structure3d.build``), the scene rules
are the GUI's (:mod:`.scene`, held equal by a corpus), and the drawing is the
GUI's renderer solved on the CPU (:mod:`.raster`).  What this module adds is
what a browser supplied: a view named in crystallographic terms
(:mod:`.views`), a frame fitted to what is drawn, the letters (:mod:`.glyphs`),
and a PNG.

**Everything the GUI sizes in CSS pixels is scaled as the GUI scales an
export** (``gl3d.ts``, device over CSS width): a line of 2 CSS px is
``2 × long side / CANVAS_CSS_PX`` image pixels, so a 3000 px figure for print
has lines three times as wide as a 1000 px one and the same proportions.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..theme import TOKENS
from . import cut, glyphs, raster, views
from . import report as rp
from . import scene as sc
from .report import FigureReport

#: The CSS width the GUI's pixel sizes are drawn against: an image whose long
#: side is this many pixels has the GUI's on-screen line widths and letters.
#: It is the structure canvas's long side in the GUI's default layout at a
#: 1400 × 900 window (measured 507 × 300 by ``test_structure3d_browser.py``),
#: so a render at ``size=N`` matches the GUI's own export at long side N from
#: that window.  The canvas follows the window, so this is a choice of window.
CANVAS_CSS_PX = 507.0
#: The fitted content leaves this fraction of the frame's width and height on
#: each side, ChimeraX ``view``'s default ``pad``.
FIT_PAD = 0.05
#: The GUI's a, b, c: ``--text-sm``, in CSS px.
LETTER_EM_CSS = 11.5
#: An outline is this wide, in CSS px, when ``outline=True`` (D9).
OUTLINE_CSS = 1.0
#: The default long side: an agent looking at its own picture.
DEFAULT_SIZE = 1000
MAX_SUPERSAMPLE = 4
MODES = ("ball", "ellipsoid")


@dataclass(frozen=True)
class StructureFigure:
    """What :func:`render_structure` drew.

    ``image`` is ``height × width × 4`` ``uint8``, straight alpha;
    ``np.asarray(figure)`` and ``plt.imshow(figure)`` both take it.
    ``rotation`` is the view drawn, rows the screen's right, up and toward the
    viewer in the structure's Cartesian Å: pass it back as ``view=`` for the
    same picture.  ``atoms`` has one entry per atom drawn, ``letters`` one per
    a, b, c: where each landed, in pixels from the top-left corner, so a caller
    can annotate without re-projecting.  ``path`` is the PNG written, if any.
    ``palette`` is each site label drawn and the colour it is drawn in, as
    ``#rrggbb`` before any dimming of the images outside the cell, for a legend
    drawn beside the figure.  A site recoloured in part
    (:func:`~rietx.viz.recolour`) appears again as ``"<label> (recoloured)"``.

    ``report`` is the numbers a look would give (:class:`~.report.FigureReport`).
    ``candidates`` is empty unless ``view="auto"``, and then the best few views
    the search ranked, each a ``view`` to pass back, the ``hidden`` share and
    the ``empty`` share it read at 256 px from atoms and bonds alone; the first
    is the one drawn.  ``recipe`` is the call that draws this picture again:
    ``render_structure(geometry, **figure.recipe)`` gives ``image`` bit for bit.
    It holds the keyword arguments as passed, JSON-serialisable, with ``view``
    the rotation drawn and ``up`` and ``turn`` folded into it.  The geometry is
    the caller's, and so are ``probability`` and ``bond_tolerance``, which build
    it, and ``path``.
    """
    image: np.ndarray
    rotation: list[list[float]]
    pixels_per_angstrom: float
    atoms: list[dict]
    letters: list[dict]
    path: str | None = None
    palette: dict[str, str] = field(default_factory=dict)
    report: FigureReport | None = None
    candidates: list[dict] = field(default_factory=list)
    recipe: dict = field(default_factory=dict)

    def __array__(self, dtype=None, copy=None):
        image = self.image if dtype is None else self.image.astype(dtype, copy=False)
        # numpy 2 trusts copy=True to have copied, so np.array(figure) must
        # not hand out the figure's own buffer
        return image.copy() if copy else image


def _colour(value) -> tuple[float, float, float] | None:
    if value is None:
        return None
    if isinstance(value, str):
        hex_ = cut.NAMED_COLOURS.get(value.lower(), value)
        if not sc._HEX.match(hex_):
            raise ValueError(f"background {value!r}: give 'white', 'black', "
                             "'#rrggbb', three channels in 0..1, or None")
        return tuple(sc.rgb(hex_))
    rgb = tuple(float(v) for v in value)
    if len(rgb) != 3 or not all(0.0 <= v <= 1.0 for v in rgb):
        raise ValueError(f"background {value!r}: three channels, each in 0..1")
    return rgb


def _species(geometry: Mapping, names) -> list[str]:
    """The species ``hidden=`` names: a species as the legend spells it
    (``"Na1+"``), or an element, which takes all of its species.  A name the
    phase does not have is refused, since hiding nothing looks like success."""
    if isinstance(names, str):
        names = [names]
    sites = geometry["sites"]
    out: list[str] = []
    for name in names:
        match = [s["species"] for s in sites if name in (s["species"], s["element"])]
        if not match:
            have = sorted({s["species"] for s in sites})
            route = ""
            if any(s["label"] == name for s in sites):
                route = (f"; {name!r} is a site label, and one site is left out by a "
                         f"mask: keep(g, ~select(g, label={name!r}))")
            raise ValueError(f"hidden {name!r}: this phase has no such species or "
                             f"element; its species are {have}{route}")
        out += [m for m in match if m not in out]
    return out


def _site_colours(geometry: Mapping) -> Mapping:
    """The geometry with every site colour as ``#rrggbb``, refused otherwise.

    ``scene.rgb`` draws anything else mid-grey, which is the GUI's rule and
    stays.  Here an edited dict is being drawn, and a colour that changes
    nothing on the screen looks like success, as ``hidden=`` has it.
    """
    colours = []
    for k, site in enumerate(geometry["sites"]):
        try:
            colours.append(cut.site_colour(site["color"]))
        except ValueError as e:
            raise ValueError(f"sites[{k}] ({site['label']}): {e}") from None
    if colours == [s["color"] for s in geometry["sites"]]:
        return geometry
    return {**geometry, "sites": [{**s, "color": c}
                                  for s, c in zip(geometry["sites"], colours)]}


def _palette(geometry: Mapping, scene: dict) -> dict[str, str]:
    drawn = {geometry["atoms"][a["index"]]["site"] for a in scene["atoms"]}
    out: dict[str, str] = {}
    for k in sorted(drawn):
        site = geometry["sites"][k]
        name = base = site["label"]
        n = 1
        while name in out and out[name] != site["color"]:
            n += 1
            name = f"{base} (recoloured)" if n == 2 else f"{base} (recoloured {n - 1})"
        out.setdefault(name, site["color"])
    return out


def _formulas(geometry: Mapping, polyhedra: Mapping) -> dict:
    """``polyhedra=`` as a formula switch, refused when it names a formula the
    phase has no polyhedron for: switching nothing looks like success, as
    ``hidden=`` has it, and ``"AlF6"`` for ``"AlF₆"`` is the easy slip."""
    have = {sc.polyhedron_formula(geometry, p) for p in geometry["polyhedra"]}
    unknown = sorted(set(polyhedra) - have)
    if unknown:
        raise ValueError(f"polyhedra {unknown}: this phase has no such polyhedron; "
                         f"its formulas are {sorted(have)}")
    return dict(polyhedra)


def _label_reach(scene: dict, geometry: Mapping, R: np.ndarray):
    """Where the atom labels are anchored, in Å, and how far past the anchor
    the widest one reaches, in CSS px: a label sits up and to the right of its
    atom (:func:`text_strokes`), outside the atom's own box."""
    points, reach = [], 0.0
    for a in scene["atoms"]:
        record = geometry["atoms"][a["index"]]
        if record["boundary"]:
            continue
        m = R @ np.asarray(a["shape"], dtype=np.float64).reshape(3, 3)
        r = max(float(np.linalg.norm(m[0])), float(np.linalg.norm(m[1])))
        c = R.T @ (R @ np.asarray(a["pos"], dtype=np.float64) + [0.72 * r, 0.72 * r, 0.0])
        points.append(c)
        text = geometry["sites"][record["site"]]["label"]
        reach = max(reach, glyphs.width(text, LETTER_EM_CSS))
    return points, reach


def _extent(scene: dict, R: np.ndarray, with_labels: bool, extra=()):
    """The drawn content's box in view coordinates, Å: (x0, x1, y0, y1).
    ``extra`` is further points, in the structure's Å, the box must hold."""
    xs, ys = [], []
    for a in scene["atoms"]:
        c = R @ np.asarray(a["pos"], dtype=np.float64)
        m = R @ np.asarray(a["shape"], dtype=np.float64).reshape(3, 3)
        hx, hy = float(np.linalg.norm(m[0])), float(np.linalg.norm(m[1]))
        xs += [c[0] - hx, c[0] + hx]
        ys += [c[1] - hy, c[1] + hy]
    for h in scene["halves"]:
        for p in (h["from"], h["to"]):
            c = R @ np.asarray(p, dtype=np.float64)
            xs += [c[0] - h["radius"], c[0] + h["radius"]]
            ys += [c[1] - h["radius"], c[1] + h["radius"]]
    points = [p for line in scene["lines"] for p in (line["a"], line["b"])]
    points += [f["triangles"][k:k + 3] for f in scene["faces"]
               for k in range(0, len(f["triangles"]), 3)]
    if with_labels:
        points += [label["pos"] for label in scene["labels"]]
    points += list(extra)
    for p in points:
        c = R @ np.asarray(p, dtype=np.float64)
        xs.append(c[0])
        ys.append(c[1])
    if not xs:
        return -1.0, 1.0, -1.0, 1.0
    return min(xs), max(xs), min(ys), max(ys)


def _fit(extent, size, margin_css: float) -> raster.Frame:
    """Scale and place the content box in the frame (D12, D13).

    ``size`` is the long side, the other following the content, or
    ``(width, height)`` with the content fitted inside.  ``margin_css`` is
    what pixel-sized things (a line's half-width, a letter) add beyond the
    box, in CSS px.
    """
    x0, x1, y0, y1 = extent
    bw, bh = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    keep = 1.0 - 2.0 * FIT_PAD
    if isinstance(size, (tuple, list)):
        if len(size) != 2:
            raise ValueError(f"size {size!r}: the long side, or (width, height)")
        width, height = (int(v) for v in size)
        if width < 1 or height < 1:
            raise ValueError(f"size {size!r}: both sides at least one pixel")
        scale = max(width, height) / CANVAS_CSS_PX
        m = margin_css * scale
        ppa = min((width * keep - 2 * m) / bw, (height * keep - 2 * m) / bh)
    else:
        long = int(size)
        if long < 16:
            raise ValueError(f"size {size!r}: at least 16 pixels")
        scale = long / CANVAS_CSS_PX
        m = margin_css * scale
        ppa = (long * keep - 2 * m) / max(bw, bh)
        other = max(1, round((min(bw, bh) * ppa + 2 * m) / keep))
        width, height = (long, other) if bw >= bh else (other, long)
    if not ppa > 0:
        raise ValueError(f"size {size!r} leaves no room for the structure")
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return raster.Frame(width=width, height=height, x0=cx - width / (2 * ppa),
                        y0=cy + height / (2 * ppa), ppa=ppa, px_scale=scale)


def gui_frame(scene: dict, R, width: int, height: int, css_width: float) -> raster.Frame:
    """The GUI's framing for one canvas: ``pixelsPerAngstrom`` at zoom 1, no
    pan, centred on the scene's centre.  The browser parity row draws with it,
    because the fitted frame is tighter and would otherwise be what it
    measured."""
    R = np.asarray(R, dtype=np.float64)
    ppa = min(width, height) / (2 * scene["radius"])
    c = R @ np.asarray(scene["center"], dtype=np.float64)
    return raster.Frame(width=width, height=height, x0=c[0] - width / (2 * ppa),
                        y0=c[1] + height / (2 * ppa), ppa=ppa, px_scale=width / css_width)


def _labels(scene: dict, geometry: Mapping, R, frame: raster.Frame, *,
            axis_labels: bool, atom_labels: bool):
    """Every string drawn, as ``(text, x, y, is_axis, half_height)`` centred on
    image pixel ``(x, y)``: a, b, c at their anchors, and each site label up and
    to the right of its atom, clear of it.  ``half_height`` is in pixels."""
    R = np.asarray(R, dtype=np.float64)
    em = LETTER_EM_CSS * frame.px_scale
    half = glyphs.HALF_BOX_UNITS * em / glyphs.EM_UNITS

    def at(p):
        c = R @ np.asarray(p, dtype=np.float64)
        return (c[0] - frame.x0) * frame.ppa, (frame.y0 - c[1]) * frame.ppa

    out = []
    if axis_labels:
        for label in scene["labels"]:
            x, y = at(label["pos"])
            out.append((label["text"], x, y, True, half))
    if atom_labels:
        for a in scene["atoms"]:
            if geometry["atoms"][a["index"]]["boundary"]:
                continue
            text = geometry["sites"][geometry["atoms"][a["index"]]["site"]]["label"]
            m = R @ np.asarray(a["shape"], dtype=np.float64).reshape(3, 3)
            r = max(float(np.linalg.norm(m[0])), float(np.linalg.norm(m[1]))) * frame.ppa
            x, y = at(a["pos"])
            # up and to the right of the atom, clear of it
            x += 0.72 * r + glyphs.width(text, em) / 2
            y -= 0.72 * r
            out.append((text, x, y, False, half))
    return out


def text_strokes(scene: dict, geometry: Mapping, R, frame: raster.Frame, *,
                 axis_labels: bool, atom_labels: bool, accent: str, ink: str):
    """The letters as strokes, and where each landed."""
    em = LETTER_EM_CSS * frame.px_scale
    strokes, letters = [], []
    for text, x, y, is_axis, _ in _labels(scene, geometry, R, frame, axis_labels=axis_labels,
                                          atom_labels=atom_labels):
        strokes += glyphs.strokes(text, x, y, em, sc.rgb(accent if is_axis else ink))
        if is_axis:
            letters.append({"text": text, "x": x, "y": y})
    return strokes, letters


def _label_overlaps(labels, frame: raster.Frame) -> int:
    """Pairs of drawn strings whose boxes intersect, the box being the string's
    advance wide and the font's box tall."""
    em = LETTER_EM_CSS * frame.px_scale
    box = np.array([[x - glyphs.width(t, em) / 2, x + glyphs.width(t, em) / 2, y - h, y + h]
                    for t, x, y, _, h in labels], dtype=np.float64).reshape(-1, 4)
    n, total = len(box), 0
    for start in range(0, n, 512):
        c = box[start:start + 512]
        hit = ((c[:, None, 0] < box[None, :, 1]) & (box[None, :, 0] < c[:, None, 1])
               & (c[:, None, 2] < box[None, :, 3]) & (box[None, :, 2] < c[:, None, 3]))
        later = np.arange(start, start + len(c))[:, None] < np.arange(n)[None, :]
        total += int((hit & later).sum())
    return total


def _dangling(geometry: Mapping, scene: dict, hidden: list[str]) -> int:
    """Bond halves drawn toward an atom that is not, unless ``hidden=`` took
    that atom's species: the half ends in mid-air."""
    if not scene["halves"]:
        return 0
    drawn = {a["index"] for a in scene["atoms"]}
    atoms, bonds = geometry["atoms"], geometry["bonds"]
    if len(drawn) == len(atoms) and not hidden:
        return 0
    far = cut._far(geometry)
    species = {k: s["species"] for k, s in enumerate(geometry["sites"])}
    count = 0
    for h in scene["halves"]:
        bond = bonds[h["bond"]]
        end = int(far[h["bond"]]) if list(bond["a"]) == h["from"] else bond["i"]
        if end not in drawn and species[atoms[end]["site"]] not in hidden:
            count += 1
    return count


def _plain(value):
    """``value`` with tuples and arrays as lists and numpy scalars as numbers,
    which is what JSON keeps of them."""
    if isinstance(value, np.ndarray):
        value = value.tolist()
    elif isinstance(value, np.generic):
        return value.item()
    return [_plain(v) for v in value] if isinstance(value, (tuple, list)) else value


def _empty(image: np.ndarray, bg) -> float:
    """The share of pixels nothing was drawn on: transparent, or the
    background colour exactly."""
    # one 32-bit compare a pixel: the four bytes read as a little-endian word,
    # alpha the top one
    word = np.ascontiguousarray(image).view("<u4")[..., 0]
    if bg is None:
        return float(((word >> 24) == 0).mean())
    r, g, b = (int(v) for v in np.floor(np.asarray(bg) * 255.0 + 0.5))
    return float((word == (r | g << 8 | b << 16 | 255 << 24)).mean())


def _png(path: Path, image: np.ndarray, dpi: float | None) -> None:
    """RGBA, 8 bits, straight alpha as the PNG standard has it, with an
    ``sRGB`` chunk and, when ``dpi`` is given, a ``pHYs`` chunk (D7, D13)."""
    height, width, _ = image.shape

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + image[y].tobytes() for y in range(height))
    parts = [b"\x89PNG\r\n\x1a\n",
             chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
             chunk(b"sRGB", b"\x00")]
    if dpi is not None:
        per_metre = round(float(dpi) / 0.0254)
        parts.append(chunk(b"pHYs", struct.pack(">IIB", per_metre, per_metre, 1)))
    parts += [chunk(b"IDAT", zlib.compress(raw, 6)), chunk(b"IEND", b"")]
    path.write_bytes(b"".join(parts))


def render_structure(structure, phase: int = 0, *, mode: str = "ball", view="opening",
                     up=None, turn: str | None = None, size=DEFAULT_SIZE,
                     supersample: int = 2, probability: float | None = None,
                     bond_tolerance: float | None = None, exaggeration: float = 1.0,
                     hidden=(), boundary: bool = True, polyhedra=None,
                     axis_labels: bool = True, atom_labels: bool = False,
                     outline: bool = False, background="white", path=None,
                     dpi: float | None = None) -> StructureFigure:
    """Draw one phase of a structure as the GUI's structure viewer draws it.

    ``structure`` is a :class:`~rietx.Structure`, or the dict
    ``rietx.gui.structure3d.build`` returns, edited as you like (a colour, a
    radius, a hidden site): the renderer draws what the dict says (D10).

    ``mode`` is ``"ball"`` or ``"ellipsoid"``; ``probability`` the ellipsoids'
    level (default 50 %) and ``exaggeration`` a drawing scale on top of it,
    which is not a probability.  ``bond_tolerance`` is the bond threshold as a
    multiple of rᵢ + rⱼ.  ``hidden`` is species to leave out, with their bond
    halves; ``boundary=False`` leaves out the images outside the cell.
    ``polyhedra`` is ``None`` for the mode's default (on for balls, off for
    ellipsoids), ``True``/``False``, or ``{formula: bool}`` switching formulas
    as the GUI's legend does (``{"AlF₆": False}``).

    ``view``, ``up`` and ``turn`` say where it is seen from
    (:func:`rietx.viz.figure3d.views.resolve`): ``"opening"``, ``"a"``,
    ``"b"``, ``"c"``, ``[u, v, w]``, ``{"hkl": (h, k, l)}`` or a rotation,
    with ``up`` defaulting to c up (b up when looking down c) and ``turn``
    ASE's ``"30y,-15x"``.  Every view is fitted to the frame.  ``"auto"``
    draws the low-index direction (indices to 2, or the opening view) that
    hides the fewest atoms and then leaves the least of the frame empty, and
    returns the runners-up in ``candidates``; the figure's ``report`` says
    what is still hidden, for ``turn=`` to work on.

    ``size`` is the long side in pixels, or ``(width, height)``;
    ``supersample`` the antialiasing, 1 to 4 samples a side.  ``background``
    is ``"white"``, ``"black"``, ``"#rrggbb"``, three channels in 0..1, or
    ``None`` for transparent.  ``outline=True`` inks silhouettes, off by
    default because the GUI draws none.  ``path`` writes a PNG, with ``dpi``
    only in its ``pHYs`` chunk.
    """
    from ...gui import structure3d as s3

    if mode not in MODES:
        raise ValueError(f"mode {mode!r}: give one of {MODES}")
    s = int(supersample)
    if not 1 <= s <= MAX_SUPERSAMPLE:
        raise ValueError(f"supersample {supersample!r}: 1 to {MAX_SUPERSAMPLE}")
    if path is not None and Path(path).suffix.lower() != ".png":
        raise ValueError("render_structure writes PNG only: JPEG's block artifacts "
                         "smear the thin rings and lines a structure figure is read by")
    if dpi is not None and not 0 < float(dpi) < 1e6:
        raise ValueError(f"dpi {dpi!r}: a positive resolution, in dots per inch")
    if isinstance(structure, Mapping):
        if probability is not None or bond_tolerance is not None:
            raise ValueError("probability= and bond_tolerance= build the geometry; "
                             "a geometry dict has already been built with its own")
        geometry = structure
    else:
        geometry = s3.build(
            structure, phase,
            probability=s3.DEFAULT_PROBABILITY if probability is None else probability,
            bond_tolerance=s3.BOND_TOLERANCE if bond_tolerance is None else bond_tolerance)
    geometry = _site_colours(geometry)
    bg = _colour(background)
    dark = bg is not None and sum(w * v for w, v in zip(sc.LOOK["luma"], bg)) < 0.5
    tokens = TOKENS["dark" if dark else "light"]
    hidden_asked = [hidden] if isinstance(hidden, str) else list(hidden)
    hidden = _species(geometry, hidden_asked)
    if polyhedra is None:
        on, formulas = mode == "ball", None
    elif isinstance(polyhedra, Mapping):
        on, formulas = True, _formulas(geometry, polyhedra)
    else:
        on, formulas = bool(polyhedra), None
    shown = sc.shown_polyhedra(geometry, on, formulas, hidden, boundary)
    scene = sc.build_scene(geometry, mode, hidden=hidden, show_boundary=boundary,
                           exaggeration=exaggeration, polyhedra=shown,
                           cell=tokens["--accent"])
    margin = max([0.5 * line["width"] for line in scene["lines"]] + [0.0])
    if axis_labels:
        margin = max(margin, 0.6 * LETTER_EM_CSS)
    probe = rp.probe(scene, geometry, size, margin + 1.0, _fit, axis_labels)
    candidates: list[dict] = []
    if isinstance(view, str) and view == "auto":
        view, candidates = rp.choose_view(geometry, probe, up, turn)
    R = views.resolve(geometry, view, up, turn)
    extra = ()
    if atom_labels:
        extra, reach = _label_reach(scene, geometry, R)
        margin = max(margin, reach, 0.6 * LETTER_EM_CSS)
    frame = _fit(_extent(scene, R, axis_labels, extra), size, margin + 1.0)
    strokes, letters = text_strokes(scene, geometry, R, frame, axis_labels=axis_labels,
                                    atom_labels=atom_labels, accent=tokens["--accent"],
                                    ink=tokens["--fg"])
    ol = None
    if outline:
        step = sc.stick_radius(geometry, mode, exaggeration)
        ol = (OUTLINE_CSS * frame.px_scale, step, sc.rgb(tokens["--fg"]))
    image = raster.draw(scene, R, frame, supersample=s, background=bg, text=strokes,
                        outline=ol)
    atoms = []
    for a in scene["atoms"]:
        c = R @ np.asarray(a["pos"], dtype=np.float64)
        record = geometry["atoms"][a["index"]]
        site = geometry["sites"][record["site"]]
        atoms.append({"index": a["index"], "site": record["site"], "label": site["label"],
                      "species": site["species"], "boundary": record["boundary"],
                      "x": (c[0] - frame.x0) * frame.ppa, "y": (frame.y0 - c[1]) * frame.ppa,
                      "depth": float(c[2])})
    written = None
    if path is not None:
        target = Path(path)
        _png(target, image, dpi)
        written = str(target)
    seen = rp.look(probe, R)
    labels = _labels(scene, geometry, R, frame, axis_labels=axis_labels, atom_labels=atom_labels)
    warnings = []
    if mode == "ellipsoid":
        flat = sorted({geometry["sites"][geometry["atoms"][a["index"]]["site"]]["label"]
                       for a in scene["atoms"]
                       if geometry["sites"][geometry["atoms"][a["index"]]["site"]]["npd"]})
        warnings += [f"{label}: its displacement tensor is not positive definite, so its "
                     "ellipsoid is drawn flat" for label in flat]
    if seen.unjudged:
        warnings.append(f"{seen.unjudged} atoms cover less than one sample at {max(probe.size) if isinstance(probe.size, tuple) else probe.size} px "
                        "and are not counted in hidden")
    report = rp.FigureReport(
        hidden=seen.hidden, hidden_atoms=seen.hidden_atoms,
        dangling_bonds=_dangling(geometry, scene, hidden),
        label_overlaps=_label_overlaps(labels, frame), empty=_empty(image, bg),
        cut={"polyhedra": 0, "bonds": 0, **geometry.get("cut", {})},
        note=geometry.get("note", ""), warnings=warnings)
    recipe = {"mode": mode, "view": views.as_list(R), "size": _plain(size),
              "supersample": s, "exaggeration": exaggeration, "hidden": hidden_asked,
              "boundary": boundary, "polyhedra": polyhedra, "axis_labels": axis_labels,
              "atom_labels": atom_labels, "outline": outline, "background": _plain(background),
              "dpi": dpi}
    return StructureFigure(image=image, rotation=views.as_list(R),
                           pixels_per_angstrom=frame.ppa, atoms=atoms, letters=letters,
                           path=written, palette=_palette(geometry, scene), report=report,
                           candidates=candidates, recipe=recipe)
