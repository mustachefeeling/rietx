"""Additive background peaks: an explicit broad Gaussian beside the background.

The feature is three parameters (position, height, width) summed on top of
whichever :data:`~rietx.schemas.instrument.Background` model is in use, and
almost every test here exists because one of those three could be wrong in a way
nothing else would notice:

* the empty default has to be **exactly** off, not approximately (the
  ``restraints``/``microstrain``/``surface_roughness`` idiom);
* the paths have to be registered in ``_collect_instrument`` **and** written back
  in ``apply_to_models``, or a refined hump silently reverts at the next stage;
* the peak paths must stay out of ``bkg_paths``, whose branch of
  ``_make_jacobian`` claims an exact linear column;
* the whole-model FD column has to be the *declared* fallback, and exact —
  including on the rows it never writes;
* and the width bound is the feature's physical content, not a numerical
  guard: a free position/height/width is a Bragg peak with no cell behind it,
  and enough of those improve any Rwp.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

import rietx as rx
from rietx.background.models import background_peak_curve
from rietx.io.exporters import _background_description
from rietx.io.instrument_profile import save_instrument_profile
from rietx.model.forward import compile_model
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.optimize.statistics import _span_basis, background_absorption
from rietx.params.vector import ParameterTable, background_peak_parameters
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import (
    BACKGROUND_PEAK_FIELDS,
    BACKGROUND_PEAK_FWHM_MIN,
    BackgroundChebyshev,
    BackgroundPeak,
    BackgroundPSpline,
    Instrument,
)
from rietx.schemas.pattern import PatternData
from rietx.strategy.staged import (
    BACKGROUND_PEAK_MIN_WIDTH_MULT,
    PLAN_PRESETS,
    check_background_peak_width,
)
from tests.test_schemas import make_lab6

WAVELENGTH = 1.5405929
PEAK_PATHS = tuple(f"instrument.background_peaks.0.{n}"
                   for n in BACKGROUND_PEAK_FIELDS)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _peak(position=32.0, height=400.0, fwhm=7.0, *, vary=True) -> BackgroundPeak:
    return BackgroundPeak(
        label="hump",
        position=Parameter(value=position, unit="deg", vary=vary),
        height=Parameter(value=height, min=0.0, unit="counts",
                         transform="softplus", vary=vary),
        fwhm=Parameter(value=fwhm, min=BACKGROUND_PEAK_FWHM_MIN, unit="deg",
                       transform="softplus", vary=vary))


def _instrument(*, peaks=(), background=None) -> Instrument:
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.source.dispersion = None      # declined, never inherited
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3
    if background is not None:
        ins.background = background
    ins.background_peaks = list(peaks)
    return ins


def _state(*, peaks=(), background=None, free=PEAK_PATHS, lo=15.0, hi=110.0,
           step=0.05):
    """A compiled LaB6 model over a flat pattern, with ``free`` freed."""
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = _instrument(peaks=peaks, background=background)
    tt = np.arange(lo, hi, step)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=(np.full_like(tt, 200.0)).tolist())
    table = ParameterTable(structure, ins)
    if free:
        table.set_vary(list(free), True)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return structure, ins, data, table, model


# ----------------------------------------------------------------------
# the empty default is exactly off
# ----------------------------------------------------------------------
def test_the_empty_default_is_byte_identical_to_no_field_at_all():
    """The ``restraints``/``microstrain``/``surface_roughness`` idiom, pinned.

    Two halves, because "off" has to hold in both directions: the serialized
    instrument differs from a pre-``background_peaks`` one by exactly the empty
    list, and the parameter table it produces is unchanged.
    """
    ins = _instrument()
    dumped = ins.model_dump(mode="json")
    assert dumped["background_peaks"] == []
    without = {k: v for k, v in dumped.items() if k != "background_peaks"}
    assert json.loads(json.dumps(without)) == without   # nothing else moved

    table = ParameterTable(make_lab6(), ins)
    assert not [e.path for e in table.entries if "background_peaks" in e.path]
    assert background_peak_parameters(ins.background_peaks) == []


def test_a_declared_peak_at_zero_height_leaves_the_background_bit_identical():
    """``height`` may take ``min=0.0`` under softplus because zero *is* the off
    state — so this is the promise that bound is allowed to make."""
    _s, _i, _d, table_off, model_off = _state(peaks=(), free=())
    _s, _i, _d, table_on, model_on = _state(
        peaks=(_peak(height=0.0, vary=False),), free=())
    off = np.asarray(model_off.background(table_off.decode(table_off.x0())))
    on = np.asarray(model_on.background(table_on.decode(table_on.x0())))
    assert model_on.bkg_peak_paths and not model_off.bkg_peak_paths
    assert np.array_equal(off, on)          # bit-identical, not allclose


# ----------------------------------------------------------------------
# the schema
# ----------------------------------------------------------------------
def test_json_round_trip_keeps_every_peak_parameter():
    ins = _instrument(peaks=(_peak(), _peak(position=70.0, height=10.0)))
    back = Instrument.model_validate(json.loads(ins.model_dump_json()))
    assert len(back.background_peaks) == 2
    assert back.background_peaks[1].position.value == 70.0
    assert back.background_peaks[0].label == "hump"
    assert back.background_peaks[0].fwhm.transform == "softplus"


def test_a_stored_zero_width_bound_is_repaired_rather_than_deserialized():
    """The ``MARCH_R_MIN`` precedent: the broken bound outlives the default.

    A project or history node written with ``min: 0.0`` would otherwise come
    back with a reachable zero width, and the Gaussian divides by it.
    """
    peak = BackgroundPeak.model_validate({
        "position": {"value": 20.0},
        "height": {"value": 1.0, "min": 0.0, "transform": "softplus"},
        "fwhm": {"value": 0.0, "min": 0.0, "transform": "softplus"}})
    assert peak.fwhm.min == BACKGROUND_PEAK_FWHM_MIN
    assert peak.fwhm.value == BACKGROUND_PEAK_FWHM_MIN
    # a caller's own positive bound is left alone
    kept = BackgroundPeak.model_validate({
        "position": {"value": 20.0},
        "height": {"value": 1.0, "min": 0.0, "transform": "softplus"},
        "fwhm": {"value": 3.0, "min": 1.0, "transform": "softplus"}})
    assert kept.fwhm.min == 1.0


def test_the_curve_is_a_gaussian_of_the_declared_fwhm():
    """Half height at ±Γ/2 — the property the −4 ln2 constant exists for."""
    xp = rx.backend.get_backend()
    tt = np.array([32.0 - 3.5, 32.0, 32.0 + 3.5], dtype=np.float64)
    y = np.asarray(background_peak_curve(tt, 32.0, 400.0, 7.0, xp))
    assert y[1] == pytest.approx(400.0, rel=1e-15)
    assert y[0] == pytest.approx(200.0, rel=1e-12)
    assert y[2] == pytest.approx(200.0, rel=1e-12)


def test_the_peak_lands_at_its_declared_position_on_the_fit_grid():
    _s, _i, _d, table, model = _state(peaks=(_peak(),), free=())
    y = np.asarray(model.background(table.decode(table.x0())))
    assert model.tt[int(np.argmax(y))] == pytest.approx(32.0, abs=0.05)


# ----------------------------------------------------------------------
# table wiring — the pair that silently loses a refined value
# ----------------------------------------------------------------------
def test_both_halves_of_the_table_know_the_peak_paths():
    _s, ins, _d, table, _m = _state(peaks=(_peak(),))
    assert set(PEAK_PATHS) <= set(table.free_paths)
    # the helper is the one authority both sides read
    assert [sub for sub, _p in background_peak_parameters(ins.background_peaks)] \
        == [f"0.{n}" for n in BACKGROUND_PEAK_FIELDS]


def test_a_refined_peak_survives_a_stage_boundary():
    """``_collect_instrument`` and ``apply_to_models`` must both know the paths.

    This is the test ``params/vector.py``'s own comment asks for: a parameter
    registered in one and forgotten in the other loses its refined value at the
    next recompile, silently, and the file says it has been bitten before.
    """
    structure, ins, _d, table, _m = _state(peaks=(_peak(),))
    for path, value in zip(PEAK_PATHS, (41.0, 555.0, 9.5), strict=True):
        table.entries[table._paths[path]].value = value
    table.apply_to_models(structure, ins)

    peak = ins.background_peaks[0]
    assert (peak.position.value, peak.height.value, peak.fwhm.value) \
        == (41.0, 555.0, 9.5)
    # and the rebuilt table — what the next stage compiles from — agrees
    rebuilt = ParameterTable(structure, ins)
    values = {e.path: e.value for e in rebuilt.entries}
    assert [values[p] for p in PEAK_PATHS] == [41.0, 555.0, 9.5]


# ----------------------------------------------------------------------
# the linear block, and the Jacobian's declared reach
# ----------------------------------------------------------------------
def test_peak_paths_never_join_the_linear_background_block():
    """``bkg_paths`` names a block ``_make_jacobian`` claims an *exact* column
    for, on the grounds that y is linear in it.  A peak is not."""
    for background in (BackgroundChebyshev.with_terms(5),
                       BackgroundPSpline.for_range(15.0, 110.0,
                                                   knot_step_deg=8.0)):
        _s, _i, _d, _t, model = _state(peaks=(_peak(),), background=background)
        peak_paths = {p for triple in model.bkg_peak_paths for p in triple}
        assert peak_paths and set(model.bkg_paths).isdisjoint(peak_paths)


@pytest.mark.parametrize("path", PEAK_PATHS)
def test_no_analytic_branch_claims_a_peak_path(path):
    """The FD fallback is declared, not discovered (WP-1070's failure mode)."""
    _s, _i, _d, _t, model = _state(peaks=(_peak(),))
    assert model.scalar_chain_supported(path) is False


def test_the_fd_column_is_exact_where_the_check_is_exact():
    """Each peak column against a hand-written derivative, not against another FD.

    The whole-model FD is the right *fallback* and the wrong *reference*
    (CLAUDE.md § Invariants), so the oracle here is the analytic derivative of
    the Gaussian chained through the transform.  ``height`` is the exact arm:
    y is **linear** in h, so the physical-space difference quotient has no
    truncation error and the bar is tight.  ``position`` and ``fwhm`` are
    nonlinear, so the FD column carries O(h) curvature and the bar says so.
    """
    _s, _i, _d, table, model = _state(peaks=(_peak(),))
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    values = table.decode(theta)
    free = list(table.free_paths)
    sqrt_w = 1.0 / model.sigma
    n_data = len(model.tt)

    tt = model.tt
    pos = values[PEAK_PATHS[0]]
    height = values[PEAK_PATHS[1]]
    fwhm = values[PEAK_PATHS[2]]
    u = (tt - pos) / fwhm
    curve = height * np.exp(-4.0 * np.log(2.0) * u * u)

    from rietx.params.transforms import dphys_dinternal

    def dpdu(path):
        e = table.entries[table._paths[path]]
        return dphys_dinternal(float(theta[free.index(path)]), e.transform)

    expect = {
        # ∂/∂2θ₀ = +8 ln2 · u/Γ · curve
        PEAK_PATHS[0]: 8.0 * np.log(2.0) * u / fwhm * curve,
        PEAK_PATHS[1]: curve / height,
        # ∂/∂Γ = +8 ln2 · u²/Γ · curve
        PEAK_PATHS[2]: 8.0 * np.log(2.0) * u * u / fwhm * curve,
    }
    bars = {PEAK_PATHS[0]: 2e-5, PEAK_PATHS[1]: 1e-9, PEAK_PATHS[2]: 2e-5}
    for path, dy in expect.items():
        col = jac[:n_data, free.index(path)]
        # the residual is (y_obs − y_calc)/σ, hence the minus sign
        truth = -sqrt_w * dy * dpdu(path)
        scale = np.max(np.abs(truth))
        assert np.max(np.abs(col - truth)) <= bars[path] * scale, path


def test_a_peak_column_is_exactly_zero_on_every_row_below_the_data():
    """Why writing only the data rows is *exact* rather than short.

    A P-spline background carries penalty rows √λ·D₂·c in the background
    *coefficients*; a peak parameter moves none of them, so the rows the FD
    leaves at their zero initialisation are the rows whose true value is zero.
    """
    _s, _i, _d, table, model = _state(
        peaks=(_peak(),),
        background=BackgroundPSpline.for_range(15.0, 110.0, knot_step_deg=8.0),
        free=(*PEAK_PATHS, "instrument.background.c3"))
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    n_data = len(model.tt)
    assert jac.shape[0] > n_data, "the P-spline penalty rows are the point"
    free = list(table.free_paths)
    for path in PEAK_PATHS:
        assert np.array_equal(jac[n_data:, free.index(path)],
                              np.zeros(jac.shape[0] - n_data))
    # and the coefficient column beside it is *not* zero there, so the test
    # above is not passing because the block is empty
    assert np.any(jac[n_data:, free.index("instrument.background.c3")])


def test_the_residual_sees_the_peak():
    """A sanity floor under the Jacobian tests: the term reaches the residual."""
    _s, _i, _d, table, model = _state(peaks=(_peak(),))
    theta = table.x0()
    r = np.asarray(_make_residual(model, table)(theta))
    lowered = theta.copy()
    lowered[list(table.free_paths).index(PEAK_PATHS[1])] -= 1.0
    assert not np.array_equal(r, np.asarray(
        _make_residual(model, table)(lowered)))


# ----------------------------------------------------------------------
# the width guard — the feature's physical content
# ----------------------------------------------------------------------
def test_a_broad_peak_trips_nothing_and_a_narrow_one_is_reported():
    _s, _i, _d, table, model = _state(peaks=(_peak(fwhm=7.0),))
    assert check_background_peak_width(table, model) == []

    values = {e.path: e.value for e in table.entries}
    gamma = float(model.instrument_fwhm_deg(values[PEAK_PATHS[0]], values))
    assert 7.0 / gamma > BACKGROUND_PEAK_MIN_WIDTH_MULT

    narrow = 0.5 * BACKGROUND_PEAK_MIN_WIDTH_MULT * gamma
    table.entries[table._paths[PEAK_PATHS[2]]].value = narrow
    findings = check_background_peak_width(table, model)
    assert [f.code for f in findings] == ["BACKGROUND_PEAK_TOO_NARROW"]
    assert findings[0].paths == (PEAK_PATHS[2],)
    assert findings[0].value == pytest.approx(narrow / gamma)
    assert "instrumental" in str(findings[0])


def test_the_guard_is_silent_without_a_model_or_without_peaks():
    """The ``check_stephens_positive`` convention: no model, no claim."""
    _s, _i, _d, table, model = _state(peaks=())
    assert check_background_peak_width(table, model) == []
    assert check_background_peak_width(table, None) == []


def test_the_width_bound_is_measured_against_the_instrument_alone():
    """Γ_inst must not depend on which phase one asks about — the question is
    how narrow a *real* reflection can be at that angle."""
    structure, ins, data, table, model = _state(peaks=(_peak(),))
    values = {e.path: e.value for e in table.entries}
    before = float(model.instrument_fwhm_deg(32.0, values))
    structure.phases[0].lor_size.value = 0.4     # heavy sample broadening
    table2 = ParameterTable(structure, ins)
    model2 = compile_model(structure, ins, data, mode="rietveld")
    after = float(model2.instrument_fwhm_deg(
        32.0, {e.path: e.value for e in table2.entries}))
    assert after == pytest.approx(before, rel=1e-15)


# ----------------------------------------------------------------------
# the absorption block, and the span it is built from
# ----------------------------------------------------------------------
def test_a_softplus_off_state_does_not_by_itself_make_a_zero_column():
    """Why the ``_span_basis`` filter changes nothing that shipped before it.

    ``to_internal`` clamps, so a softplus parameter at its own off state has a
    tiny-but-real derivative rather than none, and no design row is zero either.
    An exactly-zero column comes from a **product** — a peak at zero height —
    which is what the filter is for.
    """
    from rietx.params.transforms import dphys_dinternal, to_internal

    u = to_internal(0.0, "softplus")
    assert np.isfinite(u) and dphys_dinternal(u, "softplus") > 0.0

    _s, _i, _d, _t, model = _state(
        peaks=(),
        background=BackgroundPSpline.for_range(15.0, 110.0, knot_step_deg=8.0),
        free=())
    assert all(np.any(row) for row in model.bkg_design)

    # the product, which is exactly zero: h = 0 kills ∂y/∂2θ₀ and ∂y/∂Γ
    _s, _i, _d, table, model = _state(peaks=(_peak(height=0.0),))
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    free = list(table.free_paths)
    n_data = len(model.tt)
    for path in (PEAK_PATHS[0], PEAK_PATHS[2]):
        assert not np.any(jac[:n_data, free.index(path)]), path


def test_a_zero_column_is_dropped_from_a_projection_span():
    """LAPACK's Q is orthonormal whatever the rank of A, so a zero column of A
    becomes an arbitrary direction and saturates every R² at 1."""
    jac = np.zeros((6, 4))
    jac[:, 0] = [1.0, 1.0, 0.0, 0.0, 0.0, 0.0]      # the only real column
    jac[:, 3] = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0]      # the target
    assert _span_basis(jac, [0, 1, 2]).shape == (6, 1)
    r2 = background_absorption(jac, ["instrument.background.c0",
                                     "instrument.background_peaks.0.position",
                                     "instrument.background_peaks.0.fwhm",
                                     "phases.0.scale"])
    assert r2["phases.0.scale"] == pytest.approx(0.0, abs=1e-12)
    # all-zero block: the projector is zero, i.e. "imitates nothing"
    assert _span_basis(np.zeros((6, 2)), [0, 1]).shape == (6, 0)


