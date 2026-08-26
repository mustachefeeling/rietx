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
complete): `Structure._nonempty` (`schemas/structure.py:491`);
`refine.py:1798, 1941, 2391, 2470, 2549` (`range(len(model.phases))`);
`model/forward.py:1268, 1301`; `Project.create`'s signature
(`project.py:107-116`, `structure` keyword-only, no default); the `.rxt`
renderer's phase blocks (`gui/textdoc.py`); `tree_payload` and the history
diff's table rebuild (`history/tree.py:267-273`); the Model panel's structure
section and the 3D viewer (`GET /api/structure3d` on no phase); the
`RefinementResult` fields indexed by phase (`ticks`, `phase_support`, QPA).

Seams WP-1206 left, verified against the tree on arrival (2026-08-26):

- **The wizard's step 2 is already a `.segmented` with two answers** —
  `lib/wizard.ts`'s `StructureSource = "cif" | "cell"` and
  `useStructureFrom(state, source)`, which is where "this route implies a mode"
  already lives (it moves `rietveld` ↔ `lebail` and disables what the route
  refuses). A pattern-only project is a **third member** of that union and a
  third button, not a fourth mechanism: `structureArgument(state)` is the one
  place `createBody` reads, and `blocked()`/`typedCellReady()` branch on the
  same field.
- **`POST /api/project/new` tells its `structure` forms apart by disjoint
  keys** (`session._is_typed_cell`, dispatched in `_as_structure`:
  `space_group` / `cif`+`upload` / `phases`). `structure: null` falls through
  to the *inline* branch and reaches `_validate(Structure, None, …)` today, so
  this WP's "legal" has to be a branch decided **before** that one, not a
  `None` falling through.
- **`schemas.structure.lebail_scaffold(space_group, cell, *, name)`** is the
  one Le Bail scaffold builder (`DUMMY_SPECIES` beside it, re-exported from
  `indexing.workflow`), and **`crystallography.symmetry.free_cell_names` /
  `complete_cell`** decide which cell parameters a *setting* leaves free. A
  pattern-only project that later gains a phase — from Adopt, or from a typed
  cell — arrives through those, so zero phases must be a state those can be
  applied *to*.
- **`GET /api/spacegroup?space_group=` is project-free**, beside `/api/help`
  and `/api/capabilities`, and is not behind the in-flight 409.
- **`gui/CLAUDE.md`'s size cap now stands at 691** (`tests/test_docs_consistency.py`,
  raised again by 1206's review round — the mailbox said 687); a rule from this
  WP means raising it with the comment that test asks for.

Rules that bind: **a declared name is a claim** (WP-1076): an empty
`phases` list must not read as an answer anywhere a consumer counts phases;
`SCHEMA_VERSION` and the project format bump by one each with the reason
beside the constant (the preview promise); the compatibility direction is
"old files must always open" (memory: break by direction).

## Audit — every `phases` consumer at zero phases

Measured on the pre-change tree by lifting `Structure._nonempty` *at runtime*:
dropping the entry from `Structure.__pydantic_decorators__.model_validators`
and force-rebuilding every model that embeds a `Structure`. Both halves are
needed — `RefinementState` revalidates, so a subclass overriding the validator
does not get through, and a model embedding `Structure` inlines its compiled
core schema, so rebuilding `Structure` alone changes nothing. Synthetic LaB6
pattern (`tests/test_refine_synthetic.synthesize`), `mccusker_default`,
`[dev,jax]` / darwin-arm64.

**The finding that shapes the rest of the WP: nothing crashes.** Every `phases`
consumer in the core is iteration-driven — `for ip, cp in enumerate(model.phases)`,
`range(len(structure.phases))` — so at zero phases they do nothing and the
pipeline runs to the end. `Structure._nonempty` is the *only* thing standing
between a caller and a background-only refinement reported as **`converged`**
at Rwp 0.9637, GoF 23.89, ten instrument and background parameters refined.
So the work is not "stop it breaking"; it is "make it refuse, and make the
empty answers honest".

### Must refuse

| consumer | at zero phases today | wanted |
|---|---|---|
| `Refinement.fit` / `run_stage` / `refine` | every stage `converged`; `MODEL_FAR_FROM_DATA` fires as a *diagnostic* while `status` still says `converged` | refuse before compile, `NO_PHASES` |
| `POST /api/run {"kind":"fit"}` | 200, then `run.status == "converged"` | refused with that reason; Run disabled |
| `agent.refine_json({"task":"refine"})` | refuses `INVALID_REQUEST` — but only because the *schema* still rejects `phases: []` | the same `NO_PHASES` once the schema allows it |

The third row is the trap: today's refusal is a side effect of the validator
this WP removes, so it disappears silently unless `refine_json` is given the
refusal in its own right.

### Already the honest empty answer — no change

`ParameterTable` builds (19 entries, all instrument and background;
`free_paths`, `moving_paths` `[]`; `x0()` shape `(0,)`); `compile_model` builds
in `rietveld` *and* `lebail` and `evaluate` returns the background over all
4200 points; `RefinementResult.ticks` → `{}`; `data_support` → 0 unique
reflections and `n_effective_observations` `None`; `count_unique_reflections`
→ 0; `effective_observations` → `None`; `reflection_table` → `[]`;
`phase_support` fires no `PHASE_UNCONSTRAINED`; `identifiability.background_absorption`
→ `{}`; `phase_agreement` → `[]` through its own `not model.phases` guard
(`refine.py:2034`). The **FitReport** is the best-behaved consumer of the lot:
`layer1_available=False`, abstained `immature`, and **36 unmatched observed
peaks** — it already says the pattern has peaks the model does not.
`Project.create`/`open`, `textdoc.render` and `GET /api/project|params|structure|peaks|history|plan|textdoc|capabilities|settings`
all answer 200; `GET /api/report` is 409 `NO_RESULT` before a run.

