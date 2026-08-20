---
description: Session-start ritual — act on the hook report, pick the WP, branch, venv, restate scope
---

Run the session-start ritual. The SessionStart hook's report
(`.claude/hooks/session_start.py`) is already in context — start from it.

1. **Act on the hook's report first.** A `repair first` flag means a previous
   session missed its handover: run `/wp-handover` in repair mode for that WP
   *before* any new work. A soft `post-close commits not in the log` note is
   surfaced to the user, not necessarily repaired.

   **Read which rule fired**, because they mean different things.
   `WP file not touched since` is the *order* rule — substantive work landed
   after the WP file was last edited, and it sees a miss within the same day.
   `last handover entry <date>` is the *date* rule — the log is behind the
   commits by a day or more; it is the only rule that sees a session whose
   every commit was ritual (docs, a CLAUDE.md, `.claude/`).

   Neither rule proves health: work committed and handed over in the same
   session leaves both satisfied whatever the entry says, so a quiet report is
   a prompt, not proof.
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
6. **Tick the checklist item in the same commit that lands it** (protocol
   step 2). This is the cheap insurance behind the whole ritual: it keeps a
   partial record on disk at every point, so an interrupted session leaves the
   successor something, and it is what keeps the hook's order rule quiet
   without a handover being owed.
7. **Restate before starting**: the checklist item being started, the WP's
   acceptance command, and the session scope — this WP only; finish →
   `/wp-handover` → stop.

   Say the trigger out loud too, because `/wp-handover` is missed by drifting
   past it rather than by deciding against it. Run it when **any** of these
   happens, not only the first: the WP's scope for this session is done; the
   user says stop, `/clear`, or "that's enough"; context is about to compact;
   or the work is blocked on something outside the session. The protocol's own
   words are "at the end — **or whenever interruption threatens**".
