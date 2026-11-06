"""A magnetic moment on a time-of-flight bank (T-6a).

The neutron's own moment couples to the magnetization density at every
wavelength of a white beam, so a bank carries WP-1327's magnetic term exactly
as a constant-wavelength scan does: p²⟨|F_⊥|²⟩ is a function of the
reflection (the form factor at s = 1/2d, the projection on Q̂) and of nothing
the two arms do differently.  What a bank changes is what multiplies the row
(the d⁴·sin θ_bank Lorentz factor, absorption and extinction at λ_hkl, the
per-channel spectrum and channel width), and those already act on the row.

**Every fixture is synthetic and written here**: MnF₂ (the radiation table's
magnetic phase, Erickson 1953), and a k = (0, 0, ½) antiferromagnet stated in
its magnetic supercell by ``magnetic_supercell`` — a commensurate k ≠ 0 order
whose group carries an anti-translation.  No instrument file enters the
repository: the banks are round numbers.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.lattice import d_spacings
from rietx.crystallography.magnetic.scattering import MAGNETIC_SOURCE_KINDS
from rietx.crystallography.structure_factor import structure_factors_squared
from rietx.model.forward import compile_model, magnetic_wanted
from rietx.model.forward_tof import compile_tof_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import BackgroundChebyshev, ProfileTOF
from rietx.schemas.structure import Moment

from .test_joint_xray_neutron import mnf2

pytestmark = pytest.mark.xdist_group("tof_magnetic")

#: A 60° bank: low enough that MnF₂'s (1 0 0), d = 4.87 Å, is well inside a
#: 5-28 ms window at DIFC 5000 µs/Å (24.4 ms).
DIFC, TWO_THETA = 5000.0, 60.0
TOF_GRID = (6000.0, 28000.0, 4.0)
#: The constant-wavelength twin: any λ reaching the same d range will do,
#: since the claim is that the magnetic term does not depend on it.
LAMBDA_CW = 2.078


def bank(n_background: int = 4) -> rx.Instrument:
    ins = rx.Instrument.tof_neutron_bank(
        difc=DIFC, two_theta_bank_deg=TWO_THETA,
        profile=ProfileTOF(**{k: P(value=v, unit=None) for k, v in dict(
            alpha1=0.45, beta0=0.055, beta1=0.003, sig1=300.0).items()}))
    ins.background = BackgroundChebyshev(
        coefficients=[P(value=0.0) for _ in range(n_background)])
    return ins


def tof_grid(lo: float = TOF_GRID[0], hi: float = TOF_GRID[1]) -> rx.PatternData:
    tof = np.arange(lo, hi, TOF_GRID[2])
    return rx.PatternData(tof=tof.tolist(), intensity=[1.0] * len(tof),
                          sigma=[1.0] * len(tof), intensity_basis="density")


def cw_twin() -> tuple[rx.Instrument, rx.PatternData]:
    tt = np.arange(5.0, 150.0, 0.02)
    return (rx.Instrument.constant_wavelength_neutron(LAMBDA_CW, fwhm_deg=0.3),
            rx.PatternData(two_theta=tt.tolist(), intensity=[1.0] * len(tt)))


def values(structure, instrument) -> dict:
    table = ParameterTable(structure, instrument)
    return table.decode(table.x0())


def cell_of(v: dict, ip: int = 0) -> tuple:
    return tuple(v[f"phases.{ip}.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))


def afm_k_half():
    """Mn on 1a of P4/mmm, k = (0, 0, ½), 3 μ_B along c: BNS 124.360 in a, b, 2c."""
    from rietx.crystallography.magnetic.isotropy import candidates
    from rietx.crystallography.magnetic.supercell import magnetic_supercell

    from .test_magnetic_k_trials import tetragonal

    truth = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]
    return magnetic_supercell(tetragonal(), truth, magnetic_species=["Mn1"],
                              ion={"Mn1": "Mn3+"}, magnitude=3.0).phase


# ----------------------------------------------------------------------
# the dispatch
# ----------------------------------------------------------------------
def test_a_bank_is_a_magnetic_source_kind():
    """One table, and the bank is in it; X-ray still gets no term."""
    assert MAGNETIC_SOURCE_KINDS == {"neutron_cw", "neutron_tof"}
    phase = mnf2()
    assert magnetic_wanted(phase, bank().source) is True
    assert magnetic_wanted(phase, rx.Instrument.debye_scherrer(1.54).source) is False
    caps = rx.capabilities()
    tof = next(r for r in caps.radiations if r.kind == "neutron_tof")
    assert tof.magnetic_scattering is True


# ----------------------------------------------------------------------
# the term, against the constant-wavelength twin
# ----------------------------------------------------------------------
@pytest.mark.parametrize("make", [lambda: rx.Structure(phases=[mnf2()]),
                                  lambda: rx.Structure(phases=[afm_k_half()])],
                         ids=["MnF2_k0", "k00half_supercell"])
def test_the_magnetic_intensity_is_the_constant_wavelength_twins(make):
    """Identity: at every reflection both arms list, p²⟨|F_⊥|²⟩ agrees to
    rounding, and so does the nuclear term — the bank adds rows only where its
    d range reaches further, never a different number at the same d."""
    structure = make()
    ins_t, ins_c = bank(), cw_twin()[0]
    mt = compile_tof_model(structure, ins_t, tof_grid())
    mc = compile_model(structure, ins_c, cw_twin()[1])
    vt, vc = values(structure, ins_t), values(structure, ins_c)
    cell = cell_of(vt)
    cpt, cpc = mt.phases[0], mc.phases[0]
    assert cpt.magnetic is not None and cpc.magnetic is not None
    dt = d_spacings(cpt.reflections.hkl, *cell)
    dc = d_spacings(cpc.reflections.hkl, *cell)
    fm_t, fm_c = mt._magnetic_f2(0, dt, vt, cell), mc._magnetic_f2(0, dc, vc, cell)
    fn_t, fn_c = mt._nuclear_f2(0, dt, vt, cell), mc._nuclear_f2(0, dc, vc, cell)
    cw_rows = {tuple(h): k for k, h in enumerate(cpc.reflections.hkl)}
    matched = [(k, cw_rows[tuple(h)]) for k, h in enumerate(cpt.reflections.hkl)
               if tuple(h) in cw_rows]
    assert len(matched) >= 15
    i, j = np.array(matched).T
    assert np.max(fm_t[i]) > 10.0  # a real magnetic signal, not two zeros
    np.testing.assert_allclose(fm_t[i], fm_c[j], rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(fn_t[i], fn_c[j], rtol=1e-12, atol=1e-12)
    np.testing.assert_array_equal(cpt.nuclear_mask[i], cpc.nuclear_mask[j])


def test_the_row_is_scale_times_multiplicity_times_total_times_lorentz():
    """Both terms ride under one scale and the bank's own d⁴·sin θ_bank, bit
    for bit, and the product is not the nuclear-only one."""
    structure = rx.Structure(phases=[mnf2()])
    ins = bank()
    m = compile_tof_model(structure, ins, tof_grid())
    v = values(structure, ins)
    cell = cell_of(v)
    cp = m.phases[0]
    d = d_spacings(cp.reflections.hkl, *cell)
    (_pos, *_w, intensity), = m.phase_peaks(0, v)
    total = m._nuclear_f2(0, d, v, cell) + m._magnetic_f2(0, d, v, cell)
    want = (v["phases.0.scale"] * cp.reflections.multiplicity.astype(float)
            * total * m.lorentz(d))
    np.testing.assert_array_equal(intensity, want)
    nuclear_only = (v["phases.0.scale"] * cp.reflections.multiplicity
                    * m._nuclear_f2(0, d, v, cell) * m.lorentz(d))
    assert np.max(np.abs(intensity - nuclear_only)) > 0.0


def test_the_magnetic_only_rows_are_the_absences_the_group_lifts():
    """(1 0 0) is n-glide absent in P4₂/mnm: |F_N|² is exactly zero there and
    it carries MnF₂'s strongest magnetic line; (0 0 1) is a magnetically
    allowed point where Q ∥ c ∥ m, so |F_⊥|² is exactly zero."""
    structure = rx.Structure(phases=[mnf2()])
    ins = bank()
    m = compile_tof_model(structure, ins, tof_grid())
    v = values(structure, ins)
    cell = cell_of(v)
    cp = m.phases[0]
    d = d_spacings(cp.reflections.hkl, *cell)
    rows = {tuple(h): k for k, h in enumerate(cp.reflections.hkl)}
    fn, fm = m._nuclear_f2(0, d, v, cell), m._magnetic_f2(0, d, v, cell)
    k100, k001 = rows[(1, 0, 0)], rows[(0, 0, 1)]
    assert cp.nuclear_mask[k100] == 0.0 and fn[k100] == 0.0
    assert fm[k100] == np.max(fm)
    assert cp.nuclear_mask[k001] == 0.0 and fm[k001] == 0.0


def test_the_isolated_magnetic_peak_carries_its_intensity_onto_the_grid():
    """The unit-area profile holds the row: the (1 0 0) peak, isolated on a
    density bank, integrates over the grid to the intensity ``phase_peaks``
    gives it (to the window's own truncation)."""
    structure = rx.Structure(phases=[mnf2()])
    ins = bank()
    m = compile_tof_model(structure, ins, tof_grid(22000.0, 27000.0))
    v = values(structure, ins)
    cp = m.phases[0]
    k = next(k for k, h in enumerate(cp.reflections.hkl) if tuple(h) == (1, 0, 0))
    (_pos, *_w, intensity), = m.phase_peaks(0, v)
    y = m.bragg_component(v)
    area = float(np.sum(y) * TOF_GRID[2])
    assert area == pytest.approx(float(intensity[k]), rel=2e-3)


def test_a_phase_with_no_moment_reaches_the_nuclear_arithmetic_alone():
    """No moment: no mask, no magnetic data, and the row is
    ``structure_factors_squared`` exactly as before T-6."""
    phase = mnf2()
    phase.atoms[0].moment = None
    phase.magnetic_symmetry = None
    structure = rx.Structure(phases=[phase])
    ins = bank()
    m = compile_tof_model(structure, ins, tof_grid())
    v = values(structure, ins)
    cell = cell_of(v)
    cp = m.phases[0]
    assert cp.nuclear_mask is None and cp.magnetic is None
    d = d_spacings(cp.reflections.hkl, *cell)
    f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites,
                                   *m._site_values(0, v, cell))
    np.testing.assert_array_equal(m._total_f2(0, d, v, cell), f2)


