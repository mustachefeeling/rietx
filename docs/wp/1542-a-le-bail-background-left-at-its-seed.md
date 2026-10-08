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
