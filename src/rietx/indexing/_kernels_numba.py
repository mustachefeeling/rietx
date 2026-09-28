"""The numba box traversal behind :func:`rietx.indexing.dichotomy.search_dichotomy`
(WP-1508).

Imported lazily and only when numba is present, so it may import numba at top
level; ``dichotomy._traversal_kernels`` owns the switch, the fallback and the
decision to call it, and :mod:`rietx.model.compiled` owns the cache directory
and the one on/off switch both tiers read.

**Why this exists, measured** (WP-1508 § Gate reading).  On a 4-D search a
dichotomy unit spends 94 % of its time traversing boxes — ~70 numpy calls a
box on ~100 rows, 157 µs of which almost all is call overhead — and the leaves
cost nothing.  A loop that pays no dispatch is what that regime needs.  On a
2-D search the same traversal is ~10 % and the leaves are the cost, which is
not this module's (WP-1509).

**Every expression is a transcription, and the bar is the bit.**  Each line
mirrors, association for association, the numpy line it replaces in
``dichotomy.py``: ``_q_bounds``/``_af_interval`` sum their ≤ 6 terms left to
right (numpy's ``.sum(axis=1)`` at that width, pinned by
``tests/test_indexing_kernels.py``), ``_det_interval`` is copied operation for
operation including Python's ``min``/``max`` keeping the *first* of equal
values, and there is no library call but ``sqrt``, which IEEE rounds
correctly.  So the review question for an edit here is "is this the same
rounding as the numpy line it copies", and the equivalence test answers it.

**The traversal is the numpy loop's, in the same order.**  A LIFO stack, the
children pushed best-last by ``(misses, pairs)`` with the left child first on a
tie (``sorted(..., reverse=True)`` is stable), the widest-Q dimension split at
its midpoint, the same leaf rule.  What differs is only *where* a box's
surviving rows live: numpy stacks a copy per box, this stacks ``(start, length)``
into one index pool used as a stack — a box's survivors are written above the
live region and referenced by both children, and popping an entry frees
everything above its own list, which LIFO order guarantees is dead.

**It stops and hands back to python** when its leaf buffer fills (a leaf needs
``_accept``, which is LAPACK and stays in python), after a chunk of row-tests
(so ``Budget.expired`` is still asked every few tens of milliseconds), or when
the pool needs to grow.  A finished search is therefore bit-identical; a *cut*
one may stop up to a chunk later than the numpy loop, which is machine load
either way.

``error_model="numpy"``: a division by zero in the interval arithmetic must give
the IEEE infinity numpy gives, never raise.
"""

from __future__ import annotations

import numpy as np
from numba import njit

_KW = {"cache": True, "nogil": True, "fastmath": False, "error_model": "numpy"}

#: status codes :func:`traverse` returns
DONE = 0
LEAVES = 1
CHUNK = 2
GROW = 3


@njit(**_KW)
def _imul(x0, x1, y0, y1):
    """``dichotomy._imul``: min/max of the four products, first of equals."""
    p0 = x0 * y0
    p1 = x0 * y1
    p2 = x1 * y0
    p3 = x1 * y1
    lo = p0
    if p1 < lo:
        lo = p1
    if p2 < lo:
        lo = p2
    if p3 < lo:
        lo = p3
    hi = p0
    if p1 > hi:
        hi = p1
    if p2 > hi:
        hi = p2
    if p3 > hi:
        hi = p3
    return lo, hi


@njit(**_KW)
def _isq(lo, hi):
    """``dichotomy._isq``."""
    a = lo * lo
    b = hi * hi
    top = a
    if b > top:
        top = b
    if lo <= 0.0 <= hi:
        return 0.0, top
    bot = a
    if b < bot:
        bot = b
    return bot, top


