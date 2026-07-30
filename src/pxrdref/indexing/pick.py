"""``pick_peaks`` — the public entry point: pattern in, :class:`PeakList` out.

Detection (:mod:`.peaks`), per-group profile fitting (:mod:`.peakfit`) and flag
translation (:mod:`.diagnostics`) are separate modules; this one is the order
they run in and the flags that come out of running them.

Nothing here decides physics.  The two rules it *does* own are both about what a
peak list must not silently drop:

* ghost lines are **flagged and excluded from** :meth:`PeakList.usable`, **never
  subtracted** — they stay in ``peaks`` so a report can say why a line went;
* a component whose fitted position never separated from its neighbour by half a
  FWHM is kept, flagged ``unresolved_shoulder``, rather than merged away.  Its σ
  already carries the correlation, and deleting it would hide a line the pattern
  genuinely contains.
"""

from __future__ import annotations

import numpy as np

from ..background import contamination_flags_from_peaks
from ..model.forward import PAWLEY_OVERLAP_FWHM_FRAC
from ..schemas.indexing import (
    PEAK_ASYMMETRY_MIN_SIGMA,
    ObservedPeak,
    PeakFlag,
    PeakList,
    q_esd_of_two_theta,
    q_of_two_theta,
)
from ..schemas.instrument import Instrument
from ..schemas.pattern import PatternData
from .diagnostics import peak_diagnostics
from .peakfit import GroupFit, fit_group
from .peaks import Detection, detect_peaks


def pick_peaks(data: PatternData, instrument: Instrument, *,
               two_theta_range: tuple[float, float] | None = None,
               shoulders: bool = True,
               flag_contamination: bool = True,
               ) -> PeakList:
    """Every resolvable line in ``data``, with a fitted position and its esd.

    ``instrument`` is used for four things, none of them refined here: the
    primary wavelength and the emission-line set (positions and the doublet
    constraint), the U,V,W,X,Y width law (the separation floor and the width
    seeds), ``profile.shape`` (so the peak list and the refinement that follows
    share one peak shape), and the axial apertures (FCJ, applied and held).

    Returns a :class:`PeakList`; abstention is a *result*, so an unindexably
    short list comes back as a list carrying ``PEAK_LIST_TOO_SHORT`` rather than
    as an exception.
    """
    det = detect_peaks(data, instrument, two_theta_range=two_theta_range,
                       shoulders=shoulders)
    lam0 = instrument.source.lines[0].wavelength

    fits = [fit_group(det, g, instrument) for g in det.groups]
    peaks = _peaks_from_fits(fits, lam0)
    if flag_contamination and peaks:
        _flag_ghosts(peaks, lam0, det)

    pl = PeakList(
        peaks=peaks, wavelength=lam0,
        two_theta_min=float(det.two_theta[0]),
        two_theta_max=float(det.two_theta[-1]),
        source="fitted")
    return pl.model_copy(update={
        "diagnostics": peak_diagnostics(pl, det)})


def _peaks_from_fits(fits: list[GroupFit], wavelength: float
                     ) -> list[ObservedPeak]:
    """Flatten the group fits into one 2θ-ordered list of lines."""
    out: list[ObservedPeak] = []
    for gi, fit in enumerate(fits):
        for j in range(fit.n):
            flags = _flags_for(fit, j)
            tt = float(fit.two_theta[j])
            esd = float(fit.two_theta_esd[j])
            out.append(ObservedPeak(
                two_theta=tt, two_theta_esd=esd,
                intensity=float(fit.intensity[j]),
                intensity_esd=float(fit.intensity_esd[j]),
                q=float(q_of_two_theta(np.array(tt), wavelength)),
                q_esd=float(q_esd_of_two_theta(np.array(tt), np.array(esd),
                                               wavelength)),
                fwhm=fit.fwhm, eta=fit.eta, group=gi, n_in_group=fit.n,
                chi2_red=fit.chi2_red, flags=flags))
    out.sort(key=lambda p: p.two_theta)
    return out


def _flags_for(fit: GroupFit, j: int) -> list[PeakFlag]:
    """Flags implied by one component's converged state."""
    flags: list[PeakFlag] = []
    if not fit.converged:
        flags.append("fit_failed")
    if bool(fit.at_bound[j]):
        flags.append("position_at_bound")
    if _unresolved(fit, j):
        flags.append("unresolved_shoulder")
    t = fit.asymmetry_t[j]
    if np.isfinite(t) and abs(t) >= PEAK_ASYMMETRY_MIN_SIGMA:
        flags.append("asymmetry_unmodelled")
    return flags


def _unresolved(fit: GroupFit, j: int) -> bool:
    """Did component ``j`` end within half a FWHM of a group-mate?

    The test is on the *fitted* positions, not the seeds: grouping used the same
    criterion on seeds to decide what to fit together, and the interesting
    question afterwards is whether the fit managed to pull them apart.
    ``PAWLEY_OVERLAP_FWHM_FRAC`` is imported so "overlapped" keeps meaning one
    thing package-wide.
    """
    if fit.n < 2:
        return False
    gap = PAWLEY_OVERLAP_FWHM_FRAC * fit.fwhm
    others = np.delete(fit.two_theta, j)
    return bool(np.min(np.abs(others - fit.two_theta[j])) < gap)


def _flag_ghosts(peaks: list[ObservedPeak], wavelength: float,
                 det: Detection) -> None:
    """Mark Kβ / W Lα ghosts in place, using the shared background rule.

    Matching is on *integrated* intensity and on the fitted σ(2θ) — the two
    things a fitted list has and the raw channel census does not — via the one
    implementation in ``background.contamination_flags_from_peaks``.
    """
    tt = np.array([p.two_theta for p in peaks])
    inten = np.array([p.intensity for p in peaks])
    esd = np.array([p.two_theta_esd for p in peaks])
    flags = contamination_flags_from_peaks(
        tt, inten, esd, wavelength,
        tt_range=(float(det.two_theta[0]), float(det.two_theta[-1])))
    by_kind = {"kbeta": "ghost_kbeta", "tungsten_la": "ghost_tungsten"}
    for f in flags:
        k = int(np.argmin(np.abs(tt - f.two_theta)))
        name = by_kind[f.kind]
        if name not in peaks[k].flags:
            peaks[k].flags = [*peaks[k].flags, name]


__all__ = ["pick_peaks"]
