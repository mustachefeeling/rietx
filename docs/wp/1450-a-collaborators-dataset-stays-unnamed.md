# WP-1450 — a collaborator's dataset stays unnamed

Milestone: unscheduled · Status: ⬜
Depends on: —
Priority: P1 2026-09-23 — the data owner asked, and the staged 1.5.1 would ship the names in the wheel again; comments and docstrings only, so the job is small

## Goal

No file on `main` names the collaborator's unpublished ILL D20 in-situ
dataset: no run number, file name, compound, in-situ context or absolute
count level. Every threshold and the shape of the evidence behind it stay.

## Context

Issue #417 (2026-09-22). Commit `687a8002` (2026-08-24, the `signal_cutoffs`
work) quoted a collaborator's unpublished neutron scan in identifying
detail. The data owner has since asked that nothing identifying, and no
number derived from those files, be public. The repo's rule is the same:
nothing without a peer-reviewed citation is public. The 2026-09-18 audit
applied it to the TOPAS and FullProf corpora (commits `2b4b18a8`,
`5306a403`, `35eabb73`), which are now cited as `archive file N` and
`corpus file N`, with the map in the private `yue-here/rietx-corpus-map`.

**The sites**, checked against the tree at `644dff84` with
`git grep -n -e 306774 -e SrFeO -- src docs tests`:

- `src/rietx/background/diagnostics.py`: the `#:` comments at lines 315,
  318 and 347, the docstring at 479, and `signal_cutoffs`' docstring at
  882-884 (file name, point count, range, interior level 1.19e8).
- `docs/manual/using/results.md:578`.
- `docs/releases/1.2.0.md:121`.
- `tests/test_background_auto.py:1307` and `:1341`.
- **Two the issue did not list**, found by its own grep:
  `src/rietx/io/projects/topas.py:427-428` and
  `tests/test_projects_topas.py:2597-2603`, which use `SrFeO3-x_fit` as the
  example `#define` token. The test is about `\w+` against a hyphenated
  token, so any synthetic hyphenated name of the same shape serves.
  `tests/data/powderline/example_LaB6/input.json:4608` matches `306774`
  inside a float and is not a site.

**What stays** (the issue's list): the instrument class and wavelength ("an
ILL D20 constant-wavelength neutron scan, λ = 2.42 Å"), the shape of the
evidence (a leading cliff of a fixed factor over a few degrees, a trailing
edge at a high fraction of the interior), and every threshold. **What
goes**: the run number, the file name, the compound and its in-situ
context, the absolute count level, and a measured percentage quoted as a
number rather than as the argument's shape. Nothing in the code reads any
of it. The synthetic fixtures in `test_background_auto.py` stand on their
own, as its comment at 1307 says.

**The reporter offers the PR** (docstrings and comments, the fast suite and
the three-way skill mirror check). **Decided 2026-09-23**, answered on
#417: the offer is accepted, with the two extra sites named, and the WP
stays P1.

## Non-goals

- **Rewriting git history.** The strings stay in history and in every
  wheel released since 1.2.0. A rewrite of `main` needs the two
  branch-protection toggles only the maintainer can set. Whether to do one
  is the maintainer's call, recorded here if taken.
- Other datasets. A sweep for other unpublished names belongs to the
  2026-09-18 audit's method, not this WP. Say what was not swept.

## Tasks

- [ ] Genericise every site above, keeping each threshold and its shape.
- [ ] Re-run the grep, plus the run numbers' and file stems' other spellings,
      and record zero hits in the handover.
- [ ] If the corpus map should record the replaced numbers, add them to
      `yue-here/rietx-corpus-map`, never to this tree.
- [ ] Tests: none new. The fast selection passes unchanged, since no
      behaviour moves.
- [ ] Skill: none. No skill file names the dataset (checked at `644dff84`).

## Acceptance

```sh
git grep -n -e 306774 -e SrFeO -- src docs tests examples   # no hits, bar the float in input.json
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #417.

## Handover log

- **2026-09-23** — created, from the 2026-09-23 issue triage (issue #417).
  Checked against the tree at `644dff84`: every site the issue lists
  reproduces, and the issue's own grep finds two more in the TOPAS reader
  and its test, listed in Context. Next: accept the reporter's PR offer, or
  do it in one session.
