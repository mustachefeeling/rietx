"""WP-1115: the compiled-kernel spike — what numba buys over batched numpy.

Run: ``.venv/bin/python examples/bench_compiled_kernel.py`` (needs ``numba``;
it is not a dependency of this package, which is the point of the spike).
Four modes: the default benches the two profile kernels with a thread ladder,
``--accum`` the column seam's scatter on inputs captured from a real fit,
``--nogil`` the serial-plus-thread-pool alternative to ``parallel=True``
(**run it twice** — the question is whether the disk cache hits), and
``--seams`` decomposes a whole trigger cold fit into the shares all of the
above are weighed against.

**Reported, never gated.**  No test asserts any timing here, for the reason
``bench_torch_mps.py`` states: wall clock is a property of one machine on one
day.  What *is* asserted is agreement, and the agreement column below is the
equivalence bar — the fused kernels reproduce the numpy planes to a few ulp,
which is the bar WP-1112 set for FCJ rows and no weaker.

Why this benchmark exists
-------------------------
WP-1115's gate asks whether the gap between the WP-1111 harness and the v1.1
targets sits in the numpy peak kernel or somewhere else, and if it is the
kernel, whether a compiled tier can close it.  The gate's own Context named
two mechanisms — python dispatch and ragged (FCJ node) axes — and this
session measured **both of them small**: after WP-1112/1120 the kernel calls
are 200-400 µs each on ~10⁵-element planes, so dispatch is noise, and the
evaluation-weighted padding of the (node × window) kernel volume is 1.11×.

What is left is the mechanism numpy cannot address at all: **fusion**.
``pseudo_voigt`` alone materialises around a dozen full-size temporaries per
call and ``pseudo_voigt_derivs`` more, every one of them a write and a read
of a (rows, nodes, window) plane, and numpy has no way to keep them in
registers.  A compiled loop keeps all of it in registers and touches the
grid once.  The second is **threading**, which the GIL denies a numpy-level
python loop entirely.

What is measured
----------------
Two kernels, both on the harness's ``trigger`` case at its starting model,
both excluding FCJ node *generation* (which neither path changes):

``forward``  Ω over each row's frozen window, node-mixed, scattered into the
             pattern — ``CompiledModel._omega_batch`` + ``accumulate_planes``
             against one fused loop.  Rows scatter into overlapping windows,
             so the threaded variant gives each worker a private output and
             sums them; that reduction is inside the timing, not hidden.
``bases``    the four node-mixed planes ``derivative_bases`` builds from
             ``pseudo_voigt_derivs`` (Ω and ∂Ω/∂x, ∂Ω/∂Γ, ∂Ω/∂η).  Here rows
             write disjoint output slices, so the threaded variant needs no
             reduction and scales further.

The comparison is **in-window only**.  numpy's padded tail carries the
clipped duplicate that ``BatchLayout.mask`` zeroes downstream; the fused loop
never writes it.  Comparing the tail would compare a real value against an
untouched zero and report a disagreement that is not one.

The profile spelling is the caller's, here as everywhere: the forward kernel
reproduces ``pseudo_voigt`` and the bases kernel reproduces ``_components``,
which are deliberately 1-2 ulp apart (root CLAUDE.md § Conventions).  A
fused kernel that borrowed the other one would move every converged fit.

**This script switches the shipped tier off** (``compiled.set_enabled(False)``,
below the imports).  It is the prototype harness the WP-1115 decision was taken
on, so its "numpy" column has to be numpy; left alone it would now be the
shipped kernels measuring themselves and every ratio would read 1.0×.  What
the *shipped* tier is worth is a different measurement and belongs to
``bench_refinement.py``, run twice with and without ``RIETX_COMPILED=0``.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.model.forward import (  # noqa: E402
    CompiledModel,
    accumulate_planes,
    compile_model,
)
from rietx.model.profiles.fcj import fcj_offsets_weights_batch  # noqa: E402
from rietx.model.profiles.pseudovoigt import pseudo_voigt_derivs  # noqa: E402
from rietx.optimize import least_squares as lsq  # noqa: E402
from rietx.params.vector import ParameterTable  # noqa: E402

# the "numpy" column must be numpy: see the docstring's last paragraph
compiled.set_enabled(False)

_SQRT_LN2_PI = math.sqrt(math.log(2.0) / math.pi)
_4LN2 = 4.0 * math.log(2.0)


def _nogil_kernel():
    """The bases kernel as a *serial* ``nogil`` range kernel, for ``--nogil``.

    ``parallel=True`` is what refuses to cache — it recompiles every process,
    which is most of the startup cost a shipped compiled tier would impose.
    A serial kernel over a row range, with the GIL released, caches like any
    other and can be driven from a Python thread pool instead.  Same
    arithmetic as ``bases_parallel``; only the parallelism moves out.
    """
    from numba import njit

    @njit(cache=True, nogil=True)
    def bases_range(tt, i0, i1, pos, gam, eta, nptr, nphi, nom,
                    om_p, dx_p, dg_p, de_p, lo, hi):
        for j in range(lo, hi):
            g, e, p = gam[j], eta[j], pos[j]
            a, b = nptr[j], nptr[j + 1]
            base = i0[j]
            for i in range(i0[j], i1[j]):
                s0 = s1 = s2 = s3 = 0.0
                if b == a:
                    u = (tt[i] - p) / g
                    lor = (2.0 / (math.pi * g)) / (1.0 + 4.0 * u * u)
                    gau = (2.0 / g) * _SQRT_LN2_PI * math.exp(-_4LN2 * u * u)
                    s0 = e * lor + (1.0 - e) * gau
                    s1 = (e * (-lor * (8.0 * u / g) / (1.0 + 4.0 * u * u))
                          + (1.0 - e) * (-gau * (2.0 * _4LN2 * u / g)))
                    s2 = (e * ((lor / g) * (8.0 * u * u
                                            / (1.0 + 4.0 * u * u) - 1.0))
                          + (1.0 - e) * ((gau / g)
                                         * (2.0 * _4LN2 * u * u - 1.0)))
                    s3 = lor - gau
                else:
                    for q in range(a, b):
                        w = nom[q]
                        u = (tt[i] - nphi[q]) / g
                        lor = (2.0 / (math.pi * g)) / (1.0 + 4.0 * u * u)
                        gau = ((2.0 / g) * _SQRT_LN2_PI
                               * math.exp(-_4LN2 * u * u))
                        s0 += w * (e * lor + (1.0 - e) * gau)
                        s1 += w * (e * (-lor * (8.0 * u / g)
                                        / (1.0 + 4.0 * u * u))
                                   + (1.0 - e) * (-gau * (2.0 * _4LN2 * u / g)))
                        s2 += w * (e * ((lor / g) * (8.0 * u * u
                                                     / (1.0 + 4.0 * u * u)
                                                     - 1.0))
                                   + (1.0 - e) * ((gau / g)
                                                  * (2.0 * _4LN2 * u * u
                                                     - 1.0)))
                        s3 += w * (lor - gau)
                c = i - base
                om_p[j, c] = s0
                dx_p[j, c] = s1
                dg_p[j, c] = s2
                de_p[j, c] = s3

    return bases_range


def _accum_kernel():
    """The fused twin of :func:`accumulate_planes`, for ``--accum``.

    ``np.bincount`` accumulates sequentially from its input, which
    ``accumulate_planes`` lays out row-major as (row, term, point).  A serial
    loop in that same order is therefore **bit-identical** to it, not merely
    close — which is a stronger equivalence bar than either profile kernel
    can offer, and the mode checks it rather than asserting it.
    """
    from numba import njit

    @njit(cache=True)
    def fused_accum(y, idx, i0, i1, coefs, planes, n_terms):
        for r in range(len(i0)):
            for t in range(n_terms):
                c = coefs[t, r]
                for p in range(i1[r] - i0[r]):
                    y[idx[r, p]] += c * planes[t, r, p]
        return y

    return fused_accum


def _kernels():
    """Compile the two fused kernels, or explain why we cannot.

    Built inside a function so the module imports without numba: this script
    is in ``examples/`` and ``ruff`` and the docs tooling read it there.
    """
    from numba import njit, prange

    @njit(inline="always", cache=True)
    def pv(x, g, eta):
        """``pseudo_voigt`` in the forward's own spelling."""
        u = x / g
        lor = (2.0 / (math.pi * g)) / (1.0 + 4.0 * u * u)
        gau = (2.0 / g) * _SQRT_LN2_PI * math.exp(-_4LN2 * u * u)
        return eta * lor + (1.0 - eta) * gau

    @njit(cache=True)
    def forward_serial(tt, i0, i1, pos, gam, eta, inten, nptr, nphi, nom, y):
        for j in range(len(i0)):
            g, e, amp, p = gam[j], eta[j], inten[j], pos[j]
            a, b = nptr[j], nptr[j + 1]
            for i in range(i0[j], i1[j]):
                acc = 0.0
                if b == a:
                    acc = pv(tt[i] - p, g, e)
                else:
                    for q in range(a, b):
                        acc += nom[q] * pv(tt[i] - nphi[q], g, e)
                y[i] += amp * acc
        return y

    @njit(cache=True, parallel=True)
    def forward_parallel(tt, i0, i1, pos, gam, eta, inten, nptr, nphi, nom,
                         npts, nchunk):
        part = np.zeros((nchunk, npts))
        n = len(i0)
        per = (n + nchunk - 1) // nchunk
        for c in prange(nchunk):
            lo, hi = c * per, min(n, c * per + per)
            row = part[c]
            for j in range(lo, hi):
                g, e, amp, p = gam[j], eta[j], inten[j], pos[j]
                a, b = nptr[j], nptr[j + 1]
                for i in range(i0[j], i1[j]):
                    acc = 0.0
                    if b == a:
                        acc = pv(tt[i] - p, g, e)
                    else:
                        for q in range(a, b):
                            acc += nom[q] * pv(tt[i] - nphi[q], g, e)
                    row[i] += amp * acc
        out = np.zeros(npts)
        for c in range(nchunk):
            out += part[c]
        return out

    @njit(inline="always", cache=True)
    def pv_d(x, g, e):
        """(pV, ∂pV/∂x, ∂pV/∂Γ, L−G) in ``_components``' spelling."""
        u = x / g
        lor = (2.0 / (math.pi * g)) / (1.0 + 4.0 * u * u)
        gau = (2.0 / g) * _SQRT_LN2_PI * math.exp(-_4LN2 * u * u)
        dl_dx = -lor * (8.0 * u / g) / (1.0 + 4.0 * u * u)
        dg_dx = -gau * (2.0 * _4LN2 * u / g)
        dl_dg = (lor / g) * (8.0 * u * u / (1.0 + 4.0 * u * u) - 1.0)
        dg_dg = (gau / g) * (2.0 * _4LN2 * u * u - 1.0)
        return (e * lor + (1.0 - e) * gau,
                e * dl_dx + (1.0 - e) * dg_dx,
                e * dl_dg + (1.0 - e) * dg_dg,
                lor - gau)

    @njit(cache=True, parallel=True)
    def bases_parallel(tt, i0, i1, pos, gam, eta, nptr, nphi, nom,
                       om_p, dx_p, dg_p, de_p, nthread):
        # prange over rows: each row owns its own output slice, so unlike the
        # forward there is nothing to reduce.  ``nthread`` is unused inside
        # and kept in the signature so the caller's thread count is visible
        # in the recorded call, not only in numba's global state.
        for j in prange(len(i0)):
            g, e, p = gam[j], eta[j], pos[j]
            a, b = nptr[j], nptr[j + 1]
            base = i0[j]
            for i in range(i0[j], i1[j]):
                s0 = s1 = s2 = s3 = 0.0
                if b == a:
                    s0, s1, s2, s3 = pv_d(tt[i] - p, g, e)
                else:
                    for q in range(a, b):
                        w = nom[q]
                        t0, t1, t2, t3 = pv_d(tt[i] - nphi[q], g, e)
                        s0 += w * t0
                        s1 += w * t1
                        s2 += w * t2
                        s3 += w * t3
                c = i - base
                om_p[j, c] = s0
                dx_p[j, c] = s1
                dg_p[j, c] = s2
                de_p[j, c] = s3

    return forward_serial, forward_parallel, bases_parallel


