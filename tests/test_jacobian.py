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
from rietx.optimize.least_squares import (
    _column_extras,
    _make_jacobian,
    _make_residual,
)
from rietx.params.vector import AffineTie, ParameterTable
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


def _check_columns(structure, free_paths, ties=(), *, instrument=None):
    structure, ins, pattern = _state(structure)
    if instrument is not None:
        ins = instrument
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path, tie in ties:
        table.set_tie(path, tie)
    table.refresh_ties()
    for path in free_paths:
        assert table.set_vary([path], True), path
    table.apply_to_models(structure, ins)
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


# ------------------------------------------------- user ties (WP-1070)
def _column(structure, free_paths, path, ties=()):
    """The analytic column for ``path``, with ``ties`` declared on the table.

    Returned rather than compared to finite differences on purpose: the check
    below is *additivity*, which is exact and independent of the branch that
    produced any of the three columns.  An FD reference could not separate a
    gated column from an un-gated one at the step size the fallback itself
    uses — it **is** that finite difference.
    """
    structure, ins, pattern = _state(structure)
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for tied, tie in ties:
        table.set_tie(tied, tie)
    table.refresh_ties()
    for p in free_paths:
        assert table.set_vary([p], True), p
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    theta = table.x0()
    return _make_jacobian(model, table)(theta)[:, table.free_paths.index(path)]


def test_a_tie_makes_one_column_carry_both_dependents():
    """∂y/∂θ with b₁ ← b₀ is ∂y/∂b₀ + ∂y/∂b₁, and the column must be the sum.

    Exact by the chain rule at coefficient 1, and measurable one column at a
    time by freeing each Biso alone — so this says the tie is *carried*, not
    merely that the column looks plausible.  The peak-chain branch handles it
    because it re-derives from ``table.decode``; the assertion is what would
    fail if a branch computed only the path it was named for.
    """
    tie = [("phases.0.atoms.1.biso", AffineTie.identity("phases.0.atoms.0.biso"))]
    b0 = _column(make_rutile(), ["phases.0.atoms.0.biso"], "phases.0.atoms.0.biso")
    b1 = _column(make_rutile(), ["phases.0.atoms.1.biso"], "phases.0.atoms.1.biso")
    tied = _column(make_rutile(), ["phases.0.atoms.0.biso"],
                   "phases.0.atoms.0.biso", ties=tie)
    assert np.linalg.norm(b1) > 0.01 * np.linalg.norm(b0), "degenerate test state"
    # 3.1e-8 measured; the floor is the peak chain's own per-reflection FD, and
    # a dropped dependent would be 20-30 % of the column, not 1e-5 of it
    assert np.allclose(tied, b0 + b1, rtol=0, atol=1e-5 * np.abs(b0 + b1).max())


def test_a_tie_across_phases_keeps_the_far_phases_contribution():
    """The phases re-derived are the ones C touches, not the ones the path names.

    ``_peak_chain_column`` reads its ``affected`` list off the free path's own
    ``phases.N.`` prefix.  A tie into another phase moves that phase's scalars
    through ``decode`` all the same, so a column built from the prefix alone
    comes back missing the far phase entirely — silently, since nothing about
    the near phase is wrong.
    """
    def two_phase():
        both = make_rutile()
        both.phases.append(make_p21c_toy().phases[0])
        both.phases[1].scale.value = 1e-3
        return both

    tie = [("phases.1.atoms.1.biso", AffineTie.identity("phases.0.atoms.0.biso"))]
    near = _column(two_phase(), ["phases.0.atoms.0.biso"], "phases.0.atoms.0.biso")
    far = _column(two_phase(), ["phases.1.atoms.1.biso"], "phases.1.atoms.1.biso")
    tied = _column(two_phase(), ["phases.0.atoms.0.biso"],
                   "phases.0.atoms.0.biso", ties=tie)
    assert np.linalg.norm(far) > 0.01 * np.linalg.norm(near), "degenerate test state"
    assert np.allclose(tied, near + far, rtol=0, atol=1e-5 * np.abs(near + far).max())


def test_a_tie_beyond_a_branchs_reach_falls_back_and_stays_exact():
    """A tie between background coefficients leaves the background branch.

    y is exactly linear in the Chebyshev coefficients, so the tied column has a
    closed form — the *sum* of the two design rows — which the branch that
    writes one design row cannot produce.  The gate sends the column to the
    whole-model FD fallback instead, and that decodes through C like the
    residual does.
    """
    structure, ins, pattern = _state(make_rutile())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_tie("instrument.background.c1",
                  AffineTie.identity("instrument.background.c0"))
    table.refresh_ties()
    assert table.set_vary(["instrument.background.c0"], True)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    column = _make_jacobian(model, table)(table.x0())[:, 0]
    n0 = list(model.bkg_paths).index("instrument.background.c0")
    n1 = list(model.bkg_paths).index("instrument.background.c1")
    both = -(model.bkg_design[n0] + model.bkg_design[n1]) / model.sigma
    assert np.allclose(column[:len(both)], both, rtol=1e-4)
    # and the un-gated branch really would have been wrong here
    one = -model.bkg_design[n0] / model.sigma
    assert not np.allclose(one, both, rtol=1e-2)


def test_a_cross_atom_dof_tie_matches_finite_differences():
    """Two general-position atoms moving together: outside one atom's rows.

    ``_structural_column`` reads the coefficients of *one* atom's x/y/z off C,
    so a tie between two atoms' displacement DOFs reaches past it.  Nothing
    here is protected by symmetry — P2₁/c general sites, monoclinic cell.
    """
    toy = make_p21c_toy()
    toy.phases[0].atoms.append(Atom(
        label="N", species="N", x=Parameter(value=0.61),
        y=Parameter(value=0.18), z=Parameter(value=0.77)))
    _check_columns(toy, ["phases.0.atoms.1.dof.0", "phases.0.scale"],
                   ties=[("phases.0.atoms.2.dof.0",
                          AffineTie.identity("phases.0.atoms.1.dof.0"))])


def test_column_extras_is_empty_without_a_tie_and_names_one_with():
    """The dispatch input itself: empty everywhere an unconstrained model looks.

    That emptiness is what keeps every existing model on exactly the branch it
    took before the gate — the derived ties are the reason the list is *not*
    empty in general, and they stay on their own branches because each declares
    the reach it covers.
    """
    structure, ins, _ = _state(make_rutile())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.atoms.0.biso", "phases.0.cell.a"], True)
    extras = dict(zip(table.free_paths, _column_extras(table), strict=True))
    assert extras["phases.0.atoms.0.biso"] == []
    # a derived tie is not a special case: tetragonal b←a shows up the same way
    assert extras["phases.0.cell.a"] == ["phases.0.cell.b"]

    table.set_tie("phases.0.atoms.1.biso",
                  AffineTie.identity("phases.0.atoms.0.biso"))
    extras = dict(zip(table.free_paths, _column_extras(table), strict=True))
    assert extras["phases.0.atoms.0.biso"] == ["phases.0.atoms.1.biso"]


def test_p21c_general_site_has_all_six_adp_and_three_coord():
    """The toy structure really exercises the general-position path."""
    from rietx.crystallography.wyckoff import site_constraints

    sc = site_constraints("P21/c", (0.23, 0.31, 0.42))
    assert sc.coord_basis.tolist() == np.eye(3, dtype=int).tolist()
    fixed = site_constraints("P21/c", (0.0, 0.0, 0.0))
    assert fixed.coord_basis.shape == (0, 3)
