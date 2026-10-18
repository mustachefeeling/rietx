# generality — pay for established heuristics, leave the reasoning to the caller

**Opened 2026-10-18** by the maintainer, from a concern rather than an issue: many
features are fitted to the specific test cases that produced them and do not serve a
general-purpose package. The block 20xx is claimed for it. [`../ROADMAP.md`](../ROADMAP.md)
§ generality carries the short prose, and the WP index lists the rows.

Narrative about the WPs below goes to the record of the release in flight,
[v1.10](v1.10.md) today, as for every other WP (protocol rule 5).

## Scope

The design ethos, in the maintainer's words: rietx pays the tab for any well-established
heuristic and leaves reasoning to agents or humans. The milestone audits every place the
package decides something on the caller's behalf, sorts each by the rule below, demotes
what the rule does not keep, and installs a guard so the next WP cannot add one unaudited.

Nine WPs, 2001 to 2009. 2001 is the rule written down, the audit table and the guard, and
it lands first. 2002 to 2007 are audits, one per seam. 2008 slims the agent skill to the
API, the feedback surface and sourced traps. 2009 rewrites the rulebook rules that generated the overfit. Each WP file states
its own context; nothing is restated here except the rule, which every WP applies.

**Not in scope.** No new physics, no new correction, no new plan preset. A heuristic the
audit finds wanting is demoted, and anything needing a redesign rather than a demotion is a
follow-up WP filed from the audit's table. The reader repair records (`io/`'s 90 codes plus
five raised by name, each a statement of what was done to a file), the GUI's 27 HTTP error
names, the eight plan presets and the nine stage fields were measured and not pruned at the
open; 2006 still confirms the reader codes row by row.

## The rule

