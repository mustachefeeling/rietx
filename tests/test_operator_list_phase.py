"""A phase that carries its own operator list (Q-17).

The claim under test is that a group **no Hermann-Mauguin symbol names in its
cell** can be stated, stored, exported, read back and refined like any other,
and that stating one changes nothing for a phase that does not.  Four
properties carry it and each has its own group here:

* **exactly off.**  ``symmetry_operations=None`` is every phase written before
  the field existed, and a phase that declares the operation list of a *named*
  group predicts the identical pattern — pinned on ``predict()`` bit-for-bit,
  not on a tolerance, because the thing that would break it is a reordering of
  the structure-factor sum and a reordering is invisible to a tolerance.
* **the operations are the authority, not the label.**  Orbits, site
  multiplicities, systematic absences, reflection multiplicities and the cell
  ties all come out of the list; measured against the symbol over nine settings
  covering all seven crystal systems' constraint cases.
* **refuses rather than lies.**  A list that is not a group, a plain symbol
  that does not generate the list, and a bracketed label with no list are
  refusals with the reason in them.
* **the 29 unnamable isotropy subgroups.**  Every (group, k) case the all-group
  k-sweep could not name reaches ``candidates`` and comes back with a
  candidate carrying its operator list, and the child of the one real case —
  Ba₂FeSbSe₅'s S3(a,b) in 2a,b,a+c — is *built* rather than refused.

Nothing here needs a fit; the acceptance fit is in the report.
"""

from fractions import Fraction

import gemmi
import numpy as np
import pytest

import rietx as rx
from rietx.crystallography import symmetry as sym
from rietx.crystallography.cif import structure_from_cif, structure_to_cif
from rietx.crystallography.magnetic import supercell as sc
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.operators import identification, identify
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import EmissionLine, Instrument, Source
from rietx.schemas.structure import Atom, Cell, Phase, Structure

#: The child nuclear group of Ba₂FeSbSe₅'s S3(a,b) superstructure in
#: 2a,b,a+c — **derived**, not copied: it is what
#: ``magnetic_supercell(nuclear_group="magnetic")`` builds from the Pnma parent
#: at k = (½,0,½), and it is the shortest real example of the whole problem.
#: The (½,0,0) translation is the parent's own lattice vector (the nuclear
#: structure is still periodic on it) and the mirror carries a ½ along the
#: *undoubled* b, so no tabulated symbol has this list: ``P m 1 1`` times the
#: two lattice cosets omits two of these and adds two others.
S3_CHILD_OPS = ("x,y,z", "x+1/2,y,z", "x,-y+1/2,z", "x+1/2,-y+1/2,z")
S3_CHILD_LABEL = "Pm [unnamed in 2a,b,a+c]"

#: Every setting whose ``CellConstraints`` case is distinct, so the parity
#: check below covers each branch of ``cell_constraints`` rather than one.
SETTINGS = ("P n m a", "C m c m", "F d -3 m:2", "P 6_3/m m c", "R -3 c:H",
            "R -3 c:R", "P 1 21/m 1", "I 4_1/a m d:2", "P -1")

_CELLS = {
    "P n m a": (8.0, 6.0, 7.0, 90.0, 90.0, 90.0),
    "C m c m": (4.0, 11.0, 6.0, 90.0, 90.0, 90.0),
    "F d -3 m:2": (8.4, 8.4, 8.4, 90.0, 90.0, 90.0),
    "P 6_3/m m c": (5.0, 5.0, 8.0, 90.0, 90.0, 120.0),
    "R -3 c:H": (5.0, 5.0, 17.0, 90.0, 90.0, 120.0),
    "R -3 c:R": (6.4, 6.4, 6.4, 46.0, 46.0, 46.0),
    "P 1 21/m 1": (7.0, 6.0, 8.0, 90.0, 103.0, 90.0),
    "I 4_1/a m d:2": (5.8, 5.8, 9.4, 90.0, 90.0, 90.0),
    "P -1": (5.1, 6.2, 7.3, 88.0, 95.0, 101.0),
}

#: The two sites the sweep probes, verbatim from its own script: the origin,
#: and a general position with no accidental special relation in it.
SWEEP_SITES = {"origin": (Fraction(0), Fraction(0), Fraction(0)),
               "general": (Fraction(11, 100), Fraction(13, 100),
                           Fraction(17, 100))}

