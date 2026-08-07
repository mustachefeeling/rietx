"""WP-1024 — consensus, the confidence gate, and the shape of the answer.

Four kinds of claim, and they are not interchangeable:

* **the API shape** — that a confident wrong singleton is *unspellable*.  This is
  the milestone's founding rule and it is tested against the type rather than
  against a message: no ``.cell``, no ``.best``, and ``best_or_none()`` returning
  ``None`` under every gate failure.  A docstring asking for the rule would not be
  a test of it;
* **the gate** — each caveat's effect on the verdict, exercised on hand-built
  candidates so every branch is covered without a search;
* **the detectors** — that the whole-profile Le Bail fit separates a correct cell
  from an oversized one, with the measured numbers pinned, because the module's
  reasoning rests on them;
* **the restriction** — that a search over three systems cannot be read as a
  statement about the specimen.  Measured on this repo's own data, a restricted
  engine's coverage bands overlap between single-phase low-symmetry patterns and a
  genuine mixture, and a multiphase claim built on that ambiguity was withdrawn;
  this test is that retraction made permanent.

Every search here declares ``sigma_sys_deg`` explicitly.  The peak lists carry
*exact* positions, so the systematic allowance the engines assume for real data
(``DEFAULT_UNKNOWN_SHIFT_DEG``) is pure looseness — and it would also change what
is being measured, since it caps confidence on its own.  Declaring the physics
rather than inheriting a default is the rule (DESIGN.md §Testing & validation
policy).
"""

from __future__ import annotations

import numpy as np
import pytest

from pxrdref import IndexingResult, index_pattern
from pxrdref.crystallography.symmetry import generate_reflections
from pxrdref.indexing.consensus import (
    CONSENSUS_CHECK_TOP,
    caveats_for,
    checked_indices,
    grade,
)
from pxrdref.indexing.engines import SearchSpec, engine_names
from pxrdref.indexing.workflow import (
    _restrict_to_supported,
    absent_reflections,
    structure_from_candidate,
    validate_by_lebail,
)
from pxrdref.schemas.indexing import (
    INDEX_REFUTING_CAVEATS,
    PEAK_MIN_USABLE_LINES,
    BravaisOpinion,
    CellCandidate,
    FigureOfMerit,
    IndexCaveat,
    LeBailValidation,
    PeakList,
)

pytestmark = pytest.mark.xdist_group("indexing-consensus")

LAM = 1.5405929
TRUE_A = 4.1566
#: 2θ range of the synthetic pattern every measured number here is quoted at.
#: 145° rather than 100° for a reason the data-quality gate enforces: a cubic cell
#: shows 15 lines to 100° and 23 to 145°, and below
#: ``PEAK_MIN_USABLE_LINES = 20`` the list cannot be *scored* — the classical
#: figures leave the panel and the ``fom_panel_reduced`` caveat caps confidence
#: (WP-1043) — so a shorter pattern tests the reduced-panel path rather than
#: the scored one this module's numbers are quoted on.
TT_MAX = 145.0


# ----------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------
def _peak_list(cell, group="P m -3 m", *, esd_deg=0.005, two_theta_max=TT_MAX):
    refl = generate_reflections(group, cell, LAM, two_theta_max)
    tt = np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d))))
    return PeakList.from_positions(np.sort(tt), LAM, two_theta_esd=esd_deg)


@pytest.fixture(scope="module")
def cubic_peaks():
    return _peak_list((TRUE_A,) * 3 + (90.0,) * 3)


@pytest.fixture(scope="module")
def lab6_pattern():
    """A noisy LaB₆ powder pattern from the true model — the shared protocol.

    Module-scoped and pinned to one xdist worker (see ``pytestmark``) because the
    Le Bail validations below each cost a refinement: a second worker rebuilding
    this would cost more than the sharing saved (CLAUDE.md, the ``--durations``
    rule).
    """
    from pxrdref.model.forward import compile_model
    from pxrdref.params.vector import ParameterTable
    from pxrdref.schemas.pattern import PatternData

    structure, instrument = _true_models()
    tt = np.arange(15.0, TT_MAX, 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(11).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _true_models():
    from pxrdref.schemas.instrument import BackgroundChebyshev, Instrument
    from pxrdref.schemas.structure import (
        Atom,
        Cell,
        Parameter,
        Phase,
        Structure,
    )

    structure = Structure(phases=[Phase(
        name="LaB6", space_group="P m -3 m", cell=Cell.cubic(TRUE_A),
        scale=Parameter(value=5e-4, min=0.0, transform="softplus"),
        atoms=[
            Atom(label="La", species="La", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="B", species="B", x=Parameter(value=0.1993),
                 y=Parameter(value=0.5), z=Parameter(value=0.5))])])
    instrument = Instrument.debye_scherrer(wavelength=LAM)
    instrument.profile.w.value = 5e-3
    instrument.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (30.0, -4.0, 1.0)])
    return structure, instrument


