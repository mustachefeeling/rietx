"""WP-1418 M-8, K1b: ``search_kvector``, its ranking under Boole's bound, and its warnings.

The family is K1a's (``test_indexing_kvector.py``): synthetic Pnma (5.74 × 7.70 ×
5.54 Å, LaMnO₃-like), CW neutrons at λ 2.41 Å over 10-140°, a 0.12° radius and a
nuclear FWHM of 0.30°.  The fast tests search the 1/8 or 1/16 grid; the 1/64 tests
are marked slow.  The validation arms (H1-H7, re-measured under the bound for the
D68 rework) are measured outside the suite and quoted in the WP handover; what is
pinned here is the composition, the windows, the crowding row and the held pick.

Interpretation, written before the runs:

* The result carries no ``k`` and no ``best``, and ``best_or_none()`` is
  ``None`` on every call with ``"position_only"`` in ``withheld``.  A planted
  k with ten clean peaks still ranks first, clears ``alpha`` and fires
  nothing; four random peaks clear nothing and ``K_SEARCH_AT_CHANCE`` fires.
* Every row's adjusted p is Boole's arithmetic on its own P, and a row clears
  exactly when its score reaches the bound's threshold.
* The windows sort out exactly the peaks strictly inside them, and the same
  windows reach the scorer, so ``score_kgrid`` never refuses a peak.
* The crowding p is the one-sided KS p against the exact allowed-range
  distribution; a coarse sampled distribution (the V4″ form) agrees with it.
* The likeliest misuse (Rule 4): the residue of a profile misfit, picked with
  main's ``residual_peak_indices`` and searched, reads ``None`` with its
  reason, a crowding warning and an adjusted p on every row; the old head
  (257e34d66) returned a k on the asymmetry list.  A clean planted list is
  ``None`` for the position-only reason alone, so ``None`` is not "no k".
"""

from __future__ import annotations

import dataclasses
from fractions import Fraction as F

import numpy as np
import pytest
from scipy.stats import ksone

from rietx.crystallography.satellites import lattice_two_theta, satellite_d_spacings
from rietx.indexing import ksearch
from rietx.indexing.engines import Budget
from rietx.indexing.fom import RESOLUTION_FWHM
from rietx.indexing.ksearch import KSearchResult, search_kvector
from rietx.indexing.kvector import (
    KGridRow,
    KParent,
    KPeaks,
    kgrid_bound,
    kgrid_positions,
    kgrid_strata,
    kvector_equivalents,
    score_kgrid,
)

CELL = (5.74, 7.70, 5.54, 90.0, 90.0, 90.0)
LAMBDA = 2.41
RADIUS = 0.12
FWHM = 0.30
PNMA = KParent("P n m a", CELL, LAMBDA, 10.0, 140.0)
K_LINE16 = (F(0), F(5, 16), F(0))
K_LINE64 = (F(0), F(18, 64), F(0))


def _two_theta(d):
    return np.degrees(2.0 * np.arcsin(LAMBDA / (2.0 * np.asarray(d))))


def _nuclear(parent):
    return lattice_two_theta(parent.group, parent.cell, parent.wavelength,
                             parent.two_theta_max, parent.two_theta_min)


def _satellites(parent, k):
    d = satellite_d_spacings(parent.space_group, parent.cell, parent.wavelength,
                             parent.two_theta_max, [k], parent.two_theta_min)[0]
    tt = np.unique(_two_theta(d))
    return tt[(tt >= parent.two_theta_min) & (tt <= parent.two_theta_max)]


def _planted(parent, k, n, seed, *, sigma=0.02, off=FWHM):
    """The n lowest-angle satellites of k more than ``off`` from every nuclear
    line (one FWHM by default, so the window sort keeps them), with noise."""
    rng = np.random.default_rng(seed)
    tt = _satellites(parent, k)
    nuc = _nuclear(parent)
    keep = tt[np.min(np.abs(tt[:, None] - nuc[None, :]), axis=1) > off + 4 * sigma][:n]
    return np.sort(keep + rng.normal(0.0, sigma, len(keep)))


