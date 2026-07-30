"""Reduced cells, Bravais determination, and the cell-equality test dedup needs.

**Nothing here is hand-written that a dependency already does exactly.**  Niggli
and Delaunay (Selling) reduction are ``gemmi.GruberVector``; the lattice point
group is ``gemmi.find_lattice_symmetry`` (Le Page 1982, via
``find_lattice_2fold_ops``); ``spglib.get_symmetry_dataset`` gives an independent
opinion on the same question.  Both are hard dependencies already, MPL-2.0 and
BSD-3, neither on the licensing fence.

**Two independent opinions on Bravais, and their tolerances are not the same
kind of number.**  gemmi's is a Le Page **obliquity in degrees**; spglib's is a
distance **``symprec`` in Å**.  They parameterise the same question differently,
so both are run and the tolerance is *swept* — and the reported answer is the
highest symmetry **stable across the sweep**.  Symmetry that appears only at the
loosest tolerance is :data:`INDEX_BRAVAIS_AMBIGUOUS`, not an answer.  The device
is ``sequential.py``'s ``direction="both"`` and the cross-backend Jacobian matrix
one rank up: agreement between two independent methods is the confidence, and
disagreement is reported rather than averaged.

Monotonicity is what makes "stable" cheap to compute: loosening a tolerance can
only *add* symmetry, so the stable answer is the tightest tolerance's answer and
the ambiguity is whether the loosest one says something higher.  It is asserted
rather than assumed (``tests/test_indexing_reduce.py``).

**Both opinions must be asked about the same lattice, and that is easy to get
wrong in exactly one place.**  Niggli reduction of a *centred* cell returns the
reduced **primitive** cell — the centring is consumed by the reduction — so
:attr:`ReducedCell.centring` is provenance about the input and must not be handed
back to anything that applies a centring.  Doing so (WP-1020, fixed in WP-1024)
made gemmi report a cubic I lattice as **trigonal**, six lattice rotations instead
of twenty-four, so the two methods disagreed on every centred candidate and the
disagreement — which is supposed to mean pseudosymmetry — meant "one of us was
asked the wrong question".

**Dedup is a χ² test, not a percentage.**  Two candidates are the same lattice
when their Niggli-reduced A..F vectors agree under χ² = ΔᵀΣ⁻¹Δ against χ²₆(0.99),
using their joint covariance.  A fixed percentage merges distinct synchrotron
cells (whose esds are 100× smaller than the bound) and splits noisy lab ones —
per-line σ doing work again.  The relative fallback exists only for candidates
that arrive with no covariance at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

#: χ²₆ at 99 % — the equality bound for two 6-vectors of A..F.  Six because the
#: comparison is always made on the *reduced primitive* form, which has all six
#: components free whatever system the candidates were found in.
CELL_EQUALITY_CHI2 = 16.8119
#: Relative bound used only when a candidate carries no covariance.  Deliberately
#: an order looser than a synchrotron cell's precision, so it never *tightens* a
#: comparison the χ² test would have made.
CELL_EQUALITY_RELATIVE = 5e-3
#: Le Page obliquities (degrees) swept by :func:`bravais_screen`.
BRAVAIS_OBLIQUITIES: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0)
#: Multiples of the cell's own esd used as spglib ``symprec`` values.  Tying the
#: sweep to the *measured* precision rather than to a fixed distance is the
#: per-line-σ rule again: 1e-3 Å is generous on a synchrotron cell and tight on a
#: lab one, and a fixed value would make the two opinions incomparable.
BRAVAIS_SYMPREC_SIGMAS: tuple[float, ...] = (1.0, 3.0, 10.0)

#: Space-group number ranges → crystal system, the standard division.  Used to
#: read spglib's answer in the same vocabulary gemmi's operation count gives.
_SYSTEM_BY_NUMBER: tuple[tuple[int, str], ...] = (
    (2, "triclinic"), (15, "monoclinic"), (74, "orthorhombic"),
    (142, "tetragonal"), (167, "trigonal"), (194, "hexagonal"),
    (230, "cubic"))
#: Rotation count of each holohedral lattice group (gemmi's ``sym_ops``, i.e. the
#: Laue order halved) → system.  A *lattice* group is always holohedral, so this
#: map is exhaustive: -1, 2/m, mmm, 4/mmm, -3m, 6/mmm, m-3m.
_SYSTEM_BY_SYM_OPS: dict[int, str] = {
    1: "triclinic", 2: "monoclinic", 4: "orthorhombic", 6: "trigonal",
    8: "tetragonal", 12: "hexagonal", 24: "cubic"}
#: Rank for "higher symmetry": the **order of the lattice point group**, which is
#: `_SYSTEM_BY_SYM_OPS` read backwards.  A total order, unlike anything derived
#: from ``METRIC_DOF``: cubic and hexagonal have 1 and 2 metric degrees of freedom
#: but so do cubic and *tetragonal*-vs-*trigonal*, so a DOF-based rank ties pairs
#: of systems, and an inverse lookup through a tied rank silently returns the
#: wrong system — it returned "hexagonal" for a cubic cell, first time.  Note what
#: this order does *not* mean: a higher rank is not a supergroup relation
#: (tetragonal at 8 is not a supergroup of trigonal at 6), so it is only ever used
#: to pick the more conservative of two answers to the same question.
SYSTEM_RANK: dict[str, int] = {v: k for k, v in _SYSTEM_BY_SYM_OPS.items()}


@dataclass
class ReducedCell:
    """A reduced cell and the change of basis that produced it."""

    cell: tuple[float, float, float, float, float, float]
    change_of_basis: str            # gemmi triplet, e.g. "y,z,x"
    #: centring of the **input** cell, kept for provenance.  :attr:`cell` itself is
    #: always **primitive**: ``gemmi.GruberVector(uc, centring)`` reduces the
    #: primitive cell of the centred lattice, so the centring has already been
    #: consumed by the reduction (measured: the reduced form of a cubic I cell with
    #: a = 5.8783 Å is (5.0908, 5.0908, 5.0908, 109.4712°, …) at exactly half the
    #: conventional volume, and the change of basis is the I → P transformation).
    #: **Do not pass this back to a routine that applies a centring** — see
    #: :func:`bravais_screen`, where doing so was a live bug.
    centring: str
    kind: str                       # "niggli" or "delaunay"
    #: gemmi's own ``is_niggli`` / ``is_buerger`` predicate, evaluated on the
    #: *input*.  Informational, and **not** a reliable "reduction changed nothing"
    #: signal on floating-point input: measured, a rhombohedral cell
    #: (3, 3, 3, 65°, 65°, 65°) whose reduction is a fixed point to 1e-15 reports
    #: ``already_reduced = False`` on the second pass, because the reduced
    #: parameters carry fp noise the predicate's own tolerance does not absorb.
    #: Idempotence is asserted on the cell parameters instead
    #: (``tests/test_indexing_reduce.py``).
    already_reduced: bool


@dataclass
class BravaisScreen:
    """What the two opinions say about the lattice symmetry, tolerance by
    tolerance, and what survives all of it."""

    reduced: ReducedCell
    by_obliquity: dict[float, str] = field(default_factory=dict)
    by_symprec: dict[float, str] = field(default_factory=dict)
    spglib_symbols: dict[float, str] = field(default_factory=dict)
    #: the more conservative of the two methods' *tightest*-tolerance answers —
    #: the symmetry that survives the whole sweep
    system: str = "triclinic"
    #: highest symmetry any tolerance of either method reported
    system_loosest: str = "triclinic"
    ambiguous: bool = False
    #: each method's tightest-tolerance answer, kept separately: their tolerances
    #: are different *kinds* of number (degrees of obliquity against Å), so a
    #: disagreement is information about the cell, not a bug in either
    system_gemmi: str = "triclinic"
    system_spglib: str = "triclinic"
    methods_disagree: bool = False


def lattice_vectors(cell: tuple[float, ...]) -> np.ndarray:
    """Row-vector lattice (3, 3) in a Cartesian frame, for spglib.

    The Cholesky factor of the direct metric: L·Lᵀ = G, so the rows of L are
    lattice vectors realising exactly that metric — the same construction
    ``wyckoff._compatible_lattice`` uses, and it works in any setting.
    """
    from ..crystallography.lattice import direct_metric_tensor
    return np.linalg.cholesky(np.asarray(direct_metric_tensor(*cell)))


def reduce_cell(cell: tuple[float, ...], centring: str = "P", *,
                kind: str = "niggli") -> ReducedCell:
    """Niggli (default) or Delaunay reduction, with the change of basis kept."""
    import gemmi

    uc = gemmi.UnitCell(*cell)
    gv = gemmi.GruberVector(uc, centring, track_change_of_basis=True)
    already = gv.is_niggli() if kind == "niggli" else gv.is_buerger()
    if kind == "niggli":
        gv.niggli_reduce()
    elif kind == "delaunay":
        gv.selling()
    else:
        raise ValueError(f"kind must be 'niggli' or 'delaunay', not {kind!r}")
    gv.normalize()
    out = gv.get_cell()
    return ReducedCell(
        cell=(out.a, out.b, out.c, out.alpha, out.beta, out.gamma),
        change_of_basis=gv.change_of_basis.triplet(), centring=centring,
        kind=kind, already_reduced=already)


def _system_from_number(number: int) -> str:
    for limit, system in _SYSTEM_BY_NUMBER:
        if number <= limit:
            return system
    raise ValueError(f"space-group number {number} out of range")


def bravais_screen(cell: tuple[float, ...], centring: str = "P", *,
                   cell_esd: np.ndarray | float = 1e-3,
                   obliquities: tuple[float, ...] = BRAVAIS_OBLIQUITIES,
                   symprec_sigmas: tuple[float, ...] = BRAVAIS_SYMPREC_SIGMAS,
                   ) -> BravaisScreen:
    """Lattice symmetry from gemmi and spglib, over a tolerance sweep.

    ``cell_esd`` scales the spglib ``symprec`` sweep, so the tolerance is a
    multiple of the *measured* precision rather than a fixed distance.
    """
    import gemmi
    import spglib

    reduced = reduce_cell(cell, centring)
    uc = gemmi.UnitCell(*reduced.cell)
    by_obliquity = {}
    for tol in obliquities:
        # "P", not ``reduced.centring``: the reduction already consumed the
        # centring and returned the *primitive* cell, so passing the input
        # centring back centres it a second time.  Measured, that is not a
        # subtlety — a cubic I cell came back **trigonal** from gemmi (6 lattice
        # rotations instead of 24) while spglib, which is handed the bare lattice,
        # correctly said Im-3m.  The two then "disagreed" on every centred
        # candidate, which set ``methods_disagree`` and ``ambiguous`` and so
        # capped every centred lattice's confidence at medium for good — about
        # half of all real structures.
        ops = gemmi.find_lattice_symmetry(uc, "P", tol)
        by_obliquity[tol] = _SYSTEM_BY_SYM_OPS.get(len(ops.sym_ops), "triclinic")

    esd = float(np.max(np.atleast_1d(np.asarray(cell_esd, dtype=np.float64))[:3]))
    esd = max(esd, 1e-6)
    lat = lattice_vectors(reduced.cell)
    by_symprec, symbols = {}, {}
    for k in symprec_sigmas:
        data = spglib.get_symmetry_dataset((lat.tolist(), [[0.0, 0.0, 0.0]], [1]),
                                           symprec=k * esd)
        if data is None:
            by_symprec[k], symbols[k] = "triclinic", ""
            continue
        by_symprec[k] = _system_from_number(int(data.number))
        symbols[k] = str(data.international)

    # loosening a tolerance can only *add* symmetry (asserted in
    # tests/test_indexing_reduce.py), so "stable across the sweep" is exactly the
    # tightest tolerance's answer, and the ambiguity is whether a looser one says
    # something higher
    gemmi_tight = by_obliquity[min(obliquities)]
    spglib_tight = by_symprec[min(symprec_sigmas)]
    inverse = {v: k for k, v in SYSTEM_RANK.items()}
    tightest = min(SYSTEM_RANK[gemmi_tight], SYSTEM_RANK[spglib_tight])
    loosest = max(max(SYSTEM_RANK[s] for s in by_obliquity.values()),
                  max(SYSTEM_RANK[s] for s in by_symprec.values()))
    return BravaisScreen(
        reduced=reduced, by_obliquity=by_obliquity, by_symprec=by_symprec,
        spglib_symbols=symbols, system=inverse[tightest],
        system_loosest=inverse[loosest], ambiguous=loosest != tightest,
        system_gemmi=gemmi_tight, system_spglib=spglib_tight,
        methods_disagree=gemmi_tight != spglib_tight)


def cell_from_vectors(lattice: np.ndarray
                      ) -> tuple[float, float, float, float, float, float]:
    """Cell parameters from row-vector lattice vectors — spglib's output form."""
    lat = np.asarray(lattice, dtype=np.float64)
    g = lat @ lat.T
    a, b, c = (float(np.sqrt(g[i, i])) for i in range(3))
    ang = [float(np.degrees(np.arccos(np.clip(g[m, n] / (l1 * l2), -1.0, 1.0))))
           for (m, n), (l1, l2) in (((1, 2), (b, c)), ((0, 2), (a, c)),
                                    ((0, 1), (a, b)))]
    return a, b, c, ang[0], ang[1], ang[2]


