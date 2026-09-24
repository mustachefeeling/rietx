# WP-1450 — a collaborator's dataset stays unnamed

Milestone: unscheduled · Status: 🔄 2026-09-23 — CONTRIBUTING's rule landed (PR #435); the
redaction itself is the reporter's PR #438
Depends on: —
Priority: P1 2026-09-23 — the data owner asked; land it before 1.5.1 is cut, because the wheel ships `diagnostics.py` and `topas.py`; comments and docstrings only, so the job is small

## Goal

No file on `main` identifies a collaborator's unpublished in-situ neutron
dataset. That means no run number, file name, compound, in-situ context,
count level, instrument name or wavelength. Every threshold and the shape
of the evidence behind it stay.

## Context

Issue #417 (2026-09-22). Commit `687a8002` (2026-08-24, the `signal_cutoffs`
work) described a collaborator's unpublished neutron scan in identifying
detail. The data owner has since asked that nothing identifying, and no
number derived from those files, be public. The repo's rule is the same:
nothing without a peer-reviewed citation is public. The 2026-09-18 audit
applied it to the TOPAS and FullProf corpora (commits `2b4b18a8`,
`5306a403`, `35eabb73`). Those files are now cited by number, and the map
lives in the private `yue-here/rietx-corpus-map`.

**This file names none of the strings it removes.** It merges to `main`, so
each site is given by file and line, and each string by its role. The
search patterns live in the private map (see Acceptance).

**The sites**: thirty lines, checked against the tree at `644dff84`.

- `src/rietx/background/diagnostics.py`: 299, 315, 318, 339, 347, 479, 584,
  882-884, 893 and 940. They hold the run number, the compound, the file
  name, the point count and range, the count level, the instrument name
  and the wavelength.
- `src/rietx/io/projects/topas.py:427-428` and
  `tests/test_projects_topas.py:2597`, `:2598`, `:2601` and `:2603`. These
  use the compound as the example `#define` token. The test is about `\w+`
  against a hyphenated token, so any synthetic hyphenated name of the same
  shape serves.
- `docs/manual/using/results.md:578` and `:579`.
- `docs/releases/1.2.0.md:121`.
- `tests/test_background_auto.py:1307`, `:1311` and `:1341`.
- `docs/wp/1415-a-sigma-column-smaller-than-root-y.md`: 105, 115, 170, 224,
  385 and 404 on `644dff84`. The 2026-09-23 triage's fold into that file
  moves the last four to 180, 234, 395 and 414. **Edit these in the same
  commit, with the same wording.** A PR that only lists them leaves the
  names on `main`.

**What stays**: the fact that the thresholds were measured on real in-situ
neutron data plus the public D1B fixture, the shape of the evidence (a
leading cliff of a fixed factor over a few degrees, a trailing edge at a
high fraction of the interior), and every threshold constant. At
`diagnostics.py:893`, keep the d-spacing (d ≈ 30 Å), so the argument holds
without the wavelength. **What goes**: the run number, the file name, the
compound and its in-situ context, the count level, the instrument name, the
wavelength, and any measured percentage quoted as a number rather than as
the argument's shape. The replacement wording is "a private
constant-wavelength neutron PSD scan". Nothing in the code reads any of it.
The synthetic fixtures in `test_background_auto.py` stand on their own, as
its comment at 1307 says.

**The reporter offers the PR** (docstrings and comments, the fast suite and
the three-way skill mirror check). **Decided 2026-09-23**, answered on
#417: the offer is accepted, with the TOPAS sites added, and the WP stays
P1. **Widened 2026-09-23**
([#417 comment](https://github.com/yue-here/rietx/issues/417#issuecomment-5795538371)):
the data owner asked for the instrument name and the wavelength to go too,
and the WP-1415 file is edited in the same PR.

## Non-goals

- **Rewriting git history. Declined 2026-09-23.** The 2026-09-18 audit made
  the same call for another dataset. A rewrite of `main` would not reach
  GitHub's copies either: `refs/pull/109/head` still points at the fork's
  commits, and only GitHub Support can purge those. The strings also stay in
  every wheel released since 1.2.0.
- Other datasets. A sweep for other unpublished names belongs to the
  2026-09-18 audit's method, not this WP. Say what was not swept.

## Tasks

- [ ] The patterns file exists in `yue-here/rietx-corpus-map`: one pattern
      per role (the run number, the compound, the instrument name, the
      wavelength), as agreed on #417.
- [ ] Genericise every site above, keeping each threshold, its shape and
      the d-spacing at `diagnostics.py:893`.
- [ ] Where a record must say that a string was removed, name its role and
      never its value, in commits, the PR body and the handover alike.
- [ ] If the corpus map should record the replaced numbers, add them there,
      never to this tree.
- [ ] Tests: none new. The fast selection passes unchanged, since no
      behaviour moves.
- [ ] Skill: none. No skill file names the dataset (checked at `644dff84`).

## Acceptance

Zero hits. On `644dff84` the same patterns hit exactly the thirty sites
above and nothing else. The `'*.py' '*.md'` pathspecs keep a numeric data
file from matching the wavelength pattern by accident.

```sh
git grep -n -f <patterns file from yue-here/rietx-corpus-map> -- '*.py' '*.md'   # zero hits
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #417.

## Handover log

- **2026-09-23** — (reconstructed post hoc on 2026-09-24, from the commit's
  own diff and message; the session that made it left no entry) CONTRIBUTING
  now states for every file the rule this WP applies to one dataset: a
  dataset is named in the repository only if it is a public download or has a
  peer-reviewed citation, and private data is described by its kind while the
  number it gave is kept. Until then a human contributor met the rule only in
  CONTRIBUTING's section on the skill's rows, and CLAUDE.md had carried it
  since 2026-09-18. None of the thirty sites is touched by it; removing them
  is the reporter's pull request, still open.
  - *Done*: `bc0c25f`, merged in PR #435. `CONTRIBUTING.md` § Licensing gains
    a paragraph, "Data you cannot publish": the rule; what it covers (a sample
    or compound name, a run or proposal number, a file name, the instrument and
    conditions, a specimen property read off a refinement); that a number the
    code depends on may still come from private data; and a pointer to
    § The agent skill, which draws the same line. The reason is the commit
    message's: the rule reached CLAUDE.md three weeks after the leak it
    answers, and a human contributor reads CONTRIBUTING. It is adjacent to the
    Goal rather than one of the Tasks, so no box is ticked.
  - *Not in the record*: whether that session checked the paragraph's wording
    against § The agent skill or the CLAUDE.md clause. The diff does not say.
  - *State at the repair (2026-09-24)*: PR #438, from the reporter's fork and
    titled `WP-1450:`, is open and edits all seven files Context lists. It does
    not touch this file. Whether it reaches zero hits needs the patterns file
    of task 1, which lives in the private map, and was not checked here.
  - Next: review PR #438 against the Acceptance grep, then merge it before
    1.5.1 is cut, as Context requires. On merge, tick tasks 2 to 6 from what
    it did, record the replaced numbers in the private map if task 4 wants
    them, and close the WP.
- **2026-09-23** — created, from the 2026-09-23 issue triage (issue #417).
  Checked against the tree at `644dff84`: every site the issue lists
  reproduces, and the issue's own search finds two more in the TOPAS reader
  and its test. Widened the same day to the instrument name and the
  wavelength, which brings the count to thirty. Next: the reporter's PR.
