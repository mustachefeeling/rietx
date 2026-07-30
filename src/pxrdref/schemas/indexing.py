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
#: Significance a *curvature* (shoulder) seed must reach, in units of the
#: propagated noise of the second-derivative filter.  Higher than the prominence
#: floor for a multiple-comparison reason, not a physical one: the curvature test
#: is applied at every local dip in the pattern, i.e. of order (2θ range)/FWHM ≈
#: several hundred independent trials, so a 3σ per-trial threshold yields about
#: one false shoulder per pattern *by construction* — measured, one at 31.56° on
#: a three-peak synthetic.  At 5σ the expected count is ~1e-4.  A false line is
#: far worse here than a missed shoulder: it is the "confident wrong singleton"
#: the FitReport gates exist to prevent, one rank down.
PEAK_SHOULDER_MIN_SIGMA = 5.0
#: Detection separation floor as a fraction of the *narrowest* predicted FWHM
#: in range.  Deliberately smaller than
#: ``model.forward.PAWLEY_OVERLAP_FWHM_FRAC`` (0.5, the point past which least
#: squares cannot apportion intensity): detection should *offer* a shoulder at
#: 0.3 FWHM as a seed and let grouping plus the ΔBIC test decide whether the
#: component survives, rather than never seeing it.
PEAK_DETECT_SEPARATION_FWHM_FRAC = 0.25
#: A candidate is an **Kα2 alias** — the same reflection's second emission line,
#: not a line of its own — if it sits within this fraction of a FWHM of the
#: Bragg-predicted Kα2 position of a stronger candidate.  Why this filter has to
#: exist: once a doublet resolves (Δ2θ = 2·tanθ·Δλ/λ exceeds half a FWHM) the Kα2
#: maximum is a separate detection, lands in its own group, and — because each
#: group is fitted independently, with its own full doublet — comes back as a
#: real line with real intensity.  Measured on a synthetic Cu Kα pattern: one
#: spurious line per resolved doublet.  Stripping is not the alternative (see
#: :mod:`pxrdref.indexing.peakfit`); recognising the alias is.
PEAK_ALIAS_TOL_FWHM_FRAC = 0.3
#: Observed height ratio, as multiples of the emission line's own ``weight``,
#: inside which an alias is accepted as such.  Wide on purpose: the ratio equals
#: the weight only for a fully resolved pair, and at partial overlap the apparent
#: height at the Kα2 maximum is inflated by the Kα1 tail.  A *genuine* line that
#: happens to sit at a stronger line's Kα2 position is indistinguishable from an
#: alias in one pattern, so the drop is reported (``PEAK_KALPHA2_ALIAS``) rather
#: than made silently.
PEAK_ALIAS_RATIO_RANGE = (0.25, 4.0)
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
#: Bounds on each fitted **component** FWHM (Γ_G, Γ_L separately), as multiples
#: of the group's seed combined Γ.  The lower one is a *positivity floor*, not a
#: physical constraint, and it is tiny on purpose: a genuinely Lorentzian line
#: has Γ_G → 0 and a genuinely Gaussian one has Γ_L → 0, so a floor at a
#: fraction like 0.2 would forbid both limits.  All it has to do is keep Γ
#: strictly positive, since the profile is (1/Γ)·f(x/Γ) — which is the only thing
#: a softplus reparameterisation was ever buying here, and native trust-region
#: bounds keep the analytic Jacobian in physical units with no chain factor.
PEAK_WIDTH_BOUND_FACTORS = (1e-4, 5.0)
#: Half-width of a group's fitting window, in seed FWHM beyond the outermost
#: seed.  Far narrower than the refinement's ``WINDOW_FWHM_MULT = 30``, and for
#: a different reason: there the whole pattern is modelled and a truncated tail
#: shows up as missing intensity under its neighbours, whereas here each window
#: is fitted alone against a frozen background, so a wide window only buys more
#: baseline error.  Truncation does not bias the reported area — the profile is
#: unit-area and *not* renormalised over the window — it costs precision on the
#: Lorentzian fraction, which is why the window is not narrower still.
PEAK_WINDOW_FWHM_MULT = 4.0
#: Bounds on the global broadening factor that calibrates the instrument width
#: law to the measured width census.  A factor above 1 is ordinary sample
#: broadening; below 1 means the declared instrument is broader than the data,
#: which is a mis-declared instrument rather than physics — allowed, but not
#: without limit, and the range is what stops a pathological census (all
#: shoulders, or one saturated line) from setting every window.
PEAK_WIDTH_SCALE_BOUNDS = (0.5, 50.0)
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
# ----------------------------------------------------------------------
# Data quality (WP-1019)
# ----------------------------------------------------------------------
#: Metric degrees of freedom of the quadratic form Q(hkl) per crystal system —
#: the number of independent entries of {A..F} in
#: ``Q = Ah² + Bk² + Cl² + Dkl + Ehl + Fhk``.  A search cannot be better
#: determined than this: with fewer *usable* lines than DOF the cell is not
#: over-determined at all, and any figure of merit computed on it is fitting
#: noise exactly.  The names are the seven ``sg.crystal_system_str()`` values
#: ``params.vector`` already ties cells by, so the vocabulary is not new.
METRIC_DOF: dict[str, int] = {
    "cubic": 1, "tetragonal": 2, "hexagonal": 2, "trigonal": 2,
    "orthorhombic": 3, "monoclinic": 4, "triclinic": 6,
}
#: Usable lines per metric degree of freedom below which the data are reported
#: as unable to support a search *in that system*.  Five is not a statistical
#: threshold; it is the smallest ratio at which a wrong cell is unlikely to
#: match every line by accident, and it is what makes the abstention system-
#: dependent: 20 lines is 20× over-determined for cubic and 3.3× for triclinic,
#: which is why "enough lines" is not a single number.
MIN_LINES_PER_DOF = 5.0
#: Median σ(Q)/Q above which the position precision is reported as too poor to
#: separate candidate cells.  Read it as a *resolving power*: at 1e-3 two cells
#: differing by 0.1 % in a lattice parameter are indistinguishable, which is the
#: scale at which derivative-lattice ambiguity (Mighell & Santoro 1975) lives.
MAX_RELATIVE_SIGMA_Q = 1e-3
#: The three physical causes of a systematic 2θ shift, in the *same* names
#: ``report/layer2.py``'s ``_POSITION_ACTIONS`` uses, so one physical cause has
#: one name package-wide.  ``tan_theta`` is deliberately **absent**: a tanθ
#: deviation is a *cell* error, not an instrument shift, and offering it here
#: would let the screen "explain" a shift by changing the very answer indexing
#: is about to produce.  WP-1020 refines the cell and the chosen shift together,
#: where the tanθ direction belongs to the cell by construction.
SHIFT_TEMPLATES: tuple[str, ...] = ("constant", "cos_theta", "sin_2theta")
#: Smith (1977) volume envelope, ``V ≈ 0.6·d_N³/(1/N − 0.0052)``, evaluated for
#: **triclinic** at N = 20: 13.39·d₂₀³.  Kept as the two published constants
#: rather than the product, because the formula is used at other N.
SMITH_VOLUME_C1, SMITH_VOLUME_C2 = 0.6, 0.0052

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


