"""A FullProf ``Jbt = ±1`` phase, read or refused by name (WP-1328).

Every magnetic fixture here is **written by hand from the FullProf manual's
own statement of the format** — the Jbt/Isy/Nvk entries of the phase control
line, LINE 23/24's ``Nsym Cen Laue MagMat`` and ``SYMM``/``MSYM`` pairs, and
LINE 25's four-line magnetic atom (``Atom Typ Mag Vek X Y Z Biso Occ Rx Ry
Rz``, codewords, ``Ix Iy Iz beta11 beta22 beta33 MagPh``, codewords). No
FullProf source was opened and no file from any database was used: the
structures are synthetic (one Fe³⁺ site at a general position), so every
number below is this file's own. The header and profile block come from
``test_projects_fullprof``'s fixture writer, reused rather than restated.

One fixture per stance: read in the magnetic cell (Jbt = 1, and Jbt = −1 on
an orthogonal cell), and each refusal — the Fourier-component forms, a
basis-function phase, a moment matrix that is not an axial action, a phase
with no nuclear counterpart in its cell, and a scale the counterpart does not
share.
"""

import math

import pytest

from rietx.io.projects.fullprof import (
    FullProfPcrError,
    magnetic_reading,
    read_fullprof_pcr,
    to_structure,
)
from tests.test_projects_fullprof import _pcr, _phase

#: A monoclinic cell with β obtuse, and an orthorhombic one, both unequal-edged.
_MONO = "   5.200000   6.900000   8.400000  90.000000 100.000000  90.000000"
_ORTHO = "   5.200000   6.900000   8.400000  90.000000  90.000000  90.000000"
_NO_CODES = "    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000"

#: One Fe and one O at general positions, so Occ = 1 (multiplicity over the
#: general multiplicity) and the moment is unconstrained by site symmetry.
_NUCLEAR_SITES = """\
Fe     FE+3    0.13000  0.27000  0.41000  0.40000   1.00000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00
O      O-2     0.31000  0.07000  0.19000  0.50000   1.00000   0   0   0    1
                  0.00     0.00     0.00     0.00      0.00"""

#: P 1 21/c 1 with the two-fold and the glide primed: MSYM is ε·det(R)·R with
#: ε = −1 on those two, +1 on the identity and the inversion.
_P21C_PRIMED = """\
!Nsym Cen Laue MagMat
   4   1   2   1
!
SYMM x, y, z
MSYM u, v, w, 0.0
SYMM -x, y+1/2, -z+1/2
MSYM u, -v, w, 0.0
SYMM -x, -y, -z
MSYM u, v, w, 0.0
SYMM x, -y+1/2, z+1/2
MSYM u, -v, w, 0.0
!
"""

#: P 21 21 21, every operation unprimed (det R = +1, so MSYM = R).
_P212121 = """\
!Nsym Cen Laue MagMat
   4   1   3   1
!
SYMM x, y, z
MSYM u, v, w, 0.0
SYMM -x+1/2, -y, z+1/2
MSYM -u, -v, w, 0.0
SYMM -x, y+1/2, -z+1/2
MSYM -u, v, -w, 0.0
SYMM x+1/2, -y+1/2, -z
MSYM u, -v, -w, 0.0
!
"""

#: k = (0, 0, 0): the structure stated in its magnetic cell.
_K0 = """\
   0.000000   0.000000   0.000000
       0.00       0.00       0.00"""


def _moment_atom(r=(1.5, -2.0, 2.5), codes=(81.0, 91.0, 101.0),
                 imaginary=(0.0, 0.0, 0.0), magph=0.0, biso="0.40000",
                 xyz="0.13000 0.27000 0.41000", species="MFE3") -> str:
    ix, iy, iz = imaginary
    return (f"Fe     {species}  1  0  {xyz} {biso}  1.00000  "
            f"{r[0]:.5f} {r[1]:.5f} {r[2]:.5f}\n"
            f"                      0.00    0.00    0.00    0.00     0.00  "
            f"{codes[0]:.2f} {codes[1]:.2f} {codes[2]:.2f}\n"
            f"     {ix:.3f}   {iy:.3f}   {iz:.3f}   0.000   0.000   0.000  "
            f"{magph:.5f}\n"
            f"      0.00    0.00    0.00    0.00    0.00    0.00     0.00")


