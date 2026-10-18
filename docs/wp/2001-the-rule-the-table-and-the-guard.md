# WP-2001 — The rule, the audit table and the guard

Milestone: generality · Status: 🔄 2026-10-18 — the milestone, the rule and the nine WPs filed; the table and the guard not started
Track: The registry and the guard
Depends on: —
Priority: P2 2026-10-18 — the scoping WP the other eight wait on; nothing blocks it

## Goal

The three-tier rule is written where the package can hold itself to it: an audit table in
its own module, keyed by name, that every later audit fills; a tripwire test that fails a
diff adding a heuristic without a row; and a handover step that dispatches a fresh-context
reviewer to draft the case against each new row. The root CLAUDE.md's rule that rewards a
firing code is rewritten to prefer a record field.

## Context

The milestone record, [`../milestones/generality.md`](../milestones/generality.md) § The
rule, is the one authority for the tiers, the two grounds a tier-3 item is kept on, the
answer-invariant class, what demotion means and how a moved golden is judged. Restated in
one paragraph here so this file is self-contained; sharpen the record, never this copy.

Three tiers, each part of a heuristic tiered separately (statistic, threshold, action):
(1) physics or arithmetic, kept; (2) a citation that validated it or the same action taken
by default in GSAS-II, FullProf or TOPAS, kept and named; (3) rietx's own, demoted unless it
holds on three unrelated dataset families (by lab, instrument and material) *and* answers
yes to both halves of "could the caller see this from what rietx returns, and does missing
it cost a wrong number?", approved by the maintainer in a batch. A threshold derived from
another constant inherits its tier. An item that cannot change an accepted value needs an
invariance test and no tier.

**The seams.**

- `rietx.help.DIAGNOSTIC_HELP` (`src/rietx/help.py`, WP-1985) holds 253 `HelpEntry` rows,
  one per `Diagnostic` code, held equal to the raise sites both ways by `tests/test_help.py`
  (`docs/reference_pages.diagnostic_index()`). **Do not add audit fields to `HelpEntry`**:
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
  has 76 more, io ~30. The table stores each constant's **value** beside its name, so a
  retune fails the meta-test and reopens the audit. A row's name is checked by import.
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
The tripwire is a test over the branch diff against `origin/main` (and, so it also runs
where there is no diff, over the tree against the table) that fires on: a new `Diagnostic`
code; a new field on `StageResult`, `SeriesEntry` or `RefinementResult`; a new or retuned
module-level numeric constant under `src/rietx`; a new `suggestion=` string. The judge is a
fresh-context `generality-review` agent the handover dispatches on a hit, which answers per
item, quoting the WP's own evidence lines: what does this decide that the caller did not ask
for; deleted, what does a caller see and when could they act; which tier, with its source;
how many unrelated families, counted by lab, instrument and material; why is it not a record
field plus a suggestion. The agent drafts the case *against*, beside the author's two-ground
answer, because a row written by the author alone is self-certification and a batch
approval tends to rubber-stamp. **What it will miss, stated in the module docstring**:
inline literals (about 30 in `refine.py`, `< 0.7` at the plate-thickness test, `>= 2.0`
further down), schema-field defaults such as `intermediate_ftol`, orderings and fallback
chains, and heuristics written as skill prose (2008's half).

**The generator rule** (the second review's biggest finding). Root CLAUDE.md's "A new
correction ships with a record field or a diagnostic stating what it changed" and the P1
rubric's "a wrong number that nothing flags outranks one that raises" both reward adding a
firing code. The rewrite states a preference order: a record field first, a diagnostic
second, an action last and only with a tier; and it lands here, before the audits, so they
follow it. The P1 rubric is 2009's.

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
- [ ] The table module (`src/rietx/_audit.py` or beside `help.py`; name it in the handover):
      a frozen row type with `name`, `kind` (`code` | `action` | `constant`), `tier`
      (`1` | `2` | `3` | `invariant` | `unaudited`), `evidence` (a citation, a program and
      what it does by default, or the families), `grounds` (the two-ground answer, tier 3
      only), `approved` (a date, tier 3 only), `value` (constants only). Every existing
      code from `DIAGNOSTIC_HELP`, every record field named above and every constant the
      AST walk finds, entered at `unaudited`.
- [ ] The meta-test (`tests/test_audit_table.py`): code rows equal to `DIAGNOSTIC_HELP`'s
      keys both ways; every action row's record field exists on its schema; every constant
      row imports and its stored value equals the live one; a tier-3 row carries `grounds`
      and `approved`; a `unaudited` row is allowed only for a name that exists on
      `origin/main`'s table (the growth guard; read the base table through `git show`, and
      skip with a reason where there is no git).
- [ ] The tripwire's second half: the walk that produces the constant list is a function
      the test and the table share (`_audit.constants()`), so the inventory cannot drift
      from the guard; the same for record fields (`dataclasses.fields` /
      `model_fields` over the three schemas) and `suggestion=` strings (an AST walk for the
      keyword).
- [ ] The `generality-review` agent (`.claude/agents/generality-review.md`): read-only,
      the five questions above, output a table per item with the case against, written
      for the maintainer in plain words (root `~/.claude/CLAUDE.md`'s register). The
      handover's step 6 gains the dispatch: on a tripwire hit, or on any diff touching a
      row, run it and paste its table into the handover entry under *Generality*.
- [ ] `docs/wp/TEMPLATE.md`: one line in the Context guidance, "a rule this WP adds is
      physics, named practice, or new judgement; say which, and for the third name the
      families it was measured on".
- [ ] Root CLAUDE.md: rewrite the "new correction ships with a record field or a
      diagnostic" invariant to the preference order, one clause pointing at the record;
      a clause under § Conventions naming the table and the tripwire. Count the lines
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
`code="…"` strings in `src/rietx`, 253 of them in `DIAGNOSTIC_HELP`; by subsystem io 89,
`refine.py` 61, indexing 48, gui 27, crystallography 20, sequential 12, report 5, multi 5;
70 not named in the skill; 6 with no test, ~20 touched by one test file. 127 module-level
numeric constants in `report/`, `strategy/`, `optimize/statistics.py`, `refine.py`,
`sequential.py` by AST (the session's own grep said 117; the reviewer's AST count is the
one to carry), about 8 citing a paper in the comment block, 3 derived, ~49 citing a WP.
Skill 61 000 words, 134 tagged rows. 3 of 193 top-level exports unused outside tests
(`IndexingEvidence`, `CaveatEvidence`, `CandidateEvidence`). Public surface 2 238 entries.

*Decisions* are in the record § Decisions. The one the session took itself and the
maintainer should know it can reverse: the audit table is a separate module rather than
fields on `HelpEntry`, on the reviewer's finding that `HelpEntry` is a GUI type.

*Gotchas.* The worktree guard refuses a Bash command containing the word "eval" anywhere
(it reads it as a shell `eval`); `ls tests/ev*` works. The milestone section's heading
must match the table row's anchor exactly, or `test_docs_consistency.py` fails on the link.

*Next.* The table module and its meta-test, then the agent and the handover step, then
the CLAUDE.md rewrite, then the cross-project lesson. The maintainer intends a further
review round on this filing after `/clear`; its findings go into the record § The two
reviews as a third entry and into whichever WP they touch.

- **2026-10-18** — created.
