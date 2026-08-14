"""Analytic coordinate-DOF Jacobian columns vs plain finite differences.

Same tolerance style as ``test_v02_core.test_analytic_jacobian_matches_fd``:
relative column error < 5·10⁻³ and direction cosine > 0.99999.  Covers a
special position whose constraint reduces the free count (rutile O, one DOF
moving x and y together) and a general position (P2₁/c, three DOFs).
"""

from __future__ import annotations

import numpy as np

from rietx import Instrument, PatternData
from rietx.model.forward import compile_model
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from tests.test_coordinates import make_rutile


def make_p21c_toy() -> Structure:
    """One heavy atom on the fixed 2a inversion centre, one C on general 4e."""
    return Structure(phases=[Phase(
        name="toy",
        space_group="P21/c",
        cell=Cell(
            a=Parameter(value=5.2), b=Parameter(value=6.4),
            c=Parameter(value=7.8), alpha=Parameter(value=90.0),
            beta=Parameter(value=105.0), gamma=Parameter(value=90.0),
        ),
        atoms=[
            Atom(label="Fe", species="Fe", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="C", species="C", x=Parameter(value=0.23),
                 y=Parameter(value=0.31), z=Parameter(value=0.42)),
        ],
    )])


def _state(structure, wavelength=1.5406, tt=(10.0, 90.0, 0.02)):
    structure.phases[0].scale.value = 1e-3
    ins = Instrument.debye_scherrer(wavelength=wavelength)
    ins.profile.w.value = 1e-2
    grid = np.arange(*tt)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    return structure, ins, pattern


def _check_columns(structure, free_paths):
    structure, ins, pattern = _state(structure)
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path in free_paths:
        assert table.set_vary([path], True), path
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))

    theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    for c, path in enumerate(table.free_paths):
        h = 1e-6 * max(1.0, abs(theta[c]))
        tp = theta.copy()
        tp[c] += h
        col_fd = (residual(tp) - r0) / h
        col_an = J[:, c]
        scale = np.linalg.norm(col_fd)
        assert scale > 0, f"{path}: dead FD column — test state is degenerate"
        err = np.linalg.norm(col_an - col_fd) / scale
        assert err < 5e-3, f"{path}: analytic vs FD column mismatch ({err:.2e})"
        cos = float(col_an @ col_fd) / (np.linalg.norm(col_an) * scale)
        assert cos > 0.99999, f"{path}: column direction off (cos={cos:.6f})"


def test_special_position_dof_column_matches_fd():
    # one DOF moving x and y together through the [1, 1, 0] row; mixed with
    # other analytic families to catch cross-column indexing mistakes
    _check_columns(make_rutile(), [
        "phases.0.atoms.1.dof.0", "phases.0.cell.a", "phases.0.scale",
        "phases.0.atoms.1.biso", "instrument.zero_shift",
    ])


def test_general_position_dof_columns_match_fd():
    _check_columns(make_p21c_toy(), [
        "phases.0.atoms.1.dof.0", "phases.0.atoms.1.dof.1",
        "phases.0.atoms.1.dof.2", "phases.0.scale",
    ])


def test_constrained_adp_dof_columns_match_fd():
    """Rutile: three ADP patterns per site, one of them the U11 = U22 tie.

    Freeing coordinate and ADP DOFs together also checks that the two
    analytic families do not cross-index each other's constraint rows.
    """
    from tests.test_aniso_adp import make_aniso_rutile

    _check_columns(make_aniso_rutile(), [
        "phases.0.atoms.0.adp.0", "phases.0.atoms.0.adp.1",
        "phases.0.atoms.0.adp.2", "phases.0.atoms.1.adp.0",
        "phases.0.atoms.1.dof.0", "phases.0.scale",
    ])


def test_general_position_adp_columns_match_fd():
    """All six components free on a P2₁/c general site, monoclinic cell —
    nothing here is protected by an orthogonal metric or a symmetric R."""
    from rietx.schemas.structure import AnisoU

    toy = make_p21c_toy()
    toy.phases[0].atoms[1].aniso = AnisoU.from_values(
        [0.012, 0.017, 0.009, 0.0018, -0.0031, 0.0007])
    _check_columns(toy, [f"phases.0.atoms.1.adp.{k}" for k in range(6)]
                   + ["phases.0.atoms.1.dof.0", "phases.0.cell.beta"])


def test_adp_dof_absent_in_lebail_jacobian():
    from tests.test_aniso_adp import make_aniso_rutile

    structure, ins, pattern = _state(make_aniso_rutile())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.atoms.0.adp.0"], True)
    model = compile_model(structure, ins, pattern, mode="lebail",
                          free_paths=set(table.free_paths))
    J = _make_jacobian(model, table)(table.x0())
    assert np.allclose(J[:, 0], 0.0)


def test_free_count_reflects_site_symmetry():
    rutile = make_rutile()
    _, ins, _ = _state(rutile)
    table = ParameterTable(rutile, ins)
    assert table.set_vary(["phases.0.atoms.*.dof.*"], True) == ["phases.0.atoms.1.dof.0"]

    toy = make_p21c_toy()
    table = ParameterTable(toy, Instrument.debye_scherrer(wavelength=1.5406))
    assert table.set_vary(["phases.0.atoms.*.dof.*"], True) == [
        "phases.0.atoms.1.dof.0", "phases.0.atoms.1.dof.1", "phases.0.atoms.1.dof.2"]


def test_dof_absent_in_lebail_jacobian():
    """In Le Bail mode a coordinate DOF has no intensity effect: its FD
    column is zero and the analytic branch must not fire spuriously."""
    structure, ins, pattern = _state(make_rutile())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.atoms.1.dof.0"], True)
    model = compile_model(structure, ins, pattern, mode="lebail",
                          free_paths=set(table.free_paths))
    J = _make_jacobian(model, table)(table.x0())
    assert np.allclose(J[:, 0], 0.0)


def test_p21c_general_site_has_all_six_adp_and_three_coord():
    """The toy structure really exercises the general-position path."""
    from rietx.crystallography.wyckoff import site_constraints

    sc = site_constraints("P21/c", (0.23, 0.31, 0.42))
    assert sc.coord_basis.tolist() == np.eye(3, dtype=int).tolist()
    fixed = site_constraints("P21/c", (0.0, 0.0, 0.0))
    assert fixed.coord_basis.shape == (0, 3)
