# The command line

`rietx` is a small command with six subcommands. The package is API-first, so
the terminal gets only the jobs that are genuinely terminal-shaped: asking what
the cell of a pattern is, watching a running refinement, rendering a saved
result, launching the two browser tools, and putting the agent skill where a
harness will find it.

```console
$ rietx --help
usage: rietx <command> [...]

commands:
  gui [PROJECT.rex] [--scratch] [--port N] [--no-open]
                                    the refinement GUI (localhost)
  watch [dir] [--port N] [--open] [--read-only]
                                    list and watch the runs under a directory
  html <result.json> <out.html>     render a saved RefinementResult to HTML
  index <pattern> --wavelength A [...]
                                    determine the unit cell of an unknown
                                    phase (rietx index --help)
  compare [--data DIR] [--port N] [--open]
                                    browser UI comparing refinement
                                    settings on the bundled standards
  skill [--path | --print [SECTION] | --install [DIR]]
                                    the agent skill: where it is, its
                                    text, or install it into a repo
                                    (rietx skill --help)
```

An unknown command exits 2. Nothing here refines a structure. A refinement is a
sequence of decisions about a model, and a command line is the wrong shape for
it. Use the API ([](quickstart.md)) or the GUI.

:::{admonition} For agents
:class: agent
Prefer the Python API ([](agents.md)) over shelling out. The one exception is
`rietx index`, whose exit status is a contract: 0 when a cell reached the
confidence gate, 1 when the result abstains. That is the same statement the
diagnostics make, in the one channel a shell pipeline can branch on without
parsing.
:::

## `rietx index`: what is this cell?

The only subcommand that computes an answer rather than displaying one. It
belongs in a terminal because "what is this?" is a question you ask about a file
you have just collected.

```console
$ rietx index corundum.prn --wavelength 1.540596 --systems trigonal --total-budget 45
```

It prints the candidate list and never one cell. `IndexingResult` has no
`.cell`, and the CLI does not invent one. The list, each candidate's confidence
grade, and the caveats holding that grade down are the answer.
[](indexing.md) is what each of those means. The last block is the run's
diagnostics, which is where a truncated search says so.

| Option | Is |
|---|---|
| `--wavelength` | required, in Å, and a single line. For a lab Kα doublet build the instrument in python and call `index_pattern`, because peak picking recognises each line's Kα2 alias and a one-line source cannot |
| `--geometry`, `--radius` | `debye_scherrer` (default), `bragg_brentano` (which needs a goniometer radius) or `flat_plate_transmission` |
| `--systems` | comma-separated crystal systems; the default is all seven. A restricted search reports what it did not cover rather than concluding anything about it |
| `--engines` | comma-separated engines; the default is all of them, and `high` confidence means every engine that ran agreed |
| `--min-d`, `--max-d` | the principal d-spacing bounds of the search domain. Domain size is what an exhaustive search pays for |
| `--budget` | wall-clock seconds per (engine × system) slice |
| `--total-budget` | wall-clock ceiling for the whole run, search and validation together, overriding the preset's |
| `--preset` | `quick` (the default: every engine and system under a whole-run ceiling, truncation reported) or `full` (no ceiling) |
| `--ceiling` | print the cost arithmetic for these options and exit without searching |
| `--shift-allowance` | a measured systematic 2θ allowance in degrees. Without one the engines assume a value and cap every candidate's confidence, because a cell found inside a widened window absorbs the shift |
| `--no-validate` | skip the whole-profile Le Bail validation, which caps every candidate at `medium` |
| `--json FILE` | also write the whole `IndexingResult` as JSON |

Anything the pattern reader repaired or assumed goes to stderr before the
answer, because a reversed scan or a dropped duplicate changes every number
under it.

### Ask what it will cost before you run it

`--ceiling` answers that from the options alone, and it separates the arithmetic
from the measurement, because a worst case is not an estimate:

```console
$ rietx index corundum.prn --wavelength 1.540596 --ceiling
worst case: 1518 s   (search 630 + probe 360, arithmetic on the per-system budgets;
+ validation 12 fits x 0.6-44 s, a measured range — Le Bail cost is data-dependent)
measured typical: 4-440 s per real dataset (searches finish their systems early far
more often than not)
a --total-budget binds within ~10 s (the longest uninterruptible stretch)
```

The gap between 1518 s and "4 to 440 s typical" is the point. The worst case is
what the budgets permit rather than what a real dataset costs. Narrowing `--systems`
to where the answer can live costs exponentially less than more time buys.

