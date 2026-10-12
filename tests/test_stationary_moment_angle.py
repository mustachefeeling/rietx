"""A moment angle at a direction the symmetry fixes leaves the covariance (WP-1929).

The pattern is even in a moment's polar angle and azimuth about every
direction the site symmetry fixes, so their Jacobian columns vanish there
while the data still determine the angle through curvature.  The covariance
equilibrates every column to unit norm, so beside such a direction where the
solver stopped decided the other esds: the two-site Pnma set's moduli read
0.031 and 0.159 μ_B under LM on macOS arm64, against 0.00151 and 0.00111 with
the angle columns left out.

The solve now asks, after converging, whether its free angles sit at such a
direction (``optimize.least_squares.stationary_angle_test``): a joint
Gauss-Newton step to where their columns vanish, Δχ² there with the other
columns refitted by one linear step, against the χ̄² cut for that many
one-sided directions.  A set that passes leaves the covariance.  The fixtures
are ``test_magnetic_solve``'s two-site set simulated with Poisson noise, about
half a second a fit.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.structure import MagneticSymmetry, Moment

MN1, MN2 = "phases.0.atoms.0.moment", "phases.0.atoms.1.moment"
ANGLES = [f"{MN1}.dof1", f"{MN1}.dof2", f"{MN2}.dof1", f"{MN2}.dof2"]


def _solve():
    from tests import test_magnetic_solve as T

    return T


def _vec(mu: float, tilt: float, phi: float = 0.0) -> tuple[float, float, float]:
    """``mu`` at ``tilt`` from **a** towards **c**, turned ``phi`` towards **b**."""
    return (mu * math.cos(tilt) * math.cos(phi),
            mu * math.cos(tilt) * math.sin(phi), mu * math.sin(tilt))


def _magnetic() -> MagneticSymmetry:
    T = _solve()
    truth = T.candidate_named("P n m a", T.MN_SITE, (0, 0, 0), T.A_TYPE_BNS)
    ops, cent = truth.group.xyz_strings()
    return MagneticSymmetry(operations=list(ops), centerings=list(cent))


def _plan() -> rx.RefinementPlan:
    from rietx.strategy.magnetic import SOLVE_STAGE_NAMES, SOLVE_STAGE_PATHS

    return rx.RefinementPlan(stages=[
        rx.Stage(name, list(paths))
        for name, paths in zip(SOLVE_STAGE_NAMES, SOLVE_STAGE_PATHS, strict=True)])


def _fit(tilt: float, *, two: bool = True, start_tilt: float | None = None,
         seed: int | None = None):
    """Mn1 at 3.5 μ_B tilted ``tilt`` from **a**, Mn2 at 0.7 along **a**."""
    T = _solve()
    mag = _magnetic()
    instrument = T.neutron()
    data = T.simulate(T.two_site(
        m1=Moment.from_values(_vec(3.5, tilt), "Mn3+"),
        m2=Moment.from_values((0.7, 0.0, 0.0), "Mn3+") if two else None,
        magnetic=mag), instrument, **({} if seed is None else {"seed": seed}))
    start = T.two_site(
        m1=Moment.from_values(_vec(3.3, tilt + 0.04 if start_tilt is None
                                   else start_tilt, 0.03), "Mn3+", vary=True),
        m2=(Moment.from_values(_vec(0.75, 0.03, 0.03), "Mn3+", vary=True)
            if two else None),
        magnetic=mag)
    ref = rx.Refinement(rx.Structure(phases=[start]), instrument)
    return ref, data, ref.fit(data, plan=_plan(), telemetry=False)


def _rows(result):
    return {p.path: p for p in result.parameters}


def _rho(ref, a: str, b: str) -> float:
    _result, table, theta, stderr, corr = ref._answer_covariance
    cov = table.physical_covariance(theta, stderr, corr, [a, b])
    return float(cov[0, 1] / math.sqrt(cov[0, 0] * cov[1, 1]))


def test_the_cut_is_the_chi_bar_squared_point():
    """One function, and at k = 1 the profile interval's own bound quantile."""
    from scipy.stats import chi2

    from rietx.optimize.least_squares import STATIONARY_ANGLE_LEVEL
    from rietx.optimize.statistics import chi_bar_squared_quantile
    from rietx.schemas.interval import PARAMETER_INTERVAL_LEVEL
    from rietx.strategy.parameter_interval import interval_quantile

    assert STATIONARY_ANGLE_LEVEL == PARAMETER_INTERVAL_LEVEL
    assert chi_bar_squared_quantile(0.95, 1) == interval_quantile(0.95, one_sided=True)
    for k, expected in ((1, 2.706), (2, 4.231), (4, 6.497)):
        c = chi_bar_squared_quantile(0.95, k)
        assert c == pytest.approx(expected, abs=1e-3)
        # the tail of Σ C(k,j)/2^k χ²_j at the cut is the 5 % it was asked for
        tail = sum(math.comb(k, j) / 2 ** k * chi2.sf(c, j) for j in range(1, k + 1))
        assert tail == pytest.approx(0.05, abs=1e-9)
    # no direction; no level; and a level the point mass at 0 already meets,
    # half of it for one direction and a quarter for two
    for bad in ((0.95, 0), (1.0, 2), (0.5, 1), (0.2, 2)):
        with pytest.raises(ValueError):
            chi_bar_squared_quantile(*bad)


