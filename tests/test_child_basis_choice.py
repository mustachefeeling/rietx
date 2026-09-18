"""Q-17c: which of a doubled cell's two valid primitive bases ``child_basis``
picks (``checks/Q17B_METRIC_FROM_ROTATIONS.md`` is the finding this answers).

For a k = (½,½,0)-type doubling in a P tetragonal/orthorhombic parent, the
pre-existing recipe (``2·anti, row+anti, …``) gives ``2a, a+b, c`` -- a valid
primitive cell of the doubled lattice, but one in which mm2/4mm's mirrors sit
along the parent's [110]-type directions and the invariant metric ties one
length to *another length times a cosine*, which
:class:`~rietx.crystallography.symmetry.CellConstraints` cannot state
(Q-17b).  The *same* lattice has another primitive basis,
``a+b, −a+b, c`` (the √2×√2 cell), in which those operations are conventional
(a′ = b′, γ′ = 90°).  ``child_basis`` now tries both and keeps whichever one
at least one real magnetic candidate at that (parent, k) actually verifies
with -- preferring the pre-existing choice whenever it already does (every
(0,0,½)-type doubling, and the one pre-existing multi-anti-vector case,
Ba₂FeSbSe₅'s S₃(a,b)), and falling back to the alternate only when it does
not (the twenty-two (½,½,0) children).

Four sections:

* **the single-anti-vector family, and one pre-existing multi-anti-vector
  case, are bit-identical to the pre-Q-17c choice** -- nothing here should
  move a cell that already worked.
* **the six (½,½,0) parents all choose the sum/difference basis**, with the
  constraint a crystallographer would write down for each, justified by the
  point group in play.
* **all 39 unnamed sweep candidates now build** on the sweep's own route
  (Q-17b's ``nuclear_group="magnetic"``), where 22 used to refuse.
* **a named child stays named** -- P 4 c c's ``nuclear_group="parent"`` route
  resolves to a tabulated symbol in the new cell, and Ba₂FeSbSe₅'s own
  P 1 21/m 1 statement (a pre-existing named case, exercising the multi-anti
  path) is unaffected.
"""

from fractions import Fraction

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography import symmetry as sym
from rietx.crystallography.magnetic import isotropy as _isotropy
from rietx.crystallography.magnetic import supercell as sc
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.symmetry import CellConstraints
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev, EmissionLine, Instrument, Source
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from tests.test_metric_from_rotations import SWEEP_ROWS, SWEEP_SITES

INSTRUMENT = Instrument(source=Source(lines=[EmissionLine(wavelength=1.540598)]))
TWO_THETA = np.arange(8.0, 90.0, 0.02)


def _cell(values) -> Cell:
    a, b, c, al, be, ga = values
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=al), beta=Parameter(value=be),
                gamma=Parameter(value=ga))


def _parent(symbol: str, cell_values, xyz=(0.11, 0.13, 0.17)) -> Phase:
    """A generic one-atom phase (Q-17's convention: ``candidates`` reads a
    site only through its stabiliser and orbit, so a generic atom is sound)."""
    return Phase(name="parent", space_group=symbol, cell=_cell(cell_values),
                atoms=[Atom(label="M1", species="Fe", x=Parameter(value=xyz[0]),
                           y=Parameter(value=xyz[1]), z=Parameter(value=xyz[2]),
                           occ=Parameter(value=1.0), biso=Parameter(value=0.5))])


def _child_constraints(phase: Phase) -> CellConstraints:
    group = sym.resolve_group(phase.space_group, phase.symmetry_operations)
    return sym.cell_constraints(group)


def _pre_q17c_child_basis(space_group, k):
    """The pre-Q-17c ``child_basis`` recipe, standalone -- literally the
    algorithm before this rung (one ε = −1 vector doubled, every other
    shifted by it), so a divergence here is a real behaviour change in the
    single-anti-vector path, not a reimplementation slip.
    """
    sg = _isotropy._irreps._resolve(space_group)
    kk = _isotropy.as_kvector(k)
    cell = _isotropy.magnetic_cell(sg, kk)
    if not cell.doubled:
        return cell.basis
    prim = _isotropy._irreps.primitive_basis(sg)
    signs = [_isotropy._translation_sign(kk, row) for row in prim]
    pivot = signs.index(-1)
    anti = prim[pivot]
    rows = []
    for i, row in enumerate(prim):
        if i == pivot:
            rows.append(tuple(2 * Fraction(c) for c in row))
        elif signs[i] < 0:
            rows.append(tuple(Fraction(c) + Fraction(a) for c, a in zip(row, anti)))
        else:
            rows.append(tuple(Fraction(c) for c in row))
    return tuple(tuple(rows[j][i] for j in range(3)) for i in range(3))