def build_nodes(lay, pos, sl, hl):
    """Flat CSR (phi, weight) node arrays per row, off the frozen buckets.

    ``fcj_offsets_weights_batch`` returns ``2·max(n//2, 4)`` images for a
    bucket keyed ``n``, **not** ``n`` — so the count is read off the returned
    array rather than assumed from the key.
    """
    counts = np.zeros(len(pos), dtype=np.int64)
    built = []
    for n, rows in lay.buckets.items():
        if not n:
            continue
        phi, om = fcj_offsets_weights_batch(pos[rows], sl, hl, n)
        built.append((rows, phi, om))
        counts[rows] = phi.shape[1]
    nptr = np.zeros(len(pos) + 1, dtype=np.int64)
    np.cumsum(counts, out=nptr[1:])
    nphi = np.zeros(int(nptr[-1]))
    nom = np.zeros(int(nptr[-1]))
    for rows, phi, om in built:
        for t, j in enumerate(rows):
            nphi[nptr[j]:nptr[j + 1]] = phi[t]
            nom[nptr[j]:nptr[j + 1]] = om[t]
    return nptr, nphi, nom


def numpy_bases(lay, pos, gam, eta, nptr, nphi, nom):
    """The four planes as ``derivative_bases`` builds them: the derivative
    kernel on a (rows, nodes, window) plane, then the node-weighted mix."""
    out = [np.zeros((len(pos), lay.w_max)) for _ in range(4)]
    for n, rows in lay.buckets.items():
        x1 = lay.x[rows]
        if not n:
            got = pseudo_voigt_derivs(x1 - pos[rows, None], gam[rows, None],
                                      eta[rows, None])
            for dst, src in zip(out, got):
                dst[rows] = src
            continue
        phi = np.stack([nphi[nptr[j]:nptr[j + 1]] for j in rows])
        wq = np.stack([nom[nptr[j]:nptr[j + 1]] for j in rows])
        got = pseudo_voigt_derivs(x1[:, None, :] - phi[:, :, None],
                                  gam[rows, None, None], eta[rows, None, None])
        for dst, src in zip(out, got):
            dst[rows] = np.matmul(wq[:, None, :], src)[:, 0, :]
    return out


