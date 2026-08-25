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

- [ ] Factor the Le Bail scaffold builder out of the adopt verb into one
      function (`gui/session.py` or `schemas/structure.py`), used by both.
- [ ] `project_new` accepts `structure: {space_group, cell}` beside
      `{upload}`; refusals in gemmi's / the table's words with `where`.
- [ ] Wizard UI: "CIF file | type a cell" in the structure step; six fields
      + symbol; mode preselected `lebail`; docs-style lines.
- [ ] Tests: `test_gui_server.py` creates from a typed cell (corundum,
      `R -3 c`, the SRM 676a cell) and fits Le Bail; a bad symbol and an
      angle contradicting the symbol are refused with `where`.
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