#: The **29** rows the all-group k-sweep (2744 rows over all 230 settings ×
#: k ∈ {0,½}³ × those two sites, 61 384 s, finished 2026-09-09) reported as
#: "unidentified candidate": spglib matches the isotropy subgroup's operator
#: list to none of the 1651 magnetic space groups.  Every one is a c- or
#: n-glide group doubled along the glide's own translation, which is the same
#: quarter-translation mechanism this module is about, one rung up (magnetic
#: rather than nuclear).  Transcribed row for row from the sweep's own summary
#: table, sites included, so the count here **is** 29 — 14 (setting, k) pairs
#: at both sites plus P6mm at the general site only, which is the one row the
#: sweep hit at one site and not the other.
SWEEP_UNNAMED = tuple(
    (setting, k, site)
    for setting, k in (
        ("P c c 2", ("1/2", "1/2", "0")),
        ("C m m 2", ("0", "0", "1/2")),
        ("P c c a", ("1/2", "1/2", "0")),
        ("P c c n", ("1/2", "1/2", "0")),
        ("P 42 c m", ("0", "0", "1/2")),
        ("P 42 c m", ("1/2", "1/2", "0")),
        ("P 42 n m", ("0", "0", "1/2")),
        ("P 4 c c", ("1/2", "1/2", "0")),
        ("P -4 c 2", ("1/2", "1/2", "0")),
        ("P 42/m c m", ("0", "0", "1/2")),
        ("P 42/n n m:1", ("0", "0", "1/2")),
        ("P 42/m n m", ("0", "0", "1/2")),
        ("P 42/n c m:1", ("0", "0", "1/2")),
        ("P n -3 m:1", ("0", "0", "1/2")),
    )
    for site in ("origin", "general")
) + (("P 6 m m", ("0", "0", "1/2"), "general"),)

INSTRUMENT = Instrument(source=Source(lines=[EmissionLine(wavelength=1.540598)]))
TWO_THETA = np.arange(5.0, 100.0, 0.02)


def _cell(values) -> Cell:
    a, b, c, al, be, ga = values
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=al), beta=Parameter(value=be),
                gamma=Parameter(value=ga))


def _atoms():
    return [
        Atom(label="Fe1", species="Fe", x=Parameter(value=0.1),
             y=Parameter(value=0.25), z=Parameter(value=0.3),
             occ=Parameter(value=1.0), biso=Parameter(value=0.5)),
        Atom(label="O1", species="O", x=Parameter(value=0.33),
             y=Parameter(value=0.11), z=Parameter(value=0.62),
             occ=Parameter(value=1.0), biso=Parameter(value=0.8)),
    ]


def _phase(space_group, operations=None, cell=None):
    return Phase(name="p", space_group=space_group,
                 symmetry_operations=operations,
                 cell=_cell(cell or _CELLS.get(space_group, (7.0, 6.0, 8.0,
                                                             90.0, 97.0, 90.0))),
                 atoms=_atoms())


def _triplets(symbol) -> list[str]:
    return [op.triplet() for op in sym.get_spacegroup(symbol).operations()]