Every heuristic is sorted into one of three tiers, and each part of it separately: the
statistic it computes, the threshold it tests against, and the action it takes. A statistic
may be tier 2 while its threshold is tier 3 (ΔBIC: Schwarz 1978 and the Kass–Raftery bands
are cited; the effective sample size N/f² is rietx's own). A threshold derived from another
constant inherits that constant's tier only where the derivation has no free factor; a
factor is a threshold of its own (`SCALE_B_SEPARATION_FLOOR` is 2√`PINV_RCOND`: the root
inherits `rcond`'s tier, the 2 is tiered on its own evidence).

1. **Physics or arithmetic.** Deterministic from the model: a symmetry-fixed angle, a
   column with zero gradient, σ withheld because the scale is unknown. Kept. A numerical
   floor such as `rcond` belongs here.
2. **Established practice.** A citation that validated it, or the same action taken *by
   default* in GSAS-II, FullProf or TOPAS. Computing a statistic is not acting on it: every
   code reports R_Bragg and WP-1069 rejects it as evidence; GSAS-II concatenates multi-range
   scans and rietx refuses to. Kept, and the registry entry names the source.
3. **rietx's own.** Everything whose provenance is "measured on NAC" or a WP number. Each
   is either **demoted** or **kept on two grounds together**:
   - the mechanical ground: it holds across at least three unrelated dataset families,
     counted by laboratory, instrument and material rather than by file (a 1 213-record
     archive from one source is one family), with a stated case where it fails; and
   - the judgement ground, answered by the implementing agent and approved by the
     maintainer in a batch: **shown this statistic, would every competent refiner take
     this action?** An action is kept only where the answer is yes. Where two careful
     people could respond differently to the same number, the choice is reasoning, and
     reasoning is the caller's (DESIGN.md § North star): the package reports the number
     with its meaning and stops. The implementing agent names a competent caller who
     would choose otherwise and the situation they are in, or says none exists; the
     judge tries to name one. Whether the caller could *see* the problem is not the
     test, because what rietx returns is rietx's own choice and any action can be
     turned into a report of its statistic (fourth review; the earlier wording rewarded
     an action for lacking a record field). Visibility is instead a requirement on both
     branches: a kept action leaves a record field, a demoted one leaves its statistic.

   The series discontinuity test fails the judgement ground: a jump may be a transition,
   a sample shift or a wrong model, three careful responses at least, so rietx reports
   the step size, may *suggest* a symmetry-mode refinement, and enforces no test. The
   absent-phase hold passes it: no competent refiner lets a phase the data cannot see
   refine its cell (free, it walked 14.9 Å from truth while Rwp did not move, the v1.3
   row), so only its 3σ threshold is on trial, under the mechanical ground. The
   quarantine of a diverged pattern passes it too, since no one wants a diverged fit
   seeding its successors; the earlier visibility wording had marked it contested.

   **Tier 2 will rarely cover an action.** GSAS-II, FullProf and TOPAS take almost no
   automatic actions; the person at the GUI decides. So nearly every action in 2002 and
   2003 is tier 3 and the judgement ground decides it, which is why its wording carries
   the audit. A tier-2 *statistic* under a tier-3 *action* is the common shape.

   **Where three families do not exist.** A rare feature (magnetic, Stephens strain, TOF)
   has one family on disk or none, and rarity is not overfit. Its action is judged on the
   judgement ground alone; where kept, its threshold stays at the measured value with
   `evidence` naming the one family and the table row tiered `3` with grounds that say so,
   and the diagnostic's explanation says the threshold is a hypothesis. The row is
   re-tiered when a second and third family arrive. Chosen at the fourth review over
   demoting by construction, which would strip every rare feature of its one unanimous
   action; the maintainer may reverse it.

   **A caller pays in tokens and a fit in seconds**, so the default is the one that
   reaches a right answer in the fewest calls. The narrow exception the earlier wording
   carried, for work that is expensive or impossible to redo (an hour-long indexing search,
   a 200-pattern batch, a write into a project's history), is one instance: there the
   package may take the conservative action even where opinions differ, and records it.

**Answer-invariant efficiency** is a fourth class with no tier. `FIRST_RUNG_FACTOR` was
measured bit-identical on two chains (0 of 1030 and 0 of 392 accepted values moved) with
2.3× margin: the budget truncates only a losing rung while a winning one stays cheaper than
the budget, so the invariance is a measured margin, not a construction, and its own
docstring calls it a bet. Such an item needs an invariance test that also asserts the
margin, and nothing else; the audit classifies it and moves on.

**Demotion.** A code whose verdict rests on a tier-3 threshold keeps its text and loses the
action keyed on it; its `level` drops to `info` where the code still fires on a tier-1 or
tier-2 fact. Where the threshold decides whether the diagnostic exists at all
(`SEQUENTIAL_DISCONTINUITY` at 5× median and 3σ), there is no verdict to keep: the code is
removed and the number goes in a record field with its meaning. `Diagnostic.level` has no
"none" value and gets none. The maintainer's breaking appetite is high (every user is in
direct contact), so demotions land now; a removed code is staged in the release notes.

**A moved golden.** A demotion that moves a pinned number has moved it for the right reason
only if the new value is no further from the independent reference (a certified cell, a
weighed composition, the cross-code envelope) than the old. Re-pinning records old, new,
dataset and reference distance in the WP handover. A number that moved away from its
reference is evidence the action mattered, and the item goes back through the two grounds.
A pin with no independent reference (a report text golden, a bit-identity golden) is
re-pinned only where the ruling says the number should move, with the mechanism that moved
it named in the handover, and is restored bit-identical where the ruling says it should not.

**A contested demotion is measured on agents** before it lands. The v1.3 round measured
seven of eight agents stopping on a criterion the package states, against zero of 86 in the
baseline, so turning a stated verdict into a bare number may cost real agents something. The
harness is `tests/eval_report_agent` and `tests/eval_skill`; a run is registered before it is
made and its cells are a spend the maintainer approves per session.

## What was measured at the open

Darwin arm64, the worktree at `origin/main` on 2026-10-18; the recipe is in WP-2001.

- 276 distinct `code="…"` literals in `src/rietx`; `rietx.help.DIAGNOSTIC_HELP` (WP-1985)
  holds 256 `Diagnostic` codes, held equal to the raise sites both ways
  (`docs/reference_pages.diagnostic_index()`, the inventory to build the table from). 7 of
  the 256 are raised through a name rather than a literal (two in `schemas/results.py`,
  five in the GSAS instrument readers), so a grep for the literal undercounts them. By
  subsystem, unique literals: io 90, `refine.py` 61, indexing 48, gui 27, crystallography
  20, sequential 12, report 5, multi 5, and 9 in files no seam names (`background/select.py`,
  `optimize/qpa.py`, `schemas/migrate.py`, `strategy/magnetic.py`,
  `strategy/fraction_profile.py`; 2002 and 2005 own them). 70 are not mentioned in the
  agent skill. 6 have no test; about 20 are touched by one test file.
- 127 module-level numeric constants in `report/`, `strategy/`, `optimize/statistics.py`,
  `refine.py` and `sequential.py` (AST walk); about 8 cite a paper in their comment block,
  3 say they are derived, about 49 cite a WP measurement. Indexing's 76 and io's ~30 are
  on top of that. The same walk over all of `src/rietx` finds 619 (third review): the
  largest files outside the seams are the report schemas (46), the indexing schemas (32),
  the GUI's 3D viewer (18) and the Bruker raw reader (17 byte offsets), so the table's
  walk covers a declared directory list, not the whole package (§ The third review).
- The automatic actions are enumerated by the house rule "a correction ships with a record
  field": `StageResult` carries `held`, `held_reach`, `scale_b_held`, `released`,
  `moment_flat_axes`, `moment_turned`, `blocked_by_hold`, `seeded`; `SeriesEntry` carries
  `rung`, `reseeded`, `rwp_fence`. Three holds live in `Refinement._run_stage` (the absent
  phase, WP-1301; the moment, WP-1327; the scale–B ridge, WP-1534). `direction="both"`
  and `verify_discontinuities` are opt-in.
- The agent skill is 61 000 words; 130 lines carry a `(Measured: …)` or
  `(Hypothesis: …)` tag (145 tags). `tests/skill_caps.py` fails growth.
- `report/` carries 18 `ActionKind` members and 4 gates on rietx's own thresholds.
- 3 of 193 top-level exports are used by nothing in `src`, `examples` or `gui`. The derived
  public surface is 2 238 entries; reachability over them is 2006's.
- Calibration: WP-1985 wrote 253 explanations for ~3.8 M subagent tokens over 18 lanes.

## The order

2001 first: the audits write into its table and the guard it installs is what every later
WP is held to. 2002 second and alone: `_run_stage`'s holds run inside every fit, including
the fits the package runs for itself (the report's rival fits, the extinction screen, every
pattern of a chain), so 2003 and 2004 read a tree 2002 has settled. 2003 before 2004: 2004
owns the one `THRESHOLDS_VERSION` bump and 2003 hands its width-growth rulings to it, so
2004 depends on 2003. 2005, 2006 and 2007 run any time after 2001. 2008 after the audits,
since a demoted code's skill row changes. 2009 last.

**A gate after 2004.** The premise was measured by provenance (49 of 127 constants cite a
WP measurement, 8 a paper) and not by harm: no case on disk shows a rietx-own heuristic
giving a wrong answer on an unfamiliar dataset, and the one worked example of a false
alarm costs no number. So 2002 to 2004 are also the test of the premise. Their handovers
report how many rows were demoted, and the maintainer decides then whether 2005 to 2007
run; if the holds and gates mostly pass the judgement ground, the remaining value is the
guard and the prose, which 2001 and 2009 deliver.

## Acceptance

**These rows are written at the open** (protocol rule 6). Each names a state a later
session can check without asking what was intended. The session that opens each WP
sharpens its own row here.

- **Every verdict and every action has a tier** (2001–2007). The audit table names each
  diagnostic code that carries a verdict, each automatic action and each threshold
  constant with its tier, its evidence and, for tier 3, the two grounds and the approval
  date. A meta-test holds the table equal to the tree both ways.
- **No tier-3 action runs by default without its approval** (2002, 2003, 2004). Every
  hold, carry, refit and fence that survives names the families it was evidenced on and
  the maintainer's dated approval; every other one is demoted or opt-in.
- **A new heuristic cannot land unaudited** (2001). A diff that adds a diagnostic code, a
  record field on `StageResult`/`SeriesEntry`/`RefinementResult`, a module-level numeric
  constant in a directory the table's walk declares, or a `suggestion=` string trips a
  test until the table has its row; the names allowed at `unaudited` are a committed list
  that only shrinks, so the test needs no git; and `/wp-handover` dispatches a
  fresh-context review that drafts the case against it whenever the diff touches the table
  or that list.
- **The goldens hold or improve** (every audit). The acceptance suites pass on the final
  tree; every re-pinned number is recorded with its reference distance, none further
  from its reference than before.
- **The skill is the API, the feedback surface and sourced traps** (2008). Every row
  outside the generated API files is vocabulary, or a trap naming a source outside
  rietx's runs; no row states a verdict the package no longer makes or a rule measured
  on rietx's own data; the total falls and the caps re-land at the new sizes.
- **The rulebooks prefer a record field to a code to an action** (2009), and the rule that
  rewards a firing code is rewritten.
- **A held-out family moved no number away from its reference** (every audit, checked at
  close). One or two families named at 2002's open and used as evidence by no audit; at
  close the standards' acceptance protocol is run on them and every number with a
  reference is no further from it than at the open. The one row that measures generality
  rather than the audit (fourth review).
- **An agent given the number reaches the answer the verdict gave** (2004, 2008). For each
  demoted class the harness is run once, registered first and approved per session, and
  the handover reports the rate beside the v1.3 baseline (seven of eight stopped on a
  stated criterion, none of 86 without one). The milestone promises no rate; it records
  the gap per model generation, since the north star bets the gap closes.

## Decisions with the maintainer, 2026-10-18

Each with its reason and the alternative it was chosen over, so a later session can
reverse it knowing what it would be giving up.

- **The unit of pruning is the verdict and the action keyed on it, not the code count.**
  The maintainer's first framing was "too many diagnostic codes". Measured, the count is
  the symptom: 90 of the 276 literals are reader repair records and 27 are HTTP error names,
  neither a heuristic, and GSAS-II and TOPAS each emit hundreds of warnings. A code that
  reports a number with its meaning is cheap and cannot clash with anything; a verdict on
  a threshold of ours can, and an action keyed on it decides for the caller. So the
  audits key on the record fields and the constants, and a code is pruned only where its
  verdict or trigger is tier 3. Chosen over cutting codes by count, which would have
  removed honest records and left the actions in place.
- **Three tiers, tiered per statistic, threshold and action.** One tier per heuristic
  would have let a cited statistic carry an uncited threshold (ΔBIC's bands are Kass and
  Raftery's, its effective sample size N/f² is ours). "Documents or usage in
  well-established codes are both grounds" for tier 2, the maintainer's words; the usage
  must be the same *action by default*, on the second review's finding that every code
  computes R_Bragg and WP-1069 rejects it, and GSAS-II concatenates scans and rietx
  refuses to.
- **Three unrelated families for the mechanical ground.** A threshold that holds on
  three families is a different claim from one tuned on LaB6 alone, and three is the
  smallest number that can show a failure case beside two successes. Counted by lab,
  instrument and material because the size-flag thresholds were calibrated on 1 213
  records from one source, which is many files and one population. Not a measured
  constant; the maintainer may move it.
- **The second ground is judgement, superseding visibility (fourth review, 2026-10-18).**
  The second review proposed "can the caller detect and correct it at the moment the
  package acts"; the maintainer corrected it to visibility and significance (fits are
  cheap, so a visible mistake is a rerun). The fourth review found that wording decided
  nothing: what rietx returns is rietx's choice, any action can be reported as its
  statistic instead, so "could the caller see it" sorted items by whether a record field
  happened to exist. The record's own anchor example failed its own test (the
  absent-phase statistic reported as a diagnostic is visible, and a rerun is cheap). The
  maintainer confirmed the criterion that was meant: would every competent refiner take
  this action on seeing this number? Yes keeps it; a named dissenter demotes it. Timing
  survives as the expensive-to-redo exception, now one instance of the token rule.
- **The north star is written in DESIGN.md** (2026-10-18, § Why this package exists). The
  maintainer's position: agents will keep improving at crystallographic judgement, so
  performing it on their behalf grows less wise with each generation, and rietx's
  advantage is the best engine and outputs for a strong reasoner. Two qualifications were
  agreed. The unanimous actions do not shrink as callers improve, since the line is drawn
  by the physics; and a caller pays in tokens, so a package that decides nothing can be
  worse for the caller than one unanimous default. Chosen over leaving the ethos in this
  record alone, which a session changing the engine would not read.
- **A gate after 2004, and three families is not a demotion by itself.** The premise is a
  conviction measured by provenance, so the first three audits test it and the maintainer
  re-decides 2005–2007 on their counts. A rare feature with one family keeps its unanimous
  action with its threshold marked a hypothesis (§ The rule). Both from the fourth
  review; the second is the filing session's choice and reversible.
- **The skill carries vocabulary and sourced traps, nothing prescriptive** (2026-10-18,
  the maintainer). Its role under the north star is to save tokens: an agent that knows
  the API and the feedback surface makes the right first call. A rule measured on rietx's
  test data is the overfit written as prose and leaves; a trap stays only with a source
  outside rietx's runs (the literature, a reference code's documented behaviour) and only
  where a strong agent would not bring it to mind. Chosen over the second review's
  position that a demoted verdict's meaning moves into the skill, which would have made
  the skill the new home of the heuristics the audits remove. The maintainer expects the
  skill to shrink toward its traps as the manual improves; no agent needs a GitHub skill.
