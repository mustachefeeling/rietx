"""Peak detection — σ-normalised thresholds, instrument-derived separation, and
the seeds the profile fitter needs.

Three rules distinguish this from the one-line ``find_peaks`` census in
``background/diagnostics.py``, and each of the three is a measured failure of
the obvious alternative:

* **Thresholds are σ-normalised, never relative to the global maximum.**  A
  ``prominence = net.max()·0.01`` rule (the prototype indexer at tag
  ``guillemot-study``) couples unrelated parts of the pattern: on a pattern
  that is one enormous reflection plus a dozen weak lines it suppresses
  everything but the giant.
* **The separation floor comes from the instrument, not a channel count.**
  ``distance=3`` is a synchrotron-shaped constant; the same three channels are
  a fortieth of a FWHM on a 0.01°-step lab pattern.  It is derived here from
  the Caglioti/TCH width law at the instrument's own U,V,W,X,Y — which also
  supplies the fitter's width seeds, so detection and fitting cannot disagree
  about how wide a peak is.
* **The width census ranks first and measures second.**  A median FWHM over
  *all* detections above a prominence floor reads 0.071° on a noisy pattern
  whose real lines are 0.389° (WP-1028, measured on third-party lab data),
  because smoothing ripples survive the floor as weak maxima.  The median of
  the :data:`~pxrdref.schemas.indexing.PEAK_WIDTH_CENSUS_N` most prominent
  detections recovers 0.389°.

Grouping is not a new rule: it calls ``model.forward._overlap_groups``, so
"overlapped" means one thing package-wide.  The background is the λ-free rolling
low quantile (``background.background_envelope``) and is **held additively**,
never subtracted — the whole-pattern invariant (CLAUDE.md, Weights) applies to
a 200-point window too.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks, peak_widths, savgol_coeffs, savgol_filter

from ..background import background_envelope
from ..model.forward import PAWLEY_OVERLAP_FWHM_FRAC, _overlap_groups
from ..model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
from ..model.profiles.fcj import fcj_extent_deg
from ..model.profiles.pseudovoigt import tch_gamma_eta
from ..schemas.indexing import (
    PEAK_ALIAS_RATIO_RANGE,
    PEAK_ALIAS_TOL_FWHM_FRAC,
    PEAK_DETECT_SEPARATION_FWHM_FRAC,
    PEAK_MIN_HEIGHT_SIGMA,
    PEAK_MIN_PROMINENCE_SIGMA,
    PEAK_WIDTH_CENSUS_N,
    PEAK_WIDTH_SCALE_BOUNDS,
    PEAK_WINDOW_FWHM_MULT,
)
from ..schemas.instrument import Instrument
from ..schemas.pattern import PatternData

_LN2_8 = 8.0 * np.log(2.0)


@dataclass
class PeakGroup:
    """One frozen fitting window and the component seeds inside it.

    ``i0``/``i1`` slice the :class:`Detection` arrays (already masked and
    cropped), so a group is self-contained: the fitter never re-derives a
    window.  ``n`` is frozen before the fit and may only change between
    explicit re-seed passes — the frozen-per-stage invariant one level down.
    """

    i0: int
    i1: int
    seed_two_theta: np.ndarray      # ° 2θ, ascending
    seed_fwhm: float                # ° 2θ, shared by the group
    from_shoulder: np.ndarray       # bool per seed: curvature seed, not a maximum

    @property
    def n(self) -> int:
        return len(self.seed_two_theta)


@dataclass
class Detection:
    """Everything the fitter needs: the masked pattern, the frozen background
    level, the groups, and the two widths whose *ratio* calibrated the seeds.

    ``fwhm_measured`` and ``fwhm_predicted`` are kept separately rather than
    collapsed into the scale factor because their disagreement is diagnostic:
    a ratio near 13 is the ``ProfileTCHZ`` default (``W = 1e-3 deg²``, FWHM ≈
    0.03°, a *synchrotron* line) applied to lab data, and a caller should be
    told that rather than have it silently absorbed.
    """

    two_theta: np.ndarray
    intensity: np.ndarray
    sigma: np.ndarray
    envelope: np.ndarray
    groups: list[PeakGroup]
    fwhm_measured: float
    fwhm_predicted: float
    width_scale: float
    n_shoulder_seeds: int
    #: 2θ of candidates dropped as Kα2 aliases of a stronger line.  Reported,
    #: because in one pattern an alias and a genuine coincident line are
    #: indistinguishable (:data:`~pxrdref.schemas.indexing.PEAK_ALIAS_RATIO_RANGE`).
    alias_two_theta: np.ndarray


def predicted_fwhm(two_theta_deg: np.ndarray, instrument: Instrument) -> np.ndarray:
    """The instrument's own combined FWHM (° 2θ) at these positions.

    The TCH combined Γ of the Caglioti Gaussian and the Lorentzian law, exactly
    as ``compile_model`` sizes its evaluation windows with — including under
    ``shape="voigt"``, where Γ_TCH tracks the true Voigt FWHM to ~1 %.  Sample
    broadening is *not* in here (no phase exists yet); that is what the width
    census measures.
    """
    prof = instrument.profile
    theta = 0.5 * np.asarray(two_theta_deg, dtype=np.float64)
    g = gaussian_fwhm(theta, prof.u.value, prof.v.value, prof.w.value)
    lor = lorentzian_fwhm(theta, prof.x.value, prof.y.value)
    gamma, _eta = tch_gamma_eta(g, lor)
    return np.asarray(gamma, dtype=np.float64)


def _shoulder_seeds(tt: np.ndarray, net: np.ndarray, sigma: np.ndarray,
                    fwhm: np.ndarray, found: np.ndarray) -> np.ndarray:
    """Curvature seeds for peaks that never reach a local maximum.

    A shoulder on a strong line has no maximum, so ``find_peaks`` cannot see
    it — but it does have a curvature minimum, and the amplitude that curvature
    implies follows from the Gaussian relation |y″| = 8ln2·h/Γ².

    **The threshold has to be the filter's own noise, not the channel's.**  A
    second derivative amplifies white noise by ~1/step², so on a 0.01°-step
    pattern the raw curvature of pure noise implies an apparent peak height an
    order of magnitude above any per-channel σ — a threshold written against
    ``sigma[i]`` passes essentially every noise dip, and the first version of
    this function did exactly that (measured: hundreds of spurious seeds on a
    three-peak synthetic pattern).  So the derivative is a Savitzky-Golay filter
    over a window of about one FWHM, and its noise is *propagated exactly*: the
    filter is linear with known coefficients c, so σ(y″) = ‖c‖₂·σ.  The test is
    then the same σ-normalised significance a detection had to clear, which is
    what makes a shoulder seed and a detection mean the same thing.

    These are **seeds only**.  Whether the component survives is decided by the
    group fit's ΔBIC test (:mod:`.peakfit`), not here: this function is allowed
    to be generous, and being generous is why that gate exists.
    """
    out: list[int] = []
    step = float(np.median(np.diff(tt)))
    if len(tt) < 9 or step <= 0.0:
        return np.array(out, dtype=np.int64)
    width = max(int(float(np.median(fwhm)) / step), 5)
    width = min(width | 1, (len(tt) - 1) | 1)   # odd, and inside the pattern
    poly = min(4, width - 1)
    if poly < 3:                                # deriv=2 needs order ≥ 3
        return np.array(out, dtype=np.int64)
    curv = savgol_filter(net, width, poly, deriv=2, delta=step, mode="interp")
    coef_norm = float(np.linalg.norm(
        savgol_coeffs(width, poly, deriv=2, delta=step)))
    dips, _ = find_peaks(-curv)
    for i in dips:
        scale = fwhm[i] ** 2 / _LN2_8
        h_implied = -curv[i] * scale
        h_sigma = coef_norm * sigma[i] * scale
        if h_implied <= PEAK_MIN_PROMINENCE_SIGMA * h_sigma:
            continue
        gap = PEAK_DETECT_SEPARATION_FWHM_FRAC * fwhm[i]
        if len(found) and np.min(np.abs(tt[found] - tt[i])) < gap:
            continue
        out.append(int(i))
    return np.array(sorted(out), dtype=np.int64)


def _drop_kalpha2_aliases(tt: np.ndarray, idx: np.ndarray, height: np.ndarray,
                          fwhm: np.ndarray, instrument: Instrument,
                          ) -> tuple[np.ndarray, np.ndarray]:
    """Split candidates into (real lines, Kα2 aliases of stronger candidates).

    Once the doublet resolves, the Kα2 maximum is a detection in its own right
    and — since every group is fitted independently, each with its *own* full
    doublet — it comes back as a line with real intensity.  So it has to be
    recognised here.  Same d-spacing, different λ, exactly the ghost transform:
    sin θ_alias = (λ_l/λ₀)·sin θ_parent, checked against the candidate's height
    ratio to the parent.

    The parent must be *stronger*, which is what keeps the relation
    antisymmetric and stops a pair annihilating each other; ties are broken by
    the lower 2θ, since the alias of a Kα1 line is always above it.
    """
    lines = instrument.source.lines
    if len(lines) < 2 or not len(idx):
        return idx, np.array([], dtype=np.int64)
    lo_r, hi_r = PEAK_ALIAS_RATIO_RANGE
    alias: set[int] = set()
    order = np.argsort(height)[::-1]            # strongest parent first
    for a in order:
        if int(idx[a]) in alias:
            continue                            # an alias cannot parent one
        for il in range(1, len(lines)):
            ratio = lines[il].wavelength / lines[0].wavelength
            s = ratio * np.sin(np.radians(0.5 * tt[idx[a]]))
            if not (-1.0 <= s <= 1.0):
                continue
            predicted = 2.0 * np.degrees(np.arcsin(s))
            w = lines[il].weight.value
            for b in range(len(idx)):
                if b == a or int(idx[b]) in alias:
                    continue
                if height[b] >= height[a]:
                    continue
                if abs(tt[idx[b]] - predicted) > (PEAK_ALIAS_TOL_FWHM_FRAC
                                                  * fwhm[idx[b]]):
                    continue
                r = height[b] / max(height[a], 1e-12)
                if lo_r * w <= r <= hi_r * w:
                    alias.add(int(idx[b]))
    keep = np.array([i for i in idx if int(i) not in alias], dtype=np.int64)
    dropped = np.array(sorted(alias), dtype=np.int64)
    return keep, dropped


def detect_peaks(data: PatternData, instrument: Instrument, *,
                 two_theta_range: tuple[float, float] | None = None,
                 shoulders: bool = True) -> Detection:
    """Detect every candidate line and group them into frozen fit windows.

    ``two_theta_range`` crops on top of ``data.excluded_regions``; the
    excluded channels are removed rather than masked, because a window that
    straddles a gap has no meaningful frozen background.
    """
    mask = data.in_range_mask()
    tt_all, y_all, sig_all = data.tt(), data.y(), data.sig()
    if two_theta_range is not None:
        lo, hi = two_theta_range
        mask = mask & (tt_all >= lo) & (tt_all <= hi)
    tt, y, sigma = tt_all[mask], y_all[mask], sig_all[mask]
    if len(tt) < 16:
        raise ValueError(
            f"only {len(tt)} points survive the mask and 2θ range; peak "
            "picking needs a pattern, not a window")

    env = background_envelope(tt, y)
    net = y - env
    z = np.where(net > 0.0, net, 0.0) / sigma
    step = float(np.median(np.diff(tt)))

    fwhm_pred = predicted_fwhm(tt, instrument)
    dist = max(int(PEAK_DETECT_SEPARATION_FWHM_FRAC
                   * float(fwhm_pred.min()) / max(step, 1e-12)), 1)
    idx, props = find_peaks(z, height=PEAK_MIN_HEIGHT_SIGMA,
                            prominence=PEAK_MIN_PROMINENCE_SIGMA,
                            distance=dist)

    # width census: rank by prominence, then measure — never the reverse
    fwhm_meas = float(np.median(fwhm_pred))
    scale = 1.0
    if len(idx):
        rank = np.argsort(props["prominences"])[::-1][:PEAK_WIDTH_CENSUS_N]
        widths, *_ = peak_widths(net, idx[rank], rel_height=0.5)
        fwhm_meas = float(np.median(widths)) * step
        ref = float(np.median(fwhm_pred[idx[rank]]))
        if ref > 0.0 and fwhm_meas > 0.0:
            scale = float(np.clip(fwhm_meas / ref, *PEAK_WIDTH_SCALE_BOUNDS))
    fwhm_seed_curve = scale * fwhm_pred

    # the Kα2 maximum of a resolved doublet is not a line — drop it before it
    # can become a group of its own with its own doublet
    idx, alias_idx = _drop_kalpha2_aliases(
        tt, idx, net[idx], fwhm_seed_curve, instrument)

    shoulder_idx = (_shoulder_seeds(tt, net, sigma, fwhm_seed_curve, idx)
                    if shoulders else np.array([], dtype=np.int64))
    all_idx = np.concatenate([idx, shoulder_idx]).astype(np.int64)
    if not len(all_idx):
        return Detection(tt, y, sigma, env, [], fwhm_meas,
                         float(np.median(fwhm_pred)), scale, 0,
                         tt[alias_idx])
    order = np.argsort(tt[all_idx])
    all_idx = all_idx[order]
    is_shoulder = np.isin(all_idx, shoulder_idx)

    groups = _group_indices(tt[all_idx], fwhm_seed_curve[all_idx])
    sl = instrument.geometry.axial_sl.value
    hl = instrument.geometry.axial_hl.value
    out: list[PeakGroup] = []
    for members in groups:
        seeds = tt[all_idx[members]]
        fw = float(np.mean(fwhm_seed_curve[all_idx[members]]))
        half = PEAK_WINDOW_FWHM_MULT * fw
        # the FCJ smear is one-sided and toward *low* angle below 90°, which is
        # exactly where the lines indexing depends on most sit
        extra = (float(fcj_extent_deg(np.array(seeds.min()), sl, hl))
                 if sl > 0.0 and hl > 0.0 else 0.0)
        i0 = int(np.searchsorted(tt, seeds.min() - half - extra, side="left"))
        i1 = int(np.searchsorted(tt, seeds.max() + half, side="right"))
        out.append(PeakGroup(i0=i0, i1=i1, seed_two_theta=seeds, seed_fwhm=fw,
                             from_shoulder=is_shoulder[members]))
    return Detection(tt, y, sigma, env, out, fwhm_meas,
                     float(np.median(fwhm_pred)), scale, int(len(shoulder_idx)),
                     tt[alias_idx])


def _group_indices(tt: np.ndarray, fwhm: np.ndarray) -> list[np.ndarray]:
    """Every seed's group, singletons included.

    ``_overlap_groups`` is the package's one definition of "these peaks
    overlap" (it returns multi-member runs only, since Pawley needs restraints
    for nothing else); the singletons it omits are filled back in here so every
    seed lands in exactly one fitting window.
    """
    multi = _overlap_groups(tt, fwhm)
    claimed = {k for g in multi for k in g}
    groups = [np.array(g, dtype=np.int64) for g in multi]
    groups += [np.array([k], dtype=np.int64)
               for k in range(len(tt)) if k not in claimed]
    groups.sort(key=lambda g: int(g[0]))
    return groups


#: re-exported so a caller can see which constant set the grouping
__all__ = ["Detection", "PeakGroup", "PAWLEY_OVERLAP_FWHM_FRAC",
           "detect_peaks", "predicted_fwhm"]
