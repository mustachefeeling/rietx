"""`solve_magnetic`: the determination workflow, its criterion and its abstentions.

M-9.  Everything here is **synthetic** — the pattern is simulated from a
structure this file states, so the answer is known and a wrong ranking is a
failure rather than a disagreement with a tutorial.  The real-data arms
(LaMnO₃, Cr₂WO₆, Ba₆Co₆, Co₃O₄) are read-and-test only and live in the rung's
report, never here.

The tests worth having are the ones a *plausible wrong* implementation fails,
so each block below turns on something specific:

* the k step takes the **forbidden-lattice-point** route when that bucket
  fires, and never scores that excess against a candidate vector — a k = 0
  signature fed to the candidate ranking is the first way this workflow goes
  quietly wrong;
* the ranking is **not** Rwp: a family with more amplitudes reaches a lower Rwp
  and must still lose when BIC charges it for them;
* one trial per **equivalence class**, not per candidate — the count of fits is
  the assertion, because a workflow that refines every member produces the same
  table with a different bill and no visible difference;
* a **tie is an abstention**, and the abstention names every member of it;
* the null test is a **gate**: a pattern with no magnetic intensity produces no
  winner, whatever ΔBIC says;
* a **non-neutron histogram is refused by name**;
* the magnetic-only R is computed over the channels the nuclear model puts
  nothing on and nowhere else, which is what makes it comparable between
  candidates;
* a class with **more than one magnetic site** is refined from every one-site
  start as well as the flat one, because the flat unit-magnitude seed can land
  in a minimum that is provably not the optimum, and a ranking taken at
  non-optimal points measures the seed;
* every glob the default stages free actually frees something — a ``Stage``
  entry matching nothing is accepted silently.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
import rietx.strategy.magnetic as _magnetic_module
from rietx.crystallography.magnetic.form_factor import assumed_lande_g
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.moments import SEED_TILT, tilted_seed, warm_seed
from rietx.crystallography.symmetry import (
    refuse_an_unnamed_parent,
    resolve_group,
    unnamed_label,
)
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, MagneticSymmetry, Moment, Phase
from rietx.strategy.magnetic import (
    SOLVE_TIE_DELTA_BIC,
    MagneticSolution,
    MagneticTrial,
    MomentRow,
    _descend,
    _maximal_subgroups,
    _rank,
    _tie_lattice_lines,
    magnetic_channels,
    r_magnetic,
)

LAMBDA_CW = 2.4
GRID = np.arange(8.0, 130.0, 0.05)
MN_SITE = (0.0, 0.0, 0.5)

#: The A-type arrangement's group for an orthorhombic perovskite at k = 0.
#: A *number*, checked against MAGNDATA #0.642 (Elemans, van Laar, van der Veen
#: & Loopstra, 1971, J. Solid State Chem. 3, 238) and never a vendored file.
A_TYPE_BNS = "62.448"


def _cell(a, b, c):
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))


def _atom(label, species, xyz, biso=0.4, moment=None):
    x, y, z = xyz
    return Atom(label=label, species=species, x=Parameter(value=x),
                y=Parameter(value=y), z=Parameter(value=z),
                biso=Parameter(value=biso), moment=moment)


def perovskite(moment=None, magnetic=None) -> Phase:
    """An orthorhombic perovskite, Mn on 4b — the shape LaMnO₃ has.

    Every coordinate is a plausible round number typed here, not a published
    one: what the tests measure is the workflow, and a published structure
    would put a number in the repository that the run does not need.
    """
    return Phase(
        name="perovskite", space_group="P n m a", cell=_cell(5.74, 7.70, 5.54),
        atoms=[_atom("A1", "La", (0.05, 0.25, 0.99)),
               _atom("Mn1", "Mn", MN_SITE, moment=moment),
               _atom("O1", "O", (0.48, 0.25, 0.07)),
               _atom("O2", "O", (0.31, 0.04, 0.72))],
        magnetic_symmetry=magnetic)


def tetragonal(moment=None, magnetic=None) -> Phase:
    return Phase(
        name="tetragonal", space_group="P 4/m m m", cell=_cell(4.0, 4.0, 4.2),
        atoms=[_atom("Mn1", "Mn", (0.0, 0.0, 0.0), moment=moment),
               _atom("O1", "O", (0.5, 0.5, 0.5), biso=0.6)],
        magnetic_symmetry=magnetic)


def candidate_named(space_group, site, k, bns: str):
    for c in candidates(space_group, site, k):
        if c.bns_number == bns:
            return c
    raise AssertionError(f"{bns} is not in the candidate list at k = {k}")


def stated(phase_factory, candidate, moment, ion="Mn3+") -> Phase:
    ops, cent = candidate.group.xyz_strings()
    return phase_factory(
        moment=Moment.from_values(moment, ion),
        magnetic=MagneticSymmetry(operations=list(ops), centerings=list(cent)))


def simulate(phase, instrument, *, background=40.0, seed=20260906):
    """A pattern from a stated structure, with Poisson-scale noise."""
    ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
    y = np.asarray(ref.predict(GRID)) + background
    rng = np.random.default_rng(seed)
    y = y + rng.normal(scale=np.sqrt(np.maximum(y, 1.0)))
    return rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())


NUCLEAR_PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
    rx.Stage("cell", ["phases.*.scale", "instrument.background.c*",
                      "phases.*.cell.*"])])


def neutron():
    return rx.Instrument.constant_wavelength_neutron(LAMBDA_CW, fwhm_deg=0.35)


def nuclear_fit(phase, data, instrument):
    ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
    ref.fit(data, plan=NUCLEAR_PLAN)
    return ref


@pytest.fixture(scope="module")
def a_type():
    """A converged nuclear fit to a pattern that *is* magnetic, and its truth."""
    instrument = neutron()
    truth = candidate_named("P n m a", MN_SITE, (0, 0, 0), A_TYPE_BNS)
    data = simulate(stated(perovskite, truth, (3.5, 0.0, 0.0)), instrument)
    return nuclear_fit(perovskite(), data, instrument), data, truth


@pytest.fixture(scope="module")
def paramagnetic():
    """The same specimen with no moment — the null arm, same everything else."""
    instrument = neutron()
    data = simulate(perovskite(), instrument)
    return nuclear_fit(perovskite(), data, instrument), data


# ============================================================ the positive arm

@pytest.mark.slow
def test_the_published_arrangement_ranks_first_and_the_rivals_are_listed(a_type):
    """The whole workflow, on a pattern whose answer this file stated.

    Four Γ-point candidates at Mn, four classes (Pnma is low enough that the
    powder separates every one of them — M-7 measured exactly this), and the
    arrangement the pattern was simulated from is first.  The others are
    *reported*, with their ΔBIC, rather than dropped: a determination stage
    publishes the ranked list whole.
    """
    ref, data, truth = a_type
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")

    assert solution.verdict == "solved", solution.reason
    assert solution.best is not None
    assert solution.best.bns_number == truth.bns_number
    assert len(solution.trials) == 4, [t.bns_number for t in solution.trials]
    assert {t.bns_number for t in solution.trials} == {
        "62.448", "62.447", "62.446", "62.441"}
    # every rival carries its own ΔBIC, and the winner's lead is decisive
    assert all(t.delta_bic is not None for t in solution.trials)
    assert (solution.best.delta_bic - solution.trials[1].delta_bic
            > SOLVE_TIE_DELTA_BIC)
    assert solution.tied == (solution.best.class_index,)
    assert solution.best.moments[0].magnitude == pytest.approx(3.5, abs=0.2)
    assert solution.best.moments[0].supported


@pytest.mark.slow
def test_the_k_step_takes_the_forbidden_lattice_point_route(a_type):
    """A k = 0 signature is never scored against a candidate propagation vector.

    A magnetic space group generally drops the parent's glides and screws, so a
    k = 0 structure puts intensity where the *nuclear* structure factor is
    identically zero, and no nuclear model — right or wrong — can put any
    there.  That excess is the hypothesis; feeding it to the candidate ranking
    would rank a k against evidence that is not about it, which is the first
    way this workflow can go quietly wrong.
    """
    ref, data, _truth = a_type
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    assert solution.k_route == "forbidden lattice points"
    assert solution.k == ("0", "0", "0")
    assert solution.n_on_forbidden_lattice_points > 0
    # the k step's own sentence survives a solved verdict — it is a separate
    # field, because a determination has to be able to say how it got its k
    assert "systematic absence" in solution.k_reason
    # and the candidate list was not consulted for the choice
    assert "the candidate-k ranking is not consulted" in solution.k_reason
    assert solution.reason != solution.k_reason


@pytest.mark.slow
def test_the_worst_candidate_is_the_negative_control_inside_the_experiment(a_type):
    """One of the four puts no intensity where the data has some.

    It leaves Rwp at the nuclear-only value, its modulus comes back below three
    of its own esds, and the null test therefore disqualifies it — which is the
    control the positive arm needs and it runs in the same call.
    """
    ref, data, _truth = a_type
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    worst = solution.trials[-1]
    assert not worst.supported, worst.moments
    assert worst.rwp == pytest.approx(solution.nuclear_rwp, rel=5e-3)
    assert worst.delta_bic < 0.0
    assert solution.best is not worst


@pytest.mark.slow
def test_the_magnetic_only_r_separates_the_models_where_rwp_barely_does(a_type):
    """R_mag reads ≈1 for a model that explains none of the magnetic intensity.

    The nuclear reference is the scale: it puts nothing in that region by
    construction, so its R_mag is the "explains none of it" end and the
    winner's is near zero.  A whole-pattern Rwp cannot make that statement —
    the nuclear lines dominate it.
    """
    ref, data, _truth = a_type
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    assert solution.n_magnetic_channels > 0
    assert solution.nuclear_r_magnetic == pytest.approx(1.0, abs=0.35)
    assert solution.best.r_magnetic < 0.2
    assert solution.trials[-1].r_magnetic > 3 * solution.best.r_magnetic


@pytest.mark.slow
def test_one_magcif_per_class_and_nothing_written_unless_asked(a_type, tmp_path):
    """WP-1328's writer, one file per class, and only on request."""
    ref, data, _truth = a_type
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    assert not list(tmp_path.iterdir())
    written = solution.write_magcifs(tmp_path / "out")
    assert len(written) == sum(1 for t in solution.trials
                               if t.status == "refined")
    text = (tmp_path / "out" / written[0].rsplit("/", 1)[1]).read_text(
        encoding="utf-8")
    assert "_space_group_symop_magn_operation.xyz" in text
    assert "_atom_site_moment.crystalaxis_x" in text


