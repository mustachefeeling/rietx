"""Finger-Cox-Jephcoat axial-divergence peak asymmetry.

Finger, Cox & Jephcoat (1994), J. Appl. Cryst. 27, 892: with a sample of
axial half-length S and a receiving slit of axial half-length H at
goniometer radius L, rays leaving the diffraction plane are detected at an
*apparent* angle 2φ related to the true Bragg angle 2θ by

    cos 2φ = cos 2θ · √(1 + ξ²),      ξ = u / L,

where u is the (signed) axial offset between the sample and detector points
of the ray.  For 2θ < 90° this smears intensity from 2θ down to
2φ_min (cos 2φ_min = cos 2θ·√(1 + (S/L + H/L)²)); above 90° the smear is
toward *high* angle — the classic low-angle tail of laboratory data.  The
weight of a given offset is the axial overlap of sample and slit, a
trapezoid in ξ:

    W(ξ) = clip(s + h − ξ, 0, 2·min(s, h)),   s = S/L, h = H/L, ξ ≥ 0

(2·min for |s−h| ≥ ξ, linearly falling to zero at ξ = s + h; FCJ eqs. 4-13
reduce to this after collecting their two half-integrals).

**The singularity and its removal.**  Expressed as a density in 2φ, the
aberration D(2φ) = W(ξ)·|dξ/d2φ| diverges like 1/√(2θ − 2φ) at the Bragg
position (FCJ §2, the reason naive sampling fails).  Substituting ξ as the
integration variable removes it exactly — the observed profile is

    y(2θ_i) = ∫₀^ξmax W(ξ) · Ω(2θ_i − 2φ(ξ)) dξ  /  ∫₀^ξmax W(ξ) dξ

with a *smooth* integrand (Ω is the unit-area pseudo-Voigt).  This module
evaluates that integral by fixed-node Gauss-Legendre quadrature in the
scaled variable τ = ξ/ξmax ∈ [0, 1]:

* node positions τ_q and per-reflection node *counts* are frozen at stage
  compile time (the differentiability invariant — the quadrature never
  changes discretely during a least-squares run);
* the physical nodes ξ_q = τ_q·ξmax and weights follow s, h and 2θ smoothly,
  so finite-difference/autodiff Jacobians see a smooth residual;
* weights are renormalised to Σω = 1, so the composite peak keeps *exactly*
  unit area and reflection intensities remain areas.

ξmax = min(s + h, |tan 2θ|): the second term caps the (unphysical)
cos 2φ > 1 branch at very low angle; the truncated range is renormalised,
which conserves the diffracted intensity inside the pattern.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

#: below this ratio of asymmetric extent to peak FWHM the aberration is
#: invisible and the peak is treated as symmetric (no quadrature nodes)
SKIP_EXTENT_FWHM_RATIO = 0.02
#: node-count rule: enough nodes that adjacent images are spaced well under
#: one FWHM where the ξ → 2φ map moves fastest (d2φ/dτ is largest at τ = 1)
NODES_PER_FWHM = 6.0
MIN_NODES = 8
MAX_NODES = 64


@lru_cache(maxsize=32)
def _gauss_legendre_01(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Gauss-Legendre nodes/weights mapped from [-1, 1] to [0, 1]."""
    x, w = np.polynomial.legendre.leggauss(n)
    return (0.5 * (x + 1.0)).astype(np.float64), (0.5 * w).astype(np.float64)


def _xi_max(two_theta_rad: np.ndarray, sl: float, hl: float) -> np.ndarray:
    with np.errstate(divide="ignore"):
        cap = np.abs(np.tan(two_theta_rad))
    cap = np.where(np.isfinite(cap), cap, np.inf)
    return np.minimum(sl + hl, cap)


def fcj_extent_deg(two_theta_deg: np.ndarray, sl: float, hl: float) -> np.ndarray:
    """Full asymmetric smear |2θ − 2φ_min| in degrees (vectorised).

    Used at compile time to size evaluation windows and node counts.
    """
    tt = np.radians(np.asarray(two_theta_deg, dtype=np.float64))
    xi = _xi_max(tt, sl, hl)
    cphi = np.clip(np.cos(tt) * np.sqrt(1.0 + xi * xi), -1.0, 1.0)
    return np.abs(np.degrees(np.arccos(cphi)) - np.degrees(tt))


def fcj_node_count(two_theta_deg: float, fwhm_deg: float, sl: float, hl: float) -> int:
    """Frozen per-reflection quadrature size; 0 → treat peak as symmetric.

    Both apertures must be positive for the aberration to act: the overlap
    trapezoid W has height 2·min(S/L, H/L), so a point sample or point slit
    (either ratio = 0) carries no weight in this parameterisation — set both,
    or tie them equal, rather than zeroing one.
    """
    if sl <= 0.0 or hl <= 0.0:
        return 0
    extent = float(fcj_extent_deg(np.array(two_theta_deg), sl, hl))
    if extent < SKIP_EXTENT_FWHM_RATIO * fwhm_deg:
        return 0
    n = int(np.ceil(4.0 + NODES_PER_FWHM * extent / max(fwhm_deg, 1e-6)))
    return int(np.clip(n, MIN_NODES, MAX_NODES))


def fcj_offsets_weights(two_theta_deg: float, sl: float, hl: float,
                        n_nodes: int) -> tuple[np.ndarray, np.ndarray]:
    """Apparent-angle images 2φ_q (deg) and normalised weights ω_q (Σω = 1).

    The composite peak is  Σ_q ω_q · Ω(2θ_i − 2φ_q)  with the same unit-area
    profile Ω used for symmetric peaks.  Falls back to the single symmetric
    image when the aberration vanishes.

    Composite quadrature: W(ξ) has a kink at ξ = |s − h|, so the integral is
    split there into two Gauss-Legendre segments (W exactly constant on the
    first, exactly linear on the second).  With single-segment quadrature the
    fixed-τ nodes would sweep *across* the kink as S/L, H/L refine, putting
    O(h) steps into the parameter derivatives; splitting keeps the response
    C¹ everywhere except the inherent FCJ kink at s = h itself.
    """
    tt = np.radians(two_theta_deg)
    xi_max = float(_xi_max(np.array(tt), sl, hl))
    if xi_max <= 0.0 or sl <= 0.0 or hl <= 0.0:
        return np.array([two_theta_deg]), np.array([1.0])

    xi_kink = min(abs(sl - hl), xi_max)
    tau, glw = _gauss_legendre_01(max(n_nodes // 2, 4))
    # segment A: [0, ξ_kink], W ≡ 2·min(s,h); segment B: [ξ_kink, ξ_max]
    xi = np.concatenate([tau * xi_kink, xi_kink + tau * (xi_max - xi_kink)])
    seg_len = np.concatenate([np.full_like(glw, xi_kink),
                              np.full_like(glw, xi_max - xi_kink)])
    glw2 = np.concatenate([glw, glw])

    cphi = np.clip(np.cos(tt) * np.sqrt(1.0 + xi * xi), -1.0, 1.0)
    phi = np.degrees(np.arccos(cphi))
    w_overlap = np.clip(sl + hl - xi, 0.0, 2.0 * min(sl, hl))
    omega = glw2 * seg_len * w_overlap
    total = omega.sum()
    if total <= 0.0:
        return np.array([two_theta_deg]), np.array([1.0])
    return phi, omega / total
