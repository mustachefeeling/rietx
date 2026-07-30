# WP-1013 — Text pane (CodeMirror 6) + two-way sync

Milestone: v1.0 · Status: ⬜ not started
Depends on: WP-1009, WP-1010

## Goal

The power-user surface: a CodeMirror 6 pane over the WP-1009 `.pxt`
rendering with rectangular selection, continuous validation, and explicit
apply — the Profex/TOPAS-jEdit lineage, without merge hell.

## Context

- CM6 with `rectangularSelection` (jEdit-style column edits — the reason
  the format is column-aligned) and multi-cursor. Syntax highlighting via a
  `StreamLanguage` regex highlighter — **no lezer grammar build**; the
  Python parser (WP-1009) is the only parser, so the frontend must not
  grow a second one that can drift.
- Sync engine (`gui/src/lib/sync.ts`, framework-free): the server session
  is the single source of truth; the pane is a dirty buffer.
  - Clean pane → every model change pushes a fresh render + revision over
    SSE, applied as a minimal diff to preserve cursor/scroll.
  - Typing → 300 ms debounce → `PUT /api/textdoc {text, base_revision,
    validate_only: true}` → parse errors as CM lint diagnostics at
    line/col (WP-1009 guarantees 1-based line numbers on every error).
  - **Apply is explicit** (Cmd-Enter): continuous validation, explicit
    application. Conflict → 409 + "model changed underneath" banner; no
    three-way merge — re-render and let the user re-apply.
- Applied deltas run as the same public verbs the forms use (WP-1009
  already guarantees this), so they appear in the console as API calls and
  in history as nodes — a text bulk-edit is undoable by checkout like
  everything else.
- CM6 is the one real frontend dependency beyond Svelte/plotly; it lands in
  the committed dist as `vendor-cm.js` (stable filename, WP-1010). MIT
  licensed — no ATTRIBUTION.md entry needed for an unmodified dependency,
  but the lockfile pin is the version statement.

### Inherited

From the **v1.0 GUI plan** (2026-07-29): two-way text sync is the plan's
top-listed correctness risk. The mitigations are structural and already
decided — single server-side parser, CAS revisions, explicit apply,
all-or-nothing deltas — do not relitigate them; test the state machine
instead.

From **WP-1008** (GUI server, landed 2026-07-30): the text pane's transport is
`GET/PUT /api/textdoc`, **reserved and 404-ing** until WP-1009 fills it in, so
this WP inherits routing for free. Two constraints from the session model: the
PUT is a mutating verb and must 409 with `RUN_IN_FLIGHT` during a run like every
other (the state refusal outranks a parse complaint — tell the user the fit is
running, not that their text is invalid), and a text edit that changes *settings*
persists immediately (`project.json` is written by the verb, not by Save), which
is what keeps "nothing to confirm on close" true.

## Non-goals

- No lezer grammar, no client-side parsing beyond the regex highlighter.
- No autosave-on-type applying deltas (validation only until Cmd-Enter).
- No format changes — the `.pxt` spec is WP-1009's; a needed change goes
  there first.

## Tasks

- [ ] Text panel: CM6 + `rectangularSelection` + multi-cursor +
      `StreamLanguage` highlighter, loaded as `vendor-cm.js`.
- [ ] `lib/sync.ts` state machine (clean/dirty/validating/conflict) +
      minimal-diff application preserving cursor/scroll on SSE re-render.
- [ ] Debounced validate-only PUT → lint diagnostics; Cmd-Enter apply;
      409 conflict banner + re-render path.
- [ ] vitest: sync state-machine transitions (clean edit, concurrent model
      change, conflict, re-apply); highlighter never claims validity (only
      the server does).
- [ ] `tests/test_gui_server.py`: textdoc CAS-conflict row (two writers,
      second gets 409, no partial apply).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py -q
npm --prefix gui test
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1009 (format + parser — normative); Profex's synced-text behaviour as
  the UX precedent.

## Handover log

- **2026-07-29** — created from the v1.0 GUI plan.
