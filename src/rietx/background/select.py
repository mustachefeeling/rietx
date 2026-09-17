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

A declared fixed curve (a measured blank, an estimated baseline) is passed to
:func:`select_chebyshev_order` as ``fixed``, because the order worth choosing is
the order of the *remainder*.  :func:`select_arpls_lambda` takes no such
argument on purpose: it chooses how stiffly to **estimate** a baseline, which is
the question somebody with a measured one has already answered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from pydantic import Field

from ..schemas.common import Base
from ..schemas.pattern import PatternData
from .estimators import arpls
from .models import chebyshev_design_matrix, interpolate_fixed

if TYPE_CHECKING:  # a declared curve the chosen order sits on top of
    from ..schemas.instrument import BackgroundFixedPlusChebyshev


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
                           baseline_lambda: float = 1e7,
                           fixed: "BackgroundFixedPlusChebyshev | None" = None
                           ) -> BackgroundSelection:
    """Pick the Chebyshev background order by masked-channel BIC + DW stop.

    ``fixed`` is a declared measured or estimated curve the polynomial sits on
    top of, and it changes the question: the order being chosen is the order of
    what the curve does **not** describe.  Without it the scan measures the
    curve's own shape as though the polynomial had to reproduce it, and picks
    the flexibility to do so — which is the opposite of why anybody measured a
    blank (WP-1309, issue #171 note 4).

    How it enters follows the fit rather than approximating it.  A **held**
    scale is a known additive curve, so it comes off the data and costs no
    parameter.  A **free** scale is one more direction, so it joins the design
    and counts in the BIC's k — leaving it out of k would credit the fit with a
    degree of freedom it spent, and the two are not the same scan.

    **Read the scan within one setting of ``fixed``, never across two.**  A held
    scale changes the response variable, so its RSS carries the curve's own
    counting noise and its BIC cannot be compared with a scan that kept y whole.
    What is comparable is the *order*, and the order is the point: measured on
    the synthetic fixture of ``tests/test_background_measured.py``, a blind scan
    runs to 12 terms chasing a halo, while the same pattern with the curve held
    at its true scale selects **2** and gets worse with every term after.

    A free scale with a high ``max_order`` is the case to be careful with, and
    the care is a low ``max_order`` rather than a guard.  The polynomial and the
    curve are not orthogonal, so given enough terms the scan will dial the
    measured curve away and describe the same shape itself — BIC prefers it, and
    the scale that comes back is then a number about the polynomial.
    """
    mask = data.in_range_mask()
    tt, y, sigma = data.tt()[mask], data.y()[mask], data.sig()[mask]
    keep = peak_mask(tt, y, sigma, baseline_lambda=baseline_lambda)
    tt_m, y_m, s_m = tt[keep], y[keep], sigma[keep]
    m = len(tt_m)
    if m < max_order * 4:
        raise ValueError(f"only {m} background channels — pattern is nearly all peak")

    curve = free_scale = None
    if fixed is not None:
        curve = interpolate_fixed(tt_m, np.asarray(fixed.fixed_two_theta),
                                  np.asarray(fixed.fixed_intensity))
        free_scale = bool(fixed.scale.vary)
        if not free_scale:
            y_m = y_m - float(fixed.scale.value) * curve

    design_full = chebyshev_design_matrix(tt_m, max_order, float(tt[0]), float(tt[-1]))
    w = 1.0 / s_m
    scores: list[CandidateScore] = []
    stopped = False
    for n in range(2, max_order + 1):
        rows = design_full[:n]
        if free_scale:
            rows = np.vstack([rows, curve[None, :]])
        A = (rows * w).T
        coef, *_ = np.linalg.lstsq(A, y_m * w, rcond=None)
        r = y_m * w - A @ coef
        scores.append(CandidateScore(
            complexity=float(n), bic=_bic(float(r @ r), m, len(rows)),
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
