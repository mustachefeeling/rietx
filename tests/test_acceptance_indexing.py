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
from pxrdref.schemas.indexing import (
    PAIR_MIN_Z,
    PEAK_ASSUMED_ESD_DEG,
    PeakList,
)

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
#: Per-system wall-clock budget for the real-data searches.  **Generous on
#: purpose, and this is CLAUDE.md's rule paid for a fourth time.**  A budget
#: inside a test is a runaway guard, never a timer: at 60 s the zircon row passed
#: serially (73 s for all four systems) and **failed under ``-n auto``**, where
#: the same work takes 258 s — the search truncated, and the row reported
#: tetragonal *P* ranked first instead of *I*.  Nothing about the index table had
#: changed; the machine was busy.  At 300 s the budget never binds on any dataset
#: here, so it costs nothing when the search finishes early and only stops a
#: runaway.  The rule to apply when adding a row: compare its **serial** time
#: with its declared budget, and if the budget is not several times larger the
#: assertion is a load sensor.
REAL_DATA_BUDGET_SECONDS = 300.0

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
                      budget_seconds=REAL_DATA_BUDGET_SECONDS, n_unindexed=REAL_DATA_N_UNINDEXED,
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
                      budget_seconds=REAL_DATA_BUDGET_SECONDS, n_unindexed=REAL_DATA_N_UNINDEXED)
    return index_pattern(data=data, instrument=ins, spec=spec)


# ----------------------------------------------------------------------
# The round-robin pure phases: four crystal systems and two centrings, and the
# reference cells are **literature single-crystal cells for the mineral, not
# certificates for these specimens**
# ----------------------------------------------------------------------
#: (file, space group, literature cell).  Every row is the same cell the QPA
#: acceptance suite uses as its Rietveld starting model, quoted from the same
#: papers, so the two suites cannot drift about what "the answer" is.
#:
#: **The tier is `consistency`, never `certificate`, and brucite is the proof
#: it has to be**: its specimen's *a* sits **+1750 ppm** from Zigan &
#: Rothbauer's cell, which is 30× the ±85 ppm goniometer-radius floor and far
#: outside anything the measurement could resolve.  A literature cell is a cell
#: for *the mineral*, and a real specimen has its own composition, its own
#: solid solution and its own temperature.  So these rows assert the lattice
#: **type**, the centring, and agreement at the level a lab d-scale supports —
#: never a part-per-million number, which is what SRM 660c and SRM 676a are for.
QARR_PHASES = {
    "zincite": ("P 63 m c", (3.2499, 3.2499, 5.2066, 90.0, 90.0, 120.0)),
    "zircon": ("I 41/a m d:2", (6.6042, 6.6042, 5.9796, 90.0, 90.0, 90.0)),
}


def _index_qarr_phase(name: str, systems: tuple[str, ...]):
    """Index one pure phase over a **declared** subset of crystal systems.

    The restriction is not a shortcut, it is the price of the honest budget.
    With ``REAL_DATA_BUDGET_SECONDS`` raised so the search cannot truncate under
    load, a four-system zincite pass runs to completion and costs **850 s**,
    which made this the longest xdist group in the tree and put ~4 minutes on the
    weekly job's billed wall clock — CLAUDE.md treats that as a design input, not
    an afterthought.  Restricting to the systems each phase's answer actually
    lives in keeps every claim these rows make while staying off the critical
    path, and ``systems_searched`` travels on the result so the report says what
    was covered instead of concluding about the specimen.
    """
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    from pxrdref.indexing.pick import pick_peaks
    data, ins = _qarr(f"{name}.prn")
    peaks = pick_peaks(data, ins)
    spec = SearchSpec(systems=systems, max_volume=700.0,
                      budget_seconds=REAL_DATA_BUDGET_SECONDS,
                      n_unindexed=REAL_DATA_N_UNINDEXED)
    return index_pattern(peaks, data=data, instrument=ins, spec=spec)


@pytest.fixture(scope="module")
def zincite_index():
    """Hexagonal P from a lab pattern.  Hexagonal + trigonal only."""
    return _index_qarr_phase("zincite", ("hexagonal", "trigonal"))


@pytest.fixture(scope="module")
def zircon_index():
    """Tetragonal **I** — the only row that recovers a centring.  Tetragonal
    only, which is also where its I-against-P comparison lives."""
    return _index_qarr_phase("zircon", ("tetragonal",))


#: NAC (Na₂Ca₃Al₂F₁₄), the 11-BM synchrotron standard, cubic I2₁3 a = 10.2510.
A_NAC = 10.2510


