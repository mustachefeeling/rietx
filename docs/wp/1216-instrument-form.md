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

Design: `Field` gains `group: "source" | "geometry" | "profile"`; the panel
renders one grid per group with fixed track widths (`--w-num`): **Source**
(λ per line with weights, polarization), **Geometry** (kind on its own row;
zero, displacement, transparency, radius, µ terms, packing), **Profile**
(shape; then `U V W` over `X Y` in one 3-column grid, `S/L H/L` on the row
under them). The FCJ warning renders inside Profile. The wizard's preset
fields reuse the same grid.

Two departures from the sketch this WP was written with, both because the
sketch named something that does not exist. There is no **Z**: this profile's
Lorentzian terms are X and Y, so the second row is two wide and its third slot
is empty rather than invented — which also puts `S/L H/L` on a row of their own
rather than beside, there being no fourth and fifth column at the 200 px floor.
And there is no **background** group: the family is not offered as an edit here
and the term count is a shape change with its own verb, so neither is a
`Field`, and a fourth member of the union would be a name with no writer
(CLAUDE.md, WP-1076). The background keeps its own heading and its one control.

Three widths this form has to survive, measured by WP-1215 and WP-1034:
`MODEL_MIN.form` is **200** px, which is what this column gets at the 1136 px
stacking threshold, and the `Instrument` heading already clips `Save profile…`
there because WP-1214 put two controls in that `h2`. Stacked, the column is the
panel's own width, so 340 px at the sidebar floor. And a width stated in more
than one place needs a test on the statement, or the stale one is the one that
draws (the atom table's floor was written three times and tested once).

Three rules carried in from the two WPs before this one. Every field has a
refine flag under it in a `<span class="varyline">` that renders whether or not
the field is in θ, so any regrouping keeps the flag with its field, and **a
width rule aimed at the value reaches the control beside it** — `.cellrow input
{ width: 100% }` drew an esd at zero width until the flag was excluded by name.
`Field.param` carries the parameter-table path where it is not the model path
prefixed (`source.polarization` alone), and `fieldParam` is what every lookup
asks — including any new field. And what a field *is* comes from
`rietx.help` through `<Help>`: the `title` on a `<label>` here is the **held
reason**, `geometry.kind` and `profile.shape` are the two fields the corpus has
no entry for and are held to a named list in `wizard.test.ts`, and
`panels/Model.svelte` is allowed exactly **3** authored `title=` literals by
`lib/help.test.ts`, a budget that fails both ways.

## Non-goals

- New instrument parameters or geometries.

## Tasks

- [x] `lib/model.ts`: `group` on every field; `model.test.ts` asserts every
      field has one, that all three groups are written, that a group is what
      the field *is* rather than its path's prefix, and that the profile rows
      are `[U,V,W]` / `[X,Y]` / `[S/L,H/L]` with the row starts to match.
- [ ] `Model.svelte`: the three grids; fixed tracks; the selects on their own
      row; the warning inside Profile and the background under it; the esd
      decision WP-1214 left; the wizard's preset step on the same grid.
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
