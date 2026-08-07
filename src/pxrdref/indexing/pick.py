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
    PEAK_REFUTED_SIGMA,
    PEAK_SATELLITE_MAX_RATIO,
    PEAK_SATELLITE_NEAR_FWHM,
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
    return pick_peaks_with_state(data, instrument,
                                 two_theta_range=two_theta_range,
                                 shoulders=shoulders,
                                 flag_contamination=flag_contamination)[0]


def pick_peaks_with_state(data: PatternData, instrument: Instrument, *,
                          two_theta_range: tuple[float, float] | None = None,
                          shoulders: bool = True,
                          flag_contamination: bool = True,
                          ) -> tuple[PeakList, Detection, list[GroupFit]]:
    """:func:`pick_peaks` plus the state it was derived from.

    The :class:`Detection` and per-group :class:`GroupFit` are what an *editor*
    needs and a consumer of the list does not: WP-1027's peak panel redraws each
    group's fitted profile (:func:`~pxrdref.indexing.peakfit.group_profile`) and
    refits a single group when a human corrects it, both of which want the frozen
    windows and the fitted width pairs rather than the flattened list.
    """
    det = detect_peaks(data, instrument, two_theta_range=two_theta_range,
                       shoulders=shoulders)
    lam0 = instrument.source.lines[0].wavelength

    fits = [fit_group(det, g, instrument) for g in det.groups]
    peaks = _peaks_from_fits(fits, lam0)
    if flag_contamination and peaks:
        flag_ghosts(peaks, lam0, det)
    _flag_extrapolated_background(peaks, det.two_theta)

    pl = PeakList(
        peaks=peaks, wavelength=lam0,
        two_theta_min=float(det.two_theta[0]),
        two_theta_max=float(det.two_theta[-1]),
        source="fitted")
    return pl.model_copy(update={
        "diagnostics": peak_diagnostics(pl, det)}), det, fits


def _flag_extrapolated_background(peaks: list[ObservedPeak],
                                  two_theta: np.ndarray) -> None:
    """Flag lines standing where the background envelope was extrapolated.

    The envelope's knots sit at window *centres*, so the outermost half-window
    at each end of the pattern has no measured background under it — the level
    there comes from extending the two nearest knots (WP-1028 §(i)).  A line's
    prominence is measured against that level, so a line inside the
    extrapolated span is standing on a background nobody observed.

    **Reported, not refused**: these are real intensity, just not necessarily
    lines, and the consumer that can weigh that should be given the chance
    (the same rule the indexing gate follows).  The flag is therefore absent
    from :data:`~pxrdref.schemas.indexing.PEAK_UNUSABLE_FLAGS`.
    """
    from ..background.diagnostics import envelope_measured_span

    if not peaks or len(two_theta) < 3:
        return
    lo, hi = envelope_measured_span(two_theta)
    for peak in peaks:
        if (peak.two_theta < lo or peak.two_theta > hi) and \
                "background_extrapolated" not in peak.flags:
            peak.flags = [*peak.flags, "background_extrapolated"]


def _peaks_from_fits(fits: list[GroupFit], wavelength: float
                     ) -> list[ObservedPeak]:
    """Flatten the group fits into one 2θ-ordered list of lines."""
    out: list[ObservedPeak] = []
    for gi, fit in enumerate(fits):
        out.extend(peaks_of_group(fit, gi, wavelength))
    out.sort(key=lambda p: p.two_theta)
    return out


def peaks_of_group(fit: GroupFit, group_index: int, wavelength: float
                   ) -> list[ObservedPeak]:
    """One group's components as :class:`ObservedPeak`\\ s, flags translated.

    The per-group half of :func:`pick_peaks`, public because WP-1027's editor
    refits *one* group and splices the result into a stored list — the flag
    translation must be this one and not a second reading of it.
    """
    return [ObservedPeak(
        two_theta=(tt := float(fit.two_theta[j])),
        two_theta_esd=(esd := float(fit.two_theta_esd[j])),
        intensity=float(fit.intensity[j]),
        intensity_esd=float(fit.intensity_esd[j]),
        q=float(q_of_two_theta(np.array(tt), wavelength)),
        q_esd=float(q_esd_of_two_theta(np.array(tt), np.array(esd), wavelength)),
        fwhm=fit.fwhm, eta=fit.eta, group=group_index, n_in_group=fit.n,
        chi2_red=fit.chi2_red, flags=_flags_for(fit, j))
        for j in range(fit.n)]


