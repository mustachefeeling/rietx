"""Quantitative phase analysis (Hill & Howard ZMV weight fractions).

Reference masses (IUPAC standard atomic weights, via gemmi):
La 138.905, B 10.811, Ca 40.078, F 18.998 g/mol.
"""

import math
from pathlib import Path

import numpy as np
import pytest

from pxrdref import (
    Atom,
    Cell,
    Instrument,
    Parameter,
    PatternData,
    Phase,
    Refinement,
)
from pxrdref.crystallography.attenuation import (
    linear_attenuation,
    mass_attenuation,
    total_cross_section,
)
from pxrdref.model.forward import compile_model
from pxrdref.optimize.qpa import (
    atomic_weight,
    brindley_correction,
    brindley_tau,
    phase_zmv,
    weight_fractions,
)
from pxrdref.params.vector import ParameterTable
from pxrdref.schemas.common import Provenance
from pxrdref.schemas.instrument import BackgroundChebyshev
from pxrdref.schemas.results import (
    PhaseQuantity,
    QuantitativePhaseAnalysis,
    RefinementResult,
    Statistics,
)

from .test_schemas import make_lab6


def _caf2_phase() -> Phase:
    return Phase(
        name="CaF2", space_group="F m -3 m", cell=Cell.cubic(5.4631),
        atoms=[
            Atom(label="Ca", species="Ca2+", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="F", species="F1-", x=Parameter(value=0.25),
                 y=Parameter(value=0.25), z=Parameter(value=0.25)),
        ],
    )


def _atoms(phase: Phase):
    return [(a.species, a.x.value, a.y.value, a.z.value, a.occ.value)
            for a in phase.atoms]


def test_atomic_weight_strips_charge():
    assert math.isclose(atomic_weight("La"), 138.905, abs_tol=0.1)
    assert math.isclose(atomic_weight("Ca2+"), 40.078, abs_tol=0.1)
    assert math.isclose(atomic_weight("F1-"), 18.998, abs_tol=0.1)
    with pytest.raises(ValueError):
        atomic_weight("Zz")


def test_atomic_weight_valence_species():
    # Waasmaier-Kirfel valence keys: a greedy 2-letter parse would read "Cval"
    # as the non-element "Cv"; the fallback must resolve C and Si.
    assert math.isclose(atomic_weight("Cval"), 12.011, abs_tol=0.1)
    assert math.isclose(atomic_weight("Siva"), 28.085, abs_tol=0.1)


def test_zmv_lab6():
    phase = make_lab6().phases[0]
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(), _atoms(phase))
    # LaB6: La on 1a (mult 1) + B on 6f (mult 6); one formula unit per cell.
    assert zmv.z == 1
    assert math.isclose(zmv.cell_mass, 138.905 + 6 * 10.811, abs_tol=0.5)
    assert math.isclose(zmv.molar_mass, zmv.cell_mass, rel_tol=1e-12)
    assert math.isclose(zmv.cell_volume, 4.1566 ** 3, rel_tol=1e-6)
    assert math.isclose(zmv.zmv, zmv.cell_mass * zmv.cell_volume, rel_tol=1e-12)


def test_zmv_caf2():
    phase = _caf2_phase()
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(), _atoms(phase))
    # CaF2: Ca on 4a (mult 4) + F on 8c (mult 8); four formula units per cell.
    assert zmv.z == 4
    assert math.isclose(zmv.cell_mass, 4 * 40.078 + 8 * 18.998, abs_tol=0.5)
    assert math.isclose(zmv.molar_mass, 40.078 + 2 * 18.998, abs_tol=0.5)
    assert math.isclose(zmv.cell_volume, 5.4631 ** 3, rel_tol=1e-6)


def test_zmv_partial_occupancy_falls_back_to_one_formula_unit():
    phase = _caf2_phase()
    phase.atoms[1].occ.value = 0.3  # F count 0.3·8 = 2.4 → composition does not reduce
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(), _atoms(phase))
    assert zmv.z == 1
    assert math.isclose(zmv.molar_mass, zmv.cell_mass, rel_tol=1e-12)
    assert math.isclose(zmv.cell_mass, 4 * 40.078 + 0.3 * 8 * 18.998, abs_tol=0.5)


def test_weight_fractions_no_covariance():
    # Two phases, equal Z·M·V, scales 3:1 → fractions 0.75/0.25.
    w, sc, si = weight_fractions([100.0, 100.0], [3.0, 1.0])
    assert np.allclose(w, [0.75, 0.25])
    assert sc is None and si is None


