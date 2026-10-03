# WP-1502 — an extent beyond one cell

Milestone: rietview · Status: ✅ 2026-09-30 — build(extent=), image on every atom, periodicity(), keep by far end
Depends on: 1470 (1501 soft)

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
- [x] The cost curve: build time at 1×1×1, 2×2×2 and 3×3×3 on NAC and on
  fluorapatite, quoted as ranges, against 0.4 s for the P1 2×2×2 by hand.
  *Warm, Apple M4, 7 builds each: NAC 14-30, 23-38, 44-62 ms (185, 1064, 3143
  atoms); fluorapatite 6-7, 11-30, 22-41 ms (106, 576, 1662 atoms). The P1 2×2×2
  built by hand: NAC 377-395 ms, fluorapatite 131-148 ms.*
- [x] Docs: the extent in `exports.md`, `api-figure.md` regenerated, the
  skill's reference row.
- [x] Tests, pictures to `tests/output/`: a 2×2×1 NAC block, a (001) slab
  of fluorapatite with complete polyhedra.
- [x] The addition staged in the open milestone's record.

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

- **2026-09-30** — closed. A figure can now draw a block of cells, such as
  2×2×1 or 3×3×3, from Python, in tens of milliseconds where building the same
  crystal as a P1 cell by hand took about 0.4 s. Each atom now says which atom
  of the cell it is and by which lattice translation it was moved, so two images
  of one atom are no longer mistaken for two atoms. That makes a motif's
  periodicity readable: rutile's edge-sharing chain reads 1, gypsum's layer 2,
  a carbonate group 0 and NAC's framework 3. A cut that keeps the whole
  polyhedra at a slab's faces no longer leaves a bond ending in mid-air. The
  design differs from the WP text in one way, recorded below.
  - **Done.** `build(extent=)` in `gui/structure3d.py`: the one cell is built as
    before and `_tile` instantiates it over the cells, matching atoms, bonds and
    polyhedra by exact image `(orbit index, n)`. Payload gained `image` (every
    atom), `n_cell` and `extent`; `corners` frames the block; `note` carries the
    count and time. `viz/figure3d/cut.py`: `periodicity`, `_far` (a bond's far
    end found by image), `keep` and `component(via="bonds")` use it, `keep`
    carries `n_cell`. Exported through `rietx.viz`. `tests/test_structure_extent.py`
    (13 tests, 40 cases), the example, `exports.md`, the skill's `api-figure.md`
    and its two copies, the v1.6 record. The scene corpus was rewritten once.
  - **Design changed.** The WP planned a bond graph over the orbit with lattice
    shifts. I translated the cell's own result instead. The default path is then
    untouched, so `extent=None` is bit-identical by construction: checked once
    against HEAD's module, 0 of 21 phases differ apart from the new fields. A
    committed check cannot carry that (the WP says why), so the test pins the
    translation's identity element instead (`_tile` over `(0, 1)³` equals the
    cell on atoms, bonds and polyhedra, 21 phases). The bond search still runs
    once, over the home cell.
  - **Measured** (Apple M4, warm, 7 builds, `[dev]`, darwin arm64, no other
    suite running). NAC 1×1×1, 2×2×2, 3×3×3: 14-30, 23-38, 44-62 ms for 185,
    1064, 3143 atoms. Fluorapatite: 6-7, 11-30, 22-41 ms for 106, 576, 1662
    atoms. The P1 2×2×2 by hand: NAC 377-395 ms, fluorapatite 131-148 ms. NAC
    2×2×2 holds 672 atoms in the box, 696 with face copies, 1064 with bond
    neighbours and vertex ligands, which equals the P1 expansion's 1064. The
    acceptance line's "1064 atoms inside the box plus the face duplicates" reads
    that way: 672 are inside. A block equals a from-scratch P1 cell of that size
    on atoms, bonds and polyhedra for NAC 2×2×2, LaB6 3×2×2, gypsum 2×1×2,
    quartz 2×2×1 and rutile 2×3×1. Fast suite, `[dev]`, darwin arm64, worktree
    venv: 7024 passed, 157 skipped in 127 s; the session added 40 cases in
    `test_structure_extent.py` (13 tests, 6.2 s of the fast run, none in the slow
    tail), and the first run's 7022 plus the review's two tests is 7024 exactly.
    Vitest 581 passed and `svelte-check` 0 errors under node v26. The full
    selection did not run: the change touches a viewer, not a measured number.
  - **Review** (`/code-review high --fix`): three fixes landed. A large extent
    built every cell before the cap raised (8.7 s for 30³); it now raises in
    18 ms. `keep` left `n_cell` past the end of the list. The example's new
    picture was not checked. Declined: the wall-clock in `note` makes two builds
    of one block unequal (the WP asked for the time there; it bites a caller
    comparing payloads, so a later change could move it beside the dict);
    `max_atoms` bounds the block and not the neighbours drawn past it (documented);
    `_far` loops per bond, cheap at these sizes.
  - **Gotchas.** (1) Two structure-builders compare by position only to a
    rounding: a coordinate near 2.29685 keys differently in two builds, so the
    tests shift off the tie first. (2) A P1 supercell is an oracle only up to
    `BOUNDARY_TOL`, which is a fraction of the cell: fluorapatite's Ca1 at
    z = 0.002 gets a face copy in the doubled cell and not in the block, so
    fluorapatite is not in the oracle list. (3) The old default path can draw a
    bond neighbour and a vertex-only ligand at one spot when their rounded
    positions differ (LaB6 in a 3×2×2 P1 cell, two atoms). The block matches by
    exact image and cannot; the default path was left alone as the bit-identical
    baseline, and this is the sibling I deliberately did not fix. (4) A polyhedron
    cut from rutile reads 1, not 0: two of its O are one atom a lattice vector
    apart, which is the chain's bridge. (5) `keep` and `component` need `image`
    on the atoms, so a payload saved before this WP raises `KeyError`; forwarded
    to 1505.
  - **Forwarded.** To 1505's `### Inherited`: the new fields, `_tile` and the
    old-payload `KeyError`. 1504 depends on 1501, 1502 and 1503 and is unblocked
    on this side.
  - **Next.** 1503 (the figure reports on itself) is the open WP that can now
    describe an extent, since `note` and `n_cell` exist; it should decide first
    whether the report quotes the build time, given the declined finding above.

- **2026-09-27** — filed from the session that closed WP-1470, with the
  timings in Context. Next: the bond graph over the orbit, since the
  default's bit-identity is the test everything else rests on.
- **2026-09-27** — synced with #498's CI fix. The scene corpus no longer
  rebuilds its payloads, so it pins the scene rules and not `build()`. The
  default's bit-identity needs a check that survives the platform's tie
  order, and Design says so.
