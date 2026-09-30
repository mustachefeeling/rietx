"""Fragments, declared bonds and the body frame (WP-1802): `crystallography/fragments.py`.

The oracles are geometry built here from ideal symmetry (a D6h benzene and a
D5h cyclopentadienyl, regular rings with radial hydrogens), a dihedral worked
by hand, and distances, angles and torsions measured by formulas written here,
not imported from the module under test.  The bond lengths are round
illustrative values; every assertion is about geometry, not about them.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from rietx.crystallography import fragments as fr

EPS = np.finfo(np.float64).eps


def _angle(a, b, c):
    """Angle a–b–c in degrees, by atan2 (well conditioned at 0° and 180°)."""
    u, v = np.asarray(a) - b, np.asarray(c) - b
    return math.degrees(math.atan2(np.linalg.norm(np.cross(u, v)), u @ v))


def _dihedral(a, b, c, d):
    """Torsion a–b–c–d in degrees: positive when, looking from b to c, the
    bond b–a turns clockwise onto c–d."""
    b1, b2, b3 = np.asarray(b) - a, np.asarray(c) - b, np.asarray(d) - c
    y = np.linalg.norm(b2) * (b1 @ np.cross(b2, b3))
    x = np.cross(b1, b2) @ np.cross(b2, b3)
    return math.degrees(math.atan2(y, x))


def _distances(xyz):
    x = np.asarray(xyz)
    return np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2)


def _ideal_ring(n, cc, ch):
    """Ideal Dnh CnHn from geometry alone: a regular n-gon of side ``cc`` in the
    x–y plane, centred at the origin, each H radial at ``ch`` beyond its C."""
    rc = cc / (2.0 * math.sin(math.pi / n))
    phi = 2.0 * math.pi * np.arange(n) / n
    unit = np.stack([np.cos(phi), np.sin(phi), np.zeros(n)], axis=1)
    xyz = np.vstack([rc * unit, (rc + ch) * unit])
    bonds = [(k, (k + 1) % n) for k in range(n)] + [(k, n + k) for k in range(n)]
    return fr.Fragment(("C",) * n + ("H",) * n, xyz, bonds)


def _ring_zmatrix(ring, n):
    """Z-matrix lines for an n-ring + n H, read off ``ring``'s coordinates.

    References: each ring C from its predecessors along the ring, each H from
    its own C and the next two ring atoms.  The internal coordinates are
    measured here, so a round trip through :func:`fragments.from_zmatrix`
    must return the same geometry.
    """
    x = ring.xyz
    refs = [(), (0,), (1, 0)] + [(k - 1, k - 2, k - 3) for k in range(3, n)]
    refs += [(k, (k + 1) % n, (k + 2) % n) for k in range(n)]
    lines = []
    for i, ref in enumerate(refs):
        line = [ring.species[i]]
        if len(ref) >= 1:
            line += [ref[0], float(np.linalg.norm(x[i] - x[ref[0]]))]
        if len(ref) >= 2:
            line += [ref[1], _angle(x[i], x[ref[0]], x[ref[1]])]
        if len(ref) >= 3:
            line += [ref[2], _dihedral(x[i], x[ref[0]], x[ref[1]], x[ref[2]])]
        lines.append(tuple(line))
    return lines


# --- the fragment and its declared bonds -------------------------------------


def test_an_ideal_d6h_benzene_has_its_symmetry_and_three_rotation_dofs():
    """Built from D6h geometry (no printed coordinates): C–C and C–H uniform,
    every ring and H–C–C angle 120°, planar, and mapped onto itself by C6."""
    cc, ch = 1.39, 1.09
    benzene = _ideal_ring(6, cc, ch)
    x = benzene.xyz
    for i, j in benzene.bonds:
        want = cc if j < 6 else ch
        assert np.linalg.norm(x[i] - x[j]) == pytest.approx(want, rel=1e-14)
    for k in range(6):
        assert _angle(x[(k - 1) % 6], x[k], x[(k + 1) % 6]) == pytest.approx(120.0, abs=1e-12)
        assert _angle(x[6 + k], x[k], x[(k + 1) % 6]) == pytest.approx(120.0, abs=1e-12)
    np.testing.assert_array_equal(x[:, 2], 0.0)
    c6 = np.array([[0.5, -math.sqrt(3) / 2, 0], [math.sqrt(3) / 2, 0.5, 0], [0, 0, 1]])
    turned = x @ c6.T
    for k in range(12):   # each image is an atom of the same species
        j = int(np.argmin(np.linalg.norm(x - turned[k], axis=1)))
        assert np.linalg.norm(x[j] - turned[k]) < 1e-14 and benzene.species[j] == \
            benzene.species[k]
    frame = benzene.body_frame()
    np.testing.assert_allclose(frame.origin, 0.0, atol=1e-15)
    assert frame.rotation_dofs == 3
    np.testing.assert_array_equal(frame.rotation_axes, np.eye(3))


def test_bonds_are_declared_and_never_perceived():
    """WP-1319's rule: two atoms at a bonding distance declare nothing."""
    co = fr.Fragment(("C", "O"), [[0, 0, 0], [0, 0, 1.13]])
    assert co.bonds is None
    assert fr.Fragment(("C", "O"), co.xyz, bonds=()).bonds == ()
    assert fr.Fragment(("C", "O"), co.xyz, bonds=[(1, 0)]).bonds == ((0, 1),)
    # a Z-matrix's distance references are construction, not bonds
    lines = [("C",), ("O", 0, 1.13), ("H", 0, 1.1, 1, 120)]
    assert fr.from_zmatrix(lines).bonds is None
    assert fr.from_zmatrix(lines, bonds=[(0, 1), (0, 2)]).bonds == ((0, 1), (0, 2))