def _flags_for(fit: GroupFit, j: int) -> list[PeakFlag]:
    """Flags implied by one component's converged state."""
    flags: list[PeakFlag] = []
    if not fit.converged:
        flags.append("fit_failed")
    if bool(fit.at_bound[j]):
        flags.append("position_at_bound")
    if _unresolved(fit, j):
        flags.append("unresolved_shoulder")
    if _not_separable(fit, j):
        flags.append("not_separable")
    t = fit.asymmetry_t[j]
    if np.isfinite(t) and abs(t) >= PEAK_ASYMMETRY_MIN_SIGMA:
        flags.append("asymmetry_unmodelled")
    return flags


def _not_separable(fit: GroupFit, j: int) -> bool:
    """Is component ``j`` a *shape* the fit believes in and a *line* it does not?

    Three conditions, and all three are needed because each alone is ordinary:

    1. **a re-seed pass put it there** — detection proposed the group's other
       components against a σ-normalised height test on the data, this one was
       proposed by a residual;
    2. **it is a satellite** — inside a group-mate's own profile
       (:data:`~pxrdref.schemas.indexing.PEAK_SATELLITE_NEAR_FWHM`) and small
       enough relative to it
       (:data:`~pxrdref.schemas.indexing.PEAK_SATELLITE_MAX_RATIO`) that the
       neighbour's shape error could account for it;
    3. **the group's fit is still refuted with it in** — χ²_red more than
       :data:`~pxrdref.schemas.indexing.PEAK_REFUTED_SIGMA` of its own σ(χ²_red)
       above 1 — so the ΔBIC gain that bought it cannot be attributed to a new
       line rather than to the shape of the old one.

    The third is the load-bearing one and the reason this is not simply a tighter
    ΔBIC.  ΔBIC asks whether the data prefer n+1 components to n; that is the
    same question as "is there a line here" only while the n-component model is
    capable of fitting.  Against a refuted model *any* extra component wins, and
    on real laboratory data the model is refuted at every strong peak — measured
    on qarr corundum, χ²_red 17.4 at n = 1 and 4.6 at n = 2 on the 104 line, with
    the component bought landing 1 FWHM below it at 10 % of its area.

    Note what this does **not** do: the component stays in the model and in
    ``peaks``.  It earns its place as shape — removing it would push the real
    line's fitted position (measured: 0.010° on that same line) — and it is only
    barred from ``usable()``, i.e. from being offered as evidence of a lattice.
    """
    if fit.n < 2 or not bool(fit.reseeded()[j]):
        return False
    # ν = points − (two shared widths + two parameters per component)
    dof = max(fit.n_points - 2 - 2 * fit.n, 1)
    refuted = 1.0 + PEAK_REFUTED_SIGMA * np.sqrt(2.0 / dof)
    if not (np.isfinite(fit.chi2_red) and fit.chi2_red > refuted):
        return False
    near = np.abs(fit.two_theta - fit.two_theta[j]) < PEAK_SATELLITE_NEAR_FWHM * fit.fwhm
    near[j] = False
    if not near.any():
        return False
    strongest = float(np.max(fit.intensity[near]))
    if strongest <= 0.0:
        return False
    return bool(fit.intensity[j] < PEAK_SATELLITE_MAX_RATIO * strongest)


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


def flag_ghosts(peaks: list[ObservedPeak], wavelength: float,
                det: Detection, *, only: set[int] | None = None) -> None:
    """Mark Kβ / W Lα ghosts in place, using the shared background rule.

    Matching is on *integrated* intensity and on the fitted σ(2θ) — the two
    things a fitted list has and the raw channel census does not — via the one
    implementation in ``background.contamination_flags_from_peaks``.

    ``only`` restricts which peaks may be *marked* (matching always sees the
    whole list — a ghost's parent can be anywhere).  WP-1027's editor passes the
    indices of the one group it refitted, so recomputing ghosts for the edited
    components cannot resurrect a mark a user cleared on an untouched one.
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
        if only is not None and k not in only:
            continue
        name = by_kind[f.kind]
        if name not in peaks[k].flags:
            peaks[k].flags = [*peaks[k].flags, name]


__all__ = ["flag_ghosts", "peaks_of_group", "pick_peaks",
           "pick_peaks_with_state"]
