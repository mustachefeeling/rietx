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
