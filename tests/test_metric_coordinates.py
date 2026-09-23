"""Q-17d: refine a phase's cell on the coordinates of its invariant metric
subspace when ``CellConstraints`` (ties and fixed angles) cannot state it.

Design issue: https://github.com/yue-here/rietx/issues/293 (the specification;
where the code disagrees, the issue wins). Q-17b/Q-17c's own reports
(``checks/Q17B_METRIC_FROM_ROTATIONS.md``, ``checks/Q17C_CHILD_BASIS_CHOICE.md``)
and T-A0b's (``checks/TA0B_LAST_DIRECTION.md``) are the measured ground this
rung starts from: Q-17c's basis choice resolved 39/39 of Q-17's all-group
k-sweep to an ordinary ``CellConstraints`` tie/fixed-angle pair, and the one
case still refusing on the *magnetic-supercell* route it did not touch is a
real structure, Ba₂FeSbSe₅'s S1(rank 1)#2 at k=(0,½,½) (Maier, Gaultois et al.,
PRB 103, 054115 (2021) — published, Michael a co-author). That is the
measured trigger this module tests against, not a synthetic stand-in.

Five sections:

* the ten named settings (+ R-centred trigonal) are bit-identical
  ``CellConstraints`` — nothing here should move an already-working setting.
* Ba₂FeSbSe₅'s S1(rank 1)#2 now builds, on both the route that locks its cell
  (``displacive_statement``, M1's distortion modes) and the route that
  refines it (``magnetic_supercell`` with an ``Atom.moment``) — the second is
  where ``MetricConstraints``'s ``g`` coordinates are actually exercised.
* the A = 0 control on the magnetic route: |det P|² × parent, to 1e-10.
* a synthetic refinement recovers a known oblique child cell from a cold
  start, with finite propagated esds.
* what the issue's own text gets wrong on this tree: P 6 m m at k=(0,0,½) no
  longer needs ``MetricConstraints`` at all (Q-17c already resolved it via
  ordinary ties), so this module pins that it stays a plain ``CellConstraints``
  build rather than asserting the issue's stale ``m = 2`` claim.
"""

from fractions import Fraction
from pathlib import Path

import gemmi
import numpy as np
import pytest

import rietx as rx
from rietx.backend import get_backend, set_backend
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.supercell import (
    displacive_statement,
    magnetic_supercell,
)
from rietx.crystallography.symmetry import (
    CellConstraints,
    MetricConstraints,
    cell_constraints,
    cell_constraints_from_rotations,
    cell_from_metric_coordinates,
    get_spacegroup,
    metric_coordinates,
    resolve_group,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev, Instrument
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.staged import RefinementPlan, Stage

#: Ba₂FeSbSe₅ at 1.5 K, the refined nuclear structure and its instrument (`tests/data/README.md`).
DATA = Path(__file__).resolve().parent / "data" / "ba2fesbse5"
K_0_HALF_HALF = ("0", "1/2", "1/2")

#: Q-17b's own ten (nine tabulated settings + R-centred trigonal), copied
#: verbatim from ``tests/test_metric_from_rotations.py`` — the brief's own
#: acceptance line ("Named settings ... bit-identical CellConstraints, assert
#: it") names this exact set, and duplicating it here (rather than importing
#: it) keeps this module's own regression pin independent of that file.
NAMED_SETTINGS = ("P n m a", "C m c m", "F d -3 m:2", "P 6_3/m m c", "R -3 c:H",
                  "R -3 c:R", "P 1 21/m 1", "I 4_1/a m d:2", "P -1")


def _rotations_of(symbol: str) -> list[np.ndarray]:
    sg = get_spacegroup(symbol)
    return [np.array(op.rot, dtype=np.int64) // gemmi.Op.DEN
            for op in sg.operations()]


def _cell(values) -> Cell:
    a, b, c, al, be, ga = values
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=al), beta=Parameter(value=be),
                gamma=Parameter(value=ga))


def _parent(symbol: str, cell_values, xyz=(0.11, 0.13, 0.17)) -> Phase:
    return Phase(name="parent", space_group=symbol, cell=_cell(cell_values),
                atoms=[Atom(label="M1", species="Fe", x=Parameter(value=xyz[0]),
                           y=Parameter(value=xyz[1]), z=Parameter(value=xyz[2]),
                           occ=Parameter(value=1.0), biso=Parameter(value=0.5))])


@pytest.fixture(scope="module")
def ba2fesbse5_parent() -> tuple[Phase, Instrument]:
    struct = rx.Structure.model_validate_json(
        (DATA / "nuclear_1p5K_structure.json").read_text(encoding="utf-8"))
    inst = rx.Instrument.model_validate_json(
        (DATA / "nuclear_1p5K_instrument.json").read_text(encoding="utf-8"))
    return struct.phases[0], inst


