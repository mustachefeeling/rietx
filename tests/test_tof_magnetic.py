"""A magnetic moment on a time-of-flight bank (issue #1868).

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


def afm_k_half_in_plane():
    """``afm_k_half`` with the moment along a (BNS 51.298), ⊥ c.

    Off a symmetry axis the members of one Laue orbit see different
    projections — (1 0 l) and (0 1 l) do not share |F_⊥|² — so the row is an
    orbit *average* and a bank that evaluated one member would differ."""
    from rietx.crystallography.magnetic.isotropy import candidates
    from rietx.crystallography.magnetic.supercell import magnetic_supercell

    from .test_magnetic_k_trials import tetragonal

    truth = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, "1/2"))[1]
    assert truth.bns_number == "51.298"
    return magnetic_supercell(tetragonal(), truth, magnetic_species=["Mn1"],
                              ion={"Mn1": "Mn3+"}, magnitude=3.0).phase


def bct_anticentred():
    """Mn on 2a of I4/mmm with the body centre's moment reversed, 3 μ_B ∥ c.

    The nuclear group is centred and the magnetic one anti-centred,
    (½, ½, ½)' : the h + k + l odd points the I lattice forbids carry the
    whole magnetic signal.  Stated as a magCIF states it, in the parent's
    cell — P4/mmm's operations with ε = det(R)·R_zz (the axial c moment is
    invariant) and a centring loop carrying the anti-translation.
    ``candidates`` would state this order in a primitive cell of the magnetic
    lattice, which loses the I symbol the row list is built from."""
    from rietx.crystallography.symmetry import get_spacegroup
    from rietx.schemas.structure import Atom, Cell, MagneticSymmetry, Phase

    ops = []
    for op in get_spacegroup("P 4/m m m").operations():
        r = np.array(op.rot, dtype=float) / op.DEN
        eps = "+1" if round(np.linalg.det(r) * r[2, 2]) > 0 else "-1"
        ops.append(f"{op.triplet()},{eps}")
    cell = Cell(**{k: P(value=v) for k, v in dict(
        a=4.0, b=4.0, c=5.2, alpha=90.0, beta=90.0, gamma=90.0).items()})
    return Phase(
        name="bct_anticentred", space_group="I 4/m m m", cell=cell,
        atoms=[Atom(label="Mn1", species="Mn", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=0.0), biso=P(value=0.4),
                    moment=Moment.from_values((0.0, 0.0, 3.0), "Mn2+",
                                              vary=True))],
        magnetic_symmetry=MagneticSymmetry(
            operations=ops, centerings=["x,y,z,+1", "x+1/2,y+1/2,z+1/2,-1"]))


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
                                  lambda: rx.Structure(phases=[afm_k_half()]),
                                  lambda: rx.Structure(phases=[afm_k_half_in_plane()]),
                                  lambda: rx.Structure(phases=[bct_anticentred()])],
                         ids=["MnF2_k0", "k00half_supercell", "k00half_moment_in_plane",
                              "I_parent_anticentred"])
def test_the_magnetic_intensity_is_the_constant_wavelength_twins(make):
    """Identity: at every reflection both arms list, p²⟨|F_⊥|²⟩ agrees to
    rounding, and so does the nuclear term — the bank adds rows only where its
    d range reaches further, never a different number at the same d.

    Two cases make the comparison able to fail where a matched-rows check
    cannot: a moment ⊥ c, where an orbit evaluated at one member differs from
    the average, and a centred parent whose magnetic lattice anti-translates
    the centring, where a bank listing its rows by the parent group alone
    loses every h + k + l odd line.  So every constant-wavelength row inside
    the bank's d range must be on the bank, with the same multiplicity."""
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
    on_bank = {tuple(h) for h in cpt.reflections.hkl}
    inside = (dc >= dt.min()) & (dc <= dt.max())
    lost = [tuple(h) for h, k in zip(cpc.reflections.hkl, inside, strict=True)
            if k and tuple(h) not in on_bank]
    assert lost == []
    i, j = np.array(matched).T
    np.testing.assert_array_equal(cpt.reflections.multiplicity[i],
                                  cpc.reflections.multiplicity[j])
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
    ``structure_factors_squared`` exactly as before #1868."""
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


