# WP-1012 — History worktree, report panel, one-click suggestions

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1010

## Goal

The differentiator no competitor has: a git-like history DAG panel
(checkout/branch/compare from the browser) plus the first interactive
FitReport view anywhere — typed suggestions carrying predicted Δχ² that
apply in one click, echo as API calls, land as history nodes, and are
undoable by checkout.

## Context

- History DAG panel: Rwp badges, head marker, tags; verbs already exist —
  `checkout` (`refine.py:182`), `branch` (`:202`), `merge` (`:250`),
  `cherry_pick` (`:309`) on `Refinement`; `annotate` (`history/tree.py:120`),
  `tag` (`:140`), and the two-node read-side `compare`
  (`history/tree.py:231`) / `diff` (`:249`) on `RefinementTree`. The panel
  is a view over `GET /api/history` + the POST verbs (WP-1008 routes); no
  new history semantics.
- Nodes store **state, not curves**, and their cached metrics are
  *as-optimised* — `replay` recompiles at the values the stage ended on and
  can differ marginally; that gap is a staleness signal, not a bug
  (CLAUDE.md). The panel must not present cached-vs-replayed deltas as
  regressions.
- Report panel: Layers 0–2 rendered from the pydantic `FitReport`
  (`report/schemas.py:331`); worst regions click-zoom the plot
  (`two_theta_range` is already on the report's region entries and on
  `SuggestedAction`).
- **`SuggestedAction` is already fully typed** (`report/schemas.py:296`):
  `kind` (closed `ActionKind` enum), `confidence`, `rationale`,
  `parameter_paths`, `expected_delta_chi2` (predicted, an optimistic upper
  bound — `predict_then_verify` in `report/layer2.py` measures the real one
  and rolls back), `alternatives`, `two_theta_range`, `vetoed_by`. **The
  strategy engine holds the veto** — a vetoed action renders greyed with
  `vetoed_by` as the reason, never hidden.
- `report/apply.py`: map each `ActionKind` to concrete session verbs
  (`set_vary` globs, plan edits, run_stage) — server-side, so the mapping is
  testable without a browser. `POST /api/report/apply` executes one action;
  every application is echoed as API calls in the console and recorded as
  history nodes, so undo is checkout.

### Inherited

From the **v1.0 GUI plan** (2026-07-29): not every `ActionKind` maps to an
automatable verb (`collect_better_data` cannot be a button that does
something). `report/apply.py` must declare per-kind applicability and the
panel renders unapplicable kinds as advice — decide the split explicitly in
the first commit rather than discovering it kind by kind.

## Non-goals

- No new Layer-2 statistics or thresholds — render and apply what the
  report already says (`THRESHOLDS_VERSION` untouched).
- No mermaid/graphviz dependency — the DAG is small; draw it in Svelte.
- No auto-apply loops — one click, one action, human in the loop
  (`predict_then_verify` remains the API-side batch story).

## Tasks

- [ ] History panel: DAG render (Rwp badges, head, tags), checkout / branch /
      annotate / tag wired to the WP-1008 routes.
- [ ] Two-node compare/diff view from `RefinementTree.compare`/`diff` —
      side-by-side parameter deltas, changed-only filter.
- [ ] Report panel: Layers 0–2; worst-region click-zoom; suggestion strip
      with confidence, predicted Δχ², veto reasons.
- [ ] `report/apply.py`: per-kind applicability + verb mapping;
      `POST /api/report/apply`; applications echo + record as nodes.
- [ ] `tests/test_report_apply.py`: every applicable `ActionKind` maps to
      verbs that execute on a synthetic misfit; unapplicable kinds are
      declared, not silently skipped; applied action is undone by checkout.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_report_apply.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- `report/schemas.py` — `ActionKind`, `SuggestedAction`,
  `VerificationOutcome`; `report/layer2.py` `predict_then_verify`.
- CLAUDE.md FitReport invariant (never a confident wrong singleton) — the
  panel renders abstentions and non-separability as such.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.
