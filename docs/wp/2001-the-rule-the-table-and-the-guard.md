# WP-2001 — The rule, the audit table and the guard

Milestone: generality · Status: 🔄 2026-10-19 — the milestone, the rule and ten WPs filed and read against DESIGN.md's rules; the table and the guard not started
Track: The registry and the guard
Depends on: —
Priority: P2 2026-10-18 — the scoping WP the other eight wait on; nothing blocks it

## Goal

The three-tier rule is written where the package can hold itself to it: an audit table in
its own module, keyed by name, that every later audit fills; a tripwire test that fails a
diff adding a heuristic without a row; and a handover step that dispatches a fresh-context
reviewer to draft the case against each new row. The root CLAUDE.md's rule that rewards a
firing code is rewritten to DESIGN.md § Rules, 1's three outcomes.

## Context

The milestone record, [`../milestones/generality.md`](../milestones/generality.md) § The
rule, is the one authority for the tiers, the two grounds a tier-3 item is kept on, the
answer-invariant class, what demotion means and how a moved golden is judged. Restated in
one paragraph here so this file is self-contained; sharpen the record, never this copy.

Three tiers, each part of a heuristic tiered separately (statistic, threshold, action):
(1) physics or arithmetic, kept; (2) a citation that validated it or the same action taken
by default in GSAS-II, FullProf or TOPAS, kept and named; (3) rietx's own, demoted unless it
holds on three unrelated dataset families (by lab, instrument and material) *and* every
competent refiner, shown the statistic, would take the same action (DESIGN.md § Rules, 1's
unanimity gate); a named dissenter demotes it to a ranking where the data can rank the
alternatives and to the number with its meaning otherwise, approved by the maintainer in a
batch. The
inheritance rule, the answer-invariant class, the one-family clause and the moved-golden
rule are the record's; this copy carries no more than that sentence (third review: the
first copy inverted the polarity; fourth: visibility gave way to judgement).

**The seams.**

- `rietx.help.DIAGNOSTIC_HELP` (`src/rietx/help.py`, WP-1985) holds 256 `HelpEntry` rows,
  one per `Diagnostic` code, held equal to the raise sites both ways by `tests/test_help.py`
  (`docs/reference_pages.diagnostic_index()`). Build the inventory from that index, never
  from a grep for `code="…"`: seven codes are raised through a name and have no literal. **Do not add audit fields to `HelpEntry`**:
  the class is shared by every help arm and serialised to `/api/help`, so a field there
  moves `gui/src/lib/help.ts`, the vitest table and the committed dist. The audit table is
  its own module, maintainer-facing, and a meta-test holds its code rows equal to
  `DIAGNOSTIC_HELP`'s keys both ways.
- Automatic actions have no code. The house rule "a correction ships with a record field"
  is the inventory: `StageResult` (`schemas/results.py`) fields `held`, `held_reach`,
  `scale_b_held`, `released`, `moment_flat_axes`, `moment_turned`, `blocked_by_hold`,
  `seeded`; `SeriesEntry` (`schemas/sequential.py`) `rung`, `reseeded`, `rwp_fence`. The
  table keys an action on the record field that reports it.
