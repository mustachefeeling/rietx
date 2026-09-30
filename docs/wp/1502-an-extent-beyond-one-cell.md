# WP-1502 — an extent beyond one cell

Milestone: v1.7 · Status: 🔄 2026-09-30 — claimed by @yue-here
Depends on: 1470 (1501 soft)
Priority: P3 2026-09-27 — a view over what the model already knows; VESTA draws a supercell today, and a P1 expansion by hand is the workaround

## Goal

`build(structure, extent=((0, 2), (0, 2), (0, 1)))` returns the geometry of
a 2×2×1 block in the same dict shape as today, bonds and polyhedra
consistent, at a cost that grows with the atoms drawn. Each atom carries a
periodic identity, so a motif's periodicity can be reported and a cut can
be completed past its face.

## Context

### Measured 2026-09-27

On an Apple M4, 1000 px, 2×2 supersampling, warm:

| Atoms | Bonds | Polyhedra | Ball render | Ellipsoid render |
|---|---|---|---|---|
| 185 (one NAC cell) | 255 | 34 | 40-43 ms | 33-34 ms |
| 1480 (2×2×2, tiled dict) | 2040 | 272 | 114-143 ms | 95-97 ms |
| 4995 (3×3×3, tiled dict) | 6885 | 918 | 299-304 ms | 260-267 ms |

The renderer is not the limit. The builder is. `structure3d._bonds`
computes 27 dense N×N distance matrices, one per lattice shift. A P1
2×2×2 NAC (672 atoms in the asymmetric unit, 1064 drawn) took 0.4 s to
build, and at 10⁴ atoms one matrix is 800 MB. Tiling the built dict by
hand is no substitute: it drew 1480 atoms where the true count is 1064,
because every face atom was duplicated once per neighbouring cell.

### What `build()` does today

Today's dict is the extent (0, 1)³. `_boundary_shifts` duplicates an atom
on a face, edge or corner onto the opposite ones (`boundary=True`), so a
corner atom appears at all eight corners. `_partners` adds a bonded
neighbour outside the cell so a bond that leaves the cell is drawn leaving
it. `_polyhedra` adds a ligand no stick reached (`vertex_only`). VESTA's
Boundary dialog and its "search additional atoms" options are the same
three rules over a general box, and Jmol's `load {2 2 2}` and `PACKED`
the same box with the same duplication.

### Design

- **The bond search runs once, over the orbit in the home cell.** Each
  bond is recorded as (orbit atom i, orbit atom j, lattice shift). The 27
  shifts are already the loop `_bonds` runs. An extent is then a
  translation of that graph: the cost is N_cell² × 27 once, then linear in
  the images drawn. A cell list beyond a few thousand orbit atoms is added
  only if a measurement asks for it.