- **Rulings by class where the evidence is shared.** Roughly 500 rows enter the table and
  a hundred or more will be tier 3; the maintainer's own calibration says a brief over
  150 words bounces. So a batch groups rows that rest on one evidence base (the size-flag
  thresholds calibrated on one archive are one ruling) and the table records the class
  ruling on each row. Chosen over per-row briefs, which the WPs had asked for.
- **The automatic runners are re-examined for generality, not dismissed.** The
  absent-phase hold is the case the rule keeps (a 14.9 Å cell walk invisible in Rwp), and
  it is a runner. So each runner goes through the two grounds like anything else, and the
  maintainer asked that none be removed on the strength of being a runner.
- **Batch approval**, as `/issue-review` does it: an audit presents its table once, the
  maintainer rules on each row, rulings are dated into the table. Chosen over per-item
  approval as found, which interrupts the audit and loses the comparison across rows.
  The rubber-stamp risk of a batch is answered by the judge drafting the case against
  each row rather than the author alone writing its defence.
- **Demotion now, deprecation later by best practice.** The maintainer's breaking appetite
  is high (every user is in direct contact, memory `rietx-few-users-in-direct-contact`),
  so a demotion lands when ruled and a removed code is staged in the release notes.
  Chosen over a deprecation period, which would keep the overfit running by default for
  a release with no one waiting on it.
