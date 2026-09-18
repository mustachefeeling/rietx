"""The amplitude is absolute, and A = 0 needs a seed (M-3, WP-1419 § Inherited).

Two of the maintainer's five findings meet here, and they are the same fact
seen from two sides.

**Absolute.**  A mode amplitude is a *reported* quantity that a sequential run
warm-starts, so it cannot be a displacement from the stored coordinate the way
a Wyckoff DOF is: a DOF is rebuilt from the coordinates it wrote and returns to
zero at every table build, while an amplitude keeps its value, and a quantity
that both keeps its value and is re-applied at every write-through verb walks
the structure.  Measured on ``main`` with a user variable driving a coordinate
DOF: z ran 0.26 → 0.27 → 0.28 → 0.29 → 0.30 over four unrelated ``set_values``
calls with the variable fixed at 0.01, an antiphase pair seeded at 0.005 ended
at +0.02251 and −0.01751, and a second ``fit()`` on the same ``Refinement``
reported A = 0.0 with the structure still carrying the distortion.  The four
tests in § absolute are those four states, on this package's own mechanism
(``params.vector._collect_distortion_modes``, whose base coordinate is
``atom.x − Σ A⁰ e`` with A⁰ the incoming amplitude), and they pass because the
base is *recomputed from the incoming amplitude at every collect* rather than
stored.

**The seed.**  The lost parent translation carries the mode field to its
negative, so the pattern is an even function of the whole amplitude vector and
its gradient at the origin vanishes for every mode at once: A = 0 is a local
*maximum* of fit quality along every mode, not a starting point.  § the seed
rule measures that on this toy — χ²(A) even to 2.3e-15, dχ²/du = 0.0 at u = 0
against −1.61e7 at u = 0.005 — and then exercises ``Stage.distortion_seed``,
the amplitude's counterpart of ``Stage.strain_seed``.

The toy is the maintainer's: a P1 child, a = b = 4 Å, c = 8 Å, an antiphase Sr
pair at z = ¼ and ¾ with two O on parent-symmetric sites, λ = 1.5406 Å,
10–90° 2θ at 0.02°, Poisson noise, and a planted amplitude of 0.16 Å along c
(u = 0.02 in fractional units, the number his measurement quotes).

References: Perez-Mato, J. M., Orobengoa, D. & Aroyo, M. I. (2010),
*Acta Cryst.* A**66**, 558, § 7 (the lost translation and the domain sign);
Campbell, B. J., Stokes, H. T., Tanner, D. E. & Hatch, D. M. (2006),
*J. Appl. Cryst.* **39**, 607 (parent + irrep + direction → structure).
"""

import numpy as np
import pytest

import rietx as rx
from rietx import DistortionMode, Instrument, PatternData, Refinement
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, Phase, Structure

WAVELENGTH = 1.5406
A_A = 4.0
C_A = 8.0
#: the planted amplitude in Å; 0.16 Å along c = 8 Å is u = 0.02 fractional,
#: which is the unit the maintainer's measurement quotes
PLANTED_A = 0.16
TWO_THETA = np.arange(10.0, 90.0, 0.02)
AMPLITUDE_GLOB = "phases.*.distortion_modes.*.amplitude"


def _antiphase(axis: int):
    """(+e, −e) along ``axis``, normalised to 1 Å per unit amplitude."""
    step = 1.0 / (C_A if axis == 2 else A_A)
    plus = tuple(step if i == axis else 0.0 for i in range(3))
    return plus, tuple(-c for c in plus)


