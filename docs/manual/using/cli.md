# The command line

`rietx` is a small command with five subcommands. It is deliberately small: the
package is API-first, and the terminal gets only the jobs that are genuinely
terminal-shaped. Asking what the cell of a pattern is, watching a running
refinement, rendering a saved result, and launching the two browser tools.

```console
$ rietx --help
usage: rietx <command> [...]

commands:
  gui [PROJECT.rex] [--port N] [--no-open] [--machine]
                                    the refinement GUI (localhost)
  watch <dir> [--port N] [--open]   live viewer for a LiveSession directory
  html <result.json> <out.html>     render a saved RefinementResult to HTML
  index <pattern> --wavelength A [...]
                                    determine the unit cell of an unknown
                                    phase (rietx index --help)
  compare [--data DIR] [--port N] [--open]
                                    browser UI comparing refinement
                                    settings on the bundled standards
```

An unknown command exits 2. Nothing here refines a structure: a refinement is a
sequence of decisions about a model, and a command line is the wrong shape for
it. Use the API ([](quickstart.md)) or the GUI.

:::{admonition} For agents
:class: agent
Prefer the Python API ([](agents.md)) over shelling out. The one exception
is `rietx index`, whose **exit status is a contract**: 0 when a cell reached the
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

It prints the **candidate list, never one cell**. `IndexingResult` has no
`.cell`, and the CLI does not invent one: the list, each candidate's confidence
grade, and the caveats holding that grade down are the answer.
[](indexing.md) is what each of those means. The last block is the run's
diagnostics, which is where a truncated search says so.

| Option | Is |
|---|---|
| `--wavelength` | required, in Å, and a **single line**. For a lab Kα doublet build the instrument in python and call `index_pattern`, because peak picking recognises each line's Kα2 alias and a one-line source cannot |
| `--geometry`, `--radius` | `debye_scherrer` (default), `bragg_brentano` (which needs a goniometer radius) or `flat_plate_transmission` |
| `--systems` | comma-separated crystal systems; the default is all seven. A restricted search **reports what it did not cover** rather than concluding anything about it |
| `--engines` | comma-separated engines; the default is all of them, and `high` confidence *means* every engine that ran agreed |
| `--min-d`, `--max-d` | the principal d-spacing bounds of the search domain. Domain size is what an exhaustive search pays for |
| `--budget` | wall-clock seconds per (engine × system) slice |
| `--total-budget` | wall-clock ceiling for the whole run, search and validation together, overriding the preset's |
| `--preset` | `quick` (the default: every engine and system under a whole-run ceiling, truncation reported) or `full` (no ceiling) |
| `--ceiling` | print the cost arithmetic for these options and exit without searching |
| `--shift-allowance` | a **measured** systematic 2θ allowance in degrees. Without one the engines assume a value and cap every candidate's confidence, because a cell found inside a widened window absorbs the shift |
| `--no-validate` | skip the whole-profile Le Bail validation, which caps every candidate at `medium` |
| `--json FILE` | also write the whole `IndexingResult` as JSON |

Anything the pattern reader repaired or assumed goes to **stderr before the
answer**, because a reversed scan or a dropped duplicate changes every number
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

The gap between 1518 s and "4 to 440 s typical" is the point: the worst case is
what the budgets *permit*, not what a real dataset costs. Narrowing `--systems`
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

That run is an honest failure: the certified corundum cell is
candidate 1 at 4.75950 Å, and the command still exits 1, because six caveats
stand between it and the gate. Exit 0 is the narrow claim "one candidate reached
`high` with no ambiguity partner", not "something was printed".

## `rietx watch`: a running refinement, live

```console
$ rietx watch ./live-dir --port 8899 --open
```

Serves the directory a `LiveSession` writes, with a self-refreshing plot and the
event console beside it. The directory is the one passed to the session, or a
project's own `live/` ([](files.md)). It reads the log; it does not drive the
fit, so it can be started and stopped while a refinement runs.
[](refining.md) covers the event stream itself.

## `rietx html`: a saved result as a page

```console
$ rietx html result.json fit.html
wrote fit.html
```

Takes a serialized `RefinementResult` and writes a standalone HTML page. Two
arguments exactly; anything else exits 2. Because a `RefinementResult`
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
standard, tick the settings variants, and read the **cumulative Δχ² against the
reference** panel rather than the Rwp.

It needs the standards, which are test data rather than package data, so
`--data` points it at a checkout's `tests/data`. Started without them it says so
and lists nothing:

```console
  standards available: (none found)
  hint: pass --data <dir> pointing at a checkout's tests/data
```

`rietx.viz.compare.run` is the same computation headless, and takes the same
standard and variant keys.

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
