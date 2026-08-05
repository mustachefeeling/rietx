# WP-1041 — The indexing benchmark gallery

Milestone: v1.0 · Status: ⬜
Depends on: WP-1026

## Goal

Every indexing acceptance row leaves a picture: the picked peaks over the real
pattern, the ranked candidates' tick marks, and the Le Bail validation fit. Today
the indexing suite draws nothing at all.

## Context

### Inherited

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