def _random_off_nuclear(parent, n, seed, *, off=FWHM):
    rng = np.random.default_rng(seed)
    nuc = _nuclear(parent)
    out = []
    while len(out) < n:
        x = rng.uniform(parent.two_theta_min, parent.two_theta_max)
        if np.min(np.abs(nuc - x)) > off:
            out.append(x)
    return np.sort(out)


def _codes(res):
    return {d.code for d in res.diagnostics}


@pytest.fixture(scope="module")
def grid16():
    return kgrid_positions(PNMA, kgrid_strata("P n m a", denominator=16))


@pytest.fixture(scope="module")
def planted16(grid16):
    return search_kvector(_planted(PNMA, K_LINE16, 10, 0), PNMA, RADIUS, strata=grid16,
                          nuclear_fwhm=FWHM)


@pytest.fixture(scope="module")
def random16(grid16):
    return search_kvector(_random_off_nuclear(PNMA, 4, 0), PNMA, RADIUS, strata=grid16,
                          nuclear_fwhm=FWHM)


# ============================================================ no singleton

def test_the_result_names_no_k_and_no_best(planted16):
    for name in ("k", "best", "top", "cell"):
        assert not hasattr(planted16, name), name
    assert not hasattr(KSearchResult, "k")
    assert "k = (0, 5/16, 0)" in repr(planted16)
    assert "best_or_none: None (position_only)" in repr(planted16)


def test_a_planted_k_ranks_first_and_clears_but_is_not_picked(planted16, random16):
    """The held pick: ``None`` for the position-only reason alone, never "no k"."""
    top = planted16.rows[0]
    assert ksearch._steps_apart("P n m a", top.equivalents, K_LINE16, 16) == 0
    assert planted16.p_adjusted[0] < planted16.alpha == 0.01
    assert planted16.n_cleared >= 1 and planted16.margin > 0
    assert planted16.best_or_none() is None
    assert planted16.withheld == ("position_only",)
    assert "confirmed by refinement" in planted16.withheld_reasons[0]
    assert not _codes(planted16) & {"K_SEARCH_AT_CHANCE", "K_SEARCH_FEW_PEAKS",
                                    "K_SEARCH_CUT", "K_SEARCH_CROWDED"}
    # four random peaks: rows kept as hypotheses, nothing clears, the warning says so
    assert random16.rows and random16.n_cleared == 0 and random16.best_or_none() is None
    assert "K_SEARCH_AT_CHANCE" in _codes(random16)
    at_chance = next(d for d in random16.diagnostics if d.code == "K_SEARCH_AT_CHANCE")
    assert at_chance.level == "warning" and at_chance.suggestion
    assert at_chance.value == pytest.approx(random16.margin)
    assert "Boole's bound" in at_chance.message


def test_the_pick_opens_only_when_nothing_is_withheld(planted16):
    """``best_or_none`` reads ``withheld`` alone: the one place the rule holds."""
    opened = dataclasses.replace(planted16, withheld=())
    assert opened.best_or_none() is planted16.rows[0]
    assert dataclasses.replace(planted16, withheld=("search_cut",)).best_or_none() is None


# ============================================================ the bound

def test_each_adjusted_p_is_booles_arithmetic_on_its_own_p(planted16, grid16):
    res = planted16
    pk = res.peaks
    grid = score_kgrid(pk, PNMA, grid16, radius=RADIUS, band_deg=5.0, exclude=res.exclude)
    bound = kgrid_bound(grid, alpha=0.01, weighting="flat")
    assert (res.bound.n_total, res.bound.thresholds) == (bound.n_total, bound.thresholds)
    assert res.weighting == "flat" and len(res.p_adjusted) == len(res.rows)
    n = bound.n_total
    for row, p in zip(res.rows, res.p_adjusted):
        assert p == pytest.approx(min(1.0, row.p_value * n), rel=1e-12)
        assert (p <= res.alpha) == (row.score >= res.threshold(row) - 1e-12)
    assert res.n_cleared == sum(r.score >= res.threshold(r) for r in res.rows)