# ---------------------------------------------------------------------------
# the ten named settings, unaffected
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("symbol", NAMED_SETTINGS)
def test_ten_named_settings_are_still_bit_identical_cellconstraints(symbol):
    derived = cell_constraints_from_rotations(_rotations_of(symbol))
    assert isinstance(derived, CellConstraints), (
        f"{symbol}: Q-17d's fallback must never trigger on a tabulated "
        f"setting — got {type(derived).__name__}")
    assert derived == cell_constraints(get_spacegroup(symbol))


# ---------------------------------------------------------------------------
# Ba2FeSbSe5's S1(rank 1)#2 at k=(0,1/2,1/2): the measured trigger
# ---------------------------------------------------------------------------
def test_displacive_route_now_builds_with_four_metric_coordinates(ba2fesbse5_parent):
    """The exact case T-A0b found still refusing on operator-list-basis.

    ``displacive_statement`` (M1's distortion-mode route) locks the child
    cell regardless of ``CellConstraints`` vs ``MetricConstraints`` (M1's own
    rule, untouched here) — so this checks that the phase *builds* and that
    the diagnostic and the underlying constraints both correctly name the
    4-dimensional metric subspace, not that the cell is independently free.
    """
    ph, _inst = ba2fesbse5_parent
    statement = displacive_statement(ph, K_0_HALF_HALF, irrep="S1",
                                     direction="(rank 1)#2")
    assert statement.child_group_named is False
    assert statement.phase.distortion_modes, (
        "the displacive route is expected to carry amplitude modes; if this "
        "no longer holds, the held-cell branch this test exercises has moved")

    sg = resolve_group(statement.phase.space_group,
                       statement.phase.symmetry_operations)
    cons = cell_constraints(sg)
    assert isinstance(cons, MetricConstraints)
    assert cons.m == 4, f"measured dimension was {cons.m}, not T-A0b's 4"
    assert "dimension 4" in cons.relation

    diag = next(d for d in statement.diagnostics if d.code == "CHILD_GROUP_UNNAMED")
    assert "4 metric coordinate" in diag.message

    cell = statement.phase.cell.lengths_angles()
    g0 = metric_coordinates(cons, cell)
    back = cell_from_metric_coordinates(cons, g0)
    assert np.max(np.abs(np.array(cell) - np.array(back))) < 1e-8, (
        "the cell must lie in its own derived subspace to round-trip exactly")

    # the phase still predicts a finite pattern (M1's existing locked-cell path)
    y = rx.Refinement(Structure(phases=[statement.phase]),
                      _inst.model_copy(deep=True)).predict(np.arange(8.0, 90.0, 0.02))
    assert np.isfinite(np.asarray(y)).all() and float(np.asarray(y).max()) > 0.0


def _s1_rank1_2_magnetic_candidate(ph: Phase):
    fe = next(a for a in ph.atoms if a.label == "Fe1")
    cs = candidates(ph.space_group, (fe.x.value, fe.y.value, fe.z.value),
                    K_0_HALF_HALF, kind="magnetic")
    return next(c for c in cs if c.label.startswith("S1(rank 1)#2"))


@pytest.fixture(scope="module")
def ba2fesbse5_magnetic_statement(ba2fesbse5_parent):
    """The *same* transform, magnetic-moment route: a free (not locked) cell.

    ``nuclear_group="magnetic"`` reads the candidate's own (smaller) isotropy
    subgroup rather than the parent's full point group, which measures a
    different-dimension subspace (m=3, not the parent route's 4) — a real,
    independent trigger of ``MetricConstraints``, and the one this module
    uses to exercise ``ParameterTable``'s g-coordinate machinery, since this
    route carries ``Atom.moment`` rather than a distortion mode and so does
    not lock its cell.
    """
    ph, inst = ba2fesbse5_parent
    cand = _s1_rank1_2_magnetic_candidate(ph)
    statement = magnetic_supercell(ph, candidate=cand, magnetic_species="Fe",
                                   ion="Fe3+", magnitude=4.0,
                                   nuclear_group="magnetic")
    return statement, inst