def best_of(fn, reps: int) -> float:
    best = math.inf
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def _trigger_setup():
    import bench_refinement as bench

    return {c.key: c for c in bench.CASES}["trigger"].build()


def bench_kernels(reps: int) -> int:
    try:
        forward_serial, forward_parallel, bases_parallel = _kernels()
    except ImportError:
        print("numba is not installed; this spike needs it "
              "(`uv pip install numba`).  It is deliberately not a "
              "dependency — whether it ever becomes an optional extra is "
              "the decision this benchmark exists to inform.")
        return 1
    import numba

    setup = _trigger_setup()
    model = compile_model(setup.structure, setup.instrument, setup.data,
                          mode=setup.mode, two_theta_limits=setup.limits)
    table = ParameterTable(setup.structure, setup.instrument)
    values = table.decode(table.x0())
    sl = values["instrument.geometry.axial_sl"]
    hl = values["instrument.geometry.axial_hl"]
    maxt = numba.config.NUMBA_DEFAULT_NUM_THREADS
    tt = np.asarray(model.tt, dtype=np.float64)
    npts = len(tt)

    print(f"rietx {rx.__version__} · numpy {np.__version__} · numba "
          f"{numba.__version__} · {maxt} threads available")
    print("case trigger, starting model; node generation excluded from both "
          "paths; best-of-%d" % reps)

    rows = []
    for ip, cp in enumerate(model.phases):
        lay = cp.batch
        peaks = model.phase_peaks(ip, values, None)
        pos, gam, eta = (lay.gather(peaks, s) for s in (0, 1, 2))
        inten = lay.gather(peaks, 3)
        finite = np.isfinite(pos)
        nptr, nphi, nom = build_nodes(lay, pos, sl, hl)
        i0 = np.asarray(lay.i0, dtype=np.int64)
        i1 = np.asarray(lay.i1, dtype=np.int64)
        elems = int(np.sum(np.maximum(np.diff(nptr), 1) * (i1 - i0)))
        rows.append(dict(ip=ip, lay=lay, pos=pos, gam=gam, eta=eta,
                         inten=inten, finite=finite, nptr=nptr, nphi=nphi,
                         nom=nom, i0=i0, i1=i1, elems=elems))

    # -- forward -----------------------------------------------------------
    print("\nforward: Ω build + window scatter")
    print(f"{'phase':7s} {'rows':>5s} {'elements':>10s} {'numpy ms':>9s} "
          f"{'numba ms':>9s} {'ratio':>6s} {'max rel |Δ|':>12s}")
    t_np = t_nb = 0.0
    elems = 0
    for r in rows:
        lay = r["lay"]

        def np_path(r=r, lay=lay):
            omega = model._omega_batch(lay, r["pos"], r["gam"], r["eta"],
                                       r["finite"], sl, hl,
                                       compiled.SPELL_FORWARD)
            return accumulate_planes(npts, [(lay, [(r["inten"], omega)])])

        def nb_path(r=r):
            return forward_serial(tt, r["i0"], r["i1"], r["pos"], r["gam"],
                                  r["eta"], r["inten"], r["nptr"], r["nphi"],
                                  r["nom"], np.zeros(npts))

        y_np = np_path()
        # the FIRST call is the JIT, and its latency is a packaging fact, not
        # a benchmarking nuisance: with ``cache=True`` it is paid once per
        # install per kernel, but the first fit after an upgrade pays it.
        t_jit = time.perf_counter()
        y_nb = nb_path()
        t_jit = time.perf_counter() - t_jit
        if r["ip"] == 0:
            print(f"  (first call compiled in {t_jit:.2f} s; "
                  f"`cache=True` writes it to disk, so later processes "
                  f"reload rather than recompile)")
        a = best_of(np_path, reps)
        b = best_of(nb_path, reps)
        scale = float(np.max(np.abs(y_np))) or 1.0
        print(f"{r['ip']:<7d} {len(r['pos']):5d} {r['elems']:10d} "
              f"{1e3 * a:9.3f} {1e3 * b:9.3f} {a / b:5.2f}× "
              f"{float(np.max(np.abs(y_np - y_nb))) / scale:12.2e}")
        t_np += a
        t_nb += b
        elems += r["elems"]
    print(f"  whole forward   numpy {1e3 * t_np:7.3f} ms "
          f"({1e9 * t_np / elems:5.2f} ns/element)   "
          f"numba {1e3 * t_nb:7.3f} ms ({1e9 * t_nb / elems:5.2f})   "
          f"{t_np / t_nb:.2f}×")

    def fwd_par():
        out = np.zeros(npts)
        for r in rows:
            out += forward_parallel(tt, r["i0"], r["i1"], r["pos"], r["gam"],
                                    r["eta"], r["inten"], r["nptr"],
                                    r["nphi"], r["nom"], npts,
                                    numba.get_num_threads())
        return out

    _scaling("forward, threaded (private outputs + reduction, both timed)",
             fwd_par, t_np, reps, maxt, numba)

    # -- derivative bases --------------------------------------------------
    print("\nbases: Ω and ∂Ω/∂x, ∂Ω/∂Γ, ∂Ω/∂η, node-mixed")
    print(f"{'phase':7s} {'rows':>5s} {'elements':>10s} {'numpy ms':>9s} "
          f"{'numba ms':>9s} {'ratio':>6s} {'max rel |Δ|':>12s}")
    b_np = b_nb = 0.0
    for r in rows:
        lay = r["lay"]
        planes = tuple(np.zeros((len(r["pos"]), lay.w_max)) for _ in range(4))

        def np_path(r=r, lay=lay):
            return numpy_bases(lay, r["pos"], r["gam"], r["eta"], r["nptr"],
                               r["nphi"], r["nom"])

        def nb_path(r=r, planes=planes):
            bases_parallel(tt, r["i0"], r["i1"], r["pos"], r["gam"], r["eta"],
                           r["nptr"], r["nphi"], r["nom"], *planes, 1)

        numba.set_num_threads(1)
        ref = np_path()
        nb_path()
        mask = np.asarray(lay.mask) > 0
        worst = 0.0
        for got, want in zip(planes, ref):
            scale = float(np.max(np.abs(want[mask]))) or 1.0
            worst = max(worst,
                        float(np.max(np.abs(want[mask] - got[mask]))) / scale)
        a = best_of(np_path, reps)
        b = best_of(nb_path, reps)
        print(f"{r['ip']:<7d} {len(r['pos']):5d} {r['elems']:10d} "
              f"{1e3 * a:9.3f} {1e3 * b:9.3f} {a / b:5.2f}× {worst:12.2e}")
        b_np += a
        b_nb += b
    print(f"  whole bases     numpy {1e3 * b_np:7.3f} ms "
          f"({1e9 * b_np / elems:5.2f} ns/element)   "
          f"numba {1e3 * b_nb:7.3f} ms ({1e9 * b_nb / elems:5.2f})   "
          f"{b_np / b_nb:.2f}×")

    store = [tuple(np.zeros((len(r["pos"]), r["lay"].w_max))
                   for _ in range(4)) for r in rows]

    def bases_par():
        for r, planes in zip(rows, store):
            bases_parallel(tt, r["i0"], r["i1"], r["pos"], r["gam"],
                           r["eta"], r["nptr"], r["nphi"], r["nom"], *planes,
                           numba.get_num_threads())

    _scaling("bases, threaded (disjoint output slices, no reduction)",
             bases_par, b_np, reps, maxt, numba)
    return 0


