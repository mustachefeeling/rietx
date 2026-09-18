"""Q23: the full child group's own construction must close.

**The defect, in one sentence.** ``_candidate_group`` (isotropy.py) built the
child group's flat operator list directly from ``direction.stabilizer`` x
``cell.translations``, and for a nonsymmorphic little group that flat list is
not always already closed under multiplication: composing two coset
representatives can need a lattice translation that appears only as a
*product*, never as any single stabiliser-member-times-Δ term — the little
group's own projective factor system (Bradley & Cracknell 1972 ch. 7).  Q22's
k-sweep (``data/ksweep_20260909/q22/q22_sweep_results.csv``) found 191
(setting, k, site) rows where ``kind="displacive"`` raised ``ValueError: the
operation list is not closed`` from ``MagneticGroup.from_operations`` because
of exactly this — every one ``kind="displacive"``, none ``kind="magnetic"``,
because the magnetic path's own eta bookkeeping happens to already absorb the
missing translation's phase (see :func:`~rietx.crystallography.magnetic.
isotropy._close_operations`'s docstring for why).

**The fix** (``src/rietx/crystallography/magnetic/isotropy.py``): the flat
seed list is closed under :class:`~rietx.crystallography.magnetic.operators.
MagneticOperator` multiplication (:func:`~.isotropy._close_operations`)
before being handed to :meth:`~.operators.MagneticGroup.from_operations`,
which keeps its own closure check as the assertion that this succeeded.  The
closure is order-preserving (new elements are only ever appended after the
existing seeds, never reshuffled among them): :meth:`~.operators.
MagneticGroup.from_operations` picks "the first operation met in each coset"
as its representative, and a downstream consumer (``compile_magnetic_sites``)
depends on which member of a coset that is — an ordinary ``set`` was tried
first and flipped the sign of some declared moments on the toy Pnma fixture
(``tests/test_epsilon_bookkeeping.py::test_moment_path_is_clean_by_design``)
purely by reordering an already-closed list.
"""
import numpy as np
import pytest

from rietx import Instrument, Refinement
from rietx.crystallography.magnetic import isotropy
from rietx.crystallography.magnetic import supercell as sc
from rietx.crystallography.magnetic.isotropy import magnetic_cell
from rietx.crystallography.magnetic.operators import IDENTITY
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, Phase, Structure

TWO_THETA = np.arange(10.0, 110.0, 0.02)
WAVELENGTH = 1.5406

#: The exact (setting, k) rows Q22's sweep logged as refused
#: (data/ksweep_20260909/q22/q22_sweep.log lines 620-639), reused verbatim
#: rather than re-picked so this file tests the rows the sweep actually hit.
P42_K = ("0", "0", "1/2")
PNNA_K = ("1/2", "1/2", "1/2")
I41A_K = ("1", "1", "1")


def _assert_closed_group(group):
    """Identity present, no duplicate operations, and every pairwise product
    is itself in the group -- the definition of "closed" ``from_operations``
    itself checks, re-checked directly here rather than trusted."""
    ops = group.all_operations()
    assert IDENTITY in ops
    assert len(ops) == len(set(ops))
    ops_set = set(ops)
    for a in ops:
        for b in ops:
            assert (a * b) in ops_set


