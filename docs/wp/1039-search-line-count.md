# WP-1039 — How many lines a search enumerates on

Milestone: v1.0 · Status: ✅ 2026-08-05
Depends on: WP-1037 (1038 soft)

## Goal

`DEFAULT_SEARCH_LINES` stops being a bare 20 taken in 2θ order. Enumeration uses
enough lines to be robust; scoring stays conservative. This closes WP-1026's
inherited item, with a published answer rather than a guess.

## Context

### The defect, measured (WP-1026)

`DEFAULT_SEARCH_LINES = 20` (`engines.py:103`) takes the first twenty lines **in 2θ
order**. On `11BM_NAC.fxye`, which starts at 0.76° 2θ, that is the wrong twenty:
**six of the true cell's lines, against 268 of 285 over the whole list.** WP-1026
filed it as a peak-list *selection* question, and WP-1030 explicitly did not touch
it because it is not a search-cost question.

### The published answer

**Oishi-Tomiyasu (2014)** uses **48** q values by default in Conograph and argues
the point directly: *"the use of many q values is essential to make powder
auto-indexing robust against dominant zones and missing or false peaks"*, and
*"regardless of the proportions of missing and false peaks in the input, the success
rate of the enumeration stage is increased by raising the number of peaks used."*

The asymmetry is **proved, not asserted** (§3): a *false* peak costs only
computation, because the success rate is unchanged when Λ^obs gains a spurious
element (`Λ^obs ∪ {q^obs}` enumerates a superset); a *missing* peak costs success,
because it removes constraints the enumeration needs. And *"the sorting process
after the enumeration is more sensitive to missing and false elements, because
figures of merit are severely affected by such elements."*

**Enumerate liberally, sort conservatively.** Our current split is half-right: we
already score on every usable line (`engines.py:100-102`), which matches the second
half. It is the enumeration that is starved.

Cost is the constraint: Conograph's enumeration time is ∝ `N_zone²` ∝ **`N_peak⁴`**,
which is why it caps at 48 and why it needed the zone-sorting criterion that bought
back 18–250×. **We have no equivalent prune**, so a naive raise from 20 to 48 is a
~34× enumeration cost on the engine that is already the slow one. This is why the
WP lands after WP-1037: the ceiling and the per-system progress must exist first, or
the cost becomes invisible again.

### What "more lines" must not do

`DEFAULT_N_UNINDEXED = 2`'s docstring is the standing warning: *"raising it
manufactures cells — every extra tolerated line is one more coincidence a wrong
metric is allowed to have."* Those are different knobs (tolerated *unindexed* lines
vs lines *offered*), but the failure mode rhymes: more lines offered to
`trial_error`'s base-line pool means more base sets, and a bad base line poisons an
exact solve. `BASE_POOL_MIN = 8` and the leave-k-out recovery are the existing
guards; check they still hold at the new count.

### The selection question, which is not the same as the count

Even at 20, *which* twenty is wrong on NAC. Conograph's answer is a physically
derived q range (§2 bounds the range needed to prevent the dominant-zone problem
from `d_min`), not "the first N in 2θ order". Consider whether the selection should
be q-range-driven rather than rank-driven — that may fix NAC without raising the
count at all, which would be much cheaper.

### Licensing

Conograph is open-source (GPL-family) and the papers are open literature: implement
from the paper, port nothing.

## Non-goals

- Building Conograph's topograph/zone-sorting machinery — that is a different engine
  (fenced to v2; see WP-1040 for the engine question).
- The `reflection_ceiling_ok` obstruction that separately blocks NAC at
  d_min = 0.43 Å — a distinct WP-1026 inherited item. **Confirmed to be the sole
  remaining NAC obstruction**: at full range the run abstains under every rule and
  every N, `dichotomy.cubic.boxes = 0` in 0.06 s. Truncation now clears it (above),
  so the two are cleanly separated rather than merely asserted to be.
- Making `n_unindexed` a *fraction* of the driven set. Task 0 measured that it and
  `n_search_lines` are one knob, not two — which is an argument for touching
  neither, since the absolute budget is what `DEFAULT_N_UNINDEXED`'s
  "raising it manufactures cells" warning was calibrated against. Left stated
  rather than acted on.