def test_rows_are_ranked_by_adjusted_p_then_score_and_ties_keep_the_strata_order(planted16):
    keys = [(p, -r.score) for r, p in zip(planted16.rows, planted16.p_adjusted)]
    assert keys == sorted(keys)
    order = {name: i for i, name in enumerate(planted16.strata_searched)}
    for (a, pa), (b, pb) in zip(zip(planted16.rows, planted16.p_adjusted),
                                zip(planted16.rows[1:], planted16.p_adjusted[1:])):
        if pa == pb and a.score == b.score:
            assert order[a.stratum] <= order[b.stratum]
    assert len(planted16.rows) == sum(
        s.n_points for s in kgrid_strata("P n m a", denominator=16))


def test_stratum_weighting_and_alpha_are_the_callers(grid16):
    pk = _planted(PNMA, K_LINE16, 8, 2)
    res = search_kvector(pk, PNMA, RADIUS, strata=grid16, nuclear_fwhm=FWHM,
                         weighting="stratum", alpha=0.001)
    assert res.weighting == "stratum" and res.alpha == 0.001
    s = len(res.bound.strata)
    n = dict(zip(res.bound.strata, res.bound.n_scored))
    for row, p in zip(res.rows, res.p_adjusted):
        assert p == pytest.approx(min(1.0, row.p_value * s * n[row.stratum]), rel=1e-12)
    for bad in (0.0, 1.0, -0.1):
        with pytest.raises(ValueError, match="alpha"):
            search_kvector(pk, PNMA, RADIUS, strata=grid16, alpha=bad)
    with pytest.raises(ValueError, match="weighting"):
        search_kvector(pk, PNMA, RADIUS, strata=grid16, weighting="even")


# ============================================================ the windows

def test_the_windows_are_one_local_fwhm_and_sort_the_peaks_off(grid16):
    nuc = _nuclear(PNMA)
    clean = _planted(PNMA, K_LINE16, 8, 3)
    inside = np.array([nuc[5] + 0.5 * FWHM, nuc[40] - 0.9 * FWHM])   # within one FWHM
    pk = np.sort(np.concatenate([clean, inside]))
    res = search_kvector(pk, PNMA, RADIUS, strata=grid16, nuclear_fwhm=FWHM)
    assert res.exclude_source == "nuclear_fwhm"
    assert res.exclude == tuple((float(c), RESOLUTION_FWHM * FWHM) for c in nuc)
    dropped = [float(pk[i]) for i in res.sorted_out]
    assert sorted(dropped) == pytest.approx(sorted(inside))
    assert [float(pk[i]) for i in res.kept] == list(res.peaks.two_theta)
    assert len(res.peaks) == len(clean)
    assert all(d >= 1.0 for d in res.peak_distance_fwhm)
    assert "sorted out (2 here)" in res.coverage and "few grid steps from Γ" in res.coverage
    # a width per line: a function of 2θ sets each window
    caglioti = lambda tt: 0.2 + 0.002 * np.asarray(tt)  # noqa: E731
    res = search_kvector(clean, PNMA, RADIUS, strata=grid16, nuclear_fwhm=caglioti)
    assert [w for _, w in res.exclude] == pytest.approx(list(caglioti(nuc)))


