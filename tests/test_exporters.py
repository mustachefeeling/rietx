"""WP-0309 exporters: reflection table, refinement CIF (values + esds), QPA table.

The refinement CIF is validated by round-tripping through the package's own
readers (``read_pdcif`` for the pattern, ``Structure.from_cif`` for the
structure) — export then re-read is the cheapest correctness test.
"""

from __future__ import annotations

import numpy as np
import pytest

from pxrdref import (
    Instrument,
    PatternData,
    Refinement,
    Structure,
    format_su,
    read_pdcif,
    reflection_table,
    write_qpa_table,
    write_reflection_table,
)
from pxrdref.io.exporters import ReflectionRow, qpa_table_csv
from pxrdref.model.forward import compile_model
from pxrdref.params.vector import ParameterTable
from pxrdref.schemas.common import Parameter
from pxrdref.schemas.instrument import BackgroundChebyshev
from pxrdref.schemas.results import (
    MicroabsorptionCorrection,
    PhaseQuantity,
    QuantitativePhaseAnalysis,
)
from tests.test_schemas import make_lab6

WAVELENGTH_CU = 1.5405929


# ----------------------------------------------------------------------
# esd string formatter — the reference table (WP-0309's "genuine trap")
# ----------------------------------------------------------------------

# (value, esd, expected)  — two-significant-figure su, IUCr convention.
SU_REFERENCE = [
    (4.5937, 0.00025, "4.59370(25)"),        # the canonical cell-length case
    (0.006, 0.00012, "0.00600(12)"),
    (0.001, 0.0000031, "0.0010000(31)"),     # su finer than the value's default width
    (10.2513, 1.2e-5, "10.251300(12)"),
    (-4.5937, 0.00025, "-4.59370(25)"),      # negative value keeps its sign
    (1.23456, 0.0999, "1.23(10)"),           # decade boundary: 0.0999 rounds to 0.10
    (2.0, 0.00995, "2.000(10)"),             # decade boundary, deeper
    (98.76, 1.5, "98.8(15)"),                # esd >= 1
    (123.4, 2.5, "123.4(25)"),
    (12345.0, 250.0, "12340(250)"),          # esd >= 10, value loses precision
]


@pytest.mark.parametrize("value,esd,expected", SU_REFERENCE)
def test_format_su_reference_table(value, esd, expected):
    assert format_su(value, esd) == expected


def test_format_su_no_esd_is_a_plain_number():
    # a fixed parameter (esd None) must never imply an uncertainty it lacks
    assert format_su(0.005, None) == "0.005000"
    assert format_su(1.5, 0.0) == "1.500000"          # non-positive -> plain
    assert format_su(1.5, float("nan")) == "1.500000"  # non-finite -> plain
    assert format_su(0.005, None, decimals=3) == "0.005"


# ----------------------------------------------------------------------
# reflection table
# ----------------------------------------------------------------------


def _lab6_doublet_model():
    """A compiled LaB6 model under a Cu Kα1/Kα2 doublet (no fit needed)."""
    structure = make_lab6()
    ins = Instrument.bragg_brentano(radiation="CuKa", goniometer_radius_mm=200.0)
    tt = np.arange(20.0, 90.0, 0.02)
    pattern = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    return model, table.decode(table.x0()), structure


def test_reflection_table_accounts_for_every_emission_line():
    model, values, structure = _lab6_doublet_model()
    rows = reflection_table(model, values, structure)
    assert rows, "expected reflections in 20-90 deg"

    # both emission lines are represented — never a lambda_1-only table
    lines = {r.line for r in rows}
    assert lines == {0, 1}

    # every hkl that appears for the primary line also appears for Ka2, and the
    # Ka2 peak sits at higher 2theta (longer wavelength, same d)
    by_line = {0: {}, 1: {}}
    for r in rows:
        by_line[r.line][(r.h, r.k, r.l)] = r
    assert set(by_line[0]) == set(by_line[1])
    for hkl, r1 in by_line[0].items():
        r2 = by_line[1][hkl]
        assert r2.two_theta > r1.two_theta          # doublet splits with tanθ
        assert r2.d == pytest.approx(r1.d)          # d is line-independent
        assert r2.wavelength > r1.wavelength