- **Atoms gain a periodic identity**, `"image": [orbit_index, [n1, n2,
  n3]]`. `boundary` becomes "outside the extent's half-open box", with
  duplicates at the extent's faces by today's rule. `extent=None` means
  (0, 1)³ and the dict is bit-identical to today's on the 21 phases of
  `tests/data/polyhedra_phases.json`. A committed snapshot of the dict cannot
  carry that check. `build()` breaks ties in distance on the last bit, so its
  order moves with the platform (#498's CI). The scene corpus
  (`tests/data/gui/scene_cases.json`) replays committed payloads and pins
  the scene rules, not the builder. The new `image` field rewrites it once.
- **Polyhedra follow their centres.** A centre inside the extent draws its
  polyhedron whole, ligands wherever they lie. VESTA never truncates one.
- **The cap stays the GUI's.** `max_atoms` keeps its default of 400 for
  `GET /api/structure3d`. A Python caller passes a larger one, and `note`
  reports the atom count and the build time.
- **`periodicity(geometry, mask) -> int`**, 0 to 3, from the lattice
  translations accumulated around cycles of the kept atoms' bond graph on
  their image labels (Larsen et al. 2019, pymatgen's
  `get_dimensionality_larsen`). A molecule is 0, a chain 1, a layer 2, a
  framework 3. It is a function of a mask, so WP-1501's `component` needs
  no second return value.
- **`keep(..., complete=True)` completes from the periodic graph**, so a
  slab keeps whole octahedra at its faces and a bond never ends in mid-air
  unless the caller asked for that.

### Consumers of the dict

`gui/src/lib/structure3d.ts`, `viz/figure3d/scene.py`, the browser parity
row and `test_structure3d.py` read `atoms`, `bonds` and `polyhedra`. A new
field is additive. A changed meaning of `boundary` is not, so the default
extent must leave it as it is.

### Inherited

- **From WP-1468 (2026-09-28).** Only an atom among the first `n_cell` of
  `atoms` (the cell's own images and their boundary duplicates) is a
  polyhedron centre; a bond partner or a vertex outside is not. The GUI's
  double-click on such an image falls back to its site's nearest centred
  polyhedron (`focusedPolyhedra`), which an extent that makes more atoms
  centres changes. Each image also carries the number of the rotation that
  made it, server-side only (`_turn`, stripped from the dict), because two
  images of a negative disorder group coexist only when one rotation made
  both. An image the extent adds by a lattice translation keeps its parent's.
- **From WP-1501 (2026-09-30).** `keep`, `complete=` and `component` act on
  the finite built graph, and `component(via="corners")` on NAC returns 168 of
  185 atoms because two images of one atom are two atoms. A periodic identity
  (which image is the same atom) is what makes a motif's piece finite, and only
  this WP can supply it. `component` with `via="edges"`/`"faces"` starts only
  from a polyhedron's centre. A polyhedron's `bonds` are found by position, so
  their `i` and `j` can be periodic twins of its centre and vertices: an extent
  that adds atoms must keep that, since `keep` renumbers them by index.

## Non-goals

- A GUI control for the extent.
- A supercell as a `Structure`. A P1 expansion is a model change and
  belongs to the crystallography, if anywhere.
- A cell list or KD-tree before a measurement demands one.
- A packing diagram or a surface slab with vacuum (`ase.build.surface`).

## Tasks

- [x] The bond graph over the home-cell orbit with shifts, and the
  translation that instantiates an extent; the default bit-identical on
  the 21 phases, asserted as dict equality. *Built as the cell's own result
  translated and matched by image (`_tile`), not as a second graph; see the
  handover. Bit-identity held by leaving the default path untouched, checked
  once against HEAD's module (0 of 21 differ besides the new fields).*
- [x] `image` on every atom; `boundary` from the extent's box; the corner
  rule generalised.
- [x] Polyhedra for every centre in the extent; `note` with the count and
  the time.
- [x] `periodicity()`; a test that gives rutile's edge-sharing chain 1,
  gypsum's layer 2, calcite's CO₃ group 0 and NAC's framework 3, each
  looked at.
- [x] `keep(complete=True)` reaching the periodic graph.
- [ ] The cost curve: build time at 1×1×1, 2×2×2 and 3×3×3 on NAC and on
  fluorapatite, quoted as ranges, against 0.4 s for the P1 2×2×2 by hand.
- [ ] Docs: the extent in `exports.md`, `api-figure.md` regenerated, the
  skill's reference row.
- [ ] Tests, pictures to `tests/output/`: a 2×2×1 NAC block, a (001) slab
  of fluorapatite with complete polyhedra.
- [ ] The addition staged in the open milestone's record.

## Acceptance

- `build(nac, extent=((0, 2),) * 3)["atoms"]` counts 1064 atoms inside the
  box plus the face duplicates the corner rule adds, and no other.
- Build time at 3×3×3 on NAC is under the 0.4 s the 2×2×2 P1 cost by
  hand.
- `extent=None` is bit-identical to today's dict on all 21 phases.

```sh
.venv/bin/python -m pytest tests/test_structure3d.py tests/test_render_structure.py
npm --prefix gui test
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Larsen, P. M., Pandey, M., Strange, M. & Jacobsen, K. W. (2019). Definition
  of a scoring parameter to identify low-dimensional materials components.
  *Phys. Rev. Materials* 3, 034003.
- VESTA manual ch. 10 § 10.1.1 (boundary), ch. 8 § 8.1 (search modes).
- Jmol `load {i j k}` and `PACKED`; OVITO `ReplicateModifier(num_x, num_y,
  num_z, adjust_box)`; ASE `Atoms.repeat`; pymatgen `make_supercell`.

## Handover log

- **2026-09-27** — filed from the session that closed WP-1470, with the
  timings in Context. Next: the bond graph over the orbit, since the
  default's bit-identity is the test everything else rests on.
- **2026-09-27** — synced with #498's CI fix. The scene corpus no longer
  rebuilds its payloads, so it pins the scene rules and not `build()`. The
  default's bit-identity needs a check that survives the platform's tie
  order, and Design says so.
