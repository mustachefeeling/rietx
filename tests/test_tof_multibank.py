"""Several banks, one structure: the joint fit admits time of flight (T-5).

A time-of-flight experiment is not several experiments — it is several detector
banks of one sample, each with its own DIFC/TZERO, angle, resolution and
channel width, and one structure.  This file is the rung where
:class:`~rietx.multi.MultiHistogramRefinement` takes that list: two banks
jointly, a bank beside a constant-wavelength histogram, and the four things
that must not happen (a shared per-bank quantity, a width scaled by a
wavelength a bank has not got, microseconds in a member called ``two_theta``,
and a crossed pair passing).

**Every fixture is synthetic and written here.**  No line of any real
instrument file enters this repository: the banks below are a plausible 90°
and 150° pair with round constants, and each pattern is generated from the
model it is then refined against.

The constant-wavelength arm must not move by one bit while this lands.  That is
pinned three ways: the existing joint goldens in
:mod:`tests.test_multi_histogram` are untouched;
:func:`test_a_constant_wavelength_joint_fit_compiles_the_same_objects` checks
the compile; and
:func:`test_the_cw_block_of_a_mixed_fit_is_the_single_histogram_jacobian`
hashes a mixed fit's constant-wavelength Jacobian block against the block a
single-histogram compile builds.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

import rietx as rx
from rietx.params.multi import MultiParameterTable, SharingMap
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import BackgroundChebyshev, ProfileTOF
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import Atom, Cell, Phase, Structure

# ----------------------------------------------------------------------
# the two synthetic banks and the constant-wavelength histogram
# ----------------------------------------------------------------------
#: The generating cell — silicon's, near enough to be recognisable and taken
#: from no certificate: nothing here is compared against one.
A_GEN = 5.4311946

#: ``(difc, tzero, two_theta_bank_deg, profile overrides, window, step, seed)``
#: for the two banks.  They differ in every per-bank quantity there is, which
#: is what makes "nothing per-bank is shared" a test rather than a hope.
BANK_90 = dict(difc=12000.0, tzero=-5.0, two_theta=90.0)
BANK_150 = dict(difc=15500.0, tzero=3.0, two_theta=150.0,
                alpha1=0.35, beta0=0.040, sig1=180.0)
GRID_90 = (8000.0, 45000.0, 5.0)
GRID_150 = (10000.0, 52000.0, 6.0)

#: How far out the fits start: 0.5 % on the cell, 20 µs on each TZERO, 2x on
#: the scale — the same displacement ``tests.test_tof_refine`` starts from, so
#: the single-bank and joint arms are comparable.
CELL_OFFSET, TZERO_OFFSET, SCALE_START = 1.005, -20.0, 6.0

CW_LAMBDA = 1.5406


def silicon(a: float = A_GEN) -> Structure:
    """Si, Fd-3m:2, one atom on 8a — no free coordinate, one Biso."""
    return Structure(phases=[Phase(
        name="Si", space_group="F d -3 m :2",
        cell=Cell(a=P(value=a), b=P(value=a), c=P(value=a),
                  alpha=P(value=90.0), beta=P(value=90.0),
                  gamma=P(value=90.0)),
        scale=P(value=1.0, min=0.0, transform="softplus"),
        atoms=[Atom(label="Si", species="Si", x=P(value=0.125),
                    y=P(value=0.125), z=P(value=0.125),
                    biso=P(value=0.5, min=0.0, max=5.0))])])


def bank(*, difc: float, tzero: float, two_theta: float, n_background: int = 4,
         **profile) -> rx.Instrument:
    """One synthetic bank with a Chebyshev background."""
    coeffs = dict(alpha1=0.45, beta0=0.055, beta1=0.003, sig1=300.0)
    coeffs.update(profile)
    ins = rx.Instrument.tof_neutron_bank(
        difc=difc, tzero=tzero, two_theta_bank_deg=two_theta,
        profile=ProfileTOF(**{k: P(value=v, unit=None)
                              for k, v in coeffs.items()}))
    ins.background = BackgroundChebyshev(
        coefficients=[P(value=0.0) for _ in range(n_background)])
    return ins


def cw_instrument(wavelength: float = CW_LAMBDA,
                  n_background: int = 4) -> rx.Instrument:
    ins = rx.Instrument.debye_scherrer(wavelength=wavelength)
    ins.background = BackgroundChebyshev(
        coefficients=[P(value=0.0) for _ in range(n_background)])
    ins.profile.u.value, ins.profile.v.value = 0.02, -0.01
    ins.profile.w.value = 0.008
    return ins


def _poisson_from(model, structure, instrument, seed: int) -> np.ndarray:
    table = ParameterTable(structure, instrument)
    y = np.asarray(model.evaluate(table.decode(table.x0())), dtype=np.float64)
    return np.random.default_rng(seed).poisson(
        np.maximum(y, 0.0)).astype(np.float64)


def tof_pattern(ins: rx.Instrument, grid: tuple[float, float, float], *,
                seed: int, scale: float = 12.0,
                background=(40.0, -8.0)) -> PatternData:
    """A bank generated from the model it will be refined against.

    ``intensity_basis="counts"`` throughout: that is what a LANSCE ``TIME_MAP``
    bank and a Mantid ``SaveGSS`` export declare, so the channel-width factor is
    in both the generating model and the fitted one.  Poisson noise on the
    compiled curve, so χ² ≈ 1 is a real bar rather than a coincidence.
    """
    from rietx.model.forward_tof import compile_tof_model

    lo, hi, step = grid
    x = np.arange(lo, hi + 0.5 * step, step)
    blank = PatternData(tof=x.tolist(), intensity=[1.0] * len(x),
                        intensity_basis="counts")
    gen = ins.model_copy(deep=True)
    for k, v in enumerate(background):
        gen.background.coefficients[k].value = v
    structure = silicon()
    structure.phases[0].scale.value = scale
    y = _poisson_from(compile_tof_model(structure, gen, blank), structure, gen,
                      seed)
    return PatternData(tof=x.tolist(), intensity=y.tolist(),
                       intensity_basis="counts")


def cw_pattern(ins: rx.Instrument, *, seed: int, lo: float = 15.0,
               hi: float = 120.0, step: float = 0.02, scale: float = 0.05,
               background=(40.0, -5.0)) -> PatternData:
    """The constant-wavelength histogram of the same specimen.

    ``scale`` is small deliberately.  A frozen peak window is cut around each
    reflection, and the generating compile (which knows nothing is about to
    move) cuts a slightly different one from the fit's; on a 10⁷-count peak the
    one-channel difference at the tail is a 600σ step, which is a statement
    about this fixture and not about any joint fit.  At 3 × 10⁴ counts it is
    under one σ, which is what a synthetic pattern is supposed to be.
    """
    from rietx.model.forward import compile_model

    x = np.arange(lo, hi + 0.5 * step, step)
    blank = PatternData(two_theta=x.tolist(), intensity=[1.0] * len(x))
    gen = ins.model_copy(deep=True)
    for k, v in enumerate(background):
        gen.background.coefficients[k].value = v
    structure = silicon()
    structure.phases[0].scale.value = scale
    y = _poisson_from(compile_model(structure, gen, blank), structure, gen, seed)
    return PatternData(two_theta=x.tolist(), intensity=y.tolist())


def started_bank(**gen) -> rx.Instrument:
    """The bank as the fit starts from it: TZERO 20 µs out, nothing else."""
    off = dict(gen)
    off["tzero"] = gen["tzero"] + TZERO_OFFSET
    return bank(**off)


def started_structure() -> Structure:
    s = silicon(a=A_GEN * CELL_OFFSET)
    s.phases[0].scale.value = SCALE_START
    return s


def joint_plan(*, cw: bool = False) -> rx.RefinementPlan:
    """The brief's plan: per-bank scale/background/TZERO free, cell shared.

    The profile stays at its calibrated values, which is what a bank standard
    is for and what keeps the arm honest: with the widths free as well,
    ``phases.0.cell.a`` and ``instrument.source.profile_tof.alpha1`` correlate
    at ρ = −0.9998 on the 90° bank (α is a rise rate, and a rise rate moves a
    centroid), and the esd this arm compares would be measuring that
    degeneracy rather than the joint gain.
    """
    calibration = ["instrument.source.tzero"]
    if cw:
        # the constant-wavelength histogram's own counterpart, per histogram —
        # the banks force-fix it, so this frees exactly one copy
        calibration.append("instrument.zero_shift")
    return rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("calibration", calibration),
        rx.Stage("cell", ["phases.*.cell.a"]),
        rx.Stage("displacement", ["phases.*.atoms.*.biso"]),
    ])


@pytest.fixture(scope="module")
def patterns() -> list[PatternData]:
    return [tof_pattern(bank(**BANK_90), GRID_90, seed=1),
            tof_pattern(bank(**BANK_150), GRID_150, seed=2),
            cw_pattern(cw_instrument(), seed=3)]


@pytest.fixture(scope="module")
def two_bank_fit(patterns):
    """The committed acceptance: two synthetic banks of one Si cell."""
    ref = rx.MultiHistogramRefinement(
        started_structure(),
        [started_bank(**BANK_90), started_bank(**BANK_150)])
    return ref, ref.fit(patterns[:2], plan=joint_plan())


@pytest.fixture(scope="module")
def single_bank_esds(patterns):
    """esd(a) from refining each bank alone, for the joint-vs-single check."""
    out = []
    for gen, data in ((BANK_90, patterns[0]), (BANK_150, patterns[1])):
        res = rx.Refinement(started_structure(), started_bank(**gen),
                            history=False).fit(data, plan=joint_plan())
        out.append(res.parameter("phases.0.cell.a").stderr)
    return out


@pytest.fixture(scope="module")
def mixed_fit(patterns):
    """Two banks and a constant-wavelength histogram of the same structure."""
    ref = rx.MultiHistogramRefinement(
        started_structure(),
        [started_bank(**BANK_90), started_bank(**BANK_150), cw_instrument()])
    return ref, ref.fit(patterns, plan=joint_plan(cw=True))


# ----------------------------------------------------------------------
# 1. two banks, one structure
# ----------------------------------------------------------------------
def test_two_banks_refine_one_cell_better_than_either_alone(two_bank_fit,
                                                            single_bank_esds):
    """The positive arm, and the whole point of the rung.

    Two banks are two measurements of one quantity, so the joint esd must beat
    both — and by the amount two independent measurements combine by, which is
    the check that says the joint residual is stacked rather than that one
    histogram won.
    """
    _ref, result = two_bank_fit
    assert result.status == "converged"
    a = result.parameter("phases.0.cell.a")
    assert a.stderr is not None and a.stderr > 0.0
    assert abs(a.value - A_GEN) < 3.0 * a.stderr

    assert a.stderr < min(single_bank_esds), (a.stderr, single_bank_esds)
    combined = 1.0 / np.sqrt(sum(1.0 / e ** 2 for e in single_bank_esds))
    assert a.stderr == pytest.approx(combined, rel=0.15)


def test_each_bank_keeps_its_own_calibration(two_bank_fit):
    """Per-bank stays per-bank.  Both TZEROs started 20 µs out, in the same
    direction, and each comes back at *its own* generating value — which two
    numbers sharing one column could not do."""
    _ref, result = two_bank_fit
    for h, gen in enumerate((BANK_90, BANK_150)):
        row = result.parameter(f"hist.{h}.instrument.source.tzero")
        assert abs(row.value - gen["tzero"]) < 1.0, (h, row.value)
    t0 = result.parameter("hist.0.instrument.source.tzero").value
    t1 = result.parameter("hist.1.instrument.source.tzero").value
    assert abs(t0 - t1) > 5.0
    # …and there is no unscoped (shared) row for a per-bank quantity at all
    shared = {r.path for r in result.parameters if not r.path.startswith("hist.")}
    assert not any(".source." in p or ".background." in p or p.endswith(".scale")
                   for p in shared), sorted(shared)


def test_a_bank_histogram_carries_microseconds_and_never_two_theta(two_bank_fit):
    """The T-1 fence, at the one member that could break it on this path.

    ``multi.py`` wrote ``two_theta=model.tt.tolist()`` unconditionally until
    this rung; the line was unreachable only because the class refused a bank.
    """
    _ref, result = two_bank_fit
    for h in range(2):
        hist = result.histograms[h]
        assert hist.axis == "tof"
        assert hist.two_theta is None
        assert hist.tof is not None and len(hist.tof) == len(hist.y_obs)
        assert min(hist.tof) > 1000.0        # microseconds, not degrees
        view = result.for_histogram(h)
        assert view.axis == "tof"
        assert view.two_theta is None
        assert view.tof == hist.tof
    # the top-level mirror is histogram 0's, matched pair and all
    assert result.axis == "tof"
    assert result.two_theta is None
    assert result.tof == result.histograms[0].tof


def test_the_ticks_of_a_bank_come_from_its_own_calibration(two_bank_fit):
    """Positions on each histogram's own axis: two banks of one cell put the
    same reflection at two different flight times, and a tick list that used
    one bank's calibration for both would show it."""
    _ref, result = two_bank_fit
    ticks = [sorted(result.histograms[h].ticks["Si"]) for h in range(2)]
    assert ticks[0] and ticks[1]
    assert len(ticks[0]) != len(ticks[1]) or ticks[0] != ticks[1]
    for h, hist in enumerate(result.histograms):
        lo, hi = min(hist.tof), max(hist.tof)
        inside = [t for t in ticks[h] if lo <= t <= hi]
        assert len(inside) > 5, (h, len(inside))
    # the 150° bank's DIFC is the larger, so one d-spacing lands later there
    assert max(ticks[1]) > max(ticks[0])


