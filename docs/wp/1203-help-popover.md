# WP-1203 — The help popover: one mechanism across the panels

Milestone: v1.2 · Status: ⬜
Depends on: WP-1201 (the registers), WP-1202 (the corpus)

## Goal

Hovering any entity that has help shows the help cursor; a click opens one
popover with the entry's title, description, unit, default, typical range and
a link into the manual. `title=` survives only on buttons, as a verb phrase.

## Context

User decision (2026-08-25): **cursor-only**, no visible mark before hover
(the alternatives offered were a dotted underline and a ⓘ glyph). The user's
own words: "on cursor-over things such as headings, should have cursor changes
to question mark + cursor, and on click shows a clear description of that
entity's role in the refinement, with good default values or common ranges".

Findings:

- No popover, tooltip or help component exists; `cursor: help`,
  `aria-describedby`, `popover` and `role="tooltip"` have zero hits in
  `gui/src`. `title=` counts per panel: Peaks 41, Series 23, Model 16,
  History 10, Plot 10, Params 9, Plan 9, Report 9, App 9, Structure3D 8,
  Console 2, Text 2; plus `lib/controls.ts` 22 and `lib/wizard.ts` 17 as
  `title:` props.
- Where the corpus lands (WP-1202): a `ParameterRow` carries `help_key`, the
  family glob, **not** the entry — inlining one on every row measured 3.4x the
  `/api/params` payload (20.8 kB → 70.0 kB on the NAC example) against 40.7 kB
  for the whole registry fetched once. `GET /api/help` serves the arms;
  `help_key` is `None` only when no family claims the path, never "nobody
  looked". Fetch it once at startup like `/api/capabilities`: it needs no
  project and is not behind the in-flight 409.
- The arms and their key vocabularies: `parameters` (a list, grouped by entry,
  each carrying every glob that reaches it), `peak_flags` (13, `PeakFlag`),
  `peak_diagnostics` (12 `PEAK_*` codes), `stage_fields` (9 `StageSpec`
  fields), `reader_options` (2), `instrument_fields` (11, the union of
  `INSTRUMENT_PRESETS`), `plans` (7, each carrying `modes`) and — added here —
  `search_fields` (21, `IndexingControls` flattened one level). Six fields per
  entry: `title`, `description`, `unit`, `default`, `typical`, `anchor`.
- Panels where a term needs help: Params (parameter names), Model (field
  labels, atom columns, the wizard's fields), Plan (stage fields, the preset),
  Peaks (flag chips, table headers, the search controls), Report (statistic
  names), History (Rwp, GoF, action names), Series (status chips), Plot
  (residual and scale knobs). Panel headings too.
- Two meta-tests already pin that fields carry a `title`
  (`wizard.test.ts:178-207`, `controls.test.ts:55-60`): they become "carry a
  help key that resolves in the corpus". Their target set is ready — every
  `INSTRUMENT_PRESETS` field and every `StageSpec` field has an entry, crossed
  both ways — so the converted test can pass on day one.
- jsdom traps recorded in `gui/CLAUDE.md`: no `ResizeObserver`, no
  `DragEvent` (filled in `test-setup.ts`); a popover positioned from
  `getBoundingClientRect` gets zeros there, so position logic is a pure
  function in `lib/help.ts` and asserted on numbers.

Design:

- `gui/src/panels/Help.svelte`: `<Help for="phases.*.cell.a">term</Help>`
  wraps the term in a `<span class="help">` (`cursor: help`, no decoration);
  click opens the single app-level popover (one instance mounted in `App`,
  fed through a store: anchor rect + entry). Esc, click-away and a second
  click close it. Keyboard: the span is focusable and Enter opens it.
- `lib/help.ts`: `resolve(key)` over the params rows and the `/api/help`
  arms; `place(anchor, viewport, size)` returns the popover position (below
  the anchor, flipped above when it would leave the viewport, clamped
  horizontally).
- The popover body: title, description, `unit`, `default`, `typical`, and
  `in the manual →` to the entry's anchor. **Decided on arrival** (WP-1202
  handed this WP the choice): an `anchor` becomes `page.html#heading-id`
  relative to the manual root, and `GET /api/help` carries `docs_url` beside
  the arms so no frontend spells the site's address. Measured: 30 distinct
  anchors, every one on exactly one page of the built manual, so the change
  was mechanical and `test_every_anchor_resolves_in_the_built_manual` now
  checks the page as well as the id.
