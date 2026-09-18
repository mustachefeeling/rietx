"""Item 1 of small-fixes-20260917: operator-order dependence.

**The defect, in one sentence.** ``MagneticGroup.from_operations``
(``operators.py``) used to pick, as the representative of each coset, "the
first operation met" in whatever order its caller's operation list happened
to enumerate — insertion order of a ``dict``-as-ordered-set. Two equally
valid seed orderings of the *same set* of operations (``_candidate_group``'s
``stabilizer x cell.translations`` walk, or ``_close_operations``'s closure
discovery order, both upstream in ``isotropy.py``) could therefore produce a
``MagneticGroup`` whose ``.operations``/``.all_operations()`` differed only
in *order*, not in membership — and Q23 measured that this order reaches a
consumer: ``scattering.py``'s ``_axial_matrices`` (called from
``compile_magnetic_sites``) walks ``group.all_operations()`` and keeps the
*first* operation whose image matches a nuclear site, with (before this fix)
no check that a later match would agree. Reordering the group's operations
could therefore silently flip which operation — and so which
``moment_matrix()`` sign — got recorded for an image, purely by
reordering an already-correct list (measured on
``test_epsilon_bookkeeping.py::test_moment_path_is_clean_by_design`` when
Q23 tried an unordered ``set()`` in ``_close_operations``).

**The fix.** ``MagneticGroup.from_operations`` now sorts the deduplicated
operation list canonically by ``(rotation, translation, time_reversal)`` —
a property of each operation's own identity, never of the position it
happened to occupy in the caller's list — before choosing coset
representatives, so ``.operations``/``.centerings``/``.all_operations()``
are bit-identical for any input order of the same operation *set*. This is
exercised directly by :func:`test_from_operations_is_order_independent`
below, and end to end (through ``compile_magnetic_sites``) by
:func:`test_permuted_group_gives_bit_identical_moments`.

**Why ``_axial_matrices`` itself needed no change.** It was tempting to add
a "do all matching operations agree" assertion there too, and an earlier
draft of this fix did — but that check is *wrong*, not merely redundant:
on a special position, a non-trivial stabiliser of the site (say a mirror
with η = −1) legitimately has a different ``moment_matrix()`` from the
identity that also reaches the same (k = 0, the atom itself) image — that
disagreement is exactly what forces the corresponding moment component to
zero via :func:`~.operators.allowed_moment_basis`, not a bug (confirmed
directly: adding the "must agree" check made
``test_moment_path_is_clean_by_design`` raise on the toy fixture's own
Ti/Ti_1 sites, which are not defective). The reason "any matching
operation" is still safe, special position or not, is that the *stored*
moment is always a linear combination of :class:`~.scattering.
MagneticSites` DOF frames — themselves built from
``allowed_moment_basis`` — so for **every** operation that reaches a given
image, ``op.moment_matrix() @ m`` gives the identical numeric result for
any ``m`` actually in that subspace, regardless of which matching
operation ``mats[k]`` records the *matrix* of. What Q23 fixed is
therefore exactly the right layer: make the *order* used to pick "the
first match" itself independent of the caller's enumeration order, not
add a check for a disagreement that can legitimately exist.
"""
from __future__ import annotations

import random

import numpy as np
import pytest

from rietx.crystallography.magnetic import isotropy as iso
from rietx.crystallography.magnetic import supercell as sc
from rietx.crystallography.magnetic.operators import (
    IDENTITY,
    MagneticGroup,
    MagneticOperator,
)
from rietx.crystallography.magnetic.scattering import (
    _axial_matrices,
    compile_magnetic_sites,
)
from rietx.crystallography.structure_factor import compile_phase_sites
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase

K = ("1/2", "0", "1/2")
RNG = random.Random(20260917)


def parent_phase() -> Phase:
    """The toy two-site Pnma parent, verbatim from
    ``test_epsilon_bookkeeping.py::parent_phase`` / ``test_multi_component_
    statements.py::parent_phase`` — re-declared, not imported, so this file
    stands alone, per this test tree's own convention.
    """
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


def _magnetic_candidates(label: str):
    """Every site's verified ``kind="magnetic"`` candidate named ``label``,
    on the toy Pnma parent at K — same construction as
    ``test_epsilon_bookkeeping.py::test_naive_moment_propagation_would_
    flip_sign``.
    """
    parent = parent_phase()
    mcell = iso.magnetic_cell(parent.space_group, K)
    per_site = []
    for atom in parent.atoms:
        cs = iso.candidates(parent.space_group,
                            (atom.x.value, atom.y.value, atom.z.value),
                            mcell.k, kind="magnetic", verify=True)
        per_site.append({c.label: c for c in cs.candidates if c.verified is not False})
    return parent, mcell, per_site, [per_site[j][label] for j in range(len(parent.atoms))]


