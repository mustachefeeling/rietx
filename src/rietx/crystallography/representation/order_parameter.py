"""The real order-parameter space of one irrep, and its isotropy directions.

:mod:`.irreps` gives the small irreps of the little group of **k** and
:mod:`.modes` projects a site orbit's basis vectors for each of them.  This
module turns one irrep's basis into the real space its amplitudes live in, with
the grey little group G_k1' acting on it (:func:`order_parameter_space`), and
lists every direction in that space with a distinct stabiliser — the isotropy
subgroups of Stokes & Hatch (1988) as group elements
(:func:`isotropy_directions`).  It is kind-neutral: ``kind="magnetic"`` gives
time reversal the −1 a moment carries and ``kind="displacive"`` the +1 a
displacement carries.  Turning a stabiliser into a space group, a cell and an
operator list is :func:`~rietx.crystallography.magnetic.isotropy.candidates`
(#418, WP-1419).

Conventions a caller can get wrong silently
-------------------------------------------
1. **The order-parameter space is real.**  For an irrep with a real gauge (the
   one :func:`~.modes.basis_vectors` already found) it is ℝ^{d_ν}; otherwise
   it is the *realification* ℝ^{2d_ν}, with matrices [[Re D, −Im D], [Im D,
   Re D]], which is the physically irreducible representation and is what makes
   the amplitude count agree with :attr:`~.modes.IrrepBasis.free_real_amplitudes`.
   For a **pseudoreal** irrep (Frobenius–Schur −1) the n_ν realified copies are
   not independent: the real irrep complexifies to D ⊕ D, so they pair up and
   n_ν/2 of them span the real isotypic block of n_ν·d_ν dimensions; only those
   are kept (Bradley & Cracknell, 1972, Def. 1.3.7 p. 20).
   The realification is only a representation of the same group because Γ_mag
   is real, which is exactly what 2k ∈ L* buys — the same fact the scope fence
   of :mod:`~rietx.crystallography.magnetic.isotropy` rests on.

2. **The direction label is gauge-dependent; the subgroup is not.**  The irrep
   matrices are canonical only up to a unitary intertwiner (:mod:`.irreps`), so
   which vector of the order-parameter space is called (a, a, 0) depends on the
   gauge :func:`~.modes.basis_vectors` chose.  The set of stabiliser subgroups,
   the operator lists, the identified BNS numbers and the moment families do
   **not**: conjugating the gauge conjugates the fixed subspaces and leaves the
   stabilisers alone.  So the labels here are this package's, not ISODISTORT's,
   and a comparison with a published table must be made on the subgroup.

References
----------
Stokes, H. T. & Hatch, D. M. (1988). *Isotropy Subgroups of the 230
Crystallographic Space Groups*. Singapore: World Scientific.
Campbell, B. J., Stokes, H. T., Tanner, D. E. & Hatch, D. M. (2006).
*J. Appl. Cryst.* **39**, 607 — ISODISPLACE.
Howard, C. J. & Stokes, H. T. (1998). *Acta Cryst.* B**54**, 782.
Bradley, C. J. & Cracknell, A. P. (1972). *The Mathematical Theory of Symmetry
in Solids*. Oxford: Clarendon Press.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from .irreps import LittleGroup, SmallIrrep
from .modes import IrrepBasis

#: Order-parameter kinds.  ``"magnetic"`` gives time reversal the −1 a moment
#: carries; ``"displacive"`` gives it the +1 a displacement carries (the
#: coset character ε(Δ) acts on both kinds alike)
ORDER_PARAMETER_KINDS = ("magnetic", "displacive")

#: Tolerance on the numerical linear algebra of the order-parameter space —
#: subspace comparisons, fixed-subspace ranks, "this matrix is real".  The
#: irrep matrices come out of an eigendecomposition (:mod:`.irreps`), so this
#: cannot be exact; it is deliberately far above the residuals :mod:`.modes`
#: verifies (1e-14) and far below any real degeneracy.
ISOTROPY_ATOL = 1e-8

_LETTERS = "abcdefghijklmnopqrstuvwxyz"


# --------------------------------------------------------------------------
# the order-parameter space
# --------------------------------------------------------------------------

#: One element of the grey little group as the order parameter sees it:
#: ``(index into LittleGroup, time-reversal sign)``.
GreyElement = tuple[int, int]


@dataclass(frozen=True, eq=False)
class OrderParameterSpace:
    """The real order-parameter space of one irrep under the grey little group.

    ``matrices[e]`` is the real matrix by which the element ``elements[e]`` acts.
    ``configurations[c, p]`` is the ``(N, 3)`` moment pattern of order-parameter
    coordinate ``p`` in copy ``c``, in the parent's own cell and in contravariant
    fractional components, so a point (amplitudes A) of the family is
    Σ_{c,p} A[c, p]·configurations[c, p].

    ``doubled`` says the irrep had no real gauge and the space is the
    realification, of dimension 2d_ν; :attr:`dimension` is d_ν otherwise.
    """

    irrep: SmallIrrep
    basis: IrrepBasis
    kind: str
    elements: tuple[GreyElement, ...]
    matrices: np.ndarray            # (2n, dim, dim) float
    configurations: np.ndarray      # (n_copies, dim, N, 3) float
    doubled: bool

    @property
    def dimension(self) -> int:
        """Dimension of the real order-parameter space, d_ν or 2·d_ν."""
        return int(self.matrices.shape[1])

    @property
    def copies(self) -> int:
        """The independent copies: n_ν, or n_ν/2 for a pseudoreal irrep (convention 1)."""
        return int(self.configurations.shape[0])

    @property
    def little(self) -> LittleGroup:
        return self.irrep.little


def order_parameter_space(basis: IrrepBasis, *, kind: str = "magnetic"
                          ) -> OrderParameterSpace:
    """The real order-parameter space of one irrep, with time reversal in the group.

    The grey little group is G_k1' = G_k ∪ G_k·1'.  A **magnetic** order
    parameter changes sign under 1' and a **displacive** one does not.  The
    element (g, ε) acts by ε·D_ν(g) for **both** kinds: ε is the character of
    the coset (the anti-translation of a k ≠ 0 star carries −1 on the order
    parameter, whatever the order parameter is) and for a moment it also
    absorbs the time-reversal sign.  What ``kind`` changes is which group
    :func:`~rietx.crystallography.magnetic.isotropy.candidates`
    builds from the stabiliser: a displacive element
    {R | v + Δ} stabilises the field when ε(Δ) = η, with either time-reversal
    sign, since a displacement ignores 1' (Howard & Stokes 1998, *Acta Cryst.*
    B54, 782).  D_ν is taken in the gauge
    :func:`~.modes.basis_vectors` used for the vectors, so the order-parameter
    coordinates and the moment patterns are in step; where that gauge is not
    real the space is the realification (module docstring, convention 1).

    The construction is Stokes & Hatch (1988): an isotropy subgroup is the
    stabiliser of a point of this space, and turning it into a magnetic space
    group is what
    :func:`~rietx.crystallography.magnetic.isotropy.candidates` then does.
    """
    if kind not in ORDER_PARAMETER_KINDS:
        raise ValueError(f"kind must be one of {ORDER_PARAMETER_KINDS}, got {kind!r}")
    if basis.multiplicity == 0:
        raise ValueError(
            f"irrep {basis.irrep.label!r} does not occur in this site representation "
            f"(multiplicity 0), so it has no order-parameter space here")
    matrices = np.asarray(basis.irrep_matrices)
    vectors = np.asarray(basis.vectors)
    real_gauge = float(np.max(np.abs(matrices.imag))) <= ISOTROPY_ATOL
    if real_gauge != bool(basis.real):
        raise RuntimeError(
            f"irrep {basis.irrep.label!r} has real matrices = {real_gauge} but real "
            f"basis vectors = {basis.real}; with a real representation the two are the "
            f"same statement and this module's amplitude count depends on it")
    if not real_gauge and basis.irrep.frobenius_schur == 1:
        raise RuntimeError(
            f"irrep {basis.irrep.label!r} is real (Frobenius-Schur +1) but came without a "
            f"real gauge; its realification is reducible, so the order-parameter space and "
            f"the amplitude count would both be wrong. modes._maybe_real_gauge should have "
            f"found one; this is a bug, not a tolerance")
    n_ops = matrices.shape[0]
    if real_gauge:
        small = matrices.real
        configs = vectors.real
    else:
        small = np.array([np.block([[m.real, -m.imag], [m.imag, m.real]])
                          for m in matrices])
        # m = Σ C ψ + c.c. with C = A + iB gives m = Σ (A·2Reψ − B·2Imψ)
        configs = _independent_copies(
            np.concatenate([2.0 * vectors.real, -2.0 * vectors.imag], axis=1))
    elements: list[GreyElement] = []
    stack: list[np.ndarray] = []
    for i in range(n_ops):
        for eps in (1, -1):
            elements.append((i, eps))
            stack.append(eps * small[i])
    space = OrderParameterSpace(
        irrep=basis.irrep, basis=basis, kind=kind, elements=tuple(elements),
        matrices=np.array(stack, dtype=np.float64), configurations=configs,
        doubled=not real_gauge)
    expected = basis.free_real_amplitudes
    if space.copies * space.dimension != expected:
        raise RuntimeError(
            f"{basis.irrep.label!r} gives {space.copies}·{space.dimension} real "
            f"order-parameter coordinates against {expected} free real amplitudes "
            f"from modes.basis_vectors; the realification and the amplitude count "
            f"must agree or every parameter count downstream is wrong")
    return space


def _independent_copies(configs: np.ndarray) -> np.ndarray:
    """The realified copies whose moment patterns are independent, in order.

    Each realified copy spans a subspace of moment space carrying the same real
    representation, irreducible for FS = 0 and FS = −1, so a copy either adds
    its whole dimension to the span of those kept or adds nothing.  For FS = 0
    every copy adds; for a pseudoreal irrep half of them do, because the real
    irrep complexifies to D ⊕ D and the n_ν complex copies pair up.  A partial
    increment means the realified copy is reducible, and is refused.
    """
    kept: list[np.ndarray] = []
    rank = 0
    for copy in configs:
        flat = np.concatenate(kept + [copy]).reshape(-1, copy[0].size)
        s = np.linalg.svd(flat, compute_uv=False)
        new_rank = int(np.sum(s > ISOTROPY_ATOL * max(1.0, float(s.max()))))
        if new_rank == rank:
            continue
        if new_rank != rank + copy.shape[0]:
            raise RuntimeError(
                f"a realified copy adds {new_rank - rank} of its {copy.shape[0]} "
                f"dimensions to the span of the others; it is reducible, so the "
                f"order-parameter space would be wrong. This is a bug, not a tolerance")
        kept.append(copy)
        rank = new_rank
    return np.array(kept, dtype=np.float64)


# --------------------------------------------------------------------------
# the lattice of fixed subspaces
# --------------------------------------------------------------------------

def _nullspace(matrix: np.ndarray, atol: float = ISOTROPY_ATOL) -> np.ndarray:
    """Orthonormal rows spanning ker(matrix)."""
    m = np.atleast_2d(np.asarray(matrix, dtype=np.float64))
    _, s, vt = np.linalg.svd(m)
    scale = max(1.0, float(s.max())) if s.size else 1.0
    rank = int(np.sum(s > atol * scale))
    return vt[rank:]


def _projector(rows: np.ndarray, dim: int) -> np.ndarray:
    if rows.shape[0] == 0:
        return np.zeros((dim, dim))
    q, _ = np.linalg.qr(np.asarray(rows, dtype=np.float64).T)
    return q @ q.T


def _intersect(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Projector onto the intersection of two subspaces given by projectors."""
    dim = p.shape[0]
    eye = np.eye(dim)
    return _projector(_nullspace(np.vstack([eye - p, eye - q])), dim)


