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
