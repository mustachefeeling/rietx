# WP-1501 — cut and keep: a figure of part of the structure

Milestone: v1.7 · Status: 🔄 2026-09-30 — claimed by @yue-here
Depends on: 1470
Priority: P2 2026-09-27 — a cut is the first edit a figure needs, and today it means re-indexing the dict by hand; #498 stopped the manual offering the deletion that raised

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

### Inherited

- **From WP-1468 (2026-09-28).** The dict `structure3d.build` returns grew
  arms, all additive. Each site has `disorder_assembly` and
  `disorder_group`, and each polyhedron a `rival` (`[ligands, ratio]` or
  null). The top level has `polyhedra_dropped` (a site index and ligand
  elements, no atom index), `disorder`, `minor_sites` (site indices),
  `centres`, `ligands`, `centre_elements` and `ligand_elements`. A cut that
  remaps `atoms` indices still touches only `bonds` (`i`, `j`) and
  `polyhedra` (`center`, `vertices`, `bonds`); the new arms hold site indices
  or none. `build(disorder="major")` keeps a minor site in `sites` with no
  image, so a mask can meet a site with no atom. `build(centres=…,
  ligands=…)` rebuilds the polyhedra before any cut: an anion-centred FCa₄,
  or an intermetallic's environments. The GUI's double-click draws one
  atom's polyhedron alone by filtering what is shown (`focusedPolyhedra` in
  `gui/src/lib/structure3d.ts`), a client-side keep.

## Non-goals

- An extent beyond one cell, and a motif's periodicity (WP-1502).
- The report numbers and the automatic view (WP-1503).
- GUI controls for a cut. The viewer keeps one cell and its legend.
- A per-atom colour in the scene rules.
- Widening `hidden=` to labels.

## Tasks

- [ ] `keep` with the re-indexing, the `note` counts and `complete=`; a
  test that every index in the result is in range on the 21 phases of
  `tests/data/polyhedra_phases.json`, and that `keep` under an all-true
  mask renders bit-identically.
- [ ] `select`, `plane`, `sphere`, `component` with `via=`; a test that
  `component(via="edges")` on rutile is a chain and on NAC by bonds is the
  whole cell, and that a plane through the origin at `distance=1` on a
  cubic cell keeps the atoms with `frac · hkl ≤ 1`.
- [ ] `recolour` and `StructureFigure.palette`; the colour validation at
  entry; `hidden=`'s error names the mask route.
- [ ] The import-boundary pin.
- [ ] `exports.md` rewritten with a runnable example per verb, the
  `model_copy` rule, `api-figure.md` regenerated, and the manual partition
  green.
- [ ] Skill: the verbs on `api-figure.md`, and a line in the routing row's
  reference saying a site is hidden by a mask. Pay for any body byte with a
  cut.
- [ ] Tests, and pictures to `tests/output/`: NAC without F2 by mask, a
  (110) slab of NAC with `complete=True`, rutile's chain, one recoloured
  site.
- [ ] The addition staged in the open milestone's record.

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

- **2026-09-27** — filed from the session that closed WP-1470, after the
  probe in Context and a survey of five programs' cut and select verbs.
  Next: land `keep` first, since the documented route raises today.
- **2026-09-27** — synced with #498, which took the manual's raising example
  and the skill's "a site to leave out" out before it merged. Two of the
  three fixes remain here. `keep` is still first, since nothing else removes
  an atom.
