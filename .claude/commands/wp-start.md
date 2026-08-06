---
description: Session-start ritual — act on the hook report, pick the WP, branch, venv, restate scope
---

Run the session-start ritual. The SessionStart hook's report
(`.claude/hooks/session_start.py`) is already in context — start from it.

1. **Act on the hook's report first.** A `repair first` flag means a previous
   session missed its handover: run `/wp-handover` in repair mode for that WP
   *before* any new work. A soft `post-close commits not in the log` note is
   surfaced to the user, not necessarily repaired. Remember the report's
   blind spot: a same-day commit-then-no-handover is invisible, so a quiet
   report is a prompt, not proof.
2. **Identify the WP**: the one the user names, else ROADMAP "Current
   focus". Read that one WP file only (plus the DESIGN.md sections it
   links); do not read other WP files.
3. **Branch.** If on `main`, or on a branch already merged into main, create
   `wpNNNN-<slug>` from current main — `git fetch origin main` first when a
   remote exists; in a worktree, branching from the local `main` ref works
   even though main is checked out elsewhere. If on an in-flight branch,
   continue it.
4. **Venv.** If the hook flagged a mismatch or a missing venv, build this
   worktree's own (`uv venv --python 3.12 && uv pip install -e ".[dev]"`)
   and say which extras were installed — every test count quoted later
   depends on that statement (`tests/CLAUDE.md`).
5. **Prune the WP's `### Inherited`** on arrival: fold still-true entries
   into Context or Tasks, delete stale ones, and say why in the handover
   entry.
6. **Restate before starting**: the checklist item being started, the WP's
   acceptance command, and the session scope — this WP only; finish →
   `/wp-handover` → stop.