def _instrument():
    return _true_models()[1]


def _candidate(a: float, **over) -> CellCandidate:
    """A hand-built candidate that passes the gate unless ``over`` breaks it."""
    fields = dict(
        cell=(a, a, a, 90.0, 90.0, 90.0), cell_esd=(1e-5,) * 6, system="cubic",
        centring="P", lattice_group="P m -3 m", volume=a ** 3,
        n_indexed=23, n_lines=23,
        fom=[FigureOfMerit(name="indexed_fraction", value=1.0, n_lines=23,
                           n_possible=28, k_sigma=3.0)],
        found_by=sorted(engine_names()),
        bravais=BravaisOpinion(system="cubic", system_loosest="cubic",
                               system_gemmi="cubic", system_spglib="cubic"),
        lebail=LeBailValidation(rwp=0.2, gof=1.3, space_group="P m -3 m",
                                n_reflections=28))
    fields.update(over)
    return CellCandidate(**fields)


def _gate(cand, **over):
    kw = dict(engines_run=sorted(engine_names()), panel_disagrees=False,
              validated=True, search_complete={"cubic": True},
              shift_allowance_assumed=False, checked=True)
    kw.update(over)
    caveats = caveats_for(cand, **kw)
    return caveats, grade(caveats, cand.found_by, kw["engines_run"])


# ----------------------------------------------------------------------
# the API shape — the milestone's founding rule
# ----------------------------------------------------------------------
def test_the_result_type_has_no_singleton_accessor():
    """No ``.cell``, no ``.best``, no ``.solution`` — on the *class*.

    Asserted against the type because that is where the rule lives: the same
    species of guard as ``Geometry.mu_r`` being a plain float so refining it is
    unspellable.  A caller's discipline is not what holds here.
    """
    for forbidden in ("cell", "best", "solution", "unit_cell"):
        assert forbidden not in IndexingResult.model_fields
        assert not hasattr(IndexingResult, forbidden)
    assert "candidates" in IndexingResult.model_fields
    assert callable(IndexingResult.best_or_none)


@pytest.mark.parametrize("break_it,expect", [
    ({}, "high"),
    ({"found_by": ["dichotomy"]}, "low"),
    ({"lebail": None}, "medium"),
    ({"lebail": LeBailValidation(rwp=0.4, gof=2.4, space_group="P m -3 m",
                                 n_reflections=153, predicted_but_absent=117)},
     "low"),
    ({"lebail": LeBailValidation(rwp=float("inf"), gof=float("inf"),
                                 space_group="P m -3 m", n_reflections=0,
                                 status="failed")}, "low"),
    ({"fom": [FigureOfMerit(name="indexed_fraction", value=0.5, n_lines=23,
                            n_possible=28, k_sigma=3.0)]}, "low"),
    ({"volume": 1.0}, "low"),
    ({"bravais": BravaisOpinion(system="tetragonal", system_loosest="cubic",
                                system_gemmi="tetragonal",
                                system_spglib="tetragonal", ambiguous=True)},
     "medium"),
])
def test_best_or_none_is_none_under_every_gate_failure(break_it, expect):
    """One candidate, one broken precondition, and the singleton disappears.

    The parametrisation is the gate's specification read as a table: ``high``
    needs *everything*, a refuting caveat means ``low``, a capping one means
    ``medium`` — and only ``high`` reaches ``best_or_none()``.
    """
    cand = _candidate(TRUE_A, **break_it)
    caveats, verdict = _gate(cand)
    assert verdict == expect, caveats
    cand.confidence, cand.confidence_caveats = verdict, caveats
    result = _result([cand])
    assert (result.best_or_none() is not None) is (expect == "high")