# ---------------------------------------------------------------------------
# exactly off
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("symbol", SETTINGS)
def test_the_explicit_list_of_a_named_group_predicts_bit_identically(symbol):
    """``predict()`` to the last bit, with and without the operation list.

    The property that makes the field additive, and the *only* test that can
    catch what would break it.  ``gemmi.GroupOps`` rebuilt from a flat
    operation list re-splits the group into coset representatives and picks
    different ones (measured on ``F d -3 m:2``: the 18th operation comes back
    as ``y,z,x`` where the table has ``y,z+1/2,x+1/2``, the same operation
    times a centring), so the orbit images — and with them the frozen
    operation subsets ``structure_factor.select_orbit_ops`` sums over — come
    out permuted.  A permuted sum of the same terms differs in the last bits of
    every intensity, which no tolerance-based assertion would see.
    """
    bare = _phase(symbol)
    listed = _phase(symbol, _triplets(symbol))
    y_bare = rx.Refinement(Structure(phases=[bare]),
                           INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    y_listed = rx.Refinement(Structure(phases=[listed]),
                             INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    assert np.array_equal(np.asarray(y_bare), np.asarray(y_listed))
    assert float(np.max(np.abs(np.asarray(y_bare) - np.asarray(y_listed)))) == 0.0


def test_a_phase_without_the_field_stores_none_and_resolves_the_symbol():
    """The default is exactly the old object: ``None``, and the symbol resolves."""
    phase = _phase("P n m a")
    assert phase.symmetry_operations is None
    group = sym.resolve_group(phase.space_group, phase.symmetry_operations)
    assert isinstance(group, gemmi.SpaceGroup)
    assert group.xhm() == "P n m a"


# ---------------------------------------------------------------------------
# the operations are the authority
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("symbol", SETTINGS)
def test_orbits_absences_and_cell_ties_come_out_of_the_list(symbol):
    """Every symmetry answer is the symbol's when the list is the symbol's.

    The nine settings exist to cover every distinct ``cell_constraints``
    branch (cubic, tetragonal, hexagonal, both trigonal axis choices,
    monoclinic, triclinic, orthorhombic primitive and C-centred), because the
    metric constraints of an unnamed group are the one thing that cannot be
    read off the operation list directly and go through
    :attr:`OperatorGroup.closest_type` instead.
    """
    sg = sym.get_spacegroup(symbol)
    og = sym.OperatorGroup(label=f"{symbol} [explicit]", xyz=tuple(_triplets(symbol)))
    cell = _CELLS[symbol]

    a = sym.generate_reflections(sg, cell, 1.5406, 90.0)
    b = sym.generate_reflections(og, cell, 1.5406, 90.0)
    assert np.array_equal(a.hkl, b.hkl)
    assert np.array_equal(a.multiplicity, b.multiplicity)
    assert np.array_equal(a.d, b.d)

    for xyz in ((0.1234, 0.25, 0.5678), (0.0, 0.0, 0.0), (0.5, 0.0, 0.25)):
        x = np.array(xyz)
        assert np.array_equal(sym.expand_positions(sg, x),
                              sym.expand_positions(og, x))
        assert (sym.site_orbit(sg, x).multiplicity
                == sym.site_orbit(og, x).multiplicity)

    assert sym.cell_constraints(sg) == sym.cell_constraints(og)
    assert sym.free_cell_names(sg) == sym.free_cell_names(og)
    assert np.array_equal(sym.rotation_matrices(sg), sym.rotation_matrices(og))
    assert np.array_equal(sym.reflection_orbits(sg, a.hkl[:12])[0],
                          sym.reflection_orbits(og, a.hkl[:12])[0])


def test_the_closest_type_of_a_group_no_symbol_names():
    """A half-translation is no Bravais centring, and the point group answers.

    The real S3(a,b) child.  Its (½,0,0) is the parent's lattice vector, which
    gemmi reads as a centring it has no letter for, so the symmorphic lookup
    returns nothing; the fallback — the bare point group on a P lattice —
    resolves it as ``P 1 m 1``, monoclinic with unique axis b, which is what
    the child cell 2a,b,a+c is.  The constraints that follow are the ones the
    cell needs: α and γ held at 90°, β free, no length tied.
    """
    og = sym.OperatorGroup(label=S3_CHILD_LABEL, xyz=S3_CHILD_OPS)
    assert og.closest_type.xhm() == "P 1 m 1"
    assert og.crystal_system_str() == "monoclinic"
    assert og.monoclinic_unique_axis() == "b"
    constraints = sym.cell_constraints(og)
    assert constraints.ties == {}
    assert constraints.fixed_angles == {"alpha": 90.0, "gamma": 90.0}
    assert sym.free_cell_names(og) == ("a", "b", "c", "beta")


def test_no_hermann_mauguin_symbol_generates_the_child_list():
    """The premise, asserted rather than argued.

    Every setting of every group in gemmi's table is tried, and none of them
    generates this operation list.  If a future gemmi table did hold one, this
    test fails and the whole bracketed-label mechanism becomes unnecessary for
    this case — which is the direction the failure should point.
    """
    wanted = {(tuple(int(v) for row in op.rot for v in row),
               tuple(int(v) % op.DEN for v in op.tran))
              for op in (gemmi.Op(s) for s in S3_CHILD_OPS)}
    for sg in gemmi.spacegroup_table():
        got = {(tuple(int(v) for row in op.rot for v in row),
                tuple(int(v) % op.DEN for v in op.tran))
               for op in sg.operations()}
        assert got != wanted, sg.xhm()


def test_the_label_convention_round_trips():
    assert sym.split_group_label(S3_CHILD_LABEL) == ("Pm", "unnamed in 2a,b,a+c")
    assert sym.split_group_label("P n m a") is None
    assert sym.unnamed_label("Pm", "unnamed in 2a,b,a+c") == S3_CHILD_LABEL
    assert sym.split_group_label(sym.unnamed_label(None, "no closest type")) \
        == ("", "no closest type")


# ---------------------------------------------------------------------------
# storage: JSON and CIF
# ---------------------------------------------------------------------------
def test_the_operation_list_survives_a_json_round_trip_bit_identically():
    phase = _phase(S3_CHILD_LABEL, list(S3_CHILD_OPS))
    text = phase.model_dump_json()
    back = Phase.model_validate_json(text)
    assert back.model_dump_json() == text
    assert tuple(back.symmetry_operations) == S3_CHILD_OPS
    assert back.space_group == S3_CHILD_LABEL


def test_any_spelling_of_an_operation_stores_canonically():
    """Two callers who wrote the same group differently store one document."""
    phase = _phase(S3_CHILD_LABEL,
                   [" X , Y , Z ", "x+1/2,y,z", "x,-y+1/2,z", "x+3/2,-y+1/2,z"])
    assert tuple(phase.symmetry_operations) == S3_CHILD_OPS


def test_a_repeated_operation_is_stored_once():
    phase = _phase(S3_CHILD_LABEL, list(S3_CHILD_OPS) + ["x,y,z"])
    assert tuple(phase.symmetry_operations) == S3_CHILD_OPS


def test_the_cif_round_trip_carries_the_loop_and_the_label(tmp_path):
    """``_space_group_symop_operation_xyz`` out, and the same list back in."""
    phase = _phase(S3_CHILD_LABEL, list(S3_CHILD_OPS))
    path = tmp_path / "child.cif"
    structure_to_cif(Structure(phases=[phase]), str(path))
    text = path.read_text(encoding="utf-8")
    assert "_space_group_symop_operation_xyz" in text
    assert "_space_group_name_H-M_alt" in text
    for triplet in S3_CHILD_OPS:
        assert triplet in text

    back = structure_from_cif(str(path)).phases[0]
    assert back.space_group == S3_CHILD_LABEL
    assert tuple(back.symmetry_operations) == S3_CHILD_OPS
    assert [round(v, 6) for v in back.cell.lengths_angles()] == \
        [round(v, 6) for v in phase.cell.lengths_angles()]


def test_an_ordinary_cif_is_read_exactly_as_it_always_was(tmp_path):
    """A symop loop beside a *symbol* is not this path.

    Most structure CIFs carry an operation loop, and for those the symbol is
    the group; taking the loop instead would change how every such file is
    read.  The trigger is the bracket, so a named phase round-trips with
    ``symmetry_operations`` still ``None``.
    """
    phase = _phase("P n m a", _triplets("P n m a"))
    path = tmp_path / "named.cif"
    structure_to_cif(Structure(phases=[phase]), str(path))
    assert "_space_group_symop_operation_xyz" in path.read_text(encoding="utf-8")
    back = structure_from_cif(str(path)).phases[0]
    assert back.space_group == "P n m a"
    assert back.symmetry_operations is None


# ---------------------------------------------------------------------------
# refuses rather than lies
# ---------------------------------------------------------------------------
def test_a_list_that_disagrees_with_a_plain_symbol_is_refused():
    with pytest.raises(ValueError, match="not the same group"):
        _phase("P n m a", ["x,y,z", "-x,y,-z"])


def test_the_same_list_is_accepted_once_the_label_is_bracketed():
    """The refusal above is about the *claim*, and bracketing withdraws it."""
    phase = _phase("P 1 2 1 [unnamed in this cell]", ["x,y,z", "-x,y,-z"])
    assert tuple(phase.symmetry_operations) == ("x,y,z", "-x,y,-z")


def test_a_bracketed_label_without_the_list_is_refused():
    with pytest.raises(ValueError, match="nothing is left to be the group"):
        _phase(S3_CHILD_LABEL)


def test_a_list_missing_the_identity_is_refused():
    with pytest.raises(ValueError, match="identity 'x,y,z' is not one of them"):
        _phase("P 1 [unnamed]", ["-x,y,z"])


def test_a_list_that_is_not_closed_under_composition_is_refused():
    with pytest.raises(ValueError, match="not closed under composition"):
        _phase("P 1 [unnamed]", ["x,y,z", "-x,y,z", "x,-y+1/3,z"])


def test_an_empty_list_is_refused_and_none_is_the_way_off():
    with pytest.raises(ValueError, match="empty list"):
        _phase("P n m a", [])


def test_an_unparsable_operation_is_refused_by_name():
    with pytest.raises(ValueError, match="not an 'x,y,z'-style symmetry operation"):
        _phase("P 1 [unnamed]", ["x,y,z", "q,y,z"])


def test_a_label_that_is_neither_a_symbol_nor_bracketed_is_refused():
    with pytest.raises(ValueError, match="neither a symbol this package resolves"):
        _phase("Zork", ["x,y,z"])


# ---------------------------------------------------------------------------
# identify(): a result instead of a refusal
# ---------------------------------------------------------------------------
def test_identification_names_a_database_group_and_agrees_with_identify():
    from rietx.crystallography.magnetic.operators import magnetic_group

    group = magnetic_group("136.499")
    result = identification(group)
    assert result.named is True
    assert result.group_id is not None
    assert result.group_id.bns_number == "136.499"
    assert result.bns_number == "136.499"
    assert result.group_id == identify(group)
    assert result.reason == ""
    assert len(result.operations) == len(group.all_operations())


def test_identification_returns_a_result_where_identify_still_raises():
    """UNI 283 is the database entry spglib cannot match to itself.

    ``identify`` keeps raising there — it is the strict form, and the two tests
    that pin its message are unchanged — while ``identification`` answers with
    ``named=False``, the operator list, the closest nuclear type and the
    reason.  That is what lets ``candidates`` and ``magnetic_supercell``
    proceed instead of dropping the case.
    """
    from rietx.crystallography.magnetic.operators import magnetic_group

    group = magnetic_group(283)
    with pytest.raises(ValueError, match="did not match"):
        identify(group)
    result = identification(group)
    assert result.named is False
    assert result.group_id is None
    assert result.bns_number == "unnamed"
    assert "did not match" in result.reason
    assert len(result.operations) == len(group.all_operations())
    assert result.closest_type


# ---------------------------------------------------------------------------
# the 29 sweep cases
# ---------------------------------------------------------------------------
def test_the_sweep_case_list_is_the_sweeps_own_count():
    """29 rows, because the sweep reported 29. Guards the transcription."""
    assert len(SWEEP_UNNAMED) == 29
    assert len({(s, k) for s, k, _site in SWEEP_UNNAMED}) == 15


@pytest.mark.slow
@pytest.mark.parametrize("setting,k,site", SWEEP_UNNAMED,
                         ids=lambda v: str(v).replace(" ", ""))
def test_the_sweeps_unnamable_isotropy_subgroups_still_produce_candidates(
        setting, k, site):
    """Each case comes back with candidates, and the unnamed ones say so.

    The sweep's ``RuntimeError: unidentified candidate`` is raised by the
    *sweep script*, not by ``candidates`` — which already tolerates
    ``identify`` refusing and stores ``identification=None``.  What was missing
    is what an unnamed candidate can then be *used* for, so this asserts both
    halves: the call returns, and every candidate carries the operator list its
    label cannot supply.
    """
    kk = tuple(Fraction(c) for c in k)
    found = candidates(setting, SWEEP_SITES[site], kk)
    assert len(found) > 0
    unnamed = [c for c in found if c.identification is None]
    assert unnamed, f"{setting} at {k} ({site}) was expected an unnamed candidate"
    for candidate in unnamed:
        assert candidate.bns_number == "unidentified"
        result = identification(candidate.group)
        assert result.named is False
        assert result.operations
        assert result.reason


@pytest.mark.slow
def test_the_ba2fesbse5_s3ab_child_is_built_instead_of_refused():
    """The one real case: Pm in 2a,b,a+c, which M-1 could not state at all.

    The parent is a *generic* Pnma structure — generic members of the 8d and 4c
    Wyckoff classes and a nominal cell, no fitted or published number — which
    is sound because ``candidates`` reads a site only through its stabiliser
    and its orbit.
    """
    from rietx.crystallography.adp import cartesian_basis

    parent = Phase(
        name="parent", space_group="P n m a",
        cell=_cell((12.0, 9.0, 8.0, 90.0, 90.0, 90.0)),
        atoms=[
            Atom(label="Ba1", species="Ba", x=Parameter(value=0.11),
                 y=Parameter(value=0.13), z=Parameter(value=0.17),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.9)),
            Atom(label="Fe1", species="Fe", x=Parameter(value=0.19),
                 y=Parameter(value=0.25), z=Parameter(value=0.23),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.5)),
            Atom(label="Se1", species="Se", x=Parameter(value=0.29),
                 y=Parameter(value=0.31), z=Parameter(value=0.37),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.7)),
        ])
    lattice = np.asarray(cartesian_basis(*parent.cell.lengths_angles())).T
    k = ("1/2", "0", "1/2")
    per_site = [{c.label: c for c in candidates(
        parent.space_group, (a.x.value, a.y.value, a.z.value), k,
        kind="displacive", cell=lattice, verify=True)}
        for a in parent.atoms]
    assert all("S3(a,b)" in table for table in per_site)

    statement = sc.magnetic_supercell(parent, candidate=per_site[0]["S3(a,b)"],
                                      nuclear_group="magnetic")
    assert statement.child_group_named is False
    assert sym.split_group_label(statement.phase.space_group) is not None
    assert statement.phase.symmetry_operations is not None
    # M2d: two of S3_CHILD_OPS's four operations carry the wrong little-group
    # sign for this candidate's own (grey) mode field (checks/
    # M2B_SINGLE_COMPONENT_SIGN_CHECK.md) — the cross-coset mirror
    # 'x+1/2,-y+1/2,z' and the pure translation 'x+1/2,y,z' — so the declared
    # group is now only the sign-consistent order-2 subgroup, and the sibling
    # they used to reach (wrongly) is its own explicit representative
    # instead: 24 atoms where the pre-M2d group gave 12.
    assert set(statement.phase.symmetry_operations) == {"x,y,z", "x,-y+1/2,z"}
    assert len(statement.phase.atoms) == 24
    codes = [d.code for d in statement.diagnostics]
    assert "CHILD_GROUP_UNNAMED" in codes
    note = next(d for d in statement.diagnostics
                if d.code == "CHILD_GROUP_UNNAMED")
    assert "quarter" in note.message
    # the child compiles and predicts, which is the whole point of stating it
    y = rx.Refinement(Structure(phases=[statement.phase]),
                      INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    assert np.isfinite(np.asarray(y)).all()
    assert float(np.asarray(y).max()) > 0.0


@pytest.mark.slow
def test_a_named_child_is_untouched_by_the_unnamed_path():
    """S2(a,b) of the same parent still gives the plain symbol and no list.

    The negative arm of the test above: a child whose nuclear group *is*
    reproduced by a symbol keeps the symbol, carries no operation list, and
    raises no diagnostic — so the new path cannot have been taken for it.
    """
    from rietx.crystallography.adp import cartesian_basis

    parent = Phase(
        name="parent", space_group="P n m a",
        cell=_cell((12.0, 9.0, 8.0, 90.0, 90.0, 90.0)),
        atoms=[
            Atom(label="Fe1", species="Fe", x=Parameter(value=0.19),
                 y=Parameter(value=0.25), z=Parameter(value=0.23),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.5)),
        ])
    lattice = np.asarray(cartesian_basis(*parent.cell.lengths_angles())).T
    found = {c.label: c for c in candidates(
        parent.space_group, (0.19, 0.25, 0.23), ("1/2", "0", "1/2"),
        kind="displacive", cell=lattice, verify=True)}
    statement = sc.magnetic_supercell(parent, candidate=found["S2(a,b)"],
                                      nuclear_group="magnetic")
    assert statement.child_group_named is True
    assert statement.phase.space_group == "P 1 21/m 1"
    assert statement.phase.symmetry_operations is None
    assert [d.code for d in statement.diagnostics] == []