### Reading the exit status

```console
$ rietx index corundum.prn --wavelength 1.540596 --systems trigonal --total-budget 45
...
NO CELL: the result abstains — see the diagnostics below.
  [warning] INDEX_ABSTAINED: no cell reached the confidence gate; the best
            candidate (trigonal R, V = 127.5 Å³) is low because of:
            geometric_ambiguity, fom_panel_disagrees, not_validated,
            indexed_fraction_low, search_incomplete, shift_allowance_assumed
$ echo $?
1
```

That run is an honest failure. The certified corundum cell is candidate 1 at
4.75950 Å, and the command still exits 1, because six caveats stand between it
and the gate. Exit 0 is the narrow claim "one candidate reached `high` with no
ambiguity partner", and not "something was printed".

## `rietx watch`: a running refinement, live

```console
$ rietx watch --port 8899 --open
```

With no directory it scans the working directory and lists every run beneath it,
running and finished together. The list is one panel and the selected run is
the other. The run panel carries a status line, the plot and the event console.
With no run in the URL the page follows the newest run, so opening it beside an
agent's job shows what is happening now. Clicking a run pins it.

Two seams divide the page and both are yours to move. One runs between the list
and the run, the other between the plot and the console. Drag a seam to size
the panel beside it. Double-click it, or focus it and press Enter, to collapse
that panel, and repeat the gesture to bring it back. A focused seam also takes
the arrow keys, 16 px a press and ten times that with Shift, with Home and End
for its two stops. The browser remembers both sizes and re-fits them to the
window you next open in, so a width chosen on a wide screen does not leave a
sliver on a narrow one.

A seam stops where the panel stops being readable. The list stops at the width
its five declared columns need plus room for the run column's own heading, 63
characters in all. The run panel keeps 340 px. At that width the plot's legend
already takes three rows over the top of the picture.

`full list`, beside the title, hides the run panel altogether and gives the
list the window. It is a button rather than a third seam because no seam sizes
that panel, and dragging the list to its stop is a different thing: that leaves
the run panel at the 340 px above. The choice persists like the two sizes do.

The list has six columns. `state` is the liveness word below. `run` is what the
run is called: for a series member the pattern it fitted, otherwise the label.
The label is the word the caller passed as `label=`, and failing that the
project's name or the directory the fit was launched from. `stage`
is the stage its writer last recorded, and `Rwp` and `GoF` the fit at that
point, Rwp as a percentage. `started` is a clock time, to the second for a run
started today and a date before that. Hovering a row gives the rest of the
record: the label, the run directory, the command line that launched it, and
where that was run.

An unnamed batch launched from one directory gives every run the same label, so
the second it started is what tells its rows apart. That is a fact about the
record rather than about the fit. Pass `label=` to the verb that starts the fit
and the row carries the work instead ([](refining.md)).

Opening a run puts you at the newest line of its log, not at its first. A job
that has been running for a while has a log of some megabytes, and the console
reads the end of it and says that earlier lines are above; it does not say how
many, having not read them. From there it follows the log as it always did.

The page holds still while the fit moves. The plot redraws in place as the fit
writes each stage. Its 2θ and intensity axes are set by the pattern, so they
change only when the data does, and a zoom survives a stage. The Δ/σ axis is
symmetric and steps between fixed rungs (±3, ±5, ±10, ±20 and so on) as the
residual tightens. The console tails the log from where it left off and follows
it only while you are at the end. For a series the status line names the
pattern being fitted, its pass and its stage.