def _result(candidates) -> IndexingResult:
    from pxrdref.schemas.common import Provenance

    return IndexingResult(candidates=candidates, engines_run=sorted(engine_names()),
                          systems_searched=["cubic"], search_complete={"cubic": True},
                          validated=True, provenance=Provenance(package_version="t"))


def test_two_high_candidates_are_not_a_singleton():
    """Two cells that both pass everything is exactly when a lesser API would
    return the first one."""
    a, b = _candidate(TRUE_A), _candidate(2 * TRUE_A)
    for cand in (a, b):
        cand.confidence = "high"
    result = _result([a, b])
    assert result.best_or_none() is None
    from pxrdref.indexing.diagnostics import index_diagnostics

    codes = {d.code for d in index_diagnostics(result)}
    assert "INDEX_MULTIPLE_SOLUTIONS" in codes
    assert "INDEX_ABSTAINED" in codes


def test_an_ambiguous_winner_is_not_a_singleton():
    """``best_or_none`` re-checks the ambiguity the gate already checked.

    Deliberate redundancy: this method is the single place the rule is
    *guaranteed*, so it does not delegate the guarantee to whoever filled the
    field.
    """
    from pxrdref.schemas.indexing import AmbiguityPartner

    cand = _candidate(TRUE_A)
    cand.confidence = "high"
    assert _result([cand]).best_or_none() is not None
    cand.ambiguity = [AmbiguityPartner(
        cell=(2 * TRUE_A,) * 3 + (90.0,) * 3,
        transformation=[[2, 0, 0], [0, 1, 0], [0, 0, 1]], index=2,
        system="triclinic", volume=8 * TRUE_A ** 3)]
    assert _result([cand]).best_or_none() is None


# ----------------------------------------------------------------------
# the gate
# ----------------------------------------------------------------------
def test_the_caveat_vocabulary_is_closed_and_the_split_is_a_subset():
    """``INDEX_REFUTING_CAVEATS`` must name only real caveats.

    A refuting set that drifted from the vocabulary would silently stop refuting:
    a typo'd member is never in a candidate's caveat list, so nothing would ever
    be demoted by it and no test of the *gate* would notice.
    """
    from typing import get_args

    members = set(get_args(IndexCaveat))
    assert INDEX_REFUTING_CAVEATS <= members
    assert members - INDEX_REFUTING_CAVEATS, "some caveats must merely cap"


def test_an_assumed_tolerance_caps_confidence_on_its_own():
    """The measured reason: a cell found inside a widened window absorbs the
    shift (+1400 ppm on a certified pattern), so an *assumed* allowance is not a
    neutral setting — and the way to clear it is evidence, not a constant."""
    cand = _candidate(TRUE_A)
    caveats, verdict = _gate(cand, shift_allowance_assumed=True)
    assert caveats == ["shift_allowance_assumed"]
    assert verdict == "medium"
    assert _gate(cand)[1] == "high"


def test_a_reduced_panel_caps_confidence_on_its_own():
    """WP-1043: below the scoring bar the ranking stands and ``high`` does not —
    the same reachability the old abstention gave unattended use, kept without
    refusing the search.  Capping rather than refuting, because a short list is
    not evidence *against* a cell."""
    cand = _candidate(TRUE_A)
    caveats, verdict = _gate(cand, panel_reduced=True)
    assert caveats == ["fom_panel_reduced"]
    assert verdict == "medium"
    assert "fom_panel_reduced" not in INDEX_REFUTING_CAVEATS


def test_an_unchecked_candidate_cannot_reach_high():
    """Not enumerating the ambiguity is not the same as finding none.

    The expensive checks run on a subset, so a candidate outside it has an
    unasked question, and an unasked question must not read as a clean answer.
    """
    cand = _candidate(TRUE_A)
    caveats, verdict = _gate(cand, checked=False)
    assert "geometric_ambiguity" in caveats
    assert verdict == "low"


def test_an_incomplete_search_caps_the_systems_it_did_not_finish():
    cand = _candidate(TRUE_A)
    caveats, verdict = _gate(cand, search_complete={"cubic": False})
    assert caveats == ["search_incomplete"] and verdict == "medium"


def test_a_single_engine_is_never_agreement():
    """Even with nothing to qualify: one search is one opinion."""
    cand = _candidate(TRUE_A, found_by=["dichotomy"])
    caveats, verdict = _gate(cand)
    assert caveats == ["engines_disagree"] and verdict == "low"