@njit(**_KW)
def _rho(x_lo, x_hi, y0, y1, z0, z1, c):
    """``dichotomy._rho_interval``."""
    if y0 <= 0.0 or z0 <= 0.0:
        return -c, c
    small = 2.0 * np.sqrt(y0 * z0)
    big = 2.0 * np.sqrt(y1 * z1)
    lo = x_lo / small if x_lo < 0.0 else x_lo / big
    hi = x_hi / small if x_hi > 0.0 else x_hi / big
    out_lo = lo
    if -c > out_lo:
        out_lo = -c
    out_hi = hi
    if c < out_hi:
        out_hi = c
    return out_lo, out_hi


@njit(**_KW)
def _det(af_lo, af_hi, c):
    """``dichotomy._det_interval``, operation for operation."""
    a0, a1 = af_lo[0], af_hi[0]
    b0, b1 = af_lo[1], af_hi[1]
    c0, c1 = af_lo[2], af_hi[2]
    d23_0, d23_1 = 0.5 * af_lo[3], 0.5 * af_hi[3]
    d13_0, d13_1 = 0.5 * af_lo[4], 0.5 * af_hi[4]
    d12_0, d12_1 = 0.5 * af_lo[5], 0.5 * af_hi[5]
    ab0, ab1 = _imul(a0, a1, b0, b1)
    diag0, diag1 = _imul(ab0, ab1, c0, c1)
    x0, x1 = _imul(d12_0, d12_1, d13_0, d13_1)
    cd0, cd1 = _imul(x0, x1, d23_0, d23_1)
    s0, s1 = _isq(d23_0, d23_1)
    t3_0, t3_1 = _imul(a0, a1, s0, s1)
    s0, s1 = _isq(d13_0, d13_1)
    t4_0, t4_1 = _imul(b0, b1, s0, s1)
    s0, s1 = _isq(d12_0, d12_1)
    t5_0, t5_1 = _imul(c0, c1, s0, s1)
    lo = diag0 + 2.0 * cd0 - t3_1 - t4_1 - t5_1
    hi = diag1 + 2.0 * cd1 - t3_0 - t4_0 - t5_0

    r23_0, r23_1 = _rho(af_lo[3], af_hi[3], b0, b1, c0, c1, c)
    r13_0, r13_1 = _rho(af_lo[4], af_hi[4], a0, a1, c0, c1, c)
    r12_0, r12_1 = _rho(af_lo[5], af_hi[5], a0, a1, b0, b1, c)
    s23_0, s23_1 = _isq(r23_0, r23_1)
    s13_0, s13_1 = _isq(r13_0, r13_1)
    s12_0, s12_1 = _isq(r12_0, r12_1)
    x0, x1 = _imul(r12_0, r12_1, r13_0, r13_1)
    cr0, cr1 = _imul(x0, x1, r23_0, r23_1)
    dr0 = 1.0 + 2.0 * cr0 - s23_1 - s13_1 - s12_1
    dr1 = 1.0 + 2.0 * cr1 - s23_0 - s13_0 - s12_0
    cl, ch = _imul(diag0, diag1, dr0, dr1)
    out_lo = lo
    if cl > out_lo:
        out_lo = cl
    out_hi = hi
    if ch < out_hi:
        out_hi = ch
    return out_lo, out_hi


@njit(**_KW)
def _q_bounds_row(m, r, lo, hi):
    """``dichotomy._q_bounds`` for one row: the ≤ 6 terms summed left to right."""
    n = lo.shape[0]
    v = m[r, 0]
    if v > 0.0:
        q_min = v * lo[0]
        q_max = v * hi[0]
    else:
        q_min = v * hi[0]
        q_max = v * lo[0]
    for j in range(1, n):
        v = m[r, j]
        if v > 0.0:
            q_min = q_min + v * lo[j]
            q_max = q_max + v * hi[j]
        else:
            q_min = q_min + v * hi[j]
            q_max = q_max + v * lo[j]
    return q_min, q_max


