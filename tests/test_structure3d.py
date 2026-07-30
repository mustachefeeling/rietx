"""WP-1015 — the structure viewer's geometry payload.

Everything asserted here is crystallography that the browser is deliberately not
allowed to do: the symmetry orbit, the rotation each image carries, the
displacement ellipsoid in the representation whose eigenvalues are physical, and
the cell frame.  The client's whole job is ``pos + k·T·v`` over a unit sphere,
so a defect in this module is a picture that is *confidently wrong* — the same
failure mode the FitReport's gates exist for, one dimension up.

Two of these tests exist because a viewer's plausible-looking output hides them:
an image drawn with its parent's tensor looks fine on a cubic cell and is wrong
on every other one, and ``√(negative eigenvalue)`` is a NaN that takes a whole
mesh with it rather than an atom that looks odd.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from pxrdref.crystallography.adp import principal_values, u_cartesian
from pxrdref.crystallography.cif import structure_from_cif
from pxrdref.crystallography.symmetry import expand_orbit, expand_positions, get_spacegroup
from pxrdref.gui import structure3d as s3
from pxrdref.schemas.structure import AnisoU, Atom, Cell, Phase, Structure

DATA = Path(__file__).parent / "data"


def _p(value: float) -> dict:
    return {"value": value}


@pytest.fixture(scope="module")
def lab6():
    """Cubic, Pm-3m, one atom on the corner and one on a face-diagonal axis."""
    return structure_from_cif(str(DATA / "cod_1000055.cif"))


@pytest.fixture(scope="module")
def nac():
    """Cubic I2₁3 **with** the file's anisotropic tensors — six sites, six shapes."""
    return structure_from_cif(str(DATA / "cod_1000236.cif"), aniso=True)


def monoclinic(**atom_kw) -> Structure:
    """P2₁/c, β = 110° — the cheapest cell on which a wrong metric shows.

    Built rather than read: nothing here needs a real refinement, and the
    assertions are about a general position (multiplicity 4) against an
    inversion centre (multiplicity 2) in a cell whose axes are not orthogonal.
    """
    cell = Cell(a=_p(5.0), b=_p(9.0), c=_p(7.0),
                alpha=_p(90.0), beta=_p(110.0), gamma=_p(90.0))
    atoms = [Atom(label="C1", species="C", x=_p(0.12), y=_p(0.23), z=_p(0.34),
                  **atom_kw),
             Atom(label="O1", species="O", x=_p(0.0), y=_p(0.0), z=_p(0.0))]
    return Structure(phases=[Phase(name="mono", space_group="P 1 21/c 1",
                                   cell=cell, atoms=atoms)])


# ----------------------------------------------------------------------
# the orbit and the frame
# ----------------------------------------------------------------------
def test_a_cubic_phase_expands_to_its_multiplicities(lab6):
    payload = s3.build(lab6)
    by_label = {site["label"]: site for site in payload["sites"]}
    assert by_label["La"]["multiplicity"] == 1      # 1a, the cell corner
    assert by_label["B"]["multiplicity"] == 6       # 6f, on the fourfold axes
    assert all(site["special"] for site in payload["sites"])

    # the *drawn* atoms are the orbit plus boundary duplicates, and the two are
    # distinguishable: a count that mixed them would report 8 La in a cell with
    # one, which is exactly the "8 corners" picture told as a structure
    real = [a for a in payload["atoms"] if not a["boundary"]]
    assert len(real) == 7
    assert sum(1 for a in real if a["site"] == 0) == by_label["La"]["multiplicity"]
    # …and with no bonds to complete, the only images are the seven copies that
    # put the corner atom at all eight corners
    plain = s3.build(lab6, bond_tolerance=0.5)
    assert not plain["bonds"]
    assert sum(a["boundary"] for a in plain["atoms"]) == 7


def test_a_monoclinic_phase_expands_and_frames_the_same_way():
    payload = s3.build(monoclinic())
    multiplicity = {site["label"]: site["multiplicity"] for site in payload["sites"]}
    assert multiplicity == {"C1": 4, "O1": 2}       # 4e general, 2a inversion
    assert payload["sites"][0]["special"] is False
    assert payload["sites"][1]["special"] is True

    assert payload["volume"] == pytest.approx(5.0 * 9.0 * 7.0
                                              * math.sin(math.radians(110.0)))
    lattice = np.array(payload["lattice"])
    # the c axis leans: a payload built on a diagonal metric would not
    assert lattice[2][0] == pytest.approx(7.0 * math.cos(math.radians(110.0)))


