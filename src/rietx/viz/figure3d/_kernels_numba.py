"""The ray-caster's compiled kernel (WP-1470 D1).

One serial ``njit(cache=True, nogil=True)`` function draws a band of output
rows, and :mod:`.raster` spreads bands over the compiled tier's shared pool, so
no two threads write one pixel (root CLAUDE.md § compiled tier: never
``prange``, which refuses to cache and measured slower).

Every per-sample expression here is written in the order
``raster._band_numpy`` writes it, and there is no library call in either:
``sqrt`` is an IEEE operation, the specular power is repeated squaring, and the
box filter adds the samples in one order.  So the bar between the two paths is
the bit, and ``tests/test_render_structure.py`` asserts it.  An edit to one is
an edit to the other.

The arrays are packed by ``raster._pack``; its docstring says what each holds.
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit


@njit(cache=True, nogil=True)
def _ipow(x, n):
    """``x**n`` for an integer ``n ≥ 0`` by repeated squaring."""
    out = 1.0
    base = x
    while n > 0:
        if n & 1:
            out = out * base
        base = base * base
        n >>= 1
    return out


@njit(cache=True, nogil=True)
def _shade(b0, b1, b2, n0, n1, n2, look, col):
    """The GUI's ``shade``: ``base·(ambient + diffuse·d) + specular·s^k``."""
    ndl = n0 * look[0] + n1 * look[1] + n2 * look[2]
    d = max(ndl, 0.0)
    rz = -look[2] + 2.0 * ndl * n2
    spec = _ipow(max(rz, 0.0), int(look[6]))
    k = look[3] + look[4] * d
    col[0] = b0 * k + look[5] * spec
    col[1] = b1 * k + look[5] * spec
    col[2] = b2 * k + look[5] * spec


@njit(cache=True, nogil=True)
def _clamp(v):
    return min(max(v, 0.0), 1.0)


@njit(cache=True, nogil=True)
def _flat(prim_p, prim_half, prim_dir, prim_len, prim_z, prim_col, prim_box, depth,
          r0, hs, ws, zb, pm, al):
    """Segments with a width in samples: the cell frame and polyhedron edges
    (``depth`` true, tested and written like the GUI's line quads), or the
    letters (``depth`` false, drawn over everything)."""
    for i in range(prim_p.shape[0]):
        iy0 = max(prim_box[i, 0], r0)
        iy1 = min(prim_box[i, 1], r0 + hs)
        if iy0 >= iy1:
            continue
        ix0 = max(prim_box[i, 2], 0)
        ix1 = min(prim_box[i, 3], ws)
        ax = prim_p[i, 0]
        ay = prim_p[i, 1]
        dx = prim_dir[i, 0]
        dy = prim_dir[i, 1]
        h = prim_half[i]
        length = prim_len[i]
        za = prim_z[i, 0]
        dz = prim_z[i, 1] - prim_z[i, 0]
        span = length + 2.0 * h
        for iy in range(iy0, iy1):
            v = iy + 0.5 - ay
            for ix in range(ix0, ix1):
                u = ix + 0.5 - ax
                along = u * dx + v * dy
                across = v * dx - u * dy
                if abs(across) > h or along < -h or along > length + h:
                    continue
                row = iy - r0
                if depth:
                    z = za + dz * ((along + h) / span)
                    if z < zb[row, ix]:
                        continue
                    zb[row, ix] = z
                pm[row, ix, 0] = prim_col[i, 0]
                pm[row, ix, 1] = prim_col[i, 1]
                pm[row, ix, 2] = prim_col[i, 2]
                al[row, ix] = 1.0


@njit(cache=True, nogil=True)
def _outline(ext0, sr0, hs, ws, total, ow, otau, ocol, zb, pm):
    """Ink a covered sample whose depth stands more than ``otau`` in front of
    any sample within ``ow`` samples of it: the silhouette from the depth
    buffer's discontinuities (D9).  The band carries ``ow`` rows of halo, so a
    silhouette crossing a band boundary is found from both sides."""
    for iy in range(sr0, sr0 + hs):
        row = iy - ext0
        for ix in range(ws):
            z = zb[row, ix]
            if z == -np.inf:
                continue
            edge = False
            for dy in range(-ow, ow + 1):
                qy = iy + dy
                if qy < 0 or qy >= total:
                    continue
                for dx in range(-ow, ow + 1):
                    if dx * dx + dy * dy > ow * ow:
                        continue
                    qx = ix + dx
                    if qx < 0 or qx >= ws:
                        continue
                    if zb[qy - ext0, qx] < z - otau:
                        edge = True
                        break
                if edge:
                    break
            if edge:
                pm[row, ix, 0] = ocol[0]
                pm[row, ix, 1] = ocol[1]
                pm[row, ix, 2] = ocol[2]


