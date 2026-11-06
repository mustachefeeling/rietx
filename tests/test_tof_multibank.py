"""Several banks, one structure: the joint fit admits time of flight (T-5).

A time-of-flight experiment is several detector banks of one sample, each with
its own DIFC/TZERO, angle, resolution and channel width, and one structure.
This file is the rung where :class:`~rietx.multi.MultiHistogramRefinement`
takes that list.

**Every fixture is synthetic and written here.**  No line of any real
instrument file enters this repository: the banks below are a plausible 90°
and 150° pair with round constants, and each pattern is generated from the
model it is then refined against, with Poisson noise.

The constant-wavelength joint path is pinned by ``tests/test_multi_histogram*``
(unchanged here) and by
:func:`test_a_constant_wavelength_joint_fit_compiles_the_same_objects`.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.params.multi import MultiParameterTable
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import BackgroundChebyshev, ProfileTOF
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import Atom, Cell, Phase, Structure

pytestmark = pytest.mark.xdist_group("tof_multibank")

# ----------------------------------------------------------------------
# the two synthetic banks and a constant-wavelength histogram
# ----------------------------------------------------------------------
#: The generating cell: silicon's, near enough to be recognisable, and compared
#: against no certificate here.
A_GEN = 5.4311946

#: The two banks differ in every per-bank quantity there is, which is what makes
#: "nothing per-bank is shared" a test rather than a hope.
BANK_90 = dict(difc=12000.0, tzero=-5.0, two_theta=90.0)
BANK_150 = dict(difc=15500.0, tzero=3.0, two_theta=150.0,
                alpha1=0.35, beta0=0.040, sig1=180.0)
GRID_90 = (8000.0, 45000.0, 5.0)
GRID_150 = (10000.0, 52000.0, 6.0)

#: How far out the fits start: 0.5 % on the cell, 20 µs on each TZERO, 2x on
#: the scale (``tests.test_tof_refine``'s displacement, so the arms compare).
CELL_OFFSET, TZERO_OFFSET, SCALE_START = 1.005, -20.0, 6.0

CW_LAMBDA = 1.5406


def silicon(a: float = A_GEN) -> Structure:
    """Si, Fd-3m:2, one atom on 8a: no free coordinate, one Biso."""
    return Structure(phases=[Phase(
        name="Si", space_group="F d -3 m :2",
        cell=Cell(a=P(value=a), b=P(value=a), c=P(value=a),
                  alpha=P(value=90.0), beta=P(value=90.0),
                  gamma=P(value=90.0)),
        scale=P(value=1.0, min=0.0),
        atoms=[Atom(label="Si", species="Si", x=P(value=0.125),
                    y=P(value=0.125), z=P(value=0.125),
                    biso=P(value=0.5, min=0.0, max=5.0))])])


def bank(*, difc: float, tzero: float, two_theta: float, n_background: int = 4,
         capillary_radius_mm: float | None = None, **profile) -> rx.Instrument:
    """One synthetic bank with a Chebyshev background."""
    coeffs = dict(alpha1=0.45, beta0=0.055, beta1=0.003, sig1=300.0)
    coeffs.update(profile)
    ins = rx.Instrument.tof_neutron_bank(
        difc=difc, tzero=tzero, two_theta_bank_deg=two_theta,
        capillary_radius_mm=capillary_radius_mm,
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
                seed: int, scale: float = 12.0, background=(40.0, -8.0),
                a: float = A_GEN, sigma: bool = True) -> PatternData:
    """A bank generated from the model it will be refined against.

    ``intensity_basis="counts"`` (a Mantid ``SaveGSS`` export's declaration),
    and σ = √y from the Poisson draw, written as the file's esd column, as a
    reduction would write it.
    """
    from rietx.model.forward_tof import compile_tof_model

    lo, hi, step = grid
    x = np.arange(lo, hi + 0.5 * step, step)
    blank = PatternData(tof=x.tolist(), intensity=[1.0] * len(x),
                        intensity_basis="counts")
    gen = ins.model_copy(deep=True)
    for k, v in enumerate(background):
        gen.background.coefficients[k].value = v
    structure = silicon(a)
    structure.phases[0].scale.value = scale
    y = _poisson_from(compile_tof_model(structure, gen, blank), structure, gen,
                      seed)
    return PatternData(tof=x.tolist(), intensity=y.tolist(),
                       sigma=np.sqrt(np.maximum(y, 1.0)).tolist() if sigma else None,
                       intensity_basis="counts")


def cw_pattern(ins: rx.Instrument, *, seed: int, lo: float = 15.0,
               hi: float = 120.0, step: float = 0.02, scale: float = 0.05,
               background=(40.0, -5.0)) -> PatternData:
    """The constant-wavelength histogram of the same specimen (small scale,
    so the generating and fitted compiles' one-channel window difference stays
    under one σ)."""
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
    """Per-bank scale, background and TZERO free, the cell shared.

    The profile stays at its calibrated values, which is what a bank standard
    is for: with α free as well the cell and ``profile_tof.alpha1`` correlate
    at ρ ≈ −1 on the 90° bank (a rise rate moves a centroid), and the esd this
    file compares would measure that degeneracy rather than the joint gain.
    """
    calibration = ["instrument.source.tzero"]
    if cw:
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
    """Two synthetic banks of one Si cell, refined jointly."""
    ref = rx.MultiHistogramRefinement(
        started_structure(),
        [started_bank(**BANK_90), started_bank(**BANK_150)])
    return ref, ref.fit(patterns[:2], plan=joint_plan(), telemetry=False)


@pytest.fixture(scope="module")
def single_bank_esds(patterns):
    """esd(a) from refining each bank alone, for the joint-vs-single check."""
    out = []
    for gen, data in ((BANK_90, patterns[0]), (BANK_150, patterns[1])):
        res = rx.Refinement(started_structure(), started_bank(**gen),
                            history=False).fit(data, plan=joint_plan(),
                                               telemetry=False)
        out.append(res.parameter("phases.0.cell.a").stderr)
    return out


# ----------------------------------------------------------------------
# 1. two banks, one structure
# ----------------------------------------------------------------------
def test_two_banks_refine_one_cell_better_than_either_alone(two_bank_fit,
                                                            single_bank_esds):
    """The positive arm.  Two banks are two measurements of one quantity, so
    the joint esd beats both, by the amount two independent measurements
    combine by: the check that says the residual is stacked rather than that
    one histogram won."""
    _ref, result = two_bank_fit
    assert result.status == "converged"
    a = result.parameter("phases.0.cell.a")
    assert a.stderr is not None and a.stderr > 0.0
    assert abs(a.value - A_GEN) < 3.0 * a.stderr
    assert a.stderr < min(single_bank_esds), (a.stderr, single_bank_esds)
    combined = 1.0 / np.sqrt(sum(1.0 / e ** 2 for e in single_bank_esds))
    assert a.stderr == pytest.approx(combined, rel=0.15)


def test_each_bank_keeps_its_own_calibration(two_bank_fit):
    """Per-bank stays per-bank: both TZEROs started 20 µs out in the same
    direction, and each returns to *its own* generating value, which two
    numbers sharing one column could not do."""
    _ref, result = two_bank_fit
    for h, gen in enumerate((BANK_90, BANK_150)):
        row = result.parameter(f"hist.{h}.instrument.source.tzero")
        assert abs(row.value - gen["tzero"]) < 1.0, (h, row.value)
    shared = {r.path for r in result.parameters if not r.path.startswith("hist.")}
    assert not any(".source." in p or ".background." in p or p.endswith(".scale")
                   for p in shared), sorted(shared)


def test_the_sharing_defaults_are_the_practice_split(two_bank_fit):
    """Per bank: scale, background, calibration, instrument profile.  Shared:
    the structure (cell, coordinates, ADPs), extinction and the sample widths.
    Attfield (2004, p. 100): "an individual background and peak shape
    function, but the sample parameters are common"."""
    ref, _result = two_bank_fit
    sharing = ref.mtable.sharing
    for path in ("phases.0.scale", "instrument.background.c0",
                 "instrument.source.difc", "instrument.source.tzero",
                 "instrument.source.profile_tof.alpha1",
                 "instrument.source.profile_tof.sig1"):
        assert not sharing.is_shared(path), path
    for path in ("phases.0.cell.a", "phases.0.atoms.0.biso",
                 "phases.0.extinction", "phases.0.lor_size",
                 "phases.0.gauss_strain"):
        assert sharing.is_shared(path), path


def test_absorption_is_held_and_one_coefficient_across_banks():
    """Absorption is computed from composition and held (no refinable row on
    either bank), and it is one sample coefficient: µR per ångström is the
    same for two banks of one capillary, each applying it at its own angle."""
    banks = [bank(**BANK_90, capillary_radius_mm=3.0),
             bank(**BANK_150, capillary_radius_mm=3.0)]
    ref = rx.MultiHistogramRefinement(silicon(), banks)
    for table in ref.mtable.tables:
        assert not any("mu_r" in e.path or "absorption" in e.path
                       for e in table.entries if e.vary or not e.locked)
    mus = [ins.geometry.mu_r for ins in ref.fitted_instruments]
    sources = set(ref._mu_r_source)
    assert len(sources) == 1, sources
    assert mus[0] == mus[1]


def test_a_bank_histogram_carries_microseconds_and_never_two_theta(two_bank_fit):
    """The T-1 fence at the one member that could break it on this path."""
    _ref, result = two_bank_fit
    for h in range(2):
        hist = result.histograms[h]
        assert hist.axis == "tof"
        assert hist.two_theta is None
        assert hist.tof is not None and len(hist.tof) == len(hist.y_obs)
        assert min(hist.tof) > 1000.0        # microseconds, not degrees
        view = result.for_histogram(h)
        assert view.axis == "tof" and view.two_theta is None
        assert view.tof == hist.tof
    assert result.axis == "tof"
    assert result.two_theta is None
    assert result.tof == result.histograms[0].tof


def test_the_ticks_of_a_bank_come_from_its_own_calibration(two_bank_fit):
    """Two banks of one cell put one reflection at two flight times."""
    _ref, result = two_bank_fit
    ticks = [sorted(result.histograms[h].ticks["Si"]) for h in range(2)]
    assert ticks[0] and ticks[1] and ticks[0] != ticks[1]
    for h, hist in enumerate(result.histograms):
        lo, hi = min(hist.tof), max(hist.tof)
        assert sum(lo <= t <= hi for t in ticks[h]) > 5, h
    assert max(ticks[1]) > max(ticks[0])      # the larger DIFC


def test_each_bank_reports_its_own_rwp_and_its_own_channel_width(two_bank_fit):
    """A pooled Rwp would hide a badly fitting bank, and the statements a bank
    owes (its channel width) are per histogram."""
    _ref, result = two_bank_fit
    rwps = [h.statistics.rwp for h in result.histograms]
    assert len(set(rwps)) == 2
    for hist in result.histograms:
        assert hist.statistics.chi2 < 1.3
        codes = {d.code for d in hist.diagnostics}
        assert "TOF_CHANNEL_WIDTH_APPLIED" in codes


def test_a_joint_fit_report_builds_per_bank(two_bank_fit):
    ref, _result = two_bank_fit
    for h in range(2):
        report = ref.report(h)
        assert report is not None


# ----------------------------------------------------------------------
# 2. negative controls
# ----------------------------------------------------------------------
def test_a_crossed_pair_is_refused_naming_its_histogram(patterns):
    banks = [started_bank(**BANK_90), started_bank(**BANK_150)]
    ref = rx.MultiHistogramRefinement(started_structure(), banks)
    with pytest.raises(ValueError) as exc:
        ref.fit([patterns[0], patterns[2]])          # a 2θ scan on a bank
    message = str(exc.value)
    assert message.startswith("MultiHistogramRefinement.fit(), histogram 1 of 2")
    assert "neutron_tof bank" in message

    mixed = rx.MultiHistogramRefinement(
        started_structure(), [started_bank(**BANK_90), cw_instrument()])
    with pytest.raises(ValueError) as exc:
        mixed.fit([patterns[0], patterns[1]])        # a bank on a CW source
    message = str(exc.value)
    assert message.startswith("MultiHistogramRefinement.fit(), histogram 1 of 2")
    assert "time of flight in microseconds" in message


def test_a_bank_with_no_esd_column_is_refused_in_a_joint_fit(patterns):
    """Unit inter-bank weights make σ the balance between banks, so a bank
    without one is refused by name, unless the caller states the weights."""
    bare = tof_pattern(bank(**BANK_150), GRID_150, seed=2, sigma=False)
    ref = rx.MultiHistogramRefinement(
        started_structure(), [started_bank(**BANK_90), started_bank(**BANK_150)])
    with pytest.raises(ValueError, match=r"histogram 1 is a time-of-flight bank "
                                         r"with no esd column"):
        ref.fit([patterns[0], bare], plan=joint_plan(), telemetry=False)
    # stating the balance is accepted, and recorded
    result = ref.fit([patterns[0], bare], plan=joint_plan(), weights=[1.0, 1.0],
                     telemetry=False)
    assert result.provenance.notes["histogram_weights"]


def test_a_declined_profile_is_refused_naming_its_histogram(patterns):
    """An all-zero ``ProfileTOF`` has no peak shape: the compiler's refusal,
    reached through the joint path with the histogram's address."""
    flat = rx.Instrument.tof_neutron_bank(
        difc=BANK_150["difc"], tzero=BANK_150["tzero"],
        two_theta_bank_deg=BANK_150["two_theta"], profile=ProfileTOF())
    flat.background = BackgroundChebyshev(
        coefficients=[P(value=0.0) for _ in range(4)])
    ref = rx.MultiHistogramRefinement(started_structure(),
                                      [started_bank(**BANK_90), flat])
    with pytest.raises(ValueError) as exc:
        ref.fit(patterns[:2], plan=joint_plan(), telemetry=False)
    message = str(exc.value)
    assert message.startswith("MultiHistogramRefinement.fit(), histogram 1 of 2")
    assert "compile_tof_model" in message
    assert str(exc.value.__cause__) in message


def test_le_bail_and_pawley_are_still_refused(patterns):
    ref = rx.MultiHistogramRefinement(
        started_structure(),
        [started_bank(**BANK_90), started_bank(**BANK_150)])
    for mode in ("lebail", "pawley"):
        with pytest.raises(NotImplementedError, match="Rietveld-only"):
            ref.fit(patterns[:2], mode=mode)


def test_a_joint_fit_over_banks_is_a_legitimate_object():
    """The class no longer refuses a ``neutron_tof`` instrument at
    construction, and each bank registers its own calibration and profile."""
    ref = rx.MultiHistogramRefinement(
        silicon(), [bank(**BANK_90), bank(**BANK_150)])
    assert [i.source.kind for i in ref.fitted_instruments] == \
        ["neutron_tof", "neutron_tof"]
    paths = {e.path for e in ref.mtable.tables[0].entries}
    assert "instrument.source.difc" in paths
    assert "instrument.source.profile_tof.sig1" in paths
    # and a bank list declares no wavelength scaling of the size column
    assert all(not s for s in ref.mtable.value_scales)


# ----------------------------------------------------------------------
# 3. the constant-wavelength path, unmoved
# ----------------------------------------------------------------------
def test_a_constant_wavelength_joint_fit_compiles_the_same_objects():
    """A 2θ-only joint refinement reaches exactly the objects it did before the
    routing: the same compiler, class and grid."""
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


# ----------------------------------------------------------------------
# 4. the reference bank (T-5b): at most N − 1 DIFCs free beside a free cell
# ----------------------------------------------------------------------
#: A sample-position offset on the 90° bank: its peaks sit where a DIFC 1.5e-3
#: smaller puts them, which the file's DIFC (the fit's start) does not know.
#: The HRPD furnace run measured −1.65e-3 on its 90° bank.
POSITION_OFFSET = -1.5e-3


def _offset_patterns() -> list[PatternData]:
    gen90 = dict(BANK_90)
    gen90["difc"] = BANK_90["difc"] * (1.0 + POSITION_OFFSET)
    return [tof_pattern(bank(**gen90), GRID_90, seed=1),
            tof_pattern(bank(**BANK_150), GRID_150, seed=2)]


def _position_plan(extra: list[str]) -> rx.RefinementPlan:
    return rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("calibration", ["instrument.source.tzero"]),
        rx.Stage("cell", ["phases.*.cell.a", *extra]),
        rx.Stage("displacement", ["phases.*.atoms.*.biso"]),
    ])


