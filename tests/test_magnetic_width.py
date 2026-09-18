"""WP-1343 — the magnetic peaks are broader, and the moment pays for it.

A phase's magnetic contribution is drawn with its own extra Lorentzian width,
refined as a term of that phase rather than of a second one.  What this file
holds is the four claims that make the term worth having, and each of them is
a way the shape could be wrong while every number still looked plausible:

1. **The two contributions are separable at the per-line intensity**, and
   every factor after the structure factor multiplies both.  The structure
   factors add to the bit; the intensities to rounding, because fp
   multiplication does not distribute — which is itself why the off state has
   to be a structural skip and not a coincidence of widths.
2. **The off state is a structural skip, not two floats agreeing.**  With both
   terms at their zero default the second frozen family is not built, no
   magnetic-width memo slot is ever populated, and ``phase_peaks`` reads
   ``_total_f2`` on one pass — the WP-1327 code path.  Asserted on **both**
   the gated compile (``moving_paths`` given, the two paths absent from it)
   and the ungated one (``moving_paths=None``), because those are two
   different reasons for the same skip and only one of them is a claim.
3. **The moment pays for a missing width, measurably.**  The synthetic round
   trip recovers a planted width and moment; the same pattern
   refined without the term returns the moment low by more than its esd and
   ``MAGNETIC_WIDTH_UNMODELLED`` fires naming the magnetic-only reflections.
   The control is the same pattern generated with **no** extra broadening,
   where the diagnostic must stay silent — a diagnostic that cannot fail
   confirms whatever you hoped.
4. **An unmeasurable width is named, not quoted.**  A k = 0 structure comes
   back with an esd larger than the value and
   ``MAGNETIC_WIDTH_UNMEASURED`` says so.

References
----------
Scherrer's law as the package already carries it
(``model/profiles/caglioti.py``), with the magnetic coherence length in place
of the crystallite size; Rodríguez-Carvajal, J. (1993). *Physica B* **192**,
55 — FullProf, where a separate magnetic phase is what carries its own size
and strain, and the route WP-1327 closed.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.model.forward import MAGNETIC_SIZING_FLOOR, compile_model
from rietx.params.multi import SIZE_LAMBDA_POWER
from rietx.params.vector import ParameterTable
from rietx.report.magnetic import _classified_reflections, magnetic_width_findings
from rietx.report.schemas import (
    MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA,
    MAGNETIC_WIDTH_SIGMA,
)
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Moment, Phase
from rietx.strategy.magnetic import (
    MAGNETIC_WIDTH_SEED_DEG,
    MAGNETIC_WIDTH_STAGE_PATHS,
)
from rietx.strategy.staged import PLAN_PRESETS
from tests.test_magnetic import LAMBDA_CW, MNF2_BNS, MNF2_CELL, atom, cell

#: the size term used wherever a test needs the split path live
SIZE = 0.30


def _mnf2(*, size=0.0, strain=0.0, moment=(0.0, 0.0, 4.6), magnetic=True):
    """MnF₂ under BNS 136.499, optionally with the two magnetic widths set."""
    ph = Phase(
        name="MnF2", space_group="P 42/m n m", cell=cell(*MNF2_CELL),
        atoms=[atom("Mn", "Mn", (0.0, 0.0, 0.0),
                    moment=None if not magnetic
                    else Moment.from_values(moment, "Mn2+", vary=True)),
               atom("F", "F", (0.3050, 0.3050, 0.0))],
        magnetic_symmetry=MNF2_BNS if magnetic else None)
    ph.scale.value = 1.0
    if size or strain:
        ph.magnetic_lor_size = Parameter(value=size, min=0.0, unit="deg",
                                         transform="softplus")
        ph.magnetic_lor_strain = Parameter(value=strain, min=0.0, unit="deg",
                                           transform="softplus")
    return ph


def _state(ph, *, moving=None, step=0.02, lo=8.0, hi=140.0):
    st = rx.Structure(phases=[ph])
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    ins.profile.u.value, ins.profile.w.value = 0.05, 0.02
    ins.profile.x.value = 0.05
    tt = np.arange(lo, hi, step)
    pat = rx.PatternData(two_theta=tt.tolist(),
                         intensity=np.ones_like(tt).tolist())
    model = compile_model(st, ins, pat, mode="rietveld",
                          moving_paths=None if moving is None else set(moving))
    table = ParameterTable(st, ins)
    return model, table, table.decode(table.x0())


# ===================================================== the schema and the table

def test_both_terms_default_to_exactly_off():
    ph = _mnf2()
    assert ph.magnetic_lor_size.value == 0.0
    assert ph.magnetic_lor_strain.value == 0.0
    for p in (ph.magnetic_lor_size, ph.magnetic_lor_strain):
        assert p.min == 0.0 and p.transform == "softplus"
        assert p.unit == "deg" and not p.vary


def test_a_nonzero_magnetic_width_needs_a_moment_block():
    """A width on a component that does not exist is a name nothing writes.

    WP-1076's trap, refused at the schema rather than ignored in the forward
    model: only a *non-zero* value, because the zero default is carried by
    every phase in the package.
    """
    plain = _mnf2(magnetic=False)
    assert plain.magnetic_lor_size.value == 0.0        # the default is fine

    for name in ("magnetic_lor_size", "magnetic_lor_strain"):
        with pytest.raises(ValidationError, match="declares no magnetic_symmetry"):
            plain.model_copy(deep=True).model_validate({
                **plain.model_dump(),
                name: {"value": 0.2, "min": 0.0, "transform": "softplus"}})
    # vary alone is refused too, at the same place
    with pytest.raises(ValidationError, match="declares no magnetic_symmetry"):
        Phase.model_validate({
            **plain.model_dump(),
            "magnetic_lor_size": {"value": 0.0, "vary": True, "min": 0.0,
                                  "transform": "softplus"}})


def test_the_paths_exist_only_on_a_phase_with_a_moment():
    """So no stage can free a term whose component is absent."""
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    mag = ParameterTable(rx.Structure(phases=[_mnf2()]), ins)
    plain = ParameterTable(rx.Structure(phases=[_mnf2(magnetic=False)]), ins)
    for name in ("magnetic_lor_size", "magnetic_lor_strain"):
        assert f"phases.0.{name}" in mag._paths
        assert f"phases.0.{name}" not in plain._paths


def test_a_non_magnetic_phase_gains_no_table_row_at_all():
    """The bit-identity claim one rank below the pattern: an ordinary fit's
    parameter table is the table it was, entry for entry."""
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    plain = ParameterTable(rx.Structure(phases=[_mnf2(magnetic=False)]), ins)
    assert not [e.path for e in plain.entries if "magnetic_lor" in e.path]


def test_the_size_term_carries_one_power_of_lambda():
    """WP-1131's invariant: a size coefficient is (180/π)·K·λ/L, so one
    magnetic domain needs coefficients in the ratio λ₂/λ₁ across two
    histograms.  Its strain partner is λ-free and must **not** be listed."""
    assert SIZE_LAMBDA_POWER["magnetic_lor_size"] == 1.0
    assert "magnetic_lor_strain" not in SIZE_LAMBDA_POWER


def test_a_joint_fit_converts_the_shared_magnetic_size_between_wavelengths():
    """The two-histogram test WP-1343's multi-histogram task asks for: a
    shared magnetic size column lands on each histogram's own coefficient."""
    from rietx.params.multi import SharingMap, size_value_scales

    st = rx.Structure(phases=[_mnf2(size=0.2)])
    a = rx.Instrument.constant_wavelength_neutron(2.4)
    b = rx.Instrument.constant_wavelength_neutron(1.2)
    scales = size_value_scales(st, [a, b], SharingMap())
    assert scales[0] == {}                       # histogram 0 carries the column
    assert scales[1]["phases.0.magnetic_lor_size"] == pytest.approx(1.2 / 2.4)
    assert scales[1]["phases.0.lor_size"] == pytest.approx(1.2 / 2.4)
    # and a phase with no moment contributes no such path, because no table
    # would hold it
    plain = rx.Structure(phases=[_mnf2(magnetic=False)])
    assert "phases.0.magnetic_lor_size" not in size_value_scales(
        plain, [a, b], SharingMap())[1]


