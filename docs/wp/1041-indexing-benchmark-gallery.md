# WP-1041 — The indexing benchmark gallery

Milestone: v1.0 · Status: ⬜
Depends on: WP-1026

## Goal

Every indexing acceptance row leaves a picture: the picked peaks over the real
pattern, the ranked candidates' tick marks, and the Le Bail validation fit. Today
the indexing suite draws nothing at all.

## Context

### Inherited

**From [1016](1016-sequential-series-panel.md), 2026-08-05 — two measured facts
about drawing an esd, since this WP's whole deliverable is pictures.** Both were
measured against the bundled **plotly 3.7.0** (what `/plotly.js` serves; the
Python `plotly` package is 6.9.0 and the two version independently) and neither
transfers to matplotlib without checking — but the *reasoning* does.

- **A `null` in `error_y.array` does not leave a gap.** plotly draws the bar's two
  caps at the point with zero height between them — byte-identical to what a `0`
  produces — so a quantity with no esd renders as one measured exactly, which is a
  confident-wrong singleton in picture form. The fix is a second, invisible trace
  carrying the bars over only the points that *have* an esd
  (`lib/series.ts:trajectoryTraces`). If this gallery plots a candidate's fitted
  quantities with esds, it has the same problem: some candidates carry `cov_af`
  and some do not.
- **An esd smaller than a pixel must be left invisible.** Measured: σ(a) = 6.5e-6 Å
  against a 4.8e-3 Å axis over 189 px is a 0.5 px bar, and 0.5 px is what was
  drawn. That is the data, and scaling it to be seen would be WP-1029's "an
  exaggeration is not a probability" — the rule it set for ellipsoid probability
  levels, which applies to any error indicator a picture draws.

**From WP-1040, 2026-08-05 — the scoreboard is stale a second time, and it now has
a third column.** `search_svd` is registered, so `index_pattern` runs **three**
engines by default and `high` requires all three to agree. Two rows already moved:
SRM 660c LaB6 is found by all three, and **11-BM NAC is indexed as measured** —
a = 10.2512 Å cubic I, +19 ppm, `predicted_but_absent` 0 of 837, by `svd` alone —
where the acceptance file previously asserted it could not be. Anything the
gallery says about NAC abstaining is wrong as of that commit.

Three things to carry into the re-measure:

* **the wall clock moved**: the indexing acceptance file is 36 rows and **20:03**
  against 11:58 with two engines. That is the price of the confidence gate, not a
  regression, but it is the number the gallery's own cost claims must use.
* **`trial_error._solution_key` has two defects, and both were measured in
  `svd.py` where they were fixed.** (1) It is **scale-invariant**, so for a
  one-dimensional metric — cubic, and only cubic — every candidate hashes to one
  key and the engine reports **at most one cubic candidate per system search**.
  (2) Its `seen` set spans the **centring loop** while the key carries no
  centring, so **the first centring tried claims a metric and every later one is
  silently discarded** — and `P` is first in `centrings_for`. Defect (2) is not
  hypothetical: it put 11-BM NAC's answer back as cubic **P** with 92
  predicted-and-absent reflections in place of the cubic **I** description of
  identical axes, and it contradicts `dedup_groups`' own rule that two centrings
  of one metric are two hypotheses. WP-1040 left `trial_error` alone on purpose
  — changing a shipped engine's dedup inside a WP about a third engine is an
  unmeasured behaviour change — but both fixes are one line each and both will
  move rows, so **do them before recording the counts, not after.**
* **The panel's aggregation leads with the wrong candidate when two centrings of
  one metric are both returned**, which is now reachable. `borda_scores` weighs
  all seven members alike, so on NAC the four forward members outvote the three
  reversed ones 4-3 even though `m_rev` separates the two **516×** (356.1 vs
  0.69). Balancing the two directions is *not* the fix — it produces a tie. This
  needs a magnitude-aware aggregate measured across every acceptance row, which
  is squarely this WP's kind of work; `test_short_wavelength_data_is_indexed_…`
  pins the current order with an assertion that inverts when it lands.
