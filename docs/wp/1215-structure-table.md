# WP-1215 — Model: the structure table

Milestone: v1.2 · Status: ⬜
Depends on: WP-1214

## Goal

One row per atom: label, species, Wyckoff site, editable x y z, occupancy,
Biso, aniso, vary, remove. No sub-rows, no "moves along", no separator line
sitting on the inputs.

## Context

The user: "It needs to be tidier, with one row for each atom. Editable atom
positions. 'Moves along' is not a natural UI, and clutters the interface.
Wyckoff sites don't have headings etc. Revisit fetching them automatically.
The thin line just above each atom row is too close to the editable fields."

Findings (2026-08-25, `Model.svelte:998-1089`):

- An atom is one to three `<tr>`s: the main row (label, species, a read-only
  `xyz` cell at 4 places, occ, Biso, aniso checkbox, `×`), then either a
  `frozen` sub-row (`fully fixed special position…`, `lib/model.ts:418-420`)
  or the DOF sub-row (`moves along` + one `[pattern]` box per DOF,
  `:1049-1067`), then an ADP sub-row (`:1069-1085`).
- The separator is `tr.sub td { border-bottom: 1px solid var(--line) }`
  (`:1543-1546`): it is the last sub-row's bottom edge, so it sits directly
  above the next atom's inputs.
- Coordinates are affine ties onto `phases.i.atoms.j.dof.k`
  (`crystallography/wyckoff.py`), so x/y/z are never typed; the editor
  offers the DOFs so "a site-symmetry violation is unrepresentable rather
  than refused" (WP-1014). `GET /api/structure`'s `sites` arm
  (`gui/symmetry.py:197-210`) carries `dof_paths`, `dof_directions`,
  `adp_paths`, `adp_patterns`, `site_symmetry_order`, `special`; the values
  come from the structure arm's `Atom.x/y/z` and the params rows.
- Wyckoff letters are behind a button (`Model.svelte:920-926` →
  `GET /api/structure/symmetry?phase=N`, `wyckoffLabel` in
  `lib/symmetry.ts:135-140`) and dropped on every head move (`:376-377`).
  The cost that argued for the button was 1.8-8.7 ms per atom **on a route
  that refetches on every head move** (WP-1035); it did not argue against
  fetching.
- The table's measured floor is 448 px + 24 (WP-1034), reflowed by
  `lib/resize.ts:modelStacks`.

Design:

- Columns: `label · species · site · x · y · z · occ · Biso · aniso · vary ·
  ×`. `site` is the Wyckoff letter and site symmetry, fetched automatically
  and **cached by a content hash** of (space group, positions), so a head
  move that leaves the structure unchanged costs nothing.
- x y z editable. A typed coordinate goes to `POST /api/structure/position
  {atom, xyz}`: the server projects onto the site's DOF basis and, when the
  residual exceeds a tolerance (1e-6 in fractional units), **refuses**
  naming the free direction(s) (`x = y is fixed here; y moved with x`),
  because silently rewriting a number the user typed is the objection that
  made `check_cell_angles` refuse rather than normalise. On a general
  position any value is accepted and lands as three DOF values through the
  existing `PATCH /api/params`. A fully fixed position renders read-only.
- ADPs in a per-atom disclosure on the `aniso` cell; the sub-rows go, and
  with them the separator.

## Non-goals

- Adding or removing atoms differently (the existing whole-model edit).
- The 3D viewer.

## Tasks

- [ ] `POST /api/structure/position` (projection, refusal wording, tests on
      NAC's special positions and a general position).
- [ ] Automatic Wyckoff with the content-hash cache (server-side cache keyed
      on the hash; `tests/test_gui_server.py` counts the spglib calls across
      two head moves without a structure change).
- [ ] The table: one row per atom, the columns above, the ADP disclosure;
      `modelStacks` floor re-measured; `model.test.ts`.
- [ ] Browser pass on NAC (special positions) and the corundum example;
      screenshot at the floor width; dist.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q -k "position or wyckoff"
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-0301 (affine site constraints), WP-1014, WP-1035 (symmetry surfaced).

## Handover log

- **2026-08-25** — created from the v1.2 triage.
