"""The declared operation list and the child group are two objects (M-3 item 5a).

WP-1419 § Inherited: "The ε fix reduces a displacive child's declared list to
the sign-consistent stabiliser of its mode field, a strict subgroup.  The full
child group still has to drive reflection generation, multiplicities and the
metric derivation of § The metric subspace, since reading ``cell_constraints``
off the reduced list refines the cell with more freedom than the crystal has."

This module measures which of those three the fork actually drives off which
list, and the answer is not the same for all three.

**The metric is safe, and structurally rather than by luck.**  M2d's reduction
(``supercell._sign_consistent_operations``) drops an operation whose ε it
cannot state — and every operation it drops turns out to be the *translation
coset partner* of one it keeps: ``x+½,-y+½,z`` beside ``x,-y+½,z``, differing
by the parent translation the k-doubling lost.  So the **rotation set is
unchanged**, and ``cell_constraints_from_rotations`` reads nothing else: the
invariant subspace of the direct metric under Rᵀ·G·R = G is a property of the
rotations alone.  Measured over 32 (k, direction) pairs of the toy Pnma parent,
15 of which the reduction bites: ``cell_constraints`` is identical, reduced
against full, on every one — ``CellConstraints`` where it is one, and
``MetricConstraints`` with the same dimension m where it is that.

**Reflection generation is not.**  The dropped translations are exactly what
produces the child cell's translational absences, so the reduced list allows
about twice as many reflections: 298 → 594 unique in 10–110° for S3(a,b) at
k = (½,0,½).  The predicted *pattern* is unaffected to 1e-10 — the extra
reflections have |F|² = 0 for the structure as listed, which is what
``tests/test_epsilon_bookkeeping.py`` already pins — but the tick list a report
prints is twice as long as the crystal's, and a Le Bail or Pawley fit on such a
phase would extract intensity into reflections the true child group forbids.

That last one is a defect and it is **not fixed here**, because the fix is a
schema decision the maintainer has reserved: a phase would have to carry both
lists, and WP-1419's own task list still says "decide, with the maintainer: …
the operator-list phase shared with 1327".  These tests pin the current
behaviour so the fix has a baseline, and the report says what it costs.
"""

import gemmi
import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic import supercell as sc
from rietx.crystallography.symmetry import (
    MetricConstraints,
    cell_constraints,
    generate_reflections,
    resolve_group,
)
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure

WAVELENGTH = 1.5406

#: (k, irrep, direction) pairs of the toy Pnma parent on which M2d's reduction
#: actually removes operations.  Measured, not guessed: the full sweep over the
#: parent's six zone-boundary k's finds 15 such pairs out of 32, and these are
#: the four shortest.
REDUCED_CASES = [
    (("1/2", "0", "1/2"), "S3", "(a,b)"),
    (("0", "1/2", "1/2"), "S1", "(rank 1)#2"),
    (("0", "1/2", "1/2"), "S2", "(rank 1)#2"),
    (("1/2", "0", "0"), "S2", "(rank 1)#1"),
]

#: pairs on which it removes nothing — the control that says the comparison
#: below can tell the two apart at all
UNREDUCED_CASES = [
    (("1/2", "0", "1/2"), "S1", "(a,b)"),
    (("1/2", "0", "1/2"), "S2", "(a,b)"),
    (("0", "1/2", "1/2"), "S2", "(rank 1)#1"),
]


def parent_phase() -> Phase:
    """The toy two-site Pnma parent, verbatim from ``test_epsilon_bookkeeping``."""
    return Phase(
        name="parent", space_group="P n m a",
        cell=Cell(a=Parameter(value=5.4), b=Parameter(value=7.6),
                  c=Parameter(value=5.3), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Ti", species="Ti", x=Parameter(value=0.1),
                    y=Parameter(value=0.25), z=Parameter(value=0.3),
                    biso=Parameter(value=0.6)),
               Atom(label="O", species="O", x=Parameter(value=0.42),
                    y=Parameter(value=0.25), z=Parameter(value=0.11),
                    biso=Parameter(value=0.8))],
        scale=Parameter(value=0.02))


