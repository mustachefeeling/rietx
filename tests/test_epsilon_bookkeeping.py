"""M2d: carry the little-group sign through ``magnetic_supercell``'s declared
symmetry (checks/M2B_SINGLE_COMPONENT_SIGN_CHECK.md's confirmed defect).

**The defect, in one sentence.** For a candidate whose order-parameter
direction is >= 2-dimensional, a spatial operation of its own isotropy group
can be a symmetry of one component of the direction (little-group character
eta = +1) and an anti-symmetry of another (eta = -1) -- a single scalar eta
per operator cannot state that, and ``_colourless()`` (which every
declared-symmetry consumer downstream reads) forces every operator's eta to
+1 before the group ever reaches the compiled ``Phase``.  Downstream, the
ordinary structure-factor orbit expansion (``expand_positions``, called by
``crystallography.structure_factor.py``'s ``select_orbit_ops``/
``_orbit_terms``) then propagates a representative's mode vector to its
orbit siblings by the bare rotation -- correct for the eta = +1 component,
sign-flipped for the eta = -1 one.  Measured on S3(a,b) of the toy Pnma
fixture at k = (1/2,0,1/2) (``test_multi_component_statements.py::
parent_phase``, reused here rather than re-declared): 16 of 64 (position,
mode) checks were exact sign flips on 3e53660d; S1(a,b), S2(a,b), S4(a,b) on
the same fixture were clean.

**The fix (option (a)).**  The declared child group is reduced, per
candidate, to the subgroup that is a symmetry of the candidate's own
**signed** field -- :func:`~rietx.crystallography.magnetic.supercell.
_sign_consistent_operations` -- before ``resolve_child_group``/
``_partition_into_child_orbits`` ever see it.  An operation this rung cannot
state a correct sign for is *excluded* rather than trusted with an implicit
+1; the sibling it used to reach becomes its own explicit representative,
its vector filled by the same direct position-match every representative
already gets.  Gated to ``candidate.kind == "displacive"``: the moment
path's own consumer (``magnetic.scattering.compile_magnetic_sites``)
re-derives each nuclear image's axial matrix from the *full*, non-colourless
magnetic group at compile time -- one operation at a time, matched by
*position* -- so it never trusts the declared (colourless) group's implicit
sign in the first place.  ``test_naive_moment_propagation_would_flip_sign``
and ``test_moment_path_is_clean_by_design`` below measure that this is not
merely assumed.
"""
from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, Refinement
from rietx.crystallography.adp import cartesian_basis
from rietx.crystallography.magnetic import isotropy as iso
from rietx.crystallography.magnetic import supercell as sc
from rietx.crystallography.magnetic.scattering import compile_magnetic_sites
from rietx.crystallography.structure_factor import compile_phase_sites
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, Moment, Structure

RNG = np.random.default_rng(20260915)
TWO_THETA = np.arange(10.0, 110.0, 0.02)
WAVELENGTH = 1.5406
K = ("1/2", "0", "1/2")


def parent_phase():
    """The toy two-site Pnma parent (re-declared, not imported, so this file
    stands alone): S1/S2/S3/S4(a,b) all build at k = (1/2,0,1/2), the same
    four directions Ba2FeSbSe5's real acceptance uses.  Verbatim from
    ``test_multi_component_statements.py::parent_phase`` (M2's own toy
    fixture, which M2b's diagnosis and this rung's fix both reuse) -- kept
    identical so every number in this file's docstrings is directly
    comparable to M2b's and M2's own reports.
    """
    from rietx.schemas.structure import Phase

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


def instrument() -> Instrument:
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.profile.w.value = 0.004
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=30.0), Parameter(value=-4.0)])
    return ins


def _same_site(a, b, tol: float = 1e-6) -> bool:
    d = np.abs(np.asarray(a) - np.asarray(b))
    return bool(np.all(np.minimum(d, 1.0 - d) <= tol))