def test_a_phase_stated_by_its_operation_list_enumerates_the_same_rows():
    """A bank reads ``Phase.symmetry_operations`` through ``resolve_group``,
    as ``compile_model`` does: a child with no Hermann-Mauguin symbol (a
    bracketed label) lists the reflections its symbol twin lists."""
    from rietx.crystallography.symmetry import get_spacegroup

    named = mnf2()
    named.atoms[0].moment = None
    named.magnetic_symmetry = None
    ops = [op.triplet() for op in get_spacegroup("P 42/m n m").operations()]
    listed = rx.Phase.model_validate({**named.model_dump(),
                                      "space_group": "[MnF2 child]",
                                      "symmetry_operations": ops})
    ins = bank()
    a = compile_tof_model(rx.Structure(phases=[named]), ins, tof_grid())
    b = compile_tof_model(rx.Structure(phases=[listed]), ins, tof_grid())
    np.testing.assert_array_equal(a.phases[0].reflections.hkl,
                                  b.phases[0].reflections.hkl)
    np.testing.assert_array_equal(a.phases[0].reflections.multiplicity,
                                  b.phases[0].reflections.multiplicity)


# ----------------------------------------------------------------------
# what a bank refuses
# ----------------------------------------------------------------------
def test_the_separate_magnetic_width_is_refused_on_a_bank():
    """WP-1343's magnetic broadening is a deg-2θ width with no flight-time law
    yet: a non-zero value is refused by name, and a single bank's table holds
    the pair locked, as an X-ray table does."""
    phase = mnf2()
    phase.magnetic_lor_size.value = 0.05
    with pytest.raises(ValueError, match=r"magnetic_lor_size is non-zero.*bank"):
        compile_tof_model(rx.Structure(phases=[phase]), bank(), tof_grid())
    with pytest.raises(ValueError, match=r"magnetic_lor_strain is free"):
        compile_tof_model(rx.Structure(phases=[mnf2()]), bank(), tof_grid(),
                          moving_paths={"phases.0.magnetic_lor_strain"})
    table = ParameterTable(rx.Structure(phases=[mnf2()]), bank())
    locked = {e.path for e in table.entries if e.locked}
    assert {"phases.0.magnetic_lor_size",
            "phases.0.magnetic_lor_strain"} <= locked


