"""The free real-amplitude count, against the real fields the vectors build (#601).

The count a refinement varies for an irrep is the real dimension of the moment
fields it can make,

    m_j(R) = Σ_l C_l·ψ_lj·e^{+2πik·R} + c.c.,      C_l complex,

which is the module docstring's own definition of what the vectors mean.  The
oracle here builds those fields on a block of cells, for C = 1 and C = i on
every vector, and takes the rank: it never asks whether the vectors are real,
what the Frobenius–Schur indicator is, or which irrep is whose partner, so it
cannot share a mistake with the counting rule it checks.

What it must give (Bradley & Cracknell, 1972, Def. 1.3.7 p. 20 and Th. 4.6.2
p. 204): at 2k ∈ L*, n·d for FS = ±1 and 2·n·d for FS = 0, the counts closing on
3N with a conjugate pair counted once; at 2k ∉ L*, 2·n·d for every irrep and a
total of 2·3N.  Before the fix a pseudoreal irrep was counted 2·n·d (P2₁2₁2₁ at
(½,½,½): 24 on a 12-dimensional moment space), and at 2k ∉ L* an irrep whose
vectors came out real was counted n·d and a conjugate-character pair collapsed
(P 3 at K: 9 against 18).
"""

from fractions import Fraction
from math import lcm

import numpy as np
import pytest

from rietx.crystallography.magnetic import isotropy
from rietx.crystallography.representation import irreps, modes

H, T, Q = Fraction(1, 2), Fraction(1, 3), Fraction(1, 4)
GENERAL = (0.1234, 0.2345, 0.3456)

# (group, k, 2k in L*, {irrep label: expected free real amplitudes}); the
# per-irrep numbers are the closure arithmetic of the module docstring, written
# out so that a change in any one of them is visible here.
CASES = [
    ("P 21 21 21", (H, H, H), True, {"S1": 12}),
    ("P a -3", (H, H, H), True, {"S1": 12, "S2": 12, "S3": 24, "S4": 24, "S5": 24, "S6": 24}),
    ("P 4 c c", (0, 0, H), True, {"S1": 6, "S2": 6, "S3": 6, "S4": 6, "S5": 12}),
    ("P n m a", (0, 0, H), True, {"S1": 12, "S2": 12}),
    ("P 3", (T, T, 0), False, {"S1": 6, "S2": 6, "S3": 6}),
    ("P 4", (0, 0, Q), False, {"S1": 6, "S2": 6, "S3": 6, "S4": 6}),
    ("P n m a", (0, 0, Q), False, {"S1": 12, "S2": 12, "S3": 12, "S4": 12}),
]
IDS = [f"{g.replace(' ', '')}-{'_'.join(str(c) for c in k)}" for g, k, *_ in CASES]


def _fields(bases, k) -> np.ndarray:
    """Rows: the real field of C·ψ on a block of cells, C ∈ {1, i}, every ψ.

    The cells are lattice vectors: an integer block plus the centring vectors,
    without which a centred lattice's 2k ∉ L* would look like 2k ∈ L*.
    """
    span = lcm(*(Fraction(c).denominator for c in k), 2)
    centrings = [[float(c) for c in t] for t in bases[0].representation.little.centrings]
    cells = np.array([(x + t[0], y + t[1], z + t[2]) for x in range(span)
                      for y in range(span) for z in range(span) for t in centrings])
    phase = np.exp(2j * np.pi * cells @ np.array([float(c) for c in k]))   # (R,)
    rows = []
    for basis in bases:
        for psi in basis.vectors.reshape(-1, basis.vectors.shape[-2] * 3):
            for c in (1.0, 1.0j):
                rows.append(np.real(c * phase[:, None] * psi[None, :]).reshape(-1))
    return np.array(rows)


def _rank(rows: np.ndarray) -> int:
    s = np.linalg.svd(rows, compute_uv=False)
    return int(np.sum(s > 1e-8 * max(1.0, float(s.max()))))


@pytest.mark.parametrize("group, k, two_k_in_lattice, expected", CASES, ids=IDS)
def test_each_irrep_counts_the_real_fields_it_makes(group, k, two_k_in_lattice, expected):
    rep = modes.magnetic_representation(group, GENERAL, k)
    assert rep.little.has_minus_k is two_k_in_lattice
    table = modes.mode_table(rep, irreps.small_irreps(group, k))
    got = {b.irrep.label: b.free_real_amplitudes for b in table.bases}
    assert got == expected
    for basis in table.bases:
        assert _rank(_fields([basis], k)) == basis.free_real_amplitudes, basis.irrep.label


