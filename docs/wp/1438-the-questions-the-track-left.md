# WP-1438 — the questions the watcher track left

Milestone: unscheduled · Status: ✅ 2026-09-17 — twelve questions answered over two rounds; the pages hold a narrow window, a reload and a theme their reader can reach
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

### A second round, 2026-09-17

Six more comments from the maintainer on the same pages, each measured before
it was answered.

- [x] The narrow window: `#main` stacks below the width where the two panes
      cannot both meet their floors, the breakpoint lives once in the
      stylesheet, and the list seam keeps a size per arrangement.
- [x] The list sheds the stage and the start time before it sheds the run
      name, by zeroing the `<col>` rather than hiding the cells.
- [x] The empty `gui` cell says why it is empty, and says nothing per row on a
      watcher that cannot perform the verb at all.
- [x] The console comes back with the rest of the page: the boot's two walks
      become one and a pinned run's log is asked for beside it, with the two
      readers of one tail serialised.
- [x] The theme is settable from the watcher, through one writer beside the
      reader in `viz/theme.py`, with the GUI's own glyphs and sentences and a
      meta-test holding the two equal.
- [x] A tick names its reflection, on all three pages, off a `tick_hkl`
      companion built where the positions are.
- [x] The GUI's title bar wraps rather than forcing a 618 px document.
- [x] `CLAUDE.md` takes the three clauses that govern what comes after them;
      the cap moves in the commit that says so.
- [x] `multi.py` keeps its own tick builder and owes the same pairing, which
      it did not have: one walk yields both lists now.
- [x] `node --check` for `compare_app.py`'s quoted page, the one WP-1430 did
      not reach and this WP edited.
- [x] The manual's screenshots, regenerated for the accent ink.
- [x] The two seam-floor tests read the pane's box off the page rather than
      adding the 1 px that only an overlay scrollbar leaves.

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

**2026-09-17 — the second round, six comments and what each measured.**

*The narrow window.* At 420 px the list kept its declared `80ch` = 578 px, the
run pane came out **0 px wide**, and the document scrolled to 1283 px. The
seam could not have helped: 71ch of columns measured 513 px at this font, plus
the pane's 1 px border, the grip's 5 and the 340 px of picture the run pane
keeps — 859 px, below which the two panes cannot both meet their floors
however the seam is dragged. So that is the breakpoint, computed from floors
already declared rather than chosen. It lives once, as `--stacked`, because a
number in a media query and the same number in javascript are two layouts
disagreeing about which one the page is in.

*Two sizes for one seam.* Chrome DevTools keeps a separate setting per
orientation and this now does too: a px width is not a px height, so one
stored number would hand the reader a pane they never asked for the moment the
window turns. `stackedSize` is on the list seam only — the other two never
stack, and a field nothing reads is a declared name with no writer.

*The table at phone width.* Stacked at 500 px every name in the list read
`5…`: the six declared columns are 66ch = 477 px and the run column is what is
left. Below 563 px — the six plus twelve for a name — the stage and the start
time go, those being the two the page answers elsewhere. **Two mechanisms were
tried and measured before the third was used.** `display:none` on the cells
shifts every later cell one place left into the colgroup: Rwp inherited the
zeroed width while the launch button took GoF's 9ch, and the table still had
the right number of visible cells throughout, which is why the browser test
asserts per column and not a count. `visibility:collapse` on the `<col>` is
the standards answer and collapsed the *flexible* run column along with the
two asked for. What works is zeroing the column and taking the cell's padding
off it, which keeps the cell count equal to the col count.

*Why some runs have no `open`.* They are outside a `.rex` project, so
`project_of` is `None` and there is nothing for the GUI to copy. The row was
correct and said nothing, which reads as a control that failed — WP-1076's
rule from the page's side. The shape of the answer is decided by the
`--read-only` case: there the column is empty for *every* run, so a reason
attached to one row would be a false claim about that row, and the cell says
nothing at all.

*The console flicker.* Measured across a reload with a run pinned: the list
and the picture were drawn at **107 ms** with the console still empty, and it
filled at **248 ms**. The log's fetch was third in a chain of three, and two
of those three were the same request — the boot asked `api/runs` for the
page's constants and the first poll asked again, about 85 ms later, for the
runs it had discarded. Reading the constants off the poll and asking for a
pinned run's log beside the walk puts all three panes in one frame at 123 ms.
Two readers of one tail then became possible and are serialised, because both
would take the same `tail.offset` and append the same lines twice.

