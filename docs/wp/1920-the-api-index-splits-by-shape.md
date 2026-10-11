# WP-1920 — the API index splits by shape: another program's files go to `api-io.md`

Milestone: unscheduled · Status: ✅ 2026-10-11 — `api-io.md` split out (PR #906); one 39 000 B ceiling for every index
Track: The repo's own process
Depends on: —

## Goal

`references/api.md` has room again under its 40 kB truncation, because the
readers and writers for another program's files render to a generated
`references/api-io.md`. Each index is checked against its own ceiling, and a
name has an entry row in one index only.

## Context

Issue #808 (mustachefeeling, 2026-10-07) measured the cap and prototyped the
split. Root CLAUDE.md already states the rule: "a shape's entry points render
to a generated `api-<shape>.md`, never `api.md`". `api-figure.md` and
`api-magnetic.md` exist under it, as `TECHNIQUES` entries in
`docs/skill/make_api_index.py`. WP-1419 measured this seam on 2026-09-18 (§ In
plus § Out to `api-io.md`) and parked it as "not the chain's to carry". WP-1532
(⬜) records that "the split decision is due now". No WP owns the split itself.

**Re-checked 2026-10-11 at 6075319c (superseding the block below in
part):**

- `api.md` is 39 789 B against `API_INDEX_MAX_BYTES` = 39 800. WP-1930
  raised the ceiling from 39 700 for `StageResult.seeded` and
  `.floor_unseeded` (85 B), leaving 200 B to the 40 kB truncation. WP-1543
  then took 7 B of over-run back by trimming the `read_gsas_prm` sentence in
  the In prose, one of the 16 names the prototype moves.
- PR #815 merged on 2026-10-08. `write_topas_inp(instrument=, pattern=)` is
  in the index, and its docstring's first line is now "Write."
- #801 merged. `RigidBody`, `BodyOrigin` and `BodyTorsion` are exported and
  have no entry row in any index: `TECHNIQUE_FIELDS` defers
  `Phase.rigid_bodies` and `ParameterRow.body`, and
  `tests/api_surface_deferred.txt` defers the classes' fields. TOF T-1 has
  not landed. `read_gsas_tof_iparm`, `TOFSource`, `ProfileTOF` and
  `IncidentSpectrum` are not on `main`.
- The prototype cherry-picks onto `main` with conflicts in
  `make_api_index.py` (the In prose WP-1543 trimmed) and `skill_caps.py`
  (WP-1930's raise). Resolved to the prototype's side and regenerated,
  `api.md` is 33 292 B and `api-io.md` 7 447 B. Of the sections left in
  `api.md`, Series, history, projects is 3 306 B.

**Checked against the tree at 5d1f5f67:**

- `api.md` is 39 697 B against `API_INDEX_MAX_BYTES` = 39 700
  (`tests/skill_caps.py:136`). The comment above it ends "the next raise is
  the split". The issue measured 39 694 B at 65ec59e8.
- Its sections: header 1 022 B, In 9 362, The model objects 7 101, Refining
  5 651, The four answers 6 373, The report 2 682, Series, history,
  projects 3 306, An unknown phase 1 682, Out 2 518. These match the issue
  to within 5 B per section.
- `caps()` gives every `api*.md` the one ceiling, so a second index needs no
  list edit today and would inherit `api.md`'s number.
- PR #815 (open) lands `api.md` at exactly 39 700 B by shortening a
  docstring's first line.

**The prototype.** Commit 80bac374 on `mustachefeeling/rietx` branch
`skill/api-index-split`, on 65ec59e8. It adds an `io` entry to `TECHNIQUES`
holding 16 names and their prose verbatim ("A recipe or an instrument file",
"Another program's whole refinement"). `api.md`'s In and Out keep one pointer
sentence each. `skill_caps.py` gets `API_INDEX_CEILINGS` per index and
`API_TECHNIQUE_INDEX_MAX_BYTES` = 39 000 for any other `api-<shape>.md`.
`test_skill.py` gains a check that no name has entry rows in two indexes,
and runs the dotted-name check over every technique index. `SKILL.md`'s
routing row and §1 name `api-io`, and the body shrinks 3 B. Its numbers on
the prototype: `api.md` 33 208 B and `api-io.md` 7 436 B; the fast suite on
Linux 8634 passed, 125 skipped. Trial merges with #801, #802, TOF T-1 and R9
are reported clean.

**Why this cut and not another** (the issue's table). A split by size or
alphabet leaves a reader opening both halves for a name not yet met. A
two-level index costs a typical fit four or five reads. The pattern readers
stay in `api.md`, because nearly every fit needs one. The cut buys about 40
days at the measured 100-250 B a day. The issue names the next seam:
series, history and projects (3.3 kB), routed by `SKILL.md` §9 and §9b.

## Non-goals

- Raising `API_INDEX_MAX_BYTES` again. It is 300 B under the 40 kB
  truncation.
- The rigid-body index (`api-bodies.md`): WP-1812.
- WP-1532's fourteen rows. They land after this, in whichever index holds
  their name.

## Tasks

- [x] **Decision (maintainer, 2026-10-11):** #808's three questions, plus
      who lands it. (1) `api-io.md` is the first cut and the name.
      `api-series.md` waits until `api.md` nears its ceiling again. (2) Every
      `api*.md` gets one ceiling, 39 000 B, the 1 kB margin under the 40 kB
      truncation `api.md` started from. The per-index table the prototype
      added is then unneeded. (3) Each held-back name goes to its shape's
      index. `read_gsas_tof_iparm` leaves `SKILL_EXCLUDED_VERBS` for a row in
      `api-io.md`. The TOF classes go to an `api-tof.md` and the rigid-body
      classes to `api-bodies.md`. The first PR that documents each set creates
      its index, without waiting for WP-1812. An everyday field whose type
      grows (`Instrument.source` accepting a `TOFSource`) still renders in
      `api.md`. A field the technique adds to an everyday type follows
      `TECHNIQUE_FIELDS`. (4) This WP lands the prototype, cherry-picked
      so mustachefeeling stays the commit's author.
- [x] The `io` technique in `make_api_index.py`, the one 39 000 B ceiling in
      `skill_caps.py`, and `SKILL.md`'s routing row (the prototype's
      commit, cherry-picked onto `main` after #815)
- [x] Tests: every index against the ceiling; one entry row per name;
      the dotted-name check over every index
- [x] Skill: this WP is the skill change; `rietx skill --install . --copy`
      re-syncs the two committed copies

## Acceptance

`python -m tests.skill_caps` exits 0 with `api.md` at least 5.5 kB under its
39 000 B ceiling, and every name in the old `api.md` has exactly one entry row across
the indexes.

```sh
.venv/bin/python -m tests.skill_caps
.venv/bin/python -m pytest tests/test_skill.py tests/test_skill_claims.py tests/test_skill_surface.py tests/test_docs_consistency.py tests/test_manual_api.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #808 and the prototype commit 80bac374 (mustachefeeling/rietx).
- WP-1419 § the parked split (the seam measured 2026-09-18); WP-1532's
  inherited note from WP-1510; WP-1812 (`api-bodies.md`).

## Handover log

- **2026-10-11** — closed. The skill's API index can grow again. It had
  11 bytes of room, and pull requests were shortening docstrings to fit. It
  now has 5.7 kB. The readers and writers for other programs' files moved to
  their own generated index, which an agent opens only with such a file in
  hand. The maintainer settled #808's three questions and chose to land the
  reporter's commit here. Where the held-back time-of-flight and rigid-body
  names go is decided too, so those branches no longer wait on this file.

  *Done.* Four commits on top of the claim and the findings re-check.
  - The decision (task 1), recorded in Tasks with the maintainer's four
    answers. Every recommended option was taken.
  - mustachefeeling's 80bac374, cherry-picked as 2732f967 with its author
    kept. It had two conflicts. The moved `read_gsas_prm` sentence takes
    WP-1543's wording, and `skill_caps.py` kept WP-1930's 39 800 beside the
    split's history.
  - 3040c07b applies answer 2. `API_INDEX_MAX_BYTES` is 39 000 for every
    `api*.md`, and the per-index table (`API_INDEX_CEILINGS`,
    `API_TECHNIQUE_INDEX_MAX_BYTES`, `api_index_ceiling`) and its test are
    gone. The generator's docstring records answer 3. The `TECHNIQUE_FIELDS`
    comment says the first PR documenting rigid bodies creates
    `api-bodies.md`.
  - a6def80b, the code review's fixes (below).
  - Inherited pruned on arrival. WP-1543's note (`api.md` 39 789 of 39 800 B)
    was still true and folded into Context's 2026-10-11 re-check.

  *Measured* (`[dev]` venv, darwin arm64, Python 3.12).
  - `api.md` 39 789 → 33 292 B, `api-io.md` 7 447 B, `SKILL.md` body
    16 950 → 16 947 B. `python -m tests.skill_caps` exits 0. All 118 names in
    `main`'s `api.md` have exactly one entry row across the four indexes.
  - The acceptance selection (five files): 257 passed.
  - Fast suite: 9109 passed, 178 skipped, 1 xfailed and 1 failed, in 6:23,
    with no other suite running at its start. The failure was
    `test_the_wp_index_is_the_generators_output`, run before this entry
    regenerated the index. It passes after.
  - `tests/test_skill.py` collects 167 cases against `main`'s 158, so +9.
    Five reference-file parametrisations gain an `api-io.md` case. The
    dotted-name check runs over four indexes instead of one (+3), and the
    duplicate-row check is new (+1). No new skip. `tests.added_test_times`
    puts the two added tests at 0.04 s together, one run on this machine.
  - No full suite. The change touches the skill's prose, its generator and
    its tests, and can move no measured number.

  *Code review* (`/code-review high --fix`, seven findings). Fixed four. The
  duplicate-row gate read `rx.X` and `rietx.X` as two names. The new
  dotted-name test copied the old one, and is now one test over every index
  (`test_every_dotted_name_in_the_api_indexes_resolves`). This file had
  `api-io.md` at 7 465 B for 7 447. A docstring sentence is split. Declined
  three:
  - `SKILL.md`'s routing row names reading and five extensions, while
    `api-io.md` also holds the writers, the `.instprm` pair and the recipe.
    Widening the row grows a body that is over its token budget. Every
    session loads `api.md` first, and its In and Out prose point at
    `api-io.md`.
  - `api-io.md` renders none of the readers' return types (`ProjectModel`,
    `Recipe`, the per-format models). `api.md` did not render them before the
    split either, so the gap predates this WP.
  - `api.md` points at `api-io.md` from In and again from Out. Out is where a
    reader looking for a writer goes.

  *Not done.* `api-series.md` waits, by decision. The reply to #808 is
  drafted and waits for the maintainer to post it.

  *Forward references.* WP-1927 learns where T-1's names go, and its priority
  is re-dated. WP-1812 and WP-1809 learn that `api-bodies.md` need not wait
  for WP-1812. WP-1532 learns the split landed, which supersedes WP-1510's
  note there.

  Next, outside this WP. T-1 (WP-1927) rebases onto `main` once #906 merges,
  and creates `api-tof.md`. The first rigid-body PR that documents its
  classes, possibly #888, creates `api-bodies.md`. The next split is series,
  history and projects (3.3 kB), due when `api.md` nears 39 000 B again.

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #808).
  Checked against the tree at 5d1f5f67: `api.md` 39 697 of 39 700 B, its
  sections as the issue measured, one shared ceiling for every `api*.md`.
  No open WP owns it: WP-1419 parked the split as not its own, WP-1532 (⬜)
  waits on it, WP-1812 (⬜) adds a later index, and WP-1907 (✅) closed.
  Next: the maintainer's decision, then the contributor's commit as a PR.
