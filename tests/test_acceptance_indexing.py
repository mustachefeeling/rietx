"""WP-1026 — indexing acceptance against a **published, scored** benchmark.

Bergmann, Le Bail, Shirley & Zlokazov (2004), *Z. Kristallogr.* **219**, 783-790
ran eleven indexing programs over one compound at six levels of difficulty and
printed both the data (Table 6) and every program's score (Table 5).  No other
feature in this package has had that: the bar here is not a tolerance somebody
chose, it is what ITO13, DICVOL91, TREOR90 and McMaille actually achieved on
these exact numbers.

Three groups of tests, and the order is deliberate.

**First the fixture proves itself.**  Two hundred numbers were typed from a
printed table, so before anything is graded against them they are checked against
three statements the paper makes *in prose and never tabulates* — the zeroshift
arithmetic, the I ≥ 5 % subsetting, and its own impurity counts.  A transcription
error breaks at least one.

**Then the claims that need no search**, which is where the strongest evidence
is: the published figures of merit, and the first test of the paper's own
hypothesis about what caused the zeroshift.

**Then the search itself**, marked ``slow``.

**What is deliberately absent is the global score, and that is a measured
no-go rather than an unfinished row.**  The paper's protocol specifies the
search domain — "maximum cell parameters of 20 Å and V_max = 2000 Å³ in
monoclinic symmetry" by default, and in manual mode "a monoclinic run with
volume range 800-1200 Å³, and 5-20 Å cell parameters".  Adopting a protocol
means adopting it wholesale (CLAUDE.md), and a score computed over a narrower
domain is not comparable with Table 5.  Measured on set F, the *easiest* of the
ten (synchrotron, M(20) = 197, all twenty lines explained by the published cell):

===========================  ==========  ============  =========
run                          budget      candidates    complete
===========================  ==========  ============  =========
dichotomy, n_unindexed = 0   240 s       0             **False**
dichotomy, n_unindexed = 2   240 s       0             **False**
dichotomy, manual mode       900 s       0             **False**
trial-and-error, n_un = 0/2  240 s       12 (no truth) **False**
===========================  ==========  ============  =========

Every one of them exhausted its budget without finishing the domain, so the
negative is about *cost*, not about the search being wrong — an incomplete
search says nothing at all (``EngineResult.search_complete``).  The tolerance
was excluded as the cause: declaring σ = 0.005° instead of the assumed 0.02°
takes median σ(Q)/Q from 4.4e-3 to 1.1e-3 and changes nothing (0 candidates,
still incomplete at 240 s).  So an exhaustive dichotomy over four free metric
parameters at this domain size is the limit, and reporting a score obtained by
shrinking the domain would be reporting a different experiment.  The engines'
synthetic monoclinic recovery is solid, so this is a statement about the
*domain*, not about monoclinic.

One protocol note, because it decides whether any of this means anything: the
sets arrive as bare positions, so every one of them is a ``from_positions`` list
whose σ is *assumed*.  That is the input the benchmark defines, and it is why
``PEAK_SIGMA_ASSUMED`` fires on all ten and why none of them may be refused on a
precision figure computed from that σ (``indexing/quality.py``).
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

from pxrdref.indexing.fom import (
    _count_possible,
    nearest_discrepancy,
    predicted_lines,
)
from pxrdref.indexing.quality import assess_peak_list, fit_shift_model
from pxrdref.schemas.indexing import PEAK_ASSUMED_ESD_DEG, PeakList

DATA = pathlib.Path(__file__).parent / "data"
BENCH = DATA / "bethanechol_indexing.json"

#: 2θ window (°) within which an observed line counts as explained by the
#: published cell.  Generous on purpose: these are 1993-era ICDD entries carrying
#: a ~0.06° systematic, and the question here is "is this line a line of this
#: compound", not "how precise is it".
EXPLAINED_DEG = 0.08


@pytest.fixture(scope="module")
def bench() -> dict:
    if not BENCH.exists():
        pytest.skip("bethanechol benchmark fixture not present")
    return json.loads(BENCH.read_text(encoding="utf-8"))


def _truth(bench: dict) -> tuple[float, ...]:
    a = bench["answer"]
    return (a["a"], a["b"], a["c"], a["alpha"], a["beta"], a["gamma"])


def _set(bench: dict, name: str) -> tuple[np.ndarray, float]:
    s = bench["sets"][name]
    return np.array(s["two_theta"], dtype=np.float64), float(s["wavelength"])


def _predicted(bench: dict, name: str, pad: float = 1.06) -> np.ndarray:
    """2θ of every line the published lattice allows over this set's range."""
    tt, lam = _set(bench, name)
    _, q = predicted_lines(_truth(bench), "monoclinic", "P", lam,
                           two_theta_max=float(tt.max()) * pad)
    return np.degrees(2.0 * np.arcsin(np.clip(lam * np.sqrt(q) / 2.0, -1.0, 1.0)))


