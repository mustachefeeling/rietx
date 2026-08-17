# WP-1077 — The extinction screen refutes a certified class

Milestone: 1.0.x · Status: ⬜
Depends on: — (found by WP-1067's `using/indexing.md` session, 2026-08-17)

## Goal

Establish what the intensity at corundum's forbidden positions actually is, and
either fix the absence test or record why the refutation is correct. Either way
the package gains the acceptance row that would have caught this: a rhombohedral
glide case, on real laboratory data, with an impurity in it.

## Context

**The measurement.** `determine_extinction_symbol` rejects the class the
specimen's certificate names. On the bundled IUCr round-robin corundum pattern
(`tests/data/qarr/corundum.prn`, NIST SRM 676a, α-Al₂O₃, **R -3 c**, Cu Kα,
7251 points over 5–150°), given the certified cell (a = 4.759355 Å,
c = 12.99231 Å, trigonal *R*) and `tests/test_acceptance_qpa_roundrobin.py`'s
`qarr_instrument()`:

| Protocol | `profile_rwp` | `R - c -` | verdict |
|---|---|---|---|
| whole range, declared widths | 0.287 | 5 of 15 testable forbidden positions carry intensity | refuted |
| 20–90°, widths from `workflow.seed_widths` | 0.149 | 2 of 9, first (2, 0, 5) at 56.919° | refuted, ΔBIC **−251** |

`ExtinctionScreen.best_or_none()` returns `R - - -` in both runs, whose members
are R 3, R -3, R 3 2, R 3 m and R -3 m. **The certified group is not in that
list.** This is not the package abstaining, which is what its design is for; it
is a wrong answer, and it is reachable from the workflow
`docs/AGENT_PROTOCOL.md` §7d prescribes.

Improving the shared profile fit halves the count and does not remove it, so
"the profile was badly modelled" is at most part of the story.

**Reproduction** (the exact script the numbers came from is not committed —
rebuild it; it is ~40 lines):

```python
data = rx.read_pattern(QARR / "corundum.prn")            # tests/data/qarr
ins = qarr_instrument()                                  # dispersion declined
peaks = rx.pick_peaks(data, ins)
seeded, _ = rietx.indexing.workflow.seed_widths(ins, peaks)
cand = CellCandidate(cell=(4.759355, 4.759355, 12.99231, 90.0, 90.0, 120.0),
                     cell_esd=(1e-4,) * 6, system="trigonal", centring="R",
                     lattice_group=fom.lattice_group("trigonal", "R"), volume=254.9)
screen = rx.determine_extinction_symbol(data, cand, seeded,
                                        two_theta_limits=(20.0, 90.0))
```

**What is already known about this specimen.** The same pattern's default
`index_pattern` run reports **49 `unmatched_observed`** lines against its own
top candidate, and `PEAK_NOT_SEPARABLE` / `PEAK_AXIAL_TAIL` /
`PEAK_KALPHA2_RESIDUAL` all fire on its peak list (8 / 11 / 1 components). So an
impurity line or an artefact landing on a forbidden position is a live
hypothesis, and `docs/AGENT_PROTOCOL.md` §7e already tells an operator to make
exactly that cross-check by hand. What it does not do is stop the screen from
answering.

**The mechanism, and which half is under test.** `src/rietx/indexing/`
`extinction.py` ranks classes by ΔBIC and Hamilton against the absence-free
reference, then applies the direct absence test at each class's own *testable*
forbidden positions, read against that class's own calculated pattern
(`workflow.absent_reflections`, with `ABSENT_SIGMA` and `ABSENT_WINDOW_FWHM`).
**One-sided refutation is deliberate and is not what this WP re-opens**
(`schemas/indexing.py`, `ExtinctionCandidate.refuted`): a class asserts
absences, so intensity at a position it forbids contradicts it, and ΔBIC cannot
buy that back. The question here is whether the *evidence* is sound — whether
those positions are testable in the sense the field claims (inside the range,
and separable from every line the class still allows) and whether the intensity
read there belongs to the reflection at all.

**No test covers this shape.** `tests/test_extinction_symbol.py` has three
real-answer rows: a synthetic monoclinic P 2₁/c, FAP (hexagonal, `P 63 - -`,
passes) and 11-BM NAC (cubic *I*, absence-free answer, passes). None is
rhombohedral, none is a glide on real laboratory data, and none carries an
impurity. Root CLAUDE.md's rule applies directly here: **choose an acceptance
dataset by space group**, the way SRM 660c (P m -3 m) was chosen to prove that
`predicted_but_absent` counts against the lattice group.

**Two rules from `tests/CLAUDE.md` bind the new row.** An eval's expected answer
is a measurement, so decide what the data supports *before* reading the grid;
and a wall-clock budget in a test is a runaway guard, never a timer (the screen
costs ~2–3 s here plus the profile fit).

## Non-goals

- **Not a re-opening of one-sided refutation.** If the evidence turns out to be
  sound, the finding is that this specimen violates its own class at two
  positions, and the answer is to say so in the chapter — not to let ΔBIC
  outvote a violated absence.
- **No new diagnostic without evidence.** If the absence test is admitting a
  position it should not, the fix is in the test, not a warning bolted beside it.
- **Not the indexing surface's stability tier** — that is
  [1078](1078-indexing-provisional.md).

## Tasks

- [ ] Reproduce from a committed script or test and record the numbers, then
      **look at the pattern** at 56.919° and at the second flagged position:
      is there a line there, and is it the specimen's, an impurity's, a Kα2
      residual or an axial tail? Cross-check against the indexing run's
      `LeBailValidation.unmatched_observed_two_theta` and against
      `PeakList.peaks` flags. Plot it (tests/output/).
- [ ] Check the testability half: is each flagged position genuinely separable
      from every line `R - c -` still allows, at the window
      `workflow.absent_reflections` uses? A forbidden position hiding under an
      allowed neighbour is not an observation, and `n_testable` is the field
      that claims it is not one.
- [ ] Decide, and say which of the three it is: the evidence is wrong (fix the
      test), the evidence is right and the intensity is foreign (then the screen
      needs the impurity cross-check the protocol currently leaves to a human),
      or the evidence is right and the specimen violates its class (then the
      chapter's paragraph stands and gains the answer).
- [ ] Acceptance row in `tests/test_extinction_symbol.py`: corundum, real data,
      expected answer measured before the grid is read, budget as a runaway
      guard. Marked `slow` with an `xdist_group` if it costs like the others.
- [ ] If the behaviour changes: `docs/manual/using/indexing.md`'s measured
      paragraph (§ The extinction symbol, the two "Read `profile_rwp`" and
      "refutation outranks ΔBIC" blocks) and `docs/AGENT_PROTOCOL.md` §7e's
      `EXTINCTION_FORBIDDEN_INTENSITY` row are the two places that quote it.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extinction_symbol.py -q
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup   # engine-adjacent
.venv/bin/python -m pytest tests/test_manual_api.py tests/test_docs_consistency.py
.venv/bin/python -m ruff check src tests examples
```

The extinction screen sits on top of the Le Bail path, so a change in
`extinction.py` or `workflow.absent_reflections` can move a measured number:
run the full suite once on the final tree.

## References

- WP-1067's 2026-08-17 handover entry — where this was measured, and the rest
  of that session's corundum numbers.
- `src/rietx/schemas/indexing.py`, `ExtinctionCandidate` and `ExtinctionScreen`
  docstrings — the one-sided rule, and what `best_or_none` requires.
- `src/rietx/indexing/CLAUDE.md` — "read `predicted_but_absent` as *this cell
  predicts lines the pattern lacks*", and why acceptance datasets are chosen by
  space group.
- `docs/AGENT_PROTOCOL.md` §7e — the operator-facing reading of
  `EXTINCTION_FORBIDDEN_INTENSITY`, including the impurity cross-check.

## Handover log

- **2026-08-18** — created, from WP-1067's measurement. Nothing run here yet;
  every number above came from that session's ad-hoc script, so the first task
  is to reproduce them from something committed.
