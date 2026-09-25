"""magCIF in and out, and the three foreign-reader refusals (WP-1328).

**No file here is vendored.** Every fixture is *typed*, and the two kinds of
number in it are cited differently, which is the rule M-5 set and this file
keeps:

* an **operator list** is a mathematical fact about a group — the same fact
  Litvin's tables print and spglib's database holds — so it is typed and
  checked by being identified back to its published BNS number
  (:func:`~rietx.crystallography.magnetic.operators.identify`), never taken on
  trust from a record;
* a **moment** is a measurement, and it is cited to the **original paper**.
  MAGNDATA is named only as the record each transcription was checked against;
  it is never cited as the source of a number, and per the standing
  citation-vs-provenance rule none of the original papers was read here — a
  wrong transcription would have to land inside the derived allowed span by
  accident, which for the constrained sites below is a real constraint.

The licence position is M-5's, re-checked and unchanged: MAGNDATA and the
Bilbao server carry no terms of use, licence or redistribution statement, so
redistribution is not clearly permitted and no entry is shipped. Entries were
read to verify these fixtures (#0.6, #0.7, #0.75, #0.642, #1.0.1, #1.10, #2.1).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.crystallography import magcif
from rietx.crystallography.cif import structure_from_cif, structure_to_cif
from rietx.crystallography.magnetic.operators import (
    MagneticGroup,
    identify,
    in_span,
    moment_from_cartesian,
    moment_magnitude,
    moment_to_cartesian,
)
from rietx.io.projects import coverage
from rietx.io.projects.topas import (
    TopasInpError,
    read_topas_inp,
)
from rietx.io.projects.topas import to_structure as topas_to_structure

# ===========================================================================
# fixtures — typed, cited, not vendored
# ===========================================================================

_HEADER = """\
#\\#CIF_2.0
data_{name}
_parent_space_group.name_H-M_alt  {parent}
_parent_space_group.IT_number     {it}
_parent_space_group.transform_Pp_abc  'a,b,c;0,0,0'

loop_
_parent_propagation_vector.id
_parent_propagation_vector.kxkykz
k1 [{k}]

_parent_space_group.child_transform_Pp_abc  '{child}'
_space_group_magn.transform_BNS_Pp_abc  '{transform}'
_space_group_magn.number_BNS  {bns}
_space_group_magn.name_BNS  {symbol}
_cell_length_a  {a}
_cell_length_b  {b}
_cell_length_c  {c}
_cell_angle_alpha  {alpha}
_cell_angle_beta   {beta}
_cell_angle_gamma  {gamma}

loop_
_space_group_symop_magn_operation.id
_space_group_symop_magn_operation.xyz
{operations}

loop_
_space_group_symop_magn_centering.id
_space_group_symop_magn_centering.xyz
{centerings}

loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
{sites}
"""


def _magcif(tmp_path, name, *, parent, it, bns, symbol, cell, operations,
            sites, moment_loop, centerings=("x,y,z,+1",), k="0 0 0",
            child="a,b,c;0,0,0", transform="a,b,c;0,0,0", extra="") -> Path:
    """Write one magCIF fixture. One writer, so the layout is stated once."""
    a, b, c, alpha, beta, gamma = cell
    text = _HEADER.format(
        name=name, parent=f"'{parent}'", it=it, bns=bns, symbol=f'"{symbol}"',
        a=a, b=b, c=c, alpha=alpha, beta=beta, gamma=gamma, k=k, child=child,
        transform=transform,
        operations="\n".join(f"{i} {op}" for i, op in enumerate(operations, 1)),
        centerings="\n".join(f"{i} {op}" for i, op in enumerate(centerings, 1)),
        sites="\n".join(sites),
    ) + moment_loop + extra
    path = tmp_path / f"{name}.mcif"
    path.write_text(text, encoding="utf-8")
    return path


def _moment_loop(items, *, tags=("crystalaxis_x", "crystalaxis_y",
                                 "crystalaxis_z", "symmform")) -> str:
    head = "\n".join(f"_atom_site_moment.{t}" for t in ("label", *tags))
    rows = "\n".join(" ".join(str(v) for v in row) for row in items)
    return f"\nloop_\n{head}\n{rows}\n"


# --- LaMnO3 ---------------------------------------------------------------
#
# P n m a, BNS 62.448 ("P n' m a'"), k = 0.  The A-type antiferromagnet.
# Moment 3.7(1) mu_B along **a** on Mn1 at the origin: Elemans, van Laar, van
# der Veen & Loopstra (1971), *J. Solid State Chem.* **3**, 238-242.  Checked
# against MAGNDATA #0.642, which is the record and not the source.  This is
# WP-1327's second acceptance structure and the group its fit selects.
_LAMNO3 = dict(
    parent="P n m a", it=62, bns="62.448", symbol="P n' m a'",
    cell=(5.74200, 7.66800, 5.53200, 90.0, 90.0, 90.0),
    operations=("x,y,z,+1", "-x,y+1/2,-z,+1", "-x,-y,-z,+1", "x,-y+1/2,z,+1",
                "x+1/2,-y+1/2,-z+1/2,-1", "-x+1/2,-y,z+1/2,-1",
                "-x+1/2,y+1/2,z+1/2,-1", "x+1/2,y,-z+1/2,-1"),
    sites=("La1 La 0.54900 0.25000 0.01000 1",
           "Mn1 Mn 0.00000 0.00000 0.00000 1",
           "O1 O 0.98600 0.25000 0.93000 1",
           "O2 O 0.30900 0.03900 0.22400 1"),
    moment_loop=_moment_loop([("Mn1", "3.7(1)", "0.0(5)", "0.00000",
                               "mx,my,mz")]),
)

# --- Cr2WO6 ---------------------------------------------------------------
#
# P 4_2/m n m, BNS 58.395 ("P n' n m") **in the parent tetragonal setting**,
# with the non-identity `transform_BNS_Pp_abc 'b,-a,c;0,0,0'` that carries it
# to the BNS standard setting.  Cr moment in the ab plane: Zhu, Do, Cruz, Dun,
# Zhou, Mahanti & Ke (2014), *Phys. Rev. Lett.* **113**, 076406.  Checked
# against MAGNDATA #0.75, whose own record says "moment scale arbitrary" and
# writes the direction (0, 1, 0) with no magnitude — so the **direction** is
# the fact taken from it and the modulus below is the GSAS-II `Magnetic-II`
# tutorial's 2.35(2) mu_B, quoted as that page's number.  This is WP-1327's
# first acceptance structure and 58.395 is the group its fit selects.
_CR2WO6 = dict(
    parent="P  4_2/m  n  m", it=136, bns="58.395", symbol="P  n'  n  m",
    transform="b,-a,c;0,0,0",
    cell=(4.58200, 4.58200, 8.87000, 90.0, 90.0, 90.0),
    operations=("x,y,z,+1", "-x+1/2,y+1/2,-z+1/2,+1", "-x+1/2,y+1/2,z+1/2,+1",
                "x,y,-z,+1", "x+1/2,-y+1/2,-z+1/2,-1", "-x,-y,z,-1",
                "-x,-y,-z,-1", "x+1/2,-y+1/2,z+1/2,-1"),
    sites=("Cr1 Cr 0.00000 0.00000 0.33450 1",
           "W1 W 0.00000 0.00000 0.00000 1",
           "O1 O 0.30300 0.30300 0.00000 1",
           "O2 O 0.30600 0.30600 0.34000 1"),
    moment_loop=_moment_loop([("Cr1", "0.00000", "2.35(2)", "0.00000",
                               "mx,my,0")]),
)

# --- YMnO3 ----------------------------------------------------------------
#
# P 6_3 c m, BNS 185.197, type I.  **The hexagonal fixture**, and it is here
# for one reason: on 120-degree axes the crystal-axis metric is not the
# identity, so |(1.68, 3.36, 0)| is 2.9098 mu_B and the Euclidean norm is
# 3.7566 — 29 % out.  Moment: Munoz, Alonso, Martinez-Lope, Casais, Martinez &
# Fernandez-Diaz (2000), *Phys. Rev. B* **62**, 9498-9510, checked against
# MAGNDATA #0.6.  M-5 measured that the transposed symmetry action is
# invisible outside space groups 149-194, and that this structure is one of the
# three published rows that catches it, so a magnetic reader tested only on
# perovskites and rutiles would prove nothing about the conversion.
_YMNO3 = dict(
    parent="P  6_3c  m", it=185, bns="185.197", symbol="P  6_3c  m",
    cell=(6.15530, 6.15530, 11.40260, 90.0, 90.0, 120.0),
    operations=("x,y,z,+1", "x-y,x,z+1/2,+1", "-y,x-y,z,+1", "-x,-y,z+1/2,+1",
                "-x+y,-x,z,+1", "y,-x+y,z+1/2,+1", "-x+y,y,z+1/2,+1",
                "-y,-x,z+1/2,+1", "x,x-y,z+1/2,+1", "-x,-x+y,z,+1",
                "x-y,-y,z,+1", "y,x,z,+1"),
    sites=("Y1 Y 0.00000 0.00000 0.26890 1",
           "Y2 Y 0.33333 0.66667 0.22900 1",
           "Mn1 Mn 0.32080 0.00000 0.00000 1",
           "O1 O 0.31000 0.00000 0.16210 1",
           "O2 O 0.63890 0.00000 0.33670 1",
           "O3 O 0.00000 0.00000 0.47450 1",
           "O4 O 0.33333 0.66667 0.01330 1"),
    moment_loop=_moment_loop([("Mn1", "1.68", "3.36", "0.0", "mx,2mx,0")]),
)

#: |m| of YMnO3's moment under the magCIF cosine metric, and the Euclidean
#: norm that is *not* it.  Both written down because the gap is what the
#: hexagonal fixture exists to measure.
_YMNO3_MAGNITUDE = 2.9098453567157145
_YMNO3_EUCLIDEAN = math.sqrt(1.68 ** 2 + 3.36 ** 2)

# --- ScMnO3 ---------------------------------------------------------------
#
# P 6_3 c m, BNS 185.201, **type III** — the one M-5 measured as catching all
# three wrong symmetry actions.  Moment (-3.03, 0, 0) mu_B: Munoz et al.
# (2000), *Phys. Rev. B* **62**, 9498-9510; MAGNDATA #0.7.
_SCMNO3 = dict(
    parent="P  6_3c  m", it=185, bns="185.201", symbol="P  6_3c'  m'",
    cell=(5.83338, 5.83338, 11.16862, 90.0, 90.0, 120.0),
    operations=("x,y,z,+1", "x-y,x,z+1/2,+1", "-y,x-y,z,+1", "-x,-y,z+1/2,+1",
                "-x+y,-x,z,+1", "y,-x+y,z+1/2,+1", "-x+y,y,z+1/2,-1",
                "-y,-x,z+1/2,-1", "x,x-y,z+1/2,-1", "-x,-x+y,z,-1",
                "x-y,-y,z,-1", "y,x,z,-1"),
    sites=("Sc1 Sc 0.00000 0.00000 0.27470 1",
           "Sc2 Sc 0.33333 0.66667 0.23080 1",
           "Mn1 Mn 0.33160 0.00000 0.00000 1",
           "O1 O 0.30180 0.00000 0.16800 1",
           "O2 O 0.63570 0.00000 0.33290 1",
           "O3 O 0.00000 0.00000 0.46780 1",
           "O4 O 0.33333 0.66667 0.02380 1"),
    moment_loop=_moment_loop([("Mn1", "-3.03", "0.0", "0.0", "mx,0,mz")]),
)

_ALL = {"LaMnO3": _LAMNO3, "Cr2WO6": _CR2WO6, "YMnO3": _YMNO3,
        "ScMnO3": _SCMNO3}

#: Which ion each fixture's magnetic site is, and the paper's own oxidation
#: state.  magCIF has no item for this (``_atom_site_type_symbol`` states the
#: *nuclear* species and MAGNDATA writes a bare ``Mn``), so it is the caller's
#: to supply and the reader reports when it had to fall back.
_IONS = {"LaMnO3": {"Mn1": "Mn3+"}, "Cr2WO6": {"Cr1": "Cr3+"},
         "YMnO3": {"Mn1": "Mn3+"}, "ScMnO3": {"Mn1": "Mn3+"}}


def _fixture(tmp_path, key, **overrides):
    spec = dict(_ALL[key])
    spec.update(overrides)
    return _magcif(tmp_path, key, **spec)


def _read(tmp_path, key, **overrides):
    return structure_from_cif(str(_fixture(tmp_path, key, **overrides)),
                              moment_ions=_IONS[key])


def _stored(phase) -> str:
    """The magnetic half of a phase, as a canonical JSON blob to hash.

    "Every stored field", spelled out rather than left to a model dump of the
    whole phase: the claim this file makes about a round trip is about the
    fields magCIF carries, and naming them is what makes the claim checkable
    when a field is added.
    """
    return json.dumps({
        "magnetic_symmetry": phase.magnetic_symmetry.model_dump(mode="json"),
        "moments": {a.label: a.moment.model_dump(mode="json")
                    for a in phase.atoms if a.moment is not None},
    }, sort_keys=True)


# ===========================================================================
# 1. the positive arm: the operator lists are facts, and they identify
# ===========================================================================

@pytest.mark.parametrize("key", sorted(_ALL))
def test_the_typed_operator_list_identifies_to_its_published_bns_number(key):
    """Nothing here is taken on trust from a record.

    The operator list of each fixture is typed, and what makes the typing
    checkable is that spglib identifies it back to the BNS number the paper's
    own record states — a transcription error in an operator would land the
    group somewhere else in the 1651, or on nothing at all. This is the only
    verification the fixtures' *symmetry* half gets, and it is a strong one:
    the number was not used to build the list.
    """
    spec = _ALL[key]
    group = MagneticGroup.from_xyz(spec["operations"], ["x,y,z,+1"])
    assert identify(group).bns_number == spec["bns"]


@pytest.mark.parametrize("key", sorted(_ALL))
def test_a_magcif_reads_into_wp1327s_model(tmp_path, key):
    """The whole of the read, on four published structures.

    What has to arrive: the *nuclear* space group (from
    ``_parent_space_group.name_H-M_alt``, because a magCIF states no ordinary
    H-M symbol at all and gemmi resolves none for one), the operator list
    verbatim, the BNS number and name as metadata, and the moment on the site
    the loop names.  The parent k is read only to be refused when it is not Γ
    (every fixture here states ``[0 0 0]``) and is not stored.
    """
    spec = _ALL[key]
    structure = _read(tmp_path, key)
    (phase,) = structure.phases
    assert phase.space_group  # resolved, not None
    ms = phase.magnetic_symmetry
    assert tuple(ms.operations) == tuple(spec["operations"])
    assert ms.bns_number == spec["bns"]
    assert ms.symbol == spec["symbol"]
    assert ms.uni_number == identify(ms.group()).uni_number
    moments = [a for a in phase.atoms if a.moment is not None]
    assert len(moments) == 1
    assert moments[0].moment.ion == next(iter(_IONS[key].values()))


@pytest.mark.parametrize("key", sorted(_ALL))
def test_the_published_moment_lies_in_the_span_the_operators_derive(tmp_path, key):
    """The reader's own cross-check, and the schema's.

    A moment read from a file is only meaningful if the file's own operator
    list allows it on that site, and WP-1327's schema refuses one that does not
    (``Phase._moments_are_stateable``) — so a fixture that reads at all has
    already passed that test. Asserted here explicitly, and as a **span** test
    rather than a dimension count, because M-5 measured that a wrong symmetry
    action gives the right dimension in every crystal system.
    """
    structure = _read(tmp_path, key)
    phase = structure.phases[0]
    group = phase.magnetic_symmetry.group()
    for atom in phase.atoms:
        if atom.moment is None:
            continue
        basis = group.allowed_moment_basis(
            (atom.x.value, atom.y.value, atom.z.value))
        assert basis.size, f"{atom.label} carries a moment on a forbidden site"
        assert in_span(basis, atom.moment.values())


def test_the_transform_to_the_bns_setting_is_carried_and_not_applied(tmp_path):
    """`transform_BNS_Pp_abc` is metadata, and applying it would be wrong.

    Cr2WO6's record states ``'b,-a,c;0,0,0'``: the operator list in the file is
    in the **parent tetragonal setting**, the setting the file's own cell and
    coordinates are in, and the transform is how to reach the BNS standard
    setting from there. So carrying the operators as written is the only
    reading that keeps the group, the cell and the atoms in one frame —
    transforming them would move the group away from the coordinates beside
    it.

    The measurement that this is the right way round: the list as written
    identifies as 58.395 (above), and it is *not* the list spglib's database
    serves for 58.395, which is in the BNS setting. M-5's ``transformed`` is
    what relates the two, and the check here is that this reader stores the
    file's own and records the transform rather than doing either silently.
    """
    structure = _read(tmp_path, "Cr2WO6")
    ms = structure.phases[0].magnetic_symmetry
    assert ms.setting == "b,-a,c;0,0,0"
    assert tuple(ms.operations) == tuple(_CR2WO6["operations"])
    database = rx.MagneticSymmetry.model_validate("58.395")
    assert set(database.operations) != set(ms.operations), (
        "if these agreed, the fixture would not be in a non-standard setting "
        "and the test would prove nothing")
    # ...and the two really are the same group, related by that transform.
    assert (identify(ms.group()).uni_number
            == identify(database.group()).uni_number)


# ===========================================================================
# 2. the round trip
# ===========================================================================

@pytest.mark.parametrize("key", sorted(_ALL))
def test_the_round_trip_is_bit_identical_on_every_stored_field(tmp_path, key):
    """read -> write -> read is bit-identical, and write -> read -> write is
    byte-identical.

    The claim is stated in this shape and not as "the written file equals the
    input" for a reason worth being explicit about: a CIF quotes a number to a
    fixed precision, so *no* writer — this one or the nuclear one beside it —
    can return a refined value with more digits than the file carries. What
    can be guaranteed, and is what a caller needs, is that the model is a fixed
    point of the pair: whatever the first read produced survives every
    subsequent write and read exactly.
    """
    first = _read(tmp_path, key)
    out1 = tmp_path / "one.cif"
    structure_to_cif(first, str(out1))
    second = structure_from_cif(str(out1))
    out2 = tmp_path / "two.cif"
    structure_to_cif(second, str(out2))
    assert _stored(first.phases[0]) == _stored(second.phases[0])
    assert out1.read_bytes() == out2.read_bytes()
    # and the hash is stable, which is what "hash them" asks for
    assert (hashlib.sha256(_stored(first.phases[0]).encode()).hexdigest()
            == hashlib.sha256(_stored(second.phases[0]).encode()).hexdigest())


def test_the_esds_survive_the_round_trip_because_the_su_tags_carry_them(tmp_path):
    """A moment's esd is 0.1-0.9 mu_B, which is why the components are *not*
    written in ``value(su)`` notation.

    LaMnO3's record states 3.7(1) and 0.0(5). Under the crystallographic
    ``value(su)`` convention every other number in a rietx CIF uses, two
    significant figures of su leave the value quoted to one decimal — and a
    refined 2.0785 +/- 0.878 would be written ``2.1(9)`` and come back as 2.1.
    So the crystal-axis components go out as their own doubles with the
    dictionary's own ``_su`` items beside them, and this asserts both halves
    arrive.
    """
    structure = _read(tmp_path, "LaMnO3")
    moment = structure.phases[0].atoms[1].moment
    assert moment.crystalaxis_x.value == 3.7
    assert moment.crystalaxis_x.stderr == pytest.approx(0.1)
    assert moment.crystalaxis_y.stderr == pytest.approx(0.5)
    assert moment.crystalaxis_z.stderr is None      # no parenthesis, no esd
    out = tmp_path / "rt.cif"
    structure_to_cif(structure, str(out))
    text = out.read_text(encoding="utf-8")
    assert "_atom_site_moment.crystalaxis_x_su" in text
    back = structure_from_cif(str(out)).phases[0].atoms[1].moment
    assert back.crystalaxis_x.stderr == pytest.approx(0.1)
    assert back.crystalaxis_y.stderr == pytest.approx(0.5)
    assert back.crystalaxis_z.stderr is None


def test_the_ion_and_the_g_round_trip_through_the_two_private_items(tmp_path):
    """The two quantities no magnetic dictionary defines.

    ``cif_mag.dic`` has no item for the magnetic **ion** (its
    ``_atom_type_scat.neutron_magnetic_j0_*`` items state the coefficients
    themselves, not which ion they are) and none for the Landé **g**. Both are
    part of the model — <j0> for Mn and for Mn3+ are different curves, and g is
    what the <j2> term of a 4f form factor needs — so losing them on a round
    trip would lose which form factor a refinement was run against. They go out
    under ``_rietx_atom_site_moment.``, namespaced, enumerated in
    :data:`~rietx.crystallography.magcif.PRIVATE_TAGS`, and asserted here to be
    the **only** non-dictionary tags the writer emits.
    """
    structure = _read(tmp_path, "LaMnO3")
    atom = structure.phases[0].atoms[1]
    structure.phases[0].atoms[1] = atom.model_copy(update={
        "moment": atom.moment.model_copy(update={"ion": "Mn3+", "g": 1.98})})
    out = tmp_path / "g.cif"
    structure_to_cif(structure, str(out))
    text = out.read_text(encoding="utf-8")
    written = {t for t in re.findall(r"(?m)^\s*(_[A-Za-z0-9_.\-]+)", text)
               if "magn" in t or "moment" in t or "propagation" in t}
    assert written <= set(magcif.WRITTEN_TAGS) | set(magcif.PRIVATE_TAGS)
    assert written & set(magcif.PRIVATE_TAGS) == set(magcif.PRIVATE_TAGS)
    back = structure_from_cif(str(out)).phases[0].atoms[1].moment
    assert (back.ion, back.g) == ("Mn3+", 1.98)


def test_a_g_with_twelve_significant_digits_round_trips_exactly(tmp_path):
    """The g is written at ``repr`` precision, not to six figures.

    An assumed Hund's-rule g_J is a rational — Nd3+'s is 8/11 — whose decimal
    does not end in six significant figures, so a ``:.6g`` writer returned it
    3.7e-7 to 2.9e-6 off on 156 MAGNDATA entries: a form-factor weight lost on
    the first trip and then stable, which a byte comparison of two writes
    alone cannot see.
    """
    structure = _read(tmp_path, "LaMnO3")
    atom = structure.phases[0].atoms[1]
    structure.phases[0].atoms[1] = atom.model_copy(update={
        "moment": atom.moment.model_copy(update={"g": 0.727272727273})})
    out1 = tmp_path / "one.cif"
    structure_to_cif(structure, str(out1))
    second = structure_from_cif(str(out1))
    out2 = tmp_path / "two.cif"
    structure_to_cif(second, str(out2))
    assert second.phases[0].atoms[1].moment.g == 0.727272727273
    assert _stored(structure.phases[0]) == _stored(second.phases[0])
    assert out1.read_bytes() == out2.read_bytes()


def test_the_first_read_of_a_su_is_the_double_a_second_read_gives(tmp_path):
    """``3.7000(3)`` reads an esd of 0.0003 — the nearest double — on the first
    read, and the writer's ``0.00030`` reads the same double back.

    Multiplying by ``10.0 ** -4`` rounds twice and landed 1 ulp high
    (0.00030000000000000003), so a read -> write -> read moved every such esd
    once; dividing by ``10 ** 4`` is a single correctly-rounded operation.
    """
    import gemmi

    loop = _moment_loop([("Mn1", "3.7000(3)", "0.0(3)", "0.00000", "mx,my,mz")])
    structure = _read(tmp_path, "LaMnO3", moment_loop=loop)
    first = structure.phases[0].atoms[1].moment
    out = tmp_path / "rt.cif"
    structure_to_cif(structure, str(out))
    block = gemmi.cif.read(str(out)).sole_block()
    written = [float(block.find_values(f"_atom_site_moment.crystalaxis_{n}_su")[0])
               for n in "xy"]
    second = structure_from_cif(str(out)).phases[0].atoms[1].moment
    for n, w in zip("xy", written):
        assert (getattr(first, f"crystalaxis_{n}").stderr
                == getattr(second, f"crystalaxis_{n}").stderr == w)
    assert written == [0.0003, 0.3]


def test_a_caller_supplied_ion_beats_the_files_own(tmp_path):
    """``moment_ions=`` overrides what the file wrote, and the file's own
    private item overrides nothing else.

    The precedence has to be this way round: a magCIF written by this package
    carries the ion it was refined with, and a caller correcting it — say from
    Mn3+ to Mn4+ after a chemistry argument — must win, or the override would
    be silently inert on exactly the files it is most likely to be used on.
    """
    structure = _read(tmp_path, "LaMnO3")
    out = tmp_path / "ion.cif"
    structure_to_cif(structure, str(out))
    again = structure_from_cif(str(out), moment_ions={"Mn1": "Mn4+"})
    assert again.phases[0].atoms[1].moment.ion == "Mn4+"


# ===========================================================================
# 3. the three moment forms, and the metric
# ===========================================================================

def test_the_crystal_axis_magnitude_is_the_cosine_metric_not_the_euclidean_norm(
        tmp_path):
    """On 120-degree axes the two differ by 29 %, and the file may state either
    number in ``_atom_site_moment.magnitude``.

    ``cif_mag.dic`` defines the crystal-axis basis as **unit vectors** along a,
    b, c, so |m| = sqrt(m.G.m) with G the cosine metric and not sqrt(sum m_i^2)
    — the trap M-5 wrote ``moment_magnitude`` for. This reader cross-checks a
    stated magnitude against the components under that metric, so a file
    quoting the Euclidean norm is refused naming the metric, and one quoting
    the right number reads. YMnO3's (1.68, 3.36, 0) is 2.9098 mu_B and 3.7566
    Euclidean.
    """
    assert moment_magnitude((1.68, 3.36, 0.0), _YMNO3["cell"]) == pytest.approx(
        _YMNO3_MAGNITUDE)
    good = _moment_loop([("Mn1", "1.68", "3.36", "0.0", f"{_YMNO3_MAGNITUDE:.5f}")],
                        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z",
                              "magnitude"))
    _read(tmp_path, "YMnO3", moment_loop=good)          # reads
    bad = _moment_loop([("Mn1", "1.68", "3.36", "0.0", f"{_YMNO3_EUCLIDEAN:.5f}")],
                       tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z",
                             "magnitude"))
    with pytest.raises(magcif.MagCifError, match="Euclidean norm"):
        _read(tmp_path, "YMnO3", moment_loop=bad)


def test_a_rounded_magnitude_reads_within_its_own_stated_precision(tmp_path):
    """D5(i), false positive class 1 (77% of the measured cluster). A file
    stating its magnitude to fewer significant figures than the crystal-axis
    components imply is self-consistent, just imprecisely rounded -- YMnO3's
    true cosine-metric magnitude is 2.9098453... mu_B; stating it as the
    1-sig-fig "3" is off by 0.090, which the old fixed 0.02 mu_B tolerance
    refused outright. The fix compares against the stated text's own
    precision (no su here, so half its last printed digit: "3" -> 0 decimals
    -> 0.5 mu_B), which covers the rounding.
    """
    loop = _moment_loop([("Mn1", "1.68", "3.36", "0.0", "3")],
                        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z",
                              "magnitude"))
    structure = _read(tmp_path, "YMnO3", moment_loop=loop)
    assert structure.phases[0].atoms[2].moment.crystalaxis_x.value == 1.68
    # negative control: a magnitude stated to full precision must still
    # agree closely -- rounding tolerance is not a blanket exemption
    tight = _moment_loop([("Mn1", "1.68", "3.36", "0.0", "3.00000")],
                         tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z",
                               "magnitude"))
    with pytest.raises(magcif.MagCifError, match="mu_B"):
        _read(tmp_path, "YMnO3", moment_loop=tight)


def test_a_negative_stated_magnitude_is_a_sign_convention_not_a_mismatch(tmp_path):
    """D5(ii), false positive class 2 (11% of the measured cluster). A file
    stating a *negative* magnitude alongside a components row that already
    encodes the sign geometrically is a common shorthand for "antiparallel to
    the reference direction" -- comparing the signed stated value against the
    unsigned derived norm used to double the apparent gap. The fix compares
    |magnitude| to the (always non-negative) derived norm.
    """
    loop = _moment_loop(
        [("Mn1", "1.68", "3.36", "0.0", f"-{_YMNO3_MAGNITUDE:.5f}")],
        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z", "magnitude"))
    structure = _read(tmp_path, "YMnO3", moment_loop=loop)
    assert structure.phases[0].atoms[2].moment.crystalaxis_y.value == 3.36
    # negative control: the same magnitude, positive, reads identically --
    # this is genuinely a sign-convention no-op, not a separate leniency
    positive = _moment_loop(
        [("Mn1", "1.68", "3.36", "0.0", f"{_YMNO3_MAGNITUDE:.5f}")],
        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z", "magnitude"))
    baseline = _read(tmp_path, "YMnO3", moment_loop=positive)
    assert _stored(structure.phases[0]) == _stored(baseline.phases[0])
    # and doubling the gap the old (signed) comparison made is still refused
    # once it is a *real* mismatch, not just a flipped sign: a magnitude with
    # the wrong sign *and* the wrong size
    wrong = _moment_loop([("Mn1", "1.68", "3.36", "0.0", "-1.00000")],
                         tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z",
                               "magnitude"))
    with pytest.raises(magcif.MagCifError, match="mu_B"):
        _read(tmp_path, "YMnO3", moment_loop=wrong)


def test_a_genuine_magnitude_mismatch_past_stated_precision_still_refuses(
        tmp_path):
    """D5(iii), the real class (11% of the measured cluster): a magnitude
    that disagrees with its components by far more than any plausible
    rounding or sign confusion stays refused -- this is the check's whole
    point, and neither of the two false-positive fixes above may weaken it.
    """
    # 0.35 mu_B off, stated to full precision (no rounding or sign story can
    # explain this away)
    off = _moment_loop(
        [("Mn1", "1.68", "3.36", "0.0", f"{_YMNO3_MAGNITUDE + 0.35:.5f}")],
        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z", "magnitude"))
    with pytest.raises(magcif.MagCifError, match="mu_B"):
        _read(tmp_path, "YMnO3", moment_loop=off)
    # and an explicit magnitude_su column narrower than the gap still refuses
    su_loop = _moment_loop(
        [("Mn1", "1.68", "3.36", "0.0", f"{_YMNO3_MAGNITUDE + 0.35:.5f}", "0.01")],
        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z", "magnitude",
              "magnitude_su"))
    with pytest.raises(magcif.MagCifError, match="mu_B"):
        _read(tmp_path, "YMnO3", moment_loop=su_loop)
    # ...but a magnitude_su wide enough to cover the gap is read, not refused
    # -- the file's own stated uncertainty is the authority once it is given
    wide_su_loop = _moment_loop(
        [("Mn1", "1.68", "3.36", "0.0", f"{_YMNO3_MAGNITUDE + 0.35:.5f}", "0.4")],
        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z", "magnitude",
              "magnitude_su"))
    _read(tmp_path, "YMnO3", moment_loop=wide_su_loop)


def test_the_magnitude_tolerance_also_covers_the_components_own_rounding(
        tmp_path):
    """D5(i), a second false-positive shape found by re-measuring the sweep
    on the fixed tree: a magnitude compared only against *its own* last
    printed digit still refused 7 of 540 real, previously-loading MAGNDATA
    entries, because the derived norm is itself only as precise as the
    (also rounded, coarser) components it came from -- YMnO3's coarse "1.68,
    3.36" components (2 decimals) carry their own +-0.005 mu_B rounding,
    which the cosine metric can amplify past a 3-decimal magnitude's own
    +-0.0005 mu_B tolerance alone.

    Fixed by propagating each component's own imprecision (its su where
    stated, else half its own last printed digit) through the metric and
    adding it to the magnitude's tolerance -- an L1, first-order worst-case
    bound, deliberately generous since two independent roundings essentially
    never cancel exactly.
    """
    # true cosine-metric magnitude is 2.9098453... (YMnO3, see above); stated
    # to 3 decimals as "2.906" the gap (0.003845) is 7.7x the magnitude's own
    # last-digit tolerance alone, but within the combined one
    loop = _moment_loop([("Mn1", "1.68", "3.36", "0.0", "2.906")],
                        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z",
                              "magnitude"))
    _read(tmp_path, "YMnO3", moment_loop=loop)
    # negative control: explicit, narrow esds on *both* components that carry
    # the tolerance override the "half the last digit" guess with a tighter
    # one, and the same gap against that narrower combined tolerance refuses
    tight_loop = _moment_loop(
        [("Mn1", "1.6800(1)", "3.3600(1)", "0.0", "2.906")],
        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z", "magnitude"))
    with pytest.raises(magcif.MagCifError, match="mu_B"):
        _read(tmp_path, "YMnO3", moment_loop=tight_loop)


def test_the_spherical_form_converts_to_the_vector_M5_gives(tmp_path):
    """``cif_mag.dic``'s spherical frame is x || a, z || c*, and that is
    ``adp.cartesian_basis``'s own frame — which is why this conversion needs no
    second convention.

    Asserted rather than assumed, because it is load-bearing and invisible: the
    Cholesky factor of the direct metric is upper triangular with a positive
    diagonal, so its first column is along +x (hence x || a) and a x b is along
    +z (hence z || c*). If ``cartesian_basis`` ever chose a different
    orientation — the docstring says the choice "cancels in every quantity
    reported here", which is true of eigenvalues and traces and **not** of a
    spherical angle — every spherical moment in the package would silently
    rotate. This test is the thing that would notice.
    """
    from rietx.crystallography.adp import cartesian_basis

    cell = _YMNO3["cell"]
    basis = cartesian_basis(*cell)
    assert np.allclose(np.tril(basis, -1), 0.0), "x || a requires upper triangular"
    assert np.all(np.diag(basis) > 0)
    a_hat = basis[:, 0] / np.linalg.norm(basis[:, 0])
    c_star = np.cross(basis[:, 0], basis[:, 1])
    assert np.allclose(a_hat, [1, 0, 0])
    assert np.allclose(c_star / np.linalg.norm(c_star), [0, 0, 1])

    components = (1.68, 3.36, 0.0)
    cartesian = moment_to_cartesian(components, cell)
    modulus = float(np.linalg.norm(cartesian))
    polar = math.degrees(math.acos(cartesian[2] / modulus))
    azimuth = math.degrees(math.atan2(cartesian[1], cartesian[0])) % 360.0
    assert modulus == pytest.approx(_YMNO3_MAGNITUDE)
    spherical = _moment_loop(
        [("Mn1", f"{modulus:.10f}", f"{polar:.10f}", f"{azimuth:.10f}")],
        tags=("spherical_modulus", "spherical_polar", "spherical_azimuthal"))
    read = _read(tmp_path, "YMnO3", moment_loop=spherical)
    got = [a.moment for a in read.phases[0].atoms if a.moment][0]
    assert got.values() == pytest.approx(components, abs=1e-9)


def test_the_cartesian_form_converts_to_the_same_vector(tmp_path):
    """The third form ``cif_mag.dic`` defines, read for the same reason: a form
    this reader did not take would be a moment silently dropped."""
    cell = _YMNO3["cell"]
    cartesian = moment_to_cartesian((1.68, 3.36, 0.0), cell)
    loop = _moment_loop([("Mn1", *[f"{v:.10f}" for v in cartesian])],
                        tags=("Cartn_x", "Cartn_y", "Cartn_z"))
    read = _read(tmp_path, "YMnO3", moment_loop=loop)
    got = [a.moment for a in read.phases[0].atoms if a.moment][0]
    assert got.values() == pytest.approx((1.68, 3.36, 0.0), abs=1e-9)
    assert np.allclose(moment_from_cartesian(cartesian, cell), (1.68, 3.36, 0.0))


def test_two_forms_that_disagree_are_refused_naming_the_site(tmp_path):
    """Both are the same vector in ``cif_mag.dic``, so a file stating two
    different ones contradicts itself and this reader does not pick a side."""
    cell = _YMNO3["cell"]
    wrong = moment_to_cartesian((3.36, 1.68, 0.0), cell)     # x and y swapped
    loop = _moment_loop(
        [("Mn1", "1.68", "3.36", "0.0", *[f"{v:.6f}" for v in wrong])],
        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z",
              "Cartn_x", "Cartn_y", "Cartn_z"))
    with pytest.raises(magcif.MagCifError, match="contradicts itself"):
        _read(tmp_path, "YMnO3", moment_loop=loop)


def test_a_su_is_read_in_the_place_of_the_last_decimal(tmp_path):
    """The CIF su convention, and its three traps, on the parser itself."""
    assert magcif.parse_su("3.7(1)") == (3.7, pytest.approx(0.1))
    assert magcif.parse_su("0.549(12)") == (0.549, pytest.approx(0.012))
    assert magcif.parse_su("1.") == (1.0, None)          # MAGNDATA writes this
    assert magcif.parse_su("-3.03") == (-3.03, None)
    assert magcif.parse_su("123(25)") == (123.0, pytest.approx(25.0))
    with pytest.raises(ValueError, match="exponential"):
        magcif.parse_su("1.2e-3(4)")
    with pytest.raises(ValueError):
        magcif.parse_su("?")


# ===========================================================================
# 4. the negative controls
# ===========================================================================

_MODULATION = {
    "moment Fourier": "\nloop_\n_atom_site_moment_Fourier.atom_site_label\n"
                      "_atom_site_moment_Fourier.axis\n"
                      "_atom_site_moment_Fourier.wave_vector_seq_id\n"
                      "Mn1 x 1\n",
    "cell wave vector": "\nloop_\n_cell_wave_vector.seq_id\n_cell_wave_vector.x\n"
                        "_cell_wave_vector.y\n_cell_wave_vector.z\n"
                        "1 0.128 0.0 0.0\n",
    "moment special function":
        "\nloop_\n_atom_site_moment_special_func.atom_site_label\n"
        "_atom_site_moment_special_func.sawtooth_ax\n"
        "Mn1 1.0\n",
    "superspace group": "\n_superspace_group.name  'Pnma(00g)s00'\n",
}


@pytest.mark.parametrize("what", sorted(_MODULATION))
def test_a_modulated_magcif_is_refused_by_name(tmp_path, what):
    """A moment that varies from cell to cell has no shape in this model, and
    reading its k = 0 amplitude alone would return a collinear structure for a
    modulated one — a structure that looks complete.

    Refused by **tag**, so the refusal does not depend on this reader
    recognising what the modulation *means*: the category is enough.
    """
    with pytest.raises(magcif.MagCifError, match="modulated magnetic structure"):
        _read(tmp_path, "LaMnO3", extra=_MODULATION[what])


def test_the_modulation_flag_alone_is_enough_to_refuse(tmp_path):
    """``_atom_site_moment.modulation_flag yes`` says the stated components are
    an *average* moment, which is not the moment — so the row is refused even
    with no Fourier loop beside it."""
    loop = _moment_loop([("Mn1", "3.7", "0.0", "0.0", "yes")],
                        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z",
                              "modulation_flag"))
    with pytest.raises(magcif.MagCifError, match="modulation_flag"):
        _read(tmp_path, "LaMnO3", moment_loop=loop)


def test_a_magnetic_supercell_is_refused_naming_what_would_be_needed(tmp_path):
    """The k != 0 fence, and it is a statement about WP-1327's model.

    A commensurate k != 0 structure is stated in its magnetic supercell — the
    generic MAGNDATA record, e.g. ``child_transform_Pp_abc 'a,b,2c;0,0,0'``
    with k = (0, 1, 1/2) — and the asymmetric unit of the magnetic group in
    that cell generally splits **one nuclear orbit into several sites with
    different moments**. WP-1327 stores one moment per atom of the *nuclear*
    asymmetric unit and propagates it over that site's magnetic orbit, so those
    moments have nowhere to go, and building the phase from them under a
    nuclear space group would count the nuclear atoms more than once in
    |F_N|^2.

    So it is refused, and the message names both halves of what would be
    needed. This is a real gap and not a formatting question.
    """
    with pytest.raises(magcif.MagCifError, match="not the parent cell"):
        _read(tmp_path, "LaMnO3", child="a,b,2c;0,0,0", k="0 1 1/2")
    # ...and a k != 0 alone is enough, even with no transform stated
    with pytest.raises(magcif.MagCifError, match="magnetic supercell"):
        _read(tmp_path, "LaMnO3", k="1/2 0 0")


def test_an_all_integer_k_is_gamma_not_a_supercell(tmp_path):
    """D2: k = (1, 1, 1) is Gamma identically -- a propagation vector is only
    ever physically meaningful modulo the reciprocal lattice, so an all-integer
    nonzero k states no enlargement at all and must read exactly like k = 0.

    Before the fix, ``is_commensurate_zero`` compared each component against
    literal ``0.0``, so every all-integer k != (0, 0, 0) -- (1, 1, 1), (0, 0, 1),
    (1, 0, 0), all present in the MAGNDATA corpus -- was refused as if it were a
    genuine k != 0 magnetic supercell, even with an identity child transform
    stating no cell enlargement.
    """
    structure = _read(tmp_path, "LaMnO3", k="1 1 1")
    baseline = _read(tmp_path, "LaMnO3")
    # the file's own stated k is still carried verbatim (it is not silently
    # rewritten to (0, 0, 0)) -- what changes is that it no longer triggers
    # the supercell refusal, and the moments/symmetry read exactly as k = 0's
    phase, base_phase = structure.phases[0], baseline.phases[0]
    assert phase.space_group == base_phase.space_group
    assert {a.label: a.moment.model_dump(mode="json") for a in phase.atoms
            if a.moment is not None} == {
        a.label: a.moment.model_dump(mode="json") for a in base_phase.atoms
        if a.moment is not None}
    # ...and a single-component integer offset reads the same way
    structure2 = _read(tmp_path, "LaMnO3", k="0 0 1")
    phase2 = structure2.phases[0]
    assert phase2.space_group == base_phase.space_group
    # negative control: a genuine non-integer commensurate k != 0 is still refused
    with pytest.raises(magcif.MagCifError, match="magnetic supercell"):
        _read(tmp_path, "LaMnO3", k="1/2 0 0")
    # ...and a mix of an integer and a genuine fractional component is refused too
    with pytest.raises(magcif.MagCifError, match="magnetic supercell"):
        _read(tmp_path, "LaMnO3", k="1 1/2 0")


def test_an_incommensurate_k_is_refused_with_its_own_sentence(tmp_path):
    """A k that is not a rational has no commensurate cell to be read in at
    all, which is a different refusal from the supercell one and says so."""
    with pytest.raises(magcif.MagCifError, match="incommensurate"):
        _read(tmp_path, "LaMnO3", child="a,b,7c;0,0,0", k="0 0 0.128")


def test_a_parent_setting_change_is_read_not_refused(tmp_path):
    """``_parent_space_group.transform_Pp_abc`` non-identity is a record of
    which setting the *symbol* was tabulated in, never a statement that the
    file's own cell is a supercell of anything — both real MAGNDATA fixtures
    this bug was found on (0.93 Ca2Fe2O5 'c,b,-a;0,0,0', 0.1084 Sr2Fe2O5
    '-b,a,c;0,0,0') carry exactly this shape and neither is a supercell.  The
    bug this guards against: an earlier version of
    ``refuse_a_magnetic_supercell`` refused any file whose parent transform
    was non-identity, which refused the *majority* of MAGNDATA's
    non-standard-setting entries outright.

    The fix reads this file exactly as it reads the identity-transform
    baseline: the nuclear group comes from the file's own magnetic operators
    (:func:`~rietx.crystallography.magcif.nuclear_operations`), which do not
    depend on what ``transform_Pp_abc`` says at all, so a |det| = 1 parent
    transform is inert metadata once the operators — not the symbol plus its
    reference-setting transform — are what the phase is built from."""
    text = _fixture(tmp_path, "LaMnO3").read_text(encoding="utf-8").replace(
        "_parent_space_group.transform_Pp_abc  'a,b,c;0,0,0'",
        "_parent_space_group.transform_Pp_abc  'c,a,b;0,0,0'")
    path = tmp_path / "setting.mcif"
    path.write_text(text, encoding="utf-8")
    structure = structure_from_cif(str(path), moment_ions=_IONS["LaMnO3"])
    baseline = _read(tmp_path, "LaMnO3")
    phase, base_phase = structure.phases[0], baseline.phases[0]
    assert phase.space_group == base_phase.space_group == "P n m a"
    assert _stored(phase) == _stored(base_phase)


def test_a_child_setting_permutation_is_read_not_refused(tmp_path):
    """The supercell predicate is the *child* transform's determinant, not
    whether it is exactly the identity: a |det| = 1 permutation of the
    magnetic cell's own axes (with k = 0 beside it) is a setting choice on
    that cell, not an enlargement of it, and reads exactly like the
    identity-transform baseline."""
    structure = _read(tmp_path, "LaMnO3", child="c,a,b;0,0,0")
    baseline = _read(tmp_path, "LaMnO3")
    assert _stored(structure.phases[0]) == _stored(baseline.phases[0])


@pytest.mark.parametrize("transform,expected", [
    (None, 1),
    ("a,b,c;0,0,0", 1),
    ("c,a,b;0,0,0", 1),          # a permutation -- a setting change, not a supercell
    ("-b,a,c;0,0,0", 1),         # MAGNDATA 0.1084's own parent transform
    ("2a,b,c;0,0,0", 2),         # a real supercell along a
    ("a,b,2c;0,0,0", 2),
])
def test_transform_determinant_is_the_supercell_fingerprint(transform, expected):
    """The predicate :func:`~rietx.crystallography.magcif.refuse_a_magnetic_supercell`
    now runs on: |det(P)|, never on whether P is exactly the identity."""
    assert magcif._transform_determinant(transform) == expected


def test_an_ima2_type_setting_mismatch_reads_in_the_setting_the_operators_state(
        tmp_path):
    """Bug B, synthetic. gemmi's tabulated operator table for a Hermann-Mauguin
    symbol can sit in a different setting than a magCIF's own magnetic
    operators state — measured on space group 46 (Ima2): MAGNDATA/Bilbao's
    setting for BNS 46.245 disagrees pointwise with gemmi's canonical
    ``I m a 2`` table. The operator list below *is* the public BNS 46.245
    table (verified independently two lines down, by identifying it back to
    its own number, exactly as every other fixture in this file is checked);
    the atom position and the moment are invented for this test and are not
    copied from any MAGNDATA record — no MAGNDATA file is added to this tree.

    Building the phase from the bare label ``"I m a 2"`` would attach gemmi's
    frame to a right-looking name — silent corruption, not a raise. The
    reader derives the nuclear operations from the file itself and finds the
    one tabulated setting of type 46 that contains them, ``I b m 2``, and
    reports the substitution.
    """
    import gemmi

    from rietx.crystallography.symmetry import operator_key, operator_keys

    ops = ("x,y,z,+1", "-x,-y,z,+1", "x,-y+1/2,z,-1", "-x,y+1/2,z,-1")
    cent = ("x,y,z,+1", "x+1/2,y+1/2,z+1/2,+1")
    assert identify(MagneticGroup.from_xyz(ops, cent)).bns_number == "46.245"

    path = _magcif(
        tmp_path, "ima2_synthetic", parent="I m a 2", it=46, bns="46.245",
        symbol="I m' a' 2", cell=(5.0, 15.0, 5.5, 90.0, 90.0, 90.0),
        operations=ops, centerings=cent,
        sites=("Fe1 Fe 0.00000 0.00000 0.00000 1",),
        moment_loop=_moment_loop([("Fe1", "0.0", "0.0", "2.00000", "0,0,mz")]),
    )
    diagnostics: list = []
    structure = structure_from_cif(str(path), moment_ions={"Fe1": "Fe3+"},
                                   diagnostics=diagnostics)
    (phase,) = structure.phases
    assert phase.space_group == "I b m 2"

    def keys(xyz):
        return frozenset(operator_key(np.asarray(op.rot) / op.DEN,
                                      np.asarray(op.tran) / op.DEN)
                         for op in map(gemmi.Op, xyz))

    derived = magcif.nuclear_operations(phase.magnetic_symmetry)
    taken = operator_keys(gemmi.find_spacegroup_by_name("I b m 2"))
    assert keys(derived) <= taken
    assert not keys(derived) <= operator_keys(
        gemmi.find_spacegroup_by_name("I m a 2")), (
        "the fixture must reproduce a real mismatch")
    assert phase.atoms[0].moment.crystalaxis_z.value == pytest.approx(2.0)
    (hit,) = [d for d in diagnostics if d.code == "CIF_MAGNETIC_NUCLEAR_SETTING"]
    assert "I m a 2" in hit.message and "I b m 2" in hit.message


def test_a_setting_no_tabulated_symbol_names_is_refused_by_name(tmp_path):
    """Synthetic, the positive arm of the setting check: the inversion centre
    moved to (1/4, 0, 0). No tabulated setting of P-1 has it there, so a phase
    built from the symbol would put the inversion at the origin — every
    moment's image on the wrong site. That needs the operation list carried on
    the phase (the operation-list phase), so here it is refused, naming the
    symbol and what would make it readable, rather than read in the wrong
    frame."""
    path = _magcif(
        tmp_path, "shifted_p1bar", parent="P -1", it=2, bns="2.4",
        symbol="P -1", cell=(5.0, 6.0, 7.0, 90.0, 90.0, 90.0),
        operations=("x,y,z,+1", "-x+1/2,-y,-z,+1"), centerings=("x,y,z,+1",),
        sites=("Fe1 Fe 0.10000 0.20000 0.30000 1",),
        moment_loop=_moment_loop([("Fe1", "0.0", "0.0", "2.00000", "mx,my,mz")]),
    )
    with pytest.raises(magcif.MagCifError,
                       match=r"(?s)'P -1'.*no single tabulated\s+symbol "
                             r"names.*symmetry_operations"):
        structure_from_cif(str(path), moment_ions={"Fe1": "Fe3+"})


def test_a_parent_orbit_split_by_the_magnetic_group_is_not_counted_twice(
        tmp_path):
    """Synthetic. A magCIF lists the asymmetric unit of the *magnetic* group,
    and a symmetry-lowering one can split a parent orbit into two listed
    sites: here P1 (type I) in a P-1 parent, with Fe1 and its inversion image
    Fe2 stated separately, antiparallel — a moment arrangement inversion (an
    axial vector is even under it) forbids, so the magnetic group really is
    lower. Built under the parent the two sites would be one orbit counted
    twice in |F_N|²; the reader builds the phase under the group the file's
    own operators state and reports why (measured on the MAGNDATA mirror:
    this shape is roughly one read entry in five)."""
    path = _magcif(
        tmp_path, "split_p1", parent="P -1", it=2, bns="1.1",
        symbol="P 1", cell=(5.0, 6.0, 7.0, 90.0, 90.0, 90.0),
        operations=("x,y,z,+1",), centerings=("x,y,z,+1",),
        sites=("Fe1 Fe 0.10000 0.20000 0.30000 1",
               "Fe2 Fe 0.90000 0.80000 0.70000 1"),
        moment_loop=_moment_loop([("Fe1", "0.0", "0.0", "2.00000", "mx,my,mz"),
                                  ("Fe2", "0.0", "0.0", "-2.00000", "mx,my,mz")]),
    )
    diagnostics: list = []
    structure = structure_from_cif(
        str(path), moment_ions={"Fe1": "Fe3+", "Fe2": "Fe3+"},
        diagnostics=diagnostics)
    (phase,) = structure.phases
    assert phase.space_group == "P 1"
    (hit,) = [d for d in diagnostics if d.code == "CIF_MAGNETIC_NUCLEAR_SETTING"]
    assert "'Fe1' has 2 images under 'P -1' and 1 under" in hit.message


def test_a_subgroup_magnetic_group_keeps_the_parent_where_no_orbit_shrinks(
        tmp_path):
    """The negative arm of the test above, and WP-1327's own shape: a
    magnetic group that is a proper subgroup of the parent, on a site whose
    orbit it does not shrink (an inversion centre, fixed by the inversion the
    magnetic group drops), keeps the parent as the nuclear group — the phase
    1327's acceptance refines (Cr₂WO₆: ``Pn'nm`` in ``P4₂/mnm``)."""
    path = _magcif(
        tmp_path, "kept_p1", parent="P -1", it=2, bns="1.1",
        symbol="P 1", cell=(5.0, 6.0, 7.0, 90.0, 90.0, 90.0),
        operations=("x,y,z,+1",), centerings=("x,y,z,+1",),
        sites=("Fe1 Fe 0.00000 0.00000 0.00000 1",),
        moment_loop=_moment_loop([("Fe1", "0.0", "0.0", "2.00000", "mx,my,mz")]),
    )
    diagnostics: list = []
    kept = structure_from_cif(str(path), moment_ions={"Fe1": "Fe3+"},
                              diagnostics=diagnostics)
    assert kept.phases[0].space_group == "P -1"
    assert not [d for d in diagnostics
                if d.code == "CIF_MAGNETIC_NUCLEAR_SETTING"]
    # and the same group with the site moved off the centre is not the parent:
    # its parent orbit would be two atoms and the file states one
    moved = tmp_path / "moved_p1.mcif"
    moved.write_text(path.read_text(encoding="utf-8").replace(
        "Fe1 Fe 0.00000 0.00000 0.00000", "Fe1 Fe 0.10000 0.20000 0.30000"),
        encoding="utf-8")
    assert structure_from_cif(
        str(moved), moment_ions={"Fe1": "Fe3+"}).phases[0].space_group == "P 1"


def test_an_underscore_screw_axis_symbol_normalises_before_the_lookup(tmp_path):
    """D4, synthetic. MAGNDATA writes a parent H-M symbol's screw-axis
    subscript with an underscore (``P 2_1/c``) -- a standard IUCr spelling --
    but gemmi's lookup table does not accept it verbatim: verified directly,
    ``gemmi.find_spacegroup_by_name("P 2_1/c")`` returns ``None`` while
    ``"P 21/c"`` resolves. Before the fix, ``resolve_nuclear_symmetry`` passed
    the file's own spelling straight through and raised "unrecognised space
    group" on every underscore-spelled entry (measured: ~108/1388 in-scope
    MAGNDATA entries, `P 2_1/n`, `P 2_1/c`, `P 2_1/a`, `P 2_1/m`, `P 2_1`).

    The operator list below is invented to isolate the normalisation
    mechanism -- not a claim about any real magnetic structure -- and is
    deliberately the plain four operations of ``P 1 21/c 1`` (b-unique) with
    time reversal ``+1`` throughout, a colourless (type I) description.
    """
    ops = ("x,y,z,+1", "-x,y+1/2,-z+1/2,+1", "-x,-y,-z,+1", "x,-y+1/2,z+1/2,+1")
    cent = ("x,y,z,+1",)
    path = _magcif(
        tmp_path, "p21c_synthetic", parent="P 2_1/c", it=14, bns="14.75",
        symbol="P 2_1/c", cell=(6.0, 7.0, 8.0, 90.0, 99.0, 90.0),
        operations=ops, centerings=cent,
        sites=("Fe1 Fe 0.10000 0.20000 0.30000 1",),
        moment_loop=_moment_loop([("Fe1", "0.0", "0.0", "2.00000", "0,0,mz")]),
    )
    structure = structure_from_cif(str(path), moment_ions={"Fe1": "Fe3+"})
    (phase,) = structure.phases
    assert phase.space_group.startswith("P 1 21/c 1")
    assert phase.atoms[0].moment.crystalaxis_z.value == pytest.approx(2.0)
    # negative control: an unrelated, genuinely unresolvable symbol still raises
    with pytest.raises(ValueError, match="unrecognised space group"):
        structure_from_cif(str(_magcif(
            tmp_path, "bad_symbol", parent="Q 9_9/z", it=14, bns="14.75",
            symbol="Q 9_9/z", cell=(6.0, 7.0, 8.0, 90.0, 99.0, 90.0),
            operations=ops, centerings=cent,
            sites=("Fe1 Fe 0.10000 0.20000 0.30000 1",),
            moment_loop=_moment_loop([("Fe1", "0.0", "0.0", "2.00000", "0,0,mz")]),
        )), moment_ions={"Fe1": "Fe3+"})


def test_tier_one_names_the_group_the_positions_refine_under(tmp_path):
    """Issue #457 ask 1: taking the parent is never silent. Cr₂WO₆'s magnetic
    group ``Pn'nm`` drops the parent's 4-fold, so its own family group is
    ``P n n m``, index 2 in ``P 4₂/m n m``; the positions refine under the
    parent, which carries constraints the file's operators do not impose, and
    ``CIF_MAGNETIC_NUCLEAR_GROUP`` names both groups, the index and the
    magnetic group. The file text is built here from the paper's operators."""
    diagnostics: list = []
    structure = structure_from_cif(str(_fixture(tmp_path, "Cr2WO6")),
                                   moment_ions=_IONS["Cr2WO6"],
                                   diagnostics=diagnostics)
    assert structure.phases[0].space_group == "P 42/m n m"
    (hit,) = [d for d in diagnostics if d.code == "CIF_MAGNETIC_NUCLEAR_GROUP"]
    assert hit.level == "info" and hit.value == 2.0
    assert ("positions refine under 'P 42/m n m', index 2 over the file's own "
            "'P n n m'; moments under the file's magnetic group") in hit.message
    assert "58.395" in hit.message
    assert not [d for d in diagnostics
                if d.code == "CIF_MAGNETIC_NUCLEAR_SETTING"]


