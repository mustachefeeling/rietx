# WP-1201 — GUI house style: tokens and registers

Milestone: v1.2 · Status: ⬜
Depends on: —

## Goal

One token layer and eight control registers, each register meaning one thing
and drawn one way everywhere; a test that no panel redeclares a size; the
header rebuilt as the exemplar. Every other v1.2 GUI WP builds on this one, so
it lands first (user rule, 2026-08-25: "before making any other changes").

## Context

The rule the user set: **a style element communicates one specific thing, and
that thing is consistent throughout the interface.** Size is a property of a
register, never of a call site. The 2026-08-25 inventory (three read-only
passes over `gui/src`) found:

- **The header carries five button geometries** (`App.svelte:672-748`):
  `button`/`button.ghost` at 13px / `5px 12px` (`app.css:114-126`), the
  `.segmented` controls at 11.5px / `3px 9px` (`app.css:151-160`), the theme
  segmented re-sized to 12px / `3px 7px` (`App.svelte:912-916`), `⚠ not a fit
  yet` as `ghost tiny warn` at 11px / `0 5px` (`App.svelte:698-701, 899-903`),
  and the status `.pill` at 12px mono (`app.css:175-181`). The tab strip
  (`App.svelte:994-1009`) is a sixth, undeclared register.
- **Sizes are literals.** `app.css:13-40` defines colour, plot-colour and one
  typographic token (`--mono`); there is no font-size, spacing or radius token.
  Panels use eight literal font sizes (10, 10.5, 11, 11.5, 12, 12.5, 13, 15px;
  68 `font-size` declarations). `.small` (11.5px) is redeclared in nine panels,
  `.tiny` in five, and `Report.svelte:345-348` redeclares `button.tiny` at
  10.5px against the global 11px; `Console.svelte:130-133` has a 10px button.
- **Chips have three geometries**: mono 10px / `0 4px` / radius 8
  (`History.svelte:447-455`, `Report.svelte:393-401`), 10px / `0 5px` / radius
  7 (`Peaks.svelte:989-996`, `Series.svelte:917-924`), and a border-less
  `inline-flex` chip sized by `.tiny` (`Structure3D.svelte:461-466, 340`).
- **A specificity collision is the "different-sized chips" the user saw**:
  `Peaks.svelte:989` `.chip { font-size: 10px }` and `Peaks.svelte:1039`
  `.note { font-size: 12px }` are equal specificity, so `class="chip note"`
  (the tone `flagTone` gives `position_at_bound`, `Peaks.svelte:485,500,526,
  658` and the flags cell) renders at 12px while `excluded` (`chip out`) and
  `manual` (`chip origin`) render at 10px. Same shape in `Series.svelte:917`
  vs `:936`. The register rule fixes it by construction.
- **Chips act**: `button.chip.act` (`Peaks.svelte:1002-1003`, the space-group
  adopt chips at `Peaks.svelte:773-777`) and `button.chip.warn`
  (`Series.svelte:926-931`) give a chip a cursor and hover.
- `Text.svelte:297-302` redeclares `.pill` without `--mono`; `Text.svelte:356`
  declares `button.link`, a link-shaped button.

The design (from the plan, 2026-08-25):

| Register | Means | Folds in |
|---|---|---|
| `button` | the one state-changing action in its region (Run, Create, Apply) | — |
| `button.ghost` | any other action; **same size** as primary | `h2 button`, every `.small`/`.tiny` button |
| `.segmented` | choose one of N views or modes | the theme control's own size |
| `.tab` | choose one of N panels | one size, no growth |
| `.chip` | a **non-interactive** fact (flag, tag, status); tone by colour token | the three geometries; `button.chip.*` become `button.ghost` |
| `.pill` | a live mono readout (status, Rwp) | `Text.svelte`'s copy |
| `.link` | inline navigation | `button.link` |
| help | `cursor: help` + click popover | landed by WP-1203 |

Tokens, all in `app.css`: a type scale `--text` 13px, `--text-sm` 11.5px,
`--text-xs` 10.5px; a space scale `--s1..--s4` = 2/4/8/12px; radii
`--r-control` 5px, `--r-chip` 8px; the existing colour and plot tokens. Chips
get one tone set: `note`, `warn`, `bad`, `ok`, `accent`.

Rules carried from earlier WPs that this one must not break: **overflow is
wrap, never truncation, and the buttons do not grow** (WP-1034; the header
wraps at 860px); a **stored size is not a settled size** (WP-1029); the theme
is three-way and resolved once (`data-theme` on the root). Prose a user reads
in the GUI is written under `/yue-docs-style`; a button's `title=` is a verb
phrase (this WP writes that rule into `gui/CLAUDE.md`).

## Non-goals

- No new help mechanism (WP-1202/1203); `title=` strings stay where they are.
- No panel content changes; layout inside a panel only where a deleted local
  rule needs a register in its place.
- No change to the plot's own palette (`--plot-*`).

## Tasks

- [x] `app.css`: the type/space/radius tokens; the eight registers written
      once, each with a one-line comment saying what it means; delete
      `.small`/`.tiny`; chip tones as one set.
- [x] `App.svelte`: the header on the registers (`Open…` ghost, the three
      segmented controls at register size, the status pill, `Run` primary,
      `Cancel`/`⌘K` ghost, `⚠ not a fit yet` as a `chip bad`); the tab strip
      as `.tab`.
- [x] Every `panels/*.svelte` `<style>`: delete local `button`, `.chip`,
      `.pill`, `.small`, `.tiny` rules and literal font sizes; replace call
      sites (`class="ghost tiny"` → `class="ghost"`, `button.chip.act` →
      `button.ghost`, `chip tiny` → `chip`), keeping every existing tone.
- [x] `gui/src/lib/style.test.ts`: reads every `panels/*.svelte` and
      `App.svelte` `<style>` block (a regex over the file, no compiler) and
      fails on `font-size`, `padding` or `border-radius` declared on a
      selector containing `button`, `.chip`, `.pill`, `.segmented` or `.tab`,
      and on any `font-size:` whose value is not `var(--text`; a second
      assertion greps `gui/src` for `.small`/`.tiny` selectors and class
      names and expects none.
- [ ] `gui/CLAUDE.md` § House style: the register table compressed to one
      rule per register, the token rule, the docs-style rule for GUI prose.
- [ ] Browser pass (playwright-core in the scratchpad, `gui/CLAUDE.md`):
      light/dark screenshots of the header and of each panel at the sidebar
      floor and ceiling (WP-1034's widths), compared by eye against the
      register table; rebuild the committed dist.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
npm --prefix gui run build && git diff --exit-code src/rietx/gui/static || echo "dist rebuilt: commit it"
.venv/bin/python -m pytest tests/test_gui_dist.py tests/test_docs_consistency.py -q
grep -rn "\.small\b\|\.tiny\b" gui/src --include=*.svelte --include=*.css | wc -l   # 0
```

The header screenshot shows at most three control geometries (button,
segmented, pill); the style test is green.

## References

- WP-1029 (usability), WP-1032 (repairs), WP-1034 (panel layout): the layout
  rules restated above.
- The user's notes of 2026-08-25 (the plan file for this milestone's opening).

## Handover log

- **2026-08-25** — created from the v1.2 triage.