def test_reflection_table_fields_are_physical():
    model, values, structure = _lab6_doublet_model()
    rows = reflection_table(model, values, structure)
    assert all(isinstance(r, ReflectionRow) for r in rows)
    for r in rows:
        assert r.phase == "LaB6"
        assert r.multiplicity >= 1
        assert r.d > 0.0
        assert r.f_squared is not None and r.f_squared >= 0.0   # rietveld mode
        assert r.intensity >= 0.0
    # (1,0,0), (1,1,0), (1,1,1) of a P m -3 m cube have multiplicities 6, 12, 8
    prim = {(r.h, r.k, r.l): r for r in rows if r.line == 0}
    assert prim[(1, 0, 0)].multiplicity == 6
    assert prim[(1, 1, 0)].multiplicity == 12
    assert prim[(1, 1, 1)].multiplicity == 8


def test_reflection_table_lebail_has_no_structure_factor():
    structure = make_lab6()
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    tt = np.arange(3.0, 24.0, 0.01)
    pattern = PatternData(two_theta=tt.tolist(), intensity=[100.0] * len(tt))
    model = compile_model(structure, ins, pattern, mode="lebail")
    table = ParameterTable(structure, ins)
    rows = reflection_table(model, table.decode(table.x0()), structure)
    assert rows
    # Le Bail intensity is extracted, not computed from |F|²
    assert all(r.f_squared is None for r in rows)


def test_write_reflection_table_csv_round_trips(tmp_path):
    model, values, structure = _lab6_doublet_model()
    rows = reflection_table(model, values, structure)
    out = tmp_path / "refl.csv"
    write_reflection_table(rows, out)

    text = out.read_text().splitlines()
    header = text[0].split(",")
    assert header[:6] == ["phase", "line", "wavelength", "h", "k", "l"]
    assert len(text) - 1 == len(rows)                # one data row per reflection row

    # a .tsv suffix switches the delimiter
    out_tsv = tmp_path / "refl.tsv"
    write_reflection_table(rows, out_tsv)
    assert "\t" in out_tsv.read_text().splitlines()[0]


# ----------------------------------------------------------------------
# QPA table
# ----------------------------------------------------------------------


def _two_phase_qpa(*, microabsorption=False, skipped=None):
    phases = [
        PhaseQuantity(name="corundum", weight_fraction=0.6,
                      weight_fraction_stderr=0.01, scale=1e-4, cell_mass=611.8,
                      cell_volume=254.8, zmv=1.559e5),
        PhaseQuantity(name="fluorite", weight_fraction=0.4,
                      weight_fraction_stderr=0.01, scale=8e-5, cell_mass=312.3,
                      cell_volume=163.0, zmv=5.09e4),
    ]
    micro = None
    if microabsorption:
        phases[0].weight_fraction_corrected = 0.58
        phases[0].mu_r = 0.03
        phases[0].brindley_tau = 0.98
        phases[0].particle_radius_um = 5.0
        micro = MicroabsorptionCorrection(wavelength=WAVELENGTH_CU, mu_mean_cm=125.0)
    return QuantitativePhaseAnalysis(phases=phases, microabsorption=micro,
                                     microabsorption_skipped=skipped)


def test_qpa_table_carries_crystalline_only_caveat(tmp_path):
    qpa = _two_phase_qpa()
    out = tmp_path / "qpa.csv"
    write_qpa_table(qpa, out)
    text = out.read_text()

    # the scope caveat is in the file itself, not just the API docstring
    assert "CRYSTALLINE" in text
    assert "crystalline_only=True" in text
    comments = [ln for ln in text.splitlines() if ln.startswith("#")]
    assert comments, "caveats must be written as leading comments"

    body = [ln for ln in text.splitlines() if not ln.startswith("#")]
    assert body[0].split(",")[:2] == ["phase", "weight_fraction"]
    assert len(body) - 1 == 2                          # two phase rows
    assert "corundum" in text and "fluorite" in text


def test_qpa_table_reports_microabsorption_status():
    corrected = qpa_table_csv(_two_phase_qpa(microabsorption=True))
    assert "Brindley" in corrected
    assert "0.58" in corrected                          # corrected fraction column
    assert "mu_r" in corrected

    skipped = qpa_table_csv(_two_phase_qpa(skipped="radii missing on 1 of 2 phases"))
    assert "skipped" in skipped
    assert "radii missing" in skipped


