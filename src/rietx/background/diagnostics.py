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


class ContaminationFlag(Base):
    """A weak peak consistent with a known contamination line of a strong one."""

    kind: str                  # "kbeta" | "tungsten_la"
    two_theta: float           # where the ghost sits
    parent_two_theta: float    # the strong Kα parent reflection
    intensity_ratio: float     # ghost/parent net height


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
