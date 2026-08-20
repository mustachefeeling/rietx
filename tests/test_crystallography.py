import gemmi
import numpy as np
import pytest

from rietx.crystallography.lattice import cell_volume, d_spacings, two_theta_deg
from rietx.crystallography.scattering import f0, normalize_species
from rietx.crystallography.structure_factor import (
    compile_phase_sites,
    structure_factors_squared,
)
from rietx.crystallography.symmetry import generate_reflections, get_spacegroup

CUBIC = (4.1566, 4.1566, 4.1566, 90.0, 90.0, 90.0)


def test_cubic_d_spacings_analytic():
    hkl = np.array([[1, 0, 0], [1, 1, 0], [1, 1, 1], [2, 1, 0]])
    d = d_spacings(hkl, *CUBIC)
    a = CUBIC[0]
    expected = a / np.sqrt((hkl ** 2).sum(axis=1))
    np.testing.assert_allclose(d, expected, rtol=1e-12)


def test_bragg_angle():
    # λ = 2 d sinθ: for d = λ, 2θ = 60°
    tt = two_theta_deg(np.array([1.0]), 1.0)
    np.testing.assert_allclose(tt, [60.0], rtol=1e-12)


def test_cell_volume_cubic():
    assert cell_volume(*CUBIC) == pytest.approx(CUBIC[0] ** 3, rel=1e-12)


def test_pm3m_multiplicities():
    refl = generate_reflections("P m -3 m", CUBIC, wavelength=0.4139, two_theta_max=26.0)
    mult = {tuple(sorted(np.abs(h))): m for h, m in zip(refl.hkl, refl.multiplicity)}
    # m-3m Laue class multiplicities (International Tables A)
    assert mult[(0, 0, 1)] == 6
    assert mult[(0, 1, 1)] == 12
    assert mult[(1, 1, 1)] == 8
    assert mult[(0, 1, 2)] == 24
    assert mult[(1, 1, 2)] == 24
    assert mult[(1, 2, 3)] == 48


#: (symbol, cell, 2θ_max) across every crystal system — the orbit action is
#: vectorised over all hkl at once, and the Rᵀ trap in symmetry.py's docstring
#: keeps the reflection *count* right in every system while serving the wrong
#: orbits, so these two tests assert the partition itself rather than a count.
_ORBIT_SETTINGS = [
    ("P m -3 m", CUBIC, 26.0),
    ("I 21 3", (10.25,) * 3 + (90.0,) * 3, 10.0),
    ("R -3 c", (4.7592, 4.7592, 12.9918, 90.0, 90.0, 120.0), 60.0),
    ("P 63/m m c", (3.2094, 3.2094, 5.2108, 90.0, 90.0, 120.0), 60.0),
    ("I 41/a m d", (3.7842, 3.7842, 9.5146, 90.0, 90.0, 90.0), 60.0),
    ("P n m a", (5.4, 7.6, 5.2, 90.0, 90.0, 90.0), 60.0),
    ("P 1 21/c 1", (10.0, 12.0, 15.0, 90.0, 103.0, 90.0), 40.0),
    ("P -1", (8.0, 11.0, 14.0, 88.0, 97.0, 105.0), 30.0),
]


@pytest.mark.parametrize(("symbol", "cell", "tt_max"), _ORBIT_SETTINGS)
def test_orbits_partition_the_reflection_sphere(symbol, cell, tt_max):
    """Every allowed hkl in range belongs to exactly one reported orbit.

    Re-derives the orbits from the operators independently of
    ``generate_reflections``: each representative is expanded under Rᵀ (Friedel
    mates included) and the images are checked to be distinct across orbits and
    to number exactly the reported multiplicity.  A transposed-versus-untransposed
    slip leaves the number of representatives unchanged, so only the images
    themselves catch it.
    """
    refl = generate_reflections(symbol, cell, wavelength=1.5406,
                                two_theta_max=tt_max, two_theta_min=2.0)
    sg = get_spacegroup(symbol)
    # built here from gemmi directly (rotations are stored scaled by Op.DEN)
    # rather than through the module's own helper, so the check does not inherit
    # the transpose it is meant to police
    rot = np.array([np.transpose(np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN)
                    for op in sg.operations()])
    rot = np.rint(rot).astype(np.int64)

    seen: set[tuple[int, int, int]] = set()
    for h, m in zip(refl.hkl, refl.multiplicity):
        images = np.einsum("mij,j->mi", rot, h)
        orbit = {tuple(map(int, im)) for im in images}
        orbit |= {tuple(-np.array(k)) for k in orbit}  # Friedel
        assert len(orbit) == m, f"{symbol} {h}: orbit {len(orbit)} vs reported {m}"
        assert not (orbit & seen), f"{symbol} {h}: orbit overlaps an earlier one"
        seen |= orbit
    # the representatives are themselves distinct
    assert len({tuple(map(int, h)) for h in refl.hkl}) == len(refl.hkl)


