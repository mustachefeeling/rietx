"""A moment through a series: the onset, the hold, the trajectory (WP-1329).

Everything here is **synthetic**.  The patterns are simulated from a structure
this file states, with a declared m(T) and a declared T_N, so the onset has a
right answer and a wrong one is a failure rather than a disagreement with a
tutorial.  The real-data arms — the Co₃O₄ quench series at 1.5 K and the
Cr₂WO₆ 4 K/150 K pair — are read-and-test only and live in the rung's report.

What a plausible wrong implementation would pass, and therefore what each
block below turns on:

* **the onset is read off the verdicts, never off the values.**  A warm-started
  chain produces a smooth |m| column *through* the transition, so a threshold
  on the numbers would locate wherever the chain relaxed.  The tests assert on
  ``supported``, and one of them puts a value above the transition that a
  value-threshold would accept;
* **a held point keeps its value and loses its esd.**  Not zero (no fit
  measured zero) and not a small number with a small bar (which is the one
  misreading this whole arm exists to prevent);
* **the ± is the pattern spacing.**  A bracket is not a fitted critical point,
  and the field that says so is asserted rather than described;
* **the bracket is refused when its supported side did not converge.**  The
  asymmetry is measured here in both directions: a descent to nothing does not
  terminate and must not invalidate anything, while an ascent out of the floor
  terminates at once, so only a *supported* verdict from a truncated fit is
  suspect;
* **the two chain directions are compared.**  The failure a single pass cannot
  see is a moment carried across the transition by one warm start and not the
  other, so the agreement is a property of the pair;
* **a non-magnetic series is untouched.**  No rows, no diagnostics, and no
  ``ParameterTable`` built to find that out.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.report.schemas import MOMENT_SUPPORT_SIGMA, MomentEvidence
from rietx.schemas.common import Parameter
from rietx.schemas.sequential import (
    MagneticTrajectory,
    SeriesEntry,
    SeriesResult,
    locate_onset,
)
from rietx.schemas.structure import (
    MOMENT_FLOOR_MU_B,
    Atom,
    Cell,
    Moment,
    Phase,
    Structure,
)
from rietx.sequential import _floor_unsupported_moments

OUT = Path(__file__).resolve().parent / "output"

#: MnF₂ — rutile-structured, uniaxial, and a real collinear antiferromagnet, so
#: the moment axis the site allows is the one a reader expects.  The cell and
#: the fluorine coordinate are the ones ``test_magnetic.py`` states; the BNS
#: number is its ``MNF2_BNS``, the type-IV group with the moment along c.
MNF2_CELL = (4.8734, 4.8734, 3.3099, 90.0, 90.0, 90.0)
MNF2_BNS = "136.499"
LAMBDA_CW = 2.4

#: The declared order parameter: |m|(T) = m₀(1 − T/T_N)^β below T_N and nothing
#: above it.  β = 0.35 is a three-dimensional Heisenberg-ish value and is here
#: only to make the ramp curve — **nothing in this rung fits it** (the
#: parametric form of m(T) is WP-1325's question and this WP's non-goal), so
#: no test below asserts on β.
M0_MU_B, T_N_K, BETA = 5.0, 67.0, 0.35

#: Coarse enough that the whole nine-pattern chain is a second or two, fine
#: enough that the magnetic lines are resolved at λ = 2.4 Å.
GRID = np.arange(12.0, 120.0, 0.2)


def _cell(a, b, c, alpha=90.0, beta=90.0, gamma=90.0) -> Cell:
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=alpha), beta=Parameter(value=beta),
                gamma=Parameter(value=gamma))


def _atom(label, species, xyz, *, moment=None, biso=0.4) -> Atom:
    x, y, z = xyz
    return Atom(label=label, species=species, x=Parameter(value=x),
                y=Parameter(value=y), z=Parameter(value=z),
                biso=Parameter(value=biso, unit="A^2"), moment=moment)


def mnf2(mz: float, *, vary: bool = True) -> Phase:
    """MnF₂ with a moment of ``mz`` μ_B along c."""
    return Phase(
        name="MnF2", space_group="P 42/m n m", cell=_cell(*MNF2_CELL),
        atoms=[_atom("Mn", "Mn", (0.0, 0.0, 0.0), biso=0.3,
                     moment=Moment.from_values((0.0, 0.0, mz), "Mn2+",
                                               vary=vary)),
               _atom("F", "F", (0.3050, 0.3050, 0.0))],
        magnetic_symmetry=MNF2_BNS)


def nuclear_mnf2() -> Phase:
    """The same phase with no moment block at all — the absence arm."""
    return Phase(
        name="MnF2", space_group="P 42/m n m", cell=_cell(*MNF2_CELL),
        atoms=[_atom("Mn", "Mn", (0.0, 0.0, 0.0), biso=0.3),
               _atom("F", "F", (0.3050, 0.3050, 0.0))])


def neutron():
    return rx.Instrument.constant_wavelength_neutron(LAMBDA_CW, fwhm_deg=0.4)


def moment_at(t_kelvin: float) -> float:
    """The declared |m|(T), exactly zero above T_N."""
    if t_kelvin >= T_N_K:
        return 0.0
    return M0_MU_B * (1.0 - t_kelvin / T_N_K) ** BETA


def simulate(mz: float, seed: int, *, scale: float = 200.0,
             background: float = 40.0) -> rx.PatternData:
    """A pattern from a stated moment, with the pattern's own Poisson noise.

    ``sigma`` is √counts rather than left to the default, because the whole
    arm turns on the *ratio* |m|/σ and a σ the caller did not state is a σ the
    test is not measuring against.
    """
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    # A moment block refuses to be free at exactly zero, so the paramagnetic
    # arm is simulated at the floor rather than at nothing: the two differ by
    # 1e-3 μ_B, whose |F_m|² is 1e-6 of a 1 μ_B one and is below the noise of
    # any pattern here by many orders.
    structure = Structure(phases=[mnf2(max(mz, MOMENT_FLOOR_MU_B))])
    instrument = neutron()
    blank = rx.PatternData(two_theta=GRID.tolist(),
                           intensity=np.ones_like(GRID).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())
    values["phases.0.scale"] = scale
    clean = np.asarray(model.evaluate(values), dtype=np.float64) + background
    counts = np.random.default_rng(seed).poisson(
        np.clip(clean, 1e-6, None)).astype(float)
    return rx.PatternData(two_theta=GRID.tolist(), intensity=counts.tolist(),
                          sigma=np.sqrt(np.clip(counts, 1.0, None)).tolist())


def moment_plan(max_iter: int = 100) -> rx.RefinementPlan:
    """Scale and background, then the moment beside them."""
    return rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"],
                 max_iter=max_iter),
        rx.Stage("moment", ["phases.*.atoms.*.moment.dof*", "phases.*.scale",
                            "instrument.background.c*"], max_iter=max_iter)])


#: The ramp's temperatures.  60 K and 75 K straddle T_N = 67 K, so the bracket
#: the chain should find is 60 → 75, i.e. 67.5 ± 7.5 — which contains the
#: declared T_N, and could not be tighter with these patterns however good each
#: fit is.  That is the point the ± exists to make.
RAMP_T = [15.0, 35.0, 55.0, 60.0, 75.0, 95.0]
RAMP_BRACKET = (60.0, 75.0)


def _row(path="phases.0.atoms.0.moment.dof0", *, magnitude, esd, supported,
         atom="Mn") -> MomentEvidence:
    return MomentEvidence(phase="MnF2", atom=atom, ion="Mn2+", path=path,
                          magnitude=magnitude, magnitude_esd=esd,
                          crystalaxis=[0.0, 0.0, magnitude],
                          approximation="dipole, <j0> only (g = 2)",
                          supported=supported)


def _hand_built(points, *, statuses=None) -> SeriesResult:
    """A ``SeriesResult`` assembled from verdicts, with no fit behind it.

    The onset, the trajectory and the two diagnostics are functions of the
    verdicts alone, so the unit block states verdicts directly.  That is not a
    convenience: it is what makes those tests independent of whether any
    particular solver run happens to converge.
    """
    statuses = statuses or ["converged"] * len(points)
    entries = []
    for i, ((x, magnitude, esd, supported), status) in enumerate(
            zip(points, statuses, strict=True)):
        entries.append(SeriesEntry(
            index=i, label=f"p{i}", x=x, status=status,
            magnetic=[_row(magnitude=magnitude, esd=esd, supported=supported)]))
    return SeriesResult(entries=entries, x_label="T (K)")


# ============================================================ the onset, alone

def test_the_onset_is_a_bracket_and_its_esd_is_half_the_gap():
    """Where the verdict switches, and what the ± is about.

    The bracket is the last released pattern and the first held one; the
    midpoint is the estimate and **half the gap** is the uncertainty, because
    what limits it is the spacing of the measurements and not the quality of
    any fit.  ``sense="falls"`` records which way round the transition runs, so
    a field-ramp that *gains* a moment with x is not silently read as a
    temperature ramp that loses one.
    """
    series = _hand_built([(10.0, 4.0, 0.05, True), (30.0, 2.0, 0.05, True),
                          (50.0, 0.02, 0.4, False), (70.0, 0.01, 0.4, False)])
    onset = series.magnetic_trajectory().onset

    assert onset.bracket == [30.0, 50.0]
    assert onset.bracket_labels == ["p1", "p2"]
    assert onset.x == pytest.approx(40.0)
    assert onset.x_esd == pytest.approx(10.0)
    assert onset.sense == "falls"
    assert onset.monotone and onset.bracket_verdicts_final
    assert (onset.n_supported, onset.n_held) == (2, 2)
    assert "WP-1325" in onset.note, "the ± must say what it is not"


def test_the_onset_is_read_off_the_verdicts_and_not_off_the_values():
    """The discriminating case: a *large* |m| above the transition.

    The third pattern's modulus is 1.9 μ_B — larger than the second pattern's
    released 0.9 — but its esd is 0.8, so it is 2.4σ and unsupported.  Any
    implementation that located the onset by thresholding |m|, or by looking
    for the largest step in it, puts the boundary in the wrong place here; one
    that reads ``supported`` puts it between p1 and p2.
    """
    series = _hand_built([(10.0, 4.0, 0.05, True), (30.0, 0.9, 0.05, True),
                          (50.0, 1.9, 0.8, False), (70.0, 0.01, 0.4, False)])
    onset = series.magnetic_trajectory().onset

    assert onset.bracket == [30.0, 50.0]
    # and the trap is real: the largest step in the value column is elsewhere
    values = series.magnetic_trajectory().value
    steps = np.abs(np.diff(values))
    assert int(np.argmax(steps)) == 0, "the biggest step is p0→p1, not the onset"


def test_a_moment_supported_everywhere_locates_no_onset():
    series = _hand_built([(10.0, 4.0, 0.05, True), (30.0, 3.0, 0.05, True)])
    onset = series.magnetic_trajectory().onset

    assert onset.x is None and onset.x_esd is None
    assert onset.sense == "none" and onset.bracket == []
    assert onset.n_held == 0
    assert "outside the measured window" in onset.note


def test_a_moment_supported_nowhere_locates_no_onset():
    """The negative control's shape: unsupported throughout, and no onset.

    A series with no moment anywhere must not produce a boundary — and the note
    has to say the result is about the window rather than about the specimen,
    since "no onset in 10-70 K" and "this specimen never orders" are different
    claims and only the first one was measured.
    """
    series = _hand_built([(10.0, 0.02, 0.4, False), (30.0, 0.01, 0.5, False),
                          (50.0, 0.03, 0.6, False)])
    onset = series.magnetic_trajectory().onset

    assert onset.x is None and onset.bracket == []
    assert (onset.n_supported, onset.n_held) == (0, 3)
    assert "about the window and not about the specimen" in onset.note


def test_an_interleaved_verdict_withholds_the_bracket_and_lists_the_switches():
    """Two boundaries are not one onset, and are not averaged into one.

    A verdict that switches more than once along the axis is a statement about
    the *fits* — a pattern the ladder rescued cold, a moment a warm start
    carried across — and the honest answer is the list of switches with no
    single number, not the mean of them.
    """
    series = _hand_built([(10.0, 4.0, 0.05, True), (30.0, 0.02, 0.4, False),
                          (50.0, 3.0, 0.05, True), (70.0, 0.01, 0.4, False)])
    onset = series.magnetic_trajectory().onset

    assert onset.x is None and not onset.monotone
    assert onset.boundaries == [[10.0, 30.0], [30.0, 50.0], [50.0, 70.0]]
    assert "switches 3 times" in onset.note


def test_the_onset_is_ordered_by_the_axis_and_not_by_the_walk():
    """A cooling chain reports its onset on the temperature axis.

    The entries of a backward chain come back in *series* order already, but
    nothing stops a caller handing in patterns whose x descends.  The bracket
    is located after sorting by x, so the same six patterns give the same
    onset whichever order they were listed in — which is what makes a warming
    pass and a cooling pass comparable at all.
    """
    rising = [(10.0, 4.0, 0.05, True), (30.0, 2.0, 0.05, True),
              (50.0, 0.02, 0.4, False)]
    a = _hand_built(rising).magnetic_trajectory().onset
    b = _hand_built(list(reversed(rising))).magnetic_trajectory().onset

    assert a.bracket == b.bracket == [30.0, 50.0]
    assert a.x == b.x == pytest.approx(40.0)
    assert a.sense == b.sense == "falls"


def test_a_rising_sense_is_recorded_as_rising():
    """x is not always a temperature: a field ramp gains a moment with x."""
    onset = _hand_built([(0.0, 0.01, 0.4, False), (2.0, 0.02, 0.5, False),
                         (4.0, 1.5, 0.05, True)]).magnetic_trajectory().onset

    assert onset.sense == "rises"
    assert onset.bracket == [2.0, 4.0]


# ================================== the bracket, and a fit that stopped early

def test_a_supported_verdict_from_a_truncated_fit_makes_the_bracket_unquotable():
    """The fence, and it is the one the reseed rule cannot supply.

    ``supported`` is |m| against *that pattern's own* esd, so a fit stopped at
    its iteration cap can hand back a verdict about an intermediate state — a
    modulus that had not finished falling.  Measured on a starved chain below,
    that is exactly how a moment above the transition survives as a small
    confident number while Rwp stays fine and no other fence fires.
    """
    series = _hand_built(
        [(10.0, 4.0, 0.05, True), (30.0, 0.6, 0.05, True),
         (50.0, 0.02, 0.4, False)],
        statuses=["converged", "max_iter", "converged"])
    onset = series.magnetic_trajectory().onset

    assert onset.x == pytest.approx(40.0), "the bracket is still located"
    assert not onset.bracket_verdicts_final
    assert onset.n_unconverged == 1
    assert "Do not quote it" in onset.note and "p1" in onset.note
    assert "NOT QUOTABLE" in str(onset)


def test_a_held_verdict_from_a_truncated_fit_does_not_invalidate_the_bracket():
    """The other half of the asymmetry, and it is the load-bearing half.

    A modulus descending to nothing **does not terminate**: |F_m|² ∝ m², so the
    column vanishes with the moment and the flat direction WP-1327 holds for the
    angles opens up for the modulus itself.  The first pattern above a
    transition therefore reports ``max_iter`` as a matter of course — measured
    on this file's own ramp, 3247 iterations against a 400-iteration cap at
    3.5e-6 μ_B — and refusing the bracket for it would refuse every ordering
    transition there is.  So a truncated fit that came back *unsupported* is
    left alone.
    """
    series = _hand_built(
        [(10.0, 4.0, 0.05, True), (30.0, 2.0, 0.05, True),
         (50.0, 1e-6, 0.4, False)],
        statuses=["converged", "converged", "max_iter"])
    onset = series.magnetic_trajectory().onset

    assert onset.bracket_verdicts_final, "a held truncation is not a doubt"
    assert onset.n_unconverged == 1, "and it is still reported"
    assert "Do not quote it" not in onset.note


def test_the_ascent_out_of_the_floor_terminates_at_once():
    """The measurement the asymmetry above rests on, run rather than quoted.

    Seeded *at* the floor against a pattern carrying a real 4.5 μ_B, one
    iteration per stage already reaches a supported moment.  So a truncated fit
    cannot manufacture "unsupported" the way it can manufacture "supported",
    and the asymmetric fence is not a convenience.
    """
    from rietx.params.vector import ParameterTable
    from rietx.report.magnetic import analyse_moments

    data = simulate(4.5, 4400, scale=6.0, background=300.0)
    ref = rx.Refinement(Structure(phases=[mnf2(MOMENT_FLOOR_MU_B)]), neutron())
    result = ref.fit(data, plan=moment_plan(max_iter=1))
    table = ParameterTable(ref.structure, ref.instrument)
    row = analyse_moments(
        ref._model, table.decode(table.x0()), ref.structure,
        held=list(result.stages[-1].held),
        esd={p.path: p.stderr for p in result.parameters
             if p.stderr is not None})[0]

    assert result.status == "max_iter", "the point is that it was cut short"
    assert row.supported, (row.magnitude, row.magnitude_esd)
    assert row.magnitude > 1.0


# ========================================================= the trajectory view

def test_a_held_point_keeps_its_value_and_loses_its_esd():
    """Not zero, and not a small number with a small bar.

    The value is the modulus the fit reached and it is the numerator of the
    ratio that called the point unsupported, so it stays; the esd is withheld
    so that a plotted point cannot read as a small *measured* moment.
    ``arrays()`` turns the withheld one into the NaN an errorbar ignores.
    """
    series = _hand_built([(10.0, 4.0, 0.05, True), (70.0, 0.067, 0.395, False)])
    traj = series.magnetic_trajectory()

    assert traj.value == [4.0, 0.067], "the held value is not overwritten"
    assert traj.stderr == [0.05, None]
    assert traj.supported == [True, False]
    assert traj.held == [False, True]
    assert traj.status == ["converged", "converged"]
    assert traj.atom == "Mn" and traj.ion == "Mn2+"
    _x, value, sd = traj.arrays()
    assert value[1] == pytest.approx(0.067)
    assert np.isnan(sd[1]) and sd[0] == pytest.approx(0.05)
    assert "HELD" in str(traj)


def test_a_pattern_without_the_site_is_skipped_rather_than_filled():
    """A gap in a trajectory is a real thing, for ``trajectory``'s reason."""
    series = _hand_built([(10.0, 4.0, 0.05, True), (30.0, 3.0, 0.05, True)])
    series.entries[1].magnetic = []
    traj = series.magnetic_trajectory()

    assert len(traj.value) == 1 and traj.x == [10.0]
    assert series.magnetic_sites() == ["phases.0.atoms.0.moment.dof0"]


