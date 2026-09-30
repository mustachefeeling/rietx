"""Part of a structure drawn: cut atoms out of the figure and recolour some (WP-1501).

Structure: COD 1000236 (Courbion & Ferey, 1988), NAC, cubic I2₁3.  The pictures
are written beside this script.
"""

from pathlib import Path

import rietx as rx
from rietx import viz
from rietx.gui.structure3d import build

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"
HERE = Path(__file__).resolve().parent

structure = rx.Structure.from_cif(str(DATA / "cod_1000236.cif"), aniso=True)
geometry = build(structure)
print(f"built: {len(geometry['atoms'])} atoms, {len(geometry['bonds'])} bonds, "
      f"{len(geometry['polyhedra'])} polyhedra")

# leave out one site: F2 and F1 share a species, so a mask names the site
no_f2 = viz.keep(geometry, ~viz.select(geometry, label="F2"))
fig = viz.render_structure(no_f2, path=HERE / "nac_without_f2.png")
print(f"without F2: {len(fig.atoms)} atoms drawn; {no_f2['note']}")

# the same cut, completed: the octahedra that lost a vertex get it back
whole = viz.keep(geometry, ~viz.select(geometry, label="F2"), complete=True)
fig = viz.render_structure(whole, path=HERE / "nac_without_f2_completed.png")
print(f"completed: {len(fig.atoms)} atoms drawn; note {whole['note']!r}")

# a slab between the (110) planes at half and one d-spacing from the origin
slab = viz.keep(geometry, viz.plane(geometry, (1, 1, 0), 0.5, width=0.5), complete=True)
viz.render_structure(slab, path=HERE / "nac_110_slab.png")
print(f"(110) slab: {len(slab['atoms'])} atoms kept")

# everything within 4 Å of one aluminium atom
al = next(i for i in viz.select(geometry, element="Al").nonzero()[0])
ball = viz.keep(geometry, viz.sphere(geometry, al, 4.0))
print(f"4 Å round atom {al}: {len(ball['atoms'])} atoms kept")

# the piece of the structure one AlF6 octahedron is joined to by shared corners
piece = viz.component(geometry, al, via="corners")
print(f"corner-sharing piece of atom {al}: {piece.sum()} atoms")

# paint one aluminium atom and the octahedron round it red; the rest keep theirs
mask = viz.select(geometry, element="Al") & viz.sphere(geometry, al, 0.1)
fig = viz.render_structure(viz.recolour(geometry, mask, "#ff0000"),
                           path=HERE / "nac_one_red.png")
print(f"palette: {fig.palette}")

# a block of cells: the cell's bonds and polyhedra translated, so it costs what it draws
block = build(structure, extent=((0, 2), (0, 2), (0, 1)), max_atoms=2000)
viz.render_structure(block, path=HERE / "nac_2x2x1.png")
print(f"2x2x1 block: {len(block['atoms'])} atoms, {len(block['bonds'])} bonds, "
      f"{len(block['polyhedra'])} polyhedra")

# which atom of the cell each atom is, and by which lattice translation
print(f"atom 0 is {block['atoms'][0]['image']}, atom {block['n_cell'] - 1} is "
      f"{block['atoms'][block['n_cell'] - 1]['image']}")

# how many directions a piece repeats in: the octahedron's corner-sharing
# framework in three, one AlF6 and its bonds in none
al = next(i for i in viz.select(block, element="Al").nonzero()[0])
framework = viz.component(block, al, via="corners")
octahedron = viz.sphere(block, al, 2.0)
print(f"periodicity: framework {viz.periodicity(block, framework)}, "
      f"one octahedron {viz.periodicity(block, octahedron)}")
