"""Model-free pattern diagnostics — the structured object an agent (or the
background auto-selection) reasons over before any refinement is attempted.

Everything is computed from the raw pattern alone; nothing here linearises or
assumes a structural model.  Baseline *shape* questions (amorphous hump, air
scatter) are answered from a **rolling low-quantile envelope** rather than an
arPLS baseline: the answers must not depend on a smoothing λ that is itself
being chosen (arPLS stiff enough to be safe under peaks is too stiff to
follow a genuine hump — measured, which is why the envelope is used here).
Wavelength-dependent contamination checks (Kβ ghosts, W Lα from an aging
tube) run only when the primary wavelength is supplied.

One measure here reads the **σ column** rather than the intensities:
:func:`counting_coverage`, which asks whether every channel was observed with
the same statistical weight.  On a multi-detector instrument it is not — fewer
detectors reach the ends of the range — and the σ column is the only place that
shows.  It is the one thing in this module that a Poisson fallback σ cannot
answer at all, so it returns nothing rather than a number.

One measure is about the **range** rather than about the pattern on it, and it
is read before all the others: :func:`signal_cutoffs`, which finds leading or
trailing stretches where the instrument stopped seeing the sample.  Everything
else here is computed over the whole range it is handed, so a dead end corrupts
those answers — measured, and the numbers are in that function's docstring.  It
reads the **intensities**, and it is not :func:`counting_coverage` under another
name: measured on the pattern quoted there, σ²/y holds at ≈20 000 straight
through the collapse, so σ is honest and those channels are not thinly covered,
they are empty.  What σ adds is that same level re-expressed as a precision, and
:class:`SignalCutoff` carries it as a derived number rather than as a second
observation.
"""

from __future__ import annotations

import warnings

import numpy as np
from pydantic import Field
from scipy.ndimage import median_filter
from scipy.signal import find_peaks, peak_widths

from ..schemas.common import Base
from ..schemas.pattern import PatternData
from .models import chebyshev_design_matrix

#: Kβ1,3 wavelengths (Å) per anode, for contamination checks only — Kβ is never
#: a modelled emission line (see ``schemas.instrument._RADIATIONS``).  Same
#: source and column as the Kα table it is keyed against: the NIST X-ray
#: Transition Energies Database (SRD 128) direct-experimental KM3.  For the 3d
#: metals that column reports the KM2,3 *blend*, which is what a check wants;
#: for Mo and Ag it resolves Kβ1 (KM3) from Kβ3 (KM2, half the weight), and we
#: take Kβ1 rather than blending them 2:1 — the two choices differ by 3.1e-4
#: relative, i.e. Δ2θ = 2·tanθ·Δλ/λ ≤ 0.02° out to 60° 2θ, which is an order
#: inside the 0.15° matching window in :func:`_contamination_flags`.
_KBETA: dict[str, float] = {
    "CrKa": 2.0848810,
    "FeKa": 1.7566040,
    "CoKa": 1.6208260,
    "CuKa": 1.3922340,
    "MoKa": 0.632303,
    "AgKa": 0.4970817,
}

#: W Lα1 (Bearden 1967, Rev. Mod. Phys. 39, 78).  Tungsten reaches the target
#: by subliming off the *filament*, so unlike Kβ this line is a property of the
#: tube's age rather than of the anode material, and is checked for every anode.
_W_LA1 = 1.4763800

#: How close the pattern's wavelength must be to an anode's Kα1 to be treated
#: as that anode.  The closest pair in the table is Fe/Co at 0.147 Å (Mo/Ag is
#: next at 0.150), so the assignment cannot be ambiguous — but it can be
#: *absent*, and that is the case the caller has to handle.
_ANODE_MATCH_TOL = 0.01

#: Floor on the ghost-matching window in ° 2θ.  It is a *floor*, not the whole
#: budget: the predicted ghost position carries error that a fitted σ(2θ) knows
#: nothing about — the Kβ wavelength table (≈3e-4 relative for the blended 3d
#: entries, i.e. Δ2θ = 2·tanθ·Δλ/λ ≈ 0.02° at 60°) and any unmodelled 2θ shift.
#: When per-line σ(2θ) *is* supplied, :data:`GHOST_MATCH_K`·√(σ_g² + σ_p²) may
#: widen the window but never narrows it, so a poorly-determined line is matched
#: loosely and a well-determined one is not matched *more* tightly than the
#: prediction deserves.
GHOST_TOL_DEG = 0.15
#: How many combined σ the observed ghost may sit from its predicted position.
GHOST_MATCH_K = 3.0
#: Ghost/parent intensity-ratio window.  Kβ is ≤ ~0.2 of Kα even unfiltered and
#: W Lα weaker still, so anything above the upper bound is a reflection, not a
#: ghost; the lower bound keeps noise-level coincidences out.
GHOST_RATIO_RANGE = (0.005, 0.6)
#: How many of the strongest lines are searched for ghosts.  A ghost of a weak
#: line is below noise by construction.
GHOST_N_PARENTS = 8

#: The sampling band of McCusker, Von Dreele, Cox, Louër & Scardi (1999) §2:
#: "There should be at least five steps (but generally not more than ten)
#: across the top of each peak (i.e. step size = FWHM/5)".  The two ends are
#: **not** the same kind of statement — below the minimum the integrated
#: intensities were never measured and no refinement can recover them, while
#: above the maximum the experiment merely spent longer than it needed to.  So
#: only the lower one is ever flagged; the upper is here because a reader
#: comparing against the guideline needs both halves of the sentence.
STEPS_PER_FWHM_MIN = 5.0
STEPS_PER_FWHM_MAX = 10.0

#: How far a maximum must rise above its flanking saddles, in σ, before the
#: sampling measurement treats it as a *resolved* peak rather than a bump.
#: Without it the measurement inverts on exactly the patterns it exists to
#: judge: on an undersampled synthetic LaB6 (17 reflections, 3.2 steps per
#: FWHM by construction) plain 5σ detection returns **49** peaks and a median
#: width of 1.38 steps, because Poisson noise on a 10⁵-count peak puts several
#: 5σ maxima across its own jagged top.  A spurious maximum's *prominence*
#: above the saddle beside it is small, which is what separates the two.
#: Measured at 5 and at 20: identical answers on all four grids of the sweep in
#: WP-1071's handover, so the number is a floor and not a tuning.
SAMPLING_PROMINENCE_SIGMA = 5.0

