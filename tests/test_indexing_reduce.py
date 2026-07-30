"""WP-1020 — reduction, Bravais determination, dedup, and ambiguity.

The two property tests here are the WP's acceptance criteria: Niggli reduction
must be **idempotent** and **unimodular-invariant** on hypothesis-generated cells,
because every downstream comparison (dedup, ambiguity, "is this the parent in a
different setting") is stated in terms of the reduced form.  If reduction is not
canonical, none of those questions is well posed.

The rest are about refusals: symmetry that appears only at a loose tolerance is
reported ambiguous rather than claimed, and a derivative lattice that explains the
data as well as the parent is reported as a partner with the reflections that would
break the tie.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from pxrdref.crystallography.lattice import cell_volume
from pxrdref.crystallography.symmetry import generate_reflections
from pxrdref.indexing.ambiguity import (
    MAX_AMBIGUITY_INDEX,
    ambiguity_partners,
    derivative_cells,
    hnf_matrices,
    transform_cell,
)
from pxrdref.indexing.qspace import af_from_cell
from pxrdref.indexing.reduce import (
    BRAVAIS_OBLIQUITIES,
    CELL_EQUALITY_CHI2,
    SYSTEM_RANK,
    bravais_screen,
    cell_from_vectors,
    conventional_cell,
    lattice_vectors,
    reduce_cell,
    same_lattice,
)
from pxrdref.schemas.indexing import q_esd_of_two_theta

LAM = 1.5405929

lengths = st.floats(min_value=3.0, max_value=25.0, allow_nan=False)
angles = st.floats(min_value=65.0, max_value=115.0, allow_nan=False)


def _valid(cell) -> bool:
    """Is this parameter set a real lattice?  Angle triples are not free."""
    try:
        return float(cell_volume(*cell)) > 1.0
    except (ValueError, np.linalg.LinAlgError):
        return False


def _unimodular(rng: np.random.Generator, n: int = 4) -> np.ndarray:
    """A random integer matrix with |det| = 1, as a product of shears."""
    m = np.eye(3, dtype=np.int64)
    for _ in range(n):
        i, j = rng.choice(3, size=2, replace=False)
        e = np.eye(3, dtype=np.int64)
        e[i, j] = int(rng.integers(-2, 3))
        m = m @ e
    return m


# ----------------------------------------------------------------------
# Reduction is canonical
# ----------------------------------------------------------------------
@settings(max_examples=60, deadline=None,
          suppress_health_check=[HealthCheck.filter_too_much])
@given(lengths, lengths, lengths, angles, angles, angles)
def test_niggli_reduction_is_idempotent(a, b, c, al, be, ga):
    """``niggli(niggli(C)) == niggli(C)`` — reduction reaches a fixed point."""
    cell = (a, b, c, al, be, ga)
    assume(_valid(cell))
    once = reduce_cell(cell)
    twice = reduce_cell(once.cell)
    assert np.allclose(twice.cell, once.cell, atol=1e-6)
    assert np.allclose(reduce_cell(twice.cell).cell, once.cell, atol=1e-6)


@settings(max_examples=40, deadline=None,
          suppress_health_check=[HealthCheck.filter_too_much])
@given(lengths, lengths, lengths, angles, angles, angles,
       st.integers(min_value=0, max_value=2 ** 32 - 1))
def test_niggli_reduction_is_unimodular_invariant(a, b, c, al, be, ga, seed):
    """A change of basis is not a change of lattice.

    This is what makes every downstream question well posed: dedup asks whether
    two candidates reduce to the same cell, and ambiguity asks about the ones that
    *do not*.  If reduction depended on the setting, both would be noise.
    """
    cell = (a, b, c, al, be, ga)
    assume(_valid(cell))
    rng = np.random.default_rng(seed)
    t = _unimodular(rng)
    assume(abs(round(float(np.linalg.det(t)))) == 1)
    other = transform_cell(cell, t)
    assume(_valid(other))

    want = reduce_cell(cell).cell
    got = reduce_cell(other).cell
    assert np.allclose(got, want, atol=1e-4), f"{cell} vs {other}: {got} != {want}"


def test_already_reduced_is_gemmis_predicate_and_not_a_fixed_point_test():
    """A caveat worth pinning, because the field invites the wrong reading.

    ``already_reduced`` is gemmi's own ``is_niggli``, and on floating-point input
    it can be False for a cell whose reduction changes nothing: measured on
    (3, 3, 3, 65°, 65°, 65°), where the reduced parameters carry ~1e-15 noise the
    predicate's tolerance does not absorb.  Idempotence is therefore asserted on
    the parameters, never on this flag.
    """
    cell = (3.0, 3.0, 3.0, 65.0, 65.0, 65.0)
    once = reduce_cell(cell)
    twice = reduce_cell(once.cell)
    assert np.allclose(twice.cell, once.cell, atol=1e-9)
    assert twice.already_reduced is False


def test_delaunay_reduction_is_available_and_distinct():
    """Both reductions exist and are the dependency's, not ours."""
    cell = (8.875, 16.408, 7.137, 90.0, 93.84, 90.0)
    niggli = reduce_cell(cell, kind="niggli")
    delaunay = reduce_cell(cell, kind="delaunay")
    assert niggli.kind == "niggli" and delaunay.kind == "delaunay"
    assert float(cell_volume(*niggli.cell)) == pytest.approx(
        float(cell_volume(*cell)), rel=1e-9)
    assert float(cell_volume(*delaunay.cell)) == pytest.approx(
        float(cell_volume(*cell)), rel=1e-9)
    with pytest.raises(ValueError, match="niggli"):
        reduce_cell(cell, kind="buerger")


