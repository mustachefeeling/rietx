# WP-1422 — the WP two sessions picked

Milestone: unscheduled · Status: ✅ 2026-09-15 — both directions: a local claim
with an `EnterWorktree` refusal, the contributor half through open PRs and the
issues WPs cite, and a draft claim PR that announces. 36 tests; it found a live
overlap (WP-1311 against PR #289) on its first run
Depends on: —

## Goal

`/wp-start` can answer "is anyone already working this WP?" before it commits
to one — **anyone**, meaning another session on this machine *and* a contributor
on theirs — and `EnterWorktree` refuses a WP a live local session already holds.
Nobody spends a day on work someone else is doing and finds out at handover.

## Context

WP-1061 gave this repo a session-start scan, WP-1116 its second coverage rule,
and WP-1410 scoped the worktree gate. All three enforce **one session per
tree**: sessions sharing a checkout share HEAD, the index, the stash and the
working tree, and four collisions in one day (2026-08-26) paid for the rule.

**One WP per session is the same rule one rank out, and nothing enforced it.**
Two sessions in two proper worktrees collide in a way `worktree_only.py` cannot
see: they duplicate hours of work, and they find out at handover, when both
have a branch and a PR.

### What was already observable

Everything the answer needs, which is why the design adds almost no state:

| fact | where it already lives |
|---|---|
| the worktrees of this repo | `git worktree list --porcelain` |
| which are live | a `claude` process with a cwd — `session_start.live_sessions` |
| which WP a tree is on | its name, by the repo's own convention |
| whether that WP is still open | its Status glyph — `session_start.wp_file_state` |

So derivation answers the ordinary case with no ledger at all, and a ledger
that can be forgotten is worse than one that is never needed.

### What derivation cannot see (measured 2026-09-15, this repo)

- A live session sat in `.claude/worktrees/wp1402-.../wp1404-what-recording-every-fit-costs`
  on branch `wp1413-snapshot-cost`, working **WP-1413**. The branch happened to
  say so. Had the session reused the branch too, derivation would have named
  1404 and the real claim would have been invisible. Hence branch before tree
  name, and a declaration that can override both.
- A refusal needs a way past it. A session parked idle in a tree it has
  finished with would otherwise block the next session for ever.

### Why no clash appears in the history

Searched: three branches carry `wp1110-` and two carry `wp1067-`, and in every
case the commit ranges are strictly sequential (1110: 2026-08-20 23:58, then
08-21 01:47, then 08-21 14:43). **No clash has happened yet.** This WP is
opened on the mechanism, not on an incident, and that is stated rather than
dressed up as evidence.

### The model

**A claim is held by a worktree, and a worktree is live when a session sits in
it.** Two states follow, and the third one usually wanted does not exist:

- **held** — a live `claude` session's cwd is inside the tree. The only state
  that bears on a clash.
- **dormant** — the tree and branch exist with nobody in them. Unfinished work
  with a branch to resume, and never a refusal.

A claim whose worktree is gone is deleted on the next read, so staleness cannot
accumulate and there is no expiry policy to tune. That matters because
`session_start.py`'s own docstring records the cost of a false alarm: it teaches
the reader to skip the one line that is ever load-bearing.

### Where it reports and where it refuses

Every other signal in this workflow reports (WP-1061: "a prompt to the session,
never a gate"). This one refuses in exactly one place, and the distinction is
the repo's existing one — **a gate exists where the collision is unrecoverable
and the trigger is provable.**

- **Session start**: a line naming any WP a live session in another tree holds.
  Quiet on a machine running one session.
- **`EnterWorktree`**: refused, before the tree is made. It is the last moment
  before the cost is paid, the trigger is a live process rather than a leftover
  branch, and git already refuses the narrower version of the same accident (a
  branch cannot be checked out in two worktrees). Leaving the wider check
  advisory would block the narrow accident and wave the broad one through.

### Where the store lives

`<git-common-dir>/wp-claims/`. Git guarantees the common dir is shared by every
worktree (measured: the main checkout, a worktree and a worktree nested inside a
worktree all resolve `git rev-parse --git-common-dir` to `/Users/yue/Code/rietx/.git`),
nothing tracks it, `git status` never sees it, and a fresh clone starts empty.
A tracked file could not do the job: a claim has to be visible across branches
that never merge.

### The contributor half

A local claim answers "which of *my* trees is on this WP" and can answer nothing
else. The maintainer clashing with a contributor is the case this WP exists for,
and it needs a signal both machines can see.

Measured on this repo, 2026-09-15:

| | |
|---|---|
| open contributor PRs | 3, all by one contributor |
| on a fork | 3 of 3 — so absent from `git ls-remote origin` |
| naming a WP in branch, title or body | 0 of 3 |
| citing an issue | 3 of 3 (#287, #283, #124) |
| open issues carrying an assignee | **0 of 78** |

So contributors key on **issues**, and every WP file already cites the issues it
closes — the triage protocol audits exactly that with a `#N\b` grep. The chain
is therefore **PR → issue → WP**, and it asks no new habit of anyone. Issue
assignment was considered and rejected on the 0-of-78 row: building on it would
mean asking a contributor to adopt a convention they do not use.

**It found a live near-miss on its first run.** WP-1311 is ⬜ unstarted and
contributor PR #289 is open on issue #283, which WP-1311 cites. Picking 1311
that day would have been the clash.

Two rules keep it honest. **An issue link is evidence of overlap, never proof of
a clash** — issue #287 is cited by five WP files — so this tier reports and
`EnterWorktree` never refuses on it. And it needs the network and a `gh` login,
so it lives in `/wp-start` and **never in the SessionStart hook**, which stays
stdlib-only, offline-safe and 0.25 s. When `gh` cannot answer the command says
so rather than printing an empty list, because "no PRs" and "could not look"
must not read alike.

### Announcing, not only looking

Reading the other side is half of it. A session also has to *say* what it is on,
or every clone is polite and blind at once. The local claim cannot do that: it
is a file on one machine's disk.

So `/wp-start` step 4b opens a **draft pull request** as its first act in the new
tree, carrying one commit that sets the WP's `Status:` to `🔄 <date> — claimed
by @<who>` and mirrors the glyph in its ROADMAP row. Four properties earn it:

- **It is the real PR, opened early**, not a second one. `/wp-handover` step 11
  already edits an existing open PR rather than duplicating it, and now marks it
  ready. Claiming therefore costs nothing at the end, and the work is reviewable
  from the first commit.
- **A commit touching only its own WP file is already *ritual*** (`_is_ritual`),
  so the claim owes no handover entry and trips no coverage rule.
- **Both edits are mechanically pinned** — the glyph must match between the WP
  file and the ROADMAP row, and the row's cell must be a glyph and a date and
  nothing else (`tests/test_docs_consistency.py`).
- **Everyone does it, not only contributors.** A maintainer working locally is
  exactly as invisible to a contributor as the reverse, and a one-sided claim
  leaves half the clash open.

`CONTRIBUTING.md` § Maintainer-only machinery reserved WP files for the
maintainer; it now sanctions this one edit, beside the handover-log entry it
already welcomed. And `open_prs` gained the **branch** as a third WP source
after the title and the WP file touched, because a claim PR is opened before
either of those says anything and `wp1414-slug` is the one thing it always has.

## Non-goals

- ~~**No cross-machine claim.**~~ **Withdrawn the same day, and it was the
  point.** This said a claim keyed on a live local process cannot mean anything
  on another machine, which is true, and then concluded that the cross-machine
  case was out of scope, which was wrong: the maintainer clashing with a
  *contributor* is the case the WP was asked for. It also proposed a pushed
  branch as the existing signal, and that does not work either — measured
  2026-09-15, all three open contributor PRs sat on **forks**, so no `origin`
  branch names them. § The contributor half replaces this.
- **No release at handover.** The session ending is what makes a claim dormant,
  and dormant already refuses nothing. A release step in `/wp-handover` would be
  one more ritual able to be skipped, for no state that is not reached anyway.
- **No claim on `main`.** The main checkout is read-only for a session, so it
  claims nothing whatever it is called.

## Tasks

- [x] `.claude/hooks/wp_claim.py`: the claim store on the git common dir, WP
      name parsing, `occupancy`/`held_elsewhere`/`clashes`/`bears_on_a_clash` as
      pure functions, and the `status`/`claim`/`release` CLI.
- [x] `session_start.py`: `claim_lines`, the flag, and the two docstring
      paragraphs saying what it prints and which gate holds the rule.
- [x] `worktree_create.py`: `clash_refusal` before the tree is made, the claim
      written after it, and why this is the one refusal.
- [x] `worktree_remove.py`: the docstring clause saying the claim needs no
      cooperation from it, and why a fourth path to the same state is not added.
- [x] `.claude/commands/wp-start.md`: the check inside step 2, the dormant
      reading, the `claim` override, and the refusal at step 3.
- [x] Tests in `tests/test_workflow_hooks.py`: 30 → 56, all passing.
- [x] The handover audit's two: `provenance` reads the claim's `by`/`declared`,
      and the `"tree"` source value gets the case that reaches it.
- [x] The review pass's six, the first of them the ranking inversion that let an
      automatic claim outrank the branch it was derived from.
- [x] **The contributor half**: `open_prs`, `wp_issue_citations`, `overlaps` and
      the per-PR grouping, reported by `wp_claim.py status [NNNN]` and wired
      into `/wp-start` step 2. Reports only, needs `gh`, never in the hook.
- [x] **Announcing**: `/wp-start` step 4b opens the draft claim PR, handover
      step 11 marks it ready, `CONTRIBUTING.md` sanctions the WP-file edit, and
      `open_prs` reads the branch as a third WP source.
- [x] Root CLAUDE.md § Protocol: the one-WP-per-session clause beside the
      one-tree-per-session one, and the cap ledger entry that pays for it.
- [x] ROADMAP: the index row under § The repo's own process.
- [x] Skill: none. The claim is repo process and reaches no agent driving
      rietx (root CLAUDE.md § skill routes a rule by who needs it).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_workflow_hooks.py -q
.venv/bin/python -m pytest tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
python3 .claude/hooks/wp_claim.py status      # names every live tree's WP
python3 .claude/hooks/session_start.py        # flags a WP held in another tree
```

## References

- WP-1061 (the session-start scan; report, never gate), WP-1116 (its second
  coverage rule), WP-1410 (scoping the worktree gate) — the three this extends.
- `git rev-parse --git-common-dir`: git's own guarantee that worktrees of one
  repository share a directory.

## Handover log

### 2026-09-15 — the WP someone else is on is now something the repo can answer

A session can now find out, before it starts, whether anyone is already working
the WP it was about to pick — another session on this machine, or a contributor
on theirs. `EnterWorktree` refuses a WP a live local session holds. The cost of
getting this wrong was a whole duplicated effort, discovered at handover when
both sides have a branch and a PR.

**The first build answered only half of that, and the half it left out was the
point.** It read "every session here runs on one desktop" off the machine in
front of it and wrote *no cross-machine claim* into the non-goals. The
requirement was the maintainer not clashing with contributors. The correction is
recorded in place rather than quietly fixed, because the reasoning failed in a
way worth recognising again: **the scope was inferred from what was measurable
rather than from what was asked**, and the measurement was of one desktop
because that is what a local scan can see. The non-goal even proposed a pushed
branch as the existing cross-machine signal, which does not work either — every
contributor PR here is on a fork.

The finding worth keeping is how little had to be built. Everything the answer
needs was already observable — the worktrees from git, the live ones from the
`claude` processes and their working directories, the WP from the tree's own
name — so the answer is *derived*, and the small store added on top only
corrects the one case derivation gets wrong. That means nothing has to be
remembered: a session that skips every new step still gets the right answer
from its branch name. A claim also dies with its worktree, pruned whenever the
ledger is read, so there is no expiry policy and no way for it to start
describing trees that are gone.

It should be said plainly that **no clash has happened here yet**. The history
was searched for one: three branches carry `wp1110-` and two carry `wp1067-`,
and every commit range is strictly sequential (1110 ran 2026-08-20 23:58, then
08-21 01:47, then 08-21 14:43). This is opened on the mechanism, not on an
incident, and the WP says so rather than dressing the mechanism up as evidence.

**Done.** `wp_claim.py` holds the store and the pure functions over it
(`occupancy`, `held_elsewhere`, `clashes`, `bears_on_a_clash`) plus a
`status`/`claim`/`release` CLI. `session_start.py` grew `claim_lines`, one flag
beside the one-session-per-tree one. `worktree_create.py` refuses before making
the tree and writes the claim after. `worktree_remove.py` got a docstring clause
and no code. `/wp-start` gained the check inside step 2 — not as a new step, so
no cross-reference to a numbered step moved.

**Measured** (macOS Darwin 25.5.0, this worktree's own `[dev]` venv, no jax and
no torch, Python 3.12.12):

- Fast selection `-n auto --dist loadgroup -m "not slow"`: **4890 passed, 132
  skipped**, five runs across the session at 2:11-2:22 and nothing else on the
  machine. The one file touched went 30 → 66 collected, +36, and all 36 pass;
  skips unchanged, so no new skip. Main's own total was not re-run for the
  baseline, so the delta is closed by that collection count rather than by two
  full readings. The full selection did not run: this WP touches no code the
  package imports, which is the ladder's own condition for rung 3
  (`tests/CLAUDE.md` § Running).
- The contributor half on live data: 3 open contributor PRs, 3 of 3 on forks,
  0 of 3 naming a WP, 3 of 3 citing an issue, and 0 of 78 open issues carrying
  an assignee. Printed per WP it gave 8 rows for 3 PRs, because issue #287 is
  cited by five WP files; grouped per PR it gives 3.
- The session-start scan itself costs 0.246-0.252 s on this desktop, down from
  0.424 s before the review removed its duplicate process sweep. It runs before
  every session, so the figure is the one that matters for the flag's welcome.
- `git rev-parse --git-common-dir` resolves to the same `.git` from the main
  checkout, a worktree, and a worktree nested inside a worktree. That is the
  guarantee the store rests on.
- The live table on this machine went from six rows to two once closed WPs whose
  trees were merely kept were filtered out. Four of the six were finished work
  whose directory had not been removed.

The handover's own name audit found two things and both are fixed in the branch:
`Claim.by` and `Claim.declared` were written into every claim and read by
nothing, which is the twin of a declared name with no writer; and the third
`source` value had a producer and no test. `Holder.provenance` reads the pair,
and it earns the place rather than merely using it — the create hook's automatic
claim and a session's correction both render as "claim" under `source` alone.

**The review pass found the design inverted against itself, and it is worth
recording as the lesson of this WP.** `/code-review high --fix` returned six
findings; all six were accepted and none declined. The first was a real defect:
the create hook writes a claim whose WP is the tree's own name read back, and
`occupancy` ranked *every* claim above the branch — so the automatic claim
pinned the weakest source as the strongest, which is the exact inversion of the
branch-before-tree rule stated three paragraphs up in the same module's
docstring. On this module's own motivating case the table then said 1404, and a
third session asking for 1413 was neither warned nor refused. Only a session's
claim outranks the branch now, and `by` turns out to be load-bearing rather than
bookkeeping. The general shape: **a derived rule and a written override are two
mechanisms, and the second one silently outranked the first the moment something
automatic started writing it.**

The other five: a second `lsof` sweep per `claude` process that `render` had
already paid for (0.111 s of a 0.424 s scan, now 0.246 s); a glyph map built
over rows that were all `held`, where `held` always survives the filter, so it
could never drop anything; `main_checkout` taking the shallowest path, which is
not the main checkout for a worktree made outside `.claude/worktrees`; a shared
`.tmp` name under a comment claiming two writers were safe; and `describe`
rendering a dormant tree as "held by no session", one line asserting both of the
model's two states at once.

**Gotchas for anyone touching this.**

- The trigger for the refusal is a **live process**, never a branch. Stale
  `wp1067-*` branches have sat on the remote for a month; keying on them would
  have made the flag fire constantly, which `session_start.py`'s own docstring
  already names as the expensive failure.
- `wp_claim.py` keys its files by **worktree**, not by WP. Two trees on one WP
  is the clash itself, and a WP-keyed store would overwrite it into silence.
- The hooks are loose scripts on a directory that is not a package. The sibling
  import **appends** to `sys.path`, so nothing here can shadow a stdlib module.
- A test fixture asserting that the store is invisible to `git status` needs the
  real repo's `.claude/worktrees/` ignore rule, or it passes for the wrong
  reason — it catches its own untracked worktree directories instead.
- **`Claim.by` decides the ranking**, so a future writer of claims must say
  which kind it is. Automatic claims lose to the branch; a session's beats it.
- **The two halves are not interchangeable and must not be merged.** The local
  one is stdlib, offline, 0.25 s, and runs in a hook on every session; the
  contributor one needs `gh` and the network and runs once, in a command. Moving
  the second into the hook would make every session start depend on GitHub being
  reachable.
- **`gh` returning nothing and `gh` failing are different answers.** `open_prs`
  returns `None` for the second, and the caller prints a sentence rather than an
  empty list, so a session never reads "could not look" as "nobody is on it".
- `docs/ROADMAP.md` is now at **710 lines against a cap of 710**. The ledger's
  last entry recorded +1 headroom on 2026-09-15; three lines went in after it
  and this WP's index row took the last one, so the next index row needs a cap
  bump in its own commit.
- The rule was deliberately **not** added to ROADMAP § Session protocol step 1.
  That step already delegates to `/wp-start`, which carries the check, and a
  fourth copy beside CLAUDE.md, the command and the hook is what this repo's own
  "never restate" rule forbids.

**Next**, in order, and only if wanted. Nothing here is owed.

1. **Decide WP-1311 against contributor PR #289 before scheduling it.** That is
   the live overlap this found, and it is a judgement about the work rather than
   about the tooling.
2. Run with it for a few weeks. The refusal has never fired in anger, and the
   one question it cannot answer from inside this session is whether it fires
   when it should not — an idle session parked in a finished tree is the only
   false positive its trigger admits, and `release` is the whole answer if it
   turns out to be common.
3. If it is common, the next rung is liveness finer than "a process exists":
   the transcript's modification time would separate a session that is working
   from one that is merely open. That is `runs.liveness_of`'s pattern one rank
   out, and it is deliberately not built yet.
4. The claim PR is a convention, not a gate: nothing refuses work that skipped
   it, and nothing can, since the repo cannot see a clone that never pushed.
   What it buys is that *following* it makes you visible. If contributors do not
   take it up, the honest next move is asking them rather than adding
   enforcement that only binds the people already cooperating.

- **2026-09-15** — created.
