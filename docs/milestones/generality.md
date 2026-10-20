# generality — every decision rietx makes holds beyond the data it was tuned on

**Opened 2026-10-18** by the maintainer, from a concern rather than an issue: many
features are fitted to the specific test cases that produced them and do not serve a
general-purpose package. The block 20xx is claimed for it. [`../ROADMAP.md`](../ROADMAP.md)
§ generality carries the short prose, and the WP index lists the rows.

Narrative about the WPs below goes to the record of the release in flight,
[v1.10](v1.10.md) today, as for every other WP (protocol rule 5).

## Scope

The milestone applies [DESIGN.md](../DESIGN.md) § Rules to the tree as it stands.
Rule 1 sorts what the package decides by its kind of ambiguity: the package acts where the
data settle the question, ranks where the data can rank the alternatives, and otherwise
reports the number and stops. Rule 2 asks what reference each number was checked against.
Rule 3 governs the skill (2008). Rule 4's design tests are what the guard (2001), the
feature tripwire (2010) and the rewritten rulebooks (2009) enforce. The milestone audits every place the package decides something on the caller's behalf,
sorts each by the rule below, moves what the rule does not keep to the kind it belongs to,
and installs a guard so the next WP cannot add one unaudited. The maintainer's words at the
open were "rietx pays the tab for any well-established heuristic and leaves reasoning to
agents or humans"; DESIGN.md § History records how that became the purpose.

Ten WPs, 2001 to 2010. 2001 is the rule written down, the audit table and the guard, and
it lands first. 2002 to 2007 are audits, one per seam. 2010 audits features rather than
decisions: each names what verifies its code and what validates its physics (Rule 2). 2008 slims the agent skill to the
API, the feedback surface and sourced traps. 2009 rewrites the rulebook rules that generated the overfit. 2014, filed
2026-10-20, carries 2001's guard to outside PRs, unwatched directories and fixes made after the handover. Each WP file states
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
   scans and rietx refuses to. A statistic or threshold here is kept, and the registry
   entry names the source. An action here still faces the judgement ground under tier 3.
   Its citation or the program's default is evidence that every competent refiner would
   act, and a named dissenter outweighs it (DESIGN.md § Rules, 1; ruled 2026-10-19).
3. **rietx's own.** Everything whose provenance is "measured on NAC" or a WP number. Each
   is either **demoted** or **kept on two grounds together**:
   - the mechanical ground: it holds across at least three unrelated dataset families,
     counted by laboratory, instrument and material rather than by file (a 1 213-record
     archive from one source is one family), with a stated case where it fails. *Holds*
     is measured against each family's independent reference (DESIGN.md § Rules, 2). For
     a number the reference is a certified or published value, which validates, or the
     cross-code envelope, which only verifies. The row says which, and the action leaves
     the number no further from it. For a flag it is a known truth
     (an injected misfit, a weighed impurity), and the flag fires where the fault is and
     stays silent where it is not; and
   - the judgement ground, answered by the implementing agent and approved by the
     maintainer in a batch: **shown this statistic, would every competent refiner take
     this action?** This is DESIGN.md § Rules, 1's unanimity gate. An action is kept only
     where the answer is yes. Where two careful people could respond differently to the
     same number, the action moves to Rule 1's second or third kind. Where the
     alternatives are enumerable and the data score them, the package ranks them with
     their evidence and picks none. Where the explanation depends on facts outside the
     pattern, it reports the number with its meaning and stops. The implementing agent
     names a competent caller who would choose otherwise and the situation they are in,
     or says none exists; the judge tries to name one. Whether the caller could *see* the problem is not the
     test, because what rietx returns is rietx's own choice and any action can be
     turned into a report of its statistic (fourth review; the earlier wording rewarded
     an action for lacking a record field). Visibility is instead a requirement on both
     branches: a kept action leaves a record field, a demoted one leaves its statistic or
     its ranking.

   The series discontinuity test fails the judgement ground and is DESIGN.md's example of
   Rule 1's third kind: a jump may be a transition, a sample shift or a wrong model, and
   which one depends on facts outside the pattern. So rietx reports the step size, may
   *suggest* a symmetry-mode refinement, and enforces no test. The
   absent-phase hold passes it: no competent refiner lets a phase the data cannot see
   refine its cell (free, it walked 14.9 Å from truth while Rwp did not move, the v1.3
   row), so only its 3σ threshold is on trial, under the mechanical ground. The
   quarantine of a diverged pattern passes it too, since no one wants a diverged fit
   seeding its successors, and Rule 1 names it as a protection of expensive work; the
   earlier visibility wording had marked it contested.

   **Tier 2 will rarely cover an action.** GSAS-II, FullProf and TOPAS take almost no
   automatic actions; the person at the GUI decides. So nearly every action in 2002 and
   2003 is tier 3. The judgement ground decides every action whatever its tier, and its
   wording carries the audit. A tier-2 *statistic* under a tier-3 *action* is the common
   shape. A citation is easier to find than a program's default, so an action's tier 2
   usually rests on a paper. An always-on correction with no switch, threshold or record
   field is an action too: the Bérar–Lelann esd inflation, the √y weight fallback.

   **Where three families do not exist.** A rare feature (magnetic, Stephens strain, TOF)
   has one family on disk or none, and rarity is not overfit. Its action is judged on the
   judgement ground alone; where kept, its threshold stays at the measured value with
   `evidence` naming the one family and the table row tiered `3` with grounds that say so,
   and the diagnostic's explanation names the families its threshold was measured on and
   says it is untested beyond them. That wording is kept apart from DESIGN.md § Rules,
   2's *not yet validated*, which means a topic with no published reference; a threshold
   checked against a certified value on one family is validated there and untested
   elsewhere (ruled 2026-10-19). The row is re-tiered when a second and third family arrive. The whole field is in
   scope (DESIGN.md § Why this package exists), so rare features will multiply. Chosen at
   the fourth review over demoting by construction, which would strip every rare feature
   of its one unanimous action; the maintainer may reverse it.

   **A caller pays in tokens and a fit in seconds**, so the default is the one that
   reaches a right answer in the fewest calls (DESIGN.md § Rules, 1). Where a rerun is
   expensive (an hour-long indexing search, a 200-pattern batch, a write into a project's
   history), Rule 1 names four protections of work already done: keep the best attempt,
   seed no successor from a diverged fit, refuse to overwrite history, and record each.
   An action that is one of the four is judged as that protection. Its threshold and its
   ranking criterion are still tiered.