def test_each_bank_reports_its_own_rwp_and_its_own_channel_width(two_bank_fit):
    """A pooled Rwp would hide a badly-fitting bank; and the flight-time
    statements a bank owes (its channel width, its 2θ-only abstentions) are
    per histogram, not once for the fit."""
    _ref, result = two_bank_fit
    rwps = [h.statistics.rwp for h in result.histograms]
    assert len(set(rwps)) == 2
    for hist in result.histograms:
        assert hist.statistics.chi2 < 1.3
        codes = {d.code for d in hist.diagnostics}
        assert "TOF_CHANNEL_WIDTH_APPLIED" in codes
        assert "CAPILLARY_OFFSET_UNAVAILABLE" in codes
        # the crystallite-size flag *runs* on a bank since T-3c and finds
        # nothing here, so its abstention row is gone rather than present
        assert "SIZE_UNUSUALLY_SMALL" not in codes


# ----------------------------------------------------------------------
# 2. a bank beside a constant-wavelength histogram
# ----------------------------------------------------------------------
def test_a_mixed_list_shares_the_cell_and_keeps_both_axes(mixed_fit):
    """Von Dreele's combined fit, one axis apart.  The shared cell still lands,
    and each histogram's slice carries the abscissa it was measured on."""
    _ref, result = mixed_fit
    assert result.status == "converged"
    a = result.parameter("phases.0.cell.a")
    assert abs(a.value - A_GEN) < 3.0 * a.stderr
    assert [h.axis for h in result.histograms] == ["tof", "tof", "two_theta"]
    assert [result.for_histogram(h).axis for h in range(3)] == \
        ["tof", "tof", "two_theta"]
    assert result.histograms[2].tof is None
    assert result.histograms[2].two_theta[0] == pytest.approx(15.0)
    assert result.histograms[0].two_theta is None
    for hist in result.histograms:
        assert hist.statistics.chi2 < 1.3, (hist.label, hist.statistics.chi2)