def test_peak_columns_join_the_background_block():
    """The statistic asks what the *whole declared background* can imitate."""
    jac = np.zeros((5, 2))
    jac[:, 0] = [1.0, 0.0, 0.0, 0.0, 0.0]
    jac[:, 1] = [1.0, 1.0, 0.0, 0.0, 0.0]
    with_peak = background_absorption(
        jac, ["instrument.background_peaks.0.height", "phases.0.scale"])
    without = background_absorption(jac, ["instrument.profile.w",
                                          "phases.0.scale"])
    assert with_peak["phases.0.scale"] == pytest.approx(0.5)
    assert without == {}       # no background column at all, nothing to project


# ----------------------------------------------------------------------
# the surfaces
# ----------------------------------------------------------------------
def test_the_structural_plan_can_free_a_declared_peak_and_nothing_else():
    globs = [g for stage in PLAN_PRESETS["mccusker_structural"]().stages
             for g in stage.turn_on]
    assert "instrument.background_peaks.*" in globs

    # declared: the glob frees exactly the three
    _s, _i, _d, table, _m = _state(peaks=(_peak(vary=False),), free=())
    before = set(table.free_paths)
    table.set_vary(["instrument.background_peaks.*"], True)
    assert set(table.free_paths) - before == set(PEAK_PATHS)

    # not declared: the same glob frees nothing, which is what makes the stage
    # safe in a plan that runs against instruments with no hump
    _s, _i, _d, empty, _m = _state(peaks=(), free=())
    unchanged = set(empty.free_paths)
    empty.set_vary(["instrument.background_peaks.*"], True)
    assert set(empty.free_paths) == unchanged