def test_the_expensive_checks_cover_every_promotable_candidate():
    """The cap on cost must not become a cap on the answer.

    ``checked_indices`` is the top few *plus* every candidate the engines agree
    on — because that second set is the only kind the gate can promote, so
    skipping one would quietly make ``high`` unreachable for it.
    """
    cands = [_candidate(4.0 + 0.1 * i, found_by=["dichotomy"])
             for i in range(8)]
    cands[6].found_by = sorted(engine_names())
    idx = checked_indices(cands, sorted(engine_names()), top=CONSENSUS_CHECK_TOP)
    assert idx[:CONSENSUS_CHECK_TOP] == list(range(CONSENSUS_CHECK_TOP))
    assert 6 in idx, "a candidate both engines found must always be checked"
    assert 7 not in idx


# ----------------------------------------------------------------------
# the detectors
# ----------------------------------------------------------------------
def test_structure_from_candidate_carries_a_dummy_atom_and_no_absences():
    """Both footguns, asserted rather than only documented.

    The absence-free default is the load-bearing half: a group with reflection
    conditions would excuse an oversized cell's phantom reflections as
    extinctions, which is precisely how such a cell passes validation.
    """
    structure = structure_from_candidate(_candidate(TRUE_A))
    phase = structure.phases[0]
    assert phase.space_group == "P m -3 m"          # holohedry, no conditions
    assert len(phase.atoms) == 1                    # Phase._nonempty needs one
    assert phase.cell.a.value == pytest.approx(TRUE_A)

    centred = _candidate(TRUE_A, centring="F", lattice_group="")
    assert structure_from_candidate(centred).phases[0].space_group == "F m -3 m"


def test_absent_reflections_reads_the_fitted_background():
    """The detector on hand-made arrays: one position with a peak, one without."""
    tt = np.arange(20.0, 25.0, 0.01)
    bkg = np.full_like(tt, 100.0)
    y = bkg + 500.0 * np.exp(-0.5 * ((tt - 21.0) / 0.05) ** 2)
    sigma = np.sqrt(y)
    absent, ratio = absent_reflections(tt, y, bkg, sigma,
                                       np.array([21.0, 23.0]),
                                       np.array([0.12, 0.12]))
    assert absent == [23.0]
    assert ratio[0] < 3.0
    # a position outside the fitted range is *not* evidence of absence
    assert absent_reflections(tt, y, bkg, sigma, np.array([40.0]),
                              np.array([0.12]))[0] == []


@pytest.mark.parametrize("factor,expect_absent,expect_unmatched", [
    (1.0, 0, 0),                     # the truth
    (2.0, "most", 0),                # doubled cell: the oversized signature
    (1.01, 0, "many"),               # wrong metric: caught from the other side
])
def test_le_bail_validation_separates_the_failure_modes(lab6_pattern, factor,
                                                        expect_absent,
                                                        expect_unmatched):
    """The measurement the module's reasoning rests on, pinned.

    Read it by column rather than by row: Rwp is decisive on a wrong *metric* and
    nearly silent on an *oversized* cell, where only ``predicted_but_absent``
    sees it; the wrong metric is caught instead by ``unmatched_observed``.  That
    is why all three travel together and why none of them is the score.

    The bars are qualitative on purpose (``most``, ``many``) — the exact counts
    are noise-seed-dependent and quoted in the module docstring, whereas what must
    not regress is the *separation*.
    """
    validation = validate_by_lebail(_candidate(TRUE_A * factor), lab6_pattern,
                                   _instrument())
    assert validation.status == "converged"
    if expect_absent == 0:
        assert validation.predicted_but_absent == 0
    else:
        assert validation.predicted_but_absent > 0.5 * validation.n_reflections
    if expect_unmatched == 0:
        assert validation.unmatched_observed == 0
    else:
        assert validation.unmatched_observed > 20
    assert len(validation.predicted_but_absent_two_theta) == \
        validation.predicted_but_absent


