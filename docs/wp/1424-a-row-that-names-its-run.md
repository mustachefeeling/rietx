# WP-1424 — a row that tells its run apart, and a number that fits its slot

Milestone: unscheduled · Status: 🔄 2026-09-16 — claimed by @yue-here
Depends on: 1430 (the page as files); 1423 soft

## Goal

Every row of the `rietx watch` list can be told from its neighbours, every
number on the page is drawn whole, and the two panel toggles say what they
do. Rwp reads as a percentage in the list and the strip, the drawn-point
count sits where it has room, and the start time is a clock time a reader can
match to their own log.

## Context

The maintainer read the page over the 2026-09-16 demo and reported four
things. The `runs` and `run` toggle buttons are confusing. The Rwp column
shows `0.17…`. The strip's `5859 of 7251 pts drawn` is cut off at the `7`.
Forty rows of a batch all carry the same label, so the list names nothing.
WP-1423's handover added a fifth: the `started` column is relative time, and
a person scanning forty identical labels is helped least by that.

### What is on the page today

`src/rietx/watch/static/` after WP-1430 (`_PAGE_TEMPLATE` in `watch.py`
before it). The list is a `table-layout: fixed` table with declared column
widths (`col.c-state 12ch`, `c-stage 15ch`, `c-rwp 8ch`, `c-gof 6ch`,
`c-started 8ch`, the run column takes the rest). A cell has `padding: 6px
7px`. `fillRow` writes `run.label`, the stage, `num(rwp, 4)`, `num(gof, 2)`
and `ago(created)`. The strip is a grid of ten declared slots (`#strip`); the
point count and the path share the one `minmax(0,1fr)` slot (`s-where`),
written by `drawSnapshot` as `${n_drawn} of ${n_points} pts drawn ·
${gui_command} · ${path}`.

### A hypothesis about the cuts, to be measured first

Under `table-layout: fixed` a `<col>` width is the cell's whole box, padding
included. At 12 px `ui-monospace` one `ch` is about 7.2 px, so an `8ch` column
minus 14 px of padding leaves about 6.05ch for content, and `0.1734` is six
characters. If that is right the ellipsis is a rounding error in the declared
width, and the GoF and started columns sit inside the same margin. It has not
been measured. The first task measures every cell's `scrollWidth` against its
`clientWidth` in the browser test and only then touches a width.

The strip's slot budget is 111ch of declared columns plus nine 12 px gaps. The
`1fr` slot is the only one that can shrink, so it shrinks first, and the
sentence in it is cut wherever the run panel's width lands. Two facts share
that slot and neither belongs to a status line. The drawn count is a fact
about the picture. The path is already the label's `title`.

### What can tell one run from another, without a new writer

`RunRecorder._default_label` names a run after its working directory, or its
project, and nobody passes `label=` through `runs.attach`. What the record
already carries:

- the run directory's name, `YYYYMMDD-HHMMSS-<pid>` with a counter on a
  same-second collision (`runs.new_run_dir`);
- `meta.command` (the `sys.argv` that launched it) and `meta.cwd`;
- `meta.created`, an absolute time;
- `status.series_label` and `series_index/series_n` for a series member
  (WP-1423);
- the `run_id`, twelve hex characters of a digest of the path (`run_id_for`).
  It is stable and URL-safe and means nothing to a person.

These tell runs apart. None of them says what a run fitted. That is a
caller's fact and WP-1431 gives the caller a way to write it; this WP shows
whatever the record has, and its handover says how far that gets a batch
reader.

### Rwp as a percentage

The GUI renders Rwp as a percentage everywhere it shows one: `Report.svelte`
to three decimals, `Series.svelte` to two, `Peaks.svelte` to one. The report
layers print the fraction to four decimals (`layer0.py`, `report/__init__.py`)
because they are quoted into prose. A list row is the GUI's Series table, so
it takes the GUI's form. `17.34 %` is still six characters, so the format
alone does not fix the cut; the width does. Decide the decimals from the width
budget the measurement gives, and say which in the handover.

### The toggles

The buttons are labelled `runs` and `run`, two words one letter apart for two
different panels. WP-1425 replaces them with splitters. Until then the cheap
fix is a name and a title each: `list` and `detail`, with `title` text saying
"show or hide the run list" and "show or hide the selected run". One line, and
it lands here because 1425 is several WPs away.

### What a session after this one needs, off the two WPs before it

Folded here from the `Inherited` mailbox on 2026-09-16, all of it still true.