#: Median-filter width, in ° 2θ, applied to the variance-inflation ratio before
#: any region is cut out of it (:func:`counting_coverage`).  It is what makes the
#: threshold below mean anything: measured on the two BT-1 patterns quoted there,
#: the *per-channel* ratio through the quiet middle of the scan (60-145°) makes
#: single-channel excursions to 2.27 and 2.43 — higher than the genuine steps the
#: measure exists to find — and **every one of them is exactly one channel long**
#: (3 and 4 such channels respectively), while a median over 11 channels leaves
#: nothing above even 1.3 there.  Measured at 11, 21 and 41 channels: the regions
#: come back the same, so the width is a floor and not a tuning.  1.0° is 21
#: channels at those files' 0.05° step.
COVERAGE_SMOOTH_DEG = 1.0

#: How many times the plateau's variance-per-count a smoothed channel must carry
#: before it counts as thinly covered.  Set from the gap between the two things
#: it has to separate, on ``Al2O3023.xye`` (NIST BT-1, 3.00-166.25° at 0.05°,
#: 3266 points, σ from the file): the smoothed ratio *drifts* over 1.11-1.37
#: through 149-161°, then **steps** to 2.25 in a single channel at 161.30° and
#: holds it to the end of the scan.  1.5 sits between the two with ≈1.4× margin
#: on each side.  Not tuned to taste: neither BT-1 pattern's plateau reaches it
#: anywhere (smoothed maximum 1.3 over 60-145°), and the region that matters —
#: the one past the step — is identical at 1.3, 1.5 and 1.75.
COVERAGE_INFLATION_THRESHOLD = 1.5

#: How far below the interior level a run must sit to be a *collapse* rather
#: than a falling background (:func:`signal_cutoffs`).  Swept on the three ILL
#: D20 patterns quoted there, 0.15 to 0.40, watching the reported boundary:
#: the **trailing** cliff barely moves (143.33 → 142.73°, 0.6° over a 2.7×
#: change in the constant) because it is steep, while the **leading** boundary
#: is flat at 7.63-7.73° over 0.20-0.30 and then breaks — 9.63° at 0.35, 11.53°
#: at 0.40 — because the leading end is a graded climb that only reaches 32 % of
#: the interior level by 8°, so a threshold above ≈0.32 swallows the climb
#: itself and the walk-back starts from inside live data.  0.25 sits in the
#: middle of the flat stretch, with ≈1.3× margin to the break above and to the
#: 0.15 that puts the run's inner edge below the 4.6° halo bump.  It is also
#: what keeps a sample-free ``Background.xye`` silent at the low end (it fires
#: there at 0.30 and above), which is the one file in the set with no low-angle
#: answer to get right.
CUTOFF_FRACTION = 0.25

#: The fraction of the local plateau at which the collapse is declared to have
#: *begun*, which is the 2θ actually reported.  The floor is not the boundary a
#: fit range wants: on ``306774`` the trailing level is still 92 % of interior
#: at 142.83°, 24 % at 144.03° and 2-3 % from 145.2° on, so reporting where it
#: reaches the floor would hand back 2.3° of unfittable transition inside the
#: range.  Swept 0.80 to 0.99 on the two SrFeO₃ files, it is the gentlest of
#: these constants and the only monotone one: the trailing boundary moves
#: 143.23 → 143.13 → 143.03 → 143.03 → 142.93° and the leading one
#: 7.43 → 7.63 → 7.63 → 7.93 → 8.13°, i.e. ≈0.1-0.2° per 0.05 of the constant,
#: with no break anywhere.  0.90 is where both files agree with TOPAS's own
#: window to within half a degree; a caller who wants the boundary further out
#: or further in should pass ``onset_fraction`` rather than expect a different
#: default to be more correct.
CUTOFF_ONSET_FRACTION = 0.90

#: Shortest collapse, in ° 2θ, that is reported at all.  Twice
#: :data:`CUTOFF_SMOOTH_DEG` and for that reason: a run the smoothing cannot
#: resolve is not evidence, so the shortest reportable feature follows the
#: window it was measured through rather than being a second tunable of its
#: own.  A shorter run at an edge is a dip or a gap in the first channels, not
#: an instrument that stopped.
CUTOFF_MIN_DEG = 1.0

#: Rolling-median width, in ° 2θ, that turns the intensities into a *level*.
#: It is there to stop one spike or one dropped channel opening or closing a
#: run, not to remove peaks — the plateau window below is what averages over
#: those.  Measured at 0.3, 0.5, 1.0 and 2.0° on the three D20 patterns: 0.3
#: and 0.5 give identical boundaries at both edges, and 1.0-2.0 move the
#: trailing one by a single channel, so 0.5 is a floor rather than a tuning.
CUTOFF_SMOOTH_DEG = 0.5

#: Width, in ° 2θ, of the window just inside a collapse whose median level is
#: the "local plateau" the onset is measured against.  It has to clear the
#: cliff without being taken over by one strong peak, and both failures were
#: measured on ``306774``: at 0.5° the window sits *inside* the collapse, the
#: plateau reads 0.38 of interior and the reported trailing boundary lands at
#: 143.73°, half-way down the cliff; at 3° it reaches back over a 110 %-of-
#: interior peak, reads 1.10, and walks out to 142.73°, trimming live data.
#: Between 1 and 3° the answer moves 143.53 → 143.03 → 142.73°, i.e. under 1°
#: for a 3× change, and every one of those lies between the last full-level
#: channel (142.43°) and the floor (145.2°) — TOPAS's own ``finish_X 142`` sits
#: just inside all three, so the decision this supports is insensitive even
#: where the number is not.
CUTOFF_PLATEAU_DEG = 2.0

#: The central fraction of the range whose median level is "the interior".  It
#: must exclude both dead ends, and 0.70 clears them with ≈2× margin on the
#: files measured (the leading region is 4.7 % of the channels, the trailing one
#: 6.5-7 %).  A pattern whose dead ends exceed 15 % of the channels drags the
#: interior median down towards them, the threshold with it, and the measure
#: under-reports — silence rather than a false claim, which is the direction to
#: fail in.
CUTOFF_INTERIOR_FRACTION = 0.70


class ContaminationFlag(Base):
    """A weak peak consistent with a known contamination line of a strong one."""

    kind: str                  # "kbeta" | "tungsten_la"
    two_theta: float           # where the ghost sits
    parent_two_theta: float    # the strong Kα parent reflection
    intensity_ratio: float     # ghost/parent net height


