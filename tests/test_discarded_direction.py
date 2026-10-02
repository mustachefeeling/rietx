"""WP-1535 — a direction the covariance discards must not read as measured.

``pinv`` drops an eigenvalue under ``PINV_RCOND × λmax`` and the direction comes
back at zero variance, so a combination of columns the data cannot move reports
the variance of what it *could* move.  A pair of such columns is already a
``FLAT_DIRECTION``; a combination of three has no pairwise ρ to show for it.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.optimize.statistics import discarded_directions
from rietx.refine import _guard_diagnostics
from rietx.strategy.staged import (
    GuardFinding,
    GuardReport,
    check_discarded_directions,
)

pytestmark = pytest.mark.xdist_group("discarded-direction")


def _jac(n=400, seed=0):
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, 5))


def test_independent_columns_discard_nothing():
    n, touched = discarded_directions(_jac())
    assert n == 0 and len(touched) == 0


def test_a_sum_of_two_columns_is_a_combination_no_pair_shows():
    """c = a + b exactly: pairwise |ρ| is 0.71, the direction is not measured."""
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1]
    jj = j.T @ j
    rho = jj / np.sqrt(np.outer(np.diag(jj), np.diag(jj)))
    assert np.abs(rho[np.triu_indices(5, 1)]).max() < 0.9  # no FLAT_DIRECTION
    n, touched = discarded_directions(j)
    assert n == 1
    assert list(touched) == [0, 1, 4]


def test_a_column_the_direction_barely_loads_on_is_not_touched():
    """The bar is the reported variance: a 1e-9 loading adds ~1e-18/cut, far
    under what the kept directions say, so column 3 is not named."""
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1] + 1e-9 * j[:, 3]
    n, touched = discarded_directions(j)
    assert n == 1
    assert list(touched) == [0, 1, 4]


def test_the_touched_set_does_not_depend_on_a_columns_units():
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1]
    k = j * np.array([1.0, 1e6, 1.0, 1e-4, 1.0])
    assert list(discarded_directions(k)[1]) == [0, 1, 4]


def test_a_dead_column_is_not_this_findings_business():
    j = _jac()
    j[:, 2] = 0.0
    assert discarded_directions(j)[0] == 0


def test_a_pair_flat_direction_already_reported_adds_no_row():
    j = _jac()
    j[:, 4] = j[:, 0]
    free = [f"p{i}" for i in range(5)]
    flat = [GuardFinding.flat_direction("p0", "p4", 1.0)]
    assert check_discarded_directions(j, free, flat) == []
    (row,) = check_discarded_directions(j, free, [])
    assert row.code == "COVARIANCE_DIRECTION_DISCARDED"
    assert set(row.paths) == {"p0", "p4"}


def test_the_row_names_its_paths_and_the_diagnostic_carries_them():
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1]
    free = [f"phases.0.q{i}" for i in range(5)]
    findings = check_discarded_directions(j, free, [])
    assert [f.paths for f in findings] == [("phases.0.q0", "phases.0.q1",
                                            "phases.0.q4")]
    diags = _guard_diagnostics(GuardReport(discarded_directions=findings))
    (d,) = [d for d in diags if d.code == "COVARIANCE_DIRECTION_DISCARDED"]
    assert d.where == ["phases.0.q0", "phases.0.q1", "phases.0.q4"]
    assert d.level == "warning"
