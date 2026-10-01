"""Two figures per task, the instrument's check of its own judge (PROTOCOL.md § The judge).

    ROOT/venvs/after/bin/python docs/wp/1504-eval/reference_figures.py OUTDIR

``<task>-right.png`` is drawn by a recipe that meets every criterion, on the
``after`` surface, so it also shows each task can be done.  ``<task>-default.png``
is ``render_structure`` with nothing but the CIF, which misses at least one
criterion of every task.  ``run.py judge-references`` asks the judge about both,
before any run is scored by it: a judge that passes a default or fails a right
one is not an instrument.

Run by the ``after`` venv's interpreter, whose ``.pth`` boots the shim; the
rows land in that condition's log under no run id and no workspace, so no run
collects them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import rietx as rx
from rietx.gui.structure3d import build

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import TASKS, cif_text  # noqa: E402


def gypsum(s):
    """One (010) layer, the one about y = ½, two cells wide, seen down c."""
    g = build(s, extent=((0, 2), (0, 1), (0, 2)))
    frac = np.array([a["frac"] for a in g["atoms"]])
    return rx.viz.render_structure(rx.viz.keep(g, np.abs(frac[:, 1] - 0.5) <= 0.25),
                                   view="c")


def fap(s, path):
    """17 cm at 300 dpi, down c, a legend drawn onto the picture from ``palette``."""
    fig = rx.viz.render_structure(s, view="c", size=(2008, 1700))
    image = Image.fromarray(fig.image).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=44)
    for row, (label, colour) in enumerate(fig.palette.items()):
        y = 40 + 64 * row
        draw.ellipse((40, y, 84, y + 44), fill=colour, outline="black")
        draw.text((104, y), label, fill="black", font=font)
    image.save(path, dpi=(300, 300))


RIGHT = {
    "rutile": lambda s: rx.viz.render_structure(s, view="c"),
    "gypsum": gypsum,
    "calcite": lambda s: rx.viz.render_structure(s, hidden=("Ca",), polyhedra=False),
    "nac": lambda s: rx.viz.render_structure(
        build(s, extent=((0, 2), (0, 2), (0, 1))), view="c"),
    # `keep`, not `hidden=("La",)`, which leaves the B half of every La–B bond
    "lab6": lambda s: rx.viz.render_structure(
        rx.viz.keep(g := build(s), rx.viz.select(g, element="B", boundary=False))),
}


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for task, spec in TASKS.items():
        cif = out / spec["cif"]
        cif.write_text(cif_text(task), encoding="utf-8")
        s = rx.Structure.from_cif(cif)
        rx.viz.render_structure(s, path=out / f"{task}-default.png")
        if task == "fap":
            fap(s, out / f"{task}-right.png")
        else:
            Image.fromarray(RIGHT[task](s).image).save(out / f"{task}-right.png")
        print(task, "drawn")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