def _displacive_ground_truth(irrep: str, direction: str = "(a,b)"):
    """M2b's own method, re-derived (not imported): direct per-position
    matching of ``candidates(kind="displacive")``'s own field, independent of
    any symmetry expansion, against the compiled ``Phase``'s per-representative
    mode vectors expanded through its own declared group.

    Returns ``(total_checks, mismatches)`` where a mismatch is a (position,
    mode) pair whose orbit-expanded prediction disagrees with the direct
    ground-truth match by more than ``1e-6`` relative.
    """
    from rietx.crystallography.symmetry import resolve_group, site_orbit

    label = f"{irrep}{direction}"
    parent = parent_phase()
    parent_cell = parent.cell.lengths_angles()
    lattice = np.asarray(cartesian_basis(*parent_cell), dtype=np.float64).T
    mcell = iso.magnetic_cell(parent.space_group, K)
    per_site = sc._displacive_candidates(parent, mcell.k, lattice)
    basis = sc.child_basis(parent.space_group, mcell.k)

    stmt = sc.displacive_statement(parent, K, irrep=irrep, direction=direction)
    phase = stmt.phase
    sg = resolve_group(phase.space_group, phase.symmetry_operations)

    gt = {}
    for j, atom in enumerate(parent.atoms):
        cand = per_site[j][label]
        mm = iso._fraction_inverse(basis) @ sc._matrix_of(cand.cell.basis)
        positions = (cand.positions @ mm.T) % 1.0
        configs = np.array([c @ mm.T for c in cand.configurations])
        gt[j] = (positions, configs)

    mismatches = []
    total = 0
    mode_by_name = {m.name: m for m in phase.distortion_modes}
    for i, atom_repr in enumerate(phase.atoms):
        j, _coset = stmt.site_map[i]
        xyz = np.array([atom_repr.x.value, atom_repr.y.value, atom_repr.z.value])
        orbit = site_orbit(sg, xyz)
        names = stmt.modes_by_site[parent.atoms[j].label]
        gpos, gconf = gt[j]
        for f, name in enumerate(names):
            mode = mode_by_name[name]
            rep_vec = np.array(mode.vectors[i])
            hits0 = [k for k in range(gpos.shape[0]) if _same_site(gpos[k], xyz)]
            assert hits0, f"{name}: representative itself missing from ground truth"
            raw0 = gconf[f][hits0[0]]
            idx_max = int(np.argmax(np.abs(rep_vec)))
            worst = 1.0 if abs(rep_vec[idx_max]) < 1e-14 else raw0[idx_max] / rep_vec[idx_max]
            for m in range(orbit.multiplicity):
                image = orbit.images[m]
                rot = orbit.rot[m]
                predicted = (rot @ rep_vec) * worst
                hits = [k for k in range(gpos.shape[0]) if _same_site(gpos[k], image)]
                total += 1
                if not hits:
                    mismatches.append((name, i, m, "no ground-truth match"))
                    continue
                actual = gconf[f][hits[0]]
                worst_abs = max(float(np.max(np.abs(actual))), 1e-30)
                rel = float(np.max(np.abs(predicted - actual))) / worst_abs
                if rel > 1e-6:
                    mismatches.append((name, i, m, (predicted.tolist(), actual.tolist())))
    return total, mismatches


# --------------------------------------------------------- item 1: ground truth
@pytest.mark.parametrize("irrep,expected_checks", [
    ("S1", 32), ("S2", 64), ("S3", 64), ("S4", 32)])
def test_ground_truth_displacive_is_clean_on_the_fixed_tree(irrep, expected_checks):
    """S1(a,b), S2(a,b), S3(a,b), S4(a,b): 0 mismatches, all four, post-fix.

    On 3e53660d this was 16/64 mismatches for S3(a,b) alone (checks/
    M2B_SINGLE_COMPONENT_SIGN_CHECK.md) and 0 for the other three -- so this
    test is written to fail on the base commit and pass after the fix, per
    the brief's acceptance item 1.
    """
    total, mismatches = _displacive_ground_truth(irrep)
    assert total == expected_checks
    assert mismatches == []


