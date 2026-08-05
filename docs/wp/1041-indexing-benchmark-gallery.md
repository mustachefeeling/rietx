# WP-1041 — The indexing benchmark gallery

Milestone: v1.0 · Status: 🔄 2026-08-05 — dedup key, opt-in Le Bail result and the
three renderers landed; the aggregate measured and refuted; the benchmark tasks open
Depends on: WP-1026

## Goal

Every indexing acceptance row leaves a picture: the picked peaks over the real
pattern, the ranked candidates' tick marks, and the Le Bail validation fit. Today
the indexing suite draws nothing at all.

## Context

### Three engines now, and two fixes owed before any counts

`search_svd` is registered (WP-1040), so `index_pattern` runs **three** engines
by default and `high` requires all three to agree. Two rows already moved: SRM
660c LaB6 is found by all three (no more `engines_disagree`), and **11-BM NAC is
indexed as measured** — a = 10.2512 Å cubic I, +19 ppm, `predicted_but_absent`
0 of 837, by `svd` alone — where the acceptance file previously asserted it could
not be. Anything the gallery says about NAC abstaining is wrong. A second row
worth a picture: NAC truncated to ≤ 32° now ranks the truth first at −22 ppm with
the right centring, where WP-1026 recorded that experiment as useless. The wall
clock moved too: the acceptance file measured **20:03** during WP-1040 and
13-14 min at its close (38 rows) — the price of the confidence gate, not a
regression, and the range machine state; the gallery's own cost claims must quote
a range measured in-session.

**Three** defects were measured in WP-1040 and deliberately left for this WP
(changing a shipped engine's dedup inside a WP about a third engine is an
unmeasured behaviour change); **all must land before any count is recorded**, and
all three are checklist items below:

* **`trial_error._solution_key`**: (1) scale-invariant, so for a one-dimensional
  metric — cubic, and only cubic — every candidate hashes to one key and the
  engine reports at most one cubic candidate per system search; (2) its `seen`
  set spans the **centring loop** while the key carries no centring, so the first
  centring tried claims a metric and every later one is silently discarded (`P`
  is first in `centrings_for`). Measured: 11-BM NAC came back cubic **P** with 92
  predicted-and-absent reflections in place of the cubic **I** description of
  identical axes. Both fixes exist in `svd._solution_key`, which carries the
  measurement in its docstring.
* **`fom.borda_scores` leads with the wrong candidate when two centrings of one
  metric are both returned** — which the fixes above make reachable. It weighs all
  seven panel members alike, so on NAC the four forward members outvote the three
  reversed ones 4-3 even though `m_rev` separates the two **516×** (356.1 against
  0.69). Balancing the two directions is *not* the fix: it produces a tie. This
  needs a magnitude-aware aggregate, measured across every acceptance row.
  `test_short_wavelength_data_is_indexed_…` pins the current order with an
  assertion that inverts when it lands.

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

- [x] `trial_error._solution_key` carries the scale and the centring — landed as
      **one** shared `engines.solution_key`, since the two engines had the same
      function with a different bug fixed in each. Before any count.
- [x] **One fix, not two** — measured across a six-dataset corpus, and **neither half
      survives its measurement**. It really was one defect, but the shared defect is
      the *premise*: both halves read a comparative instrument as an absolute verdict.
      The log-sum scores 5/6, exactly Borda's, failing on a different dataset;
      `unmatched_observed` has no absolute scale (10-188 for **correct** cells) and
      within a pattern is Rwp again. Numbers below. `log_sum_scores` ships tested and
      **unwired**; `rank_candidates` and `caveats_for` are unchanged, so no acceptance
      row turned over. A successor needs a *new* panel member or a
      within-pattern-normalised score, not another aggregate over these seven.
- [x] The three rows the dedup fix turned over, re-measured and re-pinned: 11-BM NAC
      (`found_by` gains `trial_error`), `INDEX_DOMINANT_ZONE` (fixture split in two,
      genuine case now `slow`), and the LaB6 flagship (`best_or_none()` withdrawn,
      with the evidence that the old answer came from the bug).