def test_the_cw_block_of_a_mixed_fit_is_the_single_histogram_jacobian(patterns):
    """Bit-identity where it is cheapest to lose: the constant-wavelength
    histogram of a mixed fit must compile to the same object and produce the
    same analytic Jacobian columns as it would on its own.

    Hashed rather than compared elementwise so a change of one ulp in one
    column fails as loudly as a change of shape.
    """
    from rietx.model.forward import compile_model
    from rietx.optimize.least_squares import _make_jacobian
    from rietx.refine import _compile_for

    turn_on = ["phases.*.scale", "phases.*.cell.a", "instrument.background.c*",
               "phases.*.atoms.*.biso", "instrument.zero_shift"]

    single = ParameterTable(started_structure(), cw_instrument())
    single.set_vary(turn_on, True)
    alone = compile_model(started_structure(), cw_instrument(), patterns[2],
                          moving_paths=set(single.moving_paths))

    mtable = MultiParameterTable(
        started_structure(),
        [started_bank(**BANK_90), started_bank(**BANK_150), cw_instrument()])
    mtable.set_vary(["*"], False)
    mtable.set_vary(turn_on, True)
    mtable.apply_to_models()
    inside = _compile_for(mtable.structures[2], mtable.instruments[2],
                          patterns[2],
                          moving_paths=set(mtable.tables[2].moving_paths))

    assert type(inside) is type(alone)
    assert inside.n_points == alone.n_points
    assert single.free_paths == mtable.tables[2].free_paths

    def digest(model, table):
        j = _make_jacobian(model, table)(table.x0())
        return hashlib.sha256(np.ascontiguousarray(j).tobytes()).hexdigest()

    assert digest(inside, mtable.tables[2]) == digest(alone, single)