@pytest.mark.slow
def test_the_unnamed_displacive_child_at_zero_amplitude_is_the_parent_pattern():
    """|det P|² × the parent, to the last bits — and the label plays no part.

    M-1's test (a) for a *named* child, made for one no symbol names, and it is
    the sharpest statement available that the bracketed label's leading symbol
    is not being used anywhere: ``Pm`` in this cell would give a different
    orbit partition, a different atom count and a different |F_N|², so the only
    way the ratio comes out at exactly |det P|² = 4 is if the operation list is
    what the forward model read.  Compared against the three *named* children of
    the same parent at the same k, which must give the same 4.

    The background is zeroed on purpose: it is additive, so a ratio taken with
    it in would not be constant even when the peaks are identical (measured on
    the real 65 K instrument: median ratio 1.1215 with a spread of 2.7, all of
    it background).
    """
    from rietx.crystallography.magnetic.supercell import displacive_statement
    from rietx.schemas.instrument import BackgroundChebyshev

    parent = Phase(
        name="parent", space_group="P n m a",
        cell=_cell((12.0, 9.0, 8.0, 90.0, 90.0, 90.0)),
        atoms=[
            Atom(label="Ba1", species="Ba", x=Parameter(value=0.11),
                 y=Parameter(value=0.13), z=Parameter(value=0.17),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.9)),
            Atom(label="Fe1", species="Fe", x=Parameter(value=0.19),
                 y=Parameter(value=0.25), z=Parameter(value=0.23),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.5)),
            Atom(label="Se1", species="Se", x=Parameter(value=0.29),
                 y=Parameter(value=0.31), z=Parameter(value=0.37),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.7)),
        ])
    instrument = INSTRUMENT.model_copy(deep=True)
    instrument.background = BackgroundChebyshev(
        coefficients=[Parameter(value=0.0) for _ in range(3)])
    two_theta = np.arange(8.0, 90.0, 0.02)
    y_parent = np.asarray(rx.Refinement(
        Structure(phases=[parent]),
        instrument.model_copy(deep=True)).predict(two_theta))
    assert float(y_parent.max()) > 0.0

    seen = {}
    for label in ("S1(a,b)", "S2(a,b)", "S3(a,b)", "S4(a,b)"):
        irrep, direction = label.split("(", 1)
        statement = displacive_statement(parent, ("1/2", "0", "1/2"),
                                         irrep=irrep, direction="(" + direction)
        y_child = np.asarray(rx.Refinement(
            Structure(phases=[statement.phase]),
            instrument.model_copy(deep=True)).predict(two_theta))
        live = y_parent > 1e-6 * float(y_parent.max())
        ratio = y_child[live] / y_parent[live]
        constant = float(np.median(ratio))
        seen[label] = (statement.child_group_named, constant,
                       float(np.max(np.abs(y_child - constant * y_parent))
                             / float(y_parent.max())))
        assert constant == pytest.approx(statement.index ** 2, rel=1e-9)
        assert seen[label][2] < 1e-9

    assert seen["S3(a,b)"][0] is False, "S3(a,b) should be the unnamed one"
    assert all(seen[k][0] for k in ("S1(a,b)", "S2(a,b)", "S4(a,b)"))
    # and the unnamed child's constant is the named ones' constant
    assert {round(v[1], 12) for v in seen.values()} == {4.0}