- [x] `validate_by_lebail` gains an opt-in return of its `RefinementResult` (it is
      already built); default behaviour unchanged.
- [x] `viz/` gains indexing plots: picked peaks over the pattern, ranked-candidate
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

- **2026-08-05 (later, after merging `main`)** — **five of nine**. `main`'s WP-1035
  merged in (no code conflict; both doc conflicts were the always-loaded files), then
  the aggregate task was measured and **its recorded design refuted**.

  **The measurement.** A harness dumps every candidate's panel for six known-cell
  datasets, reusing the acceptance module's own fixtures so the protocol cannot
  drift; aggregates are then compared offline on identical panels. Truth is
  `same_lattice` **and centring** — the first version forgot centring and read both
  NAC candidates as the truth, which is `solution_key`'s own lesson one rank up.

  | aggregate | truth ranked first |
  |---|---|
  | Borda (shipped) | 5/6 — misses **NAC** |
  | log-sum − `m_sym` (the recorded design) | 5/6 — misses **corundum** |
  | standardised log-sum | 5/6 — misses **NAC** again |
  | gate-status first, then either | 5/6 — misses **zincite** |
  | log-sum, `m_rev` weighted 0.10–0.20 | 6/6 — on a weight two datasets fit |

  **Why the log-sum fails.** Summing raw logs weights each member by its dynamic
  range, and the panel's are not comparable: on corundum `m_rev` spans 2.5–356 where
  the coverage fractions span 0.78–0.99, so it promotes a half-volume trigonal R
  subcell indexing 43/55 over the truth's 51/55. Standardising cures that and
  **degenerates exactly where it is needed** — with NAC's two candidates every
  z-score is ±1 by construction. The corpus brackets `m_rev`'s weight only to
  `0.034 < w < 0.294`; that is two datasets setting one constant.

  **Why the gate half fails, and why it is the same failure.** `unmatched_observed`
  cannot be a caveat because a caveat is an absolute verdict and the count has no
  absolute scale: 10–188 across 21 validated candidates that are *correct* (NAC's own
  truth leaves 188 against its CaF₂ impurity). Within one pattern it does
  discriminate — and is nearly what Rwp already reports, Spearman **+0.80 to +1.00**
  on the five datasets with enough candidates to rank, against **+0.44** pooled.
  Gate-status-first ordering was measured too and demotes zincite's truth to rank 2,
  because `predicted_but_absent` fires on the correct cell's P6₃mc extinctions (4 of
  36) and clears the wrong supercell (0 of 68) — the trap CLAUDE.md already carries.

  **Also settled**: `m_sym` = `M̃ₙ × M^Rev` is now *proved*, re-derived in the test
  from `n_cal`/`nearest_discrepancy`/`trimmed_mean` and matching to 1e-9 — and `M̃ₙ`
  is **not** the panel's `m20` (1.15 against 1.43 on NAC), which the previous
  session's paraphrase had wrong in ROADMAP.

  **Counts**, `[dev,jax]` on the merged tree: fast **1760 / 67**, full **1858 / 72**.
  The sum closes — 1041's pre-merge 1841 + 1035's 12 python rows + 1041's 5 = 1858,
  no new skip, both selections moving by exactly the 5. **No timing is quotable**:
  another worktree's suite held the machine at load 40–120, so the same tree read
  fast 2:46 and 4:05 an hour apart and full 46:59 against 25–36 min pre-merge.

  **Gotcha for the next session**: `CLAUDE.md`'s size cap was raised 700 → 720 in
  `tests/test_docs_consistency.py`, deliberately and with the reason in a comment.
  The file is now 100 lines past what the last consolidation achieved — **the next WP
  that needs room there should do the consolidation pass, not another raise.**

  Open: tasks 5–9 (acceptance PNGs, contamination sweep, scoreboard re-measure,
  one-page summary). The harness lives in the job scratchpad, not the repo — if the
  scoreboard task wants it, it should land in `tests/` as a fixture.