@pytest.mark.parametrize("label", ["S1(a,b)", "S2(a,b)", "S3(a,b)", "S4(a,b)"])
def test_from_operations_is_order_independent(label):
    """Rebuilding a real candidate's group from a shuffled operation list
    gives back the identical ``.operations``/``.centerings`` tuples.

    ``group.all_operations()`` is already the fully closed set; feeding a
    random permutation of it straight back into ``from_operations`` exercises
    the exact code path Q23 flagged (representative choice), not merely a
    property that would hold trivially either way.
    """
    _parent, _mcell, _per_site, candidates = _magnetic_candidates(label)
    for candidate in candidates:
        group = candidate.group
        baseline_ops = group.operations
        baseline_cent = group.centerings
        all_ops = list(group.all_operations())
        for trial in range(8):
            shuffled = list(all_ops)
            RNG.shuffle(shuffled)
            rebuilt = MagneticGroup.from_operations(shuffled)
            assert rebuilt.operations == baseline_ops, (label, trial)
            assert rebuilt.centerings == baseline_cent, (label, trial)
            assert rebuilt.all_operations() == group.all_operations(), (label, trial)


def _mom_mat_for(parent, candidate, label):
    stmt = sc.magnetic_supercell(parent, candidate=candidate, nuclear_group="magnetic",
                                 magnetic_species=["Ti", "O"], ion="Fe3+", magnitude=1.0)
    phase = stmt.phase
    sites = compile_phase_sites(phase)
    magsites = compile_magnetic_sites(phase, sites.ops)
    assert magsites is not None
    return magsites.mom_mat, stmt


@pytest.mark.parametrize("label", ["S1(a,b)", "S2(a,b)", "S3(a,b)", "S4(a,b)"])
def test_permuted_group_gives_bit_identical_moments(label):
    """A candidate whose group was rebuilt from a shuffled operation list
    gives ``compile_magnetic_sites`` bit-identical ``mom_mat`` to the
    original — the acceptance test the brief asks for, run end to end
    through ``magnetic_supercell``/``compile_phase_sites``/
    ``compile_magnetic_sites`` rather than at the unit level only.
    """
    from dataclasses import replace

    parent, _mcell, per_site, _candidates = _magnetic_candidates(label)
    reference = per_site[0][label]
    baseline_mats, _stmt = _mom_mat_for(parent, reference, label)

    shuffled_ops = list(reference.group.all_operations())
    RNG.shuffle(shuffled_ops)
    shuffled_group = MagneticGroup.from_operations(shuffled_ops)
    shuffled_candidate = replace(reference, group=shuffled_group)
    shuffled_mats, _stmt2 = _mom_mat_for(parent, shuffled_candidate, label)

    assert len(baseline_mats) == len(shuffled_mats)
    for base, perm in zip(baseline_mats, shuffled_mats, strict=True):
        if base is None:
            assert perm is None
            continue
        assert np.array_equal(base, perm)


def test_axial_matrices_picks_a_matching_op_regardless_of_group_order():
    """``_axial_matrices`` gives the identical ``(3, 3)`` matrices whichever
    order the group's operations are enumerated in, on a case built to have
    *two* operations reaching the same (k=0, own) image with genuinely
    different ``moment_matrix()`` — the special-position case the module
    docstring's note explains is not a bug: ``IDENTITY`` and a mirror with
    η = −1 both fix ``xyz`` (only the ``y`` component moves under the
    mirror, and ``xyz``'s own ``y`` is not on that mirror's plane here, so
    this is a deliberately loose stand-in for the toy fixture's Ti_1 case —
    the point is only that ``_axial_matrices`` must not fail, and must give
    the same answer, regardless of which of the two is listed first).
    """
    mirror = MagneticOperator.build([[1, 0, 0], [0, -1, 0], [0, 0, 1]],
                                    [0, 0, 0], -1)
    xyz = np.array([0.1, 0.0, 0.3])  # y = 0 is fixed by the mirror too
    rot = np.array([[[1, 0, 0], [0, 1, 0], [0, 0, 1]]])
    tran = np.array([[0.0, 0.0, 0.0]])

    forward = _axial_matrices(MagneticGroup.from_operations([IDENTITY, mirror]),
                              xyz, rot, tran, "phase", "Ti")
    backward = _axial_matrices(MagneticGroup.from_operations([mirror, IDENTITY]),
                               xyz, rot, tran, "phase", "Ti")
    assert np.array_equal(forward, backward)
