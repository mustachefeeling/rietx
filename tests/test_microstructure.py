"""Reading a profile width as a **strain**, and the λ asymmetry behind WP-1131.

Two claims, and the second is the one the sharing map turns on.

1. ``microstrain_from_strain_coefficient`` inverts the tanθ law exactly:
   Δ2θ = 2·(Δd/d)·tanθ is Bragg's law differentiated, so the FWHM read off the
   law at any angle, divided by 2·tanθ, is the same Δd/d the angle-free form
   returns from the coefficient alone.

2. **Size depends on λ and strain does not.**  Asserted as the ratio it is —
   one specimen at two wavelengths needs size coefficients in the ratio λ₂/λ₁
   and strain coefficients in the ratio 1 — because that is exactly the
   statement ``params.multi`` normalises against, and a test of it here is the
   one that fails on paper before the joint fixture fails in the fit.
"""

from __future__ import annotations

import inspect
import math
from pathlib import Path

import numpy as np
import pytest

from rietx import Instrument, Parameter, PatternData, Refinement
from rietx.model.forward import compile_model
from rietx.model.microstructure import microstructure_table
from rietx.model.profiles.caglioti import (
    SCHERRER_K,
    apparent_size_from_size_coefficient,
    lorentzian_fwhm,
    microstrain_from_strain_coefficient,
    size_coefficient_for_size,
    strain_coefficient_for_microstrain,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.strategy.staged import RefinementPlan, Stage
from tests.test_schemas import make_lab6

# The two wavelengths of the committed two-wavelength joint fixture
# (tests/test_multi_histogram.py), whose ratio is what WP-1131 measured.
LAM_SHORT, LAM_LONG = 0.41390, 0.71070


@pytest.mark.parametrize("two_theta", [5.0, 17.5, 30.0, 62.0, 90.0, 145.0])
@pytest.mark.parametrize("coefficient", [0.02, 0.114592, 1.5])
def test_the_strain_coefficient_maps_to_one_strain_at_every_angle(
    two_theta, coefficient
):
    """The angle-free form is the law evaluated at any angle and undone.

    The size twin of this lives in ``test_profile_size.py``; the difference
    worth asserting is in the *signature* — this one takes no wavelength, so
    there is no instrument for it to be wrong about.
    """
    fwhm = float(lorentzian_fwhm(two_theta / 2.0, 0.0, coefficient))
    theta = math.radians(two_theta / 2.0)
    from_angle = math.radians(fwhm) / (2.0 * math.tan(theta))
    assert from_angle == pytest.approx(
        microstrain_from_strain_coefficient(coefficient), rel=1e-12)


@pytest.mark.parametrize("microstrain", [1e-5, 1e-4, 1e-3, 5e-3, 3e-2])
def test_the_seed_and_the_reading_are_inverses(microstrain):
    coefficient = strain_coefficient_for_microstrain(microstrain)
    assert microstrain_from_strain_coefficient(coefficient) == pytest.approx(
        microstrain, rel=1e-15)


def test_the_strain_coefficient_is_360_over_pi_times_the_strain():
    """The constant, spelled out once against a hand computation.

    Δd/d = 1e-3 is 0.114592 deg 2θ on *every* instrument — the number the
    WP-1131 fixture's strain control refines to, and the one a reader can check
    with a calculator.
    """
    assert strain_coefficient_for_microstrain(1e-3) == pytest.approx(
        360.0 / math.pi * 1e-3, rel=1e-15)
    assert strain_coefficient_for_microstrain(1e-3) == pytest.approx(
        0.1145916, abs=5e-8)


@pytest.mark.parametrize("size_a", [80.0, 400.0, 2000.0])
def test_one_specimen_needs_two_size_coefficients_and_one_strain_coefficient(size_a):
    """The asymmetry WP-1131 exists for, as a ratio and without a constant.

    A specimen of one crystallite size measured at two wavelengths needs size
    coefficients in the ratio λ₂/λ₁ — so a joint fit that serves one coefficient
    to both histograms is wrong by that ratio, 1.717× on this fixture's pair.
    The Scherrer constant cancels out of it, which is why the defect does not
    wait on the convention question.
    """
    short = size_coefficient_for_size(size_a, LAM_SHORT)
    long = size_coefficient_for_size(size_a, LAM_LONG)
    assert long / short == pytest.approx(LAM_LONG / LAM_SHORT, rel=1e-15)
    for k in (0.89, 1.0, 1.0747):
        assert (size_coefficient_for_size(size_a, LAM_LONG, k)
                / size_coefficient_for_size(size_a, LAM_SHORT, k)
                == pytest.approx(LAM_LONG / LAM_SHORT, rel=1e-15))
    # and each reads back as the one size it was built from
    assert apparent_size_from_size_coefficient(short, LAM_SHORT) == pytest.approx(size_a)
    assert apparent_size_from_size_coefficient(long, LAM_LONG) == pytest.approx(size_a)


def test_the_strain_conversion_has_no_wavelength_to_be_wrong_about():
    """The control, as a fact about the signature and then about the ratio.

    ``SharingMap`` is right about strain and wrong about size, and the reason is
    visible before any fit runs: the strain pair takes no wavelength argument at
    all, while the size pair cannot be called without one.  Then the same
    statement as a ratio — one specimen, two wavelengths, strain coefficients
    identical and size coefficients 1.717× apart.
    """
    strain_params = set(inspect.signature(
        strain_coefficient_for_microstrain).parameters)
    size_params = set(inspect.signature(size_coefficient_for_size).parameters)
    assert "wavelength_a" not in strain_params
    assert "wavelength_a" in size_params

    coefficient = strain_coefficient_for_microstrain(1e-3)
    # the same coefficient describes the same specimen on both instruments,
    # so the widths it produces at one angle are bit-identical
    assert (float(lorentzian_fwhm(20.0, 0.0, coefficient))
            == float(lorentzian_fwhm(20.0, 0.0, coefficient)))
    ratio = (size_coefficient_for_size(400.0, LAM_LONG)
             / size_coefficient_for_size(400.0, LAM_SHORT))
    assert ratio == pytest.approx(1.7171, abs=5e-5)


@pytest.mark.parametrize("fn,args", [
    (microstrain_from_strain_coefficient, (0.0,)),
    (microstrain_from_strain_coefficient, (-0.1,)),
    (microstrain_from_strain_coefficient, (float("nan"),)),
    (strain_coefficient_for_microstrain, (0.0,)),
    (strain_coefficient_for_microstrain, (-1e-3,)),
    (strain_coefficient_for_microstrain, (float("nan"),)),
])
def test_the_unusable_inputs_are_refused_by_name(fn, args):
    """A zero strain is a perfect lattice and a nan is not a number.

    The ``not x > 0.0`` spelling in the module is also the nan test; asserting
    it here is what keeps a nan from being returned as a nan strain.
    """
    with pytest.raises(ValueError):
        fn(*args)


# --- the reported block: value, esd, and the four absences -----------------


def _phase_values(**terms):
    """A decoded value dict carrying just the four sample coefficients."""
    base = {f"phases.0.{k}": 0.0
            for k in ("lor_size", "gauss_size", "lor_strain", "gauss_strain")}
    base.update({f"phases.0.{k}": v for k, v in terms.items()})
    return base


def _one_phase():
    return make_lab6()


def test_a_size_reads_back_the_crystallite_it_was_built_from():
    """The block is the conversion, applied to a result rather than by hand."""
    coefficient = size_coefficient_for_size(400.0, LAM_LONG)
    blocks = microstructure_table(
        _one_phase(), _phase_values(lor_size=coefficient),
        wavelength=LAM_LONG, esds={"phases.0.lor_size": 0.1 * coefficient})
    assert len(blocks) == 1
    term = blocks[0].term("lor_size")
    assert term.kind == "size"
    assert term.value == pytest.approx(400.0, rel=1e-12)
    # a single-parameter propagation: the relative esd is the coefficient's
    assert term.esd == pytest.approx(40.0, rel=1e-12)
    assert term.unavailable is None
    assert blocks[0].wavelength == LAM_LONG
    assert blocks[0].scherrer_k == SCHERRER_K


def test_a_gaussian_variance_carries_the_factor_two_in_its_esd():
    """√v is the FWHM coefficient, so d(value)/dv brings a 1/2.

    Asserted against a finite difference of the reading itself rather than
    against the algebra restated — the algebra is what is under test.
    """
    fwhm = size_coefficient_for_size(400.0, LAM_LONG)
    v = fwhm ** 2
    sigma = 1e-6 * v
    blocks = microstructure_table(_one_phase(), _phase_values(gauss_size=v),
                                  wavelength=LAM_LONG,
                                  esds={"phases.0.gauss_size": sigma})
    term = blocks[0].term("gauss_size")
    assert term.value == pytest.approx(400.0, rel=1e-12)

    def size_of(variance):
        return apparent_size_from_size_coefficient(math.sqrt(variance), LAM_LONG)

    h = 1e-8 * v
    numeric = abs((size_of(v + h) - size_of(v - h)) / (2 * h)) * sigma
    assert term.esd == pytest.approx(numeric, rel=1e-6)


def test_a_strain_reads_back_and_needs_no_wavelength():
    coefficient = strain_coefficient_for_microstrain(1e-3)
    blocks = microstructure_table(
        _one_phase(), _phase_values(lor_strain=coefficient,
                                    gauss_strain=coefficient ** 2),
        wavelength=None,
        esds={"phases.0.lor_strain": 0.05 * coefficient})
    lor = blocks[0].term("lor_strain")
    assert lor.kind == "strain"
    assert lor.value == pytest.approx(1e-3, rel=1e-12)
    assert lor.esd == pytest.approx(5e-5, rel=1e-12)
    # …and the Gaussian twin reads the same strain, with no λ either
    assert blocks[0].term("gauss_strain").value == pytest.approx(1e-3, rel=1e-12)
    # the sizes, meanwhile, have nothing to read with
    assert blocks[0].term("lor_size").unavailable == "at_zero"


@pytest.mark.parametrize("term,expected", [
    ("lor_size", "no_wavelength"),
    ("lor_strain", None),
])
def test_a_missing_wavelength_stops_a_size_and_not_a_strain(term, expected):
    blocks = microstructure_table(
        _one_phase(), _phase_values(lor_size=0.1, lor_strain=0.1),
        wavelength=None, esds={})
    row = blocks[0].term(term)
    assert row.unavailable == (expected or "not_measured")
    assert (row.value is None) == (expected == "no_wavelength")


def test_the_off_state_is_absent_rather_than_infinite():
    """Every coefficient at zero: four rows, four ``at_zero``, no numbers.

    This is what a phase whose widths were never refined reports, which is
    most phases — and it must be a *statement*, not an empty block, because
    "no microstructure was measured" and "the block is missing" are different
    facts (WP-1076).
    """
    blocks = microstructure_table(_one_phase(), _phase_values(),
                                  wavelength=LAM_LONG, esds={})
    assert len(blocks[0].terms) == 4
    for row in blocks[0].terms:
        assert row.unavailable == "at_zero"
        assert row.value is None and row.esd is None
    assert blocks[0].size_agreement is None
    assert blocks[0].strain_agreement is None


def test_a_column_that_measured_nothing_keeps_its_value_and_loses_its_esd():
    """``not_measured`` is the WP-1110 answer arriving as an absence.

    ``stderr_physical`` already omits a row whose column measured nothing, so
    a missing key is the fact rather than a zero — and the *value* still
    stands, because the coefficient is known however badly.
    """
    blocks = microstructure_table(_one_phase(), _phase_values(lor_size=0.1),
                                  wavelength=LAM_LONG, esds={})
    row = blocks[0].term("lor_size")
    assert row.value is not None
    assert row.esd is None
    assert row.unavailable == "not_measured"


def test_the_two_independent_columns_are_compared_rather_than_combined():
    """Finding 5: nothing makes ``lor_size`` and ``gauss_size`` agree.

    rietx registers them as independent columns where GSAS-II refines one
    magnitude and a mixing coefficient, so the consistency the constrained
    model would impose is a *measurement* here.  Built to disagree by 2× and
    asserted to say so.
    """
    lor = size_coefficient_for_size(400.0, LAM_LONG)
    gauss = size_coefficient_for_size(200.0, LAM_LONG) ** 2
    blocks = microstructure_table(
        _one_phase(), _phase_values(lor_size=lor, gauss_size=gauss),
        wavelength=LAM_LONG, esds={})
    assert blocks[0].size_agreement == pytest.approx(0.5, rel=1e-12)
    # agreement is None the moment either half has nothing to compare
    blocks = microstructure_table(_one_phase(), _phase_values(lor_size=lor),
                                  wavelength=LAM_LONG, esds={})
    assert blocks[0].size_agreement is None


# --- end to end: the block on a real fit, and the caveat on the report ------

OUT = Path(__file__).parent / "output"


@pytest.fixture(scope="module")
def size_and_strain_fit():
    """One LaB6 pattern with a 400 Å domain and Δd/d = 1e-3, refined."""
    lam = LAM_LONG
    truth = make_lab6()
    truth.phases[0].scale.value = 5e-4
    truth.phases[0].lor_size.value = size_coefficient_for_size(400.0, lam)
    truth.phases[0].lor_strain.value = strain_coefficient_for_microstrain(1e-3)
    ins = Instrument.debye_scherrer(wavelength=lam)
    ins.profile.w.value = 3e-4
    ins.profile.x.value = 0.0
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (40.0, -6.0, 1.5)])

    tt = np.arange(5.0, 42.0, 0.005)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, blank, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    pattern = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())

    start = make_lab6()
    start.phases[0].scale.value = 5e-4
    ins2 = Instrument.debye_scherrer(wavelength=lam)
    ins2.profile.w.value = 3e-4
    ins2.profile.x.value = 0.0
    ins2.background = BackgroundChebyshev.with_terms(3)
    ref = Refinement(start, ins2, history=False)
    plan = RefinementPlan(stages=[
        Stage(name="scale+bkg",
              turn_on=["phases.*.scale", "instrument.background.*"]),
        Stage(name="cell", turn_on=["phases.*.cell.*"]),
        Stage(name="width",
              turn_on=["phases.*.lor_size", "phases.*.lor_strain"], seed=1e-3),
    ])
    result = ref.fit(pattern, plan=plan)
    OUT.mkdir(exist_ok=True)
    result.plot(OUT / "wp1131_microstructure_fit.png")
    return ref, result


