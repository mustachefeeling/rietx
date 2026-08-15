"""Minimal staged refinement runner.

Encodes the IUCr-guideline practice of turning parameter groups on
cumulatively in a stable order (McCusker, Von Dreele, Cox, Louër & Scardi,
1999, J. Appl. Cryst. 32, 36): scale + background first, then peak positions
(zero/cell), then profile widths.  Each stage runs the bounded least squares
to convergence before the next group is freed; the reflection list and
evaluation windows are regenerated between stages (the differentiability
invariant — they stay frozen *within* a stage).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..schemas.common import Mode

#: ``phases.i.atoms.j.u11`` … — the stored anisotropic components, grouped by
#: site for the positive-definiteness guard.
_ADP_COMPONENT = re.compile(r"^(phases\.\d+\.atoms\.\d+)\.u(11|22|33|12|13|23)$")
_U_ORDER = {"11": 0, "22": 1, "33": 2, "12": 3, "13": 4, "23": 5}

#: The displacement-parameter stage frees whichever representation each site
#: actually uses.  Both globs are always safe: an isotropic site has no
#: ``adp.k`` entries, and an anisotropic one has its ``biso`` locked, so
#: neither can free a parameter that does not reach the model.
_DISPLACEMENT_GLOBS = ["phases.*.atoms.*.biso", "phases.*.atoms.*.adp.*"]



@dataclass
class Stage:
    name: str
    turn_on: list[str]  # path globs, e.g. "phases.*.cell.*"
    max_iter: int = 100
    lebail_cycles: int = 3  # intensity-partitioning refreshes (lebail mode)
    #: lift any softplus-bounded parameter this stage frees off the exact-zero
    #: floor to this value before solving, so TRF sees a live gradient (the
    #: softplus map's slope at p≈0 is ≈0, so a coefficient starting at 0 would
    #: never move).  0 = no seed.  The extinction stage uses it; unlike the FCJ
    #: AXIAL_SIZING_FLOOR (an identity-transform bound, movable off zero on its
    #: own) a softplus coefficient genuinely needs the value nudge.
    seed: float = 0.0
    #: microstrain (ppm of ΔM/M) to put a freed but still all-zero Stephens
    #: block on before solving.  ``seed`` cannot serve: the S_HKL DOFs are
    #: identity-transform, and their pathology at zero is the *exploding*
    #: gradient of √Σ rather than the softplus's dead one.  0 = no seed.
    strain_seed: float = 0.0
    #: c_w of McCusker eq (7), S = S_y + c_w·S_G: how heavily this stage weights
    #: the geometric 'observations' (every soft restraint the phases declare)
    #: against the diffraction data.  The paper's prescription is a *schedule* —
    #: "set high at the beginning of a refinement when the structure is
    #: incomplete or only approximately correct … then reduced during the course
    #: of the refinement as the structural model improves" — and a stage is what
    #: this package changes a discrete quantity between, so the schedule is one
    #: scalar per stage.  Constant within the stage, applied at its compile:
    #: frozen-per-stage discreteness as designed, not an exception to it.
    #: 1.0 is the identity (every pre-WP-1074 fit); 0.0 keeps the rows in the
    #: layout at zero magnitude rather than removing them, so the row count —
    #: and the statistics exclusion built on it — does not change mid-plan.
    restraint_weight_scale: float = 1.0


#: Surface roughness (WP-0502) goes **last** in every plan that carries it.
#: It is the most degenerate correction in the package: a low-angle intensity
#: depression is exactly what an inflated Biso/ADP, a shrunken scale or a
#: flexible background will each happily absorb, and unlike extinction it has no
#: |F|²-dependence to distinguish it.  Letting the structure settle first leaves
#: roughness only its own (θ-only, low-angle-weighted) signature to fit — and
#: whatever is left over is what the ROUGHNESS_ABSORPTION guard measures.
#:
#: The glob matches only instruments that declared a block, so it is safe in
#: any plan (same property as the preferred-orientation stage).  The seed lifts
#: the softplus strength parameter (Suortti ``b``, Pitschke ``c``) off the zero
#: floor where dp/du → 0; 0.3 is chosen from the measured sensitivity peak of
#: the Suortti model, which sits near b ≈ 0.17 for data from 5° 2θ and b ≈ 0.46
#: from 20° — not at a token 1e-3, which for ``b`` is not merely a dead
#: *internal* gradient but a genuinely dead *correction* (see
#: RoughnessSuortti: both b → 0 and b → ∞ are the identity).
_ROUGHNESS_STAGE = (
    Stage("roughness", ["instrument.geometry.surface_roughness.*"], seed=0.3),
)


@dataclass
class RefinementPlan:
    stages: list[Stage]
    correlation_guard: float = 0.98

    @classmethod
    def mccusker_default(cls) -> "RefinementPlan":
        """Default staged plan for a Rietveld run (McCusker et al., 1999)."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
        ])

    @classmethod
    def mccusker_structural(cls) -> "RefinementPlan":
        """The McCusker order continued into the structural parameters:
        atomic coordinates once the profile is stable, then displacement
        parameters.  Coordinates refine as site-symmetry DOFs
        (``phases.*.atoms.*.dof.*`` — WP-0301 constraint block; a special
        position contributes only its allowed directions, a fully fixed one
        contributes none, so the glob is always safe).  The displacement
        stage frees ``biso`` on isotropic sites and the ``adp.*`` patterns on
        anisotropic ones, whichever each site declares.  Kept separate from
        :meth:`mccusker_default` so profile-only workflows never free
        structural parameters by accident."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
            Stage("coordinates", ["phases.*.atoms.*.dof.*"]),
            Stage("biso", list(_DISPLACEMENT_GLOBS)),
            # March-Dollase preferred orientation (WP-0307) turns on *after* the
            # displacement stage: r, occupancies and ADPs all rescale intensity
            # in Q-dependent ways, so letting the structure settle first leaves
            # PO with its own axis-angle signature to fit.  The glob matches only
            # phases that declared a PO block; r ≡ 1 is the identity, so a start
            # from 1.0 perturbs nothing until the data pull it off.
            Stage("preferred_orientation", ["phases.*.preferred_orientation.r"]),
            # secondary extinction (WP-0506) comes *after* the displacement
            # stage on purpose: ext, Biso and the ADPs all attenuate high-Q
            # intensity, so letting the structure/ADPs settle first leaves
            # extinction with only its (different, low-angle-weighted)
            # signature to fit.  The coefficient starts at exactly 0 on the
            # softplus floor, so the stage seeds it to lift TRF off the zero.
            Stage("extinction", ["phases.*.extinction"], seed=1e-3),
            *_ROUGHNESS_STAGE,
        ])

    @classmethod
    def lab_bragg_brentano(cls) -> "RefinementPlan":
        """Lab flat-plate plan: adds sample displacement (with zero), then the
        Kα2/Kα1 intensity ratio and FCJ axial-divergence parameters last —
        the McCusker ordering extended by the v0.2 lab-instrument physics.
        Sample transparency stays fixed (free it explicitly for low-absorbing
        samples)."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero_disp", ["instrument.zero_shift",
                                "instrument.geometry.sample_displacement"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
            Stage("lines_axial", ["instrument.source.lines.*.weight",
                                  "instrument.geometry.axial_sl",
                                  "instrument.geometry.axial_hl"]),
            *_ROUGHNESS_STAGE,
        ])

    @classmethod
    def lab_calibrate(cls) -> "RefinementPlan":
        """Calibrate the instrument on a **certified line-profile standard**
        (NIST SRM 660c LaB6): the certified cell is *held fixed* — that is
        what pins the dispersion axis and decorrelates the otherwise-sloppy
        {zero (const), displacement (cosθ), cell (tanθ)} triple — while zero,
        displacement, the resolution function, the Kα2 ratio and the axial
        ratios refine.  Export the result with ``save_instrument_profile``;
        refine unknowns against it with the ``lab_sample_refine`` plan.

        **No roughness stage here, deliberately.**  A certified line-profile
        standard is a carefully prepared specimen, and this plan's job is to
        measure the *goniometer*; freeing a mount property against a fixed
        certified cell would let specimen preparation contaminate the
        calibration that every later sample inherits.  ``save_instrument_profile``
        strips any roughness block for the same reason."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero_disp", ["instrument.zero_shift",
                                "instrument.geometry.sample_displacement"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
            Stage("lines_axial", ["instrument.source.lines.*.weight",
                                  "instrument.geometry.axial_sl",
                                  "instrument.geometry.axial_hl"]),
            Stage("biso", list(_DISPLACEMENT_GLOBS)),
        ])

    @classmethod
    def lab_sample_refine(cls) -> "RefinementPlan":
        """Refine a *sample* against a **calibrated, frozen instrument**
        (the calibrate-on-standard → freeze → refine-sample workflow; see
        ``rietx.io.instrument_profile``).

        Only sample-side parameters move: scale/background, specimen
        displacement (a property of the mount, not the instrument), cell,
        the four sample broadening terms (Lorentzian + Gaussian size/strain
        — the instrument U V W X Y stay at their calibrated values), then
        Biso.  Never frees zero, axial ratios or emission-line weights."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("disp", ["instrument.geometry.sample_displacement"]),
            Stage("cell", ["phases.*.cell.*"]),
            # Stephens anisotropic strain (WP-0503) is freed *in* the
            # sample-broadening stage, not after it.  A microstrain block locks
            # lor_strain — its isotropic direction is that same column — so a
            # later stage would leave the isotropic width unrefined right up to
            # the moment four correlated patterns are turned on at once, which
            # is the worst possible starting point.  The glob matches only
            # phases that declared a block, and the seed puts an all-zero one
            # on the isotropic ray (Λ ∝ √Σ has unbounded slope at Σ = 0).
            Stage("sample_profile", ["phases.*.lor_size", "phases.*.lor_strain",
                                     "phases.*.gauss_size", "phases.*.gauss_strain",
                                     "phases.*.microstrain.dof.*"],
                  strain_seed=1000.0),
            Stage("biso", list(_DISPLACEMENT_GLOBS)),
            *_ROUGHNESS_STAGE,
        ])

    @classmethod
    def profile_only(cls) -> "RefinementPlan":
        """Le Bail-style plan: no structural parameters exist to free."""
        return cls(stages=[
            Stage("bkg", ["instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
        ])

    @classmethod
    def pawley_default(cls) -> "RefinementPlan":
        """Pawley whole-pattern plan: cell + profile, same order as
        :meth:`profile_only`.  The per-hkl intensities are *not* named globs —
        they are refined as an implicit block every stage (see
        ``model.forward.PawleyBlock``), so no ``turn_on`` frees them."""
        return cls(stages=[
            Stage("bkg", ["instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
        ])


PLAN_PRESETS = {
    "mccusker_default": RefinementPlan.mccusker_default,
    "mccusker_structural": RefinementPlan.mccusker_structural,
    "lab_bragg_brentano": RefinementPlan.lab_bragg_brentano,
    "lab_calibrate": RefinementPlan.lab_calibrate,
    "lab_sample_refine": RefinementPlan.lab_sample_refine,
    "profile_only": RefinementPlan.profile_only,
    "pawley_default": RefinementPlan.pawley_default,
}


def resolve_plan(plan: "RefinementPlan | str", mode: Mode) -> RefinementPlan:
    """A preset name (or a plan) as a concrete plan, mapped through ``mode``.

    ``"mccusker_default"`` is the name every caller passes without thinking, and
    it means something different per mode: Le Bail has no structure to refine so
    it becomes ``profile_only``, and Pawley refines its intensities off-table so
    it becomes ``pawley_default``.  That mapping decides what actually ran, so it
    lives here beside the registry rather than in each caller — four now want it
    (``Refinement.fit``, ``sequential``, ``agent``, and the GUI, which must show
    a user the stages that a run *will* have before it starts).
    """
    if not isinstance(plan, str):
        return plan
    name = plan
    if name == "mccusker_default" and mode == "lebail":
        name = "profile_only"
    elif name == "mccusker_default" and mode == "pawley":
        name = "pawley_default"
    try:
        return PLAN_PRESETS[name]()
    except KeyError:
        raise ValueError(f"unknown plan preset {plan!r}; "
                         f"available: {sorted(PLAN_PRESETS)}") from None


@dataclass(frozen=True)
class PlanInfo:
    """What a preset is for, in the words a chooser needs.

    Beside the registry rather than in a UI, a docs page or a capabilities
    module, because every one of those consumers needs the same four facts and
    the presets are what they describe: a preset added without a row here is a
    preset nobody can be told when to use.  ``tests/test_params_surface.py``
    fails on a missing or extra key (the WP-0602 registry-meta-test pattern).

    ``modes`` lists the intensity modes the plan is meaningful in — plural,
    because ``profile_only`` is both the Le Bail plan and the way to fit a
    profile in Rietveld mode without touching the structure.
    """

    title: str
    description: str
    modes: tuple[Mode, ...]
    when_to_use: str


#: Per-preset guidance.  Keys are held in bijection with PLAN_PRESETS by a test.
PLAN_INFO: dict[str, PlanInfo] = {
    "mccusker_default": PlanInfo(
        title="Standard (profile only)",
        description=(
            "The IUCr-guideline turn-on order (McCusker et al., 1999): scale + "
            "background, zero shift, cell, then the profile widths. Leaves every "
            "structural parameter fixed."),
        modes=("rietveld",),
        when_to_use=(
            "The default first fit of a known structure, and the plan to reach "
            "for whenever a structural refinement has gone wrong — it converges "
            "the parameters everything else depends on."),
    ),
    "mccusker_structural": PlanInfo(
        title="Standard + structure",
        description=(
            "The standard order continued into the structure: coordinates as "
            "site-symmetry DOFs, then displacement parameters (biso or the "
            "anisotropic patterns, whichever each site declares), then preferred "
            "orientation, extinction and surface roughness where declared."),
        modes=("rietveld",),
        when_to_use=(
            "A structure worth refining against data good enough to carry it. "
            "Run the profile-only plan first if the fit is not already close."),
    ),
    "lab_bragg_brentano": PlanInfo(
        title="Lab diffractometer (one pass)",
        description=(
            "Bragg-Brentano flat-plate order: the sample displacement and "
            "transparency corrections join the zero shift, and the axial "
            "(Finger-Cox-Jephcoat) apertures refine with the widths."),
        modes=("rietveld",),
        when_to_use=(
            "A single lab pattern with no instrument calibration to hand — it "
            "refines specimen and instrument effects together, so read the "
            "correlation guards before quoting a width."),
    ),
    "lab_calibrate": PlanInfo(
        title="Lab: calibrate on a standard",
        description=(
            "Step 1 of the two-step lab workflow. Refines the instrument "
            "profile and the position corrections on a line-position standard "
            "**with its certified cell held fixed** — which is what decorrelates "
            "zero shift, displacement and cell."),
        modes=("rietveld",),
        when_to_use=(
            "On a standard (LaB6, Si, corundum), once per instrument "
            "configuration. Follow it with save_instrument_profile."),
    ),
    "lab_sample_refine": PlanInfo(
        title="Lab: refine a specimen",
        description=(
            "Step 2 of the two-step lab workflow. The instrument profile is "
            "held at its calibrated values and only the sample's own broadening "
            "(size and strain, isotropic or Stephens-anisotropic) refines, "
            "instrument ⊕ sample."),
        modes=("rietveld",),
        when_to_use=(
            "Any specimen measured on a calibrated instrument, and the only "
            "plan whose size/strain numbers mean what they say — an "
            "uncalibrated fit absorbs the instrument into them."),
    ),
    "profile_only": PlanInfo(
        title="Cell + profile, no structure",
        description=(
            "Background, zero shift, cell and widths only. In Le Bail mode the "
            "per-hkl intensities are extracted by iterated partitioning instead "
            "of being computed from a structure."),
        modes=("lebail", "rietveld"),
        when_to_use=(
            "A known cell with an unknown or untrusted structure — indexing "
            "checks, extracted intensities for structure solution, or a "
            "cell/width measurement you want independent of any structural model."),
    ),
    "pawley_default": PlanInfo(
        title="Pawley whole-pattern",
        description=(
            "The same order as the Le Bail plan, but the per-hkl intensities "
            "are refined *inside* the least squares, so they carry esds. "
            "Overlapped groups are conditioned by an equal-split restraint and "
            "come back flagged rather than confidently split."),
        modes=("pawley",),
        when_to_use=(
            "Extracted intensities that need uncertainties — feeding structure "
            "solution or a peak-shape study. Read PAWLEY_OVERLAP_UNRESOLVED "
            "before using an intensity from an overlapped group."),
    ),
}


@dataclass(frozen=True)
class GuardFinding:
    """One guard hit, as data: which parameters, which number, which code.

    Until v1.0 these were formatted strings, and every consumer that needed a
    part of one had to take it apart again — ``refine._guard_diagnostics`` did
    ``msg.split(" ")[0]`` to recover a path, which silently produced *nothing*
    for a correlation (two paths, no leading one) and so left
    ``Diagnostic.where`` empty on the one finding a client most wants to click.
    A GUI panel reads :attr:`paths` and :attr:`value`; nobody regexes prose.

    ``__str__`` is today's formatted text, byte for byte, because the rendered
    string is what the diagnostics' messages are built from and those are a
    published surface.  Every format string that used to be written at three
    different call sites now lives in one constructor here.

    ``code`` is an **open** vocabulary of strings, deliberately not a ``Literal``
    closed over today's six: WP-1028 adds guards (a stage returning ``converged``
    at Rwp = 7225 %, a ``max_iter`` outcome, an hkl-range refusal), and a closed
    type would have to be reopened for each.  It is the *same* vocabulary as
    ``Diagnostic.code`` rather than a second one — the finding now carries the
    code, so the mapping from guard to diagnostic is data instead of six
    hand-written loops.
    """

    code: str
    paths: tuple[str, ...]
    #: the headline number — ρ, block R², a min eigenvalue, the worst σ²(M).
    #: ``None`` where the finding has no number (a parameter at its bound).
    value: float | None
    #: rendered form, identical to the pre-v1.0 list entry
    message: str

    def __str__(self) -> str:
        return self.message

    # -- constructors: one place per format string ----------------------
    @classmethod
    def correlation(cls, a: str, b: str, rho: float) -> "GuardFinding":
        return cls("HIGH_CORRELATION", (a, b), float(rho),
                   f"{a} ~ {b} (ρ={rho:+.3f})")

    @classmethod
    def at_bound(cls, path: str) -> "GuardFinding":
        return cls("BOUND_HIT", (path,), None, path)

    @classmethod
    def background_absorption(cls, path: str, r2: float) -> "GuardFinding":
        return cls("BACKGROUND_ABSORPTION", (path,), float(r2),
                   f"{path} (R²={r2:.2f})")

    @classmethod
    def roughness_absorption(cls, path: str, r2: float) -> "GuardFinding":
        return cls("ROUGHNESS_ABSORPTION", (path,), float(r2),
                   f"{path} (R²={r2:.2f})")

    @classmethod
    def nonpositive_adp(cls, site: str, min_eigenvalue: float) -> "GuardFinding":
        return cls("ADP_NOT_POSITIVE_DEFINITE", (site,), float(min_eigenvalue),
                   f"{site} (min eigenvalue {min_eigenvalue:+.2e} Å²)")

    @classmethod
    def nonpositive_strain(cls, path: str, n_bad: int, n_total: int,
                           worst: float, hkl: tuple[int, int, int]) -> "GuardFinding":
        return cls("STEPHENS_STRAIN_NOT_POSITIVE", (path,), float(worst),
                   f"{path} ({n_bad} of {n_total} reflections, "
                   f"worst σ²(M) {worst:+.2e} at {hkl})")


@dataclass
class GuardReport:
    """The guards a stage tripped, grouped by kind — see :class:`GuardFinding`.

    The six *finding* field names are unchanged from v0.2; what they hold is
    findings rather than strings.  ``str(finding)`` is the old entry, so a
    consumer that only ever printed them needs no change.

    ``measured_background_absorption`` is the one field that is **not**
    findings, and it is here rather than beside them so that the number a
    report quotes and the bit a guard fires on come from one measurement
    (WP-1055).  It carries every screened (path, R²) pair the block projection
    produced — the guard keeps those over
    :data:`BACKGROUND_ABSORPTION_GUARD` as ``background_correlations``, and
    :class:`~rietx.schemas.results.Identifiability` carries all of them onto
    the result, because a fired/not-fired bit is a verdict and 0.46-vs-0.08 is
    evidence.

    The three ``measured_*`` fields after it (WP-1056) are the same
    discipline for the parameter-space evidence: ``measured_top_correlations``
    is read from the same matrix in the same call as ``high_correlations``,
    ``measured_soft_modes`` from the same final Jacobian, and
    ``measured_exchangeability`` from one extra evaluate-only Jacobian at the
    converged values (built only on the answer-producing stage — the caller
    passes ``scan_exchangeability``).  They hold the
    :mod:`~rietx.schemas.results` rows verbatim; no guard thresholds them,
    the report does.
    """

    high_correlations: list[GuardFinding] = field(default_factory=list)
    at_bounds: list[GuardFinding] = field(default_factory=list)
    # structural parameters the background block could largely reproduce —
    # the background-eats-the-structure failure mode, measured as a multiple
    # correlation R² rather than a pairwise ρ (see check_guards)
    background_correlations: list[GuardFinding] = field(default_factory=list)
    # anisotropic displacement tensors that are no longer ellipsoids
    nonpositive_adps: list[GuardFinding] = field(default_factory=list)
    # phases whose Stephens strain coefficients have left the physical cone
    nonpositive_strain: list[GuardFinding] = field(default_factory=list)
    # two-way surface-roughness degeneracy (WP-0502): either roughness is not
    # identifiable from this data, or a displacement parameter is now hiding
    # in it.  Same block-R² statistic as background_correlations.
    roughness_correlations: list[GuardFinding] = field(default_factory=list)
    # not findings: the full screened (path, R²) table the background guard
    # decided from — see the class docstring
    measured_background_absorption: dict[str, float] = field(default_factory=dict)
    # not findings either (WP-1056): the parameter-space evidence, as
    # schemas.results rows — CorrelationPair / SoftMode / ExchangeRow
    measured_top_correlations: list = field(default_factory=list)
    measured_soft_modes: list = field(default_factory=list)
    measured_exchangeability: list = field(default_factory=list)

    def findings(self) -> list[GuardFinding]:
        """Every finding, in the order the diagnostics are emitted in."""
        return [*self.high_correlations, *self.at_bounds, *self.nonpositive_adps,
                *self.nonpositive_strain, *self.background_correlations,
                *self.roughness_correlations]


#: R² beyond which the background block is reported as able to imitate a
#: structural parameter (see ``optimize.statistics.background_absorption``).
#: Measured separation: sane backgrounds (Chebyshev-6, the default 8°-knot
#: penalized spline) sit at 0.01-0.03 even against broad peaks, while a
#: 1°-knot unpenalized spline reaches 0.46.
BACKGROUND_ABSORPTION_GUARD = 0.25

#: R² beyond which surface roughness and the displacement parameters are
#: reported as mutually substitutable (see
#: ``optimize.statistics.roughness_absorption``, which projects out the scale
#: and background first — without that every number saturates near 0.96).
#: Measured on a synthetic large-cell lab pattern, varying only the low-angle
#: cutoff: R²(Suortti b) = 0.06 with the fit reaching 7° 2θ (20 reflections
#: below 40°), 0.62 from 15°, then 0.91 / 0.93 / 0.95 from 20° / 30° / 45° —
#: the crossing happens exactly as the low-angle reflections that give the
#: depression its lever arm drop out of range.  0.9 sits in that gap.
#:
#: Deliberately looser than BACKGROUND_ABSORPTION_GUARD: a background imitating
#: a peak is always pathological, whereas roughness genuinely *is* a Q-dependent
#: intensity trend, so partial overlap with the ADPs is expected physics and
#: only near-total overlap is a finding.
ROUGHNESS_ABSORPTION_GUARD = 0.9


def check_adp_positive_definite(table) -> list[GuardFinding]:
    """Anisotropic sites whose U tensor is not positive definite.

    An unconstrained U can leave the physical cone, and the resulting
    Debye-Waller factor *grows* without bound along the offending direction
    as |h| increases — the fit does not merely become wrong, it diverges at
    high Q.  The test runs on the stored CIF U^ij matrix rather than on
    U_cart: the two are related by a congruence, so by Sylvester's law of
    inertia the eigenvalue *signs* are the same and no cell is needed here
    (magnitudes would need one — see ``crystallography.adp``).
    """
    import numpy as np

    from ..crystallography.adp import min_eigenvalue

    values = {e.path: e.value for e in table.entries}
    sites: dict[str, list[float]] = {}
    for e in table.entries:
        m = _ADP_COMPONENT.match(e.path)
        if m:
            sites.setdefault(m.group(1), [np.nan] * 6)
            sites[m.group(1)][_U_ORDER[m.group(2)]] = values[e.path]
    out = []
    for base, u6 in sorted(sites.items()):
        if not np.isnan(u6).any() and min_eigenvalue(u6) <= 0.0:
            out.append(GuardFinding.nonpositive_adp(base, min_eigenvalue(u6)))
    return out


#: relative tolerance below which a σ²(M) counts as *on* the cone rather than
#: outside it (WP-0601).  The boundary is part of the physical set — σ² = 0 is
#: a direction with no strain broadening, not an impossible variance — and two
#: legitimate states land exactly there: the all-zero block (documented as the
#: exact no-broadening identity) and the optimum of an inequality-constrained
#: solve, which the bounded-LM driver drives onto the face by construction.
#: The tolerance is relative to the largest σ² in the same phase, because the
#: constrained solve and this guard reach σ² by different association orders
#: and disagree in the last bits.
STEPHENS_CONE_TOL = 1e-9


def check_stephens_positive(table, model) -> list[GuardFinding]:
    """Phases whose Stephens σ²(M) is **negative** on some fitted reflection.

    σ² is a variance, so a negative value is not a large anisotropy but an
    unphysical set of coefficients — the width law's √ has nothing to take and
    the model quietly reports zero broadening for that direction.  The
    constraint is a *cone* coupling all fifteen coefficients (like ADP positive
    definiteness), which is why it cannot be a box bound and has to be a guard
    under the default TRF driver.  ``solver="lm"`` can carry it as a linear
    inequality instead (``optimize/lm.py``), and then this guard falls silent
    because there is nothing left to report — which is the point.

    Zero is *inside* the physical set, and the test is one-sided for that
    reason: an all-zero block is the exact no-broadening identity, and a
    constrained optimum sits on the face by construction.  Before WP-0601 the
    test read ``σ² ≤ 0``, so an inert all-zero block reported itself as
    unphysical in every stage before the one that frees it.

    Tested on the frozen reflection list rather than over all integer hkl: the
    cone condition off the measured directions is unobservable, and flagging it
    would be a claim the data cannot support.  Needs the compiled model for
    that list, so it returns ``[]`` when none is supplied.
    """
    import numpy as np

    from ..crystallography.stephens import S_NAMES, sigma2_m

    if model is None:
        return []
    values = {e.path: e.value for e in table.entries}
    out: list[GuardFinding] = []
    for ip, cp in enumerate(model.phases):
        if cp.strain_monomials is None:
            continue
        base = f"phases.{ip}.microstrain"
        s = np.array([values.get(f"{base}.{n}", 0.0) for n in S_NAMES])
        sigma2 = np.asarray(sigma2_m(cp.strain_monomials, s))
        scale = max(float(np.max(np.abs(sigma2))), 1.0)
        bad = sigma2 < -STEPHENS_CONE_TOL * scale
        if bad.any():
            k = int(np.argmin(sigma2))
            hkl = tuple(int(v) for v in cp.reflections.hkl[k])
            out.append(GuardFinding.nonpositive_strain(
                base, int(bad.sum()), len(sigma2), float(sigma2[k]), hkl))
    return out


def check_guards(table, outcome, threshold: float,
                 background_threshold: float = BACKGROUND_ABSORPTION_GUARD,
                 roughness_threshold: float = ROUGHNESS_ABSORPTION_GUARD,
                 model=None, scan_exchangeability: bool = False) -> GuardReport:
    """Correlation, bound, background/roughness-absorption, ADP- and
    strain-shape guards.

    ``scan_exchangeability`` additionally runs the WP-1056 held-parameter
    scan (one extra evaluate-only Jacobian), which only the answer-producing
    stage should pay for — ``_run_stage`` passes ``stage_index == n_stages``.
    """
    import numpy as np

    from ..optimize.identifiability import exchangeability_scan, soft_modes, top_correlations
    from ..optimize.statistics import background_absorption, roughness_absorption

    report = GuardReport()
    report.nonpositive_adps = check_adp_positive_definite(table)
    report.nonpositive_strain = check_stephens_positive(table, model)
    free = table.free_paths

    if outcome.correlation is not None and len(free) > 1:
        corr = np.asarray(outcome.correlation)
        for i in range(len(free)):
            for j in range(i + 1, len(free)):
                if abs(corr[i, j]) > threshold:
                    report.high_correlations.append(
                        GuardFinding.correlation(free[i], free[j], corr[i, j]))
        # measured once (WP-1056): the same matrix the loop above thresholds
        report.measured_top_correlations = top_correlations(corr, free)

    if outcome.jac is not None and len(free) > 1:
        # measured once: the screened table travels to the result (WP-1055)
        # and the threshold decides only which rows become findings
        report.measured_background_absorption = background_absorption(
            outcome.jac, free)
        report.measured_soft_modes = soft_modes(outcome.jac, free)
        if scan_exchangeability and model is not None:
            report.measured_exchangeability = exchangeability_scan(model, table)
        for path, r2 in sorted(report.measured_background_absorption.items(),
                               key=lambda kv: -kv[1]):
            if r2 > background_threshold:
                report.background_correlations.append(
                    GuardFinding.background_absorption(path, r2))
        for path, r2 in sorted(roughness_absorption(outcome.jac, free).items(),
                               key=lambda kv: -kv[1]):
            if r2 > roughness_threshold:
                report.roughness_correlations.append(
                    GuardFinding.roughness_absorption(path, r2))

    lo, hi = table.bounds()
    for k, path in enumerate(free):
        t = outcome.theta[k]
        span = hi[k] - lo[k]
        tol = 1e-8 * (span if np.isfinite(span) else 1.0)
        if (np.isfinite(lo[k]) and t - lo[k] <= tol) or (np.isfinite(hi[k]) and hi[k] - t <= tol):
            report.at_bounds.append(GuardFinding.at_bound(path))
    return report
