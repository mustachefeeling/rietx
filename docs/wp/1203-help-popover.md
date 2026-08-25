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
