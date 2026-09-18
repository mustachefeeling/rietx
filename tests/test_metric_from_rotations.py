"""Cell metric constraints derived from the rotation set itself (Q-17b).

Q-17 (``operator-list-phase``) let a phase carry its own operation list, but
``cell_constraints`` still needed a *tabulated* group sharing that list's
point group and lattice (``OperatorGroup.closest_type``, via gemmi's
symmorphic derivation) to say which cell edges tie and which angles symmetry
fixes — an orientation lookup that fails for a child cell whose axes are not
conventional for its own point group, which is every one of the 39 unnamed
candidates M-7's all-group k-sweep produced.  This module derives the same
:class:`~rietx.crystallography.symmetry.CellConstraints` directly from the
rotation set (Rᵀ·G·R = G — the module docstring of ``symmetry.py`` has the
derivation), so no lookup is needed at all, and wires it in as a cross-check
when a tabulated group *does* resolve and as the sole authority when none
does.

Four claims, one section each:

* **the lookup's nine settings, and the R-centred trigonal one, all agree**
  with the direct derivation — the acceptance floor, since disagreement on a
  *named* setting is a bug in the new code, never a tolerance to widen.
* **the Rᵀ-vs-R convention is pinned**, not merely dimension-checked, by a
  case where the wrong convention gives a *different, wrong* angle.
* **the five probed sweep children build**, each with the constraint a
  crystallographer would write down for it, justified in one line.
* **all 29 sweep rows** build a child and predict a finite pattern, save the
  one whose true constraint (a length tied to another length times a cosine)
  :class:`CellConstraints` cannot express — refused by name, not widened past.
"""

from fractions import Fraction

import gemmi
import numpy as np
import pytest

import rietx as rx
from rietx.crystallography import symmetry as sym
from rietx.crystallography.magnetic import supercell as sc
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.symmetry import (
    CellConstraints,
    OperatorGroup,
    cell_constraints,
    cell_constraints_from_rotations,
    get_spacegroup,
)
from rietx.crystallography.wyckoff import adp_basis
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev, EmissionLine, Instrument, Source
from rietx.schemas.structure import Atom, Cell, Phase, Structure

INSTRUMENT = Instrument(source=Source(lines=[EmissionLine(wavelength=1.540598)]))
TWO_THETA = np.arange(8.0, 90.0, 0.02)


def _cell(values) -> Cell:
    a, b, c, al, be, ga = values
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=al), beta=Parameter(value=be),
                gamma=Parameter(value=ga))


def _parent(symbol: str, cell_values, xyz=(0.11, 0.13, 0.17)) -> Phase:
    """A generic one-atom phase — a nominal cell and a general position.

    ``candidates`` reads a site only through its stabiliser and its orbit
    (Q-17), so a generic atom is sound: nothing here is a fitted or published
    structure.
    """
    return Phase(name="parent", space_group=symbol, cell=_cell(cell_values),
                atoms=[Atom(label="M1", species="Fe", x=Parameter(value=xyz[0]),
                           y=Parameter(value=xyz[1]), z=Parameter(value=xyz[2]),
                           occ=Parameter(value=1.0), biso=Parameter(value=0.5))])


# ---------------------------------------------------------------------------
# the nine tabulated settings (+ R-centred trigonal), agreeing with the lookup
# ---------------------------------------------------------------------------
#: One representative symbol per :func:`cell_constraints` branch — Q-17's own
#: nine settings (``tests/test_operator_list_phase.py``) plus the R-centred
#: trigonal axis choice the brief asks to add, since ``ext == "R"`` is the one
#: branch Q-17's own list does not reach.
NAMED_SETTINGS = ("P n m a", "C m c m", "F d -3 m:2", "P 6_3/m m c", "R -3 c:H",
                  "R -3 c:R", "P 1 21/m 1", "I 4_1/a m d:2", "P -1")


def _rotations_of(symbol: str) -> list[np.ndarray]:
    sg = get_spacegroup(symbol)
    return [np.array(op.rot, dtype=np.int64) // gemmi.Op.DEN
            for op in sg.operations()]


