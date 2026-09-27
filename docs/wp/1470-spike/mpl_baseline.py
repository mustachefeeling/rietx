"""Baseline: the same scene drawn by matplotlib, painter's algorithm, flat fills.

Run from the repo root: ``python docs/wp/1470-spike/mpl_baseline.py OUT_DIR``.
"""
import os
import sys
import time

t0 = time.perf_counter()
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PatchCollection  # noqa: E402
from matplotlib.patches import Ellipse, Polygon  # noqa: E402

t_import = time.perf_counter() - t0
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spike import rgb, view_matrix  # noqa: E402

from rietx.crystallography.cif import structure_from_cif  # noqa: E402
from rietx.gui import structure3d  # noqa: E402

g = structure3d.build(structure_from_cif("tests/data/cod_1000236.cif", aniso=True))
R = view_matrix([1.0, 0.45, 0.3])


def draw(path, size):
    atoms, sites = g["atoms"], g["sites"]
    items = []  # (depth, patch)
    for a in atoms:
        site = sites[a["site"]]
        r = g["ball_fraction"] * site["radius"]
        c = R @ a["pos"]
        items.append((c[2], Ellipse(c[:2], 2 * r, 2 * r, facecolor=rgb(site["color"]),
                                    edgecolor="k", linewidth=0.3)))
    for b in g["bonds"]:
        A, B = R @ b["a"], R @ b["b"]
        m = 0.5 * (A + B)
        for P0, P1, idx in ((A, m, b["i"]), (m, B, b["j"])):
            d = P1[:2] - P0[:2]
            nrm = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-12) * 0.08
            quad = [P0[:2] + nrm, P1[:2] + nrm, P1[:2] - nrm, P0[:2] - nrm]
            items.append((0.5 * (P0[2] + P1[2]) - 0.01,
                          Polygon(quad, facecolor=rgb(sites[atoms[idx]["site"]]["color"]),
                                  edgecolor="none")))
    items.sort(key=lambda it: it[0])
    fig = plt.figure(figsize=(size / 300, size / 300), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.add_collection(PatchCollection([p for _, p in items], match_original=True))
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.axis("off")
    fig.savefig(path, dpi=300)
    plt.close(fig)


print(f"import matplotlib: {t_import * 1e3:.0f} ms")
for size in (1000, 3000):
    for ext in ("png", "svg", "pdf"):
        ts = []
        for _ in range(3):
            t = time.perf_counter()
            draw(f"{sys.argv[1]}/mpl_{size}.{ext}", size)
            ts.append(time.perf_counter() - t)
        print(f"matplotlib {size}px {ext}: {min(ts) * 1e3:.0f}-{max(ts) * 1e3:.0f} ms")