@njit(cache=True, nogil=True)
def render_rows(r0, r1, s, height, x0, y0, pxs, width, look, alpha, bg, has_bg,
                ow, otau, ocol,
                atom_c, atom_m, atom_a, atom_col, atom_lum, atom_ring, atom_box,
                half_a, half_w, half_len, half_e, half_ea, half_r, half_col, half_box,
                line_p, line_half, line_dir, line_len, line_z, line_col, line_box,
                tri_v, tri_area, tri_tie, tri_col, tri_box,
                text_p, text_half, text_dir, text_len, text_z, text_col, text_box,
                out):
    """Draw output rows ``[r0, r1)`` into ``out`` (height × width × 4, uint8).

    The band's sample rows are ``[sr0, sr0 + hs)``; it draws ``ow`` rows more
    on each side, ``[ext0, ext1)``, for the outline to read.
    """
    hs = (r1 - r0) * s
    ws = width * s
    sr0 = r0 * s
    total = height * s
    ext0 = max(sr0 - ow, 0)
    ext1 = min(sr0 + hs + ow, total)
    he = ext1 - ext0
    zb = np.full((he, ws), -np.inf)
    pm = np.zeros((he, ws, 3))
    al = np.zeros((he, ws))
    col = np.empty(3)
    # atoms: |M⁻¹(p − c)| = 1 along the view's z, the GUI's atom shader
    for i in range(atom_c.shape[0]):
        iy0 = max(atom_box[i, 0], ext0)
        iy1 = min(atom_box[i, 1], ext1)
        if iy0 >= iy1:
            continue
        ix0 = max(atom_box[i, 2], 0)
        ix1 = min(atom_box[i, 3], ws)
        cx = atom_c[i, 0]
        cy = atom_c[i, 1]
        cz = atom_c[i, 2]
        m00 = atom_m[i, 0, 0]
        m01 = atom_m[i, 0, 1]
        e0 = atom_m[i, 0, 2]
        m10 = atom_m[i, 1, 0]
        m11 = atom_m[i, 1, 1]
        e1 = atom_m[i, 1, 2]
        m20 = atom_m[i, 2, 0]
        m21 = atom_m[i, 2, 1]
        e2 = atom_m[i, 2, 2]
        a = atom_a[i]
        for iy in range(iy0, iy1):
            y = y0 - (iy + 0.5) / pxs - cy
            for ix in range(ix0, ix1):
                x = x0 + (ix + 0.5) / pxs - cx
                q0 = m00 * x + m01 * y
                q1 = m10 * x + m11 * y
                q2 = m20 * x + m21 * y
                b = q0 * e0 + q1 * e1 + q2 * e2
                cc = q0 * q0 + q1 * q1 + q2 * q2 - 1.0
                disc = b * b - a * cc
                if disc < 0.0:
                    continue
                t = (-b + math.sqrt(disc)) / a
                z = cz + t
                row = iy - ext0
                if z < zb[row, ix]:
                    continue
                zb[row, ix] = z
                u0 = q0 + t * e0
                u1 = q1 + t * e1
                u2 = q2 + t * e2
                n0 = m00 * u0 + m10 * u1 + m20 * u2
                n1 = m01 * u0 + m11 * u1 + m21 * u2
                n2 = e0 * u0 + e1 * u1 + e2 * u2
                nn = math.sqrt(n0 * n0 + n1 * n1 + n2 * n2)
                _shade(atom_col[i, 0], atom_col[i, 1], atom_col[i, 2],
                       n0 / nn, n1 / nn, n2 / nn, look, col)
                if atom_ring[i] and min(abs(u0), min(abs(u1), abs(u2))) < look[8]:
                    if atom_lum[i] < look[9]:
                        for k in range(3):
                            col[k] = col[k] + look[10] * (1.0 - col[k])
                    else:
                        for k in range(3):
                            col[k] = col[k] * look[11]
                pm[row, ix, 0] = _clamp(col[0])
                pm[row, ix, 1] = _clamp(col[1])
                pm[row, ix, 2] = _clamp(col[2])
                al[row, ix] = 1.0
    # bond halves: open finite cylinders, the GUI's half shader
    for i in range(half_a.shape[0]):
        iy0 = max(half_box[i, 0], ext0)
        iy1 = min(half_box[i, 1], ext1)
        if iy0 >= iy1:
            continue
        ix0 = max(half_box[i, 2], 0)
        ix1 = min(half_box[i, 3], ws)
        ax = half_a[i, 0]
        ay = half_a[i, 1]
        az = half_a[i, 2]
        w0 = half_w[i, 0]
        w1 = half_w[i, 1]
        w2 = half_w[i, 2]
        f0 = half_e[i, 0]
        f1 = half_e[i, 1]
        f2 = half_e[i, 2]
        a = half_ea[i]
        r = half_r[i]
        length = half_len[i]
        for iy in range(iy0, iy1):
            o1 = y0 - (iy + 0.5) / pxs - ay
            for ix in range(ix0, ix1):
                o0 = x0 + (ix + 0.5) / pxs - ax
                o2 = -az
                oa = o0 * w0 + o1 * w1 + o2 * w2
                q0 = o0 - oa * w0
                q1 = o1 - oa * w1
                q2 = o2 - oa * w2
                b = q0 * f0 + q1 * f1 + q2 * f2
                disc = b * b - a * (q0 * q0 + q1 * q1 + q2 * q2 - r * r)
                if disc < 0.0:
                    continue
                z = (-b + math.sqrt(disc)) / a
                along = oa + z * w2
                if along < 0.0 or along > length:
                    continue
                row = iy - ext0
                if z < zb[row, ix]:
                    continue
                zb[row, ix] = z
                n0 = q0 + z * f0
                n1 = q1 + z * f1
                n2 = q2 + z * f2
                nn = math.sqrt(n0 * n0 + n1 * n1 + n2 * n2)
                _shade(half_col[i, 0], half_col[i, 1], half_col[i, 2],
                       n0 / nn, n1 / nn, n2 / nn, look, col)
                pm[row, ix, 0] = _clamp(col[0])
                pm[row, ix, 1] = _clamp(col[1])
                pm[row, ix, 2] = _clamp(col[2])
                al[row, ix] = 1.0
    _flat(line_p, line_half, line_dir, line_len, line_z, line_col, line_box, True,
          ext0, he, ws, zb, pm, al)
    if ow > 0:
        _outline(ext0, sr0, hs, ws, total, ow, otau, ocol, zb, pm)
    # polyhedron faces, already in drawing order: blended, depth-tested, and
    # writing no depth
    for i in range(tri_v.shape[0]):
        iy0 = max(tri_box[i, 0], ext0)
        iy1 = min(tri_box[i, 1], ext1)
        if iy0 >= iy1:
            continue
        ix0 = max(tri_box[i, 2], 0)
        ix1 = min(tri_box[i, 3], ws)
        ax = tri_v[i, 0, 0]
        ay = tri_v[i, 0, 1]
        bx = tri_v[i, 1, 0]
        by = tri_v[i, 1, 1]
        qx = tri_v[i, 2, 0]
        qy = tri_v[i, 2, 1]
        area = tri_area[i]
        for iy in range(iy0, iy1):
            y = y0 - (iy + 0.5) / pxs
            for ix in range(ix0, ix1):
                x = x0 + (ix + 0.5) / pxs
                ea = (qx - bx) * (y - by) - (qy - by) * (x - bx)
                eb = (ax - qx) * (y - qy) - (ay - qy) * (x - qx)
                ec = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
                if ea < 0.0 or (ea == 0.0 and not tri_tie[i, 0]):
                    continue
                if eb < 0.0 or (eb == 0.0 and not tri_tie[i, 1]):
                    continue
                if ec < 0.0 or (ec == 0.0 and not tri_tie[i, 2]):
                    continue
                z = (ea * tri_v[i, 0, 2] + eb * tri_v[i, 1, 2] + ec * tri_v[i, 2, 2]) / area
                row = iy - ext0
                if z < zb[row, ix]:
                    continue
                for k in range(3):
                    pm[row, ix, k] = alpha * tri_col[i, k] + (1.0 - alpha) * pm[row, ix, k]
                al[row, ix] = alpha + (1.0 - alpha) * al[row, ix]
    _flat(text_p, text_half, text_dir, text_len, text_z, text_col, text_box, False,
          ext0, he, ws, zb, pm, al)
    # the box filter, and the background or straight alpha
    n = float(s * s)
    for oy in range(r1 - r0):
        for ox in range(width):
            p0 = 0.0
            p1 = 0.0
            p2 = 0.0
            pa = 0.0
            for dy in range(s):
                for dx in range(s):
                    sy = sr0 - ext0 + oy * s + dy
                    sx = ox * s + dx
                    p0 += pm[sy, sx, 0]
                    p1 += pm[sy, sx, 1]
                    p2 += pm[sy, sx, 2]
                    pa += al[sy, sx]
            p0 = p0 / n
            p1 = p1 / n
            p2 = p2 / n
            pa = pa / n
            if has_bg:
                c0 = p0 + (1.0 - pa) * bg[0]
                c1 = p1 + (1.0 - pa) * bg[1]
                c2 = p2 + (1.0 - pa) * bg[2]
                ca = 1.0
            elif pa > 0.0:
                c0 = p0 / pa
                c1 = p1 / pa
                c2 = p2 / pa
                ca = pa
            else:
                c0 = 0.0
                c1 = 0.0
                c2 = 0.0
                ca = 0.0
            out[r0 + oy, ox, 0] = np.uint8(math.floor(_clamp(c0) * 255.0 + 0.5))
            out[r0 + oy, ox, 1] = np.uint8(math.floor(_clamp(c1) * 255.0 + 0.5))
            out[r0 + oy, ox, 2] = np.uint8(math.floor(_clamp(c2) * 255.0 + 0.5))
            out[r0 + oy, ox, 3] = np.uint8(math.floor(_clamp(ca) * 255.0 + 0.5))