def test_a_fragment_is_frozen_and_validated():
    f = fr.Fragment(("C", "O"), [[0, 0, 0], [0, 0, 1.13]], bonds=[(1, 0)])
    assert f.bonds == ((0, 1),)
    with pytest.raises(ValueError):
        f.xyz[0, 0] = 1.0
    with pytest.raises(AttributeError):
        f.species = ("N", "O")
    with pytest.raises(ValueError, match="one row per species"):
        fr.Fragment(("C", "O"), [[0, 0, 0]])
    with pytest.raises(ValueError, match="distinct atoms"):
        fr.Fragment(("C", "O"), [[0, 0, 0], [0, 0, 1]], bonds=[(0, 2)])
    with pytest.raises(ValueError, match="twice"):
        fr.Fragment(("C", "O"), [[0, 0, 0], [0, 0, 1]], bonds=[(0, 1), (1, 0)])
    with pytest.raises(ValueError, match="non-finite"):
        fr.Fragment(("C",), [[0, 0, float("nan")]])


# --- the body frame and the DOF count ----------------------------------------


def test_the_body_frame_is_the_centroid_and_the_template_axes():
    """Fragment-internal: the origin is the centroid wherever the template sits,
    and nothing about a cell enters it."""
    ring = _ideal_ring(5, 1.40, 1.08)
    shift = np.array([3.0, -1.5, 0.25])
    moved = fr.Fragment(ring.species, ring.xyz + shift, ring.bonds)
    frame = moved.body_frame()
    np.testing.assert_allclose(frame.origin, shift, atol=1e-15)
    assert frame.rotation_dofs == 3
    # full rank: the template's own axes, not an eigenbasis of I (which for a
    # general fragment is a rotated frame, and within a degeneracy arbitrary)
    skew = fr.Fragment(("C", "N", "O", "S"), [[0, 0, 0], [1.4, 0.2, -0.1],
                                             [-0.3, 1.1, 0.6], [0.5, -0.7, 1.3]])
    np.testing.assert_array_equal(skew.body_frame().rotation_axes, np.eye(3))
    with pytest.raises(ValueError):
        frame.origin[0] = 0.0
    with pytest.raises(ValueError):
        frame.rotation_axes[0, 0] = 0.0


def test_the_rotation_dof_count_is_the_inertia_rank_with_a_near_linear_tolerance():
    atom = fr.Fragment(("Fe",), [[0.3, 0.1, -0.2]])
    co2 = fr.Fragment(("O", "C", "O"), [[0, 0, -1.16], [0, 0, 0], [0, 0, 1.16]],
                      bonds=[(0, 1), (1, 2)])
    assert fr.rotation_dof_count(atom) == 0
    assert fr.rotation_dof_count(co2) == 2
    # linear: the two moving axes are perpendicular to the molecule's axis
    axes = co2.body_frame().rotation_axes
    np.testing.assert_allclose(axes @ [0.0, 0.0, 1.0], 0.0, atol=1e-15)
    np.testing.assert_allclose(axes @ axes.T, np.eye(2), atol=1e-15)
    # the tolerance: 4-decimal rounding stays linear, a 1° bend does not
    rng = np.random.default_rng(20260930)
    noisy = fr.Fragment(co2.species, co2.xyz + rng.uniform(-5e-5, 5e-5, (3, 3)))
    assert fr.rotation_dof_count(noisy) == 2
    t = math.radians(1.0)
    bent = fr.Fragment(co2.species, [[0, 0, 0], [0, 0, 1.16],
                                     [1.16 * math.sin(t), 0, -1.16 * math.cos(t)]])
    assert fr.rotation_dof_count(bent) == 3
    # two coincident atoms have no rotation either
    assert fr.rotation_dof_count(fr.Fragment(("O", "O"), [[1, 1, 1], [1, 1, 1]])) == 0


# --- Z-matrix ----------------------------------------------------------------


@pytest.mark.parametrize("n, cc, ch", [(5, 1.40, 1.08), (6, 1.39, 1.09)])
def test_an_ideal_ring_round_trips_through_its_z_matrix(n, cc, ch):
    """Cartesian → Z-matrix (measured here) → :func:`from_zmatrix` → the same geometry.

    n = 5 is the D5h cyclopentadienyl WP-1802 names; n = 6 is the D6h benzene.
    Every interatomic distance agrees to 1e-12 Å, so the result is the ideal
    ring up to a rigid motion, and it sits where the convention puts it.
    """
    ring = _ideal_ring(n, cc, ch)
    lines = _ring_zmatrix(ring, n)
    got = fr.from_zmatrix(lines, bonds=ring.bonds)
    assert got.species == ring.species and got.bonds == ring.bonds
    assert np.max(np.abs(_distances(got.xyz) - _distances(ring.xyz))) < 1e-12
    x = got.xyz
    assert np.array_equal(x[0], np.zeros(3))
    assert x[1, 0] == 0.0 and x[1, 1] == 0.0 and x[1, 2] > 0.0
    assert x[2, 1] == 0.0 and x[2, 0] > 0.0
    assert fr.rotation_dof_count(got) == 3