def test_orbit_chunking_is_transparent(monkeypatch):
    """The image stack is chunked to stay O(1) in memory the way the per-hkl
    loop was, so the multi-chunk branch must return what one chunk returns."""
    from rietx.crystallography import symmetry as sym

    cell = (10.0, 12.0, 15.0, 90.0, 103.0, 90.0)
    whole = generate_reflections("P 1 21/c 1", cell, wavelength=1.5406,
                                 two_theta_max=40.0, two_theta_min=2.0)
    monkeypatch.setattr(sym, "_ORBIT_CHUNK_ELEMENTS", 120)
    chunked = generate_reflections("P 1 21/c 1", cell, wavelength=1.5406,
                                   two_theta_max=40.0, two_theta_min=2.0)
    np.testing.assert_array_equal(chunked.hkl, whole.hkl)
    np.testing.assert_array_equal(chunked.multiplicity, whole.multiplicity)
    np.testing.assert_array_equal(chunked.d, whole.d)


def test_body_centring_absences():
    refl = generate_reflections("I 21 3", (10.25,) * 3 + (90.0,) * 3,
                                wavelength=0.4139, two_theta_max=8.0)
    parity = refl.hkl.sum(axis=1) % 2
    assert np.all(parity == 0), "I-centred lattice must have h+k+l even only"


def test_f0_at_zero_equals_electron_count():
    # f0(0) = Σa + c ≈ Z for neutral atoms (Waasmaier & Kirfel 1995)
    for species, z in [("La", 57), ("B", 5), ("O", 8), ("Si", 14)]:
        val = f0(species, np.array([0.0]))[0]
        assert val == pytest.approx(z, abs=0.05), species


def test_f0_monotone_decrease():
    k = np.linspace(0.0, 1.2, 50)
    vals = f0("Si", k)
    assert np.all(np.diff(vals) < 0)


def test_species_normalization():
    assert normalize_species("LA") == "La"
    assert normalize_species("La3+") == "La3+"  # tabulated ion
    with pytest.raises(KeyError):
        normalize_species("Xx")


def _reference_f2_full_cell(phase, hkl, d):
    """Dumb reference: expand every atom to the full cell via gemmi ops."""
    sg = get_spacegroup(phase.space_group)
    F = np.zeros(len(hkl), dtype=complex)
    for atom in phase.atoms:
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        images = []
        for op in sg.operations():
            r = np.array(op.rot, float) / gemmi.Op.DEN
            t = np.array(op.tran, float) / gemmi.Op.DEN
            p = (r @ xyz + t) % 1.0
            if not any(np.all(np.minimum(np.abs(p - q), 1 - np.abs(p - q)) < 1e-4) for q in images):
                images.append(p)
        k = 1.0 / (2.0 * d)
        for p in images:
            F += (atom.occ.value * f0(atom.species, k)
                  * np.exp(-atom.biso.value * k * k)
                  * np.exp(2j * np.pi * (hkl @ p)))
    return (F * F.conj()).real


def test_structure_factor_against_reference():
    from tests.test_schemas import make_lab6

    phase = make_lab6().phases[0]
    refl = generate_reflections(phase.space_group, CUBIC, wavelength=0.4139,
                                two_theta_max=15.0)
    sites = compile_phase_sites(phase)
    xyz = np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])
    occ = np.array([a.occ.value for a in phase.atoms])
    biso = np.array([a.biso.value for a in phase.atoms])
    f2 = structure_factors_squared(refl.hkl, refl.d, sites, xyz, occ, biso)
    ref = _reference_f2_full_cell(phase, refl.hkl, refl.d)
    np.testing.assert_allclose(f2, ref, rtol=1e-10)
    assert np.all(f2 > 0)


def test_structure_factor_symmetry_invariance():
    """|F| must be identical for symmetry-equivalent reflections."""
    from tests.test_schemas import make_lab6

    phase = make_lab6().phases[0]
    sites = compile_phase_sites(phase)
    xyz = np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])
    occ = np.array([a.occ.value for a in phase.atoms])
    biso = np.array([a.biso.value for a in phase.atoms])
    trip = np.array([[1, 2, 3], [3, 1, 2], [-1, -2, 3], [2, 1, 3]])
    d = d_spacings(trip, *CUBIC)
    f2 = structure_factors_squared(trip, d, sites, xyz, occ, biso)
    np.testing.assert_allclose(f2, f2[0], rtol=1e-10)
