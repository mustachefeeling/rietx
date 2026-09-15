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
   focus" — read the two sections, not the file
   (`sed -n '/^## Session protocol/,/^## Milestones/p' docs/ROADMAP.md`, one
   contiguous block): ~1.3k tokens against the file's ~12k, and a WP file is
   self-contained. **§ Session protocol is read for its step 3**, which is
   the only statement of the handover trigger that stays in context after
   this command scrolls away; narrowing this read to Current focus alone
   (2026-09-01) cost the next two sessions their handover. Read that one WP
   file only (plus the DESIGN.md sections it links); do not read other WP
   files.

   **Then check nobody else has it**, before committing to the choice:
   `python3 .claude/hooks/wp_claim.py status NNNN` for the WP in hand, or bare
   `status` for the whole picture. It answers in two parts, because a clash
   comes from two directions.

   **This machine's worktrees.** One row each: `held` means a live `claude`
   session is sitting in that tree now, `dormant` means the tree and branch
   exist with nobody in them, `→` marks this session's own. Closed WPs whose
   trees were merely kept are filtered out, so a quiet table means what it
   says, and this half needs no network and no venv.

   **A held WP is taken**: two sessions on one WP duplicate hours of work and
   discover it at handover, so pick another or ask the user. A **dormant** one
   is the opposite and is often what you want — unfinished work with a branch
   to continue, resumed by giving `EnterWorktree` that tree's name.

   **Open pull requests, contributors' forks included.** The second part, and
   the only one that can see a person on another machine. Contributors here
   work from *issues* rather than WPs — measured 2026-09-15, all three open
   contributor PRs were on forks, named no WP in branch, title or body, and
   cited issues — so the chain is PR → issue → WP, through the issue numbers
   the WP files already cite. Issue *assignees* are not a signal: 0 of 78 open
   issues carried one.

   **An issue link is evidence of overlap, not proof of a clash.** One issue
   can be cited by several WPs, so read the PR before dropping a WP over it.
   A PR that names a WP outright is the strong form. If `gh` cannot answer the
   command says so rather than printing an empty list, and a session that
   cannot look should ask the user before starting.

   The WP a tree is on comes from its branch, so a tree you resume for a
   *different* WP is telling the next session the wrong thing. Say so once:
   `python3 .claude/hooks/wp_claim.py claim NNNN`. Nothing else needs it, and
   skipping it degrades to the branch name rather than to nothing.
3. **Worktree, then branch.** If the hook's first line names the main
   checkout, call `EnterWorktree` with the WP's name (`wp1208-<slug>`) before
   anything else. The `WorktreeCreate` hook cuts that branch from `origin/main`
   (or checks out an existing branch of that name), builds the `[dev]` venv,
   and keeps memory shared. The main checkout is read-only for a session —
   `.claude/hooks/worktree_only.py` refuses an edit or a HEAD-moving git verb
   there — so there is nothing to decide. Already in a worktree: continue its
   branch; it is yours. At session end Claude Code asks whether to keep or
   remove the tree; remove once the PR is open, the branch stays either way.

   The create hook **refuses** a tree whose name is a WP a live session in
   another tree is already working, and names that session and the release
   verb. It is the one refusal in this workflow rather than a report, because
   it is the last moment before a duplicated session is paid for. A refusal
   on a WP whose holder is plainly finished is cleared with the verb the
   message prints; check it really is finished first, because the trigger is a
   live process, not a leftover branch.

   **Never `git stash` here.** The stash is per *repository*, shared by every
   worktree, and another session's `stash pop` takes yours (measured
   2026-08-26). Commit to your branch instead.
4. **Venv.** If the hook flagged a mismatch or a missing venv (the create hook
   reports when its build failed), build this worktree's own
   (`uv venv --python 3.12 && uv pip install --python .venv/bin/python -e ".[dev]"`) and say which extras
   were installed — every test count quoted later depends on that statement
   (`tests/CLAUDE.md`).
5. **Prune the WP's `### Inherited`** on arrival: fold still-true entries
   into Context or Tasks, delete stale ones, and say why in the handover
   entry.

   **Then check the WP's *Findings* the same way, before building on one.** A
   findings block is a dated claim about the tree, not a standing fact, and a
   queued WP can lose whole tasks to work that landed after it was written:
   WP-1131, opened 2026-08-23 and started 2026-09-02, declared a conversion
   module missing that had landed the next day, and the width check it had
   inherited had shipped entire in v1.2 — three of eleven tasks already done,
   one task changed shape, and a dependent WP's blocker discharged rather than
   delivered. Grep for the names a finding says are missing and
   `git log --oneline -- <the file it says lacks them>` since the WP's date;
   rewrite what has gone stale **in place** with a dated "superseded in part"
   note and commit that prune first, because the successor reads the WP file
   and not your session. Then check whether any WP depending on this one is
   now unblocked — that goes in *its* `### Inherited` at handover (step 5 of
   `/wp-handover`).
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

   **Invoke the command; do not reproduce it.** The second failure mode is
   writing the entry, syncing the glyph and opening the PR by hand and
   reporting "handed over" — which is what WP-1131 did on 2026-09-02, having
   skipped the diff review and the verify pass, the two steps that cost work.
   A summary of the checklist is not the checklist.
   `.claude/hooks/handover_owed.py` holds one stop open when a WP branch is
   clean and pushed and this session never ran the command; a session that is
   genuinely not finished says so in a line and carries on.