@pytest.fixture(scope="module")
def nac_index():
    """The synchrotron pattern indexed over its **whole** range. ~1 s.

    Fast, because nothing happens: the run abstains before exploring a single
    box, for the reason the row explains.
    """
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    from pxrdref.indexing.pick import pick_peaks
    from tests.test_acceptance_nac import build_nac_inputs
    data, _structure, ins = build_nac_inputs()
    peaks = pick_peaks(data, ins)
    spec = SearchSpec(systems=("cubic",), max_volume=1200.0,
                      budget_seconds=REAL_DATA_BUDGET_SECONDS,
                      n_unindexed=REAL_DATA_N_UNINDEXED)
    return peaks, index_pattern(peaks, data=data, instrument=ins, spec=spec)


#: GSAS's own converged cell for `FAP.XRA` (`FAP.EXP`), which is the reference
#: this row is graded against — a **cross-code** number, not a certificate.
A_FAP, C_FAP = 9.3717, 6.8859
#: The band for that comparison, and it is **not** CLAUDE.md's ±300 ppm.  That
#: figure is what a *refinement* of this dataset must meet, with a specimen
#: displacement among its free parameters; an indexed cell has no such parameter
#: and absorbs the displacement instead.  Measured on the two patterns in this
#: file where the displacement is independently known, that absorption is worth
#: 127 ppm (SRM 660c) and ~180 ppm (SRM 676a, the gap between the two protocol
#: steps).  So the indexing band is 500 ppm: above the refinement's by about the
#: size of the effect the refinement models and this does not.  Measured here:
#: a +232 ppm, c +363 ppm.
FAP_INDEXING_PPM = 5.0e-4


@pytest.fixture(scope="module")
def fap_index():
    """The GSAS-II tutorial fluorapatite, indexed. ~95 s.

    Hexagonal and trigonal only — a declared restriction, and ``systems_searched``
    carries it — because the answer is known to be P6₃/m and an exhaustive pass
    over the lower systems costs minutes for a row about *ranking*.
    """
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    from pxrdref.indexing.pick import pick_peaks
    from tests.test_acceptance_fap import build_fap_inputs
    data, _structure, ins = build_fap_inputs()
    peaks = pick_peaks(data, ins)
    spec = SearchSpec(systems=("hexagonal", "trigonal"), max_volume=600.0,
                      budget_seconds=REAL_DATA_BUDGET_SECONDS, n_unindexed=REAL_DATA_N_UNINDEXED)
    return index_pattern(peaks, data=data, instrument=ins, spec=spec)


#: Budget for the unidentified-pattern search.  Deliberately small: the row
#: asserts an *abstention*, and a search that runs out of budget abstains for a
#: reason the result already carries (``search_complete``).  Measured, the
#: verdict is identical at 15, 25 and 45 s — 12 candidates, M₂₀ ≈ 4.6, nothing
#: promoted — so the larger budget buys no evidence and 100 s of CI.
HL2_BUDGET_SECONDS = 15.0


@pytest.fixture(scope="module")
def hl2_index():
    """The unidentified pattern, indexed. ~50 s."""
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    path = DATA / "hl2_peaks.txt"
    if not path.exists():
        pytest.skip("HL2-1 abstention fixture not present")
    tt, _d, rel = np.loadtxt(path, unpack=True)
    peaks = PeakList.from_positions(tt, wavelength=1.540596, intensity=rel)
    spec = SearchSpec(systems=REAL_DATA_SYSTEMS,
                      budget_seconds=HL2_BUDGET_SECONDS,
                      n_unindexed=REAL_DATA_N_UNINDEXED)
    return peaks, index_pattern(peaks, spec=spec)