def test_magnetic_route_builds_with_a_refinable_metric_cell(ba2fesbse5_magnetic_statement):
    statement, _inst = ba2fesbse5_magnetic_statement
    assert statement.child_group_named is False
    assert not statement.phase.distortion_modes

    sg = resolve_group(statement.phase.space_group,
                       statement.phase.symmetry_operations)
    cons = cell_constraints(sg)
    assert isinstance(cons, MetricConstraints)
    assert 1 <= cons.m <= 6

    phase = statement.phase.model_copy(update={
        "cell": statement.phase.cell.model_copy(update={
            n: getattr(statement.phase.cell, n).model_copy(update={"vary": True})
            for n in ("a", "b", "c", "alpha", "beta", "gamma")})})
    table = ParameterTable(Structure(phases=[phase]), _inst)
    g_paths = [e.path for e in table.entries
              if e.path.startswith("phases.0.cell.metric.g")]
    assert len(g_paths) == cons.m
    assert all(table.entries[table._paths[p]].vary for p in g_paths)
    locked_cell = [e for e in table.entries
                  if e.path.startswith("phases.0.cell.")
                  and "metric" not in e.path]
    assert len(locked_cell) == 6 and all(not e.vary and e.locked for e in locked_cell)

    theta = table.x0()
    values = table.decode(theta)
    decoded = tuple(values[f"phases.0.cell.{n}"]
                    for n in ("a", "b", "c", "alpha", "beta", "gamma"))
    assert np.max(np.abs(np.array(decoded)
                        - np.array(phase.cell.lengths_angles()))) < 1e-8


def test_jax_backend_refuses_a_metric_constrained_cell_by_name(
        ba2fesbse5_magnetic_statement):
    """No traced twin exists for the g -> cell map (Q-17d) — same choice
    ``rietx.backend.traced`` already made for the magnetic structure factor."""
    statement, inst = ba2fesbse5_magnetic_statement
    assert get_backend().name == "numpy", "must start numpy or this test leaks state"
    try:
        set_backend("jax")
        with pytest.raises(ValueError, match="no traced twin"):
            ParameterTable(Structure(phases=[statement.phase]), inst)
    finally:
        set_backend("numpy")


# ---------------------------------------------------------------------------
# the A = 0 control: |det P|^2 * parent, to 1e-10
# ---------------------------------------------------------------------------
def test_a_equals_zero_control_on_the_magnetic_route_is_det_p_squared(
        ba2fesbse5_parent):
    """Same control and recipe as ``test_metric_from_rotations.py``'s own
    (Cmm2 at k=(0,0,½)), applied to this rung's own real-structure trigger:
    background zeroed (additive, so it would not hold the ratio constant even
    for identical peaks) and the constant read off the median ratio over the
    points the parent pattern actually lives on.
    """
    ph, inst = ba2fesbse5_parent
    cand = _s1_rank1_2_magnetic_candidate(ph)
    statement = magnetic_supercell(ph, candidate=cand, magnetic_species="Fe",
                                   ion="Fe3+", magnitude=0.0,
                                   nuclear_group="magnetic", vary=False)
    two_theta = np.arange(8.0, 90.0, 0.02)
    ins = inst.model_copy(deep=True)
    ins.background = BackgroundChebyshev(coefficients=[Parameter(value=0.0)])
    y_parent = np.asarray(rx.Refinement(
        Structure(phases=[ph]), ins.model_copy(deep=True)).predict(two_theta))
    assert float(y_parent.max()) > 0.0
    y_child = np.asarray(rx.Refinement(
        Structure(phases=[statement.phase]), ins.model_copy(deep=True)
    ).predict(two_theta))
    live = y_parent > 1e-6 * float(y_parent.max())
    ratio = y_child[live] / y_parent[live]
    constant = float(np.median(ratio))
    assert constant == pytest.approx(statement.index ** 2, rel=1e-9), (
        f"constant {constant:.6g} against |det P|^2 = {statement.index ** 2}")
    worst = float(np.max(np.abs(y_child - constant * y_parent)) / float(y_parent.max()))
    assert worst < 1e-10