# ================================================ the off state is a code path

@pytest.mark.parametrize("moving", [None, ["phases.0.scale"]],
                         ids=["ungated", "gated"])
def test_at_the_default_no_second_family_is_built(moving):
    """**Bit-identity as the same code path, on both gate readings.**

    ``moving=None`` is the *ungated* compile — the public ``compile_model``, a
    plot, a replay — and ``moving=["phases.0.scale"]`` the *gated* one, a
    stage that made its claim and did not name either width.  Both must skip:
    the skip is read off the two **values** plus ``moving_paths`` when it is
    given, which is deliberately not ``skip_extinction``'s rule (that one
    needs the claim, because *its* off state is "evaluate anyway").

    What is asserted is the path, not the numbers: no second family, no
    ``f2mag``/``widths_mag`` memo slot ever populated — so the magnetic term
    arrived through ``_total_f2`` on the single pass WP-1327 built — and
    ``phase_peaks(component=1)`` refused by name.
    """
    model, table, values = _state(_mnf2(), moving=moving)
    cp = model.phases[0]
    assert cp.magnetic is not None                       # it *is* magnetic
    assert cp.batch_mag is None and cp.win_mag is None and cp.fcj_n_mag is None
    assert not model.mag_split(0)

    model.evaluate(values)
    assert set(cp.scalar_cache) == {"cell", "f2", "aniso", "pos", "widths",
                                    "lp", "abs"}, sorted(cp.scalar_cache)
    with pytest.raises(ValueError, match="second frozen family was not built"):
        model.phase_peaks(0, values, component=1)


def test_the_gated_and_ungated_off_states_are_bit_identical():
    """Two reasons for one skip, and the same doubles out of both."""
    a = _state(_mnf2(), moving=None)
    b = _state(_mnf2(), moving=["phases.0.scale", "instrument.profile.u"])
    ya = np.asarray(a[0].evaluate(a[2]), dtype=np.float64)
    yb = np.asarray(b[0].evaluate(b[2]), dtype=np.float64)
    assert hashlib.sha256(ya.tobytes()).hexdigest() == \
        hashlib.sha256(yb.tobytes()).hexdigest()