def _scaling(title, fn, numpy_time, reps, maxt, numba) -> None:
    print(f"\n{title}")
    print(f"{'threads':>8s} {'ms':>9s} {'vs numpy':>9s} {'vs 1 thread':>12s}")
    numba.set_num_threads(1)
    fn()                                   # compile outside the timing
    base = None
    for nt in sorted({1, 2, 4, 8, maxt}):
        if nt > maxt:
            continue
        numba.set_num_threads(nt)
        t = best_of(fn, reps)
        base = base or t
        print(f"{nt:8d} {1e3 * t:9.3f} {numpy_time / t:8.2f}× "
              f"{base / t:11.2f}×")
    numba.set_num_threads(maxt)


def bench_nogil(reps: int) -> int:
    """Serial ``nogil`` kernel on a thread pool, against the ``prange`` twin.

    Two questions at once, because they trade against each other: does the
    cache hit (**run this twice** — the first process compiles, the second
    should not), and does a Python thread pool reach ``prange``'s throughput.
    """
    try:
        bases_range = _nogil_kernel()
    except ImportError:
        print("numba is not installed; this spike needs it "
              "(`uv pip install numba`).")
        return 1
    import numba

    cache_dir = Path(__file__).resolve().parent / "__pycache__"
    warm = any(cache_dir.glob("*bases_range*.nbi"))
    setup = _trigger_setup()
    model = compile_model(setup.structure, setup.instrument, setup.data,
                          mode=setup.mode, two_theta_limits=setup.limits)
    table = ParameterTable(setup.structure, setup.instrument)
    values = table.decode(table.x0())
    sl = values["instrument.geometry.axial_sl"]
    hl = values["instrument.geometry.axial_hl"]
    tt = np.asarray(model.tt, dtype=np.float64)

    args = []
    for ip, cp in enumerate(model.phases):
        lay = cp.batch
        peaks = model.phase_peaks(ip, values, None)
        pos = lay.gather(peaks, 0)
        nptr, nphi, nom = build_nodes(lay, pos, sl, hl)
        planes = tuple(np.zeros((len(pos), lay.w_max)) for _ in range(4))
        args.append((np.asarray(lay.i0, dtype=np.int64),
                     np.asarray(lay.i1, dtype=np.int64), pos,
                     lay.gather(peaks, 1), lay.gather(peaks, 2),
                     nptr, nphi, nom, planes, len(pos)))

    a0 = args[0]
    t0 = time.perf_counter()
    bases_range(tt, a0[0], a0[1], a0[2], a0[3], a0[4], a0[5], a0[6], a0[7],
                *a0[8], 0, 1)
    t_jit = time.perf_counter() - t0
    print(f"numba {numba.__version__} · disk cache "
          f"{'present' if warm else 'absent'} before this run")
    print(f"first call: {t_jit:.2f} s   (the `parallel=True` twin measures "
          f"0.38-0.39 s on EVERY run, cache or no cache)")

    pool = ThreadPoolExecutor(max_workers=max(
        16, numba.config.NUMBA_DEFAULT_NUM_THREADS))

    def run(nthreads):
        def go():
            futs = []
            for i0, i1, pos, gam, eta, nptr, nphi, nom, planes, n in args:
                per = (n + nthreads - 1) // nthreads
                for c in range(nthreads):
                    lo, hi = c * per, min(n, c * per + per)
                    if lo < hi:
                        futs.append(pool.submit(
                            bases_range, tt, i0, i1, pos, gam, eta, nptr,
                            nphi, nom, *planes, lo, hi))
            for f in futs:
                f.result()
        return go

    def serial():
        for i0, i1, pos, gam, eta, nptr, nphi, nom, planes, n in args:
            bases_range(tt, i0, i1, pos, gam, eta, nptr, nphi, nom,
                        *planes, 0, n)

    t_ser = best_of(serial, reps)
    print(f"\n{'threads':>8s} {'ms':>9s} {'vs serial':>10s}")
    print(f"{'inline':>8s} {1e3 * t_ser:9.3f} {1.0:9.2f}×")
    maxt = numba.config.NUMBA_DEFAULT_NUM_THREADS
    for nt in sorted({1, 2, 4, 8, maxt}):
        if nt > maxt:
            continue
        t = best_of(run(nt), reps)
        print(f"{nt:8d} {1e3 * t:9.3f} {t_ser / t:9.2f}×")
    pool.shutdown()
    return 0