def test_site_constraints_of_an_unnamed_group_withholds_the_wyckoff_letter():
    """Constraint bases and multiplicity yes; a Wyckoff letter no.

    The letter is a property of a tabulated setting, and spglib would answer
    for the *type* it identifies from a probe cell — which for a child cell
    whose glide translation is a quarter is not this setting.  So it is left
    empty rather than filled with a plausible wrong one; everything else here
    is read off the group's own operations and is unaffected.
    """
    from rietx.crystallography.wyckoff import site_constraints

    og = sym.OperatorGroup(label=S3_CHILD_LABEL, xyz=S3_CHILD_OPS)
    general = site_constraints(og, (0.11, 0.13, 0.17))
    assert general.wyckoff == ""
    assert general.site_symmetry == ""
    assert general.multiplicity == 4
    assert general.coord_basis.shape == (3, 3)
    special = site_constraints(og, (0.11, 0.25, 0.17))   # on the mirror
    assert special.multiplicity == 2
    assert special.coord_basis.shape == (2, 3)
    # the named twin still answers with its letter
    named = site_constraints("P n m a", (0.11, 0.25, 0.17))
    assert named.wyckoff == "4c"


def test_the_stephens_basis_reaches_an_unnamed_group_through_the_frozen_set():
    """``report.strain`` rebuilds the group from ``ReflectionSet.operations``.

    The anisotropic-strain basis depends on the rotations only, so an unnamed
    group gives what its closest type gives — but only if the consumer can get
    the group back at all, and all it has is the frozen ``spacegroup`` string,
    which for such a phase is a *label* the tables do not hold.  The list rides
    along on the set for exactly that.
    """
    from rietx.crystallography.stephens import stephens_basis

    og = sym.OperatorGroup(label=S3_CHILD_LABEL, xyz=S3_CHILD_OPS)
    refl = sym.generate_reflections(og, (14.0, 6.0, 8.0, 90.0, 97.0, 90.0),
                                    1.5406, 90.0)
    assert refl.spacegroup == S3_CHILD_LABEL
    assert refl.operations == S3_CHILD_OPS
    rebuilt = sym.resolve_group(refl.spacegroup, refl.operations)
    assert isinstance(rebuilt, sym.OperatorGroup)
    basis = stephens_basis(rebuilt)
    # the monoclinic-b Stephens subspace, which is what P 1 m 1 gives
    assert np.array_equal(basis, stephens_basis("P 1 m 1"))
    assert len(basis) == 9
    # and a named phase's set still carries no list, so nothing changed for it
    named = sym.generate_reflections("P n m a", (8.0, 6.0, 7.0, 90.0, 90.0, 90.0),
                                     1.5406, 90.0)
    assert named.operations is None