def test_lattice_vectors_round_trip():
    cell = (7.0, 8.0, 9.0, 85.0, 95.0, 100.0)
    assert np.allclose(cell_from_vectors(lattice_vectors(cell)), cell, rtol=1e-12)


# ----------------------------------------------------------------------
# Bravais: two opinions, swept
# ----------------------------------------------------------------------
def test_high_symmetry_is_stable_across_the_sweep():
    screen = bravais_screen((4.1566,) * 3 + (90.0,) * 3, cell_esd=1e-4)
    assert screen.system == "cubic"
    assert not screen.ambiguous
    assert not screen.methods_disagree
    assert set(screen.by_obliquity.values()) == {"cubic"}


def test_pseudosymmetry_is_reported_ambiguous_not_claimed():
    """A 1 % tetragonal distortion looks cubic to a loose obliquity and not to a
    tight one.  The answer is the *stable* one, plus a flag — the same refusal
    ``direction="both"`` makes for a sequential trajectory."""
    screen = bravais_screen((4.1566, 4.1566, 4.20, 90.0, 90.0, 90.0),
                            cell_esd=1e-3)
    assert screen.system == "tetragonal"
    assert screen.system_loosest == "cubic"
    assert screen.ambiguous
    assert SYSTEM_RANK[screen.system_loosest] > SYSTEM_RANK[screen.system]


def test_symmetry_is_monotone_in_the_tolerance():
    """Loosening a tolerance can only *add* symmetry — the property that makes
    "stable across the sweep" equal to "the tightest tolerance's answer"."""
    for cell in ((4.1566, 4.1566, 4.20, 90.0, 90.0, 90.0),
                 (7.0, 7.05, 9.0, 90.0, 90.2, 90.0),
                 (5.0, 5.0, 5.0, 89.5, 90.0, 90.0)):
        screen = bravais_screen(cell, cell_esd=1e-3)
        ranks = [SYSTEM_RANK[screen.by_obliquity[t]]
                 for t in sorted(BRAVAIS_OBLIQUITIES)]
        assert ranks == sorted(ranks), f"{cell}: {screen.by_obliquity}"


def test_conventional_cell_recovers_a_centred_lattice():
    """The piece a reduced cell cannot give: a primitive bcc cell *is* cubic I.

    An engine that finds the primitive rhombohedral-looking cell must report the
    conventional one, or the answer looks like a different lattice from the one in
    every database.
    """
    prim = (3.6, 3.6, 3.6, 109.4712206, 109.4712206, 109.4712206)
    conv, centring, symbol = conventional_cell(prim)
    assert centring == "I"
    assert symbol.startswith("Im-3m")
    assert conv[0] == pytest.approx(conv[1]) == pytest.approx(conv[2])
    assert conv[3] == pytest.approx(90.0, abs=1e-6)
    # the conventional cell has twice the volume — two lattice points
    assert float(cell_volume(*conv)) == pytest.approx(
        2.0 * float(cell_volume(*prim)), rel=1e-6)


# ----------------------------------------------------------------------
# Dedup
# ----------------------------------------------------------------------
def test_same_lattice_sees_through_a_setting_change():
    cell = (7.0, 8.0, 9.0, 85.0, 95.0, 100.0)
    other = transform_cell(cell, np.array([[1, 1, 0], [0, 1, 0], [0, 0, 1]]))
    equal, chi2 = same_lattice(af_from_cell(cell), af_from_cell(other))
    assert equal
    assert np.isnan(chi2)          # the covariance-free fallback ran


def test_same_lattice_separates_genuinely_different_cells():
    a = af_from_cell((7.0, 8.0, 9.0, 85.0, 95.0, 100.0))
    b = af_from_cell((7.0, 8.0, 9.3, 85.0, 95.0, 100.0))
    equal, _chi2 = same_lattice(a, b)
    assert not equal


