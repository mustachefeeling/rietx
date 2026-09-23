"""ΔBIC is charged at the independent-observation count, N/f² (issue #270).

Schwarz's N counts independent observations, and a powder residual is serially
correlated: at raw N any χ² improvement outvotes the ln N penalty, and the
reporter's four ~49 500-channel synchrotron fits gave ΔBIC +36 to +211 for an
occupancy each fit's own (Bérar-Lelann inflated) esd put within 0.76-1.89σ of
zero.  ``effective_sample_size`` divides N by the squared inflation factor, the
count at which one parameter's ΔBIC is its t² at the inflated esd minus ln N_eff.

Every fixture here is synthetic: an AR(1) residual of 50 000 rows, whose
Bérar-Lelann factor the package measures itself, and one candidate column each
for a parameter within 1σ of zero and one the data needs.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from rietx.optimize.statistics import berar_lelann_factor, effective_sample_size
from rietx.report.layer2 import delta_bic, hamilton_justified
from rietx.strategy.suggest import Candidate, build_suggestion

N = 50_000
RHO = 0.95


@pytest.fixture(scope="module")
def correlated_residual() -> np.ndarray:
    rng = np.random.default_rng(270)
    e = rng.standard_normal(N)
    r = np.empty(N)
    r[0] = e[0]
    for i in range(1, N):
        r[i] = RHO * r[i - 1] + math.sqrt(1 - RHO ** 2) * e[i]
    return r


def _column_with_t(resid: np.ndarray, t_nominal: float, seed: int) -> np.ndarray:
    """A candidate column whose nominal (uninflated) t-ratio is ``t_nominal``.

    For one column j the Gauss-Newton gain is (jᵀr)²/(jᵀj) and the nominal
    t² is that gain over χ²_red, so j = a·r̂ + b·noise is solved for the
    target gain.
    """
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(len(resid))
    noise -= resid * (noise @ resid) / (resid @ resid)
    chi2_red = float(resid @ resid) / len(resid)
    target = t_nominal ** 2 * chi2_red
    rn = resid / np.linalg.norm(resid)
    nn = noise / np.linalg.norm(noise)
    # j = a·r̂ + n̂ with n̂ ⟂ r: gain = (a|r|)² / (a² + 1), so solve for a
    r2 = float(resid @ resid)
    a = math.sqrt(target / (r2 - target))
    return a * rn + nn


def _suggest(resid, column):
    jac = column[:, None]
    chi2_red = float(resid @ resid) / len(resid)
    return build_suggestion(
        jac, resid, [], [Candidate(path="phases.0.atoms.1.occ", index=0,
                                   dp_du=1.0)],
        chi2_red=chi2_red, esd_inflation=berar_lelann_factor(resid))


def test_the_fixture_is_as_correlated_as_the_issue_s_patterns(
        correlated_residual):
    f = berar_lelann_factor(correlated_residual)
    assert 5.0 < f < 12.0          # the issue's four fits: 7.1-10.2
    assert effective_sample_size(N, f) == pytest.approx(N / f ** 2)
    # white residuals are not left at N: the factor is conservative there too
    white = np.random.default_rng(1).standard_normal(N)
    assert effective_sample_size(N, berar_lelann_factor(white)) < N / 2
    assert effective_sample_size(N, None) == N


def test_a_parameter_within_one_sigma_is_not_decisive(correlated_residual):
    f = berar_lelann_factor(correlated_residual)
    # nominal t chosen so the *inflated* esd puts the value at 0.8σ
    column = _column_with_t(correlated_residual, 0.8 * f, seed=2)
    result = _suggest(correlated_residual, column)
    group = result.groups[0]
    assert result.n_effective == pytest.approx(N / f ** 2)
    # the defect: raw N blesses it decisively
    assert group.delta_bic_raw_n > 10.0
    # the fix: at N_eff it does not pay for itself
    assert group.delta_bic < 0.0
    assert "N_eff" in result.summary


def test_a_needed_parameter_is_still_decisive(correlated_residual):
    f = berar_lelann_factor(correlated_residual)
    column = _column_with_t(correlated_residual, 12.0 * f, seed=3)
    group = _suggest(correlated_residual, column).groups[0]
    assert group.delta_bic > 10.0
    assert group.delta_bic_raw_n > group.delta_bic


@pytest.mark.parametrize("t_inflated, needed", [(0.8, False), (12.0, True)])
def test_delta_bic_and_hamilton_agree_at_one_n(correlated_residual,
                                               t_inflated, needed):
    """Read off one N_eff, the two statistics give the same verdict — and at
    raw N both bless the 0.8σ parameter, which is the issue's table."""
    f = berar_lelann_factor(correlated_residual)
    chi2_r = float(correlated_residual @ correlated_residual)
    chi2_red = chi2_r / N
    gain = (t_inflated * f) ** 2 * chi2_red
    chi2_f = chi2_r - gain
    n_eff = effective_sample_size(N, f)
    bic = delta_bic(chi2_r, chi2_f, N, 1, n_effective=n_eff)
    ham = hamilton_justified(chi2_r, chi2_f, N, 0, 1, n_effective=n_eff)
    assert (bic > 0.0) is needed
    assert ham is needed
    # the raw-N forms are unchanged, and both bless even the 0.8σ one
    assert delta_bic(chi2_r, chi2_f, N, 1) > 0.0
    assert hamilton_justified(chi2_r, chi2_f, N, 0, 1)
    assert delta_bic(chi2_r, chi2_f, N, 1) == pytest.approx(
        N * math.log(chi2_r / chi2_f) - math.log(N))


def test_the_issue_s_four_verdicts_flip_at_n_over_f_squared():
    """The issue's published table, reproduced from its own numbers."""
    n = 49_493
    rows = [(36.2, 10.16, -5.72), (211.0, 7.13, -2.52),
            (71.1, 7.89, -5.36), (80.9, 8.59, -5.27)]
    for raw, f, expected in rows:
        log_ratio = (raw + math.log(n)) / n
        chi2_f = 1.0
        chi2_r = math.exp(log_ratio)
        assert delta_bic(chi2_r, chi2_f, n, 1) == pytest.approx(raw)
        eff = delta_bic(chi2_r, chi2_f, n, 1,
                        n_effective=effective_sample_size(n, f))
        assert eff == pytest.approx(expected, abs=0.05)