**Answer-invariant efficiency** is a fourth class with no tier. `FIRST_RUNG_FACTOR` was
measured bit-identical on two chains (0 of 1030 and 0 of 392 accepted values moved) with
2.3× margin: the budget truncates only a losing rung while a winning one stays cheaper than
the budget, so the invariance is a measured margin, not a construction, and its own
docstring calls it a bet. Such an item needs an invariance test that also asserts the
margin, and nothing else; the audit classifies it and moves on.

**Demotion** moves an item to the kind of DESIGN.md § Rules, 1 its ambiguity belongs to.
Where the alternatives are enumerable and the data score them, the result is a ranking with
each alternative's evidence and no pick. Otherwise it is the number with its meaning, held
in the package's own output (Rule 3) and never in the skill alone. A code whose verdict
rests on a tier-3 threshold keeps its text and loses the action keyed on it; its `level`
drops to `info` where the code still fires on a tier-1 or tier-2 fact. Where the threshold
decides whether the diagnostic exists at all (`SEQUENTIAL_DISCONTINUITY` at 5× median and
3σ), there is no verdict to keep. The code becomes an `info` record with no threshold: it
fires on every run it applies to and states the statistic for every candidate, largest
first, under a name that asserts no verdict. Its explanation keeps the seat in
`rietx.help`, so the meaning stays where the GUI, `explain()` and the manual already show
it, and the number stays in its record field too (ruled 2026-10-18, over a help section
for result fields, which needs that seat built; GSAS-II and TOPAS print the largest
shift/esd every cycle in the same shape). `Diagnostic.level` has no
"none" value and gets none. The maintainer's breaking appetite is high (every user is in
direct contact), so demotions land now; a removed or renamed code is staged in the release notes.

**A pick on top of a ranking** is allowed in two cases, and the whole ranking travels with
the pick in both. DESIGN.md § Rules, 1 states them since 2026-10-19. The caller called a verb whose job is the pick (`auto_background`,
`IndexingResult.best_or_none`), and no default path calls that verb; the audit checks
the second half, since a pick verb the default path calls is a default. Or the top of the
ranking passes the unanimity gate, a first-kind act on a second-kind ranking, and the
margin that makes it unanimous is a threshold the audit tiers (the maintainer,
2026-10-18).

