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

#: NIST SRM 660c LaB6, the *absolute* lab anchor: the cell the certification CIF
#: recomputes for this data block's own temperature (20.85 °C), which is the
#: value ``test_acceptance_srm660c`` refines against.  The certificate's
#: 4.156826(8) Å applies at 22.5 °C and is not the number to compare with here.
A_SRM660C = 4.156780
#: The specimen displacement NIST's own analysis of this pattern recorded, and
#: the goniometer radius of the divergent-beam diffractometer it was measured on.
#: Together they *predict* the ``cos_theta`` template's amplitude, which is what
#: makes the shift this package fits from the pattern alone checkable rather than
#: merely plausible: Δ2θ = −(2s/R)·cos θ (``model.corrections``), so
#: s = −0.07877 mm at R = 217.5 mm is **+0.0415° · cos θ**.
SRM660C_DISPLACEMENT_MM, SRM660C_RADIUS_MM = -0.07877, 217.5
#: How far a picked component may sit from *every* position the certified cubic
#: cell allows before it is not a line of the phase.  An order of magnitude above
#: the real lines' own displacement (they run +0.010 to +0.041°) and an order
#: below the components this separates out (−0.16 to +0.19°), so nothing lands
#: near it.  **This uses the answer**, which is what makes every row that applies
#: it an attribution probe rather than a protocol — see
#: ``test_what_the_unflagged_tail_components_cost_the_certified_cell``.
LAB6_OFF_LATTICE_DEG = 0.05


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


def _index_corundum(peaks, **spec_kw):
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    data, ins = _qarr("corundum.prn")
    spec = SearchSpec(systems=REAL_DATA_SYSTEMS, max_volume=600.0,
                      budget_seconds=60.0, n_unindexed=REAL_DATA_N_UNINDEXED,
                      **spec_kw)
    return index_pattern(peaks, data=data, instrument=ins, spec=spec)


@pytest.fixture(scope="module")
def corundum_index(corundum_peaks):
    """Step 1 of the protocol: index with nothing declared. ~45-50 s."""
    return _index_corundum(corundum_peaks), A_SRM676A, C_SRM676A


@pytest.fixture(scope="module")
def corundum_index_with_shift(corundum_peaks):
    """Step 2: the same search with the shift template declared. ~45-50 s."""
    return (_index_corundum(corundum_peaks, shift_template="cos_theta"),
            A_SRM676A, C_SRM676A)


@pytest.fixture(scope="module")
def qpa_mixture_index():
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    data, ins = _qarr("cpd-1a.prn")
    spec = SearchSpec(systems=REAL_DATA_SYSTEMS, max_volume=600.0,
                      budget_seconds=60.0, n_unindexed=REAL_DATA_N_UNINDEXED)
    return index_pattern(data=data, instrument=ins, spec=spec)


# ----------------------------------------------------------------------
# SRM 660c LaB6 — the *absolute* anchor, and the one bundled phase whose space
# group has no extinctions at all
#
# **These rows are a separate xdist group, and the split is the point.**  The
# rule in CLAUDE.md is that runtime is set by the longest *group*, so sharing one
# is only free while that group is not the critical path.  It no longer is:
# measured 2026-07-30 with ``--durations`` on a green full run,
# ``indexing-acceptance`` totalled ~550-590 s against ``stephens-brucite``'s 533
# and ``qpa-sample1``'s 485 — i.e. the claim inherited from the previous session,
# that the indexing rows are "several times shorter" than the groups that set the
# wall clock, had stopped being true.  Nothing here shares a fixture with the
# corundum or cpd-1a rows, so putting LaB6 in its own group costs nothing and
# takes it off the critical path.  **Any further known-cell row should get its own
# group for the same reason** — one dataset, one group.
# ----------------------------------------------------------------------
def _lab6_inputs():
    """(pattern, instrument) for the NIST certification measurement.

    Built by ``test_acceptance_srm660c.build_srm_inputs`` so the two suites
    cannot disagree about the protocol — same CIF block, same instrument, same
    explicitly-declined dispersion.  Its ``structure`` is discarded: indexing is
    the question of what the cell *is*, so nothing here may see one.
    """
    from tests.test_acceptance_srm660c import build_srm_inputs
    data, _structure, instrument = build_srm_inputs()
    return data, instrument


@pytest.fixture(scope="module")
def lab6_peaks():
    """The picked line list, ~1 s.  Shared by the fast rows and the searches."""
    from pxrdref.indexing.pick import pick_peaks
    data, ins = _lab6_inputs()
    return pick_peaks(data, ins)