def test_a_stop_beside_the_symmetry_direction_leaves_the_angles_out():
    """Both moments simulated along **a**: every angle is at the direction.

    Seed 4 stops 0.008 and 0.061 rad off it in the azimuths and reads a
    statistic of −0.008 against the cut of 6.50 for four angles (macOS arm64).
    Seeds 0 and 1 read 10.4 and 11.6.  Those are false keeps, which a 95 %
    cut makes at 5 % (WP-1929 measured 3 of 48), so the seed is chosen for a
    low statistic and only the verdict is pinned.
    """
    ref, _data, result = _fit(0.0, seed=4)
    stage = result.stages[-1]
    (only,) = stage.moment_angle_tests
    assert only.paths == ANGLES and only.reached and only.zeroed
    assert abs(only.statistic) < 1.0 and only.cut == pytest.approx(6.497, abs=1e-3)
    assert set(only.half_widths) == set(ANGLES)
    rows = _rows(result)
    # free, refined and without an esd: the value stands
    assert all(rows[p].vary and rows[p].stderr is None for p in ANGLES)
    assert rows[f"{MN1}.dof0"].stderr == pytest.approx(0.00152, rel=0.05)
    assert rows[f"{MN2}.dof0"].stderr == pytest.approx(0.00112, rel=0.05)
    assert _rho(ref, f"{MN1}.dof0", f"{MN2}.dof0") == pytest.approx(-0.24, abs=0.02)
    (finding,) = [d for d in result.diagnostics
                  if d.code == "MOMENT_ANGLE_STATIONARY"]
    assert finding.where == ANGLES and finding.value == only.statistic
    assert "profile_interval" in finding.suggestion


@pytest.fixture(scope="module")
def tilted():
    """Mn1 tilted 0.05 rad towards **c**, a direction the data determine."""
    return _fit(0.05)


@pytest.mark.xdist_group("stationary-angle-tilt")
def test_a_tilt_the_data_determine_keeps_its_column(tilted):
    """Jointly, the four angles fail by three orders of magnitude.

    WP-1929 measured every 0.05 rad tilt at about 2500 and every 0.01 rad one
    at 12.2 or more, against a cut of 6.50.  The tilted polar angle is the
    first one dropped, by its second-order contribution, and keeps its esd.
    """
    _ref, _data, result = tilted
    first, *_rest = result.stages[-1].moment_angle_tests
    assert first.paths == ANGLES and first.reached and not first.zeroed
    assert 2000.0 < first.statistic < 3500.0
    rows = _rows(result)
    assert rows[f"{MN1}.dof1"].stderr is not None
    assert rows[f"{MN1}.dof1"].value == pytest.approx(math.pi / 2 - 0.05, abs=0.005)


@pytest.mark.xdist_group("stationary-angle-tilt")
def test_a_mixed_set_drops_the_tilt_and_leaves_the_azimuths_out(tilted):
    """The tilt is dropped, then Mn2's polar angle, which the tilt couples.

    With Mn1 out of the plane the interference term is odd in Mn2's polar
    angle, so no step drives that column to zero and it goes next.  The two
    azimuths pass on their own (−3e-5 here), and zeroing them gives the moduli
    the untilted set gets.
    """
    ref, _data, result = tilted
    tests = result.stages[-1].moment_angle_tests
    assert [t.paths for t in tests] == [
        ANGLES, [f"{MN1}.dof2", f"{MN2}.dof1", f"{MN2}.dof2"],
        [f"{MN1}.dof2", f"{MN2}.dof2"]]
    assert not tests[1].reached and tests[1].statistic is None
    last = tests[-1]
    assert last.zeroed and abs(last.statistic) < 1.0
    assert last.cut == pytest.approx(4.231, abs=1e-3)
    rows = _rows(result)
    assert rows[f"{MN1}.dof2"].stderr is None and rows[f"{MN2}.dof2"].stderr is None
    assert rows[f"{MN2}.dof1"].stderr is not None
    assert rows[f"{MN1}.dof0"].stderr == pytest.approx(0.00152, rel=0.05)
    assert rows[f"{MN2}.dof0"].stderr == pytest.approx(0.00111, rel=0.05)
    (finding,) = [d for d in result.diagnostics
                  if d.code == "MOMENT_ANGLE_STATIONARY"]
    assert finding.where == last.paths
    assert f"{MN1}.dof1" in finding.message   # tested and kept, named