def _best_offset(bench: dict, name: str, tol: float = EXPLAINED_DEG):
    """(δ, n explained) maximising the lines the published cell accounts for.

    A scan rather than a mean: the impurity lines never match at any δ, so a
    least-squares offset would be dragged by them.
    """
    tt = _set(bench, name)[0]
    pred = _predicted(bench, name)
    grid = np.arange(-0.20, 0.2001, 0.0005)
    counts = np.array([
        int(np.count_nonzero(
            np.min(np.abs((tt - d)[:, None] - pred[None, :]), axis=1) <= tol))
        for d in grid])
    best = int(counts.max())
    tied = np.flatnonzero(counts == best)
    # among the offsets explaining the most lines, the one with the least scatter
    resid = [float(np.mean(np.min(np.abs((tt - grid[k])[:, None] - pred[None, :]),
                                  axis=1) ** 2)) for k in tied]
    return float(grid[tied[int(np.argmin(resid))]]), best


# ----------------------------------------------------------------------
# Real-data fixtures.  Each search is ~60-90 s, so they are module-scoped and
# every consumer carries the matching xdist_group (CLAUDE.md).
# ----------------------------------------------------------------------
#: Lines a search may leave unindexed on these real patterns.  **Three, not the
#: default two, and it is a measurement rather than a knob.**  After the
#: ``not_separable`` fix the corundum list still carries one 5.17° edge artifact
#: (the pattern starts at 5.00°, where no background can be estimated) and two
#: satellites the flag does not reach, so three of the first twenty lines are not
#: lines of the phase.  The sweep is the evidence that this is not tuning: at 2
#: neither engine finds the certified cell, at 3 **both rank it first**, and at 5
#: and 6 dichotomy loses it *entirely* — the extra tolerance manufactures
#: better-scoring wrong cells, exactly as ``DEFAULT_N_UNINDEXED`` warns.
REAL_DATA_N_UNINDEXED = 3
#: Systems searched on the real-data rows.  A restriction, declared: the answers
#: are known to be trigonal/cubic/hexagonal, an exhaustive monoclinic or triclinic
#: pass costs minutes (see the handover log), and ``systems_searched`` travels on
#: the result so the report says what was covered rather than concluding about
#: the specimen.
REAL_DATA_SYSTEMS = ("cubic", "tetragonal", "hexagonal", "trigonal")

A_SRM676A, C_SRM676A = 4.759355, 12.99231     # k = 2, 22.5 °C (certificate)