def test_naming_a_width_in_moving_paths_builds_the_family_from_zero():
    """The sizing rule: ``moving_paths``, never ``free_paths``, and floored so
    a term freed *from* zero is not drawn on windows that clip its own tails
    (:data:`~rietx.model.forward.MAGNETIC_SIZING_FLOOR`, the twin of
    ``AXIAL_SIZING_FLOOR``)."""
    model, _t, _v = _state(_mnf2(), moving=["phases.0.magnetic_lor_size"])
    cp = model.phases[0]
    assert model.mag_split(0) and cp.batch_mag is not None
    wide = cp.win_mag[0, :, 1] - cp.win_mag[0, :, 0]
    narrow = cp.win[0, :, 1] - cp.win[0, :, 0]
    live = narrow > 0
    assert np.all(wide[live] > narrow[live]), "the family was sized at zero"
    assert MAGNETIC_SIZING_FLOOR > 0.0


def test_a_nonzero_value_builds_the_family_even_with_no_claim():
    """A converged fit replayed through the public ``compile_model`` draws the
    width it converged to; only the *off* state is skipped."""
    model, _t, _v = _state(_mnf2(size=SIZE), moving=None)
    assert model.mag_split(0)


# ============================================ separability, and what follows it

def test_the_two_components_sum_to_the_unsplit_intensity():
    """f2 and f2_mag separable through ``phase_peaks`` — and the identity that
    says every later factor multiplies both: the March multiplier, the line
    weight, Lp, extinction, absorption and roughness are functions of (line,
    reflection) and of nothing about *which* contribution they scale.

    The **structure factors** add to the bit, which is the separability claim
    proper.  The per-line intensities agree only to rounding, and that is
    arithmetic rather than a leak: the split evaluates s·M·f_N·w·Lp +
    s·M·f_m·w·Lp where the unsplit evaluates s·M·(f_N + f_m)·w·Lp, and fp
    multiplication does not distribute exactly.  It is also the whole reason
    the off state is a *structural* skip: at equal widths the split draw would
    still not be bit-identical, so the family must not be built.
    """
    split, _t, v = _state(_mnf2(size=SIZE), moving=None)
    plain, _t2, v2 = _state(_mnf2(), moving=None)
    cp = split.phases[0]
    d = np.asarray(cp.reflections.d)
    cellv = tuple(v[f"phases.0.cell.{k}"] for k in
                  ("a", "b", "c", "alpha", "beta", "gamma"))
    f_n = np.asarray(split._nuclear_f2(0, d, v, cellv))
    f_m = np.asarray(split._magnetic_f2(0, d, v, cellv))
    total = np.asarray(split._total_f2(0, d, v, cellv))
    assert np.array_equal(f_n + f_m, total)

    n = split.phase_peaks(0, v, component=0)
    m = split.phase_peaks(0, v, component=1)
    whole = plain.phase_peaks(0, v2)
    for il in range(len(whole)):
        got = np.asarray(n[il][3]) + np.asarray(m[il][3])
        want = np.asarray(whole[il][3])
        assert np.allclose(got, want, rtol=1e-14, atol=0.0), il


def test_only_the_magnetic_component_carries_the_extra_width():
    """The composition law is the package's own — Lorentzian FWHMs add — so
    the magnetic component's width is ``x + lor_size + magnetic_lor_size``
    fed to the same ``lorentzian_fwhm``, and the nuclear component keeps the
    width it had."""
    from rietx.model.profiles.caglioti import lorentzian_fwhm
    from rietx.model.profiles.pseudovoigt import tch_gamma_eta

    split, _t, v = _state(_mnf2(size=SIZE), moving=None)
    plain, _t2, v2 = _state(_mnf2(), moving=None)
    n = split.phase_peaks(0, v, component=0)
    m = split.phase_peaks(0, v, component=1)
    whole = plain.phase_peaks(0, v2)
    # the nuclear component is untouched
    assert np.array_equal(np.asarray(n[0][1]), np.asarray(whole[0][1]))
    # and the magnetic one is the same law with the coefficient added
    cp = split.phases[0]
    tt = cp.reflections.two_theta(
        tuple(v[f"phases.0.cell.{k}"] for k in
              ("a", "b", "c", "alpha", "beta", "gamma")), LAMBDA_CW)
    theta = 0.5 * tt
    from rietx.model.profiles.caglioti import gaussian_fwhm
    g = gaussian_fwhm(theta, v["instrument.profile.u"],
                      v["instrument.profile.v"], v["instrument.profile.w"],
                      v["phases.0.gauss_size"], v["phases.0.gauss_strain"])
    lo = lorentzian_fwhm(theta, v["instrument.profile.x"] + SIZE,
                         v["instrument.profile.y"], 0.0)
    want, _eta = tch_gamma_eta(g, lo)
    assert np.allclose(np.asarray(m[0][1]), np.asarray(want), rtol=0, atol=0)