def test_two_magnetic_sites_must_be_named_and_are_not_silently_picked():
    """"The moment" is not well defined on a two-sublattice structure."""
    series = _hand_built([(10.0, 4.0, 0.05, True)])
    series.entries[0].magnetic.append(
        _row(path="phases.0.atoms.1.moment.dof0", magnitude=1.0, esd=0.05,
             supported=True, atom="Mn2"))

    assert len(series.magnetic_sites()) == 2
    with pytest.raises(ValueError, match="name one by its path or label"):
        series.magnetic_trajectory()
    with pytest.raises(ValueError, match="name one by its path or label"):
        series.entries[0].moment()
    # named, either way round, it resolves
    assert series.magnetic_trajectory("Mn2").value == [1.0]
    assert series.entries[0].moment(
        "phases.0.atoms.1.moment.dof0").atom == "Mn2"


def test_a_magnetic_display_path_resolves_through_the_one_dispatch():
    """``resolve_trajectory`` is the single authority the plot layer calls.

    ``"magnetic."`` with nothing after it names the only site, which is what a
    one-sublattice structure has; the site may also be named by label or by
    path.  And the prefix is a *derived* path, so the caller that must skip the
    forward/backward comparison for a curve with no per-point σ skips this one
    too.
    """
    series = _hand_built([(10.0, 4.0, 0.05, True), (70.0, 0.02, 0.4, False)])

    for name in ("magnetic.", "magnetic.Mn",
                 "magnetic.phases.0.atoms.0.moment.dof0"):
        traj = series.resolve_trajectory(name)
        assert isinstance(traj, MagneticTrajectory), name
        assert traj.supported == [True, False], name
    assert series.is_derived_path("magnetic.Mn")
    # and an ordinary dot-path still falls through untouched
    assert not isinstance(series.resolve_trajectory("phases.0.cell.a"),
                          MagneticTrajectory)