def _qarr(name: str):
    """(pattern, instrument) for one IUCr round-robin pure phase.

    Dispersion is **declined explicitly**, inherited from ``qarr_instrument``
    which sets ``source.dispersion = None``, and it is worth saying why rather
    than riding it: indexing consumes only peak *positions*, and the one place a
    structure factor enters here is the Le Bail validation, whose phase is a
    single dummy carbon (``workflow.DUMMY_SPECIES``) whose intensities are
    force-fixed and re-extracted.  So f′/f″ is inert on this row — but "inert"
    is a measurement, not a licence to leave the setting implicit (WP-1001).
    """
    from tests.test_acceptance_qpa_roundrobin import DATA as QARR
    from tests.test_acceptance_qpa_roundrobin import qarr_instrument
    if not (QARR / name).exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    import pxrdref as pr
    ins = qarr_instrument()
    assert ins.source.dispersion is None
    return pr.read_pattern(QARR / name), ins


@pytest.fixture(scope="module")
def corundum_peaks():
    from pxrdref.indexing.pick import pick_peaks
    data, ins = _qarr("corundum.prn")
    return pick_peaks(data, ins)


@pytest.fixture(scope="module")
def corundum_index(corundum_peaks):
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    data, ins = _qarr("corundum.prn")
    spec = SearchSpec(systems=REAL_DATA_SYSTEMS, max_volume=600.0,
                      budget_seconds=60.0, n_unindexed=REAL_DATA_N_UNINDEXED)
    res = index_pattern(corundum_peaks, data=data, instrument=ins, spec=spec)
    return res, A_SRM676A, C_SRM676A


@pytest.fixture(scope="module")
def qpa_mixture_index():
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    data, ins = _qarr("cpd-1a.prn")
    spec = SearchSpec(systems=REAL_DATA_SYSTEMS, max_volume=600.0,
                      budget_seconds=60.0, n_unindexed=REAL_DATA_N_UNINDEXED)
    return index_pattern(data=data, instrument=ins, spec=spec)


# ----------------------------------------------------------------------
# The fixture proves itself before anything is graded against it
# ----------------------------------------------------------------------
def test_every_set_is_twenty_ascending_lines(bench):
    assert len(bench["sets"]) == 10, "Table 6 has ten columns, not six"
    for name, s in bench["sets"].items():
        tt = np.array(s["two_theta"])
        assert len(tt) == 20, name
        assert np.all(np.diff(tt) > 0), f"{name} is not ascending"


@pytest.mark.parametrize("raw,corrected", [("Aa", "Ca"), ("Ab", "Cb"),
                                           ("Ba", "Da"), ("Bb", "Db")])
def test_the_zeroshift_correction_is_exactly_the_paper_s(bench, raw, corrected):
    """C = A − 0.100 and D = B − 0.100, to the last printed digit.

    The paper describes the correction in the text ("both patterns have a
    surprisingly large zeropoint error that is close to 0.10 (2θ)°") and prints
    the corrected columns without ever stating the arithmetic that links them.
    Eighty values have to agree for this to pass.
    """
    delta = _set(bench, raw)[0] - _set(bench, corrected)[0]
    assert np.allclose(delta, 0.100, atol=5e-13)


@pytest.mark.parametrize("full,subset,n_common", [("Aa", "Ba", 13),
                                                  ("Ab", "Bb", 15)])
def test_the_intensity_cut_is_a_subset_of_the_same_measurement(
        bench, full, subset, n_common):
    """B is "the first 20 lines with I ≥ 5 % I_max" of the *same* pattern as A.

    So every B line inside A's 2θ range must be one of A's, bit-for-bit — and B
    reaches further in 2θ precisely because dropping the weak lines lets twenty
    survivors extend past A's last one.
    """
    a = _set(bench, full)[0]
    b = _set(bench, subset)[0]
    inside = b[b <= a.max() + 1e-9]
    assert len(inside) == n_common
    for x in inside:
        assert np.min(np.abs(a - x)) < 1e-12, f"{x} is in {subset} but not {full}"
    assert b.max() > a.max()


