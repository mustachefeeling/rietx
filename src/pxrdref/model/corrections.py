"""Geometric intensity corrections for constant-wavelength powder data."""

from __future__ import annotations

import numpy as np

from ..backend import get_backend


def lorentz_polarization(two_theta_deg: np.ndarray, polarization: float) -> np.ndarray:
    """Combined Lorentz-polarisation factor for CW powder diffraction.

        Lp(θ) = [K + (1 − K)·cos²2θ] / (sin²θ · cosθ)

    The 1/(sin²θ cosθ) Lorentz part is the standard CW powder factor
    (single-crystal rotation Lorentz × powder-ring statistics; International
    Tables C §6.2, Klug & Alexander).  K is the σ-polarised beam fraction —
    see :class:`pxrdref.schemas.instrument.Source` (K = 0.5 unpolarised lab
    beam; K ≈ 0.99 synchrotron vertical-plane diffraction).
    """
    xp = get_backend()
    tt = xp.radians(xp.asarray(two_theta_deg, dtype=np.float64))
    th = 0.5 * tt
    pol = polarization + (1.0 - polarization) * xp.cos(tt) ** 2
    return pol / (xp.sin(th) ** 2 * xp.cos(th))


def displacement_shift_deg(theta_deg: np.ndarray, s_mm: float,
                           radius_mm: float) -> np.ndarray:
    """Bragg-Brentano sample-displacement peak shift, in degrees 2θ.

        Δ2θ = −(2·s/R)·cosθ   [radians]

    for a flat specimen whose surface sits a distance ``s`` off the goniometer
    axis (positive toward the source/detector side of the focusing circle),
    R = goniometer radius.  Wilson (1963), *Mathematical Theory of X-ray
    Powder Diffractometry*, ch. 4; Klug & Alexander (1974), ch. 5.  The cosθ
    dependence is what separates it from a constant zero-point error.
    """
    xp = get_backend()
    th = xp.radians(xp.asarray(theta_deg, dtype=np.float64))
    return xp.degrees(-2.0 * (s_mm / radius_mm) * xp.cos(th))


def transparency_shift_deg(two_theta_deg: np.ndarray, t_coef: float) -> np.ndarray:
    """Bragg-Brentano sample-transparency peak shift, in degrees 2θ.

        Δ2θ = −t·sin2θ   [radians],   t = 1/(2·μ_eff·R)

    finite beam penetration puts the effective diffracting surface below the
    physical one, pulling peaks to lower angle with a sin2θ signature
    (thick-sample limit; Klug & Alexander, 1974, ch. 5; Wilson, 1963).
    ``t_coef`` is the dimensionless coefficient t ≥ 0; for strongly absorbing
    samples t → 0 and the correction vanishes.
    """
    xp = get_backend()
    tt = xp.radians(xp.asarray(two_theta_deg, dtype=np.float64))
    return xp.degrees(-t_coef * xp.sin(tt))