@pytest.mark.slow
def test_a_magnetic_child_with_an_operator_list_exports_both_loops(tmp_path):
    """magCIF out: the nuclear operation loop *and* the magnetic one.

    A magnetic supercell whose nuclear group has no symbol needs both — the
    magnetic loop was always written (WP-1327) and the nuclear one is what says
    which group the bracketed label stands for.  Reading it back is refused,
    and **not for the label's sake**: WP-1328 D3 refuses any magCIF stating a
    magnetic structure in a cell that is not the parent cell, which every
    commensurate k ≠ 0 supercell is.  The refusal is quoted here so the
    boundary is pinned rather than assumed, and so that the day that reader
    arrives this test is where it lands.
    """
    from rietx.crystallography import magcif

    parent = Phase(
        name="parent", space_group="P n m a",
        cell=_cell((12.6, 9.1, 9.13, 90.0, 90.0, 90.0)),
        atoms=[Atom(label="Fe1", species="Fe", x=Parameter(value=0.0979),
                    y=Parameter(value=0.25), z=Parameter(value=0.666),
                    occ=Parameter(value=1.0), biso=Parameter(value=0.4))])
    candidate = candidates("P n m a", (0.0979, 0.25, 0.666),
                           ("0", "0", "1/2")).candidates[0]
    statement = sc.magnetic_supercell(parent, candidate=candidate,
                                      magnetic_species="Fe", ion="Fe3+",
                                      magnitude=4.0, nuclear_group="magnetic")
    assert statement.child_group_named is False
    assert statement.phase.symmetry_operations is not None
    assert statement.phase.magnetic_symmetry is not None

    path = tmp_path / "magnetic_child.cif"
    structure_to_cif(Structure(phases=[statement.phase]), str(path))
    text = path.read_text(encoding="utf-8")
    assert "_space_group_symop_operation_xyz" in text
    assert "_space_group_symop_magn_operation.xyz" in text
    assert "_space_group_name_H-M_alt" in text
    for triplet in statement.phase.symmetry_operations:
        assert triplet in text

    with pytest.raises(magcif.MagCifError, match="not the parent cell"):
        structure_from_cif(str(path))


