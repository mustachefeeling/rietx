# WP-1466 — the structure viewer draws coordination polyhedra

Milestone: unscheduled · Status: 🔄 2026-09-26 — claimed by @yue-here
Depends on: 1462
Priority: P3 2026-09-26 — WP-1462 closed, so its one blocker is gone; P1-P9 are confirmed, and only P3's gap measure waits on Brunner & Schwarzenbach (1971)

## Goal

The structure viewer draws coordination polyhedra. A user who never opens a
setting sees the polyhedra a solid-state chemist would draw first, and no
others (`gui/CLAUDE.md` § Defaults).

## Context

### The renderer it extends

WP-1462 closed on 2026-09-26, and its renderer passed the GPU gate as
partial. The gate ran Direct3D 11 over WARP, Mesa llvmpipe and SwiftShader on
GitHub's runners, with no vendor GPU. Folded from that WP's inherited note
on 2026-09-26.

- **The gate is the probe for acceptance 3.** `1462-spike/gate.py` pins the
  canvas at 720 × 540 CSS px, drives one browser through a fixed script, and
  compares every picture with a reference machine's. A polyhedra case in
  that script covers this WP.
- **A context can come without a multisample buffer.** Firefox on WARP
  granted none, so anything drawn through alpha-to-coverage loses its
  coverage there. The spike's faces blend with ordinary alpha, which does
  not depend on it.
- **A payload draws the same on every machine.** The server pins an
  ellipsoid's free principal axes (`structure3d._pin_axes`).

### Why

The maintainer asked for it on 2026-09-25, because many rietx users are
solid-state chemists who know VESTA. WP-1462's spike tested whether the
new renderer can take polyhedra (its § Polyhedra: one translucent pass of
88 lines, the same in three engines), and the view was split out here as
WP-1462's D8.

### What the spike found

The spike's server stand-in is `docs/wp/1462-spike/payloads.py`, and its
measurements are `gap.py` and `results/shell_gaps.txt` there.

- **The bond rule is not a coordination rule.** Under the viewer's
  radius-sum rule (1.15 × the covalent radii), fluorapatite's P reaches
  4 Ca at 3.1-3.2 Å beside its 4 O, so its first hull had 8 vertices.
- **A ligand rule fixes it.** The spike took a centre's non-metal
  neighbours of another element. It gives PO₄, AlF₆ and CaF₈. gemmi carries
  no electronegativity table and neither does rietx.
- **A shell's size under the bond rule is not a default key.** With every
  site as a centre, LaB6's La has 24 B, NAC's Al 6, Ca 8 and Na 4 F, and
  fluorapatite's P 4 O and both Ca 9. Na's 4 is the covalent cutoff cutting
  a large ionic cation's shell short.
- **The largest distance gap finds the shell.** Sort a site's ligand
  distances and take the largest ratio of one to the one before, among the
  first 13. Na's shell is 7 F from 2.19 to 2.58 Å, then 3.63 Å: a ratio of
  1.41. The ratio is 2.08 after Al's 6 F, 1.98 after P's 4 O and 1.54 after
  NAC Ca's 8 F. Fluorapatite's Ca sites show none (1.14 and 1.15), and
  LaB6's La has 24 B at one distance.
- **A shell is matched by position.** The server can find a contact from a
  translated copy of the centre, so a shell collected by atom index came out
  short on 6 of 18 Ca in NAC.
- **A hull needs care.** A square face comes out as two triangles, so an
  edge is drawn only where its two faces are not coplanar. A shell of fewer
  than four atoms, or a planar one such as CO₃, has no 3D hull.

### What others do

From the programs' manuals and docs, surveyed on 2026-09-25. Where a
survey could not confirm a default from a primary source, it is left out.

- **VESTA** builds a polyhedron from a directed bond search: a central
  species, a ligand species, and a distance range from a pair table. Its
  default range is the radius sum plus a tolerance. Polyhedra are opt-in
  per species. Their colour is the central atom's, with opacity and edges
  set apart. The default polyhedral style keeps atoms and bonds visible.
  Its default boundary mode fetches ligands from outside the drawing box,
  so no polyhedron is cut off.
- **Mercury** declares two element lists, the possible centres and the
  possible ligands.
- **Materials Project** builds its bonded graph with CrystalNN, which
  assigns no cation-cation bonds.