def test_the_analytic_gate_is_per_histogram(patterns):
    """A constant-wavelength histogram keeps its analytic columns; a bank takes
    the finite-difference fallback for its own — in the same joint fit.

    The proof that the bank's columns were *not* built analytically is that
    ``CompiledTOFModel.derivative_bases`` raises, so reaching it would fail
    rather than quietly return a short column (WP-1070).
    """
    from rietx.optimize.least_squares import _make_jacobian
    from rietx.refine import _compile_for

    mtable = MultiParameterTable(
        started_structure(),
        [started_bank(**BANK_90), started_bank(**BANK_150), cw_instrument()])
    mtable.set_vary(["*"], False)
    mtable.set_vary(["phases.*.scale", "phases.*.cell.a",
                     "instrument.background.c*", "instrument.source.tzero"],
                    True)
    mtable.apply_to_models()
    models = [_compile_for(s, i, d, moving_paths=set(t.moving_paths))
              for s, i, d, t in zip(mtable.structures, mtable.instruments,
                                    patterns, mtable.tables, strict=True)]
    # ``getattr(model, "analytic_jacobian", True)`` is how the driver asks, and
    # the constant-wavelength model deliberately has no such field — its
    # dispatch is byte for byte what it was, and that absence is the claim.
    assert [getattr(m, "analytic_jacobian", True) for m in models] == \
        [False, False, True]
    assert not hasattr(models[2], "analytic_jacobian")
    for h, model in enumerate(models):
        jac = _make_jacobian(model, mtable.tables[h])(mtable.tables[h].x0())
        assert jac.shape[0] == model.n_points
        assert np.all(np.isfinite(jac))
        # no dead column: a short column is the WP-1070 failure the gate exists
        # to avoid, and it shows up here as an all-zero column
        assert np.all(np.abs(jac).max(axis=0) > 0.0)


def test_the_shared_column_is_the_full_finite_difference_on_a_mixed_pair():
    """The joint Jacobian's *shared* column, against a plain finite difference
    of the whole stacked residual.

    This is the assertion the mixed arm is really about: histogram 0's block of
    the shared cell column comes from an analytic ladder or a finite difference
    depending on the histogram, and the driver scatters both into one column.
    Nothing else checks that the two halves are in the same units and the same
    sign, and a sign error there would still converge — to the wrong cell.
    """
    from rietx.optimize.least_squares import _multi_closures
    from rietx.refine import _compile_for

    data = [tof_pattern(bank(**BANK_90), (8000.0, 20000.0, 20.0), seed=11),
            cw_pattern(cw_instrument(), seed=12, lo=20.0, hi=60.0, step=0.1)]
    mtable = MultiParameterTable(
        started_structure(), [started_bank(**BANK_90), cw_instrument()])
    mtable.set_vary(["*"], False)
    mtable.set_vary(["phases.*.scale", "phases.*.cell.a"], True)
    mtable.apply_to_models()
    models = [_compile_for(s, i, d, moving_paths=set(t.moving_paths))
              for s, i, d, t in zip(mtable.structures, mtable.instruments,
                                    data, mtable.tables, strict=True)]
    residual, jacobian, _n = _multi_closures(models, mtable)

    x0 = mtable.x0()
    analytic = jacobian(x0)
    col = mtable.free_paths.index("phases.0.cell.a")
    step = 1e-6 * max(abs(float(x0[col])), 1.0)
    plus, minus = x0.copy(), x0.copy()
    plus[col] += step
    minus[col] -= step
    numeric = (residual(plus) - residual(minus)) / (2.0 * step)

    scale = np.abs(numeric).max()
    assert scale > 0.0
    assert np.allclose(analytic[:, col], numeric, rtol=2e-3, atol=1e-3 * scale)
    # and it is genuinely a *shared* column: both histograms' row blocks move
    n0 = models[0].n_points
    assert np.abs(numeric[:n0]).max() > 0.0
    assert np.abs(numeric[n0:n0 + models[1].n_points]).max() > 0.0


# ----------------------------------------------------------------------
# 3. the sharing map: nothing per-bank shared, no λ a bank has not got
# ----------------------------------------------------------------------
def test_a_bank_supplies_no_wavelength_and_takes_a_unit_scaling():
    """``SIZE_LAMBDA_POWER`` divides a size coefficient by a wavelength ratio.

    A bank declares no wavelength at all — not a crash, not a 0.0 stand-in, and
    above all not a ``lines`` field its source has never had — so it contributes
    nothing to the span the constant-wavelength histograms normalise over.
    Since T-3c it does **take** a factor, and that factor is a change of unit
    rather than of wavelength: a bank holds ``lor_size`` as K/L in Å⁻¹, because
    a size coefficient is (180/π)·K·λ/L and there is no λ here to state it in
    degrees with, so the map from the shared column is (π/180)/λ_ref.
    """
    import math

    from rietx.params.multi import (
        _is_tof_instrument,
        _longest_wavelength,
        size_value_scales,
    )

    b = bank(**BANK_90)
    assert _is_tof_instrument(b) is True
    assert _longest_wavelength(b) is None          # not a crash, not a 0.0
    assert _is_tof_instrument(cw_instrument()) is False
    assert _longest_wavelength(cw_instrument()) == pytest.approx(CW_LAMBDA)

    sharing = SharingMap()
    structure = silicon()
    # two banks and one CW histogram: one wavelength, so nothing to span — but
    # the banks still have to be put into their own units
    unit = math.radians(1.0) / CW_LAMBDA
    scales = size_value_scales(structure, [b, bank(**BANK_150),
                                           cw_instrument()], sharing)
    assert scales[0]["phases.0.lor_size"] == pytest.approx(unit)
    assert scales[0]["phases.0.gauss_size"] == pytest.approx(unit ** 2)
    assert scales[1] == scales[0]
    assert scales[2] == {}                         # the reference histogram
    # a bank beside *two* wavelengths: each CW one takes its ratio, the bank
    # takes the unit factor at the reference λ
    scales = size_value_scales(
        structure, [b, cw_instrument(1.0), cw_instrument(2.0)], sharing)
    assert scales[0]["phases.0.lor_size"] == pytest.approx(math.radians(1.0))
    assert scales[1] == {}
    assert scales[2]["phases.0.lor_size"] == pytest.approx(2.0)
    assert scales[2]["phases.0.gauss_size"] == pytest.approx(4.0)
    # every histogram of an all-bank list is already in Å⁻¹: no factor anywhere
    assert size_value_scales(structure, [b, bank(**BANK_150)],
                             sharing) == [{}, {}]


