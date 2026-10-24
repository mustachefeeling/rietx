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
- **Measured 2026-10-24 on `41d76f6c1`** (arm64 venv, `[dev]`). The notebook's own pattern,
  cropped with `data.crop(10, hi)`, re-picked and searched with the notebook's `spec`:

  | 2θ max | lines | verdict | caveats on the true cell (all three engines found it) |
  |---|---|---|---|
  | 30 | 4 | NO CELL, nothing searched | `INDEX_DATA_INSUFFICIENT` |
  | 35 | 7 | NO CELL | panel_disagrees, panel_reduced, absent 5/14, shift assumed |
  | 40 | 15 | NO CELL | panel_reduced, absent 6/22, shift assumed; a 2 300 ppm off |
  | 45 | 15 | NO CELL | panel_reduced, absent 5/27, shift assumed; cell to 0.0006 Å |
  | 50 | 20 | NO CELL | absent 5/37, shift assumed |
  | 60 | 30 | NO CELL | absent 4/56 |
  | 80 (notebook) | 54 | CELL, `high` | none; absent 0/105, shift measured from 8 pairs |

  The 45° cut gave the same output on three concurrent runs beside eight CPU-bound processes
  on ten cores (23 s each against 11.5 s alone).
- **Every absent reflection in every cut is a P m c n extinction** — (010) 11.09°, (001)
  15.43°, (101) 23.68°, (120) 28.71°, (201) 39.54° — counted against the cell because the
  validation tests the lattice in Pmmm (the indexing CLAUDE.md's `predicted_but_absent` rule).
  **The full range's 0 of 105 is the validation fit's background, not the data**: it sits at
  125 counts over 10-11° and 46 over 75-78° against a true flat 200, and 10-19° holds no allowed
  reflection at all. So the notebook's `high` passes because the refuting caveat went blind —
  issue #916's mechanism (a candidate's fit buys its absences by sinking the background) on the
  *correct* cell. WP-1956 owns the repair; this WP changes no indexer code.

## Non-goals

- Changing when the indexer abstains: WP-1969 and `src/rietx/indexing/`.

## Tasks

- [x] Find a shipped pattern or a peak-list cut of one that abstains on evidence, stable across
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