# ----------------------------------------------------------------------
# refinement CIF — export then re-read through the package's own readers
# ----------------------------------------------------------------------

TRUE_A = 4.15660
TRUE_ZERO = 0.008
TRUE_SCALE = 5e-4
TRUE_W = 2.5e-4


@pytest.fixture(scope="module")
def fitted_lab6():
    """A converged single-phase LaB6 fit — its structure carries refined esds."""
    truth = make_lab6()
    truth.phases[0].cell.a.value = TRUE_A
    truth.phases[0].cell.b.value = TRUE_A
    truth.phases[0].cell.c.value = TRUE_A
    truth.phases[0].scale.value = TRUE_SCALE
    ins_t = Instrument.debye_scherrer(wavelength=0.4139)
    ins_t.zero_shift.value = TRUE_ZERO
    ins_t.profile.w.value = TRUE_W
    ins_t.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (40.0, -6.0, 1.5)])

    tt = np.arange(3.0, 24.0, 0.005)
    grid = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins_t, grid, mode="rietveld")
    table = ParameterTable(truth, ins_t)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(7)
    y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    data = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())

    structure = make_lab6()
    structure.phases[0].cell.a.value = TRUE_A + 0.004
    structure.phases[0].cell.b.value = TRUE_A + 0.004
    structure.phases[0].cell.c.value = TRUE_A + 0.004
    structure.phases[0].scale.value = TRUE_SCALE * 1.8
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.profile.w.value = TRUE_W * 2.0
    ins.background = BackgroundChebyshev.with_terms(3)

    ref = Refinement(structure, ins, history=False)
    result = ref.fit(data, plan="mccusker_default")
    assert result.status == "converged"
    return ref, result, data


def test_refinement_cif_round_trips_through_readers(fitted_lab6, tmp_path):
    ref, result, data = fitted_lab6
    out = tmp_path / "refinement.cif"
    ref.write_cif(out)
    text = out.read_text()

    # 1. the structure re-reads through the small-molecule reader with the
    #    refined cell intact
    back = Structure.from_cif(str(out))
    a_fit = ref.fitted_structure.phases[0].cell.a.value
    assert back.phases[0].cell.a.value == pytest.approx(a_fit, abs=1e-5)
    assert len(back.phases[0].atoms) == 2

    # a refined cell length carries a standard uncertainty in value(su) notation
    a_esd = result.parameter("phases.0.cell.a").stderr
    assert a_esd is not None
    assert "_cell_length_a" in text
    assert "(" in text.split("_cell_length_a")[1].split("\n")[0]

    # 2. the observed pattern re-reads through read_pdcif, matching the fit grid
    pat = read_pdcif(out)
    assert len(pat.two_theta) == len(result.two_theta)
    np.testing.assert_allclose(pat.two_theta, result.two_theta, rtol=0, atol=1e-5)
    np.testing.assert_allclose(pat.intensity, result.y_obs, rtol=1e-6, atol=1e-3)
    assert pat.sigma is not None                       # the _su column round-trips

    # 3. refinement metadata is present
    assert "_diffrn_radiation_wavelength" in text
    assert "_pd_proc_ls_prof_wR_factor" in text        # Rwp
    assert "TCHZ" in text                              # profile description
    assert "Chebyshev" in text                         # background description


def test_refinement_result_arrays_are_faithful(fitted_lab6, tmp_path):
    """The calc/background columns are written too, not just obs."""
    ref, result, data = fitted_lab6
    out = tmp_path / "r.cif"
    ref.write_cif(out)
    text = out.read_text()
    assert "_pd_calc_intensity_total" in text
    assert "_pd_proc_intensity_bkg_calc" in text


def test_refinement_helpers_smoke(fitted_lab6, tmp_path):
    """The three Refinement convenience methods all produce files."""
    ref, result, data = fitted_lab6
    ref.write_reflection_table(tmp_path / "refl.csv")
    ref.write_cif(tmp_path / "s.cif")
    ref.write_qpa_table(tmp_path / "qpa.csv")
    for name in ("refl.csv", "s.cif", "qpa.csv"):
        assert (tmp_path / name).stat().st_size > 0

    rows = ref.reflection_table()
    assert rows and all(r.phase == "LaB6" for r in rows)
    # single synchrotron line -> only line 0
    assert {r.line for r in rows} == {0}
