"""A moment's angle DOFs are reported in one chart and compared modulo a turn (#604).

Everything here is **synthetic**: one Mn at the origin of an orthorhombic cell,
neutron CW, patterns from rietx's own forward model.

Two defects, one canonicalisation.  The solver leaves the DOFs wherever its last
step put them, and nothing bounds them, so a fit ends at φ + 2πk, at (−μ, φ + π)
or at (μ, −θ, φ + π) — the moment it started from, in other numbers.

* a commit moves every block into the principal chart (μ ≥ 0, θ ∈ [0, π],
  φ ∈ (−π, π]) and changes no moment, no esd and no correlation's meaning:
  asserted on the components, on ``stderr_physical`` through the re-charted
  outcome, and on a fit run with and without the move;
* the chart still has a cut, so the two series fences take an angle's
  difference modulo a turn.  The positive arms are a real rotation across the
  cut (it must fire, with its own size and sign) and a 2π step on a parameter
  that is not an angle (it must still fire).

What a plausible wrong fix would pass, and therefore what each block turns on:
wrapping only the reported value leaves the series reading −π against π (the
cut arm); reflecting μ without carrying the correlation sign leaves a ρ that
describes the other chart (the correlation arm); wrapping every ``dof<k>`` by
its name would wrap a coordinate DOF (the angle set is read off the frames).
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.moments import canonical_dofs, moment_from_dofs
from rietx.optimize.least_squares import rechart_outcome
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter as P
from rietx.schemas.results import RefinedParameter, Statistics
from rietx.schemas.sequential import SeriesEntry, SeriesResult
from rietx.schemas.structure import Atom, Cell, MagneticSymmetry, Moment, Phase
from rietx.sequential import (
    _angle_difference,
    _angle_paths,
    _discontinuity_steps,
    _path_dependence_diagnostics,
)

BASE = "phases.0.atoms.0"
AZIMUTH_2D = f"{BASE}.moment.dof1"
INS = rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.3)


def _atom(label, species, xyz, biso, moment=None):
    return Atom(label=label, species=species, x=P(value=xyz[0]), y=P(value=xyz[1]),
                z=P(value=xyz[2]), occ=P(value=1.0), biso=P(value=biso, unit="A^2"),
                moment=moment)


def ortho(m, operations=("x,y,z,+1", "x,y,-z,-1")) -> Phase:
    """Pmmm; with {1, m_z'} the Mn moment lies in the ab plane (n = 2), with
    {1} alone it may point anywhere (n = 3)."""
    return Phase(name="ortho", space_group="P m m m",
                 cell=Cell(a=P(value=4.0), b=P(value=4.4), c=P(value=5.0),
                           alpha=P(value=90.0), beta=P(value=90.0),
                           gamma=P(value=90.0)),
                 scale=P(value=1.0, min=0.0, transform="softplus"),
                 atoms=[_atom("Mn", "Mn", (0, 0, 0), 0.3,
                              Moment.from_values(m, "Mn2+", vary=True)),
                        _atom("O", "O", (0.5, 0.5, 0.5), 0.4)],
                 magnetic_symmetry=MagneticSymmetry(operations=list(operations)))


def _table(m, operations=("x,y,z,+1", "x,y,-z,-1")) -> ParameterTable:
    return ParameterTable(rx.Structure(phases=[ortho(m, operations)]), INS)


def _components(table) -> np.ndarray:
    by = {e.path: e.value for e in table.entries}
    return np.array([by[f"{BASE}.moment.crystalaxis_{c}"] for c in "xyz"])


def _with_dofs(table, dofs) -> np.ndarray:
    """``x0()`` with the block's DOFs replaced by ``dofs`` (free columns)."""
    theta = table.x0()
    free = table.free_paths
    for k, v in enumerate(dofs):
        theta[free.index(f"{BASE}.moment.dof{k}")] = v
    return theta


# ============================================================ the chart itself

@pytest.mark.parametrize("n", [2, 3])
def test_the_chart_is_an_identity_on_the_moment_with_a_diagonal_sign_jacobian(n):
    rng = np.random.default_rng(604 + n)
    frame = np.linalg.qr(rng.normal(size=(3, 3)))[0][:n]
    for _ in range(2000):
        raw = rng.normal(size=n) * np.r_[3.0, [30.0] * (n - 1)]
        c, s = canonical_dofs(raw)
        assert c[0] >= 0.0 and -np.pi < c[-1] <= np.pi
        if n == 3:
            assert 0.0 <= c[1] <= np.pi
        np.testing.assert_allclose(moment_from_dofs(frame, c),
                                   moment_from_dofs(frame, raw), atol=1e-12)
        # the Jacobian of the move is diag(s): a small step on raw k moves
        # canonical k by s[k] times it and nothing else (modulo a turn)
        h = 1e-7
        for k in range(n):
            bumped = raw.copy()
            bumped[k] += h
            d = canonical_dofs(bumped)[0] - c
            d[1:] = _angle_difference(d[1:])
            expected = np.zeros(n)
            expected[k] = s[k] * h
            np.testing.assert_allclose(d, expected, atol=1e-11)


def test_a_moment_already_in_the_chart_comes_back_bit_for_bit():
    for raw in ([2.0, 0.3], [2.0, -np.pi + 1e-9], [2.0, np.pi], [1.5, 0.4, -2.0],
                [-1.25]):
        c, s = canonical_dofs(raw)
        assert c.tolist() == list(raw) and s.tolist() == [1.0] * len(raw)


# ============================================================ the commit

@pytest.mark.parametrize("ops, raw, reflected", [
    (("x,y,z,+1", "x,y,-z,-1"), [3.5, np.pi + 16 * np.pi], False),   # 53.4 rad
    (("x,y,z,+1", "x,y,-z,-1"), [-3.5, 0.2 - 4 * np.pi], True),      # μ < 0
    (("x,y,z,+1",), [3.9, 50.959, 0.93], False),     # the issue's polar: 0.69
    (("x,y,z,+1",), [3.9, 50.959 - 2.0, 0.93], True),  # wraps to θ < 0
    (("x,y,z,+1",), [3.9, -0.7, -763.6], True),                      # θ < 0
    (("x,y,z,+1",), [-2.0, 2.5, 7.0], True),                         # μ < 0
])
def test_a_commit_lands_in_the_chart_and_moves_no_moment_and_no_esd(
        ops, raw, reflected):
    table = _table((3.0, 0.5, 0.0) if len(raw) == 2 else (1.0, 1.0, 2.0), ops)
    theta = _with_dofs(table, raw)
    expected = moment_from_dofs(table.moment_frames()[BASE], raw)
    n = len(theta)
    stderr = np.linspace(0.01, 0.05, n)
    rng = np.random.default_rng(len(raw))
    a = rng.normal(size=(n, n))
    cov = a @ a.T + n * np.eye(n)
    corr = cov / np.sqrt(np.outer(np.diag(cov), np.diag(cov)))
    esd_before = table.stderr_physical(theta, stderr, corr)
    decoded = table.decode(theta)

    from rietx.optimize.least_squares import LSQOutcome
    outcome = LSQOutcome(theta, 1.0, 1.0, 1, "converged",
                         np.ones((5, n)), stderr, corr,
                         residual_cosine=np.linspace(-0.5, 0.5, n))
    signs = table.commit(theta)
    assert signs is not None
    after = rechart_outcome(outcome, table.x0(), signs)

    by = {e.path: e.value for e in table.entries}
    dofs = [by[f"{BASE}.moment.dof{k}"] for k in range(len(raw))]
    assert dofs[0] >= 0.0 and -np.pi < dofs[-1] <= np.pi
    if len(raw) == 3:
        assert 0.0 <= dofs[1] <= np.pi
    np.testing.assert_allclose(_components(table), expected, atol=1e-12)
    # every other entry is untouched, bit for bit
    for e in table.entries:
        if ".moment." not in e.path:
            assert e.value == decoded[e.path]
    # no esd moves, through the re-charted correlations as well
    esd_after = table.stderr_physical(after.theta, after.stderr_internal,
                                      after.correlation)
    assert esd_after.keys() == esd_before.keys()
    for path, value in esd_before.items():
        assert esd_after[path] == pytest.approx(value, rel=1e-12), path
    # a reflected column carries its sign into ρ, the Jacobian and the cosine
    s = signs
    np.testing.assert_array_equal(after.correlation, corr * np.outer(s, s))
    np.testing.assert_array_equal(after.jac, outcome.jac * s)
    np.testing.assert_array_equal(after.residual_cosine, outcome.residual_cosine * s)
    assert bool((s == -1.0).any()) is reflected


def test_a_commit_already_in_the_chart_reports_nothing_moved():
    table = _table((3.0, 0.5, 0.0))
    assert table.commit(table.x0()) is None


def test_a_tied_block_is_not_reflected_and_only_loses_its_turns():
    """A tie reads its source's value: reflecting a source's μ would negate a
    dependent that is not an angle, so a block a tie reads is left alone
    except for whole turns on its own angles."""
    from rietx.params.vector import AffineTie

    table = _table((3.0, 0.5, 0.0))
    table.set_tie("instrument.zero_shift", AffineTie(
        terms=((f"{BASE}.moment.dof0", 0.01),)))
    theta = _with_dofs(table, [-3.0, 0.4 + 6 * np.pi])
    expected = moment_from_dofs(table.moment_frames()[BASE], [-3.0, 0.4])
    table.commit(theta)
    by = {e.path: e.value for e in table.entries}
    assert by[f"{BASE}.moment.dof0"] == -3.0
    assert by[f"{BASE}.moment.dof1"] == pytest.approx(0.4, abs=1e-12)
    assert by["instrument.zero_shift"] == pytest.approx(-0.03, abs=1e-15)
    np.testing.assert_allclose(_components(table), expected, atol=1e-12)


def test_the_angle_paths_are_read_off_the_frames():
    s2 = rx.Structure(phases=[ortho((3.0, 0.5, 0.0))])
    s3 = rx.Structure(phases=[ortho((1.0, 1.0, 2.0), ("x,y,z,+1",))])
    assert _angle_paths(s2, INS) == {AZIMUTH_2D}
    assert _angle_paths(s3, INS) == {f"{BASE}.moment.dof1", f"{BASE}.moment.dof2"}


# ============================================================ the fences, by hand

def _series(path, values, sd=0.01) -> SeriesResult:
    stats = Statistics(rwp=0.05, rp=0.05, rexp=0.04, chi2=1.0, gof=1.25,
                       n_points=100, n_free_parameters=3)
    return SeriesResult(x_label="T (K)", entries=[
        SeriesEntry(index=k, label=f"p{k}", x=10.0 * (k + 1), status="converged",
                    rwp_fence=None if k == 0 else 0.1, statistics=stats,
                    parameters=[RefinedParameter(path=path, value=v, stderr=sd)])
        for k, v in enumerate(values)])


#: a moment along −a, refined either side of the azimuth's cut: it moves by
#: at most 0.012 rad a step over the whole series
ON_THE_CUT = [3.130, 3.136, 3.133, 3.139, -3.140, -3.137, -3.140]


def test_a_series_sitting_on_the_cut_is_not_a_discontinuity():
    series = _series(AZIMUTH_2D, ON_THE_CUT)
    # the defect, as the fence read it before #604
    assert [s.record.path for s in _discontinuity_steps(series)] == [AZIMUTH_2D]
    assert _discontinuity_steps(series, angles=frozenset({AZIMUTH_2D})) == []


def test_a_real_rotation_across_the_cut_still_fires_with_its_own_size():
    """The positive arm: 1 rad of rotation through φ = π reads as −5.28 in
    value, and is reported as the +1.0 it is."""
    values = [3.00, 3.01, 3.02, 3.02 + 1.0 - 2 * np.pi, 4.03 - 2 * np.pi,
              4.02 - 2 * np.pi, 4.03 - 2 * np.pi]
    (s,) = _discontinuity_steps(_series(AZIMUTH_2D, values),
                                angles=frozenset({AZIMUTH_2D}))
    assert s.record.labels == ("p2", "p3")
    assert s.record.step == pytest.approx(1.0, abs=1e-9)


def test_a_spin_flip_is_the_largest_step_an_angle_can_take_and_fires():
    values = [0.10, 0.11, 0.10, 0.10 + np.pi, 0.11 + np.pi, 0.10 + np.pi, 3.25]
    (s,) = _discontinuity_steps(_series(AZIMUTH_2D, values),
                                angles=frozenset({AZIMUTH_2D}))
    assert s.record.labels == ("p2", "p3")
    assert abs(s.record.step) == pytest.approx(np.pi, abs=1e-9)


def test_a_two_pi_step_on_a_parameter_that_is_not_an_angle_still_fires():
    values = [v + (2 * np.pi if k >= 3 else 0.0)
              for k, v in enumerate([4.0, 4.001, 4.002, 4.003, 4.004, 4.005, 4.006])]
    (s,) = _discontinuity_steps(_series("phases.0.cell.a", values, sd=1e-4),
                                angles=frozenset({AZIMUTH_2D}))
    assert s.record.step == pytest.approx(2 * np.pi + 0.001, abs=1e-9)


def test_two_chains_either_side_of_the_cut_are_not_path_dependent():
    forward = _series(AZIMUTH_2D, ON_THE_CUT)
    backward = _series(AZIMUTH_2D, [-v for v in ON_THE_CUT[:4]] + [
        v + 0.002 for v in ON_THE_CUT[4:]])
    assert [d.code for d in _path_dependence_diagnostics(forward, backward)] == [
        "SEQUENTIAL_PATH_DEPENDENT"]
    assert _path_dependence_diagnostics(
        forward, backward, angles=frozenset({AZIMUTH_2D})) == []


def test_two_chains_a_real_half_radian_apart_across_the_cut_are():
    forward = _series(AZIMUTH_2D, [3.0] * 7)
    backward = _series(AZIMUTH_2D, [3.0 + 0.5 - 2 * np.pi] * 7)
    (d,) = _path_dependence_diagnostics(forward, backward,
                                        angles=frozenset({AZIMUTH_2D}))
    assert d.code == "SEQUENTIAL_PATH_DEPENDENT"
    assert "35.4σ" in d.message      # 0.5 / (0.01·√2), not 5.78 / it


# ============================================================ fitted

GRID = np.arange(8.0, 150.0, 0.05)


def _ycalc(structure) -> np.ndarray:
    from rietx.model.forward import compile_model

    blank = rx.PatternData(two_theta=GRID.tolist(), intensity=[1.0] * len(GRID))
    table = ParameterTable(structure, INS)
    return np.asarray(compile_model(structure, INS, blank).evaluate(
        table.decode(table.x0())), float)


def _pattern(m, seed, scale=None):
    truth = rx.Structure(phases=[ortho(m)])
    s = scale or 2e4 / _ycalc(truth).max()
    truth.phases[0].scale.value = s
    y = _ycalc(truth) + 50.0
    obs = y + np.random.default_rng(seed).normal(0, np.sqrt(y))
    return rx.PatternData(two_theta=GRID.tolist(), intensity=obs.tolist(),
                          sigma=np.sqrt(np.maximum(y, 1.0)).tolist()), s


def _plan():
    base = ["phases.*.scale", "instrument.background.c*"]
    return rx.RefinementPlan(stages=[
        rx.Stage("scale", base),
        rx.Stage("moment", base + ["phases.*.atoms.*.moment.dof*"])])


def _along_minus_a(m):
    """The issue's stated moment, built as its repro built it."""
    return (m * np.cos(np.pi), m * np.sin(np.pi), 0.0)


def _start(scale):
    start = rx.Structure(phases=[ortho(_along_minus_a(3.4))])
    start.phases[0].scale.value = scale
    return start


def test_a_fit_that_winds_its_azimuth_reports_it_in_the_chart_with_the_same_esds(
        monkeypatch):
    """The issue's first pattern: before #604 this fit ended at φ = 53.33 rad.
    The move is the last stage's commit, so the solve is the same one: every
    other value is bit-identical, every esd agrees, and the angle differs by
    whole turns.  Rwp is evaluated at the moved angle, whose cos and sin round
    differently, so it agrees to rounding and not to the bit (1 ulp on Linux
    x86-64, bit-identical on darwin/arm64, measured)."""
    data, scale = _pattern(_along_minus_a(3.5), 700)
    fitted = rx.Refinement(_start(scale), INS).fit(data, plan=_plan())
    monkeypatch.setattr(ParameterTable, "_canonicalise_moment_dofs",
                        lambda self: None)
    unmoved = rx.Refinement(_start(scale), INS).fit(data, plan=_plan())
    a = {p.path: p for p in fitted.parameters}
    b = {p.path: p for p in unmoved.parameters}
    assert a.keys() == b.keys()
    assert not -np.pi < b[AZIMUTH_2D].value <= np.pi    # the defect, reproduced
    assert -np.pi < a[AZIMUTH_2D].value <= np.pi
    turns = (b[AZIMUTH_2D].value - a[AZIMUTH_2D].value) / (2 * np.pi)
    assert turns == pytest.approx(round(turns), abs=1e-9) and round(turns) != 0
    for path in a:
        assert a[path].stderr == pytest.approx(b[path].stderr, rel=1e-9), path
        if path != AZIMUTH_2D:
            assert a[path].value == b[path].value, path
    assert fitted.statistics.rwp == pytest.approx(unmoved.statistics.rwp, rel=1e-12)


@pytest.mark.slow
def test_a_series_on_the_cut_gives_no_finding_and_every_angle_in_the_chart():
    """The issue's reproduction end to end, both directions: the moment along
    −a only shrinks, and nothing about it may read as a jump, a path
    dependence or a persistent finding.  Before #604: "dof1 steps by 50.2",
    "1167.3σ"."""
    temps = [10, 20, 30, 40, 50, 60, 70]
    patterns, scale = [], None
    for i, m in enumerate(np.linspace(3.5, 2.5, len(temps))):
        data, s = _pattern(_along_minus_a(m), 700 + i, scale)
        scale = scale or s
        patterns.append(data)
    series = rx.refine_sequential(patterns, _start(scale), INS, plan=_plan(),
                                  x=temps, x_label="T (K)", direction="both")
    moment = [d for d in series.diagnostics
              if d.code.startswith("SEQUENTIAL_") and any(".moment." in w
                                                           for w in d.where)]
    assert moment == []
    for chain in (series, series.backward):
        for entry in chain.entries:
            by = {p.path: p.value for p in entry.parameters}
            assert by[f"{BASE}.moment.dof0"] >= 0.0
            assert -np.pi < by[AZIMUTH_2D] <= np.pi