def _cubic_positions(a: float, wavelength: float, two_theta_max: float
                     ) -> np.ndarray:
    """2θ of every line a cubic P lattice of edge ``a`` allows, in range."""
    _, q = predicted_lines((a, a, a, 90.0, 90.0, 90.0), "cubic", "P",
                           wavelength, two_theta_max=two_theta_max * 1.02)
    return np.degrees(2.0 * np.arcsin(
        np.clip(wavelength * np.sqrt(np.unique(q)) / 2.0, -1.0, 1.0)))


def _certified_deviation(peaks, two_theta: np.ndarray) -> np.ndarray:
    """Signed distance from each position to the nearest certified-cell line.

    Signed, not absolute, because the sign is the measurement: the real lines
    are displaced one way by the specimen displacement and the tail components
    sit on the *other* side of their own line below 90° 2θ.
    """
    pred = _cubic_positions(A_SRM660C, peaks.wavelength, peaks.two_theta_max)
    k = np.argmin(np.abs(two_theta[:, None] - pred[None, :]), axis=1)
    return two_theta - pred[k]


def _without_the_off_lattice_lines(peaks):
    """The same list with the components no certified position explains removed.

    A *probe*, not a proposal.  It answers "what do these components cost?" by
    using the answer to identify them, which no user indexing an unknown phase
    can do — and the package's own screen cannot reach them either, for three
    different reasons measured in
    ``test_the_unflagged_tail_components_escape_for_three_different_reasons``.
    """
    kept = [p for p in peaks.peaks
            if not p.usable
            or abs(_certified_deviation(peaks, np.array([p.two_theta]))[0])
            < LAB6_OFF_LATTICE_DEG]
    return peaks.model_copy(update={"peaks": kept})


def _weak_partners(peaks):
    """Every usable component that is the weak member of a two-line group.

    These are the components the ``not_separable`` screen is *about*, whether or
    not it reached them, so both the flagged and the surviving ones come from
    one definition rather than from a hand-written list of positions.
    """
    by_group: dict[int, list] = {}
    for p in peaks.peaks:
        by_group.setdefault(p.group, []).append(p)
    out = []
    for members in by_group.values():
        if len(members) < 2:
            continue
        strongest = max(members, key=lambda p: p.intensity)
        for p in members:
            if p is not strongest and p.usable:
                out.append((p, strongest))
    return out


@pytest.fixture(scope="module")
def lab6_index(lab6_peaks):
    """Step 1: index the pattern exactly as picked, nothing declared. ~20 s."""
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    data, ins = _lab6_inputs()
    spec = SearchSpec(systems=REAL_DATA_SYSTEMS, max_volume=300.0,
                      budget_seconds=60.0, n_unindexed=REAL_DATA_N_UNINDEXED)
    return index_pattern(lab6_peaks, data=data, instrument=ins, spec=spec)


@pytest.fixture(scope="module")
def lab6_calibrated(lab6_peaks):
    """``(result, screen)`` for the fully calibrated protocol. ~4 s.

    Everything the gate can be given, given: the off-lattice components removed,
    the systematic **measured** against the certificate rather than assumed, and
    the template that names its cause declared.  Cubic only — the point of this
    fixture is what the *gate* does once the evidence exists, and a four-system
    search costs 35 s to reach the identical cell (measured: 4.156772 either way).
    """
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    data, ins = _lab6_inputs()
    trimmed = _without_the_off_lattice_lines(lab6_peaks)
    tt = trimmed.two_theta()
    screen = fit_shift_model(tt, _certified_deviation(trimmed, tt),
                             trimmed.two_theta_esd())
    amplitude = next(t.coefficient for t in screen.templates
                     if t.name == screen.best)
    spec = SearchSpec(systems=("cubic",), max_volume=300.0, budget_seconds=60.0,
                      n_unindexed=REAL_DATA_N_UNINDEXED,
                      shift_template="cos_theta",
                      sigma_sys_deg=abs(float(amplitude)))
    return index_pattern(trimmed, data=data, instrument=ins, spec=spec), screen


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