@njit(**_KW)
def _af_interval(basis_t, lo, hi, af_lo, af_hi):
    """``dichotomy._af_interval`` into two length-6 buffers."""
    n = lo.shape[0]
    for i in range(6):
        v = basis_t[i, 0]
        if v > 0.0:
            s_lo = v * lo[0]
            s_hi = v * hi[0]
        else:
            s_lo = v * hi[0]
            s_hi = v * lo[0]
        for j in range(1, n):
            v = basis_t[i, j]
            if v > 0.0:
                s_lo = s_lo + v * lo[j]
                s_hi = s_hi + v * hi[j]
            else:
                s_lo = s_lo + v * hi[j]
                s_hi = s_hi + v * lo[j]
        af_lo[i] = s_lo
        af_hi[i] = s_hi


@njit(**_KW)
def _box_test(m, rows, r0, r1, lo, hi, basis_t, q_hi, band_lo, band_hi, swaps,
              lo_s, hi_s, n_unindexed, cos_max, out, o0,
              q_min_buf, q_max_buf, counts, first, af_lo, af_hi):
    """``dichotomy._test_box`` over ``rows[r0:r1]`` of ``m``.

    Returns ``(ok, n_out, width, unique)`` and writes the surviving row indices
    to ``out[o0:o0 + n_out]`` in their original order.  The prunes run in a
    different order from the numpy function's — every one of them is a
    ``return None`` with no side effect, so which fires first changes nothing
    but the cost.
    """
    _af_interval(basis_t, lo, hi, af_lo, af_hi)
    if af_hi[0] <= 0.0 or af_hi[1] <= 0.0 or af_hi[2] <= 0.0:
        return False, 0, 0.0, False
    for s in range(swaps.shape[0]):
        if af_hi[swaps[s, 0]] < af_lo[swaps[s, 1]]:
            return False, 0, 0.0, False
    det_lo, det_hi = _det(af_lo, af_hi, cos_max)
    if det_hi < band_lo or det_lo > band_hi:
        return False, 0, 0.0, False

    # the ``q_min <= q_hi`` filter: kept rows, in order, into the scratch
    n_kept = 0
    for i in range(r0, r1):
        r = rows[i]
        qa, qb = _q_bounds_row(m, r, lo, hi)
        if qa <= q_hi:
            q_min_buf[n_kept] = qa
            q_max_buf[n_kept] = qb
            out[o0 + n_kept] = r        # provisional; compacted below
            n_kept += 1
    if n_kept == 0:
        return False, 0, 0.0, False

    n_lines = lo_s.shape[0]
    for ln in range(n_lines):
        counts[ln] = 0
        first[ln] = -1
    n_out = 0
    width = 0.0
    for k in range(n_kept):
        qa = q_min_buf[k]
        qb = q_max_buf[k]
        any_hit = False
        for ln in range(n_lines):
            if qa <= hi_s[ln] and qb >= lo_s[ln]:
                any_hit = True
                counts[ln] += 1
                if first[ln] < 0:
                    first[ln] = k
        if any_hit:
            # np.max over (q_max - q_min)[relevant], NaN-propagating
            w = qb - qa
            if n_out == 0 or w > width or w != w:
                if width == width:
                    width = w
            out[o0 + n_out] = out[o0 + k]
            n_out += 1

    n_hit_lines = 0
    max_count = 0
    for ln in range(n_lines):
        if counts[ln] > 0:
            n_hit_lines += 1
        if counts[ln] > max_count:
            max_count = counts[ln]
    if n_lines - n_hit_lines > n_unindexed:
        return False, 0, 0.0, False

    # _assignment_possible: Hall's condition in its two free forms
    if n_out < n_lines - n_unindexed:
        return False, 0, 0.0, False
    n_forced = 0
    for ln in range(n_lines):
        if counts[ln] == 1:
            n_forced += 1
    if n_forced > 1:
        distinct = 0
        for ln in range(n_lines):
            if counts[ln] != 1:
                continue
            seen = False
            for pv in range(ln):
                if counts[pv] == 1 and first[pv] == first[ln]:
                    seen = True
                    break
            if not seen:
                distinct += 1
        if distinct < n_forced - n_unindexed:
            return False, 0, 0.0, False

    if n_out == 0:
        width = 0.0
    unique = n_lines > 0 and max_count <= 1
    return True, n_out, width, unique


