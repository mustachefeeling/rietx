"""Resolving a parametric declaration against its patterns (WP-1325).

:class:`~rietx.schemas.parametric.ParametricTie` is the declaration;
:func:`resolve_parametric` is the **one authority** that turns it into numbers:
the subset, the design matrix Φ over it, the term labels, and the declaration
with its reference and scale filled in.  Every refusal that can be made from
the declaration and the coordinates alone is made here, before any table is
built or any solve runs; the ones that need a table (the target exists, is not
tied, locked or held) are made by
:class:`~rietx.params.multi.MultiParameterTable`, which owns the tables.

**Why linear, and why it costs no derivative branch.**  The tie machinery is
affine, p = C·θ + d with constant C (WP-0301, WP-1070).  p_k = Σ_j Φ_kj·c_j is
exactly one affine tie per pattern with C_k = Φ_k, so ``_column_extras`` reads
the reach off C and the whole-model FD column covers what a branch does not
claim.  A coefficient inside a power or an exponential is ``Parameter.expr``'s
fence (WP-1119).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np
from scipy import linalg

from ..optimize.statistics import PINV_RCOND
from ..schemas.parametric import CoordinateTable, ParametricCoefficient, ParametricTie

#: Below this, a pivoted-QR diagonal of the column-normalised Φ is a direction
#: the basis does not have (rank refusal).  **Derived from the covariance's own
#: cut, never tuned**: ``statistics.normal_factors`` hands an equilibrated
#: normal matrix to ``pinv`` with :data:`~rietx.optimize.statistics.PINV_RCOND`,
#: and an R diagonal r against a leading 1 is an eigenvalue r² of ΦᵀΦ, so a
#: basis direction under √rcond would be discarded by the covariance anyway —
#: a coefficient with no esd that the declaration asked to measure.  An exact
#: collinearity (a ternary's x_A + x_B + x_C = 1 beside an intercept) sits at
#: rounding, ~1e-16, eight decades below.
RANK_RTOL = math.sqrt(PINV_RCOND)


@dataclass
class ResolvedParametric:
    """A declaration resolved against its patterns: what the table wires.

    ``tie`` is the declaration with its reference and scale filled in (a
    ``polynomial``'s; the other bases use none), the form to pass back for a
    refit.  ``phi`` is Φ over ``patterns``, row k for ``patterns[k]``;
    ``divisors[j]`` the product of term j's coordinate scales, which turns a
    coefficient in table units into one per unit of the coordinates.
    """

    tie: ParametricTie
    patterns: list[int]
    phi: np.ndarray
    labels: list[str]
    divisors: np.ndarray
    units: list[str | None]

    @property
    def name(self) -> str:
        return self.tie.name

    @property
    def target(self) -> str:
        return self.tie.target

    @property
    def paths(self) -> list[str]:
        return self.tie.coefficient_paths()

    def row(self, h: int) -> np.ndarray | None:
        """Φ's row for histogram ``h``, or ``None`` outside the subset."""
        try:
            return self.phi[self.patterns.index(h)]
        except ValueError:
            return None


def term_label(term: list[str]) -> str:
    """``"1"`` for the intercept, else the monomial: ``"T"``, ``"x*y"``, ``"T^2"``.

    A repeated coordinate is a power, and powers are collected in order of
    first appearance, so ``["x", "y", "x"]`` is ``"x^2*y"``.
    """
    if not term:
        return "1"
    counts = Counter(term)
    return "*".join(name if n == 1 else f"{name}^{n}"
                    for name, n in dict.fromkeys((t, counts[t]) for t in term))


def _term_unit(target_unit: str | None, term: list[str],
               coordinate_units: dict[str, str]) -> str | None:
    """The target's unit over the term's coordinate units.

    ``None`` unless every factor's unit is recorded: a target with no unit, or
    a coordinate the table gives none, would otherwise print a unit that
    claims a dimension nobody declared (``1/K`` for a slope in Å/K).
    """
    if target_unit is None:
        return None
    counts = Counter(term)
    below = []
    for t in dict.fromkeys(term):
        u = coordinate_units.get(t)
        if not u:
            return None
        below.append(u if counts[t] == 1 else f"{u}^{counts[t]}")
    if not below:
        return target_unit
    return (f"{target_unit}/{below[0]}" if len(below) == 1
            else f"{target_unit}/({'*'.join(below)})")


def resolve_parametric(tie: ParametricTie, coordinates: CoordinateTable | None,
                       n_patterns: int, *, target_unit: str | None = None
                       ) -> ResolvedParametric:
    """Resolve ``tie`` against ``n_patterns`` patterns and their ``coordinates``.

    The reference and scale a polynomial leaves out are filled **once**, from
    the subset's values (mid-range, half-range), and returned in the resolved
    declaration: a refit passing it back reproduces Φ exactly, and a pattern
    that joins later never redefines a coefficient.

    Refusals, each a ``ValueError`` naming its fix: a subset index out of
    range; a polynomial with no coordinate table, a table of the wrong length,
    a term naming a column the table lacks, a subset pattern with no value
    for a coordinate it needs, a coordinate taking one value across the
    subset with no scale given; design rows not matching the subset; fewer
    patterns in the subset than coefficients; and a Φ whose rank is below its
    column count (pivoted QR on the centred, scaled columns, naming the
    collinear terms, and the Scheffé fix when the coordinates used sum to a
    constant).
    """
    name = tie.name
    if coordinates is not None and coordinates.n_patterns != n_patterns:
        raise ValueError(
            f"the coordinate table has {coordinates.n_patterns} rows for "
            f"{n_patterns} patterns: one row per pattern, in the order passed")
    patterns = list(range(n_patterns)) if tie.patterns is None else list(tie.patterns)
    bad = [k for k in patterns if k >= n_patterns]
    if bad:
        raise ValueError(
            f"parametric tie {name!r}: pattern index {bad[0]} is out of range for "
            f"{n_patterns} patterns (indices 0…{n_patterns - 1})")
    n_sub = len(patterns)
    resolved = tie
    divisors: list[float]
    units: list[str | None]
    if tie.basis == "constant":
        phi = np.ones((n_sub, 1), dtype=np.float64)
        labels = ["1"]
        divisors = [1.0]
        units = [target_unit]
        raw: dict[str, np.ndarray] = {}
    elif tie.basis == "design":
        phi = np.asarray(tie.design, dtype=np.float64)
        if phi.shape[0] != n_sub:
            raise ValueError(
                f"parametric tie {name!r}: {phi.shape[0]} design rows for a "
                f"subset of {n_sub} patterns: one row per pattern, in subset order")
        labels = [f"d{j}" for j in range(phi.shape[1])]
        divisors = [1.0] * phi.shape[1]
        # a design column is the caller's, in units only the caller knows
        units = [None] * phi.shape[1]
        raw = {}
    else:
        if coordinates is None:
            raise ValueError(
                f"parametric tie {name!r} is a polynomial over "
                f"{tie.coordinates_used()}, which needs a CoordinateTable "
                "(coordinates=…) giving each pattern's values")
        used = tie.coordinates_used()
        missing = [c for c in used if c not in coordinates.columns]
        if missing:
            raise ValueError(
                f"parametric tie {name!r} uses coordinate(s) {missing} the "
                f"table does not have (it has {sorted(coordinates.columns)})")
        raw = {}
        for c in used:
            column = coordinates.columns[c]
            holes = [k for k in patterns if column[k] is None]
            if holes:
                raise ValueError(
                    f"parametric tie {name!r}: pattern {holes[0]} has no value for "
                    f"coordinate {c!r}, which a term uses; give it one, or leave "
                    "the pattern out of the subset (patterns=…)")
            raw[c] = np.array([column[k] for k in patterns], dtype=np.float64)
        reference = dict(tie.reference or {})
        scale = dict(tie.scale or {})
        for c in used:
            lo, hi = float(raw[c].min()), float(raw[c].max())
            if c not in reference:
                reference[c] = 0.5 * (lo + hi)
            if c not in scale:
                half = 0.5 * (hi - lo)
                if not half > 0.0:
                    raise ValueError(
                        f"parametric tie {name!r}: coordinate {c!r} takes one value "
                        f"({lo:g}) across the subset, so a term in it is the "
                        "intercept again and it has no range to scale by; drop "
                        "the term, or give scale= if the subset will grow")
                scale[c] = half
        resolved = tie.model_copy(update={"reference": reference, "scale": scale})
        u = {c: (raw[c] - reference[c]) / scale[c] for c in used}
        phi = np.ones((n_sub, len(tie.terms or [])), dtype=np.float64)
        for j, term in enumerate(tie.terms or []):
            for c in term:
                phi[:, j] *= u[c]
        labels = [term_label(t) for t in tie.terms or []]
        divisors = [math.prod(scale[c] for c in t) for t in tie.terms or []]
        units = [_term_unit(target_unit, t, coordinates.units) for t in tie.terms or []]
    m = phi.shape[1]
    if n_sub < m:
        raise ValueError(
            f"parametric tie {name!r} has {m} coefficients ({', '.join(labels)}) "
            f"and its subset {n_sub} pattern{'' if n_sub == 1 else 's'}: a "
            "coefficient needs a pattern to measure it. Drop terms or widen the subset")
    _refuse_rank_deficient(name, phi, labels, raw, tie)
    return ResolvedParametric(tie=resolved, patterns=patterns, phi=phi, labels=labels,
                              divisors=np.asarray(divisors, dtype=np.float64),
                              units=units)


def _refuse_rank_deficient(name: str, phi: np.ndarray, labels: list[str],
                           raw: dict[str, np.ndarray], tie: ParametricTie) -> None:
    """Refuse a Φ whose columns are collinear across the subset, naming them.

    Pivoted QR on the column-normalised Φ (a polynomial's columns are already
    centred and scaled; a design's are only normalised, centring being the
    caller's to choose).  The trailing pivots past the rank are the dependent
    terms; each is named with the leading terms it is a combination of.
    """
    norms = np.linalg.norm(phi, axis=0)
    zero = [labels[j] for j in np.flatnonzero(norms == 0.0)]
    if zero:
        raise ValueError(
            f"parametric tie {name!r}: term(s) {zero} are zero in every pattern of "
            "the subset, so no pattern can measure them; drop them")
    q = phi / norms
    _, r, piv = linalg.qr(q, mode="economic", pivoting=True)
    diag = np.abs(np.diag(r))
    rank = int(np.sum(diag > RANK_RTOL * diag[0]))
    if rank == phi.shape[1]:
        return
    keep, dep = list(piv[:rank]), list(piv[rank:])
    coef, *_ = np.linalg.lstsq(q[:, keep], q[:, dep], rcond=None)
    parts = []
    for i, j in enumerate(dep):
        with_ = [labels[keep[k]] for k in np.flatnonzero(np.abs(coef[:, i]) > 1e-8)]
        parts.append(f"{labels[j]} is a combination of {with_}")
    fix = "drop one of each collinear set, or widen the subset"
    if "1" in labels and raw:
        total = sum(raw.values())
        if np.ptp(total) <= 1e-9 * max(1.0, float(np.max(np.abs(total)))):
            fix = (f"the coordinates {sorted(raw)} sum to a constant across the "
                   "subset, so the intercept is their sum: drop the intercept "
                   "(Scheffé form)")
    raise ValueError(
        f"parametric tie {name!r}: its basis has rank {rank} for {phi.shape[1]} "
        f"terms over the subset ({'; '.join(parts)}), so the coefficients are "
        f"not separately measurable: {fix}")


def least_squares_start(resolved: ResolvedParametric, values: np.ndarray) -> np.ndarray:
    """The coefficients whose Φ·c is closest to the subset's starting values.

    A subset that starts at one value is represented **exactly** where the
    basis can: the intercept takes it and every other term zero, so a
    ``constant`` declaration starts from bit-for-bit the number a plain shared
    parameter would, which the equivalence with ``refine_multi`` rests on.
    """
    values = np.asarray(values, dtype=np.float64)
    m = resolved.phi.shape[1]
    if np.all(values == values[0]) and "1" in resolved.labels:
        c = np.zeros(m, dtype=np.float64)
        c[resolved.labels.index("1")] = values[0]
        return c
    c, *_ = np.linalg.lstsq(resolved.phi, values, rcond=None)
    return c


def coefficient_rows(resolved: ResolvedParametric, values: dict[str, float],
                     esds: dict[str, float], vary: dict[str, bool]
                     ) -> list[ParametricCoefficient]:
    """One :class:`ParametricCoefficient` per coefficient, in user units.

    ``values``/``esds``/``vary`` are keyed by the coefficients' paths, in the
    table's (centred, scaled) units; each is divided by its term's scale
    product, so the reported number is per unit of the coordinates at the
    reference.  A path absent from ``esds`` is reported ``None``: the
    covariance marked it unmeasured (``ParameterTable.stderr_physical`` omits a
    row drawing on a gradient-free column) or it was never free.
    """
    out = []
    ref = (dict(resolved.tie.reference)
           if resolved.tie.basis == "polynomial" and resolved.tie.reference else None)
    for j, path in enumerate(resolved.paths):
        d = float(resolved.divisors[j])
        esd = esds.get(path) if vary.get(path, False) else None
        out.append(ParametricCoefficient(
            tie=resolved.name, target=resolved.target, term=resolved.labels[j],
            path=path, value=float(values[path]) / d,
            esd=None if esd is None else float(esd) / d,
            vary=bool(vary.get(path, False)), unit=resolved.units[j], reference=ref))
    return out