def test_structure_intensity_partition_includes_the_magnetic_component():
    """checks/BUG_REFLECTION_TABLE_COMPONENT.md's second finding: the bare
    ``phase_peaks(ip, values)`` call ``structure_intensity_partition`` made at
    ``forward.py:2637`` drew only the nuclear component under ``mag_split``,
    while its own ``I_calc`` two lines below already reads ``_total_f2`` --
    the nuclear-plus-magnetic total.  A magnetically-allowed-only reflection
    (``_classified_reflections``' ``mag`` set) has an exactly-zero nuclear
    structure factor by construction, so before this fix its ``w_calc`` was
    identically 0 and its ratio came back NaN -- the same failure shape as
    the reflection-table bug, one caller over.

    Positive arm: with the observations set to the model's own noiseless
    prediction (which already includes both components,
    ``_phase_component_scalar``/``_phase_component_batched``), every
    reflection with any calculated weight, nuclear or magnetic-only, must
    come back finite and close to a ratio of 1.
    """
    model, _t, v = _state(_mnf2(strain=0.15), moving=None)
    assert model.mag_split(0)
    model.y_obs[:] = np.asarray(model.evaluate(v), dtype=np.float64)

    i_obs, i_calc = model.structure_intensity_partition(v)[0]
    _ip, mag_rows, nuc_rows, _pos, _fwhm = next(iter(
        _classified_reflections(model, v)))
    assert len(mag_rows) and len(nuc_rows)

    live = np.isfinite(i_calc)
    assert np.all(live[nuc_rows]), "nuclear-only reflections should be live regardless"
    assert np.all(live[mag_rows]), \
        "magnetic-only reflections still NaN: the magnetic component is not being drawn"
    ratio = i_obs[live] / i_calc[live]
    assert np.allclose(ratio, 1.0, atol=0.05), ratio


def test_the_scalar_and_batched_draws_agree_on_the_split_path():
    """The per-reflection loop is the oracle every batched claim is measured
    against, and it must walk the components in the same order."""
    model, _t, v = _state(_mnf2(size=SIZE), moving=None)
    a = np.asarray(model._phase_component_scalar(0, v), dtype=np.float64)
    b = np.asarray(model._phase_component_batched(0, v), dtype=np.float64)
    assert np.array_equal(a, b)


def test_extinction_reads_the_total_structure_factor_on_both_components():
    """The attenuation is of the reflection, and the reflection is whatever
    the crystal diffracts — the reading ``_total_f2`` already states.  With
    ``extinction`` freed the chain is live on both passes and the split draw
    still sums to the unsplit one."""
    ph = _mnf2(size=SIZE)
    ph.extinction = Parameter(value=2e-4, min=0.0, transform="softplus")
    plain = _mnf2()
    plain.extinction = Parameter(value=2e-4, min=0.0, transform="softplus")
    split, _t, v = _state(ph, moving=["phases.0.extinction"])
    whole, _t2, v2 = _state(plain, moving=["phases.0.extinction"])
    assert not split.phases[0].skip_extinction
    n = split.phase_peaks(0, v, component=0)
    m = split.phase_peaks(0, v, component=1)
    w = whole.phase_peaks(0, v2)
    got = np.asarray(n[0][3]) + np.asarray(m[0][3])
    assert np.allclose(got, np.asarray(w[0][3]), rtol=1e-12, atol=0.0)


def test_the_magnetic_component_is_broader_where_it_is_magnetic():
    """The point of the whole rung: intensity moves out of the magnetic peaks'
    centres and into their tails, and the nuclear peaks do not move."""
    split, _t, v = _state(_mnf2(size=SIZE), moving=None)
    plain, _t2, v2 = _state(_mnf2(), moving=None)
    ys = np.asarray(split.evaluate(v))
    yp = np.asarray(plain.evaluate(v2))
    tt = np.asarray(split.tt)
    for ip, mag, nuc, pos, fwhm in _classified_reflections(split, v):
        assert len(mag) and len(nuc)
        # a magnetic-only reflection loses its centre
        k = mag[int(np.argmax([fwhm[j] * 0 + 1 for j in mag]))]
        centre = np.abs(tt - pos[k]) <= 0.2 * fwhm[k]
        assert ys[centre].sum() < yp[centre].sum()
        break


# ================================================ the solver-side refusal

def test_a_free_width_against_an_unclaimed_compile_is_refused_by_name():
    """The one hazard the value-based gate creates, closed loudly rather than
    left to be discovered: the parameter would reach no residual row and its
    column would be identically zero (WP-1070's class of bug)."""
    from rietx.optimize.least_squares import run_least_squares

    st = rx.Structure(phases=[_mnf2()])
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    tt = np.arange(8.0, 140.0, 0.05)
    pat = rx.PatternData(two_theta=tt.tolist(),
                         intensity=np.ones_like(tt).tolist())
    model = compile_model(st, ins, pat, mode="rietveld")   # no claim
    table = ParameterTable(st, ins)
    table.set_vary(["phases.0.magnetic_lor_size"], True)
    with pytest.raises(ValueError, match="compiled without the magnetic"):
        run_least_squares(model, table, max_iter=1)


# ================================================ the staging rule

