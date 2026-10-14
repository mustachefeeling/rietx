"""A parameter as a declared function of each pattern's coordinates (WP-1325).

A joint fit over many patterns (:func:`rietx.refine_multi`) can refine a
parameter as a function of where each pattern sits: a temperature down a ramp,
an (x, y) composition across a combinatorial library.  Pattern k's value of the
target is p_k = Σ_j Φ_kj · c_j, and the coefficients c_j are the refined
parameters, with esds from the joint covariance (Stinton & Evans, 2007,
*J. Appl. Cryst.* 40, 87, "parametric Rietveld refinement").

**Data, not code.**  Everything here is a pydantic model with a JSON
round-trip, so a self-driving lab can write one and a result can carry it:

* :class:`CoordinateTable` — one row per pattern, named columns with units,
  passed **beside** the patterns because several declarations share one table.
* :class:`ParametricTie` — one target, a basis from a **closed** vocabulary
  (``constant``, ``polynomial`` over named coordinates, or an explicit
  ``design`` matrix, the escape hatch for splines, Scheffé mixture forms and
  sin²ψ), the pattern subset, and the reference point and scale per
  coordinate.  A form with a coefficient inside a power or an exponential is
  not linear in it and is not expressible here (``Parameter.expr``, WP-1119).
* :class:`ParametricCoefficient` — one refined coefficient on
  :attr:`RefinementResult.parametric <rietx.schemas.results.RefinementResult.parametric>`,
  in the caller's units at the reference.
* :class:`ParametricFormTest` — one declaration's lack-of-fit test on
  :attr:`RefinementResult.parametric_form
  <rietx.schemas.results.RefinementResult.parametric_form>`.

**The reference and scale are stored in the declaration** (patsy's lesson).  A
polynomial term is evaluated on u = (z − reference)/scale.  Left out, both are
computed **once**, when the declaration is resolved against a coordinate table
(``params.parametric.resolve_parametric``): the mid-range and half-range of the
subset's values.  The resolved declaration carries them, so a refit or a grown
campaign passing it back gets the same coefficients with the same meaning,
whatever patterns have joined.  Centring is what makes c₀ "the target at the
reference" rather than an extrapolation to z = 0, and it removes the
intercept-slope correlation an off-centre axis creates, which the normal
matrix's own equilibration (van der Sluis, 1969) does not.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from .common import Base

#: The closed basis vocabulary.  ``constant`` is one coefficient, the same in
#: every pattern of the subset (a shared parameter over a subset);
#: ``polynomial`` is a sum of monomials in named coordinates; ``design`` is a
#: caller's own matrix, one row per pattern of the subset.
ParametricBasis = Literal["constant", "polynomial", "design"]

#: fnmatch's metacharacters: a target names one path, never a family
_GLOB_CHARS = frozenset("*?[")


def _finite(value: float, what: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{what} must be finite, got {value!r}")


class CoordinateTable(Base):
    """Each pattern's coordinates: named columns, one row per pattern.

    ``columns`` maps a coordinate name to its value in every pattern, in the
    order the patterns are passed; ``None`` is a pattern with no value for that
    coordinate (a declaration whose subset needs it there is refused).
    ``units`` names a column's unit, which a coefficient's reported unit is
    built from; a term over a column it leaves out reports no unit at all,
    rather than one claiming the column dimensionless.
    """

    columns: dict[str, list[float | None]]
    units: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> "CoordinateTable":
        if not self.columns:
            raise ValueError("a coordinate table needs at least one column")
        for name, values in self.columns.items():
            if not name.isidentifier():
                raise ValueError(
                    f"coordinate name {name!r} must be a single identifier, so a "
                    "polynomial term can name it and a label can print it")
            for k, v in enumerate(values):
                if v is not None:
                    _finite(v, f"coordinate {name!r} at pattern {k}")
        lengths = {name: len(v) for name, v in self.columns.items()}
        if len(set(lengths.values())) != 1:
            raise ValueError(
                f"every coordinate column needs one value per pattern; the "
                f"lengths differ: {lengths}")
        if min(lengths.values()) < 1:
            raise ValueError("a coordinate column needs at least one pattern")
        extra = sorted(set(self.units) - set(self.columns))
        if extra:
            raise ValueError(f"units name columns the table does not have: {extra}")
        return self

    @property
    def n_patterns(self) -> int:
        """How many patterns the table describes (every column's length)."""
        return len(next(iter(self.columns.values())))


class ParametricTie(Base):
    """One target refined as a declared linear function of the coordinates.

    Its coefficients are named variables ``vars.{name}_{j}``, j = 0…m−1, one
    shared column each in the joint fit, and the target in each pattern of the
    subset is tied onto Σ_j Φ_kj·``vars.{name}_{j}``.  A plan frees them when a
    stage's glob reaches the target, so ``mccusker_default``'s cell stage frees
    a parametric cell as it would a plain one.

    * ``target`` — one model parameter's bare dot-path, no glob and no
      ``hist.`` scope (the subset says which patterns): ``phases.0.cell.a``,
      ``instrument.background.c2``.
    * ``basis`` — ``constant``; ``polynomial``, with ``terms``: each a list of
      coordinate names, a repeat being a power and ``[]`` the intercept
      (``[[], ["T"]]`` is a + b·T, ``[[], ["x"], ["y"], ["x", "y"]]`` a bilinear
      surface); or ``design``, with ``design``: one row per pattern of the
      subset, in subset order.
    * ``patterns`` — the subset, by index into the patterns as passed; ``None``
      is every pattern.
    * ``reference``/``scale`` — per coordinate a polynomial uses: terms are
      evaluated on (z − reference)/scale.  Left out, they are the subset's
      mid-range and half-range, computed once at resolution and stored.
    """

    name: str
    target: str
    basis: ParametricBasis
    terms: list[list[str]] | None = None
    design: list[list[float]] | None = None
    patterns: list[int] | None = None
    reference: dict[str, float] | None = None
    scale: dict[str, float] | None = None

    @model_validator(mode="after")
    def _check(self) -> "ParametricTie":
        if not self.name.isidentifier():
            raise ValueError(
                f"parametric tie name {self.name!r} must be a single identifier: "
                f"its coefficients are the variables vars.{self.name}_0, …, and a "
                "glob must be able to name them")
        t = self.target
        if not t or _GLOB_CHARS & set(t):
            raise ValueError(
                f"target {t!r} must be one bare dot-path, not a glob: one "
                "declaration ties one parameter")
        if not t.startswith(("phases.", "instrument.")):
            raise ValueError(
                f"target {t!r} must be a model parameter, a dot-path under "
                "'phases.' or 'instrument.'; name the patterns it applies to "
                "with patterns=, never with a 'hist.' scope")
        if self.patterns is not None:
            if not self.patterns:
                raise ValueError("patterns=[] selects nothing; pass None for every pattern")
            if any(k < 0 for k in self.patterns):
                raise ValueError(f"pattern indices are non-negative: {self.patterns}")
            if len(set(self.patterns)) != len(self.patterns):
                raise ValueError(f"a pattern appears twice in the subset: {self.patterns}")
        if self.basis == "constant":
            self._forbid("constant", "terms", "design", "reference", "scale")
        elif self.basis == "polynomial":
            self._forbid("polynomial", "design")
            self._check_terms()
        else:
            self._forbid("design", "terms", "reference", "scale")
            self._check_design()
        return self

    def _forbid(self, basis: str, *fields: str) -> None:
        given = [f for f in fields if getattr(self, f) is not None]
        if given:
            raise ValueError(
                f"a {basis} basis takes no {', '.join(given)}: "
                + {"constant": "one coefficient, the same in every pattern of the "
                               "subset, uses no coordinate",
                   "polynomial": "its rows are built from terms over the "
                                 "coordinate table",
                   "design": "its rows are the caller's own, already in the units "
                             "the caller wants each coefficient in"}[basis])

    def _check_terms(self) -> None:
        if not self.terms:
            raise ValueError("a polynomial basis needs terms, e.g. [[], ['T']] for a + b·T")
        seen: set[tuple[str, ...]] = set()
        for term in self.terms:
            for name in term:
                if not name.isidentifier():
                    raise ValueError(f"term {term!r} names {name!r}, not a coordinate name")
            key = tuple(sorted(term))
            if key in seen:
                raise ValueError(
                    f"term {term!r} appears twice (a term is a product, so its "
                    "order does not matter); a repeated column is a rank-deficient "
                    "basis")
            seen.add(key)
        used = set(self.coordinates_used())
        for field in ("reference", "scale"):
            given = getattr(self, field) or {}
            extra = sorted(set(given) - used)
            if extra:
                raise ValueError(
                    f"{field} names coordinates no term uses: {extra} (terms use "
                    f"{sorted(used)})")
            for name, v in given.items():
                _finite(v, f"{field}[{name!r}]")
        for name, v in (self.scale or {}).items():
            if v <= 0.0:
                raise ValueError(f"scale[{name!r}] must be positive, got {v!r}")

    def _check_design(self) -> None:
        if not self.design:
            raise ValueError("a design basis needs design rows, one per pattern of the subset")
        widths = {len(row) for row in self.design}
        if len(widths) != 1 or min(widths) < 1:
            raise ValueError(
                f"every design row needs the same number (≥ 1) of columns; got "
                f"{sorted(widths)}")
        for k, row in enumerate(self.design):
            for j, v in enumerate(row):
                _finite(v, f"design[{k}][{j}]")
        if self.patterns is not None and len(self.design) != len(self.patterns):
            raise ValueError(
                f"{len(self.design)} design rows for a subset of "
                f"{len(self.patterns)} patterns: one row per pattern, in subset order")

    def coordinates_used(self) -> list[str]:
        """The coordinate names the polynomial terms use, first use first."""
        out: dict[str, None] = {}
        for term in self.terms or []:
            for name in term:
                out[name] = None
        return list(out)

    @property
    def n_coefficients(self) -> int:
        """m, the number of coefficients this declaration refines."""
        if self.basis == "constant":
            return 1
        if self.basis == "polynomial":
            return len(self.terms or [])
        return len((self.design or [[]])[0])

    def coefficient_paths(self) -> list[str]:
        """``vars.{name}_{j}`` for j = 0…m−1, the coefficients' dot-paths."""
        return [f"vars.{self.name}_{j}" for j in range(self.n_coefficients)]


class ParametricCoefficient(Base):
    """One refined coefficient of a :class:`ParametricTie`, in user units.

    ``value`` and ``esd`` are the coefficient of the term ``term`` per unit of
    the coordinates themselves (not of the scaled u), **at the reference**: for
    a polynomial each is the refined coefficient divided by the product of the
    term's coordinate scales, so ``"1"`` is the target at the reference point
    and ``"T"`` its slope there.  A ``design`` coefficient is reported as the
    design matrix defines it, and a ``constant`` one is the target itself.

    ``esd`` is ``None`` where the joint covariance gives the coefficient none:
    no pattern of the subset carried gradient for it, or it was not free in
    the solve that produced the answer (``vary`` False).  ``unit`` is the target's unit over the term's coordinate
    units, and ``None`` unless the target's and every such coordinate's unit
    is recorded (a ``design`` coefficient's is the caller's, so never).
    """

    tie: str
    target: str
    term: str
    path: str
    value: float
    esd: float | None
    vary: bool
    unit: str | None
    reference: dict[str, float] | None


class ParametricFormTest(Base):
    """Whether one :class:`ParametricTie`'s form survives its own data.

    A score test at the answer.  The alternative frees the target in each
    pattern of the subset, in place of the coefficients, and one linear
    least-squares step from the answer with every other free column refitted
    says how much χ² that would remove (``params.parametric.form_tests``).
    ``statistic`` is that χ² over χ²_red·f², the answer's reduced χ² and
    Bérar-Lelann factor, which is ~χ² with ``dof`` degrees of freedom while
    the form holds.  ``rejected`` is ``statistic > cut``, the χ² point at
    ``params.parametric.FORM_TEST_LEVEL``, and then the coefficients' esds
    assume a form the data refuses.

    * ``n_patterns`` — the subset patterns whose own target entered the
      alternative.  A pattern that cannot see the target is left out, as an
      untied fit would hold it there (WP-1301), and so is one where Φ is zero.
    * ``n_subset`` — the patterns the declaration's subset names.  Where
      ``n_patterns`` is the smaller, the law sets the target in the rest and
      the test cannot check it there; ``PARAMETRIC_TARGET_UNSEEN`` names the
      patterns that cannot see it.
    * ``dof`` — the directions the alternative adds past the covariance's cut,
      ``n_patterns`` less the free coefficients when nothing is degenerate.
      ``None`` when the test did not run: a coefficient was not free at the
      answer.  0 when there was nothing to test.
    * ``statistic``, ``cut``, ``rejected``, ``p_value`` — ``None`` unless
      ``dof`` is positive and the answer's χ²_red·f² is a positive finite
      number.  ``p_value`` is χ²'s upper tail at ``statistic`` for ``dof``
      directions, so a near miss reads as one on either side of the cut.
    """

    tie: str
    target: str
    n_patterns: int
    n_subset: int
    dof: int | None
    statistic: float | None
    cut: float | None
    rejected: bool | None
    p_value: float | None
