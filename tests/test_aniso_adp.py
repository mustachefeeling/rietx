"""Anisotropic displacement parameters (WP-0303).

Structures used here on purpose:
* NAC, Na₂Ca₃Al₂F₁₄ (I2₁3, COD 1000236) — the real acceptance structure, whose
  CIF carries published U^ij for six sites spanning three different site
  symmetries (2-fold, 3-fold, general).  Any constraint error shows up as a
  mismatch against numbers someone else published.
* Rutile TiO₂ (P4₂/mnm) — Ti on 2a (4/mmm..), O on 4f (m.mm): both sites carry
  the U11 = U22 tie that a transposed rotation would silently break.
* A hexagonal toy — the case where the isotropic limit is *not* U_ij = Uiso·δ_ij
  (γ* = 60° ⇒ U12 = Uiso/2), which is the cheapest guard against pretending the
  CIF U^ij tensor lives in an orthonormal frame.
"""

from __future__ import annotations

import math
from pathlib import Path

import gemmi
import numpy as np
import pytest

from pxrdref import Instrument
from pxrdref.crystallography import adp
from pxrdref.crystallography.cif import structure_from_cif
from pxrdref.crystallography.lattice import d_spacings
from pxrdref.crystallography.structure_factor import (
    compile_phase_sites,
    structure_factors_squared,
)
from pxrdref.crystallography.symmetry import get_spacegroup
from pxrdref.params.vector import ParameterTable
from pxrdref.schemas.common import Parameter
from pxrdref.schemas.structure import AnisoU, Atom, Cell, Phase, Structure
from tests.test_coordinates import make_rutile

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"


def make_cell(cell6) -> Cell:
    a, b, c, al, be, ga = cell6
    return Cell(
        a=Parameter(value=a, min=0.1), b=Parameter(value=b, min=0.1),
        c=Parameter(value=c, min=0.1), alpha=Parameter(value=al),
        beta=Parameter(value=be), gamma=Parameter(value=ga),
    )


#: a general position in every group used here — so the orbit has many
#: distinct images and the per-image Debye-Waller factor really varies
GENERAL = (0.23, 0.11, 0.31)


def _iso_phase(cell6, space_group: str, uiso: float, xyz=GENERAL) -> Phase:
    return Phase(
        name="toy", space_group=space_group, cell=make_cell(cell6),
        atoms=[Atom(label="Zn", species="Zn",
                    x=Parameter(value=xyz[0]), y=Parameter(value=xyz[1]),
                    z=Parameter(value=xyz[2]),
                    biso=Parameter(value=8.0 * math.pi ** 2 * uiso,
                                   min=0.0, max=1e4, unit="A^2"))],
    )


def _f2(phase: Phase, cell6, *, hkl=None) -> np.ndarray:
    """|F|² over a fixed hkl block, straight through the structure factor."""
    if hkl is None:
        hkl = np.array([[1, 0, 0], [0, 0, 1], [1, 1, 0], [1, 0, 2], [2, 1, 3],
                        [0, 0, 4], [3, 2, 1], [4, 0, 0], [2, 2, 2]])
    sites = compile_phase_sites(phase)
    d = d_spacings(hkl, *cell6)
    xyz = np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])
    occ = np.array([a.occ.value for a in phase.atoms])
    biso = np.array([a.biso.value for a in phase.atoms])
    uaniso = np.array([a.aniso.values() if a.aniso else (0.0,) * 6 for a in phase.atoms])
    return structure_factors_squared(hkl, d, sites, xyz, occ, biso, uaniso,
                                     adp.reciprocal_axis_lengths(*cell6))


# -- schema ------------------------------------------------------------


def test_aniso_block_json_round_trip():
    atom = Atom(
        label="Fe", species="Fe",
        x=Parameter(value=0.1), y=Parameter(value=0.2), z=Parameter(value=0.3),
        aniso=AnisoU.from_values([0.011, 0.012, 0.013, 0.001, -0.002, 0.0],
                                 vary=True),
    )
    # ±inf bounds must survive the JSON round trip as strings, as elsewhere
    atom.aniso.u11.max = math.inf
    back = Atom.model_validate_json(atom.model_dump_json())
    assert back.aniso is not None
    assert back.aniso.values() == atom.aniso.values()
    assert back.aniso.u11.max == math.inf
    assert back.aniso.u12.vary is True