- **Daams & Villars (1993)**, read in full, define an atom's environment by
  the maximum-gap rule of Brunner & Schwarzenbach (1971). The distances to
  all neighbours go in a histogram, and the environment is every atom
  before its largest gap. When that shell encloses another atom, puts an
  atom on a face, or shows no clear gap, they take the maximum convex
  volume instead. That is the largest convex volume around the centre alone
  with every coordinating atom at a vertex. Where two gaps are about equal,
  they choose the reading that keeps the structure's environment types
  fewest. An environment whose atoms all lie on one side of the centre, such
  as the "loose triangle" of S in MoS₂, is irregular and is not a
  polyhedron. Boron's B₁₂ and B₆ clusters have no central atom and are
  drawn as clusters. Their subject is intermetallics, so every species
  counts as a neighbour.

## Decisions this WP takes

The maintainer confirmed P1-P8 on 2026-09-26, with three amendments from
a critical pass that day (in P2, P5 and P7), and chose the recommended P9.

- **P1. The server builds the polyhedra.** `/api/structure3d` gains a
  `polyhedra` arm: the centre's atom index, the vertex positions, outward
  triangles and edges. It is chemistry and geometry, and WP-1015's founding
  rule keeps both on the server.
- **P2. A ligand is a non-metal neighbour of another element, other than
  hydrogen.** This is
  Mercury's ligand list derived rather than declared, and CrystalNN's "no
  cation-cation bonds". An intermetallic therefore gets no polyhedra by
  default, where Daams & Villars would draw every atom's environment.
  Showing one atom's environment on request is the intermetallic answer,
  and is out of scope. The non-metal test is gemmi's `Element.is_metal`,
  which `structure3d.is_metal` already reads.
  *Amended 2026-09-26: hydrogen is never a ligand.* It is a non-metal, so a
  hydroxide's cation reaches it. On brucite from textbook coordinates, Mg
  has 6 O at 2.10 Å and then 6 H at 2.68 Å, and counting H drops the gap
  ratio from 1.80 to 1.28. That is inside P4's undecided window.
- **P3. The shell ends at the largest gap in the ligand distances,** as
  Daams & Villars apply Brunner & Schwarzenbach. The gap is measured the way
  Brunner & Schwarzenbach measure it once that paper is read. The spike's
  successive-distance ratio stands in until then.