def toy_phase(amplitude=0.0, *, vary=False, extra_mode=False, name="toy"):
    """The maintainer's toy child, with one (or two) hand-built modes.

    Hand-built rather than through ``displacive_statement`` on purpose: the
    claim under test is about the *engine hook*, and a P1 child with a mode
    written down by hand isolates it from the isotropy machinery that would
    otherwise be on trial at the same time.
    """
    plus, minus = _antiphase(2)
    vectors = [plus, minus, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
    modes = [DistortionMode(
        name="X-Sr-z", irrep_label="X", direction="(a)", k=("0", "0", "1/2"),
        parent_site="Sr", vectors=vectors,
        amplitude=Parameter(value=float(amplitude), vary=bool(vary),
                            min=-0.5, max=0.5, unit="A"))]
    shift = np.asarray(vectors, dtype=np.float64) * float(amplitude)
    if extra_mode:
        xplus, xminus = _antiphase(0)
        xvectors = [xplus, xminus, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
        modes.append(DistortionMode(
            name="X-Sr-x", irrep_label="X", direction="(a)",
            k=("0", "0", "1/2"), parent_site="Sr", vectors=xvectors,
            amplitude=Parameter(value=float(amplitude), vary=bool(vary),
                                min=-0.5, max=0.5, unit="A")))
        shift = shift + np.asarray(xvectors, dtype=np.float64) * float(amplitude)
    base = [(0.0, 0.0, 0.25), (0.0, 0.0, 0.75),
            (0.5, 0.5, 0.0), (0.5, 0.5, 0.5)]
    labels = (("Sr1", "Sr"), ("Sr2", "Sr"), ("O1", "O"), ("O2", "O"))
    atoms = [
        Atom(label=lab, species=sp,
             x=Parameter(value=base[j][0] + shift[j][0]),
             y=Parameter(value=base[j][1] + shift[j][1]),
             z=Parameter(value=base[j][2] + shift[j][2]),
             biso=Parameter(value=0.5 if sp == "Sr" else 0.7))
        for j, (lab, sp) in enumerate(labels)]
    return Phase(
        name=name, space_group="P 1",
        cell=Cell(a=Parameter(value=A_A), b=Parameter(value=A_A),
                  c=Parameter(value=C_A), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=atoms, scale=Parameter(value=0.02), distortion_modes=modes)


def instrument() -> Instrument:
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.profile.w.value = 0.004
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=30.0), Parameter(value=-4.0)])
    return ins


def simulate(phase: Phase, seed: int = 17) -> PatternData:
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


@pytest.fixture(scope="module")
def planted_pattern():
    """A pattern from the toy with A = 0.16 Å (u = 0.02)."""
    return simulate(toy_phase(PLANTED_A), seed=17)


def _coords(phase):
    return np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])


def _pair_shift(phase):
    """(Sr1 z − ¼, Sr2 z − ¾): the antiphase pair's two displacements."""
    return (phase.atoms[0].z.value - 0.25, phase.atoms[1].z.value - 0.75)


# ------------------------------------------------------------------ absolute
def test_unrelated_writes_do_not_walk_the_coordinates():
    """(a) four ``set_values`` on the scale; the structure must not move.

    The failure this pins is the one measured on ``main`` for a *variable*
    driving a coordinate DOF: the DOF is a displacement from the stored
    coordinate, so re-applying a held driver at every write-through verb walked
    z by one full amplitude per call (0.26 → 0.30 over four).  An amplitude
    re-anchors on ``atom.x − Σ A⁰ e`` at every collect instead, so four writes
    reproduce the coordinates bit-for-bit.
    """
    phase = toy_phase(0.01)
    ref = Refinement(Structure(phases=[phase]), instrument())
    before = _coords(ref.structure.phases[0])
    for scale in (0.021, 0.022, 0.023, 0.024):
        ref.set_values({"phases.0.scale": scale})
    after = _coords(ref.structure.phases[0])
    assert np.array_equal(before, after), (
        f"four unrelated writes moved the structure by "
        f"{np.abs(after - before).max():.3e} (fractional); the amplitude is "
        f"being applied once per write instead of being absolute")
    amplitude = ref.structure.phases[0].distortion_modes[0].amplitude.value
    assert amplitude == 0.01