def test_the_moment_rows_survive_a_json_round_trip():
    """``SeriesEntry.magnetic`` is a stored field, so it has to reload."""
    series = _hand_built([(10.0, 4.0, 0.05, True), (70.0, 0.067, 0.395, False)])
    back = SeriesResult.model_validate(series.model_dump(mode="json"))

    assert back == series
    assert back.entries[1].magnetic[0].supported is False
    assert back.entries[1].magnetic[0].path.endswith("moment.dof0")
    assert back.magnetic_trajectory().onset.x == pytest.approx(40.0)


def test_the_trajectory_plots_and_marks_the_held_points():
    pytest.importorskip("matplotlib")
    series = _hand_built([(15.0, 4.6, 0.05, True), (35.0, 3.9, 0.05, True),
                          (55.0, 2.7, 0.06, True), (75.0, 0.02, 0.4, False),
                          (95.0, 0.01, 0.5, False)])
    OUT.mkdir(exist_ok=True)
    fig = series.plot(["magnetic.Mn"], path=str(OUT / "wp1329_trajectory.png"))
    ax = fig.axes[0]
    # the hollow-square series and the shaded onset bracket are both drawn
    assert any(line.get_marker() == "s" for line in ax.lines)
    assert (OUT / "wp1329_trajectory.png").exists()