def test_layer0_unmatched_calc_cannot_serve_as_the_absent_detector(lab6_pattern):
    """The plan's own mechanism, measured false and pinned so it is not retried.

    Le Bail extraction sets each intensity from ``max(y_obs − y_bkg, 0)``, so a
    reflection predicted where there is nothing gets nothing and leaves **no
    negative residual to detect**; what Layer 0 finds instead is 5σ noise
    excursions near a tick.  It fires on the majority of the *certified* cell's
    reflections, which is the whole content of this test.
    """
    from pxrdref.refine import Refinement
    from pxrdref.report.layer0 import build_layer0

    cand = _candidate(TRUE_A)
    ref = Refinement(structure_from_candidate(cand), _instrument(), history=False)
    from pxrdref.indexing.workflow import validation_plan

    result = ref.fit(lab6_pattern, mode="lebail",
                     plan=validation_plan(cand, _instrument()))
    layer0 = build_layer0(result)
    n_calc = len([u for u in layer0.unmatched if u.kind == "unmatched_calc"])
    n_refl = len([r for r in ref.reflection_table() if r.line == 0])
    assert n_calc > 0.4 * n_refl, (
        "if this ever separates a correct cell from an oversized one, "
        "re-measure before reaching for it — it did not in WP-1024")
    assert validate_by_lebail(cand, lab6_pattern,
                              _instrument()).predicted_but_absent == 0


# ----------------------------------------------------------------------
# end to end
# ----------------------------------------------------------------------
def test_index_pattern_recovers_the_cell_and_refutes_its_supercells(lab6_pattern):
    """The closed loop, picking its own peaks: pattern in, gated cell out."""
    result = index_pattern(
        data=lab6_pattern, instrument=_instrument(),
        spec=SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                        max_volume=1500.0, budget_seconds=120.0,
                        sigma_sys_deg=1e-9))
    best = result.best_or_none()
    assert best is not None, [c.confidence_caveats for c in result.candidates]
    assert best.cell[0] == pytest.approx(TRUE_A, abs=2e-4)
    assert best.confidence == "high"
    assert sorted(best.found_by) == sorted(engine_names())
    assert best.lebail is not None and best.lebail.predicted_but_absent == 0
    assert result.validated and result.search_complete == {"cubic": True}
    assert result.provenance.notes["engines"] == ", ".join(engine_names())

    # the supercells that index every observed line are refuted by the pattern,
    # not by the panel — this is the blind spot validation exists to close.
    # Only the checked subset carries a verdict: validation costs a refinement
    # each, so the rest must say **not_validated** rather than look clean, and
    # that half of the claim is the one a widening candidate list can break.
    supercells = [c for c in result.candidates if c.volume > 2 * best.volume]
    assert supercells, "the F/I supercells should be proposed and then refuted"
    tested = [c for c in supercells if c.lebail is not None]
    assert tested, "no supercell reached validation at all"
    for cand in supercells:
        assert cand.confidence == "low"
        if cand.lebail is None:
            assert "not_validated" in cand.confidence_caveats
            continue
        assert "predicted_but_absent" in cand.confidence_caveats
        assert any(d.code == "INDEX_PREDICTED_BUT_ABSENT"
                   for d in cand.diagnostics)


def test_a_peaks_only_run_abstains_by_declaration(cubic_peaks):
    """No pattern ⇒ no whole-profile test ⇒ nothing reaches ``high``.

    The *result* abstains rather than one field being quietly downgraded, which is
    why ``INDEX_NOT_VALIDATED`` is a result-level diagnostic and not a note on a
    candidate.
    """
    result = index_pattern(
        cubic_peaks,
        spec=SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                        max_volume=1500.0, budget_seconds=120.0,
                        sigma_sys_deg=1e-9))
    assert result.candidates and result.best_or_none() is None
    assert not result.validated
    top = result.candidates[0]
    assert top.cell[0] == pytest.approx(TRUE_A, abs=2e-3)
    assert top.confidence == "medium"
    assert top.confidence_caveats == ["not_validated"]
    codes = {d.code for d in result.diagnostics}
    assert {"INDEX_NOT_VALIDATED", "INDEX_ABSTAINED"} <= codes