*Dark mode was not broken.* `~/.rietx/settings.json` held `"theme": "light"`
and the watcher obeyed it correctly. What was missing was any way to change
it from the page: WP-1429 made the GUI the one writer, which leaves the choice
unreachable for exactly the person `rietx watch` exists for. A user-level
theme is settable from whichever window you are in — VS Code, Grafana and
Jupyter all work that way — so the rule is now one home for the fact and every
page that shows it may set it. It is not under `--read-only`, which fences the
run.

*A contrast defect, found by a guard.* `color:#fff` on the new control's
active segment was caught by `test_no_colour_literal_is_left_in_the_page`.
White on the dark theme's accent measures **2.22:1**, under WCAG AA at any
size; `var(--panel)` is white on light and near-black on dark and measures
6.44 and 7.51. `app.css` carried the literal in three places and had the same
defect on every filled control. The guard the watcher has and the GUI does not
is what found it, which is the answer to "can the two share their styles":
they already share every colour *value*, and it was the sharing that surfaced
this.

*How far the two pages share their styling, asked and answered.* Every
colour **value** is already shared and has been since WP-1429: `viz/theme.py`
owns them, both Python servers render `/tokens.css` from it, `gui/src/tokens.css`
is generated and committed, and a test holds the two byte for byte. The
watcher's stylesheet declares **no** colour literal at all, which its own
guard enforces — and that is what caught the contrast defect above, in a rule
copied from the GUI. So the answer to "will a change be consistent to both" is
yes for colour, demonstrated rather than asserted: an edit to `theme.py` moves
both pages and an edit to either stylesheet's copy fails.

Not shared, and a decision rather than an omission: the **control registers**.
`app.css` declares what a button, a chip, a tab and a `.segmented` group look
like — sizes, padding, radii — and `watch.css` declares its own. The new theme
control repeats `.segmented`'s four rules rather than importing them. Two
reasons. What can cross that line is a *value*: `gui/src` is a build input the
wheel does not ship, so anything the watcher needs has to live in Python, and
a stylesheet of layout rules living in `viz/theme.py` would make `app.css`
generated — a much larger change than the six rules it would save. And the
GUI's compiled stylesheet *is* in the wheel, so the watcher could link it, but
that is hundreds of rules of panel layout for four. The option is recorded
here rather than taken: if a third page ever wants the registers, the move is
to generate them the way the tokens are generated, not to link a built asset.

*The tick hovers.* Distinct reflections land at the same 2θ to every decimal
the snapshot keeps — (3 2 2) and (4 1 0) both at 23.70007 on the module's own
fixture — so a position is not a key into the index mapping, and the hover
box names whichever of the coincident marks plotly picks. Recorded rather
than worked around: grouping them would change the tick count, which Layer 0's
`Region.n_reflections` reads. Cost of carrying the indices: 1.4 kB against a
335 kB snapshot on the NAC demo, 0.4 %.

*A layout constant that was a fact about the mouse.* Two seam tests went red
on a quiet machine after passing on the same machine an hour earlier, with
nothing in between touching `#runs`. The list's floor had gone from 514 px to
529. The difference is the pane's own box, `offsetWidth - clientWidth`: 1 px
of border, and 15 more when `scrollbar-gutter: stable` reserves a *classic*
scrollbar instead of an overlay one. macOS chooses between the two by itself —
its default setting is "automatically based on mouse or trackpad" — so the
constant those tests encoded was a fact about what was plugged into the
machine.

`watch.css` already states the rule and the page already obeys it: the floor
is 71 columns **plus whatever box the pane carries**, "measured rather than
added as a constant" (`SEAMS.list.chrome`). The tests asserted the number
instead of the rule, which is the same class as quoting a wall clock. They
read the box off the page they are asserting about now, so they are right in
either environment rather than right on one machine — and the font metric they
do still assume, 1ch = 7.225, is asserted explicitly so a font change fails
where it is legible rather than as a wrong pane width.

Worth carrying beyond this WP: a browser test may not hard-code a dimension
that the platform's own chrome contributes to.

*The GUI's own narrow window.* Measured for the same comment: at 420 px the
document scrolled to **618 px**, and to 618 at every window below that,
because the header wraps and `.controls` inside it was one unbreakable 604 px
flex line pinned `flex: 0 0 auto`. Fixed. **Deliberately not generalised:**
the GUI's split does not stack, so at 420 px the plot is 98 px wide. It wraps
and stays legible down to about 600 px, and below that it is a different
design question — nine panels, a 3D viewer and a tab strip, against the
watcher's two panes — which the maintainer's comment was not about.

## Handover log

### 2026-09-17 (2nd session) — six more comments, and the pages answer them

