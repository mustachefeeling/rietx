"""WP-1418 M-8, K1b: ``search_kvector``, its gated verdict and its two warnings.

The family is K1a's (``test_indexing_kvector.py``): synthetic Pnma (5.74 × 7.70 ×
5.54 Å, LaMnO₃-like), CW neutrons at λ 2.41 Å over 10-140°, a 0.12° radius.  The
fast tests search the 1/8 or 1/16 grid; the one 1/64 test is marked slow.  The
validation arms (H1-H8, pre-registered) are measured outside the suite and
quoted in the WP handover; what is pinned here is the composition and the gate.

Interpretation, written before the runs:

* The result carries no ``k`` and no ``best``; ``best_or_none()`` returns the
  top row on a planted k with ten clean peaks and ``None`` on four random ones,
  where ``K_SEARCH_AT_CHANCE`` and ``K_SEARCH_FEW_PEAKS`` both fire.  Either
  half failing means the gate is wired wrong.
* The null over the strata searched one at a time equals K1a's null over all of
  them at once, sample for sample; a mismatch means the per-stratum composition
  is not the grid maximum.
* A partner image that scores within the margin of the top, away from the top's
  own class, makes ``best_or_none()`` ``None``; the same rows with the image
  scored low do not.
"""

from __future__ import annotations

import math
from fractions import Fraction as F

import numpy as np
import pytest

from rietx.crystallography.satellites import lattice_two_theta, satellite_d_spacings
from rietx.indexing import ksearch
from rietx.indexing.engines import Budget
from rietx.indexing.ksearch import (
    K_SEARCH_FLOOR_MEASURED,
    K_SEARCH_MARGIN_DECADES,
    KSearchResult,
    k_search_floor,
    search_kvector,
)
from rietx.indexing.kvector import (
    KGridRow,
    KParent,
    KPeaks,
    kgrid_null,
    kgrid_positions,
    kgrid_strata,
    kvector_equivalents,
)

CELL = (5.74, 7.70, 5.54, 90.0, 90.0, 90.0)
LAMBDA = 2.41
RADIUS = 0.12
PNMA = KParent("P n m a", CELL, LAMBDA, 10.0, 140.0)
K_LINE16 = (F(0), F(5, 16), F(0))
K_LINE64 = (F(0), F(18, 64), F(0))


def _two_theta(d):
    return np.degrees(2.0 * np.arcsin(LAMBDA / (2.0 * np.asarray(d))))


def _nuclear(parent):
    return lattice_two_theta(parent.group, parent.cell, parent.wavelength,
                             parent.two_theta_max, parent.two_theta_min)


def _planted(parent, k, n, seed, *, sigma=0.02, radius=RADIUS):
    """The n lowest-angle satellites of k off the nuclear windows, with noise."""
    rng = np.random.default_rng(seed)
    d = satellite_d_spacings(parent.space_group, parent.cell, parent.wavelength,
                             parent.two_theta_max, [k], parent.two_theta_min)[0]
    tt = np.unique(_two_theta(d))
    tt = tt[(tt >= parent.two_theta_min) & (tt <= parent.two_theta_max)]
    nuc = _nuclear(parent)
    off = tt[np.min(np.abs(tt[:, None] - nuc[None, :]), axis=1) > radius][:n]
    return np.sort(off + rng.normal(0.0, sigma, len(off)))


def _random_off_nuclear(parent, n, seed):
    rng = np.random.default_rng(seed)
    nuc = _nuclear(parent)
    out = []
    while len(out) < n:
        x = rng.uniform(parent.two_theta_min, parent.two_theta_max)
        if np.min(np.abs(nuc - x)) > RADIUS:
            out.append(x)
    return np.sort(out)


def _codes(res):
    return {d.code for d in res.diagnostics}


@pytest.fixture(scope="module")
def grid16():
    return kgrid_positions(PNMA, kgrid_strata("P n m a", denominator=16))


@pytest.fixture(scope="module")
def planted16(grid16):
    return search_kvector(_planted(PNMA, K_LINE16, 10, 0), PNMA, RADIUS, strata=grid16)


@pytest.fixture(scope="module")
def random16(grid16):
    return search_kvector(_random_off_nuclear(PNMA, 4, 0), PNMA, RADIUS, strata=grid16)