- **Agent stop-rate is not an acceptance number.** The v1.3 round measured seven of eight
  agents stopping on a stated criterion against zero of 86 without one, so the reviewer
  asked whether demoting verdicts to numbers would cost that. The maintainer's ethos says
  a number with its meaning is what an agent reasons from; whether that suffices is
  measurable, so a contested demotion goes through the harness before it lands and the
  milestone does not promise a rate. The harness costs money and each run is approved
  per session.
- **Recurrence is guarded by a tripwire and a judge, not by prose alone.** The
  maintainer's instinct was an agentic guard in the `.md` files; the second review added
  a deterministic half. Prose in a rulebook is skimmed, and a tripwire cannot judge, so
  the tripwire (a test over the diff for a new code, record field, constant or
  suggestion) decides *whether* a fresh-context review runs and the review decides
  *what it finds*. A registry row written by the implementing agent is self-certification,
  so the judge drafts the case against. The rule also travels to the maintainer's other
  projects through `claude-config/workflow/LESSONS.md`, on the maintainer's ask; the
  mechanism stays rietx's and each project words the rule for itself.
- **Nine WPs, each Opus-led with subagents.** The maintainer's token economics: an audit
  reads a lot and returns a table, which is the shape that pays for lanes (memory
  `subagent-economics`), and one session cannot hold 17 000 lines of runner plus its
  evidence. The seams were cut by what each session must hold at once, not by file; the
  second review split the runner into one-stage and chain actions and gave indexing its
  own WP. WP-1985's 3.8 M subagent tokens for 253 explanations is the calibration.
