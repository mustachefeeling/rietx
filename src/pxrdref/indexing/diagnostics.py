"""``PEAK_*`` and ``INDEX_*`` diagnostics — a peak list's flags and a
data-quality verdict translated into the package's one structured-message
grammar.

Same shape as ``refine._guard_diagnostics``: the fitter records *facts* on each
line (``at_bound``, ``asymmetry_t``, a flag) and this module alone decides what
level they are and what to suggest.  Keeping the two apart is what lets a
threshold move without touching the fitter, and what stops a level being
implied by where the code happens to live.

The two translators stay separate (:func:`peak_diagnostics`,
:func:`quality_diagnostics`) because a peak list's flags and a verdict on whether
the list can be indexed are different statements about the same lines: an agent
that re-picks peaks in response to the first would be answering the wrong
question for the second.

Every message names a concrete call in its ``suggestion``, and ``where`` carries
the 2θ the statement is about — a peak list has no dot-paths (peak parameters
deliberately never enter a history node's ``free_paths``), so 2θ is the only
address a consumer can act on.
"""

from __future__ import annotations

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import (
    MAX_RELATIVE_SIGMA_Q,
    PEAK_MIN_USABLE_LINES,
    PEAK_WIDTH_CENSUS_N,
    DataQualityReport,
    PeakList,
)
from .peaks import Detection

#: Physical cause of each shift template, for the messages.  The template names
#: themselves come from ``report/layer2.py``'s ``_POSITION_ACTIONS`` — one
#: physical cause, one name, package-wide.
SHIFT_CAUSE: dict[str, str] = {
    "constant": "a detector zero-point error (instrument.zero_shift)",
    "cos_theta": ("specimen displacement from the focusing circle "
                  "(instrument.geometry.sample_displacement)"),
    "sin_2theta": ("specimen transparency — the beam penetrating a weakly "
                   "absorbing specimen (instrument.geometry.sample_transparency)"),
}

#: Ratio of measured to instrument-predicted FWHM above which the declared
#: instrument is reported as inconsistent with the data rather than merely
#: broadened by the sample.  3 is loose on purpose: real sample broadening of
#: 2-3× is ordinary, whereas the case worth shouting about is the ``ProfileTCHZ``
#: default (``W = 1e-3 deg²``, FWHM ≈ 0.03°, a *synchrotron* line) left on lab
#: data, which lands near 13.
WIDTH_MISMATCH_RATIO = 3.0


def peak_diagnostics(peaks: PeakList, detection: Detection | None = None,
                     ) -> list[Diagnostic]:
    """Translate a peak list's flags and a detection's width census.

    Public and separate from :func:`pxrdref.indexing.pick_peaks` because a list
    that arrives from outside — ``PeakList.from_positions``, i.e. the form the
    bethanechol benchmark comes in — needs the same translation without any
    detection to go with it.
    """
    out: list[Diagnostic] = []
    usable = peaks.usable()

    if len(usable) < PEAK_MIN_USABLE_LINES:
        out.append(Diagnostic(
            level="error", code="PEAK_LIST_TOO_SHORT",
            message=(f"{len(usable)} usable lines; the figures of merit the "
                     f"engines rank on (M20, F20) and Smith's volume envelope "
                     f"are all defined on {PEAK_MIN_USABLE_LINES}"),
            where=[f"2θ {peaks.two_theta_min:.2f}-{peaks.two_theta_max:.2f}°"],
            suggestion=("extend the 2θ range, count longer, or lower "
                        "PEAK_MIN_HEIGHT_SIGMA — but a list this short cannot "
                        "be scored, so indexing it would return a rank order "
                        "with no evidence behind it")))

    if peaks.source == "positions":
        out.append(Diagnostic(
            level="warning", code="PEAK_SIGMA_ASSUMED",
            message=("every σ(2θ) in this list was assumed, not measured, so "
                     "any per-line weighting downstream is weighting by a "
                     "constant"),
            where=[f"{len(peaks.peaks)} lines"],
            suggestion=("if the pattern is available, run "
                        "pxrdref.indexing.pick_peaks(data, instrument) instead "
                        "— the fitted σ is what makes the tolerance model "
                        "per-line rather than global")))

    shoulders = [p for p in peaks.peaks if "unresolved_shoulder" in p.flags]
    if shoulders:
        out.append(Diagnostic(
            level="info", code="PEAK_UNRESOLVED_SHOULDER",
            message=(f"{len(shoulders)} line(s) never separated from a "
                     "neighbour by half a FWHM, so their positions are "
                     "correlated with it and their σ says so"),
            where=[f"{p.two_theta:.4f}°" for p in shoulders],
            suggestion=("keep them — their σ already carries the penalty — but "
                        "do not quote one of a pair as an independent line")))

    ghosts = [p for p in peaks.peaks
              if {"ghost_kbeta", "ghost_tungsten"} & set(p.flags)]
    if ghosts:
        out.append(Diagnostic(
            level="info", code="PEAK_CONTAMINATION_LINE",
            message=(f"{len(ghosts)} line(s) sit at the Kβ or W Lα position of "
                     "a strong reflection and are excluded from usable(); they "
                     "are flagged, never subtracted"),
            where=[f"{p.two_theta:.4f}°" for p in ghosts],
            suggestion=("fit a monochromator or filter rather than stripping — "
                        "Rachinger stripping redistributes the counting noise, "
                        "so what is left has neither the position nor the σ it "
                        "appears to have")))

    asym = [p for p in peaks.peaks if "asymmetry_unmodelled" in p.flags]
    if asym:
        out.append(Diagnostic(
            level="warning", code="PEAK_ASYMMETRY_UNMODELLED",
            message=(f"{len(asym)} line(s) leave a significant odd residual "
                     "after fitting, i.e. an asymmetry the declared profile "
                     "does not carry; an unmodelled one-sided aberration biases "
                     "the centroid in one direction, which σ cannot see"),
            where=[f"{p.two_theta:.4f}°" for p in asym],
            suggestion=("set instrument.geometry.axial_sl and axial_hl to the "
                        "real aperture ratios and re-pick — the lowest-angle "
                        "lines are the ones indexing depends on most")))

    if detection is not None:
        out.extend(_width_diagnostics(detection))
    return out