def test_weight_fractions_zero_covariance_reports_none():
    # An all-zero scale block (no scale was freed) is absence of information,
    # not σ(W) = 0.
    w, sc, si = weight_fractions([100.0, 100.0], [1.0, 1.0], np.zeros((2, 2)))
    assert np.allclose(w, [0.5, 0.5])
    assert sc is None and si is None


def test_weight_fractions_zero_scales_raises():
    with pytest.raises(ValueError):
        weight_fractions([100.0, 100.0], [0.0, 0.0], np.eye(2))


def test_weight_fractions_correlated_differs_from_independent():
    # Strongly (positively) correlated scales: the correlated ratio propagation
    # partly cancels, so σ_corr must differ from the naive independent σ.
    scale_cov = np.array([[4.0, 3.5], [3.5, 4.0]])
    w, sigma_corr, sigma_indep = weight_fractions([100.0, 100.0], [1.0, 1.0], scale_cov)
    assert np.allclose(w, [0.5, 0.5])
    assert not np.allclose(sigma_corr, sigma_indep)
    assert np.all(sigma_corr < sigma_indep)  # positive correlation shrinks σ(W)


def test_physical_covariance_block_diagonal_matches_stderr():
    from pxrdref import Instrument
    from pxrdref.params.vector import ParameterTable

    structure = make_lab6()
    structure.phases.append(_caf2_phase())
    table = ParameterTable(structure, Instrument.debye_scherrer(wavelength=1.5406))
    table.set_vary(["phases.*.scale"], True)
    theta = table.x0()
    free = table.free_paths
    i0, i1 = free.index("phases.0.scale"), free.index("phases.1.scale")
    corr = np.eye(len(theta))
    corr[i0, i1] = corr[i1, i0] = 0.7
    stderr_internal = np.full(len(theta), 0.3)

    esds = table.stderr_physical(theta, stderr_internal, corr)
    cov = table.physical_covariance(theta, stderr_internal, corr,
                                    ["phases.0.scale", "phases.1.scale"])
    # The block's diagonal is exactly the reported per-parameter esds squared,
    # so QPA σ(W) inherits the same conditioning by construction.
    assert math.isclose(math.sqrt(cov[0, 0]), esds["phases.0.scale"], rel_tol=1e-9)
    assert math.isclose(math.sqrt(cov[1, 1]), esds["phases.1.scale"], rel_tol=1e-9)
    assert cov[0, 1] != 0.0  # scales are correlated off the diagonal


def _qpa_fixture() -> QuantitativePhaseAnalysis:
    from pxrdref.schemas.results import MicroabsorptionCorrection

    return QuantitativePhaseAnalysis(phases=[
        PhaseQuantity(name="LaB6", weight_fraction=0.6, weight_fraction_stderr=0.01,
                      scale=2.0, z=1, molar_mass=203.77, cell_mass=203.77,
                      cell_volume=71.82, zmv=14634.9,
                      weight_fraction_corrected=0.62, brindley_tau=0.97,
                      mu_cm=1136.0, mu_r=0.045, particle_radius_um=0.4),
        PhaseQuantity(name="CaF2", weight_fraction=0.4, weight_fraction_stderr=None,
                      scale=1.0, z=4, molar_mass=78.07, cell_mass=312.30,
                      cell_volume=163.05, zmv=50920.0,
                      weight_fraction_corrected=0.38, brindley_tau=1.02,
                      mu_cm=304.0, mu_r=0.012, particle_radius_um=0.4),
    ], microabsorption=MicroabsorptionCorrection(wavelength=1.5406,
                                                 mu_mean_cm=700.0))


def test_qpa_json_round_trip():
    qpa = _qpa_fixture()
    assert QuantitativePhaseAnalysis.model_validate_json(qpa.model_dump_json()) == qpa


# -- compute_qpa microabsorption wiring -----------------------------------

def _two_phase_decoded(radii):
    from pxrdref.optimize.qpa import compute_qpa

    structure = make_lab6()
    structure.phases.append(_caf2_phase())
    for phase, r in zip(structure.phases, radii, strict=True):
        phase.particle_radius_um = r
    table = ParameterTable(structure, Instrument.debye_scherrer(wavelength=1.5406))
    return structure, table.decode(table.x0()), compute_qpa