def test_each_arm_states_its_own_width_cap_in_its_own_units():
    """Both arms declare a tier-1 cap now, and the two agree where they meet.

    Until T-1d a bank contributed no cap and received none — ``strain_cap`` and
    ``size_cap`` read a 2θ extent and a wavelength, and ``tt_min`` raises on a
    bank — so a pure multi-bank fit, which is what a time-of-flight experiment
    *is*, had four free width columns with no fence at all (T-3c's owed item).

    Two properties are asserted, and the second is the one that makes
    declaring both consistent rather than a second opinion: a **strain** cap is
    one number in both arms (a microstrain is λ-free and axis-free, so
    ``SIZE_LAMBDA_POWER`` lists neither strain term) and enters one ``max``; a
    **size** cap is per arm because the arms hold that column in two units, and
    the 2 nm floor lands on the same *crystallite* once each table's value
    scale is applied.
    """
    from rietx.optimize.least_squares import (
        _freeze_size_cap_multi,
        _freeze_strain_cap_multi,
    )
    from rietx.params.vector import _SIZE_CAP_SCHERRER_K, SIZE_CAP_MIN_SIZE_A
    from rietx.refine import _compile_for

    data = [tof_pattern(bank(**BANK_90), (8000.0, 20000.0, 20.0), seed=21),
            cw_pattern(cw_instrument(), seed=22, lo=20.0, hi=60.0, step=0.1)]
    mtable = MultiParameterTable(
        started_structure(), [started_bank(**BANK_90), cw_instrument()])
    mtable.apply_to_models()
    models = [_compile_for(s, i, d)
              for s, i, d in zip(mtable.structures, mtable.instruments, data,
                                 strict=True)]
    _freeze_strain_cap_multi(models, mtable)
    _freeze_size_cap_multi(models, mtable)
    # one strain number, declared to both, because both arms hold that column
    # in the same unit
    assert mtable.tables[0]._strain_cap == mtable.tables[1]._strain_cap
    assert mtable.tables[0]._strain_cap is not None
    # the size caps differ in *value* because they differ in *unit*: the bank's
    # is k/L_min in Å⁻¹ and the scan's is (180/π)·k·λ/L_min in degrees
    bank_cap, cw_cap = mtable.tables[0]._size_cap, mtable.tables[1]._size_cap
    assert bank_cap == pytest.approx(_SIZE_CAP_SCHERRER_K / SIZE_CAP_MIN_SIZE_A)
    assert cw_cap == pytest.approx(np.degrees(
        _SIZE_CAP_SCHERRER_K * CW_LAMBDA / SIZE_CAP_MIN_SIZE_A))
    # …and they are the same crystallite: the shared column's bound is each
    # table's physical cap divided by that table's own value scale, and the
    # reference histogram here is the CW one (scale 1.0), so the bank's cap
    # divided by (π/180)/λ_ref must land on the CW cap exactly
    scale = mtable.tables[0]._value_scale["phases.0.lor_size"]
    assert bank_cap / scale == pytest.approx(cw_cap)

    # a pure multi-bank fit: every value scale is 1.0, so the banks' own Å⁻¹
    # cap is the whole answer and both tables carry it
    only_banks = MultiParameterTable(
        started_structure(), [started_bank(**BANK_90), started_bank(**BANK_150)])
    only_banks.apply_to_models()
    tof_models = [_compile_for(s, i, d)
                  for s, i, d in zip(only_banks.structures,
                                     only_banks.instruments,
                                     [data[0], tof_pattern(bank(**BANK_150),
                                                           (10000.0, 24000.0,
                                                            20.0), seed=23)],
                                     strict=True)]
    _freeze_strain_cap_multi(tof_models, only_banks)
    _freeze_size_cap_multi(tof_models, only_banks)
    assert all(t._size_cap == pytest.approx(
        _SIZE_CAP_SCHERRER_K / SIZE_CAP_MIN_SIZE_A) for t in only_banks.tables)
    assert all(t._strain_cap is not None for t in only_banks.tables)


def test_a_shared_width_a_bank_cannot_express_is_reported_not_refused(patterns):
    """A shared path one histogram's table locks is excused and **stated**.

    T-5 wrote this against ``phases.*.lor_size``; T-3c gave a bank that column
    (below), so what is left locked on a bank and shared is March-Dollase's
    ``r`` — a correction whose *form* differs on a bank rather than its units.
    The fit is right either way — the histograms that can express the column
    contribute its Jacobian rows and the bank contributes none — so what this
    pins is that the excuse is not silent: an esd read as a joint esd, on a
    number measured from one histogram, is the misreading the row prevents.
    """
    from rietx.schemas.structure import PreferredOrientation

    structure = started_structure()
    structure.phases[0].preferred_orientation = PreferredOrientation(
        axis=(1, 1, 1))
    mtable = MultiParameterTable(
        structure, [started_bank(**BANK_90), cw_instrument()])
    mtable.set_vary(["*"], False)
    freed = mtable.set_vary(
        ["phases.*.scale", "phases.*.preferred_orientation.r"], True)
    assert "phases.0.preferred_orientation.r" in freed
    assert mtable.shared_missing == {"phases.0.preferred_orientation.r": [0]}

    from rietx.multi import _shared_coverage_diagnostics

    diags = _shared_coverage_diagnostics(mtable)
    assert [d.code for d in diags] == ["SHARED_PARAMETER_NOT_IN_EVERY_HISTOGRAM"]
    assert diags[0].level == "info"
    assert diags[0].where == ["phases.0.preferred_orientation.r"]
    assert "histogram 0" in diags[0].message

    # a genuine disagreement — one histogram freeing a shared path the other
    # simply was not asked to free — is still refused, and by the same message
    plain = MultiParameterTable(started_structure(),
                                [cw_instrument(1.0), cw_instrument(2.0)])
    plain.set_vary(["*"], False)
    plain.tables[0].set_vary(["phases.0.cell.a"], True)
    with pytest.raises(ValueError, match="disagrees on the shared free set"):
        plain._rebuild_columns()