@pytest.mark.slow
def test_a_synthetic_round_trip_and_a_whole_report_on_an_unnamed_group():
    """One amplitude recovered from a cold start, and ``report()`` completes.

    The end-to-end arm, and the second half is not decoration: the real
    Ba₂FeSbSe₅ S3(a,b) acceptance fit refined for **1268 s** and then died in
    ``report()``, on a ``reflection_orbits`` call in ``report.texture`` that
    read the frozen ``ReflectionSet.spacegroup`` string — a *label* for such a
    phase — and handed it to the symbol resolver.  ``report.satellites`` had
    three more of the same, and ``irreps.primitive_basis`` keyed its cache on a
    symbol.  All four are fixed; this is what says so, because a phase that
    refines and cannot be reported is not usable and no unit test of the
    forward model would have noticed.
    """
    from rietx.crystallography.magnetic.supercell import (
        displacive_statement,
        seed_distortion_amplitudes,
    )
    from rietx.schemas.instrument import BackgroundChebyshev
    from rietx.schemas.pattern import PatternData

    parent = Phase(
        name="parent", space_group="P n m a",
        cell=_cell((12.0, 9.0, 8.0, 90.0, 90.0, 90.0)),
        atoms=[
            Atom(label="Ba1", species="Ba", x=Parameter(value=0.11),
                 y=Parameter(value=0.13), z=Parameter(value=0.17),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.9)),
            Atom(label="Fe1", species="Fe", x=Parameter(value=0.19),
                 y=Parameter(value=0.25), z=Parameter(value=0.23),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.5)),
            Atom(label="Se1", species="Se", x=Parameter(value=0.29),
                 y=Parameter(value=0.31), z=Parameter(value=0.37),
                 occ=Parameter(value=1.0), biso=Parameter(value=0.7)),
        ])
    statement = displacive_statement(parent, ("1/2", "0", "1/2"),
                                     irrep="S3", direction="(a,b)")
    assert statement.child_group_named is False
    assert statement.phase.symmetry_operations is not None

    instrument = INSTRUMENT.model_copy(deep=True)
    instrument.background = BackgroundChebyshev(
        coefficients=[Parameter(value=5.0), Parameter(value=0.0),
                      Parameter(value=0.0)])
    two_theta = np.arange(10.0, 70.0, 0.05)
    first = statement.phase.distortion_modes[0].name
    truth = seed_distortion_amplitudes(statement.phase, {first: 0.08},
                                       vary=False)
    y = np.asarray(rx.Refinement(
        Structure(phases=[truth]),
        instrument.model_copy(deep=True)).predict(two_theta))
    rng = np.random.default_rng(7)
    observed = y + rng.normal(0.0, np.sqrt(np.maximum(y, 1.0)))
    data = PatternData(two_theta=two_theta.tolist(),
                       intensity=observed.tolist())

    start = seed_distortion_amplitudes(statement.phase, {first: 0.03},
                                       vary=True)
    refinement = rx.Refinement(Structure(phases=[start]),
                               instrument.model_copy(deep=True))
    for target, source, scale, offset in statement.biso_ties:
        refinement.tie(target, source, scale=scale, offset=offset)
    plan = rx.RefinementPlan(stages=[rx.Stage(
        "all", ["phases.*.scale", "instrument.background.c*",
                "phases.0.distortion_modes.0.amplitude"], max_iter=120)])
    result = refinement.fit(data, plan=plan)
    assert str(result.status) == "converged"

    report = refinement.report()
    row = next(e for e in report.distortion if e.mode == first)
    assert row.amplitude_esd is not None
    assert abs(row.amplitude - 0.08) < 3.0 * row.amplitude_esd
    assert row.supported is True
    # the three arms that read the frozen reflection set all completed
    assert report.texture is not None
    assert report.strain is not None
    assert report.satellites is not None
    assert len(report.model_dump_json()) > 1000
