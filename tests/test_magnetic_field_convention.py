"""The translation-phase convention of the basis vectors, pinned on the FIELD side.

:mod:`rietx.crystallography.representation.modes` returns basis vectors ψ that transform by
the small irrep matrices D under the little group, with the Bradley & Cracknell
translation convention D({E|a}) = exp(−2πi k·a).  That fixes which Bloch wave the ψ
are the coefficients of: a moment field built as

    m_j(R + r_j) = Σ_l C_l ψ_lj exp(+2πi k·R) + c.c.

is the one whose active image under g ∈ G_k reproduces D(g).  Built on
exp(−2πi k·R) instead — the FullProf/Perez-Mato exponent, whose coefficient is
S_kj = conj(Σ_l C_l ψ_lj) — the same numbers give a field that transforms by D*(g),
which for 2k ∉ L* is a different irrep (a relabel) or, when the return phases within
the orbit are complex, no single irrep at all.

The decomposition-side control, ``test_magnetic_modes.py::_conjugate_return_phases``,
compares Γ with D.  It cannot see a sign error made *after* the vectors are returned,
which is the error a caller following a printed recipe makes.  These tests build the
field and measure it, on three complex-k cases where the two signs differ, with a
zone-boundary positive arm where they cannot, a negative arm that conjugates the
vectors, and spglib's magnetic-space-group identification as an oracle that knows
nothing about k, irreps or either sign.
"""
from __future__ import annotations

import itertools
from fractions import Fraction

import numpy as np
import pytest
import spglib

from rietx.crystallography.representation import irreps as I
from rietx.crystallography.representation import modes as M

THIRD = Fraction(1, 3)
HALF = Fraction(1, 2)

#: Complex-k cases: the return phases within the orbit are cube roots of unity, so
#: D ≠ D* on point operations and the two exponent signs give different fields.
COMPLEX_CASES = [
    pytest.param("P 6/m m m", (0.5, 0.0, 0.5), (THIRD, THIRD, 0), id="P6/mmm-3g-K"),
    pytest.param("P 63/m m c", (1 / 3, 2 / 3, 0.25), (0, 0, THIRD), id="P63/mmc-2c-(0,0,1/3)"),
    pytest.param("P 6", (1 / 3, 2 / 3, 0.1), (THIRD, THIRD, 0), id="P6-2b-K"),
]
#: Zone-boundary cases: 2k ∈ L*, every phase ±1, the sign is invisible by design.
REAL_CASES = [
    pytest.param("P 6/m m m", (0.5, 0.0, 0.5), (HALF, 0, 0), id="P6/mmm-3g-M"),
    pytest.param("P 63/m m c", (1 / 3, 2 / 3, 0.25), (0, 0, HALF), id="P63/mmc-2c-A"),
]

ATOL = 1e-9


# --------------------------------------------------------------------------
# the field, the active action and the read-back
# --------------------------------------------------------------------------

def _supercell(positions, k):
    """Every atom r_j + R of the smallest supercell periodic for k: (x, j, R)."""
    n = [max(1, Fraction(c).denominator) for c in k]
    atoms = [(np.asarray(R, float) + r, j, np.asarray(R, float))
             for R in itertools.product(*(range(m) for m in n))
             for j, r in enumerate(positions)]
    return atoms, np.array(n, float)


def _index(atoms, x, n):
    for i, (y, _, _) in enumerate(atoms):
        d = (x - y) - n * np.rint((x - y) / n)
        if np.all(np.abs(d) < 1e-6):
            return i
    raise KeyError(x)


def _field(atoms, psi, k, sign):
    """One complex Bloch component f_l(R + r_j) = ψ_lj exp(sign·2πi k·R), flattened."""
    kf = np.array([float(c) for c in k])
    return np.concatenate([psi[j] * np.exp(sign * 2j * np.pi * kf @ R) for (_, j, R) in atoms])


def _act(atoms, n, f, rot, tran):
    """Active action of {R|v} on an axial field: f'(g x) = det(R)·R·f(x)."""
    rot = np.asarray(rot, float)
    tran = np.array([float(t) for t in tran])
    a = np.linalg.det(rot) * rot
    out = np.zeros_like(f)
    for i, (x, _, _) in enumerate(atoms):
        i2 = _index(atoms, rot @ x + tran, n)
        out[3 * i2:3 * i2 + 3] = a @ f[3 * i:3 * i + 3]
    return out


