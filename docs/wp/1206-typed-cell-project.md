# WP-1206 — A project without a CIF, part 1: a typed cell

Milestone: v1.2 · Status: ✅ 2026-08-26 — a symbol and the free cell parameters are a project
Depends on: WP-1205

## Goal

The wizard's structure step offers "type a cell": a space-group symbol and the
cell parameters that *setting* leaves free (not six — see the first task)
become the Le Bail scaffold the indexing Adopt button already builds, and the
project opens in `lebail` mode.

## Context

- `blocked()` refuses without a CIF (`lib/wizard.ts:235`); `Structure.phases`
  must be non-empty and each `Phase` needs at least one atom
  (`schemas/structure.py:435-439, 475-480`). A Le Bail phase carries a
  mandatory dummy atom whose paths are `mode_fixed` (root CLAUDE.md, the
  parameter surface).
- The indexing panel's Adopt lands a candidate "as a Le Bail scaffold that
  flips the mode" (`gui/CLAUDE.md` WP-1027; the verb is in `session.py`'s
  adopt path, with the space-group choice a convention the user makes).
  That builder is the one to reuse; this WP factors it into one function
  rather than writing a second.
- A prior space-group symbol is validated **server-side and refused in
  gemmi's words** (WP-1045); the same rule applies to the typed symbol.
- A refused cell/symmetry pair is a `ParameterTable.__init__` raise
  (a fixed angle disagreeing with its symmetry is refused, not normalised).

## Non-goals

- Pattern-only projects (WP-1207).
- Indexing from the wizard: a user with no cell picks peaks and indexes
  after creating the project.

## Tasks