def test_compute_qpa_brindley_applied():
    structure, values, compute_qpa = _two_phase_decoded([0.4, 0.4])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    base = compute_qpa(structure, values, wavelength=None)
    assert qpa.microabsorption is not None and qpa.microabsorption_skipped is None
    rows = {r.name: r for r in qpa.phases}
    la, ca = rows["LaB6"], rows["CaF2"]
    # uncorrected numbers are untouched by the correction...
    assert [r.weight_fraction for r in qpa.phases] == \
           [r.weight_fraction for r in base.phases]
    # ...and the corrected ones move the absorbing phase (LaB6, µ≈1136/cm) up
    assert la.brindley_tau < 1.0 < ca.brindley_tau
    assert la.weight_fraction_corrected > la.weight_fraction
    assert ca.weight_fraction_corrected < ca.weight_fraction
    assert math.isclose(sum(r.weight_fraction_corrected for r in qpa.phases), 1.0,
                        abs_tol=1e-12)
    assert 1080.0 < la.mu_cm < 1180.0 and 290.0 < ca.mu_cm < 315.0
    assert math.isclose(la.mu_r, la.mu_cm * 0.4e-4, rel_tol=1e-12)
    assert ca.mu_cm < qpa.microabsorption.mu_mean_cm < la.mu_cm


def test_compute_qpa_brindley_skipped_partial_radii():
    structure, values, compute_qpa = _two_phase_decoded([0.4, None])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    assert qpa.microabsorption is None
    assert "CaF2" in qpa.microabsorption_skipped
    assert all(r.weight_fraction_corrected is None for r in qpa.phases)


def test_compute_qpa_brindley_skipped_no_wavelength():
    structure, values, compute_qpa = _two_phase_decoded([0.4, 0.4])
    qpa = compute_qpa(structure, values, wavelength=None)
    assert qpa.microabsorption is None
    assert "wavelength" in qpa.microabsorption_skipped


def test_compute_qpa_brindley_skipped_mu_unavailable():
    structure, values, compute_qpa = _two_phase_decoded([0.4, 0.4])
    qpa = compute_qpa(structure, values, wavelength=13.0)  # outside 2-120 keV
    assert qpa.microabsorption is None
    assert "attenuation unavailable" in qpa.microabsorption_skipped


def test_compute_qpa_no_radii_stays_silent():
    structure, values, compute_qpa = _two_phase_decoded([None, None])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    assert qpa.microabsorption is None and qpa.microabsorption_skipped is None


# -- µR fence diagnostics --------------------------------------------------

def test_mu_r_fence_fires_exactly_when_it_should():
    from pxrdref.optimize.qpa import BRINDLEY_MU_R_FENCE, microabsorption_diagnostics

    # In regime: LaB6 µ≈1136/cm, R=0.4 µm → µR≈0.045 < 0.05 — no diagnostic.
    structure, values, compute_qpa = _two_phase_decoded([0.4, 0.4])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    assert max(r.mu_r for r in qpa.phases) < BRINDLEY_MU_R_FENCE
    assert microabsorption_diagnostics(qpa) == []

    # Push LaB6 past the fence (R=1 µm → µR≈0.11); CaF2 stays inside.
    structure, values, compute_qpa = _two_phase_decoded([1.0, 0.4])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    diags = microabsorption_diagnostics(qpa)
    assert len(diags) == 1
    d = diags[0]
    assert d.code == "BRINDLEY_OUTSIDE_REGIME" and d.level == "warning"
    assert d.where == ["LaB6"] and "µR" in d.message
    # the correction is still reported (never silently dropped)…
    assert all(r.weight_fraction_corrected is not None for r in qpa.phases)
    # …with the offending µR travelling on the result object
    assert {r.name: r.mu_r for r in qpa.phases}["LaB6"] > BRINDLEY_MU_R_FENCE


def test_skipped_correction_surfaces_as_diagnostic():
    from pxrdref.optimize.qpa import microabsorption_diagnostics

    structure, values, compute_qpa = _two_phase_decoded([0.4, None])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    diags = microabsorption_diagnostics(qpa)
    assert len(diags) == 1 and diags[0].code == "MICROABSORPTION_SKIPPED"
    assert "CaF2" in diags[0].message


def test_result_with_qpa_round_trip():
    stats = Statistics(rwp=0.05, rp=0.04, rexp=0.03, chi2=2.0, gof=1.4,
                       n_points=1000, n_free_parameters=8)
    result = RefinementResult(
        status="converged", mode="rietveld", parameters=[], statistics=stats,
        provenance=Provenance(package_version="test"), qpa=_qpa_fixture())
    assert RefinementResult.model_validate_json(result.model_dump_json()) == result


# -- attenuation coefficients (microabsorption input) --------------------

