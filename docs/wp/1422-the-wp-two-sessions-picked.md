# WP-1422 — the WP two sessions picked

Milestone: unscheduled · Status: 🔄 2026-09-15 — claim store, session-start
report and the `EnterWorktree` refusal land; the CLAUDE.md clause is open
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
- [x] Tests in `tests/test_workflow_hooks.py`.
- [ ] Root CLAUDE.md § Protocol: the one-WP-per-session clause beside the
      one-tree-per-session one.
- [ ] ROADMAP: the index row under § The repo's own process.
- [ ] Skill: none. The claim is repo process and reaches no agent driving
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

- **2026-09-15** — created.
