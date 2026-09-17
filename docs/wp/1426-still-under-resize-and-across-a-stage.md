# WP-1426 — still under resize, and across a stage

Milestone: v1.5 · Status: ✅ 2026-09-16 — the legend no longer moves the picture, the console no longer follows it, the list holds the reader's place
Depends on: 1430 (the page as files), 1423 (the rules and the browser harness this extends)

## Goal

Nothing on the `rietx watch` page flashes or shifts when a stage lands or a
run appears, and a window resize moves the legend with the plot and nothing
else. The console keeps its lines when the picture changes. A browser test
reads the page's layout-shift entries and finds none over a stage boundary
and a new run.

## Context

WP-1423 made the page hold still between polls, measured as distinct states of
each element over 25 s. The maintainer's next reading found movement it did
not measure: the legend jumps into the middle of the plot on a window resize;
changing the plot also reloads the console; and there is still jitter and
flashing to look into. This WP takes those three and the metric that covers
the class.

### The legend

`drawSnapshot` lays the legend out horizontally with `legend: {orientation:
'h', y: 1.02, yanchor: 'bottom', x: 0}` under `margin: {t: 8}`. `viz/html.py`
line 146 uses the same spec. Where the legend sits today, and where it goes
after a resize, has not been looked at; the maintainer's report is the only
observation. Two things about the spec are worth knowing before measuring. A
legend anchored above the plot area lives in the top margin, and eight pixels
is less than one legend row. A horizontal legend wraps when its entries (one
`hkl: <phase>` row per phase, widened by the `(n of m)` cap) exceed the
width, and plotly re-lays it on `Plots.resize`. The first task records the
legend group's bounding box, relative to the plot area's, before and after a
resize at 1400, 1000 and 700 px.

Whatever the measurement shows, the fix must obey WP-1423 rule 2. The legend's
box is a dimension the page fixes. Two forms satisfy it: the legend inside the
paper at a fixed anchor (`y: 1, yanchor: 'top'`), or an HTML legend the page
owns in a strip of declared height with `showlegend: false`. Prefer the first
if it measures still; it keeps the picture `viz/html.py`'s.

### The console

`drawRun` rebuilds the shell whenever `shell.kind` changes:

```js
if (shell.id !== id || shell.kind !== kind) buildShell(run, kind);
```

`buildShell` sets `$('console').textContent = ''` and resets `tail` to offset
0. A run opened before its first snapshot has kind `none`; at the first stage
boundary it becomes `json`, the shell is rebuilt, and the console is wiped and
re-tailed from the start of the log (`tail_events` serves up to 4 MB per
call). That is the one cause the code shows. It only fires on a run opened
before its first snapshot, so the first task also reproduces the maintainer's
observation on a run that already had one, and looks further if it
reproduces there. Either way the picture and the console are two things
sharing one builder, and the fix is to rebuild the picture alone and reset the
tail only when the run changes or the route says `reset`.

### Flashing

Candidates, each confirmed or cleared by the frame differ (2026-09-16; the
differ is a CDP screencast, and chromium emits a frame only when the page
repaints, so its "1.5 fps" is the page's repaint rate and not a sampling
rate — five to six frames over three seconds, and none blank):

- `plotly.react` on scattergl traces rebuilds the WebGL scene when the trace
  count changes. **Cleared as a flash, confirmed as the real defect.** The
  redraw moved 4.6 % of pixels against 3.3 % for a plain stage, and no frame
  was blank, so the scene is not being rebuilt. What the frames did show is
  the legend gaining a row for the new entry and the whole picture dropping
  under it. That is the legend defect above, reached from the other end.
- `patchList` moves rows with `insertBefore` into the server's order. A new
  run arrives at the top and shifts every row down under the reader's eye.
  **Confirmed**: 0.0134 over four rows on a scrolled list. Fixed by the
  chat-log pattern, anchored on a visible row rather than on an inserted
  height, so an arrival below the fold compensates by nothing.
- The state pill's class change and the row's `selected` toggle repaint a
  cell. **Cleared**: neither appears in any layout-shift entry.
- The legacy `iframe` reload on a pre-1402 run. Out of scope, named here so it
  is not mistaken for a defect of this page.

### The metric, and where it does not apply

Layout shift is the browser's own measure of this defect:
`new PerformanceObserver(cb).observe({type: 'layout-shift', buffered:
true})` yields one entry per shift with a score and the elements that moved.
The browser test installs the observer at load and reads the sum after a
stage boundary and after a new run. WP-1423 counted distinct states by hand;
this observer sees every shift the layout engine saw and names the element.

