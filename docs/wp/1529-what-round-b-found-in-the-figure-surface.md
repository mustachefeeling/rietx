# WP-1529 — what round B found in the figure surface: the skill names figures, a cell draws no bare centre, the report counts every stub

Milestone: rietview · Status: ✅ 2026-10-01 — the skill names figures, no bare centre while its polyhedra are drawn, dangling_bonds counts hidden= stubs
Depends on: —

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
- [x] The GUI checked against the changed `build` (`gui/CLAUDE.md`).
- [x] Tests + PNGs to `tests/output/`.
- [x] Skill: `api-figure.md` regenerated (`docs/skill/make_api_index.py`) and
  its `hidden=` sentence corrected, beside the description task.
- [x] WP-1504's `### Inherited`: the merge commit to pin as a third condition.

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

### 2026-10-01 (2nd session) — closed: the skill names figures, no bare centre while its polyhedra are drawn, every stub counted

An agent asked for a structure figure is now pointed at the skill by its
description. A structure drawn with its polyhedra no longer shows a
polyhedron's centre outside the cell without one. VESTA's manual (§ 8.2.1)
says its default search never adds such a centre, so rietx now hides one
while its site's polyhedra are on, in the Python renderer and the GUI alike.
And the figure report no longer calls a figure clean when `hidden=` has left
bond stubs all over it. WP-1504 can now rerun its round on this tree.

**Done.**

- The description (`docs/skill/rietx/SKILL.md`) adds two sentences naming
  `rx.viz.render_structure`, at 602 of 1024 characters. Both copies are
  re-synced.
- Bare centres. `build` flags `outside_centre` on every atom and every bond
  (`_flag_outside_centres`, `src/rietx/gui/structure3d.py`), and `_tile`
  recomputes the flags on a block. `drawn_with`
  (`src/rietx/viz/figure3d/scene.py`) and `drawnWith`
  (`gui/src/lib/structure3d.ts`) draw a flagged atom and its bonds only
  while no drawn polyhedron is centred on its site. A site is keyed by its
  asymmetric-unit atom (`sites[k].index`), because `recolour` copies sites.
- Stubs. `_dangling` (`render.py`) counts every half toward an undrawn atom,
  including halves `hidden=` leaves. Updated: the `render_structure` and
  `FigureReport` docstrings, `api-figure.md` (regenerated through
  `make_api_index.py`), `docs/manual/using/exports.md` and `gui-guide.md`.
- The GUI was driven in chromium on rutile, fluorapatite, NAC and calcite.
  With polyhedra on, no outside centre is drawn. Switching them off brings
  the centres back with their sticks, and the console shows no error.
- WP-1504's `### Inherited` names PR #635's merge commit as the third
  condition. Its priority is re-rated P3.
- The context claim "calcite draws none" is corrected in place.

**Measured** (`[dev]` venv, darwin/arm64, one run each).

- Outside centres flagged, as sites drawn by default / hidden by default:
  - rutile 2 Ti / 0;
  - fluorapatite 4 P / 26 Ca;
  - calcite 8 Ca / 0;
  - NAC 0 / 9 Ca and 7 Na;
  - gypsum 0 / 8 Ca;
  - LaB₆ 0 / 0.
- On 2×2×2 blocks of five phases, the build-time first attempt kept every
  interior bond and every polyhedron. The draw-time rule removes nothing
  from the payload.
- Stubs: calcite under `hidden=("Ca",)` reads 112, LaB₆ under
  `hidden=("La",)` reads 192, and both read 0 after `keep(g,
  ~select(g, element=…))`.
- Fast selection: 7390 passed, 159 skipped, 252 s, with no other suite
  running. The session added 12 cases, 1.88 s in all
  (`tests.added_test_times`), none near the slow tail. I took no baseline on
  main (tests/CLAUDE.md § Running), so the delta is not checked against one.
  The full selection was not run, because no change can move a measured
  refinement number. vitest: 582 passed. svelte-check: 0 errors.
- Lanes (`/wp-lanes` trial, session ec2ca17f): main 103 requests, peak
  240K, $6.27. 2 lanes cost $3.87, and the session made 7 WP commits.

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | lane $ | main $ | in-session $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | bare-centres | 25 | 47 | 187K | 67K | 10K of 10K | 8 | 15K | 0 | 0 | 2.15 | 0.49 | 3.96 | +1.23 |
  | gui-check | 22 | 50 | 218K | 66K | 0K of 852K | 3 | 6K | 0 | 0 | 1.72 | 0.21 | 3.48 | +1.54 |

  | kept item | est | requests | main at decision |
  |---|---|---|---|
  | bare-centres | 30 | 53 | 104K |
  | hidden-stubs | 12 | 8 | 206K |
  | pngs | 6 | 0 | 224K |
  | api-figure | 8 | 5 | 229K |

  The trial row is appended to `docs/milestones/process.md`. With these
  inputs the replay gives the selective policy (main > 150K and an item of
  20 or more requests) a −25 % change on 404 sessions. Two notes on the
  inputs:
  - bare-centres appears twice. It was kept at 104K, then laned at 187K
    once the first design had failed.
  - "main edits after" reads 0, but after lane 1 returned I reworded one
    vitest comment and rebuilt the dist.

**Gotchas.**

- The first design removed the outside centres at build time. It cost NAC's
  F3 (0.96, 0.96, 0.96) all 11 of its sticks in the default picture, because
  Na and Ca shells are hidden by default. Any rule keyed on "the site has a
  polyhedron" rather than "the polyhedron is drawn" has that problem.
- With NAC's NaF₇ and CaF₈ switched on, F3 draws as a ball with no stick.
  That is VESTA's behaviour too.
- `bond_tolerance` no longer changes rutile's default picture, because every
  remaining stick lies inside an octahedron. The recipe test draws that case
  with `polyhedra=False`.

**Review** (`/code-review high --fix`). It fixed the site key under
`recolour` in both twins and added a test. It also brought `exports.md` and
`gui-guide.md` up to date. It declined four findings:

- A vertex of a hidden polyhedron is never flagged. This needs overlapping
  `centres=`/`ligands=` lists, and the fix is a payload redesign.
- The caption's bond count is the bond search's total, as it always was.
- The NAC `hidden=` assertion is `> 0`, and the exact counts are pinned on
  calcite and LaB₆.
- Re-keying bond ends costs a second hash pass, which is negligible.

**Next:** WP-1504 pins this PR's merge as its third condition and reruns
the round (its `### Inherited`). If an intermetallic with overlapping
`centres=`/`ligands=` lists ever draws a bare centre, the declined vertex
finding above is the place to start.

- **2026-10-01** — filed from WP-1504's session, at the maintainer's word,
  after round B. No open WP owns the work. WP-1468 covers polyhedra controls,
  but its remaining tasks wait on two papers, and this is a rendering defect
  plus a skill line. WP-1501-1503 are closed, and WP-1505 depends on this
  rather than owning it. Next: the description first, since it is the
  cheapest and decides whether the round's agents reach the rest; then the
  bare centres; then the stubs.