def bench_seams() -> int:
    """Decompose one trigger cold fit into the seams the kernels sit in.

    The kernel ratios above are only worth what their share of a real fit
    says they are, and that share moved under WP-1120: the forward is no
    longer where the time is.  Wrappers, not cProfile — the profiler inflates
    exactly the small-array calls this question is about.
    """
    total: dict[str, float] = defaultdict(float)
    calls: dict[str, int] = defaultdict(int)

    class clock:
        __slots__ = ("key", "t0")

        def __init__(self, key):
            self.key = key

        def __enter__(self):
            self.t0 = time.perf_counter()

        def __exit__(self, *exc):
            total[self.key] += time.perf_counter() - self.t0
            calls[self.key] += 1

    refine_mod = sys.modules["rietx.refine"]
    orig_compile = refine_mod.compile_model
    orig_res, orig_jac = lsq._make_residual, lsq._jacobian_for
    orig_bases = CompiledModel.derivative_bases

    def wrapped_compile(*a, **k):
        with clock("compile"):
            return orig_compile(*a, **k)

    def wrapped_res(model, table):
        inner = orig_res(model, table)

        def residual(theta):
            with clock("residual"):
                return inner(theta)

        return residual

    def wrapped_jac(model, table, backend):
        inner = orig_jac(model, table, backend)

        def jacobian(theta):
            with clock("jacobian"):
                return inner(theta)

        return jacobian

    def wrapped_bases(self, *a, **k):
        with clock("bases"):
            return orig_bases(self, *a, **k)

    # The column seam is two unlike things and only one of them is plane
    # work, so it is split here rather than quoted whole: a perturbed
    # ``phase_peaks`` per (column, affected phase) is per-reflection scalars
    # that no plane kernel can touch.
    depth = {"col": 0}
    orig_col = lsq._peak_chain_column
    orig_peaks = CompiledModel.phase_peaks
    orig_acc = lsq._accumulate

    def wrapped_col(*a, **k):
        depth["col"] += 1
        try:
            return orig_col(*a, **k)
        finally:
            depth["col"] -= 1

    def wrapped_peaks(self, *a, **k):
        if depth["col"]:
            with clock("col.peaks"):
                return orig_peaks(self, *a, **k)
        return orig_peaks(self, *a, **k)

    def wrapped_acc(*a, **k):
        if depth["col"]:
            with clock("col.accum"):
                return orig_acc(*a, **k)
        return orig_acc(*a, **k)

    refine_mod.compile_model = wrapped_compile
    lsq._make_residual, lsq._jacobian_for = wrapped_res, wrapped_jac
    CompiledModel.derivative_bases = wrapped_bases
    lsq._peak_chain_column = wrapped_col
    CompiledModel.phase_peaks = wrapped_peaks
    lsq._accumulate = wrapped_acc
    try:
        setup = _trigger_setup()
        ref = rx.Refinement(setup.structure.model_copy(deep=True),
                            setup.instrument.model_copy(deep=True),
                            history=False)
        t0 = time.perf_counter()
        result = ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                         two_theta_limits=setup.limits)
        wall = time.perf_counter() - t0
    finally:
        refine_mod.compile_model = orig_compile
        lsq._make_residual, lsq._jacobian_for = orig_res, orig_jac
        CompiledModel.derivative_bases = orig_bases
        lsq._peak_chain_column = orig_col
        CompiledModel.phase_peaks = orig_peaks
        lsq._accumulate = orig_acc

    cols = total["jacobian"] - total["bases"]
    print(f"trigger cold fit: {wall:.2f} s   Rwp "
          f"{result.statistics.rwp:.5f}   {result.status}")
    print(f"{'seam':26s} {'calls':>6s} {'s':>8s} {'ms/call':>9s} {'share':>7s}")
    shown = (("residual (forward)", total["residual"], calls["residual"]),
             ("jacobian: bases", total["bases"], calls["bases"]),
             ("jacobian: columns", cols, calls["jacobian"]),
             ("  of which accumulate", total["col.accum"], calls["col.accum"]),
             ("  of which phase_peaks", total["col.peaks"], calls["col.peaks"]),
             ("compile_model", total["compile"], calls["compile"]))
    for name, secs, n in shown:
        print(f"{name:26s} {n:6d} {secs:8.3f} {1e3 * secs / max(n, 1):9.3f} "
              f"{100 * secs / wall:6.1f}%")
    rest = wall - total["residual"] - total["jacobian"] - total["compile"]
    print(f"{'solver + runner':26s} {'':6s} {rest:8.3f} {'':9s} "
          f"{100 * rest / wall:6.1f}%")
    if cols:
        print(f"\nOnly {100 * total['col.accum'] / cols:.0f}% of the column "
              f"seam is plane work; {100 * total['col.peaks'] / cols:.0f}% is "
              f"the perturbed phase_peaks, which is per-reflection scalars "
              f"and out of a plane kernel's reach.")
    return 0