def test_a_shared_width_is_now_expressed_by_both_arms(patterns):
    """T-3c: ``phases.*.lor_size`` is a column **both** arms carry.

    T-5 wrote this test as the excuse's whole-fit half — the size was measured
    from the constant-wavelength histogram alone and the bank abstained.  A
    bank expresses a crystallite size now, so the abstention row must be gone
    and the column must be free in every histogram: a specimen's size is one
    number, and this is the joint fit finally being entitled to it.
    """
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("cell", ["phases.*.cell.a"]),
        rx.Stage("width", ["phases.*.lor_size"], seed=1e-3),
    ])
    ref = rx.MultiHistogramRefinement(
        started_structure(), [started_bank(**BANK_90), cw_instrument()])
    result = ref.fit([patterns[0], patterns[2]], plan=plan)
    assert result.status == "converged"
    row = result.parameter("phases.0.lor_size")
    assert row.vary is True
    assert not [d for d in result.diagnostics
                if d.code == "SHARED_PARAMETER_NOT_IN_EVERY_HISTOGRAM"]
    assert result.histograms[0].axis == "tof"


def test_a_background_peak_on_a_bank_abstains_instead_of_crashing(patterns):
    """A defect this rung found in T-1c's tree, on the **single**-histogram path
    as well as this one.

    ``strategy.staged.check_hump_width`` reached
    ``CompiledTOFModel.instrument_fwhm_deg``, which does not exist, so any bank
    that declared a ``HumpComponent`` died with an ``AttributeError`` from
    inside a guard scan.  The guard now abstains — its two halves are deg 2θ and
    a bank has neither — and says so, because an unrun guard that returns ``[]``
    reads exactly like one that ran and found nothing.
    """
    from rietx.model.forward_tof import compile_tof_model
    from rietx.schemas.instrument import HumpComponent
    from rietx.strategy.staged import check_hump_width

    ins = bank(**BANK_90)
    ins.extra_components = [HumpComponent()]
    structure = started_structure()
    table = ParameterTable(structure, ins)
    model = compile_tof_model(structure, ins, patterns[0])
    assert model.component_paths                     # the hump *is* compiled
    assert check_hump_width(table, model) == []

    from rietx.refine import _tof_background_peak_diagnostics

    said = _tof_background_peak_diagnostics(model)
    assert [d.code for d in said] == ["BACKGROUND_PEAK_WIDTH_UNAVAILABLE"]
    assert said[0].level == "info"
    assert said[0].where == ["instrument.extra_components.0.fwhm"]
    # …and the whole joint fit runs rather than dying in the guard
    ref = rx.MultiHistogramRefinement(structure, [ins, started_bank(**BANK_150)])
    result = ref.fit(patterns[:2], plan=joint_plan())
    codes = {d.code for d in result.histograms[0].diagnostics}
    assert "BACKGROUND_PEAK_WIDTH_UNAVAILABLE" in codes
    assert "BACKGROUND_PEAK_WIDTH_UNAVAILABLE" not in {
        d.code for d in result.histograms[1].diagnostics}


def test_the_report_survives_a_mixed_result_per_histogram(mixed_fit):
    """Point 4 of the rung: a report can be built for every histogram of a
    mixed fit, and each 2θ-only section says, per histogram, that it did not
    run rather than returning an empty list that reads as a pass."""
    _ref, result = mixed_fit
    for h in range(3):
        view = result.for_histogram(h)
        report = rx.build_report(view)
        assert report is not None
        assert view.statistics.rwp == result.histograms[h].statistics.rwp
    # the flight-time histograms carry the abstention rows; the CW one does not.
    # The two sample-width flags left that list in T-3c — they run on a bank
    # now, and a specimen with no broadening returns no row from either.
    for h in (0, 1):
        codes = {d.code for d in result.histograms[h].diagnostics}
        assert "CAPILLARY_OFFSET_UNAVAILABLE" in codes
        assert not ({"SIZE_UNUSUALLY_SMALL", "STRAIN_UNUSUALLY_LARGE"} & codes)
    # and the whole result still serialises with two axes in it
    assert result.model_dump_json()


def test_a_joint_fit_of_banks_alone_declares_no_size_scaling(two_bank_fit):
    """``SIZE_NORMALISED_ACROSS_WAVELENGTHS`` reads a λ span.  Two banks span
    none, so the row must be absent rather than quoting ``None`` as a number."""
    _ref, result = two_bank_fit
    codes = {d.code for d in result.diagnostics}
    assert "SIZE_NORMALISED_ACROSS_WAVELENGTHS" not in codes