Somebody watching a fit can now do three things they could not this morning.
They can put the window on half a screen, or turn it sideways, and still read
both the run list and the picture — before, at a phone's width the list took
its full declared width and the picture was given nothing at all. They can
make the page dark without opening the GUI, which matters because the person
this page exists for drives their fit from a script and never opens the GUI at
all. And they can point at a reflection tick and be told which reflection it
is, on the watcher, in the GUI and in `rietx compare` alike, where before two
of the three told them only the angle the axis under the tick already shows.
Three smaller things went with them: a run that offers no `open` button says
why, the console comes back with the rest of the page instead of a beat after
it, and the GUI's title bar stops forcing a document wider than the window.

The round also found two defects nobody reported. Every filled control in the
GUI inked white on the accent, which on the dark theme is a contrast ratio of
2.22 — below the accessibility floor at any text size, and it had been there
since the dark theme shipped. And a joint fit's tick rows would have been the
one surface still unable to name a reflection, because `multi.py` keeps its
own tick builder and it had not been taught. Both are fixed.

**Done.** The panes stack below 859 px and the list seam keeps a size per
arrangement; below 563 px the table sheds the stage and the start time rather
than the run name. The empty `gui` cell carries its reason, and carries none
on a watcher that cannot open anything. `readPage` takes the page's constants
off the poll every payload already carries, which deletes the boot's second
walk, and a run named in the URL has its log fetched beside that walk instead
of behind it, with the two readers of one tail serialised.
`viz/theme.set_theme_choice` joins `theme_choice`, `POST /api/theme` is the
seam, and the control is the GUI's `.segmented` three drawing its glyphs and
sentences from the module. `tick_hkl` rides beside `ticks` on
`RefinementResult` and `HistogramResult`, `hkl` beside `two_theta` in the
snapshot, built in all three places the positions are built and carried
through the same filter, sort and cap.

**Measured.** All on `[dev]` + playwright, macOS arm64, Python 3.12.

| | |
|---|---|
| fast selection | **5330 passed, 132 skipped, 0 failed** at load 2.3 |
| against this WP's first round | +29 exactly (5301/132 on the merged tree) |
| `tests/test_watch_browser.py` alone | 47 passed |
| vitest / `node --test` | 593 / 48 |
| svelte-check | 381 files, 0 errors |

The numbers behind the decisions: 420 px gave the list its declared 578 px,
the run pane 0 px and the document 1283 px of scroll; 859 px is where the
list's 71ch floor, its border, the grip and the run pane's 340 px of picture
stop fitting together; the console filled at 248 ms against a list drawn at
107, and now all three panes land in one frame at 123; white on the dark
accent is 2.22:1 against `--panel`'s 7.51; the hkl costs 1.4 kB against a
335 kB snapshot.

**Gotchas.** Two reflections land at the same 2θ to every decimal the
snapshot keeps — (3 2 2) and (4 1 0) both at 23.70007 — so a tick position is
not a key into `tick_hkl`, and a hover names whichever of the coincident
marks plotly picks. Grouping them would move the tick count, which Layer 0's
`Region.n_reflections` reads, so it was left and written down. Under
`table-layout: fixed`, `display:none` on a cell shifts every later cell one
column left into the colgroup and `visibility:collapse` on a `<col>` takes
the flexible column with it; only zeroing the column works, and the first two
fail *silently*. And a browser test may not hard-code a dimension the
platform's own chrome contributes to: two seam tests encoded the pane's box
as `+ 1`, which is only true where the scrollbar is an overlay, and macOS
picks that from whether a mouse is attached.

**Deliberately not done.** The GUI's split does not stack. Its title bar
overflow is fixed and it stays legible to about 600 px, but at 420 px the
plot is 98 px wide. Below that it is nine panels, a 3D viewer and a tab strip
against the watcher's two panes — a different design question, and not the
one that was asked. The control *registers* are also still declared twice,
`app.css` and `watch.css`; what crosses that line is colour values, and the
option not taken is recorded in Findings.

**Next:** the WP is closed and the track with it. The decision waiting is
not this WP's — **25 WPs have closed since v1.4.0 shipped on 2026-09-13 and
no milestone is open**, with `pyproject.version` still reading `1.4.0`. That
is what "finalise" meant when this session opened, and it wants a maintainer's
call before any more WPs land under no milestone.

### 2026-09-17 — created, and the six answers with the practice each follows

From the maintainer's answers to the questions the live-watcher track left.
None of the six was decided on taste: GSAS-II's per-phase colour list and the
house figure style chose the palette, CI dashboards the state pills, VS Code
the collapse command, log viewers the cold open, and the cadence answer is
WP-1413's own measurement read against what a ratio means on a 0.354 s fit.
