"""The bethanechol benchmark, run and **scored** — this package's only published
scoreboard, and the one number in the milestone that has to be generated.

Bergmann, Le Bail, Shirley & Zlokazov (2004), *Z. Kristallogr.* **219**, 783-790
ran eleven indexing programs over one compound at six levels of difficulty and
printed both the data (Table 6) and every program's score (Table 5).  The data
and the scores are transcribed in ``tests/data/bethanechol_indexing.json``, which
``tests/test_acceptance_indexing.py`` checks against three statements the paper
makes in prose and never tabulates.  **That file proves the fixture; this one
runs the benchmark.**

Why a module you run and not a ``slow`` pytest row
--------------------------------------------------
The protocol is ten sets × two modes, three engines each, and the default mode
searches **all seven crystal systems** — a full run is tens of minutes of pure
search (this session's measurement is in WP-1026's handover log).  A slow-marked
row of that size would land on the weekly job's critical path for a number that
moves only when an engine moves.  So the score is *generated on demand*, the
acceptance suite keeps the transcription checks and asserts **no score**, and
:func:`score_of_rank` — the arithmetic, not the search — is pinned by a fast row
there.  The shape was decided in WP-1043 § *Measured: bethanechol*.

Run it::

    .venv/bin/python -m tests.bethanechol_benchmark            # the whole protocol
    .venv/bin/python -m tests.bethanechol_benchmark --sets F --modes manual
    .venv/bin/python -m tests.bethanechol_benchmark --budget 120

It prints the per-set table and the global, and writes
``tests/output/bethanechol_benchmark.json`` (gitignored, like every other
measurement artifact) so a later read does not need a second run.

Three protocol rules, each of which changes the number
------------------------------------------------------
**The protocol is quoted from the fixture, never retyped.**  :func:`spec_for`
reads ``default_mode`` and ``manual_mode`` out of the JSON — the paper's own
"maximum cell parameters of 20 Å and V_max = 2000 Å³" and its manual-mode
"monoclinic, volume 800-1200 Å³, 5-20 Å axes, 8 unindexed lines tolerated".
Adopting a protocol means adopting it whole (root CLAUDE.md): a score over a
narrower domain is not comparable with Table 5, and the *default* mode's cost is
almost entirely the six systems the answer is not in.

**The run declares ``preset="full"``.**  Since WP-1042 ``quick`` is
``index_pattern``'s default and carries a 120 s whole-run ceiling that would cut
trailing low-symmetry systems — an *anytime* answer, which is the right default
for a person at a GUI and the wrong one for a graded benchmark, because a
truncated domain is a statement about the clock.  ``budget_seconds`` (per
engine × system) is the only bound here, it is recorded in every record, and
``search_complete`` is reported beside every score.

**A candidate cell is a lattice, not a tuple.**  The published cell comes back in
other settings — WP-1030 met it as ``c + a`` at β = 139.70°, and this runner's
own first result was (7.1346, 16.4091, 11.7530, β 131.107°) for a published
(8.875, 16.408, 7.137, β 93.84°), the same lattice with not one axis in common —
so the match is :func:`indexing_gallery.rank_of_lattice`: the centring, and
:data:`TRUTH_BAND` on the **Niggli-reduced** cell.  One implementation, shared
with the known-cell scoreboard; comparing conventional axes scored that correct
rank-1 answer −1 until this benchmark caught it.

What the score can and cannot say
---------------------------------
The paper's rule is ±1 per run over twenty runs (:func:`score_of_rank`), and the
bar is the **individual** program globals of Table 5 — ITO13 −14, DICVOL91 −8,
TREOR90 −4, McMaille +5, Crysfire 2003 +6.  ("≥ +9" was that table's ``first_4``
row, an *oracle* over four programs that no single entry reaches; restated by
WP-1026, and the fixture carries both.)

Two things the record must carry beside the global, because a bare score hides
them.  **Whether a set was winnable at all**: ``n_unindexed`` is an absolute
budget over the driven lines, so a set with more unexplained lines than the mode
tolerates cannot return the truth however good the search is — that is a
statement about the protocol, and ``reachable`` records it per run.  And
**how close the search came**: ``nearest`` reports the candidate whose reduced
cell sits closest to the published one, so a −1 that missed by 200 ppm and a −1
that found nothing resembling the answer are distinguishable in the artifact
rather than identical in the table.

And one knob exists because the first graded run needed it.  ``--max-candidates``
overrides ``SearchSpec.max_candidates``, the **per-engine** cap applied before
consensus ranks.  Measured on set F in manual mode: at a 30 s budget both engines
find the published lattice and the consensus panel puts it **3rd**, but at the
package default of 12 it is absent from the result entirely — each engine's own
Borda over its own larger harvest drops it below twelfth, and consensus never
sees it.  The graded run uses the package defaults, because the paper's default
mode *is* "the programs' default values"; the override is how the score's
sensitivity to that cap is measured rather than argued.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time
from dataclasses import replace
from typing import Any

import numpy as np

from pxrdref.indexing.engines import SearchSpec
from pxrdref.indexing.fom import predicted_lines
from pxrdref.indexing.qspace import af_from_cell, cell_from_af
from pxrdref.indexing.reduce import reduced_af
from pxrdref.indexing.workflow import index_pattern
from pxrdref.schemas.indexing import PeakList
from tests import indexing_gallery as gallery

DATA = pathlib.Path(__file__).parent / "data"
BENCH = DATA / "bethanechol_indexing.json"
OUTPUT = pathlib.Path(__file__).parent / "output"
ARTIFACT = OUTPUT / "bethanechol_benchmark.json"

#: The preset a graded run must declare (WP-1042).  Not a default: ``quick``'s
#: ceiling would silently truncate the six systems the answer is not in, and a
#: truncated domain scores the clock rather than the search.
PRESET = "full"

#: 2θ window (°) within which an observed line counts as explained by the
#: published cell.  Generous on purpose: these are 1993-era ICDD entries carrying
#: a ~0.06° systematic, and the question is "is this line a line of this
#: compound", not "how precise is it".
EXPLAINED_DEG = 0.08

#: Relative band on the **reduced** cell for "this candidate *is* the published
#: lattice", the second of :func:`indexing_gallery.rank_of_lattice`'s two
#: conditions.  An order looser than any band in that module's ``TRUTHS`` table,
#: and **the width is measured rather than chosen**: the paper's own +0.100°
#: zeropoint, left uncorrected on the A and B sets, biases a cell fitted to the
#: published lattice's own lines by **−6400 / −5190 / −4990 ppm** over these
#: sets' 5.4-21.7° 2θ range (probe in WP-1026's handover; the reduced angle moves
#: only 0.023°).  That is the accuracy a *correct* answer has on the raw ICDD
#: entries — the answers the paper scores +1 — so any band below ~6500 ppm scores
#: the benchmark's central difficulty as a miss.  1 % is that floor with 1.6×
#: headroom, and it stays a small box: a rival must match all three reduced
#: lengths to 1 % *and* the angles to 0.5° *and* the centring.
#:
#: ``nearest`` in every record is what keeps this honest in the other direction.
#: It prints how far the closest candidate actually sat, so a match at the edge
#: of the band is visible rather than rounded to "found", and the printed table
#: carries the matched candidate's own deviation beside its score.
TRUTH_BAND = 1e-2

#: The paper's own rule, from the text preceding Table 5; the fixture's
#: ``scoring`` block carries the three values and the key name carries the ten.
TOP_N = 10


def load() -> dict[str, Any]:
    return json.loads(BENCH.read_text(encoding="utf-8"))


def truth_cell(bench: dict) -> tuple[float, ...]:
    a = bench["answer"]
    return (a["a"], a["b"], a["c"], a["alpha"], a["beta"], a["gamma"])


def positions(bench: dict, name: str) -> tuple[np.ndarray, float]:
    s = bench["sets"][name]
    return np.array(s["two_theta"], dtype=np.float64), float(s["wavelength"])


def predicted(bench: dict, name: str, pad: float = 1.06) -> np.ndarray:
    """2θ of every line the published lattice allows over this set's range."""
    tt, lam = positions(bench, name)
    _, q = predicted_lines(truth_cell(bench), "monoclinic", "P", lam,
                           two_theta_max=float(tt.max()) * pad)
    return np.degrees(2.0 * np.arcsin(np.clip(lam * np.sqrt(q) / 2.0, -1.0, 1.0)))