# ============================================================ no singleton

def test_the_result_names_no_k_and_no_best(planted16):
    for name in ("k", "best", "top", "cell"):
        assert not hasattr(planted16, name), name
    assert not hasattr(KSearchResult, "k")
    assert "k = (0, 5/16, 0)" in repr(planted16)


def test_a_planted_k_is_returned_and_random_peaks_are_not(planted16, random16):
    best = planted16.best_or_none()
    assert best is not None and best is planted16.rows[0]
    assert ksearch._steps_apart("P n m a", best.equivalents, K_LINE16, 16) == 0
    assert planted16.margin >= K_SEARCH_MARGIN_DECADES
    assert not _codes(planted16) & {"K_SEARCH_AT_CHANCE", "K_SEARCH_FEW_PEAKS"}
    # the random list keeps its rows: they are hypotheses, never withheld
    assert random16.rows and random16.best_or_none() is None
    assert {"K_SEARCH_AT_CHANCE", "K_SEARCH_FEW_PEAKS"} <= _codes(random16)
    at_chance = next(d for d in random16.diagnostics if d.code == "K_SEARCH_AT_CHANCE")
    assert at_chance.level == "warning" and at_chance.suggestion
    assert at_chance.value == pytest.approx(random16.margin)
    few = next(d for d in random16.diagnostics if d.code == "K_SEARCH_FEW_PEAKS")
    assert few.level == "warning" and few.value == 4.0 and random16.floor > 4


def test_the_gate_reads_the_margin_not_the_diagnostics(planted16):
    """Moving the margin past the score flips the verdict on the same rows."""
    shut = _replace(planted16, margin_decades=planted16.margin + 0.01)
    assert shut.best_or_none() is None
    opened = _replace(planted16, margin_decades=planted16.margin - 0.01)
    assert opened.best_or_none() is planted16.rows[0]


def _replace(res, **kw):
    import dataclasses
    return dataclasses.replace(res, **kw)


def test_rows_are_ranked_by_score_and_ties_keep_the_strata_order(planted16):
    scores = [r.score for r in planted16.rows]
    assert scores == sorted(scores, reverse=True)
    order = {name: i for i, name in enumerate(planted16.strata_searched)}
    for a, b in zip(planted16.rows, planted16.rows[1:]):
        if a.score == b.score:
            assert order[a.stratum] <= order[b.stratum]
    assert len(planted16.rows) == sum(
        s.n_points for s in kgrid_strata("P n m a", denominator=16))


# ================================================================ the null

def test_the_per_stratum_null_is_the_whole_grid_null(grid16):
    """Shuffles depend on the seed, N and the exclusions only, so per-stratum
    maxima combine to K1a's null over every stratum at once, sample for sample."""
    pk = _planted(PNMA, K_LINE16, 7, 3)
    res = search_kvector(pk, PNMA, RADIUS, strata=grid16, n_shuffles=20)
    whole = kgrid_null(pk, PNMA, grid16, radius=RADIUS, band_deg=5.0,
                       exclude=[(float(x), RADIUS) for x in _nuclear(PNMA)],
                       n_shuffles=20, percentile=99.0, seed=20261112)
    assert res.null.sample == whole.sample
    assert res.null_threshold == whole.threshold
    assert res.null.matched_at_max == whole.matched_at_max
    assert res.exclude == whole.exclude
    assert res.strata_searched == whole.strata_searched and res.strata_left == ()


def test_the_strata_or_the_positions_give_the_same_answer(grid16):
    pk = _planted(PNMA, K_LINE16, 8, 4)
    a = search_kvector(pk, PNMA, RADIUS, strata=grid16.strata, n_shuffles=10)
    b = search_kvector(pk, PNMA, RADIUS, strata=grid16, n_shuffles=10)
    assert [(r.k, r.score) for r in a.rows] == [(r.k, r.score) for r in b.rows]
    assert a.null.sample == b.null.sample


# =============================================================== the radius

