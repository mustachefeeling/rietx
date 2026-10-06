"""Tether and anti-bump: one-sided distance restraints (WP-1809).

A tether row is √w·max(0, d − d_max)/σ and an anti-bump row
√w·min(0, d − d_min)/σ (TOPAS's ``Distance_Restrain_Keep_Within`` /
``_Keep_Out``, Technical Reference p. 159).  Each is checked where it can
fail: zero on its flat side, slope 1/σ on the other, the analytic row Jacobian
against a finite difference of the residual on both sides of the kink, the
data statistics untouched by the rows, and a pair list that is complete,
excludes a body's own pairs and states no minimum nobody gave.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, PatternData
from rietx.crystallography.bodies import add_body
from rietx.model.forward import compile_model
from rietx.model.restraints import anti_bump_restraints, summarise_restraints
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    AntiBumpRestraint,
    Atom,
    Cell,
    Phase,
    Structure,
    TetherRestraint,
)

LAB = Instrument.debye_scherrer(wavelength=1.5406)


def _pair(dx: float, restraint) -> tuple[Structure, ParameterTable]:
    """Two atoms in a P1 cubic 6 Å cell, ``dx`` (fractional) apart along a."""
    P = Parameter
    s = Structure(phases=[Phase(
        name="p", space_group="P1", cell=Cell.cubic(6.0),
        atoms=[Atom(label="A", species="Li", x=P(value=0.2, vary=True),
                    y=P(value=0.3, vary=True), z=P(value=0.4, vary=True)),
               Atom(label="B", species="O", x=P(value=0.2 + dx, vary=True),
                    y=P(value=0.3, vary=True), z=P(value=0.4, vary=True))],
        scale=P(value=1e-3), restraints=[restraint])])
    return s, ParameterTable(s, LAB)


def _rows(s, table):
    tt = np.arange(20.0, 60.0, 0.1)
    model = compile_model(s, LAB, PatternData(two_theta=tt.tolist(),
                                              intensity=np.ones_like(tt).tolist()),
                          mode="rietveld", moving_paths=set(table.moving_paths))
    return model


@pytest.mark.parametrize("dx, expect", [(0.30, 0.0), (0.40, (2.4 - 2.0) / 0.05)])
def test_tether_is_zero_inside_and_linear_outside(dx, expect):
    s, table = _pair(dx, TetherRestraint(atom_i=0, atom_j=1, max_distance=2.0,
                                         sigma=0.05, op_index=0))
    model = _rows(s, table)
    rep = summarise_restraints(model.restraints, table.decode(table.x0()))
    assert rep.rows[0].kind == "tether"
    assert rep.rows[0].deviation_over_sigma == pytest.approx(expect, abs=1e-9)


@pytest.mark.parametrize("dx, expect", [(0.40, 0.0), (0.30, (1.8 - 2.0) / 0.05)])
def test_anti_bump_is_zero_outside_and_linear_inside(dx, expect):
    s, table = _pair(dx, AntiBumpRestraint(atom_i=0, atom_j=1, min_distance=2.0,
                                           sigma=0.05, op_index=0))
    model = _rows(s, table)
    rep = summarise_restraints(model.restraints, table.decode(table.x0()))
    assert rep.rows[0].kind == "anti_bump"
    assert rep.rows[0].deviation_over_sigma == pytest.approx(expect, abs=1e-9)


@pytest.mark.parametrize("cls, dx", [
    (TetherRestraint, 0.40), (TetherRestraint, 0.30), (TetherRestraint, 1/3 + 1e-4),
    (AntiBumpRestraint, 0.30), (AntiBumpRestraint, 0.40), (AntiBumpRestraint, 1/3 - 1e-4)])
def test_analytic_row_matches_a_central_difference_either_side_of_the_kink(cls, dx):
    key = "max_distance" if cls is TetherRestraint else "min_distance"
    s, table = _pair(dx, cls(atom_i=0, atom_j=1, sigma=0.05, op_index=0, **{key: 2.0}))
    model = _rows(s, table)
    n_data = len(model.tt)
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    h = 1e-7
    for c in range(len(theta)):
        tp, tm = theta.copy(), theta.copy()
        tp[c] += h
        tm[c] -= h
        fd = (residual(tp)[n_data] - residual(tm)[n_data]) / (2 * h)
        assert jac[n_data, c] == pytest.approx(fd, rel=1e-5, abs=1e-6), (cls, dx, c)


def test_one_sided_rows_leave_the_data_statistics_alone():
    s, table = _pair(0.30, AntiBumpRestraint(atom_i=0, atom_j=1, min_distance=2.0,
                                             sigma=0.05, op_index=0))
    model = _rows(s, table)
    bare = s.model_copy(deep=True)
    bare.phases[0].restraints = []
    model0 = _rows(bare, ParameterTable(bare, LAB))
    values = table.decode(table.x0())
    assert np.array_equal(model.evaluate(values), model0.evaluate(values))
    assert len(_make_residual(model, table)(table.x0())) == len(model.tt) + 1


def _body_phase() -> Phase:
    P = Parameter
    seed = Atom(label="Li", species="Li", x=P(value=0.50), y=P(value=0.50), z=P(value=0.50))
    phase = Phase(name="p", space_group="P-1", cell=Cell.cubic(7.0), atoms=[seed])
    tmpl = np.array([[0.0, 0.0, 0.0], [1.25, 0.0, 0.0], [-0.6, 1.1, 0.0]])
    return add_body(phase, "co2", ["C1", "O1", "O2"], ["C", "O", "O"], tmpl,
                    (0.31, 0.42, 0.27))


def test_the_pair_list_is_complete_and_states_no_unasked_minimum():
    phase = _body_phase()
    rows = anti_bump_restraints(phase, {("Li", "O"): 1.9, ("O", "O"): 2.6},
                                margin=10.0)
    # no row inside the body, none for a pair nobody gave a minimum for
    sp = [a.species for a in phase.atoms]
    for r in rows:
        assert {sp[r.atom_i], sp[r.atom_j]} in ({"Li", "O"}, {"O"})
        # never the body's own copy of an intra-body pair
        assert not ({r.atom_i, r.atom_j} <= {1, 2, 3} and r.op_index == 0
                    and r.translation == (0, 0, 0))
    # completeness against a brute-force count of images under the cut
    from rietx.crystallography.structure_factor import compile_phase_sites
    from rietx.model.restraints import _metric_g
    sites = compile_phase_sites(phase)
    g = _metric_g(phase.cell.lengths_angles())
    xyz = [np.array([a.x.value, a.y.value, a.z.value]) for a in phase.atoms]
    expected = 0
    for i in range(4):
        for j in range(i, 4):
            body_pair = {i, j} <= {1, 2, 3}
            key = tuple(sorted((sp[i], sp[j])))
            r0 = {("Li", "O"): 1.9, ("O", "O"): 2.6}.get(key)
            if r0 is None:
                continue
            for k, (R, t) in enumerate(zip(*sites.ops[j], strict=True)):
                for n in np.ndindex(11, 11, 11):     # exhaustive for a 10 Å cut
                    shift = np.array(n) - 5
                    if body_pair and k == 0 and not shift.any():
                        continue          # op 0 of P-1 is the identity
                    dx = np.asarray(R) @ xyz[j] + np.asarray(t) + shift - xyz[i]
                    d = float(np.sqrt(dx @ g @ dx))
                    if 1e-3 < d < r0 + 10.0:
                        expected += 1
    assert len(rows) == expected > 0
    assert anti_bump_restraints(phase, 1.0, exclude_same_body=False, margin=0.4)


def test_the_pair_list_does_not_depend_on_the_stored_cell():
    """Shifting an atom by whole lattice vectors is the same structure, so the
    pair list keeps the same contact: P2₁ toy, Li and the 2₁ image of an O
    2.0 Å apart.  The shell about n = 0 lost it once the stored coordinates
    sat two cells apart (a body placed about any origin, a free atom anywhere)."""
    from rietx.schemas.structure import Atom, Cell, Phase
    cell = Cell(a=Parameter(value=5.0), b=Parameter(value=6.0), c=Parameter(value=7.0),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))
    for shift in ([0, 0, 0], [1, 0, 0], [2, 0, 0], [-3, 2, 1], [0, 0, 5]):
        li = np.array([0.10, 0.10, 0.10]) + shift
        o = np.array([-0.10, -0.40, -0.10 + 2.0 / 7.0])
        ph = Phase(name="t", space_group="P 1 21 1", cell=cell, atoms=[
            Atom(label="Li1", species="Li", x=Parameter(value=li[0]),
                 y=Parameter(value=li[1]), z=Parameter(value=li[2])),
            Atom(label="O1", species="O", x=Parameter(value=o[0]),
                 y=Parameter(value=o[1]), z=Parameter(value=o[2]))])
        rows = anti_bump_restraints(ph, {("Li", "O"): 2.5}, margin=0.0)
        assert len(rows) == 1, shift
        r = rows[0]
        img = np.array([[-1, 0, 0], [0, 1, 0], [0, 0, -1]]) @ o + [0, 0.5, 0] + r.translation
        d = (img - li) * [5.0, 6.0, 7.0]
        assert float(np.linalg.norm(d)) == pytest.approx(2.0, abs=1e-9), shift