@pytest.fixture(scope="module")
def offset_patterns() -> list[PatternData]:
    return _offset_patterns()


def test_every_bank_difc_free_beside_a_free_cell_is_refused_by_name(offset_patterns):
    """The positive arm of the N − 1 rule: TOF = DIFC·d, so every DIFC free
    with the shared cell is an exactly flat direction, refused naming the
    count and the bank to hold (the highest-angle one)."""
    ref = rx.MultiHistogramRefinement(
        started_structure(), [started_bank(**BANK_90), started_bank(**BANK_150)])
    with pytest.raises(ValueError, match=r"2 of 2 bank DIFCs are free beside a "
                                         r"free cell; hold one\..*Hold "
                                         r"hist\.1\.instrument\.source\.difc"):
        ref.fit(offset_patterns, plan=_position_plan(["instrument.source.difc"]),
                telemetry=False)


def test_every_difc_free_against_a_held_cell_is_a_calibration_and_allowed(
        offset_patterns):
    """The negative arm: with the cell held (a certified standard), every
    bank's DIFC is measurable, as the single-bank calibration is."""
    s = silicon()
    s.phases[0].scale.value = SCALE_START
    ref = rx.MultiHistogramRefinement(
        s, [started_bank(**BANK_90), started_bank(**BANK_150)])
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("calibration", ["instrument.source.tzero",
                                 "instrument.source.difc"])])
    result = ref.fit(offset_patterns, plan=plan, telemetry=False)
    d0 = result.parameter("hist.0.instrument.source.difc")
    assert d0.value / BANK_90["difc"] - 1.0 == pytest.approx(POSITION_OFFSET,
                                                             abs=5e-5)