def test_two_modes_keep_the_antiphase_pair_antiphase():
    """(b) seeded at 0.005 with two modes declared in order.

    The maintainer's variable-driven arm ended at +0.02251 and −0.01751 — an
    asymmetry of exactly one seed — because the base each atom was measured
    from had already absorbed part of the mode.  Here the two displacements
    must be exact negatives of each other, and each exactly the amplitude
    times the mode vector.
    """
    seed = 0.005
    phase = toy_phase(seed, extra_mode=True)
    structure = Structure(phases=[phase])
    table = ParameterTable(structure, instrument())
    values = table.decode(table.x0())
    z1 = values["phases.0.atoms.0.z"] - 0.25
    z2 = values["phases.0.atoms.1.z"] - 0.75
    x1 = values["phases.0.atoms.0.x"]
    x2 = values["phases.0.atoms.1.x"]
    assert z1 == pytest.approx(seed / C_A, abs=1e-15)
    assert z2 == pytest.approx(-seed / C_A, abs=1e-15)
    assert z1 == pytest.approx(-z2, abs=1e-15), (
        f"the antiphase pair is no longer antiphase: {z1:+.6f} / {z2:+.6f}")
    assert x1 == pytest.approx(seed / A_A, abs=1e-15)
    assert x2 == pytest.approx(-seed / A_A, abs=1e-15)


def test_a_second_fit_reports_the_amplitude_the_first_one_did(planted_pattern):
    """(c) ``fit()`` twice on one ``Refinement``.

    The measured failure was A = 0.0 on the second call with the structure
    still carrying the distortion — the amplitude having been consumed into
    the coordinates by the first fit's write-back.  Here the second fit must
    start from, and report, the first fit's amplitude, and the structure must
    not have moved between the two.
    """
    start = toy_phase(0.08, vary=True)
    ref = Refinement(Structure(phases=[start]), instrument())
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"],
                 max_iter=100),
        rx.Stage("amplitude", ["phases.*.scale", AMPLITUDE_GLOB],
                 max_iter=200)])
    first = ref.fit(planted_pattern, plan=plan)
    a1 = first.parameter("phases.0.distortion_modes.0.amplitude").value
    coords1 = _coords(ref.fitted_structure.phases[0])
    assert abs(a1) > 0.05, f"the first fit did not find the distortion: {a1}"

    second = ref.fit(planted_pattern, plan=plan)
    a2 = second.parameter("phases.0.distortion_modes.0.amplitude").value
    coords2 = _coords(ref.fitted_structure.phases[0])
    assert a2 != 0.0
    assert a2 == pytest.approx(a1, rel=1e-6), (
        f"the second fit reports A = {a2:.6f} against the first's {a1:.6f}; "
        f"the amplitude is not absolute")
    assert np.abs(coords2 - coords1).max() < 1e-9, (
        f"the structure moved by {np.abs(coords2 - coords1).max():.3e} "
        f"between two fits that report the same amplitude")


def test_a_json_round_trip_mid_refinement_reproduces_a_and_the_coordinates(
        planted_pattern):
    """(d) ``model_dump(mode="json")`` → rebuild, mid-refinement.

    A stored structure is the *current* one, so the amplitude and the
    coordinates it has already moved both have to survive the trip — and the
    rebuilt table must recover the same base, or the mode would be applied a
    second time on top of coordinates that already carry it.
    """
    start = toy_phase(0.08, vary=True)
    ref = Refinement(Structure(phases=[start]), instrument())
    ref.fit(planted_pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("amplitude", ["phases.*.scale", AMPLITUDE_GLOB],
                 max_iter=200)]))
    fitted = ref.fitted_structure
    a_before = fitted.phases[0].distortion_modes[0].amplitude.value
    coords_before = _coords(fitted.phases[0])

    revived = Structure.model_validate(fitted.model_dump(mode="json"))
    a_after = revived.phases[0].distortion_modes[0].amplitude.value
    coords_after = _coords(revived.phases[0])
    assert a_after == pytest.approx(a_before, abs=0.0, rel=1e-12)
    assert np.abs(coords_after - coords_before).max() == 0.0

    # and the rebuilt table reproduces the structure exactly: a recompile is a
    # fixed point, so the mode is never applied twice
    table = ParameterTable(revived, instrument())
    values = table.decode(table.x0())
    for j in range(len(revived.phases[0].atoms)):
        for c_idx, c in enumerate("xyz"):
            assert values[f"phases.0.atoms.{j}.{c}"] == pytest.approx(
                coords_before[j][c_idx], abs=1e-14)
    assert values["phases.0.distortion_modes.0.amplitude"] == pytest.approx(
        a_before, abs=0.0, rel=1e-12)