@pytest.mark.parametrize("name,n_unexplained", [
    # "3 impurity lines among the first 35 lines" in PDF 46-1964 — and exactly
    # three of the twenty are unexplained in every set drawn from that entry
    ("Ab", 3), ("Cb", 3),
    # "8 impurity lines among the first 26" in PDF 43-1748; the first twenty
    # carry seven of them
    ("Aa", 7), ("Ca", 7),
    # the two new measurements are clean
    ("E", 0), ("F", 0),
])
def test_the_published_cell_reproduces_the_paper_s_impurity_counts(
        bench, name, n_unexplained):
    """The strongest transcription check, because it uses the *answer*.

    Nothing here is fitted: the cell is the paper's, the offset is a scan over
    one number, and what is counted is how many of the twenty lines the lattice
    cannot account for.  The counts land on the paper's own prose statement about
    each ICDD entry, which no typo in either the positions or the cell survives.
    """
    _, explained = _best_offset(bench, name)
    assert 20 - explained == n_unexplained


# ----------------------------------------------------------------------
# What the benchmark says without any search being run
# ----------------------------------------------------------------------
def test_published_figures_of_merit_are_reproduced_unfloored(bench):
    """M(20) = 197 and F(20) = 1080 (0.0006, 32) on the synchrotron set.

    This package's ``m20``/``f_n`` **floor ⟨Δ⟩ at the median σ**, which on a
    ``from_positions`` list is the *assumed* 0.02° — thirty times the paper's
    ⟨|Δ2θ|⟩ — so the floored figures are 5.8 and 32.3 and are not comparable with
    a published value computed without the floor.  That is not a defect in either
    convention; it is why the comparison is made against the **unfloored** de
    Wolff and Smith-Snyder definitions and why the floored numbers are recorded
    rather than quietly used.

    The residual gap is the *cell's* rounding, not the data's: a, b, c are printed
    to three decimals and β to two, which alone moves predicted positions by
    ~0.001° — the same order as the 0.0006° the paper quotes.
    """
    tt, lam = _set(bench, "F")
    peaks = PeakList.from_positions(tt, wavelength=lam)
    q = peaks.q()
    pred_tt = _predicted(bench, "F")
    _, pred_q = predicted_lines(_truth(bench), "monoclinic", "P", lam,
                                two_theta_max=float(tt.max()) * 1.06)

    d_tt = nearest_discrepancy(tt, pred_tt)
    d_q = nearest_discrepancy(q, pred_q)
    n_poss_tt = _count_possible(pred_tt, float(tt.max()))
    n_poss_q = _count_possible(pred_q, float(q.max()))

    m20 = float(q.max()) / (2.0 * d_q.mean() * n_poss_q)
    f20 = 20.0 / (d_tt.mean() * n_poss_tt)

    # the paper's own N_poss for F is 32; ours is 31 — one line, at the boundary
    assert abs(n_poss_tt - bench["answer"]["published_f20_n_possible"]) <= 1
    # ⟨|Δ2θ|⟩ 0.00099° against a published 0.0006°, i.e. the same order and
    # dominated by the printed cell's own rounding
    assert d_tt.mean() < 3.0 * bench["answer"]["published_f20_mean_delta_two_theta"]
    # both figures land in the right decade, which is the honest bar for a
    # comparison whose reference was computed on an unrounded cell
    assert 100.0 < m20 < 250.0, m20
    assert 500.0 < f20 < 1200.0, f20
    # every one of the twenty lines is explained: F is the set the cell came from
    assert np.count_nonzero(d_tt < 0.01) == 20