def test_the_preset_is_the_three_step_order():
    plan = PLAN_PRESETS["magnetic_width"]()
    assert [s.name for s in plan.stages] == ["moment", "magnetic_width",
                                             "moment_and_width"]
    assert plan.stages[0].turn_on == list(MAGNETIC_WIDTH_STAGE_PATHS[0])
    # step 1: the moment, with the widths absent from the free list
    assert not any("magnetic_lor" in g for g in plan.stages[0].turn_on)
    assert plan.stages[0].seed == 0.0
    # step 2: **both** widths, seeded off the softplus floor.  Both, because
    # which of the two carries the effect is a property of the dataset — the
    # size term on the synthetic k != 0 case and on Cr2WO6, the *strain* term
    # on Ba2FeSbSe5 at 1.5 K — so a size-only step would have been blind to
    # the one real k != 0 dataset in the corpus.
    assert plan.stages[1].turn_on == ["phases.*.magnetic_lor_size",
                                      "phases.*.magnetic_lor_strain"]
    assert plan.stages[1].seed == MAGNETIC_WIDTH_SEED_DEG > 0.0
    # step 3: both
    assert any("moment.dof" in g for g in plan.stages[2].turn_on)
    assert any("magnetic_lor" in g for g in plan.stages[2].turn_on)


def test_a_plan_that_frees_the_width_beside_a_cold_moment_is_reported():
    """`STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT`, and it arrives **before the
    first stage runs** — the confound is made by the stage list, so a report
    after the answer it spoiled would be too late."""
    from rietx.refine import _stage_order_diagnostics

    st = rx.Structure(phases=[_mnf2()])
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    table = ParameterTable(st, ins)
    bad = rx.RefinementPlan(stages=[rx.Stage(
        "everything", ["phases.*.atoms.*.moment.dof*",
                       "phases.*.magnetic_lor_size", "phases.*.scale"])])
    got = _stage_order_diagnostics(bad, table)
    assert [d.code for d in got] == ["STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT"]
    assert "phases.0.magnetic_lor_size" in got[0].where
    assert "magnetic_width" in got[0].suggestion
    # the preset itself is silent, and so is a width freed after the moment
    assert not _stage_order_diagnostics(PLAN_PRESETS["magnetic_width"](), table)


def test_the_ordering_check_is_silent_on_a_plan_with_no_magnetic_width():
    from rietx.refine import _stage_order_diagnostics

    st = rx.Structure(phases=[_mnf2()])
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    table = ParameterTable(st, ins)
    for name in PLAN_PRESETS:
        if name in ("pawley_default",):
            continue
        assert not _stage_order_diagnostics(PLAN_PRESETS[name](), table), name


# ================================================ the diagnostic's classifier

def test_the_magnetic_only_set_is_read_off_the_intensity_not_the_mask():
    """The correction the k ≠ 0 case forced.

    ``CompiledPhase.nuclear_mask`` marks only the rows a k = 0 magnetic
    group's absences *added*.  On a supercell the strong magnetic reflections
    are in the child group's own list with the mask at 1.0 and ⟨|F_N|²⟩
    exactly zero, because the nuclear atoms still carry the parent's
    translation — so a classifier reading the mask would have measured the
    statistic on the wrong reflections in the very case the term exists for.
    Asserted here on MnF₂, where both kinds are present.
    """
    model, _t, v = _state(_mnf2(), moving=None)
    cp = model.phases[0]
    d = np.asarray(cp.reflections.d)
    cellv = tuple(v[f"phases.0.cell.{k}"] for k in
                  ("a", "b", "c", "alpha", "beta", "gamma"))
    f_nuc = np.asarray(model._nuclear_f2(0, d, v, cellv))
    for ip, mag, nuc, pos, fwhm in _classified_reflections(model, v):
        assert len(mag) >= 2 and len(nuc) >= 2
        # every row called magnetic-only really has no nuclear intensity …
        assert np.all(f_nuc[mag] == 0.0)
        # … and the set is a superset of the masked rows, never equal to it by
        # construction
        # every *masked* row that carries any magnetic intensity at all is in
        # the set — a magnetically allowed lattice point where |F_perp|^2
        # happens to vanish too (the moment parallel to Q) is in neither, and
        # that is why the mask alone is not the classifier in either direction
        f_m = np.asarray(model._magnetic_f2(0, d, v, cellv))
        masked = set(np.nonzero((np.asarray(cp.nuclear_mask) == 0.0)
                                & (f_m > 0.0))[0])
        assert masked <= set(mag.tolist())
        assert not (set(mag.tolist()) & set(nuc.tolist()))


def test_the_diagnostic_is_silent_while_the_term_is_free():
    """Once the width is freed the evidence is the trajectory, not a gate."""
    model, _t, v = _state(_mnf2(size=SIZE),
                          moving=["phases.0.magnetic_lor_size"])
    model.y_obs[:] = np.asarray(model.evaluate(v)) * 1.5   # a gross misfit
    assert not [d for d in magnetic_width_findings(model, v)
                if d.code == "MAGNETIC_WIDTH_UNMODELLED"]


