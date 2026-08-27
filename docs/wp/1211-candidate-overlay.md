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
