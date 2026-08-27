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

Design: `GET /api/index/ticks?candidate=<i>` returns `{two_theta: [...],
hkl: [...], line: [...]}` for the candidate's cell and centring (Laue-unique
positions, every emission line, like `RefinementResult.ticks`). **A query
string, not a path segment** — `server.ROUTES`'s own rule, stated above the
table: the surface has no path parameters, and `GET /api/structure/symmetry`
`?phase=` is the precedent. Plot takes `candidate: {label, two_theta} | null`
and draws full-height lines in the tick style; selecting a candidate switches
the plot to data-only (WP-1210) and restores on deselect; hovering a candidate
row previews it. An eager `predicted_two_theta` field on `CellCandidate` was
considered and declined: it would grow every indexing answer by hundreds of
floats per candidate for one consumer.

Three things the route must get right, none of them in the sentence above
(measured; the handover has the numbers):

- **Two shifts exist and one of them belongs on these lines.** Not the
  instrument's `zero_shift` — indexing fits the metric to the peak list's raw
  2θ, so the cell already reproduces observed positions. Yes to the
  candidate's own `shift_template`/`shift_coefficient`, inverted:
  `refine_candidate` fits to `2θ_obs − c·T(θ)`.
- **The lattice group, never a space group** — quoted from
  `structure_from_candidate`, so what is drawn is what the Le Bail validation
  was scored against.
- **A cap, because `max_d_axis` admits a cell that predicts 92 103 lines** over
  5-120° at the Cu doublet. Thinned by rank in 2θ with `n_total` beside it, not
  truncated: a head-of-list cut leaves the high-angle half empty, which reads
  as "this cell predicts nothing there".

### Inherited

*Consumed 2026-08-27 — the WP-1209 tooltip note folds into Tasks (the panel's
`title=` budget moves with the row control this WP adds), and both WP-1210
notes are now decisions in Design and in the tasks below. Nothing stale.*

- **The panel's authored-`title=` budget is 10** (`lib/help.test.ts`,
  `panels/Peaks.svelte`), and it fails **both ways** — so a `title=` added or
  removed by this WP is a decrement or increment in the same commit. Nine of
  the ten are the candidate and extinction tables'; describing them properly
  means a corpus arm keyed by a live vocabulary, which WP-1209 did in one
  commit (`help.py`, `test_help.py` `_arms`, `test_gui_help.py` `ARMS`,
  `lib/help.ts` `ARMS` + `HelpCorpus`, `docs/manual/conf.py` `_ARMS`, the
  regenerated `help_keys.json`) and which is the checklist if a chip here
  becomes a corpus term.

## Non-goals

- Drawing the Le Bail validation's calculated profile.
- Multi-candidate overlay.

## Tasks

- [x] The route in `GuiSession` + `server.ROUTES`; tested on the corundum
      cell against `generate_reflections` directly.
- [x] Plot prop and lines; auto data-only while a candidate is selected;
      row hover preview. `tests/test_gui_palette.py`'s 0.13 OKLab floor is
      what a new `--plot-*` token has to clear, and the free hue space is
      **green (≈126-150°)** alone (WP-1210 measured the rest); an overlay
      drawn in the tick style may spend no colour at all, which is cheaper.
      Gate it to the Peaks tab the way the peak layer is gated, and remember
      `peaksActive`-style props are *drawing* inputs — the one in
      `Plot.svelte`'s repaint effect is what makes leaving a tab take a layer
      off the plot. Keep the panel's `title=` budget balanced (see Inherited).
- [x] Browser pass on the **fap** example after indexing; dist. (Corundum is
      not an example project and cannot become one — `qarr/*.prn` carry no
      licence statement, WP-1204. The fap example is the better subject
      anyway: a Cu doublet, so the drawn pairs are the "every emission line"
      claim under a lens.)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_peaks.py -q -k candidate_ticks
npm --prefix gui test && npm --prefix gui run check
```

`candidate_ticks`, not `candidate`: the broader keyword also selects
`test_extinction_screen_is_cleared_when_the_candidates_renumber`, which reads
two preconditions off the tests above it in a deliberately module-ordered file
(the held screen, and the picked peak list its real `/api/index` runs on) and
therefore fails twice when run alone.

## References

- WP-1024 (Le Bail validation), WP-1032 (the tick band).

## Handover log

- **2026-08-25** — created from the v1.2 triage.