- **The page is files** (WP-1430). `watch/static/` holds `index.html`,
  `watch.css`, `watch.mjs` (the document) and `watch-core.mjs` (everything
  touching no DOM); `rietx.watch` imports unchanged. The DOM half is `.mjs`
  because `node --check` reads a `.js` as CommonJS, where the `import` of
  `watch-core.mjs` is a syntax error. The node cases are in
  `tests/watch_core.test.mjs`, not beside the module, because hatchling ships
  everything under `src/rietx` into the wheel; they are invoked from
  `tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`,
  which names `--test-reporter=tap` because node picks its reporter by whether
  stdout is a terminal. A new file under `static/` needs a row in
  `watch.STATIC_FILES` and nothing else. `@SUFFIX@`, `@DIST@` and `@HUE@` ride
  on `/api/runs` as `payload.page.{suffix,dist,palette}`, read at boot.
- **`patchList` holds the reader's place** (WP-1426): it anchors on a row the
  reader can see and moves `#runs`'s scroll by however far that row moved. A
  row edit that changes a row's *height* goes through the same compensation
  and needs no thought; one that adds or removes rows outside `patchList`
  would bypass it.
- **`runs.run_id_for` hashes `str(path)` and does not resolve it**, though its
  docstring says "a digest of the resolved path". On macOS `tempfile` hands
  back `/var/...` while the server walks `/private/var/...`, so a test that
  pins a run by an id it computed itself silently measures the page following
  the *newest* run instead. `tmp_path` is already resolved, so the suite is
  fine; a scratchpad probe is not. Use `_pinned()` in
  `tests/test_watch_browser.py` for any row test that pins a run.
- `tests/test_watch_browser.py` is the bar: if it moves, the page moved.

## Non-goals

- A caller-supplied run label (WP-1431).
- Filtering, search or grouping of the list (WP-1423's fence stands).
- Splitters (WP-1425). The rename here is the interim.
- Column widths the reader can drag. The columns are declared (WP-1423 rule 2)
  and stay declared.

## Tasks

- [x] Browser test: for every cell and strip slot, `scrollWidth <= clientWidth`
      over a fixture whose Rwp is `0.1734`, GoF `12.34`, and started `3h ago`;
      record which cells fail today and by how many pixels, in the handover
- [x] The toggles renamed `list` and `detail`, with titles
- [x] The list: Rwp and GoF as the GUI prints them (percent, decimals chosen
      from the measurement), widths that hold the content plus the padding,
      `<th scope="col">` on the headings
- [x] The list: a column that tells runs apart. The run directory's stamp
      (`HHMMSS`, the date only when it is not today) or the series label,
      with the full stamp, command and cwd in the row's `title`; started
      becomes a `<time datetime>` clock time, relative only in the tooltip
- [x] The strip: the drawn-point count moves off the strip onto the picture
      (a plotly annotation in a corner, or a legend entry), the `1fr` slot
      carries the `gui_command` alone, and the path stays the label's tooltip
- [x] Manual: `docs/manual/using/cli.md` § `rietx watch` names the columns as
      they are now. **Superseded in part, 2026-09-16**: there is no watcher
      screenshot to re-shoot. `make_screenshots.py`'s `SHOTS` is nine GUI
      shots and the watcher is in none of them, so § `rietx watch` has never
      carried a figure. Adding one is not this WP's, the page changing again
      in 1425.
- [x] Skill: none. The page is a human's; an agent driving rietx never reads it.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py
.venv/bin/python -m ruff check src tests examples
node --test tests/watch_core.test.mjs
```

**Corrected 2026-09-16**: the third line was `node --test
src/rietx/watch/static/`, which fails with `MODULE_NOT_FOUND` — there is no
test file under `static/` and node reads the directory as a module to run.
WP-1430 put the cases in `tests/`, because hatchling ships everything under
`src/rietx` into the wheel, and its own note in this WP's `Inherited` said so.
The first line runs them anyway, through
`test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`.

The browser test asserts no cell or slot overflows its box at 1400×900 and at
1000×700, and that two runs of one batch differ in at least one visible cell.
The browser test skips without a cached chromium, CI included; the handover
names the skip and quotes the run here.

## References

- WP-1423 (the page these columns and slots came from; its handover's *Next*
  names the relative-time column), WP-1431 (the label).
- `gui/src/panels/Series.svelte` line 669, the percentage form the list adopts.

## Handover log

- **2026-09-16** — created, from the maintainer's reading of the page over the
  demo job; revised the same day: the label became 1431, the toggle rename
  came in, the cut is a hypothesis until measured.
