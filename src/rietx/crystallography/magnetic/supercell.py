"""A commensurate k ≠ 0 magnetic structure, stated as a nuclear phase in its magnetic cell.

WP-1327 stores **one moment per atom of the nuclear asymmetric unit** and
propagates it over that site's magnetic orbit.  A commensurate k ≠ 0 structure
does not fit that shape in the *parent* cell: the moment is not periodic on the
parent lattice, so one nuclear orbit carries several different moments and there
is no field for the second (WP-1328 D3 refuses a k ≠ 0 magCIF for exactly this
reason, and its § 6.1 names the route out).

The route out is the one magCIF itself takes.  A commensurate structure is
stated in its **magnetic supercell**: the child cell whose lattice is
{t : k·t ∈ ℤ}, in which the moment *is* periodic.  In that cell

* the nuclear structure is the parent's, repeated — every parent lattice
  translation that is no longer a child lattice translation carries a second
  copy of every atom, and those copies are **independent sites of the child**;
* the magnetic group's anti-translation is an **anti-centring** of the child
  cell, so the two copies carry opposite moments and no new field is needed;
* the extra reciprocal-lattice points of the child are the satellites at
  Q = H ± k, and they arrive in the phase's own reflection list rather than as
  a second frozen set — which is what lets **one** scale serve the nuclear and
  the magnetic contribution.

So this module is a *restatement*, not a new physics term.  What it must not
get wrong is the bookkeeping, and the three things that would go wrong silently
are asserted rather than argued:

1. **A parent site counted twice.**  The child atom list is built by orbit
   partition — every position in the child cell belongs to exactly one child
   orbit and each orbit contributes exactly one asymmetric atom — and the
   partition is checked to cover the whole set exactly once.
2. **The child's nuclear space group not being the symbol it is given.**  The
   parent group carried through the cell transform generally contains
   operations that no Hermann-Mauguin symbol reproduces *in the child cell*
   (a ½ translation along a doubled axis becomes ¼, which is in no standard
   operation list).  :func:`magnetic_supercell` therefore checks that the
   symbol's operations, times the child's lattice cosets, reproduce the
   transformed group exactly — and when they do not, the child phase carries
   its **own operation list** under a bracketed label
   (:func:`resolve_child_group`, ``Phase.symmetry_operations``, Q-17) so that
   every orbit, multiplicity and absence still comes from the operations.  It
   used to refuse there, which was right while a phase could only store a
   symbol and cost the whole S3(a,b) direction of Ba₂FeSbSe₅; the check is
   unchanged and only the answer to "no symbol" is different.  A
   ``CHILD_GROUP_UNNAMED`` info diagnostic on
   :attr:`SupercellStatement.diagnostics` says which operations the symbol got
   wrong.
3. **A superlattice reflection with nuclear intensity on it.**  A doubled cell
   holding the parent's atoms twice has |F_N|² identically zero at every
   reciprocal-lattice point the parent does not have, by the phase sum, and
   that is a *test* (``tests/test_magnetic_supercell.py``) rather than a
   comment.

**Scope.** Commensurate k with 2k in the reciprocal lattice — the same fence
WP-1326, WP-1327 and M-7 carry — because that is where the child lattice has
index 2 and one anti-translation.  A k of higher denominator needs a larger
child cell and is M-8/M-11's; an incommensurate k has no child cell at all.

**The anti-centring has to be tied, not only seeded.**  The two cosets of one
parent site are independent *sites* of the child, so their moment DOFs are
independent columns of the fit — and one combination of those columns is the
**ferromagnetic** mode the declared group forbids.  Seeding the pair
antiparallel (which :func:`magnetic_supercell` does, by propagating one seed
over the group's own orbit) states the candidate correctly but does not keep a
refinement inside it; measured on Ba₆Co₆, a free fit leaves its own group by up
to 3.8 μ_B.  :func:`anti_translation_ties` is therefore part of the statement,
not an option: it returns the affine ties for
:meth:`rietx.Refinement.tie` that spend that freedom the way the symmetry
already spends it.  They *are* affine, and the reason is structural — an
(anti)centring's axial action is ±**I** rather than a rotation, which is
exactly the case modulus-and-angles carries linearly.
:func:`anti_translation_residual` is the check that they were applied, and the
number to quote beside any moment refined from a supercell statement.

This is **not** the moment-cardinality change WP-1328 § 6.1 item 2 asks for: it
does not let one nuclear orbit carry two independent moments, it makes two
nuclear orbits carry one. That is enough for a commensurate k with 2k ∈ L*,
where the child's magnetic asymmetric unit is the parent's; a larger child cell
would need the field.

References
----------
* Perez-Mato, J. M., Gallego, S. V., Tasci, E. S., Elcoro, L., de la Flor, G. &
  Aroyo, M. I. (2015). *Annu. Rev. Mater. Res.* **45**, 217 — magnetic
  symmetry, the magnetic supercell and MAGNDATA's stored form.
* Campbell, B. J., Stokes, H. T., Tanner, D. E. & Hatch, D. M. (2006).
  *J. Appl. Cryst.* **39**, 607 — parent + irrep + direction → structure, the
  workflow M-7's candidates come from.
* Hahn, T., ed. (2005). *International Tables for Crystallography, Vol. A* —
  sect. 5.1 for the (P, p) convention this module's transforms are written in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np

from ...schemas.common import Diagnostic, Parameter
from ...schemas.structure import (
    DISTORTION_AMPLITUDE_MAX_A,
    Atom,
    Cell,
    DistortionMode,
    MagneticSymmetry,
    Moment,
    Phase,
)
from ..symmetry import (
    SITE_TOL,
    CellConstraints,
    MetricConstraints,
    OperatorGroup,
    ReflectionSet,
    cell_constraints,
    expand_positions,
    get_spacegroup,
    refuse_an_unnamed_parent,
    resolve_group,
    unnamed_label,
)
from . import isotropy as _isotropy
from .moments import tilted_seed
from .operators import MagneticGroup, format_transform

__all__ = [
    "ChildGroup",
    "SupercellStatement",
    "DisplaciveStatement",
    "MultiComponentStatement",
    "FourierComponentSpec",
    "FourierStatement",
    "anti_translation_residual",
    "anti_translation_ties",
    "child_basis",
    "displacive_statement",
    "fourier_statement",
    "lattice_cosets",
    "magnetic_supercell",
    "seed_distortion_amplitudes",
]

#: How close two fractional coordinates must be to be the same site.  The
#: nuclear side's tolerance, deliberately: the child positions are the parent's
#: pushed through an exact rational transform, so nothing here is looser than
#: what ``site_orbit`` already accepts.
CHILD_SITE_TOL = SITE_TOL


@dataclass(frozen=True)
class SupercellStatement:
    """The nuclear phase in the magnetic cell, and how it was reached.

    ``phase`` is a complete :class:`~rietx.schemas.structure.Phase`: the child
    cell, the child's nuclear space-group symbol, one atom per child orbit, the
    magnetic space group as WP-1327's operator list **in that cell** with the
    anti-translation in its centring loop, and a moment on every atom the group
    puts one on.  It compiles and refines like any other magnetic phase — the
    whole point of the restatement.

    ``site_map[i]`` is ``(parent atom index, coset index)`` for child atom
    ``i``: which parent site it came from and which parent lattice coset put it
    there.  It is what lets a report say "Co1 and Co1′ are the two halves of
    one parent orbit" rather than leaving a reader to match coordinates.
    """

    phase: Phase
    transform: str
    #: |det P|, the child cell's volume in conventional parent cells: an
    #: ``int`` for every integral P, a ``Fraction`` when the child basis carries
    #: halves because it holds a centring vector of the parent (½ for
    #: F m -3 m at k = (0, 0, 1); :func:`lattice_cosets`).  It is not the
    #: number of integer-lattice cosets, which the two share only when P is
    #: integral.
    index: int | Fraction
    parent_space_group: str
    child_space_group: str
    group: MagneticGroup
    site_map: tuple[tuple[int, int], ...]
    k: tuple[str, str, str] | None
    #: Whether a Hermann-Mauguin symbol generates the child's nuclear group in
    #: the child cell.  ``False`` means ``phase.space_group`` is the bracketed
    #: *label* and ``phase.symmetry_operations`` is the group — the case that
    #: used to be a refusal (Q-17, ``resolve_child_group``).  A caller
    #: reporting the child group should print the label either way and read
    #: this only when it wants to say *why* the label looks the way it does.
    child_group_named: bool = True
    #: Info diagnostics about the statement itself, ``CHILD_GROUP_UNNAMED``
    #: among them.  Empty for every statement whose child group has a symbol,
    #: so a caller that ignores the field sees exactly what it saw before.
    diagnostics: tuple[Diagnostic, ...] = ()
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def volume_ratio(self) -> int | Fraction:
        """|det P| — how many parent cells the child cell holds."""
        return self.index

    def parent_reflection(self, hkl_parent) -> np.ndarray:
        """The child index of a parent reflection: h_child = Pᵀ·h_parent."""
        p = _matrix_of(self._cache.setdefault("basis", _parse_basis(self.transform)))
        return np.rint(p.T @ np.asarray(hkl_parent, dtype=np.float64)).astype(np.int64)


# ---------------------------------------------------------------------------
# the cell
# ---------------------------------------------------------------------------
def _matrix_of(basis) -> np.ndarray:
    return np.array([[float(v) for v in row] for row in basis], dtype=np.float64)


def _parse_basis(transform: str):
    from .operators import parse_transform

    p, _shift = parse_transform(transform)
    return p


def child_basis(space_group, k) -> tuple[tuple[Fraction, ...], ...]:
    """P for the magnetic cell of ``k``, **without** M-7's shortest-basis reduction.

    :func:`~.isotropy.magnetic_cell` reduces the basis so that spglib can
    identify a magnetic group in a cell no tabulated setting looks like — the
    right choice there, because nothing in M-7 needs the cell to be
    *conventional*.  Here it is the wrong one: a reduced hexagonal supercell
    comes out with γ = 60°, and the nuclear operations of a hexagonal
    Hermann-Mauguin symbol are written for γ = 120°.  A phase whose
    ``space_group`` symbol does not generate its own operations is the silent
    failure this module exists to avoid.

    So the basis is the unreduced one: the parent's primitive basis with the
    one vector that carries ε = −1 doubled, and every other ε = −1 vector
    shifted by it.  For a primitive parent that is the obvious doubling of one
    axis; for a centred one it is a primitive cell of the magnetic lattice, and
    the caller is told so by the symbol check in :func:`magnetic_supercell`.

    **When two or more primitive vectors carry ε = −1 (Q-17c), that recipe is
    ambiguous** — it names *which* ε = −1 vector is doubled and which is
    merely shifted, and the same doubled lattice has another, equally valid,
    primitive basis: shift the *other* way (``row − anti`` instead of
    ``row + anti``) while trading the doubled pivot for the sum
    (``row + anti``) as well.  For a k = (½,½,0)-type doubling in a P
    tetragonal/orthorhombic parent the first recipe gives ``2a, a+b, c``, in
    which mm2/4mm's axes sit along the parent's [110]-type directions and the
    invariant metric ties one length to *another length times a cosine*
    (b² = 2ab·cos γ) — inexpressible by :class:`~rietx.crystallography.
    symmetry.CellConstraints`, which is only ties and fixed angles.  The
    second recipe gives ``a+b, −a+b, c``, the √2×√2 cell in which those same
    operations are conventional (a′ = b′, γ′ = 90°).  Both are the *same*
    lattice — det P = 2 either way — so nothing here is a different physical
    cell, only a different, equally legitimate, choice of primitive generators
    of it.

    The choice is therefore made **empirically, against the oracle that
    already exists for this exact question** —
    :func:`~rietx.crystallography.symmetry.cell_constraints_from_rotations`
    (Q-17b) — but fed the rotation set of a **real candidate's isotropy
    subgroup**, not the parent's own full point group.  The two disagree on a
    case this rung must not disturb: Ba₂FeSbSe₅'s S₃(a,b), Pnma at
    k = (½,0,½) in ``2a,b,a+c`` (Q-17), fails for the parent's full *mmm*
    point group (one of its two mirrors does not fit that cell) but is
    exactly the tested, already-built statement, because the real candidates
    there use a 2- or 4-operation isotropy subgroup that never needs the
    mirror the full group's failure comes from — testing the full group would
    "fix" a cell that was never broken, at the cost of every transform string
    and bracketed label Q-17's own tests already pin.  So
    :func:`_choose_child_basis` probes M-7's own :func:`~.isotropy.candidates`
    against a **generic** site (a site enters ``candidates`` only through its
    stabiliser and orbit, so a generic one's isotropy subgroups are the same
    ones any real site's would give — Q-17's own convention), which is the
    same *k*-family the twenty-two (½,½,0) children were counted from and the
    same construction :func:`magnetic_supercell`'s ``nuclear_group="magnetic"``
    route performs for real.

    The **current** ``(2·anti, row+anti, …)`` choice is kept whenever *at
    least one* real candidate verifies with it — which is every pre-existing
    case, Ba₂FeSbSe₅ included, and every one of the (0,0,½)-type family too.
    Only when *no* candidate verifies with it — the twenty-two (½,½,0)
    children — are the alternates tried, each scored by whether at least one
    of its own verifying candidates also names a tabulated ``closest_type``
    (the conventional cell a published assignment is likeliest to use), then
    by the smallest transform-matrix entries (deterministic tie-break: max
    |entry|, then their sum, then the entries themselves in row-major order —
    see :func:`_choose_child_basis`).  When nothing verifies at all, the
    pre-Q17c choice is returned unchanged, so the eventual refusal is still
    :func:`_unnamed_child`'s, with its full diagnostic text, rather than a
    substitution made silently here.

    When only **one** vector carries ε = −1 — every (0,0,½)-type doubling,
    and the hexagonal γ = 60°-vs-120° trap this docstring already guards —
    there is no ambiguity to resolve (there is only the one ε = −1 vector, so
    no "other" vector to trade the shift against) and the historical choice is
    returned bit-identically, without touching the oracle at all.
    """
    sg = _isotropy._irreps._resolve(space_group)
    kk = _isotropy.as_kvector(k)
    # the scope fence, and the coset list, are magnetic_cell's — asked rather
    # than re-derived, so there is one authority on what k this rung admits
    cell = _isotropy.magnetic_cell(sg, kk)
    if not cell.doubled:
        return cell.basis
    prim = _isotropy._irreps.primitive_basis(sg)
    signs = [_isotropy._translation_sign(kk, row) for row in prim]
    anti_indices = [i for i, s in enumerate(signs) if s < 0]
    pivot = anti_indices[0]
    anti = prim[pivot]
    rows: list[tuple[Fraction, ...]] = []
    for i, row in enumerate(prim):
        if i == pivot:
            rows.append(tuple(2 * Fraction(c) for c in row))
        elif signs[i] < 0:
            rows.append(tuple(Fraction(c) + Fraction(a) for c, a in zip(row, anti)))
        else:
            rows.append(tuple(Fraction(c) for c in row))
    if len(anti_indices) < 2:
        # one ε = −1 vector: nothing to choose between, bit-identical to the
        # pre-Q17c behaviour.
        return _rows_to_columns(rows)

    candidate_rows = [rows]
    for i in anti_indices[1:]:
        row = prim[i]
        alt = list(rows)
        alt[pivot] = tuple(Fraction(c) + Fraction(a) for c, a in zip(row, anti))
        alt[i] = tuple(Fraction(c) - Fraction(a) for c, a in zip(row, anti))
        candidate_rows.append(alt)
    return _rows_to_columns(_choose_child_basis(space_group, kk, candidate_rows))


def _rows_to_columns(rows) -> tuple[tuple[Fraction, ...], ...]:
    """Three basis-vector rows as the (P, p)-convention matrix (columns)."""
    return tuple(tuple(rows[j][i] for j in range(3)) for i in range(3))


#: Generic (non-special) fractional site used only to probe which magnetic
#: candidates M-7 would generate for a (parent, k) pair, when the caller's own
#: site is not yet to hand — ``child_basis`` receives only ``space_group`` and
#: ``k``, deliberately, since the child *cell* does not depend on which site or
#: candidate direction will use it.  ``candidates`` reads a site only through
#: its stabiliser and its orbit (Q-17's own docstring; see
#: ``tests/test_operator_list_phase.py``), so a generic site's isotropy
#: subgroups are the same ones any real site's would give, just not narrowed
#: further by a site that happens to sit on a special position.
_BASIS_PROBE_SITE = (Fraction(11, 100), Fraction(13, 100), Fraction(17, 100))


def _candidate_basis_score(candidate, p_columns) -> tuple[bool, bool]:
    """``(verifies, closest_type_resolves)`` for one real candidate's isotropy
    subgroup, carried through the transform ``p_columns``.

    Mirrors :func:`magnetic_supercell`'s own ``nuclear_group="magnetic"``
    construction exactly (the ``step`` composition is copied from there), so
    this asks the identical question that function will later ask for real —
    not a proxy for it.  Any failure along the way (a transform that does not
    map the candidate's own cell onto a lattice, an inexpressible metric)
    reads as ``(False, False)`` rather than propagating: a candidate failing
    here is exactly the fact the caller is choosing against, not a bug.

    **"Verifies" still means a plain** :class:`~rietx.crystallography.symmetry.
    CellConstraints` **here, unchanged by Q-17d.** Before Q-17d, an
    inexpressible metric made :func:`~rietx.crystallography.symmetry.
    cell_constraints` raise, which this function read as "this basis is
    wrong for this candidate" — exactly the signal Q-17c's basis choice is
    built on (six parents fall back to the sum/difference basis *because*
    every real candidate they have fails this probe on the pre-existing
    one). Q-17d made that same case buildable, by returning a
    :class:`~rietx.crystallography.symmetry.MetricConstraints` instead of
    raising — a real improvement at :func:`_unnamed_child`, where the
    question is "can this cell be stated at all", but the *wrong* answer
    here, where the question is "is this basis the conventional one for this
    candidate's point group": a length tied to another length times a cosine
    is precisely the non-conventional-axes symptom this probe exists to
    detect, so a :class:`~rietx.crystallography.symmetry.MetricConstraints`
    result is still scored as *not verifying* — the same outcome the raise
    used to produce, so Q-17c's basis choice is bit-identical to before
    Q-17d for every parent it was measured on (regression-tested in
    ``tests/test_child_basis_choice.py``).
    """
    try:
        p = [[Fraction(v) for v in row] for row in p_columns]
        p_candidate = [[Fraction(v) for v in row] for row in candidate.cell.basis]
        step = _mat_mul(_isotropy._exact_inverse(p_candidate), p)
        nuclear = _colourless(candidate.group.transformed(
            format_transform(_isotropy._exact_inverse(step),
                             (Fraction(0), Fraction(0), Fraction(0)))))
        probe = OperatorGroup(label="", xyz=_child_triplets(nuclear))
        constraints = cell_constraints(probe)
        if isinstance(constraints, MetricConstraints):
            return False, False
        assert isinstance(constraints, CellConstraints)
    except ValueError:
        return False, False
    try:
        probe.closest_type.xhm()
        return True, True
    except ValueError:
        return True, False


def _basis_verifies(space_group, kk, p_columns) -> tuple[bool, bool]:
    """``(some_candidate_verifies, some_verifying_candidate_is_named)`` for
    the transform ``p_columns``, probed against :data:`_BASIS_PROBE_SITE`'s
    real candidates at ``(space_group, kk)``.

    **Restricted to candidates M-7 itself cannot identify**
    (``identification is None`` — the population ``magnetic_supercell``'s own
    unnamed path exists for, and the exact filter Q-17's and Q-17b's own sweep
    tests use).  A candidate M-7 *can* identify never reaches
    :func:`_unnamed_child` at all in production — its child resolves through
    the ordinary Hermann-Mauguin symbol lookup, which is always expressible
    and does not care what this function says — so letting one of those "pass"
    here would be answering a question production never asks.  Measured on
    P c c n at k=(½,½,0): the generic site gives six candidates, four of them
    identified MSGs (13.70, 3.4) whose *own* metric already verifies in the
    pre-Q17c basis (trivially — small point groups almost always do), and two
    unidentified ones that do not (Q-17b's actual finding); counting the
    identified ones as evidence the current basis "already works" would have
    masked the very refusal this rung exists to fix.  ``identify_groups=True``
    is therefore paid for (unlike a cheaper rotations-only probe) exactly to
    be able to apply this filter; ``verify=False`` still skips the
    moment-family cross-check, irrelevant to a cell-metric question.  A k this
    rung's scope fence refuses, or any other ``ValueError`` from the
    enumeration itself, reads as "nothing verifies" rather than propagating —
    the same conservative default as an individual candidate's own failure,
    and (see :func:`_choose_child_basis`) exactly what keeps a (parent, k)
    whose generic site simply has no unidentified candidate at all — Pnma at
    k=(½,0,½), whose real unnamed candidate (Ba₂FeSbSe₅'s S₃(a,b)) needs a
    special, non-generic site to appear — on its pre-Q17c basis rather than
    switching it on no evidence either way.
    """
    try:
        found = _isotropy.candidates(space_group, _BASIS_PROBE_SITE, kk,
                                     identify_groups=True, verify=False)
    except ValueError:
        return False, False
    verifies = named = False
    for candidate in found.candidates:
        if candidate.identification is not None:
            continue
        ok, is_named = _candidate_basis_score(candidate, p_columns)
        verifies = verifies or ok
        named = named or (ok and is_named)
    return verifies, named


def _choose_child_basis(space_group, kk, candidate_rows):
    """The candidate (rows-format) basis to use, preferring the current one.

    ``candidate_rows[0]`` is always the pre-Q17c ``(2·anti, row+anti, …)``
    choice; kept whenever :func:`_basis_verifies` finds at least one real
    candidate that verifies with it — every pre-existing case this rung must
    not disturb already does (Ba₂FeSbSe₅'s S₃(a,b) among them), and switching
    a cell that already works would be a different, gratuitous choice with a
    real cost (every pinned transform string and bracketed label) and no
    benefit.  The alternates — the sum/difference form for each other
    ε = −1 vector paired with the pivot — are tried, in order, only when
    *no* real candidate verifies with the current choice at all (the
    twenty-two (½,½,0) children); the first with at least one verifying
    candidate is kept, preferring one whose closest tabulated type also
    resolves, then the smallest transform-matrix entries (max |entry|, then
    their sum, then the entries themselves in row-major order — deterministic,
    not dependent on iteration order). When nothing verifies at all, the
    pre-Q17c choice is returned unchanged, so the eventual refusal is still
    :func:`_unnamed_child`'s, with its full diagnostic text.
    """
    current = candidate_rows[0]
    verifies, _named = _basis_verifies(space_group, kk, _rows_to_columns(current))
    if verifies:
        return current
    scored = []
    for rows in candidate_rows[1:]:
        p_columns = _rows_to_columns(rows)
        verifies, named = _basis_verifies(space_group, kk, p_columns)
        if not verifies:
            continue
        entries = [abs(v) for row in p_columns for v in row]
        scored.append((0 if named else 1, max(entries), sum(entries),
                       tuple(entries), rows))
    if not scored:
        return current
    scored.sort(key=lambda item: item[:4])
    return scored[0][-1]


def _transform_string(basis) -> str:
    return format_transform([list(row) for row in basis],
                            (Fraction(0), Fraction(0), Fraction(0)))


def _child_lattice(parent_cell, basis) -> np.ndarray:
    """The child cell's lattice vectors as **rows**, in Å.

    ``adp.cartesian_basis`` returns the direct lattice vectors as *columns* of
    M with MᵀM = G, so the row-vector matrix is Mᵀ; (a′,b′,c′) = (a,b,c)·P then
    makes the child's row matrix Pᵀ·Mᵀ.  Getting that transpose wrong produces
    a cell with the right volume and the wrong angles, which is exactly the
    kind of error a volume check does not catch — so the cell parameters below
    come from the **metric** instead, and this function exists only for
    spglib, which wants a lattice and not a metric.
    """
    from ..adp import cartesian_basis

    rows = np.asarray(cartesian_basis(*parent_cell), dtype=np.float64).T
    return _matrix_of(basis).T @ rows


def _child_cell_parameters(parent_cell, basis) -> tuple[float, ...]:
    """(a, b, c, α, β, γ) of the child cell, from the parent's metric and P.

    G′ = Pᵀ·G·P exactly — no Cartesian frame, no Cholesky, so a right angle
    stays a right angle to the last bit.  The *cosine* is then snapped onto the
    exact values a lattice symmetry can force (0, ±½): a hexagonal γ comes out
    of ``arccos(-0.5000000000000001)`` as 119.999999999999986, and a cell whose
    γ is not 120 is a cell whose space-group constraint the refinement has to
    re-impose.  The snap is at 1e-12 on the cosine, far below any physical
    departure and far above the rounding it removes.
    """
    from ..adp import direct_metric_tensor

    p = _matrix_of(basis)
    g = p.T @ np.asarray(direct_metric_tensor(*parent_cell),
                         dtype=np.float64) @ p
    lengths = np.sqrt(np.diag(g))
    angles = []
    for i, j in ((1, 2), (0, 2), (0, 1)):
        cosine = float(g[i, j] / (lengths[i] * lengths[j]))
        for exact in (0.0, 0.5, -0.5):
            if abs(cosine - exact) <= 1e-12:
                cosine = exact
                break
        angles.append(float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))))
    return (float(lengths[0]), float(lengths[1]), float(lengths[2]), *angles)


# ---------------------------------------------------------------------------
# the group
# ---------------------------------------------------------------------------
def _nuclear_operations(group: MagneticGroup) -> set[tuple]:
    """The group's operations with the time-reversal sign dropped.

    A magnetic operation {R | t, ε} moves the *nucleus* by {R | t} whatever ε
    is, so this is the nuclear space group of the child structure — including
    the anti-translation, which as a nuclear operation is an ordinary lattice
    translation and is a symmetry of the nuclear structure.
    """
    return {(tuple(map(tuple, op.rotation)),
             tuple(Fraction(v) % 1 for v in op.translation))
            for op in group.all_operations()}


def _nuclear_group_of(space_group, symmetry_operations=None) -> MagneticGroup:
    """A space group as a **colourless** :class:`MagneticGroup`, ε = +1 throughout.

    Not a grey group: 1' is not in it, so it is the nuclear group and nothing
    more.  It exists only to be handed to ``MagneticGroup.transformed``, whose
    lattice completion is what supplies the child cell's extra translation —
    that method is the one piece of operator algebra in the package that knows
    how to enlarge a cell, and writing a second one here for the nuclear case
    would be the drift this module's docstring is written against.

    ``symmetry_operations`` is a phase's own explicit operator list
    (``Phase.symmetry_operations``), for the case ``space_group`` is a
    bracketed, unnamed label (stage3 D2): :func:`~..symmetry.resolve_group`
    reads the operators directly rather than resolving the label through
    gemmi, exactly as every other consumer of a phase's own group already
    does.  ``None`` (every call before this parameter existed) is bit-
    identical to the old ``get_spacegroup(symbol)`` path.
    """
    from .operators import MagneticOperator

    sg = resolve_group(space_group, symmetry_operations)
    operations = []
    for op in sg.operations():
        rot = [[int(round(v / op.DEN)) for v in row] for row in op.rot]
        tran = [Fraction(int(v), op.DEN) for v in op.tran]
        operations.append(MagneticOperator.build(rot, tran, 1))
    return MagneticGroup.from_operations(operations, setting=str(space_group))


def _settings_of(symbol: str) -> tuple[str, ...]:
    """Every tabulated setting of the space-group *type* ``symbol`` names.

    The identified symbol first, then its axis-permutation and origin-choice
    siblings in table order, so a group that is expressible in exactly one of
    them is found and one that is expressible in none is refused with the count.
    """
    import gemmi

    try:
        number = get_spacegroup(symbol).number
    except (ValueError, RuntimeError):
        return (symbol,)
    out = [get_spacegroup(symbol).xhm()]
    for sg in gemmi.spacegroup_table():
        if sg.number == number and sg.xhm() not in out:
            out.append(sg.xhm())
    return tuple(out)


def _colourless(group: MagneticGroup) -> MagneticGroup:
    """The magnetic group with every time-reversal sign set to +1.

    The nuclear part of a magnetic space group: {R | t} for every {R | t, ε} in
    it.  Used by ``nuclear_group="magnetic"`` — see
    :func:`magnetic_supercell` for when that is the only correct choice.
    """
    from .operators import MagneticOperator

    return MagneticGroup.from_operations([
        MagneticOperator.build([[int(v) for v in row] for row in op.rotation],
                               list(op.translation), 1)
        for op in group.all_operations()], setting=group.setting)


def _symbol_operations(symbol: str) -> set[tuple]:
    """The operations a Hermann-Mauguin symbol generates, as exact rationals."""
    sg = get_spacegroup(symbol)
    out = set()
    for op in sg.operations():
        rot = tuple(tuple(int(round(v / op.DEN)) for v in row) for row in op.rot)
        tran = tuple(Fraction(int(v), op.DEN) % 1 for v in op.tran)
        out.add((rot, tran))
    return out


def _identify_child_space_group(group: MagneticGroup, lattice) -> str | None:
    """spglib's identification of the child's **nuclear** group, or ``None``.

    The magnetic identification is M-5's and lives on the group; what is wanted
    here is the plain space-group type of the same operation list with ε
    dropped, because that is the symbol :class:`Phase` stores and the symbol
    ``generate_reflections`` resolves.
    """
    import spglib

    ops = sorted(_nuclear_operations(group))
    rotations = np.array([o[0] for o in ops], dtype="intc")
    translations = np.array([[float(v) for v in o[1]] for o in ops],
                            dtype="double")
    try:
        found = spglib.get_spacegroup_type_from_symmetry(
            rotations, translations, lattice=np.asarray(lattice, dtype="double"))
    except Exception:                       # pragma: no cover - spglib refusal
        return None
    if not found:
        return None
    symbol = found.get("international_short") or found.get("international")
    if not symbol:
        return None
    # spglib writes screw axes with an underscore (``P2_1/m``, ``P4_2/mnm``);
    # rietx's resolver and gemmi's table spell them without one (``P21/m``).
    # Measured on Ba2FeSbSe5, Pnma at k = (1/2, 0, 1/2): the child came back as
    # 'P2_1/m', the resolver refused the underscore, and every candidate was
    # reported as inexpressible when all four were P 1 21/m 1 supercells.
    return str(symbol).replace("_", "")


def _cosets(group: MagneticGroup, symbol: str) -> tuple[tuple[Fraction, ...], ...]:
    """The pure translations of the child group that the symbol does not carry."""
    symbol_ops = _symbol_operations(symbol)
    identity = tuple(tuple(int(i == j) for j in range(3)) for i in range(3))
    out = []
    for rot, tran in sorted(_nuclear_operations(group)):
        if rot == identity and (rot, tran) not in symbol_ops:
            out.append(tran)
    return tuple(out)


@dataclass(frozen=True)
class ChildGroup:
    """The child cell's nuclear group, named or not.

    ``named`` is what a caller branches on.  When it is true, ``symbol`` is the
    Hermann-Mauguin symbol whose operations times ``cosets`` **are** the child
    group — the old contract, unchanged — and ``operations`` is ``None``, so
    the phase built from it is byte-identical to what this module built before.
    When it is false there is no such symbol (see
    :func:`resolve_child_group`), ``symbol`` is the closest standard *type*,
    ``label`` is the bracketed form that goes in
    :attr:`~rietx.schemas.structure.Phase.space_group`, ``operations`` is the
    child group's own ``x,y,z`` list — the phase's symmetry from then on — and
    ``reason`` is the diagnostic text saying which operations the symbol got
    wrong.

    ``label`` is the string to store either way, so a caller need not branch to
    build the phase.
    """

    named: bool
    symbol: str
    label: str
    cosets: tuple
    operations: tuple[str, ...] | None
    reason: str

    @property
    def group(self):
        """The group object every symmetry consumer should read."""
        from ..symmetry import resolve_group

        return resolve_group(self.label, self.operations)


def _child_triplets(group: MagneticGroup) -> tuple[str, ...]:
    """The child's **nuclear** operations as ``x,y,z`` triplets, deterministic.

    Sorted on the exact (rotation, translation) key, because the list is stored
    on a phase and serialized: two runs of the same statement must give the
    same document, and ``set`` iteration order would not.
    """
    import gemmi

    out = []
    for rot, tran in sorted(_nuclear_operations(group)):
        op = gemmi.Op("x,y,z")
        op.rot = [[int(v) * gemmi.Op.DEN for v in row] for row in rot]
        op.tran = [int(round(float(v) * gemmi.Op.DEN)) for v in tran]
        out.append(op.triplet())
    return tuple(out)


def _unnamed_child(group: MagneticGroup, head: str, transform: str,
                   detail: str) -> ChildGroup:
    """A :class:`ChildGroup` stated as its operation list — or the old refusal.

    **What used to be the one thing an operation list could not supply is now
    three, and only the third still refuses.** A phase cannot even build a
    ``ParameterTable`` without cell metric constraints: ``symmetry.
    cell_constraints`` needs a crystal system, a monoclinic unique axis and
    the ``R``-axes flag.  Before Q-17b those came *only* from the tabulated
    group sharing the list's point group and lattice
    (:attr:`~rietx.crystallography.symmetry.OperatorGroup.closest_type`), an
    orientation lookup that fails for a child cell whose axes are not
    conventional for its own point group — measured on 39 of the 39 unnamed
    candidates in Q-17's all-group k-sweep, every one a c- or n-glide group
    doubled along the glide's own translation.  Q-17b adds
    :func:`~rietx.crystallography.symmetry.cell_constraints_from_rotations`,
    which solves the same constraints directly from the rotation set (Rᵀ·G·R
    = G) and needs no lookup at all — so this now falls back to it whenever
    ``closest_type`` fails.  Q-17c's basis choice (``child_basis``) then
    resolved all 39 of those to a tie/fixed-angle pair; the case that
    survives both is a real structure outside that sweep, Ba₂FeSbSe₅'s
    S1(rank 1)#2 at k=(0,½,½), whose doubled-and-centred child cell needs a
    length-times-cosine relation :class:`~rietx.crystallography.symmetry.
    CellConstraints` (ties and fixed angles only) cannot state.  Q-17d's
    :class:`~rietx.crystallography.symmetry.MetricConstraints` is the third
    thing an operation list can now supply: the cell's metric coordinates
    directly, for ``ParameterTable`` to refine instead of ties.

    Everything none of the three names is still refused, and refusing there
    is still the right call: building the phase anyway would move the
    failure from this function to the first compile, where the message would
    be about a crystal system rather than about a cell transform.
    """
    triplets = _child_triplets(group)
    label = unnamed_label(head, f"unnamed in {transform.split(';')[0]}")
    probe = OperatorGroup(label=label, xyz=triplets)
    try:
        closest = probe.closest_type.xhm()
        constraint_source = f"the closest standard type by point group and lattice ({closest!r})"
    except ValueError as exc:
        try:
            derived = cell_constraints(probe)
        except ValueError as derive_exc:
            raise ValueError(
                f"magnetic_supercell(): the child cell {transform!r} carries the "
                f"parent's space group to an operation list that no "
                f"Hermann-Mauguin symbol reproduces in that cell — {detail}. "
                f"That happens when a parent operation's translation along the "
                f"doubled axis is a half, which becomes a quarter in the child "
                f"cell and appears in no standard operation list. A phase can "
                f"carry its own operation list (Phase.symmetry_operations) for "
                f"exactly this case, and that is what this function does "
                f"whenever it can — but not here: the list's own point group "
                f"and lattice name no tabulated group either ({exc}), and its "
                f"metric constraints cannot be derived directly from the "
                f"rotation set either ({derive_exc}), so this cell's metric "
                f"constraints are undefined and a phase built on it would get "
                f"the wrong site orbits and the wrong systematic absences from "
                f"a cell nothing constrains. State this structure in the "
                f"magnetic group's nuclear part (nuclear_group='magnetic'), "
                f"restate it by hand in a cell whose axes are conventional for "
                f"the child point group, or refine it in the parent cell with "
                f"a propagation vector and a Le Bail stage."
            ) from derive_exc
        if isinstance(derived, MetricConstraints):
            constraint_source = (
                f"the operation list's own rotations, refined on the "
                f"{derived.m} metric coordinate(s) of its invariant subspace "
                f"rather than stated as ties and fixed angles (Q-17d) — "
                f"{derived.relation}")
        else:
            constraint_source = (
                "the operation list's own rotations (no tabulated type shares its "
                "point group and lattice: " + str(exc) + ")")
    return ChildGroup(
        named=False, symbol=head, label=label,
        cosets=((Fraction(0), Fraction(0), Fraction(0)),
                *_cosets_of_the_operation_list(group)),
        operations=triplets,
        reason=(
            f"{detail}. That happens when a parent operation's translation "
            f"along the doubled axis is a half, which becomes a quarter in the "
            f"child cell and appears in no standard operation list. The child "
            f"phase therefore carries its own {len(triplets)} symmetry "
            f"operations ({', '.join(triplets)}) and its space_group is the "
            f"label {label!r} — the site orbits, the site multiplicities and "
            f"the systematic absences all come from the operation list, and "
            f"the cell's metric constraints from {constraint_source}, so "
            f"nothing is guessed from the label. What is *not* available for "
            f"such a group is a Wyckoff letter and a setting-comparison "
            f"warning, both of which are properties of a tabulated setting"))


def resolve_child_group(group: MagneticGroup, symbol: str | None,
                        transform: str) -> ChildGroup:
    """The child's nuclear group as a symbol if one generates it, else as a list.

    **What this used to do, and why it changed.**  A parent operation carrying
    a ½ translation along the doubled axis becomes a ¼ in the child cell, and ¼
    appears in no standard operation list — so for such a parent there is *no*
    Hermann-Mauguin symbol that generates the child's nuclear group in the
    child's cell.  Until Q-17 a ``Phase`` could only store a symbol, so the
    only honest answer was a refusal: a phase whose symbol does not generate
    its own operations gets the wrong site orbits and the wrong systematic
    absences, and a fit on it converges anyway.  That refusal cost real work —
    Ba₂FeSbSe₅'s S3(a,b) direction could not be tested at all, and M-1's
    acceptance table carries the gap.

    A phase can now carry its own operation list
    (``Phase.symmetry_operations``), so the answer is the list plus a label
    that says the symbol is only the closest type.  Nothing is loosened: the
    check is the same set comparison it always was, and the *named* branch
    returns exactly what it returned before.  What changes is the unnamed
    branch, which now states the group instead of refusing to.
    """
    nuclear = _nuclear_operations(group)
    tried: list[str] = []
    detail = ""
    if symbol is None:
        # spglib named no type at all, which is the same fact one step earlier:
        # the setting is not one its tables recognise.  The label's leading
        # half is then whatever the operation list's own point group and
        # lattice are, which is what ``_unnamed_child`` looks up anyway.
        probe = OperatorGroup(label="", xyz=_child_triplets(group))
        try:
            head = probe.closest_type.xhm()
        except ValueError:
            head = ""
        return _unnamed_child(
            group, head, transform,
            "spglib identifies no nuclear space-group *type* for this "
            "operation list at all, so the setting is not one its tables "
            "recognise")
    # **Every setting of the identified type, not only its standard one.**
    # spglib identifies a *type*; which of its axis settings the child cell is
    # in is a separate fact, and the child cell's axes are whatever the
    # transform made them.  Mn₃O₄'s child group comes back as ``Pbcn`` (#60)
    # and the cell is in the ``bca`` setting, where the symbol is **Pbna** —
    # which is the symbol the GSAS-II tutorial names in prose.  Refusing on the
    # standard setting alone would refuse a statement that is perfectly
    # expressible one qualifier over.
    for resolved in _settings_of(symbol):
        tried.append(resolved)
        try:
            symbol_ops = _symbol_operations(resolved)
        except (ValueError, RuntimeError):
            continue
        cosets = ((Fraction(0), Fraction(0), Fraction(0)),
                  *_cosets(group, resolved))
        built = {(rot, tuple((t + c) % 1 for t, c in zip(tran, coset)))
                 for rot, tran in symbol_ops for coset in cosets}
        if built == nuclear:
            return ChildGroup(named=True, symbol=resolved, label=resolved,
                              cosets=cosets, operations=None, reason="")
        missing, extra = sorted(nuclear - built), sorted(built - nuclear)
        detail = (
            f"and none of its {len(tried)} setting(s) reproduces it — {resolved!r} "
            f"times the {len(cosets)} lattice coset(s) of this cell "
            f"{'omits ' + str(len(missing)) + ' of its operations' if missing else ''}"
            f"{' and ' if missing and extra else ''}"
            f"{'adds ' + str(len(extra)) + ' it does not have' if extra else ''}")
    if not detail:
        detail = (f"and rietx cannot resolve any setting of {symbol!r} to an "
                  f"operation list, which is the same fact one step earlier")
    return _unnamed_child(
        group, symbol, transform,
        f"spglib identifies the child's nuclear group as {symbol!r}, {detail}")


def _cosets_of_the_operation_list(group: MagneticGroup
                                  ) -> tuple[tuple[Fraction, ...], ...]:
    """The pure translations of the child group, for an unnamed one.

    The named branch takes these relative to the symbol's own operations
    (:func:`_cosets`); with no symbol there is nothing to subtract, so every
    pure translation but the identity is a coset representative.  Used only to
    fill :attr:`ChildGroup.cosets`, which callers read for its *length* — the
    number of parent cells the child holds under this group.
    """
    identity = tuple(tuple(int(i == j) for j in range(3)) for i in range(3))
    zero = (Fraction(0), Fraction(0), Fraction(0))
    return tuple(tran for rot, tran in sorted(_nuclear_operations(group))
                 if rot == identity and tuple(tran) != zero)


def _sign_consistent_operations(cand, m_matrix, ops, *, tol: float = 1e-6
                                ) -> set[tuple]:
    r"""The subset of ``ops`` that is a symmetry of ``cand``'s own **signed**
    field, not only of its positions (M2d).

    ``_colourless`` drops which copy of a grey operation {R | t, ±1} a
    candidate's own isotropy subgroup actually carries, and every consumer of
    the *declared* nuclear group downstream — chiefly
    ``crystallography.structure_factor.py``'s ``select_orbit_ops``/
    ``_orbit_terms``, called through ``expand_positions`` — propagates a
    representative's mode vector to its orbit siblings by the bare rotation,
    which is only correct for the ε = +1 copy. For a candidate whose
    order-parameter direction is 1-dimensional (or whose components never
    split) that loss is harmless: every operation of the colourless group
    that moves a listed position at all turns out to carry the same, single
    character on every component, and this function returns ``ops`` back
    unchanged (measured on S1(a,b), S2(a,b), S4(a,b) of the toy fixture in
    ``tests/test_multi_component_statements.py`` — checks/M2B's own controls).
    S3(a,b) on the same fixture is where it is not (checks/
    M2B_SINGLE_COMPONENT_SIGN_CHECK.md): one of its declared operations is the
    *cross-coset* copy (rotation composed with the child lattice's own
    anti-translation-derived coset shift) and carries ε = +1 on two of its
    four free amplitudes and ε = −1 on the other two — a single scalar ε
    cannot state that, and dropping the operation (rather than keeping it
    with a wrong assumed sign) is the only choice available to a group whose
    operators carry one ε each.

    ``cand`` is one of :mod:`.isotropy`'s ``MagneticCandidate`` objects
    (``kind="displacive"`` or ``"magnetic"`` — the test is the same shape for
    either; the axial-vs-polar distinction is already baked into
    ``cand.configurations`` by :func:`~.isotropy.order_parameter_space`, so
    this function never itself decides which action a component takes).
    ``m_matrix`` carries ``cand.positions``/``cand.configurations`` from M-7's
    own cell into the cell ``ops`` is expressed in — the same matrix
    :func:`_mode_vectors` and :func:`_component_respects_declared_symmetry`
    use, because a mode vector is contravariant and one matrix carries both
    the positions and the components.

    An operation with no free amplitude to check (``cand.configurations`` has
    zero rows — an undistorted parent, or a direction with no free
    amplitude) is vacuously kept, matching
    :func:`_component_respects_declared_symmetry`'s own early return. An
    operation whose image matches no listed position at all is dropped rather
    than kept — the conservative default :func:`_component_respects_declared_symmetry`
    already takes, since an operation this rung cannot verify is not one it
    should trust.

    The identity is always kept, and the result always contains it, so
    :func:`~.operators.MagneticGroup.from_operations` never sees an empty
    list. **The result is a group in every case this rung has measured** (a
    product of two sign-consistent operations propagates ``cand``'s own field
    correctly twice in a row, hence once) — ``from_operations`` is the check
    that would catch it not being one (it raises on a set that does not
    close), so this function does not re-derive closure itself.
    """
    identity = tuple(tuple(int(i == j) for j in range(3)) for i in range(3))
    if cand.configurations.shape[0] == 0:
        return set(ops)
    moved = np.asarray([m_matrix @ q for q in cand.positions], dtype=np.float64) % 1.0
    configs = np.asarray([[m_matrix @ v for v in row] for row in cand.configurations],
                        dtype=np.float64)
    kept: set[tuple] = set()
    for rot, tran in ops:
        if rot == identity and all(Fraction(v) == 0 for v in tran):
            kept.add((rot, tran))
            continue
        rmat = np.asarray(rot, dtype=np.float64)
        tvec = np.asarray([float(v) for v in tran], dtype=np.float64)
        ok = True
        for m in range(moved.shape[0]):
            image = (rmat @ moved[m] + tvec) % 1.0
            hits = [mm for mm in range(moved.shape[0])
                   if _same_site(moved[mm], image, tol=max(tol, CHILD_SITE_TOL))]
            if not hits:
                ok = False
                break
            target = configs[:, hits[0], :]
            predicted = np.einsum("ij,fj->fi", rmat, configs[:, m, :])
            if not np.allclose(predicted, target, atol=tol):
                ok = False
                break
        if ok:
            kept.add((rot, tran))
    return kept


def _group_from_nuclear_ops(ops) -> MagneticGroup:
    """A colourless :class:`MagneticGroup` from a set of nuclear (rot, tran) pairs.

    The same construction :func:`_intersection_group` uses for the
    positionally-intersected set; factored out so :func:`magnetic_supercell`
    and the multi-component builder share it rather than each writing the
    ``MagneticOperator.build`` loop.
    """
    from .operators import MagneticOperator

    operators = [MagneticOperator.build(
        [[int(v) for v in row] for row in rot], list(tran), 1)
        for rot, tran in ops]
    return MagneticGroup.from_operations(operators)


# ---------------------------------------------------------------------------
# the atoms
# ---------------------------------------------------------------------------
def lattice_cosets(basis) -> tuple[tuple[int, int, int], ...]:
    """The integer lattice modulo the child lattice: |det P| coset representatives.

    **ℤ³/L_child, not L/L_child**, and the distinction is the difference between
    the right atom count and twice it for a centred parent.
    :func:`~rietx.crystallography.symmetry.expand_positions` returns a site's
    orbit in the *conventional* cell — the centring images already listed among
    them, because gemmi's operation list carries the centring — so what is left
    to add is the conventional cell's own translations modulo the child lattice,
    and there are exactly |det P| of those.  Adding L/L_child on top of an orbit
    that already contains the centring image counts every atom of a centred
    parent twice, and the child cell's volume ratio is the arithmetic that says
    so.

    Enumerated by class rather than by a fundamental-domain test, so a transform
    with negative entries — which is what a database setting routinely gives,
    to keep a frame right-handed — is handled without a sign convention.

    **A child basis need not be integral.**  For a centred parent, M-7's
    :func:`child_basis` is written on the conventional axes but spans a
    multiple of the *primitive* cell, so P can carry halves and |det P| can be
    below one — F m -3 m at k = (0, 0, 1) gives det P = ½.  The child lattice
    then contains the centring vectors, ℤ³ is not a sublattice of it, and the
    classes are those of ℤ³ modulo ℤ³ ∩ L_child: their count is the order of
    the group the columns of P⁻¹ generate modulo 1, which is |det P| exactly
    when P is integral and is **never zero**.  ``round(|det P|)`` was that
    count only in the integral case, and at det P = ½ it rounded to no coset
    and no atom at all.  :func:`_child_positions` removes the images such a
    child lattice identifies.
    """
    inverse = _isotropy._fraction_inverse(basis)
    want = _integer_coset_count(basis)
    seen: dict[tuple[int, ...], tuple[int, int, int]] = {}
    span = 1
    while len(seen) < want and span <= 8:
        # shortest first, and (0,0,0) first of all, so the identity coset is
        # always the representative of its own class and the list is the same
        # on two runs of the same stage
        box = [tuple(int(v) - span for v in n)
               for n in np.ndindex(2 * span + 1, 2 * span + 1, 2 * span + 1)]
        for vector in sorted(box, key=lambda v: (sum(c * c for c in v), v)):
            key = tuple(int(round(v * 720)) % 720
                        for v in (inverse @ np.array(vector, dtype=np.float64)) % 1.0)
            seen.setdefault(key, vector)
            if len(seen) == want:
                break
        span += 1
    if len(seen) != want:                    # pragma: no cover - |det P| <= 8^3
        raise ValueError(
            f"lattice_supercell(): found {len(seen)} integer lattice cosets of "
            f"the child lattice where |det P| = {want} demands that many")
    return tuple(seen.values())


def _volume_index(basis) -> int | Fraction:
    """|det P| exactly, as an ``int`` whenever it is one."""
    from .operators import _rational_determinant

    volume = abs(_rational_determinant([[Fraction(v) for v in row]
                                        for row in basis]))
    return int(volume) if volume.denominator == 1 else volume


def _integer_coset_count(basis) -> int:
    """|ℤ³ / (ℤ³ ∩ L_child)|, exactly: the order of ⟨P⁻¹·e₁, P⁻¹·e₂, P⁻¹·e₃⟩ mod 1."""
    inverse = _isotropy._exact_inverse(basis)
    generators = [tuple(inverse[i][j] % 1 for i in range(3)) for j in range(3)]
    zero = (Fraction(0), Fraction(0), Fraction(0))
    seen = {zero}
    frontier = [zero]
    while frontier:
        grown = []
        for element in frontier:
            for g in generators:
                image = tuple((a + b) % 1 for a, b in zip(element, g))
                if image not in seen:
                    seen.add(image)
                    grown.append(image)
        frontier = grown
    return len(seen)


def _child_positions(parent_phase, basis, shift, cosets):
    """Every atom of the child cell: ``(parent index, coset index, position)``.

    ``x_child = P⁻¹·(x_parent + n − p)`` with ``n`` a coset of ℤ³/(ℤ³ ∩ L_child)
    and ``p`` the origin shift of the transform.

    When the child lattice holds a centring vector of the parent (a non-integral
    P, :func:`lattice_cosets`), a site's conventional orbit lists that centring
    image and the child cell calls it the same atom, so an image already placed
    *for the same parent atom* is dropped — and the count that is left is
    checked against |det P| times the conventional orbit, because a site short
    or doubled here is silent in |F_N|².  Two parent atoms sharing one position
    (a mixed-occupancy site) are two atoms and are never merged.  For an
    integral P no image is ever dropped, so the list is what it always was.
    """
    from ..symmetry import resolve_group

    sg = resolve_group(parent_phase.space_group,
                       parent_phase.symmetry_operations)
    inverse = _isotropy._fraction_inverse(basis)
    origin = np.array([float(v) for v in shift], dtype=np.float64)
    volume = _volume_index(basis)
    out = []
    for j, atom in enumerate(parent_phase.atoms):
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value],
                       dtype=np.float64)
        orbit = expand_positions(sg, xyz)
        placed: list[np.ndarray] = []
        for image in orbit:
            for c, coset in enumerate(cosets):
                moved = inverse @ (image + np.array(coset, dtype=np.float64)
                                   - origin) % 1.0
                if any(_same_site(moved, q) for q in placed):
                    continue
                placed.append(moved)
                out.append((j, c, moved))
        want = len(orbit) * volume
        if len(placed) != want:
            raise ValueError(
                f"magnetic_supercell(): parent atom {atom.label!r} has "
                f"{len(orbit)} images in the conventional cell, so a child cell "
                f"of |det P| = {volume} must hold {want} of them, and "
                f"{len(placed)} distinct positions were placed. This is a bug "
                f"in the cell transform, not a tolerance to widen")
    return out


def _same_site(a, b, tol: float = CHILD_SITE_TOL) -> bool:
    d = np.abs(np.asarray(a) - np.asarray(b))
    return bool(np.all(np.minimum(d, 1.0 - d) <= tol))


def _partition_into_child_orbits(symbol, entries):
    """One representative per child orbit, with the entries it covers.

    Every position of the child cell must land in exactly one orbit: a position
    covered twice is a site counted twice in |F_N|², and one covered not at all
    is an atom missing from it.  Both are checked, because both are silent.

    ``symbol`` is a Hermann-Mauguin symbol or a group object — for an unnamed
    child (:class:`ChildGroup`) the partition has to run over the *operation
    list*, since the label generates nothing.  Running it over the symbol
    instead is exactly the error the old refusal existed to prevent: the child
    would get the symbol's orbits, which are a different partition of the same
    positions.
    """
    from ..symmetry import as_group

    sg = as_group(symbol)
    assigned = [False] * len(entries)
    groups: list[tuple[int, list[int]]] = []
    for i, (j, _c, position) in enumerate(entries):
        if assigned[i]:
            continue
        orbit = expand_positions(sg, position)
        # an orbit is taken over *this parent atom's* entries: two parent atoms
        # sharing a position (a mixed-occupancy site, Fe/Cr on one Wyckoff
        # position) are two atoms of the child too, and matching on position
        # alone joined them into one orbit and refused the statement.  A wrong
        # transform is still caught — an orbit reaching a position this atom
        # has no entry at is short, and the whole-orbit check below says so.
        members = [n for n, (pj, _pc, q) in enumerate(entries)
                   if pj == j and any(_same_site(q, p) for p in orbit)]
        for n in members:
            if assigned[n]:
                raise ValueError(
                    f"magnetic_supercell(): the child position "
                    f"{np.array2string(entries[n][2], precision=5)} is in two "
                    f"orbits of {sg.xhm()!r}; the supercell atom list would count "
                    f"that site twice in |F_N|^2. This is a bug in the orbit "
                    f"partition, not a tolerance to widen")
            assigned[n] = True
        if len(members) != len(orbit):
            raise ValueError(
                f"magnetic_supercell(): the orbit of "
                f"{np.array2string(position, precision=5)} under {sg.xhm()!r} has "
                f"{len(orbit)} members but only {len(members)} of them are in "
                f"the child position list; the child cell does not hold a whole "
                f"orbit and |F_N|^2 would be short")
        groups.append((i, members))
    if not all(assigned):
        raise ValueError(
            "magnetic_supercell(): the orbit partition left "
            f"{assigned.count(False)} child positions unassigned")
    return groups


# ---------------------------------------------------------------------------
# the moments
# ---------------------------------------------------------------------------
def _seed_moments(group: MagneticGroup, positions, ions, magnitude: float):
    """A moment on every site the group allows one on, consistent by construction.

    One seed per **magnetic** orbit — the orbit of the group itself, which for
    a type IV group joins a site to its anti-translation image — propagated by
    ``MagneticGroup.site_orbit``.  So the antiparallel pattern the anti-centring
    demands is the *stated* structure rather than something a fit has to find,
    and ``Phase._moments_are_stateable`` accepts it for the same reason.

    The seed itself is :func:`~rietx.crystallography.magnetic.moments.
    tilted_seed` (WP-1418 stage (b)) rather than the whole magnitude on the
    allowed basis's first row alone: a rank ≥ 2 basis (a multi-copy irrep or a
    general/kernel direction) used to leave every other DOF starting at a
    stationary point of χ², the same shape ``Stage.distortion_seed`` exists
    to fix for a whole amplitude vector at A = 0 — see that function's
    docstring.
    """
    seeded: dict[int, np.ndarray] = {}
    for i, position in enumerate(positions):
        if i in seeded or ions[i] is None:
            continue
        basis = group.allowed_moment_basis(position)
        if len(basis) == 0:
            seeded[i] = np.zeros(3)
            continue
        seed = tilted_seed(basis, (1.0, 1.0, 1.0, 90.0, 90.0, 90.0), magnitude)
        images, moments = group.site_orbit(position, seed)
        for image, moment in zip(images, moments):
            for n, q in enumerate(positions):
                if ions[n] is not None and n not in seeded and _same_site(q, image):
                    seeded[n] = np.asarray(moment, dtype=np.float64)
    return seeded


def anti_translation_residual(phase) -> float:
    """max |m(x) − ε·det(R)·R·m(x′)| over every operation of the phase's own group.

    A supercell statement puts the two cosets of a parent site on **independent**
    moment DOFs (module docstring, "What is *not* enforced"), so a refinement
    can leave the magnetic space group it declares.  This is the distance it
    has travelled, in μ_B, and a report that quotes a refined moment from a
    supercell statement should quote this beside it: zero means the refined
    structure still has the symmetry it claims.
    """
    group = phase.magnetic_symmetry.group()
    # keyed by species too: two atoms sharing a position (a mixed-occupancy
    # site) each carry their own moment, and one is never the other's image
    sites = [(np.array([a.x.value, a.y.value, a.z.value], dtype=np.float64),
              np.array(a.moment.values(), dtype=np.float64), a.species)
             for a in phase.atoms if a.moment is not None]
    worst = 0.0
    for position, moment, species in sites:
        for op in group.all_operations():
            image = op.act_on_site(position)
            carried = op.act_on_moment(moment)
            for q, m, other in sites:
                if other == species and _same_site(q, image):
                    worst = max(worst, float(np.max(np.abs(m - carried))))
    return worst


def anti_translation_ties(phase, ip: int = 0):
    """The affine ties that make the anti-centring a *constraint*, not a seed.

    Returns ``[(target_path, source_path, scale, offset)]`` for
    :meth:`rietx.Refinement.tie` (WP-1070).  Applying them removes exactly the
    freedom the magnetic space group already spends: without them a supercell
    statement carries two independent moment columns per parent site, one of
    which is a **ferromagnetic** mode the declared group forbids, and the fit
    will happily spend it.

    The relation is affine in the DOFs, and it is affine because the operation
    is a pure translation.  An (anti)centring is {1 | t, ε}, so its axial action
    is ε·det(I)·I = ±**I** — not a rotation — and ±I is exactly the case the
    modulus-and-angles parameterisation carries linearly:

    ==== ================================================================
    dim  m′ = −m in DOFs
    ==== ================================================================
    1    μ′ = −μ                       (μ is signed for a line)
    2    μ′ = μ, φ′ = φ + π
    3    μ′ = μ, θ′ = π − θ, φ′ = φ + π
    ==== ================================================================

    and ε = +1 gives the identity in every dimension.  A pair related by a
    *rotational* operation is **not** emitted: those atoms are in one nuclear
    orbit already and WP-1327 propagates them through ``mom_mat``, so a tie
    there would be a second, weaker copy of a constraint the forward model
    already applies exactly.

    Ties are chained no deeper than one step — each image follows the first
    atom of its (anti)centring coset — because ``Refinement.tie`` refuses a
    tied source by name, and rightly.
    """
    group = phase.magnetic_symmetry.group()
    magnetic = [(j, a) for j, a in enumerate(phase.atoms) if a.moment is not None]
    positions = {j: np.array([a.x.value, a.y.value, a.z.value], dtype=np.float64)
                 for j, a in magnetic}
    dims = {j: len(group.allowed_moment_basis(positions[j])) for j, _a in magnetic}
    out: list[tuple[str, str, float, float]] = []
    tied: set[int] = set()
    for op in group.centerings:
        if not op.is_translation:                      # pragma: no cover - schema
            continue
        for j, atom in magnetic:
            if j in tied:
                continue
            image = op.act_on_site(positions[j])
            if _same_site(image, positions[j]):
                continue
            # the image of *this* species: a co-sited atom of another one
            # (a mixed-occupancy site) sits at the same position and is not it
            target = next((n for n, a in magnetic
                           if n not in tied and n != j
                           and a.species == atom.species
                           and _same_site(positions[n], image)), None)
            if target is None:
                continue
            n_dof = dims[j]
            if dims[target] != n_dof:                  # pragma: no cover - symmetry
                continue
            base = f"phases.{ip}.atoms.{target}.moment.dof"
            src = f"phases.{ip}.atoms.{j}.moment.dof"
            sign = float(op.time_reversal)
            if n_dof == 1:
                out.append((f"{base}0", f"{src}0", sign, 0.0))
            elif sign > 0:
                out.extend((f"{base}{k}", f"{src}{k}", 1.0, 0.0)
                           for k in range(n_dof))
            elif n_dof == 2:
                out.append((f"{base}0", f"{src}0", 1.0, 0.0))
                out.append((f"{base}1", f"{src}1", 1.0, float(np.pi)))
            else:
                out.append((f"{base}0", f"{src}0", 1.0, 0.0))
                out.append((f"{base}1", f"{src}1", -1.0, float(np.pi)))
                out.append((f"{base}2", f"{src}2", 1.0, float(np.pi)))
            tied.add(target)
    return out


# ---------------------------------------------------------------------------
# the statement
# ---------------------------------------------------------------------------
def magnetic_supercell(parent: Phase, candidate=None, *, group=None,
                       transform: str | None = None, k=None,
                       bns_number: str | None = None,
                       nuclear_group: str = "parent", magnetic_species=None,
                       ion: str | dict[str, str] | None = None,
                       g: float | dict[str, float] | None = None,
                       magnitude: float = 1.0,
                       vary: bool = True, name: str | None = None
                       ) -> SupercellStatement:
    r"""The nuclear phase of ``parent`` restated in the magnetic cell of a k.

    **Two ways in, and only the first goes through M-7.**

    ``candidate`` is one of M-7's :class:`~.isotropy.MagneticCandidate`
    objects — a magnetic space group with its cell and its k.  Only its
    ``group``, ``cell.k`` and ``bns_number`` are read: the moment *family* is
    not, because the family is derived per site from the group itself
    (``allowed_moment_basis``), which is what lets a parent with several
    magnetic sites be stated from one candidate.  The child cell is
    :func:`child_basis`'s, and M-7's scope fence applies — 2k in the reciprocal
    lattice.

    ``group`` + ``transform`` is the other way, and it exists because that
    fence is M-7's and not this module's.  M-7 needs 2k ∈ L\* so that a lattice
    translation enters the order parameter with a phase of ±1 and an isotropy
    subgroup of the grey little group exists; **a supercell statement needs no
    such thing**.  It needs a child lattice, which every commensurate k has, and
    a magnetic space group in that cell, which a database or a k-SUBGROUPSMAG
    table supplies directly.  Mn₃O₄ on POWGEN is the case: parent I4₁/amd with
    k = (0, ½, 0), whose 2k = (0, 1, 0) is *not* a reciprocal-lattice vector of
    a body-centred lattice, so M-7 refuses it by name — and yet the structure is
    stated, and refined, in a, 2b, c with a primitive lattice.  Pass the
    operator list in that cell and its (P, p) transform in
    ``transform_BNS_Pp_abc`` form; ``k`` is then a record for the report and
    nothing derives from it.

    ``nuclear_group`` chooses which group the child phase's ``space_group``
    states, and it is the one knob a caller can get wrong, so both settings and
    the reason for each are here.

    ``"parent"`` (the default) is the parent's own group carried through the
    transform: the right answer whenever the child lattice is invariant under
    the parent's point group, which is the k = (0,0,½)-in-P-lattice family and
    every type IV case.  The nuclear model then keeps every constraint the
    parent's symmetry puts on it.

    ``"magnetic"`` states the child phase under the **magnetic group's own
    nuclear part**, and it is not a convenience: for a k that lowers the crystal
    class there is no alternative.  Mn₃O₄ again: the child cell a, 2b, c breaks
    the tetragonal symmetry, so I4₁/amd's 4₁ screw does not map the child
    lattice onto itself and the parent group **is not a group of this cell at
    all** — ``"parent"`` refuses by name, from ``MagneticGroup.transformed``'s
    own integrality guard.  The largest subgroup of the parent that does
    preserve the child lattice is not describable by a Hermann-Mauguin symbol
    in it either (the body-centring becomes a quarter translation), which is the
    same obstruction the GSAS-II Magnetic-V tutorial states in prose: *"one has
    to describe the chemical structure in the doubled magnetic cell with the
    space group Pbna"*.  ``"magnetic"`` is that description.  What it costs is
    the parent's constraints on the *coordinates* — the child asymmetric unit is
    larger and its sites are independent — which is exactly why the tutorial
    calls the refinement unstable and why a caller should hold those coordinates
    rather than free them.  What it does **not** cost is the nuclear structure
    factor: every atom of the child cell is listed explicitly, so |F_N|² is the
    parent's to the last bit (``tests/test_magnetic_supercell.py``).

    ``magnetic_species`` is the species (or atom labels) that carry a moment;
    ``ion`` the magnetic form-factor key, either one string for all of them or
    a mapping from species to key.  ``g`` is that ion's Landé factor, mirroring
    ``ion``'s shape — one float for every moment, or a mapping keyed by the
    *parent's own atom label* (the same label ``ion``'s mapping form takes) —
    ``None`` (the default) leaves every moment's ``g`` unset, bit-identical to
    every call before this parameter grew a mapping form.  ``magnitude`` is
    the seed modulus in μ_B — a seed, not a claim.

    Every number in the returned phase is derived; nothing is copied from a
    published structure.  The parent's cell, coordinates, occupancies and
    displacement parameters come through unchanged, and the cell parameters are
    the parent's carried through P.
    """
    if (candidate is None) == (group is None):
        raise ValueError(
            "magnetic_supercell(): pass either one of M-7's candidates or an "
            "explicit group with its transform, not both and not neither. The "
            "candidate route derives the child cell from k and is fenced at "
            "2k in the reciprocal lattice (M-7's scope); the explicit route "
            "takes the cell from the transform and has no such fence, because "
            "a child lattice exists for every commensurate k.")
    if nuclear_group not in ("parent", "magnetic"):
        raise ValueError(
            f"magnetic_supercell(): nuclear_group={nuclear_group!r} is not one "
            f"of 'parent' or 'magnetic'.")
    if group is not None and transform is None:
        raise ValueError(
            "magnetic_supercell(): an explicit group needs its transform. The "
            "operator list alone does not say which cell it is written in, and "
            "guessing would put the parent's atoms in the wrong cell with no "
            "sign that anything was wrong.")
    if parent.propagation_vector is not None:
        raise ValueError(
            f"magnetic_supercell(): the parent phase {parent.name!r} already "
            f"declares a propagation vector "
            f"{parent.propagation_vector!r}. A supercell statement *is* the k, "
            f"restated as a cell; declaring both would ask one phase to place "
            f"the same intensity twice. Pass the nuclear parent phase.")
    if any(a.aniso is not None for a in parent.atoms):
        raise ValueError(
            "magnetic_supercell(): an anisotropic displacement block is "
            "declared and this rung does not carry one into the child cell. "
            "U* transforms as R·U*·Rᵀ under the operation that produced an "
            "image, and the child sites are images of the parent's, so the "
            "tensors would have to be rotated rather than copied; copying them "
            "would be wrong in every non-orthogonal setting "
            "(crystallography/adp.py). Convert the sites to biso, or wait for "
            "the rung that carries the tensor.")

    # stage3 D2: an unnamed (bracketed-label) parent used to be refused here
    # by name.  ``child_basis``/``magnetic_cell``/``candidates`` all resolve
    # their group through ``_irreps._resolve``, which already accepts the
    # ``OperatorGroup`` ``resolve_group`` builds from a phase's own operator
    # list — no tabulated space-group number is used anywhere in that chain
    # (D-1, COMMON.md) — so the parent's group is resolved once, from its
    # operators when it has no name, and threaded through instead of refusing
    # before either derivation is tried.
    parent_group = resolve_group(parent.space_group, parent.symmetry_operations)
    if candidate is not None:
        basis = child_basis(parent_group, candidate.cell.k)
        origin = (Fraction(0), Fraction(0), Fraction(0))
        transform = format_transform([list(row) for row in basis], origin)
        k = candidate.cell.k
        bns_number = candidate.bns_number if bns_number is None else bns_number
        # the MSG in *this* cell.  The candidate's group is in M-7's reduced
        # cell, so it is carried across rather than rebuilt:
        # MagneticGroup.transformed takes (P, p) in the BNS sense and applies
        # the inverse map, so reaching a cell whose basis is M relative to the
        # current one means handing it M⁻¹ (isotropy.MagneticCell.
        # inverse_transform records the same direction).
        p_candidate = [[Fraction(v) for v in row] for row in candidate.cell.basis]
        step = _mat_mul(_isotropy._exact_inverse(p_candidate),
                        [[Fraction(v) for v in row] for row in basis])
        group = candidate.group.transformed(
            format_transform(_isotropy._exact_inverse(step),
                             (Fraction(0), Fraction(0), Fraction(0))))
    else:
        from .operators import parse_transform

        basis, origin = parse_transform(transform)
        transform = format_transform([list(row) for row in basis], origin)
    p_child = [[Fraction(v) for v in row] for row in basis]
    cosets = lattice_cosets(basis)
    parent_cell = parent.cell.lengths_angles()
    child_cell = _child_cell_parameters(parent_cell, basis)

    # The child's **nuclear** space group is the *parent's*, carried through the
    # same transform — not the magnetic candidate's, whose nuclear part is
    # generally smaller.  Ordering a moment lowers the magnetic symmetry and
    # leaves the nuclei exactly where they were, so the reflection list, the
    # site orbits and the systematic absences are all still the parent's.
    # Taking them from the candidate would give a different atom list for every
    # candidate of the same structure, which is the ranking measuring the wrong
    # thing.
    if nuclear_group == "parent":
        nuclear = _nuclear_group_of(
            parent.space_group, parent.symmetry_operations).transformed(
            format_transform(_isotropy._exact_inverse(p_child), origin))
    else:
        nuclear = _colourless(group)
        # **The little-group sign (M2d).**  A commensurate k != 0 little group
        # is generally grey: the same spatial operation {R | t} can carry
        # little-group character +1 on one component of a multi-dimensional
        # order-parameter direction and -1 on another
        # (checks/M2B_SINGLE_COMPONENT_SIGN_CHECK.md, confirmed). _colourless
        # already discarded that character above; here, for a candidate whose
        # own (positions, configurations) this rung can check against, the
        # declared group is reduced to the subgroup that is a symmetry of the
        # candidate's **signed** field, not only of its positions — so an
        # operation whose sign this rung cannot state correctly is excluded
        # rather than trusted with an implicit +1, and the sibling it used to
        # reach becomes its own explicit representative instead
        # (:func:`_mode_vectors` already fills every representative by direct
        # position-match against the candidate, never by rotating a
        # sibling's).  Gated on ``kind == "displacive"``: the moment path's
        # own consumer (``magnetic.scattering.compile_magnetic_sites``)
        # re-derives each image's axial matrix from the *full*, non-colourless
        # magnetic group at compile time, one operation at a time, so it never
        # trusts the *declared* nuclear group's sign in the first place —
        # reducing it too would only add atoms no consumer needs (measured;
        # see the M2d report's moment-path table).
        if candidate is not None and candidate.kind == "displacive":
            m_matrix = (_isotropy._fraction_inverse(basis)
                       @ _matrix_of(candidate.cell.basis))
            reduced_ops = _sign_consistent_operations(
                candidate, m_matrix, _nuclear_operations(nuclear))
            nuclear = _group_from_nuclear_ops(reduced_ops)
    lattice = _child_lattice(parent_cell, basis)
    # ``None`` when spglib will not even name the *type* — no longer a refusal:
    # the type is the leading half of a label and the operation list is the
    # group either way, so what used to stop the statement now only shortens
    # its label (Q-17).
    symbol = _identify_child_space_group(nuclear, lattice)
    child_group = resolve_child_group(nuclear, symbol, transform)
    symbol = child_group.label
    diagnostics: tuple[Diagnostic, ...] = ()
    if not child_group.named:
        diagnostics = (Diagnostic(
            level="info", code="CHILD_GROUP_UNNAMED",
            where=["phases.0.space_group"],
            message=f"magnetic_supercell(): {child_group.reason}",
            suggestion=(
                "nothing to fix — the statement is complete. Quote the child "
                "group as its operation list (or as the closest type with the "
                "cell beside it), not as the bracketed label's leading symbol, "
                "which names a different group. If a published assignment for "
                "this superstructure names a symbol, it is naming the type in "
                "another cell: check the transform before comparing"),
        ),)

    entries = _child_positions(parent, basis, origin, cosets)
    partition = _partition_into_child_orbits(child_group.group, entries)

    wanted = _species_map(parent, magnetic_species, ion)
    g_lookup = g if isinstance(g, dict) else None
    positions = [entries[rep][2] for rep, _members in partition]
    ions = [wanted.get(parent.atoms[entries[rep][0]].label) for rep, _ in partition]
    seeds = _seed_moments(group, positions, ions, magnitude)
    _refuse_a_nuclear_orbit_the_magnetic_group_cannot_cover(
        child_group.group, group, positions, ions, nuclear_group)

    atoms: list[Atom] = []
    site_map: list[tuple[int, int]] = []
    counts: dict[str, int] = {}
    for n, (rep, _members) in enumerate(partition):
        j, coset, position = entries[rep]
        source = parent.atoms[j]
        counts[source.label] = counts.get(source.label, 0) + 1
        suffix = "" if len(
            [1 for r, _ in partition if entries[r][0] == j]) == 1 else \
            f"_{counts[source.label]}"
        moment = None
        seed = seeds.get(n)
        if ions[n] is not None and seed is not None and float(np.abs(seed).max()) > 0:
            g_n = g_lookup.get(source.label) if g_lookup is not None else g
            moment = Moment.from_values(tuple(float(v) for v in seed), ions[n],
                                        g=g_n, vary=vary)
        atoms.append(Atom(
            label=f"{source.label}{suffix}", species=source.species,
            x=Parameter(value=float(position[0])),
            y=Parameter(value=float(position[1])),
            z=Parameter(value=float(position[2])),
            occ=Parameter(value=source.occ.value),
            biso=Parameter(value=source.biso.value), moment=moment))
        site_map.append((j, coset))

    ops, cent = group.xyz_strings()
    phase = Phase(
        name=name or f"{parent.name} ({transform})",
        space_group=symbol,
        symmetry_operations=(None if child_group.operations is None
                             else list(child_group.operations)),
        cell=Cell(a=Parameter(value=child_cell[0]), b=Parameter(value=child_cell[1]),
                  c=Parameter(value=child_cell[2]),
                  alpha=Parameter(value=child_cell[3]),
                  beta=Parameter(value=child_cell[4]),
                  gamma=Parameter(value=child_cell[5])),
        atoms=atoms,
        magnetic_symmetry=MagneticSymmetry(
            operations=list(ops), centerings=list(cent),
            bns_number=bns_number,
            setting=f"child cell {transform} of {parent.space_group}",
            propagation_vector_parent=(None if k is None
                                       else tuple(str(c) for c in k))),
        scale=Parameter(value=parent.scale.value),
    )
    return SupercellStatement(
        phase=phase, transform=transform, index=_volume_index(basis),
        parent_space_group=parent.space_group, child_space_group=symbol,
        group=group, site_map=tuple(site_map),
        k=None if k is None else tuple(str(c) for c in k),
        child_group_named=child_group.named, diagnostics=diagnostics)


def _mat_mul(a, b):
    return [[sum(Fraction(a[i][t]) * Fraction(b[t][j]) for t in range(3))
             for j in range(3)] for i in range(3)]


def _refuse_a_nuclear_orbit_the_magnetic_group_cannot_cover(
        nuclear_group_object, group: MagneticGroup, positions, ions,
        nuclear_group: str) -> None:
    """Refuse, at build, a statement whose moments the compile would refuse.

    ``compile_magnetic_sites`` already refuses a child whose **nuclear** orbit
    of a magnetic site is larger than the group's magnetic orbit of it: some
    nuclear image then has no moment the stated group determines, and no
    tolerance makes one.  It refuses at *compile*, which was invisible while
    ``resolve_child_group`` refused every such child one step earlier for the
    unrelated reason that no symbol named it — and that earlier refusal is what
    ``strategy.magnetic._supercell`` reads to take the documented remedy
    (``nuclear_group="magnetic"``) by itself.  Measured on P2₁2₁2₁ at
    k = (½,0,0): with the child now stated as an operation list, the build
    succeeds and the compile refuses, so a workflow that used to fall back
    would abstain instead.

    So the check moves here, where the remedy is still reachable.  It is the
    same arithmetic and the same verdict — nothing is loosened, and a statement
    that passes it compiles exactly as it did.
    """
    if nuclear_group != "parent":
        return
    for position, ion in zip(positions, ions):
        if ion is None:
            continue
        nuclear_images = expand_positions(nuclear_group_object, position)
        magnetic_images, _moments = group.site_orbit(position)
        for image in nuclear_images:
            if not any(_same_site(image, q) for q in magnetic_images):
                raise ValueError(
                    f"magnetic_supercell(): the child's nuclear space group "
                    f"puts an image of the site "
                    f"{np.array2string(np.asarray(position), precision=5)} at "
                    f"{np.array2string(np.asarray(image), precision=5)}, and "
                    f"no operation of the magnetic group sends the site there "
                    f"— so the stated group determines no moment for that "
                    f"atom and the child cannot carry one. The magnetic orbit "
                    f"({len(magnetic_images)} images) is smaller than the "
                    f"nuclear one ({len(nuclear_images)}), which is what "
                    f"nuclear_group='parent' means for a k that lowers the "
                    f"crystal class. State the child under the magnetic "
                    f"group's own nuclear part instead "
                    f"(nuclear_group='magnetic'), which is that group's own "
                    f"asymmetric unit and is what a magCIF from MAGNDATA, "
                    f"ISODISTORT or k-SUBGROUPSMAG gives you.")


def _species_map(parent: Phase, magnetic_species, ion) -> dict[str, str]:
    """``{atom label: form-factor ion}`` for the sites that carry a moment."""
    if magnetic_species is None:
        return {}
    wanted = {magnetic_species} if isinstance(magnetic_species, str) \
        else set(magnetic_species)
    out: dict[str, str] = {}
    for atom in parent.atoms:
        key = None
        if atom.species in wanted:
            key = atom.species
        elif atom.label in wanted:
            key = atom.species
        if key is None:
            continue
        if isinstance(ion, dict):
            resolved = ion.get(atom.species) or ion.get(atom.label)
        else:
            resolved = ion
        if resolved is None:
            raise ValueError(
                f"magnetic_supercell(): {atom.label!r} is asked to carry a "
                f"moment but no form-factor ion was given for it. The magnetic "
                f"form factor is keyed by oxidation state and the nuclear "
                f"scattering length by nuclide, so 'Mn' is not an answer: pass "
                f"ion='Mn2+' or a mapping.")
        out[atom.label] = resolved
    if not out:
        raise ValueError(
            f"magnetic_supercell(): none of {sorted(wanted)} is a species or a "
            f"label of {parent.name!r} (it has "
            f"{sorted({a.species for a in parent.atoms})}).")
    return out


# ---------------------------------------------------------------------------
# the displacive statement (M-1)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DisplaciveStatement:
    """A superstructure stated as amplitudes rather than as free coordinates.

    ``phase`` is a complete :class:`~rietx.schemas.structure.Phase`: the child
    cell of the parent + k transform with **every cell parameter held**, the
    isotropy subgroup's own Hermann-Mauguin symbol, one atom per child orbit at
    the parent-derived position, and one
    :class:`~rietx.schemas.structure.DistortionMode` per free amplitude of the
    chosen irrep direction.  It compiles and refines like any other phase; the
    amplitudes are the columns ``phases.i.distortion_modes.n.amplitude``.

    ``biso_ties`` is the tie list that makes the child's displacement
    parameters the parent's again — ``(target, source, scale, offset)`` in the
    shape :func:`anti_translation_ties` uses and ``Refinement.tie`` takes.  It
    is **returned rather than applied**, because a tie is refinement state and
    this function builds a model; the reason it exists is measured: 28 free
    child Biso alone took Ba₂FeSbSe₅ from Rwp 0.118 to 0.076 with no
    superstructure and no moment in the model, i.e. they manufacture exactly
    the intensity the mode is being tested for.

    ``modes_by_site`` maps a parent atom label to the names of the modes that
    move its orbit, and ``directions_by_site`` records every order-parameter
    direction each orbit carries — the second one is what a refusal quotes.
    """

    phase: Phase
    transform: str
    index: int | Fraction
    parent_space_group: str
    child_space_group: str
    irrep_label: str
    direction: str
    k: tuple[str, str, str]
    site_map: tuple[tuple[int, int], ...]
    biso_ties: tuple[tuple[str, str, float, float], ...]
    modes_by_site: dict[str, tuple[str, ...]]
    directions_by_site: dict[str, tuple[str, ...]]
    #: The same two fields :class:`SupercellStatement` carries, and for the
    #: same reason: a displacive child cell turns a glide's half into a quarter
    #: exactly as a magnetic one does, and this used to be where the S3(a,b)
    #: direction of Ba₂FeSbSe₅ was lost.
    child_group_named: bool = True
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def amplitude_paths(self) -> tuple[str, ...]:
        """``phases.0.distortion_modes.n.amplitude`` for every mode, in order.

        Phase 0, because that is the index the phase has in a single-phase
        structure; a caller putting it second renumbers the prefix.
        """
        return tuple(f"phases.0.distortion_modes.{n}.amplitude"
                     for n in range(len(self.phase.distortion_modes)))


@dataclass(frozen=True)
class MultiComponentStatement:
    """A phase carrying several (irrep, direction) components at one k (M2 form (a)).

    S2 ⊕ S3 at k = (½,0,½): each of the two order parameters has its own
    isotropy subgroup, and neither is a subgroup of the other in general, so
    the only group *both* components' modes actually respect is their
    **intersection** — built with :meth:`~.operators.MagneticGroup.
    from_operations` from the two (transformed to the same child basis)
    nuclear operation sets, then named the way a single-component child is
    (:func:`resolve_child_group`): a Hermann-Mauguin symbol when one
    reproduces the intersection group in this cell, else the bracketed
    ``Phase.symmetry_operations`` label Q-17 added, with the same
    ``CHILD_GROUP_UNNAMED`` diagnostic.

    ``phase.distortion_modes`` carries every component's modes on the one
    child atom list, and ``phase.distortion_components`` (M2's schema
    addition) groups them back apart — one entry per (k, irrep_label,
    direction), in the order ``labels`` gives.  Setting every component's
    amplitudes to zero reproduces the parent's pattern exactly, the same
    ``A = 0`` control :class:`DisplaciveStatement` gives, scaled by
    ``|det P|²`` — the intersection group's partition only ever *merges or
    splits* the same child positions :func:`magnetic_supercell` would build
    for a single component at this k, it does not move any of them.

    ``labels`` is ``"{irrep}{direction}"`` for each component, in the order
    passed to :func:`displacive_statement`'s ``components=``.  The rest of the
    fields mean what they mean on :class:`DisplaciveStatement`.
    """

    phase: Phase
    transform: str
    index: int | Fraction
    parent_space_group: str
    child_space_group: str
    k: tuple[str, str, str]
    labels: tuple[str, ...]
    site_map: tuple[tuple[int, int], ...]
    biso_ties: tuple[tuple[str, str, float, float], ...]
    modes_by_site: dict[str, tuple[str, ...]]
    directions_by_site: dict[str, tuple[str, ...]]
    child_group_named: bool = True
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def amplitude_paths(self) -> tuple[str, ...]:
        """``phases.0.distortion_modes.n.amplitude`` for every mode, in order."""
        return tuple(f"phases.0.distortion_modes.{n}.amplitude"
                     for n in range(len(self.phase.distortion_modes)))


def _displacive_candidates(parent: Phase, k, lattice):
    """``{atom index: {direction label: candidate}}`` for every parent orbit.

    One :func:`~.isotropy.candidates` call per listed atom, with
    ``kind="displacive"`` and ``verify=True`` — the polar action of the
    operations and the span check that pins it (M-7's ``in_allowed_span``).

    Since Q-21, ``candidates()`` no longer raises on one bad candidate of a
    site — it flags it and keeps the rest.  This function is the caller that
    "wants only verified ones" (the module docstring's own phrase): a
    direction whose family failed its own span check is dropped here, before
    ``displacive_statement`` ever sees its label, so a caller asking for a
    failing direction by name gets the same "not carried by this orbit"
    refusal it would have gotten from a raise — and every direction that
    *did* verify is unaffected, so a normal call is bit-identical to before.
    """
    from .isotropy import candidates as _candidates

    out: list[dict[str, object]] = []
    for atom in parent.atoms:
        cs = _candidates(parent.space_group,
                         (atom.x.value, atom.y.value, atom.z.value), k,
                         kind="displacive", cell=lattice, verify=True)
        out.append({c.label: c for c in cs if c.verified is not False})
    return out


def _mode_vectors(child_atoms, site_map, candidate, parent_index,
                  m_matrix) -> list[np.ndarray]:
    """One (n_child, 3) field per free amplitude of ``candidate``.

    The candidate states its orbit in M-7's reduced cell and the child phase
    states it in :func:`child_basis`' cell, so both the positions and the
    displacement components are carried across by
    ``M = B_child⁻¹·B_candidate`` — the one matrix, applied to both, because a
    displacement is contravariant and transforms exactly as a position does
    (``isotropy._expand_configurations`` makes the same choice one rung down).
    Each child orbit representative is then matched to the orbit member that
    sits at its position, and the representative's displacement is the whole
    of the mode: the isotropy subgroup leaves the pattern invariant, so the
    child group generates the rest of the orbit from it.
    """
    moved = np.array([m_matrix @ q for q in candidate.positions]) % 1.0
    fields = [np.zeros((len(child_atoms), 3), dtype=np.float64)
              for _ in range(candidate.free_amplitudes)]
    matched = 0
    for i, atom in enumerate(child_atoms):
        if site_map[i][0] != parent_index:
            continue
        position = np.array([atom.x.value, atom.y.value, atom.z.value])
        hits = [m for m in range(moved.shape[0])
                if _same_site(moved[m], position)]
        if not hits:
            raise ValueError(
                f"displacive_statement(): the child atom {atom.label!r} at "
                f"{np.array2string(position, precision=5)} matches no member "
                f"of the {candidate.label} orbit carried into the child cell. "
                f"The two cells disagree about where this parent site went, "
                f"which is a bug in the transform and not a tolerance to widen")
        matched += 1
        for f in range(candidate.free_amplitudes):
            fields[f][i] = m_matrix @ candidate.configurations[f][hits[0]]
    if matched == 0:                     # pragma: no cover - partition covers all
        raise ValueError(
            f"displacive_statement(): no child atom came from parent site "
            f"{parent_index}")
    return fields


def displacive_statement(parent_phase: Phase, k=None, *, irrep: str | None = None,
                         direction: str | None = None,
                         components=None,
                         child_group: str | None = None,
                         magnitude: float = 0.0,
                         vary: bool = False,
                         name: str | None = None) -> "DisplaciveStatement | MultiComponentStatement":
    r"""The parent restated as a child cell plus refinable mode amplitudes.

    **Two ways in (M2).**  ``k=`` (with optional ``irrep=``/``direction=``) is
    the original, single-component call and its body below is untouched by
    M2 — bit-identical to what it built before (``tests/
    test_multi_component_statements.py::test_single_component_call_is_bit_identical_with_m1``).
    ``components=[(k, irrep, direction), …]`` is the multi-component call: one
    element behaves exactly like the single-component call (it is delegated
    to, not reimplemented), and more than one at **the same k** builds the
    common-subgroup child of form (a) — see :class:`MultiComponentStatement`.
    Components spanning more than one k is form (b), the Fourier branch, which
    this function refuses by name: build its schema and reflection list with
    :func:`fourier_statement` instead, and see that function's docstring for
    exactly what is and is not built.

    The displacive twin of :func:`magnetic_supercell`, and the answer to the
    question that function cannot be asked: a superstructure at a
    zone-boundary k whose order parameter is a **displacement** rather than a
    moment.  The child coordinates are

    .. math:: x_j = x_j^{0} + \sum_\nu A_\nu\,e_{\nu j},

    with the base x⁰ the parent's positions carried through the transform and
    e_ν the irrep mode vectors of
    :func:`~.isotropy.candidates` (``kind="displacive"``) — the parent + irrep
    + direction → structure workflow of Campbell et al. (2006),
    *J. Appl. Cryst.* **39**, 607.

    ``irrep`` and ``direction`` name the order parameter (``"S2"``,
    ``"(a,b)"``).  Both ``None`` is accepted only when the parent's orbits
    carry exactly one direction in common; otherwise the choice is physics and
    the refusal lists what there is to choose from.  **A direction one orbit
    does not carry is refused by name**, with the directions that orbit does
    carry quoted beside it: the modes of an irrep the site's representation
    does not contain do not exist, and silently giving that orbit a zero field
    would state a distortion in which one sublattice is rigid for no reason.

    ``child_group`` is a Hermann-Mauguin symbol the caller expects the isotropy
    subgroup to be (``"P 1 21/m 1"``); it is *checked*, not used, so a
    published subgroup assignment can be asserted against what this derives
    rather than trusted.

    ``magnitude`` seeds every amplitude, in the same Å units the vectors are
    normalised to (below), and ``vary`` frees them.  **The default is 0.0 and
    held**, and both halves matter: at A = 0 the child's pattern is the
    parent's to the last bit (the modes contribute an exactly zero affine
    term), which is the negative control a mode test needs; and a free
    amplitude at exactly zero is refused by
    ``Phase._distortion_modes_are_refinable``, because |F|² is even in A and
    the Jacobian column vanishes there.  So free them with a seed.

    **The sign of a reported amplitude is a domain convention.**  Negating a
    component's whole amplitude vector maps the child onto its other antiphase
    domain, which is the same structure and predicts the identical pattern
    (Perez-Mato, Orobengoa & Aroyo 2010, *Acta Cryst.* A**66**, 558, § 7), so
    the overall sign is a label.  The *relative* signs inside a component are
    measured, and are kept: the report states the component's primary mode
    positive and reads the rest relative to it
    (``report.schemas.DISTORTION_SIGN_CONVENTION``).  ``magnitude`` may
    therefore be negative, and means "start in the other domain".

    **The amplitude is in Å**, defined by normalising each mode so the largest
    Cartesian displacement it produces at unit amplitude is exactly 1 Å in the
    child cell.  The irrep basis fixes the mode only up to a scale, so *some*
    convention is needed and this is the one a reader can check without it:
    A = 0.05 means the furthest-moved atom of that mode moves 0.05 Å.  The
    child cell is held, so the normalisation is a constant of the refinement
    rather than something that drifts with it
    (:meth:`~rietx.schemas.structure.DistortionMode.unit_displacement_a`
    measures it back).

    Every number in the returned phase is derived from ``parent_phase``;
    nothing is copied from a published structure.
    """
    if components is not None:
        if k is not None or irrep is not None or direction is not None:
            raise ValueError(
                "displacive_statement(): pass either k= (with optional irrep= "
                "and direction=, the single-component call) or components= "
                "(a list of (k, irrep, direction) tuples), not both")
        return _multi_component_displacive_statement(
            parent_phase, components, child_group=child_group,
            magnitude=magnitude, vary=vary, name=name)
    if k is None:
        raise ValueError(
            "displacive_statement(): pass k (a single component, with "
            "optional irrep=/direction=) or components=[(k, irrep, "
            "direction), …] (one or more)")

    from ..adp import cartesian_basis
    from .isotropy import magnetic_cell

    if parent_phase.distortion_modes:
        raise ValueError(
            f"displacive_statement(): the parent phase "
            f"{parent_phase.name!r} already carries "
            f"{len(parent_phase.distortion_modes)} distortion mode(s). The "
            f"parent of a mode statement is the *undistorted* structure; pass "
            f"the parent phase, not a child one")
    refuse_an_unnamed_parent(parent_phase, "displacive_statement()")
    parent_cell = parent_phase.cell.lengths_angles()
    lattice = np.asarray(cartesian_basis(*parent_cell), dtype=np.float64).T
    mcell = magnetic_cell(parent_phase.space_group, k)
    per_site = _displacive_candidates(parent_phase, mcell.k, lattice)
    directions_by_site = {atom.label: tuple(sorted(per_site[j]))
                          for j, atom in enumerate(parent_phase.atoms)}

    common = set(per_site[0])
    for table in per_site[1:]:
        common &= set(table)
    if irrep is None and direction is None:
        if len(common) != 1:
            raise ValueError(
                f"displacive_statement(): the orbits of "
                f"{parent_phase.name!r} carry {len(common)} order-parameter "
                f"direction(s) in common at k = "
                f"{tuple(str(c) for c in mcell.k)} "
                f"({', '.join(sorted(common)) or 'none'}); which one the "
                f"superstructure is, is physics. Name it with irrep= and "
                f"direction=")
        label = next(iter(common))
    else:
        if irrep is None or direction is None:
            raise ValueError(
                "displacive_statement(): name both irrep= and direction= or "
                "neither; an irrep without a direction is a family of "
                "candidates with different isotropy subgroups, and a "
                "direction label without its irrep does not identify one")
        label = f"{irrep}{direction}"
    missing = [atom.label for j, atom in enumerate(parent_phase.atoms)
               if label not in per_site[j]]
    if missing:
        detail = "; ".join(
            f"{lab} carries {', '.join(directions_by_site[lab])}"
            for lab in missing)
        raise ValueError(
            f"displacive_statement(): the direction {label!r} is not carried "
            f"by every orbit of {parent_phase.name!r} — "
            f"{', '.join(missing)} ha{'s' if len(missing) == 1 else 've'} no "
            f"configuration in it, so the mode does not exist on "
            f"{'that orbit' if len(missing) == 1 else 'those orbits'} and a "
            f"zero field there would state a rigid sublattice nobody claimed. "
            f"What {'it does' if len(missing) == 1 else 'they do'} carry: "
            f"{detail}")

    reference = per_site[0][label]
    statement = magnetic_supercell(parent_phase, candidate=reference,
                                   nuclear_group="magnetic",
                                   name=name or f"{parent_phase.name} "
                                                f"{label} superstructure")
    # **A bracketed label is not a symbol**, so an asserted ``child_group``
    # against an unnamed child compares a symbol with a label and always
    # differs — which is the right answer, but the message has to say why
    # rather than leaving a caller to think the two symbols disagree.
    if child_group is not None and not statement.child_group_named:
        raise ValueError(
            f"displacive_statement(): the isotropy subgroup of {label!r} in "
            f"the child cell {statement.transform!r} is not named by any "
            f"Hermann-Mauguin symbol, so the {child_group!r} the call asserted "
            f"cannot be checked against it. The child is stated as its own "
            f"operation list under the label "
            f"{statement.child_space_group!r}; drop child_group= and read "
            f"``phase.symmetry_operations``, or compare against "
            f"{statement.phase.symmetry_operations}")
    if child_group is not None and _settings_of(child_group) != _settings_of(
            statement.child_space_group):
        raise ValueError(
            f"displacive_statement(): the isotropy subgroup of {label!r} in "
            f"the child cell {statement.transform!r} is "
            f"{statement.child_space_group!r}, not the {child_group!r} the "
            f"call asserted. One of the two is wrong and this refuses rather "
            f"than choosing")

    basis = child_basis(parent_phase.space_group, mcell.k)
    m_matrix = (_isotropy._fraction_inverse(basis)
                @ _matrix_of(reference.cell.basis))
    child_lattice = _child_lattice(parent_cell, basis)

    modes = []
    modes_by_site: dict[str, tuple[str, ...]] = {}
    for j, atom in enumerate(parent_phase.atoms):
        candidate = per_site[j][label]
        names: list[str] = []
        for f, pattern in enumerate(_mode_vectors(
                statement.phase.atoms, statement.site_map, candidate, j,
                m_matrix)):
            # normalise to 1 Å of largest Cartesian displacement per unit
            # amplitude — the convention the docstring states
            worst = float(np.max(np.linalg.norm(pattern @ child_lattice, axis=1)))
            if worst <= 0.0:             # pragma: no cover - a zero basis row
                raise ValueError(
                    f"displacive_statement(): free amplitude {f} of "
                    f"{candidate.label} on {atom.label!r} moves no atom of "
                    f"the child cell")
            # **Float zeros are made exact.**  The irrep arithmetic is
            # floating point, so a component the symmetry forces to zero
            # arrives as 1e-50 rather than 0.0 — measured on every mode of
            # Ba₂FeSbSe₅'s S2(a,b), whose smallest genuine component is 0.36 of
            # its largest.  Left alone those specks put a term in the
            # constraint block for an atom the mode does not move, which makes
            # ``_check_distortion_degeneracy`` count atoms that are not there
            # and a printed mode vector unreadable.  The threshold is 1e-12 of
            # the mode's own largest component: twelve orders below anything
            # real here and thirty-eight above the specks, so it separates the
            # two rather than trimming either.
            scale = float(np.abs(pattern).max())
            pattern = np.where(np.abs(pattern) < 1e-12 * scale, 0.0, pattern)
            mode_name = f"{label}-{atom.label}-{f}"
            names.append(mode_name)
            modes.append(DistortionMode(
                name=mode_name, irrep_label=candidate.irrep_label,
                direction=candidate.direction.label,
                k=tuple(str(c) for c in mcell.k), parent_site=atom.label,
                amplitude=Parameter(
                    value=float(magnitude), vary=bool(vary),
                    min=-DISTORTION_AMPLITUDE_MAX_A,
                    max=DISTORTION_AMPLITUDE_MAX_A, unit="A"),
                vectors=[tuple(float(c) for c in row)
                         for row in pattern / worst]))
        modes_by_site[atom.label] = tuple(names)

    ties: list[tuple[str, str, float, float]] = []
    first: dict[int, int] = {}
    for i, (parent_index, _coset) in enumerate(statement.site_map):
        head = first.setdefault(parent_index, i)
        if head != i:
            ties.append((f"phases.0.atoms.{i}.biso",
                         f"phases.0.atoms.{head}.biso", 1.0, 0.0))

    phase = statement.phase.model_copy(update={
        # the child is a *nuclear* superstructure: the isotropy subgroup of a
        # displacive order parameter is grey (time reversal is a symmetry of a
        # displacement pattern), so it allows no moment on any site and
        # declaring it would put a magnetic block on the phase that forbids
        # every moment it could carry.  The symbol the block was derived for
        # is already in ``space_group``.
        "magnetic_symmetry": None,
        "distortion_modes": modes,
    })
    if magnitude:
        phase = seed_distortion_amplitudes(
            phase, {m.name: float(magnitude) for m in modes}, vary=bool(vary))
    return DisplaciveStatement(
        phase=phase, transform=statement.transform, index=statement.index,
        parent_space_group=parent_phase.space_group,
        child_space_group=statement.child_space_group,
        irrep_label=reference.irrep_label,
        direction=reference.direction.label,
        k=tuple(str(c) for c in mcell.k), site_map=statement.site_map,
        biso_ties=tuple(ties), modes_by_site=modes_by_site,
        directions_by_site=directions_by_site,
        child_group_named=statement.child_group_named,
        diagnostics=statement.diagnostics)


# ---------------------------------------------------------------------------
# multi-component statements (M2)
# ---------------------------------------------------------------------------
def _intersection_group(nuclear_op_sets) -> MagneticGroup:
    """A colourless :class:`MagneticGroup` from the intersection of nuclear ops.

    Each set in ``nuclear_op_sets`` is what :func:`_nuclear_operations` returns
    for one component's isotropy subgroup, already carried to the **same**
    child basis (same k ⇒ the same :func:`child_basis`, so the transform each
    component's operations went through is the caller's business, not this
    one's).  The intersection of a family of groups is always a group — a
    product of two operations each set contains is in each set, hence in the
    intersection — so :meth:`~.operators.MagneticGroup.from_operations` never
    refuses this input for not being closed; it can still refuse a genuinely
    malformed input (no identity), which would mean a caller's op sets were
    never each a group to start with.
    """
    from .operators import MagneticOperator

    common = set.intersection(*nuclear_op_sets)
    if not common:
        raise ValueError(  # pragma: no cover - defensive; every input set has E
            "displacive_statement(): the components share no operation at "
            "all, not even the identity — this indicates the per-component "
            "nuclear operation sets were not each transformed to the same "
            "child basis")
    operators = [MagneticOperator.build(
        [[int(v) for v in row] for row in rot], list(tran), 1)
        for rot, tran in common]
    return MagneticGroup.from_operations(operators)


def _component_respects_declared_symmetry(cand, m_matrix, declared_ops,
                                          *, tol: float = 1e-6) -> bool:
    r"""Whether ``declared_ops`` (a *nuclear*, sign-blind operation set) is
    actually a symmetry of ``cand``'s own signed mode field.

    **Why this check exists, measured while building M2.** A zone-boundary
    little group is generally *grey*: for k ≠ 0 the same spatial operation
    {R | t} appears **twice** in :attr:`~.isotropy.MagneticCandidate.group`,
    once with the little-group character ε = +1 (a true symmetry of this
    one candidate's mode field) and once with ε = −1 (a symmetry only when
    *combined* with flipping the amplitude's sign — the A ↔ −A ambiguity
    :class:`~rietx.schemas.structure.DistortionMode` already documents).
    :func:`_nuclear_operations`/:func:`_colourless` — reused unchanged from
    :func:`magnetic_supercell`, where dropping ε is correct because that
    function never lets the declared group *auto-generate* a second
    component's siblings — collapse the two into one nuclear (R, t) pair,
    discarding which copy was ε = +1. For **one** component that loss is
    harmless (:func:`_mode_vectors` matches every child atom's vector
    directly against ``cand.positions``, never by rotating a sibling's), but
    the multi-component intersection can end up **smaller** than a
    component's own group, and then this component's few independent
    representatives are far fewer than its own orbit — so the compiled
    ``Phase``'s ordinary orbit expansion (``expand_positions``, called by
    every structure-factor consumer) *does* propagate a representative's
    vector to its siblings by rotation, and if the declared operation used to
    reach a given sibling was really the ε = −1 (not +1) copy, the result
    carries the wrong sign there.

    Measured on Ba₂FeSbSe₅'s own S2(a,b) ⊕ S3(a,b) at k = (½,0,½): S2's group
    is grey (order 16, 8 spatial cosets × {+1, −1}); intersected with S3's
    (order 4, already colourless because S3's isotropy subgroup happens to be
    the intersection itself) gives back exactly S3's group — a **strict**
    subgroup of S2's own — and propagating S2's mode through it flips the
    sign on half of S2's own atoms relative to what
    :func:`~.isotropy.candidates`' own (``in_allowed_span``-verified)
    configuration says. This function is the check that catches that before
    a caller ever refines on it: it verifies self-consistency directly
    against ``cand.positions``/``cand.configurations`` (M-7's own verified
    field), not against a second build, so it costs one small loop rather
    than a second full statement per component.

    Returns ``True`` only if propagating every mode of ``cand`` through every
    non-identity operation of ``declared_ops`` (as an ordinary contravariant
    vector — the polar action a displacement takes, matching
    ``allowed_displacement_basis``) reproduces exactly what ``cand`` itself
    says at the image position, for every one of its own listed positions.

    **M2d: now a thin wrapper.** :func:`_sign_consistent_operations` answers
    the identical per-operation question and is what :func:`magnetic_supercell`
    and the multi-component builder call directly (to *reduce* rather than
    refuse); this function is ``declared_ops <= sign-consistent(declared_ops)``
    in those terms, kept for the boolean, all-or-nothing question and for
    whatever still names it in prose. One behaviour tightens in the process:
    the old loop skipped every pure-translation operation (``if rot ==
    identity: continue``) without checking it, which happened never to matter
    on any operation set this rung measured (the child lattice's own coset
    translations were always either the trivial identity or already excluded
    by the reduction for an unrelated reason) but was not, on inspection, a
    deliberate exemption — :func:`_sign_consistent_operations` checks a
    non-identity pure translation exactly like a rotation.
    """
    kept = _sign_consistent_operations(cand, m_matrix, set(declared_ops), tol=tol)
    return kept == set(declared_ops)


def _multi_component_displacive_statement(
        parent_phase: Phase, components, *, child_group: str | None = None,
        magnitude: float = 0.0, vary: bool = False,
        name: str | None = None) -> "DisplaciveStatement | MultiComponentStatement":
    r"""``components=`` branch of :func:`displacive_statement` (M2).

    One element delegates straight back to the single-component call, so it
    is bit-identical to it rather than a second implementation that might
    drift from the first.  More than one, all at the same k, is form (a): the
    intersection of the components' isotropy subgroups
    (:func:`_intersection_group`) names the common child, :func:`child_basis`
    and :func:`_child_positions` are called **once** (both depend only on the
    parent's space group and k, never on which irrep), and each component then
    contributes its own modes on that one atom list via :func:`_mode_vectors`
    — unchanged from the single-component path, called once per component.
    More than one k is form (b), refused here: see
    :func:`displacive_statement`.
    """
    from fractions import Fraction as _Fraction

    from ..adp import cartesian_basis
    from ..satellites import as_propagation_vector
    from .isotropy import magnetic_cell

    comps = list(components)
    if not comps:
        raise ValueError(
            "displacive_statement(): components=[] carries no order "
            "parameter; name at least one (k, irrep, direction)")
    if len(comps) == 1:
        k0, irrep0, direction0 = comps[0]
        return displacive_statement(
            parent_phase, k0, irrep=irrep0, direction=direction0,
            child_group=child_group, magnitude=magnitude, vary=vary, name=name)
    if parent_phase.distortion_modes:
        raise ValueError(
            f"displacive_statement(): the parent phase "
            f"{parent_phase.name!r} already carries "
            f"{len(parent_phase.distortion_modes)} distortion mode(s). The "
            f"parent of a mode statement is the *undistorted* structure; pass "
            f"the parent phase, not a child one")
    canon = [(tuple(str(c) for c in as_propagation_vector(k)), irrep, direction)
             for k, irrep, direction in comps]
    distinct_k = sorted({k for k, _, _ in canon})
    if len(distinct_k) > 1:
        raise ValueError(
            f"displacive_statement(): components span {len(distinct_k)} "
            f"distinct propagation vectors {distinct_k}. A single child "
            f"supercell states one k; several k's sharing the parent cell is "
            f"form (b), the Fourier branch of the ROADMAP's 'Multi-component "
            f"magnetic statements' (M2) note, and it has no intensity path in "
            f"this version — model/forward.py sums |F|^2 from one fixed atom "
            f"list at zero phase, not the per-k Fourier series m_j(r) = "
            f"Σ_k S_kj·exp(-2πi k·r) + c.c. a several-k statement needs. Use "
            f"fourier_statement() for the schema and the reflection-list "
            f"union this rung does build, or pass components sharing one k "
            f"here for the common-subgroup form (a) this function refines")
    if child_group is not None:
        raise ValueError(
            "displacive_statement(): child_group= is checked against one "
            "candidate's own isotropy subgroup, and a multi-component "
            "statement has no single one to check it against — its child is "
            "the *intersection* of every component's. Drop child_group= and "
            "read phase.symmetry_operations / phase.space_group instead")
    k = distinct_k[0]
    dedup: list[tuple[str, str]] = []
    seen_labels: set[str] = set()
    for _, irrep, direction in canon:
        label = f"{irrep}{direction}"
        if label in seen_labels:
            raise ValueError(
                f"displacive_statement(): component {label!r} is named twice "
                f"in components=")
        seen_labels.add(label)
        dedup.append((irrep, direction))

    refuse_an_unnamed_parent(parent_phase, "displacive_statement()")
    parent_cell = parent_phase.cell.lengths_angles()
    m7_lattice = np.asarray(cartesian_basis(*parent_cell), dtype=np.float64).T
    mcell = magnetic_cell(parent_phase.space_group, k)
    per_site = _displacive_candidates(parent_phase, mcell.k, m7_lattice)
    directions_by_site = {atom.label: tuple(sorted(per_site[j]))
                          for j, atom in enumerate(parent_phase.atoms)}

    labels: list[str] = []
    for irrep, direction in dedup:
        label = f"{irrep}{direction}"
        missing = [atom.label for j, atom in enumerate(parent_phase.atoms)
                  if label not in per_site[j]]
        if missing:
            detail = "; ".join(
                f"{lab} carries {', '.join(directions_by_site[lab])}"
                for lab in missing)
            raise ValueError(
                f"displacive_statement(): the direction {label!r} is not "
                f"carried by every orbit of {parent_phase.name!r} — "
                f"{', '.join(missing)} ha{'s' if len(missing) == 1 else 've'} "
                f"no configuration in it. What "
                f"{'it does' if len(missing) == 1 else 'they do'} carry: "
                f"{detail}")
        labels.append(label)

    basis = child_basis(parent_phase.space_group, mcell.k)
    p_basis = [[_Fraction(v) for v in row] for row in basis]
    origin = (_Fraction(0), _Fraction(0), _Fraction(0))
    transform = format_transform([list(row) for row in basis], origin)
    child_cell = _child_cell_parameters(parent_cell, basis)
    child_lattice = _child_lattice(parent_cell, basis)
    cosets = lattice_cosets(basis)
    entries = _child_positions(parent_phase, basis, origin, cosets)

    references: dict[str, object] = {}
    nuclear_sets = []
    for label in labels:
        reference = per_site[0][label]
        references[label] = reference
        p_candidate = [[_Fraction(v) for v in row] for row in reference.cell.basis]
        step = _mat_mul(_isotropy._exact_inverse(p_candidate), p_basis)
        group = reference.group.transformed(
            format_transform(_isotropy._exact_inverse(step), origin))
        nuclear_sets.append(_nuclear_operations(_colourless(group)))

    intersection = _intersection_group(nuclear_sets)
    declared_ops = _nuclear_operations(intersection)
    # **M2d: reduce rather than refuse.**  D3's own refusal fired whenever the
    # positional intersection carried an operation whose true little-group
    # character splits across some component's free amplitudes — exactly
    # M2b/M2d's single-candidate defect, one level up (the intersection can
    # inherit a "grey" operation from either component, not only from the
    # candidate that names it).  M2d's fix for the single-component path
    # (:func:`_sign_consistent_operations`) answers the same question per
    # operation rather than all-or-nothing for the whole set, so it is reused
    # here to *reduce* the intersection to the subgroup that is sign-consistent
    # for **every** component, instead of refusing the moment any one
    # operation fails for any one of them. Verified exact (not merely
    # constructed) for Ba2FeSbSe5's own S2(a,b) + S3(a,b) at this k — the
    # brief's own headline example — by the A ≠ 0 P1-equality test
    # (``tests/test_epsilon_bookkeeping.py::
    # test_multi_component_reduction_matches_an_explicit_p1_build``); had that
    # test failed, this would still be the hard refusal above.
    reduced_ops = set(declared_ops)
    for label in labels:
        reference = references[label]
        m_matrix = (_isotropy._fraction_inverse(basis)
                   @ _matrix_of(reference.cell.basis))
        for j, atom in enumerate(parent_phase.atoms):
            candidate = per_site[j][label]
            reduced_ops &= _sign_consistent_operations(candidate, m_matrix, declared_ops)
    if reduced_ops != declared_ops:
        try:
            intersection = _group_from_nuclear_ops(reduced_ops)
        except ValueError as exc:
            raise ValueError(
                f"displacive_statement(): the common-subgroup child of "
                f"{', '.join(labels)} at k = {distinct_k[0]} does not "
                f"correctly carry every component's own mode field, and the "
                f"subset of its declared operations that *is* sign-consistent "
                f"for every component ({len(reduced_ops)} of "
                f"{len(declared_ops)}) does not itself close into a group "
                f"({exc}) — this is the case the reduction cannot repair; "
                f"see _sign_consistent_operations's docstring for the "
                f"mechanism, measured on Ba2FeSbSe5's own S2(a,b) + S3(a,b) "
                f"at this k. Report it rather than widen the tolerance"
            ) from exc
        declared_ops = _nuclear_operations(intersection)
    symbol = _identify_child_space_group(intersection, child_lattice)
    child_group_stmt = resolve_child_group(intersection, symbol, transform)
    diagnostics: tuple[Diagnostic, ...] = ()
    if not child_group_stmt.named:
        diagnostics = (Diagnostic(
            level="info", code="CHILD_GROUP_UNNAMED",
            where=["phases.0.space_group"],
            message=f"displacive_statement(): {child_group_stmt.reason}",
            suggestion=(
                "nothing to fix — the statement is complete. Quote the child "
                "group as its operation list (or as the closest type with the "
                "cell beside it), not as the bracketed label's leading symbol"),
        ),)
    partition = _partition_into_child_orbits(child_group_stmt.group, entries)

    atoms: list[Atom] = []
    site_map: list[tuple[int, int]] = []
    counts: dict[str, int] = {}
    for rep, _members in partition:
        j, coset, position = entries[rep]
        source = parent_phase.atoms[j]
        counts[source.label] = counts.get(source.label, 0) + 1
        suffix = "" if len(
            [1 for r, _ in partition if entries[r][0] == j]) == 1 else \
            f"_{counts[source.label]}"
        atoms.append(Atom(
            label=f"{source.label}{suffix}", species=source.species,
            x=Parameter(value=float(position[0])),
            y=Parameter(value=float(position[1])),
            z=Parameter(value=float(position[2])),
            occ=Parameter(value=source.occ.value),
            biso=Parameter(value=source.biso.value)))
        site_map.append((j, coset))
    site_map_t = tuple(site_map)

    modes: list[DistortionMode] = []
    modes_by_site: dict[str, list[str]] = {atom.label: [] for atom in parent_phase.atoms}
    for label in labels:
        reference = references[label]
        m_matrix = (_isotropy._fraction_inverse(basis)
                   @ _matrix_of(reference.cell.basis))
        for j, atom in enumerate(parent_phase.atoms):
            candidate = per_site[j][label]
            for f, pattern in enumerate(_mode_vectors(
                    atoms, site_map_t, candidate, j, m_matrix)):
                worst = float(np.max(np.linalg.norm(pattern @ child_lattice, axis=1)))
                if worst <= 0.0:            # pragma: no cover - a zero basis row
                    raise ValueError(
                        f"displacive_statement(): free amplitude {f} of "
                        f"{candidate.label} on {atom.label!r} moves no atom "
                        f"of the child cell")
                scale = float(np.abs(pattern).max())
                pattern = np.where(np.abs(pattern) < 1e-12 * scale, 0.0, pattern)
                mode_name = f"{label}-{atom.label}-{f}"
                modes_by_site[atom.label].append(mode_name)
                modes.append(DistortionMode(
                    name=mode_name, irrep_label=candidate.irrep_label,
                    direction=candidate.direction.label,
                    k=tuple(str(c) for c in mcell.k), parent_site=atom.label,
                    amplitude=Parameter(
                        value=float(magnitude), vary=bool(vary),
                        min=-DISTORTION_AMPLITUDE_MAX_A,
                        max=DISTORTION_AMPLITUDE_MAX_A, unit="A"),
                    vectors=[tuple(float(c) for c in row)
                             for row in pattern / worst]))

    ties: list[tuple[str, str, float, float]] = []
    first: dict[int, int] = {}
    for i, (parent_index, _coset) in enumerate(site_map_t):
        head = first.setdefault(parent_index, i)
        if head != i:
            ties.append((f"phases.0.atoms.{i}.biso",
                        f"phases.0.atoms.{head}.biso", 1.0, 0.0))

    phase = Phase(
        name=name or f"{parent_phase.name} {' + '.join(labels)} superstructure",
        space_group=child_group_stmt.label,
        symmetry_operations=(None if child_group_stmt.operations is None
                             else list(child_group_stmt.operations)),
        cell=Cell(a=Parameter(value=child_cell[0]), b=Parameter(value=child_cell[1]),
                  c=Parameter(value=child_cell[2]),
                  alpha=Parameter(value=child_cell[3]),
                  beta=Parameter(value=child_cell[4]),
                  gamma=Parameter(value=child_cell[5])),
        atoms=atoms,
        magnetic_symmetry=None,
        distortion_modes=modes,
        scale=Parameter(value=parent_phase.scale.value),
    )
    return MultiComponentStatement(
        phase=phase, transform=transform, index=_volume_index(basis),
        parent_space_group=parent_phase.space_group,
        child_space_group=child_group_stmt.label,
        k=tuple(str(c) for c in mcell.k), labels=tuple(labels),
        site_map=site_map_t, biso_ties=tuple(ties),
        modes_by_site={lab: tuple(names) for lab, names in modes_by_site.items()},
        directions_by_site=directions_by_site,
        child_group_named=child_group_stmt.named, diagnostics=diagnostics)


@dataclass(frozen=True)
class FourierComponentSpec:
    """One (k, irrep, direction) term of a several-k Fourier statement (M2 form (b)).

    No per-atom vectors, unlike :class:`~rietx.schemas.structure.DistortionMode`
    — see :func:`fourier_statement` for exactly why building them would be
    building a physically wrong shortcut rather than the real thing, and what
    the real thing needs.  ``amplitude`` is carried as a bare
    :class:`~rietx.schemas.common.Parameter` so the shape the schema *would*
    need is visible even though nothing here computes what it multiplies.
    """

    k: tuple[str, str, str]
    irrep_label: str
    direction: str
    amplitude: Parameter


@dataclass(frozen=True)
class FourierStatement:
    """The schema and the reflection list for a several-k Fourier statement (M2 form (b)).

    Not a :class:`~rietx.schemas.structure.Phase`, and deliberately so: there
    is no method on this object that returns one, because there is no
    structure-factor path in this version's ``model/forward.py`` that a
    ``Refinement`` could compile a multi-k Fourier amplitude through — see
    :func:`fourier_statement`.  ``reflections`` is real: the union of the
    parent's own reflection list and each component k's satellites
    (``crystallography.satellites.satellite_reflections``, WP-1326), merged
    and de-duplicated on the rational scattering-vector index, and tested
    against the same union built by hand from the two calls it wraps.
    """

    parent_space_group: str
    ks: tuple[tuple[str, str, str], ...]
    components: tuple[FourierComponentSpec, ...]
    reflections: np.ndarray
    nuclear: ReflectionSet
    satellites: dict[tuple[str, str, str], ReflectionSet]


def _merge_reflection_index(sets, tol: float = 1e-6) -> np.ndarray:
    """The union of several :class:`~..symmetry.ReflectionSet`' ``.index`` rows.

    De-duplicated by rounding each row to ``tol`` — the two rational grids
    (parent H, and H ± k for each component k) generally coincide only at
    special points, and rounding is exact for both because every index here is
    itself an exact rational with a small denominator.
    """
    rows = [rs.index for rs in sets if len(rs) > 0]
    if not rows:
        return np.zeros((0, 3), dtype=np.float64)
    all_idx = np.concatenate(rows, axis=0)
    seen: dict[tuple[int, int, int], np.ndarray] = {}
    for row in all_idx:
        key = tuple(int(round(v / tol)) for v in row)
        seen.setdefault(key, row)
    return np.array(list(seen.values()), dtype=np.float64)


def fourier_statement(parent_phase: Phase, components, wavelength: float,
                      two_theta_max: float, two_theta_min: float = 0.0
                      ) -> FourierStatement:
    r"""Form (b): several k's as Fourier components in the **parent** cell (M2).

    The ROADMAP's design note ("one phase with a magnetic component, not two
    linked phases", 2026-09-08) prefers this form for exactly the case this
    function's name describes: moments — or, per M2's extension, displacements
    — as Fourier components m_j(r) = Σ_k S_kj·exp(-2πi k·r) + c.c., with
    satellites at Q = H ± k placed straight in the **parent** cell (no
    supercell, several k allowed) by the machinery WP-1326 already built
    (:func:`~rietx.crystallography.satellites.satellite_reflections`).

    **What this function builds, and what it refuses to fake.**  The
    reflection list — ``FourierStatement.reflections`` — is real: it is the
    union of ``crystallography.symmetry.generate_reflections`` (the parent's
    own nuclear list) and one ``satellite_reflections`` call per component k,
    merged and tested against the hand-built union
    (``tests/test_multi_component_statements.py``).  What is *not* built is a
    per-atom mode vector for each component, and that is a boundary rather
    than an oversight: :func:`displacive_statement`'s form (a) reads a mode
    vector off :mod:`.isotropy`'s ``candidates(kind="displacive")``, whose
    positions and configurations live in a **commensurate supercell** — one
    static real-space distortion, unfolded into a doubled cell.  A several-k
    Fourier term is a different mathematical object: a complex amplitude and
    phase *per atom of the parent cell*, entering the structure factor at each
    satellite through its own e^{∓2πik·r} rather than through a displaced
    coordinate.  Reusing the supercell candidate's real vectors here would
    silently state the wrong physics under a name that looks like the right
    one, which is worse than refusing — so this function does not compute
    them, and there is no route from ``components`` to a compilable
    :class:`~rietx.schemas.structure.Phase`: no field, no builder, nothing for
    a caller to reach by accident.  Turning ``components`` into an intensity
    needs a genuine ``model/forward.py`` change — a vector structure-factor
    contraction over the Fourier sum at each k — which is M-10/M-11's
    scope (ROADMAP § "M-10 — mode-amplitude parametrisation" and
    § "M-11 — incommensurate magnetic structures"), not this rung's.

    ``components`` is ``[(k, irrep_label, direction), …]`` spanning **two or
    more** distinct k; one k is form (a) and refused here with a pointer to
    :func:`displacive_statement`'s ``components=``, which has a working
    intensity path this does not.
    """
    from ..satellites import as_propagation_vector, check_propagation_vector, satellite_reflections
    from ..symmetry import generate_reflections, resolve_group

    canon = [(tuple(str(c) for c in as_propagation_vector(k)), irrep, direction)
             for k, irrep, direction in components]
    distinct_k = sorted({k for k, _, _ in canon})
    if len(distinct_k) < 2:
        raise ValueError(
            f"fourier_statement(): components carry {len(distinct_k)} "
            f"distinct propagation vector(s). This function is form (b), the "
            f"several-k Fourier branch; one k with one or more irreps is form "
            f"(a), and displacive_statement(components=…) is the builder with "
            f"a working intensity path for it")
    refuse_an_unnamed_parent(parent_phase, "fourier_statement()")
    group = resolve_group(parent_phase.space_group, parent_phase.symmetry_operations)
    for k in distinct_k:
        check_propagation_vector(group, tuple(Fraction(c) for c in k))
    cell = parent_phase.cell.lengths_angles()
    # ``group``, not ``parent_phase.space_group``: the resolved object is two
    # lines up and both of these take one (``as_group`` passes it through), so
    # handing the raw string on would put a bracketed label in front of gemmi
    # for no reason.  The guard above already refuses that case, so this is
    # belt-and-braces — and it is the shape every other consumer uses.
    nuclear = generate_reflections(group, cell, wavelength,
                                   two_theta_max, two_theta_min=two_theta_min)
    satellites = {k: satellite_reflections(group, cell,
                                           wavelength, two_theta_max, k,
                                           two_theta_min=two_theta_min)
                 for k in distinct_k}
    reflections = _merge_reflection_index([nuclear, *satellites.values()])
    specs = tuple(FourierComponentSpec(
        k=k, irrep_label=irrep, direction=direction,
        amplitude=Parameter(value=0.0, vary=False,
                            min=-DISTORTION_AMPLITUDE_MAX_A,
                            max=DISTORTION_AMPLITUDE_MAX_A, unit="A"))
        for k, irrep, direction in canon)
    return FourierStatement(
        parent_space_group=parent_phase.space_group, ks=tuple(distinct_k),
        components=specs, reflections=reflections, nuclear=nuclear,
        satellites=satellites)


def seed_distortion_amplitudes(phase: Phase, amplitudes: dict[str, float], *,
                               vary: bool = True) -> Phase:
    """A copy of ``phase`` with named mode amplitudes set — coordinates and all.

    **Both halves, and that is the point.**  A phase's stored coordinates are
    the *current* structure, and the base a mode is measured from is recovered
    as ``atom.xyz − Σ_ν A_ν e_νj`` (``params.vector._collect_distortion_modes``
    — the invariant that makes a recompile a fixed point and stops a warm-
    started amplitude being applied twice).  So setting an amplitude without
    moving the atoms changes nothing at all: the base moves back by exactly as
    much as the mode moves forward, and the fit starts from the structure it
    started from with a number beside it that lies.  Measured while building
    this: a statement seeded at 0.08 Å predicted the undistorted pattern.

    ``amplitudes`` maps :attr:`~rietx.schemas.structure.DistortionMode.name` to
    the new amplitude in Å; a name the phase does not carry is refused rather
    than ignored.  ``vary`` frees exactly the named modes and leaves the rest
    as they are.

    **A negative seed is not an error.**  The overall sign of a component's
    amplitudes is a domain label rather than a measurement — negating the whole
    vector gives the other antiphase domain and the identical pattern
    (Perez-Mato, Orobengoa & Aroyo 2010, *Acta Cryst.* A**66**, 558, § 7) — so
    a caller seeding −0.05 is choosing a domain, and the report states the
    convention beside whatever the fit comes back with
    (``report.schemas.DISTORTION_SIGN_CONVENTION``).  Inside a staged plan,
    ``Stage.distortion_seed`` does this to an all-zero block automatically.
    """
    modes = list(phase.distortion_modes)
    if not modes:
        raise ValueError(
            f"seed_distortion_amplitudes(): phase {phase.name!r} carries no "
            f"distortion modes; there is nothing named {sorted(amplitudes)} "
            f"to seed")
    known = {m.name: n for n, m in enumerate(modes)}
    unknown = sorted(set(amplitudes) - set(known))
    if unknown:
        raise ValueError(
            f"seed_distortion_amplitudes(): phase {phase.name!r} carries no "
            f"distortion mode named {unknown}; it has "
            f"{sorted(known)[:8]}{'…' if len(known) > 8 else ''}")
    shift = np.zeros((len(phase.atoms), 3), dtype=np.float64)
    new_modes = list(modes)
    for name, value in amplitudes.items():
        n = known[name]
        mode = modes[n]
        delta = float(value) - mode.amplitude.value
        shift += delta * np.asarray(mode.vectors, dtype=np.float64)
        new_modes[n] = mode.model_copy(update={
            "amplitude": mode.amplitude.model_copy(update={
                "value": float(value), "vary": bool(vary)})})
    atoms = [atom.model_copy(update={
        "x": atom.x.model_copy(update={"value": float(atom.x.value + shift[j][0])}),
        "y": atom.y.model_copy(update={"value": float(atom.y.value + shift[j][1])}),
        "z": atom.z.model_copy(update={"value": float(atom.z.value + shift[j][2])}),
    }) for j, atom in enumerate(phase.atoms)]
    return phase.model_copy(update={"atoms": atoms,
                                    "distortion_modes": new_modes})