# ================================================== one trial per class, not member

@pytest.mark.slow
def test_a_class_the_powder_cannot_separate_is_refined_once_and_named():
    """Three candidates, one class, one fit — and the members are in the answer.

    At k = (0,0,½) in P4/mmm three of the four candidates come back
    powder-equivalent (M-7's Shirane machinery), so the workflow refines the
    smallest of them and *names* the other two.  A workflow that refined every
    member would produce the same table at three times the cost and would let a
    reader rank models the data cannot separate.
    """
    instrument = neutron()
    truth = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]
    from rietx.crystallography.magnetic.supercell import magnetic_supercell

    statement = magnetic_supercell(tetragonal(), truth,
                                   magnetic_species=["Mn1"],
                                   ion={"Mn1": "Mn3+"}, magnitude=3.0)
    data = simulate(statement.phase, instrument)
    ref = nuclear_fit(tetragonal(), data, instrument)
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")

    assert solution.k == ("0", "0", "1/2")
    assert len(solution.trials) == 2, [t.members for t in solution.trials]
    sizes = sorted(len(t.members) for t in solution.trials)
    assert sizes == [1, 3], sizes
    # the class of three names all three, and its representative is the
    # smallest family in it
    big = next(t for t in solution.trials if len(t.members) == 3)
    assert big.free_amplitudes == 1, big.free_amplitudes
    assert solution.verdict == "solved"
    assert solution.best.bns_number == truth.bns_number
    # the anti-centring was a constraint, not only a seed
    assert solution.best.anti_translation_drift == pytest.approx(0.0, abs=1e-8)


# ============================================================== the abstentions

def _trial(index, *, delta_bic, r_mag, free, bns="1.1", supported=True):
    return MagneticTrial(
        class_index=index, representative=f"S{index}(a)",
        members=(f"{bns} S{index}(a)",), site="Mn1", irrep=f"S{index}",
        direction="(a)", bns_number=bns, uni_number=None, msg_type=1,
        free_amplitudes=free, determinable_amplitudes=1, status="refined",
        rwp=0.1, gof=1.0, delta_bic=delta_bic, r_magnetic=r_mag,
        n_moment_parameters=free, n_free_parameters=free + 5,
        moments=(MomentRow(label="Mn1", ion="Mn3+", magnitude=3.0,
                           esd=0.1 if supported else 30.0,
                           crystalaxis=(3.0, 0.0, 0.0), supported=supported),))


def test_a_constructed_tie_is_an_abstention_that_names_both_classes():
    """The rule the whole workflow exists to obey.

    Two classes with ΔBIC inside the stated width, the same magnetic-only R and
    the same amplitude count: nothing separates them, so the verdict is an
    abstention that names both.  Reporting the arithmetically-larger ΔBIC as a
    winner is the confident wrong singleton (WP-1043) — and at this separation
    the difference is not evidence.
    """
    a = _trial(0, delta_bic=120.0, r_mag=0.11, free=1)
    b = _trial(1, delta_bic=120.0 - 0.5 * SOLVE_TIE_DELTA_BIC, r_mag=0.11,
               free=1, bns="2.2")
    ordered, tied, verdict, reason = _rank([a, b], SOLVE_TIE_DELTA_BIC, 0.02)

    assert verdict == "abstained"
    assert set(tied) == {0, 1}
    assert "class 0" in reason and "class 1" in reason
    assert "1.1" in reason and "2.2" in reason
    assert len(ordered) == 2


def test_the_tie_is_broken_by_the_magnetic_only_r_before_parsimony():
    """Inside the tie width the next key speaks, and the reason says which."""
    a = _trial(0, delta_bic=120.0, r_mag=0.40, free=1)
    b = _trial(1, delta_bic=118.0, r_mag=0.11, free=1, bns="2.2")
    _o, tied, verdict, reason = _rank([a, b], SOLVE_TIE_DELTA_BIC, 0.02)
    assert verdict == "solved" and tied == (1,)
    assert "magnetic-only R" in reason


def test_parsimony_breaks_a_tie_neither_dbic_nor_r_can():
    a = _trial(0, delta_bic=120.0, r_mag=0.11, free=3)
    b = _trial(1, delta_bic=119.0, r_mag=0.11, free=1, bns="2.2")
    _o, tied, verdict, reason = _rank([a, b], SOLVE_TIE_DELTA_BIC, 0.02)
    assert verdict == "solved" and tied == (1,)
    assert "parsimonious" in reason


def test_an_unsupported_moment_cannot_win_however_good_its_dbic():
    """The null test is a gate, not a column.

    A trial whose modulus is below three of its own esds is what an
    unmagnetised pattern looks like under a magnetic model, and a large ΔBIC
    there is the criterion being fooled by extra freedom rather than evidence.
    """
    a = _trial(0, delta_bic=5000.0, r_mag=0.01, free=3, supported=False)
    _o, tied, verdict, reason = _rank([a], SOLVE_TIE_DELTA_BIC, 0.02)
    assert verdict == "nothing to solve"
    assert tied == ()
    assert "not one came back with a supported moment" in reason
    # and the reason is true of the state it reports: this trial *refined*, so
    # it must not be described as one that could not be stated
    assert "could not be stated" not in reason


