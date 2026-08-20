---
description: End-of-session WP handover — record everything, verify, open the PR, report ready for /clear
---

Run the end-of-WP-session checklist (docs/ROADMAP.md § Session protocol,
steps 3–5). Work through every item; do not skip one silently — if an item
does not apply, say why in one line.

**Repair mode** — when invoked for work a *previous* session left
un-handed-over (the session-start hook's `repair first` flag): reconstruct
the missing entry from `git log --stat` over that WP's commits and the
current state of its checklist, date it with the commits' own date (never
today's), and mark it "(reconstructed post hoc)". A reconstruction records
what the commits show, not what the session might have known — where the
diff does not say why, say so rather than inventing a rationale. All other
steps below run unchanged.

1. **Identify the active WP** from this session's `git log` (`WP-NNNN:`
   prefixes). If more than one WP was touched, confirm with the user before
   proceeding. If the session made **no** commit and left no uncommitted work,
   say so in one line and stop — there is nothing to hand over, and running the
   rest anyway is what makes this command feel expensive enough to skip.
2. **Tick landed tasks** in the WP file's checklist — every commit that
   landed should correspond to a checked item.
3. **Prepend the dated handover entry** to the WP's `## Handover log`
   (newest first), in one of the two forms `docs/wp/TEMPLATE.md` sanctions —
   a `- **YYYY-MM-DD** — …` bullet, or a `### YYYY-MM-DD [(Nth session)] — …`
   heading once the WP takes more than one session in a day. **Only those two
   are read by `.claude/hooks/session_start.py`**, and an entry it cannot see
   is a handover that did not happen: it flags the WP at the next session and
   spends the successor's first act on a repair that was not needed.

   The entry has two audiences and therefore two registers.

   - **Open with a short plain-language paragraph saying what the work
     *means*** — what a person who has not read the diff now knows, or can do,
     that they could not before, and what it cost or ruled out. No dot-paths,
     no symbol names, no commit list. Two to five sentences. If the honest
     answer is "nothing yet, but X is now refuted", write that; a negative
     result stated plainly is worth more than a summary of activity.
   - **Close by naming the next actions** — the concrete next thing, in order,
     with whatever decides between them. "Next: answer the last task first,
     because it decides whether the rest is JSON-surface work or python-surface
     work" is an entry a successor can act on; "next: continue" is not.
   - **Between them go the working details** for the successor: *Done* /
     *Measured* / *In flight* / *Gotchas*, written for someone who has read
     only this WP file and CLAUDE.md.
4. **Sync the Status line** (`glyph date — free text`, vocabulary in
   `docs/wp/TEMPLATE.md`) and mirror the glyph in the WP's ROADMAP index
   row.
5. **Push forward references**: anything learned that changes work in a WP
   that is not closed and not this one goes into *that* WP's `### Inherited`
   section, naming this WP as the source.
6. **Audit this session's CLAUDE.md edits** (root, `gui/`, `tests/`,
   `src/rietx/indexing/`): every added line must be a standing rule
   (protocol rule 4 — evidence compressed to a clause plus a pointer), never
   a dated finding. Counts and timings this session measured go **in the
   handover entry** (root CLAUDE.md § Numbers is a recipe, not a ledger),
   and run the count check there: passed+skipped moved by exactly the tests
   this session added, in both the fast and full selections, and any new
   skip is named as a skip, not a pass.
7. **If the WP is closing** (✅/🛑): delete its consumed `### Inherited`
   section, rewrite ROADMAP's "Current focus" for the successor (within
   `CURRENT_FOCUS_CAP`, tests/test_docs_consistency.py), and MOVE the
   outgoing focus narrative to the in-flight milestone record
   (`docs/milestones/v1.0.md` § "How v1.0 is getting here").
8. **Sweep session memory notes**: anything in the assistant memory
   directory that corrects or extends the repo record gets ported into the
   repo now — a memory note is not a channel to the next session's repo
   state.
9. **Verify**: run `python3 .claude/hooks/session_start.py` — the scan the
   *next* session starts from. It must come back with no flag for this WP; a
   flag here means the entry was written in a form it cannot read, or that
   work landed after the WP file was last touched, and either way the
   successor pays for it. Then run
   `.venv/bin/python -m pytest tests/test_docs_consistency.py -q` and
   `.venv/bin/python -m ruff check src tests examples`; confirm the working
   tree is clean and pushed (or say what deliberately is not). **Clean and
   pushed is not the same as landed**: if the branch is already merged, check
   `git log origin/main..HEAD` is empty too. A commit made after its own PR
   merged is stranded on a dead branch — the merge cannot carry it and the
   session-start hook only compares dates, so nothing detects it (measured
   2026-08-18: `11ec1cd5` sat there until the next session's repair).
10. **Open or update the pull request.** A session's work is not handed over
    until it is reviewable, so the PR is part of the ritual rather than a
    follow-up request. Skip it — saying so in one line — when the branch is
    `main`, when `git log origin/main..HEAD` is empty, or when the branch is
    already merged (repair mode usually lands here).
    - Check first with `gh pr view --json url,state`: an existing open PR for
      this branch is **edited** (`gh pr edit --title --body`), never
      duplicated.
    - Title mirrors the lead commit: `WP-NNNN: <what landed>`.
    - Body is the handover entry **rewritten for a reviewer**, not pasted:
      what landed and why, what it measured (with the venv **and** platform,
      per `tests/CLAUDE.md` § Quoting numbers), what it deliberately did not
      do, and any finding filed into another WP, named with its number. End
      with the repo's two-line Claude Code footer.
    - **Never merge, and never wait on CI to decide.** Whether green is
      enough, and when to merge, is the maintainer's call.
11. **Report**, to the person and not to the log: **first the same
    plain-language paragraph the entry opens with** — what this session's work
    means, in a few sentences someone can read without opening the diff — then
    the next actions, then the PR URL, and that CI is the gate — the required checks run
    ruff plus the fast suite across the supported Pythons and a `[dev,jax]`
    job. Offer to watch the run rather than assuming; when you do watch, read
    state from `gh run list` (REST) rather than `gh pr checks` (GraphQL, which
    has 503'd through a GitHub incident while runs kept reporting), and read a
    sub-minute failure as one that never reached repo code. Only when step 9
    is green, end with exactly: **ready for /clear**.
