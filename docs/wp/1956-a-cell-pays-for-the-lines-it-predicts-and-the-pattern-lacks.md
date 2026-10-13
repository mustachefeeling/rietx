# WP-1956 — a cell pays for the lines it predicts and the pattern lacks

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 1449 soft (the index 2–4 refutation it widens); 1511 soft (one Le Bail protocol per cell)
Priority: P2 2026-10-13 — the absent-line detector fires on the truth and is blind on every wrong cell, and a distorted cell ranks first; no grade is confident today only because the run-level `fom_panel_disagrees` fires, which the reporter measured quiet on arms where a wrong cell reached `medium`

## Goal

An indexing candidate whose predicted lines the pattern lacks is charged for
them at the grade, beyond the index 2–4 sublattices WP-1449 asks about, and the
absence test reads inputs a candidate cannot buy: a background shared by every
candidate or owned by the pattern, and the peak list's measured width. A correct
cell with a glide (Si 3/18, corundum, magnetite) stays unrefuted, and an
unresolved split stays unpunished.

## Context

**What is measured** (issue #916, synthetic Si, reproduced on c3d0367 to the
digit). `indexing.workflow.absent_reflections` (`workflow.py:180`) integrates
each candidate's own co-refined Le Bail background, and a wrong cell's fit buys
its absences away by sinking that background:

| cell | Rwp | predicted_but_absent | background vs the true 7700 counts |
|---|---|---|---|
| truth, cF a₀ | 0.013 | 5/18 | −7 |
| cI √2·a₀ | 0.828 | 0/59 | −3782 |
| cF 1.006·a₀ | 0.904 | 0/18 | −2823 |
| cP a₀ (triage's arm) | | 0/50 | −3233 |
| cP 2a₀ (triage's arm) | | 0/290 | −8422 |

So the detector fires only on the truth. Under `preset="quick"` (121 s, 17
lines) a distorted hR cell (a = 3.8450, c = 9.3904) ranks first with no
refuting caveat, and the true cF 5.4306 ranks second, the only candidate
carrying `predicted_but_absent`. cI 7.6800 is refuted only through an index-4
check against a tI parent (`consensus.supercell_checks`, `consensus.py:174`,
volume index 2 to `ambiguity.MAX_AMBIGUITY_INDEX` = 4).

**Why nothing confident is returned today, and why that is not a fix.** Every
candidate is graded `low` through `fom.fom_panel_disagrees` (`fom.py:775`),
computed once per run (`consensus.py:460`) and attached to every candidate
(`:610-611`), so `best_or_none()` is `None`. The reporter's follow-up measured
that flag quiet on arms where wrong cells reached `medium` or `high` (the cI cell
was graded `medium` on `f22e9a7c` under a steeper background). Their conclusion,
taken here: the flag is not to be relaxed, scoped per candidate or removed before
this repair, and any redesign of it is measured with this WP, on the same arms.

**The design was recorded and left unowned.** WP-1043 (✅) measured the same
pathology on magnetite (the rival's background driven negative, mean −11.4
counts, so net > 3σ at every channel and the detector cannot fire). It recorded
the fix as candidate-independent inputs (a floored or pattern-owned background,
the peak list's measured width), and the bound a repaired detector meets there:
14 of 163, not most of 163. It also recorded that the repair re-measures every
`predicted_but_absent` count in the tree and "should be scheduled deliberately,
not folded into a passing WP" (1043's tasks and its last handover).

**The question the issue asks** (from #916, open): should a cell pay at the
grade, and with which inputs: one background shared by all candidates, the
measured width, line-set containment rather than lattice containment for
`supercell_chance`? The reporter is working the options through and will post a
measured proposal on the issue. Read it before designing.

**Rules that bind it** (`src/rietx/indexing/CLAUDE.md`): never a confident
singleton; a new indexing rule lands in that file; run
`tests/test_acceptance_indexing.py` before closing anything that touches an
engine or the ranking. Indexing is provisional by declaration
(`PROVISIONAL_MODULES`).

## Non-goals

- The blind search and enumeration ceilings (WP-1924), dedup across a reduction
  boundary (WP-1932), peak picking (WP-1909), the extinction screen (WP-1910).
- WP-1511's per-cell Le Bail evidence, which fences the blind search itself.
- A refinement's own Le Bail background left too low at its seed (WP-1542): the
  opposite sign, in another call.

## Tasks

- [ ] Read the reporter's proposal on #916 when it lands, and record the design
      as `Decided YYYY-MM-DD:` here.
- [ ] Rebuild the issue's synthetic Si arms as a test fixture: the truth, cI
      √2·a₀, cF +0.6 %, cP a₀, cP 2a₀, the steeper-background arm, and a
      tetragonal descent of the true lattice; exact and picked lines.
- [ ] Candidate-independent inputs for `absent_reflections`: the shared or
      pattern-owned background and the measured width (WP-1043's design).
- [ ] Charge absences at the grade beyond index 2–4, with the glide and
      unresolved-split guards; re-measure every `predicted_but_absent` count in
      the tree and record the moves.
- [ ] Revisit `fom_panel_disagrees` only on the same arms, after the repair.
- [ ] Tests, and `tests/test_acceptance_indexing.py` green.
- [ ] Skill: the indexing reference row for any changed caveat or grade rule.

## Acceptance

On the #916 arms every wrong cell reads a non-zero `predicted_but_absent` and
ranks below the truth, with the truth's grade not lowered by its 5/18 glide
absences; Si, corundum and magnetite keep their correct cells.

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #916 (body, and the follow-up on `fom_panel_disagrees`).
- WP-1043 (the magnetite measurement and the recorded design), WP-1449.

## Handover log

- **2026-10-13** — created, from the 2026-10-13 issue triage (issue #916).
  Checked against the tree at c3d0367: every symbol the issue names exists
  where it says, nothing touching `absent_reflections`, `supercell_checks` or
  the grade moved since the issue's `dd20f0fd7`, and the three rows, the
  hR-first ranking and the all-`low`-through-the-panel-flag reproduce. No open
  WP owns it: WP-1043 recorded the repair as unowned and asked for it to be
  scheduled on its own, WP-1449 (✅) shipped the index 2–4 refutation only,
  WP-1511 fences the blind search, and WP-1542 is the opposite sign in a
  refinement. *Next:* wait for the reporter's measured proposal on #916, then
  task 2.
