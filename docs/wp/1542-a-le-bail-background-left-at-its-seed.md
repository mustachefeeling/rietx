# WP-1542 — a Le Bail background left at its seed

Milestone: unscheduled · Status: 🔄 2026-10-08 — #725's opt-in `auto_background(seed=True)` landed from outside (PR #744); every task remains
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-03 — a background too low reads as a good Le Bail fit and feeds every structure fit after it; a path few fits run

## Goal

A Le Bail fit whose background sits at a seed that is too low says so, and
the Le Bail call has a stated background protocol that does not need the
person to spot a flat line in a plot.

## Context

**The failure, from a real run** (2026-09-28, the review of `solution case 1`,
private corpus map § 5; WP-1510 has the source). The agent followed SKILL.md
§2 rule 5 and seeded every coefficient of an `auto_background` P-spline at a
low percentile. The pattern carried a broad diffuse hump over several degrees.
The free per-reflection intensities absorbed it, the background stayed at its
seed, and the Lorentzian width term grew to carry the hump's tails (it fell 4×
once the background was corrected). The cell was unaffected, so nothing looked
wrong. Every structure fit after it inherited a background that was too low,
with light-atom Biso at bounds and strong peaks under-predicted, for about two
hours, until the person saw the flat line in a plot.

**What worked** was a SNIP estimate held fixed under a 4-term Chebyshev: Le
Bail Rwp fell to 0.74× its first value. A fully free background went the other
way (`BACKGROUND_ABSORPTION`, R² 0.70 against the scale). The agent wrote its
own SNIP although `rietx.background.snip` ships, and the skill names neither it
nor this failure.

**Why nothing fired.** Root CLAUDE.md § Background flexibility: a background
able to imitate the peaks is measured (`background_absorption`), and the
too-stiff side has no guard. Under Le Bail the intensities are free, so a hump
the background cannot reach goes into them rather than into the residual. The
tell named in WP-1323's review is a width term that grows while the background
sits at its seed.

