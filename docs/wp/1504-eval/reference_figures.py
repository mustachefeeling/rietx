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


def without_bare_centres(g):
    """``g`` less every atom of a polyhedron-centre element that carries none.

    One cell draws them as bond ends just outside it: rutile's two Ti above and
    below the body centre, fluorapatite's four P beyond the side faces (measured
    for amendment 1.2).  No verb names them and the report counts none, so the
    mask is read off the dict.
    """
    centres = {p["center"] for p in g["polyhedra"] if p["drawn_by_default"]}
    kinds = {g["sites"][g["atoms"][c]["site"]]["element"] for c in centres}
    mask = np.array([g["sites"][a["site"]]["element"] not in kinds or i in centres
                     for i, a in enumerate(g["atoms"])])
    return rx.viz.keep(g, mask)


def carbonate_groups(g):
    """The connected pieces holding a C once Ca is gone: 12 C, 36 O, C–O bonds only.

    Not ``hidden=("Ca",)``, which leaves the O half of every Ca–O bond drawn and
    uncounted by ``dangling_bonds``; not ``keep`` of all but Ca, which leaves
    the O whose C lies outside the cell; and not ``keep`` of the C with
    ``complete=True``, which left 16 O bonded to no C (amendment 1.2).
    """
    g = rx.viz.keep(g, ~rx.viz.select(g, element="Ca"))
    mask = np.zeros(len(g["atoms"]), bool)
    for i in np.flatnonzero(rx.viz.select(g, element="C")):
        mask |= rx.viz.component(g, int(i))
    return rx.viz.keep(g, mask)


def gypsum(s):
    """One (010) layer, the one about y = ½, two cells wide, seen down c."""
    g = build(s, extent=((0, 2), (0, 1), (0, 2)))
    frac = np.array([a["frac"] for a in g["atoms"]])
    return rx.viz.render_structure(rx.viz.keep(g, np.abs(frac[:, 1] - 0.5) <= 0.25),
                                   view="c")


def fap(s, path):
    """17 cm at 300 dpi, down c, a legend drawn onto the picture from ``palette``."""
    fig = rx.viz.render_structure(without_bare_centres(build(s)), view="c", size=(2008, 1700))
    image = Image.fromarray(fig.image).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=44)
    for row, (label, colour) in enumerate(fig.palette.items()):
        y = 40 + 64 * row
        draw.ellipse((40, y, 84, y + 44), fill=colour, outline="black")
        draw.text((104, y), label, fill="black", font=font)
    image.save(path, dpi=(300, 300))


def chains(s):
    """One chain, the one through the body centre, four cells along c, from the side.

    ``component`` over shared edges is the chain; ``keep`` without
    ``complete``, since completing it brings back the neighbouring chains'
    titanium bare (22 of 26 measured, amendment 1.2).
    """
    g = build(s, extent=((0, 1), (0, 1), (0, 4)), max_atoms=2000)
    centre = next(i for i, a in enumerate(g["atoms"])
                  if g["sites"][a["site"]]["element"] == "Ti"
                  and np.allclose(a["frac"], [0.5, 0.5, 0.5]))
    return rx.viz.render_structure(rx.viz.keep(g, rx.viz.component(g, centre, via="edges")),
                                   view=[1, 1, 0])


RIGHT = {
    "rutile": lambda s: rx.viz.render_structure(without_bare_centres(build(s)), view="c"),
    "chains": chains,
    "gypsum": gypsum,
    "calcite": lambda s: rx.viz.render_structure(carbonate_groups(build(s)), polyhedra=False),
    # the opening view, where the block's outline is a flat box: down c it is a
    # square either way, and the 1.2 judge could not count the cells
    "nac": lambda s: rx.viz.render_structure(build(s, extent=((0, 2), (0, 2), (0, 1)))),
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