* **bethanechol A-D are unreachable, and it is *not* the zeroshift — that was
  measured and the answer came back no** (WP-1040 task 3, 2026-08-05; the bullet
  here previously said the opposite and was a prediction, not a measurement).
  Coelho's zero-error column landed and the per-trial hit rate on the ten
  published sets did not move at all. Closest approach to the true lattice over
  1500 random starts, in `equal_reduced`'s relative units where 0.005 is a hit:
  **six of the ten never get inside 0.21-0.33** under any pass strategy, while
  the four that get inside 0.03 improve 3-17× with it on. Half the A-D sets
  barely have a shift — the paper's blanket −0.100° is right for PDF 43-1748 and
  wrong for 46-1964, so `Ab`/`Bb` need ~0.003° and `Cb`/`Db` need −0.103°. What
  blocks the `a` entries is that they carry **7 impurity lines in 20**, past the
  33 % Coelho's own N_c/N_o gate says it tolerates and past anything his Table 6
  tests. **So score the benchmark as it stands** — there is no pending fix to
  wait for, and the global number is a real result about impurity tolerance
  rather than a handicap.

**From WP-1039, closed 2026-08-05.** You now own the eight-dataset scoreboard's
numbers: CLAUDE.md keeps the *rule* ("never wrong, and silent more often than
right; never let a summary round it up") and points here for the counts, which
had been "five right, one refused, two fail, all eight abstain". **They are stale
and at least one has moved** — SRM 660c no longer reports `engines_disagree`,
because both engines now find the certified cell once `trial_error` solves from
the selected lines rather than the whole list's low-Q end. Re-measure rather than
copy. A second row worth a picture while you are there: NAC truncated to ≤ 32° now
ranks the truth first at −22 ppm with the right centring, where WP-1026 recorded
that experiment as useless.

Also inherited, as a caution about this WP's own artefacts: a
`validation_matrix.py` Claim's `measured` prose went **two WPs** out of date
without failing anything, because the per-Claim meta-tests check structure and not
prose. A gallery is the same species of artefact. Generate it from live runs.

### The gap

`tests/CLAUDE.md` carries a standing rule — *"every test refinement also writes
obs/calc/diff PNGs to `tests/output/` for visual inspection; Rwp hides locally-bad
fits"* — and `tests/output/` holds ~120 files from the refinement suites.
**`tests/test_acceptance_indexing.py` writes zero.** So does every other indexing
test module. `grep -n "plot\|matplotlib\|savefig"` across all of
`src/pxrdref/indexing/` returns only the phrase "figure of merit".

The only picked-peak overlay anywhere is
`tests/test_peak_picking.py::test_pull_calibration_writes_overlays`, which draws
`peak_picking_groups.png` and `peak_picking_pattern.png` — **on a synthetic
forward-modelled pattern**. There is no picked-peak picture for corundum, LaB6, FAP
or any other real dataset, even though two acceptance rows exist entirely about
phantom components on real patterns (8 of 63 components flagged `not_separable`;
tail components escaping for three different reasons) and their evidence is numeric
only.

### What is already plottable, and what is not

`LeBailValidation` (`schemas/indexing.py:603-651`) keeps the **2θ positions** of both
detector lists — `predicted_but_absent_two_theta`, `unmatched_observed_two_theta` —
explicitly so the report is actionable rather than a count. Those overlay the raw
pattern with no new plumbing.

But `validate_by_lebail` (`workflow.py:289-368`) builds a full `RefinementResult`
and **discards it two lines before returning**, consuming it only for scalars. A
real obs/calc/diff panel needs that object, so the WP's one structural change is an
opt-in return path. `plot_result`/`plot_for_vlm` (`viz/plots.py:16,97`) then work
unchanged.

Candidate tick marks need *regeneration*, not retrieval: `CellCandidate` carries no
hkl assignment and no predicted 2θ list. `indexing.fom.predicted_lines(...)` plus a
Q→2θ conversion is the route, and the acceptance suite already does exactly this at
`tests/test_acceptance_indexing.py:104-108` — the helper exists, it just is not in
`viz/`.

Note the Le Bail scaffold is **single-phase by construction**, and that is measured
rather than incidental (WP-1028: Rwp 742–9281 % for two phases against 7.5–24.8 %
for one). A gallery panel shows one candidate lattice per plot.

### Grading scales now exist

Two source papers publish impurity-robustness rates this suite can be read against:

- **Coelho (2003) Table 6** — SVD-Index success vs randomly inserted impurity
  lines: 3 lines → 84 % orthorhombic / 91 % monoclinic / 67 % triclinic; 6 → 73/72/26;
  9 → 61/56/6.
- **Le Bail (2004) §V** — McMaille, provided impurity intensity < 15 % of the total:
  under 35 % impurity lines by *number*, the correct cell is generally first; at
  35–50 % it may be found but usually not first.

Our contamination coverage is three synthetic tests plus the `n_unindexed` A/B
control (`tests/test_indexing_engines.py:579-602`). There is **no real-data
contamination sweep**. `tests/test_fitreport_layers.py` is the shape to copy: a
truth fixture, single-cause injections, then a calibration test over the ensemble.

### The scoreboard needs re-measuring, not reproducing

The eight-dataset scoreboard ("five right, one refused, two fail, all eight
abstain") is copied in three places. Two defects to fix rather than propagate:
its arithmetic does not close (5 + 1 + 2 = 8, but nine datasets are named across the
buckets), and **brucite and magnetite — the two failures — were measured before
WP-1030's prunes landed and are not test rows at all**; their numbers live only in
WP-1026's prose. Whichever WP re-measures should also decide whether they become
rows.

## Non-goals

- An interactive indexing panel in the Svelte GUI (the peak editor already exists;
  a candidate panel is separate).
- An indexing arm in the `compare` UI — its registry assumes a `Structure` and
  instant re-ticking from cache, against 60–150 s real searches.

## Tasks

- [ ] `validate_by_lebail` gains an opt-in return of its `RefinementResult` (it is
      already built); default behaviour unchanged.
- [ ] `viz/` gains indexing plots: picked peaks over the pattern, ranked-candidate
      tick rows via `fom.predicted_lines`, and the Le Bail obs/calc/diff panel with
      `predicted_but_absent` / `unmatched_observed` marked.
- [ ] Every acceptance row writes its PNGs to `tests/output/`, closing the
      `tests/CLAUDE.md` rule's exception. Prioritise the phantom-component and
      tail-component rows — those are pictures waiting to be drawn.
- [ ] Real-data contamination sweep: inject k impurity lines into a certified peak
      list, sweep k, measure rank of truth / n_indexed / M₂₀ / confidence /
      `best_or_none()`. Report against Coelho Table 6 and McMaille §V.
- [ ] Re-measure the eight-dataset scoreboard, fix its arithmetic, and decide
      whether brucite and magnetite become rows. Update all three copies
      (`CLAUDE.md`, `docs/milestones/v1.0.md`, `docs/wp/1026-*.md`).
- [ ] A one-page benchmark summary a reader can scan: dataset, provenance, what is
      asserted, what happened, and the picture.

## Acceptance

Every indexing acceptance row leaves a PNG; the contamination sweep produces a
curve, not an anecdote; the scoreboard is re-measured and internally consistent.

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_viz.py tests/test_validation_matrix.py -n auto
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
# then look at the PNGs — that is the point of the WP
```

## References

- Coelho (2003), *J. Appl. Cryst.* **36**, 86 — Table 6 impurity success rates.
  `/Users/yue/zotero-linker/derived/5RI7CB42/`
- Le Bail (2004), *Powder Diffr.* **19**, 249 — §V impurity and two-phase limits.
  `/Users/yue/zotero-linker/derived/7AEVVGH6/`
- Bergmann, Le Bail, Shirley & Zlokazov (2004), *Z. Kristallogr.* **219**, 783 — the
  only externally graded benchmark in the package.
  `/Users/yue/zotero-linker/derived/CSGZVXR2/`
- `docs/VALIDATION.md` § `tests/test_acceptance_indexing.py` — the benchmark
  inventory as it stands.

## Handover log

- **2026-08-04** — created from the source-literature review. The "zero PNGs"
  finding and the `validate_by_lebail` discard were established by reading the code
  this session; the scoreboard defects are read off WP-1026's own text. No
  measurement was run.