def test_one_held_reference_bank_recovers_the_offset_and_the_cell(offset_patterns):
    """N − 1 free: the 150° bank's DIFC held, the 90° bank's free.  The offset
    comes back as that bank's DIFC and the shared cell at the generating one,
    where holding both splits the offset into the cell."""
    held = rx.MultiHistogramRefinement(
        started_structure(), [started_bank(**BANK_90), started_bank(**BANK_150)]
    ).fit(offset_patterns, plan=_position_plan([]), telemetry=False)
    a_held = held.parameter("phases.0.cell.a")
    assert abs(a_held.value / A_GEN - 1.0) > 2e-4      # the offset leaks in
    freed = rx.MultiHistogramRefinement(
        started_structure(), [started_bank(**BANK_90), started_bank(**BANK_150)]
    ).fit(offset_patterns, plan=_position_plan(["hist.0.instrument.source.difc"]),
          telemetry=False)
    a = freed.parameter("phases.0.cell.a")
    assert abs(a.value - A_GEN) < 3.0 * a.stderr
    d0 = freed.parameter("hist.0.instrument.source.difc")
    assert d0.value / BANK_90["difc"] - 1.0 == pytest.approx(POSITION_OFFSET,
                                                             abs=2e-5)
    assert all(h.statistics.chi2 < 1.3 for h in freed.histograms)