def bench_accum(reps: int) -> int:
    """Bench the fused scatter against ``accumulate_planes`` on real inputs.

    The ``parts`` are captured from inside a real trigger fit, sampled
    **evenly across it** rather than from the head: the first calls come from
    ``scale_bkg``, where a column touches one phase with one term, and
    measuring those flatters the kernel by ~5× against the fit's own average.
    """
    try:
        fused = _accum_kernel()
    except ImportError:
        print("numba is not installed; this spike needs it "
              "(`uv pip install numba`).")
        return 1

    captured: list = []
    want, stride = 40, 240
    seen = {"n": 0}
    orig_acc = lsq._accumulate

    def cap(n_points, parts):
        seen["n"] += 1
        if seen["n"] % stride == 0 and len(captured) < want:
            keep = [(lay, [(c.copy(), p.copy()) for c, p in terms])
                    for lay, terms in parts if terms and len(lay.i0)]
            if keep:
                captured.append((n_points, keep))
        return orig_acc(n_points, parts)

    lsq._accumulate = cap
    try:
        setup = _trigger_setup()
        ref = rx.Refinement(setup.structure.model_copy(deep=True),
                            setup.instrument.model_copy(deep=True),
                            history=False)
        ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                two_theta_limits=setup.limits)
    finally:
        lsq._accumulate = orig_acc

    packed = []
    for n_points, parts in captured:
        per = []
        for lay, terms in parts:
            coefs = np.empty((len(terms), len(lay.i0)))
            planes = np.empty((len(terms), len(lay.i0), lay.w_max))
            for t, (c, p) in enumerate(terms):
                coefs[t], planes[t] = c, p
            per.append((np.asarray(lay.idx), np.asarray(lay.i0),
                        np.asarray(lay.i1), coefs, planes, len(terms)))
        packed.append((n_points, per))

    exact = True
    worst = 0.0
    for (n_points, parts), (_, per) in zip(captured, packed):
        want_y = accumulate_planes(n_points, parts)
        got = np.zeros(n_points)
        for idx, i0, i1, coefs, planes, nt in per:
            fused(got, idx, i0, i1, coefs, planes, nt)
        if not np.array_equal(want_y, got):
            exact = False
            scale = float(np.max(np.abs(want_y))) or 1.0
            worst = max(worst, float(np.max(np.abs(want_y - got))) / scale)

    def np_run():
        for n_points, parts in captured:
            accumulate_planes(n_points, parts)

    def nb_run():
        for n_points, per in packed:
            y = np.zeros(n_points)
            for idx, i0, i1, coefs, planes, nt in per:
                fused(y, idx, i0, i1, coefs, planes, nt)

    elems = sum(int(nt * len(i0) * planes.shape[2])
                for _, per in packed for _, i0, _, _, planes, nt in per)
    a, b = best_of(np_run, reps), best_of(nb_run, reps)
    n = len(captured)
    print(f"\ncolumn accumulation, {n} real calls sampled across a trigger "
          f"fit, {elems} plane elements")
    print(f"  numpy accumulate_planes {1e3 * a / n:8.3f} ms/call "
          f"({1e9 * a / elems:5.2f} ns/element)")
    print(f"  numba fused             {1e3 * b / n:8.3f} ms/call "
          f"({1e9 * b / elems:5.2f} ns/element)   {a / b:.2f}×")
    print("  equivalence: " + ("BIT-IDENTICAL on every captured call"
                               if exact else
                               f"max rel {worst:.2e} — NOT bit-identical"))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seams", action="store_true",
                    help="decompose a trigger cold fit instead of benching "
                         "the kernels")
    ap.add_argument("--nogil", action="store_true",
                    help="serial nogil kernel on a thread pool vs the "
                         "prange twin: cache behaviour and throughput")
    ap.add_argument("--accum", action="store_true",
                    help="bench the column seam's plane accumulation on "
                         "inputs captured from a real fit")
    ap.add_argument("--repeats", type=int, default=7,
                    help="timed repeats per kernel (default 7)")
    args = ap.parse_args(argv)
    if args.seams:
        return bench_seams()
    if args.accum:
        return bench_accum(args.repeats)
    if args.nogil:
        return bench_nogil(args.repeats)
    return bench_kernels(args.repeats)


if __name__ == "__main__":
    raise SystemExit(main())
