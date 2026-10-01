"""A magnetic group in a sheared cell: the crystal-axis action is refused, not guessed (#614).

On crystal-axis moment components an operation acts by D·R·D⁻¹ with
D = diag(a, b, c), which is the integer R only when every pair of axes R mixes
has equal lengths.  A ``MagneticGroup`` carries no cell, so where no cell of
its setting can make those lengths equal — a sheared cell such as (a, b, a+c),
which ``transformed`` produces — its crystal-axis methods now refuse by name
instead of answering with R.  Settings where the lengths *can* be equal (a
monoclinic group on its hexagonal parent's axes, as MAGNDATA states many) are
still served, and served right.

The oracle is independent of the integer algebra: the axial action of each
stabiliser operation on the moment as a Cartesian vector,
ε·det(R)·(M·R·M⁻¹) with M the cell's column matrix, and the moment converted to
crystal-axis components by the cell's own lengths.
"""

import numpy as np
import pytest

from rietx.crystallography.magnetic.operators import (
    N_MAGNETIC_SPACE_GROUPS,
    allowed_moment_basis,
    magnetic_group,
)

#: transformed() takes the transform *from* the BNS setting, so the cell
#: (a, b, a+c) is reached by handing it the inverse basis change.
SHEAR = "a,b,-a+c;0,0,0"
Q = np.array([[1, 0, 1], [0, 1, 0], [0, 0, 1]], dtype=float)   # columns: new axes in old


def _columns(a, b, c, alpha, beta, gamma):
    """Cell basis vectors as Cartesian columns, a along x."""
    al, be, ga = np.radians([alpha, beta, gamma])
    cx = c * np.cos(be)
    cy = c * (np.cos(al) - np.cos(be) * np.cos(ga)) / np.sin(ga)
    return np.array([[a, 0, 0], [b * np.cos(ga), b * np.sin(ga), 0],
                     [cx, cy, np.sqrt(c ** 2 - cx ** 2 - cy ** 2)]]).T


def _cartesian_allowed(stabiliser, m_cols) -> np.ndarray:
    """Rows: the allowed moments in crystal-axis components, derived in Cartesian."""
    lengths = np.linalg.norm(m_cols, axis=0)
    blocks = [op.time_reversal * op.determinant
              * (m_cols @ op.matrix.astype(float) @ np.linalg.inv(m_cols)) - np.eye(3)
              for op in stabiliser]
    _, s, vt = np.linalg.svd(np.vstack(blocks))
    cartesian = vt[int(np.sum(s > 1e-9)):]
    return np.array([lengths * np.linalg.solve(m_cols, v) for v in cartesian]).reshape(-1, 3)


def _same_span(u, v) -> bool:
    u, v = np.atleast_2d(u).astype(float), np.atleast_2d(v).astype(float)
    r = np.linalg.matrix_rank
    return r(u) == r(v) == r(np.vstack([u, v]))


def _sheared(bns, cell):
    group = magnetic_group(bns).transformed(SHEAR)
    old = _columns(*cell)
    return group, old @ Q


@pytest.mark.parametrize("bns, cell, site", [
    ("136.499", (4.87, 4.87, 3.31, 90, 90, 90), (0.0, 0.0, 0.0)),        # MnF2, the issue's case
    ("62.448", (5.0, 6.0, 7.0, 90, 90, 90), (0.0, 0.0, 0.5)),            # Pn'ma'
])
def test_a_sheared_setting_is_refused_by_name(bns, cell, site):
    group, _ = _sheared(bns, cell)
    mixing = group.axis_mixing()
    assert mixing is not None
    op, i, j = mixing
    with pytest.raises(ValueError, match=r"mixes the a and c axes.*no cell of this setting") as err:
        group.allowed_moment_basis(site)
    assert op.xyz() in str(err.value)
    with pytest.raises(ValueError, match="site_orbit with a moment"):
        group.site_orbit(site, (1.0, 0.0, 0.0))
    positions, moments = group.site_orbit(site)              # positions are cell-free
    assert moments is None and len(positions) > 0


@pytest.mark.parametrize("bns, cell, site", [
    ("136.499", (4.87, 4.87, 3.31, 90, 90, 90), (0.0, 0.0, 0.0)),
    ("62.448", (5.0, 6.0, 7.0, 90, 90, 90), (0.0, 0.0, 0.5)),
])
def test_the_fractional_route_the_refusal_names_gives_the_right_moments(bns, cell, site):
    """The message's advice, checked: fractional rows, converted with the cell, are right."""
    group, cols = _sheared(bns, cell)
    site_new = np.linalg.solve(Q, site) % 1.0
    stabiliser = group.site_stabilizer(site_new)
    fractional = allowed_moment_basis(stabiliser)
    lengths = np.linalg.norm(cols, axis=0)
    crystal_axis = fractional * lengths                       # m_ca = D · m_frac
    assert _same_span(crystal_axis, _cartesian_allowed(stabiliser, cols))


@pytest.mark.parametrize("bns, transform, cell, site", [
    # U3Ru4Al12 on its hexagonal parent's axes: the setting mixes a and b, and a = b there
    ("63.461", "b,-2a-b,c;0,0,0", (6.0, 6.0, 9.6, 90, 90, 120), (0.60980, 0.80490, 0.25)),
    # a monoclinic unique-axis change mixes nothing
    ("14.79", "c,a,b;0,0,0", (5.0, 6.0, 7.0, 104.0, 90, 90), (0.0, 0.0, 0.0)),
])
def test_a_setting_whose_mixed_axes_can_be_equal_is_served_and_right(bns, transform, cell, site):
    group = magnetic_group(bns).transformed(transform)
    assert group.axis_mixing() is None
    cols = _columns(*cell)
    got = group.allowed_moment_basis(site)
    want = _cartesian_allowed(group.site_stabilizer(site), cols)
    assert _same_span(got, want) if len(want) else len(got) == 0


def test_every_tabulated_setting_is_served():
    """All 1651 of spglib's BNS-setting groups: none mixes axes it cannot make equal."""
    refused = [uni for uni in range(1, N_MAGNETIC_SPACE_GROUPS + 1)
               if magnetic_group(uni).axis_mixing() is not None]
    assert refused == []