def best_offset(bench: dict, name: str,
                tol: float = EXPLAINED_DEG) -> tuple[float, int]:
    """(δ, n explained) maximising the lines the published cell accounts for.

    A scan rather than a mean: the impurity lines never match at any δ, so a
    least-squares offset would be dragged by them.
    """
    tt = positions(bench, name)[0]
    pred = predicted(bench, name)
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


def spec_for(bench: dict, mode: str, *,
             budget_seconds: float | None = None,
             max_candidates: int | None = None) -> SearchSpec:
    """The paper's search domain for one mode, read out of the fixture.

    ``default`` is "the programs' default values … in all crystal symmetries"
    with the paper's two stated ceilings, so every other field — the systems, the
    two unindexed lines, the twenty search lines — is **this package's own
    default**, which is what the instruction means.  ``manual`` is the paper's
    "special conditions" block: monoclinic only, 800-1200 Å³, 5-20 Å axes, eight
    unindexed lines tolerated.
    """
    if mode == "default":
        block = bench["default_mode"]
        spec = SearchSpec(max_d_axis=float(block["max_d_axis"]),
                          max_volume=float(block["max_volume"]))
    elif mode == "manual":
        block = bench["manual_mode"]
        spec = SearchSpec(systems=tuple(block["systems"]),
                          min_d_axis=float(block["min_d_axis"]),
                          max_d_axis=float(block["max_d_axis"]),
                          min_volume=float(block["min_volume"]),
                          max_volume=float(block["max_volume"]),
                          n_unindexed=int(block["n_unindexed"]))
    else:
        raise ValueError(f"unknown mode {mode!r}; the paper has two")
    if budget_seconds is not None:
        spec = replace(spec, budget_seconds=float(budget_seconds))
    if max_candidates is not None:
        spec = replace(spec, max_candidates=int(max_candidates))
    return spec


