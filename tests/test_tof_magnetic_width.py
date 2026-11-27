"""The separate magnetic width on a time-of-flight bank (#1868).

WP-1343's ``magnetic_lor_size``/``magnetic_lor_strain`` broaden a phase's
magnetic lines beyond its nuclear ones.  On a scan they add to the 1/cosθ and
tanθ Lorentzian coefficients; on a bank they add a Lorentzian to the magnetic
lines' γ(d) by the bank's own sample law, DIFC·(Δd/d·d + (K/L)·d²), stored as
the bank stores ``lor_size`` (K/L in Å⁻¹) and ``lor_strain`` (the λ-free
coefficient).  The case that required it is real: WISH NiO, run 29726 (ISIS
RB1510360), whose (½ ½ ½) line is about twice as broad in Δd/d as its nuclear
neighbours.

**Every fixture is synthetic and written here**, on the round-number bank of
``test_tof_magnetic``: MnF₂ (Erickson 1953) for the law and its reach, and
NiO's k = (½ ½ ½) child (BNS 2.7 on R-3m:R) for the moment direction, which
MnF₂'s symmetry fixes.  A width shared between a scan and a bank in one
joint fit is not tested here: a joint fit refuses a bank on this tree.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward_tof import (
    compile_tof_model,
    magnetic_broadening_terms,
)
from rietx.model.profiles.caglioti import microstrain_width
from rietx.model.profiles.tof import tof_sample_gamma
from rietx.params.vector import ParameterTable

from .test_joint_xray_neutron import mnf2
from .test_tof_magnetic import (
    DIFC,
    bank,
    tof_grid,
    values,
)

pytestmark = pytest.mark.xdist_group("tof_magnetic")

SIZE = "phases.0.magnetic_lor_size"
STRAIN = "phases.0.magnetic_lor_strain"
#: K/L of a 1250 Å magnetic coherence length: Δd/d = 0.39 % at MnF₂'s (1 0 0),
#: d = 4.87 Å, beside a nuclear resolution of about 0.8 % on this bank.
SIZE_TRUE = 8.0e-4


def _with_width(size: float = 0.0, strain: float = 0.0) -> rx.Structure:
    phase = mnf2()
    phase.magnetic_lor_size.value = size
    phase.magnetic_lor_strain.value = strain
    return rx.Structure(phases=[phase])


# ----------------------------------------------------------------------
# the law and its reach
# ----------------------------------------------------------------------
def test_the_width_is_free_on_a_bank_and_off_draws_one_family():
    """The pair is a free row of a single bank's table (no longer locked), and
    at its off state the compile builds one family: the phase's arithmetic is
    the pre-law draw bit for bit."""
    table = ParameterTable(_with_width(), bank())
    by_path = {e.path: e for e in table.entries}
    assert not by_path[SIZE].locked and not by_path[STRAIN].locked
    off = compile_tof_model(_with_width(), bank(), tof_grid())
    assert off.mag_split(0) is False
    assert off.phases[0].win_mag is None and off.flat_windows_mag == [None]
    with pytest.raises(ValueError, match="second frozen family was not built"):
        off.phase_peaks(0, values(_with_width(), bank()), component=1)


@pytest.mark.parametrize("size, strain", [(SIZE_TRUE, 0.0), (0.0, 0.05)],
                         ids=["size", "strain"])
def test_the_magnetic_lines_take_the_banks_own_size_and_strain_law(size, strain):
    """γ_magnetic − γ_nuclear is exactly DIFC·(Δd/d·d + (K/L)·d²) with the
    pair read as ``lor_size`` and ``lor_strain`` are read; α, β, σ, the
    positions and the nuclear component are untouched."""
    st = _with_width(size, strain)
    v = values(st, bank())
    m = compile_tof_model(st, bank(), tof_grid())
    assert m.mag_split(0) and m.profile_kind == "pseudovoigt"
    (pn, an, bn, sn, gn, _in), = m.phase_peaks(0, v, component=0)
    (pm, am, bm, sm, gm, _im), = m.phase_peaks(0, v, component=1)
    d = np.asarray(pn) / DIFC
    for a, b in ((pn, pm), (an, am), (bn, bm), (sn, sm)):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    s_l, e_l = magnetic_broadening_terms(0, v)
    assert (s_l, e_l) == (size, microstrain_width(strain))
    np.testing.assert_allclose(np.asarray(gm) - np.asarray(gn),
                               tof_sample_gamma(d, DIFC, s_l, e_l),
                               rtol=1e-12, atol=1e-12)
    # the nuclear component is the off-state phase's nuclear term alone
    off = compile_tof_model(_with_width(), bank(), tof_grid())
    (_p, _a, _b, _s, g0, _i), = off.phase_peaks(0, values(_with_width(), bank()))
    np.testing.assert_array_equal(np.asarray(gn), np.asarray(g0))


def test_the_two_components_sum_to_the_one_family_draw_at_equal_widths():
    """A split forced at width zero (the path movable, the value 0) draws
    ⟨|F_N|²⟩ and p²⟨|F_⊥|²⟩ on two families at one γ: their sum is the
    one-family curve to rounding, so the split changes nothing but the
    association — and the batched scatter equals the reflection loop."""
    st = _with_width()
    v = values(st, bank())
    one = compile_tof_model(st, bank(), tof_grid())
    two = compile_tof_model(st, bank(), tof_grid(), moving_paths={SIZE})
    assert two.mag_split(0)
    a = np.asarray(one.evaluate(v))
    b = np.asarray(two.evaluate(v))
    # the magnetic family's windows are wider (sized at the floor), so the
    # far tails it adds are real area the one-family windows dropped
    assert np.max(np.abs(a - b)) < 2e-4 * np.max(np.abs(a))
    pv = compile_tof_model(st, bank(), tof_grid(),
                           moving_paths={"instrument.source.profile_tof.gam1"})
    c = np.asarray(pv.evaluate(v))
    assert np.max(np.abs(c - b)) < 2e-4 * np.max(np.abs(a))
    st = _with_width(SIZE_TRUE)
    m = compile_tof_model(st, bank(), tof_grid())
    v = values(st, bank())
    y_b = np.asarray(m._phase_component_batched(0, v))
    y_s = np.asarray(m._phase_component_scalar(0, v))
    assert np.max(np.abs(y_b - y_s)) <= 1e-13 * np.max(np.abs(y_b))
    assert m.phase_line_counts()[0] == int(np.count_nonzero(
        (m.phases[0].win[0, :, 1] > m.phases[0].win[0, :, 0])
        | (m.phases[0].win_mag[0, :, 1] > m.phases[0].win_mag[0, :, 0])))


def test_the_width_column_reaches_the_magnetic_family_only():
    """The finite-difference column of ``magnetic_lor_size`` (the arm declares
    no analytic Jacobian, so every column is FD): two central steps a decade
    apart agree, the column is non-zero, and it is exactly zero outside the
    magnetic family's windows and on the nuclear component."""
    st = _with_width(SIZE_TRUE)
    m = compile_tof_model(st, bank(), tof_grid(), moving_paths={SIZE})
    v = values(st, bank())

    def col(h):
        up, dn = dict(v), dict(v)
        up[SIZE] += h
        dn[SIZE] -= h
        return (np.asarray(m.evaluate(up)) - np.asarray(m.evaluate(dn))) / (2 * h)

    c1, c2 = col(1e-5), col(1e-6)
    scale = np.max(np.abs(c1))
    assert scale > 0.0
    assert np.max(np.abs(c1 - c2)) < 1e-4 * scale
    inside = np.zeros(m.n_points, dtype=bool)
    for k in range(m.phases[0].win_mag.shape[1]):
        i0, i1 = m.phases[0].win_mag[0, k]
        inside[i0:i1] = True
    assert np.all(c1[~inside] == 0.0)
    up = dict(v)
    up[SIZE] += 1e-5
    (_p, _a, _b, _s, g_up, _i), = m.phase_peaks(0, up, component=0)
    (_p, _a, _b, _s, g_0, _i), = m.phase_peaks(0, v, component=0)
    np.testing.assert_array_equal(np.asarray(g_up), np.asarray(g_0))


