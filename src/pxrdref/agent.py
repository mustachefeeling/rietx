"""Single-call JSON surface for driving pxrdref from an agent (WP-0602).

``refine_json(dict) → dict`` is the whole API: a typed request in, either a
serialized result or a structured error out, never a raw traceback.  The
envelope is deliberate:

- success: ``{"ok": true, "result": …, "series": …, "report": …}`` — exactly
  one of ``result``/``series`` is set, so a consumer branches on which, and
  the two top-level result types (a refinement vs a warm-started series,
  WP-0505) stay structurally distinct instead of being coerced into one.
- failure: ``{"ok": false, "error": {code, message, suggestion, details}}`` —
  the same grammar as :class:`~pxrdref.schemas.common.Diagnostic`, so an agent
  has one vocabulary for "the fit warns" and "the call failed".  Three codes,
  closed: ``INVALID_REQUEST`` (any validation failure, with per-field
  dot-paths in ``details``), ``BACKEND_UNAVAILABLE`` (a valid backend name
  whose optional dependency is not installed), ``REFINEMENT_FAILED`` (the
  request was valid but the engine raised).

Two asymmetries are answered here on purpose rather than by accident:
``task="refine_multi"`` runs **without** the history DAG (a multi-pattern
fingerprint is a future seam — WP-0308), so its ``node_id``/``tree_id`` are
always null and the field description says so; a series has **one history
tree per pattern**, so its ids live on each entry and there is no run-level
pair.

``task="index"`` (WP-1024) is the fourth branch and the only one that is not a
refinement.  It answers with an ``indexing`` arm rather than ``result``/``series``
for the same reason those two are distinct: an
:class:`~pxrdref.schemas.indexing.IndexingResult` is a different kind of answer,
and its **shape** is load-bearing — it has no ``.cell``, so a consumer must go
through ``candidates`` or ``best_or_none()`` and cannot be handed a confident wrong
singleton by the envelope either.

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

from .backend.api import BACKEND_NAMES

# importing the package (not ``.indexing.engines``) is what registers the engines,
# so the names quoted below are the ones ``index_pattern`` would actually run
from .indexing import SYSTEM_ORDER, engine_descriptions, engine_names
from .optimize.least_squares import SOLVERS
from .params.multi import SharingMap
from .report.schemas import FitReport
from .schemas.common import Base, Mode
from .schemas.indexing import IndexingResult, PeakList
from .schemas.instrument import Instrument
from .schemas.pattern import PatternData

# one plan schema for the whole package (WP-1004): this module used to define a
# second ``StageSpec``/``PlanSpec`` pair that had drifted from the history one
from .schemas.plan import PlanSpec, StageSpec  # noqa: F401
from .schemas.results import RefinementResult
from .schemas.sequential import SeriesResult
from .schemas.structure import Structure
from .strategy.staged import PLAN_PRESETS

# ----------------------------------------------------------------------
# vocabularies quoted from the live registries (never restated literals)
# ----------------------------------------------------------------------
_BACKEND_DESC = (
    "Jacobian backend, validated against the live registry (currently: "
    + ", ".join(BACKEND_NAMES)
    + "); 'numpy' is the default and the only one a single pattern needs")
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
_SYSTEM_DESC = (
    "crystal systems to search (default: all, in decreasing symmetry — "
    + ", ".join(SYSTEM_ORDER)
    + "). A restricted search is not a verdict: the result reports "
    "systems_searched and INDEX_SYSTEMS_NOT_COVERED rather than concluding "
    "anything about the specimen")


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


class _RequestBase(Base):
    backend: str = Field("numpy", description=_BACKEND_DESC)
    solver: str = Field("trf", description=_SOLVER_DESC)
    plan: str | PlanSpec = Field("mccusker_default", description=_PLAN_DESC)

    @field_validator("backend")
    @classmethod
    def _known_backend(cls, v: str) -> str:
        if v not in BACKEND_NAMES:
            raise ValueError(f"unknown backend {v!r}; "
                             f"available: {', '.join(BACKEND_NAMES)}")
        return v

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


class SearchSpecSpec(Base):
    """Mirrors ``indexing.engines.SearchSpec``; every engine reads the same one.

    Flat and complete rather than a handful of convenience knobs, because the
    engines' **agreement** is the confidence and that only means something if they
    were given identical bounds: a per-engine option would make ``high`` a
    statement about two different searches.
    """

    systems: list[str] | None = Field(None, description=_SYSTEM_DESC)
    min_d_axis: float = Field(2.0, gt=0.0, description=(
        "shortest principal d-spacing (Å) to consider — a bound on d(100), which "
        "for an oblique cell is slightly stronger than a bound on a"))
    max_d_axis: float = Field(25.0, gt=0.0, description=(
        "longest principal d-spacing (Å); raising it costs exponentially, since "
        "domain size is what an exhaustive search pays for"))
    min_volume: float = Field(15.0, gt=0.0)
    max_volume: float | None = Field(None, description=(
        "cell-volume ceiling (Å³); None takes Smith's (1977) per-system envelope "
        "from the data-quality report, which differs by up to 96x across systems"))
    n_unindexed: int = Field(2, ge=0, description=(
        "search lines a cell may leave unindexed and still be accepted. Raising "
        "it MANUFACTURES cells — every tolerated line is one more coincidence a "
        "wrong metric is allowed — so 2 is a default and 4 is a statement about "
        "the specimen"))
    n_search_lines: int = Field(20, ge=2)
    k_sigma: float = Field(3.0, gt=0.0, description=(
        "matching window in units of each line's own sigma; 3 is a calibrated "
        "99.7 % window, not a knob"))
    sigma_sys_deg: float = Field(0.0, ge=0.0, description=(
        "systematic 2theta allowance (deg) you have MEASURED, e.g. from an "
        "internal standard. Leave 0 and the engines assume 0.05 deg and say so "
        "with INDEX_SHIFT_ALLOWANCE — which caps confidence, because a cell found "
        "inside a widened window absorbs the shift (+1400 ppm measured)"))
    shift_template: str | None = Field(None, description=(
        "'constant' | 'cos_theta' | 'sin_2theta' — re-fit a surviving candidate "
        "with this shift column, which is the fix for the allowance above; a "
        "shift is only identifiable against reference positions and a candidate "
        "cell is what supplies them"))
    budget_seconds: float = Field(30.0, gt=0.0, description=(
        "wall clock per (engine x crystal system) SLICE of the search, not per "
        "run: a default two-engine, seven-system call is up to 2x7x30 s of "
        "search before the probe and validation. An engine stopped by it "
        "reports search_complete[system] = false, and a negative result there "
        "is not evidence. total_budget_seconds is the whole-run bound"))
    total_budget_seconds: float | None = Field(None, gt=0.0, description=(
        "wall-clock ceiling for the WHOLE run — search, probe and validation "
        "together. The run still returns a complete IndexingResult over what "
        "was reached; systems_searched/search_complete distinguish searched, "
        "truncated and not reached, and INDEX_BUDGET_EXHAUSTED names them. "
        "None (default) bounds nothing beyond the per-slice budget_seconds"))
    max_candidates: int = Field(12, ge=1)
    seed: int = 0

    @field_validator("systems")
    @classmethod
    def _known_systems(cls, v):
        for name in v or ():
            if name not in SYSTEM_ORDER:
                raise ValueError(f"unknown crystal system {name!r}; "
                                 f"available: {', '.join(SYSTEM_ORDER)}")
        return v

    @field_validator("shift_template")
    @classmethod
    def _known_template(cls, v):
        from .schemas.indexing import SHIFT_TEMPLATES

        if v is not None and v not in SHIFT_TEMPLATES:
            raise ValueError(f"unknown shift template {v!r}; "
                             f"available: {', '.join(SHIFT_TEMPLATES)}")
        return v

    def to_spec(self):
        from .indexing import SearchSpec

        return SearchSpec(
            systems=tuple(self.systems) if self.systems else SYSTEM_ORDER,
            min_d_axis=self.min_d_axis, max_d_axis=self.max_d_axis,
            min_volume=self.min_volume, max_volume=self.max_volume,
            n_unindexed=self.n_unindexed, n_search_lines=self.n_search_lines,
            k_sigma=self.k_sigma, sigma_sys_deg=self.sigma_sys_deg,
            shift_template=self.shift_template,
            budget_seconds=self.budget_seconds,
            total_budget_seconds=self.total_budget_seconds,
            max_candidates=self.max_candidates, seed=self.seed)


class IndexRequest(Base):
    """Unit-cell determination → ``indexing`` (an ``IndexingResult``).

    Not a refinement, so it carries no backend, solver or plan.  Give it
    ``peaks``, or a ``pattern`` + ``instrument`` pair it will pick peaks from —
    and prefer the second, because supplying a pattern is what turns **whole-
    profile validation** on.  Without one every candidate caps at ``"medium"`` and
    ``INDEX_NOT_VALIDATED`` fires: the figure-of-merit panel sees at most 20 lines
    and is blind to lines beyond them, to impurity content, and to reflections
    predicted where there is no intensity.

    Read ``indexing.candidates`` and each one's ``confidence_caveats``; call
    ``best_or_none()`` for a singleton and expect ``None`` more often than not.
    """

    task: Literal["index"]
    peaks: PeakList | None = Field(None, description=(
        "a fitted peak list (pxrdref.pick_peaks output, or "
        "PeakList.from_positions for bare positions from a publication)"))
    pattern: PatternData | None = Field(None, description=(
        "the pattern; supplying it enables Le Bail validation and lets peaks be "
        "picked when `peaks` is absent"))
    instrument: Instrument | None = Field(None, description=(
        "required with `pattern`; also what makes the cell's Bragg-Brentano "
        "systematic quantifiable (INDEX_CELL_SYSTEMATIC_UNQUANTIFIED)"))
    engines: list[str] | None = Field(None, description=_ENGINE_DESC)
    search: SearchSpecSpec = Field(default_factory=SearchSpecSpec)
    two_theta_limits: tuple[float, float] | None = None
    validate_candidates: bool = Field(True, description=(
        "run the whole-profile Le Bail validation when a pattern is available; "
        "turning it off caps every candidate at medium, so do it only to save "
        "time on a first look"))

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


#: discriminated on ``task`` so a validation failure names one branch's
#: fields, not four branches' worth of noise
AgentRequest = Annotated[
    Union[RefineRequest, MultiRefineRequest, SequentialRefineRequest,
          IndexRequest],
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
    """Exactly one of ``result``/``series``/``indexing`` is set (which one says
    what ran).

    Three arms rather than one coerced type, because the three answers are
    structurally different and pretending otherwise is what loses information: a
    joint fit has no history ids *by declaration*, a series has one pair per
    pattern, and an indexing run has **no single cell at all**.
    """

    ok: Literal[True] = True
    result: RefinementResult | None = None
    series: SeriesResult | None = None
    indexing: IndexingResult | None = None
    report: FitReport | None = None


class AgentFailure(Base):
    ok: Literal[False] = False
    error: AgentError


_RESPONSE: TypeAdapter = TypeAdapter(Union[AgentSuccess, AgentFailure])

_TASK_TAGS = ("refine", "refine_multi", "refine_sequential", "index")


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

        return AgentSuccess(indexing=index_pattern(
            req.peaks, data=req.pattern, instrument=req.instrument,
            spec=req.search.to_spec(), engines=req.engines,
            validate=req.validate_candidates,
            two_theta_limits=req.two_theta_limits))

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
        result = ref.fit(req.pattern, mode=req.mode, plan=plan,
                         two_theta_limits=req.two_theta_limits)
        report = ref.report(plan=plan) if req.include_report else None
        return AgentSuccess(result=result, report=report)

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

    try:
        response = _dispatch(req)
    except NotImplementedError as exc:
        # a *valid* backend name whose optional dependency is absent: the
        # constructors fail fast with the install hint, which we pass along
        return _failure("BACKEND_UNAVAILABLE", str(exc),
                        suggestion="install the optional dependency "
                                   "(pip install 'pxrd-refine[jax]' or "
                                   "'[torch]') or use backend='numpy'")
    except Exception as exc:  # noqa: BLE001 — the envelope IS the error channel
        return _failure(
            "REFINEMENT_FAILED", f"{type(exc).__name__}: {exc}",
            suggestion="the request validated but the engine raised; common "
                       "causes are a model the physics refuses (mu_t = 0 in "
                       "reflection geometry, a wavelength on an absorption "
                       "edge with dispersion enabled) or a plan freeing "
                       "parameters this model does not have")
    return response.model_dump(mode="json")


# ----------------------------------------------------------------------
# JSON Schema export for tool-calling
# ----------------------------------------------------------------------
_TOOL_DESCRIPTION = (
    "Rietveld/Le Bail/Pawley refinement and unit-cell indexing of powder X-ray "
    "diffraction data (pxrdref). task='refine' fits one pattern and returns the "
    "result plus a three-layer FitReport; task='refine_multi' jointly fits N "
    "patterns sharing a structure; task='refine_sequential' chains N patterns by "
    "warm start and returns per-pattern summaries with trajectories; "
    "task='index' determines the unit cell of an unknown phase from a peak list "
    "or a pattern, running "
    + " and ".join(engine_names())
    + " and gating confidence on their agreement. Read diagnostics before any "
    "statistic — a warning there outranks Rwp (docs/AGENT_PROTOCOL.md is the "
    "operating protocol). An indexing answer has NO single cell: read "
    "indexing.candidates and each one's confidence_caveats, and expect "
    "best_or_none() to be null unless both engines agreed and nothing refuted "
    "them. Returns {ok: true, result|series|indexing, report} or "
    "{ok: false, error} with error.code in " + "/".join(ERROR_CODES) + ".")


def request_schema() -> dict:
    """JSON Schema of the request union (what ``refine_json`` accepts)."""
    return _REQUEST.json_schema()


def response_schema() -> dict:
    """JSON Schema of the response envelope (what ``refine_json`` returns)."""
    return _RESPONSE.json_schema()


def tool_definition(name: str = "pxrdref_refine") -> dict:
    """A ready-to-register LLM tool definition wrapping :func:`refine_json`."""
    return {"name": name, "description": _TOOL_DESCRIPTION,
            "input_schema": request_schema()}