# ============================================== the carry rule, on its mechanics

def test_the_floor_carry_scales_an_unsupported_modulus_and_keeps_its_direction():
    """What crosses the boundary when a pattern did not support its moment.

    The components are **scaled**, not zeroed: the modulus lands on its floor
    and the site's direction — the thing the angle DOFs encode, and the thing
    the powder often cannot see at all — is preserved.  And the source object
    is not touched, because the caller reads it back as
    ``fitted_structures()``.
    """
    structure = Structure(phases=[mnf2(3.0)])
    row = _row(magnitude=0.02, esd=0.4, supported=False)

    out, floored = _floor_unsupported_moments(structure, [row])

    assert floored == ["phases.0.atoms.0.moment.dof0"]
    components = out.phases[0].atoms[0].moment.values()
    assert components[2] == pytest.approx(MOMENT_FLOOR_MU_B)
    assert components[0] == components[1] == 0.0
    # unchanged in the source
    assert structure.phases[0].atoms[0].moment.values()[2] == pytest.approx(3.0)


def test_the_floor_carry_leaves_a_supported_site_alone_and_copies_nothing():
    structure = Structure(phases=[mnf2(3.0)])
    out, floored = _floor_unsupported_moments(
        structure, [_row(magnitude=3.0, esd=0.05, supported=True)])

    assert floored == []
    assert out is structure, "a supported chain must not pay for a deep copy"