def test_the_diagnostic_fires_on_a_planted_width_and_not_without_one():
    """The differential statistic, both arms, on one synthetic pattern each.

    The positive arm plants the broadening in the *observations* and holds the
    term at zero; the control plants nothing.  Only the difference between the
    magnetic-only and nuclear-only sign splits is judged, so the control is
    what says the arm is not simply reading a misfit.
    """
    broad, _t, vb = _state(_mnf2(size=SIZE), moving=None)
    narrow, _t2, vn = _state(_mnf2(), moving=None)
    y_broad = np.asarray(broad.evaluate(vb), dtype=np.float64)
    y_narrow = np.asarray(narrow.evaluate(vn), dtype=np.float64)

    # positive arm: observations broad, model narrow
    narrow.y_obs[:] = y_broad
    narrow.sigma[:] = np.sqrt(np.maximum(y_broad, 1.0))
    hits = [d for d in magnetic_width_findings(narrow, vn)
            if d.code == "MAGNETIC_WIDTH_UNMODELLED"]
    assert len(hits) == 1, [d.code for d in magnetic_width_findings(narrow, vn)]
    assert hits[0].value > MAGNETIC_WIDTH_SIGMA
    assert "biased **low**" in hits[0].message
    assert "magnetic_lor_size" in hits[0].where[0]

    # control: observations narrow, model narrow — nothing to say
    narrow.y_obs[:] = y_narrow
    narrow.sigma[:] = np.sqrt(np.maximum(y_narrow, 1.0))
    assert not [d for d in magnetic_width_findings(narrow, vn)
                if d.code == "MAGNETIC_WIDTH_UNMODELLED"]


def test_an_unmeasured_width_is_named_rather_than_quoted():
    """``MAGNETIC_WIDTH_UNMEASURED`` on the same ratio WP-1327 uses for a
    moment — no threshold of its own, so the report cannot call a width
    measured and a moment of the same size unsupported."""
    from rietx.report.schemas import MOMENT_SUPPORT_SIGMA

    model, _t, v = _state(_mnf2(size=0.05),
                          moving=["phases.0.magnetic_lor_size"])
    got = magnetic_width_findings(
        model, v, esds={"phases.0.magnetic_lor_size": 0.05},
        free=["phases.0.magnetic_lor_size"])
    codes = [d.code for d in got]
    assert "MAGNETIC_WIDTH_UNMEASURED" in codes
    row = next(d for d in got if d.code == "MAGNETIC_WIDTH_UNMEASURED")
    assert row.value == pytest.approx(1.0)
    assert row.value < MOMENT_SUPPORT_SIGMA
    # a well-measured one says nothing
    assert not [d for d in magnetic_width_findings(
        model, v, esds={"phases.0.magnetic_lor_size": 0.002},
        free=["phases.0.magnetic_lor_size"])
        if d.code == "MAGNETIC_WIDTH_UNMEASURED"]
    # and neither does a held one
    assert not [d for d in magnetic_width_findings(
        model, v, esds={"phases.0.magnetic_lor_size": 0.05}, free=[])
        if d.code == "MAGNETIC_WIDTH_UNMEASURED"]


# ================================================ the Jacobian

@pytest.mark.parametrize("path", ["phases.0.magnetic_lor_size",
                                  "phases.0.magnetic_lor_strain"])