- **The audit table is its own module, not fields on `HelpEntry`.** `HelpEntry` is a GUI
  type served at `/api/help`, so a field there moves the TypeScript, the vitest table and
  the committed dist for a maintainer-facing fact. Taken by the filing session on the
  second review's finding; the maintainer should know it can be reversed.
- **One reviewer proposal declined as a plan decision**: that `RESEED_FACTOR`'s Rwp fence
  become opt-in. It may be right, and 2003 measures it on three chain families; deciding
  it at filing would be the overfit this milestone is about, one rank up.

## The two reviews at the open

The plan was reviewed twice before filing: once by the authoring session, once by an
Opus agent given the plan and the tree and told to find what was wrong. The second review
changed it in six places, each recorded in the WP it touched: the reasoning ground's
wording (above); demotion cannot keep a threshold-gated code (above); the action inventory
is the record fields, not keyword counts; tier 2 needs the same action by default; each
audit keeps a clash table, since heuristics interact (WP-1320 chose the fraction profile's
axis because the collapse rule fought it); and the rulebook's own rules are the generators
of the overfit (2009). One proposal was declined as a plan decision and handed to 2003 as
a finding to measure: that `RESEED_FACTOR`'s Rwp fence become opt-in.

## The third review, 2026-10-18

A fresh session after `/clear` read the record, the nine WPs and the PR against the tree,
checking each named constant, count and cited number. The rule's idea held; what it found
was that the rule has one authority and three copies, and one copy disagreed with it. The
maintainer approved every change below and they landed on the filing branch.