def test_no_plan_and_no_estimator_ever_adds_a_peak():
    """The model may not grow its own free peaks — that is the whole safety
    property of a term whose three parameters improve any Rwp."""
    for build in PLAN_PRESETS.values():
        for stage in build().stages:
            for glob in stage.turn_on:
                assert "background_peaks" not in glob or glob.endswith(".*")
    tt = np.arange(10.0, 90.0, 0.05)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=(200.0 + 400.0 * np.exp(
                           -0.5 * ((tt - 25.0) / 6.0) ** 2)).tolist())
    for kind in ("chebyshev", "pspline"):
        bkg = rx.auto_background(data, kind=kind, wavelength=WAVELENGTH)
        assert not hasattr(bkg, "background_peaks")


def test_the_cif_description_and_the_instrument_profile_both_say_so():
    ins = _instrument(peaks=(_peak(),))
    assert "1 explicit Gaussian background peak" in _background_description(ins)
    two = _instrument(peaks=(_peak(), _peak(position=70.0)))
    assert "2 explicit Gaussian background peaks" in _background_description(two)
    assert "background peak" not in _background_description(_instrument())


# ----------------------------------------------------------------------
# the claim, on a synthetic case whose truth is known
# ----------------------------------------------------------------------
#: The synthetic hump, in the shape of the case the feature was built for: a
#: constant-wavelength neutron pattern with ~0.3° lines and a 5.8°-wide feature
#: near 14.4° 2θ, which on that instrument is ~20× the resolution.  Truth, so a
#: test can ask whether it comes back rather than whether Rwp fell.
HUMP_TRUTH = {"position": 14.4, "height": 90.0, "fwhm": 5.8}
HUMP_BISO = 0.35


