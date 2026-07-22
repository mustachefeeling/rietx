"""Automatic background-complexity selection.

Two knobs need choosing before a refinement: the Chebyshev order (or
P-spline stiffness λ) of the co-refined background, and the arPLS λ of a
fixed estimated baseline.  Both use the same two ingredients:

* **BIC on peak-masked channels** — background flexibility must be justified
  by the *background* channels only, so Bragg-peak channels (net > 3σ above
  a robust baseline) are masked out of the score:
  BIC = m·ln(RSS/m) + k·ln(m)  (Schwarz, 1978, Ann. Stat. 6, 461).
* **Durbin-Watson whiteness stopping** — d = Σ(Δᵢ−Δᵢ₋₁)²/ΣΔᵢ² on the masked
  residuals (Durbin & Watson, 1950; Hill & Flack, 1987, J. Appl. Cryst. 20,
  356).  d rises toward 2 as the background stops leaving serially-correlated
  structure; once d ≥ ``dw_stop`` extra flexibility only chases noise, so the
  scan stops (masked channels are treated as contiguous for d — the gaps at
  peak positions make the test slightly conservative, which is the safe
  direction).

The selected order is the BIC minimiser among the scanned candidates.
"""

from __future__ import annotations

import numpy as np
from pydantic import Field

from ..schemas.common import Base
from ..schemas.pattern import PatternData
from .estimators import arpls
from .models import chebyshev_design_matrix


class CandidateScore(Base):
    complexity: float           # Chebyshev order n, or log10(λ) for arPLS
    bic: float
    durbin_watson: float


class BackgroundSelection(Base):
    """Outcome of an automatic selection scan, with the evidence table."""

    method: str                 # "chebyshev_order" | "arpls_lambda"
    selected: float             # the chosen order / λ
    n_masked_channels: int
    scores: list[CandidateScore] = Field(default_factory=list)
    stopped_by_whiteness: bool = False


def peak_mask(tt: np.ndarray, y: np.ndarray, sigma: np.ndarray,
              *, baseline_lambda: float = 1e7) -> np.ndarray:
    """True on background channels (net ≤ 3σ above a robust arPLS baseline)."""
    base = arpls(y, baseline_lambda)
    return (y - base) <= 3.0 * sigma


def _bic(rss: float, m: int, k: int) -> float:
    return m * float(np.log(max(rss, 1e-300) / m)) + k * float(np.log(m))


def _durbin_watson(r: np.ndarray) -> float:
    return float(np.sum(np.diff(r) ** 2) / max(np.sum(r * r), 1e-300))


def select_chebyshev_order(data: PatternData, *, max_order: int = 16,
                           dw_stop: float = 1.8,
                           baseline_lambda: float = 1e7) -> BackgroundSelection:
    """Pick the Chebyshev background order by masked-channel BIC + DW stop."""
    mask = data.in_range_mask()
    tt, y, sigma = data.tt()[mask], data.y()[mask], data.sig()[mask]
    keep = peak_mask(tt, y, sigma, baseline_lambda=baseline_lambda)
    tt_m, y_m, s_m = tt[keep], y[keep], sigma[keep]
    m = len(tt_m)
    if m < max_order * 4:
        raise ValueError(f"only {m} background channels — pattern is nearly all peak")

    design_full = chebyshev_design_matrix(tt_m, max_order, float(tt[0]), float(tt[-1]))
    w = 1.0 / s_m
    scores: list[CandidateScore] = []
    stopped = False
    for n in range(2, max_order + 1):
        A = (design_full[:n] * w).T
        coef, *_ = np.linalg.lstsq(A, y_m * w, rcond=None)
        r = y_m * w - A @ coef
        scores.append(CandidateScore(
            complexity=float(n), bic=_bic(float(r @ r), m, n),
            durbin_watson=_durbin_watson(r)))
        if scores[-1].durbin_watson >= dw_stop:
            stopped = True
            break
    best = min(scores, key=lambda s: s.bic)
    return BackgroundSelection(method="chebyshev_order", selected=best.complexity,
                               n_masked_channels=m, scores=scores,
                               stopped_by_whiteness=stopped)


def select_arpls_lambda(data: PatternData, *,
                        candidates: tuple[float, ...] = tuple(10.0 ** e for e in range(4, 11)),
                        dw_floor: float = 1.2) -> BackgroundSelection:
    """Pick the arPLS λ: the **stiffest** baseline whose masked-channel
    residuals still look white.

    Scanning stiff → flexible: an over-stiff baseline leaves low-frequency
    structure on the background channels (d ≪ 2); the first (largest) λ with
    d ≥ ``dw_floor`` wins.  BIC (with k ∝ effective flexibility ~ −log₁₀λ)
    is reported for the evidence table but whiteness decides, because the
    baseline is not a parametric fit with a countable k.
    """
    mask = data.in_range_mask()
    tt, y, sigma = data.tt()[mask], data.y()[mask], data.sig()[mask]
    keep = peak_mask(tt, y, sigma)
    m = int(np.sum(keep))

    scores: list[CandidateScore] = []
    selected = None
    stopped = False
    for lam in sorted(candidates, reverse=True):
        base = arpls(y, lam)
        r = ((y - base) / sigma)[keep]
        dw = _durbin_watson(r)
        k = max(int(30.0 - 2.0 * np.log10(lam)), 1)  # crude flexibility proxy
        scores.append(CandidateScore(complexity=float(np.log10(lam)),
                                     bic=_bic(float(r @ r), m, k),
                                     durbin_watson=dw))
        if selected is None and dw >= dw_floor:
            selected = lam
            stopped = True
            break
    if selected is None:
        selected = min(candidates)
    return BackgroundSelection(method="arpls_lambda", selected=float(selected),
                               n_masked_channels=m, scores=scores,
                               stopped_by_whiteness=stopped)