- `title=` audit. Measured inventory: 151 `title=` in the components — 58 on
  `<button>`, 93 not (29 `<label>`, 30 `<span>`, 8 `<th>`, 5 `<p>`, 5
  `<input>`, 4 `<td>`, 3 `<option>`, 3 `<Splitter>`, 5 `<div>`) — plus 21
  authored `title:` strings in `lib/controls.ts` and 11 in `lib/wizard.ts`.
  **Decided on arrival**, against this WP's "expects none": 18 of the 93 are
  not authored prose at all, so the rule is *what a title may be* rather than
  *where it may sit*. A `title=` survives on a `<button>` as a verb phrase,
  and on anything else only where it reveals a value the layout truncated
  (6 sites: `project.path`, `node.api_call`, `row.path`, two `dof.path`).
  The 12 carrying a sentence the **server** wrote (`held_because`,
  `refuted_reason`, `maturity.message`) become `<Help text={…}>`, which is
  what makes App's `⚠ not a fit yet` chip keyboard-reachable — the debt
  WP-1201 left here. The vitest is therefore: no `title=` string literal
  outside a `<button>`, and no authored `title:` prose in `lib/*.ts`.

## Non-goals

- No help *content*, with one exception taken on arrival: entries are
  WP-1202's, and a missing entry renders the popover with the title and a
  "not yet described" line and is a test failure there, not here. The
  exception is the `search_fields` arm — WP-1202 covered no indexing search
  setting, so `lib/controls.ts`'s 21 strings had nowhere to go and the task
  below could not be done. They were **moved**, not rewritten.
- No wizard prose rewrite (WP-1205), no peaks flag labels (WP-1209): those
  WPs *use* this component.

## Tasks

- [x] The corpus side the client depends on: `anchor` gains its page,
      `GET /api/help` gains `docs_url`, and the `search_fields` arm lands
      with its both-ways cross and a default crossed against the schema.
- [x] `lib/help.ts` (`resolve`, `place`) + `help.test.ts` on the placement
      numbers and the resolution order, plus `tests/test_gui_help.py` and the
      committed key set every literal `<Help for=…>` is crossed against.
- [x] `Help.svelte` + the single popover in `App.svelte`; the help cursor
      and the popover styled on WP-1201's tokens. Params is wired as its
      first consumer, and the header chip's owed debt is paid.
- [x] Wire every term the corpus covers: Params (paths, held rows), Model
      (cell edges, atom columns, the wizard's preset fields, the instrument
      editor, reader options), Plan (stage fields, the preset), Peaks (flags,
      diagnostics, the 21 search controls). `lib/controls.ts` and
      `lib/wizard.ts` now *derive* a corpus key from each field's own name
      rather than carrying prose; `lib/model.ts`'s `Field` gains `help` and
      keeps `title` as a named escape. Both title meta-tests retargeted.
- [x] The `title=` audit as a **counted budget** rather than a ban: 51
      authored literals remain, per file, each fails both ways. Report
      statistics, series settings, indexing result columns and the 3D drawing
      thresholds are vocabularies the corpus does not describe, and they
      arrive with the WPs that own those panels.
- [ ] Browser pass: open the popover on each panel, light and dark, at the
      sidebar floor (flip and clamp exercised); rebuild the committed dist.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_dist.py -q
```

The title vitest is green; the browser pass shows one popover style on every
panel.

## References

- WP-1032: `title=` as the only help mechanism and the no-mute-fields rule
  this WP retargets.

## Handover log

- **2026-08-25** — created from the v1.2 triage.
