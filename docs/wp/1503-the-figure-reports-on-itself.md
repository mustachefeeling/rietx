# WP-1503 — the figure reports on itself, and picks a view

Milestone: v1.7 · Status: ✅ 2026-09-30 — report, view="auto", recipe
Depends on: 1470 (1501 soft)

## Goal

`StructureFigure.report` carries the numbers a look would give: the share
of atoms hidden, bonds ending in mid-air, labels that overlap, the empty
share of the frame, and warnings such as a tensor drawn flat. `view="auto"`
ranks low-index directions by those numbers and returns the runners-up.
`fig.recipe` regenerates the picture. The skill says: read the numbers,
iterate small, render large once.

## Context

### Why

An agent pays per look. An image costs about width × height / 750 tokens:
1333 at 1000 px, 213 at 400 px. Each look is also a turn, and a picture
seen three turns ago may be gone after a compaction. A person at a viewer
pays none of this; they rotate and stop when it looks right.

The termination view (v1.3) set the rule for fits: numbers first, the
picture to confirm, since 0 of 6 campaign runs stopped on a package
criterion before one existed. The same rule applies to a figure. MatPlotAgent
(arXiv 2402.11453) and PlotGen (arXiv 2502.00988) close a render, critique,
adjust loop for charts with a multimodal model as the critic. The survey of
2026-09-27 found none for a crystal structure.

### What the critique decided

- **No scalar quality score.** A single number would be the mechanical
  rule the agent-first thesis argues against. The figure exposes evidence,
  the skill carries the checklist, and the model judges.
- **The numbers come from an id pass, not from geometry alone.** Projected
  discs miss the sticks and faces that hide an atom. The raster's numpy
  path already tests depth per primitive, so a variant at a small long side
  (256 px) writing the winning primitive's index gives occlusion for what
  is drawn. Its cost is measured against the 33-43 ms render; if the numpy
  path is slow at 5000 atoms, the kernel gets the id variant.
- **The automatic view searches low-index directions, not the sphere.** A
  presentation figure wants a recognisable projection. The candidates are
  the distinct directions with |u|, |v|, |w| ≤ 2, each with WP-1470's
  default up, scored by hidden share and then empty share, ties broken
  toward the smaller indices. An exact axis view on a cubic cell stacks
  atoms; the figure reports its hidden share and the agent adds `turn=`.
  The search is deterministic and the rotation chosen is returned, so the
  recipe pins it.
- **The recipe is the call, and the geometry is the caller's.** `recipe`
  holds the keyword arguments as passed plus the rotation drawn, JSON
  serialisable. `render_structure(geometry, **fig.recipe)` reproduces the
  bits. A geometry dict of 5000 atoms is megabytes of JSON, so it is saved
  by the caller with `json.dump`, as history nodes store state and never
  curves.

### Design

- **`report`**, a dataclass on the figure:
  - `hidden`: the share of non-boundary atoms with more than 80 % of their
    samples covered, and the list of their indices.
  - `dangling_bonds`: bond halves whose far atom is not drawn.
  - `label_overlaps`: pairs of label boxes that intersect, from the anchors
    the figure already returns.
  - `empty`: the share of the frame with no ink.
  - `cut`: polyhedra and bonds `keep` dropped, from the dict's `note`.
  - `warnings`: strings. A tensor drawn flat (`npd`), a component that
    crosses the frame, a polyhedron count over the atom cap.
- **`view="auto"`**: the search above, and `candidates` on the figure, a
  list of (direction, hidden share, empty share) for the top few, so the
  agent can pick the second without searching.
- **`recipe`** as decided.
- **The skill.** A figure checklist in `api-figure.md`'s reference: read
  `report` before looking; iterate at 400 px and render the final size
  once; when hidden is high, try the next candidate or `turn=`; when a bond
  dangles, widen the extent or `complete=True`; `outline=True` for print.
  A body row is paid for by a cut.

## Non-goals