# --------------------------------------------------------- item 4: label/order
def test_s3ab_child_declares_only_the_sign_consistent_subgroup():
    """Group order 4 -> 2, representative count 8 -> 16, on the toy fixture.

    The excluded pair is the cross-coset mirror (rotation composed with the
    child lattice's own coset shift) and the pure coset-shift translation --
    exactly the two operations M2b's own per-representative table showed
    carrying the wrong sign.  The kept operation is the *within-coset* mirror,
    which is a true self-stabiliser of every representative it touches (it
    never generates a new image at all on this fixture) and was already
    measured clean.
    """
    parent = parent_phase()
    before = sc.displacive_statement(parent, K, irrep="S1", direction="(a,b)")
    assert len(before.phase.atoms) == 8  # a clean control: unaffected by the fix

    after = sc.displacive_statement(parent, K, irrep="S3", direction="(a,b)")
    assert after.child_group_named is False
    assert after.phase.space_group == "Pm [unnamed in 2a,b,a+c]"
    assert set(after.phase.symmetry_operations) == {"x,y,z", "x,-y+1/2,z"}
    assert len(after.phase.atoms) == 16   # was 8 representatives (order-4 group)
    assert len(after.phase.distortion_modes) == 8  # 4 (Ti) + 4 (O), unchanged


# --------------------------------------------------------- item 2: A = 0 control
def test_a_equals_zero_negative_control_on_the_reduced_s3ab_child():
    """|det P|^2 x the parent, to the last bits, on the *reduced* child.

    Q17's own note: the background is additive and zeroed here so the ratio
    is meaningful; ``test_operator_list_phase.py::
    test_the_unnamed_displacive_child_at_zero_amplitude_is_the_parent_pattern``
    covers the same control on Ba2FeSbSe5's own generic fixture (also
    unmodified by this fix -- it already asserts < 1e-9, that test's own
    threshold) -- this is the same control on M2d's own toy fixture, same
    1e-9 relative threshold (float64 profile-function evaluation, not exact
    rational arithmetic, is the reason it is 1e-9 and not 1e-12).
    """
    parent = parent_phase()
    ins = instrument()
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=0.0) for _ in range(2)])
    y_parent = np.asarray(Refinement(
        Structure(phases=[parent]), ins.model_copy(deep=True)).predict(TWO_THETA))
    assert float(y_parent.max()) > 0.0

    stmt = sc.displacive_statement(parent, K, irrep="S3", direction="(a,b)")
    y_child = np.asarray(Refinement(
        Structure(phases=[stmt.phase]), ins.model_copy(deep=True)).predict(TWO_THETA))
    live = y_parent > 1e-6 * float(y_parent.max())
    ratio = y_child[live] / y_parent[live]
    assert float(np.median(ratio)) == pytest.approx(stmt.index ** 2, rel=1e-9)
    worst = float(np.max(np.abs(ratio - stmt.index ** 2)))
    assert worst <= 1e-9 * (stmt.index ** 2)


# --------------------------------------------------------- item 3: A != 0 decisive test
def _explicit_p1_statement(irrep: str, direction: str = "(a,b)", *,
                           magnitude: float, monkeypatch):
    """The same ``displacive_statement`` call, with every operation but the
    identity forced out of the declared group -- so every raw position is
    its own explicit representative and no symmetry-propagation step runs at
    all.  Monkeypatches :func:`~rietx.crystallography.magnetic.supercell.
    _sign_consistent_operations` rather than reimplementing
    ``magnetic_supercell``'s construction, so every other step (mode
    normalisation, tie list, amplitude seeding) is bit-identical to the real
    path and only the *declared symmetry* differs.
    """
    identity = tuple(tuple(int(i == j) for j in range(3)) for i in range(3))

    def _force_p1(cand, m_matrix, ops):
        return {op for op in ops if op[0] == identity
               and all(v == 0 for v in op[1])}

    monkeypatch.setattr(sc, "_sign_consistent_operations", _force_p1)
    parent = parent_phase()
    return sc.displacive_statement(parent, K, irrep=irrep, direction=direction,
                                   magnitude=magnitude, vary=False)


