"""WP-1041 — the indexing gallery's renderers, and the opt-in that feeds them.

``tests/CLAUDE.md`` carries a standing rule that every test refinement writes
obs/calc/diff PNGs for visual inspection, and until this WP the whole indexing
tree was its one exception: ``grep -n "savefig"`` across ``src/pxrdref/indexing/``
returned nothing.

**What is asserted here is what each renderer *drew*, never a recomputation of the
same numbers.**  That is the rule WP-1029 (s) bought with a real bug — a panel
labelled its curve ``(obs−calc)/σ`` while the σ behind it had never been measured,
and every test that recomputed the residual agreed with the renderer because both
were wrong in the same way.  So the candidate rows are read back off the axes and
compared with the panel the *ranking* saw.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pxrdref.crystallography.symmetry import generate_reflections
from pxrdref.indexing.engines import SearchSpec, match_window, to_cell_candidate
from pxrdref.indexing.trial_error import search_trial_error
from pxrdref.schemas.indexing import PeakList

OUT = Path(__file__).parent / "output"
LAM = 1.5405929
#: A body-centred cubic list: the truth predicts few lines and shows all of them,
#: and the search also returns supercells that predict a forest.  That contrast is
#: the whole content of :func:`~pxrdref.viz.indexing.plot_candidates`, so it is
#: what the fixture has to contain.
CELL = (6.2, 6.2, 6.2, 90.0, 90.0, 90.0)


@pytest.fixture(scope="module")
def bcc_peaks() -> PeakList:
    refl = generate_reflections("I m -3 m", CELL, LAM, 90.0)
    tt = np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d))))
    inten = np.asarray(refl.multiplicity, dtype=np.float64)
    order = np.argsort(tt)
    return PeakList.from_positions(tt[order], LAM, intensity=inten[order],
                                   two_theta_esd=0.01)


@pytest.fixture(scope="module")
def bcc_candidates(bcc_peaks):
    spec = SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                      max_volume=1500.0, sigma_sys_deg=1e-9,
                      budget_seconds=120.0)
    result = search_trial_error(bcc_peaks, spec=spec)
    return [to_cell_candidate(c, bcc_peaks, k_sigma=spec.k_sigma,
                              n_unindexed=spec.n_unindexed)
            for c in result.candidates[:5]]


def test_the_peak_list_picture_separates_a_line_flag_from_a_list_property(
        bcc_peaks):
    """``sigma_assumed`` is a property of the list, not of a line.

    Every entry of a ``from_positions`` list carries it, so counting it as a
    per-line flag paints the whole list as suspect and prints "clean (0)" on a
    list with nothing wrong with it.  It belongs in the title, said once.
    """
    from pxrdref.viz import plot_peak_list

    OUT.mkdir(exist_ok=True)
    fig = plot_peak_list(bcc_peaks, path=str(OUT / "indexing_peaks_bcc.png"))
    ax = fig.get_axes()[0]
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert any(f"clean ({len(bcc_peaks.usable())})" == v for v in labels), labels
    assert not any(v.startswith("flagged") for v in labels), labels
    assert "assumed, not measured" in ax.get_title()


def test_the_candidate_rows_show_both_directions(bcc_candidates, bcc_peaks):
    """A supercell's row is mostly hollow and the truth's is solid — drawn, not
    asserted from a recomputation.

    The ticks are read back off the axes: a *solid* tick is a predicted line with
    an observed line under it and a faint one is a prediction with nothing there,
    so "indexes everything by predicting a forest" — the measured false positive
    the whole FoM panel exists to catch — is a property of the picture rather
    than of a caption.
    """
    from pxrdref.viz import plot_candidates
    from pxrdref.viz.indexing import CANDIDATE_COLORS

    truth = [c for c in bcc_candidates
             if c.centring == "I" and abs(c.cell[0] - CELL[0]) < 1e-3]
    forest = [c for c in bcc_candidates if c.volume > 3.0 * truth[0].volume]
    assert truth and forest, "the fixture must contain a truth and a supercell"

    OUT.mkdir(exist_ok=True)
    fig = plot_candidates(bcc_candidates, bcc_peaks,
                          path=str(OUT / "indexing_candidates_bcc.png"))
    axt = fig.get_axes()[1]

    # two collections per row: the seen ticks then the absent ones
    rows = [c for c in axt.collections]
    assert len(rows) == 2 * len(bcc_candidates)
    seen_n = [len(rows[2 * i].get_segments()) for i in range(len(bcc_candidates))]
    absent_n = [len(rows[2 * i + 1].get_segments())
                for i in range(len(bcc_candidates))]

    i_truth = bcc_candidates.index(truth[0])
    assert absent_n[i_truth] == 0, (
        "the true lattice predicts nothing the pattern lacks, so its row must "
        "carry no faint ticks")
    i_forest = bcc_candidates.index(forest[0])
    assert absent_n[i_forest] > seen_n[i_forest], (
        f"the supercell row drew {seen_n[i_forest]} seen and "
        f"{absent_n[i_forest]} absent: a forest must look like one")

    # The caption's *drawn* count is the ticks, and its *share* is the panel's
    # own ``predicted_seen_fraction`` rather than a recomputation.  The two
    # enumerate over different ranges by design — the panel stops at the last
    # observed line and the picture covers the axis it draws — so a caption that
    # recomputed the share printed a number a few points off the one the
    # candidate was ranked on (measured on 11-BM NAC: 43 % drawn against the
    # panel's 46 %), in a figure whose whole claim is that it agrees with the
    # panel.  Both halves are asserted, because only quoting one lets the other
    # drift.
    captions = [t.get_text() for t in axt.texts]
    assert len(captions) == len(bcc_candidates)
    total = seen_n[i_truth] + absent_n[i_truth]
    assert f"({total} drawn)" in captions[i_truth], captions[i_truth]
    panel_share = truth[0].fom_value("predicted_seen_fraction")
    assert f"{panel_share:.0%} of predicted lines seen" in captions[i_truth], (
        captions[i_truth])
    # rank order fixes the colour, so two galleries of one dataset compare
    assert rows[0].get_color()[0].tolist()[:3] == pytest.approx(
        _rgb(CANDIDATE_COLORS[0]), abs=1e-6)


def _rgb(hex_colour: str) -> list[float]:
    from matplotlib.colors import to_rgb

    return list(to_rgb(hex_colour))


#: The same lattice displaced by a constant 0.04° 2θ, with a per-line σ ten times
#: smaller — corundum's situation in miniature (there the two are 0.0045° and a
#: 0.05° allowance, an 11× gap).  A search *must* open its window to the
#: systematic to find anything, so the window and the measurement genuinely
#: differ, which is what makes this fixture able to tell them apart.
SHIFTED_DEG = 0.04
SHIFTED_ESD = 0.004
SHIFTED_ALLOWANCE = 0.05


@pytest.fixture(scope="module")
def shifted_peaks() -> PeakList:
    refl = generate_reflections("I m -3 m", CELL, LAM, 90.0)
    tt = np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d))))
    inten = np.asarray(refl.multiplicity, dtype=np.float64)
    order = np.argsort(tt)
    return PeakList.from_positions(tt[order] + SHIFTED_DEG, LAM,
                                   intensity=inten[order],
                                   two_theta_esd=SHIFTED_ESD)


@pytest.fixture(scope="module")
def shifted_search(shifted_peaks):
    spec = SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                      max_volume=1500.0, sigma_sys_deg=SHIFTED_ALLOWANCE,
                      budget_seconds=120.0)
    result = search_trial_error(shifted_peaks, spec=spec)
    cands = [to_cell_candidate(c, shifted_peaks, k_sigma=spec.k_sigma,
                               n_unindexed=spec.n_unindexed,
                               q_match=match_window(shifted_peaks, spec))
             for c in result.candidates[:3]]
    return cands, spec


def test_the_tick_rows_match_in_the_window_the_search_used(shifted_search,
                                                           shifted_peaks):
    """The picture's own legend must not contradict the label beside it.

    ``plot_candidates`` asks *is this the same line* once per prediction, and
    CLAUDE.md's rule is that the answer depends on the **matching window**, not
    on the per-line σ: a search that had to open its window to a systematic
    selected its candidate under the wide one, so re-asking under the narrow one
    judges it by a criterion it was never selected under.

    Measured, this was not a subtlety.  On 11-BM NAC — which carries the default
    0.05° allowance — the figure labelled its top row ``224/285 indexed`` from
    the candidate's own field and drew ``not indexed by #1 (213)`` in the same
    legend, a direct contradiction inside one picture.  Here the two counts are
    asserted to close against the observed total, in both directions: with the
    search's window they agree, and with the raw σ they do not — which is what
    makes this a test of the window rather than of arithmetic.
    """
    from pxrdref.viz import plot_candidates

    cands, spec = shifted_search
    best = cands[0]
    n_obs = len(shifted_peaks.usable())
    OUT.mkdir(exist_ok=True)

    fig = plot_candidates(cands, shifted_peaks,
                          q_match=match_window(shifted_peaks, spec),
                          path=str(OUT / "indexing_candidates_shifted.png"))
    missed = _missed_count(fig)
    assert missed is not None, "the top row indexed everything; no window to test"
    assert best.n_indexed + missed == n_obs, (
        f"the figure drew {missed} unindexed against a label claiming "
        f"{best.n_indexed} of {n_obs} indexed")

    # and the defect this replaced: the raw σ is 10x narrower than the window
    # the search used, so it refuses lines the candidate was selected on
    narrow = plot_candidates(cands, shifted_peaks,
                             q_match=shifted_peaks.q_esd())
    assert _missed_count(narrow) > missed, (
        "the raw-σ window found no more unindexed lines than the search's — "
        "this fixture no longer separates the two")


def _missed_count(fig) -> int:
    """The ``not indexed by #1 (N)`` the figure actually drew, 0 when absent."""
    labels = [t.get_text() for t in fig.get_axes()[0].get_legend().get_texts()]
    for text in labels:
        if text.startswith("not indexed by #1"):
            return int(text.split("(")[1].rstrip(")"))
    return 0


