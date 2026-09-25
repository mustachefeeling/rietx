# WP-1450 — a collaborator's dataset stays unnamed

Milestone: unscheduled · Status: 🔄 2026-09-24 — the redaction landed (PR #438); the two private-map tasks and the map-pattern acceptance grep remain, and are the maintainer's
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
- [x] Genericise every site above, keeping each threshold, its shape and
      the d-spacing at `diagnostics.py:893`. **PR #438 (`605a0e50`), plus
      the five sites and three numerals its review found beyond the list.**
- [x] Where a record must say that a string was removed, name its role and
      never its value, in commits, the PR body and the handover alike.
      **#438's commit message, body and thread do; so does this file.**
- [ ] If the corpus map should record the replaced numbers, add them there,
      never to this tree.
- [x] Tests: none new. The fast selection passes unchanged, since no
      behaviour moves. **Only the TOPAS test's example token changed.**
- [x] Skill: none. No skill file names the dataset (checked at `644dff84`,
      and again on the merged tree, all three copies).

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

### 2026-09-24 — the redaction landed from the reporter's PR

`main` no longer names the collaborator's dataset. That means no run number,
compound, instrument, wavelength, file name or count level, and no number
measured on it. Every threshold and the shape of the evidence behind it
stay. It landed as the reporter's PR #438, reviewed over two rounds and
merged before 1.5.1 is cut, as the Priority line asks. What is left needs
the private map, which this session could not read.

- *Done*: PR #438, merged as `605a0e50`. Issue #417 was closed by hand
  with a comment naming the PR, because the PR carried no closing keyword.
  The thirty listed sites are done. Review round 1 found five more the list
  missed: the module docstring's σ²/y level; `SignalCutoff`'s counts, width,
  floor fractions and levels; and the manual's window, three before/after
  pairs and σ²/y level. The contributor's own derived-number search found
  three numerals beside them. The WP-1415 file's six lines are rewritten in
  the same commit, as Context required. The TOPAS test's token is a synthetic
  hyphenated name of the same shape. Tasks 2, 3, 5 and 6 are ticked.
- *Checked, and how*: the identifier search used one pattern per role,
  taken from the strings `main` carried. **It is not the map's patterns
  file**, because cloning `yue-here/rietx-corpus-map` was refused in this
  session. Those patterns hit 33 lines on `main` at `54a049d2` and none on
  the merged tree, across every tracked text file including the three skill
  copies and both merged commit messages. A derived-number sweep then took
  the 113 distinct numbers in the removed text. The 24 that recur in added
  lines are all package constants, sweep coordinates, public D1B figures,
  the synthetic fixture's own parameters, or issue and WP numbers.
  Fast suite on the merged tree: 1 failed, 6067 passed, 101 skipped, the
  failure being `test_telemetry`'s root-only case. The full `-m slow` suite
  ran once, on `main` + #425 + #438 + #433: 2 failed, 193 passed,
  9 skipped. Both failures were load, neither this change's
  (WP-1415's entry of this date has the detail).
- *Gotcha*: #425, the WP-1415 PR, first called the second private set
  public and named it. Its round 2 aligned it with this WP's wording before
  either merged, so the two now describe it the same way.
- *Not in scope, recorded*: issue #417's own body quotes the run number and
  the compound in its search line, and #274's body names the instrument.
  Neither is a file on `main`. Editing an issue body is the maintainer's call.
- *Follow-up the reporter offered*: `CUTOFF_ONSET_FRACTION`'s comment says
  "both files agree … within half a degree" of the TOPAS window. The removed
  sweep shows that holds at the leading end only. The review asked for it to
  be reworded like `results.md` in a separate PR.
- *Next*: run the Acceptance grep with the map's patterns file (task 1), and
  record the replaced numbers in the map if task 4 wants them. Then close
  the WP.

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
