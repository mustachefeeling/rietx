"""Schemas for the refinement history DAG.

A refinement is a walk through parameter space made of discrete, addressable
steps.  Each node records the *state* the refinement was in — enough to
reconstruct it exactly — plus the action that produced it and the agreement
statistics it achieved.  Nodes are immutable; named refs (``head``, tags) are
the mutable pointers into them, the split git uses between objects and refs.

Nodes deliberately store **state, not results**: ``y_calc`` and the agreement
indices are a pure function of ``(state, pattern)`` and are recomputed on
demand.  On the 11-BM NAC acceptance case a state-only node is ~10 kB against
~1.24 MB for one carrying the fitted curves, which is what makes wide
branching (and tree search) affordable.

Branch points sit at stage boundaries because that is where the compiled model
is legitimately regenerated — the frozen-per-stage discreteness invariant (see
``model/forward.py``) forbids changing the reflection list, symmetry-op
subsets, FCJ node counts or window ranges *within* a least-squares run.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import SCHEMA_VERSION, Base, Diagnostic, Mode
from .instrument import Instrument

# ``StageSpec``/``PlanSpec`` used to be *defined* here, in parallel with a second
# copy in ``agent.py`` that had a ``strain_seed`` field this one lacked — so a
# Stephens stage lost its seed on the way through a history tree.  One schema
# lives in ``schemas/plan.py`` (WP-1004); the compat re-export was deleted
# pre-freeze (WP-1003), so import both from there.
from .params import TieSpec
from .plan import PlanSpec
from .results import Statistics
from .structure import Structure

NodeKind = Literal["root", "stage", "set_vary", "set_value", "set_tie",
                   "edit_model", "lebail_update", "merge"]


class NodeAction(Base):
    """The edge operation that produced a node from its parent(s).

    For a ``"stage"`` action the fields are the stage's *own* arguments, because
    ``Refinement.cherry_pick`` reconstructs a ``Stage`` from them and re-runs it
    elsewhere — so a field missing here is a stage that replays differently from
    the one recorded.  ``seed``/``strain_seed`` were added in WP-1004 for exactly
    that reason: without them a cherry-picked extinction stage left its softplus
    coefficient on the dead-gradient floor, and a Stephens stage started from the
    all-zero block the seed exists to avoid.  Both are additive with a 0.0
    default, which is the no-seed behaviour, so pre-v1.0 nodes replay unchanged.
    ``restraint_weight_scale`` (WP-1074) is the same rule for eq (7)'s c_w: a
    stiff early stage cherry-picked without it would run its restraints at the
    weight the *schedule* had already relaxed to.  Additive with a 1.0 default,
    which is the no-scaling behaviour.

    ``ties``/``untied`` (WP-1070) are the ``"set_tie"`` action's own arguments,
    additive under the same rule.  They record what the action *did*, not the
    state it left: the whole tie register lives on
    :attr:`RefinementState.ties`, which is what a checkout restores — exactly as
    ``turn_on`` describes a ``set_vary`` whose result is read off ``free_paths``.
    """

    kind: NodeKind
    name: str = ""
    turn_on: list[str] = Field(default_factory=list)
    turn_off: list[str] = Field(default_factory=list)
    values: dict[str, float] = Field(default_factory=dict)
    max_iter: int = 100
    lebail_cycles: int = 3
    seed: float = 0.0
    strain_seed: float = 0.0
    restraint_weight_scale: float = 1.0
    ties: dict[str, TieSpec] = Field(default_factory=dict)
    untied: list[str] = Field(default_factory=list)

    def api_call(self) -> str:
        """The equivalent public-API call, so a log doubles as a session script.

        Computed rather than stored: a persisted copy would drift out of sync
        with the structured fields it describes.
        """
        if self.kind == "root":
            return "rx.Refinement(structure, instrument)"
        if self.kind == "stage":
            # each extra is printed only when it differs from the Stage default,
            # so a plain stage's line keeps its pre-WP-1004 text exactly
            extras = "".join(
                f", {n}={v!r}" for n, v, off in
                (("seed", self.seed, 0.0),
                 ("strain_seed", self.strain_seed, 0.0),
                 ("restraint_weight_scale", self.restraint_weight_scale, 1.0))
                if v != off)
            return (f"ref.run_stage(data, rx.Stage({self.name!r}, {self.turn_on!r}, "
                    f"max_iter={self.max_iter}{extras}))")
        if self.kind == "set_vary":
            parts = []
            if self.turn_on:
                parts.append(f"ref.set_vary({self.turn_on!r}, True)")
            if self.turn_off:
                parts.append(f"ref.set_vary({self.turn_off!r}, False)")
            return "; ".join(parts)
        if self.kind == "set_value":
            return f"ref.set_values({self.values!r})"
        if self.kind == "set_tie":
            parts = []
            for path, spec in self.ties.items():
                if len(spec.terms) != 1:
                    # no public verb declares a multi-source tie, so the log
                    # says so rather than rendering a call that does not exist
                    parts.append(f"# {path} = {spec.describe()}")
                    continue
                src, scale = spec.terms[0]
                args = f"{path!r}, {src!r}"
                if scale != 1.0:
                    args += f", scale={scale!r}"
                if spec.const:
                    args += f", offset={spec.const!r}"
                parts.append(f"ref.tie({args})")
            if self.untied:
                parts.append(f"ref.untie({self.untied!r})")
            return "; ".join(parts)
        if self.kind == "lebail_update":
            return f"ref.lebail_update(n_cycles={self.lebail_cycles})"
        if self.kind == "merge":
            return f"ref.merge(...)  # {self.name}"
        return f"# model edited: {self.name or 'structure/instrument replaced'}"


class ReflectionState(Base):
    """Per-hkl intensities, the state that is *not* in the parameter vector.

    Le Bail (Le Bail, Duroy & Fourquet, 1988, Mater. Res. Bull. 23, 447)
    extracts intensities by iterated partitioning of the observed profile.
    They are seeded flat and refined by a fixed-point loop, so they are
    **path-dependent**: they cannot be recovered from
    ``(structure, instrument, pattern)`` alone, and storing them is a
    correctness requirement for restoring a Le Bail checkpoint, not an
    optimisation.

    Pawley (1981, J. Appl. Cryst. 14, 357) puts the same quantities *into* the
    parameter vector instead.  Both live here, tagged by ``kind``, so that the
    v0.3 Pawley mode does not have to push one dot-path per reflection into
    :attr:`RefinementState.free_paths` on every node.
    """

    phase_index: int
    hkl: list[list[int]] = Field(default_factory=list)  # (N, 3)
    intensity: list[float] = Field(default_factory=list)  # (N,)
    kind: Literal["lebail_extracted", "pawley_refined"] = "lebail_extracted"
    stderr: list[float] | None = None  # Pawley has esds; Le Bail does not
    varied: bool = False  # were these free in θ?


class RefinementState(Base):
    """Everything needed to reconstruct a refinement exactly."""

    structure: Structure
    instrument: Instrument
    mode: Mode = "rietveld"
    # Named scalar parameters only — never one entry per reflection.
    # ``apply_to_models`` writes values but not vary flags, so the free set has
    # to be carried alongside the models.
    free_paths: list[str] = Field(default_factory=list)
    two_theta_limits: tuple[float, float] | None = None
    reflections: list[ReflectionState] = Field(default_factory=list)
    # User constraints (WP-1070), path → the affine dependence declared for it.
    # Carried for the same reason as ``free_paths``: a tie is not a property of
    # the models — ``ParameterTable`` derives the *symmetry* ties from the space
    # group on every build and knows nothing about a user's — so a node that did
    # not carry them would restore a state with the constraints silently gone,
    # and the parameter count with them.
    ties: dict[str, TieSpec] = Field(default_factory=dict)


class NodeMetrics(Base):
    """Cached scalars so queries (``best``, ``compare``) need no recompute.

    These are *as-optimised* values: the agreement the least squares actually
    reached on the model it was minimising, whose reflection list, windows and
    FCJ node counts were frozen at the parameter values the stage *started*
    from.  Recomputing the same state with a fresh compile (``refine.replay``)
    can differ slightly, because the refreshed freeze is built at the values
    the stage *ended* on.

    The gap is itself informative: a large one means the stage travelled far
    enough that its frozen discreteness went stale, which is a reason to split
    the stage rather than a bug.
    """

    statistics: Statistics | None = None
    status: Literal["converged", "max_iter", "diverged", "skipped"] | None = None
    n_iterations: int = 0
    cost_initial: float | None = None
    cost_final: float | None = None
    stderr: dict[str, float] = Field(default_factory=dict)  # physical esds by path


class HistoryNode(Base):
    """One immutable checkpoint in the refinement DAG."""

    id: str
    # A list, not a scalar: combining branches ("cell from A, background from
    # B") is a genuine refinement move with two parents.  Allowing it in the
    # schema costs nothing now; retrofitting it would be a format break.
    parents: list[str] = Field(default_factory=list)
    action: NodeAction
    state: RefinementState
    metrics: NodeMetrics = Field(default_factory=NodeMetrics)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    label: str = ""
    created_utc: str = ""
    scores: dict[str, float] = Field(default_factory=dict)  # agent bookkeeping
    notes: dict[str, str] = Field(default_factory=dict)

    @property
    def parent(self) -> str | None:
        return self.parents[0] if self.parents else None

    @property
    def rwp(self) -> float | None:
        return self.metrics.statistics.rwp if self.metrics.statistics else None


class TreeHeader(Base):
    """Identifies the tree and the pattern every node is fitted against."""

    tree_id: str
    created_utc: str = ""
    data_fingerprint: str = ""  # sha256 of two_theta + intensity bytes
    data_source: str = ""
    n_points: int = 0
    plan: PlanSpec | None = None
    package_version: str = ""
    schema_version: str = SCHEMA_VERSION


class Annotation(Base):
    """An append-only overlay: labels, refs and scores, applied after nodes."""

    node_id: str = ""
    label: str | None = None
    refs: dict[str, str] = Field(default_factory=dict)  # name → node id
    scores: dict[str, float] = Field(default_factory=dict)
    notes: dict[str, str] = Field(default_factory=dict)


class HistoryRecord(Base):
    """One JSONL line.  Tagged union so the log stays append-only."""

    record: Literal["header", "node", "annotation"]
    header: TreeHeader | None = None
    node: HistoryNode | None = None
    annotation: Annotation | None = None