def test_candidates_that_could_not_be_stated_are_not_called_a_null_result():
    """A refusal never had a modulus to test, so the null test cannot have failed.

    The two states reach the same "no winner" and mean opposite things: one is
    an answer about the specimen, the other is the workflow saying it could not
    ask the question. Reporting the first when the second happened is a
    diagnostic that is true of an intermediate state and false of the reported
    one, and it is what the Cr₂WO₆ 150 K arm produced before this branch
    existed.
    """
    refused = MagneticTrial(
        class_index=0, representative="S1(a)", members=("1.1 S1(a)",),
        site="Mn1", irrep="S1", direction="(a)", bns_number="1.1",
        uni_number=None, msg_type=1, free_amplitudes=1,
        determinable_amplitudes=0, status="refused",
        refusal="ValueError: the child cell carries no symbol")
    _o, tied, verdict, reason = _rank([refused], SOLVE_TIE_DELTA_BIC, 0.02)
    assert verdict == "abstained"
    assert tied == ()
    assert "could be stated as a refinable model" in reason
    assert "not a result about the specimen" in reason
    assert "null test" not in reason and "modulus" not in reason


@pytest.mark.slow
def test_a_pattern_with_no_unexplained_intensity_says_there_is_nothing_to_solve(
        paramagnetic):
    """The 150 K arm of a two-temperature acceptance, synthetically.

    Not a refusal and not an error: the nuclear model accounts for the pattern,
    so the workflow says so and names the counts it read.
    """
    ref, data = paramagnetic
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    assert solution.verdict == "nothing to solve", solution.reason
    assert solution.trials == ()
    assert solution.best is None
    assert solution.n_on_forbidden_lattice_points == 0
    assert solution.n_unexplained == 0
    assert "no magnetic intensity to model" in solution.reason


# ================================================================ the refusals

@pytest.mark.slow
def test_an_xray_histogram_is_refused_by_name():
    """A satellite on an X-ray pattern is a superstructure reflection.

    The positions are the same and the inference is not; a moment refined
    against X-rays has no gradient anywhere, so the workflow declines rather
    than producing a table of models fitted to nothing.
    """
    instrument = rx.Instrument.debye_scherrer(1.5406)
    data = simulate(perovskite(), instrument, background=200.0)
    ref = nuclear_fit(perovskite(), data, instrument)
    with pytest.raises(ValueError, match="neutron histogram and nothing else"):
        rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")


def test_a_phase_that_already_states_a_magnetic_group_is_refused():
    instrument = neutron()
    truth = candidate_named("P n m a", MN_SITE, (0, 0, 0), A_TYPE_BNS)
    phase = stated(perovskite, truth, (3.5, 0.0, 0.0))
    data = simulate(phase, instrument)
    ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
    ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"])]))
    with pytest.raises(ValueError, match="already declares a magnetic space"):
        rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")


def test_a_site_with_no_tabulated_form_factor_is_refused_with_the_keys_there_are():
    instrument = neutron()
    data = simulate(perovskite(), instrument)
    ref = nuclear_fit(perovskite(), data, instrument)
    with pytest.raises(ValueError, match="not a magnetic form-factor key"):
        rx.solve_magnetic(ref, data, sites=["O1"])


def test_calling_before_a_fit_is_refused():
    instrument = neutron()
    data = simulate(perovskite(), instrument)
    ref = rx.Refinement(rx.Structure(phases=[perovskite()]), instrument)
    with pytest.raises(RuntimeError, match="call fit\\(\\) on the nuclear model"):
        rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")


# ================================================= the magnetic-only region itself

@pytest.mark.slow
def test_the_magnetic_region_is_built_from_peaks_no_tick_explains(a_type):
    """Bucket 1 is out, and it is out on purpose.

    A residual peak sitting on a calculated reflection is a nuclear misfit or a
    k = 0 structure and this route cannot separate them, so scoring a magnetic
    model there would reward a candidate for absorbing somebody else's error.

    The property is about the **peaks the region is built from**, not about
    every channel of it: a window is a peak's own validity radius wide, so a
    channel at the edge of an included peak's window may sit closer to a tick
    than the peak does. Asserting on the channels instead is what a first
    version of this test did, and it failed for that reason rather than for a
    defect. So: every residual peak the region covers is more than its own
    radius from the nearest tick, and the region is a strict subset of what an
    unsorted "all residual peaks" region would have been.
    """
    from rietx.params.vector import ParameterTable
    from rietx.report import _resid_norm
    from rietx.report.layer0 import residual_peak_indices
    from rietx.report.schemas import VALIDITY_RADIUS_FWHM
    from rietx.strategy.magnetic import _peak_positions_and_widths

    ref, _data, _truth = a_type
    table = ParameterTable(ref.structure, ref.instrument)
    values = table.decode(table.x0())
    mask = magnetic_channels(ref._model, values, ref.result_)
    assert mask.any()

    tt = np.asarray(ref.result_.two_theta)
    ticks = np.asarray([t for p in ref.result_.ticks.values() for t in p])
    peaks = tt[residual_peak_indices(_resid_norm(ref.result_),
                                     min_peak_sigma=5.0)]
    pos, fwhm = _peak_positions_and_widths(ref._model, values)
    radius = VALIDITY_RADIUS_FWHM * fwhm[
        np.argmin(np.abs(peaks[:, None] - pos[None, :]), axis=1)]
    to_tick = np.min(np.abs(peaks[:, None] - ticks[None, :]), axis=1)

    covered = np.array([bool(mask[np.argmin(np.abs(tt - p))]) for p in peaks])
    # a peak inside the region is one no tick explains, and every peak a tick
    # does explain is outside it
    assert np.all(to_tick[covered] > radius[covered])
    # and the exclusion is exactly the tick test, not something looser
    assert np.all(to_tick[~covered] <= radius[~covered])
    assert covered.sum() < len(peaks), "no peak was excluded — bucket 1 empty?"


def test_an_empty_region_reports_none_rather_than_a_zero():
    """The honest empty state: no channels means no number, never R = 0."""

    class _Result:
        y_obs = [1.0, 2.0]
        y_calc = [1.0, 2.0]
        y_background = [1.0, 2.0]

    assert r_magnetic(_Result(), np.zeros(2, dtype=bool)) is None
    assert r_magnetic(_Result(), np.ones(2, dtype=bool)) is None


# ============================== the multi-site sweep, and dead free-list entries

def two_site(m1=None, m2=None, magnetic=None) -> Phase:
    """The same parent with a moment on **two** sites, which is where the sweep bites."""
    return Phase(
        name="two-site", space_group="P n m a", cell=_cell(5.74, 7.70, 5.54),
        atoms=[_atom("Mn1", "Mn", (0.0, 0.0, 0.5), moment=m1),
               _atom("Mn2", "Mn", (0.0, 0.0, 0.0), moment=m2),
               _atom("O1", "O", (0.48, 0.25, 0.07)),
               _atom("O2", "O", (0.31, 0.04, 0.72))],
        magnetic_symmetry=magnetic)


@pytest.mark.slow
def test_a_class_with_two_magnetic_sites_is_started_from_every_one_of_them():
    """The flat seed is not enough, and the answer records how many were tried.

    A moment stage over several sites is not convex.  Measured on Ba₆Co₆ with a
    nuclear model as complete as the GSAS-II tutorial's: the three-amplitude fit
    from a flat unit-magnitude seed reaches Rwp 0.08952 while its own
    **one-amplitude submodel** reaches 0.08867 — a superset model cannot fit
    worse than its own submodel at the true minimum, so the flat start was not
    at one.  Released from the one-site solution the same model reaches 0.08752
    with the moment on the other site, which is the published answer.

    A ranking taken at such points measures the seed, not the model, so the
    workflow sweeps one start per site plus the flat one and keeps the best.
    `MagneticTrial.n_starts` and `MagneticTrial.n_minima` are that sweep made
    visible; more than one minimum is a fact about the candidate, and it is a
    caveat on the answer rather than something the run hides.
    """
    instrument = neutron()
    truth = candidate_named("P n m a", MN_SITE, (0, 0, 0), A_TYPE_BNS)
    ops, cent = truth.group.xyz_strings()
    data = simulate(two_site(
        m1=Moment.from_values((3.5, 0.0, 0.0), "Mn3+"),
        m2=Moment.from_values((0.7, 0.0, 0.0), "Mn3+"),
        magnetic=MagneticSymmetry(operations=list(ops),
                                  centerings=list(cent))), instrument)
    ref = nuclear_fit(two_site(), data, instrument)
    solution = rx.solve_magnetic(ref, data, sites=["Mn1", "Mn2"], ion="Mn3+")

    winner = solution.trials[0]
    # flat + one per site
    assert winner.n_starts == 3, winner.n_starts
    assert winner.start in ("flat", "Mn1 only, then released",
                            "Mn2 only, then released")
    assert winner.n_minima >= 1
    # a multimodal class says so in the answer, not only in a log
    multimodal = [t for t in solution.trials if t.n_minima > 1]
    if multimodal:
        assert any(f"class {t.class_index}" in c and "distinct minima" in c
                   for t in multimodal for c in solution.caveats)
    # and the sweep did not cost correctness: the stated arrangement still wins
    assert solution.verdict == "solved", solution.reason
    assert winner.bns_number == A_TYPE_BNS