def _nuclear(sg="P 1 21/c 1", cell=_MONO, name="FeO_synth"):
    return _phase(name=name, nat=2, sg=sg, atoms=_NUCLEAR_SITES, cell=cell,
                  cell_codes=_NO_CODES)


def _magnetic(symmetry=_P21C_PRIMED, cell=_MONO, jbt=1, atom=None, nvk=1,
              k=_K0, scale="5.0000", isy=-1):
    block = _phase(name="FeO_mag", nat=1, jbt=jbt, isy=isy, sg="P -1",
                   symmetry=symmetry, atoms=atom or _moment_atom(), cell=cell,
                   cell_codes=_NO_CODES, nvk=nvk, scale=scale)
    return block + ("\n" + k if nvk else "")


def _build(tmp_path, *phases, **kw):
    model = read_fullprof_pcr(_pcr(tmp_path, "mag.pcr", *phases))
    diagnostics: list = []
    return model, to_structure(model, diagnostics=diagnostics, **kw), diagnostics


def _refused(tmp_path, *phases, match):
    model = read_fullprof_pcr(_pcr(tmp_path, "mag.pcr", *phases))
    with pytest.raises(FullProfPcrError, match=match) as err:
        to_structure(model)
    assert "cannot be read" in str(err.value)
    assert "nuclear_only=True" in str(err.value)       # the way out, named
    return str(err.value)


# ---------------------------------------------------------------- read


def test_a_jbt1_phase_in_its_magnetic_cell_is_read_onto_its_nuclear_phase(
        tmp_path):
    """One Structure phase, carrying the file's magnetic group as an operator
    list and the Fe moment in crystal-axis μ_B exactly as written — the
    manual's "components along the crystallographic axis …, in units of Bohr
    magnetons", on "a basis of unit vectors along the crystallographic unit
    cell", which is magCIF's crystal-axis basis."""
    model, structure, diags = _build(tmp_path, _nuclear(), _magnetic())
    (phase,) = structure.phases
    assert phase.name == "FeO_synth"
    assert phase.magnetic_symmetry.operations == [
        "x,y,z,+1", "-x,y+1/2,-z+1/2,-1", "-x,-y,-z,+1", "x,-y+1/2,z+1/2,-1"]
    fe, o = phase.atoms
    assert fe.moment.values() == (1.5, -2.0, 2.5)
    assert fe.moment.ion == "Fe3+" and fe.moment.vary
    assert o.moment is None
    (read,) = [d for d in diags if d.code == "FULLPROF_MAGNETIC_PHASE_READ"]
    assert read.level == "info"
    assert "moments on 1 of 2 sites" in read.message
    assert read.where == ["phases.0.magnetic_symmetry",
                          "phases.0.atoms.0.moment"]
    assert not [d for d in diags if d.code == "FULLPROF_MAGNETIC_PHASE_OMITTED"]


def test_a_jbt_minus1_phase_on_an_orthogonal_cell_converts_the_spherical_form(
        tmp_path):
    """Jbt = −1 states (M, φ, θ): φ from X, θ from Z, degrees. On an
    orthogonal cell the frame is the cell's own axes whichever way the manual
    means it, so the conversion is the plain spherical one."""
    atom = _moment_atom(r=(3.0, 30.0, 60.0))
    _, structure, _ = _build(
        tmp_path, _nuclear(sg="P 21 21 21", cell=_ORTHO),
        _magnetic(symmetry=_P212121, cell=_ORTHO, jbt=-1, atom=atom))
    got = structure.phases[0].atoms[0].moment.values()
    t, p = math.radians(60.0), math.radians(30.0)
    assert got == pytest.approx((3 * math.sin(t) * math.cos(p),
                                 3 * math.sin(t) * math.sin(p),
                                 3 * math.cos(t)), abs=1e-12)


def test_nuclear_only_still_omits_a_readable_magnetic_phase(tmp_path):
    """The caller's declared choice outranks the reading."""
    _, structure, diags = _build(tmp_path, _nuclear(), _magnetic(),
                                 nuclear_only=True)
    assert structure.phases[0].magnetic_symmetry is None
    assert [d.code for d in diags].count("FULLPROF_MAGNETIC_PHASE_OMITTED") == 1


