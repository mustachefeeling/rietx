"""Letters drawn as strokes, from the Hershey simplex font (WP-1470 D8).

The GUI's a, b, c are DOM text over its canvas, and its PNG export draws them
in; a figure without them would be a step back.  A font rasteriser (Pillow,
FreeType) would be a dependency for three letters, so the renderer draws its own
from ``rietx/data/hershey_simplex.json``: vector glyphs, drawn through the same
segment path as the cell frame.  That file carries the acknowledgement its
licence requires; ATTRIBUTION.md names it.

Sizes follow the GUI's letters: an em of 11.5 CSS px (``--text-sm``), scaled
as everything pixel-sized is.  A Hershey capital is 21 units, which is 0.7 em
in a sans-serif, so an em is 30 units; the strokes are a tenth of an em wide,
near the stem of the GUI's weight 600; and a string is centred on its anchor
by the middle of the font's box, −7 to 25 units, as the canvas export centres
with ``textBaseline = "middle"``.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources

#: Font units in an em: a capital is 21 units and 0.7 em.
EM_UNITS = 30.0
#: The vertical middle of the font's box, −7 to 25 units.
MIDDLE_UNITS = 9.0
#: Stroke width, in ems.
STROKE_EM = 0.1


@cache
def _font() -> dict:
    text = resources.files("rietx.data").joinpath("hershey_simplex.json").read_text("utf-8")
    return json.loads(text)["glyphs"]


def width(text: str, em: float) -> float:
    """The advance of ``text`` at an em of ``em`` pixels."""
    font = _font()
    return sum(font.get(ch, font["?"])[0] for ch in text) * em / EM_UNITS


def strokes(text: str, x: float, y: float, em: float, color) -> list:
    """``text`` centred on image pixel ``(x, y)`` as segments for
    :func:`.raster.draw`: ``((u0, v0, u1, v1), half-width, colour)``, v down."""
    font = _font()
    scale = em / EM_UNITS
    left = x - width(text, em) / 2
    half = 0.5 * STROKE_EM * em
    out = []
    for ch in text:
        advance, lines = font.get(ch, font["?"])
        for line in lines:
            pts = [(left + line[k] * scale, y - (line[k + 1] - MIDDLE_UNITS) * scale)
                   for k in range(0, len(line), 2)]
            out.extend(((p[0], p[1], q[0], q[1]), half, color) for p, q in zip(pts, pts[1:]))
        left += advance * scale
    return out