def test_the_2004_zeroshift_hypothesis_cannot_be_tested_on_these_data(bench):
    """The paper's hypothesis, tested for the first time — and the answer is no.

    Bergmann *et al.* observed that both ICDD entries of this compound carry a
    large zeroshift and wrote that it "would be consistent with a systematic
    specimen-displacement error".  They had no way to check, because every
    program available fitted a single constant "zeropoint".  This package fits
    three physical causes as *nested single fits* (``quality.fit_shift_model``),
    so the question is finally askable.

    It is asked here and it comes back **unanswerable**, which the WP required to
    be asserted either way: over the 6-31° 2θ these sets span, cos θ ≈ 1 and
    sin 2θ ≈ 2θ, so the three templates are collinear to 1.0000 and ``separable``
    is False on all ten.  A measured "cannot tell" is a result; a guess is not.

    What *is* determined is the magnitude, and it disagrees with the paper's own
    round number: against the published cell, PDF 43-1748 carries +0.062° and
    46-1964 +0.058°, not 0.10°.  Subtracting 0.100 to make the C and D sets
    therefore overshoots — measured, it leaves them at −0.039° and −0.043°, which
    is why C is *not* uniformly easier than A.
    """
    seen = []
    for name in bench["sets"]:
        tt = _set(bench, name)[0]
        pred = _predicted(bench, name)
        dev = np.array([t - pred[np.argmin(np.abs(pred - t))] for t in tt])
        keep = np.abs(dev) <= 0.20            # impurity lines cannot enter a fit
        screen = fit_shift_model(tt[keep], dev[keep], PEAK_ASSUMED_ESD_DEG)
        seen.append((name, screen))
        assert screen.max_collinearity > 0.999, name
        assert not screen.separable, (
            f"{name}: a cause was named from a range that cannot separate them")

    by_name = dict(seen)
    # the magnitude is well determined even though the cause is not — the
    # measured asymmetry ShiftScreen's docstring describes, one rank up
    for name, floor, ceil in [("Aa", 0.055, 0.075), ("Ab", 0.040, 0.065),
                              ("F", -0.005, 0.005)]:
        best = next(t for t in by_name[name].templates
                    if t.name == by_name[name].best)
        assert floor <= best.coefficient <= ceil, (name, best.coefficient)

    # And the paper's 0.100° correction overshoots on both entries.  Measured at
    # a *tight* window: the offset is a measurement, so it wants the narrow
    # tolerance, where EXPLAINED_DEG's job one test up is to count lines and its
    # plateau is deliberately wide.
    for raw, corrected in (("Aa", "Ca"), ("Ab", "Cb")):
        d_raw, _ = _best_offset(bench, raw, tol=0.02)
        d_corr, _ = _best_offset(bench, corrected, tol=0.02)
        assert d_raw > 0.0 > d_corr
        assert d_raw < 0.100, f"{raw} carries {d_raw:.4f}°, not the quoted 0.100°"
        assert abs(d_raw - d_corr - 0.100) < 1e-9      # the two are one apart


def test_a_bare_position_list_says_its_sigma_was_assumed(bench):
    """The benchmark's input form, and the rule it must not break.

    Every set is positions only, so every line carries ``sigma_assumed`` and the
    list's ``source`` is ``"positions"``.  The gate must let it through — a
    precision this package invented cannot be grounds for refusing to index — and
    must still say the σ is unmeasured.
    """
    for name in bench["sets"]:
        tt, lam = _set(bench, name)
        peaks = PeakList.from_positions(tt, wavelength=lam)
        assert peaks.source == "positions"
        assert all("sigma_assumed" in p.flags for p in peaks.peaks)
        report = assess_peak_list(peaks)
        assert report.supports_indexing, (name, report.abstained_reason)
        assert report.shift.source == "unavailable"


