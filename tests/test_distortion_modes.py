"""Displacive distortion modes (M-1): the schema, the engine hook, the builder.

The claim under test is that a superstructure can be refined with **one
amplitude per symmetry-adapted mode** instead of the child cell's free
coordinates, and that the amplitude behaves like any other ``Parameter``.
Three properties carry that, and each has its own group here:

* **exactly off.**  A phase declaring no mode, and a phase whose modes are all
  at zero, reach the same arithmetic as a phase without the field — pinned on
  ``predict()`` bit-for-bit, not on a tolerance.
* **exact, not approximate.**  x = x⁰ + Σ A_ν e_νj is affine and so is the
  parameter table's constraint block, so the coordinate rows carry A·e to
  roundoff and a recompile is a fixed point (the amplitude is never applied
  twice).
* **refuses rather than lies.**  The five states in which a mode statement is
  not a model — a zero mode, a wrong vector count, a free cell, an all-zero
  free amplitude vector, an amplitude degenerate with the coordinates it moves
  — are refusals with the reason in them.

The synthetic round trip is one fit carrying both arms: eight amplitudes free
against a pattern in which exactly one is non-zero.
"""

import numpy as np
import pytest

import rietx as rx
from rietx import DistortionMode, Instrument, PatternData, Refinement
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.supercell import (
    displacive_statement,
    seed_distortion_amplitudes,
)
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.report.distortion import analyse_distortion_modes
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import (
    DISTORTION_AMPLITUDE_MAX_A,
    Atom,
    Cell,
    Phase,
    Structure,
)

WAVELENGTH = 1.5406
AMPLITUDE_GLOB = "phases.*.distortion_modes.*.amplitude"

#: The k and direction the small cases use.  Not free choices: two upstream
#: fences narrow them, both measured and neither fixable from here —
#: ``candidates(kind="displacive", verify=True)`` raises for a site on the
#: inversion centre of Pnma at k = (0,0,½), and ``magnetic_supercell``'s
#: symbol check refuses the S1 directions, whose P2₁ isotropy subgroup no
#: Hermann-Mauguin symbol reproduces in the doubled cell.
SMALL_K = ("1/2", "0", "0")
SMALL_IRREP = "S2"
SMALL_DIRECTION = "(rank 1)#2"