- **The reasoning ground states its polarity.** The record asked the question and only the
  example said which answer keeps an item; 2001's restatement said "yes to both halves",
  which keeps what the caller *can* see. Now stated in § The rule and the copies carry a
  sentence and a link.
- **The constant walk covers a declared directory list.** Over all of `src/rietx` the AST
  walk finds 619 module-level numbers against the 233 the open counted in the seams, and the
  surplus is byte offsets, pixel sizes and schema defaults; mirroring each value would make a
  reader's offset edit reopen an audit. The list is data in the table module and names the
  audits' seams; a directory outside it is out of scope by declaration. Chosen over the full
  walk with a mechanical "fact" kind for the rest, which is about 400 rows of noise.
- **The growth guard is a committed baseline, not a `git show`.** CI checks out at depth 2
  with no `origin/main` ref and a local worktree's can be days stale, so a test reading the
  base table through git skips exactly where it gates a merge. The names allowed at
  `unaudited` are a list in the table module that may only shrink; the handover dispatches
  the judge when the diff touches the table or the list.
- **A golden with no independent reference has its clause** (§ A moved golden).
- **`FIRST_RUNG_FACTOR` is invariant by measured margin, not by construction**; its
  invariance test asserts the margin too (2003).
- **A derived threshold inherits a tier only without a free factor** (§ The rule).
- **2003 says where the discontinuity suggestion lives** (the skill's series reference, read
  off the trajectory; no code replaces it) **and weighs the quarantine against the stated
  exception** for work expensive to redo, not on visibility alone.
- **2004 depends on 2003**, so the one `THRESHOLDS_VERSION` bump can carry 2003's rulings;
  **2008's dependencies on 2002–2004 are hard**, as its own priority line said.
- Stale counts fixed (2006's 253; the record's 89 for `io/`), and "left alone at the open"
  reworded to "not pruned", since 2006 audits those rows.

## The fourth review, 2026-10-18

A fresh session read the plan for its reasoning rather than its counts, beside a
`/code-review` pass over the prose. The maintainer confirmed the central finding and
stated the position now in DESIGN.md § North star. What moved:

- **The judgement ground replaces the visibility ground** (§ The rule, § Decisions). The
  quarantine's classification flips from contested to kept; 2003 measures what the caller
  sees rather than whether it survives.
- **Acceptance gains the two rows that measure the outcome**: a held-out family, and the
  agent harness per demoted class. The earlier six measured the audit.
- **A gate after 2004**, since the premise is a conviction; **rare features keep a
  unanimous action on one family**; **rulings by class**; **tier 2 will rarely cover an
  action**, stated so the audits expect it.
- **2008 is recast around the skill's role**, stated by the maintainer and now in the north
  star: the skill exists to save tokens by making the API and the feedback surface known
  accurately, is not prescriptive, and beyond that names only traps with a source outside
  rietx's runs that a strong agent would not bring to mind. Rows measured on rietx's own
  data are cut or moved into the package's output; the total falls, reversing the second
  review's "the total may not fall"; the skill shrinks further as the manual improves and
  reaches the corpora models train on.
- **2006's dead-surface walk is named as the API half**, not the heuristics half, so its
  "mostly tier 1" audit is not read as carrying two deliverables by accident.
- Ten mechanical defects from the code review, each in the WP it touched: two acceptance
  globs that matched no file (2004, 2006); 2002 and 2001 disagreeing about `optimize/lm.py`;
  the constants outside the seams given owners by directory (2001); the judge's dispatch
  moved to handover step 7, since step 6 is skipped on a prose branch; 1341's note no
  longer defers a threshold under a later version bump; two codes raised from two seams
  given one owner; 2006's stale 136; the table module named `_audit`; 2003's two
  discontinuity constants given rows.