def synthetic_hump_case():
    """``(data, structure, instrument_without_peak, truth)`` for the hump case.

    A **generator** as well as a fixture: ``docs/manual/make_figures.py``
    imports this so the committed figure and the assertion below draw the same
    case.  A figure with its own copy of a case can disagree with the test that
    proves the claim, and nobody would find out (that script's own rule).

    The instrument returned declares **no** peak — the two fits differ by
    exactly that, which is what makes the comparison mean anything.
    """
    structure = make_lab6()
    phase = structure.phases[0]
    phase.scale.value = 4e-4
    for atom in phase.atoms:
        atom.biso.value = HUMP_BISO
    ins = rx.Instrument.constant_wavelength_neutron(2.078, fwhm_deg=0.30)
    ins.background = BackgroundChebyshev.with_terms(4)

    tt = np.arange(6.0, 120.0, 0.05)
    grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, grid, mode="rietveld")
    xp = rx.backend.get_backend()
    y = (np.asarray(model.evaluate(table.decode(table.x0())))
         + 900.0 - 1.2 * model.tt
         + np.asarray(background_peak_curve(
             model.tt, HUMP_TRUTH["position"], HUMP_TRUTH["height"],
             HUMP_TRUTH["fwhm"], xp)))
    rng = np.random.default_rng(11)
    data = PatternData(
        two_theta=model.tt.tolist(),
        intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())
    return data, structure, ins, dict(HUMP_TRUTH)