# ----------------------------------------------------------------------
# a moment refined against one bank
# ----------------------------------------------------------------------
def _synthetic_bank(truth: rx.Structure, *, peak: float = 5e3, seed: int = 1,
                    lo: float = TOF_GRID[0], hi: float = TOF_GRID[1]):
    """Poisson counts from ``truth`` on :func:`bank`, and the true scale."""
    ins = bank()
    grid = tof_grid(lo, hi)
    scaled = truth.model_copy(deep=True)
    y0 = compile_tof_model(scaled, ins, grid).evaluate(values(scaled, ins))
    scale = peak / float(np.max(y0))
    scaled.phases[0].scale.value = scale
    y = compile_tof_model(scaled, ins, grid).evaluate(values(scaled, ins)) + 50.0
    counts = np.random.default_rng(seed).poisson(y).astype(float)
    return (rx.PatternData(tof=grid.tof, intensity=counts.tolist(),
                           sigma=np.sqrt(np.maximum(counts, 1.0)).tolist(),
                           intensity_basis="density"), scale)


MOMENT_PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
    rx.Stage("moment", ["phases.*.atoms.*.moment.*"])])


def test_a_moment_is_recovered_from_one_bank():
    """4.6 μ_B planted, freed from 3.5: back within its esd's reach, with an
    esd, reported by the moment arm as supported, and the scale with it."""
    data, scale = _synthetic_bank(rx.Structure(phases=[mnf2()]))
    start = rx.Structure(phases=[mnf2()])
    start.phases[0].scale.value = 1.5 * scale
    start.phases[0].atoms[0].moment = Moment.from_values(
        (0.0, 0.0, 3.5), "Mn2+", vary=True)
    ref = rx.Refinement(start, bank())
    result = ref.fit(data, plan=MOMENT_PLAN, telemetry=False)
    assert result.status == "converged"
    row = next(p for p in result.parameters if ".moment." in p.path)
    assert row.stderr is not None and row.stderr > 0
    assert abs(row.value - 4.6) < 4.0 * row.stderr, (row.value, row.stderr)
    s = next(p for p in result.parameters if p.path == "phases.0.scale")
    assert abs(s.value - scale) < 4.0 * s.stderr
    evidence = ref.report().magnetic
    assert len(evidence) == 1 and evidence[0].supported is True
    assert evidence[0].magnitude == pytest.approx(row.value)