def test_the_predicted_pattern_survives_a_round_trip_bit_for_bit(planted_pattern):
    """The same round trip read on the observable rather than on the numbers."""
    phase = toy_phase(0.06)
    structure = Structure(phases=[phase])
    ins = instrument()
    model = compile_model(structure, ins, planted_pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    y_before = model.evaluate(table.decode(table.x0()))

    revived = Structure.model_validate(structure.model_dump(mode="json"))
    model2 = compile_model(revived, ins, planted_pattern, mode="rietveld")
    table2 = ParameterTable(revived, ins)
    y_after = model2.evaluate(table2.decode(table2.x0()))
    assert np.array_equal(y_before, y_after)


# ------------------------------------------------------------- the seed rule
def _chi2(amplitude, data):
    """χ² of the toy at ``amplitude``, everything else at its declared value."""
    structure = Structure(phases=[toy_phase(0.0)])
    ins = instrument()
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    table.entries[table._paths[
        "phases.0.distortion_modes.0.amplitude"]].value = float(amplitude)
    table._rebuild()
    y = model.evaluate(table.decode(table.x0()))
    yobs = np.asarray(data.intensity, dtype=float)
    w = 1.0 / np.maximum(yobs, 1.0)
    return float(np.sum(w * (yobs - y) ** 2))


def test_chi2_is_even_in_the_amplitude(planted_pattern):
    """The reason A = 0 is a stationary point, measured rather than asserted.

    The parent translation the k-doubling lost carries e_ν to −e_ν, so the
    child at −A *is* the child at +A seen in its other antiphase domain and the
    two predict the identical pattern.  χ²(A) = χ²(−A) to roundoff is that
    statement on the observable.
    """
    worst = 0.0
    for a in (0.005, 0.02, 0.04, 0.08, 0.16, 0.32):
        plus, minus = _chi2(a, planted_pattern), _chi2(-a, planted_pattern)
        worst = max(worst, abs(plus - minus) / max(abs(plus), 1.0))
    assert worst < 1e-12, f"χ²(A) is not even in A: worst residual {worst:.3e}"


def test_the_gradient_vanishes_at_the_parent_and_does_not_at_the_seed(
        planted_pattern):
    """dχ²/dA is zero at A = 0 and −1.6e7 (in Yue's u) a fifth of a seed out.

    The finding this whole item exists for.  Quoted in both units: dχ²/dA in
    the amplitude's own ångströms, and dχ²/du in the fractional shift along c
    the review's measurement used, so the two numbers can be compared.
    """
    def d_chi2_d_a(a0, h):
        return ((_chi2(a0 + h, planted_pattern) - _chi2(a0 - h, planted_pattern))
                / (2 * h))

    at_zero = d_chi2_d_a(0.0, 1e-3)
    at_seed = d_chi2_d_a(0.005 * C_A, 1e-3)
    assert at_zero == 0.0 or abs(at_zero) < 1e-6 * abs(at_seed), (
        f"dχ²/dA at the parent is {at_zero:.3e} against {at_seed:.3e} at "
        f"u = 0.005; the origin is supposed to be a stationary point")
    assert at_seed * C_A < -1e6, (
        f"dχ²/du at u = 0.005 is {at_seed * C_A:.3e}, which is not the steep "
        f"descent the seed exists to reach")


def test_the_softplus_seed_cannot_reach_an_amplitude():
    """Why ``Stage.seed`` does not serve, as a measurement rather than a claim.

    Two independent reasons, and this pins both: ``seed_softplus`` touches
    ``transform == "softplus"`` entries only, and an amplitude is
    identity-transform *because it is signed* — a softplus map cannot represent
    a negative amplitude at all, and the sign is a domain label the
    parameterisation has to be able to carry.
    """
    structure = Structure(phases=[toy_phase(0.0)])
    table = ParameterTable(structure, instrument())
    path = "phases.0.distortion_modes.0.amplitude"
    entry = table.entries[table._paths[path]]
    assert entry.transform == "identity"
    assert entry.lo < 0.0 < entry.hi, (
        "an amplitude's box straddles zero, which is what a softplus "
        "reparameterisation cannot express")
    assert table.seed_softplus([path], 0.02) == []
    assert entry.value == 0.0
    # and the Stephens seed is keyed on '.microstrain.dof.', so it misses too
    assert table.seed_stephens([path], 500.0) == []
    assert entry.value == 0.0


def test_the_seed_moves_the_coordinates_with_the_amplitude():
    """A seed that left the structure where it was would be a number that lies.

    The dual of ``seed_distortion_amplitudes``' docstring: on a *phase* the
    atoms must be moved by hand, because the table re-derives the base from
    them; in the *table* the coordinate rows are affine in the amplitude and
    already anchored, so setting the entry is the whole of it.
    """
    structure = Structure(phases=[toy_phase(0.0)])
    table = ParameterTable(structure, instrument())
    before = table.decode(table.x0())
    seeded = table.seed_distortion([AMPLITUDE_GLOB], 0.02)
    assert seeded == ["phases.0.distortion_modes.0.amplitude"]
    after = table.decode(table.x0())
    assert after["phases.0.atoms.0.z"] - before["phases.0.atoms.0.z"] == \
        pytest.approx(0.02 / C_A, abs=1e-15)
    assert after["phases.0.atoms.1.z"] - before["phases.0.atoms.1.z"] == \
        pytest.approx(-0.02 / C_A, abs=1e-15)
    assert after["phases.0.atoms.2.z"] == before["phases.0.atoms.2.z"]


def test_the_seed_leaves_a_warm_started_block_alone():
    """``seed_stephens``' rule, for ``seed_stephens``' reason.

    The evenness is a property of the whole amplitude vector, so a block with
    one amplitude already off zero has a live gradient on all of them and the
    seed has nothing to fix.  Overwriting it would lose a refined number — the
    exact failure a sequential run warm-starting from the previous point would
    hit at every temperature.
    """
    structure = Structure(phases=[toy_phase(0.11, extra_mode=True)])
    table = ParameterTable(structure, instrument())
    assert table.seed_distortion([AMPLITUDE_GLOB], 0.02) == []
    assert table.entries[table._paths[
        "phases.0.distortion_modes.0.amplitude"]].value == 0.11


def test_a_seed_outside_the_amplitude_bounds_is_refused_by_name():
    structure = Structure(phases=[toy_phase(0.0)])
    table = ParameterTable(structure, instrument())
    with pytest.raises(ValueError, match="lies outside the bounds"):
        table.seed_distortion([AMPLITUDE_GLOB], 5.0)


def test_a_stage_that_starts_from_the_parent_finds_the_amplitude(
        planted_pattern):
    """The acceptance: a stage entered at A = 0 with the seed, from both signs.

    ``distortion_statement``'s default is A = 0 and held, which is the negative
    control a mode test needs — and it is also, without a seed rule, the one
    starting point a refinement cannot leave.  This is the case the review said
    the A = 0 control does not cover: the stage *starts* at the parent.
    """
    from rietx.strategy.staged import DISTORTION_SEED_A

    results = {}
    for seed in (DISTORTION_SEED_A, -DISTORTION_SEED_A):
        ref = Refinement(Structure(phases=[toy_phase(0.0)]), instrument())
        result = ref.fit(planted_pattern, plan=rx.RefinementPlan(stages=[
            rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"],
                     max_iter=100),
            rx.Stage("modes", ["phases.*.scale", AMPLITUDE_GLOB],
                     max_iter=400, distortion_seed=seed)]))
        assert result.status == "converged"
        row = result.parameter("phases.0.distortion_modes.0.amplitude")
        assert row.stderr is not None and row.stderr > 0.0
        assert abs(abs(row.value) - PLANTED_A) <= 2.0 * row.stderr, (
            f"seed {seed:+g}: |A| = {abs(row.value):.6f} ± {row.stderr:.6f} "
            f"against a planted {PLANTED_A}")
        assert np.sign(row.value) == np.sign(seed), (
            "the sign of the answer follows the seed's — it is a domain "
            "label, not a measurement")
        results[seed] = (abs(row.value), result.statistics.rwp)

    # the two domains are the same structure, so they agree to the solver's
    # own convergence and no further: measured 2e-9 relative on |A| and
    # fifteen significant digits on Rwp, which is the review's own figure
    (a_plus, rwp_plus), (a_minus, rwp_minus) = results.values()
    assert a_plus == pytest.approx(a_minus, rel=1e-7)
    assert rwp_plus == pytest.approx(rwp_minus, rel=1e-13), (
        f"the two domains must be indistinguishable: Rwp {rwp_plus!r} against "
        f"{rwp_minus!r}")