def score_of_rank(bench: dict, rank: int | None) -> int:
    """The paper's ±1 rule: first, in the top ten, or not found.

    The three values are read from the fixture's ``scoring`` block rather than
    written here, so the rule this package grades itself by is the transcribed
    one — the same discipline as the domain.
    """
    rule = bench["scoring"]
    if rank is None or rank > TOP_N:
        return int(rule["not_found"])
    if rank == 1:
        return int(rule["found_first"])
    return int(rule["found_in_top_ten"])


def _nearest(ranking: list[dict[str, Any]], cell: tuple[float, ...]
             ) -> dict[str, Any] | None:
    """The candidate whose **reduced** cell sits closest to the published one.

    Reported whatever the verdict, because "not found" covers both a search that
    came back 200 ppm out in another setting and one that returned nothing like
    the answer, and the table cannot tell them apart.  Reduced, so a setting
    change is not counted as distance — the same reason the match itself reduces.
    """
    if not ranking:
        return None
    want = cell_from_af(reduced_af(af_from_cell(cell)))
    best = None
    for i, row in enumerate(ranking):
        got = cell_from_af(reduced_af(np.asarray(row["af"], dtype=float)))
        lengths = max(abs(g / w - 1.0) for g, w in zip(got[:3], want[:3]))
        angles = max(abs(g - w) for g, w in zip(got[3:], want[3:]))
        # one number to order by, over six parameters in two units: the angles
        # enter as a fraction of 90°, so "1 % out" means the same on both halves.
        # Ordering only — the record prints the two components, because that is
        # what a reader has to judge a near-miss on.
        distance = max(lengths, angles / 90.0)
        if best is None or distance < best["_distance"]:
            best = {"_distance": distance, "rank": i + 1,
                    "centring": row.get("centring"),
                    "cell": [round(float(v), 4) for v in row["cell"]],
                    "reduced": [round(float(v), 4) for v in got],
                    "max_rel_length_ppm": round(lengths * 1e6, 1),
                    "max_angle_deg": round(angles, 3)}
    if best is not None:
        best.pop("_distance")
    return best