class SignalCutoff(Base):
    """An end of the pattern where the instrument stopped seeing the sample.

    Not a verdict and not applied anywhere: :func:`signal_cutoffs` reports, and
    the caller decides what the fit range is.  The five numbers are five
    separate questions a caller has to answer before it can decide.

    ``edge`` is which end, and it is not cosmetic — the two ends fail for
    different reasons and carry different arguments (both measured, in
    :func:`signal_cutoffs`).  A ``"high"`` cutoff is the detector's active area
    running out: there is no diffraction information past it at all.  A
    ``"low"`` one is a beamstop or its halo, where there *is* structure — a
    direct-beam shoulder, a shadowed floor, a broad bump at an angle no lattice
    plane could put one — and it is structure that does not belong to the
    specimen.

    ``two_theta`` is the boundary, and it is the **onset** of the collapse
    rather than where the level reaches its floor, because the onset is what a
    fit range should stop at.  It is a channel that is still at level, so a
    caller trimming to it keeps it: ``n_channels`` is exactly what such a trim
    would drop, which is why the count is reported rather than the region's own
    width — 109 of 1540 channels is the fact, and 9.9° is not.

    ``floor_fraction`` is how dead: the region's median level over the interior
    level.  A **median**, so it summarises rather than resolves, and the two
    ends of the same file are different shapes underneath the same kind of
    number (0.025 trailing, a genuine floor; 0.10 leading, an average over a
    shadowed floor near 0.05 and a halo bump near 0.14).  It is also the number
    that separates "there is nothing here" from "there is less here", which is a
    judgement this function declines to make for the caller.

    ``relative_error_ratio`` is the implied precision penalty — the region's
    median σ/y over the interior's — and it is **derived, not a second
    observation**.  Where σ²/y is constant, as it is on every pattern measured
    here, σ/y = √(σ²/y) / √y, so the ratio is 1/√``floor_fraction`` and nothing
    more: measured on ``306774``, 3.18 against 3.13 at the leading edge and 6.35
    against 6.34 at the trailing one.  It is carried because it is the language
    the person who took the data uses ("the data quality steps below the
    cutoff") and because saying so once here is what stops a third measure of
    the same fact being added later.  ``None`` when σ was not measured: under
    the Poisson fallback the ratio is *identically* 1/√``floor_fraction``, so
    reporting it would be reporting the fallback.
    """

    edge: str                       # "low" | "high"
    two_theta: float                # the boundary — the onset of the collapse
    floor_fraction: float           # the region's median level / the interior level
    n_channels: int                 # channels outside the boundary
    relative_error_ratio: float | None = None   # median σ/y there, over interior


class CoverageRegion(Base):
    """A stretch of pattern whose σ carries more variance per count than the
    bulk of the scan does — fewer independent observations behind each channel.

    Purely **descriptive**, and deliberately so.  If σ is right then weighted
    least squares already gives these channels the weight they deserve, which is
    the whole job σ has; the region is a fact about *the experiment's coverage*,
    not a verdict on the data.  What it tells a caller is that the pattern's
    statistical weight is not uniform across its range — which is about how many
    detectors saw each angle, and about nothing to do with the specimen.

    The four numbers are the four separate questions: where it is, how much
    variance per count it carries relative to the bulk (``inflation``), how much
    of the pattern that is (``n_channels`` — a 3-channel region and a 700-channel
    one are different facts about the same ratio), and *where in the range* it
    sits.  ``edge`` is not a hint to do anything: a region at either end of the
    scan is the detector bank's coverage running out, the ordinary geometry of a
    multi-detector instrument, while an interior one has a different cause
    entirely (a dead or excluded detector, two scans stitched together), so the
    two must not be read as the same observation.  Both ends cannot be one
    region, because the plateau is measured in the middle.

    ``inflation`` is a **median** over the region, so it summarises rather than
    resolves: a region can hold finer steps of its own (on ``Al2O3023.xye`` the
    low-angle region runs ≈5× below 8°, ≈2.2× from 8-11°, ≈4× over 11.3-13°, then
    ≈2.2× tapering to 1× by ≈55°), and the levels are not even monotonic in 2θ.
    """

    two_theta_min: float
    two_theta_max: float
    inflation: float           # median σ²/max(y,1) in the region, over the plateau
    n_channels: int
    edge: str                  # "low" | "high" | "interior"


class PatternDiagnostics(Base):
    """Agent-readable observations about a raw pattern (no model involved).

    **Read ``signal_cutoffs`` first.**  Every other field here is computed over
    the whole range this object was handed, so where a cutoff exists they are
    measurements of a range that includes channels the instrument was not
    seeing the sample through, and they say so.  Measured on the ILL D20
    pattern of :func:`signal_cutoffs` (0.03-153.93°, against the 8-142° window
    TOPAS's own refinements of it declare): the dead tail inflates
    ``amorphous_hump_score`` 1.85× (0.2549 against 0.1380), **hides** the
    low-angle air-scatter rise altogether (``air_scatter_gain`` 0.0027 against
    0.1433, 52× understated), and moves ``baseline_lambda`` by two decades
    (10⁴ against 10⁶).  Nothing is re-run on a trimmed range and no field's
    value depends on the cutoffs — a diagnostic that quietly reported numbers
    for a range the caller did not ask about would be worse than one that says
    which range it used.  The ordering is the handling: read the cutoffs, decide
    the range, ask again if you changed it.

    * ``peak_fraction`` — fraction of channels more than 3σ above the
      envelope: how much of the pattern is peak rather than background.
    * ``peak_density_per_deg`` — resolved-peak count per degree 2θ; dense
      patterns (≳2/deg) favour stiff baselines and low background order.
    * ``signal_to_background`` — near-maximum net signal (99.9th percentile)
      over the median background level.
    * ``air_scatter_gain`` — fraction of the cubic-fit residual variance of
      the background envelope explained by adding a 1/(2θ) column, i.e. a
      nested-model test for the low-angle air-scatter rise.  ≳0.3 triggers
      the 1/x background term.
    * ``amorphous_hump_score`` — RMS residual of the envelope *after* the
      cubic **and** the 1/x term, relative to the median level: what is left
      is genuinely broad non-polynomial structure (amorphous content,
      capillary glass).  ≳0.05 calls for a more flexible background.
    * ``contamination`` — Kβ / W Lα ghost candidates.  Needs ``wavelength``,
      and an *empty list means nothing was flagged or nothing was checked*:
      the Kβ position is anode-specific, so a wavelength that matches no
      tabulated Kα1 (:func:`identify_anode`) is silently skipped.
    * ``baseline_lambda`` — the arPLS stiffness the whiteness rule selects
      for this pattern (:func:`rietx.background.select_arpls_lambda`).
    * ``steps_per_fwhm`` / ``n_peaks_measured`` — how finely the peaks were
      sampled, and over how many of them
      (:func:`sampling_steps_per_fwhm`).  ``None`` when no peak was
      measurable.  This is the one number here about the *experiment* rather
      than the pattern: below :data:`STEPS_PER_FWHM_MIN` no refinement can
      repair it, because the counts were never collected.
    * ``coverage_plateau`` — the bulk pattern's σ²/max(y, 1), the median over
      the middle half of the range.  1.0 is pure Poisson counting; a value
      away from 1 means the file's σ is something else (merged detectors, a
      monitor normalisation), which is a fact worth having on its own.
      ``None`` means σ was *not measured* and nothing below was checked.
    * ``coverage_regions`` — stretches carrying more variance per count than
      that plateau (:func:`counting_coverage`), i.e. fewer independent
      observations per channel.  Says the pattern's statistical weight is not
      uniform across its range, and how; triggers **nothing**, because a
      correct σ is already the whole handling.  Empty and
      ``coverage_plateau`` set means checked and uniform; empty with
      ``coverage_plateau`` ``None`` means not checkable.
    * ``signal_cutoffs`` — ends of the range where the instrument stopped
      seeing the sample (:func:`signal_cutoffs`), each a :class:`SignalCutoff`.
      Empty means the pattern's own ends are at its own interior level, which
      is the ordinary case and the one every other field here assumes.
    """

    n_points: int
    two_theta_min: float
    two_theta_max: float
    baseline_lambda: float
    noise_sigma_median: float
    peak_fraction: float
    n_peaks: int
    peak_density_per_deg: float
    signal_to_background: float
    amorphous_hump_score: float
    air_scatter_gain: float
    steps_per_fwhm: float | None = None
    n_peaks_measured: int = 0
    contamination: list[ContaminationFlag] = Field(default_factory=list)
    coverage_plateau: float | None = None
    coverage_regions: list[CoverageRegion] = Field(default_factory=list)
    signal_cutoffs: list[SignalCutoff] = Field(default_factory=list)


