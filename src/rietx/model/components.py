"""Where each :data:`~rietx.schemas.instrument.ExtraComponent` member lands.

Clause 2 of the member contract (stated in that union's docstring) asks for a
**declared** aggregate membership — which reported total a member's curve joins
— held as data rather than read off the class name. This module is that
declaration, and the tick-list key it resolves to on the way out.

**Why a registry and not an ``isinstance`` ladder.** The question is asked in
more than one place — the compile that partitions the declared components, the
result builder that writes the tick list, the two absorption statistics that
must divide the same components between them — and a ladder in each would be
several to grow in step. Clause 2 exists because the failure of not growing
them together is silent: a member counted twice, or not at all. A dict keyed by
the ``kind`` discriminator is the same dispatch the union itself uses, so there
is one spelling of "which member is this" in the package.

**No evaluator registry, and clause 1 says so.** Each member's arithmetic lives
where it belongs — a hump's in :mod:`rietx.background.models`, a peak's in the
unit-area pseudo-Voigt every Bragg reflection already uses — and
:mod:`rietx.model.forward` calls them directly. A table here mapping ``kind`` to
a function was written first and deleted (WP-1103): nothing read it, so it was
a second copy of a fact rather than an authority over one, which is the shape
this repository calls a declared name with no writer. What clause 1 actually
requires is that a member's evaluator be expressible in ``xp`` ops so every
backend differentiates it through the traced twin, and that is a property of
the evaluator, not of where it is listed.
"""

from __future__ import annotations

from typing import Literal

#: Which reported aggregate each member's curve joins — clause 2, as data.
#:
#: ``"background"`` means the curve is part of what the package calls the
#: background: it is in ``result.y_background``, it is inside
#: :meth:`~rietx.model.forward.CompiledModel.background`, and it is therefore
#: subtracted from the Le Bail/Pawley partition net for free, because the
#: partition already calls that one method.
#:
#: ``"ticks"`` means the curve is a *peak*: it is **not** background, it does
#: not belong in ``y_background``, and its positions join ``result.ticks`` under
#: :data:`EXTRA_TICK_KEY` so that Layer 0 stops reporting a declared peak as an
#: unindexed impurity. Its subtraction from the partition net is therefore
#: **not** free and is done explicitly — the one thing a peak-landing member
#: costs that a background-landing one does not, and the reason clause 3 is a
#: separate clause from clause 2.
#:
#: A member missing a row here registers no parameters and lands nowhere;
#: ``tests/test_extra_components.py`` crosses this against the union both ways.
COMPONENT_AGGREGATE: dict[str, Literal["background", "ticks"]] = {
    "hump": "background",
    "peak": "ticks",
}

#: ``RefinementResult.ticks`` key carrying every declared sharp peak's
#: positions — the concrete form clause 2's ``"ticks"`` aggregate takes on the
#: way out. Parenthesised because no CIF phase name is: a tick list is read by
#: name, so a phase actually called ``"(extra)"`` and this row would be one
#: entry and one of the two would vanish. ``compile_model`` refuses that
#: collision rather than renaming anything.
#:
#: One key for every declared peak, not one per component: a consumer asks "is
#: there a peak here the model knows about", and the answer does not depend on
#: which component supplied it. Which one did is in
#: ``Instrument.extra_components`` and in the diagnostics, which carry the
#: dot-path.
#:
#: It lives here rather than in :mod:`rietx.refine` because
#: :mod:`rietx.model.forward` enforces the collision and ``refine`` writes the
#: key, and ``refine`` imports ``forward`` — so the one authority has to sit
#: under both.
EXTRA_TICK_KEY = "(extra)"

__all__ = ["COMPONENT_AGGREGATE", "EXTRA_TICK_KEY"]
