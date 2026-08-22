"""The serializable mirror of a staged refinement plan — written once.

:class:`strategy.staged.Stage` and :class:`strategy.staged.RefinementPlan` are
dataclasses, constructed positionally (``Stage("cell", ["phases.*.cell.*"])``)
across the plan presets, the tests and the examples; pydantic models have no
positional constructor, so a *mirror* — not a conversion — is what crosses a
JSON boundary (a history node, an agent request, a project file).

Until v1.0 there were **two** mirrors, and the duplication was not merely
redundant — one of them lost data.  ``schemas/history.py`` carried
``from_stage``/``from_plan`` but no ``strain_seed``, reading
``getattr(stage, "seed", 0.0)`` and nothing else, so a Stephens stage's
``strain_seed`` silently round-tripped to **0.0** through the history tree
(un-caught because no Stephens stage had been checked out and re-run).
``agent.py`` carried ``strain_seed`` and the schema descriptions but had no
``from_*`` direction at all.  Both now re-export from here, and
``tests/test_schemas.py`` pins :class:`StageSpec`'s fields against
``dataclasses.fields(Stage)`` so the next field added to ``Stage`` cannot
silently fail to serialize.

``from_stage`` therefore reads every field by direct attribute access: a
``getattr`` default is exactly how the ``strain_seed`` loss was spelled.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from .common import Base

#: What :attr:`PlanSpec.intermediate_ftol` and
#: ``strategy.staged.RefinementPlan.intermediate_ftol`` both default to.
#:
#: **Here, at the lower layer, so the two mirrors quote one literal.**
#: ``strategy.staged`` imports this module and cannot be imported back from it
#: (every crossing in that direction is deferred inside a function), so a
#: constant the pydantic field needs at class-definition time cannot live
#: beside the dataclass.  ``strategy.staged`` re-exports it, which is where a
#: reader looking for plan policy will look; ``tests/test_schemas.py`` pins the
#: two names to one object.
#:
#: An expensive stage's evaluations are almost all *tail* — undamped
#: Gauss-Newton walking a near-degenerate direction (zero ↔ sample displacement
#: ↔ the low-order background terms) at ≈0.93 per iteration, the trust region
#: never binding — and 99.99 % of the stage's cost decrease is banked by
#: evaluation 55 of 93.  An intermediate stage's job is to seed its successor,
#: and the plan is cumulative, so the digits it stops short of are refined
#: again by every later stage: the *last* stage inherits the ridge walk once
#: (cpd-1a ``biso`` 47 → 49 evaluations) instead of every stage polishing it.
#: ``strategy.staged.RefinementPlan.stage_ftols`` is the rule that applies it.
#:
#: 1e-6 costs 1.5-1.7× fewer whole-plan evaluations on the three lab-shaped
#: WP-1111 harness cases, for every non-degenerate parameter within 0.02 esd of
#: the fully-converged plan and QPA fractions within 0.003 wt % (WP-1113
#: measured it, WP-1123 made it the default).  Looser is a real choice and not
#: a silly one — 1e-5 and 1e-4 buy 1.9-2.2× at 0.01-0.2 esd — which is why this
#: is a number a plan carries and not a mode with two positions.
INTERMEDIATE_FTOL = 1e-6


class StageSpec(Base):
    """One stage of a staged plan; the serializable mirror of ``Stage``."""

    name: str
    turn_on: list[str] = Field(
        default_factory=list,
        description="dot-path globs freed this stage, e.g. 'phases.*.cell.*'")
    max_iter: int = Field(100, description=(
        "approximate solver iterations for this stage; TRF caps "
        "evaluations rather than iterations, so it is scaled by the "
        "measured worst-case rejection rate (NFEV_PER_ITERATION)"))
    ftol: float | None = Field(None, gt=0.0, description=(
        "this stage's own relative cost-decrease termination tolerance, "
        "overriding the plan's schedule; null = take it from the plan "
        "(intermediate_ftol for every stage but the last, the solver's 1e-9 "
        "for the last)"))
    lebail_cycles: int = 3
    seed: float = Field(0.0, description=(
        "lift softplus-floored parameters this stage frees to this value "
        "(dead-gradient pathology, e.g. extinction)"))
    strain_seed: float = Field(0.0, description=(
        "microstrain (ppm) to seed an all-zero Stephens block onto the "
        "isotropic ray (exploding-gradient pathology — the opposite fix)"))
    restraint_weight_scale: float = Field(1.0, ge=0.0, description=(
        "c_w of McCusker eq (7), S = S_y + c_w·S_G: this stage's weight on the "
        "geometric restraints against the diffraction data; high early, "
        "reduced as the model improves.  1.0 = no scaling"))
    window_slack_deg: float | None = Field(None, ge=0.0, description=(
        "absolute window capture slack in deg 2-theta this stage compiles "
        "with, replacing the default WINDOW_MIN_DEG — declared by fits whose "
        "start may sit far from the data (the indexing Le Bail validation); "
        "null = the default"))

    @model_validator(mode="before")
    @classmethod
    def _accept_the_dataclass(cls, value: Any) -> Any:
        """A ``Stage`` read as a ``StageSpec`` — see :meth:`PlanSpec._accept_the_dataclass`."""
        from ..strategy.staged import Stage

        return cls.from_stage(value).model_dump() if isinstance(value, Stage) else value

    @classmethod
    def from_stage(cls, stage: Any) -> "StageSpec":
        return cls(name=stage.name, turn_on=list(stage.turn_on),
                   max_iter=stage.max_iter, ftol=stage.ftol,
                   lebail_cycles=stage.lebail_cycles,
                   seed=stage.seed, strain_seed=stage.strain_seed,
                   restraint_weight_scale=stage.restraint_weight_scale,
                   window_slack_deg=stage.window_slack_deg)

    def to_stage(self) -> Any:
        from ..strategy.staged import Stage

        return Stage(name=self.name, turn_on=list(self.turn_on),
                     max_iter=self.max_iter, ftol=self.ftol,
                     lebail_cycles=self.lebail_cycles,
                     seed=self.seed, strain_seed=self.strain_seed,
                     restraint_weight_scale=self.restraint_weight_scale,
                     window_slack_deg=self.window_slack_deg)


class PlanSpec(Base):
    """A staged plan; the serializable mirror of ``RefinementPlan``.

    ``stages`` is deliberately *not* ``min_length=1`` here, because this schema
    also has to read history trees written by earlier versions and a header is
    persisted before the first stage runs.  The agent surface, which validates
    a request a caller is about to spend minutes on, rejects an empty stage
    list in ``agent._RequestBase._known_plan`` instead.
    """

    stages: list[StageSpec] = Field(default_factory=list)
    correlation_guard: float = 0.98
    intermediate_ftol: float | None = Field(
        INTERMEDIATE_FTOL, gt=0.0, description=(
            "the tolerance every stage but the last stops at, unless it "
            "declares its own ftol; null = the solver default (1e-9) "
            "everywhere, i.e. the fully-converged schedule.  1e-6 is "
            "1.5-1.7x fewer whole-plan evaluations for answers within "
            "0.02 esd (WP-1113/1123)"))

    @model_validator(mode="before")
    @classmethod
    def _accept_the_dataclass(cls, value: Any) -> Any:
        """A ``RefinementPlan`` read as a ``PlanSpec`` (WP-1110 item 15).

        The mirror is written once — this module — and it is *crossed* in two
        places, this one inbound and ``strategy.staged.resolve_plan`` outbound.
        Before WP-1110 it was crossed nowhere, so a caller had to know which of
        two same-shaped types each surface wanted: two agents driving the
        trigger dataset took a preset out of ``PLAN_PRESETS``, were answered
        ``INVALID_REQUEST`` by ``refine_json``, and rebuilt the plan field by
        field.  Here rather than in ``agent.py`` because every JSON boundary in
        the package asks the same question — a request, a ``TreeHeader``, a
        ``ProjectDoc`` — and one of them answering differently is the
        duplication ``schemas/plan.py`` exists to end.

        By ``isinstance`` on the real class, never by duck-typing on
        ``.stages``: the two types share **every** field name, which is what
        makes one silently usable where the other is meant.  Measured on this
        tree — ``fit(plan=PlanSpec(...))`` ran to a bit-identical answer through
        the annotation ``RefinementPlan | str``, so a structural test would have
        certified an accident.  The import is local; ``strategy.staged`` imports
        this module.
        """
        from ..strategy.staged import RefinementPlan

        return cls.from_plan(value).model_dump() if isinstance(value, RefinementPlan) else value

    @classmethod
    def from_plan(cls, plan: Any) -> "PlanSpec":
        return cls(stages=[StageSpec.from_stage(s) for s in plan.stages],
                   correlation_guard=plan.correlation_guard,
                   intermediate_ftol=plan.intermediate_ftol)

    def to_plan(self) -> Any:
        from ..strategy.staged import RefinementPlan

        return RefinementPlan(stages=[s.to_stage() for s in self.stages],
                              correlation_guard=self.correlation_guard,
                              intermediate_ftol=self.intermediate_ftol)

    def preset_name(self) -> str | None:
        """The registered preset this plan equals, or ``None`` if it was edited.

        **Derived, never stored.**  A project records the *expanded* plan (that
        is what will run, verbatim), so "which preset was this?" has no field to
        read — and adding one would be a second authority that can disagree with
        the stages beside it.  Two consumers already ask: the GUI's plan editor,
        which labels the menu, and the text document, which prints
        ``plan mccusker_default`` instead of eight stage lines.
        """
        from ..strategy.staged import PLAN_PRESETS

        for name, build in PLAN_PRESETS.items():
            if PlanSpec.from_plan(build()) == self:
                return name
        return None