It does not apply to a resize. A resize moves everything by design, so a
zero over a resize is not a bar anything could pass. The resize assertion is
the legend's box relative to the plot area, constant across the three widths.
Flashing is not a layout shift either. Its probe is a screencast: frames at
20 fps around a stage boundary through playwright, counting frames that
differ from both neighbours. The screencast is a measurement and not a gate;
what it finds is fixed or recorded.

**And it does not apply to the picture, which is where the worst of this was.**
Measured 2026-09-16: a stage that freed the background took the plot area from
y=45 to y=64 and raised **zero** layout-shift entries. The plot is one div
whose insides plotly redraws, so its box never changes and the layout engine
has nothing to report. The observer is the right instrument for the page and
blind to the picture, so the picture is read off `_fullLayout._size` instead
and the tests carry both.

Two acceptance clauses narrowed against what the measurements showed, each
recorded in Acceptance below: a new run is a zero only on a **scrolled** list,
and the console's **line count** turned out to be no evidence at all.

### The page this edits

WP-1430 took the page out of its python string on 2026-09-16, so everything
below is a file. `src/rietx/watch/static/` holds `index.html`, `watch.css`,
`watch.mjs` (the document half) and `watch-core.mjs` (everything that touches
no DOM). Five facts carry into this WP's edits.

- **A new file under `static/` needs a row in `watch.STATIC_FILES`** and
  nothing else. The route, the content type and the `.gitignore` guard all
  read that dict. A DOM half is `.mjs`, because `node --check` reads a `.js`
  as CommonJS and the `import` of `watch-core.mjs` is a syntax error there.
- **Node cases live in `tests/watch_core.test.mjs`**, since hatchling ships
  everything under `src/rietx`. `tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`
  invokes them (15 inherited from 1430; 20 after this WP).
- **The page's three build constants ride on `/api/runs`** as
  `payload.page.{suffix,dist,palette}`, read at boot into module-level `HUE`
  and `DIST`. A file cannot carry the `@TOKEN@` substitutions they were.
- **`drawSnapshot` opens with `if (!HUE) return false;`.** A poll can reach
  the draw before the first `/api/runs` has landed the palette. Keep the
  guard in whatever `drawSnapshot` becomes.
- **`tests/test_watch_browser.py` took no diff across 1430 and stays the
  bar.** If it moves, the page moved.

### The Δ/σ ladder's spike guard, handed over as a call

`rangesOf` takes the residual's `floor(0.999 · n)`th value. That index *is*
`n - 1` for every n ≤ 1000, so the "99.9th percentile" is the maximum on a
short pattern and one spiked point sets the ladder's scale for the whole run.
Above 1000 it bites as intended: a snapshot decimates to
`viz/snapshot.MAX_POINTS` = 4000, where a lone 900σ point is cut and a
ten-point misfitted peak is not. WP-1430 pinned both directions in
`tests/watch_core.test.mjs` as the behaviour rather than the intention,
because its fence was that nothing the page does changes. The axis is this
WP's subject, so the call belongs here.

## Non-goals

- The plot's marks and colours (WP-1423's fence; WP-1429 owns the palette).
- Resizable panels (WP-1425), which depend on this WP's legend fix.
- Poll cost and payload size (WP-1427). A shift that is a slow redraw is
  1427's; a shift that is a wrong layout is this WP's. Both rewrite
  `drawRun`; whichever lands second rebases.
- The GUI's own plot, whose legend rules are `lib/plot.ts`'s.

## Tasks

- [x] Browser test with a layout-shift observer and a frame differ; measure
      today's page over a stage boundary and a new run, record the legend's
      box relative to the plot at three widths, and reproduce the console
      reload on a run that already had a snapshot; the numbers go in the
      handover
- [x] The legend holds still under resize, as a dimension the page fixes;
      `viz/html.py`'s legend spec follows if its page shows the same defect
- [x] The picture is rebuilt alone; the console and its tail survive a change
      of picture kind, and reset only on a run change or a `reset` from the
      route
- [x] The list holds the viewport when a run arrives above the fold
- [x] Whatever the frame differ found at a stage boundary, fixed or recorded
      as measured and left, with the reason
- [x] The test asserts layout shift 0 over a stage boundary and a new run,
      the legend's box constant relative to the plot across the three
      widths, and the console's line count unchanged across a picture kind
      change
- [x] The spike guard's short-pattern case: fixed, or recorded as measured
      and left, with the reason (inherited from 1430)