# ----------------------------------------------------------------------
# T-6b: the moment is scaled by the bank's nuclear lines
# ----------------------------------------------------------------------
#: (1 0 0) alone, d = 4.87 Å at 24.4 ms: a magnetic-only window.
MAGNETIC_ONLY = (22000.0, 28000.0)
#: (1 1 0) nuclear-only at 17.2 ms beside it, and no line carrying both.
TWO_LINES = (15000.0, 28000.0)


def _started(scale: float) -> rx.Structure:
    start = rx.Structure(phases=[mnf2()])
    start.phases[0].scale.value = 1.5 * scale
    start.phases[0].atoms[0].moment = Moment.from_values(
        (0.0, 0.0, 3.5), "Mn2+", vary=True)
    return start


def _unpinned(result):
    return [d for d in result.diagnostics if d.code == "MAGNETIC_SCALE_UNPINNED"]


def test_the_information_kept_is_the_nuclear_share_where_lines_do_not_overlap():
    """1 − ρ² of the scale and magnitude columns equals W_N/(W_N + W_M) on a
    window whose nuclear and magnetic lines are apart, and 0 on a window
    with no nuclear line."""
    from rietx.report.tof_banks import moment_information_kept

    structure = rx.Structure(phases=[mnf2()])
    ins = bank()
    v = values(structure, ins)
    m = compile_tof_model(structure, ins, tof_grid(*TWO_LINES))
    f, w_m = moment_information_kept(m, v, 0)
    zero = dict(v, **{"phases.0.atoms.0.moment.dof0": 0.0})
    y_n = m.phase_component(0, zero)
    w_n = float(np.sum((y_n / m.sigma) ** 2))
    assert 0.0 < f < 1.0
    assert f == pytest.approx(w_n / (w_n + w_m), rel=1e-6)
    m0 = compile_tof_model(structure, ins, tof_grid(*MAGNETIC_ONLY))
    assert moment_information_kept(m0, v, 0)[0] == pytest.approx(0.0, abs=1e-9)


def test_a_magnetic_only_bank_with_a_free_scale_is_named():
    """The positive arm: (1 0 0) alone, scale and moment free.  The code
    fires at 0 and says no other histogram fixes the magnitude; the
    covariance agrees (|ρ| = 1)."""
    data, scale = _synthetic_bank(rx.Structure(phases=[mnf2()]),
                                  lo=MAGNETIC_ONLY[0], hi=MAGNETIC_ONLY[1])
    result = rx.Refinement(_started(scale), bank()).fit(
        data, plan=MOMENT_PLAN, telemetry=False)
    (d,) = _unpinned(result)
    assert d.level == "warning" and d.where == ["phases.0.scale"]
    assert d.value == pytest.approx(0.0, abs=1e-9)
    assert "No other histogram fixes it" in d.message


