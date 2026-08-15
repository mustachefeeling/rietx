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

from pydantic import Field

from .common import Base


class StageSpec(Base):
    """One stage of a staged plan; the serializable mirror of ``Stage``."""

    name: str
    turn_on: list[str] = Field(
        default_factory=list,
        description="dot-path globs freed this stage, e.g. 'phases.*.cell.*'")
    max_iter: int = 100
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

    @classmethod
    def from_stage(cls, stage: Any) -> "StageSpec":
        return cls(name=stage.name, turn_on=list(stage.turn_on),
                   max_iter=stage.max_iter, lebail_cycles=stage.lebail_cycles,
                   seed=stage.seed, strain_seed=stage.strain_seed,
                   restraint_weight_scale=stage.restraint_weight_scale)

    def to_stage(self) -> Any:
        from ..strategy.staged import Stage

        return Stage(name=self.name, turn_on=list(self.turn_on),
                     max_iter=self.max_iter, lebail_cycles=self.lebail_cycles,
                     seed=self.seed, strain_seed=self.strain_seed,
                     restraint_weight_scale=self.restraint_weight_scale)


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

    @classmethod
    def from_plan(cls, plan: Any) -> "PlanSpec":
        return cls(stages=[StageSpec.from_stage(s) for s in plan.stages],
                   correlation_guard=plan.correlation_guard)

    def to_plan(self) -> Any:
        from ..strategy.staged import RefinementPlan

        return RefinementPlan(stages=[s.to_stage() for s in self.stages],
                              correlation_guard=self.correlation_guard)

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