@pytest.mark.parametrize("backend", ["jax", "torch"])
def test_the_split_draw_agrees_across_backends(backend):
    """The traced backends draw the two families through the reflection loop:
    the forward agrees with numpy's batched scatter to rounding (rows
    self-skip without their backend, ``test_tof_refine``'s idiom)."""
    from rietx.backend.api import resolve_backend
    from rietx.backend.traced import active

    try:
        xp = resolve_backend(backend)
    except Exception as exc:  # pragma: no cover - depends on the install
        pytest.skip(f"{backend} backend unavailable: {exc}")
    st = _with_width(SIZE_TRUE, 0.05)
    m = compile_tof_model(st, bank(), tof_grid())
    v = values(st, bank())
    y_numpy = np.asarray(m.evaluate(v), dtype=np.float64)
    with active(xp):
        y_traced = np.asarray(m.evaluate(dict(v)), dtype=np.float64)
    rel = np.abs(y_numpy - y_traced) / np.maximum(np.abs(y_numpy), 1e-300)
    assert float(rel.max()) < 1e-12


def test_a_moving_width_from_zero_is_sized_at_the_scan_floor_read_at_the_bank():
    """Freed from zero, the magnetic family's windows are sized as if the width
    were ``MAGNETIC_SIZING_FLOOR`` read at the bank: Δd/d = floor·(π/360)/sin θ
    for size; the value drawn is still zero."""
    from rietx.model.forward import MAGNETIC_SIZING_FLOOR

    st = _with_width()
    m = compile_tof_model(st, bank(), tof_grid(), moving_paths={SIZE})
    n = m.phases[0].win
    g = m.phases[0].win_mag
    assert np.all(g[0, :, 0] <= n[0, :, 0]) and np.all(g[0, :, 1] >= n[0, :, 1])
    assert np.any((g[0, :, 1] - g[0, :, 0]) > (n[0, :, 1] - n[0, :, 0]))
    dd = MAGNETIC_SIZING_FLOOR * (math.pi / 360.0) / math.sin(math.radians(30.0))
    assert dd == pytest.approx(1.745e-3, rel=1e-3)
    (_p, _a, _b, _s, gm, _i), = m.phase_peaks(0, values(st, bank()), component=1)
    (_p, _a, _b, _s, gn, _i), = m.phase_peaks(0, values(st, bank()), component=0)
    np.testing.assert_array_equal(np.asarray(gm), np.asarray(gn))


