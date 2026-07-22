"""Angular dependence of profile widths.

Gaussian variance (Caglioti, Paoletti & Ricci, 1958, Nucl. Instrum. 3, 223):

    Γ_G²(θ) = U·tan²θ + V·tanθ + W          [deg² 2θ]

Lorentzian FWHM with instrument + sample contributions:

    Γ_L(θ) = (X + Xs)/cosθ + (Y + Ys)·tanθ  [deg 2θ]

The 1/cosθ term carries Scherrer (crystallite size) broadening and the tanθ
term microstrain broadening; instrument (X, Y) and sample (Xs, Ys) parts add
because Lorentzian convolution adds FWHMs.  Note the letter conventions differ
between codes (GSAS: X=size, Y=strain; FullProf swaps them) — this module
documents the *physics* via argument names.
"""

from __future__ import annotations

import numpy as np

_MIN_GAMMA_G2 = 1e-8  # deg²; keeps Γ_G real when U,V,W make the quadratic dip


def gaussian_fwhm(theta_deg: np.ndarray, u: float, v: float, w: float) -> np.ndarray:
    """Γ_G(θ) from the Caglioti law; input θ (NOT 2θ) in degrees."""
    t = np.tan(np.radians(theta_deg))
    g2 = u * t * t + v * t + w
    return np.sqrt(np.maximum(g2, _MIN_GAMMA_G2))


def lorentzian_fwhm(theta_deg: np.ndarray, x_size: float, y_strain: float) -> np.ndarray:
    """Γ_L(θ) = x_size/cosθ + y_strain·tanθ; input θ in degrees."""
    th = np.radians(theta_deg)
    return x_size / np.cos(th) + y_strain * np.tan(th)