@pytest.mark.parametrize("irrep", ["S3", "S2"])
def test_reduced_group_child_matches_an_explicit_p1_build(irrep, monkeypatch):
    """The reduced-group child's predicted pattern equals a fully explicit P1
    build's, to |dy| <= 1e-10 of the peak -- the test that proves option (a)
    is exact (and that would falsify it if reflection enumeration under a
    subgroup were not).  S3(a,b) is where the fix changes anything; S2(a,b)
    is the clean control, verifying the *method* (declaring fewer operations
    and listing more atoms explicitly) changes nothing when forced past what
    the sign-consistency check itself would have kept.
    """
    parent = parent_phase()
    reduced = sc.displacive_statement(parent, K, irrep=irrep, direction="(a,b)",
                                      magnitude=0.05, vary=False)
    p1 = _explicit_p1_statement(irrep, magnitude=0.05, monkeypatch=monkeypatch)
    assert len(p1.phase.atoms) == 16  # every one of the 16 raw positions, explicit

    ins = instrument()
    y_reduced = np.asarray(Refinement(
        Structure(phases=[reduced.phase]), ins.model_copy(deep=True)).predict(TWO_THETA))
    y_p1 = np.asarray(Refinement(
        Structure(phases=[p1.phase]), ins.model_copy(deep=True)).predict(TWO_THETA))
    peak = float(y_reduced.max())
    assert peak > 0.0
    worst = float(np.max(np.abs(y_reduced - y_p1)))
    assert worst <= 1e-10 * peak


# --------------------------------------------------------- item 5: the moment path
def _magnetic_ground_truth(irrep: str, direction: str = "(a,b)"):
    """Whether ``compile_magnetic_sites`` reproduces a *random* amplitude
    combination's own ground-truth moment at every raw child position, for a
    kind="magnetic" candidate at the same k -- the moment-path twin of
    ``_displacive_ground_truth`` above.  Returns ``(n_atoms, free_amplitudes,
    total_checks, mismatches)``.
    """
    label = f"{irrep}{direction}"
    parent = parent_phase()
    lattice = np.asarray(cartesian_basis(*parent.cell.lengths_angles()),
                         dtype=np.float64).T
    mcell = iso.magnetic_cell(parent.space_group, K)
    per_site = []
    for atom in parent.atoms:
        cs = iso.candidates(parent.space_group,
                            (atom.x.value, atom.y.value, atom.z.value),
                            mcell.k, kind="magnetic", cell=lattice, verify=True)
        per_site.append({c.label: c for c in cs if c.verified is not False})
    reference = per_site[0][label]
    if reference.free_amplitudes == 0:
        return len(parent.atoms), 0, 0, []

    stmt = sc.magnetic_supercell(parent, candidate=reference, nuclear_group="magnetic",
                                 magnetic_species=["Ti", "O"], ion="Fe3+", magnitude=1.0)
    phase = stmt.phase
    basis = sc.child_basis(parent.space_group, mcell.k)

    gt = {}
    for j, atom in enumerate(parent.atoms):
        cand = per_site[j][label]
        mm = iso._fraction_inverse(basis) @ sc._matrix_of(cand.cell.basis)
        gpos = (cand.positions @ mm.T) % 1.0
        gconf = np.array([c @ mm.T for c in cand.configurations])
        gt[j] = (gpos, gconf)

    a = RNG.normal(size=reference.free_amplitudes)
    atoms = list(phase.atoms)
    for i, (j, _coset) in enumerate(stmt.site_map):
        if atoms[i].moment is None:
            continue
        xyz = np.array([atoms[i].x.value, atoms[i].y.value, atoms[i].z.value])
        gpos, gconf = gt[j]
        hits = [k for k in range(gpos.shape[0]) if _same_site(gpos[k], xyz)]
        assert hits, f"representative {atoms[i].label} missing from ground truth"
        truth = a @ gconf[:, hits[0], :]
        atoms[i] = atoms[i].model_copy(update={
            "moment": Moment.from_values(tuple(float(v) for v in truth),
                                         atoms[i].moment.ion, vary=False)})
    phase = phase.model_copy(update={"atoms": atoms})

    sites = compile_phase_sites(phase)
    magsites = compile_magnetic_sites(phase, sites.ops)
    assert magsites is not None

    total = 0
    mismatches = []
    for i, (j, _coset) in enumerate(stmt.site_map):
        if phase.atoms[i].moment is None:
            continue
        atom_repr = phase.atoms[i]
        xyz = np.array([atom_repr.x.value, atom_repr.y.value, atom_repr.z.value])
        m_stored = np.array(atom_repr.moment.values())
        rot, tran = sites.ops[i]
        mom_mat = magsites.mom_mat[i]
        gpos, gconf = gt[j]
        for m in range(rot.shape[0]):
            image = (rot[m] @ xyz + tran[m]) % 1.0
            predicted = mom_mat[m] @ m_stored
            hits = [k for k in range(gpos.shape[0]) if _same_site(gpos[k], image)]
            total += 1
            if not hits:
                mismatches.append((atom_repr.label, m, "no ground-truth match"))
                continue
            actual = a @ gconf[:, hits[0], :]
            rel = (float(np.max(np.abs(predicted - actual)))
                  / max(float(np.max(np.abs(actual))), 1e-12))
            if rel > 1e-6:
                mismatches.append((atom_repr.label, m, (predicted.tolist(), actual.tolist())))
    return len(phase.atoms), reference.free_amplitudes, total, mismatches