def test_without_a_nuclear_width_the_census_or_the_radius_sets_the_windows(grid16):
    pos = tuple(_planted(PNMA, K_LINE16, 6, 5))
    census = search_kvector(KPeaks(two_theta=pos, fwhm=(0.25,) * len(pos)), PNMA,
                            strata=grid16)
    assert census.radius_source == census.exclude_source == "residual census"
    assert [w for _, w in census.exclude] == pytest.approx([0.25] * len(census.exclude))
    assert census.peak_distance_fwhm is not None and census.crowding.n_near is not None
    bare = search_kvector(pos, PNMA, RADIUS, strata=grid16)
    assert bare.exclude_source == "radius"
    assert {w for _, w in bare.exclude} == {RADIUS}
    assert bare.peak_distance_fwhm is None and bare.crowding.n_near is None
    assert "± the match radius" in bare.coverage
    own = search_kvector(pos, PNMA, RADIUS, strata=grid16, exclude=[(30.0, 0.5)])
    assert own.exclude_source == "caller" and own.exclude == ((30.0, 0.5),)
    none = search_kvector(pos, PNMA, RADIUS, strata=grid16, exclude=())
    assert none.exclude == () and none.crowding is None and none.sorted_out == ()


def test_the_radius_says_where_it_came_from():
    pos = tuple(_planted(PNMA, K_LINE16, 6, 5))
    strata = kgrid_strata("P n m a", denominator=4)
    assert search_kvector(pos, PNMA, 0.1, strata=strata).radius_source == "caller"
    broad = KPeaks(two_theta=pos, fwhm=(0.48,) * len(pos))
    res = search_kvector(broad, PNMA, nuclear_fwhm=0.30, strata=strata)
    assert res.radius_source == "residual census" and res.radius == pytest.approx(0.4 * 0.48)
    sharp = KPeaks(two_theta=pos, fwhm=(0.10,) * len(pos))
    res = search_kvector(sharp, PNMA, nuclear_fwhm=0.30, strata=strata)
    assert res.radius_source == "nuclear lines" and res.radius == pytest.approx(0.4 * 0.30)
    with pytest.raises(ValueError, match="no width"):
        search_kvector(pos, PNMA, strata=strata)
    with pytest.raises(ValueError, match="positive"):
        search_kvector(pos, PNMA, -0.1, strata=strata)
    with pytest.raises(TypeError, match="cannot say which line"):
        search_kvector(pos, PNMA, nuclear_fwhm=[0.2, 0.3, 0.4], strata=strata)


# ============================================================ the crowding row

def _sampled_crowding_p(pk, centres, half, lo, hi, step=0.0005):
    """The V4″ form, written out independently: the null distance distribution
    sampled on a fine 2θ grid, then the one-sided KS p from ``ksone``."""
    xx = np.arange(lo, hi, step)
    dd = np.min(np.abs(xx[:, None] - centres[None, :]) / half[None, :], axis=1)
    dnull = np.sort(dd[dd >= 1.0])
    d = np.min(np.abs(np.asarray(pk)[:, None] - centres[None, :]) / half[None, :], axis=1)
    u = np.sort(np.searchsorted(dnull, d, side="right") / len(dnull))
    n = len(u)
    dplus = np.max(np.arange(1, n + 1) / n - u)
    return float(ksone.sf(dplus, n)) if dplus > 0 else 1.0


def test_the_crowding_p_is_the_exact_form_of_the_sampled_one(grid16):
    nuc = _nuclear(PNMA)
    rng = np.random.default_rng(11)
    near = np.sort(nuc[rng.choice(len(nuc), 30, replace=False)]
                   + rng.choice([-1, 1], 30) * FWHM * rng.uniform(1.05, 1.6, 30))
    near = near[(near > 10.0) & (near < 140.0)]
    for pk in (near, _planted(PNMA, K_LINE16, 10, 0)):
        res = search_kvector(pk, PNMA, RADIUS, strata=grid16, nuclear_fwhm=FWHM)
        assert len(res.peaks) >= 10
        half = np.array([w for _, w in res.exclude])
        ref = _sampled_crowding_p(res.peaks.two_theta, nuc, half, 10.0, 140.0)
        assert np.log10(res.crowding.p_value) == pytest.approx(np.log10(ref), abs=0.01)
        assert res.crowding.n_peaks == len(res.peaks)
    crowded = search_kvector(near, PNMA, RADIUS, strata=grid16, nuclear_fwhm=FWHM)
    assert crowded.crowding.p_value < 0.01 and "K_SEARCH_CROWDED" in _codes(crowded)
    warn = next(d for d in crowded.diagnostics if d.code == "K_SEARCH_CROWDED")
    assert warn.level == "warning" and "few grid steps from Γ" in warn.message
    assert warn.value == crowded.crowding.p_value