- **2026-08-05** — **four of nine** tasks landed (the checklist gained one: the three
  acceptance rows the dedup fix turned over, which was not foreseen work), and **the
  dedup fix was much bigger than the WP inherited it as**. Branch
  `wp1041-indexing-benchmark-gallery`, [draft PR #34](https://github.com/yue-here/pxrd-refine/pull/34).

  **Done.**
  1. *One shared `engines.solution_key`* replacing `trial_error._solution_key` and
     `svd._solution_key` — the same function with a different bug fixed in each,
     so it moved to the module CLAUDE.md names as the engines' shared home.
  2. *`validate_by_lebail(..., with_result=True)`* returns the `RefinementResult`
     it already builds. Default return shape unchanged and pinned.
  3. *`viz/indexing.py`* — `plot_peak_list`, `plot_candidates`, `plot_validation`,
     exported from `pxrdref.viz`, with `tests/test_indexing_plots.py` (4 rows)
     asserting what each renderer **drew** rather than recomputing it.

  **The defect was three defects, and the third is the dangerous one.** The WP
  inherited "scale-invariant, so cubic and only cubic". Measured: a scale-invariant
  key merges any two metrics related by a **uniform rescaling**, i.e. one candidate
  per *shape* in every system — one per c/a in tetragonal, one per axis ratio in
  orthorhombic — so **a cell always collides with its own uniform supercell**, which
  is the exact false positive the FoM panel exists to separate. And `seen.add` runs
  **before** `_score`, so a metric that *fails* scoring still claims its whole
  family. On a cubic-I list (a = 6.2 Å, 17 lines), by substitution:

  | key | candidates | first | true I present |
  |---|---|---|---|
  | scale-invariant, no centring | 1 | P a = 4.3841 | **no** |
  | scale-invariant, with centring | 2 | I a = 6.2000 | yes |
  | scale-dependent, no centring | 4 | **P a = 6.2000** | **no** |
  | both (shipped) | 8 | I a = 6.2000 | yes |

  **Two rows turned over, and one of them had been green and wrong for two years.**

  * **11-BM NAC is now found by two engines**, `svd` *and* `trial_error`, in both
    the P and I descriptions at +19 ppm. `trial_error` had reached that cell all
    along and its own key discarded it. The acceptance row, its title, and the
    `validation_matrix` Claim are updated; the gate is untouched (`dichotomy` still
    finds nothing, so `engines_disagree` stands, still `low`, `best_or_none()` still
    `None`). **Three recorded no-goes have now died on this one dataset.**
  * **`INDEX_DOMINANT_ZONE`'s fixture was never a dominant zone.** Instrumenting the
    base search on the old c = 26 Å / crop 28° construction: it reaches five metrics
    of the truth's shape at indices ≤ 2 and the truth among them, but a junk cell at
    a = 4.1812, c = 27.1561 — the same shape within the dedup grid — was solved
    first, claimed the key, **failed scoring, and blocked the truth**. So the
    diagnostic was explaining a silence it had itself caused. That construction now
    has its own fast row asserting it *is* indexed (78 of 78 lines), and the
    diagnostic moved to a genuine construction (c = 40 Å, crop 33°, 2θ_max 46°,
    `max_d_axis` 52) marked **slow**: probe 13 s of its 30 s cap, and the domain
    cannot narrow further — at `max_d_axis` 45 the probe finds nothing at any rung.
    2.3× is thinner than `tests/CLAUDE.md` likes and is stated in the row.

  **The 38-row acceptance run then found the third row, and it is the sharpest.**
  `test_what_the_unflagged_tail_components_cost_the_certified_cell` — the package's
  flagship real-data result — asserted `best_or_none() is not None`. It now returns
  `None`, and **the old behaviour was the bug's doing.** The calibrated LaB6 search
  returns three cells, and every engine finds all three: the certified cell at
  −2 ppm and **both centrings of its a·√2 supercell** (5.878564 = 4.156772·√2). The
  supercells used to carry `engines_disagree` purely because `trial_error` could
  return one cubic candidate per search and never voted for them. So a unique
  `high` on the flagship row was protected by a broken filter, not by the gate —
  the inversion of "a filter fails with a wrong answer", a broken filter producing
  the *right* answer for no reason. The `high` on the certified cell is unaffected;
  only the uniqueness claim is withdrawn.

  Everything that refutes the supercell is measured and **none of it is gated**:

  | | truth | I supercell | P supercell |
  |---|---|---|---|
  | Le Bail Rwp | 0.098 | 0.250 | 0.664 |
  | `predicted_seen_fraction` | 1.00 | 0.88 | 0.49 |
  | `m_rev` | 890 | 6.2 | 1.8 |
  | `unmatched_observed` | 17 | 91 | 136 |
  | `predicted_but_absent` (**gated**) | 0/30 | 0/35 | 0/67 |

  **This is the same root as the borda defect**, so they are one task now:
  `caveats_for` reads `predicted_but_absent` and never its mirror
  `unmatched_observed`, which `indexing/workflow.py`'s own module docstring says is
  the detector for a wrong metric — and the aggregate is magnitude-blind. A
  threshold cannot be invented from this row alone: NAC's *correct* I cell leaves
  **188** observed peaks unmatched (a two-phase pattern), so an absolute bar refutes
  a right answer. It needs the cross-row measurement.

  **In flight / next, in order.**
  1. **The magnitude-aware aggregate and the second detector in the gate** — one
     fix, because they are one defect. The aggregate half is fully measured on NAC and written into
     the acceptance row as a table. P beats I 4-3 on Borda while winning two of its
     four members by **0.4 % and 0.01 %** and losing `m_rev` **516×** and `m_sym`
     **318×**; Le Bail agrees with I (0 of 837 absent against 92 of 1668). *A
     near-tie counting as a full win is the defect.* The design that follows from
     it: rank on the **log-sum** of the panel (its product), which is magnitude-aware
     and still invariant to each member's units, since a unit change shifts every
     candidate equally — and it **must drop `m_sym`**, because `log(m_sym) =
     log(M̃₂₀) + log(M^Rev)` exactly, so keeping both counts the reversed direction
     twice. Not landed: it needs measuring across every acceptance row, not tuned on
     this one.
  2. Tasks 5-8 untouched: acceptance PNGs, the contamination sweep, the scoreboard
     re-measure, the one-page summary.

  **These counts are pre-merge, and `main` has moved.** The branch is based on
  `1185c7f` and `origin/main` gained **10 commits** of concurrent GUI work while this
  session ran; nothing here touches `gui/` or `src/pxrdref/gui/` (zero files), so
  there is no conflict to expect, but `tests/CLAUDE.md`'s rule applies — the two
  parents' additions cannot be summed, so **re-measure after the merge** rather than
  adding this WP's +5/+6 to whatever the GUI branch reports.

  **Measured green** (`worktree-indexer`, venv `[dev,jax]`, no torch, darwin/arm64
  M4): fast **1743 passed / 67 skipped** in 3:41, full **1841 / 72** in 24:36,
  `test_acceptance_indexing.py` **38 rows** in 14:12, ruff clean. The two selections
  move by **+5** and **+6** off 1040's 1738/1835 — **seven** rows added, one deleted
  (`svd`'s scale-invariance pin, subsumed by the shared key's), and
  `INDEX_DOMINANT_ZONE` *moved* from fast to slow, which is the whole of the
  difference between the two deltas. No new skip (67 and 72 both unchanged). The NAC
  row is a **rename**, not an addition, and counting it as one is how the first
  version of this paragraph said "six".

  **Gotchas.** CLAUDE.md is at **exactly** its 700-line cap — adding a line means
  moving narrative out, not raising the cap (the cap is a deliberate commit).
  `docs/VALIDATION.md` is generated: edit `tests/validation_matrix.py` and run
  `.venv/bin/python -m tests.validation_matrix`. And the two remaining renderer
  gaps: `plot_candidates` is exercised only on a synthetic list so far, and no
  acceptance row writes a PNG yet — task 5 is untouched.

- **2026-08-04** — created from the source-literature review. The "zero PNGs"
  finding and the `validate_by_lebail` discard were established by reading the code
  this session; the scoreboard defects are read off WP-1026's own text. No
  measurement was run.
