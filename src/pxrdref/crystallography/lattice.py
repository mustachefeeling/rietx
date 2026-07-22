"""Lattice metrics: cell → reciprocal metric tensor → d-spacings → 2θ.

The d-spacing of reflection (h,k,l) follows from the reciprocal metric tensor
G* (International Tables B, ch. 1.1):

    1/d² = h_vec · G* · h_vecᵀ,   G* = G⁻¹,

where G is the direct metric tensor built from (a, b, c, α, β, γ).  Peak
positions then follow Bragg's law, 2θ = 2·arcsin(λ / 2d).
"""

from __future__ import annotations

import numpy as np


def direct_metric_tensor(a: float, b: float, c: float,
                         alpha: float, beta: float, gamma: float) -> np.ndarray:
    """Direct-space metric tensor G (angles in degrees)."""
    al, be, ga = np.radians([alpha, beta, gamma])
    return np.array([
        [a * a, a * b * np.cos(ga), a * c * np.cos(be)],
        [a * b * np.cos(ga), b * b, b * c * np.cos(al)],
        [a * c * np.cos(be), b * c * np.cos(al), c * c],
    ], dtype=np.float64)


def reciprocal_metric_tensor(a: float, b: float, c: float,
                             alpha: float, beta: float, gamma: float) -> np.ndarray:
    return np.linalg.inv(direct_metric_tensor(a, b, c, alpha, beta, gamma))


def d_spacings(hkl: np.ndarray, a: float, b: float, c: float,
               alpha: float, beta: float, gamma: float) -> np.ndarray:
    """d (Å) for an (N,3) integer hkl array."""
    gstar = reciprocal_metric_tensor(a, b, c, alpha, beta, gamma)
    h = np.asarray(hkl, dtype=np.float64)
    inv_d2 = np.einsum("ni,ij,nj->n", h, gstar, h)
    return 1.0 / np.sqrt(inv_d2)


def two_theta_deg(d: np.ndarray, wavelength: float) -> np.ndarray:
    """Bragg angles 2θ (degrees); NaN where λ/2d > 1 (no reflection)."""
    s = wavelength / (2.0 * np.asarray(d, dtype=np.float64))
    with np.errstate(invalid="ignore"):
        return np.degrees(2.0 * np.arcsin(np.where(s <= 1.0, s, np.nan)))


def cell_volume(a: float, b: float, c: float,
                alpha: float, beta: float, gamma: float) -> float:
    return float(np.sqrt(np.linalg.det(direct_metric_tensor(a, b, c, alpha, beta, gamma))))