def test_the_floor_carry_is_a_no_op_on_a_modulus_already_at_nothing():
    """There is nothing stale to reseed, so nothing is reported as reseeded."""
    structure = Structure(phases=[mnf2(1e-9)])
    out, floored = _floor_unsupported_moments(
        structure, [_row(magnitude=1e-9, esd=0.4, supported=False)])

    assert floored == [] and out is structure


# ============================================================ the ramp, refined

@pytest.fixture(scope="module")
def ramp():
    """Six patterns from the declared m(T), refined forward as one chain."""
    patterns = [simulate(moment_at(t), 1329 + i) for i, t in enumerate(RAMP_T)]
    series = rx.refine_sequential(
        patterns, Structure(phases=[mnf2(3.0)]), neutron(),
        plan=moment_plan(), x=RAMP_T, x_label="T (K)")
    return series, patterns


@pytest.mark.xdist_group("wp1329-ramp")
def test_the_ramp_recovers_the_declared_onset_and_holds_above_it(ramp):
    """The rung's acceptance, on a ramp whose T_N this file declared.

    Every pattern below T_N = 67 K reports the block released and every pattern
    above it reports it held; the bracket is the pair that straddles the
    declared T_N, and the declared value lies inside ``x ± x_esd`` — which it
    must, since the bracket *contains* it by construction once the verdicts are
    right.  The magnitudes are checked loosely against the declared m(T)
    because what this rung owns is the verdict and the bracket; the magnitude
    is WP-1327's, tested there.
    """
    series, _patterns = ramp
    traj = series.magnetic_trajectory()

    assert [e.status != "diverged" for e in series.entries] == [True] * 6
    verdicts = dict(zip(traj.x, traj.supported, strict=True))
    for t, ok in verdicts.items():
        assert ok is (t < T_N_K), (t, ok)

    onset = traj.onset
    assert tuple(onset.bracket) == RAMP_BRACKET
    assert onset.monotone and onset.sense == "falls"
    assert onset.bracket_verdicts_final, onset.note
    assert abs(onset.x - T_N_K) <= onset.x_esd, (onset.x, onset.x_esd)

    # the released magnitudes track the declared order parameter, and every
    # one of them carries an esd while no held one does
    for t, value, sd, ok in zip(traj.x, traj.value, traj.stderr,
                                traj.supported, strict=True):
        if ok:
            assert value == pytest.approx(moment_at(t), abs=0.25), t
            assert sd is not None and sd > 0.0, t
        else:
            assert sd is None, t
            assert value < 0.1, (t, value)