@pytest.mark.parametrize("structure", [monoclinic(), None])
def test_the_cell_frame_is_twelve_edges_of_the_right_lengths(structure, lab6):
    payload = s3.build(structure if structure is not None else lab6)
    corners = np.array(payload["corners"])
    edges = np.array(payload["edges"])
    assert corners.shape == (8, 3)
    assert edges.shape == (12, 2)
    lengths = np.linalg.norm(corners[edges[:, 0]] - corners[edges[:, 1]], axis=1)
    a, b, c = payload["cell"][:3]
    # four parallel copies of each axis, which is what makes the box a box
    assert sorted(np.round(lengths, 9)) == pytest.approx(
        sorted([a] * 4 + [b] * 4 + [c] * 4))


def test_the_orbit_carries_the_operation_that_produced_each_image():
    """``expand_orbit`` is ``expand_positions`` plus the rotation, one authority."""
    sg = get_spacegroup("P 1 21/c 1")
    xyz = np.array([0.12, 0.23, 0.34])
    orbit = expand_orbit(sg, xyz)
    assert [p.tolist() for p, _ in orbit] == [p.tolist()
                                              for p in expand_positions(sg, xyz)]
    for position, rot in orbit:
        assert np.allclose(np.abs(np.linalg.det(rot)), 1.0)


# ----------------------------------------------------------------------
# the ellipsoids
# ----------------------------------------------------------------------
def test_an_isotropic_site_is_a_sphere_of_the_equivalent_radius():
    """U_cart = Uiso·I exactly — the closed form the module takes, checked
    against the general path it deliberately does not take."""
    structure = monoclinic()
    biso = structure.phases[0].atoms[0].biso.value
    uiso = biso / (8.0 * math.pi ** 2)
    payload = s3.build(structure)
    drawn = next(a for a in payload["atoms"] if a["site"] == 0)
    assert drawn["rms"] == pytest.approx([math.sqrt(uiso)] * 3)
    assert np.allclose(drawn["ellipsoid"], math.sqrt(uiso) * np.eye(3))

    # …and the general path, through the metric, lands on the same sphere
    from pxrdref.crystallography.adp import isotropic_u6

    cell = structure.phases[0].cell.lengths_angles()
    assert np.allclose(u_cartesian(isotropic_u6(uiso, cell), cell), uiso * np.eye(3))


def test_an_anisotropic_sites_axes_are_the_principal_values(nac):
    """The semi-axes the payload draws are √(eigenvalues of U_cart), for every
    site, and ``T·Tᵀ`` reconstructs the tensor the eigen-decomposition came from."""
    payload = s3.build(nac)
    phase = nac.phases[0]
    cell = phase.cell.lengths_angles()
    checked = 0
    for site in payload["sites"]:
        atom = phase.atoms[site["index"]]
        assert site["aniso"] is True
        want = np.sqrt(np.clip(principal_values(atom.aniso.values(), cell), 0.0, None))
        first = next(a for a in payload["atoms"] if a["site"] == site["index"])
        assert first["rms"] == pytest.approx(want.tolist())
        transform = np.array(first["ellipsoid"])
        assert np.allclose(transform @ transform.T,
                           u_cartesian(atom.aniso.values(), cell))
        checked += 1
    assert checked == 6


def test_every_symmetry_image_rotates_its_tensor_and_keeps_its_size(nac):
    """The invariant that separates a rotated tensor from a copied one.

    A rotation preserves eigenvalues, so every image of a site has the *same*
    semi-axis lengths — and the orientations must nonetheless differ, or the
    images were drawn with the parent's tensor.  That defect is invisible on a
    cubic-site sphere and wrong on every anisotropic one.
    """
    payload = s3.build(nac)
    seen_rotation = False
    for site in payload["sites"]:
        images = [a for a in payload["atoms"]
                  if a["site"] == site["index"] and not a["boundary"]]
        assert len(images) == site["multiplicity"]
        rms = np.array([a["rms"] for a in images])
        assert np.allclose(rms, rms[0])
        transforms = np.array([a["ellipsoid"] for a in images])
        if not np.allclose(transforms, transforms[0]):
            seen_rotation = True
        for transform in transforms:
            covariance = transform @ transform.T
            assert np.allclose(covariance, covariance.T)
    assert seen_rotation, "no image was rotated; the tensors were copied"


