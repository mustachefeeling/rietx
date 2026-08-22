"""The numba kernels behind :mod:`rietx.model.compiled` (WP-1115).

Imported lazily and only when numba is present, so this module may import it at
top level; :mod:`rietx.model.compiled` owns the soft-import, the fallback and
every rule about when these run.  Read that module's docstring first — what is
here is only the arithmetic.

**Every expression below is a transcription, not a derivation.**  Each one
mirrors, operation for operation and association for association, the numpy
expression it replaces in ``model/profiles/pseudovoigt.py`` and
``model/forward.py``.  Where the two profile spellings differ they differ in
exactly one place — the Gaussian exponent, ``-4ln2·(x/Γ)²`` in the forward
against ``((-4ln2)·u)·u`` in the derivative bases — and that difference is the
whole of the ``spell`` argument.  The Lorentzian is common to both: ``(4·u)·u``
and ``4·(u·u)`` are bit-equal because multiplying by a power of two is exact.

So the review question for any edit here is not "is this the right formula" but
"is this the same rounding as the numpy line it copies".  Rewriting
``a * b * c`` as ``a * (b * c)`` is a real change, and
``tests/test_compiled_kernels.py`` is what says so.
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

# The three constants, copied by value rather than imported, because a numba
# kernel closes over a python global as a compile-time constant and the module
# they live in is a numpy module: `_SQRT_LN2_PI` there is an np.float64, which
# is the same double.  Kept as the bare root so the (2/Γ)·√(ln2/π) grouping is
# unchanged from the numpy expression (pseudovoigt.py says why).
_4LN2 = 4.0 * math.log(2.0)
_SQRT_LN2_PI = math.sqrt(math.log(2.0) / math.pi)
_PI = math.pi

_KW = {"cache": True, "nogil": True, "fastmath": False}


@njit(**_KW)
def _accum(y, i0, i1, c0, p0, c1, p1, c2, p2, c3, p3, n_terms):
    """The bit-identical scatter (``accumulate_planes``).

    ``np.bincount`` walks the flattened (row, term, point) contributions in
    order, so for any one output point the additions from a part arrive
    row-major and, within a row, term-major.  This loop is point-major inside
    the row, which is the *same* per-element sequence — each term contributes
    exactly one value to a given point from a given row — with the better
    locality.  Each ``+=`` is separate on purpose: folding two terms into one
    add would change the association and with it the bits.

    The pad tail is not walked.  Planes arrive pad-zeroed, so those
    contributions are ±0.0 and dropping them is bitwise neutral, and within the
    window ``layout.idx[r, p]`` is exactly ``i0[r] + p``.
    """
    for r in range(i0.shape[0]):
        b = i0[r]
        w = i1[r] - b
        if n_terms == 1:
            a0 = c0[r]
            for p in range(w):
                y[b + p] += a0 * p0[r, p]
        elif n_terms == 2:
            a0 = c0[r]
            a1 = c1[r]
            for p in range(w):
                q = b + p
                y[q] += a0 * p0[r, p]
                y[q] += a1 * p1[r, p]
        elif n_terms == 3:
            a0 = c0[r]
            a1 = c1[r]
            a2 = c2[r]
            for p in range(w):
                q = b + p
                y[q] += a0 * p0[r, p]
                y[q] += a1 * p1[r, p]
                y[q] += a2 * p2[r, p]
        else:
            a0 = c0[r]
            a1 = c1[r]
            a2 = c2[r]
            a3 = c3[r]
            for p in range(w):
                q = b + p
                y[q] += a0 * p0[r, p]
                y[q] += a1 * p1[r, p]
                y[q] += a2 * p2[r, p]
                y[q] += a3 * p3[r, p]


@njit(**_KW)
def _omega_sym(out, x, rows, pos, w1, w2, width, spell, lo, hi):
    """Ω on symmetric rows, in whichever spelling ``spell`` names."""
    for r in range(lo, hi):
        j = rows[r]
        g = w1[j]
        e = w2[j]
        p = pos[j]
        for c in range(width[j]):
            u = (x[j, c] - p) / g
            uu = u * u
            if spell == 0:
                ex = -_4LN2 * uu
            else:
                ex = (-_4LN2 * u) * u
            lor = (2.0 / (_PI * g)) / (1.0 + 4.0 * uu)
            gau = (2.0 / g) * _SQRT_LN2_PI * math.exp(ex)
            out[j, c] = e * lor + (1.0 - e) * gau


@njit(**_KW)
def _omega_fcj(out, x, rows, w1, w2, width, phi, om, spell, lo, hi):
    """Node-weighted Ω on one FCJ bucket's rows.

    ``phi``/``om`` are bucket-local (row ``r``), everything else is indexed by
    the global row ``rows[r]``; ``phi`` already carries the peak position, as
    ``fcj_offsets_weights_batch`` returns it.  The node sum runs innermost, so
    the (rows, nodes, window) transient never exists.
    """
    n_nodes = phi.shape[1]
    for r in range(lo, hi):
        j = rows[r]
        g = w1[j]
        e = w2[j]
        for c in range(width[j]):
            xv = x[j, c]
            s = 0.0
            for m in range(n_nodes):
                u = (xv - phi[r, m]) / g
                uu = u * u
                if spell == 0:
                    ex = -_4LN2 * uu
                else:
                    ex = (-_4LN2 * u) * u
                lor = (2.0 / (_PI * g)) / (1.0 + 4.0 * uu)
                gau = (2.0 / g) * _SQRT_LN2_PI * math.exp(ex)
                s += om[r, m] * (e * lor + (1.0 - e) * gau)
            out[j, c] = s


@njit(**_KW)
def _bases_sym(omega, d_pos, d_gamma, d_eta, x, rows, pos, w1, w2, width,
               lo, hi):
    """Ω and its three partials on symmetric rows — ``pseudo_voigt_derivs``.

    ``d_pos`` is ``-∂Ω/∂x``, the sign ``derivative_bases`` applies.
    """
    for r in range(lo, hi):
        j = rows[r]
        g = w1[j]
        e = w2[j]
        p = pos[j]
        for c in range(width[j]):
            u = (x[j, c] - p) / g
            den = 1.0 + 4.0 * u * u
            lor = (2.0 / (_PI * g)) / den
            gau = (2.0 / g) * _SQRT_LN2_PI * math.exp((-_4LN2 * u) * u)
            omega[j, c] = e * lor + (1.0 - e) * gau
            dl_dx = -lor * (8.0 * u / g) / den
            dg_dx = -gau * (2.0 * _4LN2 * u / g)
            d_pos[j, c] = -(e * dl_dx + (1.0 - e) * dg_dx)
            dl_dg = (lor / g) * (8.0 * u * u / den - 1.0)
            dg_dg = (gau / g) * (2.0 * _4LN2 * u * u - 1.0)
            d_gamma[j, c] = e * dl_dg + (1.0 - e) * dg_dg
            d_eta[j, c] = lor - gau


@njit(**_KW)
def _bases_fcj(omega, d_pos, d_gamma, d_eta, d_sl, d_hl, x, rows, w1, w2,
               width, phi, om, dphi, dom, dphi_sl, dom_sl, dphi_hl, dom_hl,
               has_ax, lo, hi):
    """Every basis plane for one FCJ bucket, in one pass over the nodes.

    The node-FD derivatives are two whole sums subtracted, never a per-node
    difference: ``d_pos = Σ dom·Ω − Σ (om·dφ)·∂Ω/∂x``, exactly as
    ``_node_mix(dom, pv) - _node_mix(om * dphi, ddx)`` groups them.  ``d_sl``
    and ``d_hl`` are the same shape one aperture over, and are skipped entirely
    — not written as zeros — when the caller is not building axial columns.
    """
    n_nodes = phi.shape[1]
    for r in range(lo, hi):
        j = rows[r]
        g = w1[j]
        e = w2[j]
        for c in range(width[j]):
            xv = x[j, c]
            s_om = 0.0
            s_dg = 0.0
            s_de = 0.0
            a_pos = 0.0
            b_pos = 0.0
            a_sl = 0.0
            b_sl = 0.0
            a_hl = 0.0
            b_hl = 0.0
            for m in range(n_nodes):
                u = (xv - phi[r, m]) / g
                den = 1.0 + 4.0 * u * u
                lor = (2.0 / (_PI * g)) / den
                gau = (2.0 / g) * _SQRT_LN2_PI * math.exp((-_4LN2 * u) * u)
                pv = e * lor + (1.0 - e) * gau
                dl_dx = -lor * (8.0 * u / g) / den
                dg_dx = -gau * (2.0 * _4LN2 * u / g)
                ddx = e * dl_dx + (1.0 - e) * dg_dx
                dl_dg = (lor / g) * (8.0 * u * u / den - 1.0)
                dg_dg = (gau / g) * (2.0 * _4LN2 * u * u - 1.0)
                w = om[r, m]
                s_om += w * pv
                s_dg += w * (e * dl_dg + (1.0 - e) * dg_dg)
                s_de += w * (lor - gau)
                a_pos += dom[r, m] * pv
                b_pos += (w * dphi[r, m]) * ddx
                if has_ax:
                    a_sl += dom_sl[r, m] * pv
                    b_sl += (w * dphi_sl[r, m]) * ddx
                    a_hl += dom_hl[r, m] * pv
                    b_hl += (w * dphi_hl[r, m]) * ddx
            omega[j, c] = s_om
            d_gamma[j, c] = s_dg
            d_eta[j, c] = s_de
            d_pos[j, c] = a_pos - b_pos
            if has_ax:
                d_sl[j, c] = a_sl - b_sl
                d_hl[j, c] = a_hl - b_hl


def build() -> dict:
    """Compile (or load from the disk cache) every kernel, and hand them back.

    Called once per process behind :mod:`rietx.model.compiled`'s lock.  The
    tiny call below each name is what forces compilation here rather than
    inside the first residual, so :func:`rietx.model.compiled.warm` can put the
    whole cost on a background thread.
    """
    z1 = np.zeros(1)
    z2 = np.zeros((1, 1))
    idx = np.zeros(1, dtype=np.int64)
    one = np.ones(1, dtype=np.int64)
    _accum(z1, idx, one, z1, z2, z1, z2, z1, z2, z1, z2, 1)
    _omega_sym(z2, z2, idx, z1, np.ones(1), z1, one, 0, 0, 1)
    _omega_fcj(z2, z2, idx, np.ones(1), z1, one, z2, z2, 0, 0, 1)
    _bases_sym(z2, z2, z2, z2, z2, idx, z1, np.ones(1), z1, one, 0, 1)
    _bases_fcj(z2, z2, z2, z2, z2, z2, z2, idx, np.ones(1), z1, one, z2, z2,
               z2, z2, z2, z2, z2, z2, True, 0, 1)
    return {
        "accum": _accum,
        "omega_sym": _omega_sym,
        "omega_fcj": _omega_fcj,
        "bases_sym": _bases_sym,
        "bases_fcj": _bases_fcj,
    }