def test_a_short_clean_list_is_searched_ranked_and_capped():
    """The fluorite defect in miniature (WP-1043): fifteen clean cubic lines
    are fifteen-fold over-determined for a one-parameter metric, and the
    pre-1043 gate refused to search them because twenty is where the classical
    figures are *scored*.  Now the search runs — restricted to the systems
    ``MIN_LINES_PER_DOF`` supports — the reduced panel ranks, each absent
    figure carries its reason, and the ``fom_panel_reduced`` caveat caps the
    grade instead of a refusal standing in front of the answer."""
    peaks = _peak_list((TRUE_A,) * 3 + (90.0,) * 3, two_theta_max=100.0)
    assert len(peaks.usable()) < PEAK_MIN_USABLE_LINES
    result = index_pattern(
        peaks, spec=SearchSpec(systems=("cubic", "monoclinic"), min_d_axis=2.0,
                               max_d_axis=12.0, max_volume=1500.0,
                               budget_seconds=120.0, sigma_sys_deg=1e-9))
    # searched, not abstained — and only where the line count supports it:
    # monoclinic needs 20 lines at 5 per DOF, so the request is narrowed
    assert result.quality.supports_indexing
    assert result.systems_searched == ["cubic"]
    codes = {d.code for d in result.diagnostics}
    assert "INDEX_DATA_INSUFFICIENT" not in codes
    assert "INDEX_PANEL_REDUCED" in codes
    # ranked by the reduced panel, the truth first, reasons on the report
    assert result.candidates
    top = result.candidates[0]
    assert top.cell[0] == pytest.approx(TRUE_A, abs=2e-3)
    names = [f.name for f in top.fom]
    assert "m20" not in names and "f_n" not in names
    assert "indexed_fraction" in names
    assert set(result.quality.fom_undefined) == {"m20", "f_n"}
    # capped, uniformly: the grade is a field on the answer, not a gate in
    # front of it — and ``high`` stays exactly as unreachable as before
    for cand in result.candidates:
        assert "fom_panel_reduced" in cand.confidence_caveats
    assert result.best_or_none() is None

    # the evidence view agrees with the result it projects, by construction
    ev = result.evidence()
    assert ev.fom_undefined == result.quality.fom_undefined
    assert set(ev.fom_ranked) == set(names)
    assert set(ev.candidates[0].fom) == set(ev.fom_ranked)
    assert all(any(c.name == "fom_panel_reduced" and c.kind == "capping"
                   for c in cand.caveats)
               for cand in ev.candidates)


def test_restriction_honors_an_explicit_unsupported_request():
    """Two edges of :func:`_restrict_to_supported`, asserted on the function.

    A caller whose declared systems share *nothing* with the supported set is
    not silently handed an empty search — the same never-overridden rule as
    ``_adopt_measured_shift`` — and at or above the scoring bar the spec is
    untouched even when a declared system is under-determined, because that is
    the measured pre-1043 behaviour every acceptance row was quoted on."""
    from types import SimpleNamespace

    below_bar = SimpleNamespace(fom_undefined={"m20": "…", "f_n": "…"},
                                systems_supported=["cubic", "tetragonal"])
    no_overlap = SearchSpec(systems=("monoclinic",))
    assert _restrict_to_supported(no_overlap, below_bar) is no_overlap

    at_bar = SimpleNamespace(fom_undefined={},
                             systems_supported=["cubic"])
    unrestricted = SearchSpec()
    assert _restrict_to_supported(unrestricted, at_bar) is unrestricted

    overlap = SearchSpec(systems=("cubic", "monoclinic"))
    assert _restrict_to_supported(overlap, below_bar).systems == ("cubic",)


