# WP-1424 — a row that names its run, and a number that fits its slot

Milestone: unscheduled · Status: ⬜
Depends on: — (1423 soft: the page this edits)

## Goal

Every row of the `rietx watch` list can be told from its neighbours, and every
number on the page is drawn whole. Rwp reads as a percentage in the list and
the strip, the drawn-point count sits where it has room, and the start time is
a clock time a reader can match to their own log.

## Context

The maintainer read the page over the 2026-09-16 demo and reported three
things. The Rwp column shows `0.17…`. The strip's `5859 of 7251 pts drawn`
is cut off at the `7`. Forty rows of a batch all carry the same label, so the
list names nothing. WP-1423's handover already named the fourth: the
`started` column is relative time. A person scanning forty identical labels
is helped least by that.

### What is on the page today

`src/rietx/watch.py`, `_PAGE_TEMPLATE`. The list is a `table-layout: fixed`
table with declared column widths (`col.c-state 12ch`, `c-stage 15ch`,
`c-rwp 8ch`, `c-gof 6ch`, `c-started 8ch`, the run column takes the rest). A
cell has `padding: 6px 7px`. `fillRow` writes `run.label`, the stage, `num(rwp,
4)`, `num(gof, 2)` and `ago(created)`. The strip is a grid of ten declared
slots (`#strip`); the point count and the path share the one `minmax(0,1fr)`
slot (`s-where`), written by `drawSnapshot` as
`${n_drawn} of ${n_points} pts drawn · ${gui_command} · ${path}`.

### The mechanism, read off the CSS and not yet measured

Under `table-layout: fixed` a `<col>` width is the cell's whole box, padding
included. At 12 px `ui-monospace` one `ch` is about 7.2 px, so an `8ch` column
minus 14 px of padding leaves about 6.05ch for content. `0.1734` is six
characters. The ellipsis is a rounding error in the declared width. The GoF
column (`6ch`, content `1.23`) and the started column (`8ch`, content
`12m ago`) sit inside the same margin. Measure each cell's `scrollWidth`
against its `clientWidth` in the browser test before touching a width.

The strip's slot budget is 111ch of declared columns plus nine 12 px gaps. The
`1fr` slot is the only one that can shrink, so it shrinks first, and the
sentence in it is cut wherever the run panel's width lands. Two facts share
that slot and neither belongs to a status line. The drawn count is a fact
about the picture. The path is already the label's `title`.

### What can tell one run from another, without a new writer

`RunRecorder._default_label` names a run after its working directory, or its
project. Nobody passes `label=` through `runs.attach` today (`refine.py`,
`project.py` and `sequential.py` do not), so a batch driven from one directory
writes forty rows with one label. What the record already carries:

- the run directory's name, `YYYYMMDD-HHMMSS-<pid>` (`runs.new_run_dir`);
- `meta.command`, the `sys.argv` that launched it, and `meta.cwd`;
- `meta.created`, an absolute time;
- `status.series_label` and `series_index/series_n` for a series member
  (WP-1423);
- the `run_id`, twelve hex characters of a digest of the path (`run_id_for`).
  It is stable and URL-safe and means nothing to a person.

### Rwp as a percentage

The GUI renders Rwp as a percentage everywhere it shows one: `Report.svelte`
to three decimals, `Series.svelte` to two, `Peaks.svelte` to one. The report
layers print the fraction to four decimals (`layer0.py`, `report/__init__.py`)
because they are quoted into prose. A list row is the GUI's Series table, not a
report line, so it takes the GUI's form. `17.34 %` is still six characters, so
the format alone does not fix the cut; the width does. Decide the decimals from
the width budget the measurement gives, and say which in the handover.

## Non-goals

- A caller-supplied run label through `fit()`. That is a new keyword on the
  public surface and a manual partition entry (`tests/test_manual_api.py`), and
  the record already carries enough to tell runs apart. Note in the handover
  whether the list still wants it once the columns exist.
- Filtering, search or grouping of the list (WP-1423's fence stands).
- The `runs`/`run` toggle buttons, which WP-1425 replaces.
- Column widths the reader can drag. The columns are declared (WP-1423 rule 2)
  and stay declared.

## Tasks

- [ ] Browser test: for every cell and strip slot, `scrollWidth <= clientWidth`
      over a fixture whose Rwp is `0.1734`, GoF `12.34`, and started `3h ago`;
      it fails on today's page and names the cell
- [ ] The list: Rwp and GoF as the GUI prints them (percent, decimals chosen
      from the width measurement), widths that hold the content plus the
      padding, `<th scope="col">` on the headings
- [ ] The list: a column that tells runs apart. The run directory's stamp
      (`HHMMSS` and the pid, the date only when it is not today) or the series
      label, with the full stamp, command and cwd in the row's `title`; started
      becomes a `<time datetime>` clock time, relative only in the tooltip
- [ ] The strip: the drawn-point count moves off the strip onto the picture
      (a plotly annotation in a corner, or a legend entry), the `1fr` slot
      carries the `gui_command` alone, and the path stays the label's tooltip
- [ ] Manual: `docs/manual/using/cli.md` § `rietx watch` names the columns as
      they are now; `make_screenshots.py` re-shoots the page
- [ ] Skill: none. The page is a human's; an agent driving rietx never reads it.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py
.venv/bin/python -m ruff check src tests examples
```

The browser test asserts no cell or slot overflows its box at 1400×900 and at
1000×700, and that two runs of one batch differ in at least one visible cell.

## References

- WP-1423 (the page these columns and slots came from; its handover's *Next*
  names the relative-time column).
- `gui/src/panels/Series.svelte` line 669, the percentage form the list adopts.

## Handover log

- **2026-09-16** — created, from the maintainer's reading of the page over the
  demo job, unrolled with 1425–1429.
