# WP-1507 — the WP index is read off the WP files

Milestone: unscheduled · Status: 🔄 2026-09-27 — claimed by @yue-here
Track: The repo's own process
Depends on: — (1506 soft: the docs job it adds runs this WP's tests)
Priority: P2 2026-09-27 — was P4: the maintainer raised it the day it was filed; 17 of 25 conflicted syncs in six weeks hit ROADMAP.md, and 46 PRs in a month edited only its cap

## Goal

The WP tables and the in-flight list are generated from each WP file's
Milestone, Status, Priority and Depends lines. Filing, starting, closing or
re-rating a WP then edits only that WP's file. ROADMAP.md keeps the prose,
which changes when a milestone opens or ships.

## Context

**Measured 2026-09-27.**

- From 2026-08-27 to 2026-09-27, 232 PRs merged. `docs/ROADMAP.md` changed
  in 144 of them (62%). `tests/test_docs_consistency.py` changed in 82, and
  46 of those changed nothing but a `SIZE_CAPS` number and its diary comment.
- Every two-parent merge since 2026-08-15 was replayed with `git merge-tree`
  (method in References). 25 conflicted: 17 on ROADMAP.md, 7 on
  `test_docs_consistency.py` (the cap line), 3 on the GUI dist, 2 on
  `SCHEMA_VERSION`, 5 on WP files and 1 on the skill (in all three copies).
- Of the 17 ROADMAP conflicts, 7 were in the WP tables. Two branches had
  inserted or edited adjacent rows, which git reports as a conflict even
  when the rows differ. The other 10 were in Current focus, which Session
  protocol step 5 rewrites at every close.
- Local reflogs show 6 merges and no rebases, so the replay sees most syncs.
  It is still a floor: a rebase in a worktree since deleted leaves nothing.
- Today's instance: two sessions each added a row within the one line of
  headroom and overran it together. f90d257d raised the cap from 854 to 856
  after both had merged.

**The rows copy a fact that already has an authority.** Each WP file carries
`Milestone:`, `Status:`, `Priority:` and `Depends on:` lines. Five tests in
`test_docs_consistency.py` hold the ROADMAP rows equal to them:
`test_wp_files_and_roadmap_rows_are_a_bijection`,
`test_roadmap_glyph_mirrors_the_wp_status_line`,
`test_index_section_mirrors_the_wp_milestone_line`,
`test_roadmap_status_cell_is_a_glyph_and_a_date` and
`test_roadmap_priority_cell_mirrors_the_wp_priority_line`. The copy is written
by hand at every start, close and re-rating, and a test catches the drift.
Root CLAUDE.md's rule for such a mirror is a projection computed from the
authority.

**Prior art.**

- `docs/VALIDATION.md` is generated, committed and asserted fresh by the
  suite. That is the house precedent for a committed generated file.
- `.claude/hooks/session_start.py` already derives the in-flight list from
  the WP files (`in_flight_wps`), not from ROADMAP.
- Python's PEP index (PEP 0) is generated from the PEP headers, and nobody
  edits it.
- GitHub renders a directory's `README.md` in its listing. A generated
  `docs/wp/README.md` would show the index to anyone browsing `docs/wp/`.

**Where the index lives: decided 2026-09-27 by the maintainer, option (a).**
The two options as they were put:

- (a) Committed, as `docs/wp/README.md`, asserted fresh like VALIDATION.md.
  Adjacent-row conflicts still happen, and they resolve by rerunning the
  generator. A merge driver (`docs/wp/README.md merge=wpindex` in
  `.gitattributes`, the command set in `.git/config` by the SessionStart
  hook) makes that automatic in a local merge. GitHub's web merge runs no
  custom driver, so a PR behind main is synced locally, as today.
- (b) Not committed. A script prints the index, and `/wp-start` and the
  SessionStart hook show it. There are no conflicts at all, and nothing in
  the repository shows the index on GitHub.

Recommended: (a). Contributors work on forks and see only GitHub, and the
index is how they see what is queued. It also follows VALIDATION.md.

**Current focus.** Its 60-line and 300-word caps stay. What changes is who
writes it. The in-flight list (🔄) and the next WPs by priority are generated
into the index. Current focus keeps the milestone-level prose, written when a
milestone opens or ships, and by `/issue-review` when a triage moves the
order. A close writes its narrative into the milestone record, which step 5
already does, and stops rewriting Current focus. `milestones/v1.4.md` changed
in 33 PRs and conflicted once. `releases/1.5.1.md` changed in 23 and never
conflicted. Neither needs a change.

**The cap.** `SIZE_CAPS["docs/ROADMAP.md"]` guards a file every session
reads. With the tables out, it measures prose only, and filing a WP no longer
moves it. The diary comment above `SIZE_CAPS` gains an entry at every bump,
always at the same place, which makes it a second conflict site. With the
per-row bump gone, it is written only when prose grows.

**Touchpoints.** `grep -rl ROADMAP .claude/` finds
`commands/wp-start.md`, `commands/wp-handover.md`, `commands/pr-review.md`,
`hooks/handover_owed.py`, `skills/issue-review/SKILL.md`,
`skills/issue-review/backlog.py` and `agents/pr-conformance.md`. Beyond
`.claude/`: ROADMAP § Session protocol steps 3 and 5, and the comment in
`wp/TEMPLATE.md` that says to keep the Status line and the ROADMAP row in
sync. A touchpoint that writes a row stops writing it. One that reads a row
reads the index.

### Inherited

**From [1506](1506-a-planning-doc-pr-runs-what-reads-it.md) (2026-09-27).**
PR #504 gives `ci.yml` a `changes` job. A PR whose files all match its
`PLANNING` pattern (`docs/wp/`, `docs/milestones/`, `docs/releases/`,
`ROADMAP.md`, `DESIGN.md`, `tests/test_docs_consistency.py`) runs only the
`docs` job. That job runs the four test files an audit hook saw reading those
paths. Three consequences reach this WP. A regenerated `docs/wp/README.md` on
its own stays a docs-only PR. The generator is code unless it sits inside the
pattern, so a PR that changes it runs the full matrix. And the freshness test
must live in one of the docs job's four files, or a docs-only PR skips it
until the nightly. `test_docs_consistency.py` and `test_workflow_hooks.py`
are both on the list.

## Non-goals

- The skill's byte caps race the same way (WP-1338, issue #247). A skill file
  cannot be generated away, so its policy stays there.
- `SCHEMA_VERSION` (6 bumps in the 30 days, 2 conflicts) and WP numbers (two
  collisions, 1436 and 1469) are shared counters of the same class. Both are
  left alone. The first is a compatibility policy. The second has had a
  duplicate-number test since 2026-09-27.
- Committing one skill copy with symlinks for the two harness directories.
  The skill conflicted in one merge in six weeks, and a Windows clone without
  `core.symlinks` would lose the skill.
- Release-note and milestone-narrative fragments (the towncrier pattern).
  Measured above, those files do not conflict.
- The GUI dist: WP-1313. CI: WP-1506.

## Tasks

- [x] The decision above, taken with the maintainer and recorded here:
      (a), committed as `docs/wp/README.md`, 2026-09-27.
- [x] A generator, stdlib only, sharing one header parser with
      `test_docs_consistency.py`. It writes the per-milestone tables and the
      in-flight and next-by-priority lists from the WP files.
- [x] ROADMAP.md: each table replaced by a link to its place in the index.
      Section prose stays under its milestone heading. Current focus keeps
      milestone prose only.
- [x] `test_docs_consistency.py`: the five mirror tests become one freshness
      test on the index. The ROADMAP cap counts what is left and is set once,
      with its diary entry. The Current focus caps are unchanged.
- [x] If (a): the merge driver and its SessionStart setup, tested in
      `test_workflow_hooks.py`. Two branches adding adjacent rows merge
      locally with no conflict markers.
- [x] The touchpoints above: commands, hook, issue-review skill,
      pr-conformance agent, Session protocol, TEMPLATE comment.
- [ ] Two weeks after landing, rerun the merge replay and report ROADMAP
      conflicts against this WP's baseline of 17 in six weeks.
- [x] Skill: none. This is the repo's planning process.

## Acceptance

- Filing, starting and closing a WP change no line of ROADMAP.md and no line
  of `test_docs_consistency.py`. Check this on the first three WPs after
  landing.
- The index equals the generator's output on the tree.

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_workflow_hooks.py
```

## References

- Merge replay: for each `git log --merges --since=<date> --format='%H %P' --all`
  line with two parents, `git merge-tree --write-tree --name-only --no-messages
  <p1> <p2>` exits 1 on a conflict and lists the conflicted paths after the
  tree id. The per-PR counts come from `git diff --name-only <m>^1 <m>` over
  `git log --merges --first-parent origin/main`.
- PEP 0: generated by `pep_sphinx_extensions` in the python/peps repository.

## Handover log

- **2026-09-27** — Created by a session the maintainer asked to find where
  the repo's merge drag comes from. Most ROADMAP conflicts come from a
  hand-kept copy of the WP headers and from rewriting Current focus at every
  close, and both can stop. The numbers above are that session's merge
  replay. Next: the maintainer's answer on where the index lives, then the
  generator.