def _statement(k, irrep, direction, *, reduce: bool, monkeypatch):
    """``displacive_statement`` with M2d's reduction on or off.

    Off is spelled by monkeypatching ``_sign_consistent_operations`` to the
    identity on its ``ops`` argument, which is how ``test_epsilon_bookkeeping``
    already reaches past it — every other step of the build is untouched, so
    the two statements differ in the *declared group* and in nothing else.
    """
    if not reduce:
        monkeypatch.setattr(sc, "_sign_consistent_operations",
                            lambda cand, m_matrix, ops: set(ops))
    return sc.displacive_statement(parent_phase(), k, irrep=irrep,
                                   direction=direction)


def _rotations(operations) -> set:
    return {tuple(tuple(r) for r in gemmi.Op(str(s)).rot) for s in operations}


# ------------------------------------------------- what the reduction removes
@pytest.mark.parametrize(("k", "irrep", "direction"), REDUCED_CASES)
def test_the_reduction_removes_only_translation_coset_partners(
        k, irrep, direction, monkeypatch):
    """|ops| halves and the rotation set does not move.

    This is the mechanism behind the next test, and it is worth pinning on its
    own: if M2d ever dropped an operation carrying a rotation nothing else
    carries, the metric derived from the declared list would immediately become
    wrong, and this test — not the cell-constraints one — is the one that would
    say so first.
    """
    full = _statement(k, irrep, direction, reduce=False,
                      monkeypatch=monkeypatch).phase
    monkeypatch.undo()
    reduced = _statement(k, irrep, direction, reduce=True,
                         monkeypatch=monkeypatch).phase
    assert full.symmetry_operations is not None
    assert reduced.symmetry_operations is not None
    assert len(reduced.symmetry_operations) < len(full.symmetry_operations)
    assert _rotations(reduced.symmetry_operations) == _rotations(
        full.symmetry_operations), (
        f"{irrep}{direction} at k={k}: the reduction dropped a rotation, not "
        f"only a translation coset partner — the metric read off the declared "
        f"list is now a different subspace from the crystal's")


@pytest.mark.parametrize(("k", "irrep", "direction"),
                         REDUCED_CASES + UNREDUCED_CASES)
def test_the_metric_is_the_same_off_either_list(k, irrep, direction,
                                                monkeypatch):
    """``cell_constraints`` reduced == full, on the cases that reduce and on
    the controls that do not.

    The finding WP-1419 § Inherited asked for.  ``cell_constraints_from_rotations``
    reads only the rotation set (Rᵀ·G·R = G is a property of the rotations),
    and the test above shows the reduction leaves that set alone, so this holds
    for a reason rather than on a corpus.  Measured on all 32 (k, direction)
    pairs of this parent, not only the seven parametrised here.
    """
    full = _statement(k, irrep, direction, reduce=False,
                      monkeypatch=monkeypatch).phase
    monkeypatch.undo()
    reduced = _statement(k, irrep, direction, reduce=True,
                         monkeypatch=monkeypatch).phase
    cons_full = cell_constraints(resolve_group(full.space_group,
                                               full.symmetry_operations))
    cons_reduced = cell_constraints(resolve_group(reduced.space_group,
                                                  reduced.symmetry_operations))
    assert cons_reduced == cons_full, (
        f"{irrep}{direction} at k={k}: the reduced list states "
        f"{cons_reduced} where the full child group states {cons_full}")


