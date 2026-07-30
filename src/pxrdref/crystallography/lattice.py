"""Lattice metrics: cell → reciprocal metric tensor → d-spacings → 2θ.

The d-spacing of reflection (h,k,l) follows from the reciprocal metric tensor
G* (International Tables B, ch. 1.1):

    1/d² = h_vec · G* · h_vecᵀ,   G* = G⁻¹,

where G is the direct metric tensor built from (a, b, c, α, β, γ).  Peak
positions then follow Bragg's law, 2θ = 2·arcsin(λ / 2d).

Everything here is on the θ-dependent hot path (the cell refines), so array
ops go through the backend shim ``xp`` and matrices are built with ``stack``
rather than ``np.array`` — a list of traced scalars is not coercible.
"""

from __future__ import annotations

import numpy as np

from ..backend import get_backend


def direct_metric_tensor(a: float, b: float, c: float,
                         alpha: float, beta: float, gamma: float) -> np.ndarray:
    """Direct-space metric tensor G (angles in degrees)."""
    xp = get_backend()
    cos_al = xp.cos(xp.radians(alpha))
    cos_be = xp.cos(xp.radians(beta))
    cos_ga = xp.cos(xp.radians(gamma))
    return xp.stack([
        xp.stack([a * a, a * b * cos_ga, a * c * cos_be]),
        xp.stack([a * b * cos_ga, b * b, b * c * cos_al]),
        xp.stack([a * c * cos_be, b * c * cos_al, c * c]),
    ])


def reciprocal_metric_tensor(a: float, b: float, c: float,
                             alpha: float, beta: float, gamma: float) -> np.ndarray:
    xp = get_backend()
    return xp.linalg.inv(direct_metric_tensor(a, b, c, alpha, beta, gamma))


def inv_d_squared(hkl: np.ndarray, a: float, b: float, c: float,
                  alpha: float, beta: float, gamma: float) -> np.ndarray:
    """1/d² (Å⁻²) for an (N,3) integer hkl array — the quadratic form h·G*·hᵀ.

    This is the quantity indexing works in, and the reason is that it is
    **linear in the metric**: with (A..F) = (G*₁₁, G*₂₂, G*₃₃, 2G*₂₃, 2G*₁₃,
    2G*₁₂),

        1/d² = A h² + B k² + C l² + D kl + E hl + F hk

    so a cell fitted to assigned lines is a *linear* least-squares problem,
    while d and 2θ are not linear in the metric at all (Altomare, Cuocci,
    Moliterni & Rizzi, 2019, *International Tables for Crystallography* Vol. H
    ch. 3.4, eq. 3.4.2).  :func:`d_spacings` is the reciprocal-square-root of
    this; both are on the hot path, so the arithmetic is kept in one place
    rather than recovered from ``d``.
    """
    xp = get_backend()
    gstar = reciprocal_metric_tensor(a, b, c, alpha, beta, gamma)
    h = xp.asarray(hkl, dtype=np.float64)
    return xp.einsum("ni,ij,nj->n", h, gstar, h)


def d_spacings(hkl: np.ndarray, a: float, b: float, c: float,
               alpha: float, beta: float, gamma: float) -> np.ndarray:
    """d (Å) for an (N,3) integer hkl array."""
    xp = get_backend()
    inv_d2 = inv_d_squared(hkl, a, b, c, alpha, beta, gamma)
    return 1.0 / xp.sqrt(inv_d2)


def two_theta_deg(d: np.ndarray, wavelength: float) -> np.ndarray:
    """Bragg angles 2θ (degrees); NaN where λ/2d > 1 (no reflection)."""
    xp = get_backend()
    s = wavelength / (2.0 * xp.asarray(d, dtype=np.float64))
    with np.errstate(invalid="ignore"):
        return xp.degrees(2.0 * xp.arcsin(xp.where(s <= 1.0, s, np.nan)))


def cell_volume(a: float, b: float, c: float,
                alpha: float, beta: float, gamma: float) -> float:
    # a 0-d fp64 scalar, not a python float: float() would break tracing
    xp = get_backend()
    return xp.sqrt(xp.linalg.det(direct_metric_tensor(a, b, c, alpha, beta, gamma)))