- [x] Skill: none. The page is a human's.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py
.venv/bin/python -m ruff check src tests examples
```

The browser test, where it runs, reports a layout-shift sum of 0 over a stage
boundary and over a run arriving on a **scrolled** list, the legend's box
constant relative to the plot area from 1400 to 700 px, and the console
neither wiped nor re-tailed across a picture kind change. It skips without a
cached chromium, CI included; the handover names the skip.

Two of those are not what this WP was written asking for, and both moved
because the measurement said so rather than because they were hard.

**A new run is a zero on a scrolled list, and intended movement on one at its
top.** Prepending a row moves every row below it, and the only way to hold
those still is to scroll down by a row, which puts the arriving run out of
sight. A reader at the top of the list is watching for exactly that run. So
the list is held where a reader is reading and left alone where they are
watching, which is the chat-log rule this WP already cited; the at-the-top
case is asserted as "the scroll stayed at 0 and the new run is on screen".

**The console's line count is no evidence.** The wipe re-tailed from offset 0
and put all 121 lines back, so the count was 121 before and after, both before
this WP and after it. What separates a wipe from a tail is that nodes were
removed, that the node which was first no longer is, and that a reader scrolled
up was dropped at the bottom. Those three are asserted instead.

## References

- web.dev, Cumulative Layout Shift (the `layout-shift` performance entry).
- WP-1423 (the two rules and the harness), WP-1402 and WP-1405 (the two page
  defects no python test could see).

## Handover log

### 2026-09-16 — the legend was three of the four movements

The page holds still now. Four things had been reported as moving, and three of
them turned out to be one mechanism. The legend was anchored above the plot
area, where plotly grows the top margin to fit it, so every row the legend
gained was taken out of the picture. It gained a row when the window narrowed
and its entries wrapped. It gained another whenever a stage first freed the
background, since that adds a trace and a trace adds an entry. The reported
flashing was that second case seen at speed. Moving the legend inside the paper
settles all three at once, and the picture came out 38 px taller at a 1400 px
window and 131 px taller at 700 px. The fourth movement was the run list, which
kept its scroll offset while its rows slid underneath it.

The instrument this WP was written around turned out to be half blind, and that
is the part worth carrying off. A browser raises a layout-shift entry when an
element's box moves. A plotly plot is one div whose insides are redrawn, so the
stage boundary that moved the picture 19 px raised no entry at all. Every claim
about the picture is now read off plotly's own layout, and the observer is kept
for claims about the page.

**Done.**

- The legend takes a fixed anchor inside the paper, `y: 1, yanchor: 'top'`,
  which is the form this WP preferred and it measured still. `viz/html.py`
  carried the same spec and showed the same defect, so it took the same fix.
- `buildShell` splits into `buildPicture` and `resetTail`. `drawRun` resets the
  tail on a *run* change and rebuilds the picture on a run-or-kind change.
  `clearStrip` resets the tail alongside the console it was filling, or a reader
  returning to that run would meet an empty console that no poll refilled.
- `patchList` anchors on a row the reader can see and moves `#runs`'s scroll by
  however far that row moved. An arrival below the fold therefore compensates by
  nothing, and a list already at its top is left alone.
- `rangesOf` cuts its outliers by a count rather than by a fraction. This is
  WP-1430's handed-over call, taken rather than re-pinned.
- `withAlpha` joins `watch-core.mjs`, a legend over data needing an opacity and
  the colour staying the palette's.
- Six browser tests and five net node cases. `_pinned()` asserts the URL still
  names the run it opened, because a run id that does not match the server's
  turns a pinned-run test into a follows-the-newest test in silence.

**Measured** — this worktree's `.venv`, `[dev]` plus playwright 1.63.0,
darwin/arm64, cached chromium-1223. Plot area is `[l, t, w, h]` and the legend
box is relative to that area's corner.

- **Legend under resize**, at 1400 / 1000 / 700 px viewport. Before: area top
  46 / 65 / 139 and height 465 / 446 / 372, legend at `[0,-38]`, `[0,-57]`,
  `[-4,-131]`. After: top 8 at every width, height 503 at every width, legend at
  `[0,0]`, `[0,0]`, `[-4,0]`. The `-4` is plotly keeping a legend wider than the
  panel inside the paper, and the panel is WP-1425's.
- **`viz/html.py` under resize**, at 1400 / 1000 / 700 / 500 px: area top
  60 / 60 / 75 / 75 before. Same defect, same cause, same fix.
- **A stage that frees the background**, at 1200 px: area top 45 → 64 before and
  unchanged after. Layout shift **0 in both cases**, which is the blindness
  above and the reason the tests read `_fullLayout._size`.
