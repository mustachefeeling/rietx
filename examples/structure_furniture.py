"""A legend, an axis triad and a scale bar drawn round a structure figure (WP-1533).

rietx draws the structure and hands back what the furniture needs: ``palette``
for the legend, ``to_px`` for where a lattice direction points in the picture,
and ``pixels_per_angstrom`` for the bar.  Structure: COD 9007744, YBa₂Cu₃O₇,
orthorhombic Pmmm.  Needs matplotlib.  The picture is written beside this script.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import rietx as rx
from rietx import viz
from rietx.gui.structure3d import build

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"
HERE = Path(__file__).resolve().parent

geometry = build(rx.Structure.from_cif(str(DATA / "cod_9007744.cif")))
fig = viz.render_structure(geometry, view=[4, 1, 0], size=800, cell=False)
h, w = fig.image.shape[:2]
strip = 0.2 * h  # the furniture sits in a strip below the picture
plt.rcParams["font.size"] = 8
page = plt.figure(figsize=(w / 200, (h + strip) / 200), dpi=200)
ax = page.add_axes((0, 0, 1, 1), xlim=(0, w), ylim=(h + strip, 0), aspect="equal")
ax.imshow(fig, extent=(0, w, h, 0))
ax.axis("off")

# the legend: one swatch an element, in the colour the figure drew it
element = {site["label"]: site["element"] for site in geometry["sites"]}
legend = {}
for label, colour in fig.palette.items():
    legend.setdefault(element[label], colour)
for k, (name, colour) in enumerate(legend.items()):
    x = w * (0.5 + 0.16 * (k - (len(legend) - 1) / 2))
    ax.plot(x - 10, h + 0.04 * h, "o", ms=7, mfc=colour, mec="none")
    ax.text(x, h + 0.04 * h, name, va="center")

# the triad: each axis as 1 Å carried into pixels, so a foreshortened axis is short;
# one nearly along the line of sight is a dot toward the viewer or a cross away
arm, start = 0.12 * w, np.array([0.1 * w, h + 0.16 * h])
toward, head = np.array(fig.rotation[2]), {"arrowstyle": "-|>", "lw": 0.8, "color": "k"}
for name, v in zip("abc", np.array(geometry["lattice"])):
    v = v / np.linalg.norm(v)
    d = (fig.to_px(v) - fig.to_px(np.zeros(3))) / fig.pixels_per_angstrom
    if np.hypot(*d) < 0.3:
        ax.plot(*start, "o", ms=9, mfc="white", mec="black", mew=0.8)
        ax.plot(*start, "." if toward @ v > 0 else "x", ms=5, color="black")
        ax.text(start[0] - 12, start[1] + 12, name, style="italic", ha="right")
    else:
        ax.annotate("", start + arm * d, start, arrowprops=head)
        ax.text(*(start + (arm + 10) * d), name, style="italic", ha="center", va="center")

# the scale bar: a round length times the pixels per Å the figure was drawn at
bar, right = 5 * fig.pixels_per_angstrom, 0.95 * w
ax.plot([right - bar, right], [start[1]] * 2, color="black", lw=2, solid_capstyle="butt")
ax.text(right - bar / 2, start[1] - 8, "5 Å", ha="center", va="bottom")
page.savefig(HERE / "ybco_furniture.png", facecolor="white")
print(f"wrote ybco_furniture.png: legend {list(legend)}, bar {bar:.0f} px for 5 Å")