def test_the_same_stage_without_the_seed_is_refused_by_name(planted_pattern):
    """The negative arm: no seed, and the refusal says what to do.

    Not "stays at A = 0 and reports converged" — this package refuses the state
    outright, at the freeing, because a dead column handed to a glob is the
    failure WP-1073 force-fixes elsewhere.  The refusal is the finding, and the
    test is that it names the seed.
    """
    ref = Refinement(Structure(phases=[toy_phase(0.0)]), instrument())
    with pytest.raises(ValueError) as excinfo:
        ref.fit(planted_pattern, plan=rx.RefinementPlan(stages=[
            rx.Stage("modes", ["phases.*.scale", AMPLITUDE_GLOB],
                     max_iter=400)]))
    message = str(excinfo.value)
    assert "every mode of the phase is at exactly zero" in message
    assert "Stage(distortion_seed=" in message
    assert "seed_distortion_amplitudes" in message


def test_the_seed_survives_the_plan_and_history_round_trips():
    """A stage field that a serialized plan drops is the ``strain_seed`` bug.

    ``schemas/plan.py``'s module docstring records that exact loss — a mirror
    with no ``strain_seed`` silently round-tripped it to 0.0 — so a new stage
    field earns the same three-way check: the dataclass, its ``StageSpec``
    mirror, and the ``StageAction`` the history records.
    """
    from rietx.schemas.history import NodeAction
    from rietx.schemas.plan import StageSpec

    stage = rx.Stage("modes", ["phases.*.distortion_modes.*.amplitude"],
                     distortion_seed=-0.02)
    spec = StageSpec.from_stage(stage)
    assert spec.distortion_seed == -0.02
    assert spec.to_stage().distortion_seed == -0.02
    revived = StageSpec.model_validate_json(spec.model_dump_json())
    assert revived.distortion_seed == -0.02

    action = NodeAction(kind="stage", name="modes", turn_on=list(stage.turn_on),
                        distortion_seed=-0.02)
    assert "distortion_seed=-0.02" in action.api_call()
    assert NodeAction(kind="stage", name="modes").api_call().count(
        "distortion_seed") == 0