**Why it is not WP-1323's.** That WP's stop rule watches Rwp across passes, and
this failure lowers Rwp. WP-1323 shipped in 1.6.0 and closed with this filed
here (2026-10-03, at the maintainer's request).

### Inherited

- **2026-10-08, from the second issue triage (issue #833): a second voice
  for #725's default.** #833's third item asks for `auto_background(seed=True)`
  as the default, beside a REML-chosen P-spline λ and a
  `BACKGROUND_ORDER_AT_CAP` finding, which are WP-1931's. No new evidence
  for the seed itself; the 2026-10-05 entry's "whether a default changes is
  the maintainer's" still stands, now asked by two issues.
  Decided 2026-10-08: the default stays `seed=False` until task 4 has
  measured the seed beside the SNIP-held protocol; the choice is made then,
  from those numbers.

- **2026-10-08, from the issue triage (issue #740): a second case of this
  WP's failure, with a sharper reading of its mechanism.** The reporter's
  synthetic LaMnO3-like Pnma pattern (CW neutron, 2.4 Å, background
  300 + 2·2θ) at the true cell and profile, background free and seeded at the
  10th percentile of y (SKILL.md §2 rule 5), gives Rwp 1.62 % under one Le Bail
  stage at 100 or 400 `lebail_cycles`, against 1.09 % for the Rietveld fit
  of the true structure and 1.06 % for Pawley. The deficit is at 90-150°, where
  the weak dense reflections sit. The reporter's open question was whether the
  EM partition or its weights cause it. A probe points away from
  both: the Le Bail intensities are partitioned at stage start against the
  *seed* background (the same point as the 2026-10-05 entry above), and
  re-partitioning on the fitted background closes the gap. The mechanism
  (intensities absorbing the seed's deficit where reflections are dense) is
  the reading the numbers fit, not something the probe isolated.
  Measured: after the one stage the fitted background sits at 0.88 of the
  true one at 100° and 0.95 at 140° (0.99 at 20° and 60°), and the residual rms
  by 20° band, starting at 10°, is 0.94 0.89 0.97 1.07 1.85 2.34 1.74. Two
  stages in a row (100 cycles each, so the second partitions on the background
  the first fitted) end at 1.18 %, three at 1.10 % with bands 0.94 0.87 0.94
  1.04 1.01 1.16 1.05. One stage seeded at the Rietveld fit's own background
  ends at 1.09 %. The seed here is 346 counts against a true background of
  580 at 140°. This differs from the case 1542 was filed on
  in one respect: there the free intensities absorbed a hump and Rwp *fell*;
  here a low pedestal seed leaves Rwp *above* the structure's, so the finding
  1542 task 3 designs should fire on the background having moved a long way
  from its seed across stages, not only on a width growing. It also sharpens
  task 4: the comparison of protocols should include "partition again after
  the background solve", since a second stage does it for free.
  Not tested: the reporter's second observation, that a `profile_only` run on
  the pattern's own passes rises 1.72, 1.81, 1.82, 1.82 %. It is the same
  seed in the first pass, but the rise across passes was not reproduced.
  Checked against the tree at 5d1f5f67: reproduced to the digit. Rietveld
  0.0109; Le Bail 0.0456 / 0.0163 / 0.0162 at 3 / 100 / 400 cycles; Pawley
  0.0106 (the reporter's script, 5 s on this machine). `lebail_update` runs at
  stage start (`refine.py:3565`, on `table.x0()`) and after the solve
  (`refine.py:3864`); the reported Rwp equals the one recomputed from the
  returned `y_calc` (0.0163 both). No other open WP owns
  it: 1323 (the stop rule) is shipped, 1511 chooses between cells and 1545 is
  the notebook that reproduces the 03 case.

- **2026-10-05, from the issue triage (issue #725): a second user asks for
  §2 rule 5 as `auto_background`'s default, and the proposed default is the
  start of this WP's own failure.** The proposal: `auto_background(data, …,
  seed=True)` sets the Chebyshev constant term, or every P-spline
  coefficient, to a low percentile of y_obs over the fitted range; `seed=False`
  keeps today's zeros; the skill rule becomes "seed it yourself only for a
  hand-built background". Not proposed: seeding inside the Le Bail stage.
  Evidence: a CW neutron showcase run (λ ≈ 2.4 Å, FWHM ≈ 0.5°) whose unseeded
  first pass sent every TCHZ term to its bound and whose seeded run did not;
  not reproduced on lab silicon by the reporter. *Checked at `32ef5a6`*:
  `auto_background` returns all-zero coefficients for both kinds (15 P-spline
  and 5 Chebyshev on the issue's silicon, 5th percentile 893 counts), and the
  first `lebail_update` runs at stage compile on `y_obs − 0`. Task 4 should
  measure this seed beside the SNIP-held protocol, on the hump fixture and a
  high-pedestal one. Whether a default changes is the maintainer's.
- **2026-10-07, from WP-1545 (notebook 03): the indexer's own validation Le
  Bail may be a sibling.** On a synthetic aragonite pattern (Cu Kα, 10-80°,
  flat 200-count background, reproducible from
  `examples/tutorials/03_peaks_indexing_lebail.py`) the true cell's validation
  fit returns Rwp 0.257 and `INDEX_IMPURITY_LINES` says 96 of 105 observed
  peaks are unmatched. A Le Bail fit of the same candidate with the constant
  term seeded at the 5th percentile reaches 0.071 then 0.061 over two passes,
  and matches every peak. Not measured: whether the validation fit seeds its
  background at all. The tutorial tells the reader the impurity count follows
  from the poor fit.

## Non-goals

- The alternation's stop rule and keep-best (WP-1323, shipped).
- A too-flexible background, which `BACKGROUND_ABSORPTION` already measures.

## Tasks

- [ ] Reproduce on a fixture the tree can hold: a synthetic pattern with a
      broad hump under the peaks, Le Bail from a low-percentile seed. Record
      the background's movement from its seed and the width terms per pass.
- [ ] Name the test for "the background never left its seed while a width
      grew", with where its threshold comes from (measured here or quoted).
- [ ] A finding that names it, on the Le Bail path at least.
- [ ] The protocol: whether the Le Bail call should start from a SNIP estimate
      held under a low-order Chebyshev, as a default or as the skill's rule.
      Measure both on the fixture before choosing.
- [ ] Skill: SKILL.md §2 rule 5 and `references/judging.md` name
      `rietx.background.snip` and this failure.
- [ ] Tests, with obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_lebail_alternation.py tests/test_background_auto.py tests/test_skill.py
.venv/bin/python -m ruff check src tests examples
```

On the hump fixture, the low-seed Le Bail fit reports the finding, and the
protocol's fit leaves the hump in the background, with the width terms
within their no-hump values.

## References

- WP-1323 (the alternation; this was its Inherited entry), WP-1055
  (`FitReport.background`), WP-1454 (λ against the data).
- Ryan, C. G. et al. (1988). *Nucl. Instrum. Meth.* B34, 396 — SNIP, as
  `rietx.background.estimators` cites it.

## Handover log

- **2026-10-06** — Maintainer decision on #725, through draft PR #744:
  `auto_background(..., seed=True)` is wanted as an option, and the default
  stays `seed=False` (all-zero coefficients). Whether the default ever
  changes still waits on task 4's measurement of the seed beside the
  SNIP-held protocol, on the hump fixture and a high-pedestal one. #744's
  synthetic (a pedestal under peaks 22 times higher, Le Bail
  `profile_only`) is that high-pedestal fixture: Rwp 0.0605 unseeded against
  0.0437 seeded, and the Lorentzian X 0.0565 against 0.0 (true 0.001).
  *Recovered 2026-10-10: committed after PR #796 merged, so it reached main
  only now.*

- **2026-10-03** — filed from WP-1323's Inherited entry when 1323 closed. No
  open WP owns a too-stiff background: the open rows of the index carry no
  Le Bail or background protocol, and 1530's held background is a TOPAS
  reader's. *Next:* task 1.
- **2026-10-08** — #725's proposal landed from outside as an opt-in: PR #744
  (head `ecea30f4`), merged as `ba732997` by `/pr-review` after three rounds.
  `auto_background(data, seed=True)` starts the Chebyshev constant term, or every
  P-spline coefficient, at a low percentile of y_obs over the fitted range.
  `seed=False` is the default and keeps today's zeros. SKILL.md §2 rule 5 and
  `references/judging.md` now name the call in place of the hand recipe. The
  default is unchanged, and #725 stays open on whether it moves. *What it does
  not do:* none of this WP's tasks. A seeded background can still stay at its
  seed while a width grows, so tasks 1-3 measure what they did before. Task 4
  now compares this seed with the SNIP-held protocol rather than with a hand
  seed. *Gate:* stacked with #776, #746 and #801 on `5d1f5f67`; the results are
  in WP-1805's 2026-10-08 entry. The only slow failures are #820's, which also
  fail on `main`. *Gotcha:* `test_skill_claims.py` classifies every number in
  the skill body, so a rule-5 edit that drops a number must drop its row too.
  Round 2 caught that. *Next:* task 1.
