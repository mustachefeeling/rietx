"""Agreement indices, defined per Toby (2006), Powder Diffraction 21, 67-70.

    R_p   = Σ|y_o − y_c| / Σ y_o
    R_wp  = √[ Σ w (y_o − y_c)² / Σ w y_o² ]
    R_exp = √[ (N − P) / Σ w y_o² ]
    χ²    = Σ w (y_o − y_c)² / (N − P)        (reduced)
    GoF   = √χ² = R_wp / R_exp

``rwp_background_subtracted`` recomputes R_wp with the background removed from
both numerator-model and denominator-observed, the variant Toby recommends
when the background carries much of the raw intensity.  The Durbin-Watson
statistic d = Σ(Δᵢ−Δᵢ₋₁)²/ΣΔᵢ² on weighted residuals (Hill & Flack, 1987,
J. Appl. Cryst. 20, 356) flags serial correlation (d ≈ 2 ⇒ uncorrelated).
"""

from __future__ import annotations

import numpy as np

from ..schemas.results import Statistics


def compute_statistics(y_obs: np.ndarray, y_calc: np.ndarray, sigma: np.ndarray,
                       n_free: int, y_background: np.ndarray | None = None) -> Statistics:
    y_obs = np.asarray(y_obs, dtype=np.float64)
    y_calc = np.asarray(y_calc, dtype=np.float64)
    w = 1.0 / np.asarray(sigma, dtype=np.float64) ** 2
    n = len(y_obs)
    diff = y_obs - y_calc

    swyo2 = float(w @ (y_obs * y_obs))
    swd2 = float(w @ (diff * diff))
    rp = float(np.abs(diff).sum() / np.abs(y_obs).sum())
    rwp = float(np.sqrt(swd2 / swyo2))
    rexp = float(np.sqrt(max(n - n_free, 1) / swyo2))
    chi2 = swd2 / max(n - n_free, 1)

    rwp_bs = None
    if y_background is not None:
        net = y_obs - y_background
        denom = float(w @ (net * net))
        if denom > 0:
            rwp_bs = float(np.sqrt(swd2 / denom))

    delta = np.sqrt(w) * diff
    dw = float(np.sum(np.diff(delta) ** 2) / np.sum(delta ** 2)) if n > 2 else None

    return Statistics(
        rwp=rwp, rp=rp, rexp=rexp, chi2=chi2, gof=rwp / rexp,
        rwp_background_subtracted=rwp_bs, durbin_watson=dw,
        n_points=n, n_free_parameters=n_free,
    )
