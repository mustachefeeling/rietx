"""How dark would ambient occlusion make the default figure, and what would it cost?

Filed with WP-1538 on 2026-10-02.  Two measurements, both on the scenes
``render_structure`` draws by default.

**Darkening** is an estimate from the analytic configuration factor.  A sphere
of radius r whose centre is a distance d from a surface point, wholly above
that point's tangent plane, occludes cos θ·(r/d)² of its ambient light
(θ between the normal and the direction to the centre).  The occluders
combine as a product of (1 − f).  Each drawn atom gets 64 random surface
points.  ``--sticks`` adds the bond halves as spheres of stick radius every
0.15 Å, which overlap and so overcount.  It measures whether AO would show,
and is not the multishadow number WP-1538 would draw.

**Cost** is 64 id passes (``raster.id_plane``, the depth test's twin) from
random directions, against one plain 1000 px render after compile.

    .venv/bin/python docs/wp/1538-measure/ao_probe.py [--cutoff 5] [--sticks]
"""

import argparse
import time
from pathlib import Path

import numpy as np

import rietx as rx
from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3
from rietx.viz.figure3d import raster
from rietx.viz.figure3d import scene as sc
from rietx.viz.figure3d.render import _extent, _fit

DATA = Path(__file__).resolve().parents[3] / "tests" / "data"
CASES = ["fluorapatite.cif", "cod_1000236.cif", "cod_1000055.cif"]


def occluders(scene, sticks):
    centres = np.array([a["pos"] for a in scene["atoms"]], float)
    radii = np.array([np.cbrt(abs(np.linalg.det(np.asarray(a["shape"], float).reshape(3, 3))))
                      for a in scene["atoms"]])
    cs, rs = [centres], [radii]
    for h in scene["halves"] if sticks else []:
        p0, p1 = np.asarray(h["from"], float), np.asarray(h["to"], float)
        n = max(2, int(np.linalg.norm(p1 - p0) / 0.15))
        t = np.linspace(0, 1, n)[:, None]
        cs.append(p0 + t * (p1 - p0))
        rs.append(np.full(n, float(h["radius"])))
    return centres, radii, np.concatenate(cs), np.concatenate(rs)


def darkening(scene, cutoff, sticks, rng):
    centres, radii, oc, orad = occluders(scene, sticks)
    out = []
    for c, r in zip(centres, radii):
        n = rng.normal(size=(64, 3))
        n /= np.linalg.norm(n, axis=1)[:, None]
        d = oc[None, :, :] - (c + r * n)[:, None, :]
        dist = np.linalg.norm(d, axis=2)
        f = (np.clip(np.einsum("ij,ikj->ik", n, d) / dist, 0, 1)
             * np.minimum((orad[None, :] / dist) ** 2, 1))
        f[:, np.linalg.norm(oc - c, axis=1) < r] = 0
        if cutoff:
            f[dist > cutoff] = 0
        out.append(1 - np.prod(1 - f, axis=1))
    return np.concatenate(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", type=float, default=0.0, help="Å; 0 for none")
    ap.add_argument("--sticks", action="store_true")
    args = ap.parse_args()
    rng = np.random.default_rng(0)
    for name in CASES:
        st = structure_from_cif(str(DATA / name), aniso=True)
        g = s3.build(st)
        for mode, poly in [("ball", False), ("ball", True), ("ellipsoid", False)]:
            scene = sc.build_scene(g, mode, polyhedra=sc.shown_polyhedra(g, poly))
            dark = darkening(scene, args.cutoff, args.sticks, rng) * 100
            print(f"{name:18s} {mode:9s} polyhedra={poly!s:5s} atoms={len(scene['atoms']):4d}  "
                  f"darkening mean {dark.mean():5.1f} %  p50 {np.median(dark):5.1f} %  "
                  f"p95 {np.percentile(dark, 95):5.1f} %")
        rx.viz.render_structure(st, size=1000)
        t0 = time.perf_counter()
        rx.viz.render_structure(st, size=1000)
        plain = time.perf_counter() - t0
        scene = sc.build_scene(g, "ball", polyhedra=sc.shown_polyhedra(g, True))
        arrays = raster.scene_arrays(scene)
        for px in (256, 1024):
            t0 = time.perf_counter()
            for _ in range(64):
                q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
                raster.id_plane(raster.pack_ids(arrays, q), _fit(_extent(scene, q, False), px, 0.0))
            print(f"    64 id passes at {px:4d} px {time.perf_counter() - t0:.3f} s; "
                  f"one 1000 px render {plain:.3f} s")


if __name__ == "__main__":
    main()