# Published anchors: NIST mass attenuation coefficients of Hubbell & Seltzer
# (1995), NISTIR 5632, at exactly 8.000 keV (tables at
# physics.nist.gov/PhysRefData/XrayMassCoef/ElemTab/zNN.html).  The bundled
# McMaster (1969) tabulation tracks them to ~2.5 % for Z >= 9; light elements
# are worse (B -7 %, O -3.6 % — a known weakness of the McMaster photoelectric
# fits at low Z) but contribute little to any phase's mu.
_NIST_8KEV = {"F": 16.02, "Al": 50.33, "Si": 64.68, "Ca": 172.6,
              "Ni": 49.52, "La": 352.9}
_LAM_8KEV = 12398.4198 / 8000.0


def test_mass_attenuation_matches_nist():
    for el, ref in _NIST_8KEV.items():
        assert math.isclose(mass_attenuation(el, _LAM_8KEV), ref, rel_tol=0.04)
    assert math.isclose(mass_attenuation("B", _LAM_8KEV), 2.346, rel_tol=0.08)
    assert math.isclose(mass_attenuation("O", _LAM_8KEV), 11.63, rel_tol=0.05)


def test_linear_attenuation_common_phases():
    # Cross-check the composition -> mu plumbing against values hand-computed
    # from the NIST elemental mu/rho above: mass-fraction mixing gives
    # mu(LaB6) ≈ 1116-1137 1/cm and mu(CaF2) ≈ 300-307 1/cm at Cu Ka1.
    lam = 1.5405929
    mu_lab6 = linear_attenuation({"La": 1.0, "B": 6.0}, 4.1566 ** 3, lam)
    mu_caf2 = linear_attenuation({"Ca": 4.0, "F": 8.0}, 5.4631 ** 3, lam)
    assert 1080.0 < mu_lab6 < 1180.0
    assert 290.0 < mu_caf2 < 315.0


def test_attenuation_edge_interval_raises():
    # Ni K edge at 8.3328 keV sits inside a ~2 % tabulation interval; asking
    # for mu there must refuse rather than smear the edge, while Cu Ka (well
    # below the edge) stays fine.
    with pytest.raises(ValueError, match="absorption edge of Ni"):
        total_cross_section("Ni", 12398.4198 / 8300.0)
    assert mass_attenuation("Ni", 1.5405929) > 0


def test_attenuation_missing_element_and_band():
    with pytest.raises(KeyError, match="McMaster"):
        total_cross_section("Po", 1.5406)
    with pytest.raises(ValueError, match="outside the tabulated"):
        total_cross_section("Si", 13.0)


def test_zmv_element_counts_and_density():
    phase = _caf2_phase()
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(), _atoms(phase))
    assert zmv.element_counts == {"Ca": 4.0, "F": 8.0}
    # CaF2 X-ray density ~3.18 g/cm3
    assert math.isclose(zmv.density, 3.18, rel_tol=0.01)


# -- Brindley particle-absorption factors ---------------------------------

def test_brindley_tau_reproduces_published_values():
    """tau must match both published representations of Brindley's table.

    Anchors: the quadratic 1 - 1.450x + 1.426x^2 (FullProf QPA formulation,
    Rodriguez-Carvajal's ILL notes; valid |x| <= 0.1) and the exponential fit
    -0.00229 + 2.054*exp(-(x + 0.50356)/0.69525) (MAUD, Lutterotti's QPA
    course notes).  The two published fits themselves differ by ~1 %, which
    sets the reproduction tolerance.
    """
    for x in np.linspace(-0.1, 0.1, 21):
        quad = 1.0 - 1.450 * x + 1.426 * x * x
        assert math.isclose(brindley_tau(x), quad, rel_tol=0.015)
    for x in np.linspace(-0.1, 0.5, 25):
        expfit = -0.00229 + 2.054 * math.exp(-(x + 0.50356) / 0.69525)
        assert math.isclose(brindley_tau(x), expfit, rel_tol=0.02)


def test_brindley_tau_limits():
    assert brindley_tau(0.0) == 1.0
    # continuous across the series/closed-form switch at |2x| = 0.05: the
    # difference over 2e-9 in x is slope-dominated (~3e-9), no visible jump
    assert abs(brindley_tau(0.025 + 1e-9) - brindley_tau(0.025 - 1e-9)) < 1e-8
    xs = np.linspace(-0.3, 1.5, 200)
    taus = np.array([brindley_tau(x) for x in xs])
    assert np.all(np.diff(taus) < 0)          # monotone decreasing
    assert np.all(taus > 0)                   # never a sign flip
    assert brindley_tau(-0.05) > 1.0          # less absorbing than matrix


