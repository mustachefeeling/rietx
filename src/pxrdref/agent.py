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

``request_schema()`` / ``response_schema()`` / ``tool_definition()`` export
the JSON Schemas an LLM tool-calling loop needs.  The backend, solver and
plan vocabularies are validated against the **live registries**
(``backend.api.BACKEND_NAMES``, ``optimize.least_squares.SOLVERS``,
``strategy.staged.PLAN_PRESETS``) and the schema descriptions are built from
the same tuples at import time — a restated literal union is exactly what
went stale two days after the torch backend landed (see WP-0408's note).

The MCP server wrapping this call — and with it any file-path or CIF-text
convenience — stays fenced in v2; this surface takes typed objects only.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, TypeAdapter, ValidationError, field_validator, model_validator

from .backend.api import BACKEND_NAMES
from .optimize.least_squares import SOLVERS
from .params.multi import SharingMap
from .report.schemas import FitReport
from .schemas.common import Base, Mode
from .schemas.instrument import Instrument
from .schemas.pattern import PatternData
from .schemas.results import RefinementResult
from .schemas.sequential import SeriesResult
from .schemas.structure import Structure
from .strategy.staged import PLAN_PRESETS, RefinementPlan, Stage

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


class StageSpec(Base):
    """One stage of a hand-rolled plan; mirrors ``strategy.staged.Stage``."""

    name: str
    turn_on: list[str] = Field(
        description="dot-path globs freed this stage, e.g. 'phases.*.cell.*'")
    max_iter: int = 100
    lebail_cycles: int = 3
    seed: float = Field(0.0, description=(
        "lift softplus-floored parameters this stage frees to this value "
        "(dead-gradient pathology, e.g. extinction)"))
    strain_seed: float = Field(0.0, description=(
        "microstrain (ppm) to seed an all-zero Stephens block onto the "
        "isotropic ray (exploding-gradient pathology — the opposite fix)"))

    def to_stage(self) -> Stage:
        return Stage(self.name, list(self.turn_on), max_iter=self.max_iter,
                     lebail_cycles=self.lebail_cycles, seed=self.seed,
                     strain_seed=self.strain_seed)


class PlanSpec(Base):
    """An explicit staged plan, for when no preset fits (state why)."""

    stages: list[StageSpec] = Field(min_length=1)
    correlation_guard: float = 0.98

    def to_plan(self) -> RefinementPlan:
        return RefinementPlan(stages=[s.to_stage() for s in self.stages],
                              correlation_guard=self.correlation_guard)


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


#: discriminated on ``task`` so a validation failure names one branch's
#: fields, not three branches' worth of noise
AgentRequest = Annotated[
    Union[RefineRequest, MultiRefineRequest, SequentialRefineRequest],
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
    """Exactly one of ``result``/``series`` is set (which one says what ran)."""

    ok: Literal[True] = True
    result: RefinementResult | None = None
    series: SeriesResult | None = None
    report: FitReport | None = None


class AgentFailure(Base):
    ok: Literal[False] = False
    error: AgentError


_RESPONSE: TypeAdapter = TypeAdapter(Union[AgentSuccess, AgentFailure])

_TASK_TAGS = ("refine", "refine_multi", "refine_sequential")


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
    # sequential._resolve_plan applies the same preset→mode mapping fit() uses
    # (mccusker_default becomes profile_only under lebail, pawley_default under
    # pawley), so the plan the veto sees is the plan that actually ran
    from .sequential import _resolve_plan

    plan = _resolve_plan(
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
    "Rietveld/Le Bail/Pawley refinement of powder X-ray diffraction data "
    "(pxrdref). task='refine' fits one pattern and returns the result plus a "
    "three-layer FitReport; task='refine_multi' jointly fits N patterns "
    "sharing a structure; task='refine_sequential' chains N patterns by warm "
    "start and returns per-pattern summaries with trajectories. Read "
    "result.diagnostics before any statistic — a warning there outranks Rwp "
    "(docs/AGENT_PROTOCOL.md is the operating protocol). Returns "
    "{ok: true, result|series, report} or {ok: false, error} with error.code "
    "in " + "/".join(ERROR_CODES) + ".")


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