@pytest.mark.parametrize("symbol", NAMED_SETTINGS)
def test_the_derivation_agrees_with_the_lookup_on_every_named_setting(symbol):
    """Direct derivation == the tabulated lookup, on all nine settings + R.

    Q-17's nine settings were chosen to cover every distinct branch of
    ``cell_constraints`` (monoclinic's three unique-axis choices are one
    branch, parametrised by ``sg.monoclinic_unique_axis()`` — only ``b`` is in
    this list, but ``P 2 1 1`` / ``P 1 1 2`` are covered directly below); this
    adds ``R -3 c:R``, the one branch (``ext == 'R'``) none of the nine reach.
    """
    sg = get_spacegroup(symbol)
    derived = cell_constraints_from_rotations(_rotations_of(symbol))
    assert derived == cell_constraints(sg)


@pytest.mark.parametrize("symbol,axis", [("P 2 1 1", "a"), ("P 1 2 1", "b"),
                                         ("P 1 1 2", "c")])
def test_the_derivation_agrees_with_the_lookup_on_all_three_monoclinic_axes(
        symbol, axis):
    """The one branch a single ``b``-unique example cannot exercise."""
    sg = get_spacegroup(symbol)
    assert sg.monoclinic_unique_axis() == axis
    derived = cell_constraints_from_rotations(_rotations_of(symbol))
    assert derived == cell_constraints(sg)


def test_the_wired_cross_check_agrees_too_not_only_the_bare_function():
    """``cell_constraints`` on an ``OperatorGroup`` whose list is a named
    group's own — the actual code path a phase's cell ties go through,
    exercising the cross-check branch rather than only the free function.
    """
    for symbol in (*NAMED_SETTINGS, "P 2 1 1", "P 1 1 2"):
        sg = get_spacegroup(symbol)
        triplets = tuple(op.triplet() for op in sg.operations())
        og = OperatorGroup(label="[cross-check]", xyz=triplets)
        assert cell_constraints(og) == cell_constraints(sg)


def test_a_named_group_disagreeing_with_its_own_list_refuses_by_name(monkeypatch):
    """The D4 refusal: on disagreement, ``cell_constraints`` refuses by name.

    A genuine disagreement should not arise for a correctly-functioning list
    — ``closest_type`` is found by matching the list's own rotations, so the
    tabulated group's operations and the list's are the same matrices and the
    two derivations run over the same finite group — which is exactly why
    this is a *safety net* rather than a case real data hits.  Testing it
    therefore forces the mismatch directly: ``_closest_type`` is patched to
    return a cubic group (three ties, three fixed angles) for a triclinic
    (identity-only) operation list, whose own derivation is the empty
    constraint.  The two visibly disagree, and the refusal names both.
    """
    og = OperatorGroup(label="[disagree]", xyz=("x,y,z",))
    cubic = get_spacegroup("P m -3 m")
    monkeypatch.setattr(sym, "_closest_type", lambda xyz: cubic)
    with pytest.raises(ValueError, match="disagree"):
        cell_constraints(og)


# ---------------------------------------------------------------------------
# the Rᵀ-vs-R convention, pinned rather than merely dimension-checked
# ---------------------------------------------------------------------------
def test_the_direct_metric_convention_is_rt_g_r_not_r_g_rt():
    """Hexagonal is the discriminator, not a monoclinic β ≠ 90 setting.

    The brief suggests a monoclinic setting with β ≠ 90 as the case that
    would fail under the other convention; measured, it does not discriminate
    at all: every standard monoclinic 2-fold (any unique axis) is a diagonal
    ±1 matrix, symmetric under transposition, so ``Rᵀ·G·R`` and ``R·G·Rᵀ``
    give the *same* nullspace regardless of β's numeric value — the wrong
    convention would build a monoclinic phase with the right constraints for
    the wrong reason and this test would not catch it (see the report's
    findings section). Hexagonal's 3-fold/6-fold rotations are genuinely
    asymmetric matrices in the hexagonal (120°) basis and do discriminate,
    exactly the case CLAUDE.md already names for ``wyckoff.adp_basis`` one
    rank up: the wrong convention gives cos γ = +½ (γ = 60°), the right one
    cos γ = -½ (γ = 120°, the tabulated setting's own value).
    """
    rots = _rotations_of("P 6/m m m")
    right = adp_basis([r.T for r in rots])  # Rᵀ·G·R = G — used by this module
    wrong = adp_basis(rots)                 # R·G·Rᵀ = G — the reciprocal-tensor law
    # both bases are 2-dimensional and agree on G11=G22 (a = b free) and
    # G33 free; they disagree only in the sign relating G12 to G11
    row_right = next(r for r in right if r[3] != 0)
    row_wrong = next(r for r in wrong if r[3] != 0)
    assert row_right[3] == -row_right[0] // 2 * 2 // 2  # cos γ = -1/2 relative to a²
    cos_right = row_right[3] / row_right[0]
    cos_wrong = row_wrong[3] / row_wrong[0]
    assert cos_right == pytest.approx(-0.5)
    assert cos_wrong == pytest.approx(0.5)
    assert cos_right != cos_wrong

    derived = cell_constraints_from_rotations(rots)
    lookup = cell_constraints(get_spacegroup("P 6/m m m"))
    assert derived.fixed_angles["gamma"] == pytest.approx(120.0)
    assert derived == lookup  # would be 60.0 and disagree, under the wrong law