def test_a_turn_onto_the_starts_mirror_image_does_not_read_flat():
    """The hold's probe turns both ways (WP-1929).

    A moment 0.05 rad off **a** towards **c**: a +0.1 rad turn of the polar
    angle lands on its mirror image across the ab plane, whose pattern is the
    same, so the response a one-sided probe read is roundoff and it held a
    determined angle.  The −0.1 rad turn moves the pattern at order one.
    """
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.refine import (
        MOMENT_DIRECTION_SUPPORT,
        MOMENT_PROBE_ANGLE_RAD,
        _flat_moment_paths,
    )

    T = _solve()
    instrument = T.neutron()
    phase = T.two_site(m1=Moment.from_values(_vec(3.5, 0.05), "Mn3+", vary=True),
                       m2=None, magnetic=_magnetic())
    structure = rx.Structure(phases=[phase])
    model = compile_model(structure, instrument, T.simulate(phase, instrument))
    table = ParameterTable(structure, instrument)
    table.push_moment_frames(model)
    values = table.decode(table.x0())
    y0 = np.asarray(model.evaluate(values), dtype=np.float64)

    def response(path: str, step: float) -> float:
        v = dict(values)
        v[path] = values[path] + step
        return float(np.linalg.norm(
            np.asarray(model.evaluate(v), dtype=np.float64) - y0))

    polar = f"{MN1}.dof1"
    assert values[polar] == pytest.approx(math.pi / 2 - 0.05, abs=1e-9)
    scale = response(f"{MN1}.dof0", MOMENT_PROBE_ANGLE_RAD * 3.5)
    assert response(polar, MOMENT_PROBE_ANGLE_RAD) <= MOMENT_DIRECTION_SUPPORT * scale
    assert response(polar, -MOMENT_PROBE_ANGLE_RAD) > 1e-2 * scale
    assert polar not in _flat_moment_paths(model, table)


def test_a_start_beside_its_mirror_image_refines_the_tilt():
    """The same start through a fit: truth 0.01 rad, start 0.05 rad.

    Held by the one-sided probe, the polar angle stayed at the start and the
    fit ended at χ² 20614 (WP-1929, macOS arm64).
    """
    _ref, _data, result = _fit(0.01, two=False, start_tilt=0.05)
    assert all(f"{MN1}.dof1" not in s.held for s in result.stages)
    assert result.statistics.chi2 < 1.2
    assert _rows(result)[f"{MN1}.dof1"].value == pytest.approx(
        math.pi / 2 - 0.01, abs=0.003)


def test_an_angle_without_an_esd_still_has_a_profile_interval():
    """The diagnostic's suggestion, taken: the profile steps from the half-width.

    The azimuth's profile is even about the direction (φ = 0), so the interval
    is symmetric about 0 rather than about the value the solver stopped at.
    Measured: ±0.0287 rad around a stop at 0.011, 30 refits.
    """
    ref, data, result = _fit(0.0, two=False, seed=2)
    azimuth = f"{MN1}.dof2"
    (passed,) = [t for t in result.stages[-1].moment_angle_tests if t.zeroed]
    assert azimuth in passed.paths and _rows(result)[azimuth].stderr is None
    interval = ref.profile_interval(data, azimuth)
    assert interval.stderr is None and not interval.one_sided
    assert interval.lower_stop == interval.upper_stop == "threshold"
    width = interval.upper - interval.lower
    assert abs(interval.upper + interval.lower) < 0.05 * width
    assert interval.lower < interval.value < interval.upper


def test_the_joint_path_runs_the_same_test():
    """A joint X-ray + neutron fit tests the stacked residual (``multi``).

    Noise-free, so the statistic is large and negative: moving to the
    direction lowers χ² by more than the noise-free χ² itself.  The Pmmm
    control, with every angle determined, keeps every column.
    """
    from tests.test_joint_flat_moments import BASE, _joint

    _j, along_a = _joint("P m m m", (3.0, 0.0, 0.0), (2.5, 0.05, 0.05))
    (only,) = along_a.stages[-1].moment_angle_tests
    assert only.paths == [f"{BASE}.dof1", f"{BASE}.dof2"] and only.zeroed
    assert "MOMENT_ANGLE_STATIONARY" in {d.code for d in along_a.diagnostics}
    _j, general = _joint("P m m m", (1.5, 2.0, 3.0), (1.0, 1.0, 2.5))
    assert not any(t.zeroed for t in general.stages[-1].moment_angle_tests)