@pytest.mark.parametrize(("k", "irrep", "direction"), REDUCED_CASES)
def test_reflection_generation_does_read_the_reduced_list(
        k, irrep, direction, monkeypatch):
    """The half of § Inherited's warning that **is** live on this fork.

    The operations the reduction drops are the translation coset partners, and
    those are exactly what produces the child cell's translational absences —
    so the reduced list allows about twice as many reflections, the extras
    being systematically absent under the true child group.

    Not a wrong *pattern*: those reflections carry |F|² = 0 for the structure
    as listed, which is what ``test_epsilon_bookkeeping`` pins to 1e-10 of the
    peak.  What it costs is a tick list twice as long as the crystal's, twice
    the peak-chain work per Jacobian column, and — the one that is not merely
    wasteful — a Le Bail or Pawley fit that would put free intensities on
    reflections the crystal forbids.

    Pinned as the current behaviour, deliberately.  The fix is for a phase to
    carry both lists, which is the operator-list schema WP-1419's task list
    still reserves for the maintainer.
    """
    full = _statement(k, irrep, direction, reduce=False,
                      monkeypatch=monkeypatch).phase
    monkeypatch.undo()
    reduced = _statement(k, irrep, direction, reduce=True,
                         monkeypatch=monkeypatch).phase
    args = (full.cell.lengths_angles(), WAVELENGTH, 110.0, 10.0)
    n_full = len(generate_reflections(
        resolve_group(full.space_group, full.symmetry_operations), *args).hkl)
    n_reduced = len(generate_reflections(
        resolve_group(reduced.space_group, reduced.symmetry_operations),
        *args).hkl)
    assert n_reduced > n_full, (
        f"{irrep}{direction} at k={k}: {n_reduced} against {n_full} — if these "
        f"are equal the reduction has stopped reaching the reflection list, "
        f"which would be the fix and not a regression")
    ratio = n_reduced / n_full
    assert 1.8 <= ratio <= 2.2, (
        f"the reduced list allows {ratio:.2f}× the reflections, not the ~2× a "
        f"single dropped translation coset explains")


def test_the_metric_defect_cannot_be_reached_from_a_mode_carrying_phase():
    """The reach of the metric half, bounded: a mode-carrying phase holds its cell.

    Even if the reduced list *did* under-constrain the metric, no refinement
    could spend the extra freedom: ``Phase._distortion_modes_are_refinable``
    refuses a free cell on a phase carrying modes by name, and
    ``params.vector`` force-holds every cell parameter of such a phase besides.
    So the live half of § Inherited's warning is the reflection list, not the
    cell — which is worth stating, because the warning names the cell first.
    """
    statement = sc.displacive_statement(
        parent_phase(), ("1/2", "0", "1/2"), irrep="S3", direction="(a,b)")
    phase = statement.phase
    doc = phase.model_dump()
    doc["cell"]["b"]["vary"] = True
    with pytest.raises(ValueError, match="frees its cell"):
        Phase.model_validate(doc)
    # and the table holds them whatever the schema said
    from rietx.params.vector import ParameterTable

    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    table = ParameterTable(Structure(phases=[phase]), ins)
    for name in ("a", "b", "c", "alpha", "beta", "gamma"):
        entry = table.entries[table._paths[f"phases.0.cell.{name}"]]
        assert not entry.vary, f"{name} is free on a mode-carrying phase"


def test_the_pnma_double_refines_four_metric_coordinates():
    """WP-1419 § The metric subspace's own case, on a synthetic parent.

    Pnma at k = (0, ½, ½) gives the child lattice a, 2b, b+c: centred, and
    oblique because b ≠ c, so no primitive basis of it is rectangular.  The
    invariant subspace is 4-dimensional (monoclinic) but two of its relations
    are a length times a cosine in (a, b, c, α, β, γ), which the
    two-dictionary read-off cannot state — so ``cell_constraints`` returns
    :class:`MetricConstraints` rather than under-constraining, and the free
    count is the **subspace dimension, 4**, not the six the read-off would
    have left.

    The measured case in ``tests/test_metric_coordinates.py`` is the same
    transform on a real parent; this one needs no data file, and it is here
    because the brief asks the question of the *child group's* list rather
    than of the setting.
    """
    statement = sc.displacive_statement(
        parent_phase(), ("0", "1/2", "1/2"), irrep="S1",
        direction="(rank 1)#2")
    assert statement.child_group_named is False
    group = resolve_group(statement.phase.space_group,
                          statement.phase.symmetry_operations)
    cons = cell_constraints(group)
    assert isinstance(cons, MetricConstraints), (
        f"expected the metric fallback, got {type(cons).__name__}: {cons}")
    assert cons.m == 4, f"the subspace dimension is {cons.m}, not 4"
    assert "dimension 4" in cons.relation
    # and the child's own cell lies in that subspace, which is the acceptance
    # root CLAUDE.md states (span, never a dimension count)
    from rietx.crystallography.symmetry import (
        cell_from_metric_coordinates,
        metric_coordinates,
    )

    cell = statement.phase.cell.lengths_angles()
    back = cell_from_metric_coordinates(cons, metric_coordinates(cons, cell))
    assert np.max(np.abs(np.array(cell) - np.array(back))) < 1e-8
