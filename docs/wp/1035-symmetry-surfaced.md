# WP-1035 — Symmetry, surfaced and editable

Milestone: v1.0 · Status: ⬜
Depends on: **1036** (its tables are what a preview would encode), 1014 (landed)
· soft: 1004

## Goal

A user can see a phase's symmetry and what it is responsible for — the symbol,
its crystal system and Laue class, the Wyckoff letter of each site, the cell
ties and held rows it causes — and can change it, through a verb that says what
the change would invalidate **before** it is applied.

## Goal, restated

The user asked *"where is the space group / symmetry information?"* and the
honest answer is that it is one string, quoted in three places and explained
in none. Everything the symmetry *does* — a tied `b`, a locked angle, a site
with two coordinate DOFs instead of three, an ADP basis of four patterns — is
visible in the parameter table as an effect with no named cause.

## Context

### Inherited from [1034](1034-panel-layout.md) (added 2026-08-05, on its close)

**The pane this WP edits is a tab now, and it is routinely 340–560 px wide.**
`Model.svelte` reflows to one stacked column below 932 px (`modelStacks` in
`lib/resize.ts`, the sum of the three columns' measured floors), so a symmetry
summary added to the structure column must read at **~340 px**, not only at the
1500 px full-window layout — check both, and remember the header's `Split |
Full` is the escape hatch for anything genuinely wide. Two mechanics that come
with it: a column's minimum is stated as a **flex basis** (the structure
column's is 472 px, the atom table's `min-content` plus padding) rather than an
equal share, and the atom table sits in its own `overflow-x` wrapper, so
anything you add beside it must not re-introduce a column-wide side scroll.
`.column` widths are still the shell's `ui.model_columns`, and a drag still
overrides both.

### Inherited from [1036](1036-crystal-system-settings.md) (added 2026-08-04, on its close)

1036 was this WP's blocker and it landed, so read the following **before** the
"What exists" section below, which was written at `660c950` and is stale in four
places.

- **`cell_constraints(sg)` is the oracle this WP's preview needs**, and it did
  not exist when 1035 was written.
  `crystallography.symmetry.cell_constraints(sg) → CellConstraints(ties,
  fixed_angles)` answers "which cell parameters does this symbol tie, and which
  angles does it fix, and at what value" for **any** setting. A "what would
  changing the symbol invalidate?" preview is a diff of two `CellConstraints`
  plus the site/ADP bases the `sites` arm already computes — no new rule, which
  is exactly the constraint this WP is under. `check_cell_angles(sg, angles)` is
  its companion and is what a symbol edit must call to know whether the *current*
  cell can even carry the proposed symbol.
- **`ext` is load-bearing, not decoration.** The measurement below quotes
  `R -3 c` → xhm `R -3 c:H` and lists `ext` among the free phase-level facts.
  That resolution is **conditional on the input**: `read_small_structure` picks
  the setting from the *cell*, so the same bare symbol over a rhombohedral cell
  comes back `R -3 c:R`, `ext='R'` — a different tie set (a = b = c, α = β = γ
  free) and a different set of held rows. A symmetry summary that shows the
  crystal system but not `ext`/`monoclinic_unique_axis()` is showing the user
  something that does not determine what they are looking at.
- **`params/vector.py:141` no longer computes and discards
  `crystal_system_str()`** — `_collect` now calls `cell_constraints(sg)`. The
  "costs a lookup" argument still holds; the line reference does not.
- **The missing schema validator on `Phase.space_group` is a decision, not an
  oversight.** 1036 declined to add one deliberately: pydantic validation would
  change the error type at every construction site including history-node
  deserialization, which is not a change to make just before the API freeze. It
  is recorded as a line for [1003](1003-api-freeze-pypi.md). So this WP should
  keep validating at the *verb*, as it already planned, and not wait for a schema
  guard that is not coming.
- **The trap this WP is most exposed to**: 79 of gemmi's 564 settings were served
  wrong before 1036, and the free-parameter *count* was correct in every one of
  them. Any UI that summarises symmetry as "N refinable cell parameters" would
  have shown the right number for all 79. Name the tie and the held angle, never
  the count.

### What exists (read at `660c950`)

- **`Phase.space_group: str`** (`schemas/structure.py:310`) is the only symmetry
  field — a Hermann-Mauguin symbol or an IT number as a string, resolved by
  `get_spacegroup` (`crystallography/symmetry.py:30-40`), which tries
  `find_spacegroup_by_name` then `find_spacegroup_by_number`. There is **no
  schema validator**: pydantic accepts any string, and an unresolvable one only
  fails later, where `_site_rows` catches it per phase and returns an error row
  (`gui/session.py:1919-1923`).
- `structure_from_cif` stores gemmi's canonical **`sg.xhm()`**
  (`crystallography/cif.py:81`), not the file's literal string; export writes it
  back at `cif.py:157`.
- It is quoted read-only in three places: the Model pane
  (`Model.svelte:674-676`, titled *"symmetry is derived by the CIF reader —
  re-import to change it"*), the 3D caption (`gui/structure3d.py:416` →
  `Structure3D.svelte:407`), and the CIF upload preview
  (`gui/imports.py:332`).
- **The `sites` arm already computes the hard part.** `_site_rows`
  (`gui/session.py:1908-1944`) returns `site_symmetry_order`, `special`,
  `dof_paths`, `dof_directions`, `adp_paths` and `adp_patterns`, through the
  *same* functions `ParameterTable` uses (`stabilizer_rotations` →
  `coordinate_basis` / `adp_basis`), never a second rule.

### Two measurements that decide where things go

**The phase-level facts are free.** One `get_spacegroup` call yields `number`,
`xhm()`, `hall`, `short_name`, `ext`, `crystal_system_str()`, `laue_str()`,
`point_group_hm()`, `centring_type()`, `is_centrosymmetric`, `is_sohncke`,
`is_enantiomorphic`, `is_symmorphic`, `is_reference_setting` and
`monoclinic_unique_axis` — **measured** against the worktree venv's gemmi, e.g.
`R -3 c` → number 167, xhm `R -3 c:H`, trigonal, Laue `-3m`, centring `R`. None
of them is exposed by any route today, and `crystal_system_str()` is already
computed inside `ParameterTable._collect` (`params/vector.py:141`) and
discarded. A phase symmetry summary therefore costs a lookup and may ride on
`/api/structure`.

**The per-atom Wyckoff letter is not free, and the refusal is already written
down.** `gui/session.py:574-578` says the letter needs
`wyckoff.site_constraints`, which runs spglib per atom, on a route refetched on
**every head move — including one a `set_vary` made** — so "the letter would be
decoration bought with a symmetry search per keystroke". The same docstring
names the escape at `:584-595`: a *deliberately-opened* route may do the search,
which is what `/api/structure3d` does. So the letters go on a deliberately
opened route. Note that `wyckoff.site_constraints` (`wyckoff.py:176-221`) is
currently **called from no production code at all** — only tests — and it
discards most of what spglib hands back (`pointgroup`, `hall_number`,
`equivalent_atoms`, the transformation). Nobody has timed it; a WP quoting a
budget must measure rather than repeat "expensive".

### The editing half, and why the gate is the whole job

**`PATCH /api/structure` already accepts a changed space group today.**
`structure_patch` (`gui/session.py:618-632`) validates through `_as_structure`
(pydantic plus a species check — no symmetry at all) and calls
`Refinement.edit` (`refine.py:241-264`), which swaps the models wholesale,
clears `_model` and `result_`, and **commits an `edit_model` node from a
snapshot that never builds a ParameterTable**.

The symmetry refusals live in `ParameterTable` construction, so they fire on the
*next* table build:

- an aniso tensor outside the new site's allowed subspace →
  `params/vector.py:308-313`, naming the allowed basis and the nearest allowed
  tensor;
- a Stephens block outside the new Laue subspace → `vector.py:206-211` (and an
  all-zero block with `vary=True` → `:213-219`);
- an atom with `vary=True` on a now fully fixed special position →
  `vector.py:262-265`.

So an incompatible change **succeeds, records a node, and then surfaces as a 500
`INTERNAL_ERROR`** on the panel's follow-up `GET /api/params`
(`session.py:404-406` → `Project.parameters` → `_working_table`), because a
`ValueError` from the table is not a `GuiError` (`gui/server.py:414-418`). The
head then stands at a state whose table cannot build, and the only way out is a
history checkout. **The gate has to run before `edit`, because `edit` is a point
of no return that pydantic does not guard.**

**Build the preview out of the existing rules, not a second copy of them**: copy
the structure, swap the symbol, construct a `ParameterTable` from the candidate,
and read the answer off it. The raises *are* the incompatibility list, in the
package's own words including the "nearest allowed" remediation they already
compute; the entry diff (`Entry` carries `path`/`vary`/`tie`/`locked`,
`vector.py:85-94`) *is* the tie/lock story; and `_site_rows(candidate)` against
`_site_rows(current)` *is* the per-atom lose/gain-DOF story, already in the shape
`Model.svelte` consumes. One caveat: construction stops at the **first**
incompatible item, so a complete per-atom preview loops the same
`stabilizer_rotations` + `adp_basis` + projection path `_site_rows` already
demonstrates.

### Three silent failures the table diff will not catch

Each needs its own answer; none of them raises today.

1. **A setting change reinterprets every coordinate while still resolving.**
   `R -3 c` → `R -3 c:H`, but `R -3 c:R` is the same group on rhombohedral axes.
   `is_reference_setting`, `ext` and `qualifier` are what a preview reads, and
   [1036](1036-crystal-system-settings.md) is the WP that makes the tie tables
   honest about settings in the first place — which is why this WP depends on it
   rather than the other way round.
2. **Orbit collisions.** `select_orbit_ops`
   (`crystallography/structure_factor.py:106-129`) dedups images *within* one
   atom's orbit; two asymmetric-unit atoms mapped onto each other by a higher
   symmetry double-count in F, and nothing checks it. The check is a pairwise
   minimum periodic distance across `expand_positions` orbits
   (`symmetry.py:89-97`).
3. **`_free_paths` silently re-frees renumbered DOFs.** `…dof.k` and `…adp.k`
   are *positional*, so after a group change `dof.0` may exist with a different
   direction; `_prepare_table(restore=True)` (`refine.py:497-507`) frees it
   without comment, and a path that vanished produces only a `warnings.warn`,
   invisible in the GUI.

### Where the symbol may be edited, and where it may not

WP-1014's founding split decides it: **if the parameter table has the path, the
parameter table owns it; anything that changes what the table *contains* goes as
a whole validated model.** The space group changes what the table contains, so
it is `PATCH /api/structure` (or a verb beside it, on the `structure_aniso`
pattern at `session.py:641-691`, which exists because both directions are
physics the client must not compute) — never `PATCH /api/params`.

Symbol validation has a precedent to copy rather than invent: `index_adopt`
maps a `ValueError` from an unresolvable symbol to
`GuiError(where=["space_group"])` (`session.py:1296-1302`).

## Non-goals

- **Not a symmetry finder.** Determining symmetry from a pattern is WP-1025's
  extinction screen, which already answers with **ranked classes, every class
  listing all its space groups**, because the extinction symbol is what a powder
  measures and a singleton there is unmeasurable. Nothing here may present a
  single derived group as a measurement.
- **Not an editable space group in the text document.** The `.pxt` document's
  editable surface is parameters and settings; a second authority on a phase's
  symmetry is what its rules forbid. The symbol appears there as a **rendered
  comment** only — the form `textdoc.py`'s own module docstring documents
  (`phase 0 "NAC"  # Ia-3d`) and never implemented — via the existing
  `_atom_comment` mechanism (`textdoc.py:422`), so **no format-version bump**.
- **Not the tie tables themselves** — [1036](1036-crystal-system-settings.md).
- **Not Wyckoff letters on `/api/structure`**, for the reason that route's own
  docstring gives.

## Tasks

- [ ] **Phase symmetry summary** — symbol, IT number, crystal system, Laue
      class, point group, centring, centrosymmetric — from one gemmi lookup,
      served and rendered wherever a phase appears.
- [ ] **Wyckoff letters per site on a deliberately-opened route**, with the
      per-atom cost *measured* and quoted, not assumed.
- [ ] **Name the cause of a held row**: a cell tie or a locked angle says which
      symmetry element is responsible, so the parameter table stops showing
      effects with anonymous causes.
- [ ] **The `.pxt` phase line carries the symbol as a comment**, with the
      render → parse → render fixed-point test still passing and no format bump.
- [ ] **A preview verb** built from a candidate `ParameterTable` plus
      `_site_rows`: entries gaining/losing a tie or lock, DOF and ADP paths
      appearing/vanishing, the refusals verbatim with their nearest-allowed
      values, and the free paths that would be dropped or renumbered.
- [ ] **The three silent failures** answered: a setting change flagged as one, an
      orbit-collision check, and a `_free_paths` casualty list — each surfaced in
      the preview rather than discovered afterwards.
- [ ] **Apply through the whole-model path**, gated on the preview, with an
      unresolvable symbol refused as `GuiError(where=["space_group"])`.
- [ ] Tests: a server test that an incompatible change is **refused before any
      history node is written** (today it commits and then 500s — assert the new
      behaviour and keep a regression test for the old failure), vitest for the
      preview-rendering pure functions, and a jsdom mount test for the editor.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_wyckoff.py -q
.venv/bin/python -m ruff check src tests examples
npm --prefix gui run build && .venv/bin/python -m pytest tests/test_gui_dist.py -q
```

And by hand, on the NAC project (COD 1000236 + `11BM_NAC.fxye`, `Ia-3d`, four
species, aniso): read the symmetry summary, check the Wyckoff letters against
the published site list, then attempt a change that must be refused — an aniso
tensor is the easy one — and confirm **the head has not moved** afterwards.

## References

- International Tables for Crystallography Vol. A — the letters, classes and
  settings being displayed.
- `gui/CLAUDE.md` — WP-1014's owns-the-path split; WP-1025's ranked-class rule.
- `docs/wp/1025-extinction-symbol.md` — why a single space group is never a
  measurement.

## Handover log

- **2026-08-04** — created from the user's question *"where is the space group /
  symmetry information?"*, alongside [1032](1032-gui-repairs.md),
  [1033](1033-plot-range-regions.md), [1034](1034-panel-layout.md) and
  [1036](1036-crystal-system-settings.md). Nothing is started.

  **The user chose "show it, explain it, and make it editable"** over
  display-only. That is binding.

  **Two findings a successor should not re-derive.** The phase-level symmetry
  facts are a free gemmi lookup (measured, listed above) while the per-atom
  Wyckoff letter is a spglib search the `/api/structure` docstring already
  refuses — so the split is decided, not open. And **`PATCH /api/structure`
  already accepts a space-group change today**, committing a history node before
  anything symmetry-aware runs, so the failure mode is a 500 on the next
  `GET /api/params` with a head that cannot build a table. That is arguably a
  bug that exists right now, independent of this feature, and fixing it *is*
  most of this WP.

  **The preview is a diff of two ParameterTables** — that is the design, and its
  virtue is that it duplicates no rule. Resist writing a second compatibility
  checker; the raises already carry their own remediation values.
