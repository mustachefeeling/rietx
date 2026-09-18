"""Bounds and flags for the walking parameters the width caps do not cover.

WP-1311. The width caps (PR #144) own strain and size, and
``PHASE_UNCONSTRAINED`` plus ``cell_window`` own a walking cell. What is left
gets at most a bound from physics or a flag, never a tuned cap, and each
signal has to fire on its own motivating configuration while staying silent on
a healthy fit.

This module holds one section per item. Item 3 is the resolution-positivity
guard: U, V and W each legitimately go negative on a real instrument, so the
constraint is on the Caglioti quadratic as a whole, and a fit that leaves the
physical set does not raise — ``gaussian_fwhm`` clamps Γ_G² to a floor and the
forward model reports a resolution four orders finer than any goniometer.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.model.forward import compile_model
from rietx.model.profiles.caglioti import _MIN_GAMMA_G2, gaussian_fwhm
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import Instrument
from rietx.schemas.pattern import PatternData
from rietx.strategy.staged import (
    RESOLUTION_CONE_TOL,
    check_hump_width,
    check_resolution_positive,
)
from tests.test_schemas import make_lab6

#: the configuration from PR #115's review — every value schema-legal
#: (u ∈ [-0.05, 1], v ∈ [-0.5, 0.5], w ∈ [0, 1]) and the quadratic negative
#: across an ordinary scan.
COLLAPSED = {"u": 0.05, "v": -0.5, "w": 0.001}

#: a real lab resolution function. V is **negative**, which is the usual sign
#: of a focusing geometry and exactly what this guard must not report.
HEALTHY_NEGATIVE_V = {"u": 0.02, "v": -0.012, "w": 0.008}


#: the test fixture's own wavelength; nothing here depends on its value.
WAVELENGTH = 1.5406


def _state(*, u=0.0, v=0.0, w=1e-3, lo=15.0, hi=110.0, step=0.05):
    """A compiled LaB6 model over a flat pattern at a given resolution."""
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.source.dispersion = None      # declared, never inherited
    ins.profile.u.value = u
    ins.profile.v.value = v
    ins.profile.w.value = w
    tt = np.arange(lo, hi, step)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 200.0).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return table, model


# ----------------------------------------------------------------------
# item 3 — the resolution function is a variance
# ----------------------------------------------------------------------
def test_the_collapsed_resolution_function_is_reported():
    """The motivating configuration, and what it actually does.

    The issue described the collapse as happening "at 157°". It happens
    everywhere: the quadratic's roots sit at 0.229° and 168.577° 2θ, so Γ_G²
    is negative at every point of an ordinary scan and Γ_G is the 1e-4° floor
    throughout.
    """
    table, model = _state(**COLLAPSED)
    findings = check_resolution_positive(table, model)

    assert [f.code for f in findings] == ["RESOLUTION_NOT_POSITIVE"]
    finding = findings[0]
    assert finding.paths == ("instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.w")
    assert finding.value < 0.0
    # every fitted point, not a high-angle tail
    assert f"{model.tt.size} of {model.tt.size} fitted points" in str(finding)

    # and the forward model really is reporting the floor rather than raising
    gamma = np.asarray(gaussian_fwhm(0.5 * model.tt, **COLLAPSED))
    assert np.allclose(gamma, _MIN_GAMMA_G2 ** 0.5)


def test_a_negative_v_on_a_healthy_instrument_is_silent():
    """The guard's whole point: the constraint is coupled, not per-parameter.

    A negative V is ordinary on a focusing geometry. Reporting it would make
    the guard fire on most real lab instruments.
    """
    table, model = _state(**HEALTHY_NEGATIVE_V)
    tan = np.tan(np.radians(0.5 * model.tt))
    g2 = (HEALTHY_NEGATIVE_V["u"] * tan * tan
          + HEALTHY_NEGATIVE_V["v"] * tan + HEALTHY_NEGATIVE_V["w"])
    assert g2.min() > 0.0, "fixture no longer exercises a positive quadratic"

    assert check_resolution_positive(table, model) == []


def test_zero_is_inside_the_physical_set():
    """U = V = W = 0 is an instrument with no Gaussian broadening.

    Every profile starts there before a resolution stage frees anything, so a
    two-sided test would fire on every fit's early stages — the
    ``STEPHENS_CONE_TOL`` lesson (WP-0601) one seam over.
    """
    table, model = _state(u=0.0, v=0.0, w=0.0)
    assert check_resolution_positive(table, model) == []


def test_the_tolerance_is_relative_and_one_sided():
    """A dip of a few ulp is the two association orders disagreeing.

    ``gaussian_fwhm`` and this guard build the same quadratic in different
    orders, so the bar has to sit above their disagreement and below anything
    physical.
    """
    table, model = _state(u=0.0, v=0.0, w=0.0)
    tiny = -0.5 * RESOLUTION_CONE_TOL
    table.entries[table._paths["instrument.profile.w"]].value = tiny
    assert check_resolution_positive(table, model) == []

    table.entries[table._paths["instrument.profile.w"]].value = -1e-6
    assert [f.code for f in check_resolution_positive(table, model)] == [
        "RESOLUTION_NOT_POSITIVE"]


def test_the_guard_is_silent_without_a_model():
    """The ``check_stephens_positive`` convention: no fitted axis, no claim.

    The range is what makes the question answerable — a dip outside the
    measured angles is unobservable, and flagging it would be a claim the data
    cannot support.
    """
    table, _model = _state(**COLLAPSED)
    assert check_resolution_positive(table, None) == []


def test_the_range_is_the_fitted_one_not_all_of_theta():
    """A quadratic that only dips outside the scan is not this fit's problem."""
    # roots at 0.229 deg and 168.577 deg 2theta; a scan inside them is bad
    # everywhere, a scan is never outside both, so build the complement case
    # directly: positive over 15-110 deg, negative past the upper root.
    u, v, w = 0.05, -0.5, 0.001
    wide = _state(u=u, v=v, w=w, lo=15.0, hi=110.0)[1]
    tan = np.tan(np.radians(0.5 * wide.tt))
    assert (u * tan * tan + v * tan + w).max() < 0.0

    # the same coefficients over a range above the upper root are positive
    table, model = _state(u=u, v=v, w=w, lo=169.5, hi=175.0, step=0.05)
    tan = np.tan(np.radians(0.5 * model.tt))
    assert (u * tan * tan + v * tan + w).min() > 0.0
    assert check_resolution_positive(table, model) == []


