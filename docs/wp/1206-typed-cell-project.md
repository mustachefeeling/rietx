# WP-1206 — A project without a CIF, part 1: a typed cell

Milestone: v1.2 · Status: ⬜
Depends on: WP-1205

## Goal

The wizard's structure step offers "type a cell": a space-group symbol and six
numbers become the Le Bail scaffold the indexing Adopt button already builds,
and the project opens in `lebail` mode.

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
- [ ] Manual: `using/quickstart.md` names the route; browser pass; dist.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q -k "typed_cell or scaffold"
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1027, WP-1045: the adopt path and the symbol validation rule.

## Handover log

- **2026-08-25** — created from the v1.2 triage.
