# WP-2014 — A heuristic meets the judge on every path into main

Milestone: generality · Status: 🔄 2026-10-20 — claimed by @yue-here
Track: The registry and the guard
Depends on: 2001
Priority: P2 2026-10-20 — the guard the open milestone was opened for; twelve outside PRs wait on its review step before they merge

## Goal

Every path by which a new or changed heuristic reaches main passes the generality judge.
That means an outside PR as well as a WP branch, a directory the audit table did not
watch as well as one it did, and a fix pushed after the handover. The judge also weighs
the case for an action that a branch removes or leaves to the caller, and reports a side
with no evidence as having none.

## Context

The rule is [generality § The rule](../milestones/generality.md#the-rule); the kinds of
ambiguity are [DESIGN § Rules](../DESIGN.md#rules), 1. WP-2001 built the guard:
`src/rietx/_audit.py` (one row per heuristic, with its tier), `tests/test_audit_table.py`
(the tripwire), `_audit.UNAUDITED_BASELINE` (the names allowed to stay at `unaudited`,
meant only to shrink) and the `generality-review` agent (`.claude/agents/`), which
`/wp-handover` step 7 dispatches on a branch that touches the table. The judge's first
real run was WP-2002's, on 242 rows (its branch's handover, 2026-10-20): five `fails` and
about eleven `weak`. Two of the fails were rows their author had marked `caller` that in
fact ran by default; one was an agent-skill instruction that made a verb a default path.

**What the filing session measured** (2026-10-20, `origin/main` at 5ecd4d70; re-measured
by an independent Opus review that parsed each PR head's table with `ast`):

- **Twelve open outside PRs touch `_audit.py`**, all from one contributor: #939, 941,
  993, 995, 996, 1005, 1006, 1013, 1014, 1015, 1043, 1048. They add 38 rows and 26
  allow-list names. The contributor chose the tier of 12 rows: 11 at tier 1 or
  `invariant`, the two kinds that need no approval, and one at tier 2. Example: #1048
  tiers `indexing.engines.DRIVEN_MIN_LINES = 6` as arithmetic, while the number is the
  floor below which flagged lines are taken back, which is an action. Nine of the twelve
  also edit `docs/skill/`; four edit a CLAUDE.md (three `indexing/`, one `io/`).
- **The walk misses directories that decide things.** `WALKED` lists the directories
  whose module-level numbers the table holds. Outside it, an AST count of module-level
  numbers finds `io/` 65 (the readers' byte offsets, mostly), `viz/` 44, `gui/` 31,
  `runs.py` 7, `backend/` 4, `_display.py` 3, `solve/` 2, `watch/` 2, and one each in
  `_nearmiss.py`, `compare_app/` and `history/`; 497 inside it. `solve/` (direct-space
  structure solution) holds `cost.py` today, and open PR #1016 adds `solve/chemistry.py`
  with `CLASH_FRACTION = 0.8`, `CLASH_SIGMA_ANG = 0.1`, `PRIOR_SHARE_MAX = 0.25`,
  `DEFAULT_CN = 6`, `INVENTORY_TOL = 0.05` and `PEAK_COUNTS = 1e4`, without touching the
  table.
- **The tripwire points contributors at the allow-list.** `tests/test_audit_table.py`
  says "Give each its tier, or add its name to the baseline for the judge to read", and
  `_audit.row_source` prints a paste-ready row at `unaudited`. `CONTRIBUTING.md` does not
  mention the table. No step of `/pr-review`, the `pr-conformance` agent, `/wp-start`,
  `/steward`, `/issue-review` or `.github/workflows/ci.yml` names the table or the judge.
- **The tripwire checks presence, never content.** A tier-3 row and a tier-2 action must
  carry `grounds` and `approved`; `approved` is a free string. An `invariant` row needs an
  invariance test that asserts its margin (§ The rule), and nothing checks that one exists.
- **CI can see a PR's base.** The lint job checks out at `fetch-depth: 2`, so HEAD^1 of
  GitHub's merge commit is the base; `tests/skill_caps.py` and `tests/skill_surface.py`
  already read it there. WP-2001's third review rejected a git read *inside the suite*
  because CI had no `origin/main` and a local one can be stale. Neither applies to HEAD^1
  in a lint step.
- **WP-2002's PR (#1050) conflicts on `_audit.py`** with #995, #1005 and #1015 (the
  review's `git merge-file` against 2df48c95); the other nine merge clean.

**Rulings (the maintainer, 2026-10-20).**

1. The open outside PRs are tiered at review before they merge. Their author is informed
   and agrees with the milestone's demotions.
2. WP-2007 (indexing) owns `solve/`.
3. The judge argues both sides, without manufacturing fairness: "I don't want a system in
   which a weak case given representation seems stronger than it is." The question for
   the case *for* an action is asked; a side with no evidence reads `none found` in one
   line; each item leads with its verdict and says which side's evidence is stronger.
   No slot is filled for symmetry.

**Why the CI step is not a count.** WP-2002's next session returns five or more rows to
`unaudited` on the judge's findings, an honest growth that a count would fail. A PR that
deletes an unaudited constant, for instance by inlining it out of the walk's sight, would
buy room for a new one. The rule instead: a name absent from the base's `ROWS` may not
arrive at `unaudited`; an existing row may return there.

**Why the CI step reports every delta.** The allow-list catches one of three paths in. A
row that arrives with its author's tier, and a retuned value under an existing tier,
change no baseline name. So the step prints every added, changed and deleted row (and any
`OTHER_RECORD_FIELDS` addition) to the run summary in `skill_surface`'s shape, and fails on
the one rule above. The printout is the item list `/pr-review` hands the judge.

**Why the judge needs the other side.** A tier-3 action costs a ruling from the
maintainer; marking it `caller` or turning it into a report costs nothing, and the judge
argued only against acting. So the cheap path for an author is to decide less, which
DESIGN § Rules, 1 counts as a cost to the caller. Measured in WP-2002: a lane applied
ruling B9 to the peak-position bounds, and the 11-BM NAC cell drifted 5129 ppm against
1117 ppm until the lead restored them.

- The tier of each rule this WP adds: none. It adds no heuristic to the package; its
  tests guard the table.

### Inherited

(none at filing)

## Non-goals

- Tiering any row, the twelve PRs' included. `/pr-review` does that with this WP's step;
  the audits (2002–2007) own the existing rows.
- Linting inline literals. Ruff's `PLR2004` finds 88 float-literal comparisons in the
  walked directories (the review, ruff 0.16.7); WPs 2005–2007 are lifting such literals
  into named constants (WP-2002's ruling B14), so a lint waits for them.
- The priority rubric in `docs/wp/TEMPLATE.md`, and the rulebook findings: WP-2009.
- Skill rows: WP-2008. Both received this filing's notes in their `### Inherited`.
- A Stop hook requiring the judge's table. WP-2002's second session skipped the judge on
  148 rows, said so in its log, and the third ran it; the soft gate failed visibly.
- CODEOWNERS on the table: the maintainer authors the WP PRs and GitHub does not let an
  author approve their own.

## Tasks

- [x] **Messages and CONTRIBUTING.** `test_audit_table.py`'s failures and
      `_audit.row_source` point to a tier with its evidence and say a new name may not
      enter at `unaudited`. `CONTRIBUTING.md` gains a paragraph: every new code, record
      field, constant under `WALKED`, default at a seat and `suggestion=` site needs a row
      with a tier and evidence; the judge reads it at review; tier 3 waits for the
      maintainer's ruling. A comment to the contributor is drafted for the maintainer to
      post. This lands before the CI step, so the test and CI never disagree.
- [x] **The walk's partition.** Every top-level entry of `src/rietx` is in `WALKED` or in
      a declared not-walked set with its reason, held by a test (the shape of
      `OTHER_RECORD_FIELDS`: land in one or the other). `"solve": 2007` enters `WALKED`
      (ruling 2), with its rows at `unaudited` on the baseline. Each not-walked reason is
      listed in the handover for the maintainer; `_nearmiss.py` and `runs.py` need a look
      before they are declared out.
- [x] **The judge** (`.claude/agents/generality-review.md`). Accept a PR description and
      the CI step's printout where it now expects a WP file and handover entry. Add the
      question for a row that removes an action, demotes it, or leaves it to the caller
      (`caller`, a report-only code): would every competent refiner act anyway, and what
      does leaving it cost in calls, reruns or a number moved off its reference? Lead each
      item with its verdict; a side with no evidence is `none found` in one line (ruling
      3). An `invariant` row names the test asserting its margin, or the judge says it has
      none.
- [ ] **The CI step.** `tests/audit_delta.py`, run in the lint job like `tests.skill_caps`:
      read the base's `_audit.py` at HEAD^1 by `ast` (the baseline is a literal tuple),
      print every row delta with its tier to the step summary, and fail only on a name new
      to `ROWS` at `unaudited`. Cases: a rename passes, a return to `unaudited` passes, a
      new unaudited name fails, a deletion and a retune are listed. It turns lint red on
      the twelve PRs at their next push, so it lands with the `/pr-review` pass over them,
      and the handover says which goes first.
- [ ] **`/pr-review`.** A step beside conformance: when the CI printout lists row deltas,
      or a PR adds a module-level number under a not-walked directory, the session
      proposes a tier for each untiered row (as WP-2002's readers did), dispatches one
      `generality-review` per run over every PR's items, posts the proposed tiers as a
      review comment, and groups tier-3 rows by class into the end-of-run batch (WP-2002
      ruled 256 rows as 16 classes). After a ruling it writes `grounds` and `approved` to
      the branch (maintainer edits were allowed on every fork PR checked) or asks the
      contributor. The "classes outsiders miss" list gains two: a skill row telling agents
      to call a `caller` verb, and a one-dataset finding written into a CLAUDE.md as a rule.
- [ ] **`/wp-start` step 7.** The restatement names the tier and the kind of ambiguity of
      each flag, threshold or automatic action the item adds. A WP filed before
      2026-10-19 that plans one writes the template's tier line first. No pause for the
      maintainer; the judge still decides at handover.
- [ ] **`/steward`.** One line under Red CI: an edit to a row's tier, evidence or value,
      or to the allow-list, goes back through the judge before the push.
- [ ] **Records.** `generality.md` § Acceptance's "a new heuristic cannot land unaudited"
      row names this WP beside 2001.
- [ ] Skill: none; nothing here reaches an agent driving rietx.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_audit_delta.py tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
```

Plus two runs recorded in the handover: the CI step against one of the twelve PRs'
base and head, printing its deltas and failing on its new unaudited names; and the judge
on that PR's items, its table showing at least one `none found` side or saying why none
arose.

## References

- `docs/milestones/generality.md` § The rule, § Decisions with the maintainer (the
  2026-10-20 entry); `docs/DESIGN.md` § Rules, 1 and 4.
- WP-2001 (the guard); WP-2002's handover of 2026-10-20 on branch
  `wp2002-single-fit-actions` (the judge's first run, the B9 over-reach).
- `tests/skill_caps.py`, `tests/skill_surface.py` (the base read at HEAD^1).

## Handover log

- **2026-10-20** — created, from a planning session on the maintainer's question whether
  the generality guard can reach the rest of the tooling. Checked against the tree at
  5ecd4d70 and against the twelve PRs' heads. No open WP owns it: 2001 is closed; 2009
  owns the rulebooks and the rubric, not the review commands or CI; 2007 owns `solve/`'s
  rows, not the walk's partition. The plan was reviewed twice: by the filing session, and
  by a fresh Opus agent given only the goal, the plan and its claims to verify. The second
  review added the partition, the messages, the new-name rule in place of a count, the
  three paths and the judge's other side, and corrected the filing session's PR count
  (twelve, not ten). Filing also wrote notes into 2007, 2008 and 2009. Next: `/wp-start`.