def test_table_5_reconstruction_sums_to_the_published_globals(bench):
    """The *scores* were transcribed too, and they get the same treatment.

    Table 5 is a 20-column grid of ±1 with subscripted zeros, and it does not
    survive conversion to plain text intact — the copy this was typed from had a
    row of 21 values where there are 20.  So the per-set scores are not trusted
    because they were read carefully either: each of the two rows this package is
    graded against is summed and checked against the **Global** column the paper
    prints beside it.  Getting +9 and +12 out of twenty independently-read cells
    is not something a misread row does.

    The bar itself is the "First 4" row — the best of ITO13, DICVOL91, TREOR90
    and McMaille run outside Crysfire — and it is quoted here so a future session
    reads the target off the fixture rather than off a commit message.
    """
    published = bench["scoring"]["published"]
    for key in ("first_4", "best_of_all"):
        row = published[key]
        per_set = row["per_set"]
        assert len(per_set) == 10, key
        assert set(per_set) == set(bench["sets"]), key
        for name, modes in per_set.items():
            assert len(modes) == 2, (key, name)      # default and manual
            assert all(v in (-1, 0, 1) for v in modes), (key, name)
        assert sum(sum(v) for v in per_set.values()) == row["global"], key

    assert published["first_4"]["global"] == 9
    assert published["best_of_all"]["global"] == 12
    # …and the individual programs, so "+9" is legible as a bar rather than a
    # number: the four it is the best of scored -14, -8, -4 and +5 alone
    assert published["individual_globals"]["ITO13"] == -14
    assert published["individual_globals"]["McMaille"] == 5


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

    This is the row the indexing milestone was blocked on, and it was blocked
    twice, by two different things that produced the same symptom.  First
    ``pick_peaks`` was reporting one phantom line per strong peak
    (``not_separable``, WP-1026), so 19 % of the lines handed to the search were
    not lines.  Then, with the certified lattice reachable at last, it came back
    with **c +2799 ppm** — recorded here for one session as "what an uncalibrated
    lab pattern costs", which it was not.  The whole trigonal-R domain converges
    to eleven leaves; ``_box_key`` hashed three of them onto a sibling and skipped
    them *before refining*, and one of the three held the certificate's c.

    So this row asserts the corrected answer: peaks picked by the package, no cell
    supplied, no shift measured, and the certified lattice **ranked first with the
    right centring**, both axes inside 150 ppm.

    The second half is still the point, and it is that ``low`` is the honest grade
    for a cell this accurate.  Four caveats stand, and each names something real:
    only one engine found it (``engines_disagree``); the Le Bail fit sees ~12
    reflections the *lattice* R-3m allows where the pattern has no intensity, which
    is the R-3c c-glide and not an oversized cell (``predicted_but_absent`` cannot
    tell those apart — WP-1025's extinction screen is what can); 49 of 55 lines are
    indexed against a 0.9 bar (``indexed_fraction_low``); and the matching window
    was widened by an assumed allowance (``shift_allowance_assumed``).  Declaring
    the shift template clears the third and sharpens the cell — the next test.
    """
    res, a_cert, c_cert = corundum_index

    assert res.validated
    assert res.candidates, "no candidate at all on a pattern with a certificate"
    best = res.candidates[0]
    assert best.system == "trigonal" and best.centring == "R", (
        f"ranked first: {best.system} {best.centring}")

    da = best.cell[0] / a_cert - 1.0
    dc = best.cell[2] / c_cert - 1.0
    assert abs(da) < 1.5e-4, f"a = {best.cell[0]:.5f} ({da*1e6:+.0f} ppm)"
    assert abs(dc) < 1.5e-4, f"c = {best.cell[2]:.5f} ({dc*1e6:+.0f} ppm)"
    assert best.n_indexed >= 49, f"{best.n_indexed} of {best.n_lines} lines"
    assert best.chi2_red < 1.5, best.chi2_red

    # the gate refuses to promote it, and every caveat names something real
    assert best.confidence == "low"
    assert set(best.confidence_caveats) >= {
        "shift_allowance_assumed", "indexed_fraction_low", "predicted_but_absent"}
    assert best.lebail is not None and best.lebail.predicted_but_absent > 0
    assert res.best_or_none() is None, (
        "a cell was returned as the answer with four caveats standing")


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance")
def test_declaring_the_shift_template_is_what_recovers_the_certificate(
        corundum_index, corundum_index_with_shift):
    """The other half of the protocol: declare the systematic, and see it fitted.

    A user with a standard cannot measure a specimen displacement before there is
    a cell to measure it against, so the sequence is: index under the assumed
    allowance, then declare the template and index again.  This row is that second
    call, and it is the first end-to-end evidence that ``refine_with_shift`` does
    what it exists for on real data.

    The fitted coefficient is **−0.061 ± 0.014°**, against a specimen displacement
    of −0.065° measured independently against the certificate (WP-1023) — so the
    package recovers a systematic it was never told about, from the pattern alone.
    Both axes land inside 150 ppm and ``indexed_fraction`` crosses its bar, so one
    refuting caveat clears.

    **The figures of merit are the striking part and they are not free.**  M₂₀ goes
    22 → 77 and F_N 16 → 60, because ``engines.scored_positions`` scores a
    shift-carrying candidate against the positions it actually claims.  That is the
    blind spot ``f_n`` has always stated — a refined shift can manufacture a large
    F_N — so the number to read here is not the size of the jump but that the
    *cell* moved to the certificate at the same time.  A shift that bought figures
    of merit without moving the cell would be the failure this row would catch.
    """
    plain, _a, _c = corundum_index
    res, a_cert, c_cert = corundum_index_with_shift

    best = res.candidates[0]
    assert best.system == "trigonal" and best.centring == "R"
    assert best.shift_template == "cos_theta"
    # the displacement, recovered from the pattern rather than from the certificate
    assert best.shift_coefficient == pytest.approx(-0.061, abs=0.02)
    assert abs(best.shift_coefficient) > 3.0 * best.shift_esd, (
        f"{best.shift_coefficient:+.4f} ± {best.shift_esd:.4f} is consistent "
        "with no shift at all")

    da = best.cell[0] / a_cert - 1.0
    dc = best.cell[2] / c_cert - 1.0
    assert abs(da) < 1.5e-4, f"a = {best.cell[0]:.5f} ({da*1e6:+.0f} ppm)"
    assert abs(dc) < 1.5e-4, f"c = {best.cell[2]:.5f} ({dc*1e6:+.0f} ppm)"

    # the cell moved *and* the figures of merit did — neither alone is evidence
    before, after = plain.candidates[0], best
    assert after.chi2_red < before.chi2_red
    assert after.fom_value("m20") > 3.0 * before.fom_value("m20")
    assert after.fom_value("indexed_fraction") >= 0.9 > \
        before.fom_value("indexed_fraction")
    assert "indexed_fraction_low" not in after.confidence_caveats
    # and it is still not promoted: the allowance was assumed either way
    assert after.confidence == "low"
    assert "shift_allowance_assumed" in after.confidence_caveats
    assert res.best_or_none() is None


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


# ----------------------------------------------------------------------
# SRM 660c: the absolute anchor, a phase with no extinctions, and a rival
# no enumeration of derivative lattices can reach
# ----------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance-lab6")
def test_a_certified_cubic_cell_is_recovered_with_no_extinction_caveat(lab6_index):
    """SRM 660c LaB6, indexed end to end — and the control for the corundum row.

    Corundum comes back carrying ``predicted_but_absent = 11-12``, and WP-1026
    read that as the R-3c c-glide seen through the *lattice* R-3m, since the
    lattice group is the only model that exists before
    ``determine_extinction_symbol`` runs.  That reading has an obvious test and
    this is it: **LaB6 is P m -3 m, whose only absences are none at all.**  If the
    caveat tracks space-group extinctions it must be silent here, on a pattern
    that is otherwise the same kind of object — a certified lab standard, Cu Kα
    doublet, one phase, picked by this package.

    It is silent.  ``predicted_seen_fraction`` is **1.000** — every reflection the
    lattice predicts has intensity where it predicts it — against corundum's
    0.86, and ``predicted_but_absent`` is 0 of 30.  So the caveat says what its
    name says and not "this cell is too big", which is the one reading WP-1026
    warned against and the reason it was filed to WP-1028 rather than retuned.

    What is *not* recovered here is the accuracy corundum reached: a lands **−127
    ppm** low, because the specimen displacement is absorbed into the cell and
    the shift that would take it out is defeated by five components of the peak
    list (the next three rows).  The bar is set at 200 ppm deliberately — a
    tighter one would be asserting that a defect this file measures does not
    exist.
    """
    res = lab6_index

    assert res.validated
    assert res.candidates, "no candidate on the absolute lab anchor"
    best = res.candidates[0]
    assert best.system == "cubic" and best.centring == "P", (
        f"ranked first: {best.system} {best.centring}")

    da = best.cell[0] / A_SRM660C - 1.0
    assert abs(da) < 2.0e-4, f"a = {best.cell[0]:.5f} ({da*1e6:+.0f} ppm)"
    assert best.chi2_red < 1.5, best.chi2_red

    # the control itself: a phase with no extinctions leaves no absences behind
    assert best.lebail is not None
    assert best.lebail.predicted_but_absent == 0, (
        f"{best.lebail.predicted_but_absent} of {best.lebail.n_reflections} "
        "reflections predicted where nothing was seen, on P m -3 m")
    assert best.fom_value("predicted_seen_fraction") == pytest.approx(1.0)
    assert "predicted_but_absent" not in best.confidence_caveats

    # …and it is still not promoted, on caveats that have nothing to do with
    # extinctions: the allowance was assumed, and only one engine found it
    assert best.confidence == "low"
    assert set(best.confidence_caveats) >= {"shift_allowance_assumed",
                                            "engines_disagree"}
    assert res.best_or_none() is None


@pytest.mark.xdist_group("indexing-acceptance-lab6")
def test_the_unflagged_tail_components_escape_for_three_different_reasons(
        lab6_peaks):
    """Six components survive the ``not_separable`` screen, and no one knob explains it.

    The screen (``indexing/pick.py``) asks three questions of a weak component
    sharing a group with a strong one: was it put there by a re-seed pass, is it
    *inside* the neighbour's profile (``PEAK_SATELLITE_NEAR_FWHM`` = 1.5 fitted
    FWHM) at no more than ``PEAK_SATELLITE_MAX_RATIO`` of its area, and is the
    group's fit still refuted with it in.  On this pattern thirteen components
    face those questions, seven are flagged and six are not — and the six fail
    **three different conditions**:

    ==========  ==========  ============================================
    2θ          sep/FWHM    the condition that lets it through
    ==========  ==========  ============================================
    21.200      2.99        too far — 3 FWHM out, on the axial tail
    30.288      2.24        too far
    37.377      1.73        too far
    71.942      2.27        too far — and it sits on its mate's Kα2
    43.505      0.81        **not re-seeded**: the detection seed slid into
                            the tail and the new component took the real
                            line, so the slot labels are the wrong way round
    141.911     1.01        **not refuted** — χ²_red 1.38, and the screen
                            deliberately keeps a weak neighbour on a
                            well-fitted group
    ==========  ==========  ============================================

    That table is the finding.  Widening 1.5 would reach four of the six and
    would be a knob rather than a measurement; the other two are a slot-labelling
    weakness and a stated design choice.  So this row pins the *census* rather
    than any threshold, and the fix — if there is one — is WP-1028's.
    """
    from pxrdref.schemas.indexing import (
        PEAK_SATELLITE_MAX_RATIO,
        PEAK_SATELLITE_NEAR_FWHM,
    )
    peaks = lab6_peaks
    survivors = _weak_partners(peaks)
    flagged = [p for p in peaks.peaks if "not_separable" in p.flags]

    assert len(flagged) >= 5, f"only {len(flagged)} flagged at all"
    assert 4 <= len(survivors) <= 8, len(survivors)
    # every survivor is weak enough and close enough to be *about* the screen —
    # so what let it through is one of the other two conditions, or the distance
    for weak, strong in survivors:
        assert weak.intensity < PEAK_SATELLITE_MAX_RATIO * strong.intensity, (
            f"{weak.two_theta:.4f}° is not a satellite of "
            f"{strong.two_theta:.4f}° at all")
    far = [(w, s) for w, s in survivors
           if abs(w.two_theta - s.two_theta) >= PEAK_SATELLITE_NEAR_FWHM * w.fwhm]
    assert len(far) >= 3, (
        "the distance condition is no longer what lets most of them through; "
        "re-measure the census before trusting the docstring above")


@pytest.mark.xdist_group("indexing-acceptance-lab6")
def test_the_surviving_components_sit_on_the_axial_divergence_side(lab6_peaks):
    """They are not lines, and the *side* they are on says which aberration.

    Axial divergence puts a peak's tail on the low-2θ side below 90° and on the
    high-2θ side above it — that sign change is the aberration's signature, and
    nothing else in a Bragg-Brentano pattern has it.  Every surviving component
    lands on the tail side of its own line, with a single exception that lands on
    its group-mate's **Kα2 maximum**: the alias screen drops that candidate at
    detection (``PEAK_KALPHA2_ALIAS``, 23 dropped here), but the group is wide
    enough that the fitter re-seeds a component there — 3 % of the parent's area,
    i.e. the residual of a *modelled* Kα2 rather than an unmodelled one.

    So the census is: five axial-divergence tails and one Kα2 residual, none of
    them lines of LaB6, all six carrying a σ ten times the real lines'.  That
    last part is what makes them survivable by one consumer and fatal to another
    — the next row.
    """
    peaks = lab6_peaks
    kalpha2: list[float] = []
    exceptions = 0
    for weak, strong in _weak_partners(peaks):
        # where this line's own Kα2 would be, from the instrument's own splitting
        theta = np.radians(strong.two_theta / 2.0)
        lam2_over_lam1 = 1.5444274 / 1.5405929        # Cu Kα2/Kα1, Hölzer 1997
        d_alias = np.degrees(2.0 * (lam2_over_lam1 - 1.0) * np.tan(theta))
        if abs(weak.two_theta - (strong.two_theta + d_alias)) < strong.fwhm:
            exceptions += 1
            kalpha2.append(weak.two_theta)
            continue
        tail_side = -1.0 if strong.two_theta < 90.0 else 1.0
        assert np.sign(weak.two_theta - strong.two_theta) == tail_side, (
            f"{weak.two_theta:.4f}° is on the wrong side of "
            f"{strong.two_theta:.4f}° for an axial-divergence tail")
    assert exceptions == 1, (
        f"expected exactly one Kα2 residual, found {exceptions} at {kalpha2}")


@pytest.mark.xdist_group("indexing-acceptance-lab6")
def test_the_shift_screen_survives_the_tail_components_but_the_search_cannot(
        lab6_peaks):
    """Why the corundum protocol's second step does nothing here, in one number.

    Declaring ``shift_template="cos_theta"`` moved corundum's cell to its
    certificate.  On this pattern it does not, and the reason is not the
    template: it is that the two consumers of a peak list weight it differently.

    ``fit_shift_model`` weights each line by its **own** fitted σ, and the tail
    components carry σ ≈ 0.005° against the real lines' ≈ 0.0005° — so they are
    down-weighted a hundredfold and the screen recovers the displacement anyway:
    **+0.0367 ± 0.0015°** against a certified-geometry prediction of **+0.0415°**
    (−0.07877 mm at R = 217.5 mm, ``model.corrections.displacement_shift_deg``).

    The *search* cannot, because it adds ``DEFAULT_UNKNOWN_SHIFT_DEG`` = 0.05° in
    quadrature to every σ.  That is a flat addition, so a hundredfold precision
    contrast becomes **1.005** and the tail components are weighted like the real
    lines — which is exactly what a shift column cannot survive, since they sit
    on the side the template is trying to measure.  Measured end to end: the
    search's fitted shift is +0.009 ± 0.016° (consistent with none) and the cell
    keeps its −127 ppm.

    **An assumed allowance is not free even when it is generous enough.**  It
    buys the search a matching window at the cost of the relative weighting the
    peak fitter measured, and this row is where that shows up.
    """
    from pxrdref.indexing.engines import DEFAULT_UNKNOWN_SHIFT_DEG
    peaks = lab6_peaks
    tt, esd = peaks.two_theta(), peaks.two_theta_esd()
    dev = _certified_deviation(peaks, tt)
    off = np.abs(dev) >= LAB6_OFF_LATTICE_DEG

    # the two populations, and the contrast the allowance is about to flatten
    assert off.sum() >= 4, f"only {off.sum()} off-lattice components"
    assert np.median(esd[off]) > 5.0 * np.median(esd[~off])
    widened = np.hypot(esd, DEFAULT_UNKNOWN_SHIFT_DEG)
    assert np.median(widened[off]) / np.median(widened[~off]) < 1.02, (
        "the allowance no longer flattens the σ contrast — re-measure")

    # and the screen, which never sees the allowance, gets the displacement
    screen = fit_shift_model(tt, dev, esd)
    assert screen.best == "cos_theta"
    best = next(t for t in screen.templates if t.name == screen.best)
    predicted = np.degrees(-2.0 * SRM660C_DISPLACEMENT_MM / SRM660C_RADIUS_MM)
    assert predicted == pytest.approx(0.0415, abs=5e-4)
    assert best.coefficient == pytest.approx(0.037, abs=0.004)
    assert 0.75 < best.coefficient / predicted < 1.0, (
        "the fitted amplitude should fall a little short of the geometric "
        "prediction — the other aberrations SRM 660c's docstring names are "
        "still in the residual")

    # with the off-lattice components out the same fit sharpens threefold and
    # the cause becomes separable, which is what the calibrated row rides on
    sharp = fit_shift_model(tt[~off], dev[~off], esd[~off])
    sharp_best = next(t for t in sharp.templates if t.name == sharp.best)
    assert sharp.best == "cos_theta"
    assert sharp_best.stderr < best.stderr / 2.0
    assert sharp.separable and not screen.separable


def test_positions_alone_cannot_separate_lab6_from_a_half_volume_rival():
    """A geometrical ambiguity the derivative-lattice enumeration cannot reach.

    A tetragonal P lattice with a′ = a/√2 and c′ = a gives
    Q = (2h² + 2k² + l²)/a², and **2(h²+k²)+l² represents exactly the integers
    h²+k²+l² does** — both miss precisely 4^n(8m+7) — so the two lattices produce
    powder lines at *identical* positions, everywhere, forever.  The identity is
    exact in arithmetic and lands at 3e-16 relative in doubles, which is the
    round-off of the √2 in a/√2 and not a difference between the lattices.  Only
    the multiplicities differ, so only intensities can separate them, and Le Bail
    validation cannot either, since it fits intensities freely.

    ``ambiguity_partners`` does not report it, and the reason is structural
    rather than a threshold: it enumerates *derivative* lattices — sublattices of
    index 2-4, i.e. supercells — and this rival has **half** the volume, so it is
    not in the enumeration at all.  The asymmetry is measurable in one call: from
    the cubic cell the tetragonal rival is invisible (0 partners), while from the
    tetragonal cell the cubic **is** found, as an index-2 derivative with **zero**
    discriminating reflections — the report saying, correctly, that nothing in
    range tells them apart.

    That one-directionality is the gap.  It is not merely cosmetic: the gate
    refuses ``high`` to a candidate with an ambiguity partner, so a cell whose
    rival happens to be the smaller lattice can be promoted while its rival
    cannot.  Filed to WP-1028; asserted here so the fix has a failing test to
    turn round.
    """
    from pxrdref.indexing.ambiguity import ambiguity_partners

    a, lam, tt_max = A_SRM660C, 1.5405929, 150.91
    at = a / np.sqrt(2.0)

    # 1. the arithmetic, over a range no measurement reaches
    def represented(form) -> set[int]:
        return {n for h in range(25) for k in range(25) for ell in range(25)
                if 0 < (n := form(h, k, ell)) <= 400}

    cubic_n = represented(lambda h, k, ell: h * h + k * k + ell * ell)
    tetr_n = represented(lambda h, k, ell: 2 * h * h + 2 * k * k + ell * ell)
    assert cubic_n == tetr_n
    missing = sorted(set(range(1, 401)) - cubic_n)
    assert missing[:6] == [7, 15, 23, 28, 31, 39]      # 4^n(8m+7), both forms

    # 2. and therefore the package's own predicted positions, bit for bit
    _, q_cubic = predicted_lines((a, a, a, 90, 90, 90), "cubic", "P", lam,
                                 two_theta_max=tt_max)
    _, q_tetr = predicted_lines((at, at, a, 90, 90, 90), "tetragonal", "P", lam,
                                two_theta_max=tt_max)
    uc, ut = np.unique(q_cubic), np.unique(q_tetr)
    assert len(uc) == len(ut) > 20
    # the *only* difference doubles can carry: one line's worth of round-off in
    # the irrational axis ratio, a hundred million times below the fitted σ(Q)
    assert np.max(np.abs(uc - ut) / uc) < 1e-15, "no longer isospectral"

    # 3. the enumeration sees it from one side only
    q_esd = np.full_like(uc, 1e-5)
    from_cubic = ambiguity_partners((a, a, a, 90, 90, 90), "cubic", "P",
                                    uc, q_esd, lam, tt_max)
    from_tetr = ambiguity_partners((at, at, a, 90, 90, 90), "tetragonal", "P",
                                   uc, q_esd, lam, tt_max)
    assert from_cubic == [], (
        "the enumeration now reaches the half-volume rival — good; delete this "
        "assertion and the WP-1028 note with it")
    assert len(from_tetr) == 1
    partner = from_tetr[0]
    assert partner.index == 2
    assert partner.volume == pytest.approx(a ** 3, rel=1e-3)
    assert partner.discriminating_reflections == [], (
        "a reflection was offered as a tie-breaker between two lattices whose "
        "predicted positions are identical")


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance-lab6")
def test_the_isospectral_rival_is_ranked_beside_the_truth(lab6_index):
    """And on the real pattern both are in the list, with neither promoted.

    The rival of the row above is not a thought experiment: both engines find it
    on the measured lines, and it is ranked within the top few of the truth.  The
    gate does the right thing for the wrong reason — nothing is promoted here
    anyway, because the allowance was assumed — so what this row pins is that
    **neither** carries ``geometric_ambiguity``, which is the caveat that ought
    to be carrying this pair.

    It is the WP's "a geometrical-ambiguity case where neither partner reaches
    ``high``" row, answered on certified data rather than synthetically, and it
    is a stronger case than a synthetic one would have been: the partner here is
    exactly isospectral rather than isospectral within a tolerance.
    """
    res = lab6_index
    truth = res.candidates[0]
    assert truth.system == "cubic"

    rivals = [c for c in res.candidates
              if c.system == "tetragonal"
              and c.cell[2] / c.cell[0] == pytest.approx(np.sqrt(2.0), rel=1e-3)
              and c.volume == pytest.approx(truth.volume / 2.0, rel=5e-3)]
    assert len(rivals) == 1, [
        (c.system, tuple(round(x, 4) for x in c.cell[:3])) for c in res.candidates]
    rival = rivals[0]
    assert set(rival.found_by) == set(res.engines_run), (
        f"only {rival.found_by} reached a lattice that predicts exactly the "
        "same lines as the one ranked first")

    for cand in (truth, rival):
        assert cand.confidence != "high"
        assert "geometric_ambiguity" not in cand.confidence_caveats
    assert res.best_or_none() is None


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance-lab6")
def test_what_the_unflagged_tail_components_cost_the_certified_cell(
        lab6_calibrated, lab6_peaks):
    """The whole protocol, with every piece of evidence supplied — and ``high``.

    This is the first ``high`` confidence answer ``index_pattern`` returns on
    real data, and the first time ``best_or_none()`` hands back a cell at all.
    It costs three things, and naming them is the point of the row:

    1. the five off-lattice components removed — **using the certificate**, which
       no user of an unknown phase can do;
    2. the systematic **measured** rather than assumed, which clears
       ``shift_allowance_assumed``, the caveat WP-1024 identified as the reason
       ``high`` was unreachable on lab data;
    3. ``shift_template="cos_theta"`` declared, so the measured displacement is
       taken out of the cell instead of absorbed into it.

    With all three: **a = 4.156772 Å, −2 ppm** from the NIST certification CIF's
    own cell for this data block, M₂₀ = 1113, zero caveats.  Against the −127 ppm
    the same pattern gives with none of them.  So the arithmetic of the whole
    pipeline is sound to the part-per-million and what stands between it and a
    blind certified answer is a peak list — which is the useful form of this
    result, and the reason the tail rows above are not a footnote.

    **What the σ_sys argument means, measured the hard way.**  The obvious number
    to declare is the one ``ShiftScreen`` calls ``sigma_sys_deg`` — the scatter
    the winning template *leaves* (0.0078° here).  Declare that and the search
    finds **nothing**, because it matches against uncorrected positions: the
    template is fitted by ``refine_with_shift`` only after a candidate survives,
    so the window still has to span the shift itself.  What the search needs is
    the shift's **amplitude** (0.037°), and this fixture declares that.  The two
    quantities differ by 4.3× and only one of them indexes; filed to WP-1028.
    """
    res, screen = lab6_calibrated

    assert res.candidates, "the calibrated protocol found nothing"
    best = res.candidates[0]
    assert best.system == "cubic" and best.centring == "P"

    da = best.cell[0] / A_SRM660C - 1.0
    assert abs(da) < 1.0e-5, f"a = {best.cell[0]:.6f} ({da*1e6:+.1f} ppm)"

    # the gate, with nothing left to object to
    assert best.confidence == "high", sorted(best.confidence_caveats)
    assert best.confidence_caveats == []
    assert res.best_or_none() is not None
    assert set(best.found_by) == set(res.engines_run)

    # the displacement, taken out of the cell rather than absorbed into it
    assert best.shift_template == "cos_theta"
    assert best.shift_coefficient == pytest.approx(0.034, abs=0.006)
    assert best.fom_value("m20") > 500.0

    # and the trap: the residual the screen leaves is not the window the search
    # needs, and declaring it returns no candidate at all
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    data, ins = _lab6_inputs()
    assert screen.sigma_sys_deg < 0.3 * abs(best.shift_coefficient)
    spec = SearchSpec(systems=("cubic",), max_volume=300.0, budget_seconds=60.0,
                      n_unindexed=REAL_DATA_N_UNINDEXED,
                      shift_template="cos_theta",
                      sigma_sys_deg=float(screen.sigma_sys_deg))
    tight = index_pattern(_without_the_off_lattice_lines(lab6_peaks),
                          data=data, instrument=ins, spec=spec)
    assert tight.candidates == [], (
        "the post-correction residual now indexes — re-read the docstring, the "
        "σ_sys semantics may have been fixed")
