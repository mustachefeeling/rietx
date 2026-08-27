---
description: End-of-session WP handover — record everything, review, verify, open the PR, report ready for /clear
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

   **Check nothing else is mid-suite before the full selection** — one `pgrep`,
   `tests/CLAUDE.md` § Running. A `/pr-review` or another WP session may be
   running one, and a count measured beside it is not a count this handover can
   quote. Found one, the honest entry says the full selection did not run —
   never a figure taken anyway.

   Then **audit the names this session declared**, for the classes that have
   already gone wrong here and that no test catches. Only the ones the
   session actually triggered; the mechanised classes need no second opinion
   (`test_manual_api.py` already fails on an undocumented public surface,
   `test_docs_consistency.py` on glyphs and links, the `capabilities`
   meta-tests on a registry member missing from its arm). Did this session
   add physics with Part 1 prose but no Part 2 manual equation — **four of
   the six McCusker WPs** did exactly that (WP-1067's log)? A diagnostic code
   or a correction with no `docs/AGENT_PROTOCOL.md` row? A declared name with
   no writer — a defaulted `False`/`0` that reads as an *answer* about
   something nothing checked, a `Literal` member no code produces (**nine in
   WP-1076 alone**, and they were found by writing a manual chapter over the
   type, never by reading the code)? A correction whose evidence is an Rwp
   comparison? A physics function without its citation?

   Reading your own diff for these is weaker than reading someone else's, so
   name the trigger rather than scanning: this is a checklist against what
   the session *added*, not a re-review of it.
7. **If the WP is closing** (✅/🛑): delete its consumed `### Inherited`
   section, rewrite ROADMAP's "Current focus" for the successor (within
   `CURRENT_FOCUS_CAP`, tests/test_docs_consistency.py), and MOVE the
   outgoing focus narrative to the in-flight milestone record
   (`docs/milestones/v1.0.md` § "How v1.0 is getting here").
8. **Sweep session memory notes**: anything in the assistant memory
   directory that corrects or extends the repo record gets ported into the
   repo now — a memory note is not a channel to the next session's repo
   state.
9. **Review the diff before it becomes a PR.** Run `/code-review medium
   --fix` — it reads this session's work (a clean tree means the branch's own
   diff against `origin/main`) and applies what it accepts to the working
   tree. It belongs *here*, ahead of Verify, because a fix is a code change:
   one landed after the suite ran, or after the PR was opened, leaves neither
   the quoted counts nor the review describing the tree that merges.
   - Each accepted fix lands as its own commit prefixed `WP-NNNN:` like any
     other work; one left uncommitted fails step 10's clean-tree check.
   - **A finding is advice, not a gate** — declining one is a line in the
     handover entry, never silence. Say there what the pass changed, or that
     it found nothing: a review that left no trace cannot be told apart from
     one that never ran.
   - A finding outside this WP goes into that WP's `### Inherited` (step 5),
     not into this branch.
10. **Verify**: run `python3 .claude/hooks/session_start.py` — the scan the
    *next* session starts from. It must come back with no flag for this WP; a
    flag here means the entry was written in a form it cannot read, or that
    work landed after the WP file was last touched, and either way the
    successor pays for it. Then run
    `.venv/bin/python -m pytest tests/test_docs_consistency.py` and
    `.venv/bin/python -m ruff check src tests examples`; confirm the working
    tree is clean and pushed (or say what deliberately is not). **Clean and
    pushed is not the same as landed**: if the branch is already merged, check
    `git log origin/main..HEAD` is empty too. A commit made after its own PR
    merged is stranded on a dead branch — the merge cannot carry it and the
    session-start hook only compares dates, so nothing detects it (measured
    2026-08-18: `11ec1cd5` sat there until the next session's repair).

    **And green on this branch is not green on what lands.** Where the session
    ran the full suite at all — step 6's rule, when the change could move a
    measured number — run it on **current main merged into this branch**, not
    on the bare branch: `git fetch origin main` and merge it in first. Nothing
    else ever tests that tree. Branch protection is `strict: false`, so a PR
    merges green without ever having been built against the main it lands on,
    and `nightly.yml` has no `pull_request` trigger, so the acceptance suites
    do not run on a PR at all. `tests/CLAUDE.md` states the half of this that
    was already known: when main has moved under a branch, that branch's
    counts are not the merged tree's and the two parents' additions cannot
    simply be summed. The counts quoted in the handover entry are then the
    merged tree's, and say so.

    This is the same class as the stranded commit above, one rank out: what
    you verified and what the repository will hold are not the same object.

    **Fetch main immediately before the merge**, not at step 1. A concurrent
    `/pr-review` merges other people's PRs, so `origin/main` moves for reasons
    this session never sees, and a main fetched an hour ago can be several merges
    stale — which puts this step's tree back to being one nothing tested.
11. **Open or update the pull request.** A session's work is not handed over
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
12. **Report**, to the person and not to the log: **first the same
    plain-language paragraph the entry opens with** — what this session's work
    means, in a few sentences someone can read without opening the diff — then
    the next actions, then the PR URL, and that CI is the gate — the required checks run
    ruff plus the fast suite across the supported Pythons and a `[dev,jax]`
    job. Offer to watch the run rather than assuming; when you do watch, read
    state from `gh run list` (REST) rather than `gh pr checks` (GraphQL, which
    has 503'd through a GitHub incident while runs kept reporting), and read a
    sub-minute failure as one that never reached repo code. Only when step 10
    is green, end with exactly: **ready for /clear**.
