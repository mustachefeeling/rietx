"""Refinable background models (evaluation used by the forward model)."""

from __future__ import annotations

import numpy as np


def chebyshev_design_matrix(two_theta: np.ndarray, n_terms: int,
                            tt_min: float, tt_max: float) -> np.ndarray:
    """Design matrix T of shape (n_terms, n_points) of shifted Chebyshev
    polynomials of the first kind on x = 2(2θ−min)/(max−min) − 1.

    The background is linear in its coefficients, y_bkg = cᵀ·T, so these rows
    are also the *exact* Jacobian columns for the coefficients.
    """
    x = 2.0 * (np.asarray(two_theta, dtype=np.float64) - tt_min) / (tt_max - tt_min) - 1.0
    T = np.empty((n_terms, len(x)), dtype=np.float64)
    if n_terms > 0:
        T[0] = 1.0
    if n_terms > 1:
        T[1] = x
    for n in range(2, n_terms):
        T[n] = 2.0 * x * T[n - 1] - T[n - 2]
    return T


def chebyshev_background(two_theta: np.ndarray, coefficients: np.ndarray,
                         tt_min: float, tt_max: float) -> np.ndarray:
    T = chebyshev_design_matrix(two_theta, len(coefficients), tt_min, tt_max)
    return np.asarray(coefficients, dtype=np.float64) @ T


def interpolate_fixed(two_theta: np.ndarray, fixed_tt: np.ndarray,
                      fixed_y: np.ndarray) -> np.ndarray:
    """Fixed estimated background sampled onto the pattern grid (held, never
    subtracted — it is added inside the model so weights stay correct)."""
    return np.interp(np.asarray(two_theta, dtype=np.float64),
                     np.asarray(fixed_tt, dtype=np.float64),
                     np.asarray(fixed_y, dtype=np.float64))
