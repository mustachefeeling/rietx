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
- Where the corpus lands (WP-1202): `ParameterRow.help` on `/api/params`
  rows; `GET /api/help` for flags, stage fields, reader options, preset
  fields, presets.
- Panels where a term needs help: Params (parameter names), Model (field
  labels, atom columns, the wizard's fields), Plan (stage fields, the preset),
  Peaks (flag chips, table headers, the search controls), Report (statistic
  names), History (Rwp, GoF, action names), Series (status chips), Plot
  (residual and scale knobs). Panel headings too.
- Two meta-tests already pin that fields carry a `title`
  (`wizard.test.ts:178-207`, `controls.test.ts:55-60`): they become "carry a
  help key that resolves in the corpus".
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
  `in the manual →` to the entry's anchor (the built manual's URL from
  `capabilities()`'s docs link, or the Pages site).
- `title=` audit: every non-button `title=` is either moved into the corpus
  or deleted; buttons keep a verb phrase. A vitest greps the compiled
  components for `title=` on non-button elements and expects none.

### Inherited

From **WP-1202** (2026-08-25, shipped):

- **The row carries `help_key`, not `help`.** `ParameterRow.help_key` is the
  family glob (`phases.*.atoms.*.biso`); the entry itself is in the
  `parameters` arm of `GET /api/help`, where each object lists every glob that
  reaches it, so a key indexes it directly and no client needs `lib/fnmatch.ts`
  for this. Measured reason: inlining an entry on every row is 3.4x the
  `/api/params` payload (20.8 kB → 70.0 kB on the NAC example), against 40.7 kB
  for the whole registry fetched once. Fetch `/api/help` once at startup, like
  `/api/capabilities`; it needs no project and is not behind the in-flight 409.
- `help_key` is `None` only when no family claims the path, never "nobody
  looked": `Refinement.parameters` fills it for every caller. On both example
  models every row carries one (95/95 and 82/82).
- The arms and their keys: `parameters` (list, grouped by entry),
  `peak_flags` (13, keyed by `PeakFlag`), `peak_diagnostics` (12 `PEAK_*`
  codes), `stage_fields` (9 `StageSpec` fields), `reader_options` (2),
  `instrument_fields` (11, the union of `INSTRUMENT_PRESETS`) and `plans` (7,
  each carrying `modes`). Six fields per entry: `title`, `description`,
  `unit`, `default`, `typical`, `anchor`.
- `anchor` is a heading id in the **built** manual, checked by
  `tests/test_help.py`. It is what the popover's "link into the manual" needs;
  nothing renders it yet, so this WP picks the URL shape.
- The two meta-tests this WP converts (`wizard.test.ts:178-207`,
  `controls.test.ts:55-60`) have their target set ready: every
  `INSTRUMENT_PRESETS` field and every `StageSpec` field already has an entry,
  crossed both ways, so "carries a help key that resolves in the corpus" is a
  check that can pass on day one.
- **`gui/CLAUDE.md` has no help rule yet, deliberately.** 1202 changed nothing
  under `gui/src` and left the client-side rule to this WP: where a description
  comes from, and that a new `title=` on a non-button is not the way to add one.
  The root CLAUDE.md carries only the package-side half.

From **WP-1201** (2026-08-25, shipped):

- The `.help` register exists and is **cursor only**: `app.css` declares
  `.help { cursor: help }` and nothing else, which is the "no visible mark"
  decision taken at the milestone opening. Attach the popover to that class;
  do not add a glyph, an underline or a second class beside it.
- Size, padding and radius belong to a register, not to a call site, and
  `gui/src/lib/style.test.ts` fails a panel that says any of the three on
  `button`, `.chip`, `.pill`, `.segmented`, `.tab` or `.link`, or a
  `font-size` that is not `var(--text…)`. A popover is a *new* thing, so it
  gets its own rule in `app.css` — not a size in the panel that opens it.
- Two cascade traps this WP measured in a browser and jsdom could not see: a
  state selector (`button.on`, `(0,1,1)`) keeps every property a more
  specific rule does not restate, and `text-transform`/`letter-spacing`
  inherit into a button. Both bit a register that looked correct in the
  source.
- **A named case for the popover, and it is a regression this WP left behind.**
  `App.svelte`'s `⚠ not a fit yet` was a `<button>` carrying the maturity
  message as its `title`, and is now `<span class="chip bad" title=…>` —
  correct under the register rule (a chip does not act) but the message is on
  a non-focusable element, so it is out of reach of the keyboard and largely
  of assistive tech. 1201's non-goals fenced it off ("`title=` strings stay
  where they are"), so it is owed here: the header chip should be among the
  first things the popover covers, and whatever mechanism it uses has to be
  reachable without a pointer.

## Non-goals

- No help *content*: entries are WP-1202's; a missing entry renders the
  popover with the title and a "not yet described" line and is a test
  failure there, not here.
- No wizard prose rewrite (WP-1205), no peaks flag labels (WP-1209): those
  WPs *use* this component.

## Tasks

- [ ] `lib/help.ts` (`resolve`, `place`) + `help.test.ts` on the placement
      numbers and the resolution order.
- [ ] `Help.svelte` + the single popover in `App.svelte`; the help cursor
      and the popover styled on WP-1201's tokens.
- [ ] Wire Params, Model (editor and wizard), Plan, Peaks (flags, headers,
      search controls), Report, History, Series, Plot, and every panel
      heading; move `lib/controls.ts` and `lib/wizard.ts` titles into corpus
      keys; retarget the two title meta-tests.
- [ ] The `title=`-on-non-buttons vitest; delete or move every hit.
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
