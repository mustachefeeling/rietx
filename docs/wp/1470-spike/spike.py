"""Spike: a CPU ray-caster of structure3d.build()'s payload, numba + stdlib PNG.

Mirrors the GUI shader (gl3d.ts): exact ellipsoid/ball quadrics, bond halves as
finite cylinders, one key light, principal rings in ellipsoid mode. No text, no
polyhedra. Serial njit, primitive-major z-buffer, SSAA box filter.

Run from the repo root: ``python docs/wp/1470-spike/spike.py OUT_DIR``.
"""
import struct
import sys
import time
import zlib

import numpy as np
from numba import njit

LIGHT = np.array([-0.40, 0.55, 0.73])
LIGHT /= np.linalg.norm(LIGHT)


@njit(cache=True, nogil=True)
def shade(base, n, out):
    d = max(n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2], 0.0)
    # reflect(-l, n) · ẑ
    ndl = n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]
    rz = -LIGHT[2] + 2.0 * ndl * n[2]
    spec = max(rz, 0.0) ** 40.0
    for k in range(3):
        out[k] = min(base[k] * (0.45 + 0.60 * d) + 0.16 * spec, 1.0)


@njit(cache=True, nogil=True)
def raster(zbuf, img, px, x0, y0, centers, minv, halfext, colors, rings,
           ca, cb, crad, ccol):
    H, W = zbuf.shape
    col = np.empty(3)
    n = np.empty(3)
    # atoms: ray-cast quadric |Minv (p - c)| = 1 along ẑ
    for i in range(centers.shape[0]):
        cx, cy, cz = centers[i]
        ix0 = max(int((cx - halfext[i, 0] - x0) * px), 0)
        ix1 = min(int((cx + halfext[i, 0] - x0) * px) + 1, W)
        iy0 = max(int((y0 - (cy + halfext[i, 1])) * px), 0)
        iy1 = min(int((y0 - (cy - halfext[i, 1])) * px) + 1, H)
        M = minv[i]
        e0, e1, e2 = M[0, 2], M[1, 2], M[2, 2]
        a = e0 * e0 + e1 * e1 + e2 * e2
        for iy in range(iy0, iy1):
            y = y0 - (iy + 0.5) / px - cy
            for ix in range(ix0, ix1):
                x = x0 + (ix + 0.5) / px - cx
                q0 = M[0, 0] * x + M[0, 1] * y
                q1 = M[1, 0] * x + M[1, 1] * y
                q2 = M[2, 0] * x + M[2, 1] * y
                b = q0 * e0 + q1 * e1 + q2 * e2
                cc = q0 * q0 + q1 * q1 + q2 * q2 - 1.0
                disc = b * b - a * cc
                if disc < 0.0:
                    continue
                s = (-b + np.sqrt(disc)) / a
                z = cz + s
                if z <= zbuf[iy, ix]:
                    continue
                zbuf[iy, ix] = z
                u0, u1, u2 = q0 + s * e0, q1 + s * e1, q2 + s * e2
                # normal = Minvᵀ u
                n[0] = M[0, 0] * u0 + M[1, 0] * u1 + M[2, 0] * u2
                n[1] = M[0, 1] * u0 + M[1, 1] * u1 + M[2, 1] * u2
                n[2] = M[0, 2] * u0 + M[1, 2] * u1 + M[2, 2] * u2
                nn = np.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
                n /= nn
                shade(colors[i], n, col)
                if rings[i] and min(abs(u0), min(abs(u1), abs(u2))) < 0.035:
                    lum = 0.2126 * colors[i, 0] + 0.7152 * colors[i, 1] + 0.0722 * colors[i, 2]
                    for k in range(3):
                        col[k] = col[k] + 0.6 * (1.0 - col[k]) if lum < 0.33 else col[k] * 0.3
                for k in range(3):
                    img[iy, ix, k] = np.uint8(col[k] * 255.0 + 0.5)
    # cylinders: bond halves and cell edges
    for i in range(ca.shape[0]):
        A = ca[i]
        B = cb[i]
        r = crad[i]
        d0, d1, d2 = B[0] - A[0], B[1] - A[1], B[2] - A[2]
        L = np.sqrt(d0 * d0 + d1 * d1 + d2 * d2)
        if L == 0.0:
            continue
        d0 /= L
        d1 /= L
        d2 /= L
        Q0, Q1, Q2 = -d2 * d0, -d2 * d1, 1.0 - d2 * d2
        qa = Q0 * Q0 + Q1 * Q1 + Q2 * Q2
        if qa < 1e-9:
            continue
        ix0 = max(int((min(A[0], B[0]) - r - x0) * px), 0)
        ix1 = min(int((max(A[0], B[0]) + r - x0) * px) + 1, W)
        iy0 = max(int((y0 - (max(A[1], B[1]) + r)) * px), 0)
        iy1 = min(int((y0 - (min(A[1], B[1]) - r)) * px) + 1, H)
        for iy in range(iy0, iy1):
            w1 = y0 - (iy + 0.5) / px - A[1]
            for ix in range(ix0, ix1):
                w0 = x0 + (ix + 0.5) / px - A[0]
                w2 = -A[2]
                wd = w0 * d0 + w1 * d1 + w2 * d2
                P0, P1, P2 = w0 - wd * d0, w1 - wd * d1, w2 - wd * d2
                b = P0 * Q0 + P1 * Q1 + P2 * Q2
                c = P0 * P0 + P1 * P1 + P2 * P2 - r * r
                disc = b * b - qa * c
                if disc < 0.0:
                    continue
                t = (-b + np.sqrt(disc)) / qa
                h = wd + t * d2
                if h < 0.0 or h > L:
                    continue
                if t <= zbuf[iy, ix]:
                    continue
                zbuf[iy, ix] = t
                n[0], n[1], n[2] = P0 + t * Q0, P1 + t * Q1, P2 + t * Q2
                n /= np.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
                shade(ccol[i], n, col)
                for k in range(3):
                    img[iy, ix, k] = np.uint8(col[k] * 255.0 + 0.5)