# ============================================================ the budget

class _FlipAfter:
    """A cancel token that turns true on its (n+1)-th reading."""

    def __init__(self, n):
        self.n = n

    def __bool__(self):
        self.n -= 1
        return self.n < 0


def test_a_cut_search_abstains_with_its_own_reason_and_a_caller_restriction_does_not():
    strata = kgrid_strata("P n m a", denominator=8)
    names = tuple(s.name for s in strata)
    pk = _planted(PNMA, (F(0), F(3, 8), F(0)), 6, 6)
    cut = search_kvector(pk, PNMA, RADIUS, budget=Budget(3600.0, cancel=_FlipAfter(3)),
                         strata=strata, nuclear_fwhm=FWHM)
    assert cut.preset == "custom" and cut.budget_expired
    assert cut.strata_searched == names[:3] and cut.strata_left == names[3:]
    assert {r.stratum for r in cut.rows} <= set(names[:3])
    assert cut.withheld == ("position_only", "search_cut") and cut.best_or_none() is None
    assert "K_SEARCH_CUT" in _codes(cut)
    warn = next(d for d in cut.diagnostics if d.code == "K_SEARCH_CUT")
    assert warn.level == "warning" and 'budget="full"' in warn.suggestion
    assert names[3] in warn.message
    # the bound covers exactly the k scored
    assert cut.bound.n_total == len(cut.rows)
    restricted = search_kvector(pk, PNMA, RADIUS, budget="full", strata=strata[:3],
                                nuclear_fwhm=FWHM)
    assert restricted.withheld == ("position_only",) and "K_SEARCH_CUT" not in _codes(restricted)
    assert [(r.k, r.score) for r in restricted.rows] == [(r.k, r.score) for r in cut.rows]
    full = search_kvector(pk, PNMA, RADIUS, budget="full", strata=strata, nuclear_fwhm=FWHM)
    assert full.preset == "full" and full.strata_left == () and full.budget_seconds is None
    quick = search_kvector(pk, PNMA, RADIUS, strata=strata, nuclear_fwhm=FWHM)
    assert quick.preset == "quick" and quick.budget_seconds == 120.0
    with pytest.raises(ValueError, match="unknown preset"):
        search_kvector(pk, PNMA, RADIUS, budget="slow", strata=strata)
    with pytest.raises(RuntimeError, match="nothing was"):
        search_kvector(pk, PNMA, RADIUS, budget=Budget(3600.0, cancel=_FlipAfter(0)),
                       strata=strata)


