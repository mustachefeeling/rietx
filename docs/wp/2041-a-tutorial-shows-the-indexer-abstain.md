# WP-2041 — a tutorial shows the indexer abstain

Milestone: unscheduled · Status: 🔄 2026-10-24 — claimed by @yue-here
Track: The repo's own process
Depends on: —
Priority: P4 2026-10-24 — teaching content: no number and no decision moves, and the manual's diagnostics page still explains the abstention

## Goal

One tutorial runs a search that ends with `best_or_none()` returning `None`, and its prose reads
the verdict line and the `INDEX_ABSTAINED` diagnostic off that output.

## Context

- Notebook 03 (`examples/tutorials/03_peaks_indexing_lebail.py`) used to be the example. Since
  WP-2002 removed the U, V and Y width floors (`879fb1bcc`), its candidate validates with 0 of
  105 reflections absent and grades `high`, so the verdict line names the cell. WP-2039 checked
  this on an `origin/main` snapshot (`e921947a0`), rewrote the section to what the output shows,
  and gave the search `budget_seconds=120`, because at the 30 s default a busy machine left svd
  unfinished and flipped the verdict to NO CELL.
- So "why the indexer abstains" now has no worked example in the tutorials. The section keeps
  one sentence on it and a link to `reference/diagnostics-indexing.html#index-abstained`.
- An abstention that depends on wall clock is the wrong example: it flips with machine load.
  The example needs a search that abstains on its evidence. Two candidates, neither measured: a
  peak list with too few lines for the gate, or one carrying stray lines past the allowance
  (WP-1969's defect, so it may stop abstaining when that WP lands).
- Edit `examples/tutorials/NN_*.py` and rebuild with `build.py`. Never edit the `.ipynb`.
  `build.py` lists every cell whose text output a rebuild changed; reread each one.

## Non-goals

- Changing when the indexer abstains: WP-1969 and `src/rietx/indexing/`.

## Tasks

- [ ] Find a shipped pattern or a peak-list cut of one that abstains on evidence, stable across
      three runs on a loaded machine. Record the verdict line and the grade in the handover.
- [ ] Add it to notebook 03 after the confident search, with prose that reads the output.
- [ ] Skill: none. The skill's indexing reference already covers `best_or_none()`.

## Acceptance

```sh
.venv/bin/python examples/tutorials/build.py --check
.venv/bin/python -m pytest tests/test_tutorials.py -q
```

## References

None.

## Handover log

- **2026-10-24** — Created from WP-2039's inherited note to WP-2040, because no open WP owns
  tutorial content: WP-1969 changes when the indexer abstains, and WP-2040 adds links only.
  Next: the first task.