def test_the_evidence_view_is_a_projection_with_caveat_kinds():
    """WP-1043: the gate's inputs, serialized — not a second copy of them.

    The refuting/capping split lived only in ``INDEX_REFUTING_CAVEATS``, a
    package constant no JSON consumer can see, so the serialized answer could
    name ``predicted_but_absent`` and ``not_validated`` in the same list
    without saying that one argues against the cell and the other only says a
    question was never asked.  ``evidence()`` computes the view from the live
    fields on each call, so the two representations cannot disagree."""
    from typing import get_args

    from pxrdref.refine import _VERSION
    from pxrdref.schemas.common import Provenance
    from pxrdref.schemas.indexing import IndexingEvidence

    refuted = _candidate(
        TRUE_A, confidence="low",
        confidence_caveats=["predicted_but_absent", "not_validated"],
        lebail=LeBailValidation(rwp=0.379, gof=2.1, space_group="P m -3 m",
                                n_reflections=153, predicted_but_absent=117,
                                unmatched_observed=0))
    unreached = _candidate(
        4.9, confidence="medium", confidence_caveats=["fom_panel_reduced"],
        lebail=None, fom=[])
    result = IndexingResult(
        candidates=[refuted, unreached], engines_run=sorted(engine_names()),
        systems_searched=["cubic"], search_complete={"cubic": True},
        validated=True, wavelength=LAM, n_usable_lines=17,
        provenance=Provenance(package_version=_VERSION,
                              created_utc="2026-08-07T00:00:00Z"))

    ev = result.evidence()
    assert [c.index for c in ev.candidates] == [0, 1]
    kinds = {c.name: c.kind for c in ev.candidates[0].caveats}
    assert kinds == {"predicted_but_absent": "refuting",
                     "not_validated": "capping"}
    assert ev.candidates[1].caveats[0].kind == "capping"

    # the three whole-profile figures travel together, and an unreached
    # validation is None — absent for cause, never zero
    first = ev.candidates[0]
    assert (first.validated, first.lebail_rwp, first.predicted_but_absent,
            first.unmatched_observed) == (True, 0.379, 117, 0)
    second = ev.candidates[1]
    assert (second.validated, second.lebail_rwp, second.predicted_but_absent,
            second.unmatched_observed) == (False, None, None, None)

    # panel membership comes from the first candidate that carries one
    assert ev.fom_ranked == [f.name for f in refuted.fom]
    assert ev.candidates[0].fom == {f.name: f.value for f in refuted.fom}
    assert ev.systems_searched == ["cubic"]

    # every member of the closed vocabulary gets a kind, and the partition is
    # exactly the refuting constant — so a new caveat cannot arrive unkinded
    all_caveats = _candidate(TRUE_A,
                             confidence_caveats=sorted(get_args(IndexCaveat)))
    every = {c.name: c.kind
             for c in IndexingResult(
                 candidates=[all_caveats], provenance=result.provenance,
             ).evidence().candidates[0].caveats}
    assert {n for n, k in every.items() if k == "refuting"} \
        == set(INDEX_REFUTING_CAVEATS)

    # the view is a schema: it survives the JSON round trip intact
    assert IndexingEvidence.model_validate_json(ev.model_dump_json()) == ev


def test_a_restricted_search_is_not_a_verdict_about_the_specimen():
    """A search over three systems says nothing about the other four.

    This is the withdrawn multiphase claim made permanent.  Measured (tag
    ``guillemot-study``, check C): a two-parameter engine scores 47-60 % on
    single-phase orthorhombic/monoclinic patterns, 82-100 % on genuinely
    tetragonal or hexagonal ones and 69 % on a real mixture — **the bands
    overlap**, so a coverage score cannot tell a multiphase pattern from a
    single-phase one of lower symmetry than the engine reaches.  So the report
    names what it did not search, and nothing anywhere claims a second phase.
    """
    peaks = _peak_list((7.0, 8.0, 9.0, 90.0, 90.0, 90.0), "P m m m",
                       two_theta_max=45.0)
    common = dict(min_d_axis=2.0, max_d_axis=12.0, max_volume=1500.0,
                  budget_seconds=180.0, sigma_sys_deg=1e-9)

    restricted = index_pattern(
        peaks, spec=SearchSpec(systems=("cubic", "tetragonal", "hexagonal"),
                               **common))
    assert "orthorhombic" not in restricted.systems_searched
    assert set(restricted.systems_searched) == {"cubic", "tetragonal",
                                               "hexagonal"}
    not_covered = next(d for d in restricted.diagnostics
                       if d.code == "INDEX_SYSTEMS_NOT_COVERED")
    assert "orthorhombic" in not_covered.where

    # **No code means "multiphase", and codes are what an agent branches on.**
    # Asserted on the vocabulary rather than by scanning the prose, because the
    # prose deliberately *contains* the word — INDEX_SYSTEMS_NOT_COVERED's own
    # suggestion warns against exactly this reading, and a text scan cannot tell a
    # warning from a claim.
    codes = ({d.code for d in restricted.diagnostics}
             | {d.code for c in restricted.candidates for d in c.diagnostics})
    assert codes, "a restricted search must say what it did not cover"
    assert not any("PHASE" in code for code in codes), codes
    assert restricted.best_or_none() is None

    # the same list, with the right system in scope: the cell is there all along
    found = index_pattern(peaks, spec=SearchSpec(systems=("orthorhombic",),
                                                 **common))
    assert found.candidates, "the orthorhombic truth must be reachable"
    axes = sorted(found.candidates[0].cell[:3])
    assert axes == pytest.approx([7.0, 8.0, 9.0], abs=2e-3)
