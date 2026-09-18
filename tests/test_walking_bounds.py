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
    FLAT_DIRECTION_RHO,
    LINDEMANN_RHO,
    RESOLUTION_CONE_TOL,
    biso_melting_bound,
    check_biso_plausible,
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


# ----------------------------------------------------------------------
# item 2 — a large B is evidence about the model, so it is flagged not capped
# ----------------------------------------------------------------------
def test_the_bound_is_the_papers_arithmetic():
    """B_melt = 8π²ρ²(√2·v)^(2/3), Gilvarry (1956) eqs (1), (8) and (9).

    Written out here independently of the implementation, because the whole
    value of a quoted threshold is that it is the source's number and not a
    number that happens to look like it.
    """
    volume, n_atoms = 255.0, 30          # corundum, 8.50 Å³ per atom
    v = volume / n_atoms
    expected = 8.0 * np.pi ** 2 * LINDEMANN_RHO ** 2 * (np.sqrt(2.0) * v) ** (2 / 3)

    assert biso_melting_bound(volume, n_atoms) == pytest.approx(expected)
    assert biso_melting_bound(volume, n_atoms) == pytest.approx(4.57, abs=0.01)


def test_the_bound_moves_with_packing_so_no_constant_would_do():
    """A fixed threshold would be wrong at one end of the ordinary range.

    Over 8.5–22.4 Å³ per atom — corundum to NaCl, both perfectly ordinary —
    the bound moves by nearly a factor of two, which is why the guard computes
    it per phase instead of declaring a number.
    """
    corundum = biso_melting_bound(255.0, 30)
    nacl = biso_melting_bound(5.6402 ** 3, 8)
    assert corundum == pytest.approx(4.57, abs=0.01)
    assert nacl == pytest.approx(8.72, abs=0.01)
    assert nacl / corundum > 1.8


def test_a_degenerate_cell_gets_no_opinion():
    """No volume, no length scale, no claim — never a finding by accident."""
    assert biso_melting_bound(0.0, 5) == float("inf")
    assert biso_melting_bound(100.0, 0) == float("inf")


def test_an_ordinary_biso_is_silent_and_a_molten_one_is_reported():
    table, model = _state()
    bound = biso_melting_bound(4.1566 ** 3, 7)

    # the fixture's own starting B, an ordinary 0.5 Å²
    assert check_biso_plausible(table, model) == []

    path = "phases.0.atoms.0.biso"
    table.entries[table._paths[path]].value = 1.5 * bound
    findings = check_biso_plausible(table, model)
    assert [f.code for f in findings] == ["BISO_UNUSUALLY_LARGE"]
    assert findings[0].paths == (path,)
    assert findings[0].value == pytest.approx(1.5 * bound)
    assert "1.5× the" in str(findings[0])
    assert "Lindemann" in str(findings[0])


def test_the_25_a2_schema_ceiling_is_far_above_melting():
    """Why this guard exists at all, stated as a test.

    ``Atom.biso`` caps at 25 Å², and on every ordinary structure that ceiling
    is several times the bound below which the solid is still a solid. The cap
    therefore bounds nothing physical, and removing the guard would leave the
    whole 5–25 Å² range unremarked.
    """
    from rietx.schemas.common import Parameter
    from rietx.schemas.structure import Atom

    zero = Parameter(value=0.0)
    ceiling = Atom(label="X", species="Si", x=zero, y=zero, z=zero).biso.max
    assert ceiling == 25.0
    for volume, n_atoms in ((255.0, 30), (4.1566 ** 3, 7), (5.6402 ** 3, 8)):
        assert biso_melting_bound(volume, n_atoms) < 0.4 * ceiling


def test_the_biso_guard_is_silent_without_a_model():
    """The ``check_stephens_positive`` convention, again: no model, no claim."""
    table, _model = _state()
    table.entries[table._paths["phases.0.atoms.0.biso"]].value = 50.0
    assert check_biso_plausible(table, None) == []


def test_the_biso_finding_reaches_the_diagnostics():
    from rietx.refine import _guard_diagnostics
    from rietx.strategy.staged import GuardReport

    table, model = _state()
    table.entries[table._paths["phases.0.atoms.0.biso"]].value = 50.0
    report = GuardReport()
    report.large_biso = check_biso_plausible(table, model)

    diags = [d for d in _guard_diagnostics(report)
             if d.code == "BISO_UNUSUALLY_LARGE"]
    assert len(diags) == 1
    assert diags[0].level == "warning"
    assert diags[0].where == ["phases.0.atoms.0.biso"]
    assert diags[0].value == pytest.approx(50.0)