def test_p42_screw_squared_closure_used_to_raise():
    """Reproducer: P4_2 at k=(0,0,1/2), kind='displacive'.

    Before the Q23 fix this raised ``ValueError: the operation list is not
    closed: '-y,x,z+1/4,+1' * '-y,x,z+1/4,+1' = '-x,-y,z+1/2,+1', which is
    not in it`` from ``MagneticGroup.from_operations`` for the S1(a) and
    S4(a) candidates (the two 1-dimensional irreps, whose stabiliser closes
    to the whole little group): the 4_2 screw's own child-cell operator
    squares to the ordinary 2-fold with a translation the flat stabiliser x
    cell.translations construction never produced on its own.  Now it does
    not raise, and every candidate's group is closed, has the identity, and
    (S1/S4 only) has the order the physics predicts: |grey little group| x
    (parent : child lattice index) = (4 x 2) x 2 = 16 -- the grey little
    group because a displacive stabiliser is always Type-II (both signs of
    every stabilising index; see ``tests/test_magnetic_isotropy.py::
    test_pnma_sb_displacive_candidates_verify_true``), and the lattice index
    2 because k=(0,0,1/2) doubles c.
    """
    found = isotropy.candidates("P 42", (0.0, 0.0, 0.0), P42_K,
                                kind="displacive", verify=False)
    # S1, S2, S4: S3 is S2's complex conjugate and candidates() drops it
    # (_is_conjugate_of_a_kept_irrep)
    assert len(found) == 3

    mcell = magnetic_cell("P 42", P42_K)
    lattice_index = len(mcell.translations)
    assert lattice_index == 2

    by_label = {c.irrep_label: c for c in found}
    for label in ("S1", "S4"):
        group = by_label[label].group
        _assert_closed_group(group)
        # |grey little group| (4 rotations x 2 time-reversal signs) x lattice index
        assert group.order == 4 * 2 * lattice_index

    for candidate in found:
        _assert_closed_group(candidate.group)


def test_pnna_and_i41a_closure_used_to_raise():
    """The same defect, two more of Q22's 191 refused (setting, k) rows:
    P n n a at k=(1/2,1/2,1/2) and I 41/a:1 at k=(1,1,1) -- neither raises
    now, and every candidate's group is closed."""
    for setting, k in (("P n n a", PNNA_K), ("I 41/a:1", I41A_K)):
        found = isotropy.candidates(setting, (0.0, 0.0, 0.0), k,
                                    kind="displacive", verify=False)
        assert len(found) > 0
        for candidate in found:
            _assert_closed_group(candidate.group)


# --------------------------------------------------------------------------
# acceptance (2): the M2d exactness check on the three formerly-refused cases
# --------------------------------------------------------------------------
#
# Reuses the exact method of ``tests/test_epsilon_bookkeeping.py::
# test_reduced_group_child_matches_an_explicit_p1_build`` /
# ``test_a_equals_zero_negative_control_on_the_reduced_s3ab_child`` (M2d):
# a child built at a nonzero amplitude through the normal (declared-group,
# symmetry-propagated) path must predict the identical powder pattern as one
# built with ``_sign_consistent_operations`` monkeypatched to force every
# operation but the identity out of the declared group -- so every raw
# position is its own explicit representative and nothing propagates through
# ``_candidate_group``'s output at all.  If the Q23 fix had produced a
# *closed but wrong* group (the failure mode a bare "no longer raises" check
# cannot see), the two builds would disagree.  The A = 0 control checks the
# same construction's zero-amplitude limit against the bare parent.


def _instrument():
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.profile.w.value = 0.004
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=30.0), Parameter(value=-4.0)])
    return ins


_IDENTITY_ROTATION = tuple(tuple(int(i == j) for j in range(3)) for i in range(3))


def _force_p1(cand, m_matrix, ops):
    """Monkeypatch target for ``supercell._sign_consistent_operations``:
    keep only the identity, so every raw position becomes its own explicit
    representative (M2d's own method, reused verbatim)."""
    return {op for op in ops if op[0] == _IDENTITY_ROTATION
           and all(v == 0 for v in op[1])}


def _p42_parent():
    return Phase(
        name="parent", space_group="P 42",
        cell=Cell(a=Parameter(value=5.0), b=Parameter(value=5.0),
                  c=Parameter(value=6.0), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Ti", species="Ti", x=Parameter(value=0.12),
                    y=Parameter(value=0.34), z=Parameter(value=0.15),
                    biso=Parameter(value=0.6))],
        scale=Parameter(value=0.02))


