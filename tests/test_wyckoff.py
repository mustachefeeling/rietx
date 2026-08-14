"""Wyckoff/site-symmetry constraint bases vs published tables.

The expected values are the site-symmetry tables of International Tables A
and the cctbx worked examples (Grosse-Kunstleve & Adams, 2002, J. Appl.
Cryst. 35, 477 — rutile is their §2 example).  Two property tests verify the
algebra independently of any table: every basis vector must be exactly fixed
by every stabilizer operation (integer arithmetic, no tolerance), and the
basis dimensions must equal the character-theory counts
dim = ⟨tr R⟩ (vector rep) and ⟨(tr²R + tr R²)/2⟩ (symmetric square).
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.crystallography.symmetry import get_spacegroup
from rietx.crystallography.wyckoff import (
    adp_basis,
    coordinate_basis,
    site_constraints,
    stabilizer_rotations,
)

# (space group, site, wyckoff, site symmetry, coord basis, adp basis)
# ADP rows in (U11, U22, U33, U12, U13, U23) order.
TABLE = [
    ("Pm-3m", (0.0, 0.0, 0.0), "1a", "m-3m", [], [[1, 1, 1, 0, 0, 0]]),
    ("Pm-3m", (0.5, 0.5, 0.5), "1b", "m-3m", [], [[1, 1, 1, 0, 0, 0]]),
    ("Pm-3m", (0.0, 0.5, 0.5), "3c", "4/mm.m", [],
     [[1, 0, 0, 0, 0, 0], [0, 1, 1, 0, 0, 0]]),
    ("Pm-3m", (0.3, 0.0, 0.0), "6e", "4m.m", [[1, 0, 0]],
     [[1, 0, 0, 0, 0, 0], [0, 1, 1, 0, 0, 0]]),
    ("Pm-3m", (0.3, 0.3, 0.3), "8g", ".3m", [[1, 1, 1]],
     [[1, 1, 1, 0, 0, 0], [0, 0, 0, 1, 1, 1]]),
    ("Fm-3m", (0.0, 0.0, 0.0), "4a", "m-3m", [], [[1, 1, 1, 0, 0, 0]]),
    ("Fm-3m", (0.25, 0.25, 0.25), "8c", "-43m", [], [[1, 1, 1, 0, 0, 0]]),
    ("Fm-3m", (0.24, 0.0, 0.0), "24e", "4m.m", [[1, 0, 0]],
     [[1, 0, 0, 0, 0, 0], [0, 1, 1, 0, 0, 0]]),
    ("Fd-3m", (0.0, 0.0, 0.0), "8a", "-43m", [], [[1, 1, 1, 0, 0, 0]]),
    ("Fd-3m", (0.36, 0.36, 0.36), "32e", ".3m", [[1, 1, 1]],
     [[1, 1, 1, 0, 0, 0], [0, 0, 0, 1, 1, 1]]),
    # rutile — the cctbx paper's worked example: U12 is free on 2a, and the
    # (x,x,0) oxygen keeps U11=U22 with free U12 while U13=U23=0
    ("P42/mnm", (0.0, 0.0, 0.0), "2a", "m.mm", [],
     [[1, 1, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0], [0, 0, 0, 1, 0, 0]]),
    ("P42/mnm", (0.305, 0.305, 0.0), "4f", "m.2m", [[1, 1, 0]],
     [[1, 1, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0], [0, 0, 0, 1, 0, 0]]),
    ("I4/mmm", (0.0, 0.0, 0.0), "2a", "4/mmm", [],
     [[1, 1, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0]]),
    ("I4/mmm", (0.0, 0.0, 0.37), "4e", "4mm", [[0, 0, 1]],
     [[1, 1, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0]]),
    # hexagonal 3-/6-fold sites: the classic U11 = U22 = 2·U12 pattern
    ("P63/mmc", (0.0, 0.0, 0.0), "2a", "-3m.", [],
     [[0, 0, 1, 0, 0, 0], [2, 2, 0, 1, 0, 0]]),
    ("P63/mmc", (1 / 3, 2 / 3, 0.25), "2c", "-6m2", [],
     [[0, 0, 1, 0, 0, 0], [2, 2, 0, 1, 0, 0]]),
    ("P63/mmc", (1 / 3, 2 / 3, 0.06), "4f", "3m.", [[0, 0, 1]],
     [[0, 0, 1, 0, 0, 0], [2, 2, 0, 1, 0, 0]]),
    ("R-3m", (0.0, 0.0, 0.0), "3a", "-3m", [],
     [[0, 0, 1, 0, 0, 0], [2, 2, 0, 1, 0, 0]]),
    ("R-3m", (0.0, 0.0, 0.23), "6c", "3m", [[0, 0, 1]],
     [[0, 0, 1, 0, 0, 0], [2, 2, 0, 1, 0, 0]]),
    # monoclinic (unique axis b): mirror site kills U12, U23 only
    ("C2/m", (0.2, 0.0, 0.7), "4i", "m", [[1, 0, 0], [0, 0, 1]],
     [[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0],
      [0, 0, 0, 0, 1, 0]]),
    ("P21/c", (0.0, 0.0, 0.0), "2a", "-1", [], np.eye(6, dtype=int).tolist()),
    ("P21/c", (0.1, 0.2, 0.3), "4e", "1", np.eye(3, dtype=int).tolist(),
     np.eye(6, dtype=int).tolist()),
]


@pytest.mark.parametrize("sg,xyz,wyckoff,sitesym,coord,adp", TABLE,
                         ids=[f"{t[0]}-{t[2]}" for t in TABLE])
def test_against_published_tables(sg, xyz, wyckoff, sitesym, coord, adp):
    sc = site_constraints(sg, xyz)
    assert sc.wyckoff == wyckoff
    assert sc.site_symmetry == sitesym
    assert sc.multiplicity == int(wyckoff[:-1])
    assert sc.coord_basis.tolist() == coord
    assert sc.adp_basis.tolist() == adp


def _unvoigt(row):
    u11, u22, u33, u12, u13, u23 = row
    return np.array([[u11, u12, u13], [u12, u22, u23], [u13, u23, u33]],
                    dtype=np.int64)


@pytest.mark.parametrize("sg,xyz", [(t[0], t[1]) for t in TABLE],
                         ids=[f"{t[0]}-{t[2]}" for t in TABLE])
def test_bases_exactly_invariant(sg, xyz):
    """Every basis vector is fixed by every stabilizer op — in integers."""
    rots = stabilizer_rotations(get_spacegroup(sg), xyz)
    coord = coordinate_basis(rots)
    adp = adp_basis(rots)
    for r in rots:
        for v in coord:
            assert np.array_equal(r @ v, v)
        for row in adp:
            u = _unvoigt(row)
            assert np.array_equal(r @ u @ r.T, u)


@pytest.mark.parametrize("sg,xyz", [(t[0], t[1]) for t in TABLE],
                         ids=[f"{t[0]}-{t[2]}" for t in TABLE])
def test_dimensions_match_character_theory(sg, xyz):
    """Independent count of the free parameters via group characters."""
    rots = stabilizer_rotations(get_spacegroup(sg), xyz)
    n = len(rots)
    dim_coord = sum(np.trace(r) for r in rots) / n
    dim_adp = sum((np.trace(r) ** 2 + np.trace(r @ r)) / 2 for r in rots) / n
    assert len(coordinate_basis(rots)) == round(dim_coord)
    assert len(adp_basis(rots)) == round(dim_adp)


def test_near_special_position_snaps_within_tol():
    """A site within tol of a special position gets that position's constraints."""
    sc = site_constraints("Pm-3m", (1e-6, 1e-6, 1e-6))
    assert sc.wyckoff == "1a"
    assert sc.coord_basis.shape == (0, 3)