def run_one(bench: dict, name: str, mode: str, *,
            budget_seconds: float | None = None,
            max_candidates: int | None = None) -> dict[str, Any]:
    """One (set, mode) run, scored.  Everything the table needs is in the dict."""
    tt, lam = positions(bench, name)
    peaks = PeakList.from_positions(tt, wavelength=lam)
    spec = spec_for(bench, mode, budget_seconds=budget_seconds,
                    max_candidates=max_candidates)
    t0 = time.perf_counter()
    result = index_pattern(peaks, spec=spec, preset=PRESET)
    elapsed = time.perf_counter() - t0

    ranking = [{"system": c.system, "centring": c.centring,
                "af": [float(v) for v in c.af],
                "cell": [round(float(v), 5) for v in c.cell],
                "volume": round(float(c.volume), 2),
                "n_indexed": int(c.n_indexed),
                "found_by": list(c.found_by),
                "confidence": c.confidence}
               for c in result.candidates]
    rank = gallery.rank_of_lattice(ranking, truth_cell(bench),
                                   bench["answer"]["centring"], TRUTH_BAND)
    n_unexplained = 20 - best_offset(bench, name)[1]
    return {
        "set": name, "mode": mode,
        "elapsed_s": round(elapsed, 1),
        "preset": result.preset,
        "budget_seconds": spec.budget_seconds,
        "max_candidates": spec.max_candidates,
        "engines_run": list(result.engines_run),
        "systems_searched": list(result.systems_searched),
        "search_complete": dict(result.search_complete),
        "n_candidates": len(ranking),
        "n_unexplained": n_unexplained,
        "n_unindexed": spec.n_unindexed,
        # a set the mode cannot win: the truth would have to leave more lines
        # unindexed than the protocol tolerates, which no search can fix
        "reachable": n_unexplained <= spec.n_unindexed,
        "truth_rank": rank,
        "truth_found_by": (list(result.candidates[rank - 1].found_by)
                           if rank is not None else []),
        "score": score_of_rank(bench, rank),
        "promoted": result.best_or_none() is not None,
        "nearest": _nearest(ranking, truth_cell(bench)),
        "top": ranking[0] if ranking else None,
    }


def run(bench: dict | None = None, *, sets: list[str] | None = None,
        modes: list[str] | None = None,
        budget_seconds: float | None = None,
        max_candidates: int | None = None,
        out: pathlib.Path | None = None,
        records: list[dict[str, Any]] | None = None,
        verbose: bool = True) -> dict[str, Any]:
    """The whole protocol (or the slice named), scored, as one report dict.

    ``out`` is rewritten after **every** run rather than once at the end, and
    ``records`` seeds it with runs already on disk (``--append``): the paper's
    *default* mode searches all seven systems and costs far more per set than its
    monoclinic-only manual mode, so the protocol is naturally run in two sittings
    and a report that only exists if the last search returns is a report you
    re-run from scratch after any interruption.
    """
    bench = bench if bench is not None else load()
    sets = sets or list(bench["sets"])
    modes = modes or ["default", "manual"]
    records = list(records or [])
    done = {(r["set"], r["mode"]) for r in records}
    for mode in modes:
        for name in sets:
            if (name, mode) in done:
                if verbose:
                    print(f"  {name:>2s} {mode:<8s} … already in the artifact")
                continue
            if verbose:
                print(f"  {name:>2s} {mode:<8s} …", end="", flush=True)
            rec = run_one(bench, name, mode, budget_seconds=budget_seconds,
                          max_candidates=max_candidates)
            records.append(rec)
            if verbose:
                near = rec["nearest"]
                print(f" {rec['elapsed_s']:6.1f} s  rank="
                      f"{rec['truth_rank'] or '-':>3}  score={rec['score']:+d}"
                      f"  nearest={near['max_rel_length_ppm'] if near else '-'} ppm")
            if out is not None:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(_report(bench, records, budget_seconds,
                                                  max_candidates), indent=1),
                               encoding="utf-8")
    return _report(bench, records, budget_seconds, max_candidates)


def _report(bench, records, budget_seconds, max_candidates):
    return {
        "records": records,
        "global": sum(r["score"] for r in records),
        # the best score the protocol *allows* this package: a set whose truth
        # leaves more lines unindexed than the mode tolerates cannot be returned
        # however good the search is, so it is a -1 the search never had a say in
        "ceiling": sum(1 if r["reachable"] else -1 for r in records),
        "n_runs": len(records),
        "complete_protocol": (
            {(r["set"], r["mode"]) for r in records}
            == {(n, m) for n in bench["sets"] for m in ("default", "manual")}),
        "published": bench["scoring"]["published"],
        "preset": PRESET,
        "truth_band": TRUTH_BAND,
        "budget_seconds": budget_seconds,
        "max_candidates": max_candidates,
    }