# ----------------------------------------------------------------------
# item 5 — |ρ| = 1.000 is a rank statement, not a strong correlation
# ----------------------------------------------------------------------
def _guard_with(rho: float, threshold: float = 0.98):
    """A GuardReport from a real table whose first two free columns correlate."""
    from types import SimpleNamespace

    from rietx.strategy.staged import check_guards

    table = _state()[0]
    table.set_vary(["phases.0.cell.*", "phases.0.scale",
                    "instrument.zero_shift"], True)
    free = list(table.free_paths)
    assert len(free) >= 2, free
    corr = np.eye(len(free))
    corr[0, 1] = corr[1, 0] = rho
    outcome = SimpleNamespace(correlation=corr, jac=None, theta=table.x0())
    return check_guards(table, outcome, threshold, model=None), free[:2]


def test_the_threshold_is_the_precision_the_message_prints():
    """Not a chosen number: ρ is rendered to three decimals, so the bar is the
    half-width of that rounding and the claim is one the message can support.
    """
    assert FLAT_DIRECTION_RHO == 1.0 - 5e-4

    from rietx.strategy.staged import GuardFinding

    rendered = str(GuardFinding.correlation("a", "b", FLAT_DIRECTION_RHO))
    assert "ρ=+1.000" in rendered, "the bar and the format have drifted apart"
    just_under = str(GuardFinding.correlation("a", "b", FLAT_DIRECTION_RHO - 1e-4))
    assert "ρ=+0.999" in just_under


def test_a_strong_correlation_is_not_a_flat_direction():
    """ρ = 0.99 is what HIGH_CORRELATION is for, and nothing more is claimed."""
    report, _free = _guard_with(0.99)
    assert [f.code for f in report.high_correlations] == ["HIGH_CORRELATION"]
    assert report.flat_directions == []


def test_a_flat_direction_is_reported_beside_its_correlation():
    """Beside, never instead: the SEQUENTIAL_PERSISTENT_FINDING precedent.

    Replacing the row would silence a HIGH_CORRELATION that existing consumers
    count, so the sharper finding rides alongside the one it sharpens.
    """
    report, free = _guard_with(-1.0)
    assert [f.code for f in report.high_correlations] == ["HIGH_CORRELATION"]
    assert [f.code for f in report.flat_directions] == ["FLAT_DIRECTION"]

    flat = report.flat_directions[0]
    assert flat.paths == (free[0], free[1])
    assert flat.value == pytest.approx(-1.0)
    assert "does not separate them" in str(flat)


def test_the_sign_is_kept_because_a_domain_label_is_not_a_magnitude():
    """ρ = −1.000 and ρ = +1.000 are the same rank statement, and the sign
    still says which way the two move together. It is reported, not discarded.
    """
    minus = _guard_with(-1.0)[0].flat_directions[0]
    plus = _guard_with(1.0)[0].flat_directions[0]
    assert minus.value < 0 < plus.value
    assert "-1.000" in str(minus) or "−1.000" in str(minus)


def test_the_flat_finding_reaches_the_diagnostics():
    from rietx.refine import _guard_diagnostics

    report, free = _guard_with(-1.0)
    diags = [d for d in _guard_diagnostics(report) if d.code == "FLAT_DIRECTION"]
    assert len(diags) == 1
    assert diags[0].level == "warning"
    assert diags[0].where == [free[0], free[1]]
    assert "rank of the data" in diags[0].message


def test_the_two_codes_do_not_evict_each_other_in_the_dedup():
    """Both are keyed by pair; before WP-1311 the key was the pair alone.

    A flat pair produces one of each, so a pair-only key would have dropped
    whichever arrived second and the loss would be silent.
    """
    from rietx.refine import _dedup_high_correlations
    from rietx.schemas.results import Diagnostic

    where = ["instrument.profile.axial_sl", "instrument.profile.axial_hl"]
    hits = {
        ("HIGH_CORRELATION", frozenset(where)): [
            ("widths", Diagnostic(level="warning", code="HIGH_CORRELATION",
                                  message="hi", where=where, value=-1.0))],
        ("FLAT_DIRECTION", frozenset(where)): [
            ("widths", Diagnostic(level="warning", code="FLAT_DIRECTION",
                                  message="flat", where=where, value=-1.0))],
    }
    codes = sorted(d.code for d in _dedup_high_correlations(hits))
    assert codes == ["FLAT_DIRECTION", "HIGH_CORRELATION"]