def test_aniso_block_forbids_extra_fields():
    with pytest.raises(ValueError, match="u21|extra"):
        AnisoU.model_validate({"u11": {"value": 0.01}, "u22": {"value": 0.01},
                               "u33": {"value": 0.01}, "u21": {"value": 0.0}})


def test_isotropic_atom_keeps_no_aniso_block():
    atom = Atom(label="B", species="B", x=Parameter(value=0.2),
                y=Parameter(value=0.5), z=Parameter(value=0.5))
    assert atom.aniso is None
    assert "aniso" in atom.model_dump()  # explicit null, not a silent omission


def test_varying_biso_alongside_aniso_is_rejected():
    with pytest.raises(ValueError, match="does not enter the model"):
        Atom(label="Fe", species="Fe", x=Parameter(value=0.0),
             y=Parameter(value=0.0), z=Parameter(value=0.0),
             biso=Parameter(value=0.5, vary=True),
             aniso=AnisoU.from_values([0.01] * 3 + [0.0] * 3))


# -- representations ---------------------------------------------------


def test_isotropic_u6_is_delta_only_for_orthogonal_axes():
    cubic = (4.0, 4.0, 4.0, 90.0, 90.0, 90.0)
    assert adp.isotropic_u6(0.02, cubic) == pytest.approx([0.02] * 3 + [0.0] * 3)

    hexagonal = (3.0, 3.0, 5.0, 90.0, 90.0, 120.0)
    u6 = adp.isotropic_u6(0.02, hexagonal)
    # γ* = 60° ⇒ U12 = Uiso·cos(60°); U13 = U23 = 0 (c* ⊥ a*, b*)
    assert u6 == pytest.approx([0.02, 0.02, 0.02, 0.01, 0.0, 0.0])


def test_u_equivalent_and_principal_values_of_an_isotropic_tensor():
    cell = (3.0, 3.0, 5.0, 90.0, 90.0, 120.0)
    u6 = adp.isotropic_u6(0.017, cell)
    assert adp.u_equivalent(u6, cell) == pytest.approx(0.017, rel=1e-12)
    assert adp.principal_values(u6, cell) == pytest.approx([0.017] * 3, rel=1e-12)


def test_isotropic_limit_reproduces_the_biso_path():
    """U^ij = Uiso·G*/(a*⊗a*) must give exactly the exp(−B k²) intensities.

    Run on a hexagonal cell *and* an orthorhombic one: the orthorhombic case
    is the δ_ij limit the WP names, while the hexagonal case has γ* = 60° and
    a 3-fold axis, so a transposed-rotation error or a forgotten a*_i a*_j
    shows up as a d-dependent bias instead of cancelling.
    """
    for cell6, sg in (((4.1, 5.3, 6.7, 90.0, 90.0, 90.0), "P m m m"),
                      ((3.0, 3.0, 5.0, 90.0, 90.0, 120.0), "P 6/m m m")):
        uiso = 0.0143
        iso = _iso_phase(cell6, sg, uiso)
        ani = _iso_phase(cell6, sg, uiso)
        ani.atoms[0].aniso = AnisoU.from_values(adp.isotropic_u6(uiso, cell6))
        ani.atoms[0].biso.value = 999.0  # must be ignored entirely

        f2_iso = _f2(iso, cell6)
        f2_ani = _f2(ani, cell6)
        assert f2_ani == pytest.approx(f2_iso, rel=1e-12)