# ----------------------------------------------------------------------
# 4. negative controls
# ----------------------------------------------------------------------
def test_a_crossed_pair_is_refused_naming_its_histogram(patterns):
    """Both directions, and the message names *which* of several histograms."""
    banks = [started_bank(**BANK_90), started_bank(**BANK_150)]
    ref = rx.MultiHistogramRefinement(started_structure(), banks)
    with pytest.raises(ValueError) as exc:
        ref.fit([patterns[0], patterns[2]])          # a 2θ scan on a bank
    message = str(exc.value)
    assert message.startswith("MultiHistogramRefinement.fit(), histogram 1 of 2")
    assert "neutron_tof bank" in message
    assert "2θ in degrees" in message

    mixed = rx.MultiHistogramRefinement(
        started_structure(), [started_bank(**BANK_90), cw_instrument()])
    with pytest.raises(ValueError) as exc:
        mixed.fit([patterns[0], patterns[1]])        # a bank on a CW source
    message = str(exc.value)
    assert message.startswith("MultiHistogramRefinement.fit(), histogram 1 of 2")
    assert "time of flight in microseconds" in message
    assert "tof_neutron_bank" in message


def test_one_window_across_two_axes_is_refused(patterns):
    """``two_theta_limits=(10, 90)`` over a mixed list asks for 10-90 µs on the
    bank, which is below every channel it has.  Refused rather than broadcast:
    the alternative fits an empty grid and reports it."""
    ref = rx.MultiHistogramRefinement(
        started_structure(), [started_bank(**BANK_90), cw_instrument()])
    with pytest.raises(ValueError, match="do not share an abscissa"):
        ref.fit([patterns[0], patterns[2]], plan=joint_plan(cw=True),
                two_theta_limits=(20.0, 90.0))
    # …and one window per histogram, each in its own unit, is accepted
    result = ref.fit([patterns[0], patterns[2]], plan=joint_plan(cw=True),
                     two_theta_limits=[(10000.0, 30000.0), (20.0, 90.0)])
    assert min(result.histograms[0].tof) >= 10000.0
    assert max(result.histograms[0].tof) <= 30000.0
    assert min(result.histograms[1].two_theta) >= 20.0


def test_a_declined_profile_is_refused_per_histogram(patterns):
    """A bank whose ``ProfileTOF`` is all zero has no peak shape at all — the
    refusal T-1b/T-3 make at the compiler, reached here through the joint path
    so the caller learns *which* bank declined."""
    flat = rx.Instrument.tof_neutron_bank(
        difc=BANK_150["difc"], tzero=BANK_150["tzero"],
        two_theta_bank_deg=BANK_150["two_theta"], profile=ProfileTOF())
    flat.background = BackgroundChebyshev(
        coefficients=[P(value=0.0) for _ in range(4)])
    ref = rx.MultiHistogramRefinement(started_structure(),
                                      [started_bank(**BANK_90), flat])
    with pytest.raises(ValueError) as exc:
        ref.fit(patterns[:2], plan=joint_plan())
    message = str(exc.value)
    # the address this path adds…
    assert message.startswith("MultiHistogramRefinement.fit(), histogram 1 of 2")
    # …and the compiler's own words, verbatim, because the wrapper is not a
    # second opinion about what is wrong
    assert "compile_tof_model" in message
    assert str(exc.value.__cause__) in message


def test_le_bail_and_pawley_are_still_refused(patterns):
    """The joint contract is unchanged: intensities are per-pattern
    extractions, so a joint fit of them is independent single fits."""
    ref = rx.MultiHistogramRefinement(
        started_structure(),
        [started_bank(**BANK_90), started_bank(**BANK_150)])
    for mode in ("lebail", "pawley"):
        with pytest.raises(NotImplementedError, match="Rietveld-only"):
            ref.fit(patterns[:2], mode=mode)


def test_a_joint_fit_over_banks_is_a_legitimate_object():
    """The contract change itself, from the construction side: the class no
    longer refuses a ``neutron_tof`` instrument before it has seen a pattern."""
    ref = rx.MultiHistogramRefinement(
        silicon(), [bank(**BANK_90), bank(**BANK_150)])
    assert [i.source.kind for i in ref.fitted_instruments] == \
        ["neutron_tof", "neutron_tof"]
    paths = {e.path for e in ref.mtable.tables[0].entries}
    assert "instrument.source.difc" in paths
    assert "instrument.source.profile_tof.sig1" in paths


# ----------------------------------------------------------------------
# 5. the constant-wavelength path, unmoved
# ----------------------------------------------------------------------
def test_a_constant_wavelength_joint_fit_compiles_the_same_objects():
    """A 2θ-only joint refinement must reach exactly the objects it did before
    the dispatch existed: the same compiler, the same class, the same grid."""
    from rietx.model.forward import CompiledModel, compile_model
    from rietx.refine import _compile_for

    data = [cw_pattern(cw_instrument(1.0), seed=31, lo=20.0, hi=60.0, step=0.1),
            cw_pattern(cw_instrument(2.0), seed=32, lo=20.0, hi=60.0, step=0.1)]
    mtable = MultiParameterTable(started_structure(),
                                 [cw_instrument(1.0), cw_instrument(2.0)])
    mtable.apply_to_models()
    for s, i, d in zip(mtable.structures, mtable.instruments, data, strict=True):
        routed = _compile_for(s, i, d)
        direct = compile_model(s, i, d)
        assert isinstance(routed, CompiledModel)
        assert routed.axis == "two_theta"
        assert np.array_equal(routed.tt, direct.tt)
        # the field's *absence* is the bit-identity claim: the driver asks
        # ``getattr(model, "analytic_jacobian", True)``, so a constant-
        # wavelength model that never grew the attribute dispatches exactly as
        # it did before the gate existed
        assert not hasattr(routed, "analytic_jacobian")
        assert getattr(routed, "analytic_jacobian", True) is True


# ----------------------------------------------------------------------
# 6. a stage that freed nothing on a bank: what the record says (T-1d)
# ----------------------------------------------------------------------
#: The natural wrong spelling, and why it is natural: `instrument.profile.*` is
#: where a constant-wavelength peak shape lives, and it is what every plan
#: preset in this package carries.  On a bank it matches nothing at all — the
#: shape is at `instrument.source.profile_tof.*` — and `set_vary` returned the
#: empty list without anything surfacing it.  Measured on a real five-histogram
#: mixed fit: joint Rwp 0.11486 `converged` with the whole flight-time profile
#: at its seed, against 0.06630 with the right globs.
CW_ONLY_PROFILE_GLOBS = ["instrument.profile.u", "instrument.profile.v",
                         "instrument.profile.w", "instrument.profile.x"]