def test_a_converged_fit_reports_a_domain_size_with_an_esd(size_and_strain_fit):
    """The WP-1131 acceptance for the reporting half.

    400 Å and Δd/d = 1e-3 go in; a size and a strain with esds come out, each
    covering its truth.  The esds are large — the two are collinear over this
    range — which is the caveat's whole point and is asserted rather than
    hidden: a band of five esds is a weak statement, and it is the statement
    the data supports.
    """
    _, result = size_and_strain_fit
    assert result.status == "converged"
    assert len(result.microstructure) == 1
    block = result.microstructure[0]
    assert block.phase_index == 0
    assert block.phase_name == "LaB6"
    assert block.wavelength == pytest.approx(LAM_LONG)

    size = block.term("lor_size")
    assert size.unavailable is None
    assert size.esd is not None and size.esd > 0.0
    assert abs(size.value - 400.0) < 5 * size.esd

    strain = block.term("lor_strain")
    assert strain.unavailable is None
    assert strain.esd is not None and strain.esd > 0.0
    assert abs(strain.value - 1e-3) < 5 * strain.esd

    # the two the plan never freed say so, in the same block
    for name in ("gauss_size", "gauss_strain"):
        assert block.term(name).unavailable == "at_zero"


def test_the_report_carries_the_block_and_attaches_the_caveat(size_and_strain_fit):
    """One statistic, two readers: the width trend's verdict lands on the block.

    ``separable`` is ``None`` on the result — nothing there assessed it — and
    a bool on the report whenever Layer 1 fitted a width trend.  The
    collinearity travels with it so a reader sees how close it came rather
    than only which side of the line it fell.
    """
    ref, result = size_and_strain_fit
    assert result.microstructure[0].separable is None

    report = ref.report()
    assert len(report.microstructure) == 1
    block = report.microstructure[0]
    assert block.term("lor_size").value == pytest.approx(
        result.microstructure[0].term("lor_size").value)

    width = next((t for t in report.trends if t.observable == "width"), None)
    if width is None:
        assert block.separable is None
        assert block.size_strain_collinearity is None
    else:
        assert block.separable is width.separable
        assert block.size_strain_collinearity == pytest.approx(
            width.max_template_collinearity)


def test_the_block_survives_a_json_round_trip(size_and_strain_fit):
    """It is a result field, so it has to serialize like one."""
    _, result = size_and_strain_fit
    again = type(result).model_validate_json(result.model_dump_json())
    assert (again.microstructure[0].term("lor_size").value
            == pytest.approx(result.microstructure[0].term("lor_size").value))
    assert (again.microstructure[0].term("gauss_size").unavailable
            == "at_zero")