def test_the_third_atom_is_in_the_xz_plane_on_the_positive_side():
    """The plane convention, pinned for a third atom bonded to either earlier atom.

    Bonded to the second atom at 120°, the third atom has z ≠ 0, so the "x–y
    plane" reading of the keyword page has no place for it.
    """
    to_first = fr.from_zmatrix([("O",), ("C", 0, 1.2), ("N", 0, 1.3, 1, 120)])
    to_second = fr.from_zmatrix([("O",), ("C", 0, 1.2), ("N", 1, 1.3, 0, 120)])
    for f in (to_first, to_second):
        assert f.xyz[2, 1] == 0.0 and f.xyz[2, 0] > 0.0
    assert to_second.xyz[2, 2] == pytest.approx(1.2 + 1.3 * 0.5, rel=1e-15)


def test_the_dihedral_sign_on_a_hand_worked_point():
    """D = 0, C on +z, B on +x from C, A at 90° with dihedral A–B–C–D = +90°.

    Worked by hand: the thumb C → B is +x; D − C = (0, 0, −1) rotated
    right-handed by 90° about +x is (0, 1, 0), so A = B + (0, 1, 0) = (1, 1, 1).
    Looking from B to C, B–A turns clockwise onto C–D: a positive torsion.
    """
    f = fr.from_zmatrix([("D",), ("C", 0, 1.0), ("B", 1, 1.0, 0, 90),
                         ("A", 2, 1.0, 1, 90, 0, 90)])
    np.testing.assert_allclose(f.xyz, [[0, 0, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1]],
                               rtol=0, atol=1e-15)
    assert _dihedral(*f.xyz[::-1]) == pytest.approx(90.0, abs=1e-12)


def test_a_collinear_reference_triple_is_refused_naming_it():
    """Three atoms on the z axis cannot define a dihedral for a fourth.

    Bending the triple off the line is accepted, and so is a dummy point off
    the line used as the dihedral reference: the refusal is about the
    geometry, not the atoms.  A on the line B–C (a 180° bond angle) is not
    refused.
    """
    lines = [("C",), ("C", 0, 1.2), ("C", 1, 1.2, 0, 180),
             ("H", 2, 1.0, 1, 109.5, 0, 0)]
    with pytest.raises(ValueError, match=r"line 3 \(H\): reference atoms "
                       r"2 \(C\), 1 \(C\), 0 \(C\) are collinear"):
        fr.from_zmatrix(lines)
    bent = list(lines)
    bent[2] = ("C", 1, 1.2, 0, 170)
    assert len(fr.from_zmatrix(bent)) == 4
    X = fr.DUMMY
    fixed = fr.from_zmatrix([("C",), ("C", 0, 1.2), (X, 1, 1.0, 0, 90),
                             ("C", 1, 1.2, 0, 180, 2, 0),
                             ("H", 3, 1.0, 1, 109.5, 2, 0)],
                            bonds=[(0, 1), (1, 3), (3, 4)])
    assert fixed.species == ("C", "C", "C", "H")
    assert fixed.bonds == ((0, 1), (1, 2), (2, 3))
    np.testing.assert_allclose(fixed.xyz[2], [0.0, 0.0, 2.4], atol=1e-15)
    with pytest.raises(ValueError, match="dummy"):
        fr.from_zmatrix([("C",), ("C", 0, 1.2), (X, 1, 1.0, 0, 90)], bonds=[(1, 2)])


def test_z_matrix_lines_are_checked_before_they_are_placed():
    with pytest.raises(ValueError, match="line 1 .* takes 3"):
        fr.from_zmatrix([("C",), ("C", 0)])
    with pytest.raises(ValueError, match="not an earlier line"):
        fr.from_zmatrix([("C",), ("C", 1, 1.5)])
    with pytest.raises(ValueError, match="more than once"):
        fr.from_zmatrix([("C",), ("C", 0, 1.5), ("C", 1, 1.5, 1, 90)])
    with pytest.raises(ValueError, match="outside"):
        fr.from_zmatrix([("C",), ("C", 0, 1.5), ("C", 1, 1.5, 0, 190)])
    with pytest.raises(ValueError, match="integer line indices"):
        fr.from_zmatrix([("C",), ("C", 0.5, 1.5)])
    with pytest.raises(ValueError, match="not positive"):
        fr.from_zmatrix([("C",), ("C", 0, 0.0)])
    with pytest.raises(ValueError, match="not in the Z-matrix"):
        fr.from_zmatrix([("C",), ("C", 0, 1.5)], bonds=[(0, 2)])