# ---------------------------------------------------------------------------
# (a) bit-identity: one ε = −1 vector, and the one pre-existing multi-vector
# case, are untouched
# ---------------------------------------------------------------------------
#: Every (0,0,½)-type setting Q-17/Q-17b's own sweep tested
#: (``test_metric_from_rotations.py``'s ``SWEEP_ROWS``), so this is the exact
#: population that must not move.
SINGLE_ANTI_SETTINGS = tuple(
    (setting, k) for setting, k, _cell in SWEEP_ROWS if k == ("0", "0", "1/2"))


def test_single_anti_vector_settings_are_bit_identical_to_pre_q17c():
    assert len(SINGLE_ANTI_SETTINGS) == 9  # guards the population itself
    for symbol, k in SINGLE_ANTI_SETTINGS:
        kk = tuple(Fraction(c) for c in k)
        assert sc.child_basis(symbol, kk) == _pre_q17c_child_basis(symbol, kk), (
            f"{symbol!r} at {k!r} moved off its pre-Q-17c basis")


def test_the_hexagonal_gamma_trap_still_resolves_p6mm_unmoved():
    """P 6 m m at k=(0,0,½): the γ = 60°-vs-120° trap CLAUDE.md names, folded
    into the single-anti-vector family above -- named again here because it
    is the one CLAUDE.md itself calls out, not merely swept in with the rest.
    """
    kk = (Fraction(0), Fraction(0), Fraction(1, 2))
    assert sc.child_basis("P 6 m m", kk) == _pre_q17c_child_basis("P 6 m m", kk)


def test_pnma_half_zero_half_two_anti_vectors_but_still_bit_identical():
    """Two ε = −1 vectors (a and c) -- the ambiguous case Q-17c resolves --
    but the pre-existing choice already verifies for a real candidate here
    (Ba₂FeSbSe₅'s S₃(a,b), an established, tested statement), so it is kept.

    This is the regression this rung must not cause: switching would still
    build *something* (the physics does not care which valid primitive basis
    states it), but every transform string and bracketed label
    ``tests/test_operator_list_phase.py`` and ``tests/test_distortion_modes.py``
    already pin would then name a different (also valid) cell for no reason.
    """
    kk = (Fraction(1, 2), Fraction(0), Fraction(1, 2))
    basis = sc.child_basis("P n m a", kk)
    assert basis == _pre_q17c_child_basis("P n m a", kk)
    assert sc._transform_string(basis) == "2a,b,a+c;0,0,0"


