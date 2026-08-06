# WP-1061 — Session-workflow robustness: detect the missed handover

Milestone: v1.0 · Status: ✅ 2026-08-06 — all six tasks landed; the hook's first
live run found a real missed handover (WP-1043) before it was even wired in
Depends on: — (touches `.claude/commands/wp-handover.md`, as does 1060; different
steps, lands in either order)

## Goal

A missed `/wp-handover` stops being silent rot: a checked-in SessionStart hook
detects it (plus a wrong-tree venv, a stale branch, uncommitted work) at the
start of the next session and names the repair; `/wp-start` encodes the
session-start ritual; `/wp-handover` gains a repair mode for reconstructing a
predecessor's missing entry.

## Context

The working protocol today: on a worktree, /clear, start a new branch, one WP
per session, "*sometimes* /wp-handover is run" (the user's own description,
2026-08-06). Its weak joint: everything downstream — WP-file accuracy, ROADMAP
glyph sync, `### Inherited` mailboxes — depends on the handover being
*remembered*, and nothing detects a miss; the next session silently starts
against stale state. Session start is equally manual: right worktree, fresh
branch off main, and a venv that resolves to *this* tree —
`settings.local.json`'s permission history shows the user hand-running exactly
that check, and `tests/CLAUDE.md` documents the trap (the main checkout's
`.venv` resolves `pxrdref` to the main checkout's `src`).

**The design inverts the dependency**: a ritual cannot be forced at the end of
a session that has already ended, so the miss is detected and repaired
automatically at the start of the next one. Detection is a *prompt to the
session, never a gate*.

State measured 2026-08-06, useful as live fixtures: `.claude/worktrees/`
holds three worktrees (`gui` locked on `gui-bugfixes-zoom-theme`, `indexer` on
the stale merged `wp1043-lebail-validator-retraction`, `strategy`); on `main`,
WP-1041 has commits dated after its newest handover entry (post-close syncs) —
the case that forces the two-severity design below. The repo has no
`.claude/settings.json` (only untracked `settings.local.json` with
permissions — leave it alone); `.claude/commands/wp-handover.md` is tracked,
so new files under `.claude/` propagate to future worktrees.

**Design rule** (from 1060's verdict): the hook runs every session, so its
healthy-state output must be tiny (≤ ~8 lines) — it must not become new fixed
context ballast. And the hook must not depend on the venv it is checking: a
missing or wrong-tree venv is precisely a condition it must survive to report.

## Non-goals

- Gating: the hook informs, it never blocks; no pre-commit hooks, no CI
  enforcement of handover freshness (CI checkouts are shallow; sessions are
  not CI's business).
- Changing the protocol itself (one WP per session, commit prefixes, the
  handover checklist's existing steps) — this WP adds detection and a repair
  path, nothing else.
- Editing `settings.local.json` (user-owned, untracked).
- Firing on `resume`: a resumed session already carries its context; a
  resume-time flag on the in-flight WP would be a guaranteed false alarm.

## Tasks

- [x] 1. `.claude/hooks/session_start.py` — the read-only scan, stdlib-only
  Python, run with `python3` from PATH (never the venv), <1 s, no package
  import, no network. Prints: worktree root, current branch, ahead/behind
  local `main` (`git rev-list --count`), uncommitted-change count
  (`git status --porcelain`); **venv resolution without importing** — read
  the editable-install pointer in `.venv` (the `__editable__*pxrdref*`
  .pth/finder file in site-packages), compare its target to this tree's
  root, and on mismatch or missing venv print the fix verbatim
  (`uv venv --python 3.12 && uv pip install -e ".[dev]"`); **missed-handover
  scan with two severities** — collect `WP-NNNN:` prefixes from the last
  ~50 commits; for each, find `docs/wp/NNNN-*.md`'s newest handover-log
  entry (the `- **YYYY-MM-DD**` bullets, per TEMPLATE.md) and its Status
  glyph; if the
  newest such commit's date is later than the newest entry (or no entry
  exists): 🔄/⬜ WP → `repair first (/wp-handover, repair mode)`; ✅/🛑 WP →
  soft `post-close commits not in the log` note. Also list any WP whose
  glyph is 🔄. Docstring states the known limitation: entries are day-dated,
  so a same-day commit-then-no-handover is invisible; the flag is a prompt,
  never a gate. Healthy output is one or two lines.
- [x] 2. `.claude/settings.json` — new checked-in file wiring
  `hooks.SessionStart`, matchers `startup|clear` only (NOT `resume`, see
  Non-goals), command `python3 .claude/hooks/session_start.py`. Note: Claude
  Code prompts once per user to trust a project hook — expected.
- [x] 3. `tests/test_workflow_hooks.py` — one small file importing the scan
  functions directly (no subprocess bash parsing), tmp_path git fixture:
  healthy state → short output; 🔄 fixture WP + later `WP-NNNN:` commit →
  repair flag; ✅ WP + later commit → soft note, not a repair flag; same-day
  entry and commit → no flag (the documented blind spot, pinned as such);
  venv pointer mismatch → flagged with the fix line.
- [x] 4. `.claude/commands/wp-start.md` — the session-start ritual: (a) act
  on the hook's report first — a flagged missed handover is repaired
  *before* new work; (b) identify the WP (user-named, else ROADMAP Current
  focus) and read that one WP file only; (c) branch — if on `main` or a
  branch already merged into main, create `wpNNNN-<slug>` from current main
  (`git fetch origin main` first when a remote exists; in a worktree,
  branching from the local `main` ref works even though main is checked out
  elsewhere); if on an in-flight branch, continue it; (d) if the hook
  flagged a venv mismatch, build this worktree's venv and say which extras
  were installed; (e) prune the WP's `### Inherited`; (f) restate the
  checklist item being started, the WP's acceptance command, and the
  session scope (this WP only; finish → /wp-handover → stop).
- [x] 5. Repair mode in `.claude/commands/wp-handover.md`: when invoked for
  work a *previous* session left un-handed-over (the hook's flag),
  reconstruct the entry from `git log --stat` and the WP checklist state,
  date it with the commits' date, mark it "(reconstructed post hoc)"; all
  other steps unchanged.
- [x] 6. Protocol sync, minimal: ROADMAP § Session protocol step 1 gains
  "`/wp-start` encodes this"; step 3 gains one sentence ("a missed handover
  is detected at the next session start and repaired before new work").
  Respect the size caps as they stand at execution time (1060 may have
  lowered them).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_workflow_hooks.py tests/test_docs_consistency.py
.venv/bin/python -m ruff check src tests examples
python3 .claude/hooks/session_start.py            # healthy path: short output, exit 0
(cd .claude/worktrees/indexer && python3 ../../hooks/session_start.py)  # detection path: real flags
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"   # passed+skipped moves by exactly the new file's tests
```

Live checks: from the main checkout the WP-1041 post-entry commits surface as
the *soft* note, not a repair flag; from the `indexer` worktree the stale
branch and/or venv are flagged. Hook wiring: /clear in the repo → the report
appears in the fresh session's context after the one-time trust prompt.

## References

Claude Code hooks documentation (SessionStart matchers: startup / resume /
clear); `tests/CLAUDE.md` § Quoting numbers (the worktree-venv trap this
automates); the user's protocol description, 2026-08-06.

## Handover log

- **2026-08-06 (close)** — all six tasks landed as six commits on
  `wp1061-workflow-robustness`; acceptance green (hook 0.13 s live from both
  checkouts; the new tests + docs consistency + ruff; fast suite measured with
  and without the new file). Counts: **1886 / 5** fast with
  `test_workflow_hooks.py`, **1880 / 5** without, main checkout venv
  `[dev,jax,torch]` — passed+skipped +6 exactly, all passes, no new skips;
  full selection not run (the acceptance names the fast one, and the file
  carries no slow marks, so the full delta is the same +6). Gotchas for a
  successor: (1) the editable pointer on this repo is **uv's**
  `_editable_impl_pxrd_refine.pth` carrying the bare src path — the task's
  `__editable__*pxrdref*` name is the setuptools form; the hook reads both.
  (2) The Context fixtures had drifted exactly as the created entry warned:
  WP-1041's fourth-session entry (2026-08-06) is same-day with its post-close
  commits, so the promised soft note now sits inside the documented blind spot
  and does not fire; and the `indexer` worktree's venv is *correct* (its .pth
  resolves to its own tree), so what shows there is the stale branch (ahead
  10 / behind 2), not a venv flag. The Acceptance section's "Live checks"
  paragraph is stale on both points — this entry is the correction. (3) The
  live detection case instead is **WP-1043**: ⬜, two 2026-08-06 commits, no
  `## Handover log` section at all — flagged for repair from every checkout
  and **left standing deliberately** (one WP per session); its `### Inherited`
  names the repair, and the next session should run it before new work, which
  is exactly the flow this WP built. (4) Two handover-time catches by the doc
  machinery itself: the Current-numbers rewrite ran CLAUDE.md to its 720-line
  cap **exactly** — zero headroom, so the next session needing a line there
  should do the reflow consolidation `test_docs_consistency.py`'s comment
  describes rather than raise the cap — and the closed-WP Inherited check was
  a substring test, which this WP's *prose mentions* of the section name
  tripped; it is now heading-anchored (`^### Inherited`, re.M), mirroring the
  H2 check beside it. Next: nothing — the WP closes; expect the one-time
  project-hook trust prompt at the next session start.
- **2026-08-06** — created, from the approved two-WP plan (trim + workflow
  robustness, this one the robustness). Nothing executed yet. The live
  fixtures named in Context (stale `indexer` worktree, WP-1041 post-entry
  commits) were true on this date — re-check before relying on them in the
  acceptance runs.