@pytest.mark.xdist_group("wp1329-ramp")
def test_the_ramp_reports_both_codes_with_the_counts_and_the_bracket(ramp):
    """The two diagnostics, in the WP-1333 idiom: "N of M", and the bracket."""
    series, _patterns = ramp
    codes = {d.code: d for d in series.diagnostics}

    hold = codes["SEQUENTIAL_MOMENT_HOLD"]
    assert hold.level == "warning"
    assert hold.value == pytest.approx(2.0), "two patterns above T_N"
    assert "2 of 6 pattern(s)" in hold.message and "33%" in hold.message
    assert hold.where == ["phases.0.atoms.0.moment.dof0"]
    assert "never as \"a small moment\"" in hold.message

    onset = codes["SEQUENTIAL_MOMENT_ONSET"]
    assert onset.level == "info"
    assert onset.value == pytest.approx(67.5)
    assert "60 → 75" in onset.message
    assert "not a fitted critical point" in onset.message


@pytest.mark.xdist_group("wp1329-ramp")
def test_the_ramp_draws_obs_calc_diff_and_the_trajectory(ramp):
    """Rwp hides a locally bad fit, so every refinement here draws itself."""
    pytest.importorskip("matplotlib")
    from rietx.viz.plots import plot_result

    series, patterns = ramp
    OUT.mkdir(exist_ok=True)
    for t, result in zip(RAMP_T, series.entries, strict=True):
        assert result.statistics is not None
    for t, pattern in zip(RAMP_T, patterns, strict=True):
        ref = rx.Refinement(Structure(phases=[mnf2(3.0)]), neutron())
        plot_result(ref.fit(pattern, plan=moment_plan()),
                    path=str(OUT / f"wp1329_ramp_{t:g}K.png"))
    series.plot(["magnetic.Mn", "phases.0.scale"],
                path=str(OUT / "wp1329_ramp_trajectory.png"))
    assert (OUT / "wp1329_ramp_trajectory.png").exists()