@pytest.fixture(scope="module")
def qarr_fluorite():
    """``(peaks, quality report, result)`` for CaF₂ — and it never searches.

    Left **fast** and ungrouped on purpose: the whole row is that no engine
    starts, so it costs a peak pick (~0.1 s) and nothing else.  A `slow` mark
    here would be claiming a cost this row does not have.
    """
    from pxrdref.indexing import index_pattern
    from pxrdref.indexing.engines import SearchSpec
    from pxrdref.indexing.pick import pick_peaks
    from pxrdref.indexing.quality import assess_peak_list
    data, ins = _qarr("fluorite.prn")
    peaks = pick_peaks(data, ins)
    spec = SearchSpec(systems=REAL_DATA_SYSTEMS, max_volume=700.0,
                      budget_seconds=REAL_DATA_BUDGET_SECONDS, n_unindexed=REAL_DATA_N_UNINDEXED)
    res = index_pattern(peaks, data=data, instrument=ins, spec=spec)
    return peaks, assess_peak_list(peaks), res


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
                      budget_seconds=REAL_DATA_BUDGET_SECONDS, n_unindexed=REAL_DATA_N_UNINDEXED)
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
    # ``screen.allowance_deg`` — WP-1038.  This used to be ``abs(amplitude)``
    # computed here by hand, because ``ShiftScreen`` reported only the scatter the
    # template leaves and that is not what a window must span.  The screen now
    # computes it, by the same formula the reflection-pair road uses, so the one
    # place in the suite that knew the difference no longer has to.
    spec = SearchSpec(systems=("cubic",), max_volume=300.0, budget_seconds=REAL_DATA_BUDGET_SECONDS,
                      n_unindexed=REAL_DATA_N_UNINDEXED,
                      shift_template="cos_theta",
                      sigma_sys_deg=float(screen.allowance_deg))
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
    supplied, no shift *declared*, and the certified lattice **ranked first with
    the right centring**, both axes inside 150 ppm.

    **WP-1038 changed what "no shift measured" means here, and two caveats moved
    with it.**  The shift is now measured from harmonic reflection pairs before
    the search — −0.0639° on this pattern, against an independently known
    −0.065° — so the window is a measurement rather than the assumed 0.05°, and
    ``shift_allowance_assumed`` no longer fires.  With it the search indexes
    **51 of 55** lines where it indexed 49, which crosses the 0.9 bar unaided and
    clears ``indexed_fraction_low`` as well.  Declaring the template used to be
    what crossed that bar; now it is not, and the next test says what declaring it
    still buys.

    **The wider window is not free and the cost is recorded rather than hidden.**
    A measured 0.0680° is wider than the assumed 0.05° on *this* pattern (it is
    narrower on six of the corpus's seven fitted lists), and a is +122 ppm where
    it was +101.  The reason is knowable: the true cause is a cos θ displacement,
    whose deviation falls to ~0.26·|c| by 150° 2θ, while a window that cannot rule
    out a *constant* must stay at |c| everywhere.  That is the price of measuring
    the magnitude without being able to name the cause, and it is inside the bar.

    ``low`` remains the honest grade, on three caveats that each name something
    real: only one engine found it (``engines_disagree``); the Le Bail fit sees 12
    reflections the *lattice* R-3m allows where the pattern has no intensity,
    which is the R-3c c-glide and not an oversized cell (``predicted_but_absent``
    cannot tell those apart — WP-1025's extinction screen is what can); and the
    panel's members do not agree on the ranking (``fom_panel_disagrees``).
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
    assert best.n_indexed >= 51, f"{best.n_indexed} of {best.n_lines} lines"
    assert best.chi2_red < 1.5, best.chi2_red

    # the shift reached the search as a measurement, and said so
    assert any(d.code == "INDEX_SHIFT_FROM_PAIRS" for d in res.diagnostics)
    assert not any(d.code == "INDEX_SHIFT_ALLOWANCE" for d in res.diagnostics)
    assert "shift_allowance_assumed" not in best.confidence_caveats
    # …which is what carried indexed_fraction over its bar with nothing declared
    assert best.fom_value("indexed_fraction") >= 0.9
    assert "indexed_fraction_low" not in best.confidence_caveats

    # the gate still refuses to promote it, and every caveat names something real
    assert best.confidence == "low"
    assert set(best.confidence_caveats) >= {
        "engines_disagree", "predicted_but_absent"}
    assert best.lebail is not None and best.lebail.predicted_but_absent > 0
    assert res.best_or_none() is None, (
        "a cell was returned as the answer with caveats standing")


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance")
def test_declaring_the_shift_template_is_what_recovers_the_certificate(
        corundum_index, corundum_index_with_shift):
    """The other half of the protocol: declare the systematic, and see it fitted.

    A user cannot measure a specimen displacement's *cause* before there is a cell
    to measure it against, so the sequence is: index under the pair-measured
    allowance, then declare the template and index again.  This row is that second
    call, and it is the end-to-end evidence that ``refine_with_shift`` does what it
    exists for on real data.

    The fitted coefficient is **−0.0726 ± 0.0181°**, against a specimen
    displacement of −0.065° measured independently against the certificate
    (WP-1023) and a pre-search pair estimate of −0.0639° (WP-1038) — three routes
    to the same systematic, none of which was told the answer.

    **What declaring the template buys changed with WP-1038, and the change is
    the point.**  It used to be what carried ``indexed_fraction`` over its bar;
    now the pair-measured window does that on its own, and both calls index 51 of
    55 lines.  What is left is what the template was always actually for: the
    *cell*.  a goes +122 → −93 ppm and c +28 → −140 ppm, χ²_red 0.70 → 0.37, and
    the Le Bail Rwp 0.282 → 0.225.  So the two mechanisms are now cleanly
    separated — the measured **magnitude** widens the window and finds more lines,
    the declared **shape** corrects the cell — where before they were confounded.

    **The figures of merit are the striking part and they are not free.**  M₂₀
    goes 22 → 83 and F_N 16 → 66, because ``engines.scored_positions`` scores a
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
    assert after.lebail.rwp < before.lebail.rwp
    # the cell is what the template buys: both axes move *toward* the certificate
    assert abs(after.cell[0] - a_cert) < abs(before.cell[0] - a_cert), (
        "declaring the shape must sharpen a, not merely the figures of merit")
    # and the window already carried indexed_fraction over its bar in both calls,
    # since WP-1038 measures the magnitude before the search rather than assuming
    for c in (before, after):
        assert c.fom_value("indexed_fraction") >= 0.9
        assert "indexed_fraction_low" not in c.confidence_caveats
    # still not promoted, on caveats that have nothing to do with the shift
    assert after.confidence == "low"
    assert "shift_allowance_assumed" not in after.confidence_caveats
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


def test_a_phase_can_be_too_symmetric_to_index_from_its_own_pattern(qarr_fluorite):
    """Fluorite abstains **before any engine starts**, and the reason is sound.

    CaF₂ is Fm-3m with a = 5.4631 Å, and over this round robin's 5-150° Cu Kα
    range that lattice simply does not produce many lines: ``pick_peaks`` finds
    **18** usable, against ``PEAK_MIN_USABLE_LINES`` = 20.  So
    ``assess_peak_list`` refuses, ``systems_searched`` is **empty**, and the run
    costs 0.1 s rather than a minute of searching.

    Two things make this worth a row rather than a footnote.  It is the
    *counterintuitive* direction — high symmetry is what makes a pattern easy to
    index right up until it makes the pattern too sparse to index at all — and
    the bar is not arbitrary: M₂₀, F₂₀ and Smith's volume envelope are all
    **defined** on twenty lines, so below that the package would be reporting
    figures of merit outside their own definitions.  WP-1024's handover warned
    that two spikes were debugged before someone checked ``quality.n_usable``
    first; this row is that warning made executable.
    """
    peaks, report, res = qarr_fluorite
    assert len(peaks.usable()) < 20
    assert not report.supports_indexing
    assert report.abstained_reason and "20" in report.abstained_reason

    assert res.candidates == []
    assert res.systems_searched == [], (
        "an engine ran on a list the quality gate had already refused")
    assert res.best_or_none() is None
    codes = {d.code for d in res.diagnostics}
    assert {"INDEX_DATA_INSUFFICIENT", "INDEX_ABSTAINED"} <= codes, sorted(codes)


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance-qarr")
def test_a_hexagonal_lab_pattern_recovers_its_lattice(zincite_index):
    """ZnO wurtzite: the truth ranked first, by both engines, on lab data.

    The cleanest of the round-robin recoveries and the one that shows the panel
    working rather than being overridden — a = −217 ppm and c = −186 ppm from
    Kihara & Donnay's cell, **all 27 usable lines indexed**, M₂₀ = 902, and both
    engines agree.

    It is graded ``low`` anyway, on three caveats that each name something real,
    and the second is the point of this row.  ``predicted_but_absent`` is **4**:
    P6₃mc has a 6₃ screw (00l absent for l odd) and a c-glide, neither of which
    the *lattice* hexagonal P knows about — so this is the extinction blind spot
    again, now measured on a third space group.  With LaB₆ (no absences, 0) and
    corundum (a c-glide, 11-12) that makes a table rather than an anecdote.
    """
    res = zincite_index
    a_ref, c_ref = QARR_PHASES["zincite"][1][0], QARR_PHASES["zincite"][1][2]
    assert res.candidates
    best = res.candidates[0]

    assert best.system in ("hexagonal", "trigonal") and best.centring == "P"
    assert abs(best.cell[0] / a_ref - 1.0) < 1e-3, best.cell[0]
    assert abs(best.cell[2] / c_ref - 1.0) < 1e-3, best.cell[2]
    assert best.n_indexed == best.n_lines, (
        f"{best.n_indexed} of {best.n_lines} — the truth should index all of them")
    assert best.fom_value("m20") > 300.0
    assert set(best.found_by) == set(res.engines_run)

    # the extinction blind spot, third data point: a 6_3 screw and a c-glide
    assert best.lebail is not None and best.lebail.predicted_but_absent > 0
    assert "predicted_but_absent" in best.confidence_caveats
    assert best.confidence == "low"
    assert res.best_or_none() is None


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance-qarr")
def test_a_centred_tetragonal_lattice_is_recovered_with_its_centring(zircon_index):
    """ZrSiO₄: the only row where the answer includes a **centring**.

    Everything else recovered here is primitive (LaB₆ cubic P, zincite hexagonal
    P) or rhombohedral (corundum R), so this is the row that exercises the part
    of the pipeline CLAUDE.md flags as deliberately un-merged: two centrings of
    one metric stay *separate* candidates, because they predict different numbers
    of lines, and the figure-of-merit panel is what chooses between them
    (``engines.dedup_groups``).  Here it chooses correctly — tetragonal **I**,
    a +207 ppm and c +1906 ppm from Hazen & Finger's cell.

    Note which figure does the choosing, and note that the obvious one would
    choose **wrong**.  The primitive twin of the same metric is also in the list
    and indexes 60 of 68 observed lines against the centred cell's 59 — *more*,
    not fewer, because a cell predicting twice as many reflections can only ever
    match at least as many observed ones.  What separates them is
    ``predicted_seen_fraction``, 0.57 for I against 0.28 for P, since half of what
    P predicts is not there.  That is coverage scored *in both directions*, which
    is the whole reason the panel is a panel — and forward coverage alone would
    rank the wrong twin first.
    """
    res = zircon_index
    a_ref, c_ref = QARR_PHASES["zircon"][1][0], QARR_PHASES["zircon"][1][2]
    assert res.candidates
    best = res.candidates[0]

    assert best.system == "tetragonal" and best.centring == "I", (
        f"ranked first: {best.system} {best.centring}")
    assert abs(best.cell[0] / a_ref - 1.0) < 1e-3, best.cell[0]
    assert abs(best.cell[2] / c_ref - 1.0) < 3e-3, best.cell[2]

    # the primitive twin of the same metric, and what puts it below
    twins = [c for c in res.candidates
             if c.system == "tetragonal" and c.centring == "P"
             and abs(c.cell[0] / best.cell[0] - 1.0) < 1e-3
             and abs(c.cell[2] / best.cell[2] - 1.0) < 1e-3]
    assert twins, "the primitive twin was merged away; dedup_groups must keep it"
    twin = twins[0]
    # Forward coverage cannot separate them: the twins index 59 and 60 of 68
    # lines, i.e. the *primitive* twin explains marginally more, which is the
    # trap — a cell that predicts twice as many reflections will never index
    # fewer.  (They were exactly equal under the assumed 0.05° window; WP-1038's
    # measured 0.0299° is narrower and splits them by one line, in the direction
    # that would rank the wrong twin first if forward coverage decided.)
    assert abs(twin.n_indexed - best.n_indexed) <= 1, (
        f"forward coverage: I {best.n_indexed}, P {twin.n_indexed} of "
        f"{best.n_lines} — the twins should be within a line of each other")
    assert twin.n_indexed >= best.n_indexed, (
        "the primitive twin should not index *fewer* lines than the centred one "
        "— if it does, this row is no longer testing what it claims")
    # what actually separates them is coverage in the *reverse* direction
    assert (best.fom_value("predicted_seen_fraction")
            > 1.5 * twin.fom_value("predicted_seen_fraction"))

    # I 4_1/a m d has screw axes and glides on top of its centring
    assert best.lebail is not None and best.lebail.predicted_but_absent > 0
    assert best.confidence == "low"
    assert res.best_or_none() is None


def test_short_wavelength_data_must_be_truncated_before_it_can_be_indexed(nac_index):
    """The 11-BM synchrotron pattern cannot be indexed *as measured*, and says so.

    λ = 0.4139 Å and the pattern runs to 57.4° 2θ, so d_min = **0.43 Å**.  A
    10.25 Å cubic cell at that resolution predicts more reflections than
    ``engines.reflection_ceiling_ok`` — the crash guard in front of every
    ``generate_reflections`` call a search reaches — will allow, so the dichotomy
    rejects its very first box and explores **zero**.  The run costs 0.15 s and
    comes back with no candidate and ``search_complete[cubic] = False``.

    That is the guard working, and the row exists to pin the *shape* of the
    failure rather than the failure itself.  A null result that says "incomplete"
    is a different statement from one that says "nothing exists", and every piece
    of machinery here is built to keep those apart — ``INDEX_SEARCH_INCOMPLETE``
    fires, ``INDEX_ABSTAINED`` says explicitly that it "is not the same statement
    as none existing", and ``best_or_none()`` is None either way.

    **Truncating 2θ is the obvious fix and it was measured, and it does not
    work** — recorded so the next session does not spend the hour again.
    Picking over 2-18°, 2-25° and 2-32° raises d_min enough that the guard lets
    the dichotomy through (215 boxes each time), and the answers are still wrong:
    a = −5967, +8189 and +7997 ppm, M₂₀ = 4 in all three, and cubic **P** where
    the truth is **I**.  Each run costs 300-620 s.  So the ceiling is not what
    stands between this package and this pattern; it is only what stands first.

    The obstruction underneath is the peak list, again, and in a third form.
    This pattern begins at **0.76° 2θ**, and of the first twenty picked lines —
    which is what ``DEFAULT_SEARCH_LINES`` hands the engines — the true NAC cell
    explains only **six**, while CaF₂, its known impurity, explains **none**.  So
    the search is built from twenty lines that are mostly low-angle artifact, and
    the engines are solving for a metric that fits them.  Over the whole list the
    true cell does fine: 268 of 285.  A search-line selection that ranked on
    something other than 2θ order would change this row's outcome, which makes it
    an engine question (WP-1030) rather than an acceptance one.
    """
    peaks, res = nac_index

    assert len(peaks.usable()) > 200, "the pattern should be line-rich"
    assert res.candidates == []
    assert res.best_or_none() is None

    # the search declined rather than concluded, and the stats say how completely
    assert res.search_complete.get("cubic") is False
    assert res.engine_stats.get("dichotomy.cubic.boxes") == 0.0, (
        "the dichotomy now explores boxes here — the reflection ceiling may have "
        "moved, and this row's premise with it")
    codes = {d.code for d in res.diagnostics}
    assert {"INDEX_SEARCH_INCOMPLETE", "INDEX_ABSTAINED"} <= codes, sorted(codes)


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance-fap")
def test_the_cross_code_cell_is_found_but_not_ranked_first(fap_index):
    """Fluorapatite: the right cell is in the list, and the ranking does not lead with it.

    This is the one dataset here whose reference is **another code's converged
    result** — GSAS's own `FAP.EXP` for this exact pattern — so it grades
    agreement rather than accuracy, at ``FAP_INDEXING_PPM`` — which is *not* the
    refinement suite's ±300 ppm, for the reason that constant records.

    The candidate that meets that band is present, is the one **both engines
    agree on**, and indexes 181 of 185 lines: a = +232 ppm, c = +363 ppm.  It is
    not ranked first.  Above it sits a cell 1218 ppm out that indexes *fewer*
    lines (167) but scores a higher M₂₀ — the ordering M₂₀ produces when a
    slightly wrong metric matches a subset of lines more tightly than the right
    one matches all of them.

    So the assertion is deliberately about *membership and refusal*, not about
    rank: the correct cell is reachable, and the gate declines to hand back the
    leader.  Writing this row as "rank 0 is the answer" would have meant tuning
    the panel until it was, on a dataset whose own reference is another code's
    fit.  What the package promises is that it never hands back a confident
    wrong singleton, and here it keeps that promise while its ranking is wrong —
    which is exactly the case the promise exists for.

    The doublet is the sub-plot.  These are Cu Kα1/Kα2 data and the positions
    that reproduce GSAS's cell are **Kα1** positions, so the constrained-pair fit
    and the alias screen (``PEAK_KALPHA2_ALIAS`` fires on this pattern) are doing
    their job — a list of raw maxima would carry every Kα2 as a line and no cell
    would index it.
    """
    res = fap_index
    assert res.candidates

    band = [c for c in res.candidates
            if abs(c.cell[0] / A_FAP - 1.0) < FAP_INDEXING_PPM
            and abs(c.cell[2] / C_FAP - 1.0) < FAP_INDEXING_PPM]
    assert band, (
        "no candidate inside the indexing band: "
        + repr([tuple(round(x, 4) for x in c.cell[:3]) for c in res.candidates[:6]]))
    agreed = [c for c in band if set(c.found_by) == set(res.engines_run)]
    assert agreed, "the in-band cell was found by only one engine"
    best_in_band = agreed[0]
    assert best_in_band.system in ("hexagonal", "trigonal")
    assert best_in_band.centring == "P"
    assert best_in_band.n_indexed >= 0.95 * best_in_band.n_lines

    # …and the leader is not it, which is the honest half of the row
    leader = res.candidates[0]
    assert leader.fom_value("m20") > best_in_band.fom_value("m20")
    assert leader.n_indexed < best_in_band.n_indexed, (
        "the leader now indexes at least as many lines as the in-band cell, so "
        "the ranking inversion this row documents has changed shape")

    # the gate refuses to promote any of it
    assert res.best_or_none() is None
    for cand in res.candidates:
        assert cand.confidence != "high"


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance-hl2")
def test_an_unidentified_pattern_stays_unidentified(hl2_index):
    """The other half of an indexer, and the half a benchmark cannot measure.

    Every other real-data row here has a known answer, so every one of them
    measures whether the package finds it.  This one measures the opposite and
    is the only fixture in the suite whose compound **is genuinely unknown** —
    74 peaks picked from an unidentified laboratory pattern (``hl2_peaks.txt``,
    provenance in ``tests/data/README.md``).  There is no answer to be graded
    against, so what is asserted is the shape of the *refusal*.

    It is not a refusal by silence.  Twelve candidates come back and the leading
    ones index **73 of 74 lines** — which is exactly the trap, because forward
    coverage alone reads like a solution.  What refuses them is that every M₂₀
    is ≈ 4.6, an order below anything publishable (de Wolff's own guidance is
    M₂₀ > 10, and the bethanechol benchmark's synchrotron set reaches 197 in this
    same file), and that none survives Le Bail validation.

    The result also says what it *did* rather than what the sample *is*: which
    systems were searched, and — the honest part — whether each one's domain was
    exhausted.  An incomplete search is not evidence of absence, and
    ``search_complete`` carries that per system rather than letting a null result
    imply it.  What is asserted is that the *statement exists* for every system
    searched, not which way it came out: whether a given domain finishes inside
    ``HL2_BUDGET_SECONDS`` depends on how busy the machine is, and an assertion
    that depends on that is a load sensor rather than a claim (see
    ``REAL_DATA_BUDGET_SECONDS`` for the row that learned this the hard way).
    """
    peaks, res = hl2_index

    # the input is a bare position list, so its precision is assumed, not measured
    assert peaks.source == "positions"
    assert all("sigma_assumed" in p.flags for p in peaks.peaks)

    # the verdict
    assert res.best_or_none() is None
    assert not res.validated
    for cand in res.candidates:
        assert cand.confidence == "low", (cand.system, cand.confidence)

    # and it is refused on merit, not on coverage — the leaders index almost
    # everything and are still nowhere near a credible figure of merit
    assert res.candidates, "no candidate at all is a weaker result than a bad one"
    leader = res.candidates[0]
    assert leader.n_indexed >= 0.8 * leader.n_lines
    assert max(c.fom_value("m20") for c in res.candidates) < 10.0, (
        "a candidate reached a publishable M20 on a pattern nobody has solved")

    # it reports coverage rather than concluding about the specimen
    assert set(res.systems_searched) == set(REAL_DATA_SYSTEMS)
    assert set(res.search_complete) == set(REAL_DATA_SYSTEMS), (
        "a system was searched without reporting whether its domain was "
        "exhausted, which is what stops a null being read as 'none exists'")
    codes = {d.code for d in res.diagnostics}
    assert "INDEX_ABSTAINED" in codes


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
    # extinctions — but the list has been shrinking, and by *evidence* each time.
    # ``shift_allowance_assumed`` went first: WP-1038 measures this pattern's
    # +0.0345° from harmonic pairs before the search, against the +0.0367° the
    # reference-based screen fits and the +0.0415° its recorded geometry predicts,
    # so the window is a measurement.  ``engines_disagree`` went second, in
    # WP-1039: ``trial_error`` was not failing to *find* the certified cell, it was
    # being handed the wrong lines to solve from.  Its base-line pool took the
    # lowest-Q lines of the whole list, and five of this pattern's low-angle
    # components are not lines of the phase; drawn instead from the strongest-N
    # selection the pool is clean, the exact solve lands, and **both engines find
    # it**.  Note what did *not* follow: on a cubic-only search the run promotes to
    # ``high``, and here it does not, because a four-system search leaves
    # ``fom_panel_disagrees`` behind.  Agreement was necessary, not sufficient.
    assert best.confidence == "low"
    assert set(best.confidence_caveats) == {"fom_panel_disagrees"}, (
        f"the caveat list moved: {sorted(best.confidence_caveats)}")
    assert set(best.found_by) == {"dichotomy", "trial_error"}, (
        f"only {best.found_by} found the certified cell")
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
def test_a_certified_shift_is_recovered_from_the_peak_list_alone(lab6_peaks):
    """SRM 660c's specimen displacement, measured with **no reference at all**.

    This is WP-1038's headline claim on a certified pattern, and the reason it is
    checkable here rather than only in principle: the CIF records −0.07877 mm at
    R = 217.5 mm, so the displacement is *predicted* parameter-free at +0.0415°
    cos θ, and the reference-based screen fits +0.0367 ± 0.0015° against it.  The
    reflection-pair method sees neither the certificate nor the prediction — only
    harmonic pairs among the list's own lines, ``m·sin θ = sin θ'`` — and lands at
    **+0.0345°**, within 0.4σ of the reference-based fit and at 0.83 of the
    geometric prediction, which is the same 0.75-1.0 band the reference-based
    screen is held to for the same reason (the other aberrations SRM 660c's
    docstring names are still in the residual).

    Note what is *not* claimed.  ``separable`` is False: ``constant`` and
    ``cos_theta`` concentrate within one pair of each other, so the method has
    measured a magnitude, not named a cause.
    """
    from pxrdref.indexing.quality import screen_shift_from_pairs

    screen = screen_shift_from_pairs(lab6_peaks.two_theta(),
                                     lab6_peaks.two_theta_esd())
    assert screen.source == "reflection_pairs", screen.pairs.declined_reason
    amp = next(t.coefficient for t in screen.templates if t.name == screen.best)

    predicted = np.degrees(-2.0 * SRM660C_DISPLACEMENT_MM / SRM660C_RADIUS_MM)
    assert amp == pytest.approx(0.0345, abs=0.004)
    assert amp == pytest.approx(0.0367, abs=0.005), (
        "the pair estimate must agree with the reference-based fit it never saw")
    assert 0.75 < amp / predicted < 1.0, (
        f"{amp:+.4f}° against a parameter-free geometric {predicted:+.4f}°")

    # the evidence, not just the number
    assert screen.pairs.n_clustered >= 8
    assert screen.pairs.z >= PAIR_MIN_Z
    assert screen.pairs.p_value <= 0.01
    # a magnitude, not a cause
    assert not screen.separable
    assert screen.allowance_deg > abs(amp)


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-acceptance-qarr")
def test_one_shift_is_measured_from_a_multi_phase_pattern(corundum_peaks):
    """Dong's own two-phase result, on this package's bundled data.

    Dong (1999) §3's second example indexes Pr₂Ni₁₋ₓLiₓO₄ containing NiO, and its
    point is that two of the eleven pairs come from the **impurity** and agree
    with the other nine: a harmonic pair constrains the *instrument*, not the
    lattice, so it does not matter which phase produced it.  That is what makes
    the method usable on exactly the patterns indexing is hardest on.

    Checked here both ways.  Corundum, single phase, gives −0.0639° against an
    independently measured −0.065°.  ``cpd-1a`` is the IUCr round-robin's
    **three-phase** mixture — corundum, zincite and fluorite on the same
    diffractometer — and returns −0.0382° from pairs its own screen cannot
    attribute to any one phase, with no cell for any of them.
    """
    from pxrdref.indexing.pick import pick_peaks
    from pxrdref.indexing.quality import screen_shift_from_pairs

    single = screen_shift_from_pairs(corundum_peaks.two_theta(),
                                     corundum_peaks.two_theta_esd())
    assert single.source == "reflection_pairs", single.pairs.declined_reason
    amp = next(t.coefficient for t in single.templates if t.name == single.best)
    assert amp == pytest.approx(-0.065, abs=0.005), (
        f"{amp:+.4f}° against the −0.065° measured against the certificate")
    assert single.pairs.z >= PAIR_MIN_Z

    data, ins = _qarr("cpd-1a.prn")
    mixture = screen_shift_from_pairs(*(lambda p: (p.two_theta(),
                                                   p.two_theta_esd()))(
        pick_peaks(data, ins)))
    assert mixture.source == "reflection_pairs", mixture.pairs.declined_reason
    m_amp = next(t.coefficient for t in mixture.templates
                 if t.name == mixture.best)
    assert m_amp == pytest.approx(-0.038, abs=0.010)
    assert mixture.pairs.z >= PAIR_MIN_Z
    # the two specimens were run on the same instrument, and the shifts agree to
    # well inside the spread a specimen-mounting difference would produce
    assert abs(m_amp - amp) < 0.030


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
    spec = SearchSpec(systems=("cubic",), max_volume=300.0, budget_seconds=REAL_DATA_BUDGET_SECONDS,
                      n_unindexed=REAL_DATA_N_UNINDEXED,
                      shift_template="cos_theta",
                      sigma_sys_deg=float(screen.sigma_sys_deg))
    tight = index_pattern(_without_the_off_lattice_lines(lab6_peaks),
                          data=data, instrument=ins, spec=spec)
    assert tight.candidates == [], (
        "the post-correction residual now indexes — re-read the docstring, the "
        "σ_sys semantics may have been fixed")
