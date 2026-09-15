# WP-1422 — the WP two sessions picked

Milestone: unscheduled · Status: ✅ 2026-09-15 — claim store, the session-start
report, the `EnterWorktree` refusal and `/wp-start` step 2; 23 tests, and the
first clash it would have caught is one that has not happened yet
Depends on: —

## Goal

`/wp-start` can answer "is anyone already working this WP?" before it commits
to one, and `EnterWorktree` refuses a WP a live session in another tree is
already working. Two sessions can no longer spend a day on the same WP and
find out at handover.

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

## Non-goals

- **No cross-machine claim.** Every session here runs on one desktop, and a
  claim keyed on a live local process cannot mean anything on another. A pushed
  branch is the cross-machine signal and it already exists.
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
- [x] Tests in `tests/test_workflow_hooks.py`: 30 → 53, all passing.
- [x] The handover audit's two: `provenance` reads the claim's `by`/`declared`,
      and the `"tree"` source value gets the case that reaches it.
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

### 2026-09-15 — the WP a session is on is now something the repo can answer

A session can now find out, before it starts, whether another session is
already working the WP it was about to pick, and `EnterWorktree` refuses one
that is taken. The cost of getting this wrong was a whole duplicated session,
discovered at handover when both sides have a branch and a PR.

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

- Fast selection `-n auto --dist loadgroup -m "not slow"`: **4877 passed, 132
  skipped**, two runs at 2:11 and 2:22 and nothing else on the machine. The one
  file touched went 30 → 53 collected, +23, and all 23 pass; skips unchanged, so
  no new skip. Main's own total was not re-run for the baseline, so the delta is
  closed by that collection count rather than by two full readings. The full
  selection did not run: this WP touches no code the package imports, which is
  the ladder's own condition for rung 3 (`tests/CLAUDE.md` § Running).
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

**Next**, in order, and only if wanted. Nothing here is owed.

1. Run with it for a few weeks. The refusal has never fired in anger, and the
   one question it cannot answer from inside this session is whether it fires
   when it should not — an idle session parked in a finished tree is the only
   false positive its trigger admits, and `release` is the whole answer if it
   turns out to be common.
2. If it is common, the next rung is liveness finer than "a process exists":
   the transcript's modification time would separate a session that is working
   from one that is merely open. That is `runs.liveness_of`'s pattern one rank
   out, and it is deliberately not built yet.

- **2026-09-15** — created.
