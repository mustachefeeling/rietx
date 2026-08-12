"""FitReport schemas — the agent-facing contract, versioned by
``FitReport.thresholds_version``.

Three gated layers (docs/DESIGN.md, "Outputs & fit assessment"):

* **Layer 0** — model-free, always trustworthy (:mod:`.layer0`);
* **Layer 1** — gated linear misfit attribution (:mod:`.layer1`), present only
  when the report is built with the compiled model *and* the fit is mature
  enough to linearise;
* **Layer 2** — typed, advisory suggested actions (:mod:`.layer2`), subject to
  the staged-strategy engine's veto.

Thresholds are pinned here (and echoed in ``Provenance``) so agent behaviour
is reproducible across versions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..schemas.common import Base
from ..schemas.results import RestraintReport

# 0.3 (WP-0602): + refine_preferred_orientation in the action vocabulary
# 0.4 (WP-1054): abstained-branch honesty.  ``reindex_or_recheck_cell`` is
#   emitted on validity-failure χ² share (REINDEX_MIN_MISFIT_SHARE — replacing
#   the mature-branch-only ``rwp > 0.2`` arm, so it now survives abstention);
#   ``add_impurity_phase`` is capped at IMPURITY_SHIFT_CAP when every strong
#   unmatched peak matches the position-error evidence;
#   ``refine_preferred_orientation`` is capped below a coexisting impurity call
#   (cross-talk); ``TextureAnalysis`` gains ``caveat`` and its ``best_axis``
#   becomes always-populated evidence.  No ActionKind changed meaning, but the
#   emission conditions moved on measured states, which a consumer sees.
# 0.5 (WP-1057): purpose-grade evidence.  ``FitReport.lebail_gap`` lands (the
#   structural-vs-profile triage statistic, evaluate-only partition at the
#   converged state; None outside Rietveld mode — absent-for-cause) and the
#   summary quotes it when the ratio is notable.  No gate or emission
#   condition moved.
THRESHOLDS_VERSION = "0.5"

#: linearisation is only meaningful for peak shifts well inside the peak; past
#: this fraction of FWHM the answer is "re-detect the peak", not "shift it"
VALIDITY_RADIUS_FWHM = 0.4
#: below this local R² the five-term shape basis does not explain the region's
#: misfit, so its coefficients are not reported as causes
MIN_REGION_R2 = 0.5
#: local reduced χ² below which a region is simply fitted — there is no misfit
#: to attribute, and the R² gate (which would legitimately read ~0 on pure
#: noise) is not applied
MIN_REGION_CHI2_RED = 1.5
#: condition number of the **scale-normalised** Gram matrix above which the
#: region's basis is too collinear for the individual coefficients to be
#: separable.  Normalising matters: the raw Gram's condition is dominated by
#: the units of ∂Ω/∂pos vs Ω and says nothing about resolvability.
MAX_GRAM_CONDITION = 1e4
#: |coef|/esd needed before a coefficient is called nonzero
MIN_COEF_SIGNIFICANCE = 3.0
#: how many times more unexplained variance the runner-up template must leave
#: before the best one is called distinguishable.  Compared on *residual* sums
#: of squares, not on R² differences: every template scores R² ≈ 0.99 against
#: a clean trend, so absolute R² gaps are ~10⁻³ and meaningless, while the
#: residual ratio spans 1.0 (indistinguishable) to 10 (decisive) on the same
#: data.
SEPARABILITY_MIN_SS_RATIO = 2.0

#: March-Dollase texture diagnostic (:mod:`.texture`).  ``TEXTURE_MIN_R2`` is the
#: fraction of the intensity misfit a single-axis March model must explain before
#: texture is *detected*; ``TEXTURE_MIN_STRENGTH`` the departure of the fitted r
#: from 1 (r ≈ 1 is no texture however good the "fit"); ``TEXTURE_MIN_REFLECTIONS``
#: the number of intensity-bearing reflections below which the pattern is not
#: enough to point at an axis.
TEXTURE_MIN_R2 = 0.5
TEXTURE_MIN_STRENGTH = 0.03
TEXTURE_MIN_REFLECTIONS = 4

#: Stephens anisotropic-strain diagnostic (:mod:`.strain`).  ``STRAIN_MIN_R2``
#: is the fraction of the width misfit a Laue-allowed Stephens model must
#: explain *beyond an isotropic strain* before anisotropy is called;
#: ``STRAIN_MIN_ANISOTROPY`` the broadest/narrowest Λ ratio below which the
#: answer is "isotropic" however good the fit (the texture diagnostic's r ≈ 1
#: escape, one model down); ``STRAIN_MIN_REFLECTIONS`` the floor on
#: intensity-bearing reflections — the effective floor is one more than the
#: Laue class's pattern count, so a triclinic phase needs sixteen.
#: ``STRAIN_MAX_GRAM_CONDITION`` is the scale-normalised Gram condition beyond
#: which the individual patterns are reported unresolved: the headline
#: "directional by N×" survives that, the per-pattern breakdown does not.
STRAIN_MIN_R2 = 0.5
STRAIN_MIN_ANISOTROPY = 1.3
STRAIN_MIN_REFLECTIONS = 6
STRAIN_MAX_GRAM_CONDITION = 1e3

#: Abstained-branch honesty (WP-1054) — all four measured on the LaB₆ misfit-
#: injection fixtures (tests/test_fitreport_layers.py), 2026-08-12.
#:
#: ``reindex_or_recheck_cell`` is emitted when at least
#: ``REINDEX_MIN_FAR_FRACTION`` of the *misfitting* regions (with an absolute
#: floor of ``REINDEX_MIN_FAR_REGIONS``) fail the validity radius — the
#: position failure must be *widespread*, which is what separates a wrong
#: cell/gross calibration from a couple of locally-bad regions.  A count
#: fraction, deliberately not a χ² share: shares proved unstable under a
#: background refit (the +0.4 % cell state measures far-region share 0.192
#: unrefined but 0.049 after one background stage — indistinguishable from
#: the 0.043 of a state whose failures are saturated-fit artefacts), while
#: the count fraction reads 0.60/0.73 on those same two wrong-cell states,
#: 0.60 on a mature broad-peak gross zero (Rwp 0.14 — the old ``rwp > 0.2``
#: arm missed it), 0.71 on a gross zero beside a real impurity, against 0.33
#: on the artefact state and 0.00 on every control (all 2026-08-12, the LaB₆
#: misfit-injection fixtures).
REINDEX_MIN_FAR_FRACTION = 0.5
REINDEX_MIN_FAR_REGIONS = 3
#: A strong unmatched observed peak with an ``unmatched_calc`` partner within
#: this window is a *displaced pair* (the model's line beside the observed one),
#: not an impurity candidate — consulted only when validity-radius failures
#: exist.  Measured pair distances on the +0.4 % cell state: 0.12–0.82°;
#: a genuinely foreign line sat 1.05–1.18° from any partner.
SHIFT_PAIR_WINDOW_DEG = 1.0
#: An unmatched observed peak within this many (pattern-median) FWHM of a
#: calculated position is shape/position misfit of that reflection, not a new
#: line — the broad-peak regime, where the fixed 0.08° matching tolerance is
#: far smaller than the peak itself.  Measured: residual lobes at 0.1–0.5 FWHM
#: from their tick on broad data; a genuine impurity at 12–14 FWHM.
SHIFT_TICK_PROXIMITY_FWHM = 1.0
#: ``add_impurity_phase`` confidence when *every* strong unmatched peak matches
#: the position-error evidence — deliberately below the reindex action's 0.4,
#: because on that evidence the phase is the less likely explanation.
IMPURITY_SHIFT_CAP = 0.3
#: how far below a coexisting ``add_impurity_phase`` call the texture action is
#: capped: an un-modelled foreign peak leaks into the per-reflection extraction
#: and can manufacture the texture signature (measured: a pure impurity
#: injection scored a phantom (1,0,1) axis at R²=0.66, outranking the impurity
#: call at 0.40), so the detection must never outrank its likely cause.
TEXTURE_IMPURITY_MARGIN = 0.05

#: Le Bail gap (WP-1057) — the structural-vs-profile triage statistic.
#: ``LEBAIL_GAP_CYCLES`` partition cycles at the frozen converged state: the
#: fixed point is reached by cycle 2-3 on the LaB₆ pore-proxy fixture
#: (Rwp_lebail 0.01713 after one cycle, 0.01700 from two onward, 2026-08-12),
#: so 5 is margin, not tuning.  ``LEBAIL_GAP_NOTABLE`` is the ratio above
#: which the summary quotes the gap; measured separation on the same fixtures:
#: 2.38 on the pore proxy (guest scatterer in truth only — intensity model
#: wrong) against ≤ 1.00 on every position/profile control (+0.4 % cell 1.00,
#: broad+0.05° zero 1.00, broad clean 1.00, sharp+0.008° zero 0.96) and 0.79
#: on the converged clean fit — the partition is *not* a noise-floor
#: estimator (its net = max(y_obs − bkg, 0) clip and profile-share weighting
#: put its own floor above a converged least-squares fit), which is why the
#: notable test is on the ratio, never on rwp_lebail alone.
LEBAIL_GAP_CYCLES = 5
LEBAIL_GAP_NOTABLE = 1.5

#: a fit worse than this is "immature": Layer 1 abstains from parameter-level
#: statements entirely
MATURITY_MAX_RWP = 0.35
#: total χ² share carried by misfitting regions below which there is nothing
#: worth attributing (a converged fit always has a region or two over the
#: noise threshold by chance — that is not grounds to abstain)
MATURITY_MIN_MISFIT_SHARE = 0.2
#: fraction of the *misfitting* χ² that must sit in gate-passing regions;
#: below it, most of what is wrong cannot be read reliably ⇒ abstain
MATURITY_MIN_EXPLAINED_FRACTION = 0.4


# ----------------------------------------------------------------------
# Layer 0
# ----------------------------------------------------------------------
class Region(Base):
    two_theta_lo: float
    two_theta_hi: float
    local_rwp: float
    chi2_share: float          # fraction of total Σw·Δ² inside this region
    max_abs_delta_over_sigma: float
    n_reflections: int


class UnmatchedPeak(Base):
    two_theta: float
    height_over_sigma: float
    kind: str  # "unmatched_obs" (no calc tick nearby) | "unmatched_calc"


class LeBailGap(Base):
    """Structural-vs-profile triage: the Rietveld Rwp against an evaluate-only
    Le Bail partition of the *same* converged state (WP-1057; the Layer-0
    inventory item of DESIGN.md § Outputs).

    **Convention.**  ``rwp_lebail`` is measured by running
    :meth:`~pxrdref.model.forward.CompiledModel.lebail_update` for
    ``n_cycles`` with θ frozen at the converged values — background, cell,
    zero, profile all held; only the per-hkl intensities move, seeded flat.
    No refinement runs, so this is the cheapest description the *positions
    and profile* alone support, not a Le Bail fit (a fit would also relax
    the background and cell).  The partition is not a noise-floor estimator
    either: its ``max(y_obs − bkg, 0)`` clip and profile-share weighting
    leave it above a converged least-squares fit (measured 0.0172 against a
    converged Rwp of 0.0137 on clean LaB₆ data), which is why ``ratio`` — not
    ``rwp_lebail`` — is the statistic.

    **Reading it.**  ``ratio`` ≫ 1 means the partition, free to reassign
    every intensity, removes most of the misfit: every line is indexed and
    the profile is right — the *intensity model* (structure, contents,
    occupancies) is what is wrong, and phase ID is safe at any absolute Rwp.
    Measured on the LaB₆ pore-proxy fixture (guest scatterer in the data
    only): 2.38, against ≤ 1.00 on every position/profile control — a wrong
    cell or zero displaces the partition's peaks identically, so the gap
    stays flat and cannot be confused with position error.  ``ratio`` ≲ 1
    says intensities are not where the remaining misfit lives — it never
    says the fit is good (both Rwp may be terrible together).
    """

    rwp_rietveld: float
    rwp_lebail: float
    #: rwp_rietveld / rwp_lebail — the triage number (see class docstring)
    ratio: float
    n_cycles: int


# ----------------------------------------------------------------------
# Layer 1
# ----------------------------------------------------------------------
#: the shape-derivative basis, in physical units per unit coefficient
BasisKind = Literal["intensity", "position", "width", "mixing", "asymmetry"]


class BasisCoefficient(Base):
    """One fitted shape-derivative amplitude, with its meaning spelled out.

    ``value`` units by kind: ``intensity`` is a *relative* intensity error
    (0.05 = the region's calculated peaks are 5 % too weak), ``position`` is
    Δ2θ in degrees (positive = observed sits at higher 2θ than calculated),
    ``width`` is ΔΓ in degrees, ``mixing`` is Δη (dimensionless), and
    ``asymmetry`` is Δ(S/L).
    """

    kind: BasisKind
    value: float
    stderr: float
    significant: bool          # |value| > MIN_COEF_SIGNIFICANCE · stderr
    #: this term's share of the region's *explained* misfit,
    #: (|aⱼ|·‖colⱼ‖)² normalised over the basis.  Statistical significance
    #: alone is not importance: at high counting statistics the second-order
    #: leakage of a peak shift into the width column (y(x−δ) ≈ y − δy′ + ½δ²y″)
    #: is significant but carries a per-cent-level share, and confidence must
    #: reflect that.
    share: float = 0.0


class RegionAttribution(Base):
    """What a locally-linear model says is wrong in one region.

    ``gates_passed`` is the *only* field a consumer should branch on: when it
    is False the coefficients are reported for transparency but must not be
    read as causes.  ``gate_failures`` names which gate(s) refused.
    """

    two_theta_lo: float
    two_theta_hi: float
    n_reflections: int
    chi2_share: float
    mean_two_theta: float
    mean_fwhm: float
    coefficients: list[BasisCoefficient] = Field(default_factory=list)
    r2: float                            # misfit variance explained
    gram_condition: float
    #: local reduced χ²; ≤ MIN_REGION_CHI2_RED means this region is already
    #: fitted to the noise, so there is nothing to attribute (which is *not*
    #: the same as "the basis failed to explain it")
    chi2_reduced: float = 0.0
    has_significant_misfit: bool = True
    gates_passed: bool
    gate_failures: list[str] = Field(default_factory=list)


class TrendTemplate(Base):
    """One angular-dependence template fitted across regions.

    ``name`` identifies the physics: ``constant``→zero shift, ``cos_theta``→
    specimen displacement, ``sin_2theta``→transparency, ``tan_theta``→cell
    error (position); ``inv_cos_theta``→size, ``tan_theta``→strain (width);
    ``sin2_over_lambda2``→ADP (intensity).
    """

    name: str
    coefficient: float
    stderr: float
    r2: float


class TrendAnalysis(Base):
    """hkl-grouped angular trends that per-region views structurally miss.

    ``max_template_collinearity`` is the largest |correlation| between any two
    templates *over the angular range actually sampled*.  Near 1 the templates
    are not separable there (the Williamson-Hall problem for size/strain, and
    zero/displacement/cell over a short 2θ range) — the report says so instead
    of returning a confident singleton.
    """

    observable: Literal["position", "width", "intensity"]
    n_regions_used: int
    templates: list[TrendTemplate] = Field(default_factory=list)
    max_template_collinearity: float = 0.0
    #: residual sum-of-squares of the runner-up template over that of the
    #: best one; > SEPARABILITY_MIN_SS_RATIO ⇒ the best template is genuinely
    #: distinguishable on this data
    separability_ratio: float = 0.0
    separable: bool = True
    #: share of the pattern's total χ² this observable accounts for, summed
    #: over regions.  Drives how confident the derived actions may be: a term
    #: explaining 2 % of the misfit is not a headline no matter how many σ
    #: it stands at.
    misfit_share: float = 0.0


class TextureAnalysis(Base):
    """Single-axis March-Dollase preferred-orientation diagnostic, per phase.

    ``detected`` is the *only* field to branch on.  ``best_axis`` is evidence,
    not a verdict (WP-1054): it always carries the best-scoring crystallographic
    direction (integer hkl) whenever enough reflections informed the fit, so a
    consumer reading a sub-threshold ``r2`` can still see *which* axis got that
    score.  ``march_coefficient`` is the fitted r on that axis (< 1 or > 1 →
    platy or needle, the sense depending on geometry — see
    :mod:`pxrdref.model.preferred_orientation`).  ``r2`` is the fraction of
    the intensity misfit that model explains.  ``runner_up_axis`` is the best
    *non-equivalent* alternative — when its ``runner_up_r2`` is close to ``r2``
    the axis is not cleanly resolved (distinct habits happen to fit similarly).
    ``caveat``, when set, names evidence elsewhere in the report that can
    manufacture this signature (currently: strong unmatched observed peaks —
    un-modelled intensity leaks into the per-reflection extraction, so an
    impurity can read as texture); a detection carrying a caveat is still a
    measurement of the residual, but not of the specimen.
    """

    phase_index: int
    best_axis: tuple[int, int, int] | None = None
    march_coefficient: float = 1.0
    r2: float = 0.0
    n_reflections_used: int = 0
    detected: bool = False
    runner_up_axis: tuple[int, int, int] | None = None
    runner_up_r2: float = 0.0
    caveat: str | None = None


class StrainAnalysis(Base):
    """Stephens anisotropic-strain (directional width) diagnostic, per phase.

    ``detected`` is the field to branch on: when True the phase's widths are
    *directional* — not a function of 2θ, which is what the size/strain trend
    templates already cover, but of hkl — and a Stephens block on it is worth
    declaring.  ``anisotropy`` is the fitted broadest/narrowest Λ ratio with
    ``broadest_hkl``/``narrowest_hkl`` naming the directions, so the finding
    reads as "widths along (00l) are 3.4× those along (hk0)".  Its ceiling
    value (10⁶) means the fit wants *zero* strain along ``narrowest_hkl``, so
    the ratio is unbounded rather than measured; the hkl fields are ``None``
    when no two reflections carry enough leverage to contrast at all.

    The measurement is of the **specimen**, not of the residual: refining a
    ``microstrain`` block does not make ``detected`` go False, it makes the two
    agree (the anisotropy is still there — it is now modelled).  Suppressing a
    suggestion once the parameters are free is the Layer-2 strategy veto's job,
    not this field's.

    ``r2`` is measured against an **isotropic-strain** baseline, so it answers
    "how much of the width variation is directional", not "how much of it is
    strain" — a specimen that is uniformly too broad scores ~0 here and belongs
    to ``lor_strain`` instead.  ``n_patterns`` is the Laue class's number of
    independent S_HKL, and ``separable`` says whether those patterns are
    individually resolved over the sampled reflections: when it is False the
    ratio and the directions still stand but the per-pattern breakdown does
    not, so refine the block and read the fit, do not quote coefficients.
    """

    phase_index: int
    n_reflections_used: int = 0
    r2: float = 0.0
    anisotropy: float = 1.0
    broadest_hkl: tuple[int, int, int] | None = None
    narrowest_hkl: tuple[int, int, int] | None = None
    n_patterns: int = 0
    gram_condition: float = 0.0
    separable: bool = False
    detected: bool = False


# ----------------------------------------------------------------------
# Layer 2
# ----------------------------------------------------------------------
#: Closed, versioned action vocabulary.  Adding a member is a minor-version
#: change; changing a member's meaning is a breaking change.
ActionKind = Literal[
    "refine_zero_shift",
    "refine_sample_displacement",
    "refine_sample_transparency",
    "refine_cell",
    "refine_profile_widths",
    "refine_sample_size_broadening",
    "refine_sample_strain_broadening",
    "refine_axial_asymmetry",
    "refine_biso",
    "refine_preferred_orientation",
    "refine_scale",
    "add_impurity_phase",
    "increase_background_flexibility",
    "decrease_background_flexibility",
    "reindex_or_recheck_cell",
    "collect_better_data",
]


class SuggestedAction(Base):
    """An advisory, typed suggestion.  **The strategy engine holds the veto.**

    ``expected_delta_chi2`` is the *predicted* χ² reduction from the linear model,
    and two things about it are load-bearing for anyone rendering it (measured in
    ``tests/test_report_apply.py``, WP-1012).  It is **one number per report, not
    per action**: :func:`~pxrdref.report.build_report` computes
    :func:`.layer2.estimate_delta_chi2` once and stamps it on every
    Layer-1-derived action, so it cannot rank or distinguish suggestions — the
    texture actions, whose evidence is per-reflection, carry ``None`` instead.
    And it is **not a bound on what applying the action achieves**: it bounds the
    misfit the linear model attributes inside the *gated* regions, while the
    refinement also moves regions that failed a gate and stretches no region entry
    covers (measured: 16.19 predicted against 16.33 observed for ``refine_cell``).
    ``predict_then_verify`` in :mod:`.layer2` measures the real one and rolls back
    if it disagrees.  ``vetoed_by`` is set when the staged plan already refines the
    parameter, or when a guard forbids it.
    """

    kind: ActionKind
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    parameter_paths: list[str] = Field(default_factory=list)
    expected_delta_chi2: float | None = None
    alternatives: list[ActionKind] = Field(default_factory=list)
    two_theta_range: tuple[float, float] | None = None
    vetoed_by: str | None = None

    @property
    def active(self) -> bool:
        return self.vetoed_by is None


class VerificationOutcome(Base):
    """Result of actually trying an action (predict-then-verify with rollback)."""

    kind: ActionKind
    predicted_delta_chi2: float | None
    observed_delta_chi2: float
    accepted: bool
    reason: str


# ----------------------------------------------------------------------
class FitReport(Base):
    """All three layers.  Layer 1/2 fields stay empty when not computed."""

    thresholds_version: str = THRESHOLDS_VERSION

    # -- Layer 0
    rwp: float
    gof: float
    cumulative_chi2_breakpoints: list[float] = Field(default_factory=list)
    regions: list[Region] = Field(default_factory=list)
    n_regions_total: int = 0
    unmatched: list[UnmatchedPeak] = Field(default_factory=list)
    #: structural-vs-profile triage (Layer-0 in trustworthiness, though it
    #: needs the compiled model to run).  Absent for cause: None when the fit
    #: is already Le Bail/Pawley (the mode *is* an intensity-free description,
    #: so there is no intensity model to triage) and on model-free reports.
    lebail_gap: LeBailGap | None = None
    summary: str = ""

    # -- Layer 1
    attribution: list[RegionAttribution] = Field(default_factory=list)
    trends: list[TrendAnalysis] = Field(default_factory=list)
    #: per-phase March-Dollase texture diagnostic; populated whenever the
    #: compiled model is supplied, independent of the maturity gate (texture is
    #: a common *cause* of an immature fit, so it must still be reported)
    texture: list[TextureAnalysis] = Field(default_factory=list)
    #: per-phase Stephens anisotropic-strain diagnostic; populated on the same
    #: terms as ``texture`` and for the same reason — a directional width error
    #: no model accounts for is a common cause of an immature fit, so it must
    #: still be reported when Layer 1 abstains
    strain: list[StrainAnalysis] = Field(default_factory=list)
    #: soft-restraint summary (bond/angle/value deviations, pooled restraint χ²),
    #: carried through from the result whenever restraints were declared; a
    #: deviation ≫ σ here is a restraint fighting the data (see RESTRAINT_TENSION)
    restraints: RestraintReport | None = None
    layer1_available: bool = False
    #: set when the global maturity gate refused Layer 1 (the report abstains)
    abstained_reason: str | None = None

    # -- Layer 2
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)

    def action(self, kind: str) -> SuggestedAction:
        for a in self.suggested_actions:
            if a.kind == kind:
                return a
        raise KeyError(kind)