@pytest.mark.parametrize("irrep", ["S1", "S2", "S3", "S4"])
def test_moment_path_is_clean_by_design(irrep):
    """The moment (magnetic) twin of S3(a,b)'s displacive candidate: 0
    mismatches, un-reduced declared group, on the same fixture and k.

    ``magnetic_supercell``'s ``nuclear_group="magnetic"`` reduction (this
    file's fix) is gated to ``candidate.kind == "displacive"`` and left
    untouched here on purpose: ``compile_magnetic_sites`` re-derives every
    nuclear image's axial matrix (eps*det(R)*R) from the *full*,
    non-colourless ``phase.magnetic_symmetry.group()`` at compile time, one
    operation at a time, matched by *position* rather than trusted from the
    declared nuclear group -- so it never inherits the declared group's
    dropped eta in the first place.  ``test_naive_moment_propagation_would_
    flip_sign`` below is the positive control that this test is not merely
    insensitive to the defect.
    """
    n_atoms, n_free, total, mismatches = _magnetic_ground_truth(irrep)
    if n_free == 0:
        pytest.skip(f"{irrep}(a,b) magnetic candidate has no free amplitude")
    assert total > 0
    assert mismatches == []


def test_naive_moment_propagation_would_flip_sign():
    """Positive control for the test above: propagating a representative's
    stored moment to its sibling by the *bare* declared-group rotation alone
    (no det(R), no magnetic-group eta -- exactly the mechanism that is wrong
    for distortion modes) gives exactly the negative of the true moment,
    every time, on S3(a,b)'s own magnetic candidate.  So the ground-truth
    method above is not vacuously passing: it can and does see this sign
    flip when the naive (declared-group-only) propagation is used instead of
    ``compile_magnetic_sites``'s own per-operation, per-image lookup.
    """
    label = "S3(a,b)"
    parent = parent_phase()
    lattice = np.asarray(cartesian_basis(*parent.cell.lengths_angles()),
                         dtype=np.float64).T
    mcell = iso.magnetic_cell(parent.space_group, K)
    per_site = []
    for atom in parent.atoms:
        cs = iso.candidates(parent.space_group,
                            (atom.x.value, atom.y.value, atom.z.value),
                            mcell.k, kind="magnetic", cell=lattice, verify=True)
        per_site.append({c.label: c for c in cs if c.verified is not False})
    reference = per_site[0][label]
    stmt = sc.magnetic_supercell(parent, candidate=reference, nuclear_group="magnetic",
                                 magnetic_species=["Ti", "O"], ion="Fe3+", magnitude=1.0)
    phase = stmt.phase
    basis = sc.child_basis(parent.space_group, mcell.k)
    sites = compile_phase_sites(phase)

    gt = {}
    for j, atom in enumerate(parent.atoms):
        cand = per_site[j][label]
        mm = iso._fraction_inverse(basis) @ sc._matrix_of(cand.cell.basis)
        gpos = (cand.positions @ mm.T) % 1.0
        gconf = np.array([c @ mm.T for c in cand.configurations])
        gt[j] = (gpos, gconf)

    a = RNG.normal(size=reference.free_amplitudes)
    checked_a_nontrivial_sibling = False
    for i, (j, _coset) in enumerate(stmt.site_map):
        atom = phase.atoms[i]
        if atom.moment is None:
            continue
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        gpos, gconf = gt[j]
        hits0 = [k for k in range(gpos.shape[0]) if _same_site(gpos[k], xyz)]
        assert hits0
        m_stored = a @ gconf[:, hits0[0], :]
        rot, tran = sites.ops[i]
        for m in range(rot.shape[0]):
            image = (rot[m] @ xyz + tran[m]) % 1.0
            if _same_site(image, xyz):
                continue   # the identity image: nothing to propagate to
            naive = rot[m] @ m_stored   # WRONG: no det(R), no magnetic eta
            hits = [k for k in range(gpos.shape[0]) if _same_site(gpos[k], image)]
            assert hits
            actual = a @ gconf[:, hits[0], :]
            assert np.allclose(naive, -actual, atol=1e-8, rtol=1e-6), (
                f"expected the naive propagation to flip sign at {atom.label} "
                f"image {m}; got naive={naive} actual={actual}")
            checked_a_nontrivial_sibling = True
    assert checked_a_nontrivial_sibling


