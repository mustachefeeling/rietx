"""Multi-component magnetic/displacive statements (M2): a phase whose modes span
more than one (k, irrep, direction) component.

Two forms, per the ROADMAP's "Multi-component magnetic statements" note
(2026-09-08) and ``briefs/M2_MULTI_COMPONENT.md``:

* **Form (a)** — several components at *one* k (``displacive_statement(...,
  components=[...])``): the child is the intersection of every component's
  isotropy subgroup, built with :class:`~rietx.crystallography.magnetic.
  operators.MagneticGroup.from_operations` and stated through
  ``Phase.symmetry_operations`` when no symbol names it (Q-17).
* **Form (b)** — several k's sharing the *parent* cell, no supercell
  (:func:`~rietx.crystallography.magnetic.supercell.fourier_statement`): the
  schema and the reflection-list union (WP-1326's own satellite machinery)
  are real and tested; there is no intensity path, and ``displacive_statement``
  refuses a ``components=`` call spanning more than one k by name rather than
  silently building something wrong.

**A real defect this rung found in form (a), and how these tests are scoped
around it.** A zone-boundary little group is generally *grey*: the same
spatial operation {R | t} sits in a candidate's own group twice, once with
little-group character ε = +1 (a true symmetry of *that* candidate's own mode
field) and once with ε = −1 (a symmetry only jointly with flipping the
amplitude's sign).  The single-component builder never needs to tell the two
apart — it assigns every child atom's vector by direct position-match against
``candidate.positions``/``configurations``, never by rotating a sibling's.
But the *multi*-component intersection can be a **strict** subgroup of a
component's own group, and then that component has fewer independent
representatives than its own orbit; the compiled ``Phase``'s ordinary
symmetry expansion (used by every structure-factor consumer) then propagates
a representative's vector to its siblings **by rotation alone**, which is
only correct if the operation used was the ε = +1 copy.  Measured directly
(not asserted) on Ba₂FeSbSe₅'s own S2(a,b) ⊕ S3(a,b) at k = (½,0,½): S2's own
group is grey (order 16); the intersection with S3's turns out to equal S3's
own (colourless) group exactly — a strict subgroup of S2's — and propagating
S2's mode through it gives the **wrong sign** on half of S2's own atoms
relative to what its own (``in_allowed_span``-verified) configuration says.
``_component_respects_declared_symmetry`` was the safety check this rung
added to catch exactly that, and the builder **refused** rather than shipped
it — a second, narrower anomaly the safety check did *not* cover (a
discrepancy against the **pre-existing single-component** builder even when
the intersection is trivial) was flagged, not fixed, out of scope for M2; see
the report's DECISIONS section for the full account.

**Both the refusal and the single-component anomaly above were later fixed by
M2d** (checks/M2B_SINGLE_COMPONENT_SIGN_CHECK.md, checks/
M2D_EPSILON_BOOKKEEPING.md): the declared group is reduced, per component, to
the subgroup that is a symmetry of that component's own **signed** field
(``supercell._sign_consistent_operations``) rather than refused whenever any
operation fails for any one component — so S2(a,b) ⊕ S3(a,b) and S2(a,b) ⊕
S4(a,b) now **build** (``test_s2_plus_s3_and_s2_plus_s4_now_build_via_the_
reduction`` below), verified exact against a fully explicit P1 build in
``tests/test_epsilon_bookkeeping.py``.  The tests below still verify form (a)
**within its own multi-component object** (never by comparing to the
single-component builder's output in general) for S3(a,b) ⊕ S4(a,b), whose
intersection happens to be trivial (P1: every raw position listed explicitly,
no symmetry-propagation risk at all) — the safe pair even before M2d.

M1's own schema (``Phase.distortion_modes``) already carried a per-mode k,
irrep label and direction, so nothing about *storage* needed to change for one
phase to hold several components — only a grouped view
(``Phase.distortion_components``), tested in the first section below.
"""
import numpy as np
import pytest

import rietx as rx
from rietx import Instrument, Refinement
from rietx.crystallography.magnetic.supercell import (
    MultiComponentStatement,
    displacive_statement,
    fourier_statement,
    seed_distortion_amplitudes,
)
from rietx.crystallography.satellites import satellite_reflections
from rietx.crystallography.symmetry import generate_reflections
from rietx.report.layer2 import delta_bic
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, DistortionComponent, Phase, Structure