def test_tier_one_at_index_one_says_the_two_groups_are_one(tmp_path):
    """LaMnO₃'s ``Pn'ma'`` is type III, so dropping time reversal gives back
    all of ``P n m a``: the parent *is* the file's own group, the index is 1,
    and the message says so rather than quoting an index."""
    diagnostics: list = []
    structure_from_cif(str(_fixture(tmp_path, "LaMnO3")),
                       moment_ions=_IONS["LaMnO3"], diagnostics=diagnostics)
    (hit,) = [d for d in diagnostics if d.code == "CIF_MAGNETIC_NUCLEAR_GROUP"]
    assert hit.value == 1.0
    assert "positions refine under 'P n m a', the file's own group;" in hit.message
    assert "index" not in hit.message.split(".mcif: ", 1)[1]
    # and "file" there is the same group, so it says the same thing
    again: list = []
    structure_from_cif(str(_fixture(tmp_path, "LaMnO3")),
                       moment_ions=_IONS["LaMnO3"], nuclear_group="file",
                       diagnostics=again)
    assert ([d.message for d in again if d.code.startswith("CIF_MAGNETIC_NUC")]
            == [hit.message])


def test_nuclear_group_file_takes_the_family_group_and_says_why(tmp_path):
    """Issue #457 ask 2, ``"file"``: the same Cr₂WO₆ text refines its
    positions under the file's own ``P n n m``, reported by the tier-2 code
    with the caller's choice as the reason, and the moments are untouched."""
    diagnostics: list = []
    path = str(_fixture(tmp_path, "Cr2WO6"))
    structure = structure_from_cif(path, moment_ions=_IONS["Cr2WO6"],
                                   nuclear_group="file",
                                   diagnostics=diagnostics)
    assert structure.phases[0].space_group == "P n n m"
    (hit,) = [d for d in diagnostics
              if d.code == "CIF_MAGNETIC_NUCLEAR_SETTING"]
    assert "positions refine under 'P n n m', the file's own group" in hit.message
    assert "nuclear_group='file'" in hit.message
    assert not [d for d in diagnostics
                if d.code == "CIF_MAGNETIC_NUCLEAR_GROUP"]
    auto = structure_from_cif(path, moment_ions=_IONS["Cr2WO6"])
    assert _stored(structure.phases[0]) == _stored(auto.phases[0])


