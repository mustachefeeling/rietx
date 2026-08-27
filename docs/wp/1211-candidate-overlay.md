# WP-1211 — Indexing candidates on the plot

Milestone: v1.2 · Status: ⬜
Depends on: WP-1210

## Goal

Selecting a candidate cell in the Peaks tab draws its predicted reflection
positions as vertical lines through the data, with everything else hidden.

## Context

The user: "Need a way to show indexing candidates as vertical lines through
just the data."

Findings (2026-08-25):

- Selecting a candidate sets `expanded` (`Peaks.svelte:85, 641-644`) and
  renders a detail row; nothing reaches the plot. `Plot.svelte`'s props
  (`:49-112`) carry no candidate.
- The served candidate (`session.index_result`, `session.py:1556-1592`;
  `CellCandidate`, `schemas/indexing.py:813-857`) carries **no predicted 2θ
  list**. The only 2θ arrays in the payload are
  `AmbiguityPartner.discriminating_two_theta`,
  `LeBailValidation.predicted_but_absent_two_theta` and
  `unmatched_observed_two_theta`; the client types none of them
  (`lib/peaks.ts:160-165`).
- The only vertical-tick trace is the fitted model's `ticks`
  (`Plot.svelte:313-321`), in its own band (`TICK_BAND`, WP-1032), fed from
  `curve_window` (`session.py:2349-2351`).
- Predicted positions for a cell are one `generate_reflections` call over
  the pattern's 2θ range at the instrument's wavelength(s), no fit.
- Reading rule (root CLAUDE.md): `predicted_but_absent` means "this cell
  predicts lines the pattern lacks", never "too big". The overlay is where a
  person sees that.

Design: `GET /api/index/candidate/{i}/ticks` returns `{two_theta: [...],
hkl: [...]}` for the candidate's cell and centring (Laue-unique positions,
every emission line, like `RefinementResult.ticks`); Plot takes
`candidate: {label, two_theta} | null` and draws full-height lines in the
tick style; selecting a candidate switches the plot to data-only
(WP-1210) and restores on deselect; hovering a candidate row previews it.
An eager `predicted_two_theta` field on `CellCandidate` was considered and
declined: it would grow every indexing answer by hundreds of floats per
candidate for one consumer.

### Inherited

From **WP-1209** (2026-08-27, shipped):

- `panels/Peaks.svelte`'s authored-`title=` budget in `lib/help.test.ts` is
  **10** now, and nine of the ten are the candidate and extinction tables'
  (the `absent`, `ΔBIC`, `testable`, `refuting`, `space groups` headers, the
  two "ranked, not chosen" hints, the streamed-grade chip, the not-screened
  chip); the tenth is the add-at-2θ box. Describing them means a corpus arm
  keyed by a live vocabulary — 1209 added `peak_origins` in one commit
  (`help.py`, `test_help.py` `_arms`, `test_gui_help.py` `ARMS`,
  `lib/help.ts` `ARMS` + `HelpCorpus`, `docs/manual/conf.py` `_ARMS`, the
  regenerated `help_keys.json`), which is the checklist. The budget fails
  both ways, so each title removed is a decrement in the same commit.
- A candidate's chips (`confidence`, `found_by`, caveats) may carry a
  `HelpEntry.label` the same way flag chips do, if they become corpus terms:
  `labelFor(corpus, key)` and the popover's `Name` row are already there.

From **WP-1210** (2026-08-27, shipped):

- **The "data-only" this WP's design leans on exists**, and it is not a
  separate mode: `dataOnlyHidden(toggles)` / `isDataOnly(toggles, hidden)`
  (`lib/plot.ts`) over the same unpersisted `hidden` exception list, with
  `Plot.svelte` holding the previous list so the second press restores the
  picture rather than showing everything. Drive the overlay through those two
  rather than adding a flag; and note `dataOnlyHidden` covers ids that are
  *listed but not drawable*, which is the property that stops a hidden layer
  reappearing when its tab comes up.
- **A new plot mark needs a `--plot-*` token of its own, and the hue space is
  nearly spent.** `--accent`/`--bad` are `--plot-diff`/`--plot-calc` exactly on
  the light theme, so borrowing chrome is what made the peak fit and the model
  one red line. `tests/test_gui_palette.py` holds every plot colour to the 0.13
  OKLab floor and will fail on a new one that collides. Measured while choosing
  1210's pair: violet is 0.10-0.12 from `--plot-diff` and `--warn` 0.053 from
  `--plot-calc`, magenta is now taken — **green (≈126-150°) is what is left**.
  A candidate overlay drawn "in the tick style" may be able to spend no colour
  at all, which is the cheaper answer.
- **A layer is drawn only where it can be edited or acted on** (the Peaks tab
  for peaks). If the overlay is a Peaks-tab thing, gate it the same way, and
  remember `peaksActive`-style props are *drawing* inputs: the one in
  `Plot.svelte`'s repaint effect is what makes leaving a tab take the layer off
  the plot. Without it the tab click redraws nothing.

## Non-goals

- Drawing the Le Bail validation's calculated profile.
- Multi-candidate overlay.

## Tasks

- [ ] The route in `GuiSession` + `server.ROUTES`; tested on the corundum
      cell against `generate_reflections` directly.
- [ ] Plot prop and lines; auto data-only while a candidate is selected;
      row hover preview.
- [ ] Browser pass on the corundum example after indexing; dist.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_peaks.py -q -k candidate
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1024 (Le Bail validation), WP-1032 (the tick band).

## Handover log

- **2026-08-25** — created from the v1.2 triage.