def test_the_hump_guard_abstains_exactly_where_this_one_speaks():
    """The hand-off ``check_hump_width``'s docstring promises.

    It abstains when the instrument width has collapsed to the floor, saying
    the unphysical instrument "is a separate, more fundamental defect and not
    this guard's to name". Nothing named it until this guard. The two must not
    both be silent on the same model.
    """
    table, model = _state(**COLLAPSED)
    assert check_hump_width(table, model) == []  # abstains, declares nothing
    assert check_resolution_positive(table, model), "nobody named the defect"


def test_the_finding_reaches_the_diagnostics_with_its_three_paths():
    """Every guard Diagnostic carries its paths in ``where`` (root CLAUDE.md).

    All three, because the constraint is on the quadratic: a client offering
    "fix this" has to reach the coefficient that is wrong, and which one that
    is cannot be read off the sum.
    """
    from rietx.refine import _guard_diagnostics
    from rietx.strategy.staged import GuardReport

    table, model = _state(**COLLAPSED)
    report = GuardReport()
    report.nonpositive_resolution = check_resolution_positive(table, model)

    diags = [d for d in _guard_diagnostics(report)
             if d.code == "RESOLUTION_NOT_POSITIVE"]
    assert len(diags) == 1
    assert diags[0].level == "warning"
    assert diags[0].where == ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.w"]
    assert diags[0].value == pytest.approx(
        report.nonpositive_resolution[0].value)