def fit_hump_case(*, with_peak: bool):
    """One arm of the comparison: the same case with and without the peak."""
    data, structure, ins, truth = synthetic_hump_case()
    if with_peak:
        ins.background_peaks = [_peak(position=13.0, height=30.0, fwhm=5.0,
                                      vary=False)]
    plan = PLAN_PRESETS["mccusker_structural"]()
    return rx.refine(data, structure, ins, plan=plan), truth


@pytest.mark.xdist_group("background-peak-hump")
def test_a_known_hump_comes_back_within_its_esds():
    """The record field, not Rwp, is the evidence (root CLAUDE.md).

    The peak is seeded 1.4° off and 0.8° narrow, so this asks whether the three
    parameters *find* a feature whose truth is known — the claim the feature
    actually makes.  It deliberately does **not** assert that the structural
    parameters improve: on this fixture they are not determined well enough to
    carry such a claim (scale esd 209 on a value of 0.046), and the real-data
    measurement in `docs/manual/using/data.md` reports what happened there,
    including where it did not go the expected way.
    """
    result, truth = fit_hump_case(with_peak=True)
    got = {row.path.rsplit(".", 1)[1]: row for row in result.parameters
           if "background_peaks" in row.path}
    assert set(got) == set(BACKGROUND_PEAK_FIELDS)
    for name in ("position", "fwhm", "height"):
        row = got[name]
        assert row.stderr is not None and row.stderr > 0.0, name
        assert abs(row.value - truth[name]) <= 2.0 * row.stderr, (
            f"{name}: {row.value} vs truth {truth[name]} ± {row.stderr}")
    assert not [d for d in result.diagnostics
                if d.code == "BACKGROUND_PEAK_TOO_NARROW"]
    assert result.identifiability.n_background_peaks == 1


@pytest.mark.xdist_group("background-peak-hump")
def test_the_declared_count_reaches_the_record_and_the_report():
    """A projection, not a second count — the two must never disagree."""
    from rietx.report import build_report

    result, _truth = fit_hump_case(with_peak=True)
    assert result.identifiability.n_background_peaks == 1
    assert build_report(result).background.n_peaks == 1

    none, _truth = fit_hump_case(with_peak=False)
    assert none.identifiability is None \
        or none.identifiability.n_background_peaks == 0


def test_save_instrument_profile_strips_the_peaks(tmp_path):
    """A hump belongs to this specimen and this sample environment, so carrying
    one into the next sample would put a free peak where nothing measured."""
    path = tmp_path / "profile.json"
    save_instrument_profile(_instrument(peaks=(_peak(),)), path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert "background_peaks" not in doc["instrument"]
    assert rx.load_instrument_profile(path).background_peaks == []