def _read(fields, images):
    """M with O_g f_l = Σ_m M_ml f_m, and the relative residual outside span{f}."""
    b = np.array(fields).T
    m, *_ = np.linalg.lstsq(b, np.array(images).T, rcond=None)
    resid = np.linalg.norm(b @ m - np.array(images).T) / np.linalg.norm(images)
    return m, resid


def _measure(rep, basis, psis, sign):
    """(span residual, max|M−D|, max|M−D*|) over the little group, for one basis set."""
    atoms, n = _supercell(rep.positions, rep.little.k)
    fields = [_field(atoms, p, rep.little.k, sign) for p in psis]
    worst = dev_d = dev_dc = 0.0
    for g in range(rep.little.order):
        images = [_act(atoms, n, f, rep.little.rotations[g], rep.little.translations[g])
                  for f in fields]
        m, resid = _read(fields, images)
        worst = max(worst, resid)
        dev_d = max(dev_d, float(np.max(np.abs(m - basis.irrep_matrices[g]))))
        dev_dc = max(dev_dc, float(np.max(np.abs(m - np.conj(basis.irrep_matrices[g])))))
    return worst, dev_d, dev_dc


def _translation_eigenvalue(rep, psi, sign, axis):
    atoms, n = _supercell(rep.positions, rep.little.k)
    f = _field(atoms, psi, rep.little.k, sign)
    t = np.zeros(3)
    t[axis] = 1
    m, resid = _read([f], [_act(atoms, n, f, np.eye(3), t)])
    assert resid < ATOL
    return complex(m[0, 0])


def _bases(symbol, site, k):
    rep = M.magnetic_representation(symbol, site, k)
    return rep, [b for b in (M.basis_vectors(rep, ir) for ir in I.small_irreps(symbol, k))
                 if b.multiplicity]


# --------------------------------------------------------------------------
# the pin
# --------------------------------------------------------------------------

@pytest.mark.parametrize("symbol, site, k", COMPLEX_CASES)
def test_a_field_on_exp_plus_2pi_i_k_R_transforms_by_the_irrep_matrices(symbol, site, k):
    """Active g on Σ ψ exp(+2πi k·R) reads back D(g), and D ≠ D* is visible."""
    rep, bases = _bases(symbol, site, k)
    assert not rep.little.has_minus_k
    seen_conjugate_difference = False
    for basis in bases:
        for s in range(basis.multiplicity):
            resid, dev_d, dev_dc = _measure(rep, basis, basis.vectors[s], +1)
            assert resid < ATOL, (basis.irrep.label, s, resid)
            assert dev_d < ATOL, (basis.irrep.label, s, dev_d)
            if dev_dc > 0.5:
                seen_conjugate_difference = True
    # the check can tell D from D*: at least one irrep of the case is not self-conjugate
    assert seen_conjugate_difference


@pytest.mark.parametrize("symbol, site, k", COMPLEX_CASES)
def test_a_pure_lattice_translation_reads_exp_minus_2pi_i_k_t_on_that_field(symbol, site, k):
    """D({E|t}) = exp(−2πi k·t) — Bradley & Cracknell (1972) eqn (3.4.3), on the field."""
    rep, bases = _bases(symbol, site, k)
    kf = [float(c) for c in k]
    for basis in bases:
        psi = basis.vectors[0, 0]
        for axis in range(3):
            if kf[axis] == 0:
                continue
            want = np.exp(-2j * np.pi * kf[axis])
            assert abs(_translation_eigenvalue(rep, psi, +1, axis) - want) < ATOL
            assert abs(_translation_eigenvalue(rep, psi, -1, axis) - np.conj(want)) < ATOL


