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
it lands first. 2002 to 2007 are audits, one per seam. 2008 is the agent skill read against
the table. 2009 rewrites the rulebook rules that generated the overfit. Each WP file states
its own context; nothing is restated here except the rule, which every WP applies.

**Not in scope.** No new physics, no new correction, no new plan preset. A heuristic the
audit finds wanting is demoted, and anything needing a redesign rather than a demotion is a
follow-up WP filed from the audit's table. The reader repair records (`io/`'s 89 codes, each
a statement of what was done to a file), the GUI's 27 HTTP error names, the eight plan
presets and the nine stage fields were measured and left alone at the open.

## The rule

Every heuristic is sorted into one of three tiers, and each part of it separately: the
statistic it computes, the threshold it tests against, and the action it takes. A statistic
may be tier 2 while its threshold is tier 3 (ΔBIC: Schwarz 1978 and the Kass–Raftery bands
are cited; the effective sample size N/f² is rietx's own). A threshold derived from another
constant inherits that constant's tier (`SCALE_B_SEPARATION_FLOOR` is 2√`PINV_RCOND`).

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
   - the reasoning ground, answered by the implementing agent and approved by the
     maintainer in a batch: **could the caller see this from what rietx already returns,
     and does missing it cost a wrong number?** A fit costs seconds and no tokens, so a
     problem the caller can see is a problem the caller fixes with a rerun. What the
     caller cannot do is detect what the outputs do not show. The narrow exception is a
     mistake that is expensive or impossible to redo: an hour-long indexing search, a
     200-pattern batch, a write into a project's history.

   The series discontinuity test fails both grounds: the kinds of discontinuity are open
   (a phase transition, a symmetry change, a sample shift), the agent can see a jump in
   the trajectory, so rietx may *suggest* a symmetry-mode refinement and enforces no
   test. The absent-phase hold passes both: a flat direction walks a cell 14.9 Å from
   truth while Rwp does not move (the v1.3 row), and nothing in the outputs shows it.

**Answer-invariant efficiency** is a fourth class with no tier. `FIRST_RUNG_FACTOR` cannot
change an accepted value by construction (0 of 1030 and 0 of 392 measured bit-identical).
Such an item needs an invariance test and nothing else; the audit classifies it and moves on.

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

**A contested demotion is measured on agents** before it lands. The v1.3 round measured
seven of eight agents stopping on a criterion the package states, against zero of 86 in the
baseline, so turning a stated verdict into a bare number may cost real agents something. The
harness is `tests/eval_report_agent` and `tests/eval_skill`; a run is registered before it is
made and its cells are a spend the maintainer approves per session.

## What was measured at the open

Darwin arm64, the worktree at `origin/main` on 2026-10-18; the recipe is in WP-2001.

- 276 `code="…"` strings in `src/rietx`; 253 are `Diagnostic` codes in
  `rietx.help.DIAGNOSTIC_HELP` (WP-1985), held equal to the raise sites both ways. By
  subsystem: io 89, `refine.py` 61, indexing 48, gui 27, crystallography 20, sequential
  12, report 5, multi 5. 70 are not mentioned in the agent skill. 6 have no test; about 20
  are touched by one test file.
- 127 module-level numeric constants in `report/`, `strategy/`, `optimize/statistics.py`,
  `refine.py` and `sequential.py` (AST walk); about 8 cite a paper in their comment block,
  3 say they are derived, about 49 cite a WP measurement. Indexing's 76 and io's ~30 are
  on top of that.
- The automatic actions are enumerated by the house rule "a correction ships with a record
  field": `StageResult` carries `held`, `held_reach`, `scale_b_held`, `released`,
  `moment_flat_axes`, `moment_turned`, `blocked_by_hold`, `seeded`; `SeriesEntry` carries
  `rung`, `reseeded`, `rwp_fence`. Three holds live in `Refinement._run_stage` (the absent
  phase, WP-1301; the moment, WP-1327; the scale–B ridge, WP-1534). `direction="both"`
  and `verify_discontinuities` are opt-in.
- The agent skill is 61 000 words; 134 reference rows carry a `(Measured: …)` or
  `(Hypothesis: …)` tag. `tests/skill_caps.py` fails growth.
- `report/` carries 18 `ActionKind` members and 4 gates on rietx's own thresholds.
- 3 of 193 top-level exports are used by nothing in `src`, `examples` or `gui`. The derived
  public surface is 2 238 entries; reachability over them is 2006's.
- Calibration: WP-1985 wrote 253 explanations for ~3.8 M subagent tokens over 18 lanes.

## The order

2001 first: the audits write into its table and the guard it installs is what every later
WP is held to. 2002 second and alone: `_run_stage`'s holds run inside every fit, including
the fits the package runs for itself (the report's rival fits, the extinction screen, every
pattern of a chain), so 2003 and 2004 read a tree 2002 has settled. 2004 owns the
`THRESHOLDS_VERSION` bump and 2003 hands its thresholds to it. 2005, 2006 and 2007 run any
time after 2001. 2008 after the audits, since a demoted code's skill row changes. 2009 last.

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
  constant or a `suggestion=` string trips a test until the table has its row, and
  `/wp-handover` dispatches a fresh-context review that drafts the case against it.
- **The goldens hold or improve** (every audit). The acceptance suites pass on the final
  tree; every re-pinned number is recorded with its reference distance, none further
  from its reference than before.
- **The skill encodes no untagged tier-3 rule** (2008). Every `(Measured: …)` row names
  its families or is demoted to `(Hypothesis: …)`; no row states a verdict the package no
  longer makes.
- **The rulebooks prefer a record field to a code to an action** (2009), and the rule that
  rewards a firing code is rewritten.

## Decisions with the maintainer, 2026-10-18

Each with its reason and the alternative it was chosen over, so a later session can
reverse it knowing what it would be giving up.

- **The unit of pruning is the verdict and the action keyed on it, not the code count.**
  The maintainer's first framing was "too many diagnostic codes". Measured, the count is
  the symptom: 89 of the 276 codes are reader repair records and 27 are HTTP error names,
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
- **The reasoning ground is visibility and significance, not timing.** The second
  review proposed "can the caller detect and correct it at the moment the package acts",
  which would keep the series quarantine on the ground that a diverged pattern seeds its
  successors before the chain returns. The maintainer's correction: fits are cheap, fast
  and cost no tokens, so a mistake the caller can see is a rerun, and what the caller
  cannot do is detect what the outputs do not show. Timing survives only as the narrow
  exception for work that is expensive or impossible to redo.
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