# ---------------------------------------------------------------------------
# the five probed sweep children build, with the constraint a
# crystallographer would write down for each -- OR are refused for a named,
# expressible reason (see the report: 2 of the 5 the brief names are refused
# by BOTH nuclear_group routes, not built, and this file follows the measured
# behaviour rather than the brief's worked example -- see "what was wrong").
# ---------------------------------------------------------------------------
SWEEP_SITES = {"origin": (Fraction(0), Fraction(0), Fraction(0)),
              "general": (Fraction(11, 100), Fraction(13, 100), Fraction(17, 100))}


def _child_constraints(phase: Phase) -> CellConstraints:
    """The :class:`CellConstraints` a built child phase's own group states."""
    group = sym.resolve_group(phase.space_group, phase.symmetry_operations)
    return cell_constraints(group)


@pytest.mark.slow
@pytest.mark.parametrize("route", ("magnetic", "parent"))
def test_pcc2_half_half_0_now_builds_after_q17c_basis_choice(route):
    """P c c 2 at k=(½,½,0): built, not refused -- superseded by Q-17c.

    This test used to pin the opposite: ``child_basis`` picking ``2a,a+b,c``
    for this k (mm2's mirrors along the parent's [110]-type directions, an
    invariant metric that ties b² = 2ab·cos γ, inexpressible by
    ``CellConstraints``). Q-17c (``crystallography/magnetic/supercell.py::
    child_basis``) made that choice conditional: when the pre-existing
    ``(2·anti, row+anti, …)`` cell verifies for no real candidate at this
    (parent, k) at all -- true here, on both routes, exactly what this test
    used to assert -- ``child_basis`` now switches to the sum/difference
    primitive basis of the *same* lattice, ``a+b,−a+b,c`` (det P = 2 either
    way), in which mm2's mirrors are conventional (a′ = b′, γ′ = 90°). Both
    ``nuclear_group`` routes read the same 4-operation isotropy subgroup here
    (mm2 has no larger point group to fall back to), so both agree.
    """
    parent = _parent("P c c 2", (6.0, 7.0, 8.0, 90.0, 90.0, 90.0))
    kk = (Fraction(1, 2), Fraction(1, 2), Fraction(0))
    found = candidates("P c c 2", SWEEP_SITES["general"], kk)
    unnamed = [c for c in found if c.identification is None]
    assert unnamed
    statement = sc.magnetic_supercell(parent, candidate=unnamed[0], nuclear_group=route)
    assert statement.child_group_named is False
    assert statement.transform == "a+b,-a+b,c;0,0,0"
    assert _child_constraints(statement.phase) == CellConstraints(
        ties={"b": "a"}, fixed_angles={"alpha": 90.0, "beta": 90.0})
    y = rx.Refinement(Structure(phases=[statement.phase]),
                      INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    assert np.isfinite(np.asarray(y)).all() and float(np.asarray(y).max()) > 0.0


@pytest.mark.slow
@pytest.mark.parametrize("route", ("magnetic", "parent"))
def test_p4cc_half_half_0_now_builds_after_q17c_basis_choice(route):
    """P 4 c c at k=(½,½,0): the same ``a+b,−a+b,c`` cell, also built now.

    The ``magnetic`` route reads the same 4-operation isotropy subgroup as
    Pcc2's above (mm2-shaped constraints); the ``parent`` route reads the
    full 8-operation 4mm point group, which the new cell makes *conventional*
    tetragonal outright -- named, not merely derived (measured: spglib
    resolves the symbol in ``a+b,−a+b,c`` where it could not in ``2a,a+b,c``).
    """
    parent = _parent("P 4 c c", (6.0, 6.0, 9.0, 90.0, 90.0, 90.0))
    kk = (Fraction(1, 2), Fraction(1, 2), Fraction(0))
    found = candidates("P 4 c c", SWEEP_SITES["general"], kk)
    unnamed = [c for c in found if c.identification is None]
    assert unnamed
    statement = sc.magnetic_supercell(parent, candidate=unnamed[0], nuclear_group=route)
    assert statement.transform == "a+b,-a+b,c;0,0,0"
    if route == "magnetic":
        assert statement.child_group_named is False
        assert _child_constraints(statement.phase) == CellConstraints(
            ties={"b": "a"}, fixed_angles={"alpha": 90.0, "beta": 90.0})
    else:
        assert statement.child_group_named is True
        assert _child_constraints(statement.phase) == CellConstraints(
            ties={"b": "a"},
            fixed_angles={"alpha": 90.0, "beta": 90.0, "gamma": 90.0})
    y = rx.Refinement(Structure(phases=[statement.phase]),
                      INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    assert np.isfinite(np.asarray(y)).all() and float(np.asarray(y).max()) > 0.0


@pytest.mark.slow
def test_cmm2_0_0_half_child_ties_b_to_a_fixes_alpha_beta():
    """C m m 2 at k=(0,0,½): the doubled axis is polar c, untouched by mm2.

    The two mirrors of mm2 exchange a and b exactly (no sign ambiguity along
    the doubled axis), so a = b is forced with both angles to the free c
    axis (α, β) held at 90°; γ (between the tied a, b) is left free because
    nothing in this 4-operation subgroup fixes it. Both nuclear_group routes
    agree here because Cmm2's own point group has only these 4 elements, so
    "magnetic" and "parent" read the same group.
    """
    parent = _parent("C m m 2", (6.0, 7.0, 9.0, 90.0, 90.0, 90.0))
    kk = (Fraction(0), Fraction(0), Fraction(1, 2))
    found = candidates("C m m 2", SWEEP_SITES["general"], kk)
    unnamed = [c for c in found if c.identification is None]
    assert unnamed
    for route in ("magnetic", "parent"):
        statement = sc.magnetic_supercell(parent, candidate=unnamed[0],
                                          nuclear_group=route)
        assert statement.child_group_named is False
        cc = _child_constraints(statement.phase)
        assert cc == CellConstraints(ties={"b": "a"},
                                     fixed_angles={"alpha": 90.0, "beta": 90.0})
    y = rx.Refinement(Structure(phases=[statement.phase]),
                      INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    assert np.isfinite(np.asarray(y)).all() and float(np.asarray(y).max()) > 0.0


@pytest.mark.slow
def test_p42cm_0_0_half_child_magnetic_route_ties_b_to_a_gamma_free():
    """P 4₂ c m at k=(0,0,½), the magnetic-group nuclear part: a = b survives,
    γ does not.

    The magnetic isotropy subgroup at this k keeps only 4 of the parent's 8
    point-group operations (the ones this order-parameter direction does not
    break) -- fewer than the full 4mm point group, so it loses the 4-fold
    that ties γ to 90° along with a = b; only two of tetragonal's three
    constraints survive. Contrast the next test's ``nuclear_group="parent"``
    route, which keeps the full point group and gets all three -- the route
    the brief's "a = b, 90/90/90" worked example actually describes.
    """
    parent = _parent("P 42 c m", (6.0, 6.0, 9.0, 90.0, 90.0, 90.0))
    kk = (Fraction(0), Fraction(0), Fraction(1, 2))
    found = candidates("P 42 c m", SWEEP_SITES["general"], kk)
    unnamed = [c for c in found if c.identification is None]
    assert unnamed
    statement = sc.magnetic_supercell(parent, candidate=unnamed[0],
                                      nuclear_group="magnetic")
    assert statement.child_group_named is False
    cc = _child_constraints(statement.phase)
    assert cc == CellConstraints(ties={"b": "a"},
                                 fixed_angles={"alpha": 90.0, "beta": 90.0})
    y = rx.Refinement(Structure(phases=[statement.phase]),
                      INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    assert np.isfinite(np.asarray(y)).all() and float(np.asarray(y).max()) > 0.0


@pytest.mark.slow
def test_p42cm_0_0_half_child_parent_route_is_the_full_tetragonal_constraint():
    """The same k, ``nuclear_group="parent"``: a = b, all three angles 90°.

    Doubling the polar c axis breaks no operation of 4mm (every one of its
    eight elements fixes c, up to a sign), so the parent's full point group
    carries through unchanged and the child is tetragonal exactly as the
    brief's worked example says -- this is the route that example describes.
    """
    parent = _parent("P 42 c m", (6.0, 6.0, 9.0, 90.0, 90.0, 90.0))
    kk = (Fraction(0), Fraction(0), Fraction(1, 2))
    found = candidates("P 42 c m", SWEEP_SITES["general"], kk)
    unnamed = [c for c in found if c.identification is None]
    assert unnamed
    statement = sc.magnetic_supercell(parent, candidate=unnamed[0],
                                      nuclear_group="parent")
    cc = _child_constraints(statement.phase)
    assert cc == CellConstraints(ties={"b": "a"},
                                 fixed_angles={"alpha": 90.0, "beta": 90.0,
                                              "gamma": 90.0})
    y = rx.Refinement(Structure(phases=[statement.phase]),
                      INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    assert np.isfinite(np.asarray(y)).all() and float(np.asarray(y).max()) > 0.0


@pytest.mark.slow
def test_p42_mnm_0_0_half_child_both_routes():
    """P 4₂/m n m at k=(0,0,½): same reduced-vs-full pattern as P4₂cm above --
    magnetic route keeps a = b only, parent route keeps all three.
    """
    parent = _parent("P 42/m n m", (6.0, 6.0, 9.0, 90.0, 90.0, 90.0))
    kk = (Fraction(0), Fraction(0), Fraction(1, 2))
    found = candidates("P 42/m n m", SWEEP_SITES["general"], kk)
    unnamed = [c for c in found if c.identification is None]
    assert unnamed
    magnetic = sc.magnetic_supercell(parent, candidate=unnamed[0],
                                     nuclear_group="magnetic")
    assert magnetic.child_group_named is False
    assert _child_constraints(magnetic.phase) == CellConstraints(
        ties={"b": "a"}, fixed_angles={"alpha": 90.0, "beta": 90.0})
    parent_route = sc.magnetic_supercell(parent, candidate=unnamed[0],
                                         nuclear_group="parent")
    assert _child_constraints(parent_route.phase) == CellConstraints(
        ties={"b": "a"},
        fixed_angles={"alpha": 90.0, "beta": 90.0, "gamma": 90.0})
    y = rx.Refinement(Structure(phases=[magnetic.phase]),
                      INSTRUMENT.model_copy(deep=True)).predict(TWO_THETA)
    assert np.isfinite(np.asarray(y)).all() and float(np.asarray(y).max()) > 0.0


# ---------------------------------------------------------------------------
# all 29 sweep rows (39 candidates) build a child or name their refusal
# ---------------------------------------------------------------------------
#: Transcribed verbatim from ``tests/test_operator_list_phase.py``'s
#: ``SWEEP_UNNAMED`` (the brief: "reuse its parametrisation"), paired here
#: with a nominal cell consistent with the parent's own crystal system.
SWEEP_ROWS = (
    ("P c c 2", ("1/2", "1/2", "0"), (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("C m m 2", ("0", "0", "1/2"), (6.0, 7.0, 9.0, 90.0, 90.0, 90.0)),
    ("P c c a", ("1/2", "1/2", "0"), (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("P c c n", ("1/2", "1/2", "0"), (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("P 42 c m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42 c m", ("1/2", "1/2", "0"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42 n m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 4 c c", ("1/2", "1/2", "0"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P -4 c 2", ("1/2", "1/2", "0"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/m c m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/n n m:1", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/m n m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/n c m:1", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P n -3 m:1", ("0", "0", "1/2"), (6.0, 6.0, 6.0, 90.0, 90.0, 90.0)),
    ("P 6 m m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 120.0)),
)

#: **Historical** (pre-Q-17c): every one of the 39 unnamed candidates at
#: k = (½,½,0) used to be refused here, and every one at k = (0,0,½) built —
#: a clean split by k-family. The reason was ``child_basis``'s canonical cell
#: for a (½,½,0)-type doubling, ``2a,a+b,c``, not being orthogonal-friendly
#: for any of these mm2/4mm point groups (it forced a length tied to another
#: length times a cosine, which ``CellConstraints`` cannot state). Q-17c
#: (``crystallography/magnetic/supercell.py::child_basis``) closed exactly
#: this gap: when the pre-existing cell verifies for no real candidate at a
#: (parent, k) at all, ``child_basis`` now switches to the sum/difference
#: primitive basis of the same lattice instead — see
#: ``tests/test_child_basis_choice.py`` for the rung that fixed it and its
#: own accounting of all 39. This set, and the two individually-named tests
#: above, are kept (updated rather than deleted) as the record of what used
#: to fail and why.
_HALF_HALF_ZERO_SETTINGS = frozenset({
    "P c c 2", "P c c a", "P c c n", "P -4 c 2", "P 4 c c"})


@pytest.mark.slow
@pytest.mark.parametrize("setting,k,cell", SWEEP_ROWS,
                         ids=lambda v: str(v).replace(" ", "") if isinstance(v, tuple) else v)
@pytest.mark.parametrize("site", ("origin", "general"))
def test_every_sweep_row_builds_a_child(setting, k, cell, site):
    """Post-Q-17c: every sweep row builds, both k-families alike.

    Was ``test_every_sweep_row_builds_a_child_or_names_the_k_family_refusal``,
    with an ``expect_refusal`` branch for the (½,½,0) family; Q-17c's basis
    choice removed the refusal, so there is nothing left to branch on --
    see ``tests/test_child_basis_choice.py`` for the rung itself and the
    41-way accounting (39 unnamed candidates plus the 2 the report notes).
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


def test_the_half_half_zero_family_is_still_exactly_6_of_the_15_rows():
    """Guards the k-family counts ``SWEEP_ROWS`` splits on against silent drift.

    Was ``test_the_refusal_is_exactly_the_half_half_zero_family_39_candidates``
    -- the split is no longer build-vs-refuse (Q-17c fixed the refusal), but
    the row counts themselves are still worth pinning, since they are what
    the 39-candidate total in the report and in
    ``tests/test_child_basis_choice.py`` is built from.
    """
    n_half_half_zero_rows = sum(
        1 for setting, k, _cell in SWEEP_ROWS if k == ("1/2", "1/2", "0"))
    assert n_half_half_zero_rows == 6  # Pcc2, Pcca, Pccn, P42cm, P4cc, P-4c2
    n_zero_zero_half_rows = sum(
        1 for setting, k, _cell in SWEEP_ROWS if k == ("0", "0", "1/2"))
    assert n_zero_zero_half_rows == 9


# ---------------------------------------------------------------------------
# the A = 0 control: |det P|² × the parent, to 1e-10 of the peak
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_a_equals_zero_control_on_an_unnamed_child_is_det_p_squared():
    """C m m 2 at k=(0,0,½), magnitude 0: prediction = |det P|² × parent.

    Same control as Q-17's own (``test_the_unnamed_displacive_child_at_
    zero_amplitude_is_the_parent_pattern``) applied to a *magnetic* unnamed
    child via ``magnetic_supercell(magnitude=0.0)`` rather than a displacive
    one: at zero moment the forward model's magnetic contribution is exactly
    zero, so the pattern is the nuclear structure factor alone, scaled by how
    many parent cells the child holds. C m m 2 at this k is used rather than
    the brief's P c c 2 (½,½,0) because that child is refused, not built —
    see the report; this is the same *unnamed, derived-constraints* child
    the control is meant to exercise, one k-family over.  Background zeroed
    because it is additive and would not hold the ratio constant even for
    identical peaks.
    """
    parent = _parent("C m m 2", (6.0, 7.0, 9.0, 90.0, 90.0, 90.0))
    instrument = INSTRUMENT.model_copy(deep=True)
    instrument.background = BackgroundChebyshev(
        coefficients=[Parameter(value=0.0) for _ in range(3)])
    y_parent = np.asarray(rx.Refinement(
        Structure(phases=[parent]), instrument.model_copy(deep=True)
    ).predict(TWO_THETA))
    assert float(y_parent.max()) > 0.0

    kk = (Fraction(0), Fraction(0), Fraction(1, 2))
    found = candidates("C m m 2", SWEEP_SITES["general"], kk)
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