- A call to a language model from the package.
- An aesthetic score.
- Perspective, fog, ambient occlusion (WP-1470's non-goals).
- A layout engine for labels. Overlaps are reported; moving them is the
  caller's, in matplotlib, from the anchors.

## Tasks

- [x] The id pass on the numpy path at a small long side, and its cost
  quoted beside the render's on one cell and on 4995 atoms. *Numpy alone is
  11.8 ms on one NAC cell and 212 ms at 3143 atoms, against a render of
  17-19 ms and 166-199 ms, so the kernel got the variant (`id_plane` in
  `_kernels_numba.py`): 0.3-0.5 ms and 1.6-1.9 ms. Packing is its own
  vectorised `pack_ids`, since `_pack`'s per-atom loop costs more than the pass.*
- [x] `report` with the five numbers and the warnings; a test on a
  constructed scene where the hidden share and the empty share are known.
- [x] `view="auto"` and `candidates`; a test that the search is
  deterministic and that on the 21 phases the chosen view's hidden share
  is at most the opening view's.
- [x] `recipe` and its round trip, bit-identical.
- [x] The skill checklist, and the token arithmetic for a look in the
  reference.
- [x] Docs in `exports.md`; `api-figure.md` regenerated; the manual
  partition green.
- [x] Tests, pictures to `tests/output/`: the automatic view on rutile,
  fluorapatite and NAC beside the opening view.
- [x] The addition staged in the open milestone's record.

## Acceptance

- The id pass costs under a third of the render at 1000 px on one NAC
  cell, quoted as a range.
- `view="auto"` on the 21 phases never chooses a view with a higher hidden
  share than `"opening"`.
- `render_structure(g, **fig.recipe).image` equals `fig.image` bit for bit.

```sh
.venv/bin/python -m pytest tests/test_render_structure.py
RIETX_COMPILED=0 .venv/bin/python -m pytest tests/test_render_structure.py
.venv/bin/python -m pytest tests/test_skill.py tests/test_manual_api.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Yang, Z. et al. (2024). MatPlotAgent. arXiv:2402.11453.
- Goswami, K. et al. (2025). PlotGen. arXiv:2502.00988.
- The v1.3 milestone record § termination view, for the numbers-first rule.
- WP-1470 D7, D8 and D12 (the array, the anchors, the views).

## Handover log

- **2026-09-30** — closed. A structure figure now says what a look would
  tell you. `StructureFigure.report` gives the share of atoms hidden behind
  others, bonds ending in mid-air, overlapping letters, the empty share of
  the frame, what `keep` cut, and warnings. `view="auto"` searches the
  low-index directions and the opening view and draws the one that hides
  least, returning the runners-up. `recipe` draws the picture again bit for
  bit through JSON. On the 21 measured phases the automatic view hid fewer
  atoms than the opening view on 14 and more on none (mean 18 % to 6 %). An
  agent can now read a number, turn, and look once at the size it keeps.
  Nothing tested whether an agent does so; that is 1504.
  - **Done.** The id pass (`raster.id_plane`, kernel `id_plane` in
    `_kernels_numba.py`, numpy twin, equal plane for plane); `pack_ids`,
    vectorised and separate from `_pack`; `viz/figure3d/report.py`
    (`FigureReport`, `probe`, `look`, `choose_view`); `_labels`/`_dangling`/
    `_empty` in `render.py`; `keep` writes a structured `cut` beside `note`;
    `views.resolve` refuses `"auto"` with a pointer. Skill section "Reading
    the figure before looking" (generated), manual § What the figure says
    about itself, the example's new lines and its test, the v1.6 record.
  - **Measured** (Apple M4, warm, `[dev]`, darwin arm64, no other session
    running). Id pass, kernel, including packing: 0.6-0.8 ms on one NAC cell
    against a render of 17-19 ms (about 4 %, acceptance was a third). Numpy
    path: 11.8 ms on the cell, 212 ms at 3143 atoms, so a build without
    numba pays 0.6x a cell render and 1.3x at 3143 atoms. Report cost in
    `render_structure`: about +2 ms on the cell, +14-55 ms at 3143 atoms
    (`cut._far` is 12 ms of that when a vertex-only atom is undrawn).
    `view="auto"`: 92 ms on the cell, 565 ms at 3143 atoms, 19-127 ms over
    the 21 phases at 256 px. Fast suite: 7060 passed, 157 skipped in 2:25,
    `[dev]`, darwin arm64, before the review's three added cases. Added
    tests: 36 cases in `test_render_structure.py`, 5.96 s summed (21 of them
    the phase sweep, 3.79 s), none in the slow tail.
  - **Design choices the WP did not fix.** The id pass packs its own arrays
    (`_pack` costs more than the pass, and the search runs it ~100 times).
    Candidates and the report's hidden share read one function and one frame
    rule, so the acceptance comparison is exact, but a candidate's `empty`
    is atoms and bonds only while `report.empty` reads the image. Lines and
    faces do not hide an atom. Both signs of each direction are searched
    (98 directions plus the opening view). The winner is often an index-2
    direction (NAC [0, 1, 2], rutile [-2, 0, -1]): the WP ties toward small
    indices only after hidden and empty, so a recognisable axis view loses
    to a cleaner one. That is the place to soften if agents dislike it.
  - **Dropped.** The WP's "a component that crosses the frame" warning: the
    frame is fitted to what is drawn, so nothing crosses it, and I could not
    find the case it meant. `recipe` leaves out `probability`,
    `bond_tolerance`, `phase` and `path`, since they build the geometry or
    write a file and the geometry is the caller's.
  - **Review.** `/code-review high --fix` found and fixed a generator passed
    as `hidden=` being consumed before `_species` read it (nothing hidden,
    silently), and `choose_view` masking a bad `turn=`/`up=` under
    "no view can have up=None"; both have tests. I also fixed three of its
    minor items (the `rp.` alias leaking into the skill file, the warning's
    size, numpy values in the recipe). Left: `probe` round-trips face
    triangles through lists and `look` re-derives the extent `_extent`
    computes, so the two can drift on a change to either.
  - **Gotchas.** `rotation` passed back as `view=` was bit-identical here;
    it was not assumed, it is tested. The `Bash` guard here refuses some
    heredocs at random: write a scratch file and append it. Pictures are in
    `tests/output/figure3d/report_*`.
  - **Next.** 1504 (measure with real agents) is unblocked by this: its
    question is whether reading `report` before looking cuts looks and
    tokens, and whether the agent takes `candidates[1]` or adds `turn=`.
    Run it only from a costed menu the user picks from.

- **2026-09-27** — filed from the session that closed WP-1470. Next: the
  id pass and its cost, since every number here rests on it.
