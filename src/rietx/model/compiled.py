"""Fused, threaded twins of the batched numpy planes (WP-1115).

This is an **accelerator of the numpy path, not a fourth backend**.  jax and
torch keep the traced twin (``backend/traced.py``); what lives here is a set of
``numba`` kernels that compute exactly what ``model/forward.py`` computes with
numpy, in one pass over the grid instead of a dozen, and on more than one core.
Nothing above it may branch on whether they ran.

Why a compiled tier at all
--------------------------
WP-1112 and WP-1120 removed the two costs a numpy-level loop is usually blamed
for: per-call dispatch (the surviving kernel calls are 200-400 µs on ~10⁵
element planes) and ragged axes (``BatchLayout`` buckets by node count, so only
the window axis pads, at an evaluation-weighted 1.11×).  What they could not
remove is **fusion** and **threading**.  ``pseudo_voigt`` materialises about a
dozen full-size temporaries per call and ``pseudo_voigt_derivs`` more, each one
a write and a read of a (rows, nodes, window) plane that numpy cannot keep in
registers; and the GIL denies a numpy-level python loop any core but one.
Measured on the WP-1111 trigger case: 2.1-2.4× on the forward, 3.2-3.4× serial
and ~12× threaded on the derivative bases, 6.9-7.1× on the column scatter.

The three rules this module is held to
--------------------------------------
1. **The fallback is not optional.**  Every entry point declines rather than
   raising — numba missing, the tier switched off, a ``shape="voigt"`` model, an
   arity it was not written for — and the caller runs the numpy expression it
   already had.  A build without numba is a supported build: the dependency is
   required (``pyproject``) so the fast path is what a user gets by default, but
   the import is *soft* so ``--no-deps``, a distro package or a constraint file
   still produces a working install.  An extra cannot express this — extras only
   ever *add* dependencies, never subtract one — so the knob is a runtime one
   (:data:`~rietx._about.COMPILED_ENV`), which is the better knob anyway: it
   needs no reinstall, and it is what keeps the numpy path exercised on the
   default install.
2. **Each kernel declares which spelling of Ω it reproduces.**  ``pseudo_voigt``
   (the forward) and ``_components`` (the derivative bases) are 1-2 ulp apart on
   purpose, and the difference is a single association: the forward computes
   ``-4ln2 · (x/Γ)²`` while the bases compute ``((-4ln2)·u)·u``.  Borrowing one
   for the other would move every converged fit in its last digits (WP-1120), so
   :data:`SPELL_FORWARD` and :data:`SPELL_BASIS` are a kernel argument and not an
   implementation detail.
3. **The equivalence bar is stated per kernel, and tested.**  The column scatter
   is **bit-identical** — multiplies and adds in the order ``np.bincount``
   performs them, with no library function in it, so the bar is the bit and
   ``tests/test_compiled_kernels.py`` asserts it.  The profile kernels call
   ``exp``, which is libm's here and numpy's own SIMD routine there; they were
   measured bit-identical on darwin/arm64 against numpy 2.5.2 and are held to
   ≤ 1e-15 relative, the rounding bar WP-1112 set for FCJ rows.  The numpy
   builder stays the oracle for bit-identity against the per-reflection loop
   (``tests/test_batched_forward.py``), which is why it has to remain a live,
   exercised path and not merely dead fallback code.

Threading
---------
``prange`` was measured the wrong shape twice over: it refuses to cache, so its
~1.0 s recompiles in **every process**, and it is *slower* than the alternative
(1.36 ms against 1.23 ms at 8 threads on the bases kernel).  So every kernel
here is serial and ``nogil=True``, and the parallelism is a shared
``ThreadPoolExecutor`` over disjoint row ranges — which caches like any other
serial kernel (0.28 s in the first process, 0.06 s thereafter).  The pool is
shared because building one per call costs more than half the win (6.0 ms
against 2.8 ms, measured).

The scatter is the exception and stays single-threaded: its rows write into
overlapping windows, so splitting it by rows is a data race, and the order the
additions arrive in is the whole of its bit-identity claim.

Startup
-------
Compilation releases the GIL and overlaps essentially completely with numpy
work (measured across separate processes: 0.96 s serial against 0.65 s
threaded), so :func:`warm` is fired from ``compile_model`` on a background
thread and hides behind the file read, CIF parse and table build a fit does
anyway.  The disk cache is redirected to the package state directory because
numba's default is beside the source, i.e. inside ``site-packages``, which is
read-only in plenty of real installs (system python, containers, Nix) — and an
unwritable cache silently means recompiling in every process.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from .._about import (
    COMPILED_ENV,
    COMPILED_THREADS_ENV,
    STATE_DIR_ENV,
    STATE_DIR_NAME,
)

#: Ω spelled as :func:`~rietx.model.profiles.pseudovoigt.pseudo_voigt` — the
#: forward model's own arithmetic.
SPELL_FORWARD = 0
#: Ω spelled as ``pseudovoigt._components`` — the derivative bases' arithmetic,
#: which is deliberately not the forward's.
SPELL_BASIS = 1

#: The scatter takes at most this many (coefficient, plane) terms per part;
#: ``_peak_chain_column`` builds four (intensity, position, width, mixing) and
#: every other column builds one.  A caller with more is declined, not
#: mis-served.
MAX_TERMS = 4

#: Rows below this in one bucket run inline: at a few hundred rows the pool's
#: submit-and-collect costs more than the extra cores buy.
_THREAD_MIN_ROWS = 512

_EMPTY_1D = np.zeros(0)
_EMPTY_2D = np.zeros((0, 0))

_LOCK = threading.Lock()
_POOL_LOCK = threading.Lock()
_KERNELS: dict | None = None
_UNAVAILABLE = False
_ENABLED: bool | None = None
_POOL: ThreadPoolExecutor | None = None
_WARMING: threading.Thread | None = None


def _off_by_env() -> bool:
    """Is the tier switched off in the environment?"""
    return os.environ.get(COMPILED_ENV, "").strip().lower() in {
        "0", "off", "no", "false"}


def _cache_dir() -> str:
    """Where numba writes ``.nbi``/``.nbc``, defaulting into the state dir.

    A ``NUMBA_CACHE_DIR`` already in the environment always wins — a container
    image that pre-warms the cache at build time sets one, and this must not
    override it.
    """
    root = os.environ.get(STATE_DIR_ENV) or Path.home() / STATE_DIR_NAME
    return str(Path(root) / "numba-cache")


def n_threads() -> int:
    """Worker threads the row-parallel kernels split across.

    Capped at 8 because the measured ladder is flat past it, and settable so a
    caller that is already parallel one rank up (a test suite under ``xdist``, a
    series fanned out across processes) can decline the second layer.
    """
    raw = os.environ.get(COMPILED_THREADS_ENV, "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return max(1, min(8, os.cpu_count() or 1))


def available() -> bool:
    """Can the compiled kernels be built here — does numba import?

    Does **not** say whether they are switched on (:func:`enabled`).  Both are
    cheap after the first call and neither compiles anything.
    """
    if _UNAVAILABLE:
        return False
    if _KERNELS is not None:
        return True
    try:
        import numba  # noqa: F401
    except Exception:  # pragma: no cover - depends on the install
        return False
    return True


def enabled() -> bool:
    """Is the compiled path what the next residual will take?

    Read once and remembered, because the answer is asked on the hot path — the
    Jacobian calls into the scatter thousands of times per iteration — and an
    ``os.environ`` lookup per call is not free at that rate.  Use
    :func:`set_enabled` to change it inside a process.
    """
    global _ENABLED
    if _ENABLED is None:
        _ENABLED = not _off_by_env() and available()
    return _ENABLED


def set_enabled(flag: bool | None) -> bool | None:
    """Force the tier on or off for this process; ``None`` re-reads the
    environment.  Returns the previous setting, so a caller can restore it.

    This is the seam the suite runs the numpy path through — the fallback is
    only real if something exercises it — and the escape hatch for a caller who
    has hit a difference and wants to say which side it is on.
    """
    global _ENABLED
    was, _ENABLED = _ENABLED, flag
    return was


def _kernels() -> dict | None:
    """Build (or fetch) the kernels; ``None`` if this build has no numba.

    **A caller that finds the build in progress waits for it.**  Declining
    instead — running numpy for the calls that arrive early and the kernels for
    the ones that arrive late — was the first shape here and it is the wrong
    one: it makes which path a given evaluation took a function of how fast the
    machine compiled, so the same script gives different last digits on two
    runs and, through a trust-region decision, occasionally a different
    iteration count.  One path per process is worth more than the few hundred
    milliseconds it costs, and :func:`warm` has already overlapped most of that
    with the model compile by the time a residual asks.
    """
    global _KERNELS, _UNAVAILABLE
    if _KERNELS is not None:
        return _KERNELS
    if _UNAVAILABLE:
        return None
    with _LOCK:
        if _KERNELS is not None:
            return _KERNELS
        if _UNAVAILABLE:
            return None
        os.environ.setdefault("NUMBA_CACHE_DIR", _cache_dir())
        try:
            from . import _kernels_numba

            built = _kernels_numba.build()
        except Exception:  # pragma: no cover - depends on the install
            _UNAVAILABLE = True
            return None
        _KERNELS = built
        return built


def warm(block: bool = False) -> None:
    """Compile the kernels, by default on a background thread.

    numba's compilation releases the GIL, so this overlaps with the setup a fit
    does before its first residual rather than adding to it.  Idempotent and
    safe to call from anywhere; on a build without numba it is a no-op the first
    time and a flag test thereafter.
    """
    global _WARMING
    if _KERNELS is not None or _UNAVAILABLE or not enabled():
        return
    if block:
        _kernels()
        return
    if _WARMING is not None and _WARMING.is_alive():
        return
    _WARMING = threading.Thread(
        target=_kernels, name="rietx-kernel-warm", daemon=True)
    _WARMING.start()


def _pool() -> ThreadPoolExecutor:
    """The shared pool: one per process, built on first use, never shut down.

    Its threads are idle between residuals, and rebuilding it per call was
    measured to cost more than half the threading win.
    """
    global _POOL
    if _POOL is None:
        # its own lock: ``_LOCK`` is held for the whole of a cold compile, and
        # a pool build must never queue behind one
        with _POOL_LOCK:
            if _POOL is None:
                _POOL = ThreadPoolExecutor(
                    max_workers=n_threads(), thread_name_prefix="rietx-kernel")
    return _POOL


def _spread(fn, n_rows: int) -> None:
    """Run ``fn(lo, hi)`` over ``n_rows`` rows, split across the pool.

    Row ranges are disjoint in the output planes, so no lock is needed; the
    kernels release the GIL for the duration of the call, which is what makes a
    python-level pool a real parallel loop here.
    """
    nt = n_threads()
    if nt == 1 or n_rows < _THREAD_MIN_ROWS:
        fn(0, n_rows)
        return
    per = -(-n_rows // nt)
    futures = [_pool().submit(fn, lo, min(n_rows, lo + per))
               for lo in range(0, n_rows, per)]
    for f in futures:
        f.result()


def _c(a: np.ndarray, dtype=np.float64) -> np.ndarray:
    """C-contiguous view of the declared dtype — free when it already is one,
    and what keeps numba to a single compiled specialisation per kernel."""
    return np.ascontiguousarray(a, dtype=dtype)


# --- entry points ---------------------------------------------------------
#
# Each declines (``None``/``False``) rather than raising, and every caller must
# have the numpy expression it already had to fall back to.


def accumulate(n_points: int, parts) -> np.ndarray | None:
    """Bit-identical fused twin of :func:`~rietx.model.forward.accumulate_planes`.

    ``np.bincount`` adds its input sequentially, so for one output point the
    additions from one part arrive in (row, term) order; the kernel walks that
    same sequence with the same two operations per contribution and no library
    call, which makes the equality exact rather than close.  The pad tail is
    skipped rather than added: the planes arrive pad-zeroed, so those
    contributions are ±0.0 and dropping them is bitwise neutral.

    Declines a part carrying more than :data:`MAX_TERMS` terms.
    """
    k = _kernels()
    if k is None:
        return None
    live = [(lay, terms) for lay, terms in parts if terms and len(lay.i0)]
    if any(len(terms) > MAX_TERMS for _lay, terms in live):
        return None
    y = np.zeros(n_points)
    for lay, terms in live:
        coefs = [_c(c) for c, _p in terms]
        planes = [_c(p) for _c0, p in terms]
        while len(coefs) < MAX_TERMS:
            coefs.append(_EMPTY_1D)
            planes.append(_EMPTY_2D)
        k["accum"](y, _c(lay.i0, np.int64), _c(lay.i1, np.int64),
                   coefs[0], planes[0], coefs[1], planes[1],
                   coefs[2], planes[2], coefs[3], planes[3], len(terms))
    return y


def omega_symmetric(out: np.ndarray, x: np.ndarray, rows: np.ndarray,
                    pos: np.ndarray, w1: np.ndarray, w2: np.ndarray,
                    width: np.ndarray, spell: int) -> bool:
    """Fill ``out[rows]`` with Ω on the symmetric rows.  ``False`` = declined."""
    k = _kernels()
    if k is None:
        return False
    if not len(rows):
        return True
    rows = _c(rows, np.int64)
    args = (out, _c(x), rows, _c(pos), _c(w1), _c(w2), _c(width, np.int64),
            spell)
    _spread(lambda lo, hi: k["omega_sym"](*args, lo, hi), len(rows))
    return True


def omega_fcj(out: np.ndarray, x: np.ndarray, rows: np.ndarray,
              w1: np.ndarray, w2: np.ndarray, width: np.ndarray,
              phi: np.ndarray, om: np.ndarray, spell: int) -> bool:
    """Fill ``out[rows]`` with the node-weighted Ω of one FCJ bucket.

    The node sum runs innermost, so the (rows, nodes, window) transient the
    numpy path materialises never exists — which is the whole of the win here,
    and also why this agrees with ``_node_mix``'s matmul to rounding rather than
    to the bit.
    """
    k = _kernels()
    if k is None:
        return False
    if not len(rows):
        return True
    rows = _c(rows, np.int64)
    args = (out, _c(x), rows, _c(w1), _c(w2), _c(width, np.int64),
            _c(phi), _c(om), spell)
    _spread(lambda lo, hi: k["omega_fcj"](*args, lo, hi), len(rows))
    return True


def bases_symmetric(omega: np.ndarray, d_pos: np.ndarray, d_gamma: np.ndarray,
                    d_eta: np.ndarray, x: np.ndarray, rows: np.ndarray,
                    pos: np.ndarray, w1: np.ndarray, w2: np.ndarray,
                    width: np.ndarray) -> bool:
    """Ω and its three partials on the symmetric rows, in one pass."""
    k = _kernels()
    if k is None:
        return False
    if not len(rows):
        return True
    rows = _c(rows, np.int64)
    args = (omega, d_pos, d_gamma, d_eta, _c(x), rows, _c(pos), _c(w1),
            _c(w2), _c(width, np.int64))
    _spread(lambda lo, hi: k["bases_sym"](*args, lo, hi), len(rows))
    return True


def bases_fcj(omega: np.ndarray, d_pos: np.ndarray, d_gamma: np.ndarray,
              d_eta: np.ndarray, d_sl: np.ndarray | None,
              d_hl: np.ndarray | None, x: np.ndarray, rows: np.ndarray,
              w1: np.ndarray, w2: np.ndarray, width: np.ndarray,
              phi: np.ndarray, om: np.ndarray, dphi: np.ndarray,
              dom: np.ndarray, ax: tuple | None) -> bool:
    """Ω and every partial for one FCJ bucket, in one pass over the nodes.

    ``dphi``/``dom`` are the node-FD position derivatives the numpy path builds
    from a shifted node generation; ``ax`` carries the same pair for S/L and
    H/L, or ``None`` when the axial columns are not being built.  All of them
    are (rows, nodes) — cheap beside the (rows, nodes, window) planes this
    avoids — and are differenced in numpy before the call, so the kernel sees
    exactly the numbers the numpy path multiplies.
    """
    k = _kernels()
    if k is None:
        return False
    if not len(rows):
        return True
    rows = _c(rows, np.int64)
    has_ax = ax is not None and d_sl is not None and d_hl is not None
    if has_ax:
        dphi_sl, dom_sl, dphi_hl, dom_hl = (_c(a) for a in ax)
        sl_out, hl_out = d_sl, d_hl
    else:
        dphi_sl = dom_sl = dphi_hl = dom_hl = _EMPTY_2D
        sl_out = hl_out = _EMPTY_2D
    args = (omega, d_pos, d_gamma, d_eta, sl_out, hl_out, _c(x), rows,
            _c(w1), _c(w2), _c(width, np.int64), _c(phi), _c(om), _c(dphi),
            _c(dom), dphi_sl, dom_sl, dphi_hl, dom_hl, has_ax)
    _spread(lambda lo, hi: k["bases_fcj"](*args, lo, hi), len(rows))
    return True