@dataclass(frozen=True, eq=False)
class OrderParameterDirection:
    """One order-parameter direction, as the subspace its stabiliser fixes pointwise.

    ``subspace`` has orthonormal rows spanning the largest set of
    order-parameter values every element of ``stabilizer`` leaves alone; the
    ISOTROPY-style ``label`` — ``(a, 0, 0)``, ``(a, a, 0)``, ``(a, b, 0)`` — is
    that subspace written as a general vector, and is **gauge-dependent**
    (module docstring, convention 2).  ``stabilizer`` is the isotropy subgroup
    as grey-little-group *elements*.  ``conjugates`` is how many distinct
    stabilisers are conjugate to this one in the grey little group — the
    orientation domains within one arm of the star — which is not the domain
    count (issue #608): see
    :meth:`~rietx.crystallography.magnetic.isotropy.CandidateSet.domain_counts`.
    """

    label: str
    subspace: np.ndarray            # (r, dim) orthonormal rows
    stabilizer: tuple[GreyElement, ...]
    conjugates: int = 1

    @property
    def rank(self) -> int:
        """Number of independent order-parameter components the direction leaves free."""
        return int(self.subspace.shape[0])


def _rref(rows: np.ndarray) -> np.ndarray:
    """Reduced row echelon form of a float row space, pivots normalised to 1."""
    m = np.array(rows, dtype=np.float64, copy=True)
    n_rows, n_cols = m.shape
    pivot = 0
    for col in range(n_cols):
        if pivot >= n_rows:
            break
        target = pivot + int(np.argmax(np.abs(m[pivot:, col])))
        if abs(m[target, col]) <= 1e-9:
            continue
        m[[pivot, target]] = m[[target, pivot]]
        m[pivot] = m[pivot] / m[pivot, col]
        for r in range(n_rows):
            if r != pivot and abs(m[r, col]) > 0:
                m[r] = m[r] - m[r, col] * m[pivot]
        pivot += 1
    return m[:pivot]


