"""The rigid-body misfit check, ``RIGID_BODY_MISFIT`` (a follow-up to WP-1805).

Positive arm: a pattern made with WP-1803's C₆Br body, fitted with the same
body carrying its C–Br bond 0.3 Å too long, must fire and must name that bond
first.  Negative arm: the right body must not fire.  The statistics are the
package's own model-comparison functions, pinned rather than re-derived.
"""

from __future__ import annotations

import numpy as np
import pytest

import tests.test_rigid_body as trb
from rietx import Refinement
from rietx.optimize.statistics import _chi2_absolute
from rietx.report.body_misfit import rigid_body_misfit
from rietx.report.layer2 import delta_bic
from rietx.strategy.staged import RefinementPlan, Stage

pytestmark = pytest.mark.xdist_group("body-misfit")


def _fitted(stretch: float):
    """The truth pattern, fitted with a body whose C–Br is ``stretch`` Å long."""
    pattern = trb.synthesize(trb.body_structure(trb.Q_TRUE))
    orig = trb.c6br

    def stretched():
        p = orig()
        u = (p[6] - p[0]) / np.linalg.norm(p[6] - p[0])
        p[6] = p[6] + stretch * u
        return p

    trb.c6br = stretched
    try:
        start = trb.body_structure(trb.Q_TRUE)
    finally:
        trb.c6br = orig
    ref = Refinement(start, trb.INS, history=False)
    ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("body", trb.BODY_GLOBS, max_iter=200)]))
    return ref, pattern


@pytest.fixture(scope="module")
def right():
    ref, pattern = _fitted(0.0)
    return rigid_body_misfit(ref, pattern)


@pytest.fixture(scope="module")
def wrong():
    ref, pattern = _fitted(0.3)
    return rigid_body_misfit(ref, pattern)


def test_a_wrong_body_fires_and_names_its_bond(wrong):
    (row,) = wrong.rows
    assert row.fires
    assert row.delta_bic > 10.0 and row.p_value < 1e-3
    assert row.chi2_released < row.chi2_body
    label, template, released, dev = row.deviations[0]
    assert label == "C0–Br"
    assert template == pytest.approx(2.20, abs=1e-6)
    # the data pull it most of the way back to the true 1.90 Å
    assert released < 2.0 and dev < -5.0
    (diag,) = wrong.diagnostics
    assert diag.code == "RIGID_BODY_MISFIT" and diag.level == "warning"
    assert "C0–Br" in diag.message and diag.value == pytest.approx(row.delta_bic)
    assert len(diag.where) == 7


def test_the_right_body_does_not_fire(right):
    (row,) = right.rows
    assert not row.fires
    assert right.diagnostics == []
    # the released atoms stay within their restraint widths of the template
    assert max(abs(d[3]) for d in row.deviations) < 2.0


def test_the_statistics_are_the_packages_own(wrong):
    (row,) = wrong.rows
    assert row.delta_bic == pytest.approx(delta_bic(
        row.chi2_body, row.chi2_released, row.n_points, row.n_added,
        n_effective=row.n_effective))
    assert row.n_added == 3 * 7 - 6        # seven free atoms against a 6-DOF pose


def test_no_body_no_rows():
    from tests.test_coordinates import make_rutile, synthesize_rutile
    pattern = synthesize_rutile()
    ref = Refinement(make_rutile(), trb.INS, history=False)
    ref.fit(pattern, plan=RefinementPlan(stages=[Stage("s", ["phases.*.scale"])]))
    out = rigid_body_misfit(ref, pattern)
    assert out.rows == [] and out.diagnostics == []


def test_chi2_absolute_is_the_unreduced_sum(right):
    # the helper the check reads its χ² through: reduced × (N − P)
    class S:
        chi2, n_points, n_free_parameters = 2.0, 110, 10
    assert _chi2_absolute(S) == pytest.approx(200.0)