WAVELENGTH = 1.5406
K = ("1/2", "0", "1/2")


def parent_phase() -> Phase:
    """A two-site Pnma parent (M1's own toy fixture): S1/S2/S3/S4(a,b) all
    build at k = (1/2,0,1/2), the same four directions Ba2FeSbSe5's real
    acceptance uses, so this fixture reproduces the real case's group
    structure at a fraction of the size (8 child atoms instead of 28).
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


def instrument() -> Instrument:
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.profile.w.value = 0.004
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=30.0), Parameter(value=-4.0)])
    return ins


TWO_THETA = np.arange(10.0, 110.0, 0.02)


def simulate(phase: Phase, seed: int):
    """A Poisson-noised pattern of one phase, on the shared 2θ grid (M1's helper)."""
    from rietx import PatternData
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    structure = Structure(phases=[phase])
    ins = instrument()
    blank = PatternData(two_theta=TWO_THETA.tolist(),
                        intensity=np.zeros_like(TWO_THETA).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    return PatternData(
        two_theta=model.tt.tolist(),
        intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())


def combined_statement() -> MultiComponentStatement:
    """S3(a,b) + S4(a,b): the safety check accepts this pair (measured
    intersection is trivial — P1, all 16 raw positions listed explicitly, so
    there is no symmetry-propagation step for the check to accept or refuse
    in the first place, and no room for the grey-little-group sign bug that
    refuses S2+S3)."""
    return displacive_statement(parent_phase(), components=[
        (K, "S3", "(a,b)"), (K, "S4", "(a,b)")])


# --------------------------------------------------------- the schema view
def test_a_single_component_phase_groups_into_exactly_one_component():
    """Every phase M1's builder ever produced groups into one entry — the
    claim that nothing about storage had to change for the view to exist."""
    statement = displacive_statement(parent_phase(), K, irrep="S2", direction="(a,b)")
    comps = statement.phase.distortion_components
    assert len(comps) == 1
    assert isinstance(comps[0], DistortionComponent)
    assert comps[0].irrep_label == "S2"
    assert comps[0].direction == "(a,b)"
    assert comps[0].k == K
    assert len(comps[0].modes) == len(statement.phase.distortion_modes)


def test_distortion_components_groups_by_k_irrep_direction_in_first_seen_order():
    statement = combined_statement()
    comps = statement.phase.distortion_components
    assert len(comps) == 2
    assert [(c.irrep_label, c.direction) for c in comps] == [
        ("S3", "(a,b)"), ("S4", "(a,b)")]
    assert all(c.k == K for c in comps)
    assert sum(len(c.modes) for c in comps) == len(statement.phase.distortion_modes)
    for c in comps:
        assert all(m.irrep_label == c.irrep_label and m.direction == c.direction
                  for m in c.modes)


def test_an_empty_phase_has_no_distortion_components():
    assert parent_phase().distortion_components == ()


# ---------------------------------------- components= delegates, bit-identical
def test_a_single_element_components_list_delegates_to_the_old_call():
    """``components=[(k, irrep, direction)]`` is exactly the old call — not a
    second implementation that might drift from it, but literally the same
    function invocation (see ``_multi_component_displacive_statement``)."""
    old = displacive_statement(parent_phase(), K, irrep="S2", direction="(a,b)")
    new = displacive_statement(parent_phase(), components=[(K, "S2", "(a,b)")])
    assert type(old) is type(new)
    assert old.phase.model_dump_json() == new.phase.model_dump_json()
    assert old.child_space_group == new.child_space_group
    assert old.transform == new.transform


def test_components_and_k_together_are_refused():
    with pytest.raises(ValueError, match="not both"):
        displacive_statement(parent_phase(), K, components=[(K, "S2", "(a,b)")])


def test_neither_k_nor_components_is_refused():
    with pytest.raises(ValueError, match="pass k"):
        displacive_statement(parent_phase())


def test_empty_components_is_refused():
    with pytest.raises(ValueError, match="no order parameter"):
        displacive_statement(parent_phase(), components=[])


def test_a_duplicate_component_label_is_refused():
    with pytest.raises(ValueError, match="named twice"):
        displacive_statement(parent_phase(), components=[
            (K, "S2", "(a,b)"), (K, "S2", "(a,b)")])


def test_child_group_is_refused_in_multi_component_mode():
    with pytest.raises(ValueError, match="no single one to check"):
        displacive_statement(parent_phase(), components=[
            (K, "S3", "(a,b)"), (K, "S4", "(a,b)")], child_group="Pm")


# ------------------------------------------------- form (a): the common child
def test_the_common_subgroup_child_builds_group_order_atoms_label_constraints():
    statement = combined_statement()
    assert isinstance(statement, MultiComponentStatement)
    assert statement.labels == ("S3(a,b)", "S4(a,b)")
    assert len(statement.phase.atoms) == 16       # trivial intersection: nothing merges
    assert len(statement.phase.distortion_modes) == 12  # 8 (S3) + 4 (S4)
    for name in ("a", "b", "c", "alpha", "beta", "gamma"):
        assert getattr(statement.phase.cell, name).vary is False
    y = Refinement(Structure(phases=[statement.phase]), instrument()).predict(TWO_THETA)
    assert np.all(np.isfinite(y))


def test_a_zero_amplitude_control_is_det_p_squared_times_the_parent():
    """A = 0 on the combined child reproduces the parent exactly, scaled by
    |det P|^2 — Q-17's own precedent for a single unnamed component, now
    measured for a two-component intersection child.  Unaffected by the
    grey-little-group sign question above: at A = 0 no mode contributes at
    all, on either side of the sign, so this is the one claim that holds
    regardless of which components are combined."""
    statement = combined_statement()
    ins = instrument()
    ins.background = BackgroundChebyshev(coefficients=[Parameter(value=0.0)])
    y_parent = Refinement(Structure(phases=[parent_phase()]),
                          ins.model_copy(deep=True)).predict(TWO_THETA)
    y_child = Refinement(Structure(phases=[statement.phase]),
                         ins.model_copy(deep=True)).predict(TWO_THETA)
    det_p_sq = float(statement.index) ** 2
    residual = float(np.max(np.abs(y_child - det_p_sq * y_parent)))
    assert residual <= 1e-6 * float(y_parent.max()), (
        f"A=0 combined child is not |det P|^2 = {det_p_sq} times the parent: "
        f"worst point off by {residual:.3g} against a peak of {y_parent.max():.3g}")

    # S2+S3 used to refuse outright (see
    # test_s2_plus_s3_and_s2_plus_s4_now_build_via_the_reduction below,
    # updated by M2d/checks/M2D_EPSILON_BOOKKEEPING.md): its own A=0 control
    # is asserted there rather than duplicated here.


def test_a_direction_missing_from_one_orbit_is_refused_in_multi_component_mode():
    with pytest.raises(ValueError, match="is not carried by every orbit"):
        displacive_statement(parent_phase(), components=[
            (K, "S3", "(a,b)"), (K, "S9", "(nonexistent)")])


def test_s2_plus_s3_and_s2_plus_s4_now_build_via_the_reduction():
    """M2d: the refusal this test used to pin (``test_s2_plus_s3_is_refused_
    by_the_grey_little_group_sign_check`` on 3e53660d) is now a *build*.

    D3's own diagnosis was right that the naive positional intersection
    (``MagneticGroup.from_operations`` on ``{R, t}`` pairs alone) cannot tell
    S2's grey operation's two little-group characters apart — but M2d's
    ``_sign_consistent_operations`` (built for the single-component defect,
    checks/M2B_SINGLE_COMPONENT_SIGN_CHECK.md) answers exactly that question
    per operation, so the intersection is now *reduced* to the subgroup that
    is sign-consistent for **every** component instead of refused whenever
    any operation fails for any one of them.  Verified exact (not merely
    constructed) by an A != 0 P1-equality test for both pairs
    (``tests/test_epsilon_bookkeeping.py::
    test_multi_component_reduction_matches_an_explicit_p1_build``) — this
    test only re-asserts the *shape* of the result and the A=0 negative
    control, which that file does not repeat.
    """
    s2s3 = displacive_statement(parent_phase(), components=[
        (K, "S2", "(a,b)"), (K, "S3", "(a,b)")])
    assert isinstance(s2s3, MultiComponentStatement)
    assert s2s3.labels == ("S2(a,b)", "S3(a,b)")
    assert s2s3.child_group_named is False
    assert s2s3.phase.space_group == "Pm [unnamed in 2a,b,a+c]"
    assert set(s2s3.phase.symmetry_operations) == {"x,y,z", "x,-y+1/2,z"}
    assert len(s2s3.phase.atoms) == 16          # every raw position explicit
    assert len(s2s3.phase.distortion_modes) == 16   # 8 (S2) + 8 (S3)

    s2s4 = displacive_statement(parent_phase(), components=[
        (K, "S2", "(a,b)"), (K, "S4", "(a,b)")])
    assert isinstance(s2s4, MultiComponentStatement)
    assert s2s4.labels == ("S2(a,b)", "S4(a,b)")
    assert s2s4.child_group_named is True
    assert s2s4.phase.space_group == "P -1"
    assert len(s2s4.phase.atoms) == 8
    assert len(s2s4.phase.distortion_modes) == 12   # 8 (S2) + 4 (S4)

    # the A=0 negative control on both, the same one every other combination
    # gets (comment above test_a_zero_amplitude_control_is_det_p_squared_
    # times_the_parent)
    ins = instrument()
    ins.background = BackgroundChebyshev(coefficients=[Parameter(value=0.0)])
    y_parent = Refinement(Structure(phases=[parent_phase()]),
                          ins.model_copy(deep=True)).predict(TWO_THETA)
    for statement in (s2s3, s2s4):
        y_child = Refinement(Structure(phases=[statement.phase]),
                             ins.model_copy(deep=True)).predict(TWO_THETA)
        det_p_sq = float(statement.index) ** 2
        residual = float(np.max(np.abs(y_child - det_p_sq * y_parent)))
        assert residual <= 1e-6 * float(y_parent.max()), (
            f"{statement.labels}: A=0 child is not |det P|^2 = {det_p_sq} "
            f"times the parent: worst point off by {residual:.3g} against "
            f"a peak of {y_parent.max():.3g}")


# ------------------------------------------------- form (a): the positive arm
def test_s3_alone_is_preferred_within_the_joint_statement_when_data_is_s3_alone():
    """The handoff's own positive arm (T-B, checks/TA0_SUPERSTRUCTURE_K.md):
    'S2 alone must be recovered as the ΔBIC-preferred model when the data
    were generated with S2 alone' — restated for the pair this rung can
    actually build and trust (S3/S4, see the module docstring for why S2/S3
    is refused rather than fit), and tested **entirely inside one joint
    statement** rather than by comparing to the single-component builder
    (which this investigation found is not always a safe cross-check).
    Truth: the joint S3⊕S4 child with only S3's amplitudes non-zero.  Two
    restricted fits against that one pattern, both starting from the *same*
    joint object and freeing only one component's amplitudes at a time — S3's
    own subset must beat S4's.
    """
    truth = combined_statement()
    s3_names = [m.name for m in truth.phase.distortion_modes if m.irrep_label == "S3"]
    s4_names = [m.name for m in truth.phase.distortion_modes if m.irrep_label == "S4"]
    truth_seeded = seed_distortion_amplitudes(truth.phase, {n: 0.09 for n in s3_names},
                                              vary=False)
    data = simulate(truth_seeded, seed=13)

    ins = instrument()
    scale_bkg = ["phases.*.scale", "instrument.background.c*"]
    ref = Refinement(Structure(phases=[parent_phase()]), ins.model_copy(deep=True))
    ref_res = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", scale_bkg, max_iter=200)]))
    ref_chi2_abs = float(ref_res.statistics.chi2) * max(
        ref_res.statistics.n_points - ref_res.statistics.n_free_parameters, 1)
    n_points = int(ref_res.statistics.n_points)

    def fit_dbic(names):
        seeded = seed_distortion_amplitudes(truth.phase, {n: 0.03 for n in names},
                                            vary=True)
        fit_ref = Refinement(Structure(phases=[seeded]), ins.model_copy(deep=True))
        for t, s, sc, off in truth.biso_ties:
            fit_ref.tie(t, s, scale=sc, offset=off)
        # only the named modes are free (others stay at their seeded/zero value
        # because their own `vary` is untouched — the rest of `truth.phase`'s
        # modes are still `vary=False` from the builder's own default)
        free_paths = scale_bkg + [f"phases.0.distortion_modes.{i}.amplitude"
                                  for i, m in enumerate(seeded.distortion_modes)
                                  if m.name in names]
        res = fit_ref.fit(data, plan=rx.RefinementPlan(stages=[
            rx.Stage("scale", scale_bkg, max_iter=200),
            rx.Stage("all", free_paths, max_iter=400)]))
        chi2_abs = float(res.statistics.chi2) * max(
            res.statistics.n_points - res.statistics.n_free_parameters, 1)
        return delta_bic(ref_chi2_abs, chi2_abs, n_points, len(names))

    dbic_s3 = fit_dbic(s3_names)
    dbic_s4 = fit_dbic(s4_names)

    assert dbic_s3 > dbic_s4, (
        f"S3's own amplitudes (ΔBIC={dbic_s3:.1f}) must beat S4's "
        f"(ΔBIC={dbic_s4:.1f}) when the data were generated with S3 alone")
    assert dbic_s3 > 0, f"S3 alone should show a positive ΔBIC gain, got {dbic_s3:.1f}"


# ------------------------------------------------------ form (b): the boundary
def test_two_distinct_k_in_components_is_refused_pointing_at_fourier_statement():
    with pytest.raises(ValueError, match="fourier_statement"):
        displacive_statement(parent_phase(), components=[
            (K, "S3", "(a,b)"), (("0", "1/2", "0"), "S1", "(a,b)")])


def test_fourier_statement_refuses_a_single_k():
    with pytest.raises(ValueError, match="displacive_statement"):
        fourier_statement(parent_phase(), [(K, "S2", "(a,b)")],
                          wavelength=WAVELENGTH, two_theta_max=100.0)


def test_fourier_statement_has_no_route_to_a_compilable_phase():
    """No attribute or method on the returned object yields a ``Phase``."""
    stmt = fourier_statement(parent_phase(), [
        (K, "S2", "(a,b)"), (("0", "1/2", "0"), "S1", "(a,b)")],
        wavelength=WAVELENGTH, two_theta_max=100.0)
    assert not hasattr(stmt, "phase")
    for name in dir(stmt):
        if name.startswith("_"):
            continue
        value = getattr(stmt, name)
        assert not isinstance(value, Phase), (
            f"FourierStatement.{name} is a Phase; form (b) must have no route "
            f"to a compilable one")


def test_fourier_statement_reflection_list_is_the_union_of_parent_and_satellites():
    parent = parent_phase()
    k2 = ("0", "1/2", "0")
    stmt = fourier_statement(parent, [(K, "S2", "(a,b)"), (k2, "S1", "(a,b)")],
                             wavelength=WAVELENGTH, two_theta_max=100.0)
    cell = parent.cell.lengths_angles()
    nuclear = generate_reflections(parent.space_group, cell, WAVELENGTH, 100.0)
    sat1 = satellite_reflections(parent.space_group, cell, WAVELENGTH, 100.0, K)
    sat2 = satellite_reflections(parent.space_group, cell, WAVELENGTH, 100.0, k2)

    def index_set(rs):
        return {tuple(round(v, 6) for v in row) for row in rs.index}

    hand_union = index_set(nuclear) | index_set(sat1) | index_set(sat2)
    got_union = {tuple(round(v, 6) for v in row) for row in stmt.reflections}
    assert got_union == hand_union
    assert len(stmt.reflections) == len(hand_union)
    assert set(stmt.ks) == {K, k2}
    assert len(stmt.nuclear) == len(nuclear)


def test_fourier_statement_validates_each_k_against_the_parents_symmetry():
    """k = 0 is refused the same way a single-k ``Phase.propagation_vector``
    is (``check_propagation_vector``) — this function reuses that check
    rather than silently enumerating a satellite list at the origin."""
    parent = parent_phase()
    with pytest.raises(ValueError):
        fourier_statement(parent, [(K, "S2", "(a,b)"), (("0", "0", "0"), "S1", "(a,b)")],
                          wavelength=WAVELENGTH, two_theta_max=100.0)