def test_a_non_positive_definite_tensor_is_flagged_and_never_nan():
    """The ``ADP_NOT_POSITIVE_DEFINITE`` case, as geometry.

    A negative eigenvalue is not a large number, it is an impossible ellipsoid,
    and ``√(negative)`` is a NaN that loses the whole mesh rather than one atom.
    The semi-axis is drawn at **zero** instead — visibly flat, and the payload
    says so rather than leaving the shape to be interpreted.
    """
    bad = AnisoU.from_values([0.02, 0.02, -0.01, 0.0, 0.0, 0.0])
    structure = monoclinic(aniso=bad)
    payload = s3.build(structure)
    site = payload["sites"][0]
    assert site["npd"] is True
    assert "not positive definite" in payload["note"]

    for atom in payload["atoms"]:
        assert np.isfinite(atom["ellipsoid"]).all()
        assert np.isfinite(atom["rms"]).all()
    flagged = [a for a in payload["atoms"] if a["site"] == 0]
    assert all(a["npd"] for a in flagged)
    assert all(min(a["rms"]) == 0.0 for a in flagged)   # collapsed, not imaginary

    # the healthy site in the same structure is untouched
    assert payload["sites"][1]["npd"] is False


def test_the_probability_levels_are_the_ortep_numbers():
    assert s3.probability_scale(0.50) == pytest.approx(1.5382, abs=5e-5)
    assert s3.probability_scale(0.90) == pytest.approx(2.5003, abs=5e-5)
    levels = s3.build(monoclinic())["probability_levels"]
    assert set(levels) == {f"{p:g}" for p in s3.PROBABILITY_LEVELS}
    assert levels["0.5"] == pytest.approx(s3.probability_scale(0.5))
    with pytest.raises(ValueError):
        s3.probability_scale(1.0)


# ----------------------------------------------------------------------
# bonds
# ----------------------------------------------------------------------
def test_a_bond_that_leaves_the_cell_is_drawn_leaving_it(lab6):
    """Segments over the 27 nearest translations, not pairs inside the box.

    The B₆ octahedra of LaB6 are joined along the axes by B–B contacts that
    cross the cell faces; a viewer that only bonded atoms drawn inside would
    show six isolated octahedra and no framework.
    """
    payload = s3.build(lab6, bond_tolerance=1.05)
    assert payload["bonds"], "no B-B contact was found at all"
    # …and they are the real ones: B-B in LaB6 is 1.68 Å between octahedra and
    # 1.75 Å within one, and nothing else is that close
    assert {round(b["d"], 3) for b in payload["bonds"]} == {1.681, 1.752}
    corners = np.array(payload["corners"])
    lo, hi = corners.min(axis=0) - 1e-9, corners.max(axis=0) + 1e-9
    outside = [b for b in payload["bonds"]
               if np.any(np.array(b["b"]) < lo) or np.any(np.array(b["b"]) > hi)]
    assert outside, "every bond stayed inside the box; the translations did nothing"


def test_the_bond_threshold_is_a_control_and_the_payload_says_which(lab6):
    """A radius-sum slack is a drawing threshold, so it is reported, not implied.

    At 1.15 the La–B contact at 3.058 Å is inside 1.15·(2.07 + 0.84) and every
    lanthanum shows its 24-fold coordination; at 1.05 it is outside and only the
    boron framework survives.  Neither is wrong — which is the argument for the
    knob, and for echoing back the value the picture was drawn at.
    """
    loose = s3.build(lab6, bond_tolerance=1.15)
    tight = s3.build(lab6, bond_tolerance=1.05)
    assert loose["bond_tolerance"] == 1.15 and tight["bond_tolerance"] == 1.05
    assert len(loose["bonds"]) > len(tight["bonds"])
    assert 3.058 == pytest.approx(max(b["d"] for b in loose["bonds"]), abs=1e-3)
    assert 1.752 == pytest.approx(max(b["d"] for b in tight["bonds"]), abs=1e-3)


def test_a_metal_metal_contact_is_a_lattice_distance_unless_the_phase_is_an_alloy(lab6):
    """The rule that keeps a large cation from bonding to its own cell edges.

    gemmi's covalent radius for lanthanum is 2.07 Å against a = 4.158 Å, so a
    plain radius-sum rule draws all twelve cell edges as La–La sticks and the
    boron framework vanishes into a cage.  Suppressed because LaB6 contains a
    non-metal; in a phase that does not, the metal–metal contact is the only
    bond there is and the suppression lifts by itself.
    """
    payload = s3.build(lab6, bond_tolerance=1.3)
    assert payload["bond_metals"] is False
    a = payload["cell"][0]
    assert all(b["d"] < a for b in payload["bonds"])   # no bond is a cell edge

    assert s3.bonds_between_metals(["Fe"]) is True     # bcc iron: bond them
    assert s3.bonds_between_metals(["Ni", "Al"]) is True
    assert s3.bonds_between_metals(["La", "B"]) is False
    assert s3.bonds_between_metals(["Na", "Ca", "Al", "F"]) is False


