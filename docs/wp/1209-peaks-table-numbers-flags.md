# WP-1209 — Peaks table: numbers, columns, flags

Milestone: v1.2 · Status: ⬜
Depends on: WP-1201, WP-1203

## Goal

The peak table reads like a peak table: intensities as a relative scale,
positions to a sensible number of digits, degenerate lines shown as such, a
`use` column of its own, and flags as short labels whose meaning is one click
away.

## Context

Six notes from the user, one cause each (2026-08-25):

- **"Intensities of 1e-17, 1e-21."** The picker fits areas with a native
  lower bound of exactly `0.0` (`indexing/peakfit.py:343-362`); on the
  certified corundum pattern two components refine to 2.1e-49 and 5.5e-19
  (`indexing/pick.py:163-168`). Such a line is flagged `no_intensity`
  (`pick.py:194-195`, `BOUND_HIT_RTOL`) and is unusable, but the table still
  prints `Number(p.intensity.toPrecision(3))` (`Peaks.svelte:578`).
- **"Ten or more decimal places."** `formatValue` (`lib/table.ts:279-311`)
  chooses `places = -floor(log10(esd))` clamped to 12, so a tiny esd gives
  twelve decimals.
- **"Two theta positions in chips."** The 2θ cell renders value and esd as
  `formatValue` + `formatEsd`; with an esd ≥ 1° the places clamp to 0 and a
  line at 35.09° with the measured degenerate σ of 111° prints `35(111)`
  (`Plot.svelte:417-420` records the 111°; the whisker is capped at 3×FWHM
  on the plot, never in the table).
- **"Chips are different sizes."** `Peaks.svelte:989` `.chip` (10px) and
  `:1039` `.note` (12px) collide; `flagTone` gives `position_at_bound` the
  `note` tone, so it renders larger than `excluded`/`manual`. WP-1201 fixes
  the mechanism; this WP owns the flags cell.
- **"On/off should be its own column."** The use-for-indexing checkbox is
  the first item of the unnamed actions cell with `↻` and `×`
  (`Peaks.svelte:587-591`); it POSTs `use_for_indexing`, and checking
  **strips every unusable flag** (`gui/peaks.py:188-191`).
- **"Remove the flags text description."** Flags render as bare tokens
  (`Peaks.svelte:579-586`) with no tooltip; the fitter's diagnostics render
  as a strip of `code` + `message` (`Peaks.svelte:551-556`). The vocabulary
  is `PeakFlag` (`schemas/indexing.py:428-442`), thirteen values; the corpus
  (WP-1202) carries a label and a sentence per flag.

Rules: flagging, never dropping (`schemas/indexing.py:424-427`,
`pick.py:155-160`); the `.rxt` peaks block's only editable columns are
`2theta` and `flags`; `usable` derives from flags only.

Number policy (in `lib/peaks.ts`, pure, tested): intensity shown as
`I/Imax × 100` at one decimal (a `no_intensity` or `fit_failed` line shows
`—`); 2θ at 4 places with the esd in parentheses only when esd < 0.1°, else
the value alone and the flag says why; `d` at 4 places. `formatValue` gains
the esd ≥ 1 guard for every caller (History and Params included).

### Inherited

From **WP-1201** (2026-08-25, shipped):

- Chip tones are now one app-wide vocabulary — `note` (the neutral default),
  `ok`, `warn`, `bad`, `accent` — declared in `app.css`, and `lib/peaks.ts`
  returns members of it: `flagTone` (its private `"out"` is gone),
  `caveatTone`, and a new `confidenceTone`. A new flag colour is a call to one
  of those, never a `.chip.<something>` rule in this panel.
- **A chip is a fact and never acts.** The space-group adopt chips and the
  centring toggles are `button.ghost` now, and the drop-this-prior `×` sits
  *beside* its chip in a `.tagged` wrapper rather than inside it. A row's flag
  cell may hold chips; it may not hold a chip that is clickable.
- **Left for this WP, seen in a browser**: the twelve centring toggles are all
  engaged by default, so the search form now shows twelve filled accent
  buttons. That is what `button.on` says, and it is loud. If this WP re-styles
  the search form, that is the place to decide whether a multi-select of
  defaults-on wants a quieter engaged state — the decision belongs in
  `app.css`, not in `Peaks.svelte`.
- The panel no longer declares `button`, `.chip`, `.pill`, `.small` or
  `.tiny`, and a literal `font-size` in its `<style>` fails
  `lib/style.test.ts`. Its table is `var(--text-sm)`; a control's label rides
  at the control's size, prose is `var(--text)`.

## Non-goals

- The peak layer on the plot (WP-1210), candidates (WP-1211).
- Changing what the picker fits or flags.

## Tasks

- [ ] `lib/peaks.ts`: `formatIntensity`, `formatPosition`; `formatValue`
      guard; `peaks.test.ts` pins the corundum cases (2.1e-49, 5.5e-19,
      σ = 111°, a 1e-13 esd).
- [ ] Table: columns `# · 2θ · d · I (rel) · flags · use · actions`; the
      `use` checkbox in its own header column; `origin` chip in its own tone.
- [ ] Flags as labels from the corpus (`at bound`, `Kβ ghost`, `W ghost`,
      `not separable`, `shoulder`, `σ assumed`, `no intensity`, …) with the
      code and sentence in the popover; the diagnostics strip folded into a
      count chip that expands.
- [ ] Browser pass on the corundum example after Pick peaks; dist.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_peaks.py -q
```

## References

- WP-1018 (peak picking), WP-1027 (the panel), WP-1110 item 14 (the
  degenerate esds the pseudo-inverse used to truncate).

## Handover log

- **2026-08-25** — created from the v1.2 triage.
