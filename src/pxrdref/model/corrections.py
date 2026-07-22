"""Geometric intensity corrections for constant-wavelength powder data."""

from __future__ import annotations

import numpy as np


def lorentz_polarization(two_theta_deg: np.ndarray, polarization: float) -> np.ndarray:
    """Combined Lorentz-polarisation factor for CW powder diffraction.

        Lp(θ) = [K + (1 − K)·cos²2θ] / (sin²θ · cosθ)

    The 1/(sin²θ cosθ) Lorentz part is the standard CW powder factor
    (single-crystal rotation Lorentz × powder-ring statistics; International
    Tables C §6.2, Klug & Alexander).  K is the σ-polarised beam fraction —
    see :class:`pxrdref.schemas.instrument.Source` (K = 0.5 unpolarised lab
    beam; K ≈ 0.99 synchrotron vertical-plane diffraction).
    """
    tt = np.radians(np.asarray(two_theta_deg, dtype=np.float64))
    th = 0.5 * tt
    pol = polarization + (1.0 - polarization) * np.cos(tt) ** 2
    return pol / (np.sin(th) ** 2 * np.cos(th))
