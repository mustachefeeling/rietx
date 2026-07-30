# WP-1011 — Parameter editor, plan editor, run controls, disclosure

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1010

## Goal

The editing core of the GUI: a virtualized grouped parameter table, a plan
editor fed by `PLAN_INFO`, Run / Run-stage / Cancel controls, and the
Simple/Advanced progressive-disclosure toggle persisted to the project.

## Context

- Parameter table: virtualized (a Pawley fit can have thousands of rows),
  grouped by dot-path prefix — value edit, vary checkbox, esd column,
  locked/tied rows greyed with the reason as tooltip (the reason text comes
  from `ParameterRow.tie`/`locked`, WP-1004 — the server verb's refusal
  message, never a frontend guess). Glob filter box + free/fix-selection
  bulk ops → `PATCH /api/params` with globs, which delegates to
  `Refinement.set_vary` — one round trip, one history node.
- **fnmatch parity is cross-language anti-drift**: a pytest writes
  `tests/data/gui/fnmatch_cases.json` from Python's `fnmatch` (the
  authority — stage plans glob with it), vitest consumes it for
  `lib/fnmatch.ts`. The client-side matcher only *previews* selection; the
  server match is authoritative.
- Plan editor: preset picker fed by `PLAN_INFO` (WP-1004; title,
  description, intended mode, when-to-use), stage list with drag-reorder,
  per-stage `free` globs, advanced fields (max_iter, lebail_cycles, seed,
  strain_seed) behind disclosure. PUT `/api/plan` stores the unified
  `PlanSpec`.
- Run controls: Run / Run-stage / Cancel with optimistic status (<50 ms
  feedback; the server 409s a second run — surface that as "already
  running", not an error dialog).
- Progressive disclosure: **Simple mode (default)** hides bounds,
  transforms, solver/backend pickers, stage seeds, and
  Pawley/Stephens/ADP blocks unless the structure declares them; the
  FitReport suggestion strip (WP-1012) is the novice's "what next".
  Persisted in `ProjectDoc.ui` (WP-1005 — untyped dict, GUI owns the keys).
- Keyboard: Cmd/Ctrl-K command palette where every entry shows its API
  echo; `r` run, `.` run-stage, `Esc` cancel, `f`/`x` free/fix selection.

### Inherited

From the **v1.0 GUI plan** (2026-07-29): `set_vary` can never free locked
entries (emission-line weight 0, symmetry-fixed cell angles) — the table
must render those rows without a vary checkbox at all, not with one that
errors on click.

From **WP-1004** (landed 2026-07-30): **do not re-derive the greying rule.**
`ParameterRow.refinable` is the single predicate over all three reasons a row
cannot be freed — `locked`, `tie`, and `mode_fixed` — and
`ParameterRow.held_because` is the tooltip text, already written. Three
consequences for this table: (a) there are **three** greyed states, not two, and
`mode_fixed` (lebail/pawley force-fixing every `.atoms.` path, `.scale`, the
line weights) must not be rendered as `locked`, because it comes back when the
mode changes — a Le Bail phase's mandatory dummy atom is the case that matters;
(b) a **tied** row's value cell is read-only and its tooltip should offer the tie
sources, since `set_values` on it raises naming them (`TieSpec.sources` /
`.describe()`); (c) `set_values` takes a **dict of several paths** on purpose —
batch the grid's edits into one call, because each call is one history node, and
per-keystroke nodes would bury the log. Bounds and transform are on the row too,
so the value editor can validate before the round trip (`set_values` refuses an
out-of-bounds value).

From **WP-1008** (GUI server, landed 2026-07-30) — the routes this WP edits
through are live:

- `GET /api/params` returns every row with `refinable` and `held_because`
  **added** to the `ParameterRow` dump (they are properties, so `model_dump`
  drops them), plus `n_free`, `mode`, `head` and `live`. Render the three held
  reasons from `held_because`; do not re-derive them from `locked`/`tie`/
  `mode_fixed`, which is the same rule spelled twice.
- `PATCH /api/params {"values": {...}, "vary": {"glob": bool}}` applies **values
  first, then vary in object order**, and each commits its own history node — so
  one editor "apply" is two or three nodes, and the history panel will show them.
- **A refused edit is the useful answer.** A tied path comes back 400 with the
  verb's own message naming its sources (`'phases.0.cell.b' follows
  'phases.0.cell.a' as an affine tie; set that instead`) and `where` = the path
  edited. Show the message; the GUI is the only place it is ever read.
- `GET /api/plan` gives the expanded stages plus a **derived** `preset` name
  (`null` when edited) and `selected`. `PUT /api/plan` takes either
  `{"preset": name}` or `{"plan": spec}`; a preset is stored **expanded through
  the mode** (`mccusker_default` + `lebail` → `profile_only`'s stages), so the
  editor shows exactly what will run. An empty stage list is refused.
- Every one of these 409s with `RUN_IN_FLIGHT` during a run, and the state
  refusal deliberately outranks body validation — disable the editor off the
  `state` SSE frame rather than letting a user retype a value into a 409.

## Non-goals

- No structure/instrument *object* editing (WP-1014) — this WP edits θ-table
  entries and plans only.
- No text pane (WP-1013), no report strip (WP-1012) — the palette and
  disclosure land here; those panels plug in later.
- No undo stack of its own — undo is history checkout (WP-1012's panel);
  edits are history nodes already.

## Tasks

- [ ] Virtualized grouped parameter table: value edit, vary checkbox, esd,
      locked/tied greyed + tooltip; glob filter; bulk free/fix via PATCH
      globs.
- [ ] fnmatch parity fixture: pytest writes
      `tests/data/gui/fnmatch_cases.json`; vitest consumes it against
      `lib/fnmatch.ts`.
- [ ] Plan editor: `PLAN_INFO` preset picker, stage list, drag-reorder,
      disclosure for advanced stage fields.
- [ ] Run / Run-stage / Cancel with optimistic status; 409 surfaced as
      state, not failure.
- [ ] Simple/Advanced toggle persisted to `ProjectDoc.ui`; command palette +
      shortcut keys with API echo.
- [ ] Server-side: params PATCH (incl. bulk glob) rows in
      `tests/test_gui_server.py`; vitest for table selection logic and
      fnmatch parity.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1004's `ParameterRow` / verbs; CLAUDE.md path conventions (fnmatch, no
  brackets in paths).

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.
