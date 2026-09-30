# WP-1501 — cut and keep: a figure of part of the structure

Milestone: v1.7 · Status: ✅ 2026-09-30 — keep, four masks and recolour landed in the v1.6 tree
Depends on: 1470

## Goal

`rietx.viz.keep(geometry, mask)` returns a geometry dict holding only the
atoms the mask keeps, with its bonds and polyhedra consistent. Four mask
builders name atoms in crystallographic terms: `select`, `plane`, `sphere`
and `component`. `recolour` changes the colour of chosen atoms without
touching the scene rules. An atom can be removed, which the manual stopped
offering in #498 because the dict edit raised.

## Context

### Why

Measured 2026-09-27 on NAC (`tests/data/cod_1000236.cif`, aniso) with the
WP-1470 tree, editing the dict `rietx.gui.structure3d.build` returns and
passing it to `render_structure`:

| Edit | Result |
|---|---|
| `sites[0]["color"] = "#ff0000"` | works, 96 859 px changed |
| `sites[0]["color"] = "red"` | draws mid-grey, no message |
| `sites[0]["radius"] *= 2` | works |
| `del atoms[k]`, mid-list or last | `IndexError` |
| `hidden=["F2"]` (a site label; F1 and F2 are both `F1-`) | refused: `hidden` takes species or elements |
| `model_copy(deep=True)`, drop site F2 from `phases[0].atoms` | works, 113 atoms drawn, but the chemistry changed: the polyhedra were rebuilt without F2 |

The dict's `bonds` (`i`, `j`) and `polyhedra` (`center`, `vertices`,
`bonds`) index into `atoms`. Deleting an entry breaks every later index.
`docs/manual/using/exports.md` § A figure of the structure named "an atom
removed" as an example edit until #498 took it out, with the skill's "a
site to leave out". WP-1470's D10 promises customisation through data.
Removing one atom by hand took ten lines and a reading of `structure3d.py`:
an index map, the bonds rewritten, the polyhedra dropped.

Two further facts decide the shape:

- `hidden=` cannot take a label without changing `build_scene`'s `hidden`
  set, which the GUI's `buildScene` shares (held equal by
  `tests/data/gui/scene_cases.json`), and the GUI's legend toggles species.
  So one site is hidden by a mask, and `hidden=`'s error names that route.
- `scene.rgb` returns mid-grey for anything that is not `#rrggbb`. That is
  a GUI rule and stays. `render_structure` validates a site colour at its
  entry, beside `_species`, where `background=` already refuses.

### Existing practice

Read 2026-09-27 from each program's documentation.

- **OVITO** chains `ExpressionSelectionModifier` into
  `DeleteSelectedModifier`, and `SliceModifier(normal, distance,
  slab_width, inverse)` cuts a half-space or a slab.
- **VESTA** takes a cutoff plane as hkl plus a distance from the origin, in
  d-spacings or Å. Its boundary search keeps bonded atoms and whole
  polyhedra past the box.
- **Jmol** selects with `within(distance, ...)` and `within(0, HKL, {h k
  l})`.
- **ASE** and **pymatgen** use boolean masks, and find molecules as
  connected components of the bond graph (`scipy.sparse.csgraph`,
  `StructureGraph.get_subgraphs_as_molecules`).

The common shape is select, then keep. The names and semantics below are
theirs. A plane's distance is in d-spacings first, VESTA's first option,
since an agent says "the plane through the origin and the next one at d".

### Design

- **`keep(geometry, mask, *, complete=False) -> dict`.** `mask` is a
  boolean array over `atoms`. A bond survives when both ends survive. A
  polyhedron survives when its centre and every vertex survive. What is
  dropped is counted in `note` ("3 polyhedra cut, 12 bonds cut"), so a cut
  figure says what it lost. `complete=True` re-adds the far ends of cut
  bonds and the vertices of cut polyhedra whose centre survives, from the
  atoms `build()` produced. That is VESTA's default search. It completes
  only within what was built; WP-1502's extent supplies more. `sites` is
  untouched and `atoms[k]["site"]` keeps its meaning. Re-indexing happens
  in this one function.