# ----------------------------------------------------------------------
# the width refined against one bank
# ----------------------------------------------------------------------
def _synthetic(truth: rx.Structure, *, seed: int, peak: float = 2e4):
    ins = bank()
    grid = tof_grid()
    scaled = truth.model_copy(deep=True)
    y0 = np.asarray(compile_tof_model(scaled, ins, grid).evaluate(values(scaled, ins)))
    scale = peak / float(np.max(y0))
    scaled.phases[0].scale.value = scale
    y = np.asarray(compile_tof_model(scaled, ins, grid).evaluate(
        values(scaled, ins))) + 50.0
    counts = np.random.default_rng(seed).poisson(y).astype(float)
    return rx.PatternData(tof=grid.tof, intensity=counts.tolist(),
                          sigma=np.sqrt(np.maximum(counts, 1.0)).tolist(),
                          intensity_basis="density"), scale


def _plan(free_width: bool) -> rx.RefinementPlan:
    common = ["phases.*.scale", "instrument.background.c*",
              "phases.*.atoms.*.moment.*"]
    return rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("moment", common + ([SIZE] if free_width else []))])


def _fit(data, scale, free_width):
    start = _with_width()
    start.phases[0].scale.value = scale
    start.phases[0].atoms[0].moment = rx.Moment.from_values(
        (0.0, 0.0, 4.0), "Mn2+", vary=True)
    return rx.Refinement(start, bank(), history=False).fit(
        data, plan=_plan(free_width), telemetry=False)


def _moment(result):
    return next(p for p in result.parameters if p.path.endswith("moment.dof0"))


