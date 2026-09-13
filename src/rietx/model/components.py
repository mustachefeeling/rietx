"""The :data:`~rietx.schemas.instrument.ExtraComponent` registry.

Clause 1 of the member contract (stated in that union's docstring) asks for one
authority holding every member's evaluator, and clause 2 for a **declared**
aggregate membership — which reported total the member's curve joins — held as
data rather than read off the class name.  This module is both.

**Why a registry and not an ``isinstance`` ladder.**  The two questions a member
answers are asked in different places: the evaluator in
:mod:`rietx.model.forward`, the membership in the result builder and in every
consumer that reports a background or a tick list.  A ladder in each would be
two ladders to grow in step, and clause 2 exists because the failure of not
growing them together is silent — a member counted twice, or not at all.  A dict
keyed by the ``kind`` discriminator is the same dispatch the union itself uses,
so there is one spelling of "which member is this" in the package.

**The arithmetic is not moved here.**  A hump is a background model and its
curve lives with the other background models; a peak is a pseudo-Voigt and uses
the unit-area one every Bragg reflection already uses, so this member adds no
new arithmetic at all.  What is one place is the *registry*, which is what
clause 1 asks for and what a member can actually drift from.
"""

from __future__ import annotations

from typing import Callable, Literal

from ..background.models import hump_curve
from ..schemas.instrument import COMPONENT_FIELDS
from .profiles.pseudovoigt import pseudo_voigt

#: Which reported aggregate each member's curve joins — clause 2, as data.
#:
#: ``"background"`` means the curve is part of what the package calls the
#: background: it is in ``result.y_background``, it is inside
#: :meth:`~rietx.model.forward.CompiledModel.background`, and it is therefore
#: subtracted from the Le Bail/Pawley partition net for free, because the
#: partition already calls that one method.
#:
#: ``"ticks"`` means the curve is a *peak*: it is **not** background, it does not
#: belong in ``y_background``, and its positions join ``result.ticks`` so that
#: Layer 0 stops reporting a declared peak as an unindexed impurity.  Its
#: subtraction from the partition net is therefore **not** free and is done
#: explicitly — the one thing a peak-landing member costs that a
#: background-landing one does not, and the reason clause 3 is a separate clause
#: from clause 2.
COMPONENT_AGGREGATE: dict[str, Literal["background", "ticks"]] = {
    "hump": "background",
    "peak": "ticks",
}

#: Whether the member is evaluated on the whole grid or in a frozen window.
#:
#: A hump is broad **by declaration** — that is what makes it a background
#: feature — so a window would be the whole grid and sizing one would buy
#: nothing.  A peak is sharp by declaration, so it is windowed, and its window is
#: frozen at stage compile like every other window in the package.
COMPONENT_EXTENT: dict[str, Literal["grid", "window"]] = {
    "hump": "grid",
    "peak": "window",
}


def component_fields(kind: str) -> tuple[str, ...]:
    """The member's refinable field names, in path order (clause 4).

    Re-exported from :data:`~rietx.schemas.instrument.COMPONENT_FIELDS` so that
    a caller asking this registry one question about a member can ask it all of
    them, while the field names stay declared beside the classes that own them.
    """
    return COMPONENT_FIELDS[kind]


def component_aggregate(kind: str) -> str:
    """Which reported aggregate this member joins — read, never inferred."""
    return COMPONENT_AGGREGATE[kind]


#: Every member's ``kind``, which is the registry's own answer to "what members
#: are there".  ``capabilities().extra_component_kinds`` derives its arm from the
#: union rather than from this, on purpose: two derivations of one fact that must
#: agree is a meta-test (``tests/test_extra_components.py``), whereas one
#: derivation quoting the other would make the agreement unfalsifiable.
COMPONENT_KINDS: tuple[str, ...] = tuple(COMPONENT_AGGREGATE)


__all__ = [
    "COMPONENT_AGGREGATE",
    "COMPONENT_EXTENT",
    "COMPONENT_KINDS",
    "component_aggregate",
    "component_fields",
    "hump_curve",
    "pseudo_voigt",
]

# Re-exported so clause 1's "registered in one authority" is literally true: a
# caller reaching for a member's evaluator reaches here, whatever module the
# arithmetic is written in.
_EVALUATORS: dict[str, Callable] = {
    "hump": hump_curve,
    "peak": pseudo_voigt,
}
