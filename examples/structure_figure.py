"""A structure figure from Python, drawn without a browser (WP-1470).

Structure: COD 1000236 (Courbion & Ferey, 1988), NAC, cubic I2₁3, read with
its anisotropic displacement tensors.  The pictures are written beside this
script.
"""

from pathlib import Path

import rietx as rx
from rietx.viz import render_structure

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"
HERE = Path(__file__).resolve().parent

structure = rx.Structure.from_cif(str(DATA / "cod_1000236.cif"), aniso=True)

# the GUI's opening picture: balls and sticks, the AlF6 octahedra drawn
fig = render_structure(structure, path=HERE / "nac_structure.png")
print(f"wrote {Path(fig.path).name}: {fig.image.shape[1]} x {fig.image.shape[0]} px, "
      f"{len(fig.atoms)} atoms, {fig.pixels_per_angstrom:.1f} px/Å")

# ellipsoids at 50 % down the [111] zone axis, transparent, for a figure
fig = render_structure(structure, mode="ellipsoid", view=[1, 1, 1],
                       background=None, path=HERE / "nac_ellipsoids.png")
print(f"wrote {Path(fig.path).name}: rotation drawn {[[round(v, 3) for v in row] for row in fig.rotation]}")

# the same view turned 20° about the screen's vertical, then drawn again from
# the rotation the figure carries: the two pictures are identical
turned = render_structure(structure, view=[1, 1, 1], turn="20y")
again = render_structure(structure, view=turned.rotation)
print(f"a round trip through the rotation draws the same picture: "
      f"{(turned.image == again.image).all()}")

# a print figure: 17 cm at 300 dpi is 2008 px, and the dpi goes in the file
fig = render_structure(structure, view="c", size=2008, dpi=300, outline=True,
                       path=HERE / "nac_print.png")
for letter in fig.letters:
    print(f"  letter {letter['text']} at ({letter['x']:.0f}, {letter['y']:.0f}) px")
print(f"wrote {Path(fig.path).name}")

# what the figure says about itself, so a look is not needed to know it
fig = render_structure(structure, size=400)
report = fig.report
print(f"opening view: {report.hidden:.0%} of atoms hidden, {report.dangling_bonds} bonds "
      f"dangling, {report.empty:.0%} of the frame empty")

# the search over low-index directions, and its runners-up
auto = render_structure(structure, view="auto", size=400)
print(f"auto view: {auto.report.hidden:.0%} hidden, chose {auto.candidates[0]['view']}, "
      f"then {[c['view'] for c in auto.candidates[1:3]]}")

# the call that draws the picture again, here at the size to keep
final = render_structure(structure, **{**auto.recipe, "size": 1000})
print(f"redrawn from the recipe with a long side of {max(final.image.shape[:2])} px, "
      f"same view: {final.rotation == auto.rotation}")
