"""Indexing schemas — the fitted peak list an indexer consumes.

The contract this module exists to establish is **per-line σ instead of a
global tolerance knob**.  Every indexing program in the literature takes a
single "position tolerance" and applies it to every line; a fitted peak list
carries σ(2θ) per line, propagated into σ(Q), so a strong sharp reflection and
a weak shoulder are weighted by what they actually determine.  That is the same
move the refinement side made with the file's esd column (CLAUDE.md, Weights).

Thresholds are pinned here and versioned by
:data:`INDEXING_THRESHOLDS_VERSION`, following ``report/schemas.py``: an agent
reading a peak list can reproduce the decisions that produced it.

**Q, not d, and not 2θ.**  ``Q = 1/d²`` is linear in the reciprocal metric
(:func:`pxrdref.crystallography.inv_d_squared`), which is what makes cell
refinement a linear least-squares problem downstream, so Q is propagated here
once rather than re-derived by each engine.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field, model_validator

from .common import Base, Diagnostic

#: 1.0 (WP-1018): first release of the peak-list contract.
INDEXING_THRESHOLDS_VERSION = "1.0"

# ----------------------------------------------------------------------
# Detection
# ----------------------------------------------------------------------
#: Net height a candidate must reach, in units of the channel's own σ.  It is
#: **σ-normalised and never relative to the global maximum**: the prototype
#: indexer used ``prominence = net.max()·0.01``, which on a pattern that is one
#: enormous reflection plus a dozen weak lines (measured on
#: ``KD1-2_5_NaCoO2``, tag ``guillemot-study``) suppresses everything but the
#: giant.  A σ-normalised threshold has no coupling between unrelated parts of
#: the pattern.  5.0 matches the existing pattern-diagnostics census.
PEAK_MIN_HEIGHT_SIGMA = 5.0
#: Topographic prominence a candidate must reach, in units of the local σ.
#: Lower than the height floor because prominence is measured against the
#: neighbouring saddle rather than the baseline, and a genuine shoulder on a
#: strong line has small prominence by construction.
PEAK_MIN_PROMINENCE_SIGMA = 3.0
#: Detection separation floor as a fraction of the *narrowest* predicted FWHM
#: in range.  Deliberately smaller than
#: ``model.forward.PAWLEY_OVERLAP_FWHM_FRAC`` (0.5, the point past which least
#: squares cannot apportion intensity): detection should *offer* a shoulder at
#: 0.3 FWHM as a seed and let grouping plus the ΔBIC test decide whether the
#: component survives, rather than never seeing it.
PEAK_DETECT_SEPARATION_FWHM_FRAC = 0.25
#: How many of the most prominent detections the width census averages over.
#: **Rank first, then measure** (WP-1028, measured on third-party lab data): a
#: median FWHM over *all* detections above a prominence floor read 0.071° on a
#: noisy 0.01°-step pattern whose real lines are 0.389°, because smoothing
#: ripples survive the floor as weak maxima and drag the median down by a factor
#: of five.  The median of the twelve most prominent detections recovers 0.389°.
PEAK_WIDTH_CENSUS_N = 12

# ----------------------------------------------------------------------
# Per-group profile fitting
# ----------------------------------------------------------------------
#: A component's position is bounded to ±this fraction of its seed FWHM.  The
#: analogue of Layer 1's ``VALIDITY_RADIUS_FWHM = 0.4``, and the reasoning is
#: the same one rank down: a fit that wants to move a component further than
#: half a FWHM is reporting a *detection* failure, not a small offset, and
#: should come back at its bound with a flag rather than converge somewhere
#: unrelated.
PEAK_POSITION_BOUND_FWHM = 0.5
#: Multiplicative bounds on each fitted component FWHM relative to its seed.
#: The lower bound is what keeps Γ strictly positive — the profile is
#: (1/Γ)·f(x/Γ) — so no softplus reparameterisation is needed on top of the
#: bounded trust-region solver.
PEAK_WIDTH_BOUND_FACTORS = (0.2, 5.0)
#: Re-seeding (adding a component to a group whose residual demands one) is an
#: explicit extra pass, capped at this many.  The component count per group is
#: frozen *before* each fit and never changes inside it: a fitter that adds or
#: drops a component mid-solve has a discontinuous residual, which is the
#: frozen-per-stage invariant (CLAUDE.md) one level down.
PEAK_MAX_RESEED_PASSES = 2
#: ΔBIC an added component must clear to be kept (``report.layer2.delta_bic``,
#: which already charges ``n_added·ln N``).  6.0 rather than 0 is "strong"
#: evidence on the Kass & Raftery (1995) scale: peak fitting is unusually prone
#: to spending a component on noise, and a spurious component does not merely
#: add a line — it displaces the position of the real one it splits.
PEAK_KEEP_COMPONENT_MIN_DELTA_BIC = 6.0
#: |t| of the residual's odd-cubic projection above which a peak is flagged
#: asymmetric-beyond-the-model.  The *odd-cubic* direction, not the odd-linear
#: one, because a free position already absorbs the first odd moment exactly —
#: after fitting, the leading detectable signature of unmodelled axial
#: asymmetry is the next odd term.
PEAK_ASYMMETRY_MIN_SIGMA = 4.0

# ----------------------------------------------------------------------
# List level
# ----------------------------------------------------------------------
#: Usable lines below which the list is reported too short to index.  Twenty is
#: not a round number: de Wolff's M₂₀ and Smith & Snyder's F₂₀ are both defined
#: on the first twenty lines, and Smith's (1977) volume envelope is quoted at
#: N = 20, so a shorter list cannot be scored by the figures of merit the
#: engines rank on.
PEAK_MIN_USABLE_LINES = 20
#: σ(2θ) in degrees assumed by :meth:`PeakList.from_positions`, which receives
#: bare positions from a publication or another program.  A typical
#: well-aligned laboratory position precision — but the number is not the point:
#: the point is that it is *assumed*, so every such line carries
#: ``"sigma_assumed"`` and downstream gates must treat the precision as
#: unmeasured rather than quote it.
PEAK_ASSUMED_ESD_DEG = 0.02

#: Flags on a line.  ``ghost_kbeta`` / ``ghost_tungsten`` — a contamination
#: line, flagged and **excluded, never subtracted** (Rachinger stripping
#: redistributes the noise and biases what is left; see
#: :mod:`pxrdref.indexing.peakfit`).  ``excluded`` — the caller removed it.
#: ``fit_failed`` — the group solve did not converge, so position and σ are the
#: seed, not a measurement.  ``sigma_assumed`` — σ(2θ) was supplied, not fitted.
#: ``unresolved_shoulder`` — a component kept in a group where it never
#: separated from its neighbour by half a FWHM.  ``position_at_bound`` — the fit
#: pushed to :data:`PEAK_POSITION_BOUND_FWHM`, i.e. detection put the seed in
#: the wrong place.  ``asymmetry_unmodelled`` — see
#: :data:`PEAK_ASYMMETRY_MIN_SIGMA`.
PeakFlag = Literal[
    "ghost_kbeta",
    "ghost_tungsten",
    "excluded",
    "fit_failed",
    "sigma_assumed",
    "unresolved_shoulder",
    "position_at_bound",
    "asymmetry_unmodelled",
]

#: Flags that take a line out of :meth:`PeakList.usable`.  ``sigma_assumed``
#: and ``unresolved_shoulder`` are deliberately absent: those lines are still
#: evidence, just less precise evidence, and their σ already says so.  Dropping
#: them would discard the input the bethanechol benchmark arrives as.
PEAK_UNUSABLE_FLAGS: frozenset[str] = frozenset(
    {"ghost_kbeta", "ghost_tungsten", "excluded", "fit_failed"})


def q_of_two_theta(two_theta_deg: np.ndarray, wavelength: float) -> np.ndarray:
    """Q = 1/d² = 4·sin²θ/λ² (Å⁻²) from 2θ in degrees."""
    tt = np.asarray(two_theta_deg, dtype=np.float64)
    return 4.0 * np.sin(np.radians(0.5 * tt)) ** 2 / wavelength ** 2


def q_esd_of_two_theta(two_theta_deg: np.ndarray, two_theta_esd: np.ndarray,
                       wavelength: float) -> np.ndarray:
    """σ(Q) from σ(2θ), by the exact derivative of :func:`q_of_two_theta`.

        dQ/d(2θ°) = (π/90)·sin(2θ)/λ²

    Note the constant: differentiating 4sin²θ/λ² with respect to 2θ *in degrees*
    gives 2·(π/180)·sin(2θ)/λ², i.e. π/90 — half of it is the θ = (2θ)/2 chain
    and the other half is the degree conversion, and it is easy to apply only
    one of the two.  Checked against a central difference in
    ``tests/test_peak_picking.py``.
    """
    tt = np.asarray(two_theta_deg, dtype=np.float64)
    esd = np.asarray(two_theta_esd, dtype=np.float64)
    return (np.pi / 90.0) * np.abs(np.sin(np.radians(tt))) / wavelength ** 2 * esd


class ObservedPeak(Base):
    """One measured line: a fitted position with its esd, width, shape, area.

    ``q``/``q_esd`` are derived from ``two_theta`` and the owning
    :class:`PeakList`'s wavelength; the list validates that they agree, so a
    consumer may use either without checking which is authoritative.

    ``fwhm`` and ``eta`` are the *group's* shared shape, not per-component
    values: within a group (a fraction of a degree) the widths are not
    separately identifiable, and pretending otherwise is what lets a doublet fit
    absorb an unresolved neighbour.
    """

    two_theta: float               # ° 2θ of the **Kα1** (primary-line) component
    two_theta_esd: float           # ° 2θ, carrying the √max(χ²_red,1) inflation
    intensity: float               # integrated area of the primary line
    intensity_esd: float
    q: float                       # Å⁻², = 1/d²
    q_esd: float
    fwhm: float                    # ° 2θ, the group's combined Γ
    eta: float                     # pseudo-Voigt mixing (0 = Gaussian)
    group: int                     # index of the fitted group this came from
    n_in_group: int                # components fitted simultaneously with it
    chi2_red: float                # reduced χ² of that group's fit
    flags: list[PeakFlag] = Field(default_factory=list)

    @property
    def d(self) -> float:
        """d-spacing (Å)."""
        return float(self.q ** -0.5)

    @property
    def usable(self) -> bool:
        return not (set(self.flags) & PEAK_UNUSABLE_FLAGS)


class PeakList(Base):
    """Every resolvable line in one pattern, with per-line σ.

    ``source`` distinguishes a list this package *measured* from one it was
    *handed*: ``"fitted"`` means every σ came out of a profile fit,
    ``"positions"`` means positions were supplied and σ was assumed (see
    :data:`PEAK_ASSUMED_ESD_DEG`).  Downstream gates read it rather than
    inferring precision from the numbers.
    """

    peaks: list[ObservedPeak]
    wavelength: float                        # primary emission line, Å
    two_theta_min: float
    two_theta_max: float
    source: Literal["fitted", "positions"] = "fitted"
    thresholds_version: str = INDEXING_THRESHOLDS_VERSION
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    @model_validator(mode="after")
    def _q_matches_two_theta(self) -> "PeakList":
        """Q is derived, so it cannot be allowed to drift from 2θ.

        Cheap (one vectorised pass) and it makes the derived field
        self-guarding: a caller that builds a peak by hand and forgets Q gets an
        error here rather than a silently mis-indexed pattern later.
        """
        if not self.peaks:
            return self
        tt = np.array([p.two_theta for p in self.peaks])
        want = q_of_two_theta(tt, self.wavelength)
        got = np.array([p.q for p in self.peaks])
        bad = np.abs(got - want) > 1e-9 * np.maximum(np.abs(want), 1.0)
        if bad.any():
            k = int(np.flatnonzero(bad)[0])
            raise ValueError(
                f"peak {k} at 2θ = {tt[k]:.4f}° carries q = {float(got[k])!r} "
                f"but 1/d² at λ = {self.wavelength} Å is {float(want[k])!r}; "
                "build peaks with PeakList.from_positions or "
                "indexing.pick_peaks rather than setting q by hand")
        return self

    def usable(self) -> list[ObservedPeak]:
        """Lines fit to index: ghosts, failed fits and caller exclusions out.

        Every screen and every engine runs on this, not on ``peaks`` — the
        excluded lines are kept in the list so a report can say *why* a line was
        dropped, which a filtered-at-source list cannot.
        """
        return [p for p in self.peaks if p.usable]

    def two_theta(self) -> np.ndarray:
        return np.array([p.two_theta for p in self.usable()], dtype=np.float64)

    def two_theta_esd(self) -> np.ndarray:
        return np.array([p.two_theta_esd for p in self.usable()], dtype=np.float64)

    def q(self) -> np.ndarray:
        return np.array([p.q for p in self.usable()], dtype=np.float64)

    def q_esd(self) -> np.ndarray:
        return np.array([p.q_esd for p in self.usable()], dtype=np.float64)

    def intensity(self) -> np.ndarray:
        return np.array([p.intensity for p in self.usable()], dtype=np.float64)

    @classmethod
    def from_positions(cls, two_theta: np.ndarray, wavelength: float, *,
                       intensity: np.ndarray | None = None,
                       two_theta_esd: float | np.ndarray = PEAK_ASSUMED_ESD_DEG,
                       fwhm: float = 0.1,
                       ) -> "PeakList":
        """A peak list from bare positions — a publication, or another program.

        Every line is flagged ``"sigma_assumed"`` and ``source`` is
        ``"positions"``, because an assumed σ is *unmeasured*: it must not be
        quoted as a precision, and a gate that weights lines by 1/σ² is being
        handed a constant rather than information.  Intensities default to equal
        weight, which is what a position-only list actually says.
        """
        tt = np.asarray(two_theta, dtype=np.float64)
        if tt.ndim != 1 or not len(tt):
            raise ValueError("two_theta must be a non-empty 1-D array")
        esd = np.broadcast_to(np.asarray(two_theta_esd, dtype=np.float64), tt.shape)
        inten = (np.ones_like(tt) if intensity is None
                 else np.asarray(intensity, dtype=np.float64))
        q = q_of_two_theta(tt, wavelength)
        q_esd = q_esd_of_two_theta(tt, esd, wavelength)
        order = np.argsort(tt)
        peaks = [
            ObservedPeak(
                two_theta=float(tt[i]), two_theta_esd=float(esd[i]),
                intensity=float(inten[i]), intensity_esd=float("inf"),
                q=float(q[i]), q_esd=float(q_esd[i]),
                fwhm=fwhm, eta=0.5, group=int(k), n_in_group=1,
                chi2_red=float("nan"), flags=["sigma_assumed"])
            for k, i in enumerate(order)
        ]
        return cls(peaks=peaks, wavelength=wavelength,
                   two_theta_min=float(tt.min()), two_theta_max=float(tt.max()),
                   source="positions")
