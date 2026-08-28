"""The parameter table as data: one row per refinable scalar.

``params.vector.Entry`` is the ground truth of what a parameter *is* — path,
value, vary flag, bounds, transform, affine tie, locked flag — but it is a
dataclass inside the optimiser's translation layer, and the hot loop is
deliberately free of pydantic.  :class:`ParameterRow` is its serializable twin
for the cold paths: a listing for a caller (``Refinement.parameters()``), a GUI
parameter table (WP-1011), a text document (WP-1009).

Unlike :class:`~rietx.schemas.results.RefinedParameter`, which reports what a
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
    """Serializable form of ``params.vector.AffineTie``: value = Σ c·src + k.

    :attr:`user` separates the two populations that share this shape.  A
    **symmetry** tie is derived: ``ParameterTable`` rebuilds it from the space
    group and the Wyckoff position every time it is constructed, and nothing a
    caller does can remove it.  A **user** tie (WP-1070) is declared through
    ``Refinement.tie``/``tie_equal``, lives in the history, and can be taken
    back with ``untie``.  Both hold a row the same way, so ``held_because``
    reads the same for either; the flag is what lets a client tell a row it may
    release from one it may not, without having to try.
    """

    terms: list[tuple[str, float]] = Field(default_factory=list)
    const: float = 0.0
    user: bool = False

    @classmethod
    def _from_tie(cls, tie: Any, *, user: bool = False) -> "TieSpec":
        """Convert a :class:`rietx.params.vector.AffineTie` — **internal**.

        Private because its argument is (WP-1076).  ``AffineTie`` is not on the
        public surface and has no reason to be: it is what ``ParameterTable``
        holds, a caller only ever sees the ``TieSpec`` this returns.  As a
        public classmethod it was a converter that could not name what it
        converts, so it sat in the manual's provisional bucket with nothing
        honest to say about it.
        """
        return cls(terms=[(p, float(c)) for p, c in tie.terms], const=float(tie.const),
                   user=user)

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

    ``.value``/``.esd`` are the numbers; the whole table, held rows included,
    comes from ``Refinement.parameters()``, never from re-deriving one here.

    The first eight fields are ``Entry``'s, name for name;
    ``tests/test_params_surface.py`` asserts that against
    ``dataclasses.fields(Entry)`` so a new ``Entry`` field cannot go unexposed.
    The rest are **deliberate additions**, listed in that same test's
    ``DELIBERATE_EXTRAS`` rather than special-cased silently:

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
    #: A wavelength that cannot be freed **right now** because this histogram's
    #: cell is free, making the two an exactly flat direction.  The fourth
    #: held-reason, and the only *dynamic* one: unlike ``locked`` it is not a
    #: fact about the parameter, and unlike ``mode_fixed`` it is undone by
    #: holding the cell rather than by changing the mode.  It exists because
    #: ``refinable`` promises "``set_vary`` could free this", and with a free
    #: cell ``set_vary`` skips the row — so without this flag the promise would
    #: be false while ``held_because`` said nothing (the defaulted-``False``
    #: failure WP-1076 removes).
    needs_held_cell: bool = False
    #: The :data:`rietx.help.PARAMETER_HELP` glob whose entry describes this
    #: path, or ``None`` when no family claims it.  The only extra that is not
    #: a held-reason: it says what the parameter *is*, and it is a key rather
    #: than the entry because an entry describes a family and a table repeats
    #: each one once per atom (``help.help_key_for`` has the measurement).
    #: Filled here rather than by whichever surface displays it, so ``None``
    #: means "no family claims this" for every caller and not "nobody looked" —
    #: the defaulted-answer failure WP-1076 went through the result rows for.
    help_key: str | None = None

    @property
    def refinable(self) -> bool:
        """Whether ``set_vary`` could free this row in the current mode."""
        return (not self.locked and self.tie is None and not self.mode_fixed
                and not self.needs_held_cell)

    @property
    def held_because(self) -> str:
        """Why this row cannot be freed, or ``""`` when it can be."""
        if self.locked:
            return "structurally fixed by symmetry or by the model"
        if self.tie is not None:
            return f"tied: = {self.tie.describe()}"
        if self.mode_fixed:
            return "force-fixed by the intensity mode (lebail/pawley)"
        if self.needs_held_cell:
            return ("a free wavelength needs this histogram's cell held: "
                    "d = lambda/(2 sin theta) fixes only the product")
        return ""