- **A plain stage boundary**: layout shift 0 before and after. WP-1423 had
  already done this one, so the test is a regression pin.
- **A run arriving, list scrolled to 250**: 0.0134 across four rows before, 0
  after, the scroll taking the difference at 250 → 277 (one 27 px row).
- **A run arriving, list at its top**: 0.0065 before and after. Left alone on
  purpose, a reader at the top being there to watch for that run.
- **The console at a picture-kind change**: 121 nodes removed and 121 re-added
  before, the first node replaced, a scrolled reader thrown from 200 to 1312.
  After: nothing removed, nothing added, same first node, scroll held at 200.
  The **line count read 121 on both sides of the wipe**, which is why the
  acceptance's line-count clause was replaced rather than met.
- **The frame differ** is a CDP screencast, and chromium emits a frame only when
  the page repaints, so its 1.5 fps is the repaint rate rather than a sampling
  rate. Five to six frames over ~3.5 s, none blank. The trace-count redraw moved
  4.6 % of pixels against 3.3 % for a plain stage, which clears "scattergl
  rebuilds the scene" and leaves the legend wrap as what the eye was seeing.

**Counts.** +6 tests, all in `tests/test_watch_browser.py`: that file and
`test_watch_app.py` together went 51 → 57 passed, +6 exactly and no new skip.
Node cases 15 → 20, one removed and six added, invoked by the one python test
that already existed. Fast suite 5156 passed, 132 skipped, measured twice and alone on the
machine, at 2:38 and 5:44. **The full suite did not run and is not owed**: the diff is a
JavaScript page, a plotly layout dict and tests, and neither consumer of
`figure_from_arrays` is slow-marked, so no measured number can move.

**The CI skip, named.** playwright is deliberately not a dependency, so on CI
the module-level `importorskip` fires and `tests/test_watch_browser.py` counts
as **one skipped test** rather than ten passes. Every browser assertion this WP
added is local-only, and the rest of the file was already in that position.

**Gotchas.**

- `runs.run_id_for` hashes `str(path)` without resolving it, while its docstring
  says "a digest of the resolved path". On macOS `tempfile` returns `/var/...`
  and the server walks `/private/var/...`, so a probe that computes its own id
  pins nothing and silently measures the newest run. `tmp_path` is resolved
  already, so the suite never saw it. Left alone rather than widening the diff,
  and pushed to 1424 with `_pinned()` as the guard.
- The legend inside the paper wraps *over* the data at narrow widths. At an
  800 px window the run panel is ~280 px, the legend takes five rows and covers
  the top quarter of the intensity panel. `withAlpha(HUE.ground, 0.72)` keeps
  the curve faintly visible through it. That is a mitigation, and the fix is a
  panel wide enough for the picture, which is 1425. Pushed there with numbers.
- `viz/html.py` needed a literal `rgba(255,255,255,0.85)`, that page drawing
  under `simple_white` with no palette to quote. It is a hardcoded colour among
  tokens. Pushed to 1429, whose subject it is.
- 1427 rebases. Both WPs were declared to rewrite `drawRun` and this one landed
  first; the three shapes that moved are in its `### Inherited`.

**The review pass.** `/code-review high --fix` found **no correctness bug** in
the product code and three names left pointing at things this WP removed: a
comment crediting `buildShell` for the plot div, a docstring still calling the
Δ/σ rule "the 99.9th-percentile cut", and a node-case count of mine that said 19
after the commit taking it to 20. It applied all three. Two more of that class
sat in `tests/watch_core.test.mjs`, which the pass did not reach, and they are
fixed in the same commit. It declined two findings with reasons worth keeping.
It tried to strengthen the scroll test's `moved_to > 250`, then doubled the
compensation in `patchList` on purpose and found the layout-shift assertion two
lines above already failed at 0.0067, so the existing pair pins it and the extra
assertion was reverted. And it left `viz/html.py`'s literal rgba alone, the light
palette carrying no ground key, which is the change this WP already pushed to
1429. It also confirmed by measurement that the scroll compensation is exact and
that chromium's own scroll anchoring is not firing alongside it, so there is no
double compensation to guard against.

**Next.** 1424 is next in the track's order, and nothing here blocks it. 1425's
blocker is discharged by this WP and its trade is written into its mailbox, so
it could be pulled forward if the narrow-panel legend is annoying in use.

- **2026-09-16** — created, from the maintainer's reading of the page over the
  demo job; revised the same day: the resize case no longer claims a zero
  layout shift, and the console cause is stated as the one the code shows.