def test_the_radius_says_where_it_came_from():
    pos = tuple(_planted(PNMA, K_LINE16, 6, 5))
    strata = kgrid_strata("P n m a", denominator=4)
    kw = dict(strata=strata, n_shuffles=3)
    assert search_kvector(pos, PNMA, 0.1, **kw).radius_source == "caller"
    broad = KPeaks(two_theta=pos, fwhm=(0.48,) * len(pos))
    res = search_kvector(broad, PNMA, nuclear_fwhm=0.30, **kw)
    assert res.radius_source == "residual census" and res.radius == pytest.approx(0.4 * 0.48)
    sharp = KPeaks(two_theta=pos, fwhm=(0.10,) * len(pos))
    res = search_kvector(sharp, PNMA, nuclear_fwhm=0.30, **kw)
    assert res.radius_source == "nuclear lines" and res.radius == pytest.approx(0.4 * 0.30)
    res = search_kvector(pos, PNMA, nuclear_fwhm=[0.2, 0.3, 0.4], **kw)
    assert res.radius_source == "nuclear lines" and res.radius == pytest.approx(0.12)
    # the null's exclusions follow the radius used
    assert all(w == pytest.approx(0.12) for _, w in res.exclude)
    with pytest.raises(ValueError, match="no width"):
        search_kvector(pos, PNMA, **kw)
    with pytest.raises(ValueError, match="positive"):
        search_kvector(pos, PNMA, -0.1, **kw)


# =============================================================== the budget

class _FlipAfter:
    """A cancel token that turns true on its (n+1)-th reading."""

    def __init__(self, n):
        self.n = n

    def __bool__(self):
        self.n -= 1
        return self.n < 0


def test_a_cut_budget_names_the_strata_left_and_its_null_covers_the_rest():
    strata = kgrid_strata("P n m a", denominator=8)
    names = tuple(s.name for s in strata)
    pk = _planted(PNMA, (F(0), F(3, 8), F(0)), 6, 6)
    cut = search_kvector(pk, PNMA, RADIUS, budget=Budget(3600.0, cancel=_FlipAfter(3)),
                         strata=strata, n_shuffles=5)
    assert cut.preset == "custom" and cut.budget_expired
    assert cut.strata_searched == names[:3] and cut.strata_left == names[3:]
    assert {r.stratum for r in cut.rows} <= set(names[:3])
    assert "left unsearched" in cut.coverage and "off this grid" in cut.coverage
    alone = kgrid_null(pk, PNMA, strata[:3], radius=RADIUS, band_deg=5.0,
                       exclude=cut.exclude, n_shuffles=5, percentile=99.0, seed=20261112)
    assert cut.null.sample == alone.sample
    full = search_kvector(pk, PNMA, RADIUS, budget="full", strata=strata, n_shuffles=5)
    assert full.preset == "full" and full.strata_left == () and full.budget_seconds is None
    quick = search_kvector(pk, PNMA, RADIUS, strata=strata, n_shuffles=5)
    assert quick.preset == "quick" and quick.budget_seconds == 120.0
    with pytest.raises(ValueError, match="unknown preset"):
        search_kvector(pk, PNMA, RADIUS, budget="slow", strata=strata)
    with pytest.raises(RuntimeError, match="nothing was searched"):
        search_kvector(pk, PNMA, RADIUS, budget=Budget(3600.0, cancel=_FlipAfter(0)),
                       strata=strata, n_shuffles=5)


# ================================================================ the floor

def test_the_floor_reads_the_measured_table_where_it_has_a_cell():
    assert K_SEARCH_FLOOR_MEASURED == {
        (0.12, 1, 1): (4, 6), (0.12, 1, 3): (6, 10), (0.12, 3, 3): (8, 10),
        (0.06, 1, 1): (4, 6), (0.06, 1, 3): (4, 8), (0.06, 3, 3): (6, 8),
    }
    for (r, top, searched), (clean, dirty) in K_SEARCH_FLOOR_MEASURED.items():
        assert k_search_floor(top, searched, contaminated=False, radius=r) == clean
        assert k_search_floor(top, searched, contaminated=True, radius=r) == dirty
    # the radius reads the nearer measured row, split at the geometric mean
    assert k_search_floor(3, 3, contaminated=False, radius=0.0848) == 6
    assert k_search_floor(3, 3, contaminated=False, radius=0.0849) == 8
    # a cell the table lacks takes the rule: a plane on the plane strata
    assert k_search_floor(2, 2, contaminated=False, radius=0.12) == 6
    assert k_search_floor(2, 2, contaminated=True, radius=0.12) == 8
    assert k_search_floor(0, 0, contaminated=False, radius=0.06) == 4
    # a hypothesis never needs fewer peaks than its own stratum's
    assert k_search_floor(3, 1, contaminated=False, radius=0.12) == 8


