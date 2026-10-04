"""WP-1534 — a scale and a B the fitted range cannot separate.

A phase's intensity is ``scale · exp(−2B·s²)`` times terms neither parameter
touches.  Where every reflection of the phase in the fitted range sits at one
d-spacing, ln(scale) − 2B·s² is one coordinate, and the two columns are one
direction.  Issue #204 walked bcc Fe's B to −165 Å² that way on a 25–50° Cu Kα
scan, and two staging orders returned it at 0.0 and 80.9 wt% at one Rwp.
WP-1534's task 1 measured the covariance *not* saying so: the pinv cut
discards the combined direction, and Fe came back 0.000 ± 0.000 wt%.

The fixture is task 1's: corundum, zincite, fluorite and bcc Fe at equal
scales, 25–50° in 0.01° steps, Poisson noise at seed 3, fitted from scales of
1e-4 with B at the truth and ``biso`` unbounded, in two staging orders.  Fe has
one reflection in range, (110); fluorite is the nearest phase that *is*
separable, and keeps its honest, huge esd.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import PatternData
from rietx.model.forward import compile_model
from rietx.optimize.qpa import compute_qpa
from rietx.optimize.statistics import PINV_RCOND
from rietx.params.vector import ParameterTable
from rietx.refine import SCALE_B_SEPARATION_FLOOR, _scale_b_separation
from rietx.schemas.instrument import BackgroundChebyshev, Dispersion
from rietx.schemas.results import RefinementResult, StageResult
from rietx.strategy.staged import RefinementPlan, Stage

pytestmark = pytest.mark.xdist_group("scale-b-ridge")

OUT = Path(__file__).parent / "output"

TT = np.arange(25.0, 50.0, 0.01)
TRUE_SCALES = [2.0e-4, 2.0e-4, 2.0e-4, 2.0e-4]
START_SCALES = [1.0e-4, 1.0e-4, 1.0e-4, 1.0e-4]
TRUE_B = {"corundum": 0.30, "zincite": 0.55, "fluorite": (0.55, 0.75),
          "iron": 0.35}
FLUORITE, FE = 2, 3
FE_B = "phases.3.atoms.0.biso"

BIG = ["phases.*.scale", "instrument.background.*"]
CELL = ["phases.*.cell.*", "instrument.zero_shift"]
BISO = ["phases.*.atoms.*.biso"]
WIDTH = ["phases.*.lor_size", "instrument.profile.w"]
ORDERS = {
    "cell_then_B": [Stage("s", BIG), Stage("c", BIG + CELL),
                    Stage("b", BIG + CELL + BISO),
                    Stage("w", BIG + CELL + BISO + WIDTH)],
    "B_then_cell": [Stage("s", BIG), Stage("b", BIG + BISO),
                    Stage("c", BIG + BISO + CELL),
                    Stage("w", BIG + CELL + BISO + WIDTH)],
}


def _p(v, **kw):
    return rx.Parameter(value=v, **kw)


def _phase(name, sg, cell, atoms, scale, unbounded):
    a, b, c, al, be, ga = cell
    # #204's shape: the caller's Parameter carries no bounds on B
    bk = dict(min=-math.inf, max=math.inf) if unbounded else {}
    return rx.Phase(
        name=name, space_group=sg,
        cell=rx.Cell(a=_p(a), b=_p(b), c=_p(c), alpha=_p(al), beta=_p(be),
                     gamma=_p(ga)),
        atoms=[rx.Atom(label=lab, species=sp, x=_p(x), y=_p(y), z=_p(z),
                       biso=_p(biso, **bk))
               for lab, sp, x, y, z, biso in atoms],
        scale=_p(scale, min=0.0, transform="softplus"),
        lor_size=_p(0.02, min=0.0, transform="softplus"),
        lor_strain=_p(0.0, min=0.0, transform="softplus"))


def _models(scales, *, unbounded=True):
    def b(name, k=0):
        v = TRUE_B[name]
        return v[k] if isinstance(v, tuple) else v
    phases = [
        _phase("corundum", "R -3 c", (4.7593, 4.7593, 12.9917, 90, 90, 120),
               [("Al", "Al", 0.0, 0.0, 0.35216, b("corundum")),
                ("O", "O", 0.30624, 0.0, 0.25, b("corundum"))],
               scales[0], unbounded),
        _phase("zincite", "P 63 m c", (3.2499, 3.2499, 5.2066, 90, 90, 120),
               [("Zn", "Zn", 1 / 3, 2 / 3, 0.0, b("zincite")),
                ("O", "O", 1 / 3, 2 / 3, 0.3826, b("zincite"))],
               scales[1], unbounded),
        _phase("fluorite", "F m -3 m", (5.4631,) * 3 + (90, 90, 90),
               [("Ca", "Ca", 0.0, 0.0, 0.0, b("fluorite", 0)),
                ("F", "F", 0.25, 0.25, 0.25, b("fluorite", 1))],
               scales[2], unbounded),
        _phase("iron", "I m -3 m", (2.8665,) * 3 + (90, 90, 90),
               [("Fe", "Fe", 0.0, 0.0, 0.0, b("iron"))], scales[3], unbounded),
    ]
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    # declared rather than inherited (root CLAUDE.md): the default, task 1's
    instrument.source.dispersion = Dispersion()
    instrument.background = BackgroundChebyshev(
        coefficients=[_p(v) for v in (150.0, -20.0, 5.0)])
    return rx.Structure(phases=phases), instrument


def _fit(data, stages, *, unbounded=True, ref=None):
    ref = ref or rx.Refinement(*_models(START_SCALES, unbounded=unbounded))
    res = ref.fit(data, plan=RefinementPlan(stages=stages), telemetry=False)
    return ref, res


def _fraction(res, name):
    (row,) = [q for q in res.qpa.phases if q.name == name]
    return row.weight_fraction


def _findings(res, code="SCALE_B_INSEPARABLE"):
    return [d for d in res.diagnostics if d.code == code]


@pytest.fixture(scope="module")
def pattern() -> PatternData:
    structure, instrument = _models(TRUE_SCALES, unbounded=False)
    blank = PatternData(two_theta=TT.tolist(), intensity=np.zeros_like(TT).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=np.asarray(model.tt).tolist(), intensity=y.tolist())


@pytest.fixture(scope="module")
def true_fraction() -> dict[str, float]:
    structure, instrument = _models(TRUE_SCALES, unbounded=False)
    table = ParameterTable(structure, instrument)
    q = compute_qpa(structure, table.decode(table.x0()))
    return {p.name: p.weight_fraction for p in q.phases}


@pytest.fixture(scope="module")
def ridge_fits(pattern) -> dict[str, tuple]:
    """Both staging orders, ``biso`` unbounded — #204's two answers."""
    return {order: _fit(pattern, stages) for order, stages in ORDERS.items()}