@pytest.mark.parametrize("group, k, two_k_in_lattice, expected", CASES, ids=IDS)
def test_the_total_closes_on_3n_or_twice_it(group, k, two_k_in_lattice, expected):
    rep = modes.magnetic_representation(group, GENERAL, k)
    table = modes.mode_table(rep, irreps.small_irreps(group, k))
    closure = rep.dimension if two_k_in_lattice else 2 * rep.dimension
    assert table.total_free_real_amplitudes == closure
    assert _rank(_fields(table.bases, k)) == closure


def test_a_pseudoreal_irrep_is_counted_once_not_twice():
    """P2₁2₁2₁ at (½,½,½): the issue's case, by the reality class it hinges on."""
    rep = modes.magnetic_representation("P 21 21 21", GENERAL, (H, H, H))
    (basis,) = modes.mode_table(rep, irreps.small_irreps("P 21 21 21", (H, H, H))).bases
    assert basis.irrep.frobenius_schur == -1 and basis.reality == "pseudoreal"
    assert not basis.real                       # complex vectors, and still n·d
    assert (basis.multiplicity, basis.irrep.dimension) == (6, 2)
    assert basis.free_real_amplitudes == 12 == rep.dimension
    assert "n*d dimensions" in basis.pairing


def test_at_two_k_off_the_lattice_real_vectors_still_need_complex_amplitudes():
    """P 4 at (0,0,¼): S1 and S4 come out real, and C and iC still differ."""
    rep = modes.magnetic_representation("P 4", GENERAL, (0, 0, Q))
    table = modes.mode_table(rep, irreps.small_irreps("P 4", (0, 0, Q)))
    real = [b for b in table.bases if b.real]
    assert {b.irrep.label for b in real} == {"S1", "S4"}
    for basis in real:
        assert basis.free_real_amplitudes == 2 * basis.multiplicity * basis.irrep.dimension
        assert _rank(_fields([basis], (0, 0, Q))) == basis.free_real_amplitudes


@pytest.mark.parametrize("group, k", [("P 21 21 21", (H, H, H)), ("P 4 c c", (0, 0, H))])
def test_candidate_amplitudes_are_independent_on_a_pseudoreal_irrep(group, k):
    """``free_amplitudes`` is the rank of the configurations it parameterises."""
    found = isotropy.candidates(group, GENERAL, k, cell=np.diag([5.0, 6.0, 7.0]))
    assert len(found.candidates) > 0
    for candidate in found.candidates:
        flat = candidate.configurations.reshape(candidate.free_amplitudes, -1)
        assert _rank(flat) == candidate.free_amplitudes, candidate.label
    widest = max(c.free_amplitudes for c in found.candidates)
    assert widest <= found.representation.dimension


def test_pseudoreal_order_parameter_space_keeps_half_the_copies():
    rep = modes.magnetic_representation("P 21 21 21", GENERAL, (H, H, H))
    (irrep,) = irreps.small_irreps("P 21 21 21", (H, H, H))
    space = isotropy.order_parameter_space(modes.basis_vectors(rep, irrep))
    assert (space.dimension, space.copies) == (4, 3)      # 2d, n/2
    assert space.copies * space.dimension == 12


def _rotated(irrep):
    """The same irrep in a complex unitary gauge: the planted error of #601."""
    u = np.array([[np.cos(0.7), 1j * np.sin(0.7)], [1j * np.sin(0.7), np.cos(0.7)]])
    return irreps.SmallIrrep(irrep.label, irrep.dimension,
                             np.einsum("ab,gbc,dc->gad", u, irrep.matrices, u.conj()),
                             irrep.characters, irrep.reality, irrep.frobenius_schur,
                             irrep.little)


def test_the_count_does_not_follow_the_gauge(monkeypatch):
    """Positive arm: a real irrep projected in a complex gauge.

    Pnma at (0,0,½) is real (FS = +1).  With the real gauge disabled and the
    irrep rotated by a complex unitary, the vectors come out complex; the count
    must stay n·d = 12, which is what the fields span, and the order-parameter
    space, whose realification is then reducible, must refuse rather than
    hand out 24 amplitudes for a 12-dimensional block.
    """
    rep = modes.magnetic_representation("P n m a", GENERAL, (0, 0, H))
    monkeypatch.setattr(modes, "_maybe_real_gauge", lambda rep, irrep: (irrep.matrices, False))
    for irrep in irreps.small_irreps("P n m a", (0, 0, H)):
        basis = modes.basis_vectors(rep, _rotated(irrep))
        assert not basis.real
        assert basis.free_real_amplitudes == 12 == _rank(_fields([basis], (0, 0, H)))
        with pytest.raises(RuntimeError, match="came without a real gauge"):
            isotropy.order_parameter_space(basis)