- [x] Factor the Le Bail scaffold builder into one function, used by both.
      It was already one — `indexing.workflow.structure_from_candidate` — but
      keyed on a `CellCandidate`, which a typed cell is not. So the cell-plus-
      dummy-atom half moved to `schemas.structure.lebail_scaffold` (with
      `DUMMY_SPECIES`, re-exported from `workflow`) and the wrapper kept the one
      thing a candidate adds: the absence-free lattice-group default.
      Beside it, `crystallography.symmetry.free_cell_names` / `complete_cell`:
      the typed route takes the parameters the **setting leaves free** and fills
      the rest, so a contradicting `b` is unrepresentable rather than tied away
      in silence (WP-1014's coordinate-DOF rule, one parameter family over).
- [x] `project_new` accepts `structure: {space_group, cell}` beside
      `{upload}`; refusals in `get_spacegroup`'s / `complete_cell`'s words with
      `where`. `cell` is an **object keyed by parameter**, carrying the ones the
      setting leaves free — a determined one is refused, naming its source.
      `GET /api/spacegroup?space_group=` (project-free, beside `/api/help`) is
      where a form learns which those are; `symmetry.phase_facts` is now a thin
      wrapper over the new `symbol_facts`, so the two cannot disagree.
      `mode: "rietveld"` over a typed cell is **refused**, not overridden.
- [x] Wizard UI: a `.segmented` "CIF file | Type a cell" in the structure step;
      the symbol, then **the fields the setting leaves free** (not six — the
      server's `free_cell`); mode moved to `lebail` by the switch and
      `rietveld` disabled while it is in force; docs-style lines.
- [x] Tests: `test_gui_server.py` creates from a typed cell and fits Le Bail
      (LaB6 against the module's own synthetic pattern — corundum against it
      would assert nothing); corundum `R -3 c` carries the shape assertions and
      every refusal, each with `where`. Five vitest cases for the client half.
- [x] Manual: `using/quickstart.md` § Le Bail before Rietveld gains "With no
      structure at all" — the GUI route and `lebail_scaffold`, with the dummy
      atom explained and `indexing.md` named as the other way to the same
      scaffold. Browser pass: four defects, all fixed (below). Dist rebuilt.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q -k "typed_cell or spacegroup_route"
.venv/bin/python -m pytest tests/test_wyckoff.py tests/test_schemas.py -q
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1027, WP-1045: the adopt path and the symbol validation rule.
- TOPAS's constrained-cell macros (`Tetragonal(a, c)`, `Rhombohedral(a, al)`)
  and GSAS-II's phase editor, which greys out the parameters a setting
  determines. Prior art for the shape only; both are concepts-only fences
  (TOPAS closed, GSAS-II inspected through its published behaviour).

## Handover log

- **2026-08-26** — **Closed.** A project no longer needs a CIF: type a
  space-group symbol and a cell into step 2 of the wizard and you get a
  working `lebail` project, the same Le Bail scaffold the indexing panel's
  Adopt button has always landed. The thing worth knowing is what the form
  refuses to let you type. The plan said "six fields"; six fields is exactly
  what the *old* six-number path did, and under `P 4/m m m` a typed `b` is tied
  away by `ParameterTable`, so the number read back was never the one entered.
  The wire and the form therefore carry only what the **setting** leaves free,
  and the server is the one that says which those are.

  *Done.* `schemas.structure.lebail_scaffold` is the one scaffold builder,
  `DUMMY_SPECIES` moved beside it (re-exported from `indexing.workflow`) and
  `structure_from_candidate` kept only the absence-free lattice-group default.
  `crystallography.symmetry.free_cell_names` / `complete_cell` are new, checked
  over gemmi's whole table against operator-derived cells in both directions.
  `POST /api/project/new` takes a fourth `structure` form; `GET /api/spacegroup`
  is project-free beside `/api/help`; `gui.symmetry.phase_facts` became a
  wrapper over the new `symbol_facts`, so form and panel cannot drift.
  `gui/CLAUDE.md` 663 → 687 with the four rules, cap comment written.

  *Measured* (`[dev,jax]`, python 3.12.12, darwin/arm64, main checkout's venv).
  A project typed as `P m -3 m` / a = 4.160 against the module's synthetic LaB6
  pattern fits Le Bail to **Rwp 0.0414, GoF 0.79**, `a` back at 4.15660 ± 5e-4
  (`tests/output/gui_typed_cell.png`, looked at). Fast suite **3072 passed /
  72 skipped**, 2m26s — the run itself printed 3071 passed / 1 failed, and the
  failure is `test_always_loaded_docs_stay_under_their_pinned_caps[tests/
  CLAUDE.md]` from **another session's uncommitted edit** in this shared
  checkout, confirmed by stashing that one file. +10 python tests, matching
  `git diff origin/main -- tests/ | grep -c '^+def test_'` exactly; the three
  touched files went 220 → 230. `npm --prefix gui test` **454 passed** (448 at
  the branch point: +5 for the typed cell, +1 for `typedCellReady`);
  `npm --prefix gui run check` clean; `test_gui_dist.py` passes on dist
  `ffd6ddc127f9`; `ruff` clean; sphinx `-W` clean.

  *Decisions taken against the WP's own text, both deliberate.* (1) The `cell`
  argument is an **object keyed by parameter carrying the free ones**, not six
  numbers — with the reason above, plus TOPAS's macro shape as prior art. A
  determined parameter is **refused, never tolerance-checked**: checking would
  need a tolerance on a *length*, a constant nothing else in this package
  needs and nothing would justify. (2) `mode="rietveld"` over a typed cell is
  **refused, not overridden**. Adopt overrides because there the caller chose a
  *candidate*; here they chose a mode, and the form disables the option so the
  refusal is unreachable from the GUI.

  *Gotchas for whoever is next here.* The candidate path deliberately does not
  go through `complete_cell`: `refine_candidate` already solves inside the
  symmetry subspace, so rebuilding a candidate's cell from its free parameters
  would move every stored number in the indexing acceptance suite at the 1e-14
  level for nothing. That is pinned as a `model_dump` equality in
  `tests/test_schemas.py`, which is the test to read before touching either
  function. And the browser pass found four defects, three of them about
  drawing a *form* rather than about this feature — a register's width belongs
  to the call site, a numeric placeholder reads as a filled value, and
  `holds: {constraints}` reads badly under a triclinic symbol. The first two
  are now rules in `gui/CLAUDE.md`; the third is fixed only at this call site,
  since the Model panel's own `holds:` line is WP-1035's and predates this.

  *Next.* [WP-1207](1207-pattern-only-project.md), whose `### Inherited` now
  carries the seams this WP left it — the `StructureSource` union a third
  member joins, the disjoint-keys dispatch a `structure: null` branch has to be
  decided *before*, and the moved `_nonempty` line number its audit quotes.

- **2026-08-25** — created from the v1.2 triage.
