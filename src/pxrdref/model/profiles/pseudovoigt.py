"""Thompson-Cox-Hastings pseudo-Voigt peak profile.

The pseudo-Voigt approximates the Voigt (Gaussian ⊗ Lorentzian) as

    pV(x) = η·L(x; Γ) + (1−η)·G(x; Γ)

with a single FWHM Γ and mixing η computed from the underlying Gaussian and
Lorentzian widths via the Thompson, Cox & Hastings (1987, J. Appl. Cryst. 20,
79) polynomial forms:

    Γ⁵ = Γ_G⁵ + 2.69269 Γ_G⁴Γ_L + 2.42843 Γ_G³Γ_L² + 4.47163 Γ_G²Γ_L³
         + 0.07842 Γ_G Γ_L⁴ + Γ_L⁵                                (TCH eq. 4)

    η  = 1.36603 q − 0.47719 q² + 0.11116 q³,   q = Γ_L/Γ         (TCH eq. 5)

Both component shapes are unit-area normalised so that ∫pV dx = 1 and the
reflection intensity enters purely through the prefactor in the forward model:

    G(x) = (2/Γ)·√(ln2/π)·exp(−4 ln2 · x²/Γ²)
    L(x) = (2/(πΓ)) / (1 + 4x²/Γ²)
"""

from __future__ import annotations

import numpy as np

_TCH_GAMMA = (2.69269, 2.42843, 4.47163, 0.07842)
_TCH_ETA = (1.36603, -0.47719, 0.11116)
_4LN2 = 4.0 * np.log(2.0)


def tch_gamma_eta(gamma_g: np.ndarray, gamma_l: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Combined FWHM Γ and mixing η from component FWHMs (TCH 1987)."""
    gg = np.asarray(gamma_g, dtype=np.float64)
    gl = np.asarray(gamma_l, dtype=np.float64)
    c1, c2, c3, c4 = _TCH_GAMMA
    gamma5 = (gg**5 + c1 * gg**4 * gl + c2 * gg**3 * gl**2
              + c3 * gg**2 * gl**3 + c4 * gg * gl**4 + gl**5)
    gamma = gamma5 ** 0.2
    q = np.where(gamma > 0.0, gl / np.where(gamma > 0.0, gamma, 1.0), 0.0)
    e1, e2, e3 = _TCH_ETA
    eta = e1 * q + e2 * q**2 + e3 * q**3
    return gamma, eta


def pseudo_voigt(x: np.ndarray, gamma: np.ndarray, eta: np.ndarray) -> np.ndarray:
    """Unit-area pseudo-Voigt evaluated at offsets ``x`` (same units as Γ).

    Broadcasts: x may be (..., N) with gamma/eta scalars or matching shapes.
    """
    g = np.asarray(gamma, dtype=np.float64)
    lorentz = (2.0 / (np.pi * g)) / (1.0 + 4.0 * (x / g) ** 2)
    gauss = (2.0 / g) * np.sqrt(np.log(2.0) / np.pi) * np.exp(-_4LN2 * (x / g) ** 2)
    return eta * lorentz + (1.0 - eta) * gauss