def test_both_directions_agree_on_the_onset_and_the_row_says_so():
    """The check a single pass cannot make (WP-1329, WP-1076's machinery).

    The failure it is for: a chain that carried a moment across the transition
    in one direction and not in the other.  Run both ways, the onset row
    carries the *other* chain's bracket and stays ``info`` only when the two
    overlap — and the reverse chain is reachable on ``result.backward``, so a
    caller of the one-shot verb can see the trajectory the comparison is about.
    """
    patterns = [simulate(moment_at(t), 1329 + i) for i, t in enumerate(RAMP_T)]
    series = rx.refine_sequential(
        patterns, Structure(phases=[mnf2(3.0)]), neutron(), plan=moment_plan(),
        x=RAMP_T, x_label="T (K)", direction="both")

    forward = series.magnetic_trajectory().onset
    assert series.backward is not None
    backward = series.backward.magnetic_trajectory().onset
    assert tuple(forward.bracket) == tuple(backward.bracket) == RAMP_BRACKET

    row = next(d for d in series.diagnostics
               if d.code == "SEQUENTIAL_MOMENT_ONSET")
    assert row.level == "info"
    assert "the backward chain brackets it 60 → 75" in row.message
    assert "not the ordering's" in row.message
    # the reverse pass carries its own reading, not the forward one's
    assert any(d.code == "SEQUENTIAL_MOMENT_ONSET"
               for d in series.backward.diagnostics)


# ================================================== the negative controls, refined

def test_a_series_with_no_moment_anywhere_reports_no_onset_and_holds_throughout():
    """Negative control: the same machinery on patterns that carry no moment.

    Every pattern unsupported, no onset, and a ``SEQUENTIAL_MOMENT_HOLD`` at
    100 % of the series.  What must *not* happen is a bracket somewhere inside
    a window where nothing ordered.
    """
    temperatures = [15.0, 35.0, 55.0, 75.0]
    patterns = [simulate(0.0, 3300 + i) for i in range(len(temperatures))]
    series = rx.refine_sequential(
        patterns, Structure(phases=[mnf2(3.0)]), neutron(), plan=moment_plan(),
        x=temperatures, x_label="T (K)")
    traj = series.magnetic_trajectory()

    assert traj.supported == [False] * 4, traj.value
    assert all(sd is None for sd in traj.stderr)
    assert traj.onset.x is None and traj.onset.bracket == []
    assert "no onset to locate" in traj.onset.note
    hold = next(d for d in series.diagnostics
                if d.code == "SEQUENTIAL_MOMENT_HOLD")
    assert "4 of 4 pattern(s) (100%" in hold.message
    assert not any(d.code == "SEQUENTIAL_MOMENT_ONSET"
                   for d in series.diagnostics)


def test_a_starved_chain_reports_a_supported_moment_above_the_transition_and_is_flagged():
    """The positive arm of the fence, beside the arm that must stay quiet.

    One pattern with a real 4.5 μ_B and three with none, refined twice: once
    with one iteration per stage and once with enough.  Starved, the modulus
    above the transition survives as a small **supported** number and the onset
    moves — so the run that a reader must not quote is the one the row refuses.
    Given enough iterations the same chain locates the boundary at the first
    pattern above the transition and the row goes quiet.

    This is also the measurement behind the flag in the rung's report: neither
    the reseed fence nor the floor carry catches the starved case, because Rwp
    is fine and no pattern ever comes back unsupported for the carry to act on.
    """
    temperatures = [10.0, 70.0, 80.0, 90.0]
    patterns = [simulate(4.5, 4400, scale=6.0, background=300.0)]
    patterns += [simulate(0.0, 4401 + i, scale=6.0, background=300.0)
                 for i in range(3)]

    def run(max_iter):
        series = rx.refine_sequential(
            patterns, Structure(phases=[mnf2(4.5)]), neutron(),
            plan=moment_plan(max_iter), x=temperatures, x_label="T (K)")
        return series, series.magnetic_trajectory()

    starved, starved_traj = run(1)
    fed, fed_traj = run(20)

    # starved: a moment above the transition, supported, and the wrong bracket
    assert starved_traj.supported[1] is True, starved_traj.value
    assert starved_traj.value[1] > 0.1
    assert tuple(starved_traj.onset.bracket) != (10.0, 70.0)
    assert not starved_traj.onset.bracket_verdicts_final
    starved_row = next(d for d in starved.diagnostics
                       if d.code == "SEQUENTIAL_MOMENT_ONSET")
    assert starved_row.level == "warning"
    assert "Do not quote it" in starved_row.message

    # fed: the boundary is at the first pattern above the transition, and quiet
    assert fed_traj.supported == [True, False, False, False], fed_traj.value
    assert tuple(fed_traj.onset.bracket) == (10.0, 70.0)
    assert fed_traj.onset.bracket_verdicts_final
    fed_row = next(d for d in fed.diagnostics
                   if d.code == "SEQUENTIAL_MOMENT_ONSET")
    assert fed_row.level == "info"