_SIMPLE = [Fraction(n, d) for d in (1, 2, 3, 4, 6) for n in range(-4 * d, 4 * d + 1)]


def _as_simple(value: float) -> Fraction | None:
    for f in _SIMPLE:
        if abs(float(f) - value) < 1e-6:
            return f
    return None


def _direction_label(subspace: np.ndarray) -> str:
    """``(a, a, 0)``-style label for a subspace, or a positional one if it will not fit."""
    rows = _rref(subspace)
    entries: list[list[Fraction]] = []
    for col in range(subspace.shape[1]):
        column = []
        for r in range(rows.shape[0]):
            simple = _as_simple(float(rows[r, col]))
            if simple is None:
                return ""
            column.append(simple)
        entries.append(column)
    parts = []
    for column in entries:
        terms = []
        for q, coeff in enumerate(column):
            if coeff == 0:
                continue
            letter = _LETTERS[q]
            if coeff == 1:
                terms.append(f"+{letter}")
            elif coeff == -1:
                terms.append(f"-{letter}")
            else:
                terms.append(f"{coeff:+}{letter}")
        text = "".join(terms).lstrip("+") if terms else "0"
        parts.append(text)
    return "(" + ",".join(parts) + ")"


def isotropy_directions(space: OrderParameterSpace, *, limit: int = 512,
                        conjugacy: bool = True) -> tuple[OrderParameterDirection, ...]:
    """Every order-parameter direction with a distinct stabiliser, one per stabiliser.

    The fixed subspace of each element of the image is computed, the lattice of
    their intersections is closed, and each non-zero subspace V is replaced by
    the largest subspace with the same pointwise stabiliser S(V) = {h : h·v = v
    ∀ v ∈ V} — so the representatives and the isotropy subgroups are in
    bijection.  The whole space (the kernel of the representation, ISOTROPY's
    "general direction") is always among them.  This is the enumeration Stokes &
    Hatch (1988) tabulate and Campbell et al. (2006) drive ISODISPLACE from,
    for moments and — since the coset character ε(Δ) enters both kinds alike —
    for displacements (Howard & Stokes 1998), which a ``+D``-only
    enumeration lacked: it missed every direction whose stabiliser needs an
    element acting as −D.

    With ``conjugacy`` (the default) directions related by an element of the
    grey little group are collapsed to one, and :attr:`OrderParameterDirection.
    conjugates` counts how many were: conjugate stabilisers are the same
    structure in a different **orientation**, so listing all of [100], [010]
    and [001] as candidates would put three copies of one model in the table
    and then discover that a powder cannot tell them apart.  That count is
    [G_k1′ : N(H)], the conjugate directions, and not the number of domains
    [G_k1′ : H] (issue #608): 1′ normalises every H and is in no magnetic one,
    so the time-reversed (180°) domain shares its direction's stabiliser and is
    never counted here — the count is at most half the domains, and 1 for a
    general direction.
    :meth:`~rietx.crystallography.magnetic.isotropy.CandidateSet.domain_counts`
    gives the domains.  Setting it False gives
    every distinct stabiliser, which is what a domain census wants.

    For a one-dimensional irrep there is exactly one direction, whatever the
    group.  ``limit`` guards the intersection closure, which is finite but has
    no useful *a priori* bound.
    """
    dim = space.dimension
    eye = np.eye(dim)
    fixed = [(_projector(_nullspace(m - eye), dim), m) for m in space.matrices]
    lattice = [eye]
    frontier = [eye]
    while frontier:
        current = frontier.pop()
        for p, _ in fixed:
            candidate = _intersect(current, p)
            if float(np.trace(candidate)) < 0.5:
                continue
            if any(np.allclose(candidate, seen, atol=1e-7) for seen in lattice):
                continue
            lattice.append(candidate)
            frontier.append(candidate)
            if len(lattice) > limit:
                raise RuntimeError(
                    f"the lattice of fixed subspaces of {space.irrep.label!r} passed "
                    f"{limit} members in dimension {dim}; this is a guard, not a "
                    f"tolerance — raise `limit` deliberately if a real case needs it")
    by_stabilizer: dict[tuple[GreyElement, ...], np.ndarray] = {}
    for p in lattice:
        stabilizer = tuple(
            element for element, (_, m) in zip(space.elements, fixed)
            if np.max(np.abs((m - eye) @ p)) <= 1e-7)
        maximal = eye
        for element, (q, _) in zip(space.elements, fixed):
            if element in stabilizer:
                maximal = _intersect(maximal, q)
        if stabilizer not in by_stabilizer:
            by_stabilizer[stabilizer] = maximal
    items = [(stabilizer, _projector_rows(projector))
             for stabilizer, projector in by_stabilizer.items()]
    groups: list[list[int]] = []
    if conjugacy:
        projectors = [_projector(rows, dim) for _, rows in items]
        assigned: dict[int, int] = {}
        for i in range(len(items)):
            if i in assigned:
                continue
            members = [i]
            assigned[i] = len(groups)
            for h in space.matrices:
                moved = _projector(items[i][1] @ h.T, dim)
                for j in range(len(items)):
                    if j in assigned:
                        continue
                    if np.allclose(moved, projectors[j], atol=1e-7):
                        assigned[j] = len(groups)
                        members.append(j)
            groups.append(members)
    else:
        groups = [[i] for i in range(len(items))]
    out: list[OrderParameterDirection] = []
    for members in groups:
        stabilizer, rows = items[members[0]]
        out.append(OrderParameterDirection(
            label=_direction_label(rows) or f"(rank {rows.shape[0]})",
            subspace=rows, stabilizer=stabilizer, conjugates=len(members)))
    out.sort(key=lambda d: (d.rank, -len(d.stabilizer), d.label))
    # a gauge that is not axis-aligned gives several directions the same
    # fallback label; number them so a table row still names one candidate
    seen: dict[str, int] = {}
    for i, direction in enumerate(out):
        seen[direction.label] = seen.get(direction.label, 0) + 1
    running: dict[str, int] = {}
    numbered = []
    for direction in out:
        if seen[direction.label] == 1:
            numbered.append(direction)
            continue
        running[direction.label] = running.get(direction.label, 0) + 1
        numbered.append(OrderParameterDirection(
            label=f"{direction.label}#{running[direction.label]}",
            subspace=direction.subspace, stabilizer=direction.stabilizer,
            conjugates=direction.conjugates))
    return tuple(numbered)


def _projector_rows(projector: np.ndarray) -> np.ndarray:
    """Orthonormal rows spanning the image of a projector, in a stable orientation."""
    dim = projector.shape[0]
    rank = int(round(float(np.trace(projector))))
    if rank == 0:
        return np.zeros((0, dim))
    values, vectors = np.linalg.eigh(projector)
    rows = vectors[:, -rank:].T
    rows = _rref(rows)
    # normalise each row so the comparison and the label are deterministic
    for i in range(rows.shape[0]):
        pivot = rows[i][np.argmax(np.abs(rows[i]) > 1e-9)]
        if pivot < 0:
            rows[i] = -rows[i]
    q, _ = np.linalg.qr(rows.T)
    return q.T if rank > 1 else rows / np.linalg.norm(rows, axis=1, keepdims=True)
