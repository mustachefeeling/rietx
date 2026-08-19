"""Single-call JSON surface for driving rietx from an agent (WP-0602).

``refine_json(dict) → dict`` is the whole API: a typed request in, either a
serialized result or a structured error out, never a raw traceback.  The
envelope is deliberate:

- success: ``{"ok": true, "result": …, "series": …, "report": …,
  "trajectory": […]}`` — exactly one of
  ``result``/``series``/``indexing``/``suggestion`` is set, so a consumer
  branches on which, and the top-level result types (a refinement, a
  warm-started series, an indexing answer, a ranked suggestion) stay
  structurally distinct instead of being coerced into one.
- failure: ``{"ok": false, "error": {code, message, suggestion, details}}`` —
  the same grammar as :class:`~rietx.schemas.common.Diagnostic`, so an agent
  has one vocabulary for "the fit warns" and "the call failed".  Three codes,
  closed: ``INVALID_REQUEST`` (any validation failure, with per-field
  dot-paths in ``details``), ``BACKEND_UNAVAILABLE`` (a valid backend name
  whose optional dependency is not importable here — refused *before*
  dispatch, from the same answer :func:`~rietx.capabilities.capabilities`
  publishes), ``REFINEMENT_FAILED`` (the request was valid, this build could
  run it, and the engine raised anyway).

Two asymmetries are answered here on purpose rather than by accident:
``task="refine_multi"`` runs **without** the history DAG (a multi-pattern
fingerprint is a future seam — WP-0308), so its ``node_id``/``tree_id`` are
always null and the field description says so; a series has **one history
tree per pattern**, so its ids live on each entry and there is no run-level
pair.

``task="index"`` (WP-1024) is the fourth branch and the only one that is not a
refinement.  It answers with an ``indexing`` arm rather than ``result``/``series``
for the same reason those two are distinct: an
:class:`~rietx.schemas.indexing.IndexingResult` is a different kind of answer,
and its **shape** is load-bearing — it has no ``.cell``, so a consumer must go
through ``candidates`` or ``best_or_none()`` and cannot be handed a confident wrong
singleton by the envelope either.

``task="suggest"`` (WP-1050) is the fifth branch and the first **no-solve**
one: one Jacobian evaluation ranks every held-but-refinable parameter by its
predicted Δχ², gated so a tie of collinear candidates is one unresolved group.
It answers with a ``suggestion`` arm, extends the backend-only base (a task
with no solver and no plan refuses those fields loudly), and is read-only —
no history, no mutation, which is why it is safe to call between fits.

``task="refine"`` answers with a **trajectory** as well as a report (WP-1058):
the FitReport at every stage boundary, projected to a
:class:`~rietx.report.StageReport` each, on ``report_trajectory=true`` (off by
default since WP-1003, on WP-1064's measured criterion).  This is delivery,
not content — every statement in it was already computable before — and it
exists because WP-1053 measured *when* a report is read as the bottleneck, not
what it says: a default-plan fit lands at a converged-looking state whose
action list is empty (E2: Rwp 0.0137 behind a compensating zero shift,
measured ``actions: []``), while the same plan's **first stage** names the
cause at confidence 0.997.  The information was always there; only the last
state was ever delivered.

Three decisions behind the shape, each measured rather than argued:

- **No ``task="diagnose"``.**  The WP proposed a declared ladder of
  bootstrap-grade states an agent would otherwise have to know to create.
  Measured, the states already exist: every shipped rietveld preset opens on a
  background+scale stage — the McCusker turn-on order *is* that ladder — and
  prepending WP-1052's background-only rung to each of the seven reproduces
  stage 1's report to three decimals (0.997 against 0.997; 0.305 against 0.306
  on ``lab_calibrate``).  A ladder would also have to *change the fit* to add
  states, which would make a report-on/report-off comparison compare two
  different refinements.  So the rungs are read off the states the plan
  already passes through, and no new verb ships.
- **A new field, not a new arm.**  The WP-1043 rule sends a differently
  *shaped* answer to its own arm; this is the same FitReport contract
  projected onto the run's states, riding beside ``report`` the way
  ``evidence`` rides beside ``indexing``.
- **No version moves.**  Nothing in ``schemas/`` gains or changes a field, so
  ``SCHEMA_VERSION`` stands; ``FitReport`` itself is untouched — no threshold,
  gate, emission condition or ``ActionKind`` moved — so ``THRESHOLDS_VERSION``
  stands too, and stamping a bump onto rungs produced by unchanged thresholds
  would claim a change that did not happen.  ``trajectory`` is a defaulted
  field on the envelope, which is additive by the same reasoning WP-1043
  recorded for ``evidence``.

``request_schema()`` / ``response_schema()`` / ``tool_definition()`` export
the JSON Schemas an LLM tool-calling loop needs.  The backend, solver,
plan and **indexing-engine** vocabularies are validated against the **live
registries** (``backend.api.BACKEND_NAMES``, ``optimize.least_squares.SOLVERS``,
``strategy.staged.PLAN_PRESETS``, ``indexing.engine_names()``) and the schema
descriptions are built from the same tuples at import time — a restated literal
union is exactly what went stale two days after the torch backend landed (see
WP-0408's note).  A meta-test fails when a registered member is missing from the
exported schema, so a third engine cannot ship invisible.

The MCP server wrapping this call — and with it any file-path or CIF-text
convenience — stays fenced in v2; this surface takes typed objects only.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, TypeAdapter, ValidationError, field_validator, model_validator

from ._about import AGENT_TOOL_NAME, DATA_PACKAGE, DIST_NAME, DOCS_URL
from .backend.api import BACKEND_NAMES

# importing the package (not ``.indexing.engines``) is what registers the engines,
# so the names quoted below are the ones ``index_pattern`` would actually run
from .indexing import (
    SEARCH_PRESET_INFO,
    SEARCH_PRESETS,
    SYSTEM_ORDER,
    engine_descriptions,
    engine_names,
)
from .optimize.least_squares import SOLVERS
from .params.multi import SharingMap
from .report.schemas import FitReport, StageReport
from .schemas.common import Base, Mode
from .schemas.indexing import (
    IndexingEvidence,
    IndexingResult,
    PeakList,
    SearchSpecSpec,
)
from .schemas.instrument import Instrument
from .schemas.pattern import PatternData

# one plan schema for the whole package (WP-1004): this module used to define a
# second ``StageSpec``/``PlanSpec`` pair that had drifted from the history one;
# the compat re-export went pre-freeze (WP-1003)
from .schemas.plan import PlanSpec
from .schemas.results import RefinementResult
from .schemas.sequential import SeriesResult
from .schemas.structure import Structure
from .schemas.suggest import SuggestionResult
from .strategy.staged import PLAN_PRESETS

# ----------------------------------------------------------------------
# vocabularies quoted from the live registries (never restated literals)
# ----------------------------------------------------------------------
_BACKEND_DESC = (
    "Jacobian backend, validated against the live registry (currently: "
    + ", ".join(BACKEND_NAMES)
    + "); 'numpy' is the default and the only one a single pattern needs. "
    "A name the registry has but this build cannot import comes back "
    "BACKEND_UNAVAILABLE before anything runs — capabilities().backends says "
    "which, without an attempt")
_SOLVER_DESC = (
    "least-squares driver (currently: " + ", ".join(SOLVERS)
    + "); 'lm' adds constraint vocabulary scipy does not have — it enforces "
    "the Stephens strain positivity cone (see the CONSTRAINT_ACTIVE "
    "diagnostic)")
_PLAN_DESC = (
    "staged-plan preset name (currently: " + ", ".join(sorted(PLAN_PRESETS))
    + ") or an explicit stage list; hand-roll stages only with a reason you "
    "can state — the presets encode the McCusker turn-on order "
    "(AGENT_PROTOCOL §2)")
_ENGINE_DESC = (
    "indexing search engines to run, from the live registry ("
    + "; ".join(f"{name}: {desc}"
                for name, desc in sorted(engine_descriptions().items()))
    + "). Default: all of them, and keep it — 'high' confidence *means* every "
    "engine that ran found the same lattice, so naming a subset narrows what "
    "the answer is able to say")
_PRESET_DESC = (
    "search preset governing the whole-run ceiling, from the live registry ("
    + "; ".join(f"'{name}': {SEARCH_PRESET_INFO[name].title}"
                for name in sorted(SEARCH_PRESETS))
    + "). Default 'quick', which fills total_budget_seconds when you left it "
    "unset; 'full' runs unbounded (the pre-1.0 behaviour). Setting your own "
    "total_budget_seconds overrides the preset's and the result records "
    "preset='custom'")
_SEARCH_DESC = (
    "search bounds and budgets — one spec every engine reads, so their "
    "agreement means one search. systems: default all, in decreasing "
    "symmetry (" + ", ".join(SYSTEM_ORDER)
    + "); a restricted search is not a verdict — the result reports "
    "systems_searched and INDEX_SYSTEMS_NOT_COVERED rather than "
    "concluding anything about the specimen. preset: " + _PRESET_DESC)


class SharingSpec(Base):
    """Multi-histogram sharing overrides; mirrors ``params.multi.SharingMap``.

    Default rule (no spec): per-histogram iff the path starts with
    ``instrument.`` or ends with ``.scale``; everything else is shared — one
    specimen, one crystal.
    """

    per_histogram: list[str] = Field(default_factory=list)
    shared: list[str] = Field(default_factory=list)

    def to_map(self) -> SharingMap:
        return SharingMap(per_histogram=list(self.per_histogram),
                          shared=list(self.shared))


class _BackendBase(Base):
    """A task that evaluates the model but need not *solve* anything.

    Split from :class:`_RequestBase` for ``task="suggest"`` (WP-1050): a
    no-solve task has a Jacobian backend but no solver and no plan, and under
    ``extra="forbid"`` passing either is a loud, field-named error rather
    than a silently ignored knob.
    """

    backend: str = Field("numpy", description=_BACKEND_DESC)

    @field_validator("backend")
    @classmethod
    def _known_backend(cls, v: str) -> str:
        if v not in BACKEND_NAMES:
            raise ValueError(f"unknown backend {v!r}; "
                             f"available: {', '.join(BACKEND_NAMES)}")
        return v


class _RequestBase(_BackendBase):
    solver: str = Field("trf", description=_SOLVER_DESC)
    plan: str | PlanSpec = Field("mccusker_default", description=_PLAN_DESC)

    @field_validator("solver")
    @classmethod
    def _known_solver(cls, v: str) -> str:
        if v not in SOLVERS:
            raise ValueError(f"unknown solver {v!r}; "
                             f"available: {', '.join(SOLVERS)}")
        return v

    @field_validator("plan")
    @classmethod
    def _known_plan(cls, v):
        if isinstance(v, str) and v not in PLAN_PRESETS:
            raise ValueError(f"unknown plan preset {v!r}; "
                             f"available: {', '.join(sorted(PLAN_PRESETS))}")
        # the shared PlanSpec (schemas/plan.py) allows an empty stage list so it
        # can read history headers written before the first stage ran; a request
        # about to spend minutes on a plan that frees nothing is a mistake
        if isinstance(v, PlanSpec) and not v.stages:
            raise ValueError("plan.stages must not be empty; name a preset "
                             f"({', '.join(sorted(PLAN_PRESETS))}) or list at "
                             "least one stage")
        return v


class RefineRequest(_RequestBase):
    """Single-pattern refinement → ``result`` (+ ``report``)."""

    task: Literal["refine"]
    structure: Structure
    instrument: Instrument
    pattern: PatternData
    mode: Mode = "rietveld"
    two_theta_limits: tuple[float, float] | None = None
    history_path: str | None = Field(None, description=(
        "JSONL file to persist the refinement history DAG; without it the "
        "one-shot call keeps no history and node_id/tree_id are null"))
    include_report: bool = Field(True, description=(
        "attach the three-layer FitReport (numbers, not pixels — "
        "AGENT_PROTOCOL §5); Layers 1-2 still gate themselves"))
    report_trajectory: bool = Field(False, description=(
        "attach `trajectory`: the report at every stage boundary, projected "
        "to a StageReport each (WP-1058). OFF by default since WP-1003 — the "
        "eval rounds' pre-registered criterion fired: consumers given the "
        "rungs decided no better at more calls, twice measured (WP-1064). "
        "Turn it on for a run you will actually read: a converged report is "
        "routinely the least informative one in the run — a compensated fit "
        "reads Rwp 0.0137 with an EMPTY action list while the same plan's "
        "first stage names the cause at confidence 0.997. Costs ~2.5x the "
        "fit's wall clock (measured 1.06 s -> 2.70 s on 59.5k channels) and "
        "~26 % of the report's payload; it changes no number the fit "
        "produces. include_report=false overrides it: that flag means no "
        "report content at all, so a caller who declines the report is never "
        "handed one a rung at a time"))


class MultiRefineRequest(_RequestBase):
    """Joint multi-histogram refinement: one stacked residual over N patterns
    sharing a structure (this is **not** a series — see refine_sequential).

    Runs without the history DAG — a multi-pattern fingerprint is a future
    seam (WP-0308) — so ``node_id``/``tree_id`` are always null here, by
    declaration rather than accident.  No FitReport either: reports are
    per-histogram (``result.for_histogram(h)`` + ``build_report`` in python).
    Rietveld-only, per the v0.3 decision recorded in ``multi.py``.
    """

    task: Literal["refine_multi"]
    structure: Structure
    instruments: list[Instrument] = Field(min_length=1)
    patterns: list[PatternData] = Field(min_length=1)
    mode: Literal["rietveld"] = "rietveld"
    two_theta_limits: tuple[float, float] | list[tuple[float, float]] | None = \
        Field(None, description="one range for every histogram, or one per")
    weights: list[float] | None = Field(None, description=(
        "inter-histogram residual weights (default: unit — each point's own "
        "esd governs); recorded in provenance, never silent"))
    sharing: SharingSpec | None = None

    @model_validator(mode="after")
    def _lengths(self) -> "MultiRefineRequest":
        if len(self.patterns) != len(self.instruments):
            raise ValueError(f"{len(self.patterns)} patterns for "
                             f"{len(self.instruments)} instruments")
        if self.weights is not None and len(self.weights) != len(self.patterns):
            raise ValueError("weights must be one positive number per histogram")
        return self


class SequentialRefineRequest(_RequestBase):
    """Warm-started series: N separate refinements chained by a warm start →
    ``series`` (per-pattern summaries + trajectories, no curves).

    One history tree per pattern (ids on each entry, none for the run).  For
    anything publishable run ``direction="both"`` — the only check that
    separates a measured trajectory from an ordering artefact
    (SEQUENTIAL_PATH_DEPENDENT).
    """

    task: Literal["refine_sequential"]
    structure: Structure
    instrument: Instrument
    patterns: list[PatternData] = Field(min_length=1)
    mode: Mode = "rietveld"
    two_theta_limits: tuple[float, float] | None = None
    x: list[float] | None = Field(None, description=(
        "series coordinate (temperature, time, pressure…); the pattern index "
        "is the axis when absent"))
    x_label: str = "index"
    labels: list[str] | None = None
    refit: Literal["single", "stages"] = Field("single", description=(
        "'single' collapses the plan into one stage for warm patterns "
        "(measured 904 vs 1623 iterations at identical accuracy, WP-0505)"))
    direction: Literal["forward", "backward", "both"] = "forward"
    carry: list[str] = Field(default_factory=lambda: ["*"], description=(
        "dot-path globs that cross a pattern boundary; restrict only for "
        "parameters that must provably not be chained"))
    reseed: bool = True
    history_dir: str | None = Field(None, description=(
        "directory for the per-pattern history trees "
        "(<dir>/<label>.jsonl, one per pattern)"))

    @model_validator(mode="after")
    def _lengths(self) -> "SequentialRefineRequest":
        for name, seq in (("x", self.x), ("labels", self.labels)):
            if seq is not None and len(seq) != len(self.patterns):
                raise ValueError(f"{name} has {len(seq)} entries for "
                                 f"{len(self.patterns)} patterns")
        return self


class IndexRequest(Base):
    """Unit-cell determination → ``indexing`` (an ``IndexingResult``).

    Not a refinement, so it carries no backend, solver or plan.  Give it
    ``peaks``, or a ``pattern`` + ``instrument`` pair it will pick peaks from —
    and prefer the second, because supplying a pattern is what turns **whole-
    profile validation** on.  Without one every candidate caps at ``"medium"`` and
    ``INDEX_NOT_VALIDATED`` fires: the figure-of-merit panel sees at most 20 lines
    and is blind to lines beyond them, to impurity content, and to reflections
    predicted where there is no intensity.

    Read the ``evidence`` arm first (WP-1043) — every candidate with each
    caveat's refuting/capping kind, the figures that ranked beside the ones
    absent for cause, and the whole-profile numbers together — then
    ``indexing.candidates`` for the full record; call ``best_or_none()`` for a
    singleton and expect ``None`` more often than not.
    """

    task: Literal["index"]
    peaks: PeakList | None = Field(None, description=(
        "a fitted peak list (rietx.pick_peaks output, or "
        "PeakList.from_positions for bare positions from a publication)"))
    pattern: PatternData | None = Field(None, description=(
        "the pattern; supplying it enables Le Bail validation and lets peaks be "
        "picked when `peaks` is absent"))
    instrument: Instrument | None = Field(None, description=(
        "required with `pattern`; also what makes the cell's Bragg-Brentano "
        "systematic quantifiable (INDEX_CELL_SYSTEMATIC_UNQUANTIFIED)"))
    engines: list[str] | None = Field(None, description=_ENGINE_DESC)
    search: SearchSpecSpec = Field(default_factory=SearchSpecSpec,
                                   description=_SEARCH_DESC)
    two_theta_limits: tuple[float, float] | None = None
    validate_candidates: bool = Field(True, description=(
        "run the whole-profile Le Bail validation when a pattern is available; "
        "turning it off caps every candidate at medium, so do it only to save "
        "time on a first look"))
    check_top: int | None = Field(None, ge=1, description=(
        "candidates given the expensive per-candidate checks (geometrical "
        "ambiguity + Le Bail validation); None = the package default plus "
        "every candidate the gate could promote"))

    @field_validator("engines")
    @classmethod
    def _known_engines(cls, v):
        for name in v or ():
            if name not in engine_names():
                raise ValueError(f"unknown indexing engine {name!r}; "
                                 f"available: {', '.join(engine_names())}")
        return v

    @model_validator(mode="after")
    def _enough_input(self) -> "IndexRequest":
        if self.peaks is None and (self.pattern is None
                                  or self.instrument is None):
            raise ValueError(
                "give either peaks, or pattern + instrument to pick peaks from: "
                "a pattern cannot be indexed without the wavelength and profile "
                "its instrument declares")
        if self.pattern is not None and self.instrument is None:
            raise ValueError("pattern needs instrument (wavelength, profile, "
                             "geometry)")
        return self


class SuggestRequest(_BackendBase):
    """Which parameter to free next → ``suggestion`` (a ``SuggestionResult``).

    The first **no-solve** task: one Jacobian evaluation at the state the
    models arrive in (their ``vary`` flags are the currently-free set), no
    least squares, no history — so it carries a backend but neither solver
    nor plan, and passing those errors loudly.  Expect
    ``suggestion.best_or_none()`` to be null whenever the evidence does not
    pick one parameter: a converged model suggests nothing, and candidates
    the data cannot separate come back as one unresolved group rather than a
    winner (the indexing contract, one task over).
    """

    task: Literal["suggest"]
    structure: Structure
    instrument: Instrument
    pattern: PatternData
    mode: Mode = "rietveld"
    two_theta_limits: tuple[float, float] | None = None
    top_n: int = Field(5, ge=1, description="ranked groups to return")
    include: str | list[str] = Field("*", description=(
        "dot-path fnmatch globs a candidate must match — same semantics as a "
        "stage's turn_on"))
    exclude: list[str] = Field(default_factory=list, description=(
        "dot-path globs to leave out of the candidate set"))


#: discriminated on ``task`` so a validation failure names one branch's
#: fields, not five branches' worth of noise
AgentRequest = Annotated[
    Union[RefineRequest, MultiRefineRequest, SequentialRefineRequest,
          IndexRequest, SuggestRequest],
    Field(discriminator="task")]
_REQUEST: TypeAdapter = TypeAdapter(AgentRequest)


# ----------------------------------------------------------------------
# response envelope
# ----------------------------------------------------------------------
ERROR_CODES = ("INVALID_REQUEST", "BACKEND_UNAVAILABLE", "REFINEMENT_FAILED")


class AgentErrorDetail(Base):
    """One field-level failure: a dot-path into the request and what is wrong."""

    where: str = ""
    message: str
    type: str = ""


class AgentError(Base):
    """Same grammar as :class:`Diagnostic`: a code to branch on, never text."""

    code: Literal["INVALID_REQUEST", "BACKEND_UNAVAILABLE", "REFINEMENT_FAILED"]
    message: str
    suggestion: str | None = None
    details: list[AgentErrorDetail] = Field(default_factory=list)


class AgentSuccess(Base):
    """Exactly one of ``result``/``series``/``indexing``/``suggestion`` is set
    (which one says what ran).

    Four arms rather than one coerced type, because the four answers are
    structurally different and pretending otherwise is what loses information: a
    joint fit has no history ids *by declaration*, a series has one pair per
    pattern, an indexing run has **no single cell at all**, and a suggestion is
    a ranked, gated list whose only singleton accessor may answer ``None``.
    """

    ok: Literal[True] = True
    result: RefinementResult | None = None
    series: SeriesResult | None = None
    indexing: IndexingResult | None = None
    suggestion: SuggestionResult | None = None
    report: FitReport | None = None
    #: the report at every stage boundary of a ``task="refine"`` run (WP-1058),
    #: one :class:`~rietx.report.StageReport` per completed stage, in the
    #: order they ran.  Empty when the request declined it; **not** a fourth
    #: answer arm and not a different shape — the same FitReport contract
    #: projected onto the states the run passed through, which is why it rides
    #: beside ``report`` instead of replacing it.
    trajectory: list[StageReport] = Field(default_factory=list)
    #: the indexing arm's companion (WP-1043), present exactly when
    #: ``indexing`` is: the same answer projected for a consumer that reasons —
    #: each caveat with its refuting/capping kind (a split that otherwise
    #: lives only in a package constant no JSON reader can see), the ranked
    #: figures beside the ones absent for cause, the three whole-profile
    #: numbers together, and what the search covered.  ``report`` is this
    #: field's twin one arm over.  Additive by decision (WP-1043):
    #: a defaulted field plus one new capping caveat in the vocabulary is the
    #: events rule's "new field, not a new kind", the one deployed consumer
    #: (the GUI) derives caveat kinds from the live constant so a capping
    #: addition costs it nothing, and SCHEMA_VERSION therefore does not move.
    evidence: IndexingEvidence | None = None


class AgentFailure(Base):
    ok: Literal[False] = False
    error: AgentError


_RESPONSE: TypeAdapter = TypeAdapter(Union[AgentSuccess, AgentFailure])

_TASK_TAGS = ("refine", "refine_multi", "refine_sequential", "index",
              "suggest")


def _failure(code: str, message: str, *, suggestion: str | None = None,
             details: list[AgentErrorDetail] | None = None) -> dict:
    return AgentFailure(error=AgentError(
        code=code, message=message, suggestion=suggestion,
        details=details or [])).model_dump(mode="json")


def _validation_failure(exc: ValidationError) -> dict:
    details = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", ())]
        # the tagged union prefixes every location with the branch it tried;
        # strip it so `where` is a dot-path into the request as written
        if loc and loc[0] in _TASK_TAGS:
            loc = loc[1:]
        details.append(AgentErrorDetail(
            where=".".join(loc), message=err.get("msg", ""),
            type=err.get("type", "")))
    return _failure(
        "INVALID_REQUEST",
        f"request failed validation with {len(details)} error(s)",
        suggestion="fix the fields named in details[] (schemas are strict: "
                   "unknown keys are errors, not ignored); request_schema() / "
                   "tool_definition() carry the full contract",
        details=details)


def _dispatch(req: AgentRequest) -> AgentSuccess:
    # indexing first: it is the one branch with no plan, so resolving one below
    # would be resolving a field it does not have
    if isinstance(req, IndexRequest):
        from .indexing import index_pattern

        answer = index_pattern(
            req.peaks, data=req.pattern, instrument=req.instrument,
            spec=req.search.to_spec(), preset=req.search.preset,
            engines=req.engines,
            validate=req.validate_candidates, check_top=req.check_top,
            two_theta_limits=req.two_theta_limits)
        # evidence() is a projection computed here, at serialisation time,
        # from the answer beside it — the two arms cannot disagree
        return AgentSuccess(indexing=answer, evidence=answer.evidence())

    # suggest second, for the same reason: a no-solve task has no plan to
    # resolve, and its read-only contract means no history either
    if isinstance(req, SuggestRequest):
        from .refine import Refinement

        ref = Refinement(req.structure, req.instrument, backend=req.backend,
                         history=False)
        suggestion = ref.suggest(
            req.pattern, top_n=req.top_n, include=req.include,
            exclude=tuple(req.exclude), mode=req.mode,
            two_theta_limits=req.two_theta_limits)
        return AgentSuccess(suggestion=suggestion)

    # staged.resolve_plan applies the same preset→mode mapping fit() uses
    # (mccusker_default becomes profile_only under lebail, pawley_default under
    # pawley), so the plan the veto sees is the plan that actually ran
    from .strategy.staged import resolve_plan

    plan = resolve_plan(
        req.plan if isinstance(req.plan, str) else req.plan.to_plan(),
        getattr(req, "mode", "rietveld"))

    if isinstance(req, RefineRequest):
        from .refine import Refinement

        ref = Refinement(req.structure, req.instrument, backend=req.backend,
                         solver=req.solver, history=req.history_path or False)
        # include_report is the master switch for report *content*: declining
        # the report and being handed one a rung at a time would make the
        # report-off arm of an A/B (WP-1053, WP-1059) not a report-off arm
        trajectory = req.report_trajectory and req.include_report
        result = ref.fit(req.pattern, mode=req.mode, plan=plan,
                         two_theta_limits=req.two_theta_limits,
                         stage_reports=trajectory)
        report = ref.report(plan=plan) if req.include_report else None
        return AgentSuccess(result=result, report=report,
                            trajectory=list(ref.stage_reports_))

    if isinstance(req, MultiRefineRequest):
        from .multi import MultiHistogramRefinement

        ref = MultiHistogramRefinement(
            req.structure, list(req.instruments),
            sharing=req.sharing.to_map() if req.sharing else None,
            backend=req.backend, solver=req.solver)
        result = ref.fit(list(req.patterns), plan=plan,
                         two_theta_limits=req.two_theta_limits,
                         weights=req.weights)
        return AgentSuccess(result=result)

    from .sequential import refine_sequential

    series = refine_sequential(
        list(req.patterns), req.structure, req.instrument,
        carry=list(req.carry), backend=req.backend, solver=req.solver,
        history=req.history_dir or False,
        x=req.x, x_label=req.x_label, labels=req.labels, mode=req.mode,
        plan=plan, refit=req.refit, two_theta_limits=req.two_theta_limits,
        direction=req.direction, reseed=req.reseed)
    return AgentSuccess(series=series)


def refine_json(request: dict) -> dict:
    """Run one refinement request; always returns the envelope, never raises.

    See the module docstring for the contract.  The returned dict is plain
    JSON-serializable data (``model_dump(mode="json")`` throughout — ±inf
    bounds become the strings the schemas already round-trip).
    """
    try:
        req = _REQUEST.validate_python(request)
    except ValidationError as exc:
        return _validation_failure(exc)

    missing = _missing_backend(getattr(req, "backend", "numpy"))
    if missing is not None:
        return _failure("BACKEND_UNAVAILABLE", missing[0], suggestion=missing[1])

    try:
        response = _dispatch(req)
    except Exception as exc:  # noqa: BLE001 — the envelope IS the error channel
        return _failure(
            "REFINEMENT_FAILED", f"{type(exc).__name__}: {exc}",
            suggestion="the request validated but the engine raised; common "
                       "causes are a model the physics refuses (mu_t = 0 in "
                       "reflection geometry, a wavelength on an absorption "
                       "edge with dispersion enabled), a plan freeing "
                       "parameters this model does not have, or a combination "
                       "this build does not support (soft restraints in a "
                       "joint multi-histogram fit)")
    return response.model_dump(mode="json")


def _missing_backend(name: str) -> tuple[str, str] | None:
    """``(message, suggestion)`` when ``name`` cannot run here, else ``None``.

    **Asked before dispatch, and answered by the same authority
    :func:`~rietx.capabilities.capabilities` publishes** (WP-1076).  A backend
    whose optional dependency is not importable is a fact about this *build*,
    knowable without running anything, so the request is refused rather than
    started and abandoned — and a client that read ``capabilities().backends``
    can never be told something different by an attempt.

    It used to be inferred from an exception type, and that was wrong in both
    directions.  ``resolve_backend`` raises ``ImportError`` for a missing
    jax/torch, so the condition this code names came back ``REFINEMENT_FAILED``
    with the generic "the physics refused" advice.  Meanwhile the
    ``NotImplementedError`` the arm caught is raised by unsupported *features*
    — measured: a soft-restrained ``refine_multi`` on ``backend="numpy"``
    returned ``BACKEND_UNAVAILABLE`` advising an install of jax.  An unknown
    backend *name* never reaches either: ``_BackendBase`` validates it against
    the live registry, so that is an ``INVALID_REQUEST``.
    """
    from .capabilities import capabilities

    for cap in capabilities().backends:
        if cap.name == name and not cap.available:
            # `requires` is the extra's name as well as the module's — the two
            # torch devices both require, and install as, `torch`
            return (
                f"backend {name!r} needs the optional {cap.requires} "
                f"dependency, which is not importable in this build",
                f"pip install '{DIST_NAME}[{cap.requires}]' or use "
                "backend='numpy'",
            )
    return None


# ----------------------------------------------------------------------
# JSON Schema export for tool-calling
# ----------------------------------------------------------------------
_TOOL_DESCRIPTION = (
    "Rietveld/Le Bail/Pawley refinement and unit-cell indexing of powder X-ray "
    "diffraction data (rietx). task='refine' fits one pattern and returns the "
    "result and a three-layer FitReport, plus — with report_trajectory=true — "
    "that report at every stage boundary; task='refine_multi' jointly fits N "
    "patterns sharing a structure; task='refine_sequential' chains N patterns by "
    "warm start and returns per-pattern summaries; "
    "task='index' determines the unit cell of an unknown phase from a peak list "
    "or a pattern, running "
    + " and ".join(engine_names())
    + " and gating confidence on their agreement; task='suggest' ranks the "
    "held parameters of a model by predicted chi-squared gain from one "
    "Jacobian evaluation (no fit, no mutation) — use it between fits to "
    "decide what to free next, and read an unresolved group as 'the data "
    "cannot separate these'. Read diagnostics before any "
    "statistic — a warning there outranks Rwp. The operating protocol is "
    "AGENT_PROTOCOL.md — hosted at " + DOCS_URL + "/AGENT_PROTOCOL.md, and "
    "shipped offline in the install as "
    "importlib.resources.files('" + DATA_PACKAGE + "')/'AGENT_PROTOCOL.md'. "
    "For a run you will reason about, request the "
    "trajectory (report_trajectory=true) and READ IT, NOT ONLY THE FINAL "
    "REPORT: the converged report is routinely the least informative one in the run, "
    "because a staged fit can absorb a real error into a compensating "
    "parameter and arrive somewhere that looks converged and suggests nothing. "
    "Each trajectory[] rung is that report at one stage's end — its actions "
    "are the ones the plan you ran will NOT fix, so a rung naming a cause at "
    "high confidence is evidence about the specimen even when the final report "
    "is silent. An indexing answer has NO single cell: read the "
    "evidence arm first (every candidate with each caveat's refuting/capping "
    "kind, the figures that ranked beside the ones absent for cause, and the "
    "Le Bail Rwp with both detector counts), then indexing.candidates for the "
    "full record, and expect best_or_none() to be null unless every engine "
    "agreed and nothing refuted or capped them. Returns "
    "{ok: true, result|series|indexing|suggestion, evidence, report, "
    "trajectory} or "
    "{ok: false, error} with error.code in " + "/".join(ERROR_CODES) + ".")


def request_schema() -> dict:
    """JSON Schema of the request union (what ``refine_json`` accepts)."""
    return _REQUEST.json_schema()


def response_schema() -> dict:
    """JSON Schema of the response envelope (what ``refine_json`` returns)."""
    return _RESPONSE.json_schema()


def tool_definition(name: str = AGENT_TOOL_NAME) -> dict:
    """A ready-to-register LLM tool definition wrapping :func:`refine_json`."""
    return {"name": name, "description": _TOOL_DESCRIPTION,
            "input_schema": request_schema()}
