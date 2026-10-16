# WP-1988 — A PR put up for review is watched by the session that opened it

Milestone: unscheduled · Status: 🔄 2026-10-16 — hook, steward skill and command edits landed; the first real subscribed handover is the acceptance
Track: The repo's own process
Depends on: —
Priority: P4 2026-10-16 — process: no number moves, but every WP PR waits on someone noticing it went red or conflicted

## Goal

A WP session's PR stops being left alone at the handover. `/wp-handover` step
12 offered to watch the run; unwatched, a PR goes conflicted or red as soon as
main moves under it, and stays so until the maintainer finds it. A cloud
session has `subscribe_pr_activity`, which delivers CI results, reviews and
merge conflicts into the session that opened the PR. This WP makes the
subscription happen and says how this repo wants the events handled.

## Design

- **A PostToolUse hook, not prose** (`.claude/hooks/pr_subscribe.py`). A hook
  cannot call an MCP tool, so it notices the PR becoming reviewable
  (`gh pr create` without `--draft`, `gh pr ready`, the two `mcp__github__`
  equivalents) and puts the call, owner, repo and number filled in, in front of
  the model as `additionalContext`. It is silent on a draft, on a read, and on
  a failed create, since it names no PR it cannot read off the output.
- **The subscription starts at ready, never at the claim draft.** `/wp-start`
  step 4b's draft is still being written; every event on it is the session's
  own push.
- **`.claude/skills/steward/SKILL.md`** is the repo half. The cloud harness
  reads that path from the PR's head branch before acting on an event, and it
  takes precedence on conventions: merge main in rather than rebase,
  regenerate generated files rather than take a side (pointing at
  `/pr-review`'s bookkeeping sync, never restating it), reproduce a CI failure
  before fixing it, never skip or widen a test, and a substantive fix touches
  the WP file so `session_start.py`'s order rule does not flag a repair.
- **One WP per session survives the handover.** A subscribed session ends on
  *watching <url>*, not *ready for /clear*, and the next WP is a new session.

## Tasks

- [x] `pr_subscribe.py` + its `PostToolUse` registration, tested in
      `tests/test_workflow_hooks.py`.
- [x] `.claude/skills/steward/SKILL.md`.
- [x] `/wp-handover` steps 11-12, `/wp-start` step 4b. ROADMAP's protocol
      step 3 is left alone: it sits at its pinned size cap, and the command
      is the authority it points to.
- [ ] Acceptance: one WP handover in a cloud session subscribes from the hook's
      prompt, and one event on it (a merge conflict or a red check) is handled
      by the skill without the person asking. Record what it cost in context.

## Handover log

- **2026-10-16** — Filed: no open WP owns PR follow-through (1506 and 1547 are
  CI's side, 1507 the index). A session that puts its PR up for review now
  gets told to subscribe to it, with the number filled in, and the repo says
  how conflicts and red checks on it are handled. Nothing has been watched
  under it yet, so whether the cost of being woken at handover-size context is
  worth it is unmeasured. Next: the acceptance task, on the next cloud WP
  session; if a wake proves too expensive, narrow the skill to merge conflicts
  and red CI and leave reviews to the person.