# ----------------------------------------------------------------------
# the gallery's declaration tables, and the one test the scoreboard turns on
# ----------------------------------------------------------------------
def test_every_gallery_table_names_a_declared_dataset():
    """Four tables key on the same stems; a typo in one silently drops a row.

    ``DATASETS`` says what a dataset is, ``PAGE_ORDER`` places it,
    ``TRUTHS`` gives it a known cell and ``SCOREBOARD_STEMS`` counts it.  A
    scoreboard stem with no truth is the dangerous one: its verdict computes as
    ``unknown``, so it silently leaves the count instead of failing — which is
    the same class of defect as the arithmetic this scoreboard replaced.
    """
    from tests import indexing_gallery as g

    assert set(g.PAGE_ORDER) == set(g.DATASETS), (
        set(g.PAGE_ORDER) ^ set(g.DATASETS))
    assert len(g.PAGE_ORDER) == len(set(g.PAGE_ORDER)), "duplicate in PAGE_ORDER"
    assert set(g.TRUTHS) <= set(g.DATASETS), set(g.TRUTHS) - set(g.DATASETS)
    assert set(g.SCOREBOARD_STEMS) <= set(g.TRUTHS), (
        f"{set(g.SCOREBOARD_STEMS) - set(g.TRUTHS)} would be counted as "
        "'unknown' and vanish from the scoreboard rather than fail")


