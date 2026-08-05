"""The pictures every indexing acceptance row leaves, and the page that indexes them.

``tests/CLAUDE.md`` carries a standing rule — *every test refinement also writes
obs/calc/diff PNGs to ``tests/output/`` for visual inspection; Rwp hides
locally-bad fits* — and until WP-1041 the whole indexing suite was its one
exception: ``grep -n "savefig" tests/test_acceptance_indexing.py`` returned
nothing, on 38 rows, several of which exist entirely to make a claim about lines
on a real pattern.  This module closes it.

Two things live here because they are one thing.  :func:`draw` writes a dataset's
gallery, and beside the PNGs it writes a small JSON **sidecar** recording what the
run actually did.  :func:`summary_html` then reads the sidecars back and renders
the one-page benchmark summary — dataset, provenance, what is asserted, what
happened, and the picture — so the summary is *generated from the measurement*
rather than maintained beside it.  A hand-written summary of a suite this size
goes stale between sessions; this one cannot say anything the run did not.

**One sidecar per dataset, never one shared file.**  The acceptance rows are
spread over five ``xdist_group``s and therefore over up to five workers, so an
appended manifest would interleave.  One writer per file has no such failure, and
the assembler is a glob.

**Why the Le Bail panel costs a second fit.**  ``index_pattern`` validates each
candidate and keeps the verdict, not the curve (``validate_by_lebail``'s docstring
has the reason: a ``LeBailValidation`` is a few hundred bytes and a
``RefinementResult`` carries y_obs/y_calc over every channel).  So a picture of
the fit means asking for one, which is exactly what ``with_result=True`` exists
for.  Measured on corundum, the refit reproduces the stored verdict *exactly* —
Rwp 0.2822 against 0.2822, 12 predicted-but-absent against 12 — which is the
property that matters: the picture cannot disagree with the number printed beside
it.  The whole gallery cost 10.2 s against that row's search, and the search is
where the time is.

Run ``python -m tests.indexing_gallery`` after an acceptance run to build the page.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

OUTPUT = pathlib.Path(__file__).parent / "output"
#: Sidecars are named so one glob finds them and nothing else in ``output/``
#: matches — that directory holds ~120 files from the refinement suites.
SIDECAR_GLOB = "indexing_*.gallery.json"

#: What each dataset **is**, and what its rows claim about it.  Declared here
#: rather than scraped from docstrings, for the reason ``PLAN_INFO`` is declared
#: rather than derived from plan names: a summary a reader trusts has to say what
#: was asserted, and a test name is not that.  :func:`draw` refuses an undeclared
#: stem, so a new dataset cannot reach the gallery without saying what it is.
#:
#: ``tier`` is the same vocabulary the acceptance suites already use for how far a
#: number may be trusted — ``certificate`` (a certified cell), ``cross-code``
#: (another refinement program's answer), ``consistency`` (a literature cell for
#: the mineral, not for this specimen), ``published`` (a printed benchmark), and
#: ``none`` (an unidentified pattern, where the claim is about the abstention).
DATASETS: dict[str, dict[str, str]] = {
    "corundum": {
        "title": "SRM 676a corundum — indexed with nothing declared",
        "provenance": "IUCr CPD QPA round robin, qarr/corundum.prn; Cu Kα doublet, "
                      "graphite diffracted-beam monochromator. NIST SRM 676a cell.",
        "tier": "certificate",
        "asserts": "the certified trigonal R lattice ranked first with the right "
                   "centring, both axes inside 150 ppm, and the grade honestly low "
                   "on three caveats that each name something real.",
    },
    "corundum_shift": {
        "title": "SRM 676a corundum — with the cos θ shift template declared",
        "provenance": "as above; the second half of the two-step protocol.",
        "tier": "certificate",
        "asserts": "declaring the shape moves the *cell* toward the certificate "
                   "(a +122 → −93 ppm) while the pair-measured window had already "
                   "carried indexed_fraction over its bar.",
    },
    "corundum_peaks": {
        "title": "SRM 676a corundum — the picked line list the search is given",
        "provenance": "as above, pick_peaks output before any search.",
        "tier": "certificate",
        "asserts": "the phantom components that blocked this dataset are flagged: "
                   "each sits ~0.17–0.24° below a line more than 4× stronger.",
    },
    "cpd1a": {
        "title": "A three-phase mixture — the correct answer is a refusal",
        "provenance": "IUCr CPD QPA round robin, qarr/cpd-1a.prn: corundum + "
                      "zincite + fluorite.",
        "tier": "none",
        "asserts": "best_or_none() is None and no candidate reaches high — a "
                   "coverage score cannot tell a multiphase pattern from a "
                   "single-phase one of lower symmetry.",
    },
    "fluorite": {
        "title": "CaF₂ — too symmetric to index from its own pattern",
        "provenance": "IUCr CPD QPA round robin, qarr/fluorite.prn; Fm-3m, "
                      "a = 5.4631 Å.",
        "tier": "none",
        "asserts": "the run abstains before any engine starts: 18 usable lines "
                   "against PEAK_MIN_USABLE_LINES = 20.",
    },
    "zincite": {
        "title": "Zincite — a hexagonal P lattice from a lab pattern",
        "provenance": "IUCr CPD QPA round robin, qarr/zincite.prn; literature cell "
                      "P 6₃ m c a = 3.2499, c = 5.2066 Å.",
        "tier": "consistency",
        "asserts": "the hexagonal lattice is recovered at the level a lab d-scale "
                   "supports — a lattice type and a centring, never a ppm figure.",
    },
    "zircon": {
        "title": "Zircon — the row that recovers a centring",
        "provenance": "IUCr CPD QPA round robin, qarr/zircon.prn; literature cell "
                      "I 4₁/a m d a = 6.6042, c = 5.9796 Å.",
        "tier": "consistency",
        "asserts": "tetragonal **I**, not the P description of the same axes — the "
                   "only acceptance row whose claim is a centring.",
    },
    "nac": {
        "title": "11-BM NAC — synchrotron, and a CaF₂ impurity",
        "provenance": "APS 11-BM, 11BM_NAC.fxye, λ = 0.4139090 Å from the .prm. "
                      "Na₂Ca₃Al₂F₁₄, cubic I2₁3, a = 10.2510 Å.",
        "tier": "certificate",
        "asserts": "the cubic I cell is found at +19 ppm by svd and trial_error — "
                   "dichotomy enumerates nothing at this wavelength, so "
                   "engines_disagree stands and the gate refuses to promote.",
    },
    "fap": {
        "title": "Fluorapatite — a cross-code comparison, not a certificate",
        "provenance": "GSAS-II LabData tutorial, FAP.XRA; the reference cell is "
                      "GSAS's own converged answer in FAP.EXP (a = 9.3717, "
                      "c = 6.8859 Å).",
        "tier": "cross-code",
        "asserts": "the cross-code cell is *found* but not ranked first, inside "
                   "500 ppm — the band an indexed cell earns, wider than a "
                   "refinement's ±300 ppm because it has no displacement parameter.",
    },
    "hl2": {
        "title": "An unidentified pattern stays unidentified",
        "provenance": "hl2_peaks.txt — a position list for a phase with no known "
                      "cell. Cu Kα.",
        "tier": "none",
        "asserts": "12 candidates, M₂₀ ≈ 4.6, nothing promoted; the verdict is "
                   "identical at 15, 25 and 45 s of budget.",
    },
    "lab6": {
        "title": "NIST SRM 660c LaB6 — the absolute anchor",
        "provenance": "NIST certification data, nist_srm660c_100a.cif (_meas "
                      "block); Cu Kα doublet + graphite analyzer. a = 4.156780 Å "
                      "at this block's 20.85 °C.",
        "tier": "certificate",
        "asserts": "the certified cubic cell at −2 ppm with no extinction caveat "
                   "(P m -3 m has none) — and, since WP-1041, **not** uniquely: "
                   "both centrings of its a·√2 supercell are found by every engine.",
    },
    "lab6_calibrated": {
        "title": "SRM 660c LaB6 — everything the gate can be given, given",
        "provenance": "as above, with the off-lattice tail components removed and "
                      "the shift measured against the certificate.",
        "tier": "certificate",
        "asserts": "what the *gate* does once the evidence exists, rather than "
                   "what the search can find.",
    },
    "lab6_peaks": {
        "title": "SRM 660c LaB6 — the picked list, and its tail components",
        "provenance": "as above, pick_peaks output.",
        "tier": "certificate",
        "asserts": "the unflagged tail components escape for three different "
                   "reasons, and sit on the axial-divergence side below 90° 2θ.",
    },
    "brucite": {
        "title": "Brucite — the ranking prefers a supercell",
        "provenance": "IUCr CPD QPA round robin, qarr/brucite.prn; literature "
                      "cell P -3 m 1 a = 3.142, c = 4.766 Å (Zigan & Rothbauer). "
                      "This specimen's a sits +1750 ppm from it — a literature "
                      "cell is a cell for the mineral, not for the specimen.",
        "tier": "consistency",
        "asserts": "what the ranking does when a supercell explains everything "
                   "the truth does: the c × 3 supercell leads, and the gate "
                   "refuses to promote it.",
    },
    "magnetite": {
        "title": "Magnetite — a subcell above a cubic F truth",
        "provenance": "IUCr CPD QPA round robin, qarr/magnetit.prn; literature "
                      "cell F d -3 m a = 8.3941 Å.",
        "tier": "consistency",
        "asserts": "the second of the two datasets WP-1026 measured and did not "
                   "land; both were measured before WP-1030's prunes and are "
                   "re-measured here rather than quoted.",
    },
    "bethanechol": {
        "title": "Bethanechol chloride — the one externally graded benchmark",
        "provenance": "Bergmann, Le Bail, Shirley & Zlokazov (2004), Z. Kristallogr. "
                      "219, 783: ten peak sets at six levels of difficulty, with "
                      "every program's score printed in Table 5.",
        "tier": "published",
        "asserts": "the published figures of merit are reproduced unfloored, and "
                   "the published cell reproduces the paper's own impurity counts. "
                   "The global score is a measured no-go, not an unfinished row — "
                   "the paper's search domain exhausts every budget.",
    },
}


#: ``stem -> (conventional cell, centring)`` for the datasets whose lattice is
#: known.  This is what turns the gallery into the **scoreboard**: with a truth
#: declared, :func:`draw` records where in the ranking that lattice landed, so
#: "five put the right lattice first" is generated from the run rather than
#: retyped into three documents.  A dataset with no entry has no known cell, and
#: its rows claim an abstention rather than an answer (cpd-1a, hl2).
TRUTHS: dict[str, tuple[tuple[float, ...], str]] = {
    "corundum": ((4.759355, 4.759355, 12.99231, 90.0, 90.0, 120.0), "R"),
    "corundum_shift": ((4.759355, 4.759355, 12.99231, 90.0, 90.0, 120.0), "R"),
    "lab6": ((4.156780,) * 3 + (90.0, 90.0, 90.0), "P"),
    "lab6_calibrated": ((4.156780,) * 3 + (90.0, 90.0, 90.0), "P"),
    "zincite": ((3.2499, 3.2499, 5.2066, 90.0, 90.0, 120.0), "P"),
    "zircon": ((6.6042, 6.6042, 5.9796, 90.0, 90.0, 90.0), "I"),
    "nac": ((10.2510,) * 3 + (90.0, 90.0, 90.0), "I"),
    "fap": ((9.3717, 9.3717, 6.8859, 90.0, 90.0, 120.0), "P"),
    "brucite": ((3.142, 3.142, 4.766, 90.0, 90.0, 120.0), "P"),
    "magnetite": ((8.3941,) * 3 + (90.0, 90.0, 90.0), "F"),
    "fluorite": ((5.4631,) * 3 + (90.0, 90.0, 90.0), "F"),
}


def truth_rank(stem: str, ranking: list[dict[str, Any]]) -> int | None:
    """1-based rank of the declared truth in a stored ``ranking``, or ``None``.

    **The centring is half the test, and leaving it out is the mistake this
    package has now made at three ranks.**  ``same_lattice`` compares A..F after
    Niggli reduction, so a *setting* change is equality — which is what it is
    for — but a primitive description of a centred lattice reduces to the same
    metric with a different content, and calling that a match reads a wrong
    answer as right.  Measured: without the centring clause both NAC candidates
    scored as the truth, and only one of them is (``engines.solution_key``
    carries the same lesson one rank down, WP-1040's monoclinic row a rank up).

    It reads the **stored** ranking rather than live candidates on purpose.  The
    A..F vectors are seven numbers a candidate already has, so keeping them costs
    nothing, and it means declaring a truth for a dataset later re-scores the
    scoreboard from sidecars already on disk instead of needing a 26-minute
    acceptance run — which is exactly the loop this was first written without.
    """
    import numpy as np

    from pxrdref.indexing.qspace import af_from_cell
    from pxrdref.indexing.reduce import same_lattice

    if stem not in TRUTHS:
        return None
    cell, centring = TRUTHS[stem]
    af_true = af_from_cell(cell)
    for i, row in enumerate(ranking):
        if row.get("centring") != centring:
            continue
        if same_lattice(np.asarray(row["af"], dtype=float), af_true)[0]:
            return i + 1
    return None


def _close(fig) -> None:
    import matplotlib.pyplot as plt
    plt.close(fig)


def draw(stem: str, *, peaks, data=None, result=None, instrument=None,
         spec=None, n: int = 5, validate: bool = True,
         note: str = "") -> dict[str, Any]:
    """Write one dataset's gallery and its sidecar; return the sidecar.

    ``peaks`` is the only required input, because it is the only thing every row
    has: a peak list is what the search was *given*, and every real-data indexing
    failure this package has measured was visible there first.  ``result`` adds
    the ranked-candidate tick rows, and ``data`` + ``instrument`` add the Le Bail
    obs/calc/diff panel for the top candidate.

    **Pass the ``spec`` the search ran under.**  It is what
    :func:`~pxrdref.indexing.engines.match_window` needs to reproduce the window
    the search matched in, and without it the tick rows are drawn in the raw
    per-line σ — which on any pattern carrying a shift allowance contradicts the
    candidate's own ``n_indexed`` in the same figure.

    Never raises on a missing picture — a search that abstained has no candidates
    to rank and no fit to draw, and that is the row's *point* rather than a
    failure.  It does raise on an **undeclared stem**, which is the one thing a
    silent skip would hide: a dataset in the suite and not in the summary.
    """
    if stem not in DATASETS:
        raise KeyError(
            f"{stem!r} has no entry in indexing_gallery.DATASETS — a dataset "
            "reaching the gallery must say what it is and what is asserted "
            "about it, or the summary page silently omits it")

    from pxrdref.viz.indexing import plot_candidates, plot_peak_list, plot_validation

    OUTPUT.mkdir(exist_ok=True)
    figures: list[str] = []
    card: dict[str, Any] = {"stem": stem, **DATASETS[stem], "note": note,
                            "figures": figures}

    name = f"indexing_{stem}_peaks.png"
    _close(plot_peak_list(peaks, data, path=str(OUTPUT / name)))
    figures.append(name)
    usable = peaks.usable()
    card["n_usable"] = len(usable)
    card["n_picked"] = len(peaks.peaks)
    card["wavelength"] = round(float(peaks.wavelength), 6)
    card["two_theta_range"] = [round(float(peaks.two_theta_min), 3),
                               round(float(peaks.two_theta_max), 3)]

    if result is None:
        _write(stem, card)
        return card

    cands = list(getattr(result, "candidates", ()) or ())
    card["n_candidates"] = len(cands)
    card["systems_searched"] = list(getattr(result, "systems_searched", ()) or ())
    card["validated"] = bool(getattr(result, "validated", False))
    best_or_none = result.best_or_none() if hasattr(result, "best_or_none") else None
    card["promoted"] = best_or_none is not None
    card["diagnostics"] = sorted({d.code for d in getattr(result, "diagnostics", ())})

    # the whole ranking, compactly — seven numbers and two strings per candidate,
    # which is what lets the scoreboard be re-scored without re-running a search
    card["ranking"] = [{
        "system": c.system, "centring": c.centring,
        "af": [float(v) for v in c.af],
        "cell": [round(float(v), 5) for v in c.cell],
        "volume": round(float(c.volume), 2),
        "n_indexed": int(c.n_indexed), "confidence": c.confidence,
    } for c in cands]

    if not cands:
        card["outcome"] = "abstained — no candidate"
        _write(stem, card)
        return card

    from pxrdref.indexing.engines import match_window

    name = f"indexing_{stem}_candidates.png"
    _close(plot_candidates(cands, peaks, n=n, path=str(OUTPUT / name),
                           q_match=match_window(peaks, spec,
                                                getattr(result, "quality", None))))
    figures.append(name)

    best = cands[0]
    card["ranked_first"] = {
        "system": best.system, "centring": best.centring,
        "cell": [round(float(v), 5) for v in best.cell],
        "volume": round(float(best.volume), 2),
        "n_indexed": int(best.n_indexed), "n_lines": int(best.n_lines),
        "found_by": list(best.found_by),
        "confidence": best.confidence,
        "caveats": list(best.confidence_caveats),
        "fom": {f.name: round(float(f.value), 4) for f in best.fom},
    }
    card["outcome"] = (
        f"{best.system} {best.centring}, {best.n_indexed}/{best.n_lines} lines, "
        f"confidence {best.confidence}"
        + (" — promoted" if best_or_none is not None else " — not promoted"))

    if best.lebail is not None:
        card["lebail"] = {
            "rwp": round(float(best.lebail.rwp), 4),
            "gof": round(float(best.lebail.gof), 3),
            "space_group": best.lebail.space_group,
            "n_reflections": int(best.lebail.n_reflections),
            "predicted_but_absent": int(best.lebail.predicted_but_absent),
            "unmatched_observed": int(best.lebail.unmatched_observed),
            "status": best.lebail.status,
        }

    if validate and data is not None and instrument is not None:
        card.update(_validation_panel(stem, best, peaks, data, instrument, figures))
    elif best.lebail is not None:
        # positions only.  Strictly worse than the fit panel and drawn anyway:
        # the two detector lists are what separate a wrong metric from an
        # oversized one, and they need no refit.
        name = f"indexing_{stem}_validation.png"
        _close(plot_validation(best.lebail, path=str(OUTPUT / name)))
        figures.append(name)

    _write(stem, card)
    return card


def _validation_panel(stem, best, peaks, data, instrument, figures) -> dict:
    """The obs/calc/diff panel behind the gate, and the check that it is the same fit.

    The refit is compared against the verdict ``index_pattern`` already stored.
    They agree exactly when nothing is stochastic between them, and a
    disagreement is worth knowing about rather than worth drawing over — so it is
    recorded in the sidecar instead of asserted here, where a picture-drawing
    helper has no business failing a row.
    """
    from pxrdref.indexing.workflow import validate_by_lebail
    from pxrdref.viz.indexing import plot_validation

    validation, result = validate_by_lebail(
        best, data, instrument, peaks=peaks, with_result=True)
    name = f"indexing_{stem}_validation.png"
    _close(plot_validation(validation, result, path=str(OUTPUT / name)))
    figures.append(name)

    out: dict[str, Any] = {"validation_refit": {
        "rwp": round(float(validation.rwp), 4),
        "predicted_but_absent": int(validation.predicted_but_absent),
        "unmatched_observed": int(validation.unmatched_observed),
    }}
    if best.lebail is not None:
        out["validation_refit"]["reproduces_stored"] = bool(
            validation.predicted_but_absent == best.lebail.predicted_but_absent
            and abs(validation.rwp - best.lebail.rwp) < 1e-9)
    return out


#: The scoreboard's vocabulary, and it is deliberately **four** buckets rather
#: than the three the pre-WP-1041 wording used.  "Right" and "wrong" cannot
#: absorb the case this package produces most: the true lattice is *in the list*
#: and something else leads it, which is neither a success nor a failure and is
#: what FAP and NAC both do.  Collapsing it either way is how a scoreboard gets
#: rounded up.
VERDICTS = {
    "first": "the true lattice is ranked first",
    "present": "the true lattice is found but not ranked first",
    "absent": "the true lattice is not among the candidates",
    "refused": "no engine ran — the quality gate refused the list",
    "unknown": "no cell is known for this dataset; the claim is the abstention",
}


def _verdict(card: dict[str, Any]) -> str:
    if not card.get("has_truth"):
        return "unknown"
    if not card.get("n_candidates"):
        return "refused" if not card.get("systems_searched") else "absent"
    rank = card.get("truth_rank")
    if rank == 1:
        return "first"
    return "present" if rank else "absent"


def _write(stem: str, card: dict[str, Any]) -> None:
    (OUTPUT / f"indexing_{stem}.gallery.json").write_text(
        json.dumps(card, indent=2), encoding="utf-8")


def add_figure(stem: str, filename: str) -> None:
    """Append a figure to a card :func:`draw` already wrote.

    For the pictures a *row* has and the dataset does not — a deviation plot for
    the row about tail components, say.  Silently does nothing when the card is
    absent, because that is a selection running one row without its fixture's
    sibling, not an error.
    """
    path = OUTPUT / f"indexing_{stem}.gallery.json"
    if not path.exists():
        return
    card = json.loads(path.read_text(encoding="utf-8"))
    if filename not in card.setdefault("figures", []):
        card["figures"].append(filename)
    _write(stem, card)


def draw_deviation(stem: str, name: str, two_theta, deviation, *,
                   split_deg: float | None = None, title: str = "",
                   marked=None, marked_label: str = "") -> str:
    """Signed distance from each picked line to its nearest reference position.

    The picture the LaB6 tail-component rows need and the three generic
    renderers cannot give them: those components are **unflagged**, so
    :func:`~pxrdref.viz.indexing.plot_peak_list` draws them exactly like the real
    lines — which is the finding, not a shortcoming.  What separates them is
    *where they sit*, and the sign is the measurement (the real lines carry the
    specimen displacement one way; the survivors sit on the other side of their
    own line below the axial-divergence crossover).
    """
    import matplotlib.pyplot as plt
    import numpy as np

    OUTPUT.mkdir(exist_ok=True)
    tt = np.asarray(two_theta, dtype=np.float64)
    dev = np.asarray(deviation, dtype=np.float64)
    fig, ax = plt.subplots(figsize=(11, 3.6), dpi=150)
    ax.axhline(0.0, lw=0.8, color="#999999", zorder=1)
    if split_deg is not None:
        ax.axvline(split_deg, lw=0.8, ls="--", color="#7a7a7a", zorder=1,
                   label=f"{split_deg:g}°")
    keep = np.ones(len(tt), dtype=bool) if marked is None else ~np.asarray(marked)
    ax.plot(tt[keep], dev[keep], "o", ms=4.5, color="#1f5fa8", zorder=3,
            label=f"on the reference lattice ({int(keep.sum())})")
    if marked is not None and (~keep).any():
        ax.plot(tt[~keep], dev[~keep], "D", ms=5.5, color="#c23b22", zorder=4,
                label=marked_label or f"off-lattice ({int((~keep).sum())})")
    ax.set_xlabel(r"2$\theta$ (deg)")
    ax.set_ylabel(r"signed $\Delta 2\theta$ to nearest reference line (deg)")
    ax.set_title(title or name, fontsize=10)
    ax.legend(loc="best", fontsize=8, frameon=False)
    fig.tight_layout()
    fname = f"indexing_{stem}_{name}.png"
    fig.savefig(OUTPUT / fname)
    _close(fig)
    add_figure(stem, fname)
    return fname


def draw_benchmark_sets(stem: str, sets: dict, predicted: dict, *,
                        note: str = "") -> dict[str, Any]:
    """The ten published peak sets, stacked, against the cell the paper solved.

    One figure rather than ten, because the benchmark's whole shape is the
    *comparison* between its levels of difficulty — the synchrotron set where
    every line is explained, against the ICDD entries carrying a zeroshift and
    impurity lines.  Ten separate stem plots would hide exactly that.

    ``predicted`` maps a set name to the 2θ its published cell allows over that
    set's range; a line further than ``EXPLAINED_DEG`` from all of them is drawn
    as an impurity, which is the paper's own count reproduced as a picture.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    OUTPUT.mkdir(exist_ok=True)
    names = list(sets)
    fig, ax = plt.subplots(figsize=(11, 0.55 * len(names) + 1.6), dpi=150)
    n_impurity = {}
    for row, name in enumerate(names):
        tt = np.asarray(sets[name], dtype=np.float64)
        pred = np.asarray(predicted[name], dtype=np.float64)
        gap = np.min(np.abs(tt[:, None] - pred[None, :]), axis=1)
        bad = gap > 0.08          # tests.test_acceptance_indexing.EXPLAINED_DEG
        n_impurity[name] = int(bad.sum())
        y = -float(row)
        ax.vlines(tt[~bad], y - 0.30, y + 0.30, lw=1.1, color="#1f5fa8",
                  zorder=3)
        if bad.any():
            ax.vlines(tt[bad], y - 0.34, y + 0.34, lw=1.6, color="#c23b22",
                      zorder=4)
        # labels in fixed gutters (axes coordinates), not beside each set's own
        # first line: the sets span different ranges — E and F are synchrotron —
        # so a data-relative label lands inside another set's lines
        ax.text(-0.012, y, name, fontsize=8, ha="right", va="center",
                color="#4a4a4a", transform=ax.get_yaxis_transform())
        ax.text(1.012, y, f"{int(bad.sum())} unexplained", fontsize=7.5,
                ha="left", va="center", color="#7a7a7a",
                transform=ax.get_yaxis_transform())
    ax.plot([], [], color="#1f5fa8", lw=1.1, label="explained by the published cell")
    ax.plot([], [], color="#c23b22", lw=1.6, label="unexplained (impurity)")
    ax.set_yticks([])
    ax.set_ylim(-len(names) + 0.4, 0.9)
    ax.set_xlabel(r"2$\theta$ (deg)")
    ax.set_title("Bergmann et al. (2004) bethanechol chloride: ten peak sets "
                 "against the published monoclinic cell", fontsize=10)
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    fig.tight_layout()
    fname = f"indexing_{stem}_sets.png"
    fig.savefig(OUTPUT / fname)
    _close(fig)

    card: dict[str, Any] = {
        "stem": stem, **DATASETS[stem], "note": note, "figures": [fname],
        "two_theta_range": [
            round(min(float(np.min(v)) for v in sets.values()), 3),
            round(max(float(np.max(v)) for v in sets.values()), 3)],
        "n_lines_total": sum(len(v) for v in sets.values()),
        "n_sets": len(names),
        "unexplained_per_set": n_impurity,
        "outcome": (f"{len(names)} sets, 20 lines each; "
                    f"{sum(n_impurity.values())} lines in total are not "
                    f"explained by the published cell"),
    }
    _write(stem, card)
    return card


# ----------------------------------------------------------------------
# the one-page summary
# ----------------------------------------------------------------------
#: The order datasets appear on the page.  Certified anchors first, then the
#: consistency-tier minerals, then the rows whose claim is an abstention, then
#: the published benchmark — which is the order of how much a reader may
#: conclude from each, not the order the suite happens to run them in.
PAGE_ORDER = ("lab6", "lab6_calibrated", "lab6_peaks", "corundum",
              "corundum_shift", "corundum_peaks", "nac",
              "fap", "zincite", "zircon", "brucite", "magnetite",
              "cpd1a", "fluorite", "hl2", "bethanechol")

#: The scoreboard's datasets, one row each — the **known-cell** ones plus
#: fluorite, whose whole result is that it is refused before any engine starts.
#: ``corundum_shift`` and ``lab6_calibrated`` are deliberately absent: they are
#: the *second step* of a two-step protocol on a dataset already counted, and
#: counting a dataset twice is how the pre-WP-1041 scoreboard came to name nine
#: datasets under a total of eight.
SCOREBOARD_STEMS = ("lab6", "corundum", "nac", "fap", "zincite", "zircon",
                    "brucite", "magnetite", "fluorite")


def scoreboard(cards: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The known-cell scoreboard, counted from the sidecars.

    The pre-WP-1041 wording was "five right, one refused, two fail" over "eight
    known-cell datasets", and it had two defects this replaces rather than
    reproduces.  **Its arithmetic did not close**: 5 + 1 + 2 = 8 while *nine*
    datasets are named across the buckets, because NAC was described inside the
    failure bucket without being counted, and FAP was counted as putting the
    right lattice first by a sentence that says in the same breath it is second.
    And **two of its rows were prose**: brucite and magnetite were measured
    before WP-1030's prunes landed and were never test rows, so the scoreboard
    quoted numbers no run reproduced.

    Both are structural, so the fix is structural: the buckets are
    :data:`VERDICTS`, computed per dataset from ``truth_rank``, and this
    function is the only place that counts them.
    """
    cards = load_cards() if cards is None else cards
    by_stem = {c["stem"]: c for c in cards}
    rows, counts = [], dict.fromkeys(VERDICTS, 0)
    for stem in SCOREBOARD_STEMS:
        card = by_stem.get(stem)
        if card is None:
            continue
        verdict = card.get("verdict", "unknown")
        counts[verdict] += 1
        rows.append({
            "stem": stem, "verdict": verdict,
            "truth_rank": card.get("truth_rank"),
            "n_candidates": card.get("n_candidates", 0),
            "promoted": bool(card.get("promoted")),
            "outcome": card.get("outcome", ""),
        })
    return {"rows": rows, "counts": counts, "n": len(rows),
            "n_promoted": sum(r["promoted"] for r in rows),
            "missing": [s for s in SCOREBOARD_STEMS if s not in by_stem]}


def load_cards() -> list[dict[str, Any]]:
    """Every sidecar the last run left, in :data:`PAGE_ORDER`, re-scored.

    ``truth_rank`` and ``verdict`` are computed **here**, not stored, so a truth
    added to :data:`TRUTHS` takes effect on the sidecars already on disk.
    """
    cards = {}
    for path in sorted(OUTPUT.glob(SIDECAR_GLOB)):
        card = json.loads(path.read_text(encoding="utf-8"))
        card["has_truth"] = card["stem"] in TRUTHS
        card["truth_rank"] = truth_rank(card["stem"], card.get("ranking", []))
        card["verdict"] = _verdict(card)
        cards[card["stem"]] = card
    ordered = [cards[s] for s in PAGE_ORDER if s in cards]
    ordered += [c for s, c in sorted(cards.items()) if s not in PAGE_ORDER]
    return ordered


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def summary_html(cards: list[dict[str, Any]] | None = None) -> str:
    """The one-page benchmark summary, generated from the sidecars.

    HTML rather than markdown because the last column is a *picture*, and a
    summary whose pictures are links is a summary nobody looks at — which is the
    failure mode the whole plotting rule exists to prevent.
    """
    cards = load_cards() if cards is None else cards
    missing = [s for s in PAGE_ORDER
               if s not in {c["stem"] for c in cards}]
    rows = []
    for card in cards:
        figs = "".join(
            f'<figure><img src="{_esc(f)}" alt="{_esc(f)}">'
            f'<figcaption>{_esc(f)}</figcaption></figure>'
            for f in card.get("figures", ()))
        facts = []
        if "n_usable" in card:
            facts.append(f"<b>{card['n_usable']}</b> usable of "
                         f"{card['n_picked']} picked lines, λ = "
                         f"{card['wavelength']} Å")
        if "n_sets" in card:
            facts.append(f"<b>{card['n_sets']}</b> sets, "
                         f"{card['n_lines_total']} lines; unexplained per set: "
                         + ", ".join(f"{k} {v}" for k, v in
                                     card["unexplained_per_set"].items()))
        facts.append(f"{card['two_theta_range'][0]}–"
                     f"{card['two_theta_range'][1]}° 2θ")
        if "n_candidates" in card:
            facts.append(f"{card['n_candidates']} candidates; "
                         f"searched {', '.join(card['systems_searched']) or '—'}")
        rf = card.get("ranked_first")
        if rf:
            facts.append(
                f"ranked first <b>{rf['system']} {rf['centring']}</b> "
                f"a={rf['cell'][0]:.5f} V={rf['volume']:.1f} Å³, "
                f"{rf['n_indexed']}/{rf['n_lines']} indexed, found by "
                f"{', '.join(rf['found_by']) or '—'}")
            caveats = ", ".join(rf["caveats"]) or "none"
            facts.append(f"confidence <b>{rf['confidence']}</b>; caveats: {caveats}")
        lb = card.get("lebail")
        if lb:
            facts.append(
                f"Le Bail {lb['space_group']}: Rwp={lb['rwp']}, "
                f"{lb['predicted_but_absent']}/{lb['n_reflections']} predicted "
                f"but absent, {lb['unmatched_observed']} unmatched observed")
        refit = card.get("validation_refit")
        if refit and "reproduces_stored" in refit:
            facts.append("the drawn fit reproduces the stored verdict"
                         if refit["reproduces_stored"] else
                         "<b>the drawn fit differs from the stored verdict</b>")
        if card.get("note"):
            facts.append(_esc(card["note"]))
        rows.append(
            f'<section><h2>{_esc(card["title"])}'
            f'<span class="tier">{_esc(card["tier"])}</span></h2>'
            f'<p class="prov"><b>Provenance.</b> {_esc(card["provenance"])}</p>'
            f'<p class="asserts"><b>Asserted.</b> {_esc(card["asserts"])}</p>'
            f'<p class="outcome"><b>Measured.</b> '
            f'{_esc(card.get("outcome", "peak list only — no search on this row"))}'
            f'</p><ul>' + "".join(f"<li>{f}</li>" for f in facts) + "</ul>"
            f'<div class="figs">{figs}</div></section>')

    warn = (f'<p class="warn">Not in this run: {", ".join(missing)}. '
            f'Run the full acceptance selection to fill the page.</p>'
            if missing else "")
    board = _scoreboard_html(cards)
    return f"""<!doctype html>
<meta charset="utf-8"><title>pxrdref indexing benchmark gallery</title>
<style>
 body {{ font: 15px/1.5 -apple-system, system-ui, sans-serif; max-width: 1100px;
        margin: 2rem auto; padding: 0 1rem; color: #222; }}
 h1 {{ font-size: 1.6rem; }}
 h2 {{ font-size: 1.1rem; margin: 2.2rem 0 .3rem; border-bottom: 1px solid #ddd;
       padding-bottom: .25rem; }}
 .tier {{ float: right; font-size: .72rem; font-weight: 600; letter-spacing: .04em;
          text-transform: uppercase; color: #666; border: 1px solid #ccc;
          border-radius: 3px; padding: 1px 6px; }}
 p {{ margin: .3rem 0; }}
 .prov, .asserts {{ color: #444; }}
 .outcome {{ color: #1f5fa8; }}
 ul {{ margin: .4rem 0 .8rem 1.1rem; padding: 0; color: #333; font-size: .93rem; }}
 figure {{ margin: .6rem 0; }}
 figcaption {{ font-size: .75rem; color: #888; }}
 img {{ max-width: 100%; border: 1px solid #eee; }}
 .warn {{ background: #fff6e0; border-left: 3px solid #f2c14e; padding: .5rem .8rem; }}
 .lede {{ color: #444; }}
 table {{ border-collapse: collapse; width: 100%; font-size: .88rem;
          margin: .6rem 0; }}
 th, td {{ text-align: left; padding: .28rem .5rem;
           border-bottom: 1px solid #eee; vertical-align: top; }}
 th {{ color: #666; font-weight: 600; font-size: .8rem; text-transform: uppercase;
       letter-spacing: .03em; }}
 .v-first {{ color: #1f7a1f; font-weight: 600; }}
 .v-present {{ color: #a06000; font-weight: 600; }}
 .v-absent {{ color: #a8195f; font-weight: 600; }}
 .v-refused, .v-unknown {{ color: #666; }}
</style>
<h1>pxrdref — indexing benchmark gallery</h1>
<p class="lede">Generated from the sidecars
<code>tests/output/{SIDECAR_GLOB}</code> that
<code>tests/test_acceptance_indexing.py</code> writes, so nothing on this page is
maintained by hand and nothing here can say more than the run did. Datasets are
ordered by how much may be concluded from each — certified cells first, then
literature cells for a mineral, then the rows whose whole claim is an abstention.
</p>
{warn}
{board}
{"".join(rows)}
"""


def _scoreboard_html(cards: list[dict[str, Any]]) -> str:
    board = scoreboard(cards)
    if not board["rows"]:
        return ""
    counted = ", ".join(f"<b>{board['counts'][v]}</b> {v}"
                        for v in VERDICTS if board["counts"][v])
    body = "".join(
        f'<tr><td>{_esc(r["stem"])}</td>'
        f'<td class="v-{r["verdict"]}">{_esc(r["verdict"])}</td>'
        f'<td>{r["truth_rank"] if r["truth_rank"] else "—"} '
        f'of {r["n_candidates"]}</td>'
        f'<td>{"yes" if r["promoted"] else "no"}</td>'
        f'<td>{_esc(r["outcome"])}</td></tr>'
        for r in board["rows"])
    miss = (f'<p class="warn">Not measured in this run: '
            f'{", ".join(board["missing"])}.</p>' if board["missing"] else "")
    return f"""<section id="scoreboard"><h2>The known-cell scoreboard</h2>
<p class="prov">{board['n']} datasets whose lattice is known independently:
{counted}. <b>{board['n_promoted']}</b> of {board['n']} were promoted — a cell
handed back as the answer rather than as a ranked candidate.</p>
{miss}
<table><thead><tr><th>dataset</th><th>verdict</th><th>truth rank</th>
<th>promoted</th><th>measured</th></tr></thead><tbody>{body}</tbody></table>
<p class="lede">Read the shape rather than the count: this feature is
<b>never wrong, and silent more often than right</b>. Every verdict here is
computed from the run — the truth's rank is a <code>same_lattice</code> test on
the reduced A..F vector <em>and</em> the centring, since a primitive description
of a centred lattice reduces to the same metric and calling that a match reads a
wrong answer as right.</p></section>"""


def write_summary(path: pathlib.Path | None = None) -> pathlib.Path:
    out = path or (OUTPUT / "indexing_gallery.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(summary_html(), encoding="utf-8")
    return out


if __name__ == "__main__":       # pragma: no cover - operator entry point
    written = write_summary()
    n = len(load_cards())
    print(f"{written}  ({n} of {len(PAGE_ORDER)} datasets)")