def test_a_bank_with_its_nuclear_lines_is_silent_and_so_is_a_held_scale():
    """Negative arms: the full window (nuclear lines in reach), and the
    magnetic-only window with its scale held, which pins the magnitude."""
    data, scale = _synthetic_bank(rx.Structure(phases=[mnf2()]))
    result = rx.Refinement(_started(scale), bank()).fit(
        data, plan=MOMENT_PLAN, telemetry=False)
    assert _unpinned(result) == []
    data, scale = _synthetic_bank(rx.Structure(phases=[mnf2()]),
                                  lo=MAGNETIC_ONLY[0], hi=MAGNETIC_ONLY[1])
    start = _started(scale)
    start.phases[0].scale.value = scale
    held = rx.RefinementPlan(stages=[
        rx.Stage("bkg", ["instrument.background.c*"]),
        rx.Stage("moment", ["instrument.background.c*",
                            "phases.*.atoms.*.moment.*"])])
    result = rx.Refinement(start, bank()).fit(data, plan=held, telemetry=False)
    assert _unpinned(result) == []
    row = next(p for p in result.parameters if ".moment." in p.path)
    assert abs(row.value - 4.6) < 4.0 * row.stderr


def test_in_a_joint_fit_the_bank_that_pins_the_moment_is_named():
    """Two banks share the moment: one with the nuclear lines, one
    magnetic-only.  The second is named, the first is quoted as fixing the
    magnitude, and the shared moment comes back at the truth."""
    d_a, s_a = _synthetic_bank(rx.Structure(phases=[mnf2()]), seed=2)
    d_b, _ = _synthetic_bank(rx.Structure(phases=[mnf2()]), seed=3,
                             lo=MAGNETIC_ONLY[0], hi=MAGNETIC_ONLY[1])
    result = rx.MultiHistogramRefinement(_started(s_a), [bank(), bank()]).fit(
        [d_a, d_b], plan=MOMENT_PLAN, telemetry=False)
    (d,) = _unpinned(result)
    assert d.where == ["hist.1.phases.0.scale"]
    assert "The other histograms fix it (histogram 0 keeps" in d.message
    row = next(p for p in result.parameters if ".moment." in p.path)
    assert abs(row.value - 4.6) < 4.0 * row.stderr


def test_a_moment_free_in_direction_refines_on_a_bank():
    """Freeing a moment's angles reaches the stationary-angle test, whose
    analytic block is built from ``derivative_bases``; a bank has none, so it
    keeps the central differences (it raised AttributeError, found on the
    T-6 real-data run, and reproduces here without the gate).  A ferromagnet
    on one site of a tetragonal P 1 cell (in a cubic one the powder average
    is blind to the direction), 3 μ_B along a planted, refined from a tilted
    start with modulus and angles free; the angle test then runs."""
    from rietx.schemas.structure import Atom, Cell, MagneticSymmetry, Phase

    def ferro(m):
        a = 4.4
        return rx.Structure(phases=[Phase(
            name="M", space_group="P 1",
            cell=Cell(a=P(value=a), b=P(value=a), c=P(value=3.3), alpha=P(value=90.0),
                      beta=P(value=90.0), gamma=P(value=90.0)),
            scale=P(value=1.0, min=0.0),
            atoms=[Atom(label="Mn", species="Mn", x=P(value=0.0), y=P(value=0.0),
                        z=P(value=0.0), biso=P(value=0.3, min=0.0, max=5.0),
                        moment=Moment.from_values(m, "Mn2+", vary=True))],
            magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))])

    data, scale = _synthetic_bank(ferro((3.0, 0.0, 0.0)))
    start = ferro((2.6, 0.8, 0.5))
    start.phases[0].scale.value = scale
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("moment", ["phases.*.scale", "phases.*.atoms.*.moment.*"])])
    result = rx.Refinement(start, bank()).fit(data, plan=plan, telemetry=False)
    assert result.status == "converged"
    assert any(".moment.dof1" in p.path for p in result.parameters)
    assert "MOMENT_ANGLE_STATIONARY" in {d.code for d in result.diagnostics}
    row = next(p for p in result.parameters if p.path.endswith("moment.dof0"))
    assert abs(row.value - 3.0) < 4.0 * row.stderr