@pytest.mark.slow
def test_a_single_site_class_is_started_once(a_type):
    """Nothing to hold out, so no sweep and no extra fits."""
    ref, data, _truth = a_type
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    assert all(t.n_starts == 1 for t in solution.trials
               if t.status == "refined")
    assert all(t.start == "flat" for t in solution.trials
               if t.status == "refined")


@pytest.mark.slow
def test_the_default_stages_free_nothing_dead(a_type):
    """A `Stage` entry that matches no parameter is accepted **silently**.

    In a *ranking* a dead entry is worse than a wasted line — it makes the
    models that were compared differ from the ones the plan describes — so the
    workflow reports any glob that froze nothing.
    """
    ref, data, _truth = a_type
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    assert not [c for c in solution.caveats if "freed no parameter" in c], \
        [c for c in solution.caveats if "freed no parameter" in c]


def test_a_dead_glob_is_detected_and_a_live_one_is_not():
    """`_dead_globs` reads what the fit *froze*, not what the table holds.

    Reading the parameter table would miss exactly the case that matters: a
    path can exist in the table and still never be freed, so "the path exists"
    is not the question. What was actually freed is.
    """
    from rietx.strategy.magnetic import _dead_globs

    class _P:
        def __init__(self, path, vary):
            self.path, self.vary = path, vary

    class _R:
        parameters = [_P("phases.0.scale", True),
                      _P("phases.0.atoms.0.moment.dof0", True),
                      _P("phases.0.lor_size", False)]

    plan = rx.RefinementPlan(stages=[
        rx.Stage("s", ["phases.*.scale", "phases.*.lor_size",
                       "instrument.nonesuch"])])
    dead = _dead_globs(plan, _R())
    assert set(dead) == {"phases.*.lor_size", "instrument.nonesuch"}


@pytest.mark.slow
def test_widening_the_tie_hands_the_decision_to_the_next_key_and_says_so(a_type):
    """When ΔBIC stops separating, the reason names whichever key did decide.

    The abstention rule itself is pinned by the constructed-tie unit tests
    above; this is the end-to-end half, and what it catches is subtler than a
    missing abstention — a workflow that keeps the ΔBIC leader while quietly
    reporting the tie. Widen the width past the real ΔBIC spread and the
    leader must stop being chosen *for that reason*: either a lower key is
    named as the one that decided, or the verdict is an abstention.

    **Why a real tie is rare here, and that is by design.** Two models a powder
    cannot separate are merged into one class before anything is ranked, so the
    ties the class machinery would otherwise produce never reach the ranking.
    That is why the exact-tie case is constructed rather than found.
    """
    ref, data, _truth = a_type
    solved = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    assert solved.verdict == "solved"
    assert "leads on ΔBIC" in solved.reason
    spread = solved.trials[0].delta_bic - solved.trials[-1].delta_bic

    widened = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+",
                                tie_width=spread * 1.5)
    assert "leads on ΔBIC" not in widened.reason, widened.reason
    assert f"tie width of {spread * 1.5:.1f}" in widened.reason
    if widened.verdict == "solved":
        # a lower key decided, and the reason says which
        assert ("magnetic-only R" in widened.reason
                or "parsimonious" in widened.reason), widened.reason
        assert len(widened.tied) == 1
    else:
        assert widened.verdict == "abstained"
        assert len(widened.tied) >= 2
        assert widened.best is None
        for index in widened.tied:
            assert f"class {index}" in widened.reason


@pytest.mark.slow
def test_disabling_the_lower_keys_makes_a_widened_tie_an_abstention(a_type):
    """With ΔBIC widened out and the magnetic-only R disabled, only parsimony
    is left; classes that also match on that are a genuine abstention naming
    every one of them."""
    ref, data, _truth = a_type
    solved = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    spread = solved.trials[0].delta_bic - solved.trials[-1].delta_bic
    equal = [t for t in solved.trials
             if t.n_moment_parameters == solved.trials[0].n_moment_parameters]
    assert len(equal) >= 2, "the fixture no longer has two equally free classes"

    widened = rx.solve_magnetic(
        ref, data, sites=["Mn1"], ion="Mn3+",
        tie_width=spread * 1.5, tie_r=1e9,
        # only the classes with the same free moment count, so parsimony is
        # unable to separate the survivors either
        top_k=1)
    if widened.verdict == "abstained":
        assert len(widened.tied) >= 2
        for index in widened.tied:
            assert f"class {index}" in widened.reason
        assert "does not choose between them" in widened.reason
    else:
        # parsimony broke it, and the reason has to say so rather than
        # claiming a ΔBIC lead it does not have
        assert "parsimonious" in widened.reason, widened.reason


# ================================================== the g/ion plumbing (stage3 D1)
#
# solve_magnetic's own candidate builder used to construct every trial Phase
# with no g and no ion-inference at all, so a 4f/5f site abstained on every
# candidate class regardless of what structure_from_cif's own g/ion defaults
# would have done for it (WP-1327; checks/MAGNDATA_SWEEP_STAGE3_20260918.md
# D1).  These tests are the positive arm (both the direct ion-in-species shape
# stage3 actually measured, and the bare-element resolve_assumed_ion fallback
# the CIF reader already had) and the negative controls: a caller-stated ion
# still needs an explicit g (issue #257 A5, carried over unchanged), a
# caller-stated g always wins, and a 3d ion's behaviour never moves.

def perovskite_re(species="Dy3+", moment=None, magnetic=None) -> Phase:
    """A rare-earth analogue of :func:`perovskite`: same cell and site, the
    transition-metal species swapped for a lanthanide — a synthetic
    substitution, not a claim about a real Dy compound, exactly as the
    lande-g-default and magnetic-ion-default fixtures swap LaMnO3's Mn for a
    bare Dy."""
    return Phase(
        name="perovskite_re", space_group="P n m a", cell=_cell(5.74, 7.70, 5.54),
        atoms=[_atom("A1", "La", (0.05, 0.25, 0.99)),
               _atom("RE1", species, MN_SITE, moment=moment),
               _atom("O1", "O", (0.48, 0.25, 0.07)),
               _atom("O2", "O", (0.31, 0.04, 0.72))],
        magnetic_symmetry=magnetic)


def stated_re(nuclear_species, moment_ion, candidate, moment, g) -> Phase:
    """``perovskite_re`` stated with a magnetic moment, for simulation only.

    ``nuclear_species`` is the *nuclear* ``Atom.species`` solve_magnetic will
    see on the fitted structure (charged, ``"Dy3+"``, or bare, ``"Dy"``, per
    the two stage3 D1 shapes); ``moment_ion``/``g`` are the real magnetic
    form-factor key and Landé g the simulated pattern is generated from —
    always the resolved ion, since a bare nuclear species is a nuclear-only
    fact and the moment needs a real ⟨j0⟩/⟨j2⟩ row regardless of it.
    """
    ops, cent = candidate.group.xyz_strings()
    return perovskite_re(
        species=nuclear_species,
        moment=Moment.from_values(moment, moment_ion, g=g),
        magnetic=MagneticSymmetry(operations=list(ops), centerings=list(cent)))


DY_G = assumed_lande_g("Dy3+")  # Hund's rule, 4f9 6H15/2: g_J = 4/3