@pytest.mark.parametrize("symbol, site, k", COMPLEX_CASES)
def test_the_exp_minus_recipe_relabels_the_irrep_or_leaves_every_irrep(symbol, site, k):
    """The negative arm on the SIGN: Σ ψ exp(−2πi k·R) is D*, or no irrep at all.

    Which of the two happens depends on the orbit: with one atom per primitive cell
    (P6 2b splits into two one-atom G_k orbits) the field stays in the span and reads
    D* — a clean relabel; with complex return phases *within* the orbit (kagome 3g,
    P6₃/mmc 2c) it leaves the span, which is a field that breaks the symmetry it is
    labelled with.  Either way the recipe field never reads D on a non-self-conjugate
    irrep.
    """
    rep, bases = _bases(symbol, site, k)
    caught = 0
    for basis in bases:
        self_conjugate = np.allclose(basis.irrep.characters,
                                     np.conj(basis.irrep.characters), atol=1e-8)
        for s in range(basis.multiplicity):
            resid, dev_d, dev_dc = _measure(rep, basis, basis.vectors[s], -1)
            if self_conjugate and resid < ATOL:
                continue                              # D = D*: the sign is invisible here
            assert resid > 0.5 or dev_d > 0.5, (basis.irrep.label, s, resid, dev_d)
            caught += 1
    assert caught >= 2


@pytest.mark.parametrize("symbol, site, k", COMPLEX_CASES)
def test_a_conjugated_basis_vector_is_caught_exactly_where_it_can_be(symbol, site, k):
    """The negative arm on the VECTORS: ψ̄ with the right sign fails the field check.

    It passes only where ψ̄ happens to lie in the D-isotypic subspace — a basis set of
    a self-conjugate irrep, or one copy of a repeated irrep whose conjugate is another
    copy.  That set is computed independently by projection, and the two must agree:
    the check fails on every row physics lets it fail on, and on no other.
    """
    rep, bases = _bases(symbol, site, k)
    metric = np.kron(np.eye(rep.n_atoms), rep.metric)
    any_caught = False
    for basis in bases:
        d, order = basis.irrep.dimension, rep.little.order
        projector = np.einsum("g,gab->ab", np.conj(basis.irrep.characters),
                              rep.matrices) * d / order
        for s in range(basis.multiplicity):
            conj_psi = np.conj(basis.vectors[s])
            flat = conj_psi.reshape(d, -1)
            weight = [float(np.real(np.vdot(projector @ v, metric @ (projector @ v)))
                            / np.real(np.vdot(v, metric @ v))) for v in flat]
            in_span = min(weight) > 1 - 1e-9
            resid, dev_d, _ = _measure(rep, basis, conj_psi, +1)
            passes = resid < ATOL and dev_d < ATOL
            assert passes == in_span, (basis.irrep.label, s, weight, resid, dev_d)
            any_caught |= not passes
    assert any_caught


@pytest.mark.parametrize("symbol, site, k", REAL_CASES)
def test_at_the_zone_boundary_both_signs_pass_and_the_translation_reads_minus_one(symbol, site, k):
    """Positive arm: where 2k ∈ L* the two exponents are the same field."""
    rep, bases = _bases(symbol, site, k)
    assert rep.little.has_minus_k
    axis = next(i for i, c in enumerate(k) if c != 0)
    for basis in bases:
        for s in range(basis.multiplicity):
            for sign in (+1, -1):
                resid, dev_d, dev_dc = _measure(rep, basis, basis.vectors[s], sign)
                assert resid < ATOL and dev_d < ATOL and dev_dc < ATOL
        assert abs(_translation_eigenvalue(rep, basis.vectors[0, 0], +1, axis) + 1) < ATOL


# --------------------------------------------------------------------------
# the oracle that knows no convention: spglib's MSG identification
# --------------------------------------------------------------------------

def _hexagonal_rows(c=1.6):
    return np.array([[1.0, 0.0, 0.0], [-0.5, np.sqrt(3) / 2, 0.0], [0.0, 0.0, c]])


def _msg_operation_count(rep, psi, sign, amplitude=np.exp(0.37j)):
    """spglib's operation count for the real field 2·Re(C ψ exp(sign·2πi k·R)).

    A second, non-magnetic species on a general-position orbit of the parent pins
    the supercell's nuclear symmetry to exactly the parent group; without it a sparse
    synthetic structure (one layer of atoms) carries accidental mirrors that P6 lacks.
    """
    rows = _hexagonal_rows()
    atoms, n = _supercell(rep.positions, rep.little.k)
    inert, _ = _supercell(M.orbit_positions(rep.spacegroup, (0.11, 0.23, 0.31)), rep.little.k)
    field = _field(atoms, psi, rep.little.k, sign).reshape(-1, 3)
    moments = np.vstack([2 * (amplitude * field).real,        # crystal-axis components
                         np.zeros((len(inert), 3))])
    dataset = spglib.get_magnetic_symmetry_dataset(
        (rows * n[:, None],
         np.array([x / n for (x, _, _) in atoms] + [x / n for (x, _, _) in inert]),
         [1] * len(atoms) + [2] * len(inert), moments @ rows),  # m_cart = Aᵀ·m
        symprec=1e-4, mag_symprec=1e-3)
    assert dataset is not None
    return len(dataset.rotations)


