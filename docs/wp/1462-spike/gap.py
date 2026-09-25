"""Ligand distances per site: is there a clear gap after the shell?"""
import sys

import numpy as np

spike = sys.argv[1]
src = open(f"{spike}/payloads.py").read().split("\nfor name, structure in cases.items():")[0]
ns = {"__file__": f"{spike}/payloads.py"}
exec(src, ns)
from rietx.gui import structure3d as s3  # noqa: E402

for name in ("lab6", "nac", "fap"):
    g = s3.build(ns["cases"][name], phase=0)
    L = np.array(g["lattice"])                       # rows a, b, c
    frac = {}
    for a in g["atoms"]:
        f = np.mod(np.round(a["frac"], 6), 1.0)
        frac[tuple(np.round(f, 5))] = (f, g["sites"][a["site"]])
    shifts = np.array([[i, j, k] for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)])
    seen = set()
    for f0, site in frac.values():
        if site["label"] in seen:
            continue
        seen.add(site["label"])
        d = []
        for f1, other in frac.values():
            if other["element"] == site["element"] or s3.is_metal(other["element"]):
                continue
            for s in shifts:
                r = np.linalg.norm((f1 + s - f0) @ L)
                if 0.4 < r < 4.2:
                    d.append(r)
        d = np.sort(d)
        if len(d) < 2:
            continue
        ratios = d[1:] / d[:-1]
        k = int(np.argmax(ratios[:12])) + 1           # the largest gap in the first 13
        cutoff = 1.15 * (site["radius"] + max(s3.element_radius(e) for e in
                                               {o["element"] for _, o in frac.values()}
                                               if not s3.is_metal(e) and e != site["element"]))
        print(f"{name:5} {site['label']:4} bond-rule shell {int((d <= cutoff).sum()):2}  "
              f"largest gap after {k:2} ligands, ratio {ratios[k-1]:.2f}  "
              f"first distances {np.round(d[:10], 2).tolist()}")
