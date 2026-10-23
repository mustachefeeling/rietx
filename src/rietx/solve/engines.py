"""The solve run's settings, its engine registry and its presets (#562 S2b; WP number pending).

:class:`SolveSpec` is the engine-side settings object, as
:class:`~rietx.indexing.engines.SearchSpec` is indexing's; its request chair
is :class:`~rietx.solve.solution.SolveSpecSpec`, and the two convert into
each other exactly (``tests/test_solve_entry.py``).

**Seeds are indices, and a unit's generator is derived, never hashed**
(:func:`unit_seed`): unit k of kind K draws from
``numpy.random.SeedSequence([spec.seed, K, k])``, so seed 2 runs the same chain
in a four-seed run and in a process that runs seed 2 alone, which is what lets
:func:`~rietx.solve.workflow.merge_seed_results` reproduce the in-process
consensus from per-seed results.  Python's ``hash()`` of a name is salted per
process and is never used (indexing's ``SearchSpec.seed`` rule).

**The registry** lists the engines a run may name, each with one line saying
what it suits; ``capabilities().solve_engines`` quotes it live.  One engine
today, ``tempering`` (S2a's parallel tempering); charge flipping is S6's.

**The presets** (:data:`SOLVE_PRESETS`, :data:`SOLVE_PRESET_INFO`, a bijection
by test, quoted by ``capabilities().solve_presets``): ``quick`` is the default,
a whole-run ceiling of the architecture's 600 s (WP-1515's 2026-09-29 plan,
the twin of indexing's ``quick``), which a binding run reports as status
``"budget"`` with what it did not reach; ``full`` has no ceiling.  A declared
``total_budget_seconds`` is never overridden and runs as ``custom``.

Nothing here is exported from :mod:`rietx`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, fields, replace

import numpy as np

#: Unit kinds in the derived generator seed (:func:`unit_seed`): the position
#: of each in this tuple is its code, so the tuple is append-only.
UNIT_KINDS = ("seed", "control", "race", "ladder")


@dataclass(frozen=True)
class SolveSpec:
    """What one solve run is asked to do (field meanings: ``help.SOLVE_FIELD_HELP``).

    ``sweeps`` is each seed's and control seed's length; ``race_sweeps`` the
    first race round's, doubled each round; ``heartbeat_sweeps`` the
    ``solve_step`` cadence; ``checkpoint_every_s`` the shortest interval
    between two checkpoint writes at the engine's boundaries (a finished unit
    always writes); ``total_budget_seconds`` the whole-run ceiling, ``None``
    for none."""

    engine: str = "tempering"
    seeds: tuple[int, ...] = (0, 1, 2, 3)
    control_seeds: tuple[int, ...] = (0, 1)
    replicas: int = 6
    sweeps: int = 20000
    race_sweeps: int = 2000
    heartbeat_sweeps: int = 1000
    checkpoint_every_s: float = 60.0
    total_budget_seconds: float | None = None
    seed: int = 0

    def __post_init__(self):
        # seed indices are a set: sorted, so a run and its merge name them alike
        object.__setattr__(self, "seeds", tuple(sorted(self.seeds)))
        object.__setattr__(self, "control_seeds", tuple(sorted(self.control_seeds)))
        if self.replicas < 2:
            raise ValueError("a ladder needs at least two replicas")
        for name in ("sweeps", "race_sweeps", "heartbeat_sweeps"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")
        if len(set(self.seeds)) != len(self.seeds) or len(set(self.control_seeds)) != len(
                self.control_seeds):
            raise ValueError("a seed index appears twice")

    def to_spec_spec(self):
        from .solution import SolveSpecSpec

        return SolveSpecSpec(**{f.name: (list(getattr(self, f.name))
                                         if isinstance(getattr(self, f.name), tuple)
                                         else getattr(self, f.name))
                                for f in fields(self)})


def unit_seed(spec: SolveSpec, kind: str, index: int) -> int:
    """The generator seed of unit ``index`` of ``kind`` (module docstring)."""
    ss = np.random.SeedSequence([int(spec.seed), UNIT_KINDS.index(kind), int(index)])
    return int(ss.generate_state(1, dtype=np.uint32)[0])


# ----------------------------------------------------------------------
# the registry
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class EngineEntry:
    name: str
    description: str
    run: Callable = field(compare=False)


_REGISTRY: dict[str, EngineEntry] = {}


def register_engine(name: str, run: Callable, description: str) -> Callable:
    _REGISTRY[name] = EngineEntry(name, description, run)
    return run


def engine_names() -> tuple[str, ...]:
    """Registered engines, in registration order."""
    _load()
    return tuple(_REGISTRY)


def engine_descriptions() -> dict[str, str]:
    _load()
    return {k: v.description for k, v in _REGISTRY.items()}


def get_engine(name: str) -> EngineEntry:
    _load()
    if name not in _REGISTRY:
        raise ValueError(f"unknown solve engine {name!r}; registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def _load() -> None:
    from . import workflow  # noqa: F401  (registers the engines)


# ----------------------------------------------------------------------
# presets
# ----------------------------------------------------------------------
#: The fields each preset sets; everything else is :class:`SolveSpec`'s default.
SOLVE_PRESETS: dict[str, dict] = {
    "quick": {"total_budget_seconds": 600.0},
    "full": {"total_budget_seconds": None},
}

SOLVE_PRESET_INFO: dict[str, str] = {
    "quick": ("The default: every seed and control seed under a whole-run ceiling of 600 s; "
              "a run the ceiling stops is graded partial and says what it did not reach."),
    "full": "No ceiling: every unit runs its sweeps.",
}


def preset_spec(name: str, base: SolveSpec | None = None) -> SolveSpec:
    if name not in SOLVE_PRESETS:
        raise ValueError(f"unknown solve preset {name!r}; known: {sorted(SOLVE_PRESETS)}")
    return replace(base or SolveSpec(), **SOLVE_PRESETS[name])


__all__ = ["SOLVE_PRESETS", "SOLVE_PRESET_INFO", "UNIT_KINDS", "EngineEntry", "SolveSpec",
           "engine_descriptions", "engine_names", "get_engine", "preset_spec",
           "register_engine", "unit_seed"]