def _predicted_count(rep, basis, k):
    """Operations of the isotropy group of a generic single 1-D-irrep field, per supercell.

    (g, t, θ) with θ·exp(−2πi k·t)·D(g) = 1 over the little group, the supercell's
    parent translations and θ = ±1.  The set of unit phases is closed under
    conjugation, so the count is the same in either convention.
    """
    atoms, n = _supercell(rep.positions, k)
    kf = np.array([float(c) for c in k])
    count = 0
    for g in range(rep.little.order):
        d = complex(basis.irrep_matrices[g][0, 0])
        for t in itertools.product(*(range(int(m)) for m in n)):
            for theta in (1, -1):
                if abs(theta * np.exp(-2j * np.pi * kf @ np.array(t, float)) * d - 1) < 1e-9:
                    count += 1
    return count


@pytest.mark.parametrize("symbol, site, k", COMPLEX_CASES)
def test_spglib_gives_the_plus_field_its_full_isotropy_group_and_the_recipe_field_less_or_equal(
        symbol, site, k):
    """A sign-free external check.

    For a one-dimensional irrep every little-group operation survives in the isotropy
    group with a compensating translation or time reversal, so spglib must find exactly
    the predicted count on the field built with exp(+2πi k·R).  The recipe field is
    either the same structure relabelled (equal count) or a mixture of two irreps
    (strictly fewer operations); it is never more symmetric.  Where the count drops it
    drops by the order of the lost point operations, and it must drop on at least one
    irrep of the case unless every recipe field is a relabel.
    """
    rep, bases = _bases(symbol, site, k)
    one_dimensional = [b for b in bases if b.irrep.dimension == 1]
    assert one_dimensional
    drops = 0
    for basis in one_dimensional:
        for s in range(basis.multiplicity):
            psi = basis.vectors[s, 0]
            plus = _msg_operation_count(rep, psi, +1)
            recipe = _msg_operation_count(rep, psi, -1)
            assert plus == _predicted_count(rep, basis, k), (basis.irrep.label, s, plus)
            assert recipe <= plus, (basis.irrep.label, s, plus, recipe)
            drops += recipe < plus
    # on the kagome and P6₃/mmc cases the recipe field is a mixture and loses the
    # 3-fold; on P6 2b it is a relabel and loses nothing — both outcomes are pinned
    expected_drop = symbol != "P 6"
    assert (drops > 0) == expected_drop, (symbol, drops)


# --------------------------------------------------------------------------
# the text the caller reads
# --------------------------------------------------------------------------

def test_the_pairing_sentence_names_the_wave_the_vectors_are_coefficients_of():
    """``IrrepBasis.pairing`` is the recipe a caller follows; it must carry the sign
    the vectors were built with, and say what FullProf's S_kj is in terms of them."""
    rep, bases = _bases("P 6/m m m", (0.5, 0.0, 0.5), (THIRD, THIRD, 0))
    text = bases[0].pairing
    assert "exp(+2*pi*i*k.R)" in text, text
    assert "exp(-2*pi*i*k.R)" not in text.split("FullProf")[0], text
    assert "S_kj = conj(sum_l C_l psi_lj)" in text, text


def test_the_module_docstring_states_the_same_wave_and_no_longer_calls_the_vectors_s_kj():
    """The module docstring carries the recipe too (the 2k ≢ 0 bullet and the
    References entry): it must print the + exponent on ψ, and must not say the
    vectors *are* FullProf's S_kj."""
    doc = " ".join(M.__doc__.split())
    assert "Σ_l C_l·ψ_lj·e^{+2πi k·R} + c.c." in doc
    assert "Σ C·ψ_j·e^{+2πi k·R} + c.c." in doc
    assert "ψ_j·e^{−2πi k·R}" not in doc
    assert "these vectors are the S_kj" not in doc
    assert "S_kj = conj(Σ_l C_l·ψ_lj)" in doc
