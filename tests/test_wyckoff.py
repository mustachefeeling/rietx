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

from pxrdref.crystallography.symmetry import get_spacegroup
from pxrdref.crystallography.wyckoff import (
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
