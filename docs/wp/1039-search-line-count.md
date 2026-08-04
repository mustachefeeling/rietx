# WP-1039 — How many lines a search enumerates on

Milestone: v1.0 · Status: ⬜
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
  d_min = 0.43 Å — a distinct WP-1026 inherited item.

## Tasks

- [ ] **Task 0 — the cost/quality curve for N.** Sweep `n_search_lines` over the
      known-cell corpus and record rank of truth, M₂₀, wall clock and
      `search_complete` at each N. `N_peak⁴` predicts the cost; measure whether it
      holds for *our* engines, which are not Conograph's. No `src/` change.
- [ ] Decide count vs selection from that table: q-range-driven selection may fix
      NAC at N = 20. Record the decision and its evidence.
- [ ] Raise/derive `DEFAULT_SEARCH_LINES`, with the enumerate-liberally /
      sort-conservatively split stated in the constant's docstring and the
      asymmetry attributed.
- [ ] Re-check `BASE_POOL_MIN` and the leave-k-out recovery at the new count.
- [ ] Acceptance: the NAC row moves from "the wrong twenty" to a stated outcome;
      re-measure every row the change touches; `validation_matrix.py` + regenerate
      `docs/VALIDATION.md`.

## Acceptance

The NAC line-selection defect is resolved or explicitly re-scoped with evidence, no
other dataset regresses, and the wall-clock change is stated as a range.

```sh
.venv/bin/python -m pytest tests/test_indexing_engines.py tests/test_indexing_core.py -n auto
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Oishi-Tomiyasu (2014), *J. Appl. Cryst.* **47**, 593 — §2 (q range vs dominant
  zone), §3 (the missing/false asymmetry), Table 1 (defaults).
  `/Users/yue/zotero-linker/derived/NWFJ8YEB/`
- Werner, Eriksson & Westdahl (1985), *J. Appl. Cryst.* **18**, 367 — TREOR's own
  base-line selection, for the trial-and-error half.
  `/Users/yue/zotero-linker/derived/PN4KSN9S/`
- Visser (1969), *J. Appl. Cryst.* **2**, 89 — ITO; the dominant-zone problem in its
  original form. `/Users/yue/zotero-linker/derived/GABUYM7L/`

## Handover log

- **2026-08-04** — created from the source-literature review. The NAC figure
  (six of the true cell's lines in the first twenty, 268 of 285 over the whole list)
  is quoted from WP-1026's inherited list and was **verified to be recorded there**
  this session, but not re-measured. The `N_peak⁴` scaling is Conograph's, for
  Conograph's algorithm — task 0 exists because it may not describe ours.
