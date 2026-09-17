# WP-1436 — the questions the watcher track left

Milestone: unscheduled · Status: 🚧 2026-09-17 — the six open questions, answered and landed
Depends on: 1429 (the tokens), 1427 (the console walk), 1425 (the seams), 1413 (the cadence), 1428 soft (the width it moved)

## Goal

The six questions the live-watcher track handed to the maintainer are answered,
each with the practice it follows and the measurement behind it, and the answers
are in the code rather than in a WP file. Nothing here reopens a decision the
track already made.

## Context

The track closed on 2026-09-17 with [1428](1428-open-in-the-gui-without-touching-the-fit.md),
sixteen rungs, and `../ROADMAP.md` § Current focus listed six questions as the
maintainer's. They were asked, and answered on 2026-09-17:

| # | The question, as its WP left it | Answer |
|---|---|---|
| 1 | The GUI's tick rows take plotly's colorway (1429, 1427) | Okabe-Ito, one list, all three surfaces |
| 2 | `abandoned` shares the warning hue with `cancelled` (1429) | `abandoned` goes neutral |
| 3 | The snapshot cadence, 50 ms against 17.7 (1413) | Every stage, and the exception is recorded |
| 4 | Whether the run pane should be collapsible again (1425) | Restore the toggle |
| 5 | Whether the list default should be 72ch or 80ch (1425, 1428) | 80ch stays |
| 6 | Whether a cold open seeks to a long log's tail (1427) | It seeks |

### 1. The tick palette

**What the GUI does.** `panels/Plot.svelte` pushes a tick trace per phase with
`marker: { symbol: "line-ns-open", size: 8, line: { width: 1 } }` and **no
colour**, so plotly assigns from its own cycle by position in the trace array.
Every trace before it is conditional — the observed points, the masked points,
the calculated curve, the background, the residual, and the candidate layer —
so a phase's colour moves when the background is freed, when a reader toggles a
curve off in the legend, and when the pattern has an excluded region. WP-1427
reported the first of those; the other two are this WP's.

**What the two lists measure.** In OKLab with the package's own metric
(`gui/structure3d._oklab_distance`, floor 0.13), scored against every curve
role and page of both themes on both surfaces:

| list | weakest role distance | weakest pair |
|---|---|---|
| `PALETTES["light"]["phase"]` (tab10) | 0.043 | 0.142 |
| `PALETTES["dark"]["phase"]` | 0.074 | 0.113 |
| Okabe-Ito, the four below | **0.078** | **0.184** |

So the shipped lists are worse than the replacement on both counts, and the
dark one fails its own pairwise floor: `#6fb1ff` and `#c9a6ff` are 0.113 apart.

**Which four, and why those.** Okabe-Ito is eight colours for a white page
(Okabe & Ito 2002; Wong, *Nature Methods* **8**, 441, 2011), and the Rietveld
plot has already spent the red and blue ends of it: orange and vermillion land
0.061 and 0.065 from the calculated curve, blue and sky blue 0.053 and 0.078
from the difference curve. What is left is **bluish green, reddish purple, sky
blue and yellow**, and sky blue survives only because the tick band is its own
row. Black is not in the set: the house rule spends it on the single-phase row,
where it is the neutral rather than a member.

**The order is the page's, not the palette's.** Spending order is by contrast
against the page — bluish green 0.390, reddish purple 0.330, sky blue 0.280,
yellow 0.191 — because a tick that collides with a curve is still in a row of
its own, and a tick invisible against the page is not saved by anything. Which
four is the curve measurement's answer; in what order is this one's.

**Practice.** One stable colour per phase, chosen by the program: GSAS-II makes
it a configurable list (`Ref_Colors`), and the house figure style declares
`PHASE` with four members, a cap ("past four the rows want labels"), and the
single-phase neutral rule. Assignment by trace index is nobody's practice.

### 2. The two pills

`abandoned` and `cancelled` are `--warn` at 12 % and 18 %, so they read as one
pill and the word is what separates them. CI dashboards reserve hue for
outcomes and make cancelled or aborted neutral (Jenkins, GitHub Actions), and
GitLab's open issue about that grey in dark mode is the reminder that the
neutral still has to be readable. Here the two facts are not the same kind:
`cancelled` is a person's decision, `abandoned` is a writer that died without a
last word, which is what `unknown` says too. So `abandoned` joins the neutral
and `cancelled` keeps the warning tone.