@pytest.fixture(scope="module")
def mnf2_arms():
    broad, s_b = _synthetic(_with_width(SIZE_TRUE), seed=5)
    equal, s_e = _synthetic(_with_width(), seed=6)
    return {(arm, free): _fit(data, scale, free)
            for arm, (data, scale) in (("broad", (broad, s_b)),
                                       ("equal", (equal, s_e)))
            for free in (False, True)}


def test_broader_magnetic_lines_give_back_their_width_and_the_moment(mnf2_arms):
    """Positive arm: planted K/L = 8e-4 Å⁻¹ comes back within its esd's reach,
    and the moment, biased low when the magnetic lines are drawn at the
    nuclear width, moves to the planted 4.6 μ_B."""
    held, free = mnf2_arms[("broad", False)], mnf2_arms[("broad", True)]
    assert free.status == "converged"
    w = free.parameter(SIZE)
    assert w.stderr is not None and w.stderr > 0.0
    assert abs(w.value - SIZE_TRUE) < 3.0 * w.stderr, (w.value, w.stderr)
    m_held, m_free = _moment(held), _moment(free)
    assert abs(m_free.value - 4.6) < abs(m_held.value - 4.6)
    assert abs(m_free.value - 4.6) < 3.0 * m_free.stderr
    assert free.statistics.rwp < held.statistics.rwp


def test_equal_widths_give_a_width_consistent_with_zero(mnf2_arms):
    """Negative arm: no planted width, the freed one is within 3 esd of zero
    (or on its floor), and the moment moves by less than its esd."""
    held, free = mnf2_arms[("equal", False)], mnf2_arms[("equal", True)]
    assert free.status == "converged"
    w = free.parameter(SIZE)
    assert w is None or w.value < 3.0 * (w.stderr or 0.0) or w.at_bound
    m_held, m_free = _moment(held), _moment(free)
    assert abs(m_free.value - m_held.value) < m_held.stderr


def test_an_unmeasured_bank_width_is_named_in_the_banks_unit(mnf2_arms):
    """The support finding reads values and esds alone, so it runs on a bank,
    and names the size in the bank's K/L unit rather than a scan's degrees."""
    free = mnf2_arms[("equal", True)]
    rows = [d for d in free.diagnostics
            if d.code == "MAGNETIC_WIDTH_UNMEASURED" and SIZE in d.where]
    assert rows, [d.code for d in free.diagnostics]
    assert "Å⁻¹" in rows[0].message and " deg " not in rows[0].message
    broad = mnf2_arms[("broad", True)]
    assert not [d for d in broad.diagnostics
                if d.code == "MAGNETIC_WIDTH_UNMEASURED" and SIZE in d.where]


# ----------------------------------------------------------------------
# the moment direction: NiO's k = (½ ½ ½) child (slow: two pairs of fits)
# ----------------------------------------------------------------------
#: [111] of the cubic parent in the BNS 2.7 child cell ``magnetic_supercell``
#: builds from R-3m:R — the axis ψ is measured from, as in Pomjakushin 2024.
U_CHILD = np.array([-0.5, 1.0, 1.0])
PSI_TRUE, PSI_START, AZIMUTH, MU = 71.0, 60.0, 30.0, 1.94
NIO_SIZE = 1.0e-3


def _nio_child():
    from fractions import Fraction

    from rietx.crystallography.magnetic.isotropy import candidates
    from rietx.crystallography.magnetic.supercell import magnetic_supercell
    from rietx.schemas.common import Parameter as P
    from rietx.schemas.structure import Atom, Cell, Phase

    ar = 4.177 / math.sqrt(2.0)
    parent = Phase(
        name="NiO", space_group="R -3 m:R",
        cell=Cell(a=P(value=ar), b=P(value=ar), c=P(value=ar),
                  alpha=P(value=60.0), beta=P(value=60.0), gamma=P(value=60.0)),
        scale=P(value=1.0, min=0.0),
        atoms=[Atom(label=el, species=el, x=P(value=xyz), y=P(value=xyz),
                    z=P(value=xyz), biso=P(value=0.3, min=0.0, max=5.0))
               for el, xyz in (("Ni", 0.0), ("O", 0.5))])
    h = Fraction(1, 2)
    cand = next(c for c in candidates(parent.space_group, (0, 0, 0),
                                      (h, h, h)).candidates
                if c.bns_number == "2.7")
    return magnetic_supercell(parent, cand, magnetic_species="Ni", ion="Ni2+",
                              magnitude=2.0).phase


