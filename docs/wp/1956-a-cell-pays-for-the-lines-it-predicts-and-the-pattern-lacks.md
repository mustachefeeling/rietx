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

**The question the issue asks** (from #916): should a cell pay at the grade,
and with which inputs: one background shared by all candidates, the measured
width, line-set containment rather than lattice containment for
`supercell_chance`?

**The reporter's measured proposal** (#916, 2026-10-13 06:56Z; a spike outside
the tree, on the issue's own seeds, not re-run here). Three findings and a
fourth from the public lab patterns in `tests/data/qarr`:
1. *The inputs were the whole of the sign problem.* Fed the picker's background
   envelope and the peak list's widths and shapes (no Le Bail),
   `absent_reflections` reads 24/40 on cI √2·a₀, 21/36 on cP a₀, 107/140 on
   cP 2a₀ and 9/35 on the hR cell, against 3/15 on the truth (its d-glide);
   the candidates' own fits read 0, 0, 0, 0 and 3. A resolved split reads only
   7/77, its partners sitting in real lines' tails.
2. *The reversed questions are asked in the search window* (3 × σ_eff with the
   allowance folded in, ±0.15° on a 0.023° FWHM). At one FWHM (floored by 3σ)
   after the candidate's common shift is estimated from its forward matches, the
   hR cell's seen fraction falls 0.77 → 0.34 (truth 0.73) and the resolved
   split's 0.99 → 0.56; the unresolved split stays at 1.00 like the truth. An
   allowance bounds a common offset and should widen the forward match only.
3. *WP-1449's chance test reaches every one of these cells* once the parent
   relation is "every observed line the parent indexes, the child indexes"
   rather than a volume ratio of 2-4, keeping its uncancellable-extras guard and
   null: all refuted (0 of 12, 8, 85, 2, 7, 14, 12 extras seen), the unresolved
   split undecided, and the truth as a child of anything never refuted. In the
   search window the hR cell and the resolved split read *supported*.
4. *No absolute absent count can refute*: corundum's own cell reads 5 over the
   full range on real lab data. Inside de Wolff's window (Q of the 20th line)
   the truths read 0 (corundum) and 2 (magnetite) and the wrong cells 7 or
   more, so the count can cap. "Refuted" should mean seen no more often than
   chance (k ≤ n·p₀), not "not significant at α".

The proposal, for the maintainer: (a) a candidate-independent line screen (peak
list + envelope + the existing overlap and quiet rules) supplies the reversed
member at the resolution and the `predicted_but_absent` count; (b)
`supercell_checks` asks indexed-set containment with a three-band verdict; (c)
`predicted_but_absent` caps rather than refutes, and the extinction screen
separates the glide from the oversized cell. The Le Bail validation keeps the
forward question with a shared frozen profile.

**Rules that bind it** (`src/rietx/indexing/CLAUDE.md`): never a confident
singleton; a new indexing rule lands in that file; run
`tests/test_acceptance_indexing.py` before closing anything that touches an
engine or the ranking. Indexing is provisional by declaration
(`PROVISIONAL_MODULES`).

### Inherited

- **2026-10-24, from WP-2041: the detector also goes blind on the *correct* cell, and
  that grade is `high`.** Tutorial 03's synthetic aragonite (P m c n, flat 200-count
  background, `examples/tutorials/03_peaks_indexing_lebail.py`) indexes at `high` over
  10-80° with `predicted_but_absent` 0 of 105. The validation fit's background sits at
  125 counts over 10-11° and 46 over 75-78° against the true 200, and 10-19° holds no
  allowed reflection, so every forbidden position reads as net intensity. Cut the same
  pattern at 35-60° and the background holds (192 at 10-11° on the 60° cut). The count
  then returns 4-6 absences, every one a P m c n extinction: (010) 11.09°, (001) 15.43°,
  (101) 23.68°, (120) 28.71° and (201) 39.54°. The cell grades `low`, found by all three
  engines. 10-60° alone holds 15 such extinctions. So aragonite is a ready fixture for
  this WP's glide guard: a correct cell with glides, synthetic, no impurity.
- **Its outcome decides two things outside `indexing/`.** Tutorial 03's prose reads the
  "0 of 105" as evidence for the `high` grade ("none of the reflections it predicts is
  missing"), and WP-2041 is held on this WP to add the notebook's abstention example
  (a 45° cut, maintainer's choice 2026-10-24). After the repair, say in WP-2041's
  `### Inherited` what the full range and the 45° cut grade, and with which caveats.
  Under decision (c) an honest count caps, so the full range may drop to `medium` and
  print NO CELL unless the extinction screen clears the glide. Rebuild the notebook with
  `examples/tutorials/build.py`, which lists every cell whose output moved.

## Non-goals

- The blind search and enumeration ceilings (WP-1924), dedup across a reduction
  boundary (WP-1932), peak picking (WP-1909), the extinction screen (WP-1910).
- WP-1511's per-cell Le Bail evidence, which fences the blind search itself.
- A refinement's own Le Bail background left too low at its seed (WP-1542): the
  opposite sign, in another call.

## Tasks

- [x] **Decision (maintainer):** the reporter's (a)-(c) above, whole or in
      part, recorded as `Decided YYYY-MM-DD:` here and answered on #916.
      *Decided 2026-10-14: (a)-(c) whole, as PR #941 builds them; answered
      in PR #941's review.*
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
  refinement. The reporter's measured proposal landed on #916 the same
  morning and is in § Context. *Next:* the maintainer's decision on its
  (a)-(c), then task 2.
- **2026-10-14** — from the PR review (PR #941): @yue-here decided (a)-(c)
  whole, including `predicted_but_absent` moving from the refuting set to a
  cap and the matching rewrite of `src/rietx/indexing/CLAUDE.md`'s
  whole-profile validation clause. Round 1 is at `f5617cb8`. Its
  before-merge items: `INDEX_ABSTAINED` still calls `predicted_but_absent`
  refuting, a module fixture with no `xdist_group`, the phantom-supercell bar
  dropped from 95 % to 50 % without a count, `contains` admitting a mutual
  containment at equal volume, `to_cell_candidate` scoring on the old seen
  fraction, and a direct `validate_by_lebail` screening on the peak list's
  range and per-line σ. *Next:* #941's round 2.