def conventional_cell(cell: tuple[float, ...], *, symprec: float = 1e-3
                      ) -> tuple[tuple[float, ...], str, str]:
    """The conventional (standardised) cell of a lattice, its centring and symbol.

    spglib's ``std_lattice`` is the standardisation, and it is the piece that
    cannot be got from a reduced cell alone: metric symmetry higher than the
    reduced primitive cell's shows up here as a *centred* conventional cell — a
    primitive bcc cell comes back as ``Im-3m`` with a cubic conventional lattice,
    which is the answer an engine that found the primitive cell needs to report.
    """
    import spglib

    lat = lattice_vectors(cell)
    data = spglib.get_symmetry_dataset((lat.tolist(), [[0.0, 0.0, 0.0]], [1]),
                                       symprec=symprec)
    if data is None:
        return tuple(cell), "P", ""
    symbol = str(data.international)
    return cell_from_vectors(np.asarray(data.std_lattice)), symbol[0], symbol


def reduced_af(af: np.ndarray) -> np.ndarray:
    """(A..F) of the Niggli-reduced form of this metric.

    Split out of :func:`same_lattice` because the reduction is the expensive half
    (a gemmi call) and a dedup pass compares every candidate against every kept
    one: reducing inside the comparison makes it O(N²) reductions where O(N) will
    do.  Measured on a monoclinic search that accepted ~5 000 raw candidates, that
    was the single largest cost in the engine.
    """
    from .qspace import af_from_cell, cell_from_af
    return af_from_cell(reduce_cell(cell_from_af(af)).cell)