def _width_diagnostics(det: Detection) -> list[Diagnostic]:
    """The width census against the instrument's own law."""
    out: list[Diagnostic] = []
    if det.fwhm_predicted <= 0.0:
        return out
    ratio = det.fwhm_measured / det.fwhm_predicted
    if ratio >= WIDTH_MISMATCH_RATIO or ratio <= 1.0 / WIDTH_MISMATCH_RATIO:
        out.append(Diagnostic(
            level="warning", code="PEAK_WIDTH_LAW_MISMATCH",
            message=(f"measured FWHM {det.fwhm_measured:.4f}° against "
                     f"{det.fwhm_predicted:.4f}° from the instrument's U,V,W,"
                     f"X,Y — a factor of {ratio:.1f}; seeds and windows were "
                     f"scaled by {det.width_scale:.2f} to match the data"),
            where=[f"median of the {PEAK_WIDTH_CENSUS_N} most prominent lines"],
            suggestion=("check instrument.profile: the ProfileTCHZ default "
                        "W = 1e-3 deg² is a synchrotron line (FWHM ≈ 0.03°) "
                        "and lands near 13 on lab data.  Run lab_calibrate on "
                        "a standard, or set U,V,W,X,Y from one")))
    if len(det.alias_two_theta):
        out.append(Diagnostic(
            level="info", code="PEAK_KALPHA2_ALIAS",
            message=(f"{len(det.alias_two_theta)} candidate(s) dropped as the "
                     "Kα2 maximum of a stronger line rather than lines of their "
                     "own; the doublet is fitted as a constrained pair, so each "
                     "reported position is a Kα1 position"),
            where=[f"{t:.4f}°" for t in det.alias_two_theta],
            suggestion=("a genuine line coincident with a stronger line's Kα2 "
                        "position is indistinguishable from an alias in one "
                        "pattern — confirm with an incident-side "
                        "monochromator (Instrument.bragg_brentano with a "
                        "Kα1-only radiation) if one of these matters")))
    if det.n_shoulder_seeds:
        out.append(Diagnostic(
            level="info", code="PEAK_SHOULDER_SEEDED",
            message=(f"{det.n_shoulder_seeds} curvature seed(s) offered for "
                     "components with no local maximum; survival was decided by "
                     "ΔBIC, not by detection"),
            where=[f"{len(det.groups)} groups"],
            suggestion=("pass shoulders=False to pick_peaks to see the list "
                        "without them, if a comparison needs maxima only")))
    return out