def table(report: dict[str, Any]) -> str:
    """The per-set table the acceptance criterion asks to be printed."""
    modes = sorted({r["mode"] for r in report["records"]})
    by = {(r["set"], r["mode"]): r for r in report["records"]}
    names = sorted({r["set"] for r in report["records"]},
                   key=lambda n: (n[0], n[1:]))
    head = (f"{'set':<4}" + "".join(f"{m + ' (rank, ppm)':>22}" for m in modes)
            + "   reachable")
    lines = [head, "-" * len(head)]
    for n in names:
        row = f"{n:<4}"
        flags = []
        for m in modes:
            r = by.get((n, m))
            if r is None:
                row += f"{'-':>22}"
                continue
            rank = "-" if r["truth_rank"] is None else str(r["truth_rank"])
            near = r["nearest"]
            # the score never appears without the accuracy beside it: a -1 that
            # missed by 200 ppm and a -1 that found nothing resembling the cell
            # are the same character in the score column and different results
            ppm = "-" if near is None else f"{near['max_rel_length_ppm']:.0f}"
            row += f"{r['score']:+d} (r{rank}, {ppm})".rjust(22)
            flags.append("y" if r["reachable"] else "n")
        lines.append(row + "   " + "/".join(flags))
    lines.append("-" * len(head))
    # per mode, because the paper's own grid is per mode and the two modes are
    # not comparable work: manual is monoclinic-only with eight unindexed lines
    # tolerated, default is all seven systems with the package's own two
    sub = f"{'':<4}"
    for m in modes:
        rows = [r for r in report["records"] if r["mode"] == m]
        sub += (f"{sum(r['score'] for r in rows):+d} of "
                f"{sum(1 if r['reachable'] else -1 for r in rows):+d}").rjust(22)
    lines.append(sub + "   subtotal / ceiling")
    lines.append(f"{'':<4}{'global':>10} {report['global']:+d}"
                 f"   over {report['n_runs']} runs, ceiling "
                 f"{report['ceiling']:+d}"
                 + ("" if report["complete_protocol"] else "  (PARTIAL — not the "
                    "paper's protocol, not comparable with Table 5)"))
    lines.append("ceiling = +1 per reachable run, −1 per run whose truth leaves "
                 "more lines unindexed than the mode tolerates")
    ind = report["published"]["individual_globals"]
    lines.append("published individual globals: "
                 + ", ".join(f"{k} {v:+d}" for k, v in ind.items()
                             if not k.startswith("_")))
    for key in ("first_4", "best_of_all"):
        per_set = report["published"][key]["per_set"]
        # the published per_set values are [default, manual] pairs, so the
        # oracles' own per-mode split is transcribed data, not our arithmetic
        d = sum(v[0] for v in per_set.values())
        m = sum(v[1] for v in per_set.values())
        lines.append(f"published {key}: {report['published'][key]['global']:+d}"
                     f"  (default {d:+d}, manual {m:+d})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sets", nargs="*", default=None,
                   help="set names (default: all ten)")
    p.add_argument("--modes", nargs="*", default=None,
                   choices=["default", "manual"],
                   help="modes (default: both)")
    p.add_argument("--budget", type=float, default=None,
                   help="budget_seconds per (engine x system); default is the "
                        "package's own DEFAULT_BUDGET_SECONDS")
    p.add_argument("--max-candidates", type=int, default=None,
                   help="override SearchSpec.max_candidates, the PER-ENGINE cap "
                        "applied before consensus ranks; the package default of "
                        "12 discards candidates the consensus panel then rates "
                        "highly (WP-1026, set F)")
    p.add_argument("--append", action="store_true",
                   help="seed from the runs already in --out and skip them; the "
                        "protocol's two modes cost very differently and are "
                        "naturally run in two sittings")
    p.add_argument("--out", type=pathlib.Path, default=ARTIFACT)
    args = p.parse_args(argv)

    bench = load()
    print(f"bethanechol benchmark — preset={PRESET}, "
          f"budget={args.budget or 'package default'} s per (engine x system), "
          f"max_candidates={args.max_candidates or 'package default'}")
    prior = []
    if args.append and args.out.exists():
        prior = json.loads(args.out.read_text(encoding="utf-8"))["records"]
        print(f"appending to {len(prior)} run(s) already in {args.out}")
    report = run(bench, sets=args.sets, modes=args.modes,
                 budget_seconds=args.budget, records=prior,
                 max_candidates=args.max_candidates, out=args.out)
    print()
    print(table(report))
    print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