- **P4. A shell is drawn only when it is a polyhedron.** It needs 4 or more
  ligands, the centre strictly inside the hull, every ligand at a hull
  vertex (Daams & Villars' convex-volume condition), and a clear gap. The
  gap threshold lies between 1.15 and 1.41 on three phases and is measured
  on more before it is fixed.
- **P5. By default, shells of 4 to 6 ligands are drawn.** Tetrahedra and
  octahedra are the framework a chemist reads first. Shells of 7 or more
  qualify and start hidden, because with them NAC's cell fills with
  overlapping polyhedra. On the three phases the default draws PO₄ and AlF₆
  and hides CaF₈ and NaF₇. The legend switches polyhedra per centre species.
  *Amended 2026-09-26 from "7 and 8"*, so a perovskite's 12-coordinate A
  site is covered.
- **P6. The look follows VESTA, except inside a polyhedron.** Faces take the
  centre's colour at alpha 0.55, and edges a darker ink as WP-1462's D9
  quads. The centre atom stays. The sticks from the centre to its ligands
  are hidden, where VESTA keeps them. The gap shell and the bond rule can
  disagree (Na: 4 sticks, 7 vertices), and drawing both shows the
  contradiction.
- **P7. A polyhedron is never cut off.** Its ligands are drawn as atoms even
  outside the cell, as VESTA's default boundary mode does. The server adds
  them as partners. *Amended 2026-09-26:* the viewer draws at most
  `MAX_ATOMS` (400) atoms and trims partners past it, so a polyhedron that
  loses a vertex to that cap is not drawn, and the payload's note counts it.
- **P8. Polyhedra show in ball mode and hide in ellipsoid mode.** Faces
  would cover the ADPs the ellipsoid mode exists to show. One toggle
  overrides either.
- **P9. A split site draws no polyhedron.** *Added 2026-09-26.* Atoms at one
  position count once, so a mixed site draws one polyhedron in the first
  species' colour. A shell holding two ligands closer to each other than to
  the centre is a split site, and it is not drawn. A site with vacancies
  and no split still draws. Daams & Villars excluded every partly occupied
  point set, which would lose each BO₆ of an oxygen-deficient perovskite.
  None of the four test CIFs is disordered, so task 3 measures P9 on one.

## Where it will bite

- **Three phases are not a threshold.** P4's gap and P5's split need a
  wider set, at least spinel, perovskite, garnet, rutile, olivine, zircon,
  corundum, fluorite, wurtzite and quartz beside the three here.
- **Two nearly equal gaps.** Daams & Villars resolve a tie by the fewest
  environment types. A display default can decline to draw instead, and
  the margin that counts as a tie is measured.
- **Disorder.** P9 is a rule without a measurement yet.
- **An anion can centre anions.** P2 admits a non-metal centre with
  non-metal ligands of another element. Fluorapatite's F gets 6 O at
  3.13 Å, and only P4's threshold rejects it, at a ratio of 1.15. Task 3
  checks whether the threshold alone holds that line on the wider set.
- **Translucency ordering** holds while polyhedra do not interpenetrate
  (WP-1462 § Polyhedra).

## Non-goals

- Cluster polyhedra (B₆, B₁₂), anion-centred polyhedra (OCa₄), and the
  all-atom environments of intermetallics.
- The octant cut-out, and any rule heavier than the gap (Voronoi solid
  angles, effective coordination numbers, CrystalNN).
- A bond rule built on the gap. The bond tolerance stays as it is.

## Tasks

- [x] The maintainer confirms P1-P8, and this file records which (2026-09-26: all, with amendments to P2, P5 and P7, and P9 added)
- [ ] Read Brunner & Schwarzenbach (1971) (the maintainer supplies it) and set P3's gap measure to theirs
- [ ] Measure P4, P5 and P9 on the wider phase set, a disordered phase among it, and record the threshold and the table
- [x] Server: the `polyhedra` arm, the ligand rule, the gap shell, the polyhedron conditions and the vertex partners, with tests in `tests/test_structure3d.py` (2026-09-26; the gap measure is the stand-in and `POLYHEDRON_GAP` provisional until tasks 2 and 3)
- [ ] Renderer: the translucent pass, the edges, and hover on a polyhedron (centre, ligand count, mean distance); a polyhedra case in `1462-spike/gate.py`'s script
- [ ] GUI: the per-species toggles, P5's and P8's defaults, and the caption saying what is drawn
- [ ] Docs: the structure viewer paragraphs in `gui/CLAUDE.md` and the GUI guide

## Acceptance

1. **Defaults:** on the measured phase set, the default picture draws the
   polyhedra this file's table lists for each phase, and no others.
2. **Every drawn polyhedron is one:** a test holds each to P4.
3. **Browsers:** Chromium, WebKit and Firefox draw it the same, and a
   trackball drag holds a p95 frame of 17.7 ms or less.

```sh
.venv/bin/python -m pytest tests/test_structure3d.py tests/test_gui_server.py
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Daams, J. L. C. & Villars, P. (1993). Atomic environment classification of
  the rhombohedral "intermetallic" structure types. The maintainer's copy
  (`rietx-refs-misc`) does not carry the journal details.
- Brunner, G. O. & Schwarzenbach, D. (1971). *Z. Kristallogr.* 133, 127.
  The maximum-gap rule, not yet read here.
- Momma, K. & Izumi, F. (2011). VESTA 3. *J. Appl. Cryst.* 44, 1272-1276,
  and the VESTA manual, chapters 8 and 12.
- Pan, H. et al. (2021). *Inorg. Chem.*, doi:10.1021/acs.inorgchem.0c02996,
  for CrystalNN. Not read here.
- WP-1462 and its spike, `docs/wp/1462-spike/`.

## Handover log

- **2026-09-25** — filed from WP-1462's session as its D8, after the
  maintainer asked for polyhedra and for good defaults. The spike's
  measurements are WP-1462's. Daams & Villars (1993) was read in full, and
  the survey of VESTA, Mercury and Materials Project came from their docs.
  *Next:* the maintainer confirms P1-P8 and supplies Brunner &
  Schwarzenbach (1971).