**A moved golden** is DESIGN.md § Rules, 2's last sentence applied. A demotion that moves a
pinned number has moved it for the right reason only if the new value is no further from the independent reference (a certified cell, a
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
made and its cells are a spend the maintainer approves per session. A poor result does not
hold the demotion back. Rule 1's line does not move with agent performance, so the
demotion lands, and a poor result sends the number's explanation back for work in the same
WP, with one more round on the new wording (ruled 2026-10-19). The harness checks the
explanation and gates nothing. At eight runs it cannot tell seven of eight from five of
eight (Fisher's exact test, p = 0.57).

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
- 24 literal defaults across `PlanSpec`, `StageSpec` and the signatures of the six main
  calls, about ten of which change what the package does (`correlation_guard = 0.98`
  twice, `max_iter`, the Le Bail cycles, `carry_hkl_intensities`, indexing's `validate`
  and `shift_from_pairs`); 347 numeric defaults over the whole package (cascade session).
- 134 acceptance claims in `tests/validation_matrix.py` over 17 suites; 24 carry a tier
  that validates (certificate, spread, prediction) and 21 more agree only with another
  code. Five suites carry neither (both magnetic, Stephens strain, extra peaks, NAC).
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
2004 depends on 2003. 2005, 2006 and 2007 run any time after 2001. 2010 depends on
nothing and stands outside the gate below. 2008 after the audits,
since a demoted code's skill row changes. 2009 last.

**A gate after 2004.** Each audit asks two questions of an item, in this order. First,
should the package make this decision at all: would every competent refiner take it (the
judgement ground, DESIGN.md § Rules, 1)? A decision that fails goes, whatever its
threshold's value. Second, and only for a decision that survives: does its threshold hold
beyond the data it was tuned on (the mechanical ground)? The milestone's premise is that
many of rietx's decisions fail one question or the other. It was measured by provenance
(49 of 127 constants cite a WP measurement, 8 a paper), never by harm: no case on disk
shows a rietx-own decision giving a wrong answer on an unfamiliar dataset, and the one
worked example of a false alarm costs no number. So 2002 to 2004 also test the premise.
Their handovers report how many rows were demoted on each question, and the maintainer
decides then whether 2005 to 2007 run. If the holds and gates mostly pass both, the
remaining value is the guard and the prose, which 2001 and 2009 deliver. WP-2010 is
outside the gate: it audits features against Rule 2, whose premise the gate does not test
and the validation matrix already measures, so it runs whatever the gate decides.

## Acceptance

**These rows are written at the open** (protocol rule 6). Each names a state a later
session can check without asking what was intended. The session that opens each WP
sharpens its own row here.

- **Every verdict and every action has a tier** (2001–2007). The audit table names each
  diagnostic code that carries a verdict, each automatic action and each threshold
  constant with its tier, its evidence and, for tier 3, the two grounds and the approval
  date. Each code and action row also states the kind of ambiguity DESIGN.md § Rules, 1
  assigns it. A meta-test holds the table equal to the tree both ways.
- **No tier-2 or tier-3 action runs by default without its approval** (2002, 2003, 2004).
  Every hold, carry, refit, fence and always-on correction that survives names its
  evidence (the families, or for tier 2 the citation or program), the record field that
  says it fired, and the maintainer's dated approval; every other one is
  demoted to a ranking or a number by its kind, or made opt-in. No default path calls a
  pick verb (§ A pick on top of a ranking).
- **A new heuristic cannot land unaudited** (2001, 2014). A diff that adds a diagnostic code, a
  record field on `StageResult`/`SeriesEntry`/`RefinementResult`, a module-level numeric
  constant in a directory the table's walk declares, a new or changed default at a seat it
  declares, or a `suggestion=` string trips a
  test until the table has its row; the names still at `unaudited` are a committed list
  that only shrinks, so the test needs no git; CI's lint job reads the base and fails a
  name new to the table that arrives at `unaudited`; every top-level module is walked or
  declared out with its reason; and a fresh-context review weighs the case against each
  row, and the case for any action the change removes, whenever the diff touches the table
  or that list. `/wp-handover` dispatches it on a WP branch, `/pr-review` on an outside
  pull request, and `/steward` before a fix to a row is pushed.
- **The goldens hold or improve** (every audit). The acceptance suites pass on the final
  tree; every re-pinned number is recorded with its reference distance, none further
  from its reference than before.
- **The skill is the API, the feedback surface and sourced traps** (2008). Every row
  outside the generated API files is vocabulary, or a trap naming a source outside
  rietx's runs; no row states a verdict the package no longer makes or a rule measured
  on rietx's own data; the total falls and the caps re-land at the new sizes.
- **Every feature names what verifies it and what validates it** (2010). A feature with no
  validating reference is declared not yet validated where a caller reads it, and a test
  holds the feature list equal to the validation matrix and to the help vocabulary.
- **The rulebooks state Rule 1's three outcomes** (2001, 2009): act and record where every
  competent refiner would act, rank where the data can rank, otherwise report the number
  with its meaning; and the rule that rewards a firing code is rewritten.
- **A held-out family moved no number away from its reference** (every audit, checked at
  close). One or two families named at 2002's open and used as evidence by no audit; at
  close the standards' acceptance protocol is run on them and every number with a
  reference is no further from it than at the open. The one row that measures generality
  rather than the audit (fourth review). Named at 2002's open (2026-10-19): the Nd₂Ru₂O₇
  pair (`tests/data/mg090*`, 11-BM X-ray and NCNR BT-1 neutron, a published joint
  refinement), WP-2002 § The batch giving the reason.
- **An agent given the number reaches the answer the verdict gave** (2004, 2008). For each
  demoted class the harness is run once (twice where the explanation is reworked),
  registered first and approved per session, and
  the handover reports the rate beside the v1.3 baseline (seven of eight stopped on a
  stated criterion, none of 86 without one). The milestone promises no rate. It records
  the gap per model generation, so a later session can see it move.

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
- **The north star rewritten as a purpose, the rule beneath it** (2026-10-18, later the
  same day). A review found the text above was a design rule sitting in the purpose's
  slot: mostly subtractive, naming no outcome for a person, and weighted to the week's
  argument. The maintainer stated the beliefs behind the package (agents as the user,
  artisanal and pipeline scale; open and installable through the usual channels; a
  Python API in current practice; the whole field in scope; verification as the
  foundation of agent-written code; feedback that teaches a non-expert to steer). The
  purpose is now one paragraph, "a scientist can trust a Rietveld refinement they did not
  drive by hand", with four rules beneath it. Rule 1 carries the decision line and adds
  the maintainer's distinction between bounded ambiguity, where the data can rank
  enumerable hypotheses and the package ranks them (indexing, structure solution), and
  unbounded ambiguity, where the explanation depends on facts outside the pattern and only
  an agent told them can weigh it (a series). The three tiers stay as the provenance
  audit. Cut on the maintainer's ruling: pipelines and channels as rules (the API must
  let an agent frame an unattended run, and conda-forge is a task), extensibility (a
  feature), MCP from the v2 fence (sandboxed python measured cheaper in tokens than a
  JSON round trip). The founding statement moved to DESIGN.md § History.
- **The record read against the purpose and rules** (2026-10-18, a fresh session after
  `/clear`). The changes that follow from DESIGN.md § Rules as written landed without a
  ruling. The judgement ground is Rule 1's unanimity gate, and a failing action moves to a
  ranking or a number by its kind rather than always to a number. The expensive-rerun
  exception is Rule 1's four protections. *Holds* on the mechanical ground is measured
  against each family's reference (Rule 2), and a one-family threshold is declared not
  yet validated. Four audit WPs (2002 to 2005) lost a skill task that sent a demoted
  verdict's meaning into the skill, which the skill decision below had already reversed.
  The judge asks Rule 4's questions, and no longer whether a caller could see the action.
  The questions the rules left open went to the maintainer, who ruled on four the same
  day. **A pick on top of a ranking** is allowed (§ The rule), "consistent with our
  ethos"; chosen over removing `best_or_none` and `auto_background`'s choice, which would
  cost every caller one more decision for an answer the ranking already shows. **Rule 1's
  three outcomes replace the preference order** "record field, then code, then action"
  in the rulebooks (2001, 2009): the order pointed a session away from acting where
  every competent refiner would act, which Rule 1's token clause says costs more than
  the action. **Rule 2 became verification and validation** in the field's sense (Roache
  1998; Oberkampf & Roy 2010), and a topic without a reference is *not yet validated*,
  since `provisional` already means an API that may change (PEP 411). A reference code's
  result on the same data verifies; it does not validate. **The milestone was renamed**
  from "pay for established heuristics, leave the reasoning to the caller", which
  restated the superseded first north star and contradicted Rule 1's first two kinds.
  Three more rulings followed. **A code whose threshold decided its existence becomes an
  `info` record with no threshold** (§ Demotion), chosen over a help section for result
  fields (84 entries over four result types, and a GUI seat to build), because the
  record keeps the explanation where readers already find it. **Defaults are walked at
  declared seats** (WP-2001 § The seams), about ten that decide behaviour among 347,
  chosen over walking all 347 and over leaving defaults to the reviewer agent. **WP-2010
  audits features against Rule 2**, inside this milestone and outside the gate after
  2004 ("useful"); a separate later milestone would lose only time, and the maintainer
  may move it. The gate itself was restated as two questions in order (should the
  package decide at all, then does the threshold hold), after the maintainer read the
  earlier wording as asking only the second.