- **Masks**, each a boolean array over `atoms`, combined with `&`, `|` and
  `~`:
  - `select(geometry, *, species=None, element=None, label=None,
    site=None, boundary=None)`. A name the phase lacks raises and names
    the vocabulary, as `_species` does.
  - `plane(geometry, hkl, distance, *, width=None, inverse=False,
    units="d")`. Keeps the origin side of the plane (hkl) at `distance`
    d-spacings (`units="angstrom"` for Å). `width` keeps the slab between
    `distance` and `distance + width`. `inverse` flips. Computed on `frac`
    through the metric.
  - `sphere(geometry, centre, radius)`. `centre` is an atom index or a
    Cartesian point, `radius` in Å. An index, because a label names several
    images; `select(label=)` finds them.
  - `component(geometry, atom, *, via="bonds")`. The connected piece
    holding `atom`. `via="bonds"` walks `bonds`. `via="corners"`,
    `"edges"` and `"faces"` walk polyhedra sharing at least one, two or
    three vertices. The critique found the second graph necessary: rutile's
    TiO₆ chains are edge-sharing connectivity, and by bonds every Ti
    reaches every other through O, so the cell is one component. Here the
    walk is over the finite built graph; a motif's periodicity needs the
    periodic identity WP-1502 adds.
- **`recolour(geometry, mask, colour) -> dict`.** Appends a copy of each
  affected site with the new colour and points the masked atoms, and the
  polyhedra centred on them, at the copy. The scene rules and the GUI twin
  are untouched. A per-atom colour in the scene would touch both. The
  figure gains `palette`, site label to colour drawn, so a caller can draw
  a legend in matplotlib.
- **The two fixes.** A site colour that is not `#rrggbb`, `white` or
  `black` raises at `render_structure`'s entry. `hidden=`'s refusal for a
  label says `keep(g, ~select(g, label=...))`. The third, the manual's
  example that raised, landed with #498.
- **An import-boundary pin.** A test lists the rietx modules that
  `viz/figure3d` and `gui/structure3d` import (`_about`, `viz.theme`,
  `model.compiled`, `crystallography.adp`, `crystallography.symmetry`) and
  fails on a new one. No injection now; WP-1505 does the adapter. The list
  is the split's measured cost, and it must not grow unseen.
- **Docs.** `exports.md` § A figure of the structure names the fields an
  agent may edit (`sites[*].color`, `sites[*].radius`), states the index
  rule, and gives one example per verb. It says that `ref.structure` is the
  live model: edit a `model_copy(deep=True)`, since an in-place edit
  changes the next fit and no history node records it. `api-figure.md` is
  regenerated. Every verb lands on the derived surface, so the manual
  partition (`tests/test_manual_api.py`) fails until each is documented.

## Non-goals

- An extent beyond one cell, and a motif's periodicity (WP-1502).
- The report numbers and the automatic view (WP-1503).
- GUI controls for a cut. The viewer keeps one cell and its legend.
- A per-atom colour in the scene rules.
- Widening `hidden=` to labels.

## Tasks

- [x] `keep` with the re-indexing, the `note` counts and `complete=`; a
  test that every index in the result is in range on the 21 phases of
  `tests/data/polyhedra_phases.json`, and that `keep` under an all-true
  mask renders bit-identically.
- [x] `select`, `plane`, `sphere`, `component` with `via=`; a test that
  `component(via="edges")` on rutile is a chain and on NAC by bonds is the
  whole cell, and that a plane through the origin at `distance=1` on a
  cubic cell keeps the atoms with `frac · hkl ≤ 1`.
- [x] `recolour` and `StructureFigure.palette`; the colour validation at
  entry; `hidden=`'s error names the mask route.
- [x] The import-boundary pin.
- [x] `exports.md` rewritten with a runnable example per verb, the
  `model_copy` rule, `api-figure.md` regenerated, and the manual partition
  green.
- [x] Skill: the verbs on `api-figure.md`, and a line in the routing row's
  reference saying a site is hidden by a mask. Pay for any body byte with a
  cut.
- [x] Tests, and pictures to `tests/output/`: NAC without F2 by mask, a
  (110) slab of NAC with `complete=True`, rutile's chain, one recoloured
  site.
- [x] The addition staged in the open milestone's record.

## Acceptance

- The manual's own edit examples run, and a removed atom renders.
- `keep(g, ~select(g, label="F2"))` on NAC draws 113 atoms with every AlF₆
  octahedron that lost a vertex counted in `note`, and with
  `complete=True` draws them whole.
- `sites[0]["color"] = "red"` raises and names the accepted forms.