def test_nuclear_group_parent_on_a_split_orbit_is_refused_by_name(tmp_path):
    """Issue #457 ask 2, ``"parent"``: forcing the parent onto a file whose
    magnetic group splits one parent orbit into two listed sites raises,
    naming the site, both multiplicities and what ``"auto"`` would have done,
    rather than falling through to the file's group."""
    path = _magcif(
        tmp_path, "split_p1_forced", parent="P -1", it=2, bns="1.1",
        symbol="P 1", cell=(5.0, 6.0, 7.0, 90.0, 90.0, 90.0),
        operations=("x,y,z,+1",), centerings=("x,y,z,+1",),
        sites=("Fe1 Fe 0.10000 0.20000 0.30000 1",
               "Fe2 Fe 0.90000 0.80000 0.70000 1"),
        moment_loop=_moment_loop([("Fe1", "0.0", "0.0", "2.00000", "mx,my,mz"),
                                  ("Fe2", "0.0", "0.0", "-2.00000", "mx,my,mz")]),
    )
    ions = {"Fe1": "Fe3+", "Fe2": "Fe3+"}
    with pytest.raises(magcif.MagCifError,
                       match=r"(?s)nuclear_group='parent'.*'P -1'.*'Fe1' has 2 "
                             r"images under 'P -1' and 1 under.*"
                             r"nuclear_group='auto' would have taken the "
                             r"file's own group 'P 1'"):
        structure_from_cif(str(path), moment_ions=ions, nuclear_group="parent")
    # and "parent" where the parent holds is exactly "auto"
    cr = str(_fixture(tmp_path, "Cr2WO6"))
    assert (structure_from_cif(cr, moment_ions=_IONS["Cr2WO6"],
                               nuclear_group="parent").phases[0].space_group
            == "P 42/m n m")