def test_an_atom_is_never_bonded_to_its_own_boundary_duplicate(lab6):
    """The corner atom is drawn eight times; a zero-length stick between two of
    those copies would be a bond to itself."""
    payload = s3.build(lab6, bond_tolerance=1.15)
    assert all(b["d"] >= s3.BOND_MIN for b in payload["bonds"])


# ----------------------------------------------------------------------
# species, colours, radii
# ----------------------------------------------------------------------
@pytest.mark.parametrize(("species", "element"), [
    ("La", "La"), ("La3+", "La"), ("O2-", "O"), ("o", "O"), ("FE", "Fe"),
    ("D", "D"), ("Xx", "X"), ("", "X"),
])
def test_a_species_resolves_to_its_element(species, element):
    """Charge is a scattering detail; radius and colour are the element's.

    gemmi's own ``Element("O2-")`` answers ``X``, which is why the charge comes
    off here first — an oxygen drawn in the unknown-element grey is a viewer
    quietly disagreeing with the parameter table about what the atom is.
    """
    assert s3.element_symbol(species) == element


def test_colours_are_cpk_where_the_convention_names_one_and_derived_elsewhere():
    assert s3.element_color("O") == s3._CPK["O"]
    assert s3.element_color("C") == s3._CPK["C"]
    # nothing names lanthanum, so it is derived — stable, and not the fallback grey
    derived = s3.element_color("La")
    assert derived == s3.element_color("La")
    assert derived.startswith("#") and len(derived) == 7
    assert derived != s3.element_color("Ce")
    assert s3.element_color("X") == "#909090"


def test_the_payload_carries_the_paths_the_parameter_table_owns(lab6):
    """A click on an atom must reach the row that already exists for it."""
    payload = s3.build(lab6, phase=0)
    assert [site["path"] for site in payload["sites"]] == [
        "phases.0.atoms.0", "phases.0.atoms.1"]
    assert payload["phases"] == [lab6.phases[0].name]


def test_the_ball_radius_is_quoted_and_leaves_room_for_a_stick(lab6):
    """The drawing constants are the payload's, not the client's own opinion.

    ``ball_fraction`` is echoed rather than assumed because the caption under the
    picture states it, and a client that hard-coded it would eventually state a
    number the balls were not drawn at.  Bounded on both sides: balls of a
    *bonded* pair cannot merge (their contact is at 0.4·(r_i+r_j), well inside
    the 1.15 cutoff), and even hydrogen keeps a ball wider than the 0.08 Å stick
    the client draws — or the smallest atom there is would be a lump on a rod.
    """
    payload = s3.build(lab6, phase=0)
    assert payload["ball_fraction"] == s3.BALL_FRACTION
    assert s3.BALL_FRACTION < payload["bond_tolerance"]
    assert s3.BALL_FRACTION * s3.element_radius("H") > 0.08


def test_a_phase_that_is_not_there_is_an_index_error(lab6):
    with pytest.raises(IndexError):
        s3.build(lab6, phase=3)


def test_a_cell_larger_than_the_viewer_draws_says_so(nac):
    payload = s3.build(nac, max_atoms=20)
    assert len(payload["atoms"]) == 20
    assert "trimmed to 20" in payload["note"]


def test_every_bond_ends_on_an_atom_that_is_drawn(lab6):
    """Found by looking at the picture, not at the payload.

    A bond to a translated image is *correct* and reads as broken — the eye sees
    a stick going into empty space — so each out-of-cell endpoint gets its atom
    drawn.  Exactly one level: completing those atoms' bonds in turn would be
    the packing diagram this WP declines to build.
    """
    payload = s3.build(lab6, bond_tolerance=1.05)
    drawn = {tuple(round(v, 6) for v in atom["pos"]) for atom in payload["atoms"]}
    for bond in payload["bonds"]:
        assert tuple(round(v, 6) for v in bond["a"]) in drawn
        assert tuple(round(v, 6) for v in bond["b"]) in drawn

    # they are images, so they do not enter the multiplicity count…
    real = [a for a in payload["atoms"] if not a["boundary"]]
    assert len(real) == sum(s["multiplicity"] for s in payload["sites"])
    # …and each carries its source's tensor unchanged, a translation being a
    # translation, with the fractional coordinate that says which image it is
    outside = [a for a in payload["atoms"] if a["boundary"] and min(a["frac"]) < 0]
    assert outside
    for atom in outside:
        assert all(math.isfinite(v) for v in atom["frac"])
        source = next(a for a in real if a["site"] == atom["site"])
        assert atom["rms"] == source["rms"]

    # the cap counts them: a cell that fills up says so rather than truncating
    small = s3.build(lab6, bond_tolerance=1.15, max_atoms=20)
    assert len(small["atoms"]) == 20
    assert "end in mid-air" in small["note"]
