# WP-1531 — what the promo figures found: a trimmed cell the report calls fine, a bond through a face, labels on atoms, polyhedra without their far ends

Milestone: unscheduled · Status: 🔄 2026-10-02 — claimed by @yue-here
Track: Render what the fit already knows
Depends on: — (1501, 1502, 1503 and 1529 are closed; they built the surface these defects sit in)
Priority: P2 2026-10-02 — `fig.report` calls a broken figure fine, and the skill tells an agent to read the report before the picture

## Goal

`render_structure`'s report counts everything wrong with the figure it
describes. A polyhedron lists all of its own bonds in a block of cells. A
label avoids atoms and bonds. A window can be completed by polyhedra alone.

## Context

Four reports filed by the maintainer's account (issues #664 to #667), from an
agent making publication figures for a rietx promo video with
`rx.viz.render_structure`. Each agent worked around its defect, and each
reproduction was re-run at `ca9bda29` in the 2026-10-02 triage with the same
output as the issue. The surface: `rietx.gui.structure3d.build` (the
geometry, `max_atoms` default `MAX_ATOMS`), `viz/figure3d/render.py`
(`render_structure`, `_label_overlaps`, `_dangling`), `viz/figure3d/report.py`
(the report's fields) and `viz/figure3d/cut.py` (`keep`). The scene rules have
a Python/TypeScript twin (`tests/data/gui/scene_cases.json`), so a rule change
in one copy needs the other.

### A trimmed cell, and a report that says it is fine (issue #665)

`render_structure` has no `max_atoms`, so a single cell is built at `build`'s
default of 400 atoms. HKUST-1 (COD 4002052) draws 648 atoms in its cell. It
is trimmed to 400, and the linkers come out broken. The report then reads
`cut {'polyhedra': 0, 'bonds': 0}`, `dangling_bonds 0` and `warnings []`.
Only the free-text `note` says "648 drawn atoms trimmed to 400" and that 96
bonds "end in mid-air". `build(extent=...)` raises on the same condition, so
one path refuses and the other trims. The reporter's options are to pass
`max_atoms` through, or to raise as the extent path does. Either way the
trim counts in `report.cut` and the 96 stubs count in `dangling_bonds`.

### A polyhedron's own bond left out of its list (issue #664)

In a block of cells, `build(extent=...)` leaves some centre–vertex bonds out
of their polyhedron's `bonds` list, while they remain in `geometry["bonds"]`.
The renderer draws each such bond as a free stick through the octahedron's
faces. On (BA)₂(MA)₂Pb₃I₁₀ (COD 4003235): one cell is clean, a 2×1×2 block
has 12 of 62 PbI₆ missing one bond each, and a 7×3×7 block has 245 of 1911.
The three centres printed lie on a cell face (y = 0 or z ≈ 0). The cause is
not traced. The CIF loads only with open PR #663 (a riding H at
B_iso = 27.6 Å²); the triage reproduced it on `main` by widening the B_iso
bound in-process.

### Labels on atoms and bonds, and a count that cannot see them (issue #666)

`atom_labels=True` puts every label up and to the right of its atom. On a
paracetamol molecule (COD 2104364) labels land on bonds and on neighbouring
atoms, and `report.label_overlaps` reads 1 (ball) and 0 (ellipsoid), because
it counts only label–label collisions. The proposal: try several anchors per
atom, keep the one clear of atoms, bonds and placed labels, and count
label–atom and label–bond overlaps beside label–label ones.

### Completing polyhedra only (issue #667)

`keep(..., complete=True)` adds both the vertices of cut polyhedra and the far
end of every cut bond, as its docstring says. A window of whole polyhedra with
nothing hanging off its edge cannot be asked for. On YBa₂Cu₃O₇ (COD 9007744),
one period in a adds 80 atoms, and 50 of them are far ends that are no kept
polyhedron's vertex. The proposal: `complete="polyhedra"` and
`complete="bonds"` beside `complete=True`.

## Non-goals

- The polyhedra's chemistry (which centres, which ligands): WP-1468.
- Moving the figure out of the package: WP-1505.
- Loading the RP CIF: PR #663.

## Tasks

- [x] #665: one rule for a cell past the cap on both paths, `max_atoms` on
      `render_structure`, and the trim and its stubs counted in the report
- [x] #664: trace why a face-centred PbI₆ misses its own bond in a block, fix
      it in `build`, and assert every polyhedron lists all its centre–vertex
      bonds on the four blocks the issue names
- [ ] #666: label placement clear of atoms and bonds, and the two new overlap
      counts in the report (both twins if the scene module moves)
- [ ] #667: `complete="polyhedra"` / `"bonds"`
- [ ] Tests, with the issues' reproductions as cases and a rendered PNG of
      each to `tests/output/`
- [ ] Skill: the figure rows that tell an agent to trust `fig.report` say
      what it now counts

## Acceptance

Each issue's reproduction gives the corrected count, and the twin corpus
stays equal.

```sh
.venv/bin/python -m pytest tests/test_render_structure.py tests/test_figure_cut.py tests/test_structure_extent.py tests/test_structure3d.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- COD 4002052 (HKUST-1), 4003235 ((BA)₂(MA)₂Pb₃I₁₀), 2104364 (paracetamol),
  9007744 (YBa₂Cu₃O₇): public structures, fetched by the tests or committed
  under their COD licence.

## Handover log

- **2026-10-02** — created, from the 2026-10-02 issue triage (issues #664,
  #665, #666, #667). Checked against the tree at `ca9bda29`: all four
  reproductions print the issues' numbers exactly (#664 with the B_iso bound
  widened in-process in place of PR #663). No open WP owns it: 1501 to 1503
  and 1529 built this surface and are closed, 1504 is the measurement, and
  1468 is polyhedron chemistry. Next: #665 first, since it is the one where
  the report says a broken figure is fine.