class FigureOfMerit(Base):
    """One figure of merit, and **what it cannot see**.

    ``blind_spot`` is not documentation, it is a field: the panel exists because
    every published figure of merit has a failure mode, and a consumer that reads
    a value without its blind spot is one step from the confident wrong singleton
    the FitReport gates exist to prevent.  ``k_sigma`` records the matching window
    the value was computed at, in units of each line's own σ — so a number is
    reproducible from the peak list that produced it.
    """

    name: str
    value: float
    n_lines: int
    n_possible: int
    k_sigma: float
    #: mean |Δ| of the matched lines, in the FoM's own units (Å⁻² for M₂₀, ° for
    #: F_N); −1 when nothing matched, which is *not* zero discrepancy
    mean_discrepancy: float = -1.0
    blind_spot: str = ""


class AmbiguityPartner(Base):
    """A distinct lattice whose calculated line *positions* match this one's.

    Mighell & Santoro (1975): a powder pattern carries only the **length** of the
    reciprocal vector, so distinct lattices can be indistinguishable in it.  This
    is reported, never resolved — and ``discriminating_reflections`` is what makes
    it actionable rather than merely honest: the hkl that would break the tie, with
    the 2θ where a line would have to appear (or be absent) to do so.  The
    structural twin of Layer 2's "extend the fit range".
    """

    cell: tuple[float, float, float, float, float, float]
    #: integer transformation from this candidate's basis to the partner's
    transformation: list[list[int]]
    index: int                      # |det| of the transformation
    system: str
    volume: float
    #: hkl of the partner (or of this cell) whose position differs, and where
    discriminating_reflections: list[tuple[int, int, int]] = Field(
        default_factory=list)
    discriminating_two_theta: list[float] = Field(default_factory=list)