def test_few_peaks_fires_below_the_floor_and_not_at_it(grid16):
    pk = _planted(PNMA, K_LINE16, 10, 7)
    ten = search_kvector(pk, PNMA, RADIUS, strata=grid16, n_shuffles=10)
    assert ten.floor <= 10 and "K_SEARCH_FEW_PEAKS" not in _codes(ten)
    three = search_kvector(pk[:3], PNMA, RADIUS, strata=grid16, n_shuffles=10)
    assert three.rows and "K_SEARCH_FEW_PEAKS" in _codes(three)


def test_no_peaks_ranks_nothing_and_says_so():
    strata = kgrid_strata("P n m a", denominator=4)
    res = search_kvector([], PNMA, RADIUS, strata=strata, n_shuffles=3)
    assert res.best_or_none() is None
    assert {"K_SEARCH_AT_CHANCE", "K_SEARCH_FEW_PEAKS"} <= _codes(res)


# ============================================================== the partner

def _row(k, score, stratum="general"):
    return KGridRow(k=k, stratum=stratum, score=score, p_value=10.0 ** -score, n_matched=0,
                    matched=(), unmatched=(), n_positions=0, space_group="P n m a")


def test_a_partner_within_the_margin_ties_the_top_and_one_below_it_does_not():
    near = KParent("P n m a", (5.74, 7.70, 5.73, 90.0, 90.0, 90.0), LAMBDA, 10.0, 140.0)
    top_k = (F(15, 64), F(7, 64), F(24, 64))
    partners = kvector_equivalents(near, top_k, tol=ksearch.K_SEARCH_PARTNER_TOL)
    image = next(e.k for e in partners.rows if e.relation == "partner")
    beside = (image[0] + F(1, 64), image[1], image[2])
    own = (top_k[0] + F(1, 64), top_k[1], top_k[2])
    far = (F(1, 64), F(31, 64), F(3, 64))
    rows = (_row(top_k, 9.0), _row(own, 8.9), _row(far, 8.6), _row(beside, 8.5))
    tie = ksearch._partner_tie(near, rows, partners, K_SEARCH_MARGIN_DECADES, 64)
    assert tie is rows[3]
    low = rows[:3] + (_row(beside, 7.9),)
    assert ksearch._partner_tie(near, low, partners, K_SEARCH_MARGIN_DECADES, 64) is None
    # a clearly orthorhombic cell lists no partner, so nothing can tie
    ortho = KParent("P n m a", (5.74, 7.70, 6.40, 90.0, 90.0, 90.0), LAMBDA, 10.0, 140.0)
    none = kvector_equivalents(ortho, top_k, tol=ksearch.K_SEARCH_PARTNER_TOL)
    assert ksearch._partner_tie(ortho, rows, none, K_SEARCH_MARGIN_DECADES, 64) is None


def test_a_partner_tie_withholds_the_verdict(planted16):
    tied = _replace(planted16, partner_tie=planted16.rows[1])
    assert tied.margin >= K_SEARCH_MARGIN_DECADES and tied.best_or_none() is None


# ================================================================ 1/64 grid

@pytest.mark.slow
@pytest.mark.xdist_group("kvector-pnma64")
def test_the_default_grid_returns_k1as_planted_line_k():
    """K1a's V4 arm through the default search: same score and threshold."""
    res = search_kvector(_planted(PNMA, K_LINE64, 10, 0), PNMA, RADIUS)
    assert res.grid_step == pytest.approx(1 / 64) and res.strata_left == ()
    best = res.best_or_none()
    assert best is not None
    assert ksearch._steps_apart("P n m a", best.equivalents, K_LINE64, 64) == 0
    assert math.isclose(res.margin, best.score - res.null_threshold)
    assert res.margin > 3.0