def test_the_new_columns_match_central_differences(path):
    """FD first, and the branch the paths land in is the peak chain, which
    ``scalar_chain_supported`` already claims for every ``phases.*`` name.
    The magnetic component's planes are what make it exact rather than short
    — without them this column would be the nuclear pass alone, i.e. zero."""
    from rietx.optimize.least_squares import _make_jacobian, _make_residual

    st = rx.Structure(phases=[_mnf2(size=0.2, strain=0.1)])
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    ins.profile.u.value, ins.profile.w.value = 0.05, 0.02
    tt = np.arange(8.0, 140.0, 0.05)
    sim = rx.PatternData(two_theta=tt.tolist(),
                         intensity=np.ones_like(tt).tolist())
    table = ParameterTable(st, ins)
    table.set_vary([path, "phases.0.scale"], True)
    model = compile_model(st, ins, sim, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    model.y_obs[:] = np.asarray(model.evaluate(table.decode(table.x0()))) * 1.02
    theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    c = list(table.free_paths).index(path)
    h = 1e-6 * max(1.0, abs(theta[c]))
    tp, tm = theta.copy(), theta.copy()
    tp[c] += h
    tm[c] -= h
    fd = (residual(tp) - residual(tm)) / (2.0 * h)
    a, b = J[:, c], fd
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    assert na > 0.0, f"{path}: the analytic column is dead"
    assert np.linalg.norm(a - b) / max(na, nb) < 5e-3
    assert float(a @ b) / (na * nb) > 0.99999


def test_the_traced_backends_decline_a_magnetic_phase_by_name():
    """Which is why the cross-backend row for these paths is analytic-vs-FD:
    WP-1327's twin declines any magnetic model rather than tracing one whose
    magnetic term it would silently drop."""
    from rietx.backend.traced import make_traced_residual

    st = rx.Structure(phases=[_mnf2(size=0.2)])
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    tt = np.arange(8.0, 140.0, 0.1)
    pat = rx.PatternData(two_theta=tt.tolist(),
                         intensity=np.ones_like(tt).tolist())
    table = ParameterTable(st, ins)
    model = compile_model(st, ins, pat, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    class _Xp:
        name = "jax"

    with pytest.raises(NotImplementedError, match="magnetic"):
        make_traced_residual(model, table, _Xp())


# ================================================ the round trip

@pytest.mark.slow
def test_a_planted_magnetic_width_and_moment_are_recovered():
    """WP-1343 acceptance 1, in miniature: MnF₂ (k = 0 but with five
    magnetic-only reflections of its own) with a planted width and moment.

    **The bar here is 2σ, and 2σ is the honest bar for one draw.**  The
    acceptance's own "within 1σ" is measured on the k ≠ 0 supercell arm in the
    report (0.245 ± 0.008 against a planted 0.25, i.e. 0.6σ, with both moments
    inside 0.9σ); a suite test that pinned 1σ on a single noise realisation
    would fail about one time in three for no reason but the seed, and picking
    the seed that passes is what makes such a test meaningless.  So this one
    asserts 2σ **and** 5 % of the planted value — the second bar is the one
    that would catch a real bias, since it does not shrink with the count
    rate.
    """
    truth_size, truth_moment = 0.22, 4.60
    # counts chosen so the width's esd is a few 1e-3 rather than 1e-4: at
    # 10^6-count peaks the esd shrinks past the systematic floor this recovery
    # has (the seeded start, and the window truncation of a Lorentzian tail),
    # and "within 1 sigma" would then be a statement about the count rate
    ph = _mnf2(size=truth_size)
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    ins.profile.u.value, ins.profile.w.value = 0.05, 0.03
    ins.background = rx.BackgroundChebyshev.with_terms(2)
    ins.background.coefficients[0].value = 20.0
    ph.scale.value = 0.02
    tt = np.arange(8.0, 140.0, 0.05)
    blank = rx.PatternData(two_theta=tt.tolist(),
                           intensity=np.zeros_like(tt).tolist())
    y = np.asarray(rx.Refinement(rx.Structure(phases=[ph]),
                                 ins.model_copy(deep=True)).predict(blank))
    rng = np.random.default_rng(1343)
    data = rx.PatternData(
        two_theta=tt.tolist(),
        intensity=(y + rng.normal(0.0, np.sqrt(np.maximum(y, 1.0)))).tolist())

    start = _mnf2()                     # the term back at its off state
    start.scale.value = 0.02
    plan = PLAN_PRESETS["magnetic_width"]()
    ref = rx.Refinement(rx.Structure(phases=[start]),
                        ins.model_copy(deep=True))
    res = ref.fit(data, plan=plan)
    rows = {p.path: p for p in res.parameters}
    w = rows["phases.0.magnetic_lor_size"]
    m = rows["phases.0.atoms.0.moment.dof0"]
    assert w.stderr is not None and m.stderr is not None
    assert abs(w.value - truth_size) < 2.0 * w.stderr
    assert abs(w.value - truth_size) < 0.05 * truth_size
    assert abs(abs(m.value) - truth_moment) < 2.0 * m.stderr
    assert abs(abs(m.value) - truth_moment) < 0.05 * truth_moment

    # …and without the term the moment is low by more than its esd
    ref0 = rx.Refinement(rx.Structure(phases=[_mnf2()]).model_copy(deep=True),
                         ins.model_copy(deep=True))
    ref0.structure.phases[0].scale.value = 0.02
    res0 = ref0.fit(data, plan=rx.RefinementPlan(stages=[plan.stages[0]]))
    m0 = {p.path: p for p in res0.parameters}["phases.0.atoms.0.moment.dof0"]
    assert abs(m0.value) < truth_moment - m0.stderr
    assert "MAGNETIC_WIDTH_UNMODELLED" in {d.code for d in res0.diagnostics}


def test_run_stage_reports_the_order_before_it_solves():
    """The manual single-stage entry point is where a caller drives the order
    by hand, so it is where the confound is easiest to walk into."""
    ph = _mnf2()
    ph.scale.value = 0.02
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    ins.profile.u.value, ins.profile.w.value = 0.05, 0.03
    tt = np.arange(8.0, 140.0, 0.1)
    blank = rx.PatternData(two_theta=tt.tolist(),
                           intensity=np.zeros_like(tt).tolist())
    y = np.asarray(rx.Refinement(rx.Structure(phases=[ph]),
                                 ins.model_copy(deep=True)).predict(blank))
    data = rx.PatternData(two_theta=tt.tolist(),
                          intensity=(y + 1.0).tolist())
    ref = rx.Refinement(rx.Structure(phases=[_mnf2()]),
                        ins.model_copy(deep=True))
    ref.structure.phases[0].scale.value = 0.02
    res = ref.run_stage(data, rx.Stage(
        "everything", ["phases.*.atoms.*.moment.dof*",
                       "phases.*.magnetic_lor_size", "phases.*.scale"],
        seed=MAGNETIC_WIDTH_SEED_DEG))
    assert "STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT" in {
        d.code for d in res.diagnostics}


# ================================ the moment the released width moved

def _shifted(off, released, widths):
    from rietx.refine import _moved_moment_diagnostics

    return _moved_moment_diagnostics("moment_and_width", off, released, widths)


def test_the_moved_moment_bar_reads_the_tighter_of_the_two_esds():
    """The threshold's own measured justification, as an assertion.

    Ba₂FeSbSe₅ at 1.5 K: the tied moment goes 3.908 ± 0.128 (widths held) →
    4.087 ± 0.18 (widths free), a shift of 0.179 μ_B.  Against the *released*
    esd that is 0.994 — under a 1.0 bar by 0.6 % — and against the off-state
    esd, the number that would have been published, it is 1.40.  The rule is
    the tighter of the two, so the case that forced the code into existence
    fires it; the arithmetic is pinned here so the denominator cannot be
    changed back without this failing.
    """
    p = "phases.0.atoms.0.moment.dof0"
    got = _shifted({p: (3.908, 0.128)}, {p: (4.087, 0.180)},
                   {"phases.0.magnetic_lor_strain": (0.375, 0.283)})
    assert [d.code for d in got] == ["MAGNETIC_WIDTH_MOVED_MOMENT"]
    assert got[0].value == pytest.approx(0.179 / 0.128, abs=2e-3)
    assert got[0].value > MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA
    assert 0.179 / 0.180 < MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA   # the other choice
    assert "correlated with the moment, not absent" in got[0].message
    assert "3.908" in got[0].message and "4.087" in got[0].message
    assert "0.375" in got[0].message
    # a shift inside the tighter bar says nothing
    assert not _shifted({p: (3.908, 0.128)}, {p: (3.95, 0.180)},
                        {"phases.0.magnetic_lor_strain": (0.375, 0.283)})
    # and neither does a fit that measured no esd at all
    assert not _shifted({p: (3.908, None)}, {p: (4.5, None)},
                        {"phases.0.magnetic_lor_size": (0.3, None)})


def test_the_support_row_withholds_its_licence_when_the_moment_moved():
    """`MAGNETIC_WIDTH_UNMEASURED` is right and misleading at the same time on
    the Ba₂FeSbSe₅ case, so its wording changes when the other code fired."""
    model, _t, v = _state(_mnf2(size=0.05),
                          moving=["phases.0.magnetic_lor_size"])
    path = "phases.0.magnetic_lor_size"
    plain = next(d for d in magnetic_width_findings(
        model, v, esds={path: 0.05}, free=[path])
        if d.code == "MAGNETIC_WIDTH_UNMEASURED")
    guarded = next(d for d in magnetic_width_findings(
        model, v, esds={path: 0.05}, free=[path], moved=[path])
        if d.code == "MAGNETIC_WIDTH_UNMEASURED")
    assert "hold" in plain.suggestion and "at zero" in plain.suggestion
    assert "not licence to drop the term" in guarded.message
    assert "MAGNETIC_WIDTH_MOVED_MOMENT" in guarded.message
    assert "keep" in guarded.suggestion and "free" in guarded.suggestion
    assert "at zero" not in guarded.suggestion
    # the ratio itself is the same measurement either way
    assert plain.value == guarded.value


@pytest.mark.slow
def test_the_preset_run_fires_the_moved_moment_code_and_the_control_does_not():
    """End to end through ``fit``, on the two synthetic patterns of the
    round-trip test: the planted broadening moves the moment when the widths
    are released, and the pattern with none does not."""
    truth_size = 0.22
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_CW)
    ins.profile.u.value, ins.profile.w.value = 0.05, 0.03
    ins.background = rx.BackgroundChebyshev.with_terms(2)
    ins.background.coefficients[0].value = 20.0
    tt = np.arange(8.0, 140.0, 0.05)
    blank = rx.PatternData(two_theta=tt.tolist(),
                           intensity=np.zeros_like(tt).tolist())
    rng = np.random.default_rng(1343)

    def pattern(size):
        ph = _mnf2(size=size)
        ph.scale.value = 0.02
        y = np.asarray(rx.Refinement(rx.Structure(phases=[ph]),
                                     ins.model_copy(deep=True)).predict(blank))
        return rx.PatternData(
            two_theta=tt.tolist(),
            intensity=(y + rng.normal(0.0,
                                      np.sqrt(np.maximum(y, 1.0)))).tolist())

    broad, flat = pattern(truth_size), pattern(0.0)
    for data, expected in ((broad, True), (flat, False)):
        start = _mnf2()
        start.scale.value = 0.02
        ref = rx.Refinement(rx.Structure(phases=[start]),
                            ins.model_copy(deep=True))
        res = ref.fit(data, plan=PLAN_PRESETS["magnetic_width"]())
        codes = {d.code for d in res.diagnostics}
        assert ("MAGNETIC_WIDTH_MOVED_MOMENT" in codes) is expected, sorted(codes)
        if expected:
            row = next(d for d in res.diagnostics
                       if d.code == "MAGNETIC_WIDTH_MOVED_MOMENT")
            assert row.value > MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA
            assert any("magnetic_lor" in q for q in row.where)
