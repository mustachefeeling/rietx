# WP-1216 — Model: the instrument form

Milestone: v1.2 · Status: ⬜
Depends on: WP-1214

## Goal

The instrument section is a grid in the order a crystallographer expects,
with U V W over X Y Z as two parallel rows, aligned inputs, and the geometry
select where it cannot move the other fields.

## Context

The user: "The instrument parameter fields are not aligned. The geometry box
is slightly narrower than the other ones, putting the first row off. The
instrument parameters should be arranged in a more logical way. For example,
UVW and XYZ are usually arranged in two parallel rows."

Findings (2026-08-25):

- `instrumentFields()` (`lib/model.ts:240-326`) returns a flat list:
  `geometry.kind`, `zero_shift`, `polarization`, per-line `wavelength`
  (+`weight` for i > 0), `profile.shape` (advanced), `u v w x y`,
  `axial_sl`, `axial_hl`, `sample_displacement`, then a geometry-dependent
  tail (`goniometer_radius_mm`, `sample_transparency`, `mu_t`,
  `thickness_mm` / `mu_t`, `thickness_mm`, `packing_fraction` / `mu_r`,
  `capillary_radius_mm`, `packing_fraction`). Every entry carries a `title`
  (WP-1029's pinned rule, `wizard.test.ts`).
- The renderer (`Model.svelte:1127-1154`) is `.grid`, a **wrapping flexbox**
  (`display: flex; flex-wrap: wrap; gap: 4px 10px`, `:1443-1448`) of
  `.cell` columns with `min-width: 92px` (`:1450-1456`). `input` and
  `select` share one rule with no width (`:1474-1485`); the geometry
  `<select>`'s longest option (`flat_plate_transmission`) makes it
  intrinsically wider and moves the wrap point, which is the misalignment
  the user saw. U V W X Y Z are six equal cells in that wrapping row. The
  cell edges, by contrast, get a real grid (`.cellrow`, `:1458-1463`).
- The background section (`:1156-1172`) and the FCJ `axialWarning`
  (`:1122-1126`) sit outside the grid.

Design: `Field` gains `group: "source" | "geometry" | "profile" |
"background"`; the panel renders one grid per group with fixed input widths
(`--w-num` from WP-1201's tokens): **Source** (λ per line with weights,
polarization), **Geometry** (kind on its own row; radius, displacement,
transparency, µ terms, packing), **Profile** (shape; then `U V W` over
`X Y Z` in one 3-column grid with `S/L H/L` beside), **Background** (family,
term count). The FCJ warning renders inside Profile. The wizard's preset
fields reuse the same grid.

### Inherited

From **WP-1215** (2026-08-28, shipped):

- **The stacking threshold moved, and this column's floor is what it is now
  measured against.** The atom table went from seven columns to eleven, so
  `MODEL_MIN.structure` is 666 (was 472) and `modelStacks` fires below
  **1136** px (was 932) — the threshold also counts the two 5 px splitter
  grips now, which no version of it did. `MODEL_MIN.form` is still 200, and
  200 is where this column sits at the threshold: measured there, the
  `Instrument` heading clips `Save profile…` to `Sa… prof`, because WP-1214
  put two controls in that `h2`. Whatever this WP does with the heading, that
  is the width it has to survive.
- **A width is written in more places than the one with a test.** The atom
  table's floor is stated three times — the table's `min-width`, the structure
  column's `flex-basis` and `MODEL_MIN` — and only the third had a test, so
  the `flex-basis` was still WP-1034's number and the column came out short at
  exactly the threshold. If this WP gives the form column a floor of its own,
  give it one statement and a test, or the same thing happens here.

From **WP-1214** (2026-08-28, shipped):

- **Every instrument field now has a refine flag under it**, in a
  `<span class="varyline">` that renders whether or not the field is in θ, so
  the wrapped grid keeps one rhythm — `geometry.kind`, the radius and the
  specimen dimensions draw an empty slot. Any regrouping this WP does has to
  keep the flag with its field, and a width rule aimed at the value reaches
  the control beside it (`.cellrow input { width: 100% }` drew an esd at zero
  width until it was excluded by name).
- **`Field.param`** carries the parameter-table path where it is not the model
  path prefixed. One field needs it — `source.polarization` is
  `instrument.polarization` in θ — and until WP-1214 that field rendered off
  the model and applied as a whole-model PATCH past `set_values`' bounds. Any
  new field this WP adds should be checked the same way: `fieldParam` is what
  every lookup asks.
- The form shows **no esds**, unlike the cell row and the Phase grid beside
  it. Left for this WP: the row is there (`byPath.get(fieldParam(…))?.esd`),
  the slot exists, and only the decision is missing.
- `Save profile…` sits beside `Load profile…` in the `Instrument` heading and
  prints the path it wrote under it (`POST /api/export/instrument_profile`,
  model-gated). Two controls in that `h2` now, so it wraps at ~1000 px.

From **WP-1203** (2026-08-26, shipped):

- **`lib/model.ts`'s `Field` gained `help`**, a corpus key carried as *data*
  because this form's paths are three different kinds of thing: most are
  parameter families (`parameters:instrument.profile.w`), four are
  `instrument_fields` entries (`mu_t`, `thickness_mm`, `packing_fraction`,
  `goniometer_radius_mm`, `capillary_radius_mm`), and two are model *choices*
  the corpus has no vocabulary for. Those two — `geometry.kind` and
  `profile.shape` — keep a `title` and are held to a **named list** in
  `wizard.test.ts`; a third fails until it is described or added deliberately.
- The label renders the help term and the `title` on the `<label>` is now the
  **held reason** alone (`heldReason(field, "instrument")`), which is the
  verb's own words about this instrument rather than a description of the
  field.
- `panels/Model.svelte` is allowed exactly **3** authored `title=` literals by
  `lib/help.test.ts`'s per-file budget (the space-group box and two splitters).
  The count fails both ways.

## Non-goals

- New instrument parameters or geometries.

## Tasks

- [ ] `lib/model.ts`: `group` on every field; `model.test.ts` asserts every
      field has one and the profile rows are `[u,v,w]`/`[x,y,z]`.
- [ ] `Model.svelte`: the four grids; fixed widths; the select on its own
      row; the warning and background inside their groups; the wizard's
      preset step on the same grid.
- [ ] Browser pass at the sidebar floor and ceiling (WP-1034's 340-560 px
      and 72 %), both themes; dist.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
```

Screenshots at floor and ceiling show every numeric input the same width
and U V W directly above X Y Z.

## References

- WP-1014, WP-1029 (no mute fields), WP-1034 (measured widths).

## Handover log

- **2026-08-25** — created from the v1.2 triage.