# ---------------------------------------------------------------------------
# synthetic recovery: a known oblique child cell from a cold start
# ---------------------------------------------------------------------------
def _simulate(structure: Structure, instrument: Instrument, seed: int) -> PatternData:
    from rietx.model.forward import compile_model

    two_theta = np.arange(8.0, 90.0, 0.02)
    blank = PatternData(two_theta=two_theta.tolist(),
                        intensity=np.zeros_like(two_theta).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    return PatternData(two_theta=model.tt.tolist(),
                       intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())


@pytest.fixture(scope="module")
def synthetic_truth(ba2fesbse5_magnetic_statement):
    """A pattern generated at g offset from the built candidate's own start.

    The offset (0.3% on each g-coordinate, signed to avoid an accidental
    return to a higher-symmetry point) moves every one of a, b, c and the one
    free angle by a measurable, non-degenerate amount, so recovering it is a
    real test of the map, not of a null perturbation.
    """
    statement, inst = ba2fesbse5_magnetic_statement
    ins = inst.model_copy(deep=True)
    ins.background = BackgroundChebyshev(coefficients=[Parameter(value=20.0)])
    phase = statement.phase.model_copy(update={
        "atoms": [a.model_copy(update={
            "moment": a.moment.model_copy(update={"vary": False}) if a.moment else None})
                 for a in statement.phase.atoms]})
    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    cons = cell_constraints(sg)
    assert isinstance(cons, MetricConstraints)
    g0 = metric_coordinates(cons, phase.cell.lengths_angles())
    signs = np.array([1.0 if k % 2 == 0 else -1.0 for k in range(cons.m)])
    g_true = g0 * (1.0 + 0.003 * signs)
    cell_true = cell_from_metric_coordinates(cons, g_true)
    phase_true = phase.model_copy(update={"cell": _cell(cell_true)})
    data = _simulate(Structure(phases=[phase_true]), ins, seed=17)
    return phase, cons, cell_true, data, ins


@pytest.mark.slow
def test_a_known_oblique_child_cell_is_recovered_from_a_cold_start(synthetic_truth):
    phase, cons, cell_true, data, ins = synthetic_truth
    start = phase.model_copy(update={
        "cell": phase.cell.model_copy(update={
            n: getattr(phase.cell, n).model_copy(update={"vary": True})
            for n in ("a", "b", "c", "alpha", "beta", "gamma")})})
    ref = rx.Refinement(Structure(phases=[start]), ins)
    result = ref.fit(data, plan=RefinementPlan(stages=[
        Stage("scale", ["phases.*.scale", "instrument.background.c*"], max_iter=200),
        Stage("cell", ["phases.*.scale", "instrument.background.c*",
                       "phases.*.cell.metric.g*"], max_iter=400),
    ]))
    assert result.status == "converged"
    names = ("a", "b", "c", "alpha", "beta", "gamma")
    # a locked entry (the six derived cell values) carries no ``RefinedParameter``
    # row of its own (only free/tied entries do -- the same "locked, so no C
    # row, so no ``result.parameters`` row" shape ``_collect_atom_moment``'s
    # crystalaxis_* components already have, which ``_apply_esds`` narrows the
    # written-back esd map to). The refined structure carries the *value*
    # (``apply_to_models`` always writes that), which is what the recovery
    # claim is about.
    refined_cell = ref.structure.phases[0].cell
    recovered = np.array([getattr(refined_cell, n).value for n in names])
    length_err = np.max(np.abs(recovered[:3] - np.array(cell_true[:3])))
    assert length_err < 1e-4, (
        f"lengths recovered to {length_err:.2e} A against a 1e-4 A target: "
        f"{recovered[:3]} vs {cell_true[:3]}")

    # The propagated esd itself: since a locked row's esd does not reach the
    # model through the normal report path (above), this checks the
    # machinery directly -- ``stderr_physical``'s new cell block, fed the g
    # covariance from a table rebuilt at the converged state.
    table = ParameterTable(ref.structure, ref.instrument)
    theta = table.x0()
    stderr_internal = np.full(len(theta), 0.01)
    esds = table.stderr_physical(theta, stderr_internal)
    for n in names:
        path = f"phases.0.cell.{n}"
        assert path in esds and np.isfinite(esds[path]) and esds[path] >= 0.0, (
            f"{n}: propagated esd must be a finite, present number; got "
            f"{esds.get(path)!r}")


# ---------------------------------------------------------------------------
# what the issue's own text gets wrong: P 6 m m at (0,0,1/2) already builds
# via ordinary CellConstraints on this tree (Q-17c), not MetricConstraints
# ---------------------------------------------------------------------------
def test_p6mm_0_0_half_stays_ordinary_cellconstraints_not_metric():
    """The design issue (#293) names this as the second still-refusing case,
    needing ``MetricConstraints`` with m=2. Measured on this tree (base
    rietx-integration ffaa80ef, which already carries Q-17c's basis choice):
    it does not reach the metric-coordinate fallback at all — the ordinary
    two-dictionary derivation already succeeds (b=a, both other angles fixed,
    gamma free), because Q-17c's ``child_basis`` picked the conventional cell
    for this point group before Q-17b/Q-17d's metric machinery is ever asked.
    The issue's text is stale for this specific case; this pins the measured
    behaviour rather than the issue's claim (brief: "where the code disagrees,
    the issue wins and you report it" -- reported in this rung's summary).
    """
    parent = _parent("P 6 m m", (6.0, 6.0, 9.0, 90.0, 90.0, 120.0))
    kk = (Fraction(0), Fraction(0), Fraction(1, 2))
    site = (Fraction(11, 100), Fraction(13, 100), Fraction(17, 100))
    found = candidates("P 6 m m", site, kk)
    unnamed = [c for c in found if c.identification is None]
    assert unnamed
    statement = magnetic_supercell(parent, candidate=unnamed[0],
                                   nuclear_group="magnetic")
    sg = resolve_group(statement.phase.space_group,
                       statement.phase.symmetry_operations)
    cons = cell_constraints(sg)
    assert isinstance(cons, CellConstraints), (
        f"expected an ordinary CellConstraints on this tree; got "
        f"{type(cons).__name__} -- if this now fails, Q-17c's basis choice "
        f"changed and the issue's m=2 claim may have become current after all")
