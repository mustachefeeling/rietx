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
characters in all. The run panel keeps 340 px, below which the plot's legend
wraps to six rows and covers the top quarter of the picture.

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

The page holds still while the fit moves. The plot redraws in place as the fit
writes each stage. Its 2θ and intensity axes are set by the pattern, so they
change only when the data does, and a zoom survives a stage. The Δ/σ axis is
symmetric and steps between fixed rungs (±3, ±5, ±10, ±20 and so on) as the
residual tightens. The console tails the log from where it left off and follows
it only while you are at the end. For a series the status line names the
pattern being fitted, its pass and its stage.

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
has stopped moving.

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

`--read-only` serves the same pages without the button:

```console
$ rietx watch --read-only
rietx watch: 3 run(s) under /Users/yue/work/demo
             http://127.0.0.1:8899/  (Ctrl-C to stop)
             read-only: no stop button
```

The page draws no button, and the route refuses with 403.

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
plot together. This page has no theme control and writes the setting nowhere:
one writer per fact, and the GUI is it. With nothing stored the choice is
`system`, and the page follows the browser's `prefers-color-scheme`.

### The JSON underneath

Seven routes carry everything the page shows, and you can read any of them
directly:

| Route | Returns |
|---|---|
| `/api/runs` | every run under the scanned root, with its liveness |
| `/api/run/<id>` | one run's row |
| `/api/run/<id>/events?offset=&limit=` | events from a byte offset, with the next offset; `limit` keeps the newest that many and counts the rest in `skipped` |
| `/api/run/<id>/snapshot` | the stage's curves, ticks and statistics as JSON |
| `/api/run/<id>/legacy` | a `fit.html` written before 1.4, served as it stands |
| `POST /api/run/<id>/cancel` | asks that run to stop; 403 under `--read-only` |
| `/plotly.js` | plotly out of the installed package, so the page works offline |

These are provisional by declaration, like the GUI's ([](compatibility.md)). A
route may be added, renamed or split in any release.

Stopping is the watcher's only verb. Everything else reads. It never opens a
project and never builds a refinement, so you can start and stop the watcher
while a refinement runs. The stop writes a request file into a run directory the
scan already found, and the fit's own token is what acts on it. No model is
edited from here and no project is touched.

The contrast worth knowing is `Project.open`, which writes an annotation into a
project before you have clicked anything. Looking at a project without changing
it is `rietx gui --scratch`. Looking at a run needs nothing.

## `rietx html`: a saved result as a page

```console
$ rietx html result.json fit.html
wrote fit.html
```

Takes a serialized `RefinementResult` and writes a standalone HTML page. Two
arguments exactly, and anything else exits 2. Because a `RefinementResult`
round-trips through JSON, this is the reporting path for a fit that ran
somewhere else: on a cluster, in CI, or in a notebook you have since closed.

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

The GUI needs the `gui` extra ([](install.md)), which is plotly only: the built
front end is committed inside the package, so installing it never needs node.

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