@pytest.fixture(scope="module")
def dy_charged_type():
    """A 4f site whose nuclear species already states its charge (``"Dy3+"``)
    — the shape the majority of stage3's 16 g-abstentions actually took: the
    ion needs no ``resolve_assumed_ion`` fallback at all, only a Landé g."""
    instrument = neutron()
    truth = candidate_named("P n m a", MN_SITE, (0, 0, 0), A_TYPE_BNS)
    data = simulate(
        stated_re("Dy3+", "Dy3+", truth, (3.5, 0.0, 0.0), DY_G), instrument)
    return nuclear_fit(perovskite_re(species="Dy3+"), data, instrument), data, truth


@pytest.fixture(scope="module")
def dy_bare_element():
    """A 4f site whose nuclear species is the bare element (``"Dy"``, no
    neutral-atom ⟨j0⟩ row at all) — needs both the ``resolve_assumed_ion``
    fallback and the Landé g default."""
    instrument = neutron()
    truth = candidate_named("P n m a", MN_SITE, (0, 0, 0), A_TYPE_BNS)
    data = simulate(
        stated_re("Dy", "Dy3+", truth, (3.5, 0.0, 0.0), DY_G), instrument)
    return nuclear_fit(perovskite_re(species="Dy"), data, instrument), data, truth


@pytest.mark.slow
def test_a_charged_rare_earth_species_defaults_g_and_recovers_the_moment(
        dy_charged_type):
    """stage3 D1's majority shape: the nuclear species already names the ion
    and only the Landé g is missing — and it was not the caller who named
    that ion, so the g default fires (issue #257 A5's exemption does not
    apply to an ion nobody but the structure itself stated)."""
    ref, data, truth = dy_charged_type
    solution = rx.solve_magnetic(ref, data)

    assert solution.verdict == "solved", solution.reason
    assert solution.best.bns_number == truth.bns_number
    assert solution.best.moments[0].ion == "Dy3+"
    assert solution.best.moments[0].magnitude == pytest.approx(3.5, abs=0.4)
    codes = {d.code for d in solution.diagnostics}
    assert "LANDE_G_ASSUMED" in codes
    assert "MAGNETIC_ION_ASSUMED" not in codes  # the ion was already stated
    lande = next(d for d in solution.diagnostics if d.code == "LANDE_G_ASSUMED")
    assert lande.value == pytest.approx(DY_G)
    assert "Dy1" not in lande.message  # the label is RE1, not a stale copy


@pytest.mark.slow
def test_a_bare_rare_earth_element_resolves_through_the_cif_readers_own_fallback(
        dy_bare_element):
    """stage3 D1's second shape: a bare 4f element with no neutral-atom row
    at all resolves through the same ``resolve_assumed_ion`` the CIF reader
    already applies at read, and its Landé g defaults alongside it."""
    ref, data, truth = dy_bare_element
    solution = rx.solve_magnetic(ref, data)

    assert solution.verdict == "solved", solution.reason
    assert solution.best.bns_number == truth.bns_number
    assert solution.best.moments[0].ion == "Dy3+"
    codes = {d.code for d in solution.diagnostics}
    assert {"MAGNETIC_ION_ASSUMED", "LANDE_G_ASSUMED"} <= codes
    ion_diag = next(d for d in solution.diagnostics if d.code == "MAGNETIC_ION_ASSUMED")
    assert "Dy3+" in ion_diag.message
    assert "moment_ions" not in ion_diag.message  # solve_magnetic's own route
    assert "ion={'RE1'" in ion_diag.suggestion.replace('"', "'")


@pytest.mark.slow
def test_a_caller_stated_ion_still_needs_an_explicit_g_issue_257_a5(dy_charged_type):
    """A caller who names the ion explicitly gets the pre-existing refusal,
    unchanged: the g default is only for an ion this call inferred itself
    (from the table or from ``resolve_assumed_ion``), never for one the
    caller stated — mirroring issue #257 A5's rule for
    ``structure_from_cif``'s ``moment_ions=``.  Every candidate class fails
    to build (the g requirement is a validation error, not a raise from this
    function), so the verdict is a workflow abstention naming why, exactly
    stage3's own measured shape."""
    ref, data, _truth = dy_charged_type
    solution = rx.solve_magnetic(ref, data, sites=["RE1"], ion="Dy3+")

    assert solution.verdict == "abstained"
    assert "Landé g factor" in solution.reason, solution.reason
    assert all(t.status == "refused" and "4f/5f ion" in (t.refusal or "")
              for t in solution.trials)
    codes = {d.code for d in solution.diagnostics}
    assert "LANDE_G_ASSUMED" not in codes


@pytest.mark.slow
def test_a_caller_stated_g_wins_over_the_hunds_rule_default(dy_charged_type):
    """A caller-passed ``g=`` always wins, even when it differs from the
    Hund's-rule default — the same "caller wins" rule ``ion=`` already had."""
    ref, data, _truth = dy_charged_type
    off_g = DY_G + 0.2
    solution = rx.solve_magnetic(ref, data, g=off_g)

    assert solution.verdict == "solved", solution.reason
    codes = {d.code for d in solution.diagnostics}
    assert "LANDE_G_ASSUMED" not in codes  # the caller stated it; not defaulted
    assert solution.best is not None


@pytest.mark.slow
def test_a_3d_ion_never_sees_the_g_default_bit_identical(a_type):
    """Bit-identity for every non-4f/5f case: the g/ion plumbing this brief
    added must never fire a diagnostic, or change a result, for the existing
    Mn3+ fixture every other test in this file already exercises."""
    ref, data, _truth = a_type
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    codes = {d.code for d in solution.diagnostics}
    assert "LANDE_G_ASSUMED" not in codes
    assert "MAGNETIC_ION_ASSUMED" not in codes


@pytest.mark.slow
def test_the_g_default_also_threads_through_the_k_nonzero_supercell_route():
    """The k = 0 route (``_state_k0``) and the k ≠ 0 route
    (``magnetic_supercell``) are two different code paths threading g into
    the candidate's ``Moment`` — this exercises the second one, mirroring
    ``test_a_class_the_powder_cannot_separate_is_refined_once_and_named``'s
    own P4/mmm, k = (0,0,½) fixture with the site's ion swapped for a bare
    4f element."""
    from rietx.crystallography.magnetic.supercell import magnetic_supercell

    instrument = neutron()
    truth = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]

    def dy_tetragonal(species="Dy", moment=None, magnetic=None) -> Phase:
        return Phase(
            name="tetragonal_re", space_group="P 4/m m m", cell=_cell(4.0, 4.0, 4.2),
            atoms=[_atom("RE1", species, (0.0, 0.0, 0.0), moment=moment),
                   _atom("O1", "O", (0.5, 0.5, 0.5), biso=0.6)],
            magnetic_symmetry=magnetic)

    statement = magnetic_supercell(dy_tetragonal(species="Dy3+"), truth,
                                   magnetic_species=["RE1"], ion={"RE1": "Dy3+"},
                                   g=DY_G, magnitude=3.0)
    data = simulate(statement.phase, instrument)
    ref = nuclear_fit(dy_tetragonal(species="Dy"), data, instrument)
    solution = rx.solve_magnetic(ref, data)

    assert solution.k == ("0", "0", "1/2")
    assert solution.verdict == "solved", solution.reason
    codes = {d.code for d in solution.diagnostics}
    assert {"MAGNETIC_ION_ASSUMED", "LANDE_G_ASSUMED"} <= codes


# ============================================== the unnamed parent (stage3 D2)
#
# solve_magnetic used to refuse outright whenever the nuclear parent's group
# was a bracketed, unnamed label — "no Hermann-Mauguin symbol generates this
# group in its cell" — on the stated grounds that the small representations
# of a k-vector come from tables keyed on the space-group *number*, and an
# operator list has none.  That reasoning does not hold for this engine (D-1,
# COMMON.md: every small irrep is built from the little group's own
# operators, projectively, with no tabulated-number lookup anywhere in
# ``crystallography.magnetic.irreps``/``isotropy``), so the parent's group is
# now resolved from its operators via the same ``OperatorGroup``
# ``Phase.symmetry_operations`` uses everywhere else, and threaded through
# instead of refusing before either candidate enumeration or the k ≠ 0
# supercell statement is tried.

