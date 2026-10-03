# WP-1540 — a milestone is named, a release is numbered

Milestone: unscheduled · Status: 🔄 2026-10-03 — renamed, rules rewritten (PR pending); the collaborator comments wait on the maintainer
Track: The repo's own process
Depends on: —
Priority: P2 2026-10-03 — work on main piles up behind a milestone that is late

## Goal

A queued or open milestone carries a name, and a version number is given to a
release when it is cut. A late milestone then holds back nothing but itself.
The next release ships whatever is on `main` and names the milestones that
were complete when it was cut.

## Context

**Measured 2026-10-03, on `main` at `0303da12`.**

- v1.5.0 shipped 2026-09-18. Since then 268 PRs have merged, and the staged
  notes in `docs/releases/1.5.1.md` have grown to 1 225 lines in 41 sections.
- The v1.6 milestone is the magnetic structure, and it is late. Its seven WPs
  are 🔄 or ⬜. Under protocol rule 6 a release follows a milestone's ship, so
  everything else on `main` waits for it.
- The milestones queued behind it are not waiting. Five of v1.7's WPs
  (1501-1503, 1529, and 1504's first round) and two of v1.8's (1801, 1802) are
  ✅ or 🔄 on `main`. A milestone number had stopped meaning an order.
- This is the second time. 1.0.2 was written and never published, folded into
  v1.1 (2026-08-23), for the same reason.
- Public magnetic API is on `main` already: `solve_magnetic`,
  `MagneticSolution`, `MagneticTrial`, `MomentRow` (declared provisional in
  `tests/api_surface.py`), and `MagneticOnset`, `MagneticTrajectory` from
  `rietx.schemas.sequential` (not declared provisional).

**What reads a milestone token.** The `Milestone:` line of every WP file;
`.claude/hooks/wp_index.py` (`SECTION_RE` and the group lookup) and the
generated `docs/wp/README.md`; ROADMAP's milestone table and `###` headings;
`tests/test_docs_consistency.py` (a ✅ row links a record, and the index is the
generator's output); protocol rules 5 and 6; `wp/TEMPLATE.md`'s numbering and
vocabulary; `/wp-handover` step on the narrative; root CLAUDE.md on
`pyproject.version`. GitHub has no milestones and no labels on this repo.

**Who was told a number.** Collaborators read them in public threads, and
the threads cannot be edited after the fact: #286 and #426 ("v1.6", magnetic),
#561 ("v1.8", rigid bodies) and #562 ("v1.9", structure solution). The two
open contributor PRs (#680, #675) touch no planning document.

## Non-goals

- Cutting the release. That is `docs/RELEASING.md`, and it also owes the notes'
  framing: `releases/1.5.1.md` calls itself a bug-fix release, and the file
  stays where it is until the cut (36 links in 21 files reach it, and every
  branch in flight appends to it).
- A release cadence. Which trigger cuts a release (an age, a size, a date) is
  the maintainer's decision, and this WP removes only what made one wait.
- History. A shipped record, a handover log and a closed WP's status text say
  what was true when they were written, so "v1.7" stays in them.
- Re-declaring the magnetic schema types provisional. That belongs to the
  release cut, which reads the whole public surface once.

## Tasks

- [x] Accept a named milestone token in `wp_index.py`, and let a ✅ row link
      a named record in `test_docs_consistency.py`.
- [x] Rename v1.6-v1.9 to `magnetic`, `rietview`, `rigid-bodies`,
      `structure-solution`: WP headers, ROADMAP headings and table, the index
      regenerated, an old-to-new map where a collaborator will look.
- [x] Split `milestones/v1.6.md`: the magnetic scope and acceptance move to
      `milestones/magnetic.md`, and v1.6 stays the record of release 1.6.
- [x] Rewrite protocol rules 5 and 6, `wp/TEMPLATE.md`, `/wp-handover`'s
      narrative step and root CLAUDE.md's version sentence for the split.
- [x] Fix the two user-facing sentences that name an unreleased version
      ("pre-1.5.1" in the manual, "Before 1.5.1" in the skill).
- [ ] Draft one comment per collaborator thread (#286, #426, #561, #562),
      batched for the maintainer to approve.

## Acceptance

`.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_skill.py`
green, and `python3 .claude/hooks/wp_index.py --check` (or the test that
holds the index equal to the generator) clean.

## Handover log

- **2026-10-03** — A late milestone no longer holds back a release. The four
  open or queued milestones now carry names (magnetic, rietview, rigid-bodies,
  structure-solution) instead of v1.6 to v1.9, and a release takes its number
  when it is cut. The next one is 1.6, and it ships whatever `main` holds at the
  cut. Nothing was released, and no history was rewritten: shipped records,
  handover logs and closed WPs still say "v1.7" where that was true.

  *Why filed:* no open WP owned release ordering; 1507 owns the index
  generator, not the milestone vocabulary.

  *Done.* `wp_index.py` accepts a lowercase name as a section token (the
  guard survives because a prose heading opens with a capital). 21 WP headers
  were renamed and the index regenerated. `milestones/v1.6.md` is now the
  record of release 1.6. Magnetic's scope, its order paragraph and its 11
  acceptance rows moved to `milestones/magnetic.md` unchanged, and the order
  paragraph left ROADMAP to keep it at its 588-line cap (587 now). Protocol
  rules 5 and 6, `TEMPLATE.md`, `/wp-handover` step 8 and root CLAUDE.md say
  the new rule. "pre-1.5.1" in the manual and "Before 1.5.1" in the skill now
  say 1.5.0 and earlier, which stays true whatever the cut is numbered. The
  staged notes' header says it ships as 1.6.0.

  *Deliberately not done.* `releases/1.5.1.md` keeps its name: 36 links in
  21 files reach it, and every branch in flight appends to it, so the cut
  renames it. `MagneticOnset` and `MagneticTrajectory`
  (`rietx.schemas.sequential`) are public and not declared provisional; that
  belongs to the cut's read of the public surface. The `v1.5.x` section is
  closed to new WPs rather than renamed, since its three WPs are ✅ history.
  No cadence was chosen.

  *Gotchas.* The worktree guard refuses a heredoc with a loop; scripts in
  the scratchpad ran instead. `tests/test_skill.py`'s `api.md` cap fails on
  `main` too (39 519 B against 39 500), so it is not this branch's.

  *Next.* (1) The maintainer approves or edits the drafted comments for #286
  (covers #426) and one-liners for #561 and #562; post them, then tick task 6
  and close. (2) Choose a release trigger, an age or a size of the staged
  notes. (3) Cut 1.6.0 by `docs/RELEASING.md`, which owes: renaming the notes
  file, rewriting its "bug-fix" framing, declaring the magnetic schema types
  provisional, and opening `milestones/v1.7.md` with `1.7.0.dev0`.