def _pnna_parent():
    return Phase(
        name="parent", space_group="P n n a",
        cell=Cell(a=Parameter(value=6.0), b=Parameter(value=7.0),
                  c=Parameter(value=8.0), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Ti", species="Ti", x=Parameter(value=0.1),
                    y=Parameter(value=0.2), z=Parameter(value=0.3),
                    biso=Parameter(value=0.6))],
        scale=Parameter(value=0.02))


def _i41a_parent():
    return Phase(
        name="parent", space_group="I 41/a:1",
        cell=Cell(a=Parameter(value=7.0), b=Parameter(value=7.0),
                  c=Parameter(value=10.0), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Ti", species="Ti", x=Parameter(value=0.1),
                    y=Parameter(value=0.2), z=Parameter(value=0.05),
                    biso=Parameter(value=0.6))],
        scale=Parameter(value=0.02))


@pytest.mark.parametrize("name,parent_fn,k,irrep,direction", [
    ("P 42", _p42_parent, P42_K, "S1", "(a)"),
    ("P n n a", _pnna_parent, PNNA_K, "S1", "(rank 1)#1"),
    ("I 41/a:1", _i41a_parent, I41A_K, "S1", "(rank 1)#1"),
])
def test_child_at_nonzero_amplitude_matches_an_explicit_p1_build(
        name, parent_fn, k, irrep, direction, monkeypatch):
    """The M2d exactness check, reused on the three formerly-refused cases."""
    parent = parent_fn()
    stmt = sc.displacive_statement(parent, k, irrep=irrep, direction=direction,
                                   magnitude=0.05, vary=False)
    monkeypatch.setattr(sc, "_sign_consistent_operations", _force_p1)
    p1 = sc.displacive_statement(parent, k, irrep=irrep, direction=direction,
                                 magnitude=0.05, vary=False)
    monkeypatch.undo()

    ins = _instrument()
    y_reduced = np.asarray(Refinement(
        Structure(phases=[stmt.phase]), ins.model_copy(deep=True)).predict(TWO_THETA))
    y_p1 = np.asarray(Refinement(
        Structure(phases=[p1.phase]), ins.model_copy(deep=True)).predict(TWO_THETA))
    peak = float(y_reduced.max())
    assert peak > 0.0
    worst = float(np.max(np.abs(y_reduced - y_p1)))
    assert worst <= 1e-10 * peak, f"{name}: {worst / peak:.3e} relative"


@pytest.mark.parametrize("name,parent_fn,k,irrep,direction", [
    ("P 42", _p42_parent, P42_K, "S1", "(a)"),
    ("P n n a", _pnna_parent, PNNA_K, "S1", "(rank 1)#1"),
    ("I 41/a:1", _i41a_parent, I41A_K, "S1", "(rank 1)#1"),
])
def test_a_equals_zero_matches_the_parent_up_to_the_index_squared_scale(
        name, parent_fn, k, irrep, direction):
    """A = 0 control: |det P|^2 x the parent, to 1e-9 relative -- same
    construction, zero amplitude, checked against the bare parent pattern."""
    parent = parent_fn()
    ins0 = _instrument()
    ins0.background = BackgroundChebyshev(coefficients=[Parameter(value=0.0) for _ in range(2)])
    y_parent = np.asarray(Refinement(
        Structure(phases=[parent]), ins0.model_copy(deep=True)).predict(TWO_THETA))
    assert float(y_parent.max()) > 0.0

    stmt = sc.displacive_statement(parent, k, irrep=irrep, direction=direction)
    y_child = np.asarray(Refinement(
        Structure(phases=[stmt.phase]), ins0.model_copy(deep=True)).predict(TWO_THETA))
    live = y_parent > 1e-6 * float(y_parent.max())
    ratio = y_child[live] / y_parent[live]
    assert float(np.median(ratio)) == pytest.approx(stmt.index ** 2, rel=1e-9)
    worst = float(np.max(np.abs(ratio - stmt.index ** 2)))
    assert worst <= 1e-9 * (stmt.index ** 2)