@njit(**_KW)
def _child_key(m, rows, r0, r1, lo, hi, lo_s, hi_s, n_unindexed, line_hit):
    """``dichotomy._push_children``'s test of one child: ``(ok, misses, pairs)``."""
    n_lines = lo_s.shape[0]
    for ln in range(n_lines):
        line_hit[ln] = 0
    pairs = 0
    n_rows_hit = 0
    for i in range(r0, r1):
        qa, qb = _q_bounds_row(m, rows[i], lo, hi)
        row_hit = False
        for ln in range(n_lines):
            if qa <= hi_s[ln] and qb >= lo_s[ln]:
                line_hit[ln] = 1
                pairs += 1
                row_hit = True
        if row_hit:
            n_rows_hit += 1
    n_hit_lines = 0
    for ln in range(n_lines):
        n_hit_lines += line_hit[ln]
    misses = n_lines - n_hit_lines
    if misses > n_unindexed:
        return False, misses, pairs
    if n_rows_hit < n_lines - n_unindexed:
        return False, misses, pairs
    return True, misses, pairs


@njit(**_KW)
def test_rows(m, rows, lo, hi, basis_t, q_hi, band_lo, band_hi, swaps, lo_s,
              hi_s, n_unindexed, cos_max, out, q_min_buf, q_max_buf, counts,
              first, af_lo, af_hi):
    """One box, standalone — the grid pass and the equivalence tests call this."""
    return _box_test(m, rows, 0, rows.shape[0], lo, hi, basis_t, q_hi, band_lo,
                     band_hi, swaps, lo_s, hi_s, n_unindexed, cos_max, out, 0,
                     q_min_buf, q_max_buf, counts, first, af_lo, af_hi)


