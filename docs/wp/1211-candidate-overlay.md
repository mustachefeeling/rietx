# WP-1211 — Indexing candidates on the plot

Milestone: v1.2 · Status: ✅ 2026-08-27 — the cell's claim, drawn over the pattern that has to answer it
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

Inherited and consumed 2026-08-27 (WP-1209, WP-1210): both of 1210's notes are
decisions in Design and Tasks above and below; 1209's is the one clause below,
because it is the constraint the row control has to be built inside. **The
panel's authored-`title=` budget is 10** (`lib/help.test.ts`,
`panels/Peaks.svelte`) and it fails **both ways**, so a `title=` this WP adds or
removes is a decrement or increment in the same commit. Nine of the ten are the
candidate and extinction tables'; describing them properly needs a corpus arm
keyed by a live vocabulary, which WP-1209 did in one commit (`help.py`,
`test_help.py` `_arms`, `test_gui_help.py` `ARMS`, `lib/help.ts` `ARMS` +
`HelpCorpus`, `docs/manual/conf.py` `_ARMS`, the regenerated `help_keys.json`)
— the checklist, if a chip here becomes a corpus term. This WP changed one
title's wording and added none, so the budget stands at 10.

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

### 2026-08-27 — a cell's claim, drawn over the pattern that has to answer it

Until now the question "does this candidate predict lines the pattern lacks"
had exactly one form in the GUI: the `absent` column, a count. A count cannot
say *where*, and where is the whole content of the reading rule root CLAUDE.md
attaches to `predicted_but_absent`. Selecting a candidate now draws that cell's
predicted positions as full-height lines through the data, with everything else
cleared away, so the answer is a look rather than a number. On the FAP example
the top candidate's 426 lines sit on the peaks in pairs — Kα1 and Kα2 — and the
supercell rival four rows down predicts 1502 over the same range, which is what
being wrong looks like when you can see it.

**Done.** All three tasks. `GET /api/index/ticks?candidate=<i>` in `GuiSession`
+ `server.ROUTES`; `--plot-candidate` in all three theme blocks with
`test_gui_palette.py` generalised from the peak *pair* to a `LAYERS` tuple; the
overlay in `Plot.svelte` on an overlaying `yaxis4`; the selection and the hover
preview in `Peaks.svelte`; the fetch, the per-index cache and its whole-map drop
in `App.svelte`; `gui/CLAUDE.md` § the candidate overlay, cap 778 → 808; the
dist rebuilt; a browser pass in Chrome on the fap example.

**Measured.**

- Reflection counts, which is what forced the cap. Over 5-120° at the Cu
  doublet: corundum `R -3 m :H` **124**, the fap example's own top candidate
  **426**, its supercell rival **1502**, and the largest cell `max_d_axis`
  admits (25 Å triclinic `P -1`) **92 103** — 460 649 for the same cell over
  1-60° at a synchrotron λ. `MAX_CANDIDATE_TICKS = 2000`, thinned evenly over
  the ranks (not every k-th, which spends half the budget for one line over).
- The shift that matters is the candidate's, not the instrument's. The
  allowance is 0.05°, which as `cos_theta` runs +0.0498° at 10° 2θ to +0.0171°
  at 140° — half a lab FWHM, five synchrotron ones, so drawing without it would
  be visibly off. Evaluating `T` at the Bragg angle rather than the observed one
  costs `c²·dT/d2θ` < 2.2e-5°. In practice `shift_template` is `None` on the
  default path (the search widens its *tolerance* instead), so the correction is
  usually the identity — it is there for the declared-template case, and the
  test injects one.
- Route cost: 1.5-5 ms for an ordinary cell (one `generate_reflections` per
  emission line), 265 ms for the 460 649-line worst case.
- Suites (`[dev]` — no jax, no torch — python 3.12.12, darwin/arm64; the branch
  is a fast-forward from `origin/main`, so these are the merged tree's): fast
  suite **3157 passed / 117 skipped** against 1210's 3153 / 117, which is the
  four `candidate_ticks` adds and no new skip; vitest **476 → 484** (+5
  `lib/plot.test.ts`, +3 `App.test.ts`); `svelte-check` 378 files 0 errors;
  `ruff` clean. **Wall clock is not quotable and is not quoted**: a `/pr-review`
  suite was running in `pr-bench` for most of this session.

**Two departures from the WP's own design, both because a written rule
outranked it.** The route is `?candidate=` and not `/candidate/{i}/ticks`,
because `server.ROUTES`'s own comment says the surface has no path parameters.
And the browser pass ran on **fap**, not corundum: `qarr/*.prn` carry no licence
statement so they cannot be example projects (WP-1204), and fap is the better
subject anyway — a doublet makes "every emission line" a thing you can see.

**Gotchas for whoever is next in this code.**

- `-k candidate` is not this WP's selection and never was. It also picks up
  `test_extinction_screen_is_cleared_when_the_candidates_renumber`, which reads
  two preconditions off the tests above it in a deliberately module-ordered file
  — a held screen, and the picked peak list its real `/api/index` runs on — so
  alone it fails twice, on the precondition and then on the 120 s wait. I fixed
  the first by injection, measured the second, and reverted: half-de-ordering a
  test in a file built that way is worse than leaving it, and the acceptance
  command was the thing at fault. It is `-k candidate_ticks` now.
- The browser found the one defect jsdom could not: at the survey view the
  overlay was drawn **last** and 426 lines over 115° (~3.7 per pixel) buried the
  pattern completely. Drawn first it is a wash under the data. Any later layer
  with a line per reflection wants the same order.
- `.candidates tbody tr` includes the open detail row, so a `nth(k)` selector
  after an expansion is off by one. Cost ten minutes in the driver script.
- A preview and a selection had to become two props (`candidate`,
  `candidatePicked`). Driving the data-only clear off "is something drawn"
  strobed the model on and off once per row the pointer crossed — caught by the
  mount test, not by reading.

**Left undone on purpose, and retargeted rather than left rotting.**
`lib/help.test.ts`'s `title=` budget line for this panel named **WP-1211** as
the owner of the nine authored tooltips on the candidate and extinction tables.
It is not this WP's: 1211 drew lines on a plot and added no `title=`, while
describing those means a new corpus arm, and an arm is crossed against a *live*
vocabulary both ways — so it has to quote something. The thing to quote does
exist, which is the finding to carry: `ΔBIC`, `testable`, `refuting` and
`absent` are `ExtinctionCandidate` and `CellCandidate` **field names**, so an
arm over those two `model_fields` is a real live vocabulary and a
`peak_origins`-sized commit across six files. The comment now says that instead
of naming a closed WP, and the work is unowned.

**Next: WP-1212** (the axes) and 1213 (the hover readout). Two things fall to
them from here: the route already serves `hkl` and `line` per position, which is
what a per-line readout would say and is deliberately unused (`hoverinfo: skip`,
because `x unified` would put a candidate row in the box at every pointer
position); and 1212 already owns 1210's finding that a hidden residual keeps its
subplot's domain, which `data only` — now pressed by this WP as well as by its
button — makes more visible, not less.

- **2026-08-25** — created from the v1.2 triage.