def background_envelope(two_theta: np.ndarray, y: np.ndarray, *,
                        window_deg: float = 3.0, quantile: float = 10.0
                        ) -> np.ndarray:
    """Rolling low-quantile envelope of the pattern — a peak-robust,
    λ-free stand-in for the background level.

    Windows are wider than any Bragg FWHM, so the low quantile inside each
    lands on background channels; the per-window values are interpolated back
    onto the grid.  Unlike a Whittaker/arPLS baseline this has no smoothing
    parameter to choose, which is what makes it usable *for* choosing one.

    **Each knot's x is its window's centre, so the outermost knots sit half a
    window inside the data and the edges must be extrapolated, not clamped**
    (WP-1028 §(i)).  ``np.interp`` clamps flat outside its knot range; against
    a falling background that clamp sits far under the truth, and the whole
    first half-window reads as positive net — enough for the peak picker to
    find a line on the pattern's rising left edge.  Measured across the seven
    bundled round-robin patterns: ``y[0]`` was 1.5-2× ``env[0]``, putting
    z = 4.7-6.9σ on the very first channel against a 5σ bar, and **five** such
    false lines survived to ``PeakList.usable()``.  So a knot is anchored at
    each *data edge*, linearly extrapolated from the two nearest — no new
    tunable, and no cropping, which would discard a real low-angle line on a
    specimen that has one.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    yy = np.asarray(y, dtype=np.float64)
    step = float(np.median(np.diff(tt)))
    w = max(int(window_deg / max(step, 1e-12)), 5)
    xs, ys = [], []
    for s in range(0, len(yy), max(w // 2, 1)):
        seg = yy[s:s + w]
        if len(seg) < 3:
            continue
        xs.append(float(tt[s:s + w].mean()))
        ys.append(float(np.percentile(seg, quantile)))
    if len(xs) < 2:
        return np.full_like(tt, float(np.median(yy)))
    xs, ys = _extrapolate_to_edges(xs, ys, float(tt[0]), float(tt[-1]))
    return np.interp(tt, np.asarray(xs), np.asarray(ys))


def envelope_measured_span(two_theta: np.ndarray, *,
                           window_deg: float = 3.0) -> tuple[float, float]:
    """The 2θ range over which :func:`background_envelope` *interpolates*.

    Outside it the envelope is extrapolated from the two nearest knots, so a
    line standing there has its prominence measured over a background level
    nobody observed.  Same window arithmetic as the envelope itself, kept
    beside it so the two cannot drift apart; the span is the first and last
    window *centres*, which is exactly where the knots are.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    if len(tt) < 3:
        return float(tt[0]), float(tt[-1])
    step = float(np.median(np.diff(tt)))
    w = max(int(window_deg / max(step, 1e-12)), 5)
    stride = max(w // 2, 1)
    centres = [float(tt[s:s + w].mean()) for s in range(0, len(tt), stride)
               if len(tt[s:s + w]) >= 3]
    if len(centres) < 2:
        return float(tt[0]), float(tt[-1])
    return centres[0], centres[-1]


def _extrapolate_to_edges(xs: list[float], ys: list[float],
                          lo: float, hi: float) -> tuple[list[float], list[float]]:
    """Anchor a knot at each data edge, linearly from the two nearest knots.

    Only extends — an edge already covered by a knot is left alone, so this is
    a no-op on a pattern whose windows happen to reach the ends.
    """
    if lo < xs[0]:
        slope = (ys[1] - ys[0]) / (xs[1] - xs[0]) if xs[1] != xs[0] else 0.0
        xs = [lo, *xs]
        ys = [ys[0] + slope * (lo - xs[1]), *ys]
    if hi > xs[-1]:
        slope = ((ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
                 if xs[-1] != xs[-2] else 0.0)
        ys = [*ys, ys[-1] + slope * (hi - xs[-1])]
        xs = [*xs, hi]
    return xs, ys


def _median_steps_per_fwhm(net: np.ndarray, sigma: np.ndarray
                           ) -> tuple[float | None, int]:
    """Median channels across the half-height width of ``net``'s peaks.

    ``scipy.signal.peak_widths`` returns the width in **samples**, which is
    already the quantity §2 asks for — "steps across the top of each peak" —
    with no conversion and no assumption that the 2θ grid is uniform.  It
    measures at half the peak's *prominence*, so for an isolated peak on a
    removed background this is the FWHM, and for one shoulder of an overlapped
    pair it is the width above the saddle, which is the part of that peak the
    steps actually resolve.

    Peaks are selected here rather than taken from :func:`diagnose`'s census
    because the two need different things: a peak *count* wants every line the
    pattern shows, while a peak *width* wants only lines that are resolved —
    hence :data:`SAMPLING_PROMINENCE_SIGMA`, without which the measurement
    reads the noise on a strong peak's own top.

    The median rather than the mean: one clipped width from a peak sitting on
    a neighbour's flank should not move the answer, and the guideline is about
    the pattern rather than about its worst line.
    """
    z = np.where(net > 0, net, 0.0) / sigma
    idx, _ = find_peaks(z, height=5.0, distance=3,
                        prominence=SAMPLING_PROMINENCE_SIGMA)
    if not len(idx):
        return None, 0
    with warnings.catch_warnings():
        # scipy warns that some peak has zero width or zero prominence, which
        # is exactly the case dropped on the next line — the filter *is* the
        # handling, so the warning is noise rather than news.  Matched on the
        # message because ``PeakPropertyWarning`` is not exported from
        # ``scipy.signal`` (checked on 1.18): a private import would be the
        # more fragile half.  Both wordings, because scipy raises the width one
        # on a synthetic pattern and the prominence one on real 11-BM data.
        warnings.filterwarnings(
            "ignore", message=r"some peaks have a (width|prominence) of 0")
        widths = peak_widths(np.maximum(net, 0.0), idx, rel_height=0.5)[0]
    usable = widths[np.isfinite(widths) & (widths > 0.0)]
    if not len(usable):
        return None, 0
    return float(np.median(usable)), int(len(usable))


def sampling_steps_per_fwhm(two_theta: np.ndarray, y: np.ndarray,
                            sigma: np.ndarray | None = None
                            ) -> tuple[float | None, int]:
    """``(steps per FWHM, peaks measured)`` for a pattern — the one authority.

    McCusker et al. (1999) §2 leads with this because undersampling is a
    data-collection error that no refinement can repair: at fewer than
    :data:`STEPS_PER_FWHM_MIN` steps across a peak, the integrated intensity of
    that reflection was never measured, whatever is done to the model
    afterwards.

    Model-free, like everything else in this module — the peaks are found on
    the pattern's own net signal over a rolling low-quantile envelope, never
    from a reflection list.  Two callers share it so the number cannot come
    out twice differently: :func:`diagnose`, which reports it before any
    refinement, and ``refine``, which reports it on the **fitted** channels and
    raises ``PATTERN_UNDERSAMPLED`` from it.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    counts = np.asarray(y, dtype=np.float64)
    if len(tt) < 3:
        return None, 0
    sig = (np.sqrt(np.maximum(counts, 1.0)) if sigma is None
           else np.asarray(sigma, dtype=np.float64))
    return _median_steps_per_fwhm(counts - background_envelope(tt, counts), sig)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive ``(start, end)`` index pairs of the True runs in ``mask``."""
    padded = np.concatenate(([False], mask.astype(bool), [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(a), int(b) - 1) for a, b in zip(edges[::2], edges[1::2])]


def _finite_median(values: np.ndarray) -> float | None:
    """Median over the finite entries, or ``None`` when there are none."""
    usable = values[np.isfinite(values)]
    return float(np.median(usable)) if len(usable) else None


def signal_cutoffs(
    two_theta: np.ndarray, y: np.ndarray, sigma: np.ndarray | None = None, *,
    cutoff_fraction: float = CUTOFF_FRACTION,
    onset_fraction: float = CUTOFF_ONSET_FRACTION,
    min_deg: float = CUTOFF_MIN_DEG,
    smooth_deg: float = CUTOFF_SMOOTH_DEG,
    plateau_deg: float = CUTOFF_PLATEAU_DEG,
    interior_fraction: float = CUTOFF_INTERIOR_FRACTION,
) -> list[SignalCutoff]:
    """Ends of the range where the pattern's level collapsed and stayed down —
    channels the instrument was not seeing the sample through.

    Detector active area running out, a beamstop or its halo, sample-environment
    shielding: whatever the cause, these channels carry no diffraction
    information and **must be excluded rather than fitted**.  This reports them
    and applies nothing; the range is the caller's decision.

    **The evidence.**  ILL D20 constant-wavelength neutron, λ = 2.422 Å, in-situ
    SrFeO₃, 1540 points over 0.034-153.934° at 0.1°, σ from the file
    (``306774_SrFeO3_801_N2_10minScan.xye``; interior median level 1.19e8).  The
    two ends are different shapes, which is why one rule has to describe both:

    * **Trailing — a cliff, then a floor.**  110 % of the interior level at
      142.43°, 91 % at 142.83°, 62 % at 143.23°, 24 % at 144.03°, 3.5 % at
      145.03°, then flat at 2.0-3.5 % for the remaining 8.7° to 153.93°.  A
      factor of ≈45 in 2.3°, and past it nothing.
    * **Leading — a graded degradation.**  23 % at 0.03° (the direct-beam
      shoulder), 4.9 % on a shadowed floor over 1.8-3.6°, a *bump* peaking near
      4.6° at 14 % — at λ = 2.422 Å that is d ≈ 30 Å, so it is not sample
      diffraction — then a monotone climb through 32 % at 8.03° and 60 % at
      20.03°, reaching the interior level only around 28°.

    So the two ends carry different arguments, and only the first is "there is
    nothing here".  At the low end there *is* structure; it is a beamstop halo
    and air scatter rather than the specimen, measured at 3-5× the interior's
    fractional error, and fitting a background through it means describing
    non-specimen structure at poor precision.  Both are reasons to exclude, and
    they are not the same reason.

    **σ is not the story.**  σ²/y holds at 19 600-21 100 (±3 %) straight through
    both transitions, so the file's σ is honest and this is not a variance or
    weighting problem — it is a region with no information in it.  Do not read a
    :class:`SignalCutoff` as a :class:`CoverageRegion` or merge the two
    measures: that one counts detectors, this one counts photons.  The precision
    penalty a caller reads (σ/y: 5.9 % at 2.03°, 2.3 % at 8.03°, 1.29 % in the
    interior, 7.3 % at 145.43°, 9.1 % at 148.13°) is a *consequence* of the
    level and is reported as :attr:`SignalCutoff.relative_error_ratio`, derived.

    **Why exclusion and not a more flexible background.**  A Chebyshev or a
    P-spline asked to span a factor-45 cliff has no such shape available: it
    either rings across the whole pattern or splits the difference, and both
    distort the background *under the real peaks*.  That is CLAUDE.md's
    "background flexibility is a correctness question, not a cosmetic one" one
    step earlier — before the background model is chosen, not after it has been
    asked to do something it cannot.

    **And it is read before the other diagnostics, because it corrupts them.**
    Measured on that file, :func:`diagnose` over the full range against the
    TOPAS 8-142° window: ``amorphous_hump_score`` 0.2549 against 0.1380 (1.85×
    inflated by the dead tail), ``air_scatter_gain`` 0.0027 against 0.1433 (the
    real low-angle rise **masked entirely**, 52× understated, because the
    envelope's 1/x column is spent on the leading collapse instead), and
    ``baseline_lambda`` 10⁴ against 10⁶ (the arPLS stiffness selection moved by
    two decades).

    **The method**, and every constant it uses carries its own measurement:

    1. ``lvl`` — a rolling median of ``y`` over :data:`CUTOFF_SMOOTH_DEG`.
    2. ``interior`` — the median of ``lvl`` over the central
       :data:`CUTOFF_INTERIOR_FRACTION` of the range.
    3. A candidate run is ``lvl < cutoff_fraction · interior``, extended outward
       through channels still below the onset level (below), and it must **reach
       the first or last channel** — that is what makes it a cutoff rather than
       an interior gap, and the extension is what lets a first channel sitting a
       hair above the threshold belong to the collapse behind it (measured: two
       of the three D20 files start at 0.226 and 0.259 of interior against a
       0.25 threshold, and the same region follows both).
    4. It must span at least ``min_deg``, or it is a dip and not an instrument.
    5. The **local plateau** is the median of ``lvl`` over the
       :data:`CUTOFF_PLATEAU_DEG` just inside the run; walking inward from the
       run's edge, the first channel back at ``onset_fraction`` × that plateau
       is the boundary reported.  The walk cannot run away: half of the plateau
       window is at or above the plateau by construction, so it stops inside it.

    **A pattern that is entirely below the threshold cannot happen, and that is
    deliberate.**  The threshold is a fraction of the pattern's *own* interior
    median, so at least half the central portion is by construction at or above
    it; there is no input for which this returns "the whole pattern is dead".
    The cost is the honest one: a pattern whose collapse consumed the middle too
    drags the interior level down with it and comes back **empty**.  Silence
    where the evidence is gone, never a claim over the whole range.

    Degenerate inputs return an empty list rather than raising: a pattern too
    short to hold an interior and a collapse, an all-zero pattern (nothing to be
    a fraction of — a dead *pattern* is the reader's problem, not this measure's),
    and one with no finite channel at all.  A non-finite channel elsewhere is
    filled from its finite neighbours before smoothing, so it neither opens a
    run nor closes one: a channel that says nothing must not be heard saying
    something, in either direction.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    counts = np.asarray(y, dtype=np.float64)
    finite = np.isfinite(counts)
    n = len(tt)
    if n < 4 or not finite.any():
        return []
    steps = np.diff(tt)
    steps = steps[np.isfinite(steps) & (steps > 0.0)]
    if not len(steps):
        return []
    step = float(np.median(steps))
    width = max(int(smooth_deg / step), 3)
    # A pattern shorter than three smoothing windows has no interior to compare
    # an edge against — the measurement is a comparison, so too few channels is
    # "not measurable" and not "no cutoff".  Both read as an empty list; the
    # caller that needs the difference has ``n_points``.
    if n < 3 * width:
        return []
    # A non-finite channel is filled from its finite neighbours, which is the
    # level it would have carried had it said anything, so it neither opens a
    # run nor closes one.  (:func:`counting_coverage` fills with its plateau for
    # the same reason: the neutral value of a *ratio* is 1, the neutral value of
    # a *level* is the level beside it.  Filling with a global median instead
    # would put a live channel at a dead edge and hide the cutoff behind it.)
    filled = np.interp(tt, tt[finite], counts[finite])
    lvl = median_filter(filled, size=width, mode="nearest")
    margin = int(n * (1.0 - interior_fraction) / 2.0)
    interior = float(np.median(lvl[margin:n - margin]))
    if not interior > 0.0:
        return []
    plateau_width = max(int(plateau_deg / step), 3)

    cutoffs: list[SignalCutoff] = []
    rel = rel_interior = None
    if sigma is not None:
        with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
            rel = np.asarray(sigma, dtype=np.float64) / np.maximum(filled, 1.0)
        rel_interior = _finite_median(rel[margin:n - margin])
        if not rel_interior:
            rel = None      # σ that is not measurable here derives nothing
    for lo, hi in _runs(lvl < cutoff_fraction * interior):
        # Unreachable while ``interior`` is the pattern's own median (see the
        # docstring), and cheap to say out loud: a run over every channel is a
        # statement about the whole pattern, which this measure never makes.
        if lo == 0 and hi == n - 1:
            continue
        # Each run is tried as both edges; an interior one answers to neither,
        # and no run can answer to both without covering the middle.  ``inward``
        # is the direction from the collapse towards the live pattern.
        for edge, inner, outer, inward in (("low", hi, lo, 1), ("high", lo, hi, -1)):
            window = (lvl[inner + 1:inner + 1 + plateau_width] if inward > 0
                      else lvl[max(inner - plateau_width, 0):inner])
            if not len(window):
                continue
            onset = onset_fraction * float(np.median(window))
            k = outer
            while 0 < k < n - 1 and lvl[k - inward] < onset:
                k -= inward
            if k != (0 if inward > 0 else n - 1):
                continue                      # an interior gap, not a cutoff
            if abs(tt[inner] - tt[k]) < min_deg:
                continue                      # a dip in the first channels
            boundary = inner
            while 0 <= boundary + inward < n and lvl[boundary] < onset:
                boundary += inward
            # The floor is measured over the channels that are actually at it,
            # never over the transition the outward extension picked up.
            floor = float(np.median(lvl[lo:hi + 1]) / interior)
            here = None if rel is None else _finite_median(rel[lo:hi + 1])
            cutoffs.append(SignalCutoff(
                edge=edge, two_theta=float(tt[boundary]), floor_fraction=floor,
                n_channels=int(boundary if inward > 0 else n - 1 - boundary),
                relative_error_ratio=(None if here is None
                                      else here / rel_interior)))
    # Two runs at one edge are one collapse with a bump in it — the outward
    # extension has already crossed a stretch that never got back to level — so
    # the usable range starts after the *last* of them and the innermost
    # boundary is the answer.  At most one cutoff per edge, low first.
    return [max((c for c in cutoffs if c.edge == edge),
                key=lambda c: c.n_channels)
            for edge in ("low", "high") if any(c.edge == edge for c in cutoffs)]


def counting_coverage(
    two_theta: np.ndarray, y: np.ndarray, sigma: np.ndarray | None, *,
    threshold: float = COVERAGE_INFLATION_THRESHOLD,
    smooth_deg: float = COVERAGE_SMOOTH_DEG,
    min_channels: int | None = None,
) -> tuple[list[CoverageRegion], float | None]:
    """``(regions, plateau)`` — where this pattern's σ implies fewer independent
    observations per channel than the bulk of the scan does.

    The statistic is the **variance inflation** v = σ²/max(y, 1), which is 1 for
    pure Poisson counting and proportional to 1/n_eff for a channel averaged over
    n_eff independent observations.  Its bulk level (``plateau``, the median over
    the middle half of the range) is the reference, and a region is a run of
    channels whose smoothed v/plateau exceeds ``threshold``.  Nothing here looks
    at the intensities except through that ratio: no baseline, no peak list, no
    model.

    **Empty when σ was not measured**, signalled by ``sigma=None`` — the spelling
    :func:`sampling_steps_per_fwhm` already uses, and the fact
    :meth:`PatternData.sig` and ``DataRef.has_sigma`` are the authorities for
    (CLAUDE.md, Weights).  Under the Poisson fallback σ = √max(y, 1) the ratio is
    *identically* 1 by construction, so the measure carries no information at
    all; an answer computed from it would be an answer about the fallback rather
    than about the experiment, and ``plateau`` comes back ``None`` to say so.
    Handing the fallback array in explicitly is therefore also empty, but for the
    weaker reason that a constant ratio crosses no threshold.

    **What a region means.** On an instrument with a bank of detectors on a
    circle, the number contributing to a given 2θ falls off at both ends of the
    range, and v ∝ 1/n_eff counts them.  Measured on two NIST BT-1
    constant-wavelength neutron patterns (``Al2O3023.xye`` and ``CrWO6003.xye``,
    3.00-166.25° at 0.05°, 3266 points, σ from the file, plateau v = 0.837 and
    0.826): both show the same ladder — ≈5× below ≈8°, ≈2.2-2.6× from 8° to
    ≈15°, tapering to 1× by ≈55°, 1× through the middle, and a step back to
    ≈2.2× within one channel at 161.30°, held to the end of the scan.  The levels
    are *quantised* because detectors are integers, which is what makes a step
    a step rather than a gradual falloff, and they are not monotonic in 2θ
    (Al2O3023 sits at ≈4× over 11.3-13.0°, between two ≈2.2× stretches).
    Neither pattern's plateau contains a region at all.

    **What it is for, and what it is not.** It reports that the pattern's
    statistical weight is not uniform across its range — a fact about the
    experiment's coverage, not about the specimen — and it is the model-free
    confirmation that a file's σ column is real and structured rather than
    fabricated, since a fabricated or fallback σ cannot show this at all.  It is
    *not* an argument for trimming the range: if σ is right, weighted least
    squares already weights those channels correctly, which is what σ is for.
    Where it disagrees with a hand-chosen fit range that is information about the
    range, in both directions and with no recommendation attached.

    **One caveat, unhandled on purpose.** v also rises where the *intensity*
    collapses — a scan or a detector that stops leaves near-empty channels with a
    finite σ, and max(y, 1) in the denominator then makes v large for a reason
    that has nothing to do with detector count.  This function cannot tell the
    two apart from σ alone and does not try; a region reported at the very end of
    a pattern whose counts fall to nothing there is that other phenomenon.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    if sigma is None or len(tt) < 4:
        return [], None
    counts = np.asarray(y, dtype=np.float64)
    sig = np.asarray(sigma, dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        v = sig ** 2 / np.maximum(counts, 1.0)
    finite = np.isfinite(v)

    n = len(tt)
    middle = v[n // 4:n - n // 4]
    usable = middle[np.isfinite(middle) & (middle > 0.0)]
    if not len(usable):
        return [], None
    # positive and finite by that filter, so the division below is safe
    plateau = float(np.median(usable))

    # A non-finite channel makes no claim rather than a false one: it is set to
    # the plateau, so it neither starts a region nor breaks the median filter.
    ratio = np.where(finite, v, plateau) / plateau

    steps = np.diff(tt)
    steps = steps[np.isfinite(steps) & (steps > 0.0)]
    if not len(steps):
        return [], plateau
    # The smoothing window doubles as the minimum region width and as the widest
    # gap that gets closed, both from one sentence: the statistic cannot resolve a
    # feature narrower than the window it was smoothed over, so a shorter run is
    # not evidence and a shorter gap is not a boundary.  One rule, no second
    # tunable — ``min_channels`` overrides only the first, since the second is a
    # property of the smoother rather than a choice about what counts.
    width = max(int(smooth_deg / float(np.median(steps))), 5)
    floor = width if min_channels is None else max(int(min_channels), 1)
    smoothed = median_filter(ratio, size=width, mode="nearest")

    merged: list[tuple[int, int]] = []
    for lo, hi in _runs(smoothed > threshold):
        if merged and lo - merged[-1][1] - 1 < width:
            merged[-1] = (merged[-1][0], hi)
        else:
            merged.append((lo, hi))

    regions: list[CoverageRegion] = []
    for lo, hi in merged:
        if hi - lo + 1 < floor:
            continue
        edge = "low" if lo == 0 else "high" if hi == n - 1 else "interior"
        regions.append(CoverageRegion(
            two_theta_min=float(tt[lo]), two_theta_max=float(tt[hi]),
            # the raw ratio, not the smoothed one: smoothing is what found the
            # boundaries, and a median over the region needs no help from it
            inflation=float(np.median(ratio[lo:hi + 1])),
            n_channels=int(hi - lo + 1), edge=edge))
    return regions, plateau


def diagnose(data: PatternData, *, wavelength: float | None = None,
             baseline_lambda: float | None = None) -> PatternDiagnostics:
    """Compute :class:`PatternDiagnostics` for a raw pattern."""
    from .select import select_arpls_lambda

    mask = data.in_range_mask()
    tt = data.tt()[mask]
    y = data.y()[mask]
    sigma = data.sig()[mask]
    span = float(tt[-1] - tt[0])

    # First, and computed first so the order is visible: everything below is
    # measured over the whole supplied range, and a dead end moves those
    # numbers by up to two decades (:class:`PatternDiagnostics` has the table).
    # σ rides along only to derive the precision penalty, and only where it was
    # *measured* — under the Poisson fallback that ratio is a function of the
    # level it was derived from and would say nothing.
    cutoffs = signal_cutoffs(tt, y, sigma if data.sigma is not None else None)

    env = background_envelope(tt, y)
    net = y - env
    med_env = float(np.median(env))

    peak_channels = net > 3.0 * sigma
    idx, _ = find_peaks(np.where(net > 0, net, 0.0) / sigma, height=5.0, distance=3)

    # nested envelope fits: cubic, then cubic + 1/(2θ) air-scatter column
    design = chebyshev_design_matrix(tt, 4, float(tt[0]), float(tt[-1]))
    coef, *_ = np.linalg.lstsq(design.T, env, rcond=None)
    r_cubic = env - coef @ design
    design_air = np.vstack([design, 1.0 / np.maximum(tt, 1e-3)])
    coef_air, *_ = np.linalg.lstsq(design_air.T, env, rcond=None)
    r_air = env - coef_air @ design_air
    rss_cubic = float(r_cubic @ r_cubic)
    air_gain = float(1.0 - (r_air @ r_air) / rss_cubic) if rss_cubic > 0 else 0.0
    hump = float(np.sqrt(np.mean(r_air ** 2)) / max(med_env, 1e-12))

    flags: list[ContaminationFlag] = []
    if wavelength is not None and len(idx):
        flags = _contamination_flags(tt, net, sigma, idx, wavelength)

    lam = (select_arpls_lambda(data).selected if baseline_lambda is None
           else baseline_lambda)

    # the same envelope and net signal this function already computed, so the
    # sampling number is measured on exactly the pattern reported above
    steps, n_measured = _median_steps_per_fwhm(net, sigma)

    # ``data.sigma is not None`` is the σ-measured test at this rank — the
    # PatternData-level peer of ``DataRef.has_sigma``, and the same branch
    # ``sig()`` itself takes.  Passing ``sigma`` unconditionally would hand the
    # Poisson fallback to a measure that reads it as a flat answer.
    coverage, plateau = counting_coverage(
        tt, y, sigma if data.sigma is not None else None)

    return PatternDiagnostics(
        n_points=len(tt),
        two_theta_min=float(tt[0]), two_theta_max=float(tt[-1]),
        baseline_lambda=float(lam),
        noise_sigma_median=float(np.median(sigma)),
        peak_fraction=float(np.mean(peak_channels)),
        n_peaks=int(len(idx)),
        peak_density_per_deg=float(len(idx) / max(span, 1e-12)),
        signal_to_background=float(np.percentile(net, 99.9) / max(med_env, 1e-12)),
        amorphous_hump_score=hump,
        air_scatter_gain=max(air_gain, 0.0),
        steps_per_fwhm=steps,
        n_peaks_measured=n_measured,
        contamination=flags,
        coverage_plateau=plateau,
        coverage_regions=coverage,
        signal_cutoffs=cutoffs,
    )


def identify_anode(wavelength: float) -> str | None:
    """The anode whose Kα1 this wavelength is, or ``None``.

    ``None`` means "not a tabulated characteristic wavelength" — synchrotron,
    an anode we do not carry, or a Kα2-referenced pattern.  Callers must treat
    it as *not checked*, never as *clean*.
    """
    from ..schemas.instrument import _KA_DOUBLETS

    for name, (ka1, _) in _KA_DOUBLETS.items():
        if abs(wavelength - ka1) <= _ANODE_MATCH_TOL:
            return name
    return None


def contamination_flags_from_peaks(
    two_theta: np.ndarray, intensity: np.ndarray,
    two_theta_esd: np.ndarray | None, wavelength: float, *,
    intensity_esd: np.ndarray | None = None,
    tt_range: tuple[float, float] | None = None,
    tol_deg: float = GHOST_TOL_DEG, k_sigma: float = GHOST_MATCH_K,
) -> list[ContaminationFlag]:
    """Ghost lines at the Kβ / W Lα positions of the strongest lines in a
    **peak list** — the one implementation of the ghost rule in this package.

    Same d-spacing, different λ:  sinθ_ghost = sinθ_parent · λ_ghost/λ_parent.
    A candidate must be a *weaker* line near the predicted position, with
    ghost/parent intensity inside :data:`GHOST_RATIO_RANGE`.

    Which ghosts are looked for follows the anode: Kβ is anode-specific, W Lα1
    is filament-derived and so applies to any of them.  An unrecognised
    wavelength yields no flags, which is a *silence*, not a clean bill — the
    caller sees the same empty list either way, and that asymmetry is why
    every anode this package can build a source for has a Kβ entry.

    Two arguments are optional because the two callers know different things.
    ``two_theta_esd`` is the per-line **position** esd; when given, the matching
    window becomes ``max(tol_deg, k_sigma·√(σ_ghost² + σ_parent²))`` — see
    :data:`GHOST_TOL_DEG` for why σ can only widen it.  ``intensity_esd``
    switches on a ``intensity > 5σ`` significance test, which a fitted peak list
    does not need (its lines cleared a σ-normalised detection threshold already)
    but a raw channel-index census does.  ``intensity`` should be an
    *integrated* intensity where one exists; net height is a fallback that
    biases the ratio test by the ghost/parent width ratio.
    """
    anode = identify_anode(wavelength)
    if anode is None:
        return []
    tt = np.asarray(two_theta, dtype=np.float64)
    inten = np.asarray(intensity, dtype=np.float64)
    if not len(tt):
        return []
    lo, hi = (float(tt.min()), float(tt.max())) if tt_range is None else tt_range
    esd = None if two_theta_esd is None else np.asarray(two_theta_esd, dtype=np.float64)
    r_lo, r_hi = GHOST_RATIO_RANGE
    strongest = np.argsort(inten)[::-1][:GHOST_N_PARENTS]
    flags: list[ContaminationFlag] = []
    for kind, lam_ghost in (("kbeta", _KBETA[anode]), ("tungsten_la", _W_LA1)):
        ratio = lam_ghost / wavelength
        for ip in strongest:
            s = np.sin(np.radians(tt[ip] / 2.0)) * ratio
            if s >= 1.0:
                continue
            tt_ghost = 2.0 * np.degrees(np.arcsin(s))
            if not (lo <= tt_ghost <= hi):
                continue
            if esd is None:
                window = np.full(len(tt), tol_deg)
            else:
                window = np.maximum(
                    tol_deg, k_sigma * np.sqrt(esd ** 2 + esd[ip] ** 2))
            near = np.flatnonzero(np.abs(tt - tt_ghost) < window)
            for ig in near:
                r = float(inten[ig] / max(inten[ip], 1e-12))
                if not (r_lo < r < r_hi):
                    continue
                if (intensity_esd is not None
                        and inten[ig] <= 5.0 * intensity_esd[ig]):
                    continue
                flags.append(ContaminationFlag(
                    kind=kind, two_theta=float(tt[ig]),
                    parent_two_theta=float(tt[ip]), intensity_ratio=r))
    return flags


def _contamination_flags(tt: np.ndarray, net: np.ndarray, sigma: np.ndarray,
                         peak_idx: np.ndarray, wavelength: float,
                         *, tol_deg: float = GHOST_TOL_DEG
                         ) -> list[ContaminationFlag]:
    """Channel-index view of :func:`contamination_flags_from_peaks`.

    This is the pre-WP-1018 surface, kept because :func:`diagnose` works from
    ``find_peaks`` channel indices and has neither a fitted position esd nor an
    integrated intensity: it passes net height for both the ranking and the
    ratio test, and no σ(2θ), so the window is the flat ``tol_deg``.
    """
    return contamination_flags_from_peaks(
        tt[peak_idx], net[peak_idx], None, wavelength,
        intensity_esd=sigma[peak_idx], tt_range=(float(tt[0]), float(tt[-1])),
        tol_deg=tol_deg)