def test_orbit_sum_matches_explicit_P1_expansion():
    """The real transpose guard: R·U*·Rᵀ on the images vs R_mᵀh on the parent.

    The isotropic-limit test above cannot catch a transposed rotation — the
    isotropic tensor Uiso·G* is invariant under *both* R·(·)·Rᵀ and Rᵀ·(·)·R,
    because the group preserves the metric.  Writing every orbit image out as
    its own P1 atom carrying the transformed tensor, and evaluating that at h
    directly, is an independent implementation of the same physics; the two
    agree only if both conventions are right.

    P6₃/m, not a monoclinic group: 8 of its 12 rotation matrices are
    non-symmetric, so R and Rᵀ genuinely differ.  (In P2₁/c — and in every
    other group whose operators are diagonal — this test would pass with the
    convention reversed, which is exactly the trap it exists to avoid.)
    """
    cell6 = (5.2, 5.2, 7.8, 90.0, 90.0, 120.0)
    u6 = np.array([0.011, 0.019, 0.008, 0.0021, -0.0035, 0.0009])
    compact = _iso_phase(cell6, "P 63/m", 0.01)
    compact.atoms[0].aniso = AnisoU.from_values(u6)

    sg = get_spacegroup("P 63/m")
    astar = adp.reciprocal_axis_lengths(*cell6)
    ustar = adp.ustar_from_ucif(u6, astar)
    images = []
    for op in sg.operations():
        r = np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN
        t = np.array(op.tran, dtype=np.float64) / gemmi.Op.DEN
        p = r @ np.array(GENERAL) + t
        # the displacement tensor of the image, back in CIF U^ij units
        u_img = adp.voigt_from_tensor(r @ ustar @ r.T / np.outer(astar, astar))
        images.append(Atom(
            label=f"Zn{len(images)}", species="Zn",
            x=Parameter(value=float(p[0])), y=Parameter(value=float(p[1])),
            z=Parameter(value=float(p[2])),
            aniso=AnisoU.from_values(u_img)))
    expanded = Phase(name="p1", space_group="P 1", cell=make_cell(cell6), atoms=images)

    assert len(images) == 12  # P6₃/m general position
    assert _f2(expanded, cell6) == pytest.approx(_f2(compact, cell6), rel=1e-10)


def test_anisotropy_actually_changes_the_pattern():
    """Guard against the equivalence test passing because nothing is wired."""
    cell6 = (3.0, 3.0, 5.0, 90.0, 90.0, 120.0)
    phase = _iso_phase(cell6, "P 6/m m m", 0.0143)
    u6 = adp.isotropic_u6(0.0143, cell6)
    u6[2] *= 3.0  # stretch the ellipsoid along c
    phase.atoms[0].aniso = AnisoU.from_values(u6)
    base = _f2(_iso_phase(cell6, "P 6/m m m", 0.0143), cell6)
    assert not np.allclose(_f2(phase, cell6), base, rtol=1e-6)


# -- constraint wiring -------------------------------------------------


def make_aniso_rutile(u_ti=(0.006, 0.006, 0.005, 0.001, 0.0, 0.0),
                      u_o=(0.009, 0.009, 0.007, -0.003, 0.0, 0.0),
                      *, vary: bool = False) -> Structure:
    structure = make_rutile()
    structure.phases[0].atoms[0].aniso = AnisoU.from_values(u_ti, vary=vary)
    structure.phases[0].atoms[1].aniso = AnisoU.from_values(u_o, vary=vary)
    return structure


def test_adp_dofs_wired_from_site_symmetry():
    """Rutile: both sites are m.mm/m.2m — U11 = U22, U33 free, U12 free,
    U13 = U23 = 0.  Three DOFs, six components, two of them locked at zero."""
    table = ParameterTable(make_aniso_rutile(),
                           Instrument.debye_scherrer(wavelength=1.5406))
    paths = {e.path: e for e in table.entries}
    assert [f"phases.0.atoms.0.adp.{k}" in paths for k in range(4)] == [True] * 3 + [False]
    # U11 and U22 ride the same DOF; U13/U23 are symmetry-zero, hence locked
    assert paths["phases.0.atoms.0.u11"].tie.terms == (("phases.0.atoms.0.adp.0", 1.0),)
    assert paths["phases.0.atoms.0.u22"].tie.terms == (("phases.0.atoms.0.adp.0", 1.0),)
    assert paths["phases.0.atoms.0.u13"].locked
    assert paths["phases.0.atoms.0.u23"].locked
    # biso exists for write-back but can never be freed alongside aniso
    assert paths["phases.0.atoms.0.biso"].locked
    assert not table.set_vary(["phases.0.atoms.*.biso"], True)
    freed = table.set_vary(["phases.0.atoms.*.adp.*"], True)
    assert len(freed) == 6  # three patterns on each of the two sites

    values = table.decode(table.x0())
    assert values["phases.0.atoms.0.u11"] == pytest.approx(0.006)
    assert values["phases.0.atoms.0.u22"] == pytest.approx(0.006)
    assert values["phases.0.atoms.0.u12"] == pytest.approx(0.001)
    assert values["phases.0.atoms.0.u13"] == 0.0