def test_nuclear_group_takes_only_its_three_words(tmp_path):
    with pytest.raises(ValueError, match="nuclear_group='family'"):
        structure_from_cif(str(_fixture(tmp_path, "Cr2WO6")),
                           nuclear_group="family")


def test_a_moment_outside_the_allowed_span_is_refused_through_the_reader(tmp_path):
    """WP-1327's schema refusal, asserted to fire **through** the reader.

    Cr1 in Cr2WO6 has an in-plane span ([1 0 0], [0 1 0] under 58.395), so a
    moment with a c component is outside it. The schema names the site and the
    allowed basis; what this test is for is that the reader does not somehow
    build around it — a reader that sanitised the moment would turn a
    contradictory file into a confident wrong answer.
    """
    loop = _moment_loop([("Cr1", "0.0", "2.35", "1.5", "mx,my,0")])
    with pytest.raises(ValueError, match="Cr1"):
        _read(tmp_path, "Cr2WO6", moment_loop=loop)


def test_a_moment_on_a_site_the_block_does_not_name_is_refused(tmp_path):
    """The whole magnetic contribution of a site, dropped because a label was
    misspelled, is the silent-drop failure in its purest form."""
    loop = _moment_loop([("Mn2", "3.7", "0.0", "0.0", "mx,my,mz")])
    with pytest.raises(magcif.MagCifError, match="not an _atom_site_label"):
        _read(tmp_path, "LaMnO3", moment_loop=loop)


def test_two_rows_for_one_site_are_refused(tmp_path):
    """Two moments on one site is a magnetic supercell stated in the parent
    cell — the same construct the supercell refusal is about, arriving by
    another route."""
    loop = _moment_loop([("Mn1", "3.7", "0.0", "0.0", "mx,my,mz"),
                         ("Mn1", "-3.7", "0.0", "0.0", "mx,my,mz")])
    with pytest.raises(magcif.MagCifError, match="two rows"):
        _read(tmp_path, "LaMnO3", moment_loop=loop)


def test_moments_with_no_operator_loop_are_refused(tmp_path):
    """A moment is only meaningful under a magnetic space group: it is the
    operator list that gives it an allowed subspace and an orbit."""
    text = _fixture(tmp_path, "LaMnO3").read_text(encoding="utf-8")
    text = re.sub(r"loop_\n_space_group_symop_magn_operation\.id\n"
                  r"_space_group_symop_magn_operation\.xyz\n(?:\d+ \S+\n)+", "",
                  text)
    path = tmp_path / "noops.mcif"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(magcif.MagCifError, match="operator list is not optional"):
        structure_from_cif(str(path))


def test_a_moment_row_with_no_moment_in_it_is_refused(tmp_path):
    """Reading it as zero would state a moment the file did not."""
    loop = "\nloop_\n_atom_site_moment.label\n_atom_site_moment.symmform\n" \
           "Mn1 mx,my,mz\n"
    with pytest.raises(magcif.MagCifError, match="no moment in any of the three"):
        _read(tmp_path, "LaMnO3", moment_loop=loop)


def test_a_magcif_with_no_resolvable_space_group_is_refused_by_name(tmp_path):
    """The operator list alone does not give the nuclear group: a type-III
    group is an index-2 subgroup of the parent, so the nuclear symmetry is
    strictly *higher* than the operators state, and inventing it from them
    would build a phase with the wrong absences and the wrong multiplicities.
    """
    text = _fixture(tmp_path, "ScMnO3").read_text(encoding="utf-8").replace(
        "_parent_space_group.name_H-M_alt  'P  6_3c  m'", "")
    path = tmp_path / "nosg.mcif"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(magcif.MagCifError, match="index-2 subgroup"):
        structure_from_cif(str(path))


# ===========================================================================
# 5. what the reader says it did
# ===========================================================================

def test_an_uncharged_type_symbol_is_reported_not_guessed(tmp_path):
    """MAGNDATA writes a bare ``Mn`` for a site that is chemically Mn3+, and
    <j0> for the two is a different curve. So the neutral atom is used, the
    substitution is reported, and the diagnostic names the ions of that element
    the table does carry."""
    diagnostics: list = []
    structure_from_cif(str(_fixture(tmp_path, "LaMnO3")),
                       diagnostics=diagnostics)
    (hit,) = [d for d in diagnostics
              if d.code == "CIF_MAGNETIC_ION_UNCHARGED"]
    assert "Mn1" in hit.message and "'Mn'" in hit.message
    assert "Mn3+" in hit.suggestion
    assert hit.where == ["phases.0.atoms.1.moment.ion"]
    # ...and stating it silences the diagnostic
    quiet: list = []
    structure_from_cif(str(_fixture(tmp_path, "LaMnO3")),
                       moment_ions={"Mn1": "Mn3+"}, diagnostics=quiet)
    assert not [d for d in quiet if d.code == "CIF_MAGNETIC_ION_UNCHARGED"]


def test_a_bare_lanthanide_with_no_neutral_row_defaults_to_its_majority_ion(
        tmp_path):
    """WP-1327 D1 / issue-magnetic-form-factor option (b).

    A bare ``Mn`` degrades to the *neutral atom's* form factor
    (``CIF_MAGNETIC_ION_UNCHARGED``, tested above) because this table carries
    a neutral ``Mn`` row. No lanthanide or actinide has one — Brown's table
    (ITC Vol C) carries only ionic curves for them — so a bare ``Dy`` refused
    outright before this fix. It now defaults one step further, to the
    majority oxidation state that is magnetic, and reports
    ``MAGNETIC_ION_ASSUMED`` rather than ``CIF_MAGNETIC_ION_UNCHARGED``, since
    this is a stronger substitution than the neutral-atom one.

    LaMnO3's own real, cited geometry and operator list are reused verbatim
    (only the magnetic site's type symbol and label are swapped to a bare
    ``Dy``) — this is a synthetic ion substitution to exercise the fallback
    in isolation, not a claim that any real Dy compound has this structure.
    ``moment_g=`` is supplied explicitly because a 4f ion's Landé g is a
    separate, unrelated requirement (``needs_explicit_g``) that this fix does
    not touch.
    """
    sites = ("La1 La 0.54900 0.25000 0.01000 1",
             "Dy1 Dy 0.00000 0.00000 0.00000 1",
             "O1 O 0.98600 0.25000 0.93000 1",
             "O2 O 0.30900 0.03900 0.22400 1")
    moment_loop = _moment_loop([("Dy1", "3.7(1)", "0.0(5)", "0.00000",
                                 "mx,my,mz")])
    path = _fixture(tmp_path, "LaMnO3", sites=sites, moment_loop=moment_loop)

    diagnostics: list = []
    structure = structure_from_cif(str(path), diagnostics=diagnostics,
                                   moment_g={"Dy1": 1.333})
    atom = structure.phases[0].atoms[1]
    assert atom.label == "Dy1"
    assert atom.moment.ion == "Dy3+"
    (hit,) = [d for d in diagnostics if d.code == "MAGNETIC_ION_ASSUMED"]
    assert "Dy1" in hit.message and "'Dy'" in hit.message and "Dy3+" in hit.message
    assert hit.level == "info"
    assert hit.where == ["phases.0.atoms.1.moment.ion"]
    assert "Dy1" in hit.suggestion and "moment_ions" in hit.suggestion
    # never both: the stronger diagnostic fires, not the neutral-atom one too
    assert not [d for d in diagnostics if d.code == "CIF_MAGNETIC_ION_UNCHARGED"]

    # ...and stating the ion explicitly beats the default, exactly as it beats
    # the neutral-atom fallback above
    quiet: list = []
    stated = structure_from_cif(str(path), moment_ions={"Dy1": "Dy2+"},
                                moment_g={"Dy1": 1.5}, diagnostics=quiet)
    assert stated.phases[0].atoms[1].moment.ion == "Dy2+"
    assert not [d for d in quiet if d.code == "MAGNETIC_ION_ASSUMED"]


def test_the_lanthanide_default_does_not_change_a_fixture_that_already_resolves(
        tmp_path):
    """Bit-identity: LaMnO3's own Mn site keeps resolving through the
    neutral-atom fallback, unchanged, because this table already carries a
    neutral ``Mn`` row — the new default only fires where today's code
    refuses outright."""
    diagnostics: list = []
    structure = structure_from_cif(str(_fixture(tmp_path, "LaMnO3")),
                                   diagnostics=diagnostics)
    assert structure.phases[0].atoms[1].moment.ion == "Mn"
    assert not [d for d in diagnostics if d.code == "MAGNETIC_ION_ASSUMED"]
    assert [d for d in diagnostics if d.code == "CIF_MAGNETIC_ION_UNCHARGED"]


def test_an_element_with_no_declared_default_still_refuses_exactly_as_before(
        tmp_path):
    """Negative control (element axis): a bare symbol this table has neither
    a neutral row nor a declared majority-ion default for (a 5d element, not
    a lanthanide/actinide) is refused by exactly the same message as before
    this fix — the new fallback table only widens the fallback that already
    existed, never adds a new one where none was designed."""
    sites = ("La1 La 0.54900 0.25000 0.01000 1",
             "Re1 Re 0.00000 0.00000 0.00000 1",
             "O1 O 0.98600 0.25000 0.93000 1",
             "O2 O 0.30900 0.03900 0.22400 1")
    moment_loop = _moment_loop([("Re1", "3.7(1)", "0.0(5)", "0.00000",
                                 "mx,my,mz")])
    path = _fixture(tmp_path, "LaMnO3", sites=sites, moment_loop=moment_loop)
    with pytest.raises(ValidationError,
                       match=r"no magnetic form factor for 'Re'"):
        structure_from_cif(str(path))


def test_ce_declares_ce3_but_the_table_only_carries_ce2_so_it_still_refuses(
        tmp_path):
    """Negative control (declared-but-unresolvable axis): Ce is declared as
    Ce3+ in the assumed-ion table (Ce4+ is 4f0, non-magnetic), but Brown's own
    ⟨j0⟩/⟨j2⟩ rows carry Ce2+ only. The declared default must not silently
    substitute the *wrong* ion (Ce2+) just because it exists in the table --
    a bare Ce site stays refused, and the refusal names Ce3+, matching what
    was actually asked for."""
    sites = ("La1 La 0.54900 0.25000 0.01000 1",
             "Ce1 Ce 0.00000 0.00000 0.00000 1",
             "O1 O 0.98600 0.25000 0.93000 1",
             "O2 O 0.30900 0.03900 0.22400 1")
    moment_loop = _moment_loop([("Ce1", "3.7(1)", "0.0(5)", "0.00000",
                                 "mx,my,mz")])
    path = _fixture(tmp_path, "LaMnO3", sites=sites, moment_loop=moment_loop)
    with pytest.raises(ValidationError,
                       match=r"no magnetic form factor for 'Ce'"):
        structure_from_cif(str(path))


def _bare_dy_fixture(tmp_path):
    sites = ("La1 La 0.54900 0.25000 0.01000 1",
             "Dy1 Dy 0.00000 0.00000 0.00000 1",
             "O1 O 0.98600 0.25000 0.93000 1",
             "O2 O 0.30900 0.03900 0.22400 1")
    moment_loop = _moment_loop([("Dy1", "3.7(1)", "0.0(5)", "0.00000",
                                 "mx,my,mz")])
    return _fixture(tmp_path, "LaMnO3", sites=sites, moment_loop=moment_loop)


