# WP-1438 — the questions the watcher track left

Milestone: unscheduled · Status: 🔄 2026-09-17 — the six open questions, answered and landing
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
role and page of both themes **and** the figure palette's roles, which are not
the tokens' — matplotlib orange against the app's red, plus a green ±3σ band:

| list | nearest role | closest pair |
|---|---|---|
| `PALETTES["light"]["phase"]` (tab10) | **0.009** | 0.142 |
| `PALETTES["dark"]["phase"]` | 0.052 | 0.113 |
| Okabe-Ito, the four below | **0.0637** | **0.184** |

So the shipped lists are worse than the replacement on both counts. The light
one's green is the figures' own band green — `#2ca02c` against `#2a9d2a`, one
colour twice — and the dark one fails its own pairwise floor at 0.113.

**The first pass of that measurement was short**, and the test written from it
is what caught it: the search scored the four curve roles and the page and left
out the three overlay layers and the band, so it chose bluish green at a claimed
0.130 when the light candidate overlay sits 0.0637 away. The lesson is
WP-1076's from the other side — a claim is checked where it is *used*, and the
use here is a palette test that scores every role on the page.

**Which four, and why those.** Okabe-Ito is eight colours for a white page
(Okabe & Ito 2002; Wong, *Nature Methods* **8**, 441, 2011), and the Rietveld
plot has already spent the red and blue ends of it: blue lands 0.053 from the
difference curve, orange 0.061 from the figures' calculated curve, vermillion
0.065 from the app's. What is left is **bluish green, reddish purple, sky blue
and yellow**. Black is not in the set: the house rule spends it on the
single-phase row, where it is the neutral rather than a member.

**No four of the eight clear 0.13 against everything**, and a tick row does not
have to: it sits in a row of its own below the data, so hue is a second
encoding and the floor is what a mark drawn *over* the data is held to. The
set is chosen by its weakest link and the number is pinned so it can only
improve. Vermillion in place of bluish green would buy 0.001 and move the
collision onto the *calculated curve*, which is on screen whenever a tick row
is, while the candidate overlay is the indexing tab's.

**The order is the page's, not the palette's.** Spending order is by contrast
against the page — bluish green 0.390, reddish purple 0.330, sky blue 0.280,
yellow 0.191 — because a tick that collides with a curve is still in a row of
its own, and a tick invisible against the page is not saved by anything. Which
four is the curve measurement's answer; in what order is this one's, and the
palette's own order is not used at all: Okabe-Ito's yellow is its weakest
against a white page and its safest against these curves.

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

- [x] `viz/theme.py` owns the phase palette: the four Okabe-Ito colours, one
      list for both themes, the order rule and the measured numbers in the
      note. `viz/plots.PALETTES` reads it rather than declaring its own, and
      `tokens.css` carries `--phase-0…3`.
- [x] The GUI's tick traces take the phase colour by phase index, sampled per
      paint like every other colour, and a single-phase pattern takes the
      neutral (`--plot-obs`'s tone, the house rule).
- [x] The watch page's `ticks` come from the same authority and follow the
      theme, rather than sending the dark list to a light page.
- [x] `tests/test_gui_palette.py` holds the phase set to its own floors —
      pairwise, against the curve roles, against the page — and names the
      weakest link as a number, so a retune cannot quietly make it worse.
- [x] `abandoned` takes the neutral tone; the CSS note says why the two are not
      one fact; `test_watch_app`/vitest pin the class.
- [x] Regenerate the manual's committed figures and the GUI dist; every
      surface drawing a phase colour is the new list.
- [x] Restore the run-pane toggle: the control, its keyboard path, the browser
      test that it collapses and restores, and the chapter sentence.
- [x] A cold open seeks to the tail: the route takes the end of the log, the
      client's `offset` means what it already meant, and the manual says a page
      opens at the newest event.
- [x] The legend/caption collision at narrow widths, measured before and after.
- [x] `docs/ROADMAP.md` § Current focus loses the six questions; the cadence
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

**2026-09-17 — the palette, measured twice.** The first search scored a
candidate against the four curve roles and the page of both themes, and found
bluish green, reddish purple, sky blue and yellow with a weakest link of 0.130.
The palette test written from the same decision scored it against everything
`CURVES` holds — the peak layer's two and the candidate overlay — and failed at
0.064: `#009e73` against the light theme's `--plot-candidate` `#1a8f45`. Adding
the figure palette's roles found a second near-miss, the ±3σ band. The set did
not change, because it is still the best of the thirty-five four-subsets on its
weakest link, but the *number* did and so did the claim in the module note.

What the same widened scoring says about what shipped is sharper than anything
the WP predicted: the tab10 light list is **0.009** from the figures' own ±3σ
band. `#2ca02c` and `#2a9d2a` are one colour, and a two-phase figure drew a
phase's tick row in the band's green for as long as both have existed.

**2026-09-17 — the caption and the legend.** Anchoring both at the paper's top
put them in one corner, and the legend is the one that grows: a second row
arrives when the window narrows *or* when a stage frees the background. The
caption is one line of fixed length, so it is the one that moves. Made to fail
first, on the old placement: red at 1180 and 900 px, green at 1500, which is
where the legend still fits one row.

**2026-09-17 — a flag that only the client may set.** `end=1` is the cold
open's, and the route infers nothing from `offset=0`: a reader tailing a run
from its start sends exactly that, so a route that seeked on it would make two
different requests indistinguishable. The same rule caught the field beside it
— `skipped_bytes`, not `start`: an ordinary poll of a long log also begins far
into the file, so an absolute start would have made every later poll claim
there was more above.

**2026-09-17 — the pane's note may not count what it did not read.** A cold
open's `skipped` is the count of what the *window* held and dropped, which on
the fixture was 46 210 against a log of 60 000: a number smaller than the truth,
printed as the truth. It says the fact without the figure when it has seeked,
and keeps the exact count when the read covered the whole log.

**2026-09-17 — what the numbers dismissed.** Sky blue against the dark
difference curve (0.078) and bluish green against the light candidate overlay
(0.0637) are both under the floor and both stay: a tick sits in a row of its
own, so hue is a second encoding there and the floor is what a mark drawn over
the data is held to. The alternative subset that scores 0.001 better puts its
collision on the calculated curve, which shares the screen with a tick row
always, while the candidate overlay is the indexing tab's.

Two things this WP did **not** do. The readout strip still gives a phase row no
ink: `ReadoutInk` names a `--plot-*` role and a phase colour is not one, so the
strip would need a second way to say a colour. And the run list at full width
stretches the run column across the window, which is what the command exists
for — a long label is why a reader opens it.

## Handover log

### 2026-09-17 — created, and the six answers with the practice each follows

From the maintainer's answers to the questions the live-watcher track left.
None of the six was decided on taste: GSAS-II's per-phase colour list and the
house figure style chose the palette, CI dashboards the state pills, VS Code
the collapse command, log viewers the cold open, and the cadence answer is
WP-1413's own measurement read against what a ratio means on a 0.354 s fit.