### 3. The snapshot cadence

WP-1413 measured the charge and left the cadence to the maintainer: 8.30 /
6.54 / 10.56 ms a stage on `nac` / `cpd-2` / `trigger`, whole-fit shares 50 /
59 / 84 ms, ratios 1.233× / 1.049× / 1.031×. Only `nac` is over the 5 % budget
and it is a 0.354 s fit, where the whole charge is 50 ms.

**The answer is no change, and the reason is written down.** The budget is a
ratio, and on a sub-second fit a ratio is the wrong test — nobody watching a
0.354 s fit can perceive 50 ms, and thinning would cost the live view its
redraws on precisely the fits somebody is watching. Practice agrees on where a
throttle goes when one is needed: loggers write on the loop's own boundary and
flush on a time interval (TensorBoard's `flush_secs`, default 120 s), so if
this number ever moves the throttle is by time, never by count.

### 4. The run pane's collapse

WP-1425 removed `toggle-run` on the grounds that a grip collapses the pane it
sizes, leaving End on the focused list grip as the gesture. Measured, End does
give the full-width list (1155 px of 1500). Practice keeps both: VS Code has
⌘B as well as a draggable sash, because a keyboard gesture on a focused
splitter is not discoverable. The toggle comes back.

### 5. The list width

Measured at two window widths, the list is 578 px at 80ch and 520 px at 72ch.
At 1180 px the 72ch list elides every run name in the column 1428 widened for
(`57…`, `72…`, `na…`) while 80ch keeps `577C`, `720C` and `nac.rex` whole. The
58 px 1425 was protecting does not buy the picture a legend row back at either
width. 80ch stays.

**A defect found while measuring it, and not the width's fault.** At 1180 px
the plot's legend wraps to two rows and the `n of m pts drawn` caption is drawn
over the wrapped row. It is WP-1424's rule one surface along — measure ink
against room — and it is fixed here.

## Non-goals

- **No new decision about what the snapshot contains** (1413's non-goal, and
  the cadence answer is no change).
- **No reopening of the seam model.** The toggle returns as a control beside
  the list; the grips keep the behaviour 1425 gave them.
- **No new colour roles.** The phase set is a categorical palette; the nine
  chrome tokens and the curve roles are untouched.

## Tasks

- [ ] `viz/theme.py` owns the phase palette: the four Okabe-Ito colours, one
      list for both themes, the order rule and the measured numbers in the
      note. `viz/plots.PALETTES` reads it rather than declaring its own, and
      `tokens.css` carries `--phase-0…3`.
- [ ] The GUI's tick traces take the phase colour by phase index, sampled per
      paint like every other colour, and a single-phase pattern takes the
      neutral (`--plot-obs`'s tone, the house rule).
- [ ] The watch page's `ticks` come from the same authority and follow the
      theme, rather than sending the dark list to a light page.
- [ ] `tests/test_gui_palette.py` holds the phase set to its own floors —
      pairwise, against the curve roles, against the page — and names the
      weakest link as a number, so a retune cannot quietly make it worse.
- [ ] `abandoned` takes the neutral tone; the CSS note says why the two are not
      one fact; `test_watch_app`/vitest pin the class.
- [ ] Regenerate the manual's committed figures and the GUI dist; every
      surface drawing a phase colour is the new list.
- [ ] Restore the run-pane toggle: the control, its keyboard path, the browser
      test that it collapses and restores, and the chapter sentence.
- [ ] A cold open seeks to the tail: the route takes the end of the log, the
      client's `offset` means what it already meant, and the manual says a page
      opens at the newest event.
- [ ] The legend/caption collision at narrow widths, measured before and after.
- [ ] `docs/ROADMAP.md` § Current focus loses the six questions; the cadence
      answer is recorded where 1413's measurement lives.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

Plus, by looking: the two pages side by side on a two-phase pattern in both
themes, and the run list showing the five liveness words.

## Findings

*(written as the work lands)*

## Handover

- **2026-09-17** — created, from the maintainer's answers to the six questions
  the track left. The three colour and layout answers were chosen against
  practice rather than taste: GSAS-II and the house figure style for the phase
  palette, CI dashboards for the pills, VS Code for the toggle.