### Empty containers that read as answers (WP-1076)

- **`RefinementResult.qpa`** → `QuantitativePhaseAnalysis(phases=[], method="zmv",
  crystalline_only=True)`: "QPA was done, the specimen holds no crystalline
  phase". The mechanism is a two-way test with three cases:
  `compute_qpa` finds Σ zmv·s ≤ 0, then asks `len(structure.phases) > 1`, so
  zero phases falls into the **single-phase** branch — "one phase is 100 %
  whatever its scale did" — and builds an empty table instead of the `None`
  that branch's own docstring reserves for "the scales cannot form fractions at
  all". Wanted: `None`.
- **`RefinementResult.geometry`** → `GeometryTable(distances=[], angles=[],
  bond_slack=0.4, contact_max=3.5, notes=[])`, from a function that *already*
  returns `None` outside Rietveld for the same reason. Wanted: `None`.
- **`io.exporters.qpa_table_csv`** renders the whole Hill & Howard scope header
  over zero rows, and **`refinement_cif_doc`** returns a gemmi `Document` with
  **0 blocks** — an empty CIF written without complaint. Both follow their
  inputs, so both are fixed by the two `None`s above.

### Refuses already, message to revisit

`GET /api/structure3d` → 404 `no phase 0 (this structure has 0)`: accurate, but
phrased for a bad index rather than for a project that has no phase yet — the
message behind the hidden 3D column (task 3). Every other phase-indexed GUI
verb guards with `IndexError` → 404 and needs no change
(`gui/symmetry.py:345, 379, 692, 721`; `gui/session.py:1169`).

### Not reachable from a pattern-only project

`viz/compare.py:197` divides by `len(structure.phases)` — a `ZeroDivisionError`,
but `compare`'s standards always carry phases; `indexing/workflow.py:420` reads
`structure.phases[0]` off a scaffold `structure_from_candidate` has just built.
`multi.py` and `sequential.py` are iteration-driven like the core and inherit
whatever `fit` decides.

## Non-goals

- Fitting with no phases: `fit` refuses (`NO_PHASES`), and the GUI's Run is
  disabled with that reason.
- Multi-phase indexing on a residual (v2 fence).

## Tasks

- [x] The audit: every `phases` consumer listed with its behaviour at zero
      phases (§ Audit above). Measured, not read: nothing crashes, because
      every core consumer is iteration-driven, so `Structure._nonempty` is the
      only thing between a caller and a background-only fit reported
      `converged` at Rwp 0.9637. `ticks` `{}` and the absent `phase_support`
      diagnostic are already right; `qpa` and `geometry` are empty containers
      that read as answers, and `refine_json`'s current refusal is a side
      effect of the validator this WP removes.
- [x] `Structure` allows `phases=[]` (the class docstring says why the refusal
      cannot live there); `Project.create(structure=None)` builds one;
      `fit`/`run_stage`/`refine_multi`/`refine_sequential` and the GUI's
      `POST /api/run` raise `NoPhasesError` (`code = "NO_PHASES"`) *before*
      the tree or the first event, and `refine_json` answers with a **fourth**
      envelope code rather than folding it into `INVALID_REQUEST` — the
      request is well-formed and the model is legal, so re-checking fields
      finds nothing and retrying reproduces it. `SCHEMA_VERSION` 0.8 → 0.9,
      `PROJECT_FORMAT_VERSION` 1.2 → 1.3, each with its reason beside the
      constant. The audit's two empty containers are now absences:
      `compute_qpa` and `geometry_table` return `None` at zero phases.
- [x] GUI: `StructureSource` gains `"none"` and step 2 a third `.segmented`
      button, which sends `structure: null` — an **answer**, where the key's
      absence stays a refusal, since `dict.get` cannot tell them apart and only
      one of the two should create a phase-free project quietly. It is the one
      route that moves the mode nowhere: with no phase there is nothing for a
      mode to govern, and Adopt sets it on the way out. `project_doc` gains
      `n_phases` (a derived summary beside `head`, not a second authority) and
      `moved()` reloads it, so Run, Run-one-stage and the series command
      disable with the reason wherever the last phase arrives or leaves. The
      Model panel's structure column says what to do instead, the 3D column and
      its toggle are hidden with it, and `structure3d`'s refusal is phrased for
      the state rather than for a bad index. The `.rxt` gains a comment where
      the phase blocks would be — a document with neither reads as one whose
      phases went missing.
- [x] Tests: the whole loop over the wire in `test_gui_peaks.py` — a
      pattern-only project refuses the run by name, picks peaks, adopts a
      candidate and *then* fits to Rwp < 0.2. On the module's synthetic LaB6
      rather than the corundum example, and with the candidate injected the way
      every other adopt test here does it: what is under test is the loop, and
      a real search belongs to the acceptance suite. Beside it: the library
      round trip and `NoPhasesError` vs `predict` (`test_project.py`), a 1.2
      and a 1.0 document still opening unmigrated, the wizard's `structure:
      null` against the required key (`test_gui_server.py`), emptying a
      structure through `PATCH`, the `NO_PHASES` envelope code on all three
      refining tasks (`test_agent_surface.py`), and four vitest cases.
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