class CellCandidate(Base):
    """One candidate lattice, with everything needed to rank or reject it.

    Deliberately *not* named "solution" and deliberately carrying no "is correct"
    field.  ``found_by`` is the engines that produced it — agreement between
    independent engines is the confidence, the same device as the cross-backend
    Jacobian matrix and ``direction="both"`` — and ``ambiguity`` is populated
    whenever a geometrically indistinguishable partner exists.
    """

    cell: tuple[float, float, float, float, float, float]
    cell_esd: tuple[float, float, float, float, float, float]
    system: str
    centring: str = "P"
    #: absence-free space-group symbol of the *lattice* (holohedry + centring) —
    #: what the FoM denominators count, and the starting point for WP-1025's
    #: extinction-symbol screen.  Not a space group: that is not known yet.
    lattice_group: str = ""
    volume: float = 0.0
    volume_esd: float = 0.0
    #: (A..F), the quadratic-form parameters actually fitted
    af: tuple[float, float, float, float, float, float] = (0.0,) * 6
    n_indexed: int = 0
    n_lines: int = 0
    chi2_red: float = 0.0
    shift_template: str | None = None
    shift_coefficient: float = 0.0
    shift_esd: float = 0.0
    fom: list[FigureOfMerit] = Field(default_factory=list)
    found_by: list[str] = Field(default_factory=list)
    ambiguity: list[AmbiguityPartner] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    def fom_value(self, name: str) -> float | None:
        """One panel member by name, or None — never a KeyError, because which
        members exist depends on what could be computed."""
        for f in self.fom:
            if f.name == name:
                return f.value
        return None


class ShiftTemplateFit(Base):
    """One systematic-shift template fitted **alone** to the deviations.

    ``coefficient`` is in degrees 2θ and means the template's own amplitude:
    δ(θ) = z (``constant``), s·cos θ (``cos_theta``), t·sin 2θ
    (``sin_2theta``).  ``residual_ss`` is the weighted residual sum of squares,
    which is what the separability ratio is computed on — not R², because every
    template scores R² ≈ 0.99 against a clean trend
    (``report/schemas.py``'s ``SEPARABILITY_MIN_SS_RATIO``).
    """

    name: str
    coefficient: float
    stderr: float
    r2: float
    residual_ss: float


