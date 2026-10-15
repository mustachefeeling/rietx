"""WP-1932 — two candidates compared across a reduction boundary.

Niggli reduction is a canonical form with decision boundaries, and two
descriptions of one lattice either side of one reduce to different sides.
``equal_reduced`` then compared the two reduced forms and called one lattice
two (#834: 4 784 comparisons on the bethanechol benchmark, 8 on the LaB6
acceptance searches).  The test now asks, of a pair it calls distinct, b's
other descriptions in Selling's form (Andrews, Bernstein & Sauter 2019, *Acta
Cryst.* A75, 115 and 593), and decides each with the same χ².

Arms: the logged splits must join (acceptance), with the pre-WP-1932 test
splitting each one (so a revert fails them); constructed pairs either side of
every Niggli boundary kind must join; two lattices near a boundary must stay
two (the positive arm of "distinct"); and every pair the old test joined is
answered exactly as before.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from rietx.indexing import reduce as R
from rietx.indexing.qspace import af_from_cell, gstar_from_af
from rietx.indexing.reduce import (
    CELL_EQUALITY_CHI2,
    af_map,
    equal_reduced,
    equal_reduced_many,
    reduce_cell,
    reduced_af,
    reduced_covariance,
    reduction,
    same_lattice,
)

PAIRS = json.loads((Path(__file__).parent / "data" / "wp1932_boundary_pairs.json")
                   .read_text(encoding="utf-8"))


def _arrays(p):
    return (np.array(p["red_a"]), np.array(p["red_b"]),
            np.array(p["cov_a"]), np.array(p["cov_b"]))


def _cov_of_cell_esd(cell, esd):
    """A..F covariance from independent cell esds (Å, °), central differences."""
    cell = np.asarray(cell, dtype=np.float64)
    jac = np.empty((6, 6))
    for k in range(6):
        h = 1e-6 * abs(cell[k])
        up, dn = cell.copy(), cell.copy()
        up[k] += h
        dn[k] -= h
        jac[:, k] = (af_from_cell(tuple(up)) - af_from_cell(tuple(dn))) / (2 * h)
    return jac @ np.diag(np.asarray(esd, dtype=np.float64) ** 2) @ jac.T


def _relabel(cell, m):
    """The same lattice in the basis m·(a, b, c), as cell parameters."""
    from rietx.indexing.reduce import cell_from_vectors, lattice_vectors
    return cell_from_vectors(np.asarray(m, dtype=np.float64) @ lattice_vectors(cell))


def _as_dedup_compares(cell_a, cell_b, esd):
    """Two candidates' reduced A..F and reduced-frame covariances, as dedup
    holds them."""
    out = []
    for cell in (cell_a, cell_b):
        af = af_from_cell(tuple(cell))
        red, t = reduction(af)
        out.append((red, reduced_covariance(_cov_of_cell_esd(cell, esd), t)))
    return out


# ----------------------------------------------------------------------
# Acceptance: the splits #834 counted are one lattice
# ----------------------------------------------------------------------
@pytest.mark.parametrize("p", PAIRS["lab6"], ids=lambda p: p["boundary"][:12])
def test_the_lab6_splits_are_one_lattice(p):
    """The acceptance arm: the 8 LaB6 comparisons (tetragonal candidates of the
    cubic cell, a three-way edge tie) that the reduced forms alone split.
    The first assert is the witness: before WP-1932 each was two lattices."""
    red_a, red_b, cov_a, cov_b = _arrays(p)
    old_same, old_chi2 = R._equal_as_given(red_a, red_b, cov_a, cov_b)
    assert not old_same and old_chi2 > CELL_EQUALITY_CHI2
    same, chi2 = equal_reduced(red_a, red_b, cov_a=cov_a, cov_b=cov_b)
    assert same and chi2 <= CELL_EQUALITY_CHI2
    assert chi2 == pytest.approx(p["oracle_chi2"], abs=0.05) or chi2 < p["oracle_chi2"]


@pytest.mark.parametrize("p", PAIRS["bethanechol"], ids=lambda p: p["boundary"][:24])
def test_the_bethanechol_splits_are_one_lattice(p):
    """Two of each boundary kind #834 found (a sign at g4/g5/g6 = 0, a
    reduction step, g1 = g2, g2 = g3), the one that needs two Selling steps on
    one side, and the published lattice's own split (γ 93.89° against 86.17°,
    χ² 261 before)."""
    red_a, red_b, cov_a, cov_b = _arrays(p)
    assert not R._equal_as_given(red_a, red_b, cov_a, cov_b)[0]
    same, chi2 = equal_reduced(red_a, red_b, cov_a=cov_a, cov_b=cov_b)
    assert same and chi2 <= p["oracle_chi2"] + 1e-6


def test_without_the_selling_images_the_splits_come_back(monkeypatch):
    """The revert check: with the boundary search switched off, every logged
    split is two lattices again, so the acceptance arm is not vacuous."""
    monkeypatch.setattr(R, "_equal_across_boundaries", lambda *a, **k: None)
    for p in PAIRS["lab6"] + PAIRS["bethanechol"]:
        red_a, red_b, cov_a, cov_b = _arrays(p)
        assert not equal_reduced(red_a, red_b, cov_a=cov_a, cov_b=cov_b)[0]
        assert not equal_reduced_many(red_a, [red_b], cov_a=cov_a, covs_b=[cov_b])[0][0]


# ----------------------------------------------------------------------
# Positive arm of "distinct": two lattices stay two
# ----------------------------------------------------------------------
@pytest.mark.parametrize("p", PAIRS["distinct"], ids=lambda p: f"oracle {p['oracle_best_chi2']:.0f}")
def test_two_lattices_near_a_boundary_stay_two(p):
    """Real bethanechol pairs whose sorted Selling scalars pass the gate, so
    the images are searched, and that no unimodular map within |m_ij| ≤ 3
    joins under the χ² test.  Each must stay distinct."""
    red_a, red_b, cov_a, cov_b = _arrays(p)
    assert bool(R._selling_gate(R._gate_inputs(red_a, cov_a), R._gate_inputs(red_b, cov_b)))
    same, chi2 = equal_reduced(red_a, red_b, cov_a=cov_a, cov_b=cov_b)
    assert not same and chi2 > CELL_EQUALITY_CHI2


ESD = [2e-5, 2e-5, 2e-5, 2e-3, 2e-3, 2e-3]           # Å ×3, ° ×3
GAM = float(np.degrees(np.arccos(-4.0 / 12.0)))      # 2ab cos γ = −a² at a = 4, b = 6
# (name, cell either side of a Niggli boundary, the other side): one lattice
# each, a hair apart in the parameter that crosses
BOUNDARY_PAIRS = [
    ("g1=g2 (a ≈ b, α ≠ β)",
     (5.0, 5.00004, 7.0, 95.0, 105.0, 100.0), (5.00004, 5.0, 7.0, 95.0, 105.0, 100.0)),
    ("g2=g3 (b ≈ c, β ≠ γ)",
     (4.0, 6.0, 6.00004, 95.0, 100.0, 105.0), (4.0, 6.00004, 6.0, 95.0, 100.0, 105.0)),
    ("g6=0 (γ ≈ 90°, type I against II)",
     (5.0, 6.0, 7.0, 95.0, 100.0, 90.002), (5.0, 6.0, 7.0, 95.0, 100.0, 89.998)),
    ("g4=0 (α ≈ 90°)",
     (5.0, 6.0, 7.0, 90.002, 100.0, 95.0), (5.0, 6.0, 7.0, 89.998, 100.0, 95.0)),
    ("|g6|=g1 (a face diagonal as long as a)",
     (4.0, 6.0, 7.5, 95.0, 100.0, GAM - 0.002), (4.0, 6.0, 7.5, 95.0, 100.0, GAM + 0.002)),
]


@pytest.mark.parametrize("name, cell_a, cell_b", BOUNDARY_PAIRS, ids=[b[0] for b in BOUNDARY_PAIRS])
def test_one_lattice_either_side_of_each_boundary_is_one_lattice(name, cell_a, cell_b):
    """A pair either side of each Niggli boundary kind, at esds of 2e-5 Å and
    2e-3°: the reduced forms land on two sides and differ by orders of
    magnitude more than their esds (the witness), and the test joins them."""
    (red_a, cov_a), (red_b, cov_b) = _as_dedup_compares(cell_a, cell_b, ESD)
    old_same, old_chi2 = R._equal_as_given(red_a, red_b, cov_a, cov_b)
    assert not old_same and old_chi2 > 1e3
    same, chi2 = equal_reduced(red_a, red_b, cov_a=cov_a, cov_b=cov_b)
    assert same and chi2 < 10.0
    assert same_lattice(af_from_cell(cell_a), af_from_cell(cell_b),
                        cov_a=_cov_of_cell_esd(cell_a, ESD),
                        cov_b=_cov_of_cell_esd(cell_b, ESD))[0]


@pytest.mark.parametrize("name, cell_a, cell_b, moved", [
    ("g1=g2, α moved 0.1° (50 esd)", (5.0, 5.00004, 7.0, 95.0, 105.0, 100.0),
     (5.00004, 5.0, 7.0, 95.1, 105.0, 100.0), None),
    ("g6=0, c moved 0.01 Å (500 esd)", (5.0, 6.0, 7.0, 95.0, 100.0, 90.002),
     (5.0, 6.0, 7.01, 95.0, 100.0, 89.998), None),
    ("|g6|=g1, b moved 0.003 Å (150 esd)", (4.0, 6.0, 7.5, 95.0, 100.0, GAM - 0.002),
     (4.0, 6.003, 7.5, 95.0, 100.0, GAM + 0.002), None),
    ("a sublattice of index 2", (5.0, 6.0, 7.0, 95.0, 100.0, 105.0),
     (10.0, 6.0, 7.0, 95.0, 100.0, 105.0), None),
])
def test_two_lattices_either_side_of_a_boundary_stay_two(name, cell_a, cell_b, moved):
    """The same boundaries with one parameter moved by 50-500 esds, and an
    index-2 sublattice: distinct before, distinct after."""
    (red_a, cov_a), (red_b, cov_b) = _as_dedup_compares(cell_a, cell_b, ESD)
    assert not equal_reduced(red_a, red_b, cov_a=cov_a, cov_b=cov_b)[0]


def test_without_covariances_the_rule_joins_across_a_boundary_and_no_further():
    """The relative fallback crosses boundaries too: γ 90.002° against 89.998°
    is one lattice, γ 90.002° against 89.0° is two."""
    a = reduced_af(af_from_cell((5.0, 6.0, 7.0, 95.0, 100.0, 90.002)))
    b = reduced_af(af_from_cell((5.0, 6.0, 7.0, 95.0, 100.0, 89.998)))
    c = reduced_af(af_from_cell((5.0, 6.0, 7.0, 95.0, 100.0, 89.0)))
    assert not R._equal_as_given(a, b, None, None)[0]
    same, chi2 = equal_reduced(a, b)
    assert same and np.isnan(chi2)
    assert not equal_reduced(a, c)[0]


def test_the_797_reduction_and_its_exact_image_are_at_distance_zero():
    """#797's cell: the reduced vector and the exact image of the input under
    the reduction's change of basis are one point (WP-1923), so the χ² of the
    pair is zero to rounding under any covariance."""
    cell = (3.0, 11.0, 14.197202585325392, 65.0, 65.0, 65.0)
    af = af_from_cell(cell)
    red, t = reduction(af)
    image = R._af_map(reduce_cell(cell).change_of_basis) @ af
    cov = np.diag((1e-7 * np.abs(red)) ** 2)
    same, chi2 = equal_reduced(red, image, cov_a=cov, cov_b=cov)
    assert same and chi2 < 1e-6


# ----------------------------------------------------------------------
# Nothing the old test joined moves, and the stacked form is the pair's own
# ----------------------------------------------------------------------
@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.integers(0, 2**31 - 1))
def test_a_pair_the_old_test_joins_is_answered_as_before(seed):
    rng = np.random.default_rng(seed)
    cell = (rng.uniform(3, 9), rng.uniform(3, 9), rng.uniform(3, 9),
            rng.uniform(80, 100), rng.uniform(80, 100), rng.uniform(80, 100))
    af = af_from_cell(cell)
    red = reduced_af(af)
    root = rng.standard_normal((6, 6)) * 1e-5 * np.abs(red).max()
    cov = root @ root.T
    other = red + rng.multivariate_normal(np.zeros(6), cov) * 0.5
    before = R._equal_as_given(red, other, cov, cov)
    if before[0]:
        assert equal_reduced(red, other, cov_a=cov, cov_b=cov) == before


def test_the_stacked_form_answers_each_pair_as_the_pair_form_does(monkeypatch):
    """Every fixture pair, stacked against all the others' b sides, gives the
    pair's own answer, joined or not, and the machine check still holds.  A
    LAPACK that rounds a stack differently is a platform fact: dedup keeps its
    per-pair loop there, so this skips as ``test_indexing_engines`` does."""
    monkeypatch.setattr(R, "_STACKED_PINV", None)
    if not R.stacked_pinv_exact():
        pytest.skip("this LAPACK answers a matrix differently inside a stack, "
                    "so dedup keeps its per-pair loop")
    pairs = [_arrays(p) for p in PAIRS["lab6"] + PAIRS["bethanechol"] + PAIRS["distinct"]]
    for red_a, _rb, cov_a, _cb in pairs:
        reds = [p[1] for p in pairs]
        covs = [p[3] for p in pairs]
        stacked = equal_reduced_many(red_a, reds, cov_a=cov_a, covs_b=covs)
        assert stacked == [equal_reduced(red_a, r, cov_a=cov_a, cov_b=c)
                           for r, c in zip(reds, covs)]


def test_the_image_test_inverts_sigma_as_the_pair_test_does(monkeypatch):
    """Σ is again a sum of two rank-deficient covariances, so the image test
    takes ``_psd_pinv`` at ``CELL_PINV_RCOND`` and no inverse of its own: numpy's
    hermitian ``pinv`` keeps a flat direction's negative rounding-level
    eigenvalue with its sign, and a negative χ² passes ``<= CELL_EQUALITY_CHI2``.
    Every logged split still joins through it, so the spy sees the call."""
    calls = []
    real = R._psd_pinv

    def spy(a, rcond):
        calls.append((np.shape(a), rcond))
        return real(a, rcond)

    def no_pinv(*_a, **_k):
        raise AssertionError("the image test inverted Σ with numpy's own pinv")

    monkeypatch.setattr(R, "_psd_pinv", spy)
    monkeypatch.setattr(np.linalg, "pinv", no_pinv)
    for p in PAIRS["bethanechol"] + PAIRS["lab6"]:
        red_a, red_b, cov_a, cov_b = _arrays(p)
        calls.clear()
        same, _chi2 = equal_reduced(red_a, red_b, cov_a=cov_a, cov_b=cov_b)
        assert same
        stacks = [c for c in calls if len(c[0]) == 3]
        assert stacks and all(rcond == R.CELL_PINV_RCOND for _s, rcond in stacks)


# ----------------------------------------------------------------------
# The pieces, from the papers
# ----------------------------------------------------------------------
def test_the_selling_step_is_the_printed_one():
    """Andrews, Bernstein & Sauter (2019), A75, 115, § 4: on s1 the step gives
    (−s1, s2 + s1, s5 + s1, s4 − s1, s3 + s1, s6 + s1)."""
    g = np.linalg.inv(gstar_from_af(af_from_cell((5.0, 6.0, 7.0, 80.0, 75.0, 70.0))))
    s = R._selling_scalars(R._SELLING_START, g)
    after = R._selling_scalars(R._selling_step(R._SELLING_START, 0), g)
    np.testing.assert_allclose(after, [-s[0], s[1] + s[0], s[4] + s[0], s[3] - s[0],
                                       s[2] + s[0], s[5] + s[0]], rtol=1e-12)


@settings(max_examples=60, deadline=None)
@given(st.integers(0, 2**31 - 1))
def test_selling_reduction_is_obtuse_unimodular_and_setting_free(seed):
    """Every scalar ≤ 0 after reduction, the basis unimodular, and the sorted
    scalars (the gate's invariant) the same in any setting of the lattice."""
    rng = np.random.default_rng(seed)
    cell = (rng.uniform(3, 12), rng.uniform(3, 12), rng.uniform(3, 12),
            rng.uniform(70, 110), rng.uniform(70, 110), rng.uniform(70, 110))
    try:
        af = af_from_cell(cell)
    except ValueError:
        return
    m = np.eye(3, dtype=np.int64)
    for _ in range(4):
        i, j = rng.choice(3, size=2, replace=False)
        e = np.eye(3, dtype=np.int64)
        e[i, j] = int(rng.integers(-2, 3))
        m = m @ e
    forms = [R._selling_form(np.ascontiguousarray(v).tobytes()) for v in (af, af_map(m) @ af)]
    for f in forms:
        assert np.all(f.s <= 1e-9 * f.scale)
        assert abs(round(np.linalg.det(f.v4[:3].astype(float)))) == 1
    np.testing.assert_allclose(forms[0].s[forms[0].order], forms[1].s[forms[1].order],
                               rtol=1e-9, atol=1e-9 * forms[0].scale)


def test_the_stacked_af_map_is_af_map():
    rng = np.random.default_rng(1932)
    ns = []
    while len(ns) < 200:
        m = rng.integers(-3, 4, (3, 3))
        if abs(round(np.linalg.det(m))) == 1:
            ns.append(m)
    for t, n in zip(R._af_maps(np.stack(ns)), ns):
        np.testing.assert_array_equal(t, af_map(n))


def test_a_metric_that_is_no_lattice_keeps_the_old_answer():
    """``stacked_pinv_exact``'s random witnesses are not lattices; the search
    declines them rather than raising."""
    red = np.array([0.01, 0.02, 0.03, 0.2, 0.2, 0.2])
    assert R._selling_form(red.tobytes()) is None
    same, chi2 = equal_reduced(red, red * 1.5)
    assert not same and np.isnan(chi2)
    assert not R._equal_as_given(red, red * 1.5, None, None)[0]