# ----------------------------------------------------------------------
# 5. what the joint fit says about its banks (report.tof_banks)
# ----------------------------------------------------------------------
def _codes(result) -> dict[str, list]:
    out: dict[str, list] = {}
    for d in result.diagnostics:
        out.setdefault(d.code, []).append(d)
    return out


def test_the_weight_shares_name_each_bank_and_each_shared_column(two_bank_fit):
    _ref, result = two_bank_fit
    (shares,) = _codes(result)["BANK_WEIGHT_SHARES"]
    assert shares.level == "info"
    for word in ("points", "χ²", "Bragg weight", "cell",
                 "ADPs"):
        assert word in shares.message


def test_the_cell_check_reads_the_offset_it_was_given(offset_patterns):
    """Both DIFCs held over a 90° bank offset by −1.5e-3: the one-step reading
    of that bank's d-scale against the 150° reference is the offset to 10 %."""
    result = rx.MultiHistogramRefinement(
        started_structure(), [started_bank(**BANK_90), started_bank(**BANK_150)]
    ).fit(offset_patterns, plan=_position_plan([]), telemetry=False)
    (cell,) = _codes(result)["BANK_CELL_INCONSISTENT"]
    assert cell.where == ["hist.0.instrument.source.difc"]
    assert cell.value == pytest.approx(POSITION_OFFSET, rel=0.1)
    assert "BANK_DOMINATES_MISFIT" in _codes(result)


