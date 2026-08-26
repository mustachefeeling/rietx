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
3. **Tree, then branch.** A session owns the tree it was launched in and no
   other. The hook's first line names it, and a `⚠ another claude session is
   in this tree` line means it is taken — sessions sharing a checkout share
   HEAD, the index, the stash and the working tree, and on 2026-08-26 alone
   that put a `reset --hard` into a live session's tree, a stash into another
   session's branch, and tooling edits into another WP's closing commit by its
   `git add -A`. Taken means **stop**: name the free slot and its launch line,
   and let the user relaunch there. Do not work a second tree from here by
   `git -C` and subshells — that arrangement cost `/pr-review` four of its
   first eight commits.

   ```sh
   (cd .claude/worktrees/wp2 && claude)        # from a terminal, inside the slot
   ```

   The slots are fixed, persistent, and each has its own venv; branches move
   through them. Never a worktree per WP — that left thirteen stale trees and
   4.8 GB in `.claude/worktrees/` (2026-08-25). The main checkout and
   `.claude/worktrees/wp2` take WP sessions; `.claude/worktrees/pr-bench` is
   `/pr-review`'s. A slot idles detached at `origin/main`, so leave it that way
   when a WP's PR has merged: `git checkout --detach origin/main`. Not
   `claude --worktree`: it makes a fresh tree and a `worktree-<name>` branch
   per session, which is the accumulation above with a venv on each. Auto-memory
   is keyed by cwd, so a slot sees the maintainer's memory
   only through a symlink in `~/.claude/projects/` (maintainer-local; the
   memory note carries it).

   Then the branch. If on `main`, detached, or on a branch the hook reports
   `merged`, create `wpNNNN-<slug>` from `origin/main` — `git fetch origin
   main` first when a remote exists. If on an in-flight branch, continue it:
   with one session per tree it is yours.

   **Never `git stash` in this repository.** The stash is per *repository* and
   shared by every worktree, so another session's `stash pop` takes yours:
   measured 2026-08-26, one pushed to lift tooling edits off another session's
   branch was popped into that branch minutes later, and only an existing
   commit elsewhere kept it. Commit to your own branch instead — a commit is
   addressed, a stash is a shared pile.
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