# --------------------------------------------------------- item 6: multi-component
def _explicit_p1_multi_component(labels, *, magnitude, monkeypatch):
    identity = tuple(tuple(int(i == j) for j in range(3)) for i in range(3))

    def _force_p1(cand, m_matrix, ops):
        return {op for op in ops if op[0] == identity
               and all(v == 0 for v in op[1])}

    monkeypatch.setattr(sc, "_sign_consistent_operations", _force_p1)
    parent = parent_phase()
    return sc.displacive_statement(
        parent, components=[(K, label.split("(", 1)[0], "(" + label.split("(", 1)[1])
                            for label in labels],
        magnitude=magnitude, vary=False)


@pytest.mark.parametrize("labels", [("S2(a,b)", "S3(a,b)"), ("S2(a,b)", "S4(a,b)")])
def test_multi_component_reduction_matches_an_explicit_p1_build(labels, monkeypatch):
    """M2d's item 6: the intersection, reduced to the subgroup that is
    sign-consistent for **every** component, predicts the same pattern as a
    fully explicit P1 build of the same pair -- the gate the brief sets
    before D3's refusal may be relaxed into a build. Both S2(a,b)+S3(a,b)
    (the brief's own headline pair -- S2's grey group intersected with S3's
    gives back exactly S3's own group, a strict subgroup) and S2(a,b)+S4(a,b)
    (the refusal's other named pair) pass this test, so both are now built
    rather than refused (``test_multi_component_statements.py::
    test_s2_plus_s3_and_s2_plus_s4_now_build_via_the_reduction`` asserts the
    new, non-refusing behaviour).
    """
    parent = parent_phase()
    reduced = sc.displacive_statement(
        parent, components=[(K, label.split("(", 1)[0], "(" + label.split("(", 1)[1])
                            for label in labels],
        magnitude=0.05, vary=False)
    p1 = _explicit_p1_multi_component(labels, magnitude=0.05, monkeypatch=monkeypatch)
    assert len(p1.phase.atoms) == 16

    ins = instrument()
    y_reduced = np.asarray(Refinement(
        Structure(phases=[reduced.phase]), ins.model_copy(deep=True)).predict(TWO_THETA))
    y_p1 = np.asarray(Refinement(
        Structure(phases=[p1.phase]), ins.model_copy(deep=True)).predict(TWO_THETA))
    peak = float(y_reduced.max())
    assert peak > 0.0
    worst = float(np.max(np.abs(y_reduced - y_p1)))
    assert worst <= 1e-10 * peak