def test_a_bare_lanthanide_with_no_stated_g_defaults_its_lande_g_too(tmp_path):
    """WP-1327 D-lande-g: the gate this whole brief exists for. Before this
    fix, resolving a bare Dy1 to Dy3+ (the test above) still needed
    ``moment_g=`` supplied explicitly — ``Phase``'s own validator calls
    ``resolve_g(atom.moment.ion, atom.moment.g)`` and a lanthanide/actinide
    ion with no g raises (issue #257 A5), and magCIF has no item for g any
    more than it has one for the ion. So a bare Dy1 with *no* ``moment_g=``
    used to refuse one line later than before, never load.

    Now the same "assume it from the physics rather than refuse" choice that
    resolved the ion (``MAGNETIC_ION_ASSUMED``) extends one step further to
    its Landé g: Dy3+'s free-ion Hund's-rule g_J = 4/3 is used, reported as
    ``LANDE_G_ASSUMED``, and the structure loads.
    """
    path = _bare_dy_fixture(tmp_path)
    diagnostics: list = []
    structure = structure_from_cif(str(path), diagnostics=diagnostics)
    atom = structure.phases[0].atoms[1]
    assert atom.moment.ion == "Dy3+"
    assert atom.moment.g == pytest.approx(4 / 3)

    (ion_hit,) = [d for d in diagnostics if d.code == "MAGNETIC_ION_ASSUMED"]
    (g_hit,) = [d for d in diagnostics if d.code == "LANDE_G_ASSUMED"]
    assert g_hit.level == "info"
    assert g_hit.where == ["phases.0.atoms.1.moment.g"]
    assert g_hit.value == pytest.approx(4 / 3)
    assert "Dy1" in g_hit.message and "Dy3+" in g_hit.message
    assert "Dy1" in g_hit.suggestion and "moment_g" in g_hit.suggestion
    del ion_hit  # only asserted to exist alongside g_hit


def test_stating_g_explicitly_beats_the_lande_default(tmp_path):
    """Negative control (g-stated axis): supplying ``moment_g=`` for the same
    bare-Dy site silences ``LANDE_G_ASSUMED`` and keeps the caller's own
    value — exactly as stating the ion beats ``MAGNETIC_ION_ASSUMED`` one
    field over. This is also the fixture the pre-existing
    ``test_a_bare_lanthanide_with_no_neutral_row_defaults_to_its_majority_ion``
    already exercises with ``moment_g={"Dy1": 1.333}``; this test asserts the
    diagnostic side of that same call explicitly."""
    path = _bare_dy_fixture(tmp_path)
    diagnostics: list = []
    structure = structure_from_cif(str(path), moment_g={"Dy1": 1.5},
                                   diagnostics=diagnostics)
    atom = structure.phases[0].atoms[1]
    assert atom.moment.ion == "Dy3+"
    assert atom.moment.g == 1.5
    assert not [d for d in diagnostics if d.code == "LANDE_G_ASSUMED"]
    # the ion default still fires: only g was stated
    assert [d for d in diagnostics if d.code == "MAGNETIC_ION_ASSUMED"]


def test_an_explicitly_stated_ion_with_no_g_still_refuses_exactly_as_before(
        tmp_path):
    """Negative control (ion-stated axis) — the D2 finding this brief exists
    to close half of: an explicitly *stated* ion (``moment_ions={"Dy1":
    "Dy3+"}``) is not an assumed ion, so ``LANDE_G_ASSUMED`` never fires for
    it and the pre-existing, unrelated g requirement (issue #257 A5) is
    unchanged — a caller who names the ion but not g still gets the
    ``resolve_g`` refusal naming it, byte for byte, because stating one fact
    and not the other is the caller's own gap, not the shape this default
    closes."""
    path = _bare_dy_fixture(tmp_path)
    with pytest.raises(ValidationError, match="4f/5f ion"):
        structure_from_cif(str(path), moment_ions={"Dy1": "Dy3+"})


def test_the_lande_g_default_does_not_change_a_fixture_that_already_resolves(
        tmp_path):
    """Bit-identity: LaMnO3's own Mn3+ site needs no g at all (Mn is a 3d
    ion, spin-only g = 2, ``needs_explicit_g`` is False for it), so this
    fix — which only ever fires for an ion :func:`resolve_assumed_ion`
    itself produced — never touches it. Same fixture and assertion shape as
    ``test_the_lanthanide_default_does_not_change_a_fixture_that_already_resolves``
    one rank up, for the g field specifically."""
    diagnostics: list = []
    structure = structure_from_cif(str(_fixture(tmp_path, "LaMnO3")),
                                   diagnostics=diagnostics)
    assert structure.phases[0].atoms[1].moment.g is None
    assert not [d for d in diagnostics if d.code == "LANDE_G_ASSUMED"]


@pytest.mark.parametrize("key,expected", [("LaMnO3", 3), ("Cr2WO6", 2),
                                          ("YMnO3", 1), ("ScMnO3", 2)])
def test_symmform_agrees_with_the_derived_subspace_on_every_fixture(
        tmp_path, key, expected):
    """``symmform`` is the producer's own constraint and the operators are
    rietx's, and the two agreeing on four published structures is evidence
    about the fixtures that neither side gives alone.

    It is a dimension comparison, which root ``CLAUDE.md`` warns is the weak
    form of a span test — and the right one here for a reason that does not
    apply there: the two sides come from *independent* sources, the file's
    producer and this package's operator algebra, so agreement is information
    about the file. The moment's own membership of the derived span is checked
    exactly, by the schema, one layer up.

    ``YMnO3``'s ``mx,2mx,0`` is the case that makes this more than a token
    count: one free parameter over two non-zero components, matching the
    derived basis [[1 2 0]].
    """
    diagnostics: list = []
    structure_from_cif(str(_fixture(tmp_path, key)), moment_ions=_IONS[key],
                       diagnostics=diagnostics)
    (hit,) = [d for d in diagnostics if d.code == "CIF_MAGNETIC_SYMMFORM"]
    assert hit.level == "info", hit.message
    assert hit.value == expected
    assert f"has {expected}" in hit.message


def test_a_symmform_that_disagrees_with_the_operators_warns(tmp_path):
    """...and warns rather than refuses, because the operators are the model
    (decision D-4) and the file's symmform is a record. A warning is what says
    the two sources disagree about the same site."""
    loop = _moment_loop([("Cr1", "0.0", "2.35", "0.0", "mx,my,mz")])
    diagnostics: list = []
    structure_from_cif(str(_fixture(tmp_path, "Cr2WO6", moment_loop=loop)),
                       diagnostics=diagnostics)
    (hit,) = [d for d in diagnostics if d.code == "CIF_MAGNETIC_SYMMFORM"]
    assert hit.level == "warning"
    assert "3 free parameters" in hit.message and "has 2" in hit.message


def test_a_magnitude_esd_the_structure_cannot_hold_is_named(tmp_path):
    """``magnitude_su`` is the esd of the *modulus*, which is a property of the
    fit and not of the structure — WP-1327 keeps it in
    ``FitReport.magnetic[i].magnitude_esd`` — so a Structure has nowhere to put
    it and the read says so rather than dropping it."""
    loop = _moment_loop(
        [("Mn1", "3.70000", "0.00000", "0.00000", "3.70000", "0.09000")],
        tags=("crystalaxis_x", "crystalaxis_y", "crystalaxis_z",
              "magnitude", "magnitude_su"))
    diagnostics: list = []
    structure_from_cif(str(_fixture(tmp_path, "LaMnO3", moment_loop=loop)),
                       diagnostics=diagnostics)
    (hit,) = [d for d in diagnostics
              if d.code == "CIF_MAGNETIC_MAGNITUDE_ESD_NOT_STORED"]
    assert hit.value == pytest.approx(0.09)
    assert "FitReport.magnetic" in hit.suggestion


# ===========================================================================
# 6. nothing changes for a file with no magnetic block
# ===========================================================================

_NUCLEAR_CIFS = ("cod_1000055.cif", "fluorapatite.cif")


@pytest.mark.parametrize("name", _NUCLEAR_CIFS)
@pytest.mark.parametrize("aniso", [False, True])
def test_a_nuclear_cif_reads_and_writes_bit_identically(tmp_path, name, aniso):
    """The negative control for the whole rung: a file with no magnetic block
    must take exactly the path it always did, and the writer must emit no
    magnetic tag for a phase with no ``magnetic_symmetry``.

    Measured against the parent commit as well, once, and recorded in the
    handover report: all four shipped CIF fixtures hash identically on the
    structure, the diagnostics and the written bytes. What is asserted *here*
    is the environment-independent half — that the pair is a fixed point and
    that no magnetic tag appears — because a hash pinned in a test would be a
    claim about this machine's gemmi and pydantic rather than about the code.
    """
    source = Path(__file__).parent / "data" / name
    first = structure_from_cif(str(source), aniso=aniso)
    assert first.phases[0].magnetic_symmetry is None
    assert all(a.moment is None for a in first.phases[0].atoms)
    out1 = tmp_path / "a.cif"
    structure_to_cif(first, str(out1))
    text = out1.read_text(encoding="utf-8")
    assert "magn" not in text and "_atom_site_moment" not in text
    second = structure_from_cif(str(out1), aniso=aniso)
    out2 = tmp_path / "b.cif"
    structure_to_cif(second, str(out2))
    assert out1.read_bytes() == out2.read_bytes()


# ===========================================================================
# 7. the TOPAS stance
# ===========================================================================

_TOPAS_MAG = """\
str
   phase_name "Cr2WO6"
   space_group "P 42/m n m"
   mag_space_group "P n' n m"
   a 4.58200 b 4.58200 c 8.87000
   scale 0.0001
   site Cr1 x 0 y 0 z 0.33450 occ Cr+3 1 beq 0.3 mlx 0 mly @ 2.35 mlz 0
   site W1  x 0 y 0 z 0       occ W+6  1 beq 0.3
   site O1  x 0.30300 y 0.30300 z 0       occ O-2 1 beq 0.5
   site O2  x 0.30600 y 0.30600 z 0.34000 occ O-2 1 beq 0.5
"""


def _inp(tmp_path, text, name="mag.inp") -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_the_registry_splits_the_magnetic_construct_by_keyword():
    """WP-1328's coverage task, asserted as the table rather than as behaviour.

    The one ``magnetic structure`` row at ``REFUSED`` over eight keywords is
    gone, and what replaces it is four stances that each say something
    different:

    * the site moments and the Landé g are **READ** (the build is behind
      ``to_structure(magnetic_symmetry=...)``, the way ``adps`` is behind
      ``aniso=True``);
    * ``mag_space_group`` is **READ**: a BNS or OG number is the group (and a
      ``str`` stating no ``space_group`` takes its nuclear group from it),
      while a Shubnikov *symbol*, which no dependency here parses, is carried
      as metadata and the build refuses a moment-bearing phase by name;
    * ``mag_only``/``mag_only_for_mag_sites`` stay **REFUSED**, now with the
      argument they always needed — a phase with no nuclear structure factor
      has no shape in WP-1327's model, which is a moment on a nuclear phase
      sharing one scale;
    * ``mag_atom_out`` is **IGNORED**, beside ``atom_out``, because an output
      directive carries nothing to read. (WP-1328's task list puts it in the
      read group; there is nothing in it to read, and the deviation is in the
      handover report.)
    """
    assert coverage.stance("mlx") is coverage.Stance.READ
    assert coverage.stance("mly") is coverage.Stance.READ
    assert coverage.stance("mlz") is coverage.Stance.READ
    assert coverage.stance("mg") is coverage.Stance.READ
    assert coverage.stance("mag_space_group") is coverage.Stance.READ
    assert coverage.stance("mag_only") is coverage.Stance.REFUSED
    assert coverage.stance("mag_only_for_mag_sites") is coverage.Stance.REFUSED
    assert coverage.stance("mag_atom_out") is coverage.Stance.IGNORED
    assert coverage.feature("mag_atom_out") is coverage.feature("atom_out")
    # a READ keyword is not scanned, because finding it changes nothing
    assert not {"mlx", "mly", "mlz", "mg"} & coverage.SCANNED
    assert {"mag_only", "mag_only_for_mag_sites"} <= coverage.SCANNED
    assert "mag_space_group" not in coverage.SCANNED
    # and the sentence that is now false is gone from the whole registry
    assert not [f for f in coverage.FEATURES
                if "no magnetic model" in f.why]


def test_a_topas_magnetic_phase_reads_with_the_moments_in_place(tmp_path):
    """The acceptance bullet: the moments arrive, and so does the stance."""
    diagnostics: list = []
    model = read_topas_inp(_inp(tmp_path, _TOPAS_MAG), diagnostics=diagnostics)
    (phase,) = model.phases
    assert phase.mag_space_group == "P n' n m"
    assert phase.space_group == "P 42/m n m"
    assert phase.sites[0].moment == {"mlx": 0.0, "mly": 2.35, "mlz": 0.0}
    assert phase.sites[0].vary["mly"] is True
    assert [s.moment for s in phase.sites[1:]] == [None, None, None]
    assert not model.coverage.reported     # every construct here is read

    built: list = []
    structure = topas_to_structure(model, magnetic_symmetry="58.395",
                                   diagnostics=built)
    (out,) = structure.phases
    assert out.magnetic_symmetry.bns_number == "58.395"
    # `mly 2.35` is fractional: 2.35 of the 4.582 Å b edge, in mu_B
    assert out.atoms[0].moment.values() == pytest.approx((0.0, 2.35 * 4.582,
                                                          0.0))
    assert out.atoms[0].moment.ion == "Cr3+"    # `occ Cr+3` normalises to it
    assert out.atoms[0].moment.vary is True
    codes = [d.code for d in built]
    assert "TOPAS_MOMENT_CONVENTION" in codes
    assert "TOPAS_MOMENT_ION_UNCHARGED" not in codes    # the file wrote Cr+3


def test_a_topas_moment_with_no_group_supplied_is_refused_by_name(tmp_path):
    """The refusal that survives WP-1328, and the real gap behind it.

    TOPAS states the group as a Shubnikov **symbol** and M-5 refuses symbols by
    name — spglib exposes UNI, BNS and OG *numbers* and no symbol table, and
    guessing one is how a fit lands under the wrong group. So the moments read,
    the symbol is metadata, and building refuses until a group is supplied.
    """
    model = read_topas_inp(_inp(tmp_path, _TOPAS_MAG))
    with pytest.raises(TopasInpError) as excinfo:
        topas_to_structure(model)
    message = str(excinfo.value)
    assert "Shubnikov" in message
    assert "Cr2WO6" in message and "'Cr1'" in message
    assert "P n' n m" in message                 # the symbol the file wrote
    assert "magnetic_symmetry=" in message       # and the way out


