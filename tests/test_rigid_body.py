"""Rigid bodies: schema, collector, anchored rotation, the body's own rows (WP-1805).

A body is a ``RigidBody`` over a phase's own atoms; its origin refines on the
site basis and its orientation as an anchored rotation increment, and its
atoms' coordinates are the rows of a derived block (WP-1804).  The positive
arms here are the ones WP-1803's record names: an orientation recovered from a
synthetic pattern started 3° and 10° off, with its esd covering the truth; a
stale anchor caught at the next build; a tie from a rotation increment refused.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.crystallography import rotation
from rietx.crystallography.bodies import (
    add_body,
    body_fractional,
    body_from_atoms,
    place_body_atoms,
)
from rietx.model.forward import compile_model
from rietx.params.vector import AffineTie, ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, RigidBody, Structure
from rietx.strategy.staged import RefinementPlan, Stage

INS = Instrument.debye_scherrer(wavelength=1.5406)
INS.profile.w.value = 8e-3
CELL = (7.21, 8.13, 9.47, 84.3, 97.6, 104.2)          # WP-1803's triclinic cell
BODY_GLOBS = ["phases.*.scale", "instrument.background.*",
              "phases.*.rigid_bodies.*.origin.dof.*",
              "phases.*.rigid_bodies.*.rotation.*"]


def c6br() -> np.ndarray:
    """WP-1803's body: ideal D6h ring (C–C 1.39 Å) and a C–Br of 1.90 Å."""
    ring = np.array([[1.39 * math.cos(k * math.pi / 3),
                      1.39 * math.sin(k * math.pi / 3), 0.0] for k in range(6)])
    return np.vstack([ring, ring[0] * (1.0 + 1.90 / 1.39)])


def _cell() -> Cell:
    P = Parameter
    return Cell(a=P(value=CELL[0]), b=P(value=CELL[1]), c=P(value=CELL[2]),
                alpha=P(value=CELL[3]), beta=P(value=CELL[4]), gamma=P(value=CELL[5]))


def body_structure(q, origin=(0.31, 0.42, 0.27), sg="P-1") -> Structure:
    seed = Atom(label="seed", species="C", x=Parameter(value=0.0),
                y=Parameter(value=0.0), z=Parameter(value=0.0))
    phase = Phase(name="c6br", space_group=sg, cell=_cell(), atoms=[seed],
                  scale=Parameter(value=1e-2, min=0.0, transform="softplus"))
    phase = add_body(phase, "c6br", [f"C{i}" for i in range(6)] + ["Br"],
                     ["C"] * 6 + ["Br"], c6br(), origin, orientation=q, biso=2.0)
    # the seed atom only lets the empty phase validate; the body is the phase
    phase = Phase.model_validate({**phase.model_dump(),
                                  "atoms": phase.model_dump()["atoms"][1:]})
    return Structure(phases=[phase])


def synthesize(structure: Structure, seed: int = 3) -> PatternData:
    tt = np.arange(8.0, 70.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, INS, blank, mode="rietveld")
    table = ParameterTable(structure, INS)
    y = model.evaluate(table.decode(table.x0())) + 30.0
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


Q_TRUE = rotation.canonical_quaternion(
    np.asarray(rotation.quaternion_from_vector(np.array([0.4, -0.7, 1.1]))))


def _turned(q, deg, axis=(0.3, 0.8, -0.5)):
    a = np.asarray(axis) / np.linalg.norm(axis)
    r = (np.asarray(rotation.matrix_from_vector(math.radians(deg) * a))
         @ np.asarray(rotation.matrix_from_quaternion(q)))
    return np.asarray(rotation.canonical_quaternion(rotation.quaternion_from_matrix(r)))


def _angle_deg(qa, qb) -> float:
    ra = np.asarray(rotation.matrix_from_quaternion(np.asarray(qa)))
    rb = np.asarray(rotation.matrix_from_quaternion(np.asarray(qb)))
    return math.degrees(float(np.linalg.norm(
        np.asarray(rotation.vector_from_matrix(ra @ rb.T)))))