def quality_diagnostics(report: DataQualityReport, peaks: PeakList,
                        ) -> list[Diagnostic]:
    """Translate a :class:`DataQualityReport` into the ``INDEX_*`` messages.

    Separate from :func:`peak_diagnostics` on purpose: a peak list's flags and a
    data-quality *verdict* are different statements about the same lines, and an
    agent that re-picks peaks in response to the first would be answering the
    wrong question for the second.  The peak-level messages are not repeated
    here — a caller that wants both calls both.
    """
    out: list[Diagnostic] = []
    where_range = [f"2θ {report.two_theta_min:.2f}-{report.two_theta_max:.2f}°"]

    if report.abstained_reason is not None:
        out.append(Diagnostic(
            level="error", code="INDEX_DATA_INSUFFICIENT",
            message=report.abstained_reason,
            where=where_range,
            suggestion=("abstention is the result here — extend the 2θ range, "
                        "count longer, or re-pick with a lower "
                        "PEAK_MIN_HEIGHT_SIGMA.  Running a search anyway "
                        "returns a rank order with nothing behind it")))

    if np.isfinite(report.relative_sigma_q_median):
        level = ("warning" if report.relative_sigma_q_median
                 > 0.3 * MAX_RELATIVE_SIGMA_Q else "info")
        out.append(Diagnostic(
            level=level, code="PEAK_POSITION_PRECISION",
            message=(f"median σ(2θ) {report.sigma_two_theta_median:.4f}°, worst "
                     f"{report.sigma_two_theta_worst:.4f}°; median σ(Q)/Q = "
                     f"{report.relative_sigma_q_median:.2e} and σ(Q) is "
                     f"{report.sigma_over_spacing:.3f} of the mean line spacing"
                     + ("  (σ was ASSUMED, not measured)"
                        if report.source == "positions" else "")),
            where=where_range,
            suggestion=("read this as the resolving power of the list: it is "
                        "what decides whether two candidate cells can be told "
                        "apart at all, and it bounds every tolerance downstream"
                        + (".  Re-pick from the pattern with "
                           "pxrdref.pick_peaks to replace the assumed σ with a "
                           "fitted one" if report.source == "positions" else ""))))

    shift = report.shift
    if shift is not None and shift.source == "measured" and shift.best:
        best = next(t for t in shift.templates if t.name == shift.best)
        if shift.separable:
            out.append(Diagnostic(
                level="warning", code="INDEX_SHIFT_DETECTED",
                message=(f"a systematic 2θ shift of {best.coefficient:+.4f}° "
                         f"± {best.stderr:.4f} follows the {shift.best} "
                         f"template, i.e. {SHIFT_CAUSE.get(shift.best, shift.best)}"
                         f"; the runner-up leaves "
                         f"{shift.separability_ratio:.1f}× more unexplained"),
                where=where_range,
                suggestion=("carry this template — not a constant zeropoint — "
                            "into the candidate refinement, and correct the "
                            "instrument rather than the cell: the three causes "
                            "differ in angular dependence, so absorbing one "
                            "into another biases the cell systematically")))
        else:
            out.append(Diagnostic(
                level="warning", code="INDEX_SHIFT_MODEL_AMBIGUOUS",
                message=(f"a shift is present ({shift.best} fits at "
                         f"{best.coefficient:+.4f}°) but the templates are not "
                         f"separable over this range: the runner-up leaves only "
                         f"{shift.separability_ratio:.2f}× more unexplained and "
                         f"the largest template collinearity is "
                         f"{shift.max_collinearity:.3f}.  The cause is not "
                         f"claimed; the templates that fit comparably disagree "
                         f"by up to {shift.prediction_spread_deg:.4f}° over the "
                         "angles sampled, which is what choosing the wrong one "
                         "would cost"),
                where=where_range,
                suggestion=("extend the 2θ range: cos θ and sin 2θ separate "
                            "from a constant only when high-angle lines are "
                            "measured.  Meanwhile the *cell* is safe to the "
                            f"{shift.prediction_spread_deg:.4f}° above — carry "
                            "that as a systematic on every position — but the "
                            "instrument fault is not identified, so do not "
                            "correct one from this data")))

    return out


def significant(values: np.ndarray, threshold: float) -> np.ndarray:
    """``|values| >= threshold`` with non-finite entries counted as False.

    A NaN t-statistic means the projection had no norm (a zero-width or
    all-masked window), which is "not measured", not "significant".
    """
    v = np.asarray(values, dtype=np.float64)
    return np.isfinite(v) & (np.abs(v) >= threshold)


__all__ = ["SHIFT_CAUSE", "WIDTH_MISMATCH_RATIO", "peak_diagnostics",
           "quality_diagnostics", "significant"]