def parent_phase() -> Phase:
    """A two-site Pnma parent, both atoms on the 4c mirror.

    Two species rather than one so the superstructure reflections carry
    contrast from more than one sublattice, and both on 4c so the child is
    small: eight atoms, eight modes.
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


def small_statement():
    return displacive_statement(parent_phase(), SMALL_K, irrep=SMALL_IRREP,
                                direction=SMALL_DIRECTION)


def instrument() -> Instrument:
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.profile.w.value = 0.004
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=30.0), Parameter(value=-4.0)])
    return ins


TWO_THETA = np.arange(10.0, 110.0, 0.02)


def simulate(phase: Phase, seed: int) -> PatternData:
    """A Poisson-noised pattern of one phase, on the shared 2θ grid."""
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


# --------------------------------------------------------------- the schema
def test_a_mode_round_trips_through_json():
    mode = DistortionMode(
        name="S2(a,b)-Fe1-0", irrep_label="S2", direction="(a,b)",
        k=("1/2", 0, "1/2"), parent_site="Fe1",
        vectors=[(0.01, 0.0, -0.02), (0.0, 0.03, 0.0)])
    assert mode.k == ("1/2", "0", "1/2"), "k must store as rational strings"
    assert rx.DistortionMode.model_validate_json(mode.model_dump_json()) == mode


def test_the_amplitude_defaults_to_held_zero_within_the_displacement_bound():
    mode = DistortionMode(name="m", irrep_label="S1", direction="(a)",
                          k=("1/2", "0", "0"), vectors=[(0.1, 0.0, 0.0)])
    assert mode.amplitude.value == 0.0 and not mode.amplitude.vary
    assert mode.amplitude.unit == "A"
    assert (mode.amplitude.min, mode.amplitude.max) == (
        -DISTORTION_AMPLITUDE_MAX_A, DISTORTION_AMPLITUDE_MAX_A)


def test_a_mode_that_moves_nothing_is_refused():
    with pytest.raises(ValueError, match="identically zero"):
        DistortionMode(name="m", irrep_label="S1", direction="(a)",
                       k=("1/2", "0", "0"),
                       vectors=[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)])


def test_the_vector_count_must_be_the_atom_count():
    phase = parent_phase()
    mode = DistortionMode(name="m", irrep_label="S1", direction="(a)",
                          k=("1/2", "0", "0"), vectors=[(0.1, 0.0, 0.0)])
    with pytest.raises(ValueError, match="1 mode vectors but the phase has 2"):
        phase.model_copy(update={}).__class__.model_validate(
            {**phase.model_dump(), "distortion_modes": [mode.model_dump()]})


def test_two_modes_may_not_share_a_name():
    phase = parent_phase()
    mode = DistortionMode(name="m", irrep_label="S1", direction="(a)",
                          k=("1/2", "0", "0"),
                          vectors=[(0.1, 0.0, 0.0), (0.0, 0.0, 0.0)])
    with pytest.raises(ValueError, match="two distortion modes named"):
        Phase.model_validate({**phase.model_dump(),
                              "distortion_modes": [mode.model_dump(),
                                                   mode.model_dump()]})


def test_a_mode_is_refused_beside_a_propagation_vector():
    phase = parent_phase()
    mode = DistortionMode(name="m", irrep_label="S1", direction="(a)",
                          k=("1/2", "0", "0"),
                          vectors=[(0.1, 0.0, 0.0), (0.0, 0.0, 0.0)])
    with pytest.raises(ValueError, match="the same intensity placed twice"):
        Phase.model_validate({**phase.model_dump(),
                              "propagation_vector": ("1/2", "0", "0"),
                              "distortion_modes": [mode.model_dump()]})


# ---------------------------------------------------------- exactly off (a)
def test_at_zero_amplitude_the_pattern_is_the_undistorted_one_bit_for_bit():
    """(a) A = 0 is exactly the child with no modes declared.

    Bit-for-bit rather than to a tolerance, because the claim is that the
    coordinate rows reach the same arithmetic in the same order: the mode
    contributes an affine term whose coefficient is zero, and the base is the
    stored coordinate with that zero taken back out.
    """
    statement = small_statement()
    with_modes = statement.phase
    bare = with_modes.model_copy(update={"distortion_modes": []})
    ins = instrument()
    y_bare = Refinement(Structure(phases=[bare]),
                        ins.model_copy(deep=True)).predict(TWO_THETA)
    y_modes = Refinement(Structure(phases=[with_modes]),
                         ins.model_copy(deep=True)).predict(TWO_THETA)
    assert np.array_equal(y_bare, y_modes), (
        "declaring a mode at A = 0 moved the pattern by "
        f"{np.abs(y_bare - y_modes).max():.3g} counts; it must be exactly off")


def test_the_child_at_zero_amplitude_is_the_parent_pattern_rescaled():
    """The other half of (a): the child *is* the parent, restated.

    ``magnetic_supercell``'s own property, re-checked here because
    ``displacive_statement`` builds on it and then edits the phase.  The claim
    is about the **shape**: the child lists every atom of |det P| parent cells
    explicitly, so at A = 0 it diffracts the parent's structure and its
    pattern is the parent's times one constant — with **exactly nothing** at
    the superstructure positions, which is the half that matters here.  The
    constant itself is not 2 or 4: the child's own multiplicities and its
    reflection list are not the parent's, so it is measured rather than
    predicted (0.9927 in this cell) and the test is that one number explains
    every point.
    """
    ins = instrument()
    ins.background = BackgroundChebyshev(coefficients=[Parameter(value=0.0)])
    y_parent = Refinement(Structure(phases=[parent_phase()]),
                          ins.model_copy(deep=True)).predict(TWO_THETA)
    y_child = Refinement(Structure(phases=[small_statement().phase]),
                         ins.model_copy(deep=True)).predict(TWO_THETA)
    scale = float(np.sum(y_child * y_parent) / np.sum(y_parent ** 2))
    residual = float(np.abs(y_child - scale * y_parent).max())
    assert residual <= 1e-9 * float(y_parent.max()), (
        f"the child at A = 0 is not the parent rescaled: worst point off by "
        f"{residual:.3g} counts against a peak of {y_parent.max():.3g} "
        f"(fitted scale {scale:.4f})")


# ----------------------------------------------------------- exact, not approximate
def test_the_coordinate_rows_carry_the_amplitude_times_the_mode_vector():
    """x = x⁰ + Σ A_ν e_νj, to roundoff, on every row the mode touches."""
    statement = small_statement()
    mode = statement.phase.distortion_modes[0]
    seeded = seed_distortion_amplitudes(statement.phase, {mode.name: 0.08})
    rows = {r.path: r.value for r in Refinement(
        Structure(phases=[seeded]), instrument()).parameters()}
    for j, vector in enumerate(mode.vectors):
        for c, name in zip(vector, ("x", "y", "z"), strict=True):
            want = getattr(statement.phase.atoms[j], name).value + 0.08 * c
            assert rows[f"phases.0.atoms.{j}.{name}"] == pytest.approx(
                want, abs=1e-12), f"atom {j} {name}"


def test_seeding_without_moving_the_atoms_would_change_nothing():
    """The invariant that makes a recompile a fixed point, stated as a test.

    The base a mode is measured from is ``atom.xyz − Σ A_ν e_νj``, so setting
    an amplitude *alone* moves the base back by exactly what the mode moves
    forward.  This is why ``seed_distortion_amplitudes`` exists, and the test
    is here because the failure is silent: a statement seeded at 0.08 Å that
    predicts the undistorted pattern.
    """
    statement = small_statement()
    mode = statement.phase.distortion_modes[0]
    amplitude_only = statement.phase.model_copy(update={
        "distortion_modes": [
            m.model_copy(update={"amplitude": m.amplitude.model_copy(
                update={"value": 0.08})}) if m.name == mode.name else m
            for m in statement.phase.distortion_modes]})
    ins = instrument()
    y_zero = Refinement(Structure(phases=[statement.phase]),
                        ins.model_copy(deep=True)).predict(TWO_THETA)
    y_amplitude_only = Refinement(Structure(phases=[amplitude_only]),
                                  ins.model_copy(deep=True)).predict(TWO_THETA)
    assert np.array_equal(y_zero, y_amplitude_only)
    y_seeded = Refinement(
        Structure(phases=[seed_distortion_amplitudes(
            statement.phase, {mode.name: 0.08})]),
        ins.model_copy(deep=True)).predict(TWO_THETA)
    assert not np.array_equal(y_zero, y_seeded)


def test_a_recompile_reproduces_the_amplitude_and_the_coordinates():
    """Writing back and re-collecting is the identity, so A is never doubled."""
    statement = small_statement()
    mode = statement.phase.distortion_modes[0]
    seeded = seed_distortion_amplitudes(statement.phase, {mode.name: 0.07})
    structure = Structure(phases=[seeded])
    ins = instrument()
    table = ParameterTable(structure, ins)
    table.apply_to_models(structure, ins)
    again = ParameterTable(structure, ins)
    path = "phases.0.distortion_modes.0.amplitude"
    values = {e.path: e.value for e in again.entries}
    assert values[path] == pytest.approx(0.07, abs=1e-15)
    for j, vector in enumerate(mode.vectors):
        for c, name in zip(vector, ("x", "y", "z"), strict=True):
            want = getattr(statement.phase.atoms[j], name).value + 0.07 * c
            assert values[f"phases.0.atoms.{j}.{name}"] == pytest.approx(
                want, abs=1e-12)


# -------------------------------------------------------------- the refusals
def test_the_child_cell_is_held_and_locked(recwarn):
    """(c) every cell row is vary=False, locked, and a glob cannot free it."""
    statement = small_statement()
    for name in ("a", "b", "c", "alpha", "beta", "gamma"):
        assert not getattr(statement.phase.cell, name).vary
    table = ParameterTable(Structure(phases=[statement.phase]), instrument())
    cell_rows = [e for e in table.entries if ".cell." in e.path]
    assert len(cell_rows) == 6
    assert all(e.locked for e in cell_rows), (
        "a mode-carrying phase's cell rows must be locked, not merely unfree")
    assert table.set_vary(["phases.*.cell.*"], True) == []


def test_declaring_a_free_child_cell_is_refused_by_name():
    """(c) the loud half: a declared ``vary=True`` is a claim, not a sweep."""
    statement = small_statement()
    phase = statement.phase.model_dump()
    phase["cell"]["beta"]["vary"] = True
    with pytest.raises(ValueError, match="non-linear functions of the parent"):
        Phase.model_validate(phase)


def test_freeing_every_amplitude_from_the_undistorted_child_is_refused():
    """The origin is a stationary point for the whole amplitude vector."""
    statement = small_statement()
    table = ParameterTable(Structure(phases=[statement.phase]), instrument())
    with pytest.raises(ValueError, match="even function of the whole"):
        table.set_vary([AMPLITUDE_GLOB], True)


def test_one_seeded_amplitude_lets_the_others_be_freed():
    """…and the same check must not refuse the fit the round trip runs.

    With one mode displaced, the other columns are first order in the cross
    term with it, so they are live — which is what makes an eight-amplitude
    fit against a one-amplitude truth a usable negative control.
    """
    statement = small_statement()
    mode = statement.phase.distortion_modes[0]
    seeded = seed_distortion_amplitudes(statement.phase, {mode.name: 0.03})
    table = ParameterTable(Structure(phases=[seeded]), instrument())
    freed = table.set_vary([AMPLITUDE_GLOB], True)
    assert len(freed) == len(statement.phase.distortion_modes)


def test_an_amplitude_free_beside_the_coordinates_it_moves_is_refused():
    """Exactly degenerate, not merely correlated: a rank-deficient Jacobian."""
    statement = small_statement()
    mode = statement.phase.distortion_modes[0]
    seeded = seed_distortion_amplitudes(statement.phase, {mode.name: 0.03})
    table = ParameterTable(Structure(phases=[seeded]), instrument())
    moved = [j for j, v in enumerate(mode.vectors) if any(v)]
    with pytest.raises(ValueError, match="exactly degenerate"):
        table.set_vary([f"phases.0.atoms.{j}.dof.*" for j in moved]
                       + ["phases.0.distortion_modes.0.amplitude"], True)


def test_a_mode_vector_outside_the_sites_allowed_subspace_is_refused():
    """The frozen orbit the structure factor sums over would be the wrong one."""
    statement = small_statement()
    modes = [m.model_dump() for m in statement.phase.distortion_modes]
    # the child atoms sit on a mirror, so a y-component is forbidden there
    vectors = [list(v) for v in modes[0]["vectors"]]
    vectors[0] = [vectors[0][0], 0.3, vectors[0][2]]
    modes[0]["vectors"] = vectors
    phase = Phase.model_validate({**statement.phase.model_dump(),
                                  "distortion_modes": modes})
    with pytest.raises(ValueError, match="site symmetry does not allow"):
        ParameterTable(Structure(phases=[phase]), instrument())


# ------------------------------------------------------------- the builder
def test_the_statement_ties_every_child_biso_to_its_parent_site():
    """(d) 28-free-Biso is how a child manufactures superstructure intensity."""
    statement = small_statement()
    n_atoms = len(statement.phase.atoms)
    n_parent = len(parent_phase().atoms)
    assert len(statement.biso_ties) == n_atoms - n_parent
    targets = {t for t, _s, _sc, _o in statement.biso_ties}
    sources = {s for _t, s, _sc, _o in statement.biso_ties}
    assert not targets & sources, "a tie target must not also be a source"
    assert all(sc == 1.0 and off == 0.0
               for _t, _s, sc, off in statement.biso_ties)
    # and the ties are applicable: every path exists in the table
    table = ParameterTable(Structure(phases=[statement.phase]), instrument())
    paths = {e.path for e in table.entries}
    assert targets | sources <= paths


def test_a_direction_one_orbit_does_not_carry_is_refused_by_name():
    """(f) with the directions that orbit does carry quoted beside it.

    The case is a parent with a 4c site and a site on the **inversion
    centre** (4a) at k = (½,0,½): the 4c orbits carry all four S directions
    and the 4a orbit carries only S1(a,b) and S3(a,b) — measured, and it is
    the physics rather than an accident, since a polar vector cannot survive
    a stabiliser containing −1 unless the irrep supplies the sign.  A mode
    the site's representation does not contain does not exist, and giving
    that orbit a zero field would state a rigid sublattice nobody claimed.
    """
    parent = parent_phase().model_copy(update={"atoms": [
        Atom(label="Ti", species="Ti", x=Parameter(value=0.1),
             y=Parameter(value=0.25), z=Parameter(value=0.3),
             biso=Parameter(value=0.6)),
        Atom(label="Zn", species="Zn", x=Parameter(value=0.0),
             y=Parameter(value=0.0), z=Parameter(value=0.0),
             biso=Parameter(value=0.5))]})
    with pytest.raises(ValueError) as excinfo:
        displacive_statement(parent, ("1/2", "0", "1/2"), irrep="S2",
                             direction="(a,b)")
    message = str(excinfo.value)
    assert "not carried by every orbit" in message
    assert "Zn" in message and "What it does carry" in message
    assert "S1(a,b)" in message and "S3(a,b)" in message


def test_naming_half_an_order_parameter_is_refused():
    with pytest.raises(ValueError, match="name both irrep= and direction="):
        displacive_statement(parent_phase(), SMALL_K, irrep="S2")


def test_an_asserted_child_group_is_checked_not_used():
    with pytest.raises(ValueError, match="not the 'P 2/m' the call asserted"):
        displacive_statement(parent_phase(), SMALL_K, irrep=SMALL_IRREP,
                             direction=SMALL_DIRECTION, child_group="P 2/m")
    statement = displacive_statement(
        parent_phase(), SMALL_K, irrep=SMALL_IRREP, direction=SMALL_DIRECTION,
        child_group="P 1 21/m 1")
    assert statement.child_space_group == "P 1 21/m 1"


def test_unit_amplitude_moves_the_furthest_atom_by_one_angstrom():
    """The convention that makes the amplitude an ångström."""
    statement = small_statement()
    for mode in statement.phase.distortion_modes:
        assert mode.unit_displacement_a(statement.phase.cell) == pytest.approx(
            1.0, abs=1e-9), mode.name


def test_the_parent_of_a_statement_may_not_already_carry_modes():
    statement = small_statement()
    with pytest.raises(ValueError, match="pass the parent phase, not a child"):
        displacive_statement(statement.phase, SMALL_K, irrep=SMALL_IRREP,
                             direction=SMALL_DIRECTION)


def test_seeding_an_unknown_mode_is_refused_rather_than_ignored():
    statement = small_statement()
    with pytest.raises(ValueError, match="no distortion mode named"):
        seed_distortion_amplitudes(statement.phase, {"not-a-mode": 0.05})


# ------------------------------------------------- the synthetic round trip (b)
@pytest.fixture(scope="module")
def one_mode_truth():
    """A pattern from a child with exactly one amplitude at 0.12 Å."""
    statement = small_statement()
    name = statement.phase.distortion_modes[0].name
    truth = seed_distortion_amplitudes(statement.phase, {name: 0.12},
                                       vary=False)
    return statement, name, 0.12, simulate(truth, 11)


def test_a_known_amplitude_is_recovered_from_a_cold_start(one_mode_truth):
    """(b) eight amplitudes free, one true: the positive and negative arms.

    Cold in the sense that matters — the amplitude starts at a quarter of its
    true value and nothing else about the mode is told to the fit — and every
    amplitude of the direction is freed, so the seven that are truly zero are
    the control: they must come back **unsupported**, not small.
    """
    statement, name, true_a, data = one_mode_truth
    start = seed_distortion_amplitudes(statement.phase, {name: 0.03},
                                       vary=True)
    ref = Refinement(Structure(phases=[start]), instrument())
    for target, source, scale, offset in statement.biso_ties:
        ref.tie(target, source, scale=scale, offset=offset)
    free = ["phases.*.scale", "instrument.background.c*", AMPLITUDE_GLOB]
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"],
                 max_iter=200),
        rx.Stage("all", free, max_iter=400)]))

    assert result.status == "converged"
    row = result.parameter("phases.0.distortion_modes.0.amplitude")
    assert row.stderr is not None and row.stderr > 0.0
    assert abs(abs(row.value) - true_a) <= 2.0 * row.stderr, (
        f"|A| = {abs(row.value):.5f} ± {row.stderr:.5f} against a true "
        f"{true_a}: {abs(abs(row.value) - true_a) / row.stderr:.2f}σ away")

    report = ref.report()
    assert len(report.distortion) == len(statement.phase.distortion_modes)
    supported = [e for e in report.distortion if e.supported]
    assert [e.mode for e in supported] == [name], (
        "exactly the one true mode must be supported; got "
        f"{[e.mode for e in supported]}")
    row0 = report.distortion[0]
    assert row0.max_displacement_a == pytest.approx(1.0, abs=1e-9)
    assert row0.displacement_a == pytest.approx(abs(row0.amplitude), abs=1e-9)
    assert row0.k == list(SMALL_K)
    assert row0.irrep_label == SMALL_IRREP


def test_the_diagnostic_is_silent_when_the_order_parameter_is_supported(
        one_mode_truth):
    """Seven of eight amplitudes are truly zero, and nothing fires (M-3).

    **This test changed meaning at M-3 and the change is the point.**  It used
    to assert the opposite — that the seven modes at zero each raised
    ``DISTORTION_MODE_UNSUPPORTED``, and only the eighth did not.  That reading
    is basis-dependent: an irrep fixes its modes only up to an orthogonal basis
    of the direction, so which components carry the order parameter is a
    property of the orthogonalisation and not of the data.  Rotating this basis
    would spread one supported amplitude over all eight and silence every
    warning without touching the structure.  The gate is now
    A_τ = (Σ_m A²_{τ,m})^½ (Perez-Mato, Orobengoa & Aroyo 2010 eq 6–7), which
    that rotation leaves alone, and the order parameter *is* supported here —
    so the honest number of warnings is zero.

    The per-mode reading is kept on ``FitReport.distortion`` as information,
    and the test below still checks it says what it always said.
    """
    statement, name, _true, data = one_mode_truth
    start = seed_distortion_amplitudes(statement.phase, {name: 0.03},
                                       vary=True)
    ref = Refinement(Structure(phases=[start]), instrument())
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"],
                 max_iter=200),
        rx.Stage("all", ["phases.*.scale", "instrument.background.c*",
                         AMPLITUDE_GLOB], max_iter=400)]))
    fired = [d for d in result.diagnostics
             if d.code == "DISTORTION_MODE_UNSUPPORTED"]
    assert not fired, (
        "the order parameter is supported, so nothing should fire: "
        f"{[d.message for d in fired]}")

    total, = result.distortion_totals
    assert total.n_modes == len(statement.phase.distortion_modes)
    assert total.supported and total.amplitude_esd is not None
    assert total.amplitude > 2.0 * total.amplitude_esd
    # the per-mode rows are still there, and still basis-dependent
    report = ref.report()
    assert len(report.distortion) == total.n_modes
    assert sum(1 for e in report.distortion if e.supported) == 1
    # the unit direction points essentially all the way along the true mode
    assert abs(total.unit_direction[0]) > 0.99


def test_a_held_amplitude_never_raises_the_diagnostic(one_mode_truth):
    """A statement the caller made is not a measurement to warn about."""
    statement, name, _true, data = one_mode_truth
    start = seed_distortion_amplitudes(statement.phase, {name: 0.001},
                                       vary=False)
    ref = Refinement(Structure(phases=[start]), instrument())
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"],
                 max_iter=200)]))
    assert not [d for d in result.diagnostics
                if d.code == "DISTORTION_MODE_UNSUPPORTED"]


def test_the_evidence_says_so_when_no_esd_was_measured():
    statement = small_statement()
    rows = analyse_distortion_modes(Structure(phases=[statement.phase]))
    assert len(rows) == len(statement.phase.distortion_modes)
    assert all(r.supported and "no esd was measured" in r.note for r in rows)


# --------------------------------------------------------- the sequential arm (e)
def test_a_three_point_ramp_reports_a_supported_amplitude_only_where_there_is_one():
    """(e) A(T) across A = 0, 0.05, 0.1 — the trajectory and its verdicts."""
    statement = small_statement()
    name = statement.phase.distortion_modes[0].name
    truths = (0.0, 0.05, 0.1)
    patterns = [simulate(seed_distortion_amplitudes(
        statement.phase, {name: a}, vary=False) if a else statement.phase,
        20 + i) for i, a in enumerate(truths)]
    start = seed_distortion_amplitudes(statement.phase, {name: 0.02},
                                       vary=True)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"],
                 max_iter=200),
        rx.Stage("all", ["phases.*.scale", "instrument.background.c*",
                         "phases.0.distortion_modes.0.amplitude"],
                 max_iter=400)])
    series = rx.refine_sequential(
        patterns, Structure(phases=[start]), instrument(), plan=plan,
        x=[0.0, 1.0, 2.0], refit="single")

    # every *declared* mode is reported, free or not — the arm is about a
    # hypothesis that was stated, so the seven held ones appear with no esd
    assert series.distortion_modes() == [
        f"phases.0.distortion_modes.{n}.amplitude"
        for n in range(len(statement.phase.distortion_modes))]
    traj = series.distortion_trajectory(name)
    assert traj.mode == name and traj.irrep_label == SMALL_IRREP
    assert len(traj.magnitude) == 3
    assert traj.supported == [False, True, True], (
        f"support verdicts {traj.supported} against truths {truths}")
    # the esd is withheld exactly where the point is unsupported
    assert traj.stderr[0] is None
    assert all(sd is not None for sd in traj.stderr[1:])
    for i, want in enumerate(truths[1:], start=1):
        assert abs(traj.magnitude[i] - want) <= 3.0 * traj.stderr[i], (
            f"point {i}: |A| = {traj.magnitude[i]:.5f} ± "
            f"{traj.stderr[i]:.5f} against a true {want}")
    assert traj.magnitude[1] < traj.magnitude[2], "A(T) must be monotone here"
    assert "UNSUPPORTED" in str(traj) and "supported" in str(traj)


# ------------------------------------------------- the Ba2FeSbSe5 orbits (g)
#: Ba₂FeSbSe₅'s Pnma asymmetric unit is one general 8d site and six 4c mirror
#: sites (Maier, Gaultois *et al.*, *Phys. Rev. B* **103**, 054115, 2021).
#: The **representative coordinates below, and the nominal cell the statement
#: test uses, are generic members of those two Wyckoff classes and not the
#: published or fitted ones**, and that is sound rather than a dodge: ``candidates`` reads the site only through its stabiliser and its
#: orbit, so the candidate set, the isotropy subgroups and the free-amplitude
#: counts are functions of the Wyckoff class alone — measured, two different
#: 8d sites and two different 4c sites give identical answers, and both agree
#: with the fitted structure's own.
_BA2FESBSE5_ORBITS = (
    ("Ba1", (0.13, 0.04, 0.31)),       # 8d, general
    ("Sb1", (0.06, 0.25, 0.09)),       # 4c, on m
    ("Se1", (0.88, 0.91, 0.22)),       # 8d, general
    ("Se2", (0.41, 0.75, 0.48)),       # 4c
    ("Se3", (0.19, 0.25, 0.17)),       # 4c
    ("Se4", (0.34, 0.25, 0.57)),       # 4c
    ("Fe1", (0.44, 0.25, 0.72)),       # 4c
)


def test_the_ba2fesbse5_orbits_enumerate_a_common_p21m_direction():
    """(g) verified displacive candidates at k = (½,0,½), P2₁/m in 2a,b,a+c.

    The claim the superstructure trial rests on: every orbit of the Pnma
    parent carries the same four order-parameter directions at this k, one of
    them has the isotropy subgroup that is the nuclear part of the magnetic
    group the same k orders in, and ``verify=True`` passes — the isotropy
    subgroup and the mode vectors agree about the allowed subspace, under the
    **polar** action a displacement takes.
    """
    from rietx.crystallography.magnetic.supercell import child_basis

    k = ("1/2", "0", "1/2")
    per_site = {}
    for label, site in _BA2FESBSE5_ORBITS:
        found = candidates("P n m a", site, k, kind="displacive", verify=True)
        per_site[label] = {c.label: c for c in found}
        assert all(c.in_allowed_span() for c in found), label

    common = set.intersection(*(set(v) for v in per_site.values()))
    assert common == {"S1(a,b)", "S2(a,b)", "S3(a,b)", "S4(a,b)"}

    # 11.51 is P2₁/m1′ — the grey group whose colourless part is P2₁/m, which
    # is what a displacive order parameter's isotropy subgroup is (time
    # reversal is a symmetry of a displacement pattern)
    p21m = [name for name in common
            if all(per_site[label][name].bns_number == "11.51"
                   for label, _site in _BA2FESBSE5_ORBITS)]
    assert p21m == ["S2(a,b)"]

    basis = child_basis("P n m a", candidates(
        "P n m a", _BA2FESBSE5_ORBITS[-1][1], k, kind="displacive",
        verify=False).k)
    assert [[str(v) for v in row] for row in basis] == [
        ["2", "0", "1"], ["0", "1", "0"], ["0", "0", "1"]], (
        "the child cell of this k must be 2a, b, a+c")

    # the free-amplitude count is the mode basis of the direction, per orbit:
    # six on a general site, four on a 4c one for S2
    counts = {label: per_site[label]["S2(a,b)"].free_amplitudes
              for label, _site in _BA2FESBSE5_ORBITS}
    assert counts == {"Ba1": 6, "Sb1": 4, "Se1": 6, "Se2": 4, "Se3": 4,
                      "Se4": 4, "Fe1": 4}


def test_the_ba2fesbse5_statement_carries_one_mode_per_free_amplitude():
    """…and the statement built from it: 28 child atoms, 32 modes, 21 ties."""
    cell = Cell(a=Parameter(value=12.6), b=Parameter(value=9.1),
                c=Parameter(value=9.15), alpha=Parameter(value=90.0),
                beta=Parameter(value=90.0), gamma=Parameter(value=90.0))
    species = {"Ba1": "Ba", "Sb1": "Sb", "Se1": "Se", "Se2": "Se",
               "Se3": "Se", "Se4": "Se", "Fe1": "Fe"}
    parent = Phase(
        name="Ba2FeSbSe5-like", space_group="P n m a", cell=cell,
        atoms=[Atom(label=label, species=species[label],
                    x=Parameter(value=site[0]), y=Parameter(value=site[1]),
                    z=Parameter(value=site[2]), biso=Parameter(value=1.0))
               for label, site in _BA2FESBSE5_ORBITS])
    statement = displacive_statement(parent, ("1/2", "0", "1/2"),
                                     irrep="S2", direction="(a,b)")
    assert statement.child_space_group == "P 1 21/m 1"
    assert statement.transform == "2a,b,a+c;0,0,0"
    assert statement.index == 2
    assert len(statement.phase.atoms) == 28
    assert len(statement.phase.distortion_modes) == 32
    assert len(statement.biso_ties) == 28 - 7
    assert {label: len(names)
            for label, names in statement.modes_by_site.items()} == {
        "Ba1": 6, "Sb1": 4, "Se1": 6, "Se2": 4, "Se3": 4, "Se4": 4, "Fe1": 4}
    # every mode moves only the child atoms of its own parent orbit
    for mode in statement.phase.distortion_modes:
        moved = {statement.site_map[j][0]
                 for j, v in enumerate(mode.vectors) if any(v)}
        assert len(moved) == 1, mode.name
        assert statement.phase.atoms[
            min(j for j, v in enumerate(mode.vectors) if any(v))
        ].label.startswith(mode.parent_site)
