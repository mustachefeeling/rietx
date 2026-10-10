# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True, initializedcheck=False
"""WP-1939 spike: ``rietx/model/_kernels_numba.py`` transcribed to Cython.

Every expression copies the numba line it replaces, association for
association; that module's docstring is the contract.  Signatures are the
numba ones, positionally, so ``compiled._KERNELS`` can hold these instead.
"""

from libc.math cimport exp, log, sqrt, M_PI

cdef double _4LN2 = 4.0 * log(2.0)
cdef double _SQRT_LN2_PI = sqrt(log(2.0) / M_PI)
cdef double _PI = M_PI


def accum(double[::1] y, const long long[::1] i0, const long long[::1] i1,
          const double[::1] c0, const double[:, ::1] p0,
          const double[::1] c1, const double[:, ::1] p1,
          const double[::1] c2, const double[:, ::1] p2,
          const double[::1] c3, const double[:, ::1] p3, long n_terms):
    cdef Py_ssize_t r, p, q, b, w
    cdef double a0, a1, a2, a3
    with nogil:
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


def omega_sym(double[:, ::1] out, const double[:, ::1] x,
              const long long[::1] rows, const double[::1] pos,
              const double[::1] w1, const double[::1] w2,
              const long long[::1] width, long spell, Py_ssize_t lo,
              Py_ssize_t hi):
    cdef Py_ssize_t r, j, c
    cdef double g, e, p, u, uu, ex, lor, gau
    with nogil:
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
                gau = (2.0 / g) * _SQRT_LN2_PI * exp(ex)
                out[j, c] = e * lor + (1.0 - e) * gau


def omega_fcj(double[:, ::1] out, const double[:, ::1] x,
              const long long[::1] rows, const double[::1] w1,
              const double[::1] w2, const long long[::1] width,
              const double[:, ::1] phi, const double[:, ::1] om, long spell,
              Py_ssize_t lo, Py_ssize_t hi):
    cdef Py_ssize_t r, j, c, m, n_nodes = phi.shape[1]
    cdef double g, e, xv, s, u, uu, ex, lor, gau
    with nogil:
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
                    gau = (2.0 / g) * _SQRT_LN2_PI * exp(ex)
                    s += om[r, m] * (e * lor + (1.0 - e) * gau)
                out[j, c] = s


def bases_sym(double[:, ::1] omega, double[:, ::1] d_pos,
              double[:, ::1] d_gamma, double[:, ::1] d_eta,
              const double[:, ::1] x, const long long[::1] rows,
              const double[::1] pos, const double[::1] w1,
              const double[::1] w2, const long long[::1] width,
              Py_ssize_t lo, Py_ssize_t hi):
    cdef Py_ssize_t r, j, c
    cdef double g, e, p, u, den, lor, gau, dl_dx, dg_dx, dl_dg, dg_dg
    with nogil:
        for r in range(lo, hi):
            j = rows[r]
            g = w1[j]
            e = w2[j]
            p = pos[j]
            for c in range(width[j]):
                u = (x[j, c] - p) / g
                den = 1.0 + 4.0 * u * u
                lor = (2.0 / (_PI * g)) / den
                gau = (2.0 / g) * _SQRT_LN2_PI * exp((-_4LN2 * u) * u)
                omega[j, c] = e * lor + (1.0 - e) * gau
                dl_dx = -lor * (8.0 * u / g) / den
                dg_dx = -gau * (2.0 * _4LN2 * u / g)
                d_pos[j, c] = -(e * dl_dx + (1.0 - e) * dg_dx)
                dl_dg = (lor / g) * (8.0 * u * u / den - 1.0)
                dg_dg = (gau / g) * (2.0 * _4LN2 * u * u - 1.0)
                d_gamma[j, c] = e * dl_dg + (1.0 - e) * dg_dg
                d_eta[j, c] = lor - gau


def bases_fcj(double[:, ::1] omega, double[:, ::1] d_pos,
              double[:, ::1] d_gamma, double[:, ::1] d_eta,
              double[:, ::1] d_sl, double[:, ::1] d_hl,
              const double[:, ::1] x, const long long[::1] rows,
              const double[::1] w1, const double[::1] w2,
              const long long[::1] width, const double[:, ::1] phi,
              const double[:, ::1] om, const double[:, ::1] dphi,
              const double[:, ::1] dom, const double[:, ::1] dphi_sl,
              const double[:, ::1] dom_sl, const double[:, ::1] dphi_hl,
              const double[:, ::1] dom_hl, bint has_ax, Py_ssize_t lo,
              Py_ssize_t hi):
    cdef Py_ssize_t r, j, c, m, n_nodes = phi.shape[1]
    cdef double g, e, xv, s_om, s_dg, s_de, a_pos, b_pos, a_sl, b_sl, a_hl, b_hl
    cdef double u, den, lor, gau, pv, dl_dx, dg_dx, ddx, dl_dg, dg_dg, w
    with nogil:
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
                    gau = (2.0 / g) * _SQRT_LN2_PI * exp((-_4LN2 * u) * u)
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