## Tasks

- [x] **Task 0 — the cost/quality curve for N.** Swept over the known-cell corpus
      (rank of truth, M₂₀, wall clock, `search_complete`, caveats), plus a
      no-search selection diagnostic scoring each rule against the known lattice.
      See § Task 0, measured.
- [x] Decide count vs selection from that table. **Selection.** `DEFAULT_SEARCH_LINES`
      stays 20; `search_line_order` now ranks by intensity with a Q tiebreak.
- [x] State the rule and the enumerate-liberally / sort-conservatively split in the
      constant's docstring, with the asymmetry attributed **and its status corrected**
      (it is asserted in the source, not proved — see § The paper, re-read).
- [x] Re-check `BASE_POOL_MIN` at the new rule: the pool is now a *prefix of the
      selected search lines* rather than of the whole list, which is where the rule
      pays on SRM 660c.
- [ ] Acceptance: the NAC row moves from "the wrong twenty" to a stated outcome;
      re-measure every row the change touches; `validation_matrix.py` + regenerate
      `docs/VALIDATION.md`.

## Task 0, measured

Corpus swept at N ∈ {20, 32, 48} × {2θ order, intensity rank}, serially on one
machine (darwin/arm64 M4, `[dev,jax]`), through `index_pattern` under each
dataset's acceptance protocol. `rank` is the rank of the **lattice** (`equal_reduced`
on the reduced primitive form, WP-1030's rule), `—` means the truth is absent from
the candidate list entirely.

**The count bought nothing anywhere, and on two datasets it destroyed the answer.**

| dataset | 2θ:20 | 2θ:32 | 2θ:48 | int:20 | int:32 | int:48 |
|---|---|---|---|---|---|---|
| zincite | rank 0 | rank 0 | rank 0 | rank 0 | rank 0 | rank 0 |
| zircon | rank 0 | **—** | **—** | rank 0 | rank 0 | **— (0 cands)** |
| LaB6 (cubic-only probe) | rank 0, `low` | rank 0, `low` | — | **rank 0, `high`** | rank 0, `low` | — |

**Why raising N loses the truth, and it is not the cost the WP predicted.**
`indexes_the_search_lines` demands `hit >= len(search) − n_unindexed` — an
**absolute** budget over the driven set. Oishi-Tomiyasu's asymmetry ("a false line
costs only computation") holds because *there* the enumeration's success is a
membership test on Λ^obs, which adding elements cannot break. Ours is not a
membership test, so every foreign line admitted spends the `n_unindexed` budget and
past it the true cell is **refused**, not out-ranked. Zircon carries 16 foreign
lines among 68: at N = 20 it indexes 18/20 and survives, at N = 32 it needs 5
unindexed against a budget of 3 and vanishes. The two knobs WP-1026 called "different"
are one knob.

**The selection defect, reproduced and fixed.** NAC's first twenty in 2θ order
explain **6** of the true cell's lines against 268 of the whole 285 — verbatim
WP-1026's figure, re-measured. The fourteen others are low-angle components at
0.1–0.6 % of the strongest line's intensity carrying a fitted σ(2θ) two orders above
their real neighbours'. Intensity rank gives **20/20** at the same N. Rules scored
against the known lattice, no search:

| dataset | 2θ:20 | intensity:20 | **shipped** (pool 2N) | precision:20 | resolving:20 |
|---|---|---|---|---|---|
| NAC | **6/20** | 20/20 | 18/20 | 20/20 | 11/20 |
| corundum | 17/20 | 19/20 | 17/20 | 18/20 | 18/20 |
| zircon | 18/20 | 18/20 | 17/20 | 19/20 | 18/20 |
| LaB6 | 18/20 | 20/20 | 20/20 | 20/20 | 18/20 |
| zincite / FAP | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 |