@njit(**_KW)
def traverse(m, basis_t, q_hi, band_lo, band_hi, swaps, lo_s, hi_s,
             n_unindexed, cos_max, tol_accept, max_depth,
             st_lo, st_hi, st_depth, st_start, st_len,
             pool, base_top, state,
             leaf_lo, leaf_hi, leaf_width, row_chunk,
             q_min_buf, q_max_buf, counts, first, af_lo, af_hi, line_hit):
    """Phase 2 of ``_search_one``: depth-first bisection until a handback.

    ``state`` is ``[top, pool_top, n_leaves, n_boxes, n_rows]``, read and
    written in place so a call resumes exactly where the last one stopped.
    Returns :data:`DONE`, :data:`LEAVES`, :data:`CHUNK` or :data:`GROW`.
    """
    n = st_lo.shape[1]
    top = state[0]
    pool_top = state[1]
    n_leaves = state[2]
    work = 0
    lo = np.empty(n)
    hi = np.empty(n)
    child_lo = np.empty(n)
    child_hi = np.empty(n)
    while top > 0:
        if work >= row_chunk:
            state[0] = top
            state[1] = pool_top
            state[2] = n_leaves
            return CHUNK
        e = top - 1
        s = st_start[e]
        ln = st_len[e]
        live = s + ln
        if live < base_top:
            live = base_top
        if live + ln > pool.shape[0]:
            state[0] = top
            state[1] = pool_top
            state[2] = n_leaves
            return GROW
        top = e
        pool_top = live
        # copied out: the children are about to be written over slot ``e``
        for j in range(n):
            lo[j] = st_lo[e, j]
            hi[j] = st_hi[e, j]
        depth = st_depth[e]
        state[3] += 1
        state[4] += ln
        work += ln

        ok, k, width, unique = _box_test(
            m, pool, s, s + ln, lo, hi, basis_t, q_hi, band_lo, band_hi, swaps,
            lo_s, hi_s, n_unindexed, cos_max, pool, pool_top,
            q_min_buf, q_max_buf, counts, first, af_lo, af_hi)
        if not ok:
            continue
        if unique or width <= tol_accept or depth >= max_depth:
            for j in range(n):
                leaf_lo[n_leaves, j] = lo[j]
                leaf_hi[n_leaves, j] = hi[j]
            leaf_width[n_leaves] = width
            n_leaves += 1
            if n_leaves == leaf_width.shape[0]:
                state[0] = top
                state[1] = pool_top
                state[2] = n_leaves
                return LEAVES
            continue
        if k == 0:
            continue

        # bisect the dimension that moves Q most: (hi - lo) * max |m| over the
        # survivors, first maximum, NaN winning as np.argmax has it
        j_best = 0
        best = 0.0
        for j in range(n):
            col = 0.0
            for i in range(pool_top, pool_top + k):
                v = abs(m[pool[i], j])
                if i == pool_top or v > col or v != v:
                    if col == col or i == pool_top:
                        col = v
            span = (hi[j] - lo[j]) * col
            if j == 0:
                best = span
            elif best == best and (span > best or span != span):
                best = span
                j_best = j
        mid = 0.5 * (lo[j_best] + hi[j_best])

        # left child (lo, hi with hi[j]=mid), right child (lo with lo[j]=mid, hi)
        for j in range(n):
            child_hi[j] = hi[j]
            child_lo[j] = lo[j]
        child_hi[j_best] = mid
        ok_l, miss_l, pair_l = _child_key(m, pool, pool_top, pool_top + k, lo,
                                          child_hi, lo_s, hi_s, n_unindexed,
                                          line_hit)
        child_lo[j_best] = mid
        ok_r, miss_r, pair_r = _child_key(m, pool, pool_top, pool_top + k,
                                          child_lo, hi, lo_s, hi_s, n_unindexed,
                                          line_hit)
        # sorted(..., reverse=True) is stable: the larger key goes first (deeper
        # in the stack), a tie keeps left before right
        left_first = True
        if ok_l and ok_r:
            if miss_l < miss_r or (miss_l == miss_r and pair_l < pair_r):
                left_first = False
        for turn in range(2):
            is_left = (turn == 0) == left_first
            if is_left and not ok_l:
                continue
            if (not is_left) and not ok_r:
                continue
            for j in range(n):
                st_lo[top, j] = lo[j]
                st_hi[top, j] = hi[j]
            if is_left:
                st_hi[top, j_best] = mid
            else:
                st_lo[top, j_best] = mid
            st_depth[top] = depth + 1
            st_start[top] = pool_top
            st_len[top] = k
            top += 1
        pool_top += k
    state[0] = top
    state[1] = pool_top
    state[2] = n_leaves
    return DONE


def build() -> dict:
    """Compile (or load from the disk cache) both entry points and hand them back."""
    m = np.zeros((1, 1))
    rows = np.zeros(1, dtype=np.int64)
    one = np.ones(1)
    basis_t = np.zeros((6, 1))
    swaps = np.zeros((0, 2), dtype=np.int64)
    ints = np.zeros(1, dtype=np.int64)
    f6 = np.zeros(6)
    test_rows(m, rows, np.zeros(1), one, basis_t, 1.0, 0.0, 1.0, swaps, one,
              one, 0, 0.5, ints.copy(), np.zeros(1), np.zeros(1), ints.copy(),
              ints.copy(), f6.copy(), f6.copy())
    state = np.zeros(5, dtype=np.int64)
    traverse(m, basis_t, 1.0, 0.0, 1.0, swaps, one, one, 0, 0.5, 1.0, 1,
             np.zeros((1, 1)), np.zeros((1, 1)), ints.copy(), ints.copy(),
             ints.copy(), ints.copy(), 0, state, np.zeros((1, 1)),
             np.zeros((1, 1)), np.zeros(1), 1, np.zeros(1), np.zeros(1),
             ints.copy(), ints.copy(), f6.copy(), f6.copy(), ints.copy())
    return {"test_rows": test_rows, "traverse": traverse}