def test_an_unsupported_pattern_reseeds_its_successor_to_the_floor():
    """The hold along the series, measured on the chain that exercises it.

    The predecessor's modulus comes back unsupported *above* the floor, so the
    successor's warm start is the floor rather than that value, and
    ``SEQUENTIAL_MOMENT_HOLD`` names the patterns it happened to.  What it does
    **not** do is move the predecessor's own reported value — that number and
    its esd are the evidence the verdict was taken from.
    """
    temperatures = [10.0, 70.0, 80.0, 90.0]
    patterns = [simulate(4.5, 4400, scale=6.0, background=300.0)]
    patterns += [simulate(0.0, 4401 + i, scale=6.0, background=300.0)
                 for i in range(3)]
    series = rx.refine_sequential(
        patterns, Structure(phases=[mnf2(4.5)]), neutron(),
        plan=moment_plan(20), x=temperatures, x_label="T (K)")
    traj = series.magnetic_trajectory()

    hold = next(d for d in series.diagnostics
                if d.code == "SEQUENTIAL_MOMENT_HOLD")
    assert "reseeded to its floor" in hold.message
    assert "successor pattern(s)" in hold.message
    # the unsupported values are the fit's own, above the floor, with their esds
    # still on the evidence row even though the trajectory withholds them
    for entry, ok in zip(series.entries, traj.supported, strict=True):
        row = entry.moment()
        if not ok:
            assert row.magnitude_esd is not None, entry.label
            assert row.magnitude <= MOMENT_SUPPORT_SIGMA * row.magnitude_esd
            assert "unsupported, not as a small moment" in row.note


# =========================================================== absence for cause

def test_a_non_magnetic_series_carries_no_rows_and_no_moment_diagnostics():
    """Absence for cause, and it costs the chain nothing to establish.

    A phase that declares no moment produces no rows, no sites, no codes —
    and the guard is the compiled model's own frozen magnetic block, so a
    non-magnetic chain never builds a ``ParameterTable`` to find that out.
    """
    temperatures = [15.0, 35.0]
    patterns = [simulate(3.0, 5500 + i) for i in range(2)]
    series = rx.refine_sequential(
        patterns, Structure(phases=[nuclear_mnf2()]), neutron(),
        plan=rx.RefinementPlan(stages=[
            rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"])]),
        x=temperatures)

    assert series.magnetic_sites() == []
    assert all(e.magnetic == [] for e in series.entries)
    assert not [d for d in series.diagnostics
                if d.code.startswith("SEQUENTIAL_MOMENT")]
    assert locate_onset(series.magnetic_trajectory()).x is None
    assert "no phase declared one" in series.magnetic_trajectory().onset.note


# ================================================ composing with solve_magnetic

@pytest.mark.slow
def test_solve_magnetic_on_the_first_pattern_gives_the_model_the_series_refines(
        tmp_path):
    """The two rungs compose: M-9 determines, WP-1329 follows it along the axis.

    ``solve_magnetic`` is run on the coldest pattern — the one with a moment to
    find — and the magnetic structure it refined is handed to
    ``refine_sequential`` as the starting model for the whole ramp.  The series
    then reports the moment released on the ordered patterns and held on the
    paramagnetic one, with an onset, from a model no human stated.

    It goes through the **magCIF** the solution writes rather than through the
    trial's in-memory structure, because that is the route a user has — the
    determination and the series need not be the same session — and it is
    therefore the one that has to keep working.
    """
    cold = simulate(4.5, 6600)
    hot = simulate(0.0, 6601)
    ref = rx.Refinement(Structure(phases=[nuclear_mnf2()]), neutron())
    ref.fit(cold, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("cell", ["phases.*.scale", "instrument.background.c*",
                          "phases.*.cell.*"])]))

    solution = rx.solve_magnetic(ref, cold, sites=["Mn"], ion="Mn2+")
    assert solution.verdict == "solved", solution.reason

    written = solution.write_magcifs(tmp_path)
    assert written, "a solved determination writes its class"
    best = f"class{solution.best.class_index}_"
    magcif = next(p for p in written if Path(p).name.startswith(best))
    solved = rx.Structure.from_cif(magcif)
    assert solved.phases[0].atoms[0].moment is not None
    assert solved.phases[0].magnetic_symmetry is not None

    series = rx.refine_sequential(
        [cold, hot], solved, ref.fitted_instrument, plan=moment_plan(),
        x=[10.0, 90.0], x_label="T (K)")
    traj = series.magnetic_trajectory()

    assert traj.supported == [True, False], traj.value
    assert traj.value[0] == pytest.approx(4.5, abs=0.4)
    assert traj.stderr[1] is None
    assert tuple(traj.onset.bracket) == (10.0, 90.0)