def test_general_position_multiplicity_is_group_order():
    # this site coincides with the module's first generic probe point, which
    # also exercises the fallback-probe path
    sc = site_constraints("Pm-3m", (0.1234, 0.5678, 0.9137))
    assert sc.wyckoff == "48n"
    assert sc.multiplicity == 48
    assert sc.coord_basis.tolist() == np.eye(3, dtype=int).tolist()


# -- WP-1036: the cell constraints, checked against the operators ---------


def _symmetry_compatible_cell(sg) -> tuple[float, ...]:
    """A cell the group's operators allow, derived without any case table.

    G = ⟨Rᵀ·G₀·R⟩ over the point group is invariant by construction, for
    *whatever setting* the operators are in — hexagonal axes, rhombohedral axes,
    a c-unique monoclinic — which is the same device
    ``wyckoff._compatible_lattice`` uses to feed spglib.  G₀ is deliberately
    generic, so every equality surviving the average is one the symmetry
    imposes and not an accident of the probe.
    """
    import gemmi

    g0 = np.array([[1.00, 0.05, 0.02],
                   [0.05, 1.21, 0.03],
                   [0.02, 0.03, 1.44]])
    rots = [np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN for op in sg.operations()]
    g = sum(r.T @ g0 @ r for r in rots) / len(rots)
    a, b, c = np.sqrt(np.diag(g))
    return (a, b, c,
            np.degrees(np.arccos(g[1, 2] / (b * c))),
            np.degrees(np.arccos(g[0, 2] / (a * c))),
            np.degrees(np.arccos(g[0, 1] / (a * b))))