# --------------------------------------------------------------- declaration
def test_a_body_over_placed_atoms_decodes_them_back():
    phase = Phase(name="t", space_group="P1", cell=_cell(), atoms=[
        Atom(label=f"A{i}", species="C", x=Parameter(value=0.1 + 0.07 * i),
             y=Parameter(value=0.2 + 0.03 * i * i), z=Parameter(value=0.5 - 0.05 * i))
        for i in range(5)])
    body = body_from_atoms(phase, [f"A{i}" for i in range(5)], "five")
    s = Structure(phases=[phase.model_copy(update={"rigid_bodies": [body]})])
    table = ParameterTable(s, INS)
    values = table.decode(table.x0())
    for j, atom in enumerate(phase.atoms):
        for c in "xyz":
            assert abs(values[f"phases.0.atoms.{j}.{c}"] - getattr(atom, c).value) < 1e-12
    paths = {e.path: e for e in table.entries}
    assert paths["phases.0.atoms.2.x"].locked
    assert "phases.0.atoms.2.dof.0" not in paths
    assert {f"phases.0.rigid_bodies.0.rotation.{k}" for k in range(3)} <= set(paths)
    assert {f"phases.0.rigid_bodies.0.origin.dof.{k}" for k in range(3)} <= set(paths)
    assert table.body_rows()["phases.0.atoms.4.z"] == "five"


def test_a_body_atom_refuses_vary_and_shared_membership():
    s = body_structure(Q_TRUE)
    s.phases[0].atoms[2].x.vary = True
    with pytest.raises(ValueError, match="placed by rigid body 'c6br'"):
        ParameterTable(s, INS)
    s = body_structure(Q_TRUE)
    phase = s.phases[0]
    twin = RigidBody(name="twin", atoms=["C0", "C1"], template=[(0, 0, 0), (1.39, 0, 0)],
                     origin=phase.rigid_bodies[0].origin)
    with pytest.raises(ValueError, match="RIGID_BODY_SHARED_ATOM"):
        Phase.model_validate({**phase.model_dump(),
                              "rigid_bodies": [*phase.model_dump()["rigid_bodies"],
                                               twin.model_dump()]})


def test_an_edited_body_atom_is_refused_as_drift_and_place_body_atoms_repairs():
    s = body_structure(Q_TRUE)
    s.phases[0].atoms[3].y.value += 0.01
    with pytest.raises(ValueError, match="RIGID_BODY_TEMPLATE_DRIFT"):
        ParameterTable(s, INS)
    fixed = Structure(phases=[place_body_atoms(s.phases[0])])
    ParameterTable(fixed, INS)