def test_a_topas_mag_only_phase_is_refused_by_name(tmp_path):
    """``mag_only`` is a phase with no nuclear structure factor, and WP-1327's
    model is a moment on a nuclear phase sharing one scale — so importing its
    sites as an ordinary phase would add the nuclear intensity the file says is
    not there."""
    text = _TOPAS_MAG.replace("mlz 0", "mlz 0 mag_only")
    model = read_topas_inp(_inp(tmp_path, text))
    (hit,) = model.coverage.refused
    assert hit.feature.name == "magnetic-only phase"
    with pytest.raises(TopasInpError, match="no nuclear structure factor"):
        topas_to_structure(model, magnetic_symmetry="58.395")


def test_a_magnetic_symmetry_for_a_phase_that_states_no_moment_is_refused(
        tmp_path):
    """A magnetic space group on a phase with no moment constrains nothing and
    contributes nothing, so storing it would be a claim the file never made."""
    text = _TOPAS_MAG.replace(" mlx 0 mly @ 2.35 mlz 0", "")
    model = read_topas_inp(_inp(tmp_path, text))
    assert topas_to_structure(model).phases[0].magnetic_symmetry is None
    with pytest.raises(TopasInpError,
                       match="no phase being built states a site moment"):
        topas_to_structure(model, magnetic_symmetry="58.395")
    with pytest.raises(TopasInpError, match="state no mlx/mly/mlz"):
        topas_to_structure(model, magnetic_symmetry={"Cr2WO6": "58.395"})


def test_one_spec_for_two_magnetic_phases_is_refused(tmp_path):
    """Which phase a single group belongs to is not a reader's guess."""
    text = _TOPAS_MAG + _TOPAS_MAG.replace('"Cr2WO6"', '"Cr2WO6_second"')
    model = read_topas_inp(_inp(tmp_path, text))
    with pytest.raises(TopasInpError, match="Which phase it belongs to"):
        topas_to_structure(model, magnetic_symmetry="58.395")
    built = topas_to_structure(model, magnetic_symmetry={
        "Cr2WO6": "58.395", "Cr2WO6_second": "58.395"})
    assert all(p.magnetic_symmetry is not None for p in built.phases)


def test_a_stated_moment_component_that_cannot_be_resolved_refuses(tmp_path):
    """The rule ``beq``, ``x`` and the ADP tensor already follow, extended to
    the moment: substituting 0 for a stated ``mlx`` is a moment pointing
    somewhere else, and |F_m|^2 is quadratic in it, so the error does not
    announce itself as an obviously broken pattern."""
    text = _TOPAS_MAG.replace("mly @ 2.35", "mly = Get(nothing);")
    with pytest.raises(TopasInpError, match="could not resolve mly"):
        read_topas_inp(_inp(tmp_path, text))


#: A ``str`` in the syntax of the Durham LaMnO₃ magnetic tutorial's
#: ``maglamno3_riet_04.inp`` (an ISODISTORT P1 export): ``mag_space_group 1.1``
#: and **no** ``space_group``, the moment resolved through a ``prm`` equation
#: carrying the equation's value after ``;:``. Synthetic: the tutorial is named
#: for its syntax only, and every number here is this file's own (the tutorial
#: states no licence). The ``MM_CrystalAxis_Display`` line TOPAS prints beside
#: the moment is left out until a TOPAS run of this str supplies it.
_TOPAS_TUTORIAL_P1 = """\
str
   phase_name "LaMnO3_P1"
   mag_space_group 1.1
   prm  Mn_1_dmlx  0.06810
   prm  Mn_1_mlx  = 0  + Mn_1_dmlx;:  0.06810`
   prm  Mn_1_mly  = 0  + 0.60240;:  0.60240`
   prm  Mn_1_mlz  = 0  + 0.04130;:  0.04130`
   a     5.61240
   b     5.83170
   c     7.74410
   al   90.00000
   be   90.00000
   ga   90.00000
   scale 0.01
   site La_1  x 0.98710 y 0.05230 z 0.25000 occ La 1 beq 1.0
   site Mn_1  x 0.00000 y 0.50000 z 0.00000 occ Mn 1 beq 1.0
      mlx = Mn_1_mlx; mly = Mn_1_mly; mlz = Mn_1_mlz;
   site O1_1  x 0.08120 y 0.48150 z 0.25000 occ O 1 beq 1.0
"""

#: mlx·a, mly·b, mlz·c for Mn_1 to five decimals, crystal-axis mu_B. Our
#: arithmetic, not a TOPAS output: the display line waits for a TOPAS run.
_TUTORIAL_DISPLAY = (0.38220, 3.51302, 0.31983)


def test_a_topas_moment_is_fractional_and_matches_the_tutorials_display(
        tmp_path):
    """``mlx mly mlz`` are fractional-basis components, so the stored
    crystal-axis moment is each times its edge — and equals the
    ``MM_CrystalAxis_Display`` values TOPAS printed beside them, to the
    precision both were printed at.

    The Technical Reference § 13 states it twice (Fmagc = L·Fmag with
    m = {mlx, mly, mlz}; ``MM_CrystalAxis_Display`` as mxc = mlx·a) and the
    tutorial's numbers agree. The old crystal-axis reading stored
    (0.06810, 0.60240, 0.04130) and is 2.9 μ_B off here. Five-decimal ``mlx``
    times an edge is good to 0.5e-5·|edge|, the display to 0.5e-5 more.
    """
    diagnostics: list = []
    model = read_topas_inp(_inp(tmp_path, _TOPAS_TUTORIAL_P1),
                           diagnostics=diagnostics)
    (phase,) = model.phases                 # a `mag_space_group`-only str reads
    assert phase.space_group == "" and phase.mag_space_group == "1.1"
    built: list = []
    structure = topas_to_structure(model, diagnostics=built)
    (out,) = structure.phases
    assert out.magnetic_symmetry.bns_number == "1.1"
    assert out.space_group == "P 1"         # derived: the family group of 1.1
    mn = next(a for a in out.atoms if a.label == "Mn_1")
    edges = (5.61240, 5.83170, 7.74410)
    for got, shown, edge in zip(mn.moment.values(), _TUTORIAL_DISPLAY, edges):
        assert abs(got - shown) <= 0.5e-5 * edge + 0.5e-5, (got, shown)
    codes = {d.code: d for d in built}
    assert "TOPAS_MOMENT_CONVENTION" in codes
    assert "fractional" in codes["TOPAS_MOMENT_CONVENTION"].message
    assert "not yet measured" in codes["TOPAS_MOMENT_CONVENTION"].suggestion
    read = codes["TOPAS_MAGNETIC_GROUP_READ"]
    assert read.where == ["phases.0.magnetic_symmetry", "phases.0.space_group"]
    assert "'P 1'" in read.message


def test_a_topas_moment_on_an_oblique_cell_is_a_per_axis_scale_not_a_rotation(
        tmp_path):
    """On a monoclinic cell the stored crystal-axis vector is
    ``(mlx·|a|, mly·|b|, mlz·|c|)``, and its Cartesian form is exactly
    TOPAS's ``L·m`` — the lattice matrix applied to (mlx, mly, mlz).

    The oblique cell is what separates the readings: the crystal-axis one
    (the old reader) stores (0.4, −0.3, 0.3), and a Cartesian-components one
    would rotate the vector off the per-axis scale. Both fail here.
    """
    text = ('str\n phase_name "mono"\n mag_space_group 1.1\n'
            ' a 5.2 b 6.9 c 8.4 al 90 be 115 ga 90\n scale 0.01\n'
            ' site Mn1 x 0.13 y 0.27 z 0.41 occ Mn+2 1 beq 0.5 '
            'mlx 0.4 mly -0.3 mlz 0.3\n')
    structure = topas_to_structure(read_topas_inp(_inp(tmp_path, text)))
    (out,) = structure.phases
    stored = np.array(out.atoms[0].moment.values())
    np.testing.assert_allclose(stored, [0.4 * 5.2, -0.3 * 6.9, 0.3 * 8.4],
                               rtol=0, atol=1e-12)
    from rietx.crystallography.adp import cartesian_basis

    cell = (5.2, 6.9, 8.4, 90.0, 115.0, 90.0)
    np.testing.assert_allclose(
        moment_to_cartesian(stored, cell),
        cartesian_basis(*cell) @ np.array([0.4, -0.3, 0.3]),
        rtol=0, atol=1e-12)
    assert moment_magnitude(stored, cell) == pytest.approx(3.2452, abs=1e-4)


def test_a_mag_space_group_only_phase_with_a_symbol_is_refused_by_name(
        tmp_path):
    """No ``space_group``, and a ``mag_space_group`` that is a *symbol*: there
    is no operator list to derive the nuclear group from, so the build refuses
    naming the phase and the symbol rather than guessing a group — whether or
    not the phase states a moment."""
    text = ('str\n phase_name "bare"\n mag_space_group "P n\' m a\'"\n'
            ' a 5.7 b 7.6 c 5.5\n scale 0.01\n'
            ' site Mn1 x 0 y 0 z 0 occ Mn+3 1 beq 0.5\n')
    model = read_topas_inp(_inp(tmp_path, text))
    assert model.phases[0].space_group == ""
    with pytest.raises(TopasInpError, match="states no space_group") as exc:
        topas_to_structure(model)
    assert "P n' m a'" in str(exc.value) and "'bare'" in str(exc.value)
    # a str stating neither group is still a skipped block, as before
    neither = read_topas_inp(_inp(tmp_path, text.replace(
        ' mag_space_group "P n\' m a\'"\n', ""), name="neither.inp"))
    assert not neither.phases
    (skipped,) = neither.skipped_blocks
    assert skipped.lacked == "space_group"


def test_mag_only_for_mag_sites_stays_refused_in_the_tutorials_two_str_idiom(
        tmp_path):
    """``mag_only_for_mag_sites`` switches a site's nuclear term off, and the
    file that uses it (the Durham tutorial's ``maglamno3_riet_02.inp`` layout)
    states the nuclear structure in one ``str`` and restates the magnetic site
    in a second, ``mag_space_group``-only one carrying the keyword. Both now
    read as phases; *building* them without the keyword would count Mn's
    nuclear scattering twice, so it is refused, not dropped with a
    diagnostic."""
    text = ('str\n phase_name "LaMnO3"\n space_group Pnma\n'
            ' a 5.8120 b 7.7030 c 5.5810\n scale 0.01\n'
            ' site Mn x 0 y 0 z 0 occ Mn 1 beq 1.0\n'
            'str\n phase_name "LaMnO3_magnetic"\n mag_only_for_mag_sites\n'
            ' a 5.8120 b 7.7030 c 5.5810\n mag_space_group 62.448\n'
            ' site Mn x 0 y 0 z 0 occ Mn 1 beq 1.0\n'
            ' mlx @ 0.66120 mly @ 0.03140 mlz @ 0.01870\n scale 0.01\n')
    model = read_topas_inp(_inp(tmp_path, text))
    assert [p.name for p in model.phases] == ["LaMnO3", "LaMnO3_magnetic"]
    (hit,) = model.coverage.refused
    assert hit.feature.name == "magnetic-only phase"
    with pytest.raises(TopasInpError, match="twice"):
        topas_to_structure(model)


# ===========================================================================
# 8. the completeness oracle: nothing magnetic is dropped in silence
# ===========================================================================

#: Every magnetic keyword and tag the readers of this package know about,
#: derived from the declarations rather than restated — the vocabulary of
#: :mod:`rietx.crystallography.magcif` plus the magnetic rows of
#: :mod:`rietx.io.projects.coverage` — so a construct added to either shows up
#: here without anyone remembering to add it.
def _magnetic_vocabulary() -> set[str]:
    tags = set(magcif.READ_TAGS) | set(magcif.PRIVATE_TAGS)
    tags |= {tag for tag, _what in magcif.REFUSED_TAGS}
    keywords = {kw for feat in coverage.FEATURES for kw in feat.keywords
                if kw.startswith("mag") or kw in ("mlx", "mly", "mlz", "mg")}
    return tags | keywords