# ----------------------------------------------------------------------
# Real data: the certified pattern the milestone was blocked on
# ----------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance")
def test_a_certified_lab_pattern_indexes_and_is_graded_honestly(corundum_index):
    """SRM 676a corundum, picked and indexed by this package end to end.

    This is the row the indexing milestone was blocked on, and it was blocked for
    a reason nobody had looked for: ``pick_peaks`` was reporting one phantom line
    per strong peak (``not_separable``, WP-1026), so 19 % of the lines handed to
    the search were not lines.  With those barred from ``usable()`` the certified
    lattice comes back **ranked first** by ``index_pattern`` on a raw pattern —
    peaks picked by the package, no cell supplied, no shift measured.

    Two halves, and the second is the point.  The cell is found; it is graded
    ``low``, and that grade is *correct*.  ``a`` lands within 100 ppm of the
    certificate while ``c`` is out by ~2800 ppm, because with no measured shift
    both engines widen their window by ``DEFAULT_UNKNOWN_SHIFT_DEG`` and each
    absorbs the specimen displacement differently — which is exactly what
    ``engines_disagree`` reports.  A gate that called this ``high`` would be
    quoting a c-axis that is wrong in the fourth digit.
    """
    res, a_cert, c_cert = corundum_index

    assert res.validated
    assert res.candidates, "no candidate at all on a pattern with a certificate"
    best = res.candidates[0]
    assert best.system == "trigonal" and best.centring == "R", (
        f"ranked first: {best.system} {best.centring}")

    da = best.cell[0] / a_cert - 1.0
    assert abs(da) < 3e-4, f"a = {best.cell[0]:.5f} against {a_cert} ({da*1e6:+.0f} ppm)"
    # c is the axis the absorbed shift lands on, and it is out by ~2800 ppm.
    # Asserted as a *range* rather than a bound: this is a characterisation of
    # what an uncalibrated lab pattern costs, and a version of it that silently
    # got better would mean the protocol changed.
    dc = best.cell[2] / c_cert - 1.0
    assert 1e-3 < dc < 5e-3, f"c = {best.cell[2]:.5f} ({dc*1e6:+.0f} ppm)"

    # the gate refuses to promote it, and names why
    assert best.confidence == "low"
    assert "shift_allowance_assumed" in best.confidence_caveats
    assert res.best_or_none() is None, (
        "a cell whose c-axis is 2800 ppm out was returned as the answer")


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance")
def test_the_phantom_lines_are_what_had_blocked_it(corundum_peaks):
    """The measurement behind the fix, pinned so it cannot silently regress.

    ``detect_peaks`` proposes 41 groups with one seed each; the fitter returns 63
    components.  Eight of them are shape repair rather than lines, and the ones
    that matter sit ~0.17-0.24° below a strong line — far outside the ~0.06°
    specimen displacement the real lines carry, which is what makes them
    separable from a systematic shift by eye and *not* by ΔBIC.
    """
    peaks = corundum_peaks
    flagged = [p for p in peaks.peaks if "not_separable" in p.flags]

    assert len(peaks.peaks) > len(peaks.usable()), "nothing was flagged at all"
    assert 4 <= len(flagged) <= 14, len(flagged)
    assert len(peaks.usable()) >= 50
    # every flagged line sits below a much stronger one, and further from it than
    # the real lines sit from their own predicted positions
    tt = np.array([p.two_theta for p in peaks.peaks])
    inten = np.array([p.intensity for p in peaks.peaks])
    for p in flagged:
        near = (np.abs(tt - p.two_theta) < 1.5 * p.fwhm) & (tt != p.two_theta)
        assert near.any() and inten[near].max() > 4.0 * p.intensity


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance")
def test_a_three_phase_mixture_abstains(qpa_mixture_index):
    """The correct answer is "we do not know", and the API must be able to say it.

    ``qarr/cpd-1a.prn`` is corundum + zincite + fluorite.  No single lattice
    explains it, and the failure mode this guards against is the one the prior
    art at ``guillemot-study`` retracted a claim over: a coverage score cannot
    tell a multiphase pattern from a single-phase one of lower symmetry, so a
    ranked list is exactly what a naive indexer produces here.
    """
    res = qpa_mixture_index
    assert res.best_or_none() is None
    # and it says what it looked at rather than concluding about the sample
    assert res.systems_searched
    for cand in res.candidates:
        assert cand.confidence != "high"