def test_an_undeclared_dataset_cannot_reach_the_gallery(bcc_peaks):
    """``draw`` raises on an unknown stem rather than writing an unlabelled card.

    A silent skip is what puts a dataset in the suite and not in the summary,
    which is precisely how the scoreboard came to describe nine datasets under a
    total of eight.
    """
    from tests import indexing_gallery as g

    with pytest.raises(KeyError, match="no entry"):
        g.draw("a_dataset_nobody_declared", peaks=bcc_peaks)


def test_the_truth_test_is_the_lattice_and_the_centring(bcc_candidates):
    """Two centrings of one metric are two lattices, and only one is the truth.

    ``same_lattice`` compares Niggli-reduced A..F, so it *deliberately* calls a
    setting change equality — and a primitive description of a centred lattice
    reduces to the same metric.  Without the centring clause both NAC candidates
    scored as the truth on identical axes, and the scoreboard would have counted
    a wrong answer as right.  The same lesson is recorded one rank down in
    ``engines.solution_key`` and one rank up in WP-1040's monoclinic row.
    """
    from pxrdref.indexing.qspace import af_from_cell
    from tests import indexing_gallery as g

    af = [float(v) for v in af_from_cell(CELL)]
    ranking = [{"centring": "P", "af": af, "cell": list(CELL)},
               {"centring": "I", "af": af, "cell": list(CELL)}]
    assert "lab6" in g.TRUTHS, "this test needs a declared cubic truth"

    original = g.TRUTHS["lab6"]
    try:
        g.TRUTHS["lab6"] = (CELL, "I", 1e-3)
        assert g.truth_rank("lab6", ranking) == 2, (
            "the P row reduces to the same metric; matching it would read a "
            "wrong centring as the truth")
        g.TRUTHS["lab6"] = (CELL, "P", 1e-3)
        assert g.truth_rank("lab6", ranking) == 1
    finally:
        g.TRUTHS["lab6"] = original

    assert g.truth_rank("no_such_stem", ranking) is None