def test_brindley_correction_direction_and_conservation():
    # Two phases, equal measured fractions; phase 0 strongly more absorbing.
    # The correction must *raise* the absorbing phase (its intensity was
    # suppressed) and lower the other, sum staying 1.
    w, taus, mu_bar = brindley_correction(
        [0.5, 0.5], densities=[4.7, 3.2], mus=[1100.0, 300.0],
        radii_um=[0.4, 0.4])
    assert math.isclose(w.sum(), 1.0, abs_tol=1e-12)
    assert w[0] > 0.5 > w[1]
    assert taus[0] < 1.0 < taus[1]
    assert 300.0 < mu_bar < 1100.0
    # zero contrast -> no correction, whatever the radius
    w2, taus2, _ = brindley_correction([0.3, 0.7], [3.0, 3.0],
                                       [500.0, 500.0], [5.0, 5.0])
    assert np.allclose(w2, [0.3, 0.7])
    assert np.allclose(taus2, 1.0)


def test_phase_particle_radius_field():
    phase = _caf2_phase()
    assert phase.particle_radius_um is None    # default: no correction
    phase.particle_radius_um = 0.75
    from pxrdref import Structure
    s = Structure(phases=[phase])
    assert Structure.model_validate_json(s.model_dump_json()) == s
    with pytest.raises(Exception):
        phase.particle_radius_um = -1.0


# -- two-phase synthetic acceptance --------------------------------------

_WAVELENGTH = 1.5406


def _two_phase_truth(la_scale: float, caf2_scale: float):
    structure = make_lab6()
    structure.phases[0].scale.value = la_scale
    caf2 = _caf2_phase()
    caf2.scale.value = caf2_scale
    structure.phases.append(caf2)
    ins = Instrument.debye_scherrer(wavelength=_WAVELENGTH)
    ins.profile.w.value = 3e-3
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (30.0, -4.0, 1.0)])
    return structure, ins


def _true_weight_fractions(structure) -> np.ndarray:
    k = np.array([phase_zmv(p.space_group, p.cell.lengths_angles(), _atoms(p)).zmv
                  for p in structure.phases])
    s = np.array([p.scale.value for p in structure.phases])
    a = s * k
    return a / a.sum()


def test_two_phase_synthetic_qpa():
    truth, ins = _two_phase_truth(la_scale=6e-4, caf2_scale=4e-4)
    w_true = _true_weight_fractions(truth)

    tt = np.arange(15.0, 90.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, blank, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    data = PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    # refine from perturbed scales (both start equal) and a slightly-off cell
    start, start_ins = _two_phase_truth(la_scale=1e-3, caf2_scale=1e-3)
    start.phases[0].cell.a.value += 0.01
    ref = Refinement(start, start_ins)
    result = ref.fit(data, plan="mccusker_default")

    assert result.status == "converged"
    assert result.qpa is not None and len(result.qpa.phases) == 2
    fractions = {row.name: row for row in result.qpa.phases}
    assert math.isclose(sum(r.weight_fraction for r in result.qpa.phases), 1.0, abs_tol=1e-9)

    for ip, name in enumerate(("LaB6", "CaF2")):
        row = fractions[name]
        assert row.weight_fraction_stderr is not None and row.weight_fraction_stderr > 0
        # recovered fraction within the propagated σ (with a modest multiplier
        # for the single noisy realisation) — and never wildly off
        assert abs(row.weight_fraction - w_true[ip]) < 4 * row.weight_fraction_stderr
        assert abs(row.weight_fraction - w_true[ip]) < 0.03

    # The wired σ(W) must come from the *correlated* scale block, not the naive
    # independent propagation from σ(S) alone — the two scales correlate through
    # the shared intensity/background, so the two must differ here.
    fitted = ref.fitted_structure
    k = np.array([phase_zmv(p.space_group, p.cell.lengths_angles(), _atoms(p)).zmv
                  for p in fitted.phases])
    scales = np.array([result.parameter(f"phases.{i}.scale").value for i in range(2)])
    sig_s = np.array([result.parameter(f"phases.{i}.scale").stderr for i in range(2)])
    _, sigma_indep, _ = weight_fractions(k, scales, np.diag(sig_s ** 2))
    sigma_wired = np.array([r.weight_fraction_stderr for r in result.qpa.phases])
    assert not np.allclose(sigma_wired, sigma_indep, rtol=1e-3)

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    result.plot(path=str(out / "qpa_two_phase.png"))
