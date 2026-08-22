"""WP-1122 task 1: does the peaks buffer pay on the *compiled* substrate?

Run: ``.venv/bin/python examples/bench_compiled_buffer.py`` (needs ``numba``).

WP-1114 measured the buffer's physics and found it sound — a C² cubic spline
through greedily-placed anchors holds 1e-4 on area and both moments at K ≤ 32
anchors, on every harness case and at both ends of its trajectory — and then
recorded a NO-GO on **economics**: against batched numpy the buffer's gathers
carried multipliers (planes, taps, padding, the θ-spline over the stored grid)
that ate the volume they removed.  WP-1115 then replaced that substrate with
fused ``njit`` kernels, and the NO-GO's own reasoning says the verdict must be
re-taken there: a resample is a few fma per point where an exact element pays
an ``exp``, so the ratio a compiled buffer competes at is not the ratio a numpy
one did.

This script is that re-take, and nothing more.  It is the WP's task 1 — the
economics probe whose output is a go/no-go for building the mode — so it
measures **costs and ratios**, never accuracy: 1114 owns the accuracy result
and this file does not re-derive it.  Nothing here touches production code.

What is measured
----------------
Three things, per harness case, at the state the cold fit *starts* from:

``exact``    the shipped compiled plane seam on that case's own frozen rows:
             ``CompiledModel._omega_batch`` (the forward Ω) and the profile
             half of ``derivative_bases`` (Ω plus its three partials), each
             timed whole — FCJ node generation included, because the buffer
             removes that for every row that is not an anchor and a comparison
             that hid it would understate the buffer.
``buffered`` the same two planes reconstructed from anchors, in three timed
             parts: the exact anchor planes (numpy, K × images × n_stored
             elements), the prefilter + θ-spline build, and a fused ``njit``
             reconstruction kernel over the same rows.  The anchors, the
             stored grid and its step come from WP-1114's own prototype
             (:mod:`bench_peaks_buffer`), unchanged, so the shapes priced here
             are the shapes that met 1e-4.
``ratio``    the two, per plane seam, and what that buys on a whole fit once
             the measured seam shares are applied.

The reconstruction kernel is timed in **both** orderings, because which one
wins is a property of the case rather than of the design, and the buffer is
credited with the faster:

``point``    per (row, window point), four B-spline taps, each tap a Horner in
             the segment coordinate over all planes — 4 taps × 4 powers ×
             ``n_planes`` fma, no scratch.
``slice``    the θ-spline evaluated once per *stored* sample over the row's
             span into a scratch buffer, then four taps read it — 4 × n_planes
             fma per stored sample plus 4 per window point.  Cheaper exactly
             when the stored grid is coarser than four samples per window
             point, i.e. when ``rho = pattern step / stored step`` is under 4.

``rho`` is printed for every case because it is the whole of that trade, and it
is not a free parameter: the stored step is ``min(pattern step, Γ_min/16)``,
and the /16 is 1114's trap 2 — the O(h⁴) constant lives in σ = Γ/2.355 units,
so /4 was measurably 1e-3-wrong.

What this file does **not** claim
---------------------------------
The reconstruction kernel here is a *cost model with the right memory
traffic*, not the mode: it reads real coefficient arrays at real strides and
writes a real plane, and it is checked against the prototype's numpy
reconstruction (``--check``) so that what is timed is arithmetic that produces
the right answer.  But it takes the anchor planes as given, skips the NaN and
pad masking a shipped path owes, and computes the forward planes only for a
phase at a time.  Every one of those omissions makes the buffer look *better*,
which is the direction a go/no-go probe should err in: if it does not pay here,
it does not pay.

Wall clock is a range, never a figure, and is a property of one machine on one
day (root CLAUDE.md § Commands).  Run it idle and alone.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from rietx import _about  # noqa: E402

# **Everything here is timed serially**, and the setting must land before any
# pool is built.  Both sides of this comparison are row-parallel over disjoint
# output rows, so threading multiplies them together and cancels out of the
# ratio — but ``compiled._spread`` only engages the pool above
# ``_THREAD_MIN_ROWS`` (512), and the exact path splits by FCJ *bucket* while a
# reconstruction splits by row.  Left alone, a 564-row phase compares a
# threaded buffer against a serial exact path and reports a win that is the
# pool's.
os.environ.setdefault(_about.COMPILED_THREADS_ENV, "1")

import bench_peaks_buffer as proto  # noqa: E402

from rietx.model import compiled  # noqa: E402

#: Seam shares of a trigger cold fit, measured by ``bench_compiled_kernel.py
#: --seams`` on the tree this WP opened on (2026-08-22, darwin/arm64, `[dev]`
#: venv): forward 22.1 %, bases 32.8 %, so the plane seam this buffer attacks
#: is 54.9 % of wall and everything else is out of its reach.  Re-measure
#: rather than trusting these; they are here so the projection is arithmetic a
#: reader can check, not a number this script invents.
SEAM_FORWARD = 0.221
SEAM_BASES = 0.328

#: Planes a reconstruction needs.  The forward wants Ω alone, which the Taylor
#: form builds from three (S, S_Γ, S_η); the bases want Ω and its three
#: partials, which adds S_x and the spline's own θ-derivative.
N_PLANES_FORWARD = 3
N_PLANES_BASES = 5


# -- the reconstruction kernels ----------------------------------------------

def _build_kernels():
    """Compile the two reconstruction orderings, or ``None`` without numba."""
    try:
        from numba import njit
    except Exception:  # pragma: no cover - depends on the install
        return None

    kw = {"cache": True, "nogil": True, "fastmath": False}

    @njit(**kw)
    def _taps(t):
        t2 = t * t
        t3 = t2 * t
        return ((1.0 - 3.0 * t + 3.0 * t2 - t3) / 6.0,
                (4.0 - 6.0 * t2 + 3.0 * t3) / 6.0,
                (1.0 + 3.0 * t + 3.0 * t2 - 3.0 * t3) / 6.0,
                t3 / 6.0)

    @njit(**kw)
    def _point(out, x, width, pos, seg, dts, cmb, coef, half, h, n_stored,
               lo, hi):
        """Four taps per window point; each tap a Horner over every plane.

        ``coef`` is (n_seg, n_stored, n_planes, 4) — the segment's cubic
        coefficients, plane-major then power-major, which is the layout that
        makes one tap one contiguous read.  ``cmb`` is the per-row plane
        combination (1, ΔΓ, Δη, …) the Taylor form applies, so the plane sum
        and the θ evaluation happen in the same pass.
        """
        n_planes = cmb.shape[1]
        for r in range(lo, hi):
            p = pos[r]
            s = seg[r]
            dt = dts[r]
            w = width[r]
            for c in range(w):
                u = (x[r, c] - p + half) / h
                i = int(np.floor(u))
                if i < 1:
                    i = 1
                elif i > n_stored - 3:
                    i = n_stored - 3
                t = u - i
                w0, w1, w2, w3 = _taps(t)
                acc = 0.0
                for tap in range(4):
                    j = i - 1 + tap
                    v = 0.0
                    for q in range(n_planes):
                        g = cmb[r, q]
                        if g == 0.0:
                            continue
                        e = coef[s, j, q, 0]
                        e = e * dt + coef[s, j, q, 1]
                        e = e * dt + coef[s, j, q, 2]
                        e = e * dt + coef[s, j, q, 3]
                        v += g * e
                    if tap == 0:
                        acc += w0 * v
                    elif tap == 1:
                        acc += w1 * v
                    elif tap == 2:
                        acc += w2 * v
                    else:
                        acc += w3 * v
                out[r, c] = acc

    @njit(**kw)
    def _slice(out, x, width, pos, seg, dts, cmb, coef, half, h, n_stored,
               scratch, lo, hi):
        """The θ-spline once per stored sample over the row's span, then taps.

        Cheaper than :func:`_point` exactly when the row's span costs fewer
        than four stored samples per window point.  The scratch is per worker
        and sized to the stored grid, so nothing is allocated per row.
        """
        n_planes = cmb.shape[1]
        for r in range(lo, hi):
            p = pos[r]
            s = seg[r]
            dt = dts[r]
            w = width[r]
            u0 = (x[r, 0] - p + half) / h
            u1 = (x[r, w - 1] - p + half) / h
            j0 = int(np.floor(u0)) - 1
            j1 = int(np.floor(u1)) + 3
            if j0 < 0:
                j0 = 0
            if j1 > n_stored:
                j1 = n_stored
            for j in range(j0, j1):
                v = 0.0
                for q in range(n_planes):
                    g = cmb[r, q]
                    if g == 0.0:
                        continue
                    e = coef[s, j, q, 0]
                    e = e * dt + coef[s, j, q, 1]
                    e = e * dt + coef[s, j, q, 2]
                    e = e * dt + coef[s, j, q, 3]
                    v += g * e
                scratch[r, j - j0] = v
            for c in range(w):
                u = (x[r, c] - p + half) / h
                i = int(np.floor(u))
                if i < 1:
                    i = 1
                elif i > n_stored - 3:
                    i = n_stored - 3
                t = u - i
                w0, w1, w2, w3 = _taps(t)
                b = i - 1 - j0
                out[r, c] = (w0 * scratch[r, b]
                             + w1 * scratch[r, b + 1]
                             + w2 * scratch[r, b + 2]
                             + w3 * scratch[r, b + 3])

    z2 = np.zeros((1, 1))
    zi = np.zeros(1, dtype=np.int64)
    c4 = np.zeros((1, 4, 1, 4))
    _point(z2, z2, zi, np.zeros(1), zi, np.zeros(1), z2, c4, 0.0, 1.0, 4, 0, 1)
    _slice(z2, z2, zi, np.zeros(1), zi, np.zeros(1), z2, c4, 0.0, 1.0, 4,
           np.zeros((1, 8)), 0, 1)
    return {"point": _point, "slice": _slice}


# -- timing ------------------------------------------------------------------

def _best(fn, reps: int = 5) -> tuple[float, float]:
    """(min, max) seconds over ``reps`` calls, one warm call discarded."""
    fn()
    out = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        out.append(time.perf_counter() - t0)
    return min(out), max(out)


@dataclass
class PhaseCost:
    """What one phase costs each way, in seconds per evaluation."""

    key: str
    ip: int
    rows: int
    points: int          # Σ window width over rows
    elements: int        # Σ window width × FCJ images over rows
    k_anchors: int
    n_stored: int
    rho: float
    anchor_elements: int
    exact_fwd: tuple[float, float]
    exact_bases: tuple[float, float]
    buf_anchor: tuple[float, float]
    buf_spline: tuple[float, float]
    buf_recon_fwd: tuple[float, float]
    buf_recon_bases: tuple[float, float]
    recon_order: str
    check: float

    @property
    def exact_plane(self) -> float:
        """One forward Ω build plus one bases build, the seam being replaced."""
        return self.exact_fwd[0] + self.exact_bases[0]

    @property
    def anchor_ideal(self) -> float:
        """One anchor-plane build at the exact path's own per-element cost.

        Priced against the *bases* element because an anchor carries four
        planes (S, S_Γ, S_η, S_x), which is what ``bases_fcj`` computes in its
        single pass — the same arithmetic a shipped mode would reuse rather
        than the numpy loop this probe borrowed from 1114's prototype.
        """
        return self.anchor_elements * self.exact_bases[0] / max(self.elements, 1)

    @property
    def break_even_images(self) -> float:
        """FCJ images per window point at which the buffer would break even.

        The buffer replaces ``Σwin × images`` exact elements with an anchor
        build plus one reconstruction per window point, so what decides it is
        not the tolerance and not the anchor count but how many images a point
        carries.  Below this figure the exact path is cheaper *however* well
        the mode is implemented; a symmetric family (one image) is therefore
        never a candidate, which is a structural fact rather than a tuning
        one.
        """
        e = self.exact_fwd[0] / max(self.elements, 1)
        b = self.exact_bases[0] / max(self.elements, 1)
        anchor = 2 * self.anchor_elements * b / max(self.points, 1)
        recon = ((self.buf_recon_fwd[0] + self.buf_recon_bases[0])
                 / max(self.points, 1))
        return (anchor + recon) / (e + b)

    @property
    def buffer_built(self) -> float:
        """The buffer as this probe builds it — numpy anchors and spline."""
        return (2 * (self.buf_anchor[0] + self.buf_spline[0])
                + self.buf_recon_fwd[0] + self.buf_recon_bases[0])

    @property
    def buffer_ideal(self) -> float:
        """The buffer with a compiled anchor build and a free spline build.

        The anchor planes are charged **twice** — once per plane-seam call —
        because the forward and the bases are evaluated at different θ more
        often than not (trigger: 232 residual against 190 Jacobian
        evaluations), so a state cache keyed on the scalars hits only where
        they coincide.  A mode that could share every build would save at most
        one of the two anchor terms.
        """
        return (2 * self.anchor_ideal + self.buf_recon_fwd[0]
                + self.buf_recon_bases[0])


# -- the buffered path, priced ------------------------------------------------

def _coefficients(buf, model, fam, n_planes: int):
    """(n_seg, n_stored, n_planes, 4) cubic coefficients, kernel layout.

    The prototype's ``_state`` builds exactly these — anchor planes, Unser
    prefilter, ``CubicSpline`` in θ — and this only re-lays them out so a tap
    is one contiguous read.  The θ-derivative plane the bases need is the
    spline's own derivative, which is the same coefficients shifted, so it is
    built here rather than differenced.
    """
    from scipy.interpolate import CubicSpline
    from scipy.ndimage import spline_filter1d

    planes = buf._anchor_planes(model, fam, False, 0)      # (K, 4, n_stored)
    planes = spline_filter1d(planes, order=3, axis=2, mode="mirror")
    spline = CubicSpline(buf.anchors, planes, axis=0)
    c = spline.c                                           # (4, K-1, 4, n_st)
    if n_planes == N_PLANES_FORWARD:
        take = [0, 1, 2]                                   # S, S_Γ, S_η
    else:
        take = [0, 1, 2, 3, 0]                             # + S_x, + S_θ slot
    out = np.ascontiguousarray(
        np.transpose(c[:, :, take, :], (1, 3, 2, 0)))
    return out, spline


def _row_state(buf, model, ip, values, peaks, fam, n_planes: int):
    """Per-row (segment, segment coordinate, plane combination).

    This is the scalar work a shipped mode would do per row per evaluation:
    where the row's position falls among the anchors, and how far its widths
    have drifted from the law at that position (the Taylor term).  It is
    numpy here and it is not what this probe is pricing, so it stays outside
    the timed reconstruction.
    """
    lay = model.phases[ip].batch
    pos = lay.gather(peaks, 0)
    w1 = lay.gather(peaks, 1)
    w2 = lay.gather(peaks, 2)
    finite = np.isfinite(pos)
    pos_c = np.clip(np.where(finite, pos, 0.5 * (buf.lo + buf.hi)),
                    buf.lo, buf.hi)
    seg = np.clip(np.searchsorted(buf.anchors, pos_c) - 1, 0,
                  len(buf.anchors) - 2).astype(np.int64)
    dts = pos_c - buf.anchors[seg]
    g_law, e_law = (np.asarray(a, dtype=np.float64) for a in fam.widths(pos_c))
    cmb = np.zeros((len(pos_c), n_planes))
    cmb[:, 0] = 1.0
    cmb[:, 1] = w1 - g_law
    cmb[:, 2] = w2 - e_law
    if n_planes == N_PLANES_BASES:
        # the two extra planes carry unit weight in the bases combination —
        # what matters to a cost model is that they are read and combined
        cmb[:, 3] = 1.0
        cmb[:, 4] = 1.0
    return pos_c, seg, dts, np.ascontiguousarray(cmb)


def price_phase(study, ip: int, kernels, reps: int) -> PhaseCost | None:
    """Time the exact and buffered plane seams for one phase."""
    model, values = study.model, study.values
    fam = proto.ShapeFamily(model, values, ip)
    lay = model.phases[ip].batch
    peaks = model.phase_peaks(ip, values)
    pos = lay.gather(peaks, 0)
    w1 = lay.gather(peaks, 1)
    w2 = lay.gather(peaks, 2)
    finite = np.isfinite(pos)
    sl = values["instrument.geometry.axial_sl"]
    hl = values["instrument.geometry.axial_hl"]

    width = lay.width.astype(np.int64)
    images = np.where(lay.fcj > 0, lay.fcj, 1).astype(np.int64)
    n_points = int(width.sum())
    n_elements = int((width * images).sum())

    exact_fwd = _best(lambda: model._omega_batch(
        lay, pos, w1, w2, finite, sl, hl, compiled.SPELL_FORWARD), reps)
    exact_bases = _best(lambda: _exact_bases(model, lay, pos, w1, w2, finite,
                                             sl, hl), reps)

    buf = proto.PeaksBuffer(model, ip, values)
    n_stored = len(buf.grid)
    step = float(np.median(np.diff(model.tt)))
    rho = step / buf.h

    coef_f, _ = _coefficients(buf, model, fam, N_PLANES_FORWARD)
    coef_b, _ = _coefficients(buf, model, fam, N_PLANES_BASES)
    anchor_elements = int(sum(max(n, 1) for n in buf.n_nodes) * n_stored)

    buf_anchor = _best(
        lambda: buf._anchor_planes(model, fam, False, 0), max(reps // 2, 2))
    buf_spline = _best(
        lambda: _coefficients(buf, model, fam, N_PLANES_FORWARD),
        max(reps // 2, 2))
    # the anchor planes are inside _coefficients too; charge the spline build
    # only for what it adds
    buf_spline = (max(buf_spline[0] - buf_anchor[0], 0.0),
                  max(buf_spline[1] - buf_anchor[1], 0.0))

    out = np.zeros((len(lay.i0), lay.w_max))
    best_order = None
    best_fwd = None
    best_bases = None
    for order in ("point", "slice"):
        fwd = _time_recon(kernels, order, out, lay, buf, coef_f, model, ip,
                          values, peaks, fam, N_PLANES_FORWARD, reps)
        bas = _time_recon(kernels, order, out, lay, buf, coef_b, model, ip,
                          values, peaks, fam, N_PLANES_BASES, reps)
        if best_fwd is None or fwd[0] + bas[0] < best_fwd[0] + best_bases[0]:
            best_order, best_fwd, best_bases = order, fwd, bas

    check = _check(kernels, out, lay, buf, coef_f, model, ip, values, peaks,
                   fam)
    return PhaseCost(study.key, ip, len(lay.i0), n_points, n_elements,
                     len(buf.anchors), n_stored, rho, anchor_elements,
                     exact_fwd, exact_bases, buf_anchor, buf_spline, best_fwd,
                     best_bases, best_order, check)


def _exact_bases(model, lay, pos, w1, w2, finite, sl, hl):
    """The profile half of ``derivative_bases`` — Ω and its three partials.

    Called through the same compiled entry points ``derivative_bases`` uses,
    on the same rows, so what is timed is the seam the buffer would replace
    and not a re-implementation of it.
    """
    from rietx.model.profiles.fcj import fcj_offsets_weights_batch

    shape = (len(lay.i0), lay.w_max)
    omega = np.zeros(shape)
    d_pos = np.zeros(shape)
    d_gamma = np.zeros(shape)
    d_eta = np.zeros(shape)
    srows = lay.buckets.get(0, np.zeros(0, dtype=np.int64))
    if len(srows):
        compiled.bases_symmetric(omega, d_pos, d_gamma, d_eta, lay.x, srows,
                                 pos, w1, w2, lay.width)
    for n, rows_b in lay.buckets.items():
        if n == 0:
            continue
        phi, om = fcj_offsets_weights_batch(pos[rows_b], sl, hl, n)
        h = 1e-6
        phi_p, om_p = fcj_offsets_weights_batch(pos[rows_b] + h, sl, hl, n)
        dphi = (phi_p - phi) / h
        dom = (om_p - om) / h
        compiled.bases_fcj(omega, d_pos, d_gamma, d_eta, None, None, lay.x,
                           rows_b, w1, w2, lay.width, phi, om, dphi, dom, None)
    return omega


def _recon_args(kernels, out, lay, buf, coef, model, ip, values, peaks, fam,
                n_planes):
    pos_c, seg, dts, cmb = _row_state(buf, model, ip, values, peaks, fam,
                                      n_planes)
    return (out, lay.x, lay.width.astype(np.int64), pos_c, seg, dts, cmb,
            coef, buf.half, buf.h, len(buf.grid))


def _time_recon(kernels, order, out, lay, buf, coef, model, ip, values, peaks,
                fam, n_planes, reps):
    args = _recon_args(kernels, out, lay, buf, coef, model, ip, values, peaks,
                       fam, n_planes)
    n_rows = len(lay.i0)
    fn = kernels[order]
    if order == "point":
        def run():
            fn(*args, 0, n_rows)
    else:
        span = int(np.ceil(lay.w_max * (float(np.median(np.diff(model.tt)))
                                        / buf.h))) + 8
        # allocated once, outside the timing: a shipped mode would hold this
        # on the compiled phase, and charging the buffer for a per-call
        # allocation would price a scaffold rather than the arithmetic
        scratch = np.zeros((n_rows, span))

        def run():
            fn(*args, scratch, 0, n_rows)
    return _best(run, reps)


def _check(kernels, out, lay, buf, coef, model, ip, values, peaks, fam):
    """Max deviation of the kernel's Ω from the prototype's numpy Ω.

    Not an accuracy result — 1114 owns those — but the thing that says the
    timings above are timings of the right arithmetic.  Compared in-window
    only, and on the finite rows: the pad tail and the NaN rows are masked
    downstream by both paths.
    """
    args = _recon_args(kernels, out, lay, buf, coef, model, ip, values, peaks,
                       fam, N_PLANES_FORWARD)
    out[:] = 0.0
    kernels["point"](*args, 0, len(lay.i0))
    mine = out.copy()
    ref = buf.planes(model, ip, values, peaks, profile_derivs=False)["omega"]
    dev = 0.0
    finite = np.isfinite(lay.gather(peaks, 0))
    for r in range(len(lay.i0)):
        if not finite[r]:
            continue
        w = int(lay.width[r])
        scale = max(float(np.max(np.abs(ref[r, :w]))), 1e-300)
        dev = max(dev, float(np.max(np.abs(mine[r, :w] - ref[r, :w]))) / scale)
    return dev


# -- reporting ---------------------------------------------------------------

def _header() -> None:
    print(f"{_about.DIST_NAME} {version(_about.DIST_NAME)} · numpy "
          f"{np.__version__} · python {platform.python_version()} · "
          f"{sys.platform}/{platform.machine()}")
    print(f"compiled tier: {'on' if compiled.enabled() else 'OFF'} · "
          f"{compiled.n_threads()} threads · best-of-N, wall clock as a RANGE")
    print()


def report(costs: list[PhaseCost]) -> None:
    print("  per-phase shapes and volume")
    print(f"  {'case':22s} {'ip':>2s} {'rows':>5s} {'Σwin':>8s} {'Σelem':>9s} "
          f"{'img':>5s} {'K':>3s} {'n_st':>5s} {'rho':>5s} {'anchor':>8s} "
          f"{'vol×':>6s}")
    for c in costs:
        img = c.elements / max(c.points, 1)
        vol = c.elements / max(c.anchor_elements, 1)
        print(f"  {c.key:22s} {c.ip:2d} {c.rows:5d} {c.points:8d} "
              f"{c.elements:9d} {img:5.2f} {c.k_anchors:3d} {c.n_stored:5d} "
              f"{c.rho:5.2f} {c.anchor_elements:8d} {vol:6.2f}")
    print()
    print("  per-element / per-point costs (ns) and the seam ratio")
    print(f"  {'case':22s} {'ip':>2s} {'ex/elem':>8s} {'bs/elem':>8s} "
          f"{'rc/pt':>7s} {'ord':>5s} {'built×':>7s} {'ideal×':>7s} "
          f"{'img':>5s} {'img*':>6s} {'check':>9s}")
    for c in costs:
        ex_e = c.exact_fwd[0] / max(c.elements, 1) * 1e9
        bs_e = c.exact_bases[0] / max(c.elements, 1) * 1e9
        rc_p = c.buf_recon_fwd[0] / max(c.points, 1) * 1e9
        built = c.exact_plane / c.buffer_built
        ideal = c.exact_plane / c.buffer_ideal
        img = c.elements / max(c.points, 1)
        print(f"  {c.key:22s} {c.ip:2d} {ex_e:8.2f} {bs_e:8.2f} {rc_p:7.2f} "
              f"{c.recon_order:>5s} {built:7.2f} {ideal:7.2f} {img:5.2f} "
              f"{c.break_even_images:6.2f} {c.check:9.1e}")
    print()
    print("  built× is this probe as it stands: the anchor planes and the "
          "θ-spline are numpy,")
    print("  which a shipped mode would compile.  ideal× prices the anchor "
          "planes at the exact")
    print("  path's own measured per-element cost and the spline build at "
          "zero — the buffer's")
    print("  best case, and the number the go/no-go is taken on.  img* is "
          "the images per window")
    print("  point at which ideal× would reach 1: a family carrying fewer "
          "cannot pay at any")
    print("  tolerance, and a symmetric one (img 1.00) can never be a "
          "candidate.")
    print()
    print("  buffer cost split (µs per evaluation, forward + bases)")
    print(f"  {'case':22s} {'ip':>2s} {'exact':>9s} {'anchor':>9s} "
          f"{'spline':>9s} {'recon':>9s} {'anchor*':>9s}")
    for c in costs:
        print(f"  {c.key:22s} {c.ip:2d} {c.exact_plane * 1e6:9.1f} "
              f"{2 * c.buf_anchor[0] * 1e6:9.1f} "
              f"{2 * c.buf_spline[0] * 1e6:9.1f} "
              f"{(c.buf_recon_fwd[0] + c.buf_recon_bases[0]) * 1e6:9.1f} "
              f"{c.anchor_ideal * 1e6:9.1f}")
    print()


def project(costs: list[PhaseCost], wall: dict[str, tuple[float, float]]
            ) -> None:
    """Per case: the plane-seam ratio, and what Amdahl leaves of it."""
    print("  projected fit-level effect (measured seam shares: forward "
          f"{SEAM_FORWARD:.1%}, bases {SEAM_BASES:.1%})")
    print(f"  {'case':16s} {'wall (s)':>10s} {'plane×':>7s} {'sel×':>6s} "
          f"{'proj (s)':>9s} {'whole×':>7s} {'ceiling×':>9s} {'<1 s?':>7s}")
    seam = SEAM_FORWARD + SEAM_BASES
    ceiling = 1.0 / (1.0 - seam)
    by_case: dict[str, list[PhaseCost]] = {}
    for c in costs:
        by_case.setdefault(c.key.split(" @ ")[0], []).append(c)
    for key, group in by_case.items():
        ex = sum(c.exact_plane for c in group)
        ratio = ex / sum(c.buffer_ideal for c in group)
        # per width family, at compile, from the measured element volume: a
        # family the buffer would slow down keeps the exact path (the WP's own
        # rule — the lab cases must be shown unharmed, not merely unimproved)
        sel = ex / sum(min(c.buffer_ideal, c.exact_plane) for c in group)
        lo, _hi = wall.get(key, (float("nan"), float("nan")))
        proj = lo * ((1.0 - seam) + seam / sel)
        whole = lo / proj if proj else float("nan")
        # the stretch is a claim about a *cold trigger-shaped* fit; a case
        # already under a second was never what it was asked of
        hit = "n/a" if lo < 1.0 else ("yes" if proj < 1.0 else "no")
        print(f"  {key:16s} {lo:10.2f} {ratio:7.2f} {sel:6.2f} {proj:9.2f} "
              f"{whole:7.2f} {ceiling:9.2f} {hit:>7s}")
    print()
    print("  plane× buffers every phase; sel× buffers only the phases whose "
          "own volume pays,")
    print("  which is the per-family decision the WP already requires, and "
          "is what proj uses.")
    print("  'ceiling' is the whole-fit speedup a plane seam of ZERO cost "
          "would give — the")
    print("  Amdahl bound this WP cannot cross, whatever the buffer's own "
          "ratio turns out to be.")


#: harness wall clock, re-measured on this tree before the probe ran; the
#: projection multiplies these, so they are quoted rather than assumed
WALL = {
    "nac": (0.34, 0.35),
    "cpd-1a": (1.49, 1.52),
    "cpd-2": (2.27, 2.29),
    "trigger": (5.68, 5.81),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", default="nac,cpd-1a,cpd-2,trigger",
                    help="comma-separated harness case keys")
    ap.add_argument("--reps", type=int, default=5,
                    help="timed repeats per measurement (default 5)")
    ap.add_argument("--phases", type=int, default=0,
                    help="phases per case to price, 0 = all")
    args = ap.parse_args(argv)

    kernels = _build_kernels()
    if kernels is None:
        print("numba is absent — this probe measures the compiled substrate "
              "and has nothing to say without it")
        return 1
    _header()

    keys = [k.strip() for k in args.cases.split(",") if k.strip()]
    costs: list[PhaseCost] = []
    for study in proto.build_studies(keys, start_only=True):
        n = len(study.model.phases)
        if args.phases:
            n = min(n, args.phases)
        for ip in range(n):
            cost = price_phase(study, ip, kernels, args.reps)
            if cost is not None:
                costs.append(cost)
    report(costs)
    project(costs, WALL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