def test_the_truth_band_is_tighter_than_the_dedup_tolerance():
    """A cell inside ``same_lattice``'s fallback and outside its dataset's band
    is **not** the truth, and FAP is the dataset that says so.

    ``CELL_EQUALITY_RELATIVE`` is 5e-3, deliberately loose so a dedup comparison
    is never *tightened* by the absence of a covariance.  Reused as a truth test
    it calls FAP's +966 ppm leader and its +258 ppm cross-code cell the same
    lattice — and the scoreboard then reports "ranked first" for the one dataset
    whose acceptance row asserts the cross-code cell is *not* first.
    """
    from pxrdref.indexing.qspace import af_from_cell
    from pxrdref.indexing.reduce import CELL_EQUALITY_RELATIVE
    from tests import indexing_gallery as g

    cell, _centring, rtol = g.TRUTHS["fap"]
    assert rtol < CELL_EQUALITY_RELATIVE, (
        f"FAP's band {rtol} is not tighter than the dedup fallback "
        f"{CELL_EQUALITY_RELATIVE}; the truth test cannot separate its "
        "candidates")

    off = (cell[0] * 1.000966, cell[1] * 1.000966, cell[2] * 1.000266,
           *cell[3:])
    good = (cell[0] * 1.000258, cell[1] * 1.000258, cell[2] * 1.000325,
            *cell[3:])
    ranking = [{"centring": "P", "af": [float(v) for v in af_from_cell(c)],
                "cell": list(c)} for c in (off, good)]
    assert g.truth_rank("fap", ranking) == 2, (
        "the +966 ppm leader was accepted as the truth; FAP's row says it is "
        "the +258 ppm cell that is the cross-code answer")


def test_an_ungated_candidate_is_not_labelled_with_a_verdict(bcc_candidates,
                                                             bcc_peaks):
    """``confidence`` defaults to ``"low"``, so printing it unconditionally puts
    a verdict in a picture that nothing had reached.

    This is the gallery's version of the ``validation_matrix`` caution these
    plots were written under: an artefact must not state more than the run behind
    it measured.
    """
    from pxrdref.viz import plot_candidates

    fig = plot_candidates(bcc_candidates, bcc_peaks)
    captions = [t.get_text() for t in fig.get_axes()[1].texts]
    assert not any("[low]" in c for c in captions), captions

    gated = bcc_candidates[0].model_copy(
        update={"confidence": "medium",
                "confidence_caveats": ["shift_allowance_assumed"]})
    fig2 = plot_candidates([gated], bcc_peaks)
    caption = fig2.get_axes()[1].texts[0].get_text()
    assert "[medium: shift_allowance_assumed]" in caption, caption


