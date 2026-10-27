# WP-1991 — a site and its own image are one atom on every route

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-16 — a doubled composition with nothing firing, but only on a stored, hand-edited or code-built coordinate; a refined coordinate cannot drift there, and the CIF route already merges it

## Goal

A free atom within a fraction of an ångström of a special position counts
once in the cell on every route into a `Structure`, and says so, as a CIF
read already does.

## Context

Issue #1007 (mustachefeeling, 2026-10-16), found building #1005 (R6 of #561).

Reproduced at `138d55dc` with the issue's script (PbSO₄,
`tests/data/gsas2_pbso4.gpx`, Pnma; S2 on the mirror at y = ¼,
multiplicity 4; only S2's y moved; counted by
`rietx.optimize.qpa.phase_zmv`):

```
dy=0       S per cell = 4
dy=5e-05   S per cell = 4
dy=6e-05   S per cell = 8
dy=0.0001  S per cell = 8
```

Mechanism, from the issue and the code: `site_orbit`
(`crystallography/symmetry.py:867`) tests |R·x + t − x| against
`SITE_TOL = 1e-4` (line 766). A mirror's displacement is 2δy, so the
effective tolerance there is `SITE_TOL`/2. Past it the atom is general and
its image sits 2δy·b away (0.0006 Å at δy = 1e-4). The two images overlap
within the profile's resolution, the scale and Biso absorb the doubled
atom, and building a `Refinement` emits nothing.

What exists to reuse: #764/#765's twin merge in `structure_from_cif`
(`crystallography/cif.py:353`, `TWIN_DISTANCE = 0.02` Å at line 320). A
site whose own images lie closer than that is put on the special position
its orbit collapses to, with `CIF_SITE_TWINS_MERGED`. The gap is every other
route: a project file, a hand edit, a structure built in code. #1005 refuses
the rigid-body analogue (`RIGID_BODY_IMAGE_OVERLAP`, WP-1807, #876).

The reporter's comment proposes the fourth of their options: apply the twin
merge wherever an orbit is expanded, at the same distance, under a code
renamed off the `CIF_` prefix. A reader and a hand-built structure then
agree. They have said a PR follows.

Two constraints. `SITE_TOL` stays tight (#215: five-decimal files), so the
answer is the merge at a distance, never a looser snap. And the merge must
happen where a diagnostics channel exists: `ParameterTable` has none (root
CLAUDE.md, "a silent correction is a reader's to make").

### Inherited

- 2026-10-26 issue triage: #1088 shows this WP's Priority premise "a refined coordinate cannot drift there" holds only for a site already special. A general atom at occupancy ½ refined onto a mirror is snapped by the next stage compile, and the default plan's closing stage then returns 10 O per cell for 12 (10 of 16 noise draws). The mid-fit case is WP-2052's, outside this WP and PR #1014. Checked against the tree at c0e32ab29.

## Non-goals

- Changing `SITE_TOL`.
- The rigid-body case (WP-1807).

## Tasks

- [ ] Find every route that expands an orbit without the CIF reader's merge,
  and the one place a merge with a diagnostic can sit for all of them.
- [ ] Apply the twin merge there, renaming the code off `CIF_` (keep the old
  code readable for stored results, or record the break).
- [ ] Tests: the issue's δy sweep reads 4 S at every step, and the warning
  fires from δy = 6e-5 to the 0.02 Å boundary
- [ ] Skill: the reference row for the renamed code

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cif_sites_coincide.py -q   # plus the file this WP adds
.venv/bin/python -m ruff check src tests examples
```

## References

- International Tables for Crystallography Vol. A (site multiplicity).
- Issues #1007, #765, #876, #215.

## Handover log

- **2026-10-16** — created, from the 2026-10-16 issue triage (issue #1007).
  Checked against the tree at `138d55dc`: reproduced, S doubles from
  δy = 6e-5. No open WP owns it: WP-1807 owns a body on a special position,
  and WP-1324 and WP-1319, which touched site handling, are closed. The
  reporter has said a PR follows on option four. Next: review that PR
  against this file.