def test_a_moment_free_in_direction_refines_on_a_bank():
    """Freeing a moment's angles reaches the stationary-angle test, whose
    analytic block is built from ``derivative_bases``; a bank has none, so it
    keeps the central differences (it raised AttributeError, found on a
    real-data run, and reproduces here without the gate).  A ferromagnet
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


# ----------------------------------------------------------------------
# issue #1868's verification: identity, derivative, control, misuse
# ----------------------------------------------------------------------
MOMENT = "phases.0.atoms.0.moment.dof0"


def _absorbing_extinguished(ext: float | None = 3000.0):
    """MnF₂ on :func:`bank` with a 3 mm capillary (µR at λ_hkl) and, unless
    ``ext`` is None, Sabine extinction, so every factor of the bank's chain
    differs from 1 and an arm that skipped one on the magnetic term would
    show."""
    structure = rx.Structure(phases=[mnf2()])
    if ext is not None:
        structure.phases[0].extinction = P(value=ext)
    ins = bank()
    ins.geometry.capillary_radius_mm = 3.0
    return structure, ins


def test_the_bank_row_is_the_cw_magnetic_term_times_the_bank_chain():
    """Identity (#1868): per reflection, the bank's intensity is
    scale · m · (|F_N|² + p²⟨|F_⊥|²⟩) · L(d) · A(λ_hkl) · E(λ_hkl), with both
    squared moduli from the **constant-wavelength** model's own functions on a
    CW twin, and the chain's three factors from the bank, with Sabine's E read
    on the total.  Equal to the last bit here; the bar is 1e-13 relative.

    The arm that can fail: the same product with the magnetic term left out
    of A and E (a bank that scaled only the nuclear part) misses by far more
    than the bar."""
    from rietx.crystallography.lattice import cell_volume
    from rietx.model.extinction import sabine_extinction

    structure, ins = _absorbing_extinguished()
    model = compile_tof_model(structure, ins, tof_grid(),
                              moving_paths={"phases.0.extinction"})
    assert model.absorption_terms is not None
    assert not model.phases[0].skip_extinction
    v = values(structure, ins)
    cell = cell_of(v)
    cp = model.phases[0]
    d = d_spacings(cp.reflections.hkl, *cell)
    row = np.asarray(model.phase_peaks(0, v)[0][5], dtype=np.float64)

    cw_ins, cw_data = cw_twin()
    cw = compile_model(structure, cw_ins, cw_data)
    vc = values(structure, cw_ins)
    ccp = cw.phases[0]
    dc = d_spacings(ccp.reflections.hkl, *cell)
    fn_cw = np.asarray(cw._nuclear_f2(0, dc, vc, cell))
    fm_cw = np.asarray(cw._magnetic_f2(0, dc, vc, cell))
    where = {tuple(h): i for i, h in enumerate(np.asarray(ccp.reflections.hkl).tolist())}
    idx = np.array([where[tuple(h)] for h in np.asarray(cp.reflections.hkl).tolist()])
    fn, fm = fn_cw[idx], fm_cw[idx]
    assert np.sum((fn == 0.0) & (fm > 0.0)) >= 3      # magnetic-only rows
    total = fn + fm
    lam = model.wavelength_of(d)
    lorentz = np.asarray(model.lorentz(d))
    absorption = np.asarray(model.absorption(d))
    vol = cell_volume(*cell)
    ext = v["phases.0.extinction"]
    e_total = np.asarray(sabine_extinction(total, lam, vol, TWO_THETA, ext))
    assert absorption.min() < 0.99 and e_total.min() < 0.99
    pre = v["phases.0.scale"] * np.asarray(cp.reflections.multiplicity)
    np.testing.assert_allclose(row, pre * total * lorentz * absorption * e_total,
                               rtol=1e-13, atol=0.0)
    e_nuc = np.asarray(sabine_extinction(fn, lam, vol, TWO_THETA, ext))
    nuclear_only_chain = pre * (fn * absorption * e_nuc + fm) * lorentz
    assert np.max(np.abs(row - nuclear_only_chain) / row.max()) > 1e-3


def test_the_moment_column_on_a_bank_against_closed_form_and_differences():
    """Derivative (#1868).  A bank has no analytic Jacobian
    (``analytic_jacobian = False``), so the moment's column is the solver's
    finite-difference fallback, as every bank column is; and the magnetic
    path is numpy-only on both arms (``_moment_dofs`` builds a numpy vector),
    so ``jax.jvp`` cannot be taken through a moment.  The references instead:

    * with extinction off, |F_M|² is quadratic in the modulus and every other
      factor is linear in the row, so dy/dμ = 2·(y(μ) − y(0))/μ exactly; the
      central difference matches it to rounding at two steps;
    * with extinction on, the central difference converges as O(h²) (the
      error ratio over a halving is 4), and the solver's own column agrees
      with the Richardson extrapolate to its forward-difference precision.
    """
    from rietx.optimize.least_squares import _make_jacobian

    structure, ins = _absorbing_extinguished(ext=None)
    v = values(structure, ins)
    model = compile_tof_model(structure, ins, tof_grid())

    def y(mu, m=model, vv=v):
        return np.asarray(m.evaluate({**vv, MOMENT: mu}), dtype=np.float64)

    mu0 = v[MOMENT]
    exact = 2.0 * (y(mu0) - y(0.0)) / mu0
    for h in (0.2, 0.1):
        central = (y(mu0 + h) - y(mu0 - h)) / (2.0 * h)
        assert np.max(np.abs(central - exact)) / np.max(np.abs(exact)) < 1e-12

    structure, ins = _absorbing_extinguished()
    v = values(structure, ins)
    table = ParameterTable(structure, ins)
    assert table.free_paths == [MOMENT]
    model = compile_tof_model(structure, ins, tof_grid(),
                              moving_paths={MOMENT, "phases.0.extinction"})
    central = {h: (y(mu0 + h, model, v) - y(mu0 - h, model, v)) / (2.0 * h)
               for h in (0.4, 0.2, 0.1)}
    e1 = np.max(np.abs(central[0.4] - central[0.2]))
    e2 = np.max(np.abs(central[0.2] - central[0.1]))
    assert 3.6 < e1 / e2 < 4.4, e1 / e2
    richardson = (4.0 * central[0.1] - central[0.2]) / 3.0
    column = (np.asarray(_make_jacobian(model, table)(table.x0()))[:model.n_points, 0]
              * np.asarray(model.sigma))
    scale = np.max(np.abs(richardson))
    # the solver's column is ∂r/∂μ with r = (y_obs − y)/σ, so column·σ is
    # −dy/dμ: a column of the wrong sign fails here
    assert np.max(np.abs(column + richardson)) / scale < 1e-6


def test_a_moment_held_at_zero_leaves_the_magnetic_lines_in_the_residual():
    """Recovery's control (#1868).  MnF₂ is MAGNDATA 0.15 (BNS 136.499,
    P4₂'/mnm', k = 0, 4.6 μ_B along c; Yamani, Tun & Ryan 2010, Can. J. Phys.
    88, 771, doi:10.1139/p10-081), and :func:`test_a_moment_is_recovered_
    from_one_bank` refines that moment back from 3.5.  The same pattern with
    the moment held at zero cannot fit the magnetic lines: the (1 0 0) window
    (24.4 ms, absent in P 4₂/mnm) keeps them in its residual, χ² there more
    than 100 times the freed fit's, so the recovery test can fail."""
    data, scale = _synthetic_bank(rx.Structure(phases=[mnf2()]))
    tof = np.asarray(data.tof)
    window = (tof > 23000.0) & (tof < 26000.0)

    def window_chi2(moment, plan):
        start = rx.Structure(phases=[mnf2()])
        start.phases[0].scale.value = 1.5 * scale
        start.phases[0].atoms[0].moment = moment
        ref = rx.Refinement(start, bank())
        result = ref.fit(data, plan=plan, telemetry=False)
        assert result.status == "converged"
        r = (np.asarray(data.intensity) - np.asarray(ref.predict(data))) / np.asarray(data.sigma)
        return float(np.sum(r[window] ** 2))

    freed = window_chi2(Moment.from_values((0.0, 0.0, 3.5), "Mn2+", vary=True),
                        MOMENT_PLAN)
    held = window_chi2(Moment.from_values((0.0, 0.0, 0.0), "Mn2+", vary=False),
                       rx.RefinementPlan(stages=[rx.Stage(
                           "scale_bkg", ["phases.*.scale", "instrument.background.c*"])]))
    assert freed < 2.0 * int(window.sum())
    assert held > 100.0 * freed


def test_a_propagation_vector_on_a_bank_is_refused_beside_a_moment():
    """Misuse (Rule 4, #1868).  The likeliest misuse of a bank that draws a
    moment is to hand it a k-satellite structure: a phase with
    ``propagation_vector``, beside a magnetic phase.  The bank builds no
    satellite list, so it raises at compile, before any reflection is
    generated, naming the field, the rung (#193) and the form a bank does
    take (#1868); ``Refinement.fit`` raises the same before a solve.  A
    propagation vector *with* a moment on one phase is refused earlier still,
    by the schema, on either arm."""
    import pydantic

    structure = rx.Structure(phases=[mnf2(), mnf2()])
    structure.phases[1].atoms[0].moment = None
    structure.phases[1].magnetic_symmetry = None
    structure.phases[1].propagation_vector = ("0", "0", "1/2")
    with pytest.raises(ValueError, match=r"phases\.1 declares propagation_vector") as exc:
        compile_tof_model(structure, bank(), tof_grid())
    message = str(exc.value)
    assert "issue #193" in message and "issue #1868" in message
    assert "propagation_vector = None" in message
    with pytest.raises(ValueError, match=r"propagation_vector"):
        rx.Refinement(structure, bank(), history=False).fit(tof_grid(),
                                                             plan=MOMENT_PLAN)
    with pytest.raises((ValueError, pydantic.ValidationError),
                       match="propagation vector and a moment"):
        both = mnf2()
        both.propagation_vector = ("0", "0", "1/2")
        rx.Structure(phases=[both])
    structure.phases[1].propagation_vector = None
    assert compile_tof_model(structure, bank(), tof_grid()).n_points > 0


def test_a_magnetic_bank_on_the_jax_backend_is_refused_by_name():
    """The second misuse: asking for the jax backend on a magnetic bank.  The
    magnetic structure factor has no traced twin on either arm, so the fit
    refuses by name and says where the column is exact, as on a scan."""
    data, scale = _synthetic_bank(rx.Structure(phases=[mnf2()]))
    start = rx.Structure(phases=[mnf2()])
    start.phases[0].scale.value = scale
    try:
        ref = rx.Refinement(start, bank(), backend="jax")
    except Exception as exc:  # pragma: no cover - depends on the install
        pytest.skip(f"jax backend unavailable: {exc}")
    with pytest.raises(NotImplementedError, match="no traced twin.*numpy"):
        ref.fit(data, plan=MOMENT_PLAN, telemetry=False)
