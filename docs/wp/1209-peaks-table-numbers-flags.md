# WP-1209 — Peaks table: numbers, columns, flags

Milestone: v1.2 · Status: 🔄 2026-08-27
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
  `:1039` `.note` (12px) collided. WP-1201 fixed the mechanism: a chip's size
  is the register's (`--text-xs`, `app.css`), the panel declares no `.chip`
  rule and a literal `font-size` in its `<style>` fails `lib/style.test.ts`,
  and a tone is a member of one app-wide vocabulary (`note` the default, `ok`,
  `warn`, `bad`, `accent`) returned by `lib/peaks.ts`'s `flagTone` /
  `caveatTone` / `confidenceTone`. **A chip is a fact and never acts**: a verb
  on a chip sits beside it in a `.tagged` wrapper. This WP owns the flags
  cell, and a new flag colour is a call to a tone function, never a
  `.chip.<something>` rule.
- **"On/off should be its own column."** The use-for-indexing checkbox is
  the first item of the unnamed actions cell with `↻` and `×`
  (`Peaks.svelte:587-591`); it POSTs `use_for_indexing`, and checking
  **strips every unusable flag** (`gui/peaks.py:188-191`).
- **"Remove the flags text description."** Flags render as bare tokens
  (`Peaks.svelte:605-609`); the fitter's diagnostics render as a strip of
  `code` + `message` (`:569-579`). The vocabulary is `PeakFlag`
  (`schemas/indexing.py:428-442`), thirteen values. Since WP-1203 **a flag's
  meaning is already rendered**: every chip in the flags column and every
  `PEAK_*` code in the strip is a `<Help>` term over `rietx.help`'s
  `peak_flags` (13) and `peak_diagnostics` (12) arms, so what this WP owes is
  the *label* — the short words on the chip — not a second explanation.
  Changing what a flag means is an edit to `help.py`.
- **The panel's authored `title=` budget is 12** (`lib/help.test.ts`, failing
  both ways). Three of the twelve are the peak table's — the add-at-2θ box,
  the `σ assumed` chip, the `origin` chip — and nine are the indexing result's
  (WP-1211). Describing one properly means a corpus arm keyed by a live
  vocabulary, the way `search_fields` was added in 1203; `origin` is
  `ObservedPeak.origin`'s `Literal`, and the σ-assumed chip is the list-level
  `PEAK_SIGMA_ASSUMED`. The 21 search-control fields are done
  (`searchHelp(field)`).

Rules: flagging, never dropping (`schemas/indexing.py:424-427`,
`pick.py:155-160`); the `.rxt` peaks block's only editable columns are
`2theta` and `flags`; `usable` derives from flags only.

Number policy (in `lib/peaks.ts`, pure, tested): intensity shown as
`I/Imax × 100` at one decimal (a `no_intensity` or `fit_failed` line shows
`—`); 2θ at 4 places with the esd in parentheses only when esd < 0.1°, else
the value alone and the flag says why; `d` at 4 places. `formatValue` gains
the esd ≥ 1 guard for every caller (History and Params included).

## Non-goals

- The peak layer on the plot (WP-1210), candidates (WP-1211).
- Changing what the picker fits or flags.
- Re-styling the search form. WP-1201's browser pass saw its twelve centring
  toggles all engaged by default, twelve filled accent buttons, which is what
  `button.on` says and is loud. Whether a defaults-on multi-select wants a
  quieter engaged state is a decision for `app.css`, not `Peaks.svelte`, and
  it belongs to whichever WP next touches that form.

## Tasks

- [x] `lib/peaks.ts`: `formatIntensity`, `formatPosition`; `formatValue`
      guard; `peaks.test.ts` pins the corundum cases (2.1e-49, 5.5e-19,
      σ = 111°, a 1e-13 esd).
- [x] Table: columns `# · 2θ · d · I (rel) · flags · use · actions`; the
      `use` checkbox in its own header column; `origin` chip in its own tone.
- [x] Flags as labels from the corpus (`at bound`, `Kβ ghost`, `W ghost`,
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
