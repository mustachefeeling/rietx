# WP-1531 — what the promo figures found: a trimmed cell the report calls fine, a bond through a face, labels on atoms, polyhedra without their far ends

Milestone: unscheduled · Status: ✅ 2026-10-02 — closed, PR #671
Track: Render what the fit already knows
Depends on: — (1501, 1502, 1503 and 1529 are closed; they built the surface these defects sit in)

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
- [x] #666: label placement clear of atoms and bonds, and the two new overlap
      counts in the report (both twins if the scene module moves)
- [x] #667: `complete="polyhedra"` / `"bonds"`
- [x] Tests, with the issues' reproductions as cases and a rendered PNG of
      each to `tests/output/`
- [x] Skill: the figure rows that tell an agent to trust `fig.report` say
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

- **2026-10-02** — closed, all six tasks, in one session with WP-1533 under the
  `/wp-lanes` trial (PR #671).

  A figure's report no longer calls a broken figure fine. A cell too big for
  the atom cap now raises when drawn from a structure, and names the count to
  pass. A trimmed geometry handed in says what the cap left out, and its
  dangling bonds are counted. A polyhedron now lists every bond of its own.
  The cause was a rounding tie in the position key, which also drew a second
  atom on four of LaB6's corners. Labels move off atoms and bonds, and the
  report counts any that could not. A window can be completed with whole
  polyhedra and nothing hanging off its edge.

  *Done.*
  - #665 (`82cc6ec9`, `f62da502`): `render_structure(max_atoms=)` builds at
    the cap and raises past it on the cell's own atoms. It rebuilds uncapped
    when the cap kept out neighbours or polyhedra, which it does not bound,
    as `build(extent=)` does not. `build`'s one-cell trim stays the GUI's.
    Its payload now has `cut = {atoms, neighbours, segments, polyhedra}`,
    `keep` carries every key, and `_dangling` counts a bond whose far end the
    geometry does not hold. Each cap loss gets a warning.
  - #664 (`69793ccd`): the cause was `_keys`, not `_tile`. It rounded to
    1e-6 Å, and a short CIF decimal times a short cell length lands on a half
    step: I1 at 0.0605 × 51.959 = 3.1435195 Å, LaB6's B at 2.0787985 Å. A
    bond's far end and the polyhedron vertex there are two computations
    4e-15 Å apart, which rounded to two keys. The bins now start 2 − φ of a
    step off the grid.
  - #666 (`9b338001`): eight places per label, up-right first, kept clear of
    projected atom ellipses, widened bond halves and earlier labels. The
    report gains `label_atom_overlaps` and `label_bond_overlaps` from the
    same test.
  - #667 (`32448e71`): `keep(complete="polyhedra" | "bonds")`.
  - Skill row (`d0b88675`), and the `/code-review` pass (`f5f5d501`).
  - `session_usage.py lanes` (`31c2434e`) found none of this session's
    lanes: the session entered its worktree after starting, so its agents'
    transcripts sat under the worktree's project directory. `subagent_dirs`
    looks in both.

  *Measured* (`[dev]` venv, macOS 26.6.2 arm64):
  - HKUST-1 (COD 4002052) trimmed to 400: `cut["atoms"]` 248,
    `cut["neighbours"]` 96, `dangling_bonds` 96. Drawn whole at
    `max_atoms=648`: 744 atoms, 0 dangling.
  - (BA)₂(MA)₂Pb₃I₁₀ (COD 4003235): 3 of the cell's 17 PbI₆, 12 of the
    2×1×2 block's 62 and 245 of the 7×3×7 block's 1911 left a bond off
    before the fix, and 0 after. LaB6: 4 of 8 in the cell, 12 of 27 in
    2×2×2. Across 21 measured phases and the test CIFs only LaB6 (4 fewer
    atoms) and the RP phase (3 fewer) changed, and no bond count moved.
  - Paracetamol (COD 2104364) at 800 px, label/atom/bond overlaps: ball
    1/2/15 before and 0/0/0 after, ellipsoid 0/3/14 and 0/0/1 (C9 has
    four bonds and no clear place). Label cost: a 185-atom cell 13 to 25 ms,
    a 2412-atom labelled block 82 to 589 ms.
  - YBa₂Cu₃O₇ (COD 9007744), a window of 44 atoms: `complete=True` adds 80
    and `complete="polyhedra"` adds 30.
  - Fast selection: 7898 passed, 160 skipped, 1 failed. The failure is
    `test_numpy_path_bit_identical_to_golden[toy_anomalous]` at 1.6e-11:
    #669 re-baselined that golden for macOS 27.0.1, and this machine runs
    26.6.2. The branch touches neither the golden nor the anomalous path.
    23 test functions were added with 46 cases. The slowest is
    `test_a_cell_drawn_whole_has_no_stubs_and_replays` at 4.8 s in the
    loaded run (1.1 s serial), not marked slow. Main's count was not
    re-measured. vitest 583 passed under node v22.15.0 (the default here
    is v20.11.1, too old). The full suite did not run: no change reaches a
    refinement number.
  - Lanes, from `session_usage.py lanes 46f97a56-…` (both WPs' items):

    | lane | est | requests | main at dispatch | re-read | main requests | left in main | fixed | redo | lane $ | in-session $ | saved $ |
    |---|---|---|---|---|---|---|---|---|---|---|---|
    | #665-cap-rule | 25 | 58 | 171K | 24K | 13 | 31K | 1 | 0 | 2.84 | 7.19 | +2.81 |
    | #664-face-centre-bond | 25 | 58 | 209K | 20K | 9 | 14K | 0 | 0 | 2.91 | 7.72 | +3.98 |
    | #666-label-placement | 30 | 65 | 223K | 15K | 8 | 20K | 0 | 0 | 3.46 | 9.16 | +4.75 |
    | stick-argument | 22 | 60 | 284K | 12K | 5 | 12K | 0 | 0 | 2.49 | 5.99 | +2.95 |
    | furniture-to_px | 22 | 50 | 334K | 2K | 7 | 13K | 1 | 0 | 2.13 | 5.02 | +2.23 |

    Kept: #667-complete-modes estimated 14, took 20, at 244K; cell-switch
    estimated 10, took 11, at 268K. Trial row: +$16.73, +39 % of the
    session. Lanes took 2.27× their estimates. The baseline replay with
    this session's numbers gives the selective policy −19 % across 64
    sessions.

  *Not done, deliberately.*
  - The position key can still split a point that two computations put
    either side of a shifted edge. The chance is about 4e-9 a point for
    positions off the decimal grid. Matching within a tolerance is the
    deeper fix.
  - `_tile` copies the one cell's `segments` count to a block, so a block
    past the bond cap undercounts. It bites only past 4000 segments in one
    cell.
  - A label's own atom, the cell edges and polyhedron faces are not label
    obstacles. Labels cost grows with atoms times shapes near each label.
  - Two `/code-review` findings were declined with these: the cost of
    labels on large blocks, and the key's remaining split chance.

  Next: none here. The follow-ups went to WP-1468 (a theme-dependent C,
  cropping, a polyhedron colour), WP-1504 (whether `auto` should rank by
  occlusion) and WP-1903 (the lane tool's fix and this trial row).

- **2026-10-02** — created, from the 2026-10-02 issue triage (issues #664,
  #665, #666, #667). Checked against the tree at `ca9bda29`: all four
  reproductions print the issues' numbers exactly (#664 with the B_iso bound
  widened in-process in place of PR #663). No open WP owns it: 1501 to 1503
  and 1529 built this surface and are closed, 1504 is the measurement, and
  1468 is polyhedron chemistry. Next: #665 first, since it is the one where
  the report says a broken figure is fine.