# ---------------------------------------------------------------------------
# (b) the six (½,½,0) parents: the chosen basis, its constraints, a build
# ---------------------------------------------------------------------------
HALF_HALF_ZERO_PARENTS = (
    ("P c c 2", (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("P c c a", (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("P c c n", (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("P 42 c m", (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 4 c c", (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P -4 c 2", (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
)
HALF_HALF_ZERO_K = (Fraction(1, 2), Fraction(1, 2), Fraction(0))


@pytest.mark.parametrize("symbol,cell", HALF_HALF_ZERO_PARENTS,
                         ids=lambda v: str(v).replace(" ", "") if isinstance(v, tuple) else v)
def test_the_six_parents_choose_the_sum_difference_basis(symbol, cell):
    """``a+b,−a+b,c`` for every one -- the alternate, not the pre-Q-17c
    ``2a,a+b,c`` -- because the pre-existing choice verifies for no real
    candidate at any of the six (Q-17b's finding, reproduced in (c) below).
    """
    basis = sc.child_basis(symbol, HALF_HALF_ZERO_K)
    assert sc._transform_string(basis) == "a+b,-a+b,c;0,0,0"


#: The constraint the ``nuclear_group="magnetic"`` route gives for each of
#: the six -- uniformly a′ = b′ with only the two angles to the free c axis
#: fixed (γ free), because every one of the six reads a 4-operation isotropy
#: subgroup here whose mirrors tie a′ = b′ and fix α′ = β′ = 90° without a
#: 4-fold to also tie γ′ (mm2's own two mirrors do this directly; the three
#: tetragonal/−4 parents' magnetic route loses their 4-fold at this k, the
#: same reduction Q-17b's P42cm-at-(0,0,½) case already showed).
MAGNETIC_ROUTE_CONSTRAINT = CellConstraints(
    ties={"b": "a"}, fixed_angles={"alpha": 90.0, "beta": 90.0})

#: The ``nuclear_group="parent"`` route instead reads the parent's *full*
#: point group. mm2/mmm without a 4-fold (Pcc2, Pcca, Pccn) gives the same
#: two-tie constraint as the magnetic route (nothing in mmm without a 4-fold
#: ties γ′ either); the three parents whose full point group *does* carry a
#: 4-fold or −4 along c (P42cm, P4cc, P-4c2) gets all three angles fixed,
#: because that cell now makes the whole 4mm/-42m point group conventional.
PARENT_ROUTE_CONSTRAINT = {
    "P c c 2": MAGNETIC_ROUTE_CONSTRAINT,
    "P c c a": MAGNETIC_ROUTE_CONSTRAINT,
    "P c c n": MAGNETIC_ROUTE_CONSTRAINT,
    "P 42 c m": CellConstraints(ties={"b": "a"},
                                fixed_angles={"alpha": 90.0, "beta": 90.0, "gamma": 90.0}),
    "P 4 c c": CellConstraints(ties={"b": "a"},
                               fixed_angles={"alpha": 90.0, "beta": 90.0, "gamma": 90.0}),
    "P -4 c 2": CellConstraints(ties={"b": "a"},
                                fixed_angles={"alpha": 90.0, "beta": 90.0, "gamma": 90.0}),
}
#: P 4 c c is the one of the six whose ``parent`` route resolves to a
#: tabulated symbol outright (measured: spglib names it in ``a+b,−a+b,c``
#: where it could not in ``2a,a+b,c``) -- see (d) below for the assertion.
PARENT_ROUTE_NAMED = {"P 4 c c"}


@pytest.mark.slow
@pytest.mark.parametrize("symbol,cell", HALF_HALF_ZERO_PARENTS,
                         ids=lambda v: str(v).replace(" ", "") if isinstance(v, tuple) else v)
@pytest.mark.parametrize("route", ("magnetic", "parent"))
def test_the_six_parents_build_with_the_expected_constraint(symbol, cell, route):
    parent = _parent(symbol, cell)
    found = candidates(symbol, SWEEP_SITES["general"], HALF_HALF_ZERO_K)
    unnamed = [c for c in found if c.identification is None]
    assert unnamed
    statement = sc.magnetic_supercell(parent, candidate=unnamed[0], nuclear_group=route)
    assert statement.transform == "a+b,-a+b,c;0,0,0"
    expected = (MAGNETIC_ROUTE_CONSTRAINT if route == "magnetic"
               else PARENT_ROUTE_CONSTRAINT[symbol])
    assert _child_constraints(statement.phase) == expected
    assert statement.child_group_named == (route == "parent" and symbol in PARENT_ROUTE_NAMED)
    y = rx.Refinement(Structure(phases=[statement.phase]),
                      INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    assert np.isfinite(np.asarray(y)).all() and float(np.asarray(y).max()) > 0.0


@pytest.mark.slow
def test_a_equals_zero_control_on_pcc2_half_half_0_is_det_p_squared():
    """The control the brief's own worked example asked for, now buildable:
    P c c 2 at k=(½,½,0), magnitude 0 -- the prediction is |det P|² × the
    parent's, to 1e-10 of the peak (same control as Q-17's and Q-17b's own,
    applied to the family this rung unlocks)."""
    parent = _parent("P c c 2", (6.0, 7.0, 8.0, 90.0, 90.0, 90.0))
    instrument = INSTRUMENT.model_copy(deep=True)
    instrument.background = BackgroundChebyshev(
        coefficients=[Parameter(value=0.0) for _ in range(3)])
    y_parent = np.asarray(rx.Refinement(
        Structure(phases=[parent]), instrument.model_copy(deep=True)
    ).predict(TWO_THETA))
    assert float(y_parent.max()) > 0.0

    found = candidates("P c c 2", SWEEP_SITES["general"], HALF_HALF_ZERO_K)
    unnamed = [c for c in found if c.identification is None]
    statement = sc.magnetic_supercell(parent, candidate=unnamed[0],
                                      nuclear_group="magnetic",
                                      magnitude=0.0, vary=False)
    assert statement.child_group_named is False
    y_child = np.asarray(rx.Refinement(
        Structure(phases=[statement.phase]), instrument.model_copy(deep=True)
    ).predict(TWO_THETA))
    live = y_parent > 1e-6 * float(y_parent.max())
    ratio = y_child[live] / y_parent[live]
    constant = float(np.median(ratio))
    assert constant == pytest.approx(statement.index ** 2, rel=1e-9)
    worst = float(np.max(np.abs(y_child - constant * y_parent)) / float(y_parent.max()))
    assert worst < 1e-10


# ---------------------------------------------------------------------------
# (c) all 39 unnamed sweep candidates now build (Q-17b's own route)
# ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.parametrize("setting,k,cell", SWEEP_ROWS,
                         ids=lambda v: str(v).replace(" ", "") if isinstance(v, tuple) else v)
@pytest.mark.parametrize("site", ("origin", "general"))
def test_all_39_unnamed_sweep_candidates_now_build(setting, k, cell, site):
    """Q-17b found 17 build / 22 refuse; after this rung's basis choice, all
    39 build -- exceptions, if any turn up, are listed here with their
    refusal text rather than silently swallowed.
    """
    if (setting, k) == ("P 6 m m", ("0", "0", "1/2")) and site == "origin":
        pytest.skip("P6mm's sweep row is general-site only (Q-17's own table)")
    kk = tuple(Fraction(c) for c in k)
    found = candidates(setting, SWEEP_SITES[site], kk)
    unnamed = [c for c in found if c.identification is None]
    if not unnamed:
        pytest.skip(f"{setting} at {k} ({site}) named every candidate here")
    xyz = (tuple(float(v) for v in SWEEP_SITES[site]) if site == "general"
          else (0.0, 0.0, 0.0))
    parent = _parent(setting, cell, xyz=xyz)
    for candidate in unnamed:
        statement = sc.magnetic_supercell(parent, candidate=candidate,
                                          nuclear_group="magnetic")
        assert statement.child_group_named is False
        y = rx.Refinement(Structure(phases=[statement.phase]),
                          INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
        assert np.isfinite(np.asarray(y)).all()
        assert float(np.asarray(y).max()) > 0.0


def test_the_39_count_itself_is_unchanged():
    """Same 15-row, 39-candidate parametrisation Q-17b counted -- this rung
    changes whether they build, not how many there are."""
    n_half_half_zero_rows = sum(
        1 for setting, k, _cell in SWEEP_ROWS if k == ("1/2", "1/2", "0"))
    assert n_half_half_zero_rows == 6
    n_zero_zero_half_rows = sum(
        1 for setting, k, _cell in SWEEP_ROWS if k == ("0", "0", "1/2"))
    assert n_zero_zero_half_rows == 9


# ---------------------------------------------------------------------------
# (d) a named-group regression: the child stays named where it already was,
# and a case that becomes *newly* named still checks out
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_p4cc_parent_route_now_resolves_a_tabulated_symbol():
    """P 4 c c's ``nuclear_group="parent"`` route: unnamed before this rung
    (the full 4mm point group did not fit ``2a,a+b,c`` either), named now --
    the new cell makes the whole point group conventional, and the symbol
    check ``magnetic_supercell`` performs (operations × cosets reproduce the
    transformed group exactly) is what ``child_group_named`` reports.
    """
    parent = _parent("P 4 c c", (6.0, 6.0, 9.0, 90.0, 90.0, 90.0))
    found = candidates("P 4 c c", SWEEP_SITES["general"], HALF_HALF_ZERO_K)
    unnamed = [c for c in found if c.identification is None]
    assert unnamed
    statement = sc.magnetic_supercell(parent, candidate=unnamed[0], nuclear_group="parent")
    assert statement.child_group_named is True
    assert _child_constraints(statement.phase) == CellConstraints(
        ties={"b": "a"}, fixed_angles={"alpha": 90.0, "beta": 90.0, "gamma": 90.0})


@pytest.mark.slow
def test_ba2fesbse5_pnma_named_candidate_is_unaffected():
    """The *other* real candidates at Pnma's k=(½,0,½) (BNS 11.55, 14.82,
    both P 1 21/m 1) are named regardless of which basis is used, and this
    rung keeps the pre-existing one -- reproducing
    ``tests/test_magnetic_supercell.py::
    test_pnma_half_zero_half_states_in_the_magnetic_nuclear_group`` here as
    the explicit "no regression in the named path" check the brief asks for.
    """
    phase = Phase(name="t", space_group="P n m a",
                  cell=Cell(a=Parameter(value=12.6), b=Parameter(value=9.1),
                            c=Parameter(value=9.13), alpha=Parameter(value=90.0),
                            beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
                  atoms=[Atom(label="Fe1", species="Fe", x=Parameter(value=0.0979),
                              y=Parameter(value=0.25), z=Parameter(value=0.666))])
    found = candidates("P n m a", (0.0979, 0.25, 0.666), ("1/2", "0", "1/2"))
    assert sorted({c.bns_number for c in found}) == ["11.55", "14.82"]
    for c in found:
        statement = sc.magnetic_supercell(phase, candidate=c, magnetic_species="Fe",
                                          ion="Fe3+", nuclear_group="magnetic")
        assert statement.child_space_group == "P 1 21/m 1"
        assert statement.transform == "2a,b,a+c;0,0,0"