```sh
.venv/bin/python -m pytest tests/test_render_structure.py tests/test_structure3d.py tests/test_manual_api.py
RIETX_COMPILED=0 .venv/bin/python -m pytest tests/test_render_structure.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- OVITO, *Slice*, *Expression selection*, *Delete selected* modifiers,
  docs.ovito.org/reference/pipelines/modifiers/.
- VESTA manual ch. 8 § 8.1 (search modes) and ch. 10 § 10.1.2 (cutoff
  planes), jp-minerals.org/vesta/en/doc/.
- Jmol scripting, `within()`, chemapps.stolaf.edu/jmol/docs/.
- pymatgen `StructureGraph.get_subgraphs_as_molecules`;
  ASE `ase.neighborlist.get_connectivity_matrix`.
- WP-1470 D10 and the manual section it wrote.

## Handover log

- **2026-09-30** — closed. A figure of part of a structure can now be drawn
  from Python. An atom, a site, a slab, a sphere or a connected motif is kept or
  left out by a mask, and the bonds and polyhedra stay consistent. Part of a
  site can be painted, with a legend from the figure. The manual no longer
  avoids removing an atom, because the way to do it exists. Two quiet failures
  now speak: a site colour like `"red"` raises where it drew grey, and
  `hidden="F2"` says how to leave one site out.
  - **Done.** New `viz/figure3d/cut.py` (`keep`, `select`, `plane`, `sphere`,
    `component`, `recolour`), exported through `rietx.viz`;
    `StructureFigure.palette`; colour validation and the `hidden=` message in
    `render.py`; `tests/test_figure_cut.py` (35 cases, 20 of them the measured
    phases) and `tests/test_figure_boundary.py`; `examples/structure_cut.py` with
    its `test_examples.py` row; `exports.md` § Drawing part of the structure; the
    skill's `api-figure.md` (generator edited, three copies synced); the v1.6
    record's entry. Pictures in `tests/output/figure3d/cut_*.png`, looked at.
  - **Measured.** NAC without F2: 113 atoms, `26 polyhedra cut · 108 bonds cut`;
    with `complete=True` 173 atoms and an empty note. NAC by bonds: all 84 cell
    atoms are one piece (plus 6 images), the other 95 atoms are images no bond
    reaches, so the WP's "whole cell" holds for the cell and not for every atom.
    Rutile by edges is 12 atoms, by corners 49, by faces 7. Fast suite, `[dev]`
    venv, darwin/arm64, nothing else running: 6984 passed, 157 skipped, 136 s
    (150 s before the review's test). 17 added fast tests cost 4.7 s in
    that run, one `test_examples` row included; none is in the slow tail.
    `RIETX_COMPILED=0` on `test_render_structure.py` green. `-W` manual build and
    `test_skill*.py` green. The full suite was not run: nothing here moves a
    measured number.
  - **Review.** `/code-review high --fix` fixed four and left four. Fixed:
    `component` via edges or faces seeded from a *vertex* merged octahedra that
    touch at a corner, so those two now start from a centre only and raise
    otherwise; a non-finite `plane` distance or width raises; two recolours of a
    site in different colours each keep a palette entry; one white/black table.
    Declined, with reasons: `recoloured: True` is read only by a test
    (the palette infers it from colours; changing that changes the contract),
    the O(P²) scan in `component` (unmeasured), a local named `keep` inside
    `select` (cosmetic), and `select(species=[])` selecting nothing (kept as a
    caller's empty list; `keep(~mask)` then keeps everything).
  - **Gotchas.** A polyhedron's `bonds` are found by position, so their `i`/`j`
    can be periodic twins of its centre and vertices; a bond's `b` is the far
    end's image, not atom `j`'s position. Both shaped the consistency test.
    `StructureFigure.palette` gained a field, so a positional constructor call
    would shift; none exists. The WP's Design named `viz/figure3d` a module and
    it is a package.
  - **Findings filed.** 1502's `### Inherited` (finite graph, periodic identity,
    polyhedron bonds by position) and 1505's (the pinned boundary, scipy).
  - Next: WP-1502, the extent beyond one cell, which is the only place a motif's
    periodicity can be supplied; or WP-1503, which reads what `keep`'s `note` and
    `palette` now carry. Neither is blocked.
- **2026-09-27** — filed from the session that closed WP-1470, after the
  probe in Context and a survey of five programs' cut and select verbs.
  Next: land `keep` first, since the documented route raises today.
- **2026-09-27** — synced with #498, which took the manual's raising example
  and the skill's "a site to leave out" out before it merged. Two of the
  three fixes remain here. `keep` is still first, since nothing else removes
  an atom.