#: Pnma's own tabulated operator list (gemmi), carried under a bracketed
#: label as if no symbol named it — a synthetic non-standard-setting stand-in
#: (mirroring the magcif-fix-20260917 report's own synthetic Ima2 fixture):
#: the mechanism under test is "an explicit operator list with no resolvable
#: symbol", and this operator list is real Pnma, independently checked back
#: to it by ``resolve_group(...).operations()`` matching gemmi's own table.
def _pnma_operations() -> tuple[str, ...]:
    import gemmi

    return tuple(op.triplet() for op in
                gemmi.find_spacegroup_by_name("P n m a").operations())


UNNAMED_PNMA = unnamed_label("P n m a", "unnamed for a stage3 D2 synthetic test")


def perovskite_unnamed(moment=None, magnetic=None) -> Phase:
    """``perovskite()``, restated with its own operators under a bracketed,
    unnamed label — the WP-1328 escape-hatch shape ``structure_from_cif``
    already writes for a real setting mismatch, built synthetically here."""
    return Phase(
        name="perovskite_unnamed", space_group=UNNAMED_PNMA,
        symmetry_operations=list(_pnma_operations()),
        cell=_cell(5.74, 7.70, 5.54),
        atoms=[_atom("A1", "La", (0.05, 0.25, 0.99)),
               _atom("Mn1", "Mn", MN_SITE, moment=moment),
               _atom("O1", "O", (0.48, 0.25, 0.07)),
               _atom("O2", "O", (0.31, 0.04, 0.72))],
        magnetic_symmetry=magnetic)


@pytest.fixture(scope="module")
def a_type_unnamed_parent():
    """``a_type``'s own A-type Pnma structure, with the nuclear parent stated
    as an unnamed operator list instead of the symbol ``"P n m a"``."""
    instrument = neutron()
    parent_group = resolve_group(UNNAMED_PNMA, _pnma_operations())
    truth = candidate_named(parent_group, MN_SITE, (0, 0, 0), A_TYPE_BNS)
    ops, cent = truth.group.xyz_strings()
    truth_phase = perovskite_unnamed(
        moment=Moment.from_values((3.5, 0.0, 0.0), "Mn3+"),
        magnetic=MagneticSymmetry(operations=list(ops), centerings=list(cent)))
    data = simulate(truth_phase, instrument)
    return nuclear_fit(perovskite_unnamed(), data, instrument), data, truth


@pytest.mark.slow
def test_an_unnamed_bracketed_parent_still_enumerates_and_recovers(
        a_type_unnamed_parent):
    """The positive arm: candidate enumeration, the k = 0 statement and the
    ranking all still work when the parent's group is a bracketed, unnamed
    operator list rather than a symbol gemmi resolves."""
    ref, data, truth = a_type_unnamed_parent
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")

    assert solution.verdict == "solved", solution.reason
    assert solution.best.bns_number == truth.bns_number
    assert solution.best.moments[0].magnitude == pytest.approx(3.5, abs=0.4)
    assert solution.space_group == UNNAMED_PNMA


def test_refuse_an_unnamed_parent_would_have_stopped_it_here(
        a_type_unnamed_parent):
    """Negative control: the refusal solve_magnetic used to call still exists
    and still fires on exactly this phase, proving the positive arm's success
    is the fix and not a phase that was never actually unnamed."""
    ref, _data, _truth = a_type_unnamed_parent
    parent = ref.fitted_structure.phases[0]
    with pytest.raises(ValueError, match="label"):
        refuse_an_unnamed_parent(parent, "solve_magnetic()")