@pytest.fixture(params=list(ORDERS))
def ridge_fit(request, ridge_fits):
    return (request.param, *ridge_fits[request.param])


# ----------------------------------------------------------------------
# the floor and the probe
# ----------------------------------------------------------------------
def test_the_floor_is_where_the_covariance_cut_falls():
    """Two unit columns ``r`` apart lose their difference direction to pinv's
    cut below the floor and keep it above — the derivation, checked against
    the call the covariance makes rather than restated."""
    assert SCALE_B_SEPARATION_FLOOR == pytest.approx(2.0 * math.sqrt(PINV_RCOND))
    diff = np.array([1.0, -1.0]) / math.sqrt(2.0)

    def variance_of_the_difference(r):
        c = math.sqrt(1.0 - r * r)
        k = np.linalg.pinv(np.array([[1.0, c], [c, 1.0]]), rcond=PINV_RCOND,
                           hermitian=True)
        return float(diff @ k @ diff)

    # the true value is 1/(1 − c) ≈ 2/r²: 2e15 at half the floor, 1e14 at twice
    assert variance_of_the_difference(0.5 * SCALE_B_SEPARATION_FLOOR) < 1.0
    assert variance_of_the_difference(2.0 * SCALE_B_SEPARATION_FLOOR) > 1e13