# ------------------------------------------------------------- refused


@pytest.mark.parametrize("atom_kw, match", [
    ({"imaginary": (0.5, 0.0, 0.0)}, r"imaginary component Ix = 0\.5.*Fourier"),
    ({"magph": 0.25}, r"MagPh = 0\.25.*Fourier"),
])
def test_the_fourier_component_form_is_refused_by_name(tmp_path, atom_kw, match):
    """S_k = ½(R_k + i I_k)·exp(−2πi MagPh): an imaginary part or a phase is a
    moment stated as a Fourier amplitude, not one real moment per site."""
    _refused(tmp_path, _nuclear(), _magnetic(atom=_moment_atom(**atom_kw)),
             match=match)


def test_a_propagation_vector_other_than_zero_is_refused_by_name(tmp_path):
    k = """\
   0.500000   0.000000   0.000000
       0.00       0.00       0.00"""
    _refused(tmp_path, _nuclear(), _magnetic(k=k),
             match=r"propagation vector \(0\.5, 0\.0, 0\.0\).*Fourier-component")


def test_an_msym_phase_is_refused_by_name(tmp_path):
    symmetry = _P21C_PRIMED.replace("SYMM -x, -y, -z\nMSYM u, v, w, 0.0",
                                    "SYMM -x, -y, -z\nMSYM u, v, w, 0.5")
    _refused(tmp_path, _nuclear(), _magnetic(symmetry=symmetry),
             match=r"magnetic phase 0\.5")


def test_a_moment_matrix_that_is_not_an_axial_action_is_refused(tmp_path):
    """The manual allows any matrix; only ±det(R)·R is a Shubnikov operation."""
    symmetry = _P21C_PRIMED.replace("SYMM -x, y+1/2, -z+1/2\nMSYM u, -v, w",
                                    "SYMM -x, y+1/2, -z+1/2\nMSYM -u, -v, w")
    _refused(tmp_path, _nuclear(), _magnetic(symmetry=symmetry),
             match=r"not ±det\(R\)·R")


def test_a_basis_function_phase_is_refused_by_name(tmp_path):
    symmetry = """\
! Nsym   Cen  Laue Ireps N_Bas
     1     1      1    -1     1
! Real(0)-Imaginary(1) indicator for Ci
  0
!
SYMM x, y, z
BASR     1     0     0
BASI     0     0     0
!
"""
    _refused(tmp_path, _nuclear(), _magnetic(symmetry=symmetry, isy=-2),
             match=r"Isy = -2 states basis functions")


def test_a_magnetic_phase_with_no_nuclear_phase_in_its_cell_is_refused(tmp_path):
    """A nuclear phase in the chemical cell beside a magnetic one stated in a
    doubled cell: the moments have no site to land on in this Structure."""
    doubled = "  10.400000   6.900000   8.400000  90.000000 100.000000  90.000000"
    _refused(tmp_path, _nuclear(), _magnetic(cell=doubled),
             match=r"0 nuclear phases of this file share its cell")


def test_a_magnetic_scale_the_nuclear_phase_does_not_share_is_refused(tmp_path):
    """Two scales, one built phase: the moments would come out scaled."""
    message = _refused(tmp_path, _nuclear(), _magnetic(scale="20.0000"),
                       match=r"Scale x f\^2 is 20 and 'FeO_synth''s is 5")
    assert "scaled by 2" in message


def test_jbt_minus1_on_an_oblique_cell_is_refused(tmp_path):
    _refused(tmp_path, _nuclear(),
             _magnetic(jbt=-1, atom=_moment_atom(r=(3.0, 30.0, 60.0))),
             match=r"Jbt = -1 .* not\s+orthogonal")


def test_magnetic_reading_returns_the_reason_rather_than_raising(tmp_path):
    """The refusal sentence is data, so a caller can ask before building."""
    model = read_fullprof_pcr(_pcr(tmp_path, "m.pcr", _nuclear(),
                                   _magnetic(scale="20.0000")))
    reason = magnetic_reading(model, model.magnetic_phases[0])
    assert isinstance(reason, str) and "Scale" in reason