def rgb(h):
    return [int(h[k:k + 2], 16) / 255 for k in (1, 3, 5)]


def view_matrix(toward, up=(0, 0, 1)):
    t = np.asarray(toward, float)
    t /= np.linalg.norm(t)
    r = np.cross(up, t)
    r /= np.linalg.norm(r)
    return np.array([r, np.cross(t, r), t])


def scene(g, R, mode):
    atoms, sites = g["atoms"], g["sites"]
    centers = np.array([R @ a["pos"] for a in atoms])
    minv, half, colors, rings = [], [], [], []
    for a in atoms:
        site = sites[a["site"]]
        if mode == "ellipsoid":
            # the GUI's FLAT_AXIS floor is not applied: a zero semi-axis would
            # make kT singular here, and NAC has none
            kT = np.array(a["ellipsoid"]) * g["scale"]
        else:
            kT = np.eye(3) * g["ball_fraction"] * site["radius"]
        M = R @ kT
        minv.append(np.linalg.inv(kT) @ R.T)
        half.append([np.linalg.norm(M[0]), np.linalg.norm(M[1])])
        colors.append(rgb(site["color"]))
        rings.append(mode == "ellipsoid" and site["aniso"])
    stick = 0.08
    if mode == "ellipsoid":
        semi = [v for a in atoms for v in a["rms"] if v > 0]
        stick = max(0.02, min(0.08, 0.5 * min(semi) * g["scale"]))
    ca, cb, crad, ccol = [], [], [], []
    for b in g["bonds"]:
        A, B = R @ b["a"], R @ b["b"]
        m = 0.5 * (A + B)
        for P0, P1, idx in ((A, m, b["i"]), (m, B, b["j"])):
            ca.append(P0); cb.append(P1); crad.append(stick)
            ccol.append(rgb(sites[atoms[idx]["site"]]["color"]))
    corners = np.array(g["corners"])
    for e0, e1 in g["edges"]:
        ca.append(R @ corners[e0]); cb.append(R @ corners[e1]); crad.append(0.025)
        ccol.append([0.25, 0.35, 0.8])
    f = lambda x: np.ascontiguousarray(np.array(x, dtype=np.float64))
    return (f(centers), f(minv), f(half), f(colors), np.array(rings, dtype=np.bool_),
            f(ca), f(cb), f(crad), f(ccol))


def render(g, R, size, ssaa=2, mode="ball"):
    sc = scene(g, R, mode)
    centers, half = sc[0], sc[2]
    pts = np.vstack([centers[:, :2] - half, centers[:, :2] + half, sc[5][:, :2], sc[6][:, :2]])
    lo, hi = pts.min(0) - 0.3, pts.max(0) + 0.3
    span = hi - lo
    px = size * ssaa / span.max()
    W, H = int(span[0] * px) + 1, int(span[1] * px) + 1
    zbuf = np.full((H, W), -np.inf)
    img = np.full((H, W, 3), 255, dtype=np.uint8)
    raster(zbuf, img, px, lo[0], hi[1], *sc)
    if ssaa > 1:
        H2, W2 = H // ssaa, W // ssaa
        img = img[:H2 * ssaa, :W2 * ssaa].reshape(H2, ssaa, W2, ssaa, 3).mean((1, 3)).astype(np.uint8)
    return img


def write_png(path, img):
    H, W, _ = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(H))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    from rietx.crystallography.cif import structure_from_cif
    from rietx.gui import structure3d

    out = sys.argv[1]
    s = structure_from_cif("tests/data/cod_1000236.cif", aniso=True)
    t = time.perf_counter(); g = structure3d.build(s); tb = time.perf_counter() - t
    print(f"build(): {tb*1e3:.0f} ms, {len(g['atoms'])} atoms, {len(g['bonds'])} bonds")
    R = view_matrix([1.0, 0.45, 0.3])
    t = time.perf_counter(); render(g, R, 64, 1); print(f"first call (JIT or cache load): {time.perf_counter()-t:.2f} s")
    for mode in ("ball", "ellipsoid"):
        for size, ssaa in ((1000, 2), (2000, 2), (3000, 1), (3000, 2)):
            ts = []
            for _ in range(3):
                t = time.perf_counter(); img = render(g, R, size, ssaa, mode); ts.append(time.perf_counter() - t)
            t = time.perf_counter(); write_png(f"{out}/nac_{mode}_{size}_ss{ssaa}.png", img); tw = time.perf_counter() - t
            print(f"{mode:9s} {size}px ssaa{ssaa}: render {min(ts)*1e3:.0f}-{max(ts)*1e3:.0f} ms, png write {tw*1e3:.0f} ms, {img.shape[1]}x{img.shape[0]}")