def test_validate_by_lebail_hands_back_the_result_it_already_built(
        bcc_peaks, tmp_path):
    """The WP's one structural change, and the default it must not disturb.

    ``validate_by_lebail`` builds a whole ``RefinementResult`` and discarded it
    two lines before returning, consuming it only for scalars — so a real
    obs/calc/diff panel of the fit behind the gate was impossible to draw.  The
    return is opt-in rather than a field on ``LeBailValidation`` for the reason
    history nodes store state and not curves.
    """
    from pxrdref.indexing.workflow import validate_by_lebail
    from pxrdref.schemas.indexing import CellCandidate
    from pxrdref.schemas.results import RefinementResult

    data, instrument = _bcc_pattern()
    cand = CellCandidate(cell=CELL, cell_esd=(1e-4,) * 6, system="cubic",
                         centring="I", lattice_group="I m -3 m",
                         volume=float(CELL[0] ** 3), volume_esd=1e-3,
                         af=(1.0 / CELL[0] ** 2,) * 3 + (0.0,) * 3,
                         n_indexed=len(bcc_peaks.usable()),
                         n_lines=len(bcc_peaks.usable()), chi2_red=1.0)

    plain = validate_by_lebail(cand, data, instrument, peaks=bcc_peaks)
    assert not isinstance(plain, tuple), "the default return shape must not move"

    validation, result = validate_by_lebail(cand, data, instrument,
                                            peaks=bcc_peaks, with_result=True)
    assert isinstance(result, RefinementResult)
    assert validation.rwp == pytest.approx(result.statistics.rwp)
    assert len(result.two_theta) == len(result.y_calc)

    from pxrdref.viz import plot_validation

    OUT.mkdir(exist_ok=True)
    fig = plot_validation(validation, result,
                          path=str(OUT / "indexing_lebail_bcc.png"))
    ax = fig.get_axes()[0]
    assert f"Rwp={validation.rwp:.4f}" in ax.get_title()
    assert len(fig.get_axes()) == 2, "the Δ/σ panel is not optional"

    # and it still draws something without a result, which is the degraded view
    bare = plot_validation(validation)
    assert len(bare.get_axes()) == 1


def _bcc_pattern():
    """A forward-modelled pattern for the fixture cell — cheap and single-phase."""
    from pxrdref.model.forward import compile_model
    from pxrdref.params.vector import ParameterTable
    from pxrdref.schemas.instrument import Instrument
    from pxrdref.schemas.pattern import PatternData
    from pxrdref.schemas.structure import Atom, Cell, Parameter, Phase, Structure

    a = CELL[0]
    structure = Structure(phases=[Phase(
        name="bcc", space_group="I m -3 m",
        cell=Cell(a=Parameter(value=a), b=Parameter(value=a),
                  c=Parameter(value=a), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Fe", species="Fe", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0),
                    biso=Parameter(value=0.5))])])
    structure.phases[0].scale.value = 8.0e-3
    # declared, never inherited: a test that pins a number must not move when a
    # default does (CLAUDE.md), and dispersion has been on by default since v1.0
    instrument = Instrument.debye_scherrer(wavelength=LAM)
    instrument.source.dispersion = None
    instrument.profile.w.value = 8e-3

    tt = np.arange(18.0, 90.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0())) + 30.0
    rng = np.random.default_rng(1041)
    noisy = rng.poisson(np.maximum(y, 1.0)).astype(np.float64)
    return PatternData(two_theta=model.tt.tolist(),
                       intensity=noisy.tolist()), instrument