def test_leave_one_out_is_opt_in_and_names_the_compromise(offset_patterns):
    ref = rx.MultiHistogramRefinement(
        started_structure(), [started_bank(**BANK_90), started_bank(**BANK_150)])
    plain = ref.fit(offset_patterns, plan=_position_plan([]), telemetry=False)
    assert "BANK_LEAVE_ONE_OUT" not in _codes(plain)
    result = ref.fit(offset_patterns, plan=_position_plan([]), telemetry=False,
                     leave_one_out=True)
    rows = _codes(result)["BANK_LEAVE_ONE_OUT"]
    assert [d.where for d in rows] == [["hist.0"], ["hist.1"]]
    # each bank alone reads a different cell, so dropping either moves it by
    # many joint esds
    assert all(d.value > 10.0 for d in rows)


def test_the_normalisation_factors_agree_when_the_scales_follow_difc_over_sin_theta():
    """Paddison's s_t ∝ scale·sinθ/DIFC: banks generated with scales in that
    ratio read one factor (silent); equal scales on these two banks, whose
    flight paths differ by 5 %, do not (fires)."""
    import math

    def q(g):
        return g["difc"] / math.sin(math.radians(0.5 * g["two_theta"]))

    ratio = q(BANK_150) / q(BANK_90)
    for scales, fires in (((12.0, 12.0 * ratio), False), ((12.0, 12.0), True)):
        pats = [tof_pattern(bank(**BANK_90), GRID_90, seed=1, scale=scales[0]),
                tof_pattern(bank(**BANK_150), GRID_150, seed=2, scale=scales[1])]
        result = rx.MultiHistogramRefinement(
            started_structure(), [started_bank(**BANK_90), started_bank(**BANK_150)]
        ).fit(pats, plan=joint_plan(), telemetry=False)
        assert ("BANK_SCALE_INCONSISTENT" in _codes(result)) is fires, scales