def test_no_shipped_fixture_carries_a_magnetic_construct_without_a_stance():
    """The oracle the acceptance asks for: **no reader drops a magnetic
    construct silently**, asserted over the whole shipped fixture set with a
    grep-derived list.

    Two halves, and the second is why this is a control and not a tautology:

    1. every magnetic token found in any shipped fixture must be one this
       package declares a stance on — a tag in
       :data:`~rietx.crystallography.magcif.READ_TAGS` or its refused list, or
       a keyword with a row in :mod:`~rietx.io.projects.coverage`;
    2. the shipped set is *recorded*, so if someone adds a magnetic fixture the
       count changes and this test says so. Today it is zero, which is exactly
       what makes the synthetic fixtures above the only coverage of the magnetic
       readers — a fact worth failing on rather than assuming.
    """
    root = Path(__file__).parent / "data"
    vocabulary = _magnetic_vocabulary()
    #: tokens that *look* magnetic in a data file and are not: `mag` appears in
    #: "magnitude", "image", "magnesium"; the scan is anchored to a CIF tag or
    #: a TOPAS/FullProf keyword at a token boundary, and every hit has to have
    #: a stance.
    token = re.compile(r"(?m)(?:^\s*(_[A-Za-z0-9_.\-]*magn[A-Za-z0-9_.\-]*)"
                       r"|\b(mag_[a-z_]+|ml[xyz]|mg)\b)")
    found: dict[str, set[str]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_dir() or path.suffix in (".xye", ".fxye", ".xy", ".dat",
                                            ".raw", ".png"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for match in token.finditer(text):
            hit = match.group(1) or match.group(2)
            found.setdefault(hit, set()).add(str(path.relative_to(root)))
    undeclared = {hit: sorted(where) for hit, where in found.items()
                  if hit not in vocabulary
                  and not any(hit.startswith(t) for t in vocabulary)}
    assert not undeclared, (
        f"magnetic constructs in shipped fixtures with no declared stance: "
        f"{undeclared}. Add a row to io/projects/coverage.py or to "
        f"crystallography/magcif.py's tag lists — a construct with no stance "
        f"is one that is dropped in silence.")
    assert not found, (
        f"a shipped fixture now carries a magnetic construct ({sorted(found)}) "
        f"where none did when WP-1328 landed. That is not a failure — it is "
        f"this test saying the magnetic readers now have a shipped fixture and "
        f"the synthetic ones above are no longer their only coverage. Update "
        f"this assertion, and point the round-trip tests at the new file.")


def test_every_written_magnetic_tag_is_one_the_reader_takes_back(tmp_path):
    """The writer's vocabulary is a subset of the reader's, checked on a real
    file rather than by comparing two lists.

    A tag written and not read is a field lost on the next round trip, and the
    two lists agreeing on paper is not evidence that the code uses them.
    """
    structure = _read(tmp_path, "Cr2WO6")
    out = tmp_path / "w.cif"
    structure_to_cif(structure, str(out))
    written = {t for t in re.findall(r"(?m)^\s*(_[A-Za-z0-9_.\-]+)",
                                     out.read_text(encoding="utf-8"))
               if "magn" in t or "moment" in t or "propagation" in t}
    assert written, "the writer emitted no magnetic tag at all"
    readable = set(magcif.READ_TAGS) | set(magcif.PRIVATE_TAGS) | {
        # the loop `id` columns, which are keys and carry no model state
        "_space_group_symop_magn_operation.id",
        "_space_group_symop_magn_centering.id",
    }
    assert written <= readable, sorted(written - readable)
    assert set(magcif.WRITTEN_TAGS) >= written - set(magcif.PRIVATE_TAGS)


# ===========================================================================
# 9. the refined write-back: where the modulus esd goes, and what a fixed
#    precision costs
# ===========================================================================

def test_a_refined_moment_writes_its_modulus_esd_and_survives_the_round_trip(
        tmp_path):
    """The exporter's hook, on the numbers WP-1327's Cr2WO6 fit actually gives.

    A refined moment's components carry **no** ``stderr`` by design (WP-1327:
    they are written back from the DOFs and the DOF that carries the esd is the
    modulus), so ``_atom_site_moment.magnitude_su`` is where the uncertainty
    goes and ``write_refinement_cif`` supplies it from
    ``phases.i.atoms.j.moment.dof0`` — the one writer, never recomputed.

    The precision claim is asserted rather than hoped for: 2.0784535703041347
    is written as the shortest text for its double (``_moment_number``), so
    the value that comes back is the one that was refined, bit for bit, and so
    is the modulus esd — and every subsequent read and write is exact too.
    """
    import gemmi

    from rietx.crystallography.cif import write_structure_block

    fitted = 2.0784535703041347
    esd = 0.06551
    structure = _read(tmp_path, "Cr2WO6")
    phase = structure.phases[0]
    atom = phase.atoms[0]
    assert atom.label == "Cr1"
    phase = phase.model_copy(update={"atoms": [
        atom.model_copy(update={"moment": atom.moment.model_copy(update={
            "crystalaxis_x": rx.Parameter(value=-1.1419873752181259e-06,
                                          vary=True, unit="mu_B"),
            "crystalaxis_y": rx.Parameter(value=fitted, vary=True,
                                          unit="mu_B"),
            "crystalaxis_z": rx.Parameter(value=0.0, vary=True, unit="mu_B"),
        })}), *phase.atoms[1:]]})

    doc = gemmi.cif.Document()
    block = doc.add_new_block("refined")
    write_structure_block(block, phase, moment_magnitude_esds={"Cr1": esd})
    out = tmp_path / "refined.cif"
    doc.write_file(str(out))
    assert "_atom_site_moment.magnitude_su" in out.read_text(encoding="utf-8")

    diagnostics: list = []
    first = structure_from_cif(str(out), diagnostics=diagnostics)
    got = first.phases[0].atoms[0].moment
    assert got.crystalaxis_y.value == fitted
    assert got.crystalaxis_y.stderr is None      # the components never had one
    (named,) = [d for d in diagnostics
                if d.code == "CIF_MAGNETIC_MAGNITUDE_ESD_NOT_STORED"]
    assert named.value == esd

    # ...and from here on it is exact
    out2 = tmp_path / "again.cif"
    structure_to_cif(first, str(out2))
    second = structure_from_cif(str(out2))
    assert _stored(first.phases[0]) == _stored(second.phases[0])


#: A moment along YMnO3's tied ``mx,2mx,0`` direction whose five-decimal
#: rounding leaves the line: (0.1456956, 0.2913912) prints ``0.14570 0.29139``,
#: 4e-6 μ_B off it, past ``in_span``'s 1e-6.  Synthetic — the *shape* of the
#: case a solver's own ``write_magcifs`` output was refused on (2026-09-23).
_TIED_X = 0.1456956


def _ymno3_with_tied_moment(tmp_path):
    phase = _read(tmp_path, "YMnO3").phases[0]
    j = next(i for i, a in enumerate(phase.atoms) if a.moment is not None)
    atom = phase.atoms[j]
    moment = atom.moment.model_copy(update={
        name: rx.Parameter(value=value, unit="mu_B")
        for name, value in zip(("crystalaxis_x", "crystalaxis_y",
                                "crystalaxis_z"),
                               (_TIED_X, 2 * _TIED_X, 0.0))})
    atoms = [a.model_dump() for a in phase.atoms]
    atoms[j] = atom.model_copy(update={"moment": moment}).model_dump()
    # validated, not model_copy'd: the moment is on the line to float
    # precision, so the in-memory model passes the check the reader applies
    phase = rx.Phase.model_validate({**phase.model_dump(), "atoms": atoms})
    return rx.Structure(phases=[phase]), j


def test_a_moment_on_a_tied_direction_reads_back_from_its_own_writer(tmp_path):
    """The writer's file passes the reader's span test on the moment it wrote.

    The reproduction first: the site allows only [1, 2, 0], and the same moment
    rounded to five decimals per component — what the writer printed until
    2026-09-24 — is outside that span at the validator's 1e-6, so the reader
    refused its own writer's file.  Written as the double itself it comes back
    exactly, and exactly on the line.
    """
    structure, j = _ymno3_with_tied_moment(tmp_path)
    phase = structure.phases[0]
    atom = phase.atoms[j]
    basis = phase.magnetic_symmetry.group().allowed_moment_basis(
        (atom.x.value, atom.y.value, atom.z.value))
    assert [list(map(int, r)) for r in basis] == [[1, 2, 0]]
    assert in_span(basis, atom.moment.values())
    assert not in_span(basis, [round(v, 5) for v in atom.moment.values()])

    out = tmp_path / "tied.cif"
    structure_to_cif(structure, str(out))
    back = structure_from_cif(str(out)).phases[0].atoms[j].moment
    assert list(back.values()) == list(atom.moment.values())


def test_a_tied_moment_round_trips_bit_and_byte_identically(tmp_path):
    """read → write → read is bit-identical on every stored field, and
    write → read → write byte-identical, on the synthetic tied moment — the
    fixed-point claim the four published fixtures make, on a moment whose
    components carry every digit a refinement leaves in them."""
    structure, _ = _ymno3_with_tied_moment(tmp_path)
    out0 = tmp_path / "zero.cif"
    structure_to_cif(structure, str(out0))
    first = structure_from_cif(str(out0))
    out1 = tmp_path / "one.cif"
    structure_to_cif(first, str(out1))
    second = structure_from_cif(str(out1))
    out2 = tmp_path / "two.cif"
    structure_to_cif(second, str(out2))
    assert _stored(structure.phases[0]) == _stored(first.phases[0])
    assert _stored(first.phases[0]) == _stored(second.phases[0])
    assert out0.read_bytes() == out1.read_bytes() == out2.read_bytes()


def test_the_modulus_esd_comes_from_the_dof_row_and_nowhere_else(tmp_path):
    """``_moment_esds`` reads ``phases.i.atoms.j.moment.dof0`` and does not
    recompute anything (WP-1076: one writer per number).

    A site whose moment did not refine is **absent** from the mapping and the
    writer puts a CIF ``.`` there — inapplicable, which is the right word: a
    component written back from a held modulus has no esd of its own, and a
    ``0`` there would state a moment known exactly.
    """
    from rietx.io.exporters import _moment_esds

    structure = _read(tmp_path, "LaMnO3")
    phase = structure.phases[0]

    class _Row:
        def __init__(self, path, stderr):
            self.path, self.stderr = path, stderr

    class _Result:
        parameters = [_Row("phases.0.atoms.1.moment.dof0", 0.3275),
                      _Row("phases.0.atoms.1.dof.0", 0.001)]

    assert _moment_esds(_Result(), 0, phase) == {"Mn1": pytest.approx(0.3275)}

    class _NoEsd:
        parameters = [_Row("phases.0.atoms.1.moment.dof0", None)]

    assert _moment_esds(_NoEsd(), 0, phase) == {}
    assert magcif._number_or_dot(None) == "."
    assert magcif._number_or_dot(float("nan")) == "."
    assert magcif._number_or_dot(0.3275) == "0.3275"
    # a phase with no magnetic symmetry is not even walked
    nuclear = phase.model_copy(update={
        "magnetic_symmetry": None,
        "atoms": [a.model_copy(update={"moment": None}) for a in phase.atoms]})
    assert _moment_esds(_Result(), 0, nuclear) == {}


# ===========================================================================
# 10. the FullProf `.pcr` stance, and why it is a refusal
# ===========================================================================

def _pcr_fixtures():
    """The `.pcr` fixture writers, borrowed from the reader's own test file.

    Imported rather than re-typed: those fixtures are the corpus evidence for
    the two magnetic sub-grammars — every line of them is quoted from a named
    real file — and a second copy here would be a second thing to keep true.
    """
    from tests.test_projects_fullprof import _magnetic_isy1, _magnetic_isy2, _pcr, _phase

    return _pcr, _phase, _magnetic_isy1, _magnetic_isy2


def test_a_jbt_1_phase_is_refused_with_the_argument_wp1327_left_standing(tmp_path):
    """The refusal survives WP-1327, and the *reason* had to change.

    Until this rung the sentence was "rietx has no magnetic scattering model",
    and WP-1327 made that false. A stale reason in a refusal is the diagnostic
    that is true of an intermediate state and false of the reported one, so it
    is replaced by the two reasons that are still true:

    * a ``Jbt = 1`` phase is a **pure magnetic** phase — its own ``Scale``, no
      nuclear structure factor, only the magnetic atoms listed, a form-factor
      label in the species column and ``P -1`` as the symbol — which is
      FullProf's spelling of a TOPAS ``mag_only``, and WP-1327's model is a
      moment on a *nuclear* phase sharing one scale;
    * its symmetry is a magnetic **representation** and not a Shubnikov
      operator list.

    The second is the one worth measuring, and the corpus's own fixture
    measures it: ``SYMM Y, X, -Z+1`` with ``MSYM -u,-v,w`` gives a moment
    matrix of diag(−1, −1, 1) where the Shubnikov axial action ε·det(R)·R for
    that rotation is (v, u, −w). The two disagree, so those lines cannot both
    be read as one magnetic space-group operator, and **which reading is right
    is not something any file on this tree settles** — so the conversion is
    refused rather than guessed. A wrong ε is a fit under the wrong magnetic
    group, reported with a confident esd.
    """
    from rietx.io.projects.fullprof import (
        MAGNETIC_PHASE_REFUSAL,
        FullProfPcrError,
        read_fullprof_pcr,
    )
    from rietx.io.projects.fullprof import to_structure as pcr_to_structure

    _pcr, _phase, _magnetic_isy1, _magnetic_isy2 = _pcr_fixtures()

    # the measurement the refusal's second half rests on
    rotation = np.array([[0, 1, 0], [1, 0, 0], [0, 0, -1]])   # SYMM Y, X, -Z+1
    msym = np.diag([-1, -1, 1])                               # MSYM -u,-v,w
    axial = round(float(np.linalg.det(rotation))) * rotation
    assert not np.array_equal(msym, axial)
    assert not np.array_equal(msym, -axial)

    path = _pcr(tmp_path, "mag.pcr", _phase(), _magnetic_isy1())
    model = read_fullprof_pcr(path)
    assert len(model.magnetic_phases) == 1
    with pytest.raises(FullProfPcrError) as excinfo:
        pcr_to_structure(model)
    message = str(excinfo.value)
    assert "pure magnetic" in message
    assert "magnetic *representation*" in message or "representation" in message
    assert "no magnetic scattering model" not in message   # the stale reason
    assert MAGNETIC_PHASE_REFUSAL in message


def test_nuclear_only_still_names_what_it_omitted(tmp_path):
    """The omission is the caller's declared choice, which is not the same as
    the omission being invisible.

    ``nuclear_only=True`` returns the nuclear subset; the channel then says
    which phases went and how large they were — the sub-grammar, the site
    count, the propagation vectors, which moment columns are non-zero and the
    phase's own R_Bragg — so a caller can see the size of what they asked to
    drop.
    """
    from rietx.io.projects.fullprof import read_fullprof_pcr
    from rietx.io.projects.fullprof import to_structure as pcr_to_structure

    _pcr, _phase, _magnetic_isy1, _magnetic_isy2 = _pcr_fixtures()
    path = _pcr(tmp_path, "mag.pcr", _phase(), _magnetic_isy1(), _magnetic_isy2())
    model = read_fullprof_pcr(path)
    diagnostics: list = []
    structure = pcr_to_structure(model, nuclear_only=True,
                                 diagnostics=diagnostics)
    assert len(structure.phases) == 1
    omitted = [d for d in diagnostics
               if d.code == "FULLPROF_MAGNETIC_PHASE_OMITTED"]
    assert len(omitted) == 2
    assert all(d.level == "warning" for d in omitted)
    assert "Jbt 1" in omitted[0].message and "Isy -1" in omitted[0].message
    assert "Isy -2" in omitted[1].message
    assert omitted[0].value is not None                 # its own R_Bragg


def test_a_fourier_component_phase_is_refused_naming_the_form(tmp_path):
    """``Jbt`` values this reader has no file for are refused, and the message
    names the **Fourier-component** magnetic form explicitly.

    Two different fences in one sentence, and they are worth keeping apart. A
    phase whose moments are stated as amplitudes per propagation vector is
    outside rietx's magnetic model *whatever* its Jbt — WP-1327 carries a
    single commensurate moment per site, and this is the same fence
    ``Structure.from_cif`` states by name for a magCIF's
    ``_atom_site_moment_Fourier`` loop. But **which** Jbt selects that layout
    is something this reader does not claim to know, because no file it was
    written against states one, and a wrong guess desynchronises every line
    after it: a ``.pcr`` is positional.
    """
    from rietx.io.projects.fullprof import FullProfPcrError, read_fullprof_pcr

    _pcr, _phase, _magnetic_isy1, _magnetic_isy2 = _pcr_fixtures()
    path = _pcr(tmp_path, "fourier.pcr", _phase(jbt=5, isy=-1))
    with pytest.raises(FullProfPcrError) as excinfo:
        read_fullprof_pcr(path)
    message = str(excinfo.value)
    assert "Jbt = 5" in message
    assert "Fourier-component" in message
    assert "not** something this reader claims to know" in message