Two rules were measured and **rejected**. `precision` (rank by smallest σ_Q/Q) scores
well and is wrong physics: it drags the selection to high angle — LaB6 49–148.7°,
corundum 52.5–149.2° — abandoning the low-Q lines the enumeration's small-index
assumption needs. `resolving` (the package's own `MAX_RELATIVE_SIGMA_Q` applied per
line instead of to the list median) **does not separate the junk**: 278 of NAC's 285
lines pass it, and it reaches only 11/20.

**Where the rule actually pays is the base-line pool.** On SRM 660c the certified
cell comes back either way, but under 2θ order only `dichotomy` finds it and the run
reports `engines_disagree`; under intensity rank **both engines find it**. The
acceptance suite *asserted* that disagreement ("what still stands is that only one
engine found it") and now asserts its absence. The mechanism is `trial_error`'s exact
solve, whose pool of base lines was the lowest-Q lines of the whole list — on a
pattern opening on background, exactly the lines the selection declines. The pool is
now a prefix of the selection.

**Agreement was necessary and not sufficient, and the two search scopes disagree
about that** — worth stating because it is an easy over-claim. On the *cubic-only*
probe above the run promotes to **`high`**, the first real-data promotion in the
package. Under the shipped four-system acceptance protocol it stays `low`, with
`fom_panel_disagrees` the sole surviving caveat. Quote the second; the first is a
narrower search.

## The rank is not free, and half its price was avoidable

The unbounded rank took `tests/test_acceptance_indexing.py` from **6:10 to 25:19**
— all 36 rows green either way, so this is cost, not correctness. Profiled rather
than reasoned about (WP-1030's rule), it is two fixtures: the corundum searches ran
**662 s and 596 s** of the 1519 s, against ~45–50 s recorded when they were written.

The mechanism is one line of `dichotomy._search_one`: the recursion's trial set is
`root_min <= q_hi_search`, sized by the **largest Q among the driven lines**.
Ranking by intensity over the whole list lets the driven set reach a lab pattern's
high-angle tail — corundum's twenty span 25.5–150.1° where the low-Q rule gives
5.2–76.8° — so every box in the recursion carries a much larger set.

Hence `SEARCH_POOL_MULTIPLE = 2`: the strongest N drawn from the lowest 2N in Q.
Two because it is the *smallest* pool that gives the rank any freedom at all (at
one, the selection is the lowest N and intensity cannot act), not a tuned optimum.
Measured on corundum's trigonal search: **72 s unbounded, 26 s bounded, 6 s** for
the old low-Q rule, all three ranking the certified cell first. Over the whole
acceptance file, **11:58 against 25:19**, 36/36 either way.

What it costs is stated rather than hidden: NAC 20/20 → 18/20, corundum 19 → 17,
zircon 18 → 17. The bound is safe where it matters because a list of 2N lines or
fewer is selected exactly as the unbounded rule would select it — SRM 660c has 30,
so the caveat the rank cleared stays cleared.

**A calibration worth keeping**: m = 3 and unbounded produce *identical* selections
on corundum (its 55 lines are inside a 60-line pool) and timed 72 s and 93 s. That
is 1.29× on byte-identical work, which is the noise floor any factor quoted here
has to beat — CLAUDE.md's "quote wall clock as a range" made concrete.

The residual **1.9× against the pre-WP baseline is real and unpaid**. The lever, if
it needs paying, is CLAUDE.md's own: narrow the *scope* of the corundum rows (they
already declare `REAL_DATA_SYSTEMS`), never the budget.

**NAC is still blocked, by something else, and this is now separated cleanly.** At
full range the run abstains under every rule and N in ~4 s with
`dichotomy.cubic.boxes = 0` — `reflection_ceiling_ok` at d_min = 0.43 Å, this WP's
declared non-goal. But truncating 2θ, which WP-1026 recorded as measured-and-useless
("do not spend that hour again"), **was measured with the broken selection**:

| truncation | 2θ order | intensity rank |
|---|---|---|
| ≤ 25° | no candidates, 0.5 s | truth rank 1, −23 ppm, 5.2 s |
| ≤ 32° | no candidates, 0.9 s | **truth rank 0, cubic I, a = 10.25108 Å, −22 ppm, 10.5 s** |

against WP-1026's recorded −5967/+8189/+7997 ppm, M₂₀ = 4, cubic **P**, at 300–620 s
each. So truncation *does* work once the search is driven by the right lines — three
orders of magnitude closer, the right centring, and 30–60× faster. The gate still
declines it (`indexed_fraction_low`: 91 of 129), which is correct. **WP-1026's
"do not spend that hour again" is hereby withdrawn as attributed to truncation.**

## The paper, re-read

WP-1039's own Context over-claimed its source, and the corrections matter enough to
record (the WP-0501 b₂ precedent — check the paper, do not quote the summary):

- **The asymmetry is asserted, not proved.** §3 is running prose with no
  proposition, lemma or proof; the claim is made for a *single* added element
  (`Λ^obs ∪ {q^obs}`), and the superset argument that would justify it is never
  written down. It is a correct reading of the intent, not a quotable result.
- **48 is an upper threshold, not the default.** Table 1 lists `N_peak` as **AUTO**,
  set by eq. (A.9) in supporting information *absent from our corpus*; 48 is the cap.
- **The 18–250× zone-sorting speedup was never timed.** Fig. 6 computes it as
  1/rate² from measured zone-*selection* rates of 0.06–0.24 under the assumed
  N²_zone model, excluding one case. By this package's own rule, a cost model
  reasoned from an algorithm's structure is not a profile.
- **The prescription is on the q *span*, not on a count**: q_max − q_min should be
  "a few times larger than D₃", with 1.5·d_min⁻² ≤ D₃ ≤ 2.4·d_min⁻². Conograph's own
  48-line default reaches < 0.8 D₃ on half its test data, which the paper states.
- **Conograph enumerates on ≤ 48 and *sorts* on 20–30.** Our split is not "half
  right" as the Context claimed — it is the more conservative one: we search on N
  and score on **every** usable line.
- **Conograph uses no intensity anywhere, and does not decline it either.** The
  explicit refusal is in Oishi-Tomiyasu (2013b) §1 and is argued on *computation
  time*, not robustness — so intensity-ranked selection contradicts no published
  finding.

## Acceptance

The NAC line-selection defect is resolved or explicitly re-scoped with evidence, no
other dataset regresses, and the wall-clock change is stated as a range.

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py tests/test_indexing_core.py -n auto
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

### Measured, 2026-08-05

darwin/arm64 M4, worktree `indexer`, venv `[dev,jax]` (**no torch** — jax turns
skips into passes, so none of these compares with a `[dev]` count).

- **NAC resolved as a selection defect and re-scoped as an obstruction.** The
  wrong-twenty problem is fixed (6/20 → 20/20); the pattern still abstains at full
  range, and the sole remaining cause is now *demonstrated* rather than assumed to
  be `reflection_ceiling_ok` — zero boxes explored under every rule and every N.
- **`tests/test_acceptance_indexing.py`: 36 rows, 35 pass unchanged.** The one row
  that moved is `test_a_certified_cubic_cell_is_recovered_with_no_extinction_caveat`,
  and it moved the right way: `engines_disagree` is gone, both engines now find the
  certified LaB6 cell, and the row now asserts that plus the single surviving caveat
  `fom_panel_disagrees`. No dataset regressed; no cell, ppm figure or M₂₀ bar moved.
- **Fast suite: 1708 passed / 67 skipped**, ~57 s. Exactly WP-1038's 1701 + this
  WP's 7 (five unit rows plus one end-to-end row parametrized over both engines),
  and **no new skips**.
- **The end-to-end row is checked against the rule it replaces**: under the 2θ-order
  selection it finds *nothing* on either engine, so it fails for the reason it
  claims rather than passing either way.
- **Wall clock, `tests/test_acceptance_indexing.py`: 6:10 before this WP, 25:19
  with the unbounded rank, 11:58 as shipped.** All three green; see § The rank is
  not free. The residual ~1.9× is real, and this file is likely now the longest
  xdist group — re-read `--durations` before trusting any statement about which
  group sets the full suite's wall clock.

One `validation_matrix.py` Claim moved and `docs/VALIDATION.md` was regenerated: the
SRM 660c indexing Claim's `measured` string was stale **twice** — it still named
`shift_allowance_assumed`, which WP-1038 cleared, as well as `engines_disagree`,
which this WP cleared. Worth noting as a process point: nothing failed because of
it. The per-Claim meta-tests check structure, not prose, so a `measured` string
rots silently and is only caught by a session that happens to read it.

One thing this did **not** do, stated so it is not read as done: the corundum and
FAP arms of the rule-vs-rule sweep were killed rather than finished.

## References

- Oishi-Tomiyasu (2014), *J. Appl. Cryst.* **47**, 593 — §2 (q range vs dominant
  zone), §3 (the missing/false asymmetry), Table 1 (defaults).
  Corpus item `NWFJ8YEB`.
- Werner, Eriksson & Westdahl (1985), *J. Appl. Cryst.* **18**, 367 — TREOR's own
  base-line selection, for the trial-and-error half.
  Corpus item `PN4KSN9S`.
- Visser (1969), *J. Appl. Cryst.* **2**, 89 — ITO; the dominant-zone problem in its
  original form. Corpus item `GABUYM7L`.

## Handover log

- **2026-08-05** — **the answer is selection, not count, and the WP's own premises
  needed three corrections.** Done: task 0's two sweeps (a no-search rule
  diagnostic scored against the known lattice, and real `index_pattern` runs at
  N ∈ {20,32,48} × {2θ, intensity}); the seam `engines.search_line_order`, which
  both engines now go through, ranking by intensity with a Q tiebreak;
  `trial_error`'s base pool moved to a prefix of *the selection*;
  `SEARCH_POOL_MULTIPLE`, which bounds the rank to a low-Q pool and halves what it
  costs; `INDEXING_THRESHOLDS_VERSION` → **1.2**; the `n_search_lines` agent-schema
  description it never had; a manual subsection; seven tests (there were **zero**
  referencing `n_search_lines` before this WP).

  Four things the next session should not have to rediscover. **A selection rule
  has a cost and it is not where you would look for it** — the driven lines' largest
  Q sizes dichotomy's per-box trial set, so reaching the high-angle tail doubled the
  acceptance file; measure `--durations` after touching selection, and note the
  1.29× noise floor measured here on byte-identical work. **`n_search_lines`
  and `n_unindexed` are one knob, not two** — `indexes_the_search_lines` is an
  absolute budget, so raising N *refutes* the truth rather than ranking it lower,
  and zircon loses its certified lattice going from 20 to 32. That is why nothing
  was raised, and it is also why Oishi-Tomiyasu's false-line asymmetry cannot be
  imported: it rests on a membership test we do not have. **The WP's Context
  over-quoted the paper** in three places (§ The paper, re-read) — read it before
  citing it again. And **WP-1026's "truncating NAC's 2θ was measured and does not
  work — do not spend that hour again" was measured with the broken selection**;
  redone, ≤32° now ranks the truth first at −22 ppm with the right centring in
  10.5 s.

  Not done / next: the corundum and FAP arms of the search sweep were **killed at
  ~15 min** rather than finished — the acceptance suite covers both under their
  real protocols and was the better use of the machine, so their rule-vs-rule
  comparison at matched settings is unmeasured. Gotcha for whoever resumes it:
  `budget_seconds` is per (engine × system), so a 6-combo corundum sweep at
  `REAL_DATA_BUDGET_SECONDS` has a two-hour worst case. Also unmeasured: the q-span
  check against the paper's D₃ criterion (script written, `qspan.py` in the
  session scratch, never run).

- **2026-08-04** — created from the source-literature review. The NAC figure
  (six of the true cell's lines in the first twenty, 268 of 285 over the whole list)
  is quoted from WP-1026's inherited list and was **verified to be recorded there**
  this session, but not re-measured. The `N_peak⁴` scaling is Conograph's, for
  Conograph's algorithm — task 0 exists because it may not describe ours.