def test_the_probe_separates_one_d_spacing_from_several(pattern):
    """Fe's one reflection reads at the probe's rounding floor, every other
    phase several decades above the cut — at the values a B stage starts from."""
    structure, instrument = _models(START_SCALES)
    table = ParameterTable(structure, instrument)
    table.set_vary(BIG + BISO, True)
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    r = _scale_b_separation(model, table)
    print(f"\nseparation at stage start: "
          f"{ {ip: f'{v:.3g}' for ip, v in r.items()} }")
    assert sorted(r) == [0, 1, 2, FE]
    assert r[FE] < SCALE_B_SEPARATION_FLOOR * 1e-3
    assert min(v for ip, v in r.items() if ip != FE) > SCALE_B_SEPARATION_FLOOR * 1e3


# ----------------------------------------------------------------------
# the hold, the record and the finding
# ----------------------------------------------------------------------
def test_fe_b_is_held_in_every_stage_that_frees_it(ridge_fit):
    order, _, res = ridge_fit
    for stage, sr in zip(ORDERS[order], res.stages):
        if BISO[0] in stage.turn_on:
            assert FE_B in sr.held and FE_B not in sr.freed, (order, sr.name)
            assert list(sr.scale_b_held) == [FE], (order, sr.name)
            assert sr.scale_b_held[FE] < SCALE_B_SEPARATION_FLOOR
        else:
            # looked, and nothing to hold: the written empty, never None
            assert sr.scale_b_held == {} and FE_B not in sr.held
        # fluorite is separable, so its B refines and keeps its honest esd
        assert not any(p.startswith(f"phases.{FLUORITE}.") for p in sr.held)
        assert sr.released == []
    params = {p.path: p for p in res.parameters}
    assert FE_B not in params, "a held value is the caller's, not a result"
    assert params[f"phases.{FLUORITE}.atoms.0.biso"].stderr is not None


def test_fe_b_stays_at_the_value_handed_in(ridge_fit):
    """Unbounded, the walk is gone: task 1 measured −150 Å² in both orders."""
    _, ref, _ = ridge_fit
    assert ref.structure.phases[FE].atoms[0].biso.value == TRUE_B["iron"]


def test_the_finding_names_iron_and_only_iron(ridge_fit):
    order, ref, res = ridge_fit
    (finding,) = _findings(res)
    assert finding.level == "warning"
    assert finding.where == [FE_B]
    assert finding.value == min(sr.scale_b_held.get(FE, math.inf)
                                for sr in res.stages)
    assert "phase 3 (iron)" in finding.message
    held_in = [s.name for s in ORDERS[order] if BISO[0] in s.turn_on]
    assert f"stages {', '.join(held_in)}" in finding.message
    # the fraction's sensitivity, from Fe (110)'s own s² = 1/(4d²)
    s2 = 0.25 / (2.8665 / math.sqrt(2.0)) ** 2
    assert f"about {100.0 * math.expm1(2.0 * s2):.2g} %" in finding.message
    assert "1 scale-B inseparable (WP-1534)" in ref.summary()


def test_fe_fraction_lands_near_the_truth_and_both_orders_agree(
        ridge_fits, true_fraction):
    """The acceptance: never two different confident fractions at one Rwp.

    The tolerance is the fit's own: three of Fe's scale esds, relative — the
    one direction this fixture's Fe fraction is measured along once B is held.
    Its QPA esd is no tolerance here: fluorite's near-ridge carries thousands
    of wt% through the normalisation into every fraction (task 1).
    """
    fractions, rwps, tolerances = {}, {}, {}
    for order, (_, res) in ridge_fits.items():
        scale = {p.path: p for p in res.parameters}[f"phases.{FE}.scale"]
        fractions[order] = _fraction(res, "iron")
        rwps[order] = res.statistics.rwp
        tolerances[order] = 3.0 * scale.stderr / scale.value
    truth = true_fraction["iron"]
    print(f"\nFe wt%: truth {truth * 100:.4f}; "
          + "; ".join(f"{o} {w * 100:.6f} (tol ±{tolerances[o] * truth * 100:.4f}, "
                      f"Rwp {rwps[o]:.10f})" for o, w in fractions.items()))
    for order, w in fractions.items():
        assert abs(w - truth) < tolerances[order] * truth, order
    a, b = fractions.values()
    # measured 1.284265 and 1.284271 wt%, against 0.000 ± 0.000 in both
    # orders before the hold (task 1); the truth is 1.2111, 1.1 scale esds away
    assert abs(a - b) < 1e-4 * truth


