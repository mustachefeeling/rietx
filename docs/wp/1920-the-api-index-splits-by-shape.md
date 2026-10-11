# WP-1920 — the API index splits by shape: another program's files go to `api-io.md`

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: —
Priority: P2 2026-10-08 — the decision other WPs wait on: `api.md` is 3 B under its ceiling, and PR #815, #801's follow-ups and TOF T-1 each hold back names to fit

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

### Inherited

- **2026-10-10, from WP-1543: `api.md` is 39 789 B against a ceiling of
  39 800.** `read_gsas_prm` gained `profile_set=`, which put the generated
  index 7 B over. WP-1543 paid for it by trimming the hand-written
  `read_gsas_prm` sentence in `make_api_index.py`'s In prose, and did not
  split the index. That sentence is one of the 16 names the prototype moves
  to `api-io.md`.

## Non-goals

- Raising `API_INDEX_MAX_BYTES` again. It is 300 B under the 40 kB
  truncation.
- The rigid-body index (`api-bodies.md`): WP-1812.
- WP-1532's fourteen rows. They land after this, in whichever index holds
  their name.

## Tasks

- [ ] **Decision (maintainer):** #808's three questions. (1) Is `api-io.md`
      the first cut and the name, and does `api-series.md` come in the same
      change or wait? (2) Does `api.md`'s ceiling stay at 39 700 or return to
      39 000? (3) After the split, does `read_gsas_tof_iparm` leave
      `SKILL_EXCLUDED_VERBS` for a row in `api-io.md`, and do the rigid
      track's deferred names wait for `api-bodies.md`?
- [ ] The `io` technique in `make_api_index.py`, the per-index ceilings in
      `skill_caps.py`, and `SKILL.md`'s routing row (the prototype's
      commit, rebased onto `main` and over #815 if that lands first)
- [ ] Tests: each index against its own ceiling; one entry row per name;
      the dotted-name check over every index
- [ ] Skill: this WP is the skill change; `rietx skill --install . --copy`
      re-syncs the two committed copies

## Acceptance

`python -m tests.skill_caps` exits 0 with `api.md` at least 6 kB under its
ceiling, and every name in the old `api.md` has exactly one entry row across
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

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #808).
  Checked against the tree at 5d1f5f67: `api.md` 39 697 of 39 700 B, its
  sections as the issue measured, one shared ceiling for every `api*.md`.
  No open WP owns it: WP-1419 parked the split as not its own, WP-1532 (⬜)
  waits on it, WP-1812 (⬜) adds a later index, and WP-1907 (✅) closed.
  Next: the maintainer's decision, then the contributor's commit as a PR.