def test_a_budget_inside_a_stratum_is_passed_to_the_scorer(monkeypatch):
    """The cut lands inside a stratum (#1732's block read), and is carried."""
    from rietx.indexing import kvector
    monkeypatch.setattr(kvector, "_CHUNK", 7)
    strata = kgrid_strata("P n m a", denominator=8)
    big = max(strata, key=lambda s: s.n_points)
    before = sum(-(-s.n_points // 7) for s in strata[:[s.name for s in strata].index(big.name)])
    pk = _planted(PNMA, (F(0), F(3, 8), F(0)), 6, 6)
    cut = search_kvector(pk, PNMA, RADIUS, budget=Budget(3600.0, cancel=_FlipAfter(before + 2)),
                         strata=strata, nuclear_fwhm=FWHM)
    assert cut.strata_cut == ((big.name, 14, big.n_points),)
    assert "search_cut" in cut.withheld and "K_SEARCH_CUT" in _codes(cut)


# ================================================================ few peaks

def test_few_peaks_fires_only_when_nothing_clears_and_the_top_matches_every_peak(grid16):
    pk = _planted(PNMA, K_LINE16, 10, 7)
    ten = search_kvector(pk, PNMA, RADIUS, strata=grid16, nuclear_fwhm=FWHM)
    assert ten.n_cleared and "K_SEARCH_FEW_PEAKS" not in _codes(ten)
    two = search_kvector(pk[:2], PNMA, RADIUS, strata=grid16, nuclear_fwhm=FWHM)
    assert two.rows[0].n_matched == 2 and two.n_cleared == 0
    assert {"K_SEARCH_AT_CHANCE", "K_SEARCH_FEW_PEAKS"} <= _codes(two)
    few = next(d for d in two.diagnostics if d.code == "K_SEARCH_FEW_PEAKS")
    assert few.level == "warning" and few.value == 2.0
    assert "not evidence" not in few.message and "neither finds a k nor rules one out" in \
        few.message
    # at chance with an unmatched peak: the top does not match every peak, so silent
    rand = search_kvector(_random_off_nuclear(PNMA, 6, 1), PNMA, RADIUS, strata=grid16,
                          nuclear_fwhm=FWHM)
    if rand.n_cleared == 0 and rand.rows[0].n_matched < len(rand.peaks):
        assert "K_SEARCH_AT_CHANCE" in _codes(rand) and "K_SEARCH_FEW_PEAKS" not in _codes(rand)


def test_no_peaks_ranks_nothing_and_says_so():
    strata = kgrid_strata("P n m a", denominator=4)
    res = search_kvector([], PNMA, RADIUS, strata=strata)
    assert res.best_or_none() is None and res.n_cleared == 0 and res.crowding is None
    assert {"K_SEARCH_AT_CHANCE", "K_SEARCH_FEW_PEAKS"} <= _codes(res)


# ============================================================== the partner

def _row(k, score, stratum="general"):
    return KGridRow(k=k, stratum=stratum, score=score, p_value=10.0 ** -score, n_matched=0,
                    matched=(), unmatched=(), n_positions=0, space_group="P n m a")


def test_a_partner_that_also_clears_alpha_ties_and_one_that_does_not_is_silent():
    near = KParent("P n m a", (5.74, 7.70, 5.73, 90.0, 90.0, 90.0), LAMBDA, 10.0, 140.0)
    top_k = (F(15, 64), F(7, 64), F(24, 64))
    partners = kvector_equivalents(near, top_k, tol=ksearch.K_SEARCH_PARTNER_TOL)
    image = next(e.k for e in partners.rows if e.relation == "partner")
    beside = (image[0] + F(1, 64), image[1], image[2])
    own = (top_k[0] + F(1, 64), top_k[1], top_k[2])
    far = (F(1, 64), F(31, 64), F(3, 64))
    rows = (_row(top_k, 9.0), _row(own, 8.9), _row(far, 8.6), _row(beside, 8.5))
    clears = (1e-5, 2e-5, 3e-3, 5e-3)
    tie = ksearch._partner_tie(near, rows, clears, 0.01, partners, 64)
    assert tie is rows[3]
    assert ksearch._partner_tie(near, rows, clears[:3] + (0.02,), 0.01, partners, 64) is None
    # nothing ties a top that does not clear itself
    assert ksearch._partner_tie(near, rows, (0.5,) * 4, 0.01, partners, 64) is None
    ortho = KParent("P n m a", (5.74, 7.70, 6.40, 90.0, 90.0, 90.0), LAMBDA, 10.0, 140.0)
    none = kvector_equivalents(ortho, top_k, tol=ksearch.K_SEARCH_PARTNER_TOL)
    assert ksearch._partner_tie(ortho, rows, clears, 0.01, none, 64) is None


# =========================================== the likeliest misuse (Rule 4)
#
# Patterns are generated from seeds here; no data is vendored.  M1 is K1a's V4
# width misfit (Gaussian lines, data 0.33° against a 0.30° model); M2 is a
# pseudo-Voigt family on a Caglioti curve (0.30° at 10°, 0.90° at 140°, η 0.5)
# whose data carry a finite-axial-divergence asymmetry (Finger, Cox & Jephcoat
# 1994, rietx's ``fcj`` quadrature, S/L = H/L = 0.02) the model lacks.  The
# residue is picked with main's ``residual_peak_indices`` at 5σ, and the
# nuclear width passed is the model's.

_X = np.arange(10.0, 140.0 + 1e-9, 0.01)
_LN2 = np.log(2.0)
_A = np.array([[np.tan(np.radians(5.0)) ** 2, 1.0], [np.tan(np.radians(70.0)) ** 2, 1.0]])
_CAG_U, _CAG_W = np.linalg.solve(_A, [0.30 ** 2, 0.90 ** 2])


def _caglioti(tt):
    return np.sqrt(_CAG_U * np.tan(np.radians(np.asarray(tt, float) / 2.0)) ** 2 + _CAG_W)


def _pv(dx, f, eta=0.5):
    z = dx / f
    return (eta * (2.0 / (np.pi * f)) / (1.0 + 4.0 * z * z)
            + (1.0 - eta) * np.sqrt(4.0 * _LN2 / np.pi) / f * np.exp(-4.0 * _LN2 * z * z))


def _pv_height(f, eta=0.5):
    return eta * 2.0 / (np.pi * f) + (1.0 - eta) * np.sqrt(4.0 * _LN2 / np.pi) / f


def _gauss(fw, centres, heights):
    sg = fw / 2.3548200450309493
    y = np.full_like(_X, 100.0)
    for c, a in zip(centres, heights):
        m = np.abs(_X - c) < 8 * sg
        y[m] += a * np.exp(-0.5 * ((_X[m] - c) / sg) ** 2)
    return y


def _width_misfit(seed, counts):
    nuc = _nuclear(PNMA)
    rng = np.random.default_rng(seed)
    h = counts * np.exp(rng.normal(0.0, 0.8, len(nuc)))
    return rng.poisson(_gauss(0.33, nuc, h)).astype(float), _gauss(0.30, nuc, h)


def _asymmetry_misfit(seed, counts):
    from rietx.model.profiles.fcj import fcj_offsets_weights_batch
    nuc = _nuclear(PNMA)
    rng = np.random.default_rng(seed)
    h = counts * np.exp(rng.normal(0.0, 0.8, len(nuc)))
    f = _caglioti(nuc)
    areas = h / _pv_height(f)
    phi, om = fcj_offsets_weights_batch(np.asarray(nuc, float), 0.02, 0.02, 24)
    data = 100.0 + sum(a * (w[:, None] * _pv(_X[None, :] - p[:, None], ff)).sum(axis=0)
                       for a, ff, p, w in zip(areas, f, phi, om))
    model = 100.0 + sum(a * _pv(_X - c, ff) for a, c, ff in zip(areas, nuc, f))
    return rng.poisson(data).astype(float), model


def _zero_shift_mixture(seed, counts, k, height=1000.0, shift=0.02):
    """M2 with a zero shift the model lacks, plus k's ten lowest satellites."""
    nuc = _nuclear(PNMA)
    rng = np.random.default_rng(seed)
    h = counts * np.exp(rng.normal(0.0, 0.8, len(nuc)))
    f = _caglioti(nuc)
    areas = h / _pv_height(f)
    tt = _satellites(PNMA, k)
    sats = tt[np.min(np.abs(tt[:, None] - nuc[None, :]), axis=1) > RADIUS][:10]
    data = (100.0 + sum(a * _pv(_X - (c + shift), ff) for a, c, ff in zip(areas, nuc, f))
            + sum(height / _pv_height(ff) * _pv(_X - (c + shift), ff)
                  for c, ff in zip(sats, _caglioti(sats))))
    model = 100.0 + sum(a * _pv(_X - c, ff) for a, c, ff in zip(areas, nuc, f))
    return rng.poisson(data).astype(float), model


def _residual_picks(data, model):
    from rietx.report.layer0 import residual_peak_indices
    r = (data - model) / np.sqrt(np.maximum(data, 1.0))
    return _X[residual_peak_indices(r, min_peak_sigma=5.0)]


@pytest.mark.parametrize("make, width", [(_width_misfit, FWHM), (_asymmetry_misfit, _caglioti)],
                         ids=["width-misfit", "asymmetry-misfit"])
def test_misuse_a_misfit_residue_reads_none_with_its_reason_and_the_crowding_warning(
        grid16, make, width):
    """Arm 1.  Seed 0 at 20 000 counts.  On the asymmetry list the old head
    (257e34d66: shuffle null, ± radius) returned k = (5/16, 1/4, 1/8) from
    ``best_or_none()`` on this grid; on the width-misfit list it names
    nothing on the 1/64 grid either (V4″ p2, 0/40)."""
    pk = _residual_picks(*make(0, 20000))
    res = search_kvector(pk, PNMA, RADIUS, strata=grid16, nuclear_fwhm=width)
    assert res.best_or_none() is None and "position_only" in res.withheld
    assert res.sorted_out                                   # the shoulders inside a window
    assert res.crowding.p_value < res.alpha and "K_SEARCH_CROWDED" in _codes(res)
    assert len(res.p_adjusted) == len(res.rows) and all(0.0 <= p <= 1.0 for p in res.p_adjusted)


def test_misuse_a_clean_planted_list_is_none_for_the_position_only_reason_alone(planted16):
    """Arm 2, the positive arm: ``None`` read as "no k" is the held pick's own
    misuse, so the reason is the only one, and the planted k leads, clears and
    warns nothing."""
    assert planted16.best_or_none() is None and planted16.withheld == ("position_only",)
    assert ksearch._steps_apart("P n m a", planted16.rows[0].equivalents, K_LINE16, 16) == 0
    assert planted16.p_adjusted[0] < planted16.alpha
    assert "K_SEARCH_CROWDED" not in _codes(planted16)


@pytest.mark.slow
@pytest.mark.xdist_group("kvector-pnma64")
def test_misuse_a_mixture_through_mains_picker_is_characterised():
    """Arm 3 (characterisation, DESIGN Rule 2): real satellites of (0, 18/64, 0)
    at 1 000 counts plus a 0.02° zero shift at 5 000, seed 5, through main's
    picker.  ``rows[0]`` lies ≥ 4 grid steps from the planted k, clears alpha
    and fires no crowding warning: the reason the pick is held.  When a
    validating fit opens the pick, this call must return ``None`` or the
    planted k."""
    pk = _residual_picks(*_zero_shift_mixture(5, 5000, K_LINE64))
    res = search_kvector(pk, PNMA, RADIUS, nuclear_fwhm=_caglioti)
    steps = ksearch._steps_apart("P n m a", res.rows[0].equivalents, K_LINE64, 64)
    assert steps >= 4 and res.p_adjusted[0] < res.alpha
    assert "K_SEARCH_CROWDED" not in _codes(res)
    best = res.best_or_none()
    assert best is None or ksearch._steps_apart("P n m a", best.equivalents, K_LINE64, 64) == 0


# ================================================================ 1/64 grid

@pytest.mark.slow
@pytest.mark.xdist_group("kvector-pnma64")
def test_the_default_grid_ranks_k1as_planted_line_k_first():
    """K1a's V4 arm through the default search, under the bound."""
    res = search_kvector(_planted(PNMA, K_LINE64, 10, 0), PNMA, RADIUS, nuclear_fwhm=FWHM)
    assert res.grid_step == pytest.approx(1 / 64) and res.strata_left == ()
    assert ksearch._steps_apart("P n m a", res.rows[0].equivalents, K_LINE64, 64) == 0
    assert res.p_adjusted[0] < res.alpha and res.margin > 1.0
    assert res.bound.n_total == len(res.rows) and res.best_or_none() is None