The plot is the GUI's pattern chart, and it takes the GUI's gestures. Drag to
zoom, or scroll to zoom about the pointer. Shift-scroll or Alt-drag pans, and a
double-click shows the whole pattern again. Clicking an entry in the legend
hides that curve until you click it again, and a stage landing leaves it
hidden. The shaded band on the Δ/σ panel runs from −3 to +3. The `export`
menu in the bar holds the four exports of [the GUI's plot](gui-guide.md): a
PNG, an SVG, the picture on the clipboard, and the channels in view as
tab-separated columns.

The status line shows what the run panel is wide enough to hold, and it drops
slots rather than cutting each of them a little. The GUI command and the
free-parameter count go first, then the label, then the series. The state, the
Rwp and the GoF are always there, and the stage shortens rather than going.
Widening the window, dragging the seam, or collapsing the list brings the rest
back.

### Where the runs come from

Every fit writes one. `Refinement.fit` and its neighbours record a run directory
whether or not you asked, so `rietx watch` in the directory you are working in
usually has something to show. A fit that came from a project records into that
project's `live/`; every other fit records under `.rietx/runs/` in the working
directory.
[](refining.md) is what a run holds and how to switch recording off.

A run is any directory holding an `events.jsonl`, which also covers a project's
own `live/` ([](files.md)) and any directory you passed to a `LiveSession`
yourself. Pass one and the page opens straight onto that run instead of listing.

```console
$ rietx watch ./my_sample.rex/live
```

### What the liveness column means

A finished run says so. A run still being written is the interesting case, and
the watcher answers it from a lock the writing process holds for its life, which
the kernel releases however that process dies, `kill -9` included.

| Word | Means |
|---|---|
| `running` | a process holds the run's lock |
| `done`, `failed`, `cancelled` | the writer recorded its own last word |
| `abandoned` | the status says `running` and the lock is free |
| `unknown` | the question could not be answered here |

`abandoned` is a third answer and not a rounding of the other two. It is what a
killed process leaves behind, and it is the state you are looking for when a run
has stopped moving. It is drawn in the neutral the list gives `unknown` rather
than in the colour it gives `cancelled`: colour here means the run reported its
own last word, and these two are the states where nothing did.

`unknown` arises three ways: the run was written on another host, so its pid
names one of our processes and not the writer's; the lock is free and no state
was recorded, which is every run written before the recorder existed; or there
is no lock file to probe. A heartbeat age is reported beside all of this and
never decides it. A live process is evidence, and a clock is not.

### Stopping a fit

A run that reads `running` has a stop button on its page. It takes two clicks,
and there is no keyboard shortcut for it. The confirmation says what is about to
happen in the other process.

The fit stops at its next residual evaluation. Its process sees
`RefinementCancelled`, the same exception it would have seen had it passed a
`cancel=` token of its own and set that. A script that does not catch the
exception prints a traceback and exits. Latency is one poll interval plus the
evaluation in flight. Measured on a 150-stage synthetic fit, the process exited
0.12 s after the request was written.

The stages that already finished are kept, and the working state stands at the
last of them. The stage in flight is abandoned. No history node is written for
it, no parameters are committed, and the structure and instrument go back to
where that stage found them. A cancelled run gets no `summary.txt`, because
there is no result to write one from.

Only a run being written on this machine can be stopped. A finished run, a run
on another host, and a run whose writer holds no lock all refuse with 409. A
request written into any of those would lie in the directory unread.

Afterwards the run reads `cancelled`, and its `status.json` carries
`cancelled_by`. A fit that its own caller stopped records the same state with no
`cancelled_by`. That field is the only place the two are told apart. The
exception does not distinguish them, and neither does the fit.

`--read-only` serves the same pages without either button:

```console
$ rietx watch --read-only
rietx watch: 3 run(s) under /Users/yue/work/demo
             http://127.0.0.1:8899/  (Ctrl-C to stop)
             read-only: no stop button, no GUI launch
```

The page draws no button, and both routes refuse with 403. The theme control
stays, because what `--read-only` fences is the run: a page that could not be
made legible by the person reading it would be a strange thing to call
read-only.

### What the page does about its window

Light or dark is one choice for the whole of rietx, kept beside your recent
projects rather than in any project. The three buttons in the title bar are the
GUI's, and they write the same setting: follow the system, light, or dark. A
change made here reaches an open watcher on the poll it already makes, and an
open GUI when it is reloaded.

Below about 860 pixels the run list and the run stack instead of sitting side by
side, and the seam between them becomes a horizontal one. That is the width at
which the list's narrowest useful columns and the picture's own floor stop both
fitting. The seam remembers a width and a height separately, so turning the
window does not hand you a pane you never asked for. Narrower still, the list
drops the stage and the start time: the strip above the picture names the stage,
and the list is ordered by the time.

Pointing at a tick names the reflection. It gives the Miller index, `2 1 1`,
and the angle under it. A run recorded before 1.5 has positions and no Miller
indices, and its ticks keep the angle alone.

### Opening a copy in the GUI

Every run inside a `.rex` project has an `open` button in the run list. It
starts a second process, `rietx gui --scratch`, on a throwaway copy of that
project, and opens it in a new tab. The button is in the list rather than the
status strip because the strip drops its flexible slot on a narrow window.

#### The copy is frozen at the click

It holds the model, the parameters and the history as they stood at that
moment. It never gains the next stage. The watcher stays the live view. The
copy is for what the watcher has no room for: the parameter table, the report,
the 3D structure, and branching a strategy from the head the fit had reached.

#### The project the fit is writing is not touched

A project cannot be opened read-only. `Project.open` appends an annotation
before you have clicked anything, and every action after that appends more.
Opening the live project would put a second appender on a `history.jsonl` the
fit is still growing. So the button copies first and opens the copy, and the
copy's own directory is where everything you then do lands.

The copy is a temp directory and nothing removes it. That is deliberate, the
point of looking being usually to keep what you found, and the directory is the
operating system's to reap.

For a run that has a project, the status strip also carries the command the
button runs, for anyone who would rather type it:

```console
rietx gui --scratch campaign/sample.rex
```

A run recorded by a bare `fit()` has no project to copy. Its row offers no
button, its strip carries no command, and the route answers 409.

The stop route also checks `Origin` and `Referer`, the way the GUI's writing
routes do. A cross-origin POST needs no preflight, so without that check any
page open in another tab could stop a refinement, and a domain whose DNS
answers `127.0.0.1` could read the run ids first. A same-origin fetch sends no
`Origin` and a command-line client sends none either, so `curl -X POST` against
`127.0.0.1` works unchanged.

### Colours and the theme

The page draws in the GUI's colours. The chrome takes the same tokens and the
plot takes the same curve colours, so a reader with the watcher and the GUI
open at once sees one fit rather than two colour schemes. The tokens come out
of the package, on a `/tokens.css` route. The GUI imports a committed copy
generated from the same module.

The theme is whichever the GUI stored, in `ui.theme` in
`~/.rietx/settings.json` (`$RIETX_STATE_DIR` moves that directory). Switch it
in the GUI and an open watch page follows on its next poll, 1.2 s, chrome and
plot together. The three buttons in the page's title bar write the same
setting. With nothing stored the choice is
`system`, and the page follows the browser's `prefers-color-scheme`.

### The JSON underneath

These routes carry everything the page shows, and you can read any of them
directly:

| Route | Returns |
|---|---|
| `/api/runs` | every run under the scanned root, with its liveness |
| `/api/run/<id>` | one run's row |
| `/api/run/<id>/events?offset=&limit=` | events from a byte offset, with the next offset; `limit` keeps the newest that many and counts the rest in `skipped` |
| `/api/run/<id>/snapshot` | the stage's curves, ticks and statistics as JSON |
| `/api/run/<id>/legacy` | a `fit.html` written before 1.4, served as it stands |
| `POST /api/run/<id>/cancel` | asks that run to stop; 403 under `--read-only` |
| `POST /api/run/<id>/gui` | opens a copy of that run's project in the GUI; 403 under `--read-only` |
| `POST /api/theme` | stores the theme; not under `--read-only`, which fences the run |
| `/tokens.css` | the colour tokens the GUI is drawn from, so both pages agree |
| `/rxplot.mjs`, `/uPlot.iife.min.js`, `/uPlot.min.css` | the chart the plot is drawn with, out of the installed package, so the page works offline |

These are provisional by declaration, like the GUI's ([](compatibility.md)). A
route may be added, renamed or split in any release.

The watcher has three verbs and everything else reads. It never opens a project
and never builds a refinement, so you can start and stop the watcher while a
refinement runs. The stop writes a request file into a run directory the scan
already found, and the fit's own token is what acts on it. The GUI launch copies
a project and starts a second process on the copy. No model is edited from here,
and neither verb writes into the project a fit is using.

The contrast worth knowing is `Project.open`, which writes an annotation into a
project before you have clicked anything. That is why the button opens a copy.
Looking at a project without changing it is `rietx gui --scratch`. Looking at a
run needs nothing.

## `rietx html`: a saved result as a page

```console
$ rietx html result.json fit.html
wrote fit.html
```

Takes a serialized `RefinementResult` and writes a standalone HTML page. Two
arguments exactly, and anything else exits 2. Because a `RefinementResult`
round-trips through JSON, this is the reporting path for a fit that ran
somewhere else: on a cluster, in CI, or in a notebook you have since closed.

The page is the GUI's pattern plot with the fit inside it. The chart library
and the curves are in the file, so it opens from a disk with no network and no
server. The NAC example's page is 1.36 MB. It takes the GUI's gestures, a
legend entry hides its curve, and the header holds the four exports of
[the GUI's plot](gui-guide.md). Past 150 000 channels the file carries a
min/max sample, as the GUI does.

`viz.html.write_html` writes the same page from Python. Its `weighted=True`
draws Δ/σ with its ±3σ band instead of the raw difference.

## `rietx compare`: did that correction help?

```console
$ rietx compare --open
rietx compare — http://127.0.0.1:8730
  data: /path/to/checkout/tests/data
  standards available: srm660c, corundum, zincite, fluorite, brucite, nac, lab6_capillary
```

The browser front end for the comparison [](report.md) describes: pick a bundled
standard, tick the settings variants, and read the cumulative
Δχ²-against-the-reference panel rather than the Rwp.

The three panes share one 2θ axis and take the GUI's gestures. A drag zooms
every pane, scrolling zooms about the pointer, and a double-click shows the
whole pattern again. The variant list is the legend: each variant shows the
colour it is drawn in, and unticking one hides it in every pane. The line above
the panes reads each variant's value at the pointer. Over the tick band it names
the reflection instead. The Export section saves or copies the three panes as
the GUI's plot does ([](gui-guide.md)). Its `copy data` gives `y_obs`, then
each shown variant's `y_calc`, Δ/σ and Δχ² over the channels in view.

It needs the standards, which are test data rather than package data, so
`--data` points it at a checkout's `tests/data`. Started without them it says so
and lists nothing:

```console
  standards available: (none found)
  hint: pass --data <dir> pointing at a checkout's tests/data
```

`rietx.viz.compare.run` is the same computation headless, and takes the same
standard and variant keys.

### The variant colours

The chrome is the GUI's, through the same `/tokens.css` the watcher links, and
the theme is read when the page is served. This page has no poll, so switching
in the GUI reaches it on a reload.

The ten variant curves keep colours of their own. A categorical set of ten is
one the GUI has no answer to lend: its only categorical set is the history
graph's five lanes, and ten hues at one lightness cannot be told apart the way
five at 72° can.

## `rietx gui`: the refinement GUI

This section is the command. The application it starts is three chapters of its
own: [](gui-quickstart.md) for a first fit, [](gui-guide.md) for the panels, and
[](gui-power.md) for the text document, the keyboard and the routes.

```console
$ rietx gui my_sample.rex
```

Serves the GUI on `127.0.0.1:8731` and opens a browser. The project argument is
optional; without one it starts empty and you open or create a project from
inside. A project that will not open exits 2 and prints the reason, which is the
whole value of the refusal messages.

| Option | Is |
|---|---|
| `--port N` | serve somewhere else |
| `--no-open` | do not open a browser |
| `--scratch` | open a copy of the project in a temporary directory; the one you named is not written to |
| `--state-dir PATH` | keep the recent list and the theme here instead of `~/.rietx` |
| `--machine` | print one JSON boot line (url, port, project, pid, scratch_of) and nothing else, for a supervising process |
| `--backend`, `--solver` | the Jacobian backend and the least-squares driver the session runs with, the same names `capabilities()` reports |

Every GUI verb writes to the project as you click it, and opening one appends a
line to its log before you click anything. `--scratch` is how you look at a
project you do not want changed:

```console
$ rietx gui my_sample.rex --scratch
rietx gui — http://127.0.0.1:8731/
  project: /var/folders/8r/qnc8y_5j.../T/rietx-scratch-xe9arpn1/my_sample.rex
  scratch copy — my_sample.rex is not written to
  Ctrl-C to stop
```

The copy is byte-for-byte, so it opens exactly as the original does. Nothing
deletes it: the point of a scratch run is usually to look at what happened.

This is also what `rietx watch`'s `open` button runs, with `--no-open` and
`--machine` so the watcher can read the port and open the tab itself. A project
under a running fit is safe to open this way and no other way. The copy is
frozen at the moment it is taken, and the fit carries on writing the original.

The GUI needs nothing beyond a base install. Its built front end is committed
inside the package, so installing it never needs node. The `gui` extra
([](install.md)) is empty and kept for old install lines.

## `rietx skill`: the protocol, where your harness looks

The operating protocol ships as an Agent Skill, and this subcommand is how it
reaches a repository. [](skill.md) is the whole of it; the short form is
`rietx skill --path` to find it, `--print` to read it as text, and `--install`
to put it in `.agents/skills/` with a link from each harness that reads
somewhere else.

There is deliberately no `rietx[claude]` or `rietx[codex]` extra. A pip extra
can only add a dependency, and it cannot write a file into your project, which
is the whole of what installing a skill means. So the install is a verb you run
rather than a package you resolve. It stays visible, reversible and yours to
re-run when the skill changes.
