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

From **WP-1011** (landed 2026-07-30) — the sidebar this panel plugs into now
exists, and three of its rules are not obvious:

- **The sidebar is a tab strip in `App.svelte`, and every tab stays mounted**
  (`.panel.hidden { display: none }`). Add `History` and `Report` as tabs; do
  *not* mount on demand, because switching tabs must not throw away a filter, a
  pending edit or an unsaved stage list. Adding a tab is one `<button>` and one
  wrapper div.
- **`head` is the one reload signal.** The head node *is* the working state
  (WP-1005), so panels take `head` as a prop and reload in an `$effect` keyed on
  it — that covers a run, a checkout and an edit made in another panel with one
  subscription. A checkout from this panel will therefore refresh the parameter
  table by itself, provided the state frame's `head` moves.
- **A `ResizeObserver` stub lives in `gui/src/test-setup.ts`** because
  `bind:clientHeight` throws in jsdom *during mount* — the blank-page failure the
  component test exists to catch. jsdom also has no `DragEvent`, and reports every
  measurement as 0. Any panel that measures itself must still work at zero height.

And one contract fact: **`"Infinity"` crosses the wire as a string.** WP-1011
found that `json.dumps` writes a bare `Infinity` token, which `JSON.parse`
rejects outright — so `gui/server.py` now spells non-finite floats as the schemas
do. A report payload carrying an infinite bound or a NaN statistic is therefore a
*string* on the client side; run it through `lib/table.ts`'s `num()` before
comparing it to anything.

From the **v1.0 GUI plan** (2026-07-29): not every `ActionKind` maps to an
automatable verb (`collect_better_data` cannot be a button that does
something). `report/apply.py` must declare per-kind applicability and the
panel renders unapplicable kinds as advice — decide the split explicitly in
the first commit rather than discovering it kind by kind.

From **WP-1007** (landed 2026-07-30): **the diagnostics panel needs no regex.**
Every guard `Diagnostic` now carries its parameter paths in `where` — including
`HIGH_CORRELATION`, which had an *empty* `where` until then, so the degenerate
pair could only be recovered by parsing `"a ~ b (ρ=+0.994)"`. Read `d.where` to
make a finding clickable, and `d.code` to branch; never split `d.message`.

One limitation to design around rather than discover: **the headline *number* is
still only in the message text.** `GuardFinding` carries it as `.value` (ρ, a
block R², a min eigenvalue), but `Diagnostic` was fenced out of scope in WP-1007
and has no numeric field, and `GuardReport` is transient — it is converted to
diagnostics inside `_run_stage` and never stored, so it does not reach a client at
all. If this panel wants to *sort* or *threshold* on ρ rather than display it,
that is either an additive optional `value` on `Diagnostic` (a freeze decision —
raise it in WP-1003) or a server-side arm on the run response. Do not parse the
message for the number.

From the **indexing plan** (WP-1018…1027, added 2026-07-29): one of those
kinds stops being advice. **`reindex_or_recheck_cell` becomes automatable** —
`report/layer2.layer0_actions` has emitted it as an `alternatives` member since
v0.2 with nothing behind it, and WP-1024 gives it `pxrdref.pick_peaks(...)` /
`index_pattern(...)`. Put it on the applicable side of the split and wire its
button to launch an indexing run through the WP-1006 run state machine (it is
long-running, unlike every other applicable action). No `ActionKind` change is
involved, so `THRESHOLDS_VERSION` does not bump.

From **WP-1008** (GUI server, landed 2026-07-30):

- `GET /api/history` returns the shape, not the states: per node `id`, `parents`,
  `children`, `kind`, `action`, **`api_call`** (the node's equivalent public-API
  line — the "show me the code" affordance for free), `label`, `tags`, `rwp`,
  `gof`, `n_free`, `status`, `n_iterations`, `diagnostics`, `scores`, `notes`.
  A node's ~10 kB `state` is deliberately **not** in the payload; if a panel
  needs one node's parameter values, `GET /api/history/diff?a=&b=` answers the
  question it actually has.
- `POST /api/history/branch` is **checkout + tag**, not a new ref: this DAG has
  only `head` and tags, and a fork appears when you run from a node that already
  has a child. Label lanes from `tags`; do not draw a branch that does not exist.
- **A `checkout` clears the result.** `/api/result`, `/api/report` and every
  export answer `NO_RESULT` (409) afterwards until the next run — so "select a
  node" cannot repaint the report panel from a result, and the panel needs that
  empty state. Re-running or `replay` is the only way back to curves.
- `GET /api/report[?plan=preset]` is **idle-only** (Layers 1-2 read the compiled
  model a stage would be rewriting) and 409s with `RUN_IN_FLIGHT` mid-run; it
  defaults the Layer-2 veto to the project's own effective plan, so a panel need
  not pass one. `POST /api/report/apply` is reserved for this WP and 404s naming
  it.

From **WP-1010** (frontend scaffold, landed 2026-07-30): the app shell, `api.ts`
(with `history`, `checkout` and `report` already wired) and the console panel are
in place; add panels beside `panels/Plot.svelte` and delete the matching row from
`panels/Stubs.svelte`. Two shell behaviours to build on rather than duplicate:
the shell refetches `/api/result` whenever the run state returns to `idle` (any
way it ended) and holds the single `state` frame every control's `disabled`
derives from, and `ApiError.empty` already marks `NO_RESULT` — which is exactly
the state a history panel puts the app into every time it checks out a node.
Rebuild the committed dist in the same commit as any `gui/src/**` edit.

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