def test_the_record_round_trips(ridge_fit):
    _, _, res = ridge_fit
    held = [sr for sr in res.stages if sr.scale_b_held]
    assert held
    for sr in res.stages:
        back = StageResult.model_validate_json(sr.model_dump_json())
        assert back == sr
        assert all(isinstance(ip, int) for ip in back.scale_b_held)
    whole = RefinementResult.model_validate_json(res.model_dump_json())
    assert [s.scale_b_held for s in whole.stages] == [s.scale_b_held
                                                      for s in res.stages]
    # a record written before the field: nobody looked, never "nothing held"
    old = held[0].model_dump(mode="json")
    old.pop("scale_b_held")
    assert StageResult.model_validate(old).scale_b_held is None


# ----------------------------------------------------------------------
# where the test does not apply
# ----------------------------------------------------------------------
def test_a_plan_that_never_frees_b_holds_nothing(pattern):
    _, res = _fit(pattern, ORDERS["cell_then_B"][:2])
    assert all(sr.scale_b_held == {} and sr.held == [] for sr in res.stages)
    assert _findings(res) == []


def test_a_held_scale_leaves_b_to_measure_the_intensity(pattern):
    """The ridge is a *pair* of columns: with the scale fixed, B is what the
    one intensity determines, and holding it would freeze a measured value."""
    _, res = _fit(pattern, [Stage("b", ["instrument.background.*"] + BISO)])
    (sr,) = res.stages
    assert sr.scale_b_held == {} and FE_B in sr.freed
    assert _findings(res) == []


def test_a_phase_released_inside_the_stage_is_asked_before_its_second_solve(
        pattern):
    """Fe starts under the noise, so the support hold takes its B before the
    probe can see it; the solve raises its scale and the release frees B.  The
    probe is asked then, or the second solve runs on the ridge unflagged."""
    ref = rx.Refinement(*_models(START_SCALES[:FE] + [1e-9]))
    _, res = _fit(pattern, [Stage("b", BIG + BISO)], ref=ref)
    (sr,) = res.stages
    assert FE_B in sr.held and FE_B not in sr.released + sr.freed
    assert list(sr.scale_b_held) == [FE]
    assert sr.scale_b_held[FE] < SCALE_B_SEPARATION_FLOOR
    (finding,) = _findings(res)
    assert finding.where == [FE_B]
    assert _findings(res, "PHASE_UNCONSTRAINED") == []


def test_a_variable_driving_b_is_held_as_its_column(pattern):
    """Columns, never names (WP-1342): the free name is the variable's."""
    ref = rx.Refinement(*_models(START_SCALES))
    ref.add_variable("B_fe", TRUE_B["iron"])
    ref.tie(FE_B, "vars.B_fe")
    _, res = _fit(pattern, [Stage("s", BIG), Stage("b", BIG + BISO + ["vars.*"])],
                  ref=ref)
    sr = res.stages[-1]
    assert sr.held == ["vars.B_fe"]
    assert sr.held_reach == {"vars.B_fe": [FE_B]}
    assert list(sr.scale_b_held) == [FE]
    (finding,) = _findings(res)
    assert finding.where == ["vars.B_fe"]


def test_a_variable_shared_with_a_separable_phase_is_not_held(pattern):
    """All, never any: fluorite's B gives the shared column a direction Fe's
    scale cannot imitate, so the pair is not a ridge and nothing is held."""
    ref = rx.Refinement(*_models(START_SCALES))
    ref.add_variable("B", TRUE_B["iron"])
    ref.tie_equal([FE_B, f"phases.{FLUORITE}.atoms.0.biso"], source="vars.B")
    _, res = _fit(pattern, [Stage("s", BIG), Stage("b", BIG + BISO + ["vars.*"])],
                  ref=ref)
    sr = res.stages[-1]
    assert "vars.B" in sr.freed and sr.held == []
    assert sr.scale_b_held == {}
    assert _findings(res) == []


# ----------------------------------------------------------------------
# the block: more displacement columns than the reflections leave room for
# ----------------------------------------------------------------------
#: 25–33° Cu Kα: fluorite keeps (111) and (200), two reflections for its
#: scale, B(Ca) and B(F).  The uniform B is separable there, the block is not.
TT_NARROW = np.arange(25.0, 33.0, 0.01)
ADP = ["phases.*.atoms.*.adp.*"]