- **A gate after 2004, and three families is not a demotion by itself.** The premise is a
  conviction measured by provenance, so the first three audits test it and the maintainer
  re-decides 2005–2007 on their counts. A rare feature with one family keeps its unanimous
  action, its threshold declared untested beyond its one family (§ The rule). Both from the fourth
  review; the second is the filing session's choice and reversible.
- **The skill carries vocabulary and sourced traps, nothing prescriptive** (2026-10-18,
  the maintainer). Its role under the north star is to save tokens: an agent that knows
  the API and the feedback surface makes the right first call. A rule whose only evidence
  is a run on rietx's own test data is the code's overfit in prose form and is cut from
  the skill; a trap stays only with a source
  outside rietx's runs (the literature, a reference code's documented behaviour) and only
  where a strong agent would not bring it to mind. Chosen over the second review's
  position that a demoted verdict's meaning moves into the skill, which would have made
  the skill the new home of the heuristics the audits remove. The maintainer expects the
  skill to shrink toward its traps as the manual improves; no agent needs a GitHub skill.
  Three conditions accepted with it: agents do not browse a manual, so the first act is a
  measured baseline (skill against manual-only); the manual must be reachable from inside
  the package before a class of rows is cut, and a slower task is repaired by a pointer
  and never by a row; the vocabulary is generated from the live surface, since training
  corpora are years late and version-blind. The skill's structure (one reference per
  task shape) is on the table, ruled in 2008's batch on the token count per call.
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
- **The milestone re-read against DESIGN.md** (2026-10-19, a fresh session after
  `/clear`). Thirteen changes followed from the rules as written and landed without a
  ruling (commit ee8a9181 lists them). The maintainer ruled two more. **DESIGN.md states
  the pick exception**, in Rule 1's second kind and Rule 4's test, so a session reading
  DESIGN.md alone no longer flags `best_or_none`. Rule 4's skill-row test also admits a
  sourced practice, as Rule 3 already did. Chosen over leaving the exception in this
  record alone. **A threshold measured on fewer than three families is declared untested
  beyond them**, and *not yet validated* stays Rule 2's term for a topic with no
  reference. Chosen over one phrase for both, which would let a reader take "checked on
  one dataset" for "no reference exists". **A poor agent result reworks the explanation
  and does not hold a demotion back** (§ The rule). Chosen over a block until agents
  recover, which would keep a verdict that failed its tests steering agents, on a harness
  too small to show the recovery. **Every action faces the unanimity question whatever its
  tier** (§ The rule, tier 2), since Rule 1 makes no exception by source. Chosen over
  keeping a tier-2 action on its citation alone, which would have passed the Bérar–Lelann
  esd inflation unexamined although GSAS-II does not apply it. The cost measured at the
  ruling: two or three of the ten behavioural defaults cite a paper or a program, plus the
  always-on corrections 2002 now lists.
- **The guard reaches every path into main** (2026-10-20, a planning session; WP-2014).
  The maintainer asked whether the tooling could now carry the rule forward. Measured: the
  judge ran only at a WP's handover, while twelve open outside PRs had added 38 rows and
  26 allow-list names with no judge, and `solve/` sat outside the walk. Three rulings.
  **Outside PRs are tiered at review before they merge**; their author is informed and
  agrees with the demotions. **WP-2007 owns `solve/`.** **The judge argues both sides
  without manufacturing fairness**: it also asks, of an action a branch removes or leaves
  to the caller, whether every competent refiner would act anyway and what leaving it
  costs, and a side with no evidence reads `none found` in one line. In the maintainer's
  words, "I don't want a system in which a weak case given representation seems stronger
  than it is." Chosen over the judge drafting only the case against, which made deciding
  less the cheap path for an author; a WP-2002 lane's over-reach on the peak-position
  bounds (11-BM NAC's cell 5129 ppm off against 1117 ppm) is the measured cost. The
  priority rubric stays with 2009.

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
stated the position now in DESIGN.md § Rules, 1 (written that day as a § North star,
rewritten the same evening; see below). What moved:

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