def test_a_body_on_a_special_position_is_refused_for_now():
    s = body_structure(Q_TRUE, origin=(0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="RIGID_BODY_NOT_INVARIANT"):
        ParameterTable(s, INS)


def test_parameter_rows_say_which_body_holds_a_coordinate():
    ref = Refinement(body_structure(Q_TRUE), INS, history=False)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.0.x"].body == "c6br"
    assert "rigid body 'c6br'" in rows["phases.0.atoms.0.x"].held_because
    assert rows["phases.0.rigid_bodies.0.rotation.0"].refinable


# ------------------------------------------------------------ the esd chain
def test_body_esds_equal_the_central_fd_chain():
    s = body_structure(Q_TRUE)
    for p in ("a", "b", "c", "alpha", "beta", "gamma"):
        getattr(s.phases[0].cell, p).vary = True
    table = ParameterTable(s, INS)
    table.set_vary(BODY_GLOBS, True)
    theta = table.x0()
    for k, v in enumerate((0.05, -0.03, 0.02)):
        theta[table.free_paths.index(f"phases.0.rigid_bodies.0.rotation.{k}")] = v
    rng = np.random.default_rng(5)
    a = rng.normal(size=(len(theta), len(theta)))
    cov = a @ a.T + len(theta) * np.eye(len(theta))
    s_int = np.sqrt(np.diag(cov)) * 1e-3
    corr = cov / np.outer(np.sqrt(np.diag(cov)), np.sqrt(np.diag(cov)))
    esd = table.stderr_physical(theta, s_int, corr)
    h = 1e-6
    rows = [f"phases.0.atoms.{j}.{c}" for j in range(7) for c in "xyz"]
    jac = np.zeros((len(rows), len(theta)))
    for col in range(len(theta)):
        tp, tm = theta.copy(), theta.copy()
        tp[col] += h
        tm[col] -= h
        vp, vm = table.decode(tp), table.decode(tm)
        jac[:, col] = [(vp[p] - vm[p]) / (2 * h) for p in rows]
    # the scale is softplus: chain its internal esd the way the table does
    from rietx.params.transforms import dphys_dinternal
    sc = table.free_paths.index("phases.0.scale")
    s_phys = s_int.copy()
    s_phys[sc] *= abs(dphys_dinternal(float(theta[sc]), "softplus"))
    var = np.einsum("ij,jk,ik->i", jac, corr * np.outer(s_phys, s_phys), jac)
    # the FD Jacobian is of θ, so the scale's column carries dφ/du already;
    # the scale reaches no body row, which makes the chain factor moot there
    for r, p in enumerate(rows):
        assert esd[p] == pytest.approx(math.sqrt(var[r]), rel=1e-8), p


# ----------------------------------------------------------- the recovery
@pytest.mark.parametrize("off_deg", [3.0, 10.0])
def test_orientation_recovered_from_a_synthetic_pattern(off_deg):
    """WP-1803's C₆Br body, Poisson noise, started off by 3° and 10° (and the
    origin 0.02 off): the orientation comes back within 0.1° with every
    increment component within 3σ of the truth, and the committed body is
    rigid to 1e-9 Å."""
    pattern = synthesize(body_structure(Q_TRUE))
    start = body_structure(_turned(Q_TRUE, off_deg), origin=(0.33, 0.41, 0.26))
    ref = Refinement(start, INS, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("body", BODY_GLOBS, max_iter=200)]))
    assert result.status == "converged"
    fitted = ref.fitted_structure.phases[0].rigid_bodies[0]
    err = _angle_deg(fitted.orientation, Q_TRUE)
    assert err < 0.1, f"orientation {err:.4f}° off"
    # the increment the fit reports, against the increment the truth needs
    r0 = np.asarray(rotation.matrix_from_quaternion(np.asarray(start.phases[0]
                                                               .rigid_bodies[0].orientation)))
    rt = np.asarray(rotation.matrix_from_quaternion(Q_TRUE))
    w_true = np.asarray(rotation.vector_from_matrix(rt @ r0.T))
    for k in range(3):
        par = result.parameter(f"phases.0.rigid_bodies.0.rotation.{k}")
        assert par.stderr is not None and par.stderr > 0
        assert abs(par.value - w_true[k]) < 3 * par.stderr + 1e-9, (k, par.value, w_true[k])
    # every body atom carries an esd (through the block's local Jacobian),
    # and the body is rigid in the fitted cell
    phase = ref.fitted_structure.phases[0]
    assert all(getattr(a, c).stderr is not None and getattr(a, c).stderr > 0
               for a in phase.atoms for c in "xyz")
    frac = np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])
    assert np.allclose(frac, body_fractional(fitted, phase.cell.lengths_angles()),
                       atol=1e-12)
    from rietx.params.derived import cartesian_frame
    cart = frac @ np.asarray(cartesian_frame(phase.cell.lengths_angles())).T
    d = np.linalg.norm(cart[:, None] - cart[None], axis=2)
    t = c6br() - c6br().mean(axis=0)
    d0 = np.linalg.norm(t[:, None] - t[None], axis=2)
    assert np.abs(d - d0).max() < 1e-9


