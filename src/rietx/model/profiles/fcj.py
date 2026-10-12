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

**One aperture at zero.**  W then has no height, and the profile below is a
ratio of two zeros.  Its limit as h → 0⁺ with s > 0 is a uniform weight over
[0, s], since W/(2h) → 1 there and the falling edge shrinks to nothing.  The
quadrature evaluates that limit directly, so the profile is continuous on the
whole box of apertures, and only s = h = 0 is the symmetric peak.  Until
WP-1953 a single zero aperture gave the symmetric peak instead.  That was a
jump at the very bound the LM driver's exact step lands a variable on, and a
fit freeing both apertures crawled beside it to its evaluation cap.

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

from ...backend import get_backend

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


def fcj_live(sl: float, hl: float) -> bool:
    """Whether the aberration acts at these apertures: neither negative and
    not both zero.  One zero aperture acts (the module docstring's limit).

    The one test every reader of the off state calls, so the profile, the
    compile-time node sizing and the axial columns agree on where it is.
    """
    return sl >= 0.0 and hl >= 0.0 and sl + hl > 0.0


def _xi_max(two_theta_rad: np.ndarray, sl: float, hl: float) -> np.ndarray:
    # shared by the runtime quadrature and the compile-time sizing below
    xp = get_backend()
    with np.errstate(divide="ignore"):
        cap = xp.abs(xp.tan(two_theta_rad))
    cap = xp.where(xp.isfinite(cap), cap, np.inf)
    return xp.minimum(sl + hl, cap)


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

    The aberration acts unless both apertures are zero (:func:`fcj_live`).  A
    point slit beside a sample of half-length S still smears the peak, over
    the uniform weight the module docstring derives.
    """
    if not fcj_live(sl, hl):
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
    profile Ω used for symmetric peaks.  When the aberration vanishes (both
    apertures zero, a negative one, or ξ_max = 0) the result falls back to the
    single symmetric image, expressed branchlessly (purity (d)) as a
    ``where``-select of the *same shape*: every image at 2θ with a one-hot
    weight vector, whose dot with the profile rows reproduces the single-image
    path bit-for-bit.  That fallback is the limit of the profile as both
    apertures go to zero, since the smear's extent goes with them.

    **One aperture at zero** gives W unit height on the first segment, which
    then spans [0, ξ_max], and the second segment has zero length.  That is
    the uniform limit of the module docstring, and the trapezoid's own
    expression is selected wherever both apertures are positive, so those
    weights are the ones computed before WP-1953 bit for bit.

    Composite quadrature: W(ξ) has a kink at ξ = |s − h|, so the integral is
    split there into two Gauss-Legendre segments (W exactly constant on the
    first, exactly linear on the second).  With single-segment quadrature the
    fixed-τ nodes would sweep *across* the kink as S/L, H/L refine, putting
    O(h) steps into the parameter derivatives; splitting keeps the response
    C¹ everywhere except the inherent FCJ kink at s = h itself.
    """
    xp = get_backend()
    tau_np, glw_np = _gauss_legendre_01(max(n_nodes // 2, 4))  # frozen host nodes
    fallback_w = np.zeros(2 * len(tau_np))
    fallback_w[0] = 1.0
    # lifted onto the backend: both sit on the *left* of products against the
    # θ-derived ξ below, which torch will not accept (backend/api.py)
    tau = xp.asarray(tau_np, dtype=np.float64)
    glw = xp.asarray(glw_np, dtype=np.float64)
    tt = xp.radians(two_theta_deg)
    xi_max = _xi_max(tt, sl, hl)
    ok = (xi_max > 0.0) & (sl >= 0.0) & (hl >= 0.0)

    xi_kink = xp.minimum(xp.abs(sl - hl), xi_max)
    # segment A: [0, ξ_kink], W ≡ 2·min(s,h); segment B: [ξ_kink, ξ_max]
    xi = xp.concatenate([tau * xi_kink, xi_kink + tau * (xi_max - xi_kink)])
    seg_len = xp.concatenate([xp.full_like(glw, xi_kink),
                              xp.full_like(glw, xi_max - xi_kink)])
    glw2 = xp.concatenate([glw, glw])

    cphi = xp.clip(xp.cos(tt) * xp.sqrt(1.0 + xi * xi), -1.0, 1.0)
    phi = xp.degrees(xp.arccos(cphi))
    w_overlap = xp.where(xp.minimum(sl, hl) > 0.0,
                         xp.clip(sl + hl - xi, 0.0, 2.0 * xp.minimum(sl, hl)), 1.0)
    omega = glw2 * seg_len * w_overlap
    total = omega.sum()
    ok = ok & (total > 0.0)
    return (xp.where(ok, phi, two_theta_deg),
            xp.where(ok, omega / xp.where(ok, total, 1.0), fallback_w))


def fcj_offsets_weights_batch(two_theta_deg: np.ndarray, sl: float, hl: float,
                              n_nodes: int) -> tuple[np.ndarray, np.ndarray]:
    """:func:`fcj_offsets_weights` vectorised over reflections sharing one
    frozen node count — the batched derivative-bases path (WP-1112).

    The same expressions evaluated on a (B, 1) position column against the
    (m,) quadrature row; returns (B, 2m) images and normalised weights, row b
    equal to the scalar routine at ``two_theta_deg[b]`` to fp rounding (the
    per-row ``sum`` reduces along the contiguous last axis, elementwise ops
    broadcast — but bit-equality is not claimed, and the batched Jacobian
    consumers do not claim it either).  The branchless fallback is per row:
    a row whose aberration vanishes gets its own 2θ image with the one-hot
    weight, exactly as the scalar's ``where``-select.  numpy-only by intent —
    the traced backends keep the scalar routine.

    A non-finite position (a reflection the current cell pushes out of
    range) propagates NaN through its own row and poisons nothing else; the
    caller excludes such rows exactly as the scalar loop skipped them.
    """
    tau, glw = _gauss_legendre_01(max(n_nodes // 2, 4))
    tt_deg = np.asarray(two_theta_deg, dtype=np.float64)[:, None]
    tt = np.radians(tt_deg)
    b, m = tt.shape[0], len(tau)
    with np.errstate(divide="ignore", invalid="ignore"):
        cap = np.abs(np.tan(tt))
    cap = np.where(np.isfinite(cap), cap, np.inf)
    xi_max = np.minimum(sl + hl, cap)
    ok = (xi_max > 0.0) & (sl >= 0.0) & (hl >= 0.0)

    xi_kink = np.minimum(abs(sl - hl), xi_max)
    xi = np.concatenate([tau * xi_kink, xi_kink + tau * (xi_max - xi_kink)],
                        axis=1)
    seg_len = np.concatenate([np.broadcast_to(xi_kink, (b, m)),
                              np.broadcast_to(xi_max - xi_kink, (b, m))],
                             axis=1)
    glw2 = np.concatenate([glw, glw])[None, :]

    with np.errstate(invalid="ignore"):
        cphi = np.clip(np.cos(tt) * np.sqrt(1.0 + xi * xi), -1.0, 1.0)
        phi = np.degrees(np.arccos(cphi))
        w_overlap = (np.clip(sl + hl - xi, 0.0, 2.0 * min(sl, hl))
                     if min(sl, hl) > 0.0 else np.ones_like(xi))
    omega = glw2 * seg_len * w_overlap
    total = omega.sum(axis=1, keepdims=True)
    ok = ok & (total > 0.0)
    fallback_w = np.zeros((1, 2 * m))
    fallback_w[0, 0] = 1.0
    return (np.where(ok, phi, tt_deg),
            np.where(ok, omega / np.where(ok, total, 1.0), fallback_w))
