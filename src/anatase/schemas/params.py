"""The parameter table as data: one row per refinable scalar.

``params.vector.Entry`` is the ground truth of what a parameter *is* — path,
value, vary flag, bounds, transform, affine tie, locked flag — but it is a
dataclass inside the optimiser's translation layer, and the hot loop is
deliberately free of pydantic.  :class:`ParameterRow` is its serializable twin
for the cold paths: a listing for a caller (``Refinement.parameters()``), a GUI
parameter table (WP-1011), a text document (WP-1009).

Unlike :class:`~anatase.schemas.results.RefinedParameter`, which reports what a
fit *refined*, a row exists for **every** entry — fixed, locked and tied ones
included.  A caller deciding what to free next has to see the whole table,
including the parts it may not touch and why it may not.  Three separate
reasons make a row un-refinable and they are distinguishable on purpose:

* ``locked`` — structurally fixed, ``set_vary`` can never free it (a
  symmetry-fixed cell angle, the line-0 emission weight, ``biso`` on a site
  that declares an anisotropic tensor);
* ``tie`` — an affine function of other entries, so the freedom lives in its
  sources (``b`` in a tetragonal cell, an atom coordinate behind its Wyckoff
  DOFs);
* ``mode_fixed`` — refinable in principle, but force-fixed by the intensity
  mode currently in force.

:attr:`ParameterRow.refinable` is the single predicate over the three, so a
front end has one rule to grey a row by rather than three it could get wrong.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import Base, TransformKind


class TieSpec(Base):
    """Serializable form of ``params.vector.AffineTie``: value = Σ c·src + k."""

    terms: list[tuple[str, float]] = Field(default_factory=list)
    const: float = 0.0

    @classmethod
    def from_tie(cls, tie: Any) -> "TieSpec":
        return cls(terms=[(p, float(c)) for p, c in tie.terms], const=float(tie.const))

    @property
    def sources(self) -> list[str]:
        """The paths this value follows — what to edit instead of this row."""
        return [p for p, _ in self.terms]

    def describe(self) -> str:
        """Human-readable right-hand side, e.g. ``0.1993 + 1·phases.0.atoms.1.dof.0``."""
        parts = [f"{c:g}·{p}" for p, c in self.terms]
        if self.const or not parts:
            parts.insert(0, f"{self.const:g}")
        return " + ".join(parts)


class ParameterRow(Base):
    """One row of the parameter table — the mirror of ``params.vector.Entry``.

    The first eight fields are ``Entry``'s, name for name;
    ``tests/test_params_surface.py`` asserts that against
    ``dataclasses.fields(Entry)`` so a new ``Entry`` field cannot go unexposed.
    The last two are **deliberate additions**, listed in that same test rather
    than special-cased silently:

    ``esd``
        the standard uncertainty from the most recent fit, if this parameter was
        free or tied in it.  It belongs on the row and not on ``Entry`` because
        ``Entry`` is what the residual reads; an esd is a property of a
        *completed* fit, and merging it here is what lets one listing answer
        "what is this worth, and how well is it known".
    ``mode_fixed``
        ``True`` when ``lebail``/``pawley`` mode force-fixes this path (every
        ``.atoms.`` path, the phase scale, the emission-line weights — see
        ``Refinement._run_stage``).  It is not ``locked``: nothing about the
        parameter is structurally fixed, and switching back to ``rietveld``
        frees it again.  The distinction matters most for a Le Bail-only phase,
        which must carry a dummy atom to exist at all — presenting its
        ``biso`` as editable would invite refining something the mode discards.
    """

    path: str
    value: float
    vary: bool = False
    lo: float = float("-inf")
    hi: float = float("inf")
    transform: TransformKind = "identity"
    tie: TieSpec | None = None
    locked: bool = False
    esd: float | None = None
    mode_fixed: bool = False

    @property
    def refinable(self) -> bool:
        """Whether ``set_vary`` could free this row in the current mode."""
        return not self.locked and self.tie is None and not self.mode_fixed

    @property
    def held_because(self) -> str:
        """Why this row cannot be freed, or ``""`` when it can be."""
        if self.locked:
            return "structurally fixed by symmetry or by the model"
        if self.tie is not None:
            return f"tied: = {self.tie.describe()}"
        if self.mode_fixed:
            return "force-fixed by the intensity mode (lebail/pawley)"
        return ""