TOF_PROFILE_GLOBS = ["instrument.source.profile_tof.sig1",
                     "instrument.source.profile_tof.sig2"]


def _freed_nothing(result) -> list:
    return [d for d in result.diagnostics if d.code == "STAGE_FREED_NOTHING"]


def test_a_cw_only_profile_stage_on_a_bank_is_matched_not_freed(patterns):
    """The single-histogram arm of the measured failure, under main's ruling.

    This branch first answered it with a ``STAGE_FREED_NOTHING`` row of its
    own.  The merge of main (2026-09-23) took WP-1414's instead, which rules
    the other way on this exact shape: **matched, not freed** — a row that
    exists and is force-fixed was *reached*, and ``held_because`` is where the
    reason lives (``params.multi.unreached_histograms``' docstring), while a
    single-histogram fit never emits ``STAGE_FREED_NOTHING`` at all
    (``test_params_surface``).  A bank carries ``instrument.profile.*`` and
    force-fixes it, so the stage is silent and the evidence is the record:
    an empty ``freed`` and the rows' ``held_because``.  The merge report
    names the lost detection as an open decision.
    """
    ref = rx.Refinement(started_structure(), started_bank(**BANK_90),
                        history=False)
    result = ref.fit(
        patterns[0], plan=rx.RefinementPlan(stages=[
            rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
            rx.Stage("profile", CW_ONLY_PROFILE_GLOBS)]))
    assert _freed_nothing(result) == []
    stage = result.stages[-1]
    assert stage.name == "profile"
    assert stage.freed == []
    # the paths exist, so none is a typo either
    assert stage.unknown_paths == []
    rows = {r.path: r for r in ref.parameters()}
    for path in CW_ONLY_PROFILE_GLOBS:
        assert not rows[path].refinable
        assert rows[path].held_because


def test_the_right_globs_on_the_same_bank_are_silent(patterns):
    """The negative control the arm above needs: the diagnostic is about the
    globs matching nothing, not about the stage being a profile stage."""
    result = rx.Refinement(started_structure(), started_bank(**BANK_90),
                           history=False).fit(
        patterns[0], plan=rx.RefinementPlan(stages=[
            rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
            rx.Stage("profile", TOF_PROFILE_GLOBS)]))
    assert _freed_nothing(result) == []
    assert set(result.stages[-1].freed) == set(TOF_PROFILE_GLOBS)


def test_a_mixed_joint_fit_records_which_histogram_the_stage_freed(patterns):
    """The shape that hides, under main's WP-1414 ruling.

    Two banks and one constant-wavelength histogram; the profile stage's globs
    are the CW container's.  It frees four rows — all histogram 2's.  Both
    banks carry those paths force-fixed, so ``unreached_histograms`` counts
    them as reached ("matched, not freed") and no ``STAGE_FREED_NOTHING``
    fires; this branch's own per-histogram row said the opposite and was
    dropped at the merge of 2026-09-23 for main's.  What the record still says
    is which histogram the four rows belong to.
    """
    ref = rx.MultiHistogramRefinement(
        started_structure(),
        [started_bank(**BANK_90), started_bank(**BANK_150), cw_instrument()])
    result = ref.fit(patterns, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("profile", CW_ONLY_PROFILE_GLOBS)]))
    assert _freed_nothing(result) == []
    profile_stage = next(s for s in result.stages if s.name == "profile")
    assert profile_stage.unreached_histograms == {}
    assert len(profile_stage.freed) == 4
    assert all(p.startswith("hist.2.") for p in profile_stage.freed)


def test_a_shared_glob_counts_for_every_histogram(patterns):
    """A shared path is one column in every histogram, so freeing it is work
    done on all of them — the joint arm's negative control."""
    ref = rx.MultiHistogramRefinement(
        started_structure(),
        [started_bank(**BANK_90), started_bank(**BANK_150), cw_instrument()])
    result = ref.fit(patterns, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("cell", ["phases.*.cell.a"])]))
    cell = next(s for s in result.stages if s.name == "cell")
    # once per histogram, bare each time: a shared path has no ``hist.h.``
    # scope, which is exactly what makes it count for all three
    assert cell.freed == ["phases.0.cell.a"] * 3
    assert _freed_nothing(result) == []


def test_a_shared_path_a_bank_force_fixes_is_named_through_the_public_fit(patterns):
    """``SHARED_PARAMETER_NOT_IN_EVERY_HISTOGRAM`` reached through ``fit``.

    The two structural paths a bank force-fixes (March-Dollase ``r``, the
    Stephens block) never get this far: declaring either on the phase is
    refused by ``compile_tof_model`` first.  An ``instrument.`` path is
    per-histogram by default, and a caller who shares one on purpose is the
    reachable case: ``instrument.zero_shift`` is a 2θ offset the bank locks,
    so only the constant-wavelength histogram carries its column.
    """
    ref = rx.MultiHistogramRefinement(
        started_structure(), [started_bank(**BANK_90), cw_instrument()],
        sharing=rx.SharingMap(shared=["instrument.zero_shift"]))
    result = ref.fit([patterns[0], patterns[2]], plan=rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("zero", ["instrument.zero_shift"], max_iter=5)]))
    hits = [d for d in result.diagnostics
            if d.code == "SHARED_PARAMETER_NOT_IN_EVERY_HISTOGRAM"]
    assert len(hits) == 1
    assert hits[0].level == "info"
    assert hits[0].where == ["instrument.zero_shift"]
    assert hits[0].value == 1.0          # one histogram carried it
    assert "histogram 0 cannot express it" in hits[0].message