def test_vary_flag_on_any_component_seeds_the_site_dofs():
    table = ParameterTable(make_aniso_rutile(vary=True),
                           Instrument.debye_scherrer(wavelength=1.5406))
    assert "phases.0.atoms.0.adp.0" in table.free_paths
    assert "phases.0.atoms.0.u11" not in table.free_paths  # tied, not free


def test_tensor_incompatible_with_site_symmetry_is_rejected():
    """U11 ≠ U22 on rutile's 4-fold site is not a tolerance question."""
    with pytest.raises(ValueError, match="not compatible with the site symmetry"):
        ParameterTable(make_aniso_rutile(u_ti=(0.006, 0.009, 0.005, 0.0, 0.0, 0.0)),
                       Instrument.debye_scherrer(wavelength=1.5406))


def test_published_nac_tensors_satisfy_the_derived_constraints():
    """The COD 1000236 U^ij pass through the wiring untouched.

    Al, Na and F3 sit on I2₁3's .3. axis, where the basis forces
    U11 = U22 = U33 and U12 = U13 = U23 — which is exactly what Courbion &
    Ferey (1988) published, so any error in ``adp_basis`` or in the tie
    plumbing shows up as a rejected tensor or a changed value.
    """
    structure = structure_from_cif(str(DATA / "cod_1000236.cif"), aniso=True)
    table = ParameterTable(structure, Instrument.debye_scherrer(wavelength=0.4139))
    values = table.decode(table.x0())
    for j, atom in enumerate(structure.phases[0].atoms):
        for name, u in zip(adp.U_NAMES, atom.aniso.values(), strict=True):
            assert values[f"phases.0.atoms.{j}.{name}"] == pytest.approx(u, abs=1e-12)
    # Al1 (.3.): two patterns, not six free components
    al = next(j for j, a in enumerate(structure.phases[0].atoms) if a.label == "Al1")
    assert f"phases.0.atoms.{al}.adp.2" not in {e.path for e in table.entries}


def test_adp_write_back_survives_stage_boundary():
    structure = make_aniso_rutile()
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.atoms.0.adp.*"], True)

    theta = table.x0()
    theta[0] += 0.002  # the U11 = U22 pattern
    table.commit(theta)
    table.apply_to_models(structure, ins)

    ti = structure.phases[0].atoms[0]
    assert ti.aniso.u11.value == pytest.approx(0.008)
    assert ti.aniso.u22.value == pytest.approx(0.008)  # tie held through commit
    assert ti.aniso.u33.value == pytest.approx(0.005)
    # a fresh table re-projects the committed tensor without complaint
    assert ParameterTable(structure, ins).decode(
        ParameterTable(structure, ins).x0())["phases.0.atoms.0.u22"] == pytest.approx(0.008)


def test_positive_definiteness_sign_is_representation_independent():
    cell = (5.2, 6.4, 7.8, 90.0, 105.0, 90.0)  # monoclinic: no orthogonal frame
    good = [0.010, 0.012, 0.008, 0.001, -0.002, 0.0005]
    bad = [0.010, 0.012, 0.008, 0.020, -0.002, 0.0005]  # U12 too large
    assert adp.is_positive_definite(good)
    assert not adp.is_positive_definite(bad)
    # the physical tensor agrees with the cell-free test in both directions
    assert np.min(adp.principal_values(good, cell)) > 0
    assert np.min(adp.principal_values(bad, cell)) < 0