def test_cell_constraints_reproduce_the_operators_for_every_gemmi_setting():
    """``cell_constraints`` must state exactly what the operators impose.

    For all ~550 settings in gemmi's table — every unique-axis choice, every
    origin choice, both R descriptions — a symmetry-compatible cell is derived
    from the operators alone and the tabulation is checked against it **in both
    directions**: everything the constraints claim must hold, and nothing they
    omit may hold.

    The second direction is the one that matters and the one a
    degrees-of-freedom count cannot supply (WP-1036).  Omitting ``c ← a`` for a
    rhombohedral-axes R group leaves the count right and the subspace wrong; it
    is caught here because the derived cell has a = c and the constraints failed
    to say so.
    """
    import gemmi

    from rietx.crystallography.symmetry import cell_constraints

    lengths, angles = ("a", "b", "c"), ("alpha", "beta", "gamma")
    checked = 0
    for sg in gemmi.spacegroup_table():
        cell = dict(zip(lengths + angles, _symmetry_compatible_cell(sg)))
        con = cell_constraints(sg)
        where = f"{sg.xhm()!r} ({sg.crystal_system_str()}, ext={sg.ext!r})"

        # 1. everything the constraints claim, holds
        for dependent, source in con.ties.items():
            assert cell[dependent] == pytest.approx(cell[source], rel=1e-9), (
                f"{where}: claims {dependent}←{source}, operators disagree "
                f"({cell[dependent]} vs {cell[source]})")
        for angle, target in con.fixed_angles.items():
            assert cell[angle] == pytest.approx(target, abs=1e-9), (
                f"{where}: claims {angle}={target}, operators give {cell[angle]}")

        # 2. nothing the constraints omit, holds
        for i, first in enumerate(lengths):
            for second in lengths[i + 1:]:
                if con.ties.get(second) == first or con.ties.get(first) == second:
                    continue
                if first in con.ties and con.ties[first] == con.ties.get(second):
                    continue
                assert cell[first] != pytest.approx(cell[second], rel=1e-7), (
                    f"{where}: operators force {first} = {second}, "
                    f"constraints leave them independent")
        for angle in angles:
            if angle in con.fixed_angles or angle in con.ties:
                continue
            if any(src == angle for src in con.ties.values()):
                continue  # it is the source another angle is tied to
            for target in (90.0, 120.0, 60.0):
                assert cell[angle] != pytest.approx(target, abs=1e-7), (
                    f"{where}: operators force {angle}={target}, "
                    f"constraints leave it free")
        checked += 1

    assert checked > 500, f"only {checked} settings checked"


def test_rhombohedral_and_hexagonal_r_settings_differ_in_the_derived_cell():
    """The two descriptions of an R lattice are genuinely different cells.

    This is why ``ext`` has to be read: the crystal system is ``trigonal`` for
    both, and both have two degrees of freedom.
    """
    hexagonal = _symmetry_compatible_cell(get_spacegroup("R -3 c:H"))
    rhombohedral = _symmetry_compatible_cell(get_spacegroup("R -3 c:R"))
    assert hexagonal[3:] == pytest.approx((90.0, 90.0, 120.0))
    assert hexagonal[0] == pytest.approx(hexagonal[1])
    assert hexagonal[0] != pytest.approx(hexagonal[2])
    # rhombohedral: all three lengths equal, all three angles equal and free
    assert rhombohedral[0] == pytest.approx(rhombohedral[1]) == pytest.approx(rhombohedral[2])
    assert rhombohedral[3] == pytest.approx(rhombohedral[4]) == pytest.approx(rhombohedral[5])
    assert rhombohedral[3] != pytest.approx(90.0)