def test_a_stale_anchor_is_caught_at_the_next_build():
    """The positive arm of the re-exponentiation: write a turned body back
    *without* composing its orientation and the next table refuses it."""
    s = body_structure(Q_TRUE)
    table = ParameterTable(s, INS)
    table.set_vary(BODY_GLOBS, True)
    theta = table.x0()
    theta[table.free_paths.index("phases.0.rigid_bodies.0.rotation.1")] = math.radians(3.0)
    table.commit(theta)
    assert max(table.body_bond_errors().values()) < 1e-9
    good = s.model_copy(deep=True)
    table.apply_to_models(good, INS)
    ParameterTable(good, INS)                        # composed: builds
    stale = good.model_copy(deep=True)
    stale.phases[0].rigid_bodies[0].orientation = tuple(Q_TRUE)
    with pytest.raises(ValueError, match="RIGID_BODY_TEMPLATE_DRIFT"):
        ParameterTable(stale, INS)


# ------------------------------------------------------------------ ties
def test_ties_onto_a_body_row_or_from_an_increment_are_refused():
    s = body_structure(Q_TRUE)
    table = ParameterTable(s, INS)
    with pytest.raises(ValueError, match="locked"):
        table.set_tie("phases.0.atoms.0.x",
                      AffineTie(terms=(("phases.0.scale", 1.0),)))
    with pytest.raises(ValueError, match="rotation.*restart"):
        table.set_tie("phases.0.atoms.0.occ",
                      AffineTie(terms=(("phases.0.rigid_bodies.0.rotation.0", 1.0),)))
    with pytest.raises(ValueError, match="restart"):
        table.set_tie("phases.0.rigid_bodies.0.rotation.0",
                      AffineTie(terms=(("phases.0.atoms.0.occ", 1.0),)))
    # one increment may follow another of its own kind
    table.set_tie("phases.0.rigid_bodies.0.rotation.1",
                  AffineTie(terms=(("phases.0.rigid_bodies.0.rotation.0", 1.0),)))


def test_le_bail_force_fixes_the_body():
    from rietx.refine import mode_fixed_column
    table = ParameterTable(body_structure(Q_TRUE), INS)
    table.set_vary(BODY_GLOBS, True)
    reach = table.column_reach()
    assert mode_fixed_column(reach["phases.0.rigid_bodies.0.rotation.0"], "lebail")
    assert not mode_fixed_column(reach["phases.0.rigid_bodies.0.rotation.0"], "rietveld")


def test_hold_on_a_body_dof_blocks_the_plan_stage():
    pattern = synthesize(body_structure(Q_TRUE))
    ref = Refinement(body_structure(_turned(Q_TRUE, 2.0)), INS, history=False)
    ref.hold("phases.0.rigid_bodies.0.rotation.*")
    result = ref.fit(pattern, plan=RefinementPlan(stages=[Stage("body", BODY_GLOBS)]))
    assert "HOLD_BLOCKED_PLAN" in {d.code for d in result.diagnostics}
    assert ref.fitted_structure.phases[0].rigid_bodies[0].orientation == pytest.approx(
        tuple(_turned(Q_TRUE, 2.0)), abs=1e-15)


def test_a_body_round_trips_through_json_and_checkout():
    s = body_structure(Q_TRUE)
    again = Structure.model_validate_json(s.model_dump_json())
    assert again == s
    pattern = synthesize(s)
    ref = Refinement(body_structure(_turned(Q_TRUE, 2.0)), INS)
    ref.fit(pattern, plan=RefinementPlan(stages=[Stage("body", BODY_GLOBS)]))
    fitted = ref.fitted_structure.phases[0].rigid_bodies[0].orientation
    head = ref.history.head
    ref.set_values({"phases.0.scale": 1e-3})
    ref.checkout(head)
    assert ref.structure.phases[0].rigid_bodies[0].orientation == pytest.approx(fitted)