- Threshold constants are module-level numbers. 127 in `report/`, `strategy/`,
  `optimize/statistics.py`, `refine.py`, `sequential.py` (AST walk, 2026-10-18); indexing
  has 76 more, io ~30. **The table's walk covers a declared directory list**, held as data
  in the table module (`_audit.WALKED`): `refine.py`, `sequential.py`, `multi.py`,
  `strategy/`, `report/`, `optimize/`, `background/`, `indexing/`, `crystallography/`, and
  the readers' repair code under `io/`. The second review found `background/`,
  `optimize/lm.py` and `crystallography/` in neither the open's count nor any audit WP's
  scope, so they are on the list; the third review ran the walk over all of `src/rietx` and
  found 619 constants, the surplus over the seams being byte offsets in file readers, pixel
  sizes in the 3D viewer and schema defaults, so the list is not the whole package. A
  directory outside the list is out of scope by declaration, and the module docstring says
  so. Every constant the walk finds opens at `unaudited` and belongs to an audit WP **by
  directory** (fourth review; 2005's partition covers codes only): `refine.py`,
  `strategy/`, `background/` and every `optimize/` constant that is not report-facing to
  2002; `sequential.py` and `multi.py` to 2003; `report/` and the report-facing rows of
  `optimize/statistics.py` to 2004; `io/` and `crystallography/` to 2006; `indexing/` to
  2007. A file the walk reaches that none of those names is this WP's to assign before
  it closes. The table stores each constant's
  **value** beside its name, so a retune fails the meta-test and reopens the audit. A
  row's name is checked by import.
- Defaults that decide behaviour are written into signatures and schema fields, where a
  walk over module-level assignments cannot see them: `correlation_guard: float = 0.98`
  in `PlanSpec`, and again as a literal in `run_stage`. Measured 2026-10-18: 24 literal
  defaults across `PlanSpec`, `StageSpec` and the signatures of `fit`, `refine`,
  `run_stage`, `refine_sequential`, `index_pattern` and `auto_background`. About ten
  change what the package does (`correlation_guard`, `max_iter`, `lebail_cycles`,
  `lebail_passes`, `carry_hkl_intensities`, `validate`, `shift_from_pairs`,
  `temperature`); the rest are off states and counters. The whole package holds 347
  numeric defaults, mostly plot sizes, starting values and search ranges. So the table
  walks a declared list of seats (`_audit.DEFAULT_SEATS`: those classes and functions,
  plus `Source`, whose `dispersion` default turned a correction on in v1.0), as it walks a
  declared list of directories, and a default outside the list is out of scope by
  declaration (ruled 2026-10-18, over walking all 347, which would reopen an audit on
  every cosmetic edit). A default row belongs to the audit that owns the code it feeds:
  the plan schemas, `fit`, `refine`, `run_stage`, `auto_background` and `Source` to 2002,
  `refine_sequential` to 2003, `index_pattern` to 2007.
- `Diagnostic.level` (`schemas/common.py`) is a required `Literal["info", "warning",
  "error"]`; demotion uses `info`, never a new member.
- `/wp-handover` (`.claude/commands/wp-handover.md`) step 6 runs `/code-review high --fix`
  on the branch; step 7 is a checklist of named triggers against what the session added.
  `/pr-review` dispatches the `pr-conformance` agent (`.claude/agents/`) on outside PRs
  only. WP branches, where every overfit here was born, get no fresh-context read today.
- `docs/wp/TEMPLATE.md` is where a WP is filed from one dataset. One line there asks the
  origin question.
- `~/Code/claude-config/workflow/LESSONS.md` carries rules between the maintainer's
  projects through `/workflow-sync`; a lesson travels as a rule, worded per project, and
  names its exemplar.

**The recurrence design, decided 2026-10-18.** A tripwire and a judge, not prose alone.
The tripwire is a test over the tree against the table that fires on: a new `Diagnostic`
code; a new field on `StageResult`, `SeriesEntry` or `RefinementResult`; a new or retuned
module-level numeric constant in a walked directory; a new or changed default at a
declared seat; a new `suggestion=` string. It reads
no git (third review): CI checks out at depth 2 with no `origin/main` ref and a local
worktree's is days stale, so a test comparing against the base table through `git show`
skips exactly where it gates a merge. Instead the names allowed at `unaudited` are a
committed list in the table module (`_audit.UNAUDITED_BASELINE`), written once at the open
and allowed only to shrink; a row at `unaudited` whose name is not on it fails, and a name
in the tree with no row fails. The handover dispatches the judge whenever the diff touches
the table module or that list, so an author who adds a name to the baseline has made a
visible edit on a file whose name says what it is. The dispatch hangs on **step 7**, the
checklist every branch runs, and not on step 6, which a prose-only branch skips (fourth
review): a heuristic added as skill prose is already invisible to the tripwire, and on
step 6 it would have had no judge either. The judge is a
fresh-context `generality-review` agent the handover dispatches on a hit, which answers
DESIGN.md § Rules, 4's test for the kind of change per item, quoting the WP's own evidence
lines: what does this decide that the caller did not ask for, and which of Rule 1's three
kinds is its ambiguity; for the first kind, which competent refiner would act otherwise and
in what situation; for the second, does it rank with evidence and pick only in Rule 1's
two cases; for the
third, does it report the number and stop; which tier, with its source; how many unrelated
families, counted by lab, instrument and material, and the reference each was measured
against (Rule 2); which record field says it fired. An earlier question, "deleted, what
does a caller see and when could they act", was the visibility ground the fourth review
retired; it survived here until the cascade from the rules removed it. The agent
drafts the case *against*, beside the author's two-ground
answer, because a row written by the author alone is self-certification and a batch
approval tends to rubber-stamp. **What it will miss, stated in the module docstring**:
inline literals (about 30 in `refine.py`, `< 0.7` at the plate-thickness test, `>= 2.0`
further down), defaults outside `DEFAULT_SEATS`, orderings and fallback chains, and heuristics written as skill prose (2008's half).

**The generator rule** (the second review's biggest finding). Root CLAUDE.md's "A new
correction ships with a record field or a diagnostic stating what it changed" and the P1
rubric's "a wrong number that nothing flags outranks one that raises" both reward adding a
firing code. The rewrite states Rule 1's three outcomes in one clause: where every
competent refiner would act, act and record it in a field; where the data can rank the
alternatives, rank them with evidence; otherwise report the number with its meaning. It
keeps "never an Rwp comparison as its evidence" and points at DESIGN.md § Rules, 4. It
lands here, before the audits, so they follow it. The P1 rubric is 2009's. The second
review had worded the rewrite as a flat order (record field, then diagnostic, then
action); the maintainer replaced it on 2026-10-18, because the order points a session away
from acting where Rule 1's first kind says act.

### Inherited

(none at filing)

## Non-goals

- Auditing any row. The table opens with every existing code, action and constant at
  `unaudited`; 2002–2007 fill it. The growth guard refuses only a **new** item at
  `unaudited`.
- The P1 rubric in `TEMPLATE.md` and the findings-as-rules pass over the CLAUDE.md files:
  2009.
- The skill: 2008. The tripwire does not read `docs/skill/`.
- A `Diagnostic.level` member for "no verdict". Demotion is `info` or removal.

## Tasks

- [x] The milestone record (`docs/milestones/generality.md`), its ROADMAP row and section,
      the WP block 20xx and this file plus 2002–2009; ROADMAP's cap 589 → 614 with its
      diary line. (2026-10-18, the filing session.)
- [ ] The table module `src/rietx/_audit.py` (named here, since 2002–2009, the record and
      the handover's dispatch all key on `_audit`):
      a frozen row type with `name`, `kind` (`code` | `action` | `constant` | `default`),
      `tier`
      (`1` | `2` | `3` | `invariant` | `caller` | `unaudited`; `caller` is an action only
      the caller turns on, an opt-in flag or a pick verb no default path calls, since
      DESIGN.md § Rules, 1 governs what the package decides alone), `ambiguity` (`1` | `2` | `3`, DESIGN.md
      § Rules, 1's kinds; code and action rows only, where Rule 4 asks for it to be
      stated), `evidence` (a citation, a program and what it does by default, or the
      families with their references), `grounds` (the two-ground answer, tier 3 only),
      `approved` (a date, tier 3 only), `value` (constants and defaults only). Every
      existing code from `DIAGNOSTIC_HELP`, every record field named above, every constant
      the AST walk finds over `WALKED` and every default at `DEFAULT_SEATS`, entered at
      `unaudited`; `UNAUDITED_BASELINE` the
      sorted list of those names, written once here.
- [ ] The meta-test (`tests/test_audit_table.py`): code rows equal to `DIAGNOSTIC_HELP`'s
      keys both ways; every action row's record field exists on its schema; every constant
      and default row imports and its stored value equals the live one; a tier-3 row carries `grounds`
      and `approved`; every `unaudited` row's name is on `UNAUDITED_BASELINE` (the growth
      guard; no git); every name on the baseline still has a row, so the list shrinks as
      rows are audited and never grows.
- [ ] `/wp-handover`'s dispatch condition for the judge, on step 7: the tripwire fired, or
      the diff touches the table module or the baseline.
- [ ] The tripwire's second half: the walk that produces the constant list is a function
      the test and the table share (`_audit.constants()`), so the inventory cannot drift
      from the guard; the same for record fields (`dataclasses.fields` /
      `model_fields` over the three schemas), defaults (`_audit.defaults()`, over
      `DEFAULT_SEATS`' fields and signatures) and `suggestion=` strings (an AST walk for the
      keyword).
- [ ] `correlation_guard`'s two literal copies (`PlanSpec`, `run_stage`) become one named
      constant, bit-identical before and after.
- [ ] The `generality-review` agent (`.claude/agents/generality-review.md`): read-only,
      the Rule 4 questions above, output a table per item with the case against, written
      for the maintainer in plain words (root `~/.claude/CLAUDE.md`'s register). The
      handover's step 7 gains the dispatch: on a tripwire hit, or on any diff touching a
      row, run it and paste its table into the handover entry under *Generality*.
- [ ] `docs/wp/TEMPLATE.md`: one line in the Context guidance, "a rule this WP adds is
      physics, named practice, or new judgement; say which, and for the third name the
      families it was measured on and their references; a default or automatic action
      also names its kind under DESIGN.md § Rules, 1; a new topic names its reference
      (dataset, published number, tolerance) before any code is written, or says none
      exists and that it ships not yet validated" (Rule 4's test for a new topic, whose
      only other seat is 2010's check at landing).
- [ ] Root CLAUDE.md: rewrite the "new correction ships with a record field or a
      diagnostic" invariant to Rule 1's three outcomes, one clause pointing at DESIGN.md
      § Rules;
      a clause under § Invariants naming the table and the tripwire, since DESIGN.md
      § Rules, 4 places the mechanisms that enforce its tests there. Count the lines
      against the cap (`tests/test_docs_consistency.py`) and bump with a diary line if
      needed.
- [ ] `claude-config/workflow/LESSONS.md`: the lesson "a heuristic enters with its tier or
      not at all", with rietx's table and agent as the exemplar, through `/workflow-sync
      harvest`. This is a separate repository and a separate commit; the handover names it.
- [ ] Tests + the fast selection count moved by exactly the tests added.
- [ ] Skill: none. The table is maintainer-facing; an agent driving rietx reads the
      diagnostic's `explanation`, which 1985 built and this WP does not change.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

Plus, by hand once: add a throwaway constant to `src/rietx/refine.py` on a scratch branch
and confirm `test_audit_table.py` goes red naming it; remove it. A guard that was never
seen to fail is a guard that may go quiet (`tests/CLAUDE.md` § Guards that go quiet).

## References

- `docs/milestones/generality.md` § The rule, § Decisions, § The two reviews.
- WP-1985 (the per-code explanations and `DIAGNOSTIC_HELP`); WP-1076 (a declared name is a
  claim); WP-1007 (`capabilities()` and `_SURFACE_FLAGS`, the registry-plus-meta-test shape
  this copies).
- Kass, R. E. & Raftery, A. E. (1995). J. Am. Stat. Assoc. 90, 773–795 (the ΔBIC bands the
  record cites as the worked tier-2 example); Schwarz, G. (1978). Ann. Stat. 6, 461–464.

## Handover log

### 2026-10-19 — the milestone read against DESIGN.md's purpose and rules

The session before this one rewrote DESIGN.md's north star as a purpose with four rules.
This session carried those rules down into the milestone and its WP files, and brought the
maintainer the questions the rules left open. Each audit now asks two questions of a
decision, in order: should rietx make it at all, and only then, does its threshold hold
beyond the data it was tuned on. A decision that fails moves to a ranking where the data
can rank the alternatives, and otherwise to the number with its meaning. Rule 2 now
separates verification from validation, and a tenth WP (2010) gives every feature its
state under both: 24 of 134 acceptance claims validate, and magnetic refinement has no
validating reference at all. Nothing in the package changed. The work ran late on
2026-10-18; the commits carry that date.

*Done.* Three commits on top of the previous session's purpose rewrite (9dcb29c4, pushed
here). 7b7ed875 made the changes that follow from the rules as written: the judgement
ground is Rule 1's unanimity gate; the expensive-rerun exception is Rule 1's four
protections; *holds* on the mechanical ground is measured against each family's
reference; the table gains an `ambiguity` field; the judge asks Rule 4's questions and
lost the visibility question the fourth review had retired; 2002 to 2005 lost a skill
task that contradicted the skill decision. 59eb477c and 32d63ee3 landed seven rulings,
each in the record § Decisions with its reason and alternative. (1) A verb whose job is
the pick may pick on a ranking while no default path calls it, and a top candidate passing
the unanimity gate may be picked; the ranking travels with the pick. (2) WP-2010 filed,
inside the milestone and outside the gate. (3) Rule 1's three outcomes replace the flat
order "record field, code, action" in the rulebooks (2001, 2009, and 1341's note). (4) A
code whose threshold decided its existence becomes an `info` record with no threshold,
keeping its explanation (2003's discontinuity code first). (5) Defaults are walked at a
declared list of seats. (6) Rule 2 is verification and validation in the field's sense,
and a feature without a reference is *not yet validated*; *provisional* keeps its API
meaning. (7) The milestone renamed to "every decision rietx makes holds beyond the data
it was tuned on". Under (6) this session placed a reference code's result on the same data
under verification, as the field does; the maintainer was told and did not object. The
gate after 2004 was restated as the two questions after the maintainer read it as asking
only the second. Forward notes: 1341's note reworded to Rule 1's outcomes; 1327 told that
2010 will label magnetic refinement not yet validated, and what would lift it.

*Measured* (darwin arm64, `[dev]`). `tests/validation_matrix.py`: 134 claims over 17
suites; 24 carry a validating tier, 21 more agree only with another code; five suites
carry neither (both magnetic, Stephens strain, extra peaks, NAC) and three cross-code only
(fluorapatite, LaB6–cBN, Powderline). Defaults: 24 literal defaults across `PlanSpec`,
`StageSpec` and the six main calls, about ten behavioural; 347 numeric defaults
package-wide (166 class fields, 181 public signatures). The four result types hold 84
fields (`RefinementResult` 33, `StageResult` 20, `SeriesResult` 12, `SeriesEntry` 19), and
`rietx.help` has no section for them. `auto_background` and `best_or_none` have no caller
in `refine.py` or `strategy/`. No test added, so no count moved.

*Review.* This session touched only `docs/`, so `/code-review` was skipped; the branch's
one `.py` change (five lines of `tests/test_docs_consistency.py`) was reviewed in the
opening session's step 6.

*Gotchas.* The worktree guard refuses a heredoc'd python script and a shell loop over git
refs; write the script to the scratchpad and run it as one command. Importing
`tests.validation_matrix` from a scratchpad script needs `PYTHONPATH=.`. A new WP file
must be `git add`ed before `test_docs_consistency.py` runs, or
`test_no_planning_doc_links_something_gitignored` fails on the untracked link.

*Next.* This WP's second task, unchanged: `_audit.py` with the `ambiguity` field, the
`default` kind and `DEFAULT_SEATS`, then its meta-test, the judge and its handover step,
the root CLAUDE.md rewrite to Rule 1's outcomes, and the cross-project lesson. WP-2010
depends on nothing and can run in another session at any time. Whether PR #1044 merges
first is the maintainer's call; the later tasks need nothing from it beyond the files.

### 2026-10-18 — the milestone opened and nine WPs filed

The maintainer raised a concern rather than a defect: that many of rietx's features are
fitted to the test cases that produced them, that there are too many diagnostic codes, and
that the package decides things the caller should. This session measured the concern,
agreed a sorting rule with the maintainer, had the plan reviewed twice, and filed the
milestone and its nine WPs. Nothing in the package changed. The next action is this WP's
second task: the table module, opened with every row at `unaudited`.

*Done.* `docs/milestones/generality.md` (the rule, the measurements, the order, six
acceptance rows, the dated decisions, the two reviews); ROADMAP's row, section and three
tracks, the Current focus line; the cap 589 → 614; WP files 2001–2009; the index
regenerated.

*Measured* (darwin arm64, this worktree at `origin/main` 049bc823, `[dev]` venv): 276
distinct `code="…"` literals in `src/rietx`, 256 codes in `DIAGNOSTIC_HELP` (7 of them
raised through a name, no literal; the filing first wrote 253 and 89 for io from the
literal grep, corrected at review); by subsystem io 90, `refine.py` 61, indexing 48, gui
27, crystallography 20, sequential 12, report 5, multi 5, and 9 in `background/select.py`,
`optimize/qpa.py`, `schemas/migrate.py`, `strategy/magnetic.py`,
`strategy/fraction_profile.py`; 70 not named in the skill; 6 with no test, ~20 touched by
one test file. 127 module-level
numeric constants in `report/`, `strategy/`, `optimize/statistics.py`, `refine.py`,
`sequential.py` by AST (the session's own grep said 117; the reviewer's AST count is the
one to carry), about 8 citing a paper in the comment block, 3 derived, ~49 citing a WP.
Skill 61 000 words, 130 tagged lines (145 tags). 3 of 193 top-level exports unused outside tests
(`IndexingEvidence`, `CaveatEvidence`, `CandidateEvidence`). Public surface 2 238 entries.

*Decisions* are in the record § Decisions. The one the session took itself and the
maintainer should know it can reverse: the audit table is a separate module rather than
fields on `HelpEntry`, on the reviewer's finding that `HelpEntry` is a GUI type.

*Review* (`/code-review high --fix`, handover step 6): ten findings, eight applied by the
pass in the working tree and committed here. The counts were off (256 codes in
`DIAGNOSTIC_HELP`, not 253; io raises 90 literals plus five by name; seven codes have no
`code="…"` literal, so the inventory is built from `diagnostic_index()`, never a grep;
130 tagged skill lines, not 134); nine codes and five constants had no audit WP (now 2002's
and 2005's, the partition stated in 2005 § Non-goals); 1327 is in flight, not closed, so
2002 merges main before touching the moment hold; 2004's acceptance lacked
`test_fitreport_layers.py`; `CIF_ANGLE_CORRECT_MAX_DEG` lives in `crystallography/`, not
`io/`; `process.md`'s caps diary was two ROADMAP bumps stale. Of the two left: the
tripwire's walk was specified over five files and must cover all of `src/rietx` (fixed in
Context above, by this session); ROADMAP landing at its cap with no headroom is deliberate
and has a precedent at 588, so the next line added there bumps it with its own diary line.
The second Opus review's findings are in the record § The two reviews.

*Gotchas.* The worktree guard refuses a Bash command containing the word "eval" anywhere
(it reads it as a shell `eval`); `ls tests/ev*` works. The milestone section's heading
must match the table row's anchor exactly, or `test_docs_consistency.py` fails on the link.

*Next.* The table module and its meta-test, then the agent and the handover step, then
the CLAUDE.md rewrite, then the cross-project lesson.

*Third review, same day, a fresh session after `/clear`.* Twelve changes, all approved by
the maintainer and listed in the record § The third review. The four that move this WP:
the restatement above now carries the reasoning ground's polarity and no more of the rule
than one sentence; the constant walk covers `_audit.WALKED`, a declared directory list,
after the walk over all of `src/rietx` found 619 constants against the seams' 233; the
growth guard is `_audit.UNAUDITED_BASELINE`, a committed list that only shrinks, in place
of a `git show` of `origin/main` that CI's depth-2 checkout cannot make; and the handover
dispatches the judge on any diff touching the table or the baseline. The record also
gained a clause for a golden with no independent reference and tightened the inheritance
rule to derivations with no free factor.

*Fourth review, same day, a fresh session reading the plan's reasoning.* The maintainer
confirmed that the second ground is judgement (would every competent refiner take this
action on seeing this number?) and that visibility decided nothing, since any action can
be reported as its statistic; the north star went into DESIGN.md § Why this package
exists. The record § The fourth review lists the rest. In this file: the restatement, the
constants partition by directory, the judge on step 7, the module named `_audit`.

- **2026-10-18** — created.