def _cell6(phase):
    return tuple(float(getattr(phase.cell, k).value)
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))


def _axis(cell6):
    from rietx.crystallography.magnetic.operators import (
        _crystalaxis_to_cartesian_matrix,
    )
    return (_crystalaxis_to_cartesian_matrix(cell6) * np.array(cell6[:3])) @ U_CHILD


def _components(psi, cell6):
    """Crystal components of a moment at ψ to [111] and AZIMUTH about it."""
    from rietx.crystallography.magnetic.operators import moment_to_cartesian

    basis = np.column_stack([moment_to_cartesian(e, cell6) for e in np.eye(3)])
    u = _axis(cell6)
    u = u / np.linalg.norm(u)
    t = np.cross(u, [0.0, 0.0, 1.0])
    t /= np.linalg.norm(t)
    w = np.cross(u, t)
    p, a = math.radians(psi), math.radians(AZIMUTH)
    m = MU * (math.cos(p) * u + math.sin(p) * (math.cos(a) * t + math.sin(a) * w))
    return tuple(float(c) for c in np.linalg.solve(basis, m))


def _psi(phase):
    from rietx.crystallography.magnetic.operators import moment_to_cartesian

    cell6 = _cell6(phase)
    atom = next(a for a in phase.atoms if a.moment is not None)
    m = moment_to_cartesian(np.asarray(atom.moment.values()), cell6)
    u = _axis(cell6)
    c = abs(m @ u) / np.linalg.norm(m) / np.linalg.norm(u)
    return math.degrees(math.acos(min(1.0, c)))


def _nio(psi, size):
    phase = _nio_child()
    j = next(i for i, a in enumerate(phase.atoms) if a.moment is not None)
    phase.atoms[j].moment = rx.Moment.from_values(
        _components(psi, _cell6(phase)), "Ni2+", vary=True)
    phase.magnetic_lor_size.value = size
    return rx.Structure(phases=[phase])


def _nio_fit(data, scale, free_width):
    start = _nio(PSI_START, 0.0)
    start.phases[0].scale.value = scale
    ref = rx.Refinement(start, bank(), history=False)
    result = ref.fit(data, plan=_plan(free_width), telemetry=False)
    return result, _psi(ref.structure.phases[0])


@pytest.mark.slow
def test_on_nio_the_freed_width_moves_psi_toward_the_truth():
    """Positive arm on the direction: magnetic lines broader than the nuclear
    ones, ψ planted at 71°.  Held at the nuclear width the fit lands off 71°;
    freed, the width comes back within its esd's reach and ψ moves toward
    the truth.  Negative arm: equal widths, and freeing the width moves ψ by
    less than the held fit's own scatter about the truth."""
    broad, s_b = _synthetic(_nio(PSI_TRUE, NIO_SIZE), seed=11)
    (held, psi_held), (free, psi_free) = (_nio_fit(broad, s_b, f)
                                          for f in (False, True))
    w = free.parameter(SIZE)
    assert abs(w.value - NIO_SIZE) < 3.0 * w.stderr, (w.value, w.stderr)
    assert abs(psi_free - PSI_TRUE) < abs(psi_held - PSI_TRUE), (psi_held, psi_free)
    equal, s_e = _synthetic(_nio(PSI_TRUE, 0.0), seed=12)
    (held0, psi_held0), (free0, psi_free0) = (_nio_fit(equal, s_e, f)
                                              for f in (False, True))
    w0 = free0.parameter(SIZE)
    assert w0 is None or w0.value < 3.0 * (w0.stderr or 0.0) or w0.at_bound
    assert abs(psi_free0 - psi_held0) < 0.5, (psi_held0, psi_free0)
    m0, m1 = _moment(held0), _moment(free0)
    assert abs(m1.value - m0.value) < m0.stderr
