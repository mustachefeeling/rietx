# WP-1503 — the figure reports on itself, and picks a view

Milestone: v1.7 · Status: 🔄 2026-09-30 — claimed by @yue-here
Depends on: 1470 (1501 soft)
Priority: P3 2026-09-27 — an agent can look at its picture today; this makes each look count, and nothing is wrong without it

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
- [ ] The skill checklist, and the token arithmetic for a look in the
  reference.
- [ ] Docs in `exports.md`; `api-figure.md` regenerated; the manual
  partition green.
- [ ] Tests, pictures to `tests/output/`: the automatic view on rutile,
  fluorapatite and NAC beside the opening view.
- [ ] The addition staged in the open milestone's record.

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

- **2026-09-27** — filed from the session that closed WP-1470. Next: the
  id pass and its cost, since every number here rests on it.
