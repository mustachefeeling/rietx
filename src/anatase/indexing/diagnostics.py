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

    Public and separate from :func:`anatase.indexing.pick_peaks` because a list
    that arrives from outside — ``PeakList.from_positions``, i.e. the form the
    bethanechol benchmark comes in — needs the same translation without any
    detection to go with it.
    """
    out: list[Diagnostic] = []
    usable = peaks.usable()

    if len(usable) < PEAK_MIN_USABLE_LINES:
        out.append(Diagnostic(
            level="warning", code="PEAK_LIST_TOO_SHORT",
            message=(f"{len(usable)} usable lines; the classical figures of "
                     f"merit (M20, F20) and Smith's volume envelope are "
                     f"defined on {PEAK_MIN_USABLE_LINES}, so this list can be "
                     "searched but not scored (WP-1043)"),
            where=[f"2θ {peaks.two_theta_min:.2f}-{peaks.two_theta_max:.2f}°"],
            suggestion=("the search runs over the systems the line count "
                        "supports (MIN_LINES_PER_DOF per system) and ranks on "
                        "the reduced panel — coverage in both directions and "
                        "the reversed figures — with confidence capped by the "
                        "fom_panel_reduced caveat.  To score against published "
                        "thresholds, extend the 2θ range, count longer, or "
                        "lower PEAK_MIN_HEIGHT_SIGMA until twenty lines are "
                        "usable")))

    if peaks.source == "positions":
        out.append(Diagnostic(
            level="warning", code="PEAK_SIGMA_ASSUMED",
            message=("every σ(2θ) in this list was assumed, not measured, so "
                     "any per-line weighting downstream is weighting by a "
                     "constant"),
            where=[f"{len(peaks.peaks)} lines"],
            suggestion=("if the pattern is available, run "
                        "anatase.indexing.pick_peaks(data, instrument) instead "
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

    repair = [p for p in peaks.peaks if "not_separable" in p.flags]
    if repair:
        out.append(Diagnostic(
            level="warning", code="PEAK_NOT_SEPARABLE",
            message=(f"{len(repair)} component(s) are profile-shape repair "
                     "rather than lines: a re-seed pass added each one inside a "
                     "much stronger neighbour's own profile, in a group whose "
                     "fit is still refuted — so the ΔBIC gain that bought it "
                     "cannot be told from the neighbour's shape being wrong"),
            where=[f"{p.two_theta:.4f}°" for p in repair],
            suggestion=("they are kept in peaks and excluded from usable(), "
                        "because removing one from the *model* displaces the "
                        "real line it sits on.  If many fire, suspect the "
                        "declared instrument profile rather than the specimen — "
                        "undeclared axial divergence reproduces this exactly")))

    tails = [p for p in peaks.peaks if "axial_tail" in p.flags]
    if tails:
        out.append(Diagnostic(
            level="info", code="PEAK_AXIAL_TAIL",
            message=(f"{len(tails)} weak component(s) sit on the "
                     "axial-divergence tail side of a much stronger group-mate "
                     "— the low-2θ side below 90° and the high-2θ side above "
                     "it, the one sign flip nothing else in a powder pattern "
                     "has (WP-1043)"),
            where=[f"{p.two_theta:.4f}°" for p in tails],
            suggestion=("kept usable: the side test is evidence, not proof, "
                        "and a real weak line can sit there too.  Measured on "
                        "SRM 660c, five such components carried 125 ppm of "
                        "certified-cell bias, and excluding exactly the "
                        "flagged ones (use_for_indexing=False) plus measuring "
                        "the shift took the gate to high at −2 ppm — so on a "
                        "well-aligned Bragg-Brentano pattern excluding them "
                        "is usually right, but look at the group's fit first "
                        "on a pattern whose answer you do not know")))

    residuals = [p for p in peaks.peaks if "kalpha2_residual" in p.flags]
    if residuals:
        out.append(Diagnostic(
            level="info", code="PEAK_KALPHA2_RESIDUAL",
            message=(f"{len(residuals)} weak component(s) sit at a strong "
                     "group-mate's predicted Kα2 maximum at a few per cent of "
                     "its area — the residual of a *modelled* doublet, "
                     "re-created by a re-seed pass after detection dropped "
                     "the alias candidate (WP-1043)"),
            where=[f"{p.two_theta:.4f}°" for p in residuals],
            suggestion=("kept usable for the same reason as axial_tail — a "
                        "real line can coincide with an alias position in one "
                        "pattern.  It is not a lattice line of anything: "
                        "exclude it before indexing unless the pattern gives "
                        "you a reason to believe a genuine reflection hides "
                        "under the doublet")))

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
    elif report.fom_undefined:
        absent = "; ".join(f"{name}: {why}"
                           for name, why in sorted(report.fom_undefined.items()))
        out.append(Diagnostic(
            level="warning", code="INDEX_PANEL_REDUCED",
            message=(f"{report.n_usable} usable lines is below the "
                     f"{PEAK_MIN_USABLE_LINES} the classical figures of merit "
                     f"are defined on, so the ranking panel is reduced — "
                     f"absent: {absent}"),
            where=where_range,
            suggestion=("the search still runs, over "
                        f"{', '.join(report.systems_supported) or 'no system'} "
                        "(the systems MIN_LINES_PER_DOF supports at this line "
                        "count), and Borda ranks on the members that remain — "
                        "the same members for every candidate, so the order "
                        "means what it always does.  Each absent figure is "
                        "reported with its reason on quality.fom_undefined "
                        "rather than computed at a different N, where it would "
                        "not be the published quantity; confidence is capped "
                        "by the fom_panel_reduced caveat")))

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
                           "anatase.pick_peaks to replace the assumed σ with a "
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


# ----------------------------------------------------------------------
# The answer's diagnostics (WP-1024)
# ----------------------------------------------------------------------
#: Cell systematic a Bragg-Brentano geometry carries that no esd reports, in ppm.
#: Measured (tag ``guillemot-study``, ``audit_tools.py`` check A): sweeping
#: ``Geometry.goniometer_radius_mm`` over 180-320 mm moves Rwp by 0.029 points —
#: i.e. **the data cannot identify R** — while specimen displacement absorbs the
#: change 4.6× and ≈ ±85 ppm lands on the lattice parameters, larger than the
#: fit's own 1σ.  It bites hardest here of anywhere in the package, because
#: indexing *produces* a cell from lab data with nothing to compare it against.
BRAGG_BRENTANO_CELL_PPM = 85.0

#: Where a per-candidate statement belongs.  Statements about **one** candidate go
#: on that candidate (``CellCandidate.diagnostics``); statements about the
#: **result** — that it abstained, what it did not search, that nothing validated
#: it — go on the result.  Not duplicated: ``INDEX_ABSTAINED`` names the top
#: candidates' caveats, which is the pointer from one level to the other, and
#: duplicating the text would let the two copies disagree.
_PER_CANDIDATE_CODES = ("INDEX_GEOMETRIC_AMBIGUITY", "INDEX_BRAVAIS_AMBIGUOUS",
                        "INDEX_PREDICTED_BUT_ABSENT", "INDEX_IMPURITY_LINES",
                        "INDEX_VOLUME_UNPHYSICAL")


def candidate_diagnostics(cand) -> list[Diagnostic]:
    """Everything to say about **one** candidate cell.

    Attached to the candidate rather than to the result, so a caller reading the
    third-ranked cell sees why it is third — and so a twelve-candidate answer does
    not bury its own abstention under thirty-six messages.
    """
    out: list[Diagnostic] = []
    where = [f"{cand.system} {cand.centring}, "
             f"V = {cand.volume:.1f} Å³, cell {_cell_str(cand.cell)}"]

    if cand.ambiguity:
        tt = [t for p in cand.ambiguity for t in p.discriminating_two_theta]
        out.append(Diagnostic(
            level="warning", code="INDEX_GEOMETRIC_AMBIGUITY",
            message=(f"{len(cand.ambiguity)} distinct lattice(s) explain these "
                     "line positions as well as this one does, and a powder "
                     "pattern carries only the length of each reciprocal vector "
                     "(Mighell & Santoro 1975) — so the information that would "
                     "separate them is absent from the measurement, not buried "
                     "in noise"),
            where=where,
            suggestion=("this is reported, never resolved: collect to the 2θ in "
                        "each partner's discriminating_two_theta and look for the "
                        "reflections it names"
                        + (f" (nearest: {min(tt):.2f}°)" if tt else "")
                        + ".  Quoting either cell before that is a coin toss with "
                        "a confidence attached")))

    if cand.bravais is not None and (cand.bravais.ambiguous
                                     or cand.bravais.methods_disagree):
        b = cand.bravais
        detail = []
        if b.ambiguous:
            detail.append(f"{b.system_loosest} appears only at a loose tolerance "
                          f"while {b.system} survives the whole sweep")
        if b.methods_disagree:
            detail.append(f"gemmi says {b.system_gemmi} and spglib says "
                          f"{b.system_spglib} at their tightest tolerances")
        out.append(Diagnostic(
            level="warning", code="INDEX_BRAVAIS_AMBIGUOUS",
            message="the lattice symmetry is not settled: " + "; ".join(detail),
            where=where,
            suggestion=("the reported system is the conservative one.  A "
                        "disagreement between the two methods is information "
                        "rather than a bug — their tolerances are different kinds "
                        "of number (a Le Page obliquity in degrees against a "
                        "symprec in Å) — and it is what genuine pseudosymmetry "
                        "looks like.  Refine in the lower symmetry and test the "
                        "higher one, never the reverse")))

    lebail = cand.lebail
    if lebail is not None and lebail.predicted_but_absent:
        tt = lebail.predicted_but_absent_two_theta
        out.append(Diagnostic(
            level="warning", code="INDEX_PREDICTED_BUT_ABSENT",
            message=(f"{lebail.predicted_but_absent} of {lebail.n_reflections} "
                     "reflections this lattice predicts have no net intensity "
                     "above the fitted background — the oversized-cell "
                     "signature, and the one M20 cannot see (its N_poss "
                     "denominator penalises it only weakly, Oishi-Tomiyasu 2013)"),
            where=where + ([f"first at {tt[0]:.3f}°"] if tt else []),
            suggestion=("prefer the smaller cell that indexes the same lines: a "
                        "cell whose extra reflections are systematically absent "
                        "has a translation it is not using, so the lattice is the "
                        "sublattice.  Read this beside lebail.rwp — Rwp is nearly "
                        "silent on an oversized cell (measured 0.389 against a "
                        "correct 0.200) and this count is what sees it")))

    if lebail is not None and lebail.unmatched_observed:
        tt = lebail.unmatched_observed_two_theta
        out.append(Diagnostic(
            level="warning", code="INDEX_IMPURITY_LINES",
            message=(f"{lebail.unmatched_observed} observed peak(s) have no "
                     "calculated reflection nearby after a whole-pattern Le Bail "
                     "fit of this cell"),
            where=where + ([f"strongest region near {tt[0]:.3f}°" ] if tt else []),
            suggestion=("two readings, and they are not the same action: a second "
                        "phase (index the residual — but note that this package "
                        "does not index multi-phase patterns, so subtract the "
                        "solved phase first), or a wrong cell.  A handful of "
                        "lines is an impurity; most of the pattern is a wrong "
                        "metric — measured, 87 of a 17-reflection cell's list "
                        "when the metric was 1 % off")))

    if "volume_unphysical" in cand.confidence_caveats:
        out.append(Diagnostic(
            level="warning", code="INDEX_VOLUME_UNPHYSICAL",
            message=(f"the cell volume {cand.volume:.1f} Å³ is outside what these "
                     "data can support — either below a single atom's exclusion "
                     "volume (a numerical artefact of the metric cone rather than "
                     "a lattice) or clear of Smith's (1977) envelope for the "
                     "number of lines observed"),
            where=where,
            suggestion=("a search only reaches here if max_volume was widened "
                        "past the envelope assess_peak_list supplied; narrow it, "
                        "or measure more lines — the envelope is a statement "
                        "about how many lines a cell of that size would show")))
    return out


def index_diagnostics(result, instrument=None) -> list[Diagnostic]:
    """Result-level ``INDEX_*`` messages: abstention, coverage, validation.

    Separate from :func:`candidate_diagnostics` on the rule stated at
    :data:`_PER_CANDIDATE_CODES`, and separate from the engines' own diagnostics
    (which arrive already built on :attr:`IndexingResult.diagnostics`) for the same
    reason :func:`quality_diagnostics` is separate from :func:`peak_diagnostics`:
    "the search did not finish" and "the answer does not qualify" are different
    statements, and an agent acting on one would be answering the wrong question
    for the other.
    """
    from ..schemas.indexing import Confidence  # noqa: F401  (documented vocabulary)
    from .engines import SYSTEM_ORDER

    out: list[Diagnostic] = []
    high = [c for c in result.candidates if c.confidence == "high"]

    if len(high) > 1:
        out.append(Diagnostic(
            level="warning", code="INDEX_MULTIPLE_SOLUTIONS",
            message=(f"{len(high)} candidate lattices each satisfy the whole "
                     "confidence gate, so the evidence does not choose between "
                     "them"),
            where=[f"{c.system} {c.centring}, V = {c.volume:.1f} Å³"
                   for c in high],
            suggestion=("best_or_none() returns None by construction here — a "
                        "singleton would be the confident wrong answer this API "
                        "exists to prevent.  Compare their figure-of-merit panels "
                        "and their lebail.rwp, and extend the 2θ range: two cells "
                        "that both explain a range this wide are usually "
                        "separated by one high-angle reflection")))

    if result.best_or_none() is None:
        top = result.candidates[0] if result.candidates else None
        caveats = ", ".join(top.confidence_caveats) if top else "no candidates"
        out.append(Diagnostic(
            level="warning" if result.candidates else "error",
            code="INDEX_ABSTAINED",
            message=(("no cell reached the confidence gate; the best candidate "
                      f"({top.system} {top.centring}, V = {top.volume:.1f} Å³) is "
                      f"{top.confidence} because of: {caveats}")
                     if top else
                     ("no candidate cell was found in the systems searched — "
                      "which is not the same statement as none existing, see "
                      "search_complete")),
            where=[f"searched: {', '.join(result.systems_searched) or 'nothing'}"],
            suggestion=("abstention is the result.  Read each candidate's "
                        "confidence_caveats and act on the refuting ones first "
                        "(geometric_ambiguity, predicted_but_absent, "
                        "fom_panel_disagrees, indexed_fraction_low, "
                        "volume_unphysical) — the others cap confidence rather "
                        "than arguing against the cell, and most of them are "
                        "closed by better data rather than by a different search")))

    if not result.validated:
        out.append(Diagnostic(
            level="warning", code="INDEX_NOT_VALIDATED",
            message=("no pattern was supplied, so no candidate was tested against "
                     "the whole profile; the figure-of-merit panel is computed on "
                     "at most 20 lines and is blind to lines beyond them, to "
                     "impurity content, and to reflections predicted where there "
                     "is no intensity"),
            where=[f"{len(result.candidates)} candidate(s) from a peak list only"],
            suggestion=("pass data= (and instrument=) to index_pattern.  Every "
                        "candidate caps at medium without it — the result "
                        "abstains rather than one field being quietly "
                        "downgraded")))

    missing = [s for s in SYSTEM_ORDER if s not in result.systems_searched]
    if missing:
        out.append(Diagnostic(
            level="info", code="INDEX_SYSTEMS_NOT_COVERED",
            message=(f"{len(missing)} crystal system(s) were not searched, so "
                     "this result says nothing about them"),
            where=missing,
            suggestion=("read a failure as 'no cell found in the systems "
                        "searched', never as a statement about the specimen — and "
                        "in particular never as 'this pattern is multiphase'.  "
                        "Measured on this repo's own data, a restricted engine's "
                        "coverage bands overlap between single-phase "
                        "low-symmetry patterns (47-60 %) and a genuine mixture "
                        "(69 %), and a multiphase claim built on that ambiguity "
                        "was withdrawn")))

    systematic = _cell_systematic(instrument, bool(result.candidates))
    if systematic is not None:
        out.append(systematic)
    return out


def _cell_systematic(instrument, have_candidates: bool) -> Diagnostic | None:
    """``INDEX_CELL_SYSTEMATIC_UNQUANTIFIED`` — the cell's esd is not its accuracy.

    **The trigger the plan named is unreachable, and the reachable one is
    stronger.**  WP-1024 asked for this to fire "on Bragg-Brentano data when no
    radius was supplied"; ``Geometry._bb_needs_radius`` *raises* on exactly that,
    so no such instrument exists.  The real gap is that a **declared** radius is
    not identifiable from the data either — Rwp moves 0.029 points across
    180-320 mm — so the systematic is present whatever the caller declared, and it
    is unquantified because the fit cannot measure it.
    """
    if not have_candidates:
        return None
    if instrument is None:
        return Diagnostic(
            level="info", code="INDEX_CELL_SYSTEMATIC_UNQUANTIFIED",
            message=("no instrument was supplied, so the geometry that would "
                     "determine the cell's systematic error is unknown; the "
                     "reported cell_esd is a *precision* from the line positions "
                     "and says nothing about accuracy"),
            where=["geometry unknown"],
            suggestion=("pass instrument= — on a Bragg-Brentano diffractometer "
                        f"the goniometer radius alone carries ≈ ±"
                        f"{BRAGG_BRENTANO_CELL_PPM:.0f} ppm onto the cell"))
    if instrument.geometry.kind != "bragg_brentano":
        return None
    return Diagnostic(
        level="info", code="INDEX_CELL_SYSTEMATIC_UNQUANTIFIED",
        message=(f"a Bragg-Brentano cell carries ≈ ±{BRAGG_BRENTANO_CELL_PPM:.0f} "
                 "ppm that no esd reports: sweeping the goniometer radius over "
                 "180-320 mm moves Rwp by only 0.029 points, so the data cannot "
                 "identify it, while specimen displacement absorbs the change 4.6× "
                 "and the rest lands on the lattice parameters"),
        where=[f"R = {instrument.geometry.goniometer_radius_mm:g} mm (declared, "
               "not measured by the fit)"],
        suggestion=("quote the cell to no better than this, or calibrate against "
                    "a certified standard (lab_calibrate with the certified cell "
                    "held fixed) and carry the correction.  It bites hardest here "
                    "of anywhere in the package, because indexing produces a cell "
                    "with nothing to compare it against"))


# ----------------------------------------------------------------------
# WP-1025 — the extinction screen
# ----------------------------------------------------------------------
def extinction_class_diagnostics(cand) -> list[Diagnostic]:
    """Everything to say about **one** extinction class.

    Same split as :data:`_PER_CANDIDATE_CODES` one level up: a refutation belongs
    to the class it refutes, while "your answer is not one space group" is a
    statement about the answer and lives on the screen.
    """
    out: list[Diagnostic] = []
    where = [f"{cand.symbol} (fitted as {cand.representative})"]
    if cand.refuted and cand.forbidden_hkl:
        pairs = ", ".join(f"{tuple(h)} at {t:.3f}°" for h, t in
                          zip(cand.forbidden_hkl[:4],
                              cand.forbidden_two_theta[:4]))
        out.append(Diagnostic(
            level="warning", code="EXTINCTION_FORBIDDEN_INTENSITY",
            message=(f"{cand.n_present} of the {cand.n_testable} forbidden "
                     "position(s) this class could be tested at carry intensity "
                     "its own Le Bail fit cannot account for — the absences it "
                     "claims are not in the pattern"),
            where=where + [pairs],
            suggestion=("look at those 2θ in the pattern: the test is a 3σ "
                        "integral over ±½ FWHM of the fit residual, so it sees "
                        "what the class's allowed reflections and the background "
                        "leave over.  A single flagged position can also be an "
                        "impurity line — check it against "
                        "IndexingResult's unmatched_observed before dropping the "
                        "class")))
    if cand.n_absent and not cand.n_testable:
        out.append(Diagnostic(
            level="info", code="EXTINCTION_SYMBOL_AMBIGUOUS",
            message=(f"none of the {cand.n_absent} line(s) this class forbids "
                     "can be tested by these data: each is either outside the "
                     "fitted range or coincides with a line the class still "
                     "allows"),
            where=where,
            suggestion=("this class is indistinguishable from a less restrictive "
                        "one here, and it is *not* preferred on parsimony — the "
                        "nested comparison counts only testable lines, so an "
                        "absence nobody could see earns nothing.  Extending the "
                        "range or resolving the overlap is what would separate "
                        "them")))
    if not cand.conditions_complete:
        out.append(Diagnostic(
            level="info", code="EXTINCTION_CONDITIONS_PARTIAL",
            message=("the reflection conditions printed for this class do not "
                     "name every absence in it — the screen used the absence set "
                     "itself, which is unaffected, but the human-readable list is "
                     "incomplete"),
            where=where + [f"conditions: {'; '.join(cand.conditions) or 'none'}"],
            suggestion=("read space_groups rather than conditions here; the "
                        "derivation covers 549 of gemmi's 550 settings and says "
                        "so rather than guessing")))
    return out


def extinction_diagnostics(screen) -> list[Diagnostic]:
    """Screen-level messages: what the answer is, and why it may not be one.

    ``EXTINCTION_GROUPS_NOT_SEPARABLE`` fires whenever the leading class holds
    more than one space group — **always**, not only when the data are weak.
    That is a statement about the physics: those groups differ by symmetry
    elements a powder pattern cannot carry, so no amount of counting time
    separates them, and a caller who needs one of them is using chemistry, not
    these data.
    """
    from ..schemas.indexing import ExtinctionScreen  # noqa: F401  (documented)
    from .extinction import DECISIVE_DELTA_BIC

    out: list[Diagnostic] = []
    alive = [c for c in screen.candidates if not c.refuted and c.screened]
    unscreened = [c for c in screen.candidates if not c.refuted and not c.screened]
    if not screen.candidates:
        return [Diagnostic(
            level="warning", code="EXTINCTION_SYMBOL_AMBIGUOUS",
            message=("no extinction class could be screened: the lattice "
                     f"{screen.lattice_group} produced no fittable reflections in "
                     f"{screen.two_theta_range[0]:.1f}-"
                     f"{screen.two_theta_range[1]:.1f}° 2θ"),
            where=[f"{screen.system} {screen.centring}"],
            suggestion="check the cell and the wavelength before reading further")]

    top = alive[0] if alive else screen.candidates[0]
    if len(top.space_groups) > 1:
        out.append(Diagnostic(
            level="info", code="EXTINCTION_GROUPS_NOT_SEPARABLE",
            message=(f"extinction symbol {top.symbol} is compatible with "
                     f"{len(top.space_groups)} space groups, and a powder pattern "
                     "cannot separate them: they differ only by symmetry elements "
                     "that produce no systematic absences (centre of symmetry, "
                     "enantiomorph, a mirror), so the patterns are identical by "
                     "construction rather than for want of counting time"),
            where=[", ".join(top.space_groups)],
            suggestion=("choose between them with chemistry, not with these data "
                        "— an optically active or polar compound cannot be "
                        "centrosymmetric, |E²−1| statistics are indicative at "
                        "best, and a structure solution that works in one is the "
                        "usual arbiter.  Any of them can be handed to "
                        "structure_from_candidate for the next fit")))

    reasons = []
    if len(alive) > 1 and alive[1].delta_bic - top.delta_bic < DECISIVE_DELTA_BIC:
        reasons.append(f"{alive[1].symbol} is within ΔBIC "
                       f"{alive[1].delta_bic - top.delta_bic:.1f} of it "
                       f"(decisive is {DECISIVE_DELTA_BIC:g})")
    if top.n_absent and not top.n_testable:
        reasons.append("none of its absences is testable in this range")
    if unscreened:
        reasons.append(f"{len(unscreened)} class(es) were never fitted, so their "
                       "standing is unknown")
    if not alive:
        reasons.append("every class was refuted, including the absence-free "
                       "lattice — which means the fit itself failed, not the "
                       "symmetry")
    if reasons:
        out.append(Diagnostic(
            level="warning", code="EXTINCTION_SYMBOL_AMBIGUOUS",
            message=("the extinction symbol is not settled by these data: "
                     + "; ".join(reasons)),
            where=[f"leading: {top.symbol}"]
            + [f"then: {c.symbol} (ΔBIC {c.delta_bic:+.1f})" for c in alive[1:3]],
            suggestion=("best_or_none() returns None for exactly this reason.  "
                        "The discriminating evidence is the forbidden positions "
                        "the leading classes disagree about — count longer at "
                        "those 2θ, or extend the range, rather than picking the "
                        "better Rwp, which always favours the class with more "
                        "reflections")))
    return out


def _cell_str(cell) -> str:
    a, b, c, al, be, ga = cell
    return (f"{a:.4f} {b:.4f} {c:.4f} Å, {al:.3f} {be:.3f} {ga:.3f}°")


def significant(values: np.ndarray, threshold: float) -> np.ndarray:
    """``|values| >= threshold`` with non-finite entries counted as False.

    A NaN t-statistic means the projection had no norm (a zero-width or
    all-masked window), which is "not measured", not "significant".
    """
    v = np.asarray(values, dtype=np.float64)
    return np.isfinite(v) & (np.abs(v) >= threshold)


__all__ = ["BRAGG_BRENTANO_CELL_PPM", "SHIFT_CAUSE", "WIDTH_MISMATCH_RATIO",
           "candidate_diagnostics", "extinction_class_diagnostics",
           "extinction_diagnostics", "index_diagnostics", "peak_diagnostics",
           "quality_diagnostics", "significant"]
