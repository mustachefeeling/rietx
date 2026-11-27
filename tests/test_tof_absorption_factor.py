"""A time-of-flight bank's refinable sample absorption factor A_B = µR/λ.

Issue #1867.  ``Geometry.mu_r_per_angstrom`` is GSAS's histogram absorption
parameter (Larson & Von Dreele 2004, LAUR 86-748, "Powder absorption factor",
p. 134), applied per reflection through rietx's one cylinder function (Rouse,
Cooper, York & Chakera 1970, *Acta Cryst.* A26, 682) at µR = A_B·λ_hkl.  The
tests below are the verification the feature ships with (DESIGN-RULES Rule 2):
the off state, an exact identity with the computed-µR path, the derivative
against an analytic oracle and a finite difference, recovery of a known A_B
from a synthetic bank with a control that fails without it, and the two
refusals that are its likeliest misuses (Rule 4).

**Every fixture here is synthetic.**  Silicon at the fixture cell of
:mod:`tests.test_tof_corrections`; the generating Biso is a number of the size
a room-temperature Si refinement gives, chosen here, not quoted.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

import rietx as rx
from rietx.model.absorption import (
    CYLINDER_MU_R_MAX,
    cylinder_absorption,
    cylinder_absorption_and_dmur,
)
from rietx.model.forward_tof import compile_tof_model
from rietx.params.vector import ParameterTable
from tests.test_tof_corrections import (
    TOF_HI,
    TOF_LO,
    _d_of,
    _generated,
    bank,
    blank_pattern,
    silicon,
    values_of,
)

P = rx.Parameter
PATH = "instrument.geometry.mu_r_per_angstrom"
#: Å⁻¹.  µR = A_B·λ then runs about 0.09 to 0.54 over the fixture bank (λ from
#: 0.9 to 5.3 Å at 2θ = 90°): inside the Rouse domain at both ends and a
#: factor of six apart, so the correction has a shape in d.
AB_GEN = 0.10
#: Å².  The generating displacement parameter.
BISO_GEN = 0.46


def ab_bank(value: float = AB_GEN, **kwargs):
    ins = bank(**kwargs)
    ins.geometry.mu_r_per_angstrom = P(value=value)
    return ins


# ------------------------------------------------------------- the off state
def test_an_undeclared_factor_adds_no_row_and_zero_is_bit_identical_to_none():
    """``None`` is the build before this field; A_B = 0 multiplies by exactly 1.

    Two statements, each able to fail alone.  An undeclared factor registers
    no table row and compiles no path, so every existing bank is the
    arithmetic it was.  A declared factor at zero is ``exp(−0.0)`` = 1.0 per
    reflection, so the pattern is the undeclared one **bit for bit**, which is
    what lets a stage free it from zero without moving the start.
    """
    st = silicon()
    plain = bank()
    assert PATH not in {e.path for e in ParameterTable(st, plain).entries}
    m_plain = compile_tof_model(st, plain, blank_pattern())
    assert m_plain.absorption_factor_path is None
    assert m_plain.absorption(np.array([2.0, 1.0]), values_of(st, plain)) is None

    zero = ab_bank(0.0)
    table = ParameterTable(st, zero)
    row = next(e for e in table.entries if e.path == PATH)
    assert row.value == 0.0 and not row.vary
    assert table._units[PATH] == "1/A"
    m_zero = compile_tof_model(st, zero, blank_pattern())
    assert m_zero.absorption_factor_path == PATH
    y_plain = np.asarray(m_plain.evaluate(values_of(st, plain)))
    y_zero = np.asarray(m_zero.evaluate(values_of(st, zero)))
    assert np.array_equal(y_plain, y_zero)


# --------------------------------------------------------------- the identity
def test_the_factor_is_rouse_at_each_reflections_own_mu_r():
    """A(2θ_bank, A_B·λ_hkl) exactly, and exactly the radius path at (A_B, 0).

    The computed path carries µR(λ) = a·λ + b frozen at compile; the refined
    one is the same function with (a, b) = (A_B, 0) read per evaluation.  The
    whole pattern is compared, not only the factor, so a factor applied in the
    wrong place (per channel, or twice) fails here too.
    """
    st = silicon()
    ins = ab_bank(0.07)
    m = compile_tof_model(st, ins, blank_pattern())
    v = values_of(st, ins)
    d = np.asarray(_d_of(m, 0, v))
    lam = np.asarray(m.wavelength_of(d))
    assert np.array_equal(np.asarray(m.absorption(d, v)),
                          np.asarray(cylinder_absorption(90.0, 0.07 * lam)))

    radius = compile_tof_model(st, bank(capillary_radius_mm=3.0), blank_pattern())
    forced = dataclasses.replace(radius, absorption_terms=(0.07, 0.0))
    assert np.array_equal(np.asarray(forced.absorption(d)),
                          np.asarray(m.absorption(d, v)))
    assert np.array_equal(np.asarray(forced.evaluate(v)),
                          np.asarray(m.evaluate(v)))


def test_the_factor_is_read_per_evaluation_and_the_span_follows_it():
    """A free parameter, not a compile-frozen constant like (a, b).

    The same compiled model evaluated at two values of A_B gives two patterns,
    and µR at the two window ends is reported for the value asked about.  A
    caller that does not pass ``values`` is refused rather than handed the
    compile-time factor.
    """
    st = silicon()
    ins = ab_bank(0.05)
    m = compile_tof_model(st, ins, blank_pattern())
    v = values_of(st, ins)
    y1 = np.asarray(m.evaluate(v))
    y2 = np.asarray(m.evaluate({**v, PATH: 0.15}))
    assert not np.array_equal(y1, y2)

    lo, hi = m.mu_r_span({**v, PATH: 0.15})
    lo0, hi0 = m.mu_r_range
    assert (lo, hi) == pytest.approx((3.0 * lo0, 3.0 * hi0), rel=1e-12)
    mu_r = 0.15 * np.asarray(m.wavelength_of(_d_of(m, 0, v)))
    assert mu_r.min() >= lo and mu_r.max() <= hi

    with pytest.raises(ValueError, match="pass values="):
        m.absorption(np.array([2.0]))


# ------------------------------------------------------------- the derivative
def _y(model, values, ab):
    return np.asarray(model.evaluate({**values, PATH: ab}), dtype=np.float64)


def test_d_ycalc_d_ab_matches_the_analytic_rouse_chain_and_a_central_difference():
    """dy/dA_B three ways that share no code path.

    The Bragg sum is linear in each reflection's absorption factor, so
    dy/dA_B is the same sum with A(µR_k) replaced by λ_k·dA/dµR(µR_k) — an
    exact oracle, built from ``cylinder_absorption_and_dmur`` (Rouse's
    expression differentiated by hand).  A central difference must approach it
    as O(h²), and this arm's solver uses finite differences
    (``CompiledTOFModel.analytic_jacobian`` is False), so this is the check on
    the column it builds.  jax's forward-mode derivative of the traced model is
    the third estimator, where jax is installed.
    """
    st = silicon()
    st.phases[0].scale.value = 2.0e4
    ins = ab_bank(AB_GEN)
    m = compile_tof_model(st, ins, blank_pattern())
    v = values_of(st, ins)

    def dfactor(d, values=None):
        lam = np.asarray(m.wavelength_of(d))
        _a, da = cylinder_absorption_and_dmur(90.0, AB_GEN * lam)
        return np.asarray(da) * lam

    oracle_model = dataclasses.replace(m)
    object.__setattr__(oracle_model, "absorption", dfactor)
    exact = (np.asarray(oracle_model.evaluate(v))
             - np.asarray(oracle_model.background(v)))
    scale = float(np.abs(exact).max())
    assert scale > 0.0 and np.all(exact <= 0.0)        # absorption only removes

    errors = []
    for h in (1e-4, 1e-5):
        fd = (_y(m, v, AB_GEN + h) - _y(m, v, AB_GEN - h)) / (2.0 * h)
        errors.append(float(np.abs(fd - exact).max()) / scale)
    assert errors[1] < 1e-8
    assert errors[1] < errors[0] / 50.0                # O(h²): ×100 per decade

    try:
        import jax
        import jax.numpy as jnp

        from rietx.backend.api import resolve_backend
        from rietx.backend.traced import active
        xp = resolve_backend("jax")
    except Exception as exc:  # pragma: no cover - depends on the install
        pytest.skip(f"jax backend unavailable: {exc}")
    with active(xp):
        traced = {k: jnp.asarray(x) for k, x in v.items()}
        _y0, tangent = jax.jvp(lambda ab: m.evaluate({**traced, PATH: ab}),
                               (jnp.asarray(AB_GEN),), (jnp.asarray(1.0),))
    assert float(np.abs(np.asarray(tangent) - exact).max()) / scale < 1e-10


# --------------------------------------------------------------- the recovery
def _fit(data, *, with_factor: bool):
    ins = ab_bank(0.0) if with_factor else bank()
    late = ["phases.*.cell.a", "phases.*.atoms.*.biso"]
    if with_factor:
        late.append(PATH)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("late", late),
    ])
    plan.intermediate_ftol = None
    return rx.Refinement(silicon(1.0), ins, history=False).fit(data, plan=plan)


def _long_d_ratio(result) -> float:
    """Integrated (obs − bkg)/(calc − bkg) over the longest-d quarter of the bank."""
    tof = np.asarray(result.tof)
    keep = tof >= TOF_LO + 0.75 * (TOF_HI - TOF_LO)
    obs = np.asarray(result.y_obs)[keep] - np.asarray(result.y_background)[keep]
    calc = np.asarray(result.y_calc)[keep] - np.asarray(result.y_background)[keep]
    return float(obs.sum() / calc.sum())


def test_a_known_factor_is_recovered_and_leaving_it_out_leaves_the_long_d_deficit():
    """Generated with A_B = 0.10 Å⁻¹ and Biso = 0.46 Å², refitted from A_B = 0.

    With the factor free beside Biso both come back within three esds — the
    degeneracy the constant-wavelength case has is broken because the factor
    runs with λ at one angle and so suppresses the long-d end, the opposite
    end from the Debye-Waller factor.  The control is the same pattern fitted
    without the factor: the long-d lines stay short of the data (the
    obs/calc ratio of the longest-d quarter below 0.95) and Biso is driven
    far from where it was generated, so this test fails if the factor stops
    reaching the model.  The report states the refined A_B and µR at both ends
    of the window, under the parameter's own path.
    """
    data = _generated(silicon(BISO_GEN), ab_bank(AB_GEN), seed=20261127)

    with_it = _fit(data, with_factor=True)
    rows = {p.path: p for p in with_it.parameters}
    ab, biso = rows[PATH], rows["phases.0.atoms.0.biso"]
    assert ab.stderr is not None and biso.stderr is not None
    assert abs(ab.value - AB_GEN) < 3.0 * ab.stderr
    assert abs(biso.value - BISO_GEN) < 3.0 * biso.stderr
    assert abs(_long_d_ratio(with_it) - 1.0) < 0.005

    said = [d for d in with_it.diagnostics if d.code == "SPECIMEN_ABSORPTION_TOF"]
    assert len(said) == 1 and said[0].where == [PATH]
    assert f"{ab.value:.4g}" in said[0].message
    # µR at both window ends, for the refined A_B (not the starting 0): the
    # same pair a model compiled at the refined value carries
    lo, hi = compile_tof_model(silicon(), ab_bank(ab.value), data).mu_r_range
    assert f"runs {lo:.3f} to {hi:.3f}" in said[0].message
    assert 0.0 < lo < hi < CYLINDER_MU_R_MAX
    assert not [d for d in with_it.diagnostics
                if d.code == "ABSORPTION_MU_R_OUT_OF_RANGE"]

    without = _fit(data, with_factor=False)
    b_without = {p.path: p for p in without.parameters}["phases.0.atoms.0.biso"]
    assert _long_d_ratio(without) < 0.95
    assert abs(b_without.value - BISO_GEN) > 10.0 * b_without.stderr
    assert "SPECIMEN_ABSORPTION_TOF" not in [d.code for d in without.diagnostics]


# ----------------------------------------------------------- the misuses
def test_a_radius_or_a_scalar_mu_r_beside_the_factor_is_refused_naming_both():
    """The likeliest misuse: two sources of one µR, the correction applied twice.

    Refused at construction and at assignment (``Geometry`` validates on
    assignment), naming both fields and the fix.
    """
    with pytest.raises(ValueError, match=r"mu_r_per_angstrom is declared together "
                                         r"with capillary_radius_mm.*Keep one"):
        rx.Geometry(capillary_radius_mm=1.0, mu_r_per_angstrom=P(value=0.1))
    ins = bank(capillary_radius_mm=1.0)
    with pytest.raises(ValueError, match="geometry.capillary_radius_mm = None"):
        ins.geometry.mu_r_per_angstrom = P(value=0.1)
    with pytest.raises(ValueError, match="together with mu_r"):
        rx.Geometry(mu_r=0.3, mu_r_per_angstrom=P(value=0.1))
    with pytest.raises(ValueError, match="applies only to debye_scherrer"):
        rx.Geometry(kind="flat_plate_transmission",
                    mu_r_per_angstrom=P(value=0.1))


def test_the_factor_on_a_constant_wavelength_source_is_refused_with_the_reason():
    """At one wavelength a free A_B is a combination of scale and Biso.

    Refused by ``Instrument``'s validator, and — because an assignment to the
    geometry after construction re-runs only ``Geometry``'s validators — again
    by the parameter table, before the fit does any work.  The message quotes
    the manual's constant-wavelength sentence and names the fix.
    """
    cw = rx.Instrument.debye_scherrer(1.54)
    with pytest.raises(ValueError, match="indistinguishable from thermal motion"):
        rx.Instrument(source=cw.source,
                      geometry=rx.Geometry(mu_r_per_angstrom=P(value=0.1)))

    cw.geometry.mu_r_per_angstrom = P(value=0.1, vary=True)
    st = silicon()
    with pytest.raises(ValueError, match=r"Set geometry.mu_r_per_angstrom = None"):
        ParameterTable(st, cw)
    grid = np.linspace(20.0, 120.0, 2001)
    data = rx.PatternData(two_theta=grid.tolist(), intensity=[1.0] * len(grid))
    with pytest.raises(ValueError, match="mu_r_per_angstrom"):
        rx.Refinement(st, cw, history=False).fit(data)
