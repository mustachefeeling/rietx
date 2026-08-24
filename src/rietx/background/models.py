"""Refinable background models (evaluation used by the forward model)."""

from __future__ import annotations

import math

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


def bspline_design_matrix(two_theta: np.ndarray, breakpoints: np.ndarray
                          ) -> np.ndarray:
    """Clamped cubic B-spline design matrix, shape (n_breaks + 2, n_points).

    Knot vector t = [b₀]*3 + breakpoints + [b_m]*3 (de Boor); the background
    is linear in the coefficients, so these rows are exact Jacobian columns —
    the same property the Chebyshev design has.  Points outside the
    breakpoint span are clamped to the ends (flat extrapolation of the basis)
    so a cropped fit range never errors.
    """
    x = np.asarray(two_theta, dtype=np.float64)
    b = np.asarray(breakpoints, dtype=np.float64)
    from scipy.interpolate import BSpline

    t = np.concatenate([[b[0]] * 3, b, [b[-1]] * 3])
    eps = 1e-12 * max(b[-1] - b[0], 1.0)
    xc = np.clip(x, b[0], b[-1] - eps)
    design = BSpline.design_matrix(xc, t, 3).toarray().T  # (n_basis, n_points)
    return np.ascontiguousarray(design)


def second_difference_matrix(n: int) -> np.ndarray:
    """The (n−2, n) second-difference operator D₂ used by the P-spline
    penalty rows √λ·D₂·c (Eilers & Marx, 1996, Stat. Sci. 11, 89)."""
    d = np.zeros((max(n - 2, 0), n), dtype=np.float64)
    for i in range(n - 2):
        d[i, i:i + 3] = (1.0, -2.0, 1.0)
    return d


#: −4 ln 2, the Gaussian's FWHM normalisation, as one named constant so the
#: numpy and traced evaluations cannot spell it two ways.  The association is
#: fixed too: ``FOUR_LN2_NEG * (u * u)`` with u = (2θ − 2θ₀)/Γ, one spelling,
#: because unlike the Bragg profile there is no second caller with a reason to
#: reproduce a different one (root CLAUDE.md → Conventions, the two-Ω rule:
#: the point is that each caller owns *which* spelling it reproduces, and here
#: there is only one to own).
FOUR_LN2_NEG = -4.0 * math.log(2.0)


def background_peak_curve(two_theta, position, height, fwhm, xp):
    """One explicit broad background Gaussian, evaluated on the whole grid.

        y(2θ) = h · exp[ −4 ln2 · ((2θ − 2θ₀)/Γ)² ]

    The evaluator for :class:`rietx.schemas.instrument.BackgroundPeak`, and the
    **only** one: :meth:`rietx.model.forward.CompiledModel.background` calls it
    for the numpy path and, through ``get_backend()``, for every traced backend,
    so there is no twin to drift (``backend/traced.py``'s reason for existing,
    satisfied by having nothing to copy).

    Empirical basis function, not a peak shape — see
    :class:`~rietx.schemas.instrument.BackgroundPeak` for the citation of the
    *practice* and the note that no physical derivation is claimed.

    ``two_theta`` must already be lifted onto ``xp`` by the caller: it is a
    frozen constant and ``position`` is θ-derived, so a bare ndarray here would
    be a frozen numpy constant on the left of a python operator against a traced
    value (root CLAUDE.md → Conventions: raises on torch, mis-routes under
    functorch).  ``height`` and ``fwhm`` are 0-d traced scalars; ``fwhm`` is
    floored away from zero by the schema, so the division has no pole.

    Whole-grid, no frozen window — the term is broad *by declaration*, which is
    what makes it a background feature, so a window would be the whole grid.
    """
    u = (two_theta - position) / fwhm
    return height * xp.exp(FOUR_LN2_NEG * (u * u))