def equal_reduced(red_a: np.ndarray, red_b: np.ndarray, *,
                  cov_a: np.ndarray | None = None,
                  cov_b: np.ndarray | None = None) -> tuple[bool, float]:
    """The χ² equality test on **already reduced** A..F vectors."""
    delta = np.asarray(red_a) - np.asarray(red_b)
    if cov_a is None or cov_b is None:
        scale = np.maximum(np.abs(red_a), np.abs(red_b))
        ok = bool(np.all(np.abs(delta) <= CELL_EQUALITY_RELATIVE * scale))
        return ok, float("nan")
    sigma = np.asarray(cov_a) + np.asarray(cov_b)
    chi2 = float(delta @ np.linalg.pinv(sigma, hermitian=True) @ delta)
    return chi2 <= CELL_EQUALITY_CHI2, chi2


def same_lattice(af_a: np.ndarray, af_b: np.ndarray, *,
                 cov_a: np.ndarray | None = None,
                 cov_b: np.ndarray | None = None) -> tuple[bool, float]:
    """Are these two A..F vectors the same lattice?  Returns (verdict, χ²).

    Both are Niggli-reduced first, so a *setting* change is equality rather than
    ambiguity — which is the whole reason dedup and geometrical ambiguity
    (WP-1020's ``ambiguity.py``) are different questions.  With covariances the
    test is χ² = ΔᵀΣ⁻¹Δ against :data:`CELL_EQUALITY_CHI2`; without, it falls back
    to :data:`CELL_EQUALITY_RELATIVE` on the reduced cell parameters and the
    returned χ² is NaN so a caller can see which test ran.
    """
    return equal_reduced(reduced_af(af_a), reduced_af(af_b),
                         cov_a=cov_a, cov_b=cov_b)


__all__ = ["BRAVAIS_OBLIQUITIES", "BRAVAIS_SYMPREC_SIGMAS",
           "CELL_EQUALITY_CHI2", "CELL_EQUALITY_RELATIVE", "SYSTEM_RANK",
           "BravaisScreen", "ReducedCell", "bravais_screen", "cell_from_vectors",
           "conventional_cell", "equal_reduced", "lattice_vectors",
           "reduce_cell", "reduced_af", "same_lattice"]
