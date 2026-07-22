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

When residuals *are* serially correlated the χ²·(JᵀJ)⁻¹ esds are too small:
neighbouring points do not carry independent information.  Bérar & Lelann
(1991, J. Appl. Cryst. 24, 1) sum consecutive same-sign weighted residuals
coherently, χ²' = Σ_runs (Σ_{i∈run} δᵢ)² ≥ χ², and multiply every esd by
√(χ²'/χ²) — the inflation factor reported here and applied to the esds.
"""

from __future__ import annotations

import numpy as np

from ..schemas.results import Statistics


def berar_lelann_factor(delta: np.ndarray) -> float:
    """Esd inflation factor for serial correlation.

    Bérar & Lelann (1991), J. Appl. Cryst. 24, 1: runs of consecutive
    weighted residuals δᵢ = √wᵢ·Δᵢ sharing a sign are summed coherently,

        χ²' = Σ_runs (Σ_{i∈run} δᵢ)²

    and esds are multiplied by √(χ²'/χ²).  Same-sign cross terms are
    positive, so the factor is always ≥ 1.

    Caveat (documented, not hidden): the estimator is *conservative*.  Even
    iid Gaussian residuals form chance runs (geometric length distribution,
    mean 2), giving E[χ²']/χ² = 1 + 4/π, i.e. an expected factor ≈ 1.51 for
    perfectly white residuals — verified against simulation in the tests.
    Treat the factor as an upper bound on the serial-correlation esd damage;
    Andreev (1994, J. Appl. Cryst. 27, 288) develops a figure of merit that
    removes this bias.  The raw published factor is what FullProf applies,
    and it is reported in ``Statistics.esd_inflation`` so it can be divided
    back out.
    """
    d = np.asarray(delta, dtype=np.float64)
    if len(d) < 2:
        return 1.0
    chi2 = float(d @ d)
    if chi2 <= 0.0:
        return 1.0
    sign = np.sign(d)
    change = np.nonzero(sign[1:] != sign[:-1])[0] + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change, [len(d)]])
    cs = np.concatenate([[0.0], np.cumsum(d)])
    run_sums = cs[ends] - cs[starts]
    return max(float(np.sqrt((run_sums @ run_sums) / chi2)), 1.0)


def background_absorption(jac: np.ndarray, free_paths: list[str]) -> dict[str, float]:
    """How much of each structural parameter the background could reproduce.

    For parameter i with Jacobian column jᵢ and the background columns
    spanning B, the multiple correlation

        R²ᵢ = 1 − ‖jᵢ − P_B jᵢ‖² / ‖jᵢ‖²          (P_B = orthogonal projector)

    is the fraction of jᵢ's effect the background can imitate.  R² → 1 means
    the two are degenerate: the background absorbs Bragg intensity, biasing
    ADPs up and scales (hence QPA fractions) down *while Rwp improves* — the
    documented failure mode of over-flexible backgrounds.

    Pairwise ρ is the wrong statistic for this: with ~100 spline coefficients
    each individual |ρ| stays small (~0.2) while the block collectively
    absorbs ~50 % of the parameter (measured).  The projection sees the block.

    ``jac`` must be the **full** Jacobian including any P-spline penalty rows
    — those rows are what makes a stiff background unable to imitate a peak,
    and dropping them overstates the risk by ~5× (measured: R² 0.46 → 0.08 at
    λ = 10⁴).
    """
    bg = [k for k, p in enumerate(free_paths) if p.startswith("instrument.background.")]
    targets = [(k, p) for k, p in enumerate(free_paths)
               if p.endswith((".biso", ".scale", ".occ"))]
    if not bg or not targets:
        return {}
    q, _ = np.linalg.qr(np.asarray(jac)[:, bg])
    out: dict[str, float] = {}
    for k, path in targets:
        j = np.asarray(jac)[:, k]
        denom = float(j @ j)
        if denom <= 0.0:
            continue
        resid = j - q @ (q.T @ j)
        out[path] = float(np.clip(1.0 - float(resid @ resid) / denom, 0.0, 1.0))
    return out


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
        esd_inflation=berar_lelann_factor(delta) if n > 2 else None,
        n_points=n, n_free_parameters=n_free,
    )
