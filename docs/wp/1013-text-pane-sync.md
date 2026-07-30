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

From **WP-1011** (landed 2026-07-30): **the form side now follows the text
document's comparison rule**, which is what makes a two-way sync coherent rather
than merely bidirectional. A cell counts as edited when its text differs from the
*rendered* value (`lib/table.ts`'s `editState`), exactly as `textdoc.changes`
diffs against the rendered document — so a value shown at the precision its esd
justifies (`4.1568(2)` for 4.156783) is not silently truncated by a round trip
through either surface. If this pane's sync ever compares against the stored
float on one side and the rendered string on the other, that asymmetry is where
the drift will come from.

Two smaller ones. The **command palette** (`lib/palette.ts`, Cmd-K) is where a
"Format document" / "Apply text" command belongs — every entry carries the Python
call it makes, and its `isShortcutTarget` is already the rule that stops a
single-letter shortcut firing inside an editor. And **the sidebar is a tab strip
whose tabs all stay mounted**, so a text pane holding unsaved edits survives a
visit to the parameter table; add a tab rather than a route.

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

From **WP-1009** (text document, landed 2026-07-30) — the primitive is done and
`GET/PUT /api/textdoc` are live. What the sync engine has to know:

- **`PUT` is compare-and-set on a `revision`** (`textdoc.revision(text)`, a short
  sha256 of the rendered document). A stale `base_revision` is a 409
  `STALE_REVISION` and there is no merge — the document is *regenerated from
  state*, so a three-way merge would be merging two renderings of the same
  authority. The response to a successful `PUT` carries the re-rendered `text`
  and its new `revision`, so the pane can adopt them without a second round trip.
- **`validate_only: true`** does everything but apply and returns
  `{valid, delta, would_change}` — that is the continuous-validation call, and it
  is cheap (no fit, no compile).
- **An invalid document applies none of itself.** The 400 carries
  `error.details[]`, one entry per problem, each with a 1-based `line`, a
  `where` dot-path and the offending `text` — enough to place a squiggle without
  parsing prose. The frontend gets a regex highlighter and no grammar, by
  decision, so this list is the only diagnostics channel.
- **A re-render discards the user's comments** (see that WP's handover for why
  storing them was rejected). The pane should say so before it replaces the
  buffer — "apply, then re-read" is the flow, and a user who has annotated the
  document will otherwise lose notes they had no reason to expect were transient.
- Canonical output normalises **glob lines** away (`profile.* @` becomes one line
  per parameter on the next render). That is deliberate bulk-edit sugar, and it is
  the clearest case where the buffer *must* be replaced after an apply rather than
  patched.
- `PUT` is a mutating verb: 409 `RUN_IN_FLIGHT` while a run is going, and the
  state refusal outranks a parse complaint.

From **WP-1010** (frontend scaffold, landed 2026-07-30): `api.ts` already has
`textdoc()` / `putTextdoc(text, baseRevision, validateOnly)`, and CodeMirror will
be the **first real dependency in the dist** — everything so far is 48.7 kB of JS
because plotly is served from the Python package rather than bundled. Budget for
it deliberately (the WP-1010 report: ≤250 kB gz first load, 52.8 kB used), and
consider whether `vendor-cm.js` should be a separate chunk — `vite.config.ts`
currently forces one chunk (`codeSplitting: false`) to keep the committed dist
reviewable, which is a decision to revisit rather than inherit silently.

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
