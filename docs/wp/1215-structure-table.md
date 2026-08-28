# WP-1215 — Model: the structure table

Milestone: v1.2 · Status: 🔄 2026-08-28 — in flight
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

Findings (2026-08-25, refreshed 2026-08-28 after WP-1214 —
`Model.svelte:1367-1475`):

- An atom is one to three `<tr>`s: the main row (label, species, a read-only
  `xyz` cell at 4 places, occ, Biso, aniso checkbox, `×`), then either a
  `frozen` sub-row (`fully fixed special position…`, `lib/model.ts:431-433`)
  or the DOF sub-row (`moves along` + one `[pattern]` box per DOF,
  `:1433-1453`), then an ADP sub-row (`:1455-1470`).
- The separator is `tr.sub td { border-bottom: 1px solid var(--line) }`
  (`:2052-2055`): it is the last sub-row's bottom edge, so it sits directly
  above the next atom's inputs.
- Coordinates are affine ties onto `phases.i.atoms.j.dof.k`
  (`crystallography/wyckoff.py`), so x/y/z are never typed; the editor
  offers the DOFs so "a site-symmetry violation is unrepresentable rather
  than refused" (WP-1014). `GET /api/structure`'s `sites` arm
  (`gui/symmetry.py:213-228`) carries `dof_paths`, `dof_directions`,
  `adp_paths`, `adp_patterns`, `site_symmetry_order`, `special`; the values
  come from the structure arm's `Atom.x/y/z` and the params rows.
- **A DOF is a displacement, re-anchored on every table build** (measured
  2026-08-28 on the LaB₆ fixture): `x = x₀ + Σₖ Bₖ·θₖ` anchors `const` at the
  stored `Parameter.value`, `set_values` writes x back through
  `refresh_ties` → `apply_to_models`, and the next `_working_table()` reads
  the new x₀ with every `dof.k` at 0.0 again. So a typed coordinate is a
  **delta** to solve for, never an absolute; and an axis the site holds is
  `locked`, not `tie`d (B at `6f` has `y`/`z` locked, `x` tied to `dof.0`).
- A vary request on a site frees **all** of its DOFs — "per-axis intent does
  not map onto rows such as [1,1,0]" (`params/vector.py:_collect_atom_coords`)
  — so the position carries **one** flag, not three.
- Wyckoff letters are behind a button (`Model.svelte:1259-1265` →
  `GET /api/structure/symmetry?phase=N`, `wyckoffLabel` in
  `lib/symmetry.ts:134-140`) and dropped on every head move (`:502-503`).
  The cost that argued for the button was 1.8-8.7 ms per atom **on a route
  that refetches on every head move** (WP-1035); it did not argue against
  fetching.
- The table's measured floor is 448 px + 24 (WP-1034, `MODEL_MIN.structure`
  = 472 in `lib/resize.ts`), reflowed by `lib/resize.ts:modelStacks`.

Design:

- Columns: `label · species · site · x · y · z · occ · Biso · aniso · vary ·
  ×`. `site` is the Wyckoff letter and site symmetry, fetched automatically
  and **cached by a content hash** of (space group, positions), so a head
  move that leaves the structure unchanged costs nothing.
- x y z editable. A typed coordinate goes to `POST /api/structure/position
  {atom, xyz}`: the server projects onto the site's DOF basis and, when the
  residual exceeds a tolerance (1e-6 in fractional units), **refuses** naming
  the free direction(s) and the nearest allowed position, because silently
  rewriting a number the user typed is the objection that made
  `check_cell_angles` refuse rather than normalise. On a general position the
  projection is the identity and any value is accepted; it lands as three DOF
  values through `set_values`, one `set_value` node, like every other typed
  number here. A fully fixed position renders read-only.
- The **`vary` column is the position's flag** — the one WP-1214 could not
  draw beside a value, because the value it is about is three cells wide and
  the DOFs it sets are freed together. `occ` and `Biso` keep their own
  in-cell flags.
- ADPs in a per-atom disclosure on the `aniso` cell; the sub-rows go, and
  with them the separator.

Carried in from **WP-1214** (2026-08-28, shipped; `### Inherited` consumed
2026-08-28):

- **Every value in this panel carries a refine flag beside it**, drawn by one
  `{#snippet varyBox(path)}` in `Model.svelte` (`:836-851`) and addressed by
  `data-vary="<parameter path>"`. The flag belongs *after* its value in the
  DOM — inside a `<label>`, the first labelable descendant is what the label
  names, so a flag placed first steals the value's label. The aniso checkbox
  is addressed by `data-aniso` for the same reason: "the first checkbox in
  the table" stopped being an address.
- A **held** value gets a mark rather than a box, and there are **four**
  reasons (`heldGlyph` in `lib/table.ts:112-119`). A locked coordinate wears
  `🔒`; the position's `vary` cell on a fully fixed site has no row at all,
  so the frozen sentence is what the cell carries.
- The phase's scale and its four sample-broadening terms are a `Phase` grid
  between the cell row and the atom table (`lib/model.ts:phaseFields`). It is
  the structure column's third block; the corrections (extinction, preferred
  orientation, Stephens) are still nowhere, deliberately.

Carried in from **WP-1201** (2026-08-25, shipped):

- The phase selector `nav.phases` is the `.segmented` register. Keep it
  segmented if this WP reworks the structure column.
- The atom table is `var(--text-sm)`, its `th` and the sub-labels are
  `var(--text-xs)`, and the per-row remove button is a plain `button.ghost`
  at the one button size (~22 px, chosen so the register fits a table row). A
  literal `font-size`, `padding` or `border-radius` on a register in this
  panel fails `gui/src/lib/style.test.ts`.
- A field is control-sized with **no exception** — a field that needs to feel
  prominent gets width and padding, never a step of its own. Two panels had
  put the size back with `font: inherit` on `input`; that is the shape to
  avoid.

## Non-goals

- Adding or removing atoms differently (the existing whole-model edit).
- The 3D viewer.

## Tasks

- [x] `POST /api/structure/position` (projection, refusal wording, tests on
      NAC's special positions and a general position). *The fixture is LaB₆,
      not NAC — it already carries both special positions this needs (`1a`
      fully fixed, `6f` one-DOF) and a two-DOF site is one appended atom, so
      importing a second structure would have bought nothing.*
- [x] Automatic Wyckoff with the content-hash cache (server-side cache keyed
      on the hash; `tests/test_gui_server.py` counts the spglib calls across
      two head moves without a structure change). *Keyed on the content tuple
      itself rather than a digest of it — a content hash with the collisions
      taken out. Measured: cold 9.7-12.2 ms for 2-6 atoms (2.0-5.5 ms an atom,
      inside WP-1035's 1.8-8.7), warm 1-3 us.*
- [x] The table: one row per atom, the columns above, the ADP disclosure;
      `modelStacks` floor re-measured; `model.test.ts`.
- [x] Browser pass on NAC (special positions) and the corundum example;
      screenshot at the floor width; dist. *The second project is
      **fluorapatite**, not corundum: corundum is a round-robin `.prn` and its
      data fence keeps it out of the wheel (WP-1204), so it is not an example
      project and cannot be opened. FAP is the better second case anyway —
      seven sites, four Wyckoff letters, and it is what sets the floor.*

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q -k "position or wyckoff"
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-0301 (affine site constraints), WP-1014, WP-1035 (symmetry surfaced).

## Handover log

- **2026-08-25** — created from the v1.2 triage.