class ShiftScreen(Base):
    """Which physical cause a systematic 2θ shift has — or that it has no
    nameable one over the range measured.

    ``best`` always names the template that fits best; ``separable`` says
    whether that name means anything.  The asymmetry is the point: when the
    templates are collinear over the sampled angles the *magnitude* is still
    well determined (all three remove the same amount at those angles, so a cell
    refined against any of them lands in the same place) while the *cause* is
    not, and reporting the cause anyway is the confident-wrong-singleton failure
    one rank up from the FitReport's.
    """

    n_lines: int
    templates: list[ShiftTemplateFit] = Field(default_factory=list)
    best: str | None = None
    separable: bool = False
    separability_ratio: float = 0.0
    max_collinearity: float = 0.0
    #: residual scatter (°2θ) after removing the best template — the σ_sys floor
    #: WP-1020's tolerance model adds in quadrature to each line's own σ
    sigma_sys_deg: float = 0.0
    #: largest disagreement (°2θ), over the angles actually sampled, between the
    #: corrections the **competitive** templates predict — competitive meaning
    #: within ``SEPARABILITY_MIN_SS_RATIO`` of the best residual sum of squares.
    #: It is the cost of choosing the wrong cause, reported rather than argued,
    #: and the qualifier is load-bearing.  Measured (WP-1019) on a 0.10° cos θ
    #: displacement sampled over 10-25° 2θ, where the screen correctly refuses to
    #: name a cause: over **all three** templates the predictions differ by
    #: 0.046°, nearly half the shift — but ``sin_2theta`` is not competitive
    #: there (it fits worse by more than the ratio bar), and over the two that
    #: are, the spread is **0.0011°**, about 1 % of the shift.  So the plan's
    #: conclusion holds — the *cell* stands while the *cause* does not — but only
    #: with "competitive" in it: a template the data rejects is not a candidate
    #: cause, and averaging it in overstates the risk forty-fold.  Read this field
    #: rather than inferring the risk from ``separable``.
    prediction_spread_deg: float = 0.0
    #: ``"measured"`` when reference positions were supplied and the templates
    #: were fitted; ``"unavailable"`` when there was nothing to fit against,
    #: which is the *normal* state at index time — see
    #: :func:`pxrdref.indexing.quality.assess_peak_list`.
    source: Literal["measured", "unavailable"] = "unavailable"


class DataQualityReport(Base):
    """Is this peak list fit to index, and what does it already say?

    ``supports_indexing`` is read by ``index_pattern`` before any budget is
    spent, and **abstention is a result**: a list that cannot support a search
    comes back with ``supports_indexing = False`` and a reason, never as an
    exception and never as a ranked list of cells with nothing behind it.

    Every threshold this verdict rests on is a module constant in
    ``schemas/indexing.py`` with its reasoning, and ``thresholds_version``
    records which set produced it.
    """

    n_usable: int
    n_total: int
    two_theta_min: float
    two_theta_max: float
    source: Literal["fitted", "positions"]
    #: median and worst σ(2θ) over the usable lines, ° 2θ
    sigma_two_theta_median: float
    sigma_two_theta_worst: float
    #: median σ(Q)/Q — a dimensionless resolving power, see
    #: :data:`MAX_RELATIVE_SIGMA_Q`
    relative_sigma_q_median: float
    #: median σ(Q) over the mean spacing between neighbouring Q values.  Above
    #: ~1 the lines are not individually resolved in Q and no tolerance can
    #: separate a right cell from a wrong one.
    sigma_over_spacing: float
    #: usable lines ÷ metric DOF, per system — the system-dependent half of
    #: "enough lines" (:data:`MIN_LINES_PER_DOF`)
    lines_per_dof: dict[str, float] = Field(default_factory=dict)
    #: systems this list can support a search in at all
    systems_supported: list[str] = Field(default_factory=list)
    #: Smith (1977) envelope on the unit-cell volume, Å³, from d at the N-th
    #: line — the default ``max_volume`` for a search, **per system** because the
    #: bound differs by up to 96× across them (a cubic F lattice shows ~96× fewer
    #: distinct lines than a primitive triclinic one of the same volume, so the
    #: same N lines admit a correspondingly larger cell).  One number would
    #: therefore either exclude the true cubic cell or be useless for triclinic.
    volume_envelope: dict[str, float] = Field(default_factory=dict)
    shift: ShiftScreen | None = None
    supports_indexing: bool = True
    abstained_reason: str | None = None
    thresholds_version: str = INDEXING_THRESHOLDS_VERSION
    diagnostics: list[Diagnostic] = Field(default_factory=list)
