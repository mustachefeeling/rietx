# WP-1207 — A project without a CIF, part 2: pattern-only projects

Milestone: v1.2 · Status: ⬜
Depends on: WP-1206

## Goal

`Project.create(structure=None)` is legal: a project with zero phases in
which peak picking and indexing work, the parameter table holds the instrument
and background, and `fit` refuses before compile with a named reason.

## Context

User decision (2026-08-25): a pattern-only project is in scope (WP-1017 named
the user with a pattern and no CIF as the audience least served). It is a
library change, which is why it is its own WP.

What assumes at least one phase today (the audit starts here, and is not
complete): `Structure._nonempty` (`schemas/structure.py:475-480`);
`refine.py:1798, 1941, 2391, 2470, 2549` (`range(len(model.phases))`);
`model/forward.py:1268, 1301`; `Project.create`'s signature
(`project.py:107-116`, `structure` keyword-only, no default); the `.rxt`
renderer's phase blocks (`gui/textdoc.py`); `tree_payload` and the history
diff's table rebuild (`history/tree.py:267-273`); the Model panel's structure
section and the 3D viewer (`GET /api/structure3d` on no phase); the
`RefinementResult` fields indexed by phase (`ticks`, `phase_support`, QPA).

Rules that bind: **a declared name is a claim** (WP-1076): an empty
`phases` list must not read as an answer anywhere a consumer counts phases;
`SCHEMA_VERSION` and the project format bump by one each with the reason
beside the constant (the preview promise); the compatibility direction is
"old files must always open" (memory: break by direction).

### Inherited

From **WP-1206** (2026-08-26), which built the wizard's other CIF-free route:

- **Step 2 is already a `.segmented` with two answers**, `lib/wizard.ts`'s
  `StructureSource` = `"cif" | "cell"` and `useStructureFrom(state, source)`.
  A pattern-only project is a **third member** of that union and a third
  button, not a fourth mechanism: `structureArgument(state)` is the one place
  `createBody` reads, and `useStructureFrom` is where "this route implies a
  mode" already lives (it moves `rietveld` ↔ `lebail` and the mode select
  disables what the route refuses). `blocked()` and `typedCellReady()` branch
  on the same field.
- **`POST /api/project/new` tells its `structure` forms apart by disjoint
  keys** (`session._is_typed_cell`; `phases` / `cif`+`upload` /
  `space_group`). `structure: null` is currently the *inline* branch and
  reaches `_validate(Structure, None, …)`, so this WP's "legal" has to be a
  fifth branch decided before that one, not a `None` falling through.
- **`schemas.structure.lebail_scaffold(space_group, cell, *, name)`** is the
  one Le Bail scaffold builder now, shared by Adopt and the typed cell;
  `DUMMY_SPECIES` moved there from `indexing.workflow` (re-exported). The
  audit item "`Structure._nonempty` (`schemas/structure.py:475-480`)" above is
  still right, but that file has moved: `_nonempty` is now near line 490.
- **`crystallography.symmetry.free_cell_names` / `complete_cell`** decide which
  cell parameters a *setting* leaves free and fill the rest. If a pattern-only
  project later gains a phase from the indexing panel, that is the same seam.
- **`GET /api/spacegroup?space_group=` is project-free**, beside `/api/help`
  and `/api/capabilities`, and is not behind the in-flight 409.
- **The size caps are all at their pinned value.** `gui/CLAUDE.md` went
  663 → 687 for 1206; a rule from this WP means raising it again with the
  comment `tests/test_docs_consistency.py` asks for.

## Non-goals

- Fitting with no phases: `fit` refuses (`NO_PHASES`), and the GUI's Run is
  disabled with that reason.
- Multi-phase indexing on a residual (v2 fence).

## Tasks

- [ ] The audit: every `phases` consumer listed with its behaviour at zero
      phases; the ones that must refuse, and the ones that must return an
      empty answer (`ticks` `{}`, no `phase_support` diagnostic).
- [ ] `Structure` allows `phases=[]`; `Project.create(structure=None)`
      builds it; `fit`/`run_stage`/`refine_json` refuse with `NO_PHASES`;
      version bumps.
- [ ] GUI: the wizard's third choice "none yet"; the Model panel's structure
      section shows "no phase yet: pick peaks and index, or add a phase";
      Run disabled with the reason; the 3D column hidden.
- [ ] Tests: a pattern-only project on the corundum example picks peaks,
      indexes, adopts a cell (becoming a WP-1206 project) and then fits;
      `fit` on it before adoption refuses; an old `project.json` still opens.
- [ ] Manual (`using/files.md`, `quickstart.md`), AGENT_PROTOCOL row for
      `NO_PHASES`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_project.py tests/test_gui_server.py tests/test_gui_peaks.py tests/test_textdoc.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- WP-1076 (declared names), WP-1117 (the preview promise).

## Handover log

- **2026-08-25** — created from the v1.2 triage.
