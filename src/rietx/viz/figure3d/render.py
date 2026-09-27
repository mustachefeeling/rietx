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
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..theme import TOKENS
from . import glyphs, raster, views
from . import scene as sc

#: The CSS width the GUI's pixel sizes are drawn against: an image whose long
#: side is this many pixels has the GUI's on-screen line widths and letters.
CANVAS_CSS_PX = 600.0
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
    """
    image: np.ndarray
    rotation: list[list[float]]
    pixels_per_angstrom: float
    atoms: list[dict]
    letters: list[dict]
    path: str | None = None

    def __array__(self, dtype=None, copy=None):
        return self.image if dtype is None else self.image.astype(dtype)


def _colour(value) -> tuple[float, float, float] | None:
    if value is None:
        return None
    if isinstance(value, str):
        named = {"white": "#ffffff", "black": "#000000"}
        hex_ = named.get(value.lower(), value)
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
            raise ValueError(f"hidden {name!r}: this phase has no such species or "
                             f"element; its species are {have}")
        out += [m for m in match if m not in out]
    return out


def _extent(scene: dict, R: np.ndarray, with_labels: bool):
    """The drawn content's box in view coordinates, Å: (x0, x1, y0, y1)."""
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


def text_strokes(scene: dict, geometry: Mapping, R, frame: raster.Frame, *,
                 axis_labels: bool, atom_labels: bool, accent: str, ink: str):
    """The letters as strokes, and where each landed."""
    R = np.asarray(R, dtype=np.float64)
    em = LETTER_EM_CSS * frame.px_scale

    def at(p):
        c = R @ np.asarray(p, dtype=np.float64)
        return (c[0] - frame.x0) * frame.ppa, (frame.y0 - c[1]) * frame.ppa

    strokes, letters = [], []
    if axis_labels:
        for label in scene["labels"]:
            x, y = at(label["pos"])
            strokes += glyphs.strokes(label["text"], x, y, em, sc.rgb(accent))
            letters.append({"text": label["text"], "x": x, "y": y})
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
            strokes += glyphs.strokes(text, x, y, em, sc.rgb(ink))
    return strokes, letters


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
    ASE's ``"30y,-15x"``.  Every view is fitted to the frame.

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
    bg = _colour(background)
    dark = bg is not None and sum(w * v for w, v in zip(sc.LOOK["luma"], bg)) < 0.5
    tokens = TOKENS["dark" if dark else "light"]
    hidden = _species(geometry, hidden)
    if polyhedra is None:
        on, formulas = mode == "ball", None
    elif isinstance(polyhedra, Mapping):
        on, formulas = True, dict(polyhedra)
    else:
        on, formulas = bool(polyhedra), None
    shown = sc.shown_polyhedra(geometry, on, formulas, hidden, boundary)
    scene = sc.build_scene(geometry, mode, hidden=hidden, show_boundary=boundary,
                           exaggeration=exaggeration, polyhedra=shown,
                           cell=tokens["--accent"])
    R = views.resolve(geometry, view, up, turn)
    margin = max([0.5 * line["width"] for line in scene["lines"]] + [0.0])
    if axis_labels:
        margin = max(margin, 0.6 * LETTER_EM_CSS)
    frame = _fit(_extent(scene, R, axis_labels), size, margin + 1.0)
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
    return StructureFigure(image=image, rotation=views.as_list(R),
                           pixels_per_angstrom=frame.ppa, atoms=atoms, letters=letters,
                           path=written)