def test_cell_equality_respects_the_measured_precision():
    """The reason dedup is a χ² test and not a percentage.

    The *same* pair of cells is one lattice at laboratory precision and two at
    synchrotron precision — which a fixed percentage cannot express, and which is
    the whole point of carrying per-line σ this far.
    """
    a = af_from_cell((7.0, 8.0, 9.0, 90.0, 90.0, 90.0))
    b = af_from_cell((7.0005, 8.0, 9.0, 90.0, 90.0, 90.0))
    lab = np.diag(np.full(6, (2e-5) ** 2))
    synchrotron = np.diag(np.full(6, (2e-8) ** 2))

    same_lab, chi2_lab = same_lattice(a, b, cov_a=lab, cov_b=lab)
    same_sync, chi2_sync = same_lattice(a, b, cov_a=synchrotron,
                                        cov_b=synchrotron)
    assert same_lab and chi2_lab <= CELL_EQUALITY_CHI2
    assert not same_sync and chi2_sync > CELL_EQUALITY_CHI2


# ----------------------------------------------------------------------
# Ambiguity
# ----------------------------------------------------------------------
@pytest.mark.parametrize("index,count", [(2, 7), (3, 13), (4, 35)])
def test_hnf_enumeration_counts(index, count):
    """7, 13, 35 — the closed sets.  A count mismatch is how an enumeration bug
    announces itself instead of silently dropping a partner."""
    ms = hnf_matrices(index)
    assert len(ms) == count
    assert all(round(float(np.linalg.det(m))) == index for m in ms)
    # Hermite normal form is canonical, so no matrix repeats
    assert len({m.tobytes() for m in ms}) == count


def test_hnf_rejects_a_nonpositive_index():
    with pytest.raises(ValueError):
        hnf_matrices(0)


def test_transform_cell_scales_the_volume_by_the_index():
    cell = (7.0, 8.0, 9.0, 85.0, 95.0, 100.0)
    for index in (2, 3, 4):
        for h in hnf_matrices(index):
            child = transform_cell(cell, h)
            assert float(cell_volume(*child)) == pytest.approx(
                index * float(cell_volume(*cell)), rel=1e-9)


def test_derivative_cells_drop_the_parent_in_a_new_setting():
    """A setting change is dedup's business, not ambiguity's — so a derivative
    that reduces to the parent must never be offered as a partner."""
    cell = (7.0, 8.0, 9.0, 85.0, 95.0, 100.0)
    parent = af_from_cell(cell)
    for _index, _h, child in derivative_cells(cell, max_index=3):
        equal, _ = same_lattice(parent, af_from_cell(child))
        assert not equal


def test_ambiguity_partners_are_reported_with_a_way_to_break_the_tie():
    """A supercell explains every observed line, so it cannot be excluded by the
    positions alone — which is exactly what must be *reported*.

    The entry earns its place through ``discriminating_reflections``: the lines the
    partner predicts and the parent does not, lowest angle first, which is what a
    caller goes and looks for.
    """
    cell = (4.1566,) * 3 + (90.0,) * 3
    refl = generate_reflections("P m -3 m", cell, LAM, 90.0)
    q = np.sort(1.0 / np.asarray(refl.d) ** 2)
    tt = np.degrees(2.0 * np.arcsin(LAM * np.sqrt(q) / 2.0))
    esd = q_esd_of_two_theta(tt, np.full_like(tt, 0.01), LAM)

    partners = ambiguity_partners(cell, "cubic", "P", q, esd, LAM, 90.0,
                                  max_index=2)
    assert partners, "a doubled cell indexes every line and must be reported"
    assert all(p.index == 2 for p in partners)
    assert all(p.volume > float(cell_volume(*cell)) for p in partners)
    with_refl = [p for p in partners if p.discriminating_reflections]
    assert with_refl, "no partner said what would break the tie"
    p = with_refl[0]
    assert len(p.discriminating_reflections) == len(p.discriminating_two_theta)
    assert all(0.0 < t <= 90.0 for t in p.discriminating_two_theta)
    assert p.transformation and abs(round(float(np.linalg.det(
        np.array(p.transformation))))) == p.index


def test_ambiguity_index_is_fenced():
    """Index 2-4 is a fence, recorded rather than attempted: a high-index partner
    is more likely a numerical coincidence than a geometrical one."""
    assert MAX_AMBIGUITY_INDEX == 4
    cells = derivative_cells((5.0, 6.0, 7.0, 90.0, 90.0, 90.0))
    assert cells and max(index for index, _h, _c in cells) == MAX_AMBIGUITY_INDEX
