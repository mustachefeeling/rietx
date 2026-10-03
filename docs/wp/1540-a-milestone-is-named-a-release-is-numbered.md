# WP-1540 — a milestone is named, a release is numbered

Milestone: unscheduled · Status: 🔄 2026-10-03 — filed and started the same day
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

- [ ] Accept a named milestone token in `wp_index.py`, and let a ✅ row link
      a named record in `test_docs_consistency.py`.
- [ ] Rename v1.6-v1.9 to `magnetic`, `rietview`, `rigid-bodies`,
      `structure-solution`: WP headers, ROADMAP headings and table, the index
      regenerated, an old-to-new map where a collaborator will look.
- [ ] Split `milestones/v1.6.md`: the magnetic scope and acceptance move to
      `milestones/magnetic.md`, and v1.6 stays the record of release 1.6.
- [ ] Rewrite protocol rules 5 and 6, `wp/TEMPLATE.md`, `/wp-handover`'s
      narrative step and root CLAUDE.md's version sentence for the split.
- [ ] Fix the two user-facing sentences that name an unreleased version
      ("pre-1.5.1" in the manual, "Before 1.5.1" in the skill).
- [ ] Draft one comment per collaborator thread (#286, #426, #561, #562),
      batched for the maintainer to approve.

## Acceptance

`.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_skill.py`
green, and `python3 .claude/hooks/wp_index.py --check` (or the test that
holds the index equal to the generator) clean.

## Handover log
