# WP-1529 — what round B found in the figure surface: the skill names figures, a cell draws no bare centre, the report counts every stub

Milestone: v1.7 · Status: 🔄 2026-10-01 — claimed by @yue-here
Depends on: —
Priority: P3 2026-10-01 — a workaround covers each (reading the package, a hand mask), and WP-1504's next round waits on all three

## Goal

An agent asked for a structure figure finds the figure surface through the
skill. A single cell draws no atom of a polyhedron-centre element without its
polyhedron. And `fig.report.dangling_bonds` no longer reads 0 on a figure
covered in bond halves. WP-1504 then reruns its round on this tree.

## Context

### What WP-1504's round B measured

On 2026-10-01, under WP-1504's protocol amendment 1.2: 28 runs, one per task,
model (Sonnet, Opus) and condition (the WP-1470 tree, the WP-1503 tree). The
record is `docs/wp/1504-eval/runs/`, and the table is in 1504's handover log.

- **The skill does not route a figure request to itself.** Its description
  reads, verbatim: "Refine powder diffraction data with the rietx Python
  package (Rietveld, Le Bail, Pawley, phase quantification, indexing an
  unknown cell, judging a FitReport) — read it before the first fit()
  whenever a task involves a powder pattern, a CIF to fit against one, phase
  fractions, a cell to determine, an in-situ series, a batch of candidates or
  of patterns fitted as separate jobs, or an existing rietx result to judge."
  It names no figure. The skill was opened in 5 of 28 runs. Opus found the
  figure functions by listing the package and reading `figure3d`'s source.
  Sonnet drew by hand in matplotlib in 8 of 14 runs and finished one of them.
  The description is at 416 characters of the 1024 the spec allows
  (`tests/test_skill.py`, `DESCRIPTION_MAX`).
- **One cell draws bare centres.** `rietx.gui.structure3d.build` brings in
  the far ends of bonds just outside the cell, and those atoms carry no
  polyhedron. Measured on the `tests/data/polyhedra_phases.json` rows:
  rutile draws 2 Ti bare, at (½, ½, −½) and (½, ½, 1½); fluorapatite draws
  4 P bare, beyond the side faces; NAC, gypsum, calcite and LaB₆ draw none.
  *Superseded in part 2026-10-01:* calcite drew 8 Ca bare too, all on a site
  whose CaO₆ is drawn by default. Shells hidden by default add 26 Ca in
  fluorapatite, 9 Ca and 7 Na in NAC and 8 Ca in gypsum.
  `polyhedra_dropped` is empty for all six, because those polyhedra were
  never built rather than dropped. Both Opus fluorapatite runs failed the
  judge's "polyhedra are whole" check on exactly this. Dropping the bare atoms
  with `keep` leaves no dangling bond and cuts 4 bonds in each phase, so the
  hand mask works. But no verb names them and no report field counts them.
- **`hidden=` leaves stubs that the report cannot see.**
  `render_structure(..., hidden=("Ca",))` removes the Ca and draws the O half
  of every Ca–O bond. On calcite that covers the figure in stubs while
  `report.dangling_bonds` reads 0. LaB₆ with `hidden=("La",)` does the same.
  The report leaves those halves out on purpose (the `FigureReport`
  docstring, `src/rietx/viz/figure3d/report.py`; the count is `_dangling` in
  `render.py`). So an agent that reads the report rather than the picture is
  told the figure is clean. Agents printed the report whole in 10 of 14
  after-runs, so the report is what they read.

### Where each fix lives

- The description: `docs/skill/rietx/SKILL.md`'s frontmatter. Its budget is
  `tests/test_skill.py`'s, and `rietx skill --install . --copy` re-syncs the
  two committed copies (root CLAUDE.md § skill).
- Bare centres: `build` in `src/rietx/gui/structure3d.py`. The GUI's 3D viewer
  draws the same dict, so the fix reaches the GUI too (`gui/CLAUDE.md`). Two
  designs, and the session chooses after looking at how VESTA treats a
  polyhedron-centre atom found by a bond search: build the missing vertices
  so the polyhedron is drawn, or leave such an atom out of the picture.
- Stubs: decide whether `hidden=` drops both halves of a bond, or the report
  counts the halves it leaves. Either way the picture and the report have to
  agree. The `hidden=` docstring and `api-figure.md` say what it does today.

### Constraints

- `render_structure` draws as the GUI's structure viewer draws. A change to
  `build` changes both, and `tests/test_structure3d.py`'s measured-phase test
  pins the default polyhedra per phase.
- WP-1504's reference figures (`docs/wp/1504-eval/reference_figures.py`)
  carry the hand workarounds: `without_bare_centres` and `carbonate_groups`.
  Once this lands, those recipes should not need them, and that is a check.

## Non-goals

- Rerunning the round. That is WP-1504's, on a third condition pinned to
  this WP's merge.
- Any other figure feature. Round B gives no evidence for one.
- WP-1505's split of the figure code into its own package.

## Tasks

- [x] The skill's description names structure figures, within its budget;
  the two committed copies re-synced.
- [x] One cell draws no bare centre: the design chosen against VESTA's
  behaviour, and a test over the six round-B phases (rutile 2 Ti and
  fluorapatite 4 P today, 0 after).
- [x] `hidden=` and `dangling_bonds` agree: a test on calcite and LaB₆.
- [ ] The GUI checked against the changed `build` (`gui/CLAUDE.md`).
- [ ] Tests + PNGs to `tests/output/`.
- [ ] Skill: `api-figure.md` regenerated (`docs/skill/make_api_index.py`) and
  its `hidden=` sentence corrected, beside the description task.
- [ ] WP-1504's `### Inherited`: the merge commit to pin as a third condition.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_structure3d.py tests/test_render_structure.py tests/test_figure_cut.py tests/test_figure_boundary.py tests/test_skill.py tests/test_skill_cli.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The new tests show 0 bare centres over the six phases, and a nonzero
`dangling_bonds` or no drawn stub wherever `hidden=` removes a bonded species.

## References

- WP-1504's handover log (round B) and `docs/wp/1504-eval/PROTOCOL.md`
  § Amendment 1.2.
- VESTA's manual, on its boundary and bond-search modes. VESTA is closed
  source, so its manual and its behaviour are the prior art, never its code.

## Handover log

- **2026-10-01** — filed from WP-1504's session, at the maintainer's word,
  after round B. No open WP owns the work. WP-1468 covers polyhedra controls,
  but its remaining tasks wait on two papers, and this is a rendering defect
  plus a skill line. WP-1501-1503 are closed, and WP-1505 depends on this
  rather than owning it. Next: the description first, since it is the
  cheapest and decides whether the round's agents reach the rest; then the
  bare centres; then the stubs.