@pytest.fixture(scope="module")
def narrow_pattern() -> PatternData:
    structure, instrument = _models(TRUE_SCALES, unbounded=False)
    blank = PatternData(two_theta=TT_NARROW.tolist(),
                        intensity=np.zeros_like(TT_NARROW).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=np.asarray(model.tt).tolist(), intensity=y.tolist())


def test_two_sites_on_two_reflections_are_one_ridge(narrow_pattern):
    """Stepping both of fluorite's B together finds a direction the scale
    cannot imitate; the two sites apart do not.  The round robin's cpd-1c
    walked them to +99 and −111 Å² this way (WP-1534, 2026-10-04)."""
    from rietx.refine import SCALE_B_STEP, _column_separation

    structure, instrument = _models(START_SCALES)
    table = ParameterTable(structure, instrument)
    table.set_vary(BIG + BISO, True)
    model = compile_model(structure, instrument, narrow_pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    r = _scale_b_separation(model, table)
    assert r[FLUORITE] < SCALE_B_SEPARATION_FLOOR * 1e-3
    values = table.decode(table.x0())
    sigma = np.asarray(model.sigma)
    a = np.asarray(model.phase_component(FLUORITE, values)) / sigma
    both = dict(values)
    for j in (0, 1):
        both[f"phases.{FLUORITE}.atoms.{j}.biso"] += SCALE_B_STEP
    uniform = np.asarray(model.phase_component(FLUORITE, both)) / sigma - a
    assert _column_separation(a, [uniform]) > SCALE_B_SEPARATION_FLOOR * 1e3


def test_the_block_hold_keeps_fluorite_off_the_walk(narrow_pattern, true_fraction):
    ref = rx.Refinement(*_models(START_SCALES))
    _, res = _fit(narrow_pattern, [Stage("s", BIG), Stage("b", BIG + BISO)], ref=ref)
    sr = res.stages[-1]
    flu = [f"phases.{FLUORITE}.atoms.{j}.biso" for j in (0, 1)]
    assert set(flu) <= set(sr.held)
    assert FLUORITE in sr.scale_b_held
    (finding,) = [f for f in _findings(res) if flu[0] in f.where]
    assert finding.where == flu
    assert [a.biso.value for a in ref.structure.phases[FLUORITE].atoms] == list(
        TRUE_B["fluorite"])
    print(f"\nfluorite wt% on 25–33°: {100 * _fraction(res, 'fluorite'):.3f} "
          f"(truth {100 * true_fraction['fluorite']:.3f})")


def test_an_anisotropic_site_is_probed(pattern):
    """An ADP DOF is a displacement column like a ``biso``; the probe once
    skipped a phase with no isotropic site (WP-1534's declined finding)."""
    structure, instrument = _models(START_SCALES)
    fe = structure.phases[FE].atoms[0]
    u = TRUE_B["iron"] / (8.0 * math.pi ** 2)
    fe.aniso = rx.AnisoU(u11=_p(u, vary=True), u22=_p(u, vary=True),
                         u33=_p(u, vary=True))
    fe.biso.vary = False
    table = ParameterTable(structure, instrument)
    table.set_vary(BIG + BISO + ADP, True)
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    r = _scale_b_separation(model, table)
    assert r[FE] < SCALE_B_SEPARATION_FLOOR * 1e-3
    _, res = _fit(pattern, [Stage("s", BIG), Stage("b", BIG + BISO + ADP)],
                  ref=rx.Refinement(structure, instrument))
    sr = res.stages[-1]
    assert list(sr.scale_b_held) == [FE]
    assert all(p.startswith(f"phases.{FE}.atoms.0.adp.") for p in sr.held)


def test_the_held_fit_is_drawn_for_inspection(ridge_fit):
    """Rwp hides locally-bad fits; the picture is the check that does not."""
    from rietx.viz.plots import plot_result

    order, _, res = ridge_fit
    OUT.mkdir(exist_ok=True)
    path = OUT / f"scale_b_ridge_{order}.png"
    plot_result(res, path=str(path))
    import matplotlib.pyplot as plt

    plt.close("all")
    assert path.exists()
