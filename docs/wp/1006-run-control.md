# WP-1006 — Run control: streaming, progress, cancellation

Milestone: v1.0 · Status: ⬜ not started
Depends on: —

## Goal

Interactive single-stage runs stream events, every run reports progress
(stage k of N), and a running fit can be cancelled cleanly — the stage in
flight is abandoned, the working state stays at the last completed node, and
the caller learns what did complete.

## Context

- **`run_stage` has no telemetry today, and the fix is plumbing**: `fit()`
  (`refine.py:432`) takes `events=None`, and the private `_run_stage`
  (`refine.py:350`) already takes `events=None` — but the public
  `run_stage()` (`refine.py:525`) does not accept it, so interactive
  single-stage work is blind. Mirror `fit`'s parameter through.
- `optimize/cancel.py`: `CancelToken` (wrapping `threading.Event`) +
  `RefinementCancelled`. `run_least_squares` (`optimize/least_squares.py:489`
  — currently **no** `cancel=` parameter) grows `cancel=None`, checked **at
  eval boundaries only**: inside the residual closure that already wraps for
  events on the TRF path (`least_squares.py:500-513`) and in the LM callback
  (`least_squares.py:479-486` → `lm.minimize(callback=...)`, `lm.py:240`,
  invoked on accepted points at `lm.py:324`). Compiled state is never touched
  from outside — frozen-per-stage discreteness holds; cancellation is a
  cooperative check between residual evaluations, not an interrupt.
- On cancel: the in-flight stage is **abandoned** — no history node, the
  `ParameterTable` is not committed — and `RefinementCancelled` re-raises
  with `.completed_stages` so the caller knows where the working state
  stands (the last completed node).
- Progress: additive `stage_start.index` / `.n_stages` event fields. Today's
  `stage_start` payload (`refine.py:413-415`) carries `stage, turn_on, freed,
  n_free, n_points` and lacks both. Events stay `v="1"`
  (`history/events.py:36`, `EVENT_SCHEMA_VERSION`) — additive fields are
  compatible; **note the additivity rule in `history/events.py`** so the next
  field addition doesn't bump the version reflexively.

### Inherited

From the **v1.0 GUI plan** (2026-07-29): the GUI server (WP-1008) holds the
`CancelToken` and maps POST `/api/cancel` onto it; keep the token dumb
(set/is_set) so that mapping stays trivial. `CancelToken` and
`RefinementCancelled` are freeze candidates — recorded in WP-1003's
`### Inherited`.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): **indexing is a
long-running job that is not a refinement.** `index_pattern` (WP-1024) can run
for minutes and the GUI drives it through this state machine, so do not assume
a run has stages, an Rwp, or a history node — an indexing run has none of the
three. Add an `"index"` run kind alongside the refinement one, and keep
progress reporting generic enough that "engine 2 of 3, orthorhombic" is
expressible. The `CancelToken` itself needs no change; the cooperative
check-between-evaluations pattern transfers directly to a search loop.

## Non-goals

- No mid-stage checkpointing or resume — cancel abandons the stage, full
  stop.
- No timeout/watchdog policy — callers compose that from the token.
- No event-schema version bump (additive fields only).

## Tasks

- [ ] `Refinement.run_stage(..., events=)` — mirror `fit`'s parameter into
      the public single-stage path; test that `run_stage` emits
      `stage_start`/`eval`/`stage_end`.
- [ ] `optimize/cancel.py`: `CancelToken` + `RefinementCancelled`;
      `run_least_squares(..., cancel=None)` checked in the TRF residual
      wrapper and the LM callback only.
- [ ] Cancel semantics in `refine.py`: abandoned stage (no node, table not
      committed), re-raise with `.completed_stages`; working state at last
      completed node — tested via a token tripped from an event callback.
- [ ] `stage_start.index` / `.n_stages` additive fields + the additivity
      note in `history/events.py`; live viewer/watch unaffected (they ignore
      unknown fields — assert that stays true).
- [ ] `tests/test_run_control.py`: cancel stops within ≤2 further residual
      evals; `run_stage` streams; `.completed_stages` correct across both
      solvers (`trf`, `lm`).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_run_control.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- `history/events.py` — `EVENT_SCHEMA_VERSION = "1"`, `EventKind` Literal
  (`fit_start, stage_start, eval, stage_end, fit_end`).

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan. Signatures verified
  against the tree the same day (`run_stage` lacks `events=`; `_run_stage`
  has it; `run_least_squares` has no `cancel=`; both solver paths already
  have an event hook to piggyback on).