@pytest.mark.slow
def test_an_unnamed_parent_also_threads_through_the_k_nonzero_supercell_route():
    """The k ≠ 0 route (``magnetic_supercell``) had its *own* copy of the same
    refusal — this exercises that second call site, mirroring
    ``test_a_class_the_powder_cannot_separate_is_refined_once_and_named``'s
    P4/mmm, k = (0,0,½) fixture with the parent's group stated as an unnamed
    operator list."""
    import gemmi

    from rietx.crystallography.magnetic.supercell import magnetic_supercell

    instrument = neutron()
    ops = tuple(op.triplet() for op in
               gemmi.find_spacegroup_by_name("P 4/m m m").operations())
    label = unnamed_label("P 4/m m m", "unnamed for a stage3 D2 synthetic test")
    parent_group = resolve_group(label, ops)
    truth = candidates(parent_group, (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]

    def tetragonal_unnamed(moment=None, magnetic=None) -> Phase:
        return Phase(
            name="tetragonal_unnamed", space_group=label,
            symmetry_operations=list(ops), cell=_cell(4.0, 4.0, 4.2),
            atoms=[_atom("Mn1", "Mn", (0.0, 0.0, 0.0), moment=moment),
                   _atom("O1", "O", (0.5, 0.5, 0.5), biso=0.6)],
            magnetic_symmetry=magnetic)

    statement = magnetic_supercell(tetragonal_unnamed(), truth,
                                   magnetic_species=["Mn1"], ion={"Mn1": "Mn3+"},
                                   magnitude=3.0)
    data = simulate(statement.phase, instrument)
    ref = nuclear_fit(tetragonal_unnamed(), data, instrument)
    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")

    assert solution.k == ("0", "0", "1/2")
    assert solution.verdict == "solved", solution.reason
    assert solution.best.bns_number == truth.bns_number


# =========================================================================
# WP-1418: the two negative-margin sweep entries (stage (a)); a kernel/
# general-direction candidate's seed (stage (b)); the descent audit after
# selection (stage (c)); the group-subgroup lattice among near-ties (d).
# =========================================================================

def _solution(trials, tied, verdict, why, tie_width=SOLVE_TIE_DELTA_BIC):
    """The minimum ``MagneticSolution`` a ``_rank`` output needs to exercise
    ``.margin``/``__str__`` without running the whole ``solve_magnetic`` chain."""
    return MagneticSolution(
        verdict=verdict, reason=why, criterion="test", phase="p",
        space_group="P 1", k=("0", "0", "0"), k_route="given by the caller",
        k_reason="test", k_candidates=(), sites=("Mn1",),
        n_residual_peaks=0, n_on_nuclear_lines=0,
        n_on_forbidden_lattice_points=0, n_unexplained=0,
        trials=trials, tied=tied, tie_width=tie_width, d_min=1.5,
        nuclear_rwp=None, nuclear_gof=None, nuclear_r_magnetic=None,
        n_magnetic_channels=0)


# ------------------------------------------------------- stage (a): margin --

def test_margin_is_the_true_gap_between_two_eligible_classes():
    winner = _trial(0, delta_bic=200.0, r_mag=0.1, free=2, bns="1.1")
    runner_up = _trial(1, delta_bic=140.0, r_mag=0.2, free=1, bns="1.2")
    ordered, tied, verdict, why = _rank((winner, runner_up), SOLVE_TIE_DELTA_BIC, 0.02)
    assert _solution(ordered, tied, verdict, why).margin == pytest.approx(60.0)


def test_margin_is_none_not_negative_when_the_second_row_is_disqualified():
    """The mechanism behind the two negative-margin sweep entries, ``0.37``
    and ``0.710`` (``checks/MAGNDATA_SWEEP_STAGE3_20260918.md``).
    ``MagneticSolution.trials`` is eligible classes (best ΔBIC first) **then**
    the disqualified ``rest``, each sorted by its own raw ΔBIC — so an
    unsupported model that happens to fit the noise better than the true
    winner (a real possibility: BIC alone does not know the null test
    disqualified it) sorts second and carries a *higher* raw ΔBIC.  A naive
    ``trials[0].delta_bic - trials[1].delta_bic`` diff against it is negative;
    ``_rank`` never considered that class a competitor in the first place, and
    ``.margin`` says so by returning ``None``, never a negative number.
    """
    winner = _trial(0, delta_bic=225.0, r_mag=0.1, free=8, bns="5.13")
    disqualified = _trial(1, delta_bic=533.0, r_mag=0.1, free=8, bns="5.15",
                          supported=False)
    ordered, tied, verdict, why = _rank((winner, disqualified),
                                        SOLVE_TIE_DELTA_BIC, 0.02)
    assert verdict == "solved"
    assert ordered[0].bns_number == "5.13"
    assert ordered[1].bns_number == "5.15"
    naive_margin = ordered[0].delta_bic - ordered[1].delta_bic
    assert naive_margin < 0.0, "this is the bug's own shape, reproduced"
    assert _solution(ordered, tied, verdict, why).margin is None


def test_margin_is_none_on_an_abstention():
    tied_trials = (_trial(0, delta_bic=10.0, r_mag=0.1, free=1, bns="1.1"),
                  _trial(1, delta_bic=9.0, r_mag=0.1, free=1, bns="1.2"))
    ordered, tied, verdict, why = _rank(tied_trials, SOLVE_TIE_DELTA_BIC, 0.02)
    assert verdict == "abstained"
    assert _solution(ordered, tied, verdict, why).margin is None


# ------------------------------------------------- stage (b): the seed tilt --

def test_a_rank_one_basis_seed_is_untouched_by_the_tilt():
    """Negative control: a single-copy, one-amplitude basis (the ordinary
    case, every site this workflow refined before WP-1418) is bit-identical
    to the pre-fix seed, whatever the tilt."""
    basis = [[1, 0, 0]]
    cell = (4.0, 4.0, 4.2, 90.0, 90.0, 90.0)
    old = tilted_seed(basis, cell, 3.0, tilt=0.0)
    new = tilted_seed(basis, cell, 3.0, tilt=SEED_TILT)
    assert np.allclose(old, new)
    assert np.allclose(new, [3.0, 0.0, 0.0])


def test_a_rank_two_basis_seed_moves_every_row_and_keeps_the_modulus():
    """The bug's own shape: tilt = 0 places nothing at all on the second row
    — the angle DOF then starts at exactly the value of pointing along the
    first, WP-1418's stationary-point mechanism.  ``SEED_TILT`` does not, and
    the modulus is exactly what was asked for either way (the frame is
    metric-orthonormal by construction, so a unit-Euclidean-norm coefficient
    vector gives a unit modulus automatically)."""
    basis = [[1, 0, 0], [0, 1, 0]]
    cell = (4.0, 4.0, 4.2, 90.0, 90.0, 90.0)
    old = tilted_seed(basis, cell, 3.0, tilt=0.0)
    new = tilted_seed(basis, cell, 3.0, tilt=SEED_TILT)
    assert old[1] == pytest.approx(0.0, abs=1e-12)
    assert abs(new[1]) > 1e-3
    assert np.linalg.norm(old) == pytest.approx(3.0)
    assert np.linalg.norm(new) == pytest.approx(3.0)


def test_warm_seed_keeps_the_preferred_direction_and_tilts_the_rest():
    """``warm_seed`` (stage (c)'s own seed): anchored on a caller-given
    direction rather than the basis's own row 0, for warm-starting a subgroup
    refit from a supergroup's converged moment."""
    basis = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    cell = (5.0, 5.0, 5.0, 90.0, 90.0, 90.0)
    preferred = (0.0, 4.0, 0.0)
    seed = warm_seed(basis, cell, preferred)
    assert np.linalg.norm(seed) == pytest.approx(4.0)
    cos_to_preferred = float(np.dot(seed, preferred) / (4.0 * 4.0))
    assert cos_to_preferred > 0.97        # mostly along the preferred direction
    assert seed[0] != 0.0 and seed[2] != 0.0    # the other two rows still tilted


def test_warm_seed_falls_back_to_the_ordinary_seed_at_zero_preferred():
    """An atom whose winner moment was itself ~zero has nothing to anchor
    on; it still gets a real (nonzero) seed rather than staying at zero."""
    basis = [[1, 0, 0], [0, 1, 0]]
    cell = (5.0, 5.0, 5.0, 90.0, 90.0, 90.0)
    seed = warm_seed(basis, cell, (0.0, 0.0, 0.0))
    assert np.linalg.norm(seed) > 0.0


@pytest.mark.slow
def test_the_pre_fix_seed_leaves_a_general_direction_stuck_at_its_special_case(
       monkeypatch):
    """WP-1418 stage (b), the mechanism verified end to end, not only inside
    ``tilted_seed`` itself.  P4/mmm's own S10 irrep at (0,0,0) gives a genuine
    general direction ("(a,b)", BNS 10.46, rank 2 at this atom) whose
    stabiliser is a real operator-list subgroup of the special direction's
    ("(a)", BNS 47.252, rank 1) — verified directly, not asserted.  Refit from
    a pattern simulated at a genuinely general moment (both components
    nonzero, neither along a symmetry axis), the pre-fix seed (tilt = 0,
    monkeypatched) never moves the second component off exactly zero; the fix
    does.

    **What this test does not claim.**  It does not claim the fit reaches a
    lower χ² with the fix — measured directly, Rwp is bit-identical either
    way (to 1e-6): the equivalence machinery already merges 47.252/65.486/
    10.46 into one powder-equivalence class
    (``analyse(candidates("P 4/m m m", (0,0,0), (0,0,0)))``, smallest first)
    before ``solve_magnetic`` ever refines the general one on its own — the
    same residual symmetry that pins the second DOF at zero is what makes the
    direction powder-degenerate, so failing to explore it costs nothing here.
    Flagged in the report rather than overclaimed: this session did not find
    a case where the fix changes a ranking outcome, only where it changes
    what the *reported direction* honestly says.
    """
    instrument = neutron()
    general = candidate_named("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, 0), "10.46")
    special = candidate_named("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, 0), "47.252")
    ops_g, _ = general.group.xyz_strings()
    ops_s, _ = special.group.xyz_strings()
    assert set(ops_g) < set(ops_s), "10.46 must be a genuine subgroup of 47.252"
    truth_xyz = tuple(float(v) for v in general.moments([2.4, 0.9])[0])
    data = simulate(stated(tetragonal, general, truth_xyz), instrument, seed=20260918)
    magnetic = [(0, "Mn1", "Mn3+")]
    plan = rx.RefinementPlan(stages=[rx.Stage(
        "moment", ["phases.*.atoms.*.moment.dof*", "phases.*.scale",
                  "instrument.background.c*"])])

    def refit(tilt):
        monkeypatch.setattr(_magnetic_module, "SOLVE_SEED_TILT", tilt)
        child = _magnetic_module._state_k0(tetragonal(), general, magnetic,
                                          _magnetic_module.SOLVE_SEED_MU_B, {})
        structure = rx.Structure(phases=[child])
        return _magnetic_module._fit(structure, instrument, data, plan)

    ref_stuck, stuck = refit(0.0)
    ref_fixed, fixed = refit(SEED_TILT)
    assert ref_stuck.fitted_structure.phases[0].atoms[0].moment.crystalaxis_y.value \
        == pytest.approx(0.0, abs=1e-9)
    assert abs(ref_fixed.fitted_structure.phases[0].atoms[0].moment
              .crystalaxis_y.value) > 1e-3
    assert stuck.statistics.rwp == pytest.approx(fixed.statistics.rwp, abs=1e-6)


# --------------------------------------------- stage (c): the descent audit --

def test_maximal_subgroups_finds_a_genuine_operator_list_subgroup():
    cs = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, 0))
    by_bns = {c.bns_number: c for c in cs}
    winner = by_bns["47.252"]
    classes = [((c.label,), c, "Mn1") for c in
              (by_bns["65.486"], by_bns["10.46"], by_bns["123.345"])]
    found = _maximal_subgroups(winner, classes)
    assert [c.bns_number for _i, _m, c, _s in found] == ["10.46"]


def test_maximal_subgroups_drops_one_nested_inside_another_found_one():
    """A genuine three-level chain (F m -3 m at (0,0,0), S4's own directions):
    the fully general direction (BNS 2.4) is a subgroup of one of the two
    ``12.62`` domains (verified directly), which is itself a subgroup of the
    winner (71.536) — ``2.4`` must not be reported, since refitting it would
    only repeat what the larger ``12.62`` subgroup already tests.  The other
    ``12.62`` domain is *not* a subgroup of this particular winner (a
    different domain of the same label, verified directly) and must not be
    reported either — ``_maximal_subgroups`` only ever returns genuine
    subgroups, whatever else shares a class's bare label.
    """
    cs = candidates("F m -3 m", (0.0, 0.0, 0.0), (0, 0, 0))
    winner = next(c for c in cs if c.bns_number == "71.536")
    twelves = [c for c in cs if c.bns_number == "12.62"]
    general = next(c for c in cs if c.bns_number == "2.4")
    ops_g, _ = general.group.xyz_strings()
    ops_t0, _ = twelves[0].group.xyz_strings()
    ops_t1, _ = twelves[1].group.xyz_strings()
    ops_w, _ = winner.group.xyz_strings()
    assert set(ops_g) < set(ops_t0), "2.4 must nest inside twelves[0]"
    assert set(ops_t0) < set(ops_w), "twelves[0] must be a genuine subgroup of the winner"
    assert not set(ops_t1) < set(ops_w), "twelves[1] must not be"
    classes = [((c.label,), c, "site") for c in (*twelves, general)]
    found = _maximal_subgroups(winner, classes)
    assert len(found) == 1
    assert found[0][2] is twelves[0]


@pytest.mark.slow
def test_descend_reports_a_subgroup_and_does_not_let_it_win_on_noise():
    """The negative control the brief itself names: a pattern simulated from
    the *true* special direction (BNS 71.536, F m -3 m at (0,0,0)) must not
    have its subgroup (BNS 12.62, one extra free amplitude) beat it beyond
    the tie width once refit from the winner's own solution — the extra
    freedom has nothing real to buy on this data."""
    instrument = neutron()
    cs = candidates("F m -3 m", (0.0, 0.0, 0.0), (0, 0, 0))
    winner_candidate = next(c for c in cs if c.bns_number == "71.536")
    sub_candidate = next(c for c in cs if c.bns_number == "12.62")

    def cubic(moment=None, magnetic=None) -> Phase:
        return Phase(
            name="cubic", space_group="F m -3 m", cell=_cell(4.0, 4.0, 4.0),
            atoms=[_atom("Mn1", "Mn", (0.0, 0.0, 0.0), moment=moment),
                   _atom("O1", "O", (0.25, 0.25, 0.25), biso=0.6)],
            magnetic_symmetry=magnetic)

    magnetic = [(0, "Mn1", "Mn3+")]
    plan = rx.RefinementPlan(stages=[rx.Stage(
        "moment", ["phases.*.atoms.*.moment.dof*", "phases.*.scale",
                  "instrument.background.c*"])])
    truth_xyz = tuple(float(v) for v in winner_candidate.moments([3.0])[0])
    data = simulate(stated(cubic, winner_candidate, truth_xyz), instrument,
                    seed=20260918)

    child = _magnetic_module._state_k0(cubic(), winner_candidate, magnetic,
                                      _magnetic_module.SOLVE_SEED_MU_B, {})
    winner_ref, winner_result = _magnetic_module._fit(
        rx.Structure(phases=[child]), instrument, data, plan)
    winner_trial = MagneticTrial(
        class_index=0, representative=winner_candidate.label,
        members=(winner_candidate.label,), site="Mn1",
        irrep=winner_candidate.irrep_label,
        direction=winner_candidate.direction.label,
        bns_number=winner_candidate.bns_number, uni_number=None, msg_type=1,
        free_amplitudes=winner_candidate.free_amplitudes,
        determinable_amplitudes=1, status="refined",
        rwp=float(winner_result.statistics.rwp),
        gof=float(winner_result.statistics.gof), delta_bic=999.0,
        r_magnetic=None, n_moment_parameters=1,
        n_free_parameters=int(winner_result.statistics.n_free_parameters),
        _structure=winner_ref.fitted_structure, _result=winner_result)
    classes = [((sub_candidate.label,), sub_candidate, "Mn1")]

    audits, note, diagnostics = _descend(
        cubic(), winner_trial, winner_candidate, classes, magnetic, {},
        plan, instrument, data, None, SOLVE_TIE_DELTA_BIC, True)

    assert len(audits) == 1, audits
    assert audits[0].bns_number == "12.62"
    assert audits[0].status == "refined", audits[0].refusal
    assert audits[0].delta_bic_over_winner is not None
    assert audits[0].delta_bic_over_winner <= SOLVE_TIE_DELTA_BIC
    assert ("no subgroup beats the winner" in note
           or "no subgroup supported" in note), note
    assert diagnostics == ()


def test_descend_is_not_attempted_off_k_equals_zero():
    audits, note, diagnostics = _descend(
        None, None, None, [], [], {}, None, None, None, None,
        SOLVE_TIE_DELTA_BIC, False)
    assert audits == ()
    assert "only a k = 0 statement is warm-started" in note
    assert diagnostics == ()


# --------------------------------------- stage (d): the tie-width lattice ---

def _cubic_phase(moment=None, magnetic=None) -> Phase:
    return Phase(
        name="cubic", space_group="F m -3 m", cell=_cell(4.0, 4.0, 4.0),
        atoms=[_atom("Mn1", "Mn", (0.0, 0.0, 0.0), moment=moment),
               _atom("O1", "O", (0.25, 0.25, 0.25), biso=0.6)],
        magnetic_symmetry=magnetic)


def _trial_with_structure(index, candidate, free=1):
    ops, cent = candidate.group.xyz_strings()
    moment_xyz = tuple(float(v) for v in
                       candidate.moments([1.0] * candidate.free_amplitudes)[0])
    phase = _cubic_phase(moment=Moment.from_values(moment_xyz, "Mn3+"),
                         magnetic=MagneticSymmetry(operations=list(ops),
                                                   centerings=list(cent)))
    structure = rx.Structure(phases=[phase])
    return MagneticTrial(
        class_index=index, representative=f"S{index}(a)",
        members=(f"{candidate.bns_number} S{index}(a)",), site="Mn1",
        irrep=f"S{index}", direction="(a)", bns_number=candidate.bns_number,
        uni_number=None, msg_type=1, free_amplitudes=free,
        determinable_amplitudes=1, status="refined",
        rwp=0.1, gof=1.0, delta_bic=100.0, r_magnetic=0.1,
        n_moment_parameters=free, n_free_parameters=free + 5,
        moments=(MomentRow(label="Mn1", ion="Mn3+", magnitude=3.0, esd=0.1,
                           crystalaxis=moment_xyz, supported=True),),
        _structure=structure)


def test_tie_lattice_lines_names_a_subgroup_and_an_unrelated_pair():
    """Data only, per the brief: no new ranking rule, just which tied class
    is a subgroup of which, read off the operator lists the trials
    themselves already carry (``trial._structure``)."""
    cs = candidates("F m -3 m", (0.0, 0.0, 0.0), (0, 0, 0))
    top = next(c for c in cs if c.bns_number == "71.536")
    sub = next(c for c in cs if c.bns_number == "12.62")
    other = next(c for c in cs if c.bns_number == "166.101")
    t0 = _trial_with_structure(0, top, free=1)
    t1 = _trial_with_structure(1, sub, free=2)
    t2 = _trial_with_structure(2, other, free=1)

    lines = _tie_lattice_lines((t0, t1, t2), (0, 1, 2))

    subgroup_lines = [line for line in lines if "subgroup of class 0" in line and "class 1" in line]
    assert subgroup_lines, lines
    unrelated_lines = [line for line in lines if "class 2" in line and "unrelated" in line]
    assert unrelated_lines, lines


def test_the_tie_lattice_appears_in_str_only_for_a_genuine_tie():
    cs = candidates("F m -3 m", (0.0, 0.0, 0.0), (0, 0, 0))
    top = next(c for c in cs if c.bns_number == "71.536")
    sub = next(c for c in cs if c.bns_number == "12.62")
    t0 = _trial_with_structure(0, top, free=1)
    t1 = _trial_with_structure(1, sub, free=2)
    tied_solution = _solution((t0, t1), (0, 1), "abstained", "tied for test")
    assert "descent among the tied classes" in str(tied_solution)
    solved_solution = _solution((t0,), (0,), "solved", "solo for test")
    assert "descent among the tied classes" not in str(solved_solution)
