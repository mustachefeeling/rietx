# WP-1431 — a caller names its run

Milestone: unscheduled · Status: 🔄 2026-09-16 — claimed by @yue-here
Depends on: 1424 (the column that shows the name)

## Goal

A caller of `fit()`, `refine()` or `Project.fit()` can name the run it
records, the name is what the `rietx watch` list shows, and the agent skill's
batch reference tells an agent to pass one.

## Context

`RunRecorder` names a run after its working directory, or its project
(`runs.RunRecorder._default_label`). `runs.attach` takes `label=` and nobody
passes it: `refine.py`, `project.py` and `sequential.py` do not. A batch of
forty candidate fits driven from one directory writes forty rows with one
label. WP-1424 makes those rows tell apart by the run directory's stamp and
the clock time, and its handover is to say whether that is enough. This WP is
the answer when it is not: the stamp tells runs apart and names none of them.
What a batch reader wants to read is which candidate each run fitted, and only
the caller knows that.

### What the record can carry without a new field

`meta.label` exists, is optional, and has a writer (`_write_meta`). The
change is a keyword on the three entry points, threaded to `attach(label=)`.
A series already stamps `series_label` per pattern (WP-1016, WP-1423), so a
series member's row is named; a batch is the case with nothing.

### The cost

The keyword is public surface, so `tests/test_manual_api.py`'s partition
fails until `docs/manual/using/` documents it, and `help.py` gains nothing
(it is not a parameter or a stage field). The skill's batch reference
(`docs/skill/rietx/references/`, the `9c` file) gains one row: name each run
after the thing it fits. That row is the reason this WP exists at all; a
keyword nobody is told about is WP-1322's `history=False` again.

### The name

`label=` is what `attach` and `RunRecorder` already call it. A `run_label=`
on `fit` would be the same fact under a second name. Keep `label=`.

### Inherited

- **2026-09-16, from [1424](1424-a-row-that-names-its-run.md): the seam you
  want already exists, and the limit this WP removes is now measured.**
  - **`rowName(run)` in `watch-core.mjs` is the one place a run is named in a
    *list*.** It returns `status.series_label` when there is one and
    `runLabel(run)` otherwise, so a caller's label is a third source at that
    same point rather than a new call site. `runLabel` is the plain label plus
    the `· legacy` marker and is what the strip's own label slot uses; the two
    are deliberately separate, the strip having a series slot beside it.
  - **1424 could not name what a run *fitted*, and said so.** Everything the
    record holds about which run is which is now on the page: the start second
    in the `started` column (the run directory is named after it), and the
    label, directory, command line and cwd in the row's `title` via
    `runTitle(run)`. None of it is about the science. That gap is this WP.
  - **The run column is the flexible one** — every other column in the list is
    a declared `ch` width sized for its worst content, so the label column
    takes whatever is left, about 12ch at the default 72ch panel. A label
    longer than that elides with the `title` behind it. Sizing the column for
    a caller's label is not free; it comes out of `stage`, which already
    elides.
  - `tests/watch_core.test.mjs` has cases for `rowName`, `runLabel` and
    `runTitle`; extend them rather than adding a browser test for a naming
    rule.

- **2026-09-16, from [1430](1430-the-page-is-a-file.md): the page is files, and
  three of its names are not the ones 1430's plan said.** `watch.py` is the
  package `watch/`, and the page is `watch/static/`: `index.html`, `watch.css`,
  `watch.mjs` (the document) and `watch-core.mjs` (everything that touches no
  DOM). `rietx.watch` imports unchanged. What to carry:
  - **The DOM half is `.mjs`, not `.js`.** `node --check` reads a `.js` as
    CommonJS, where the `import` of `watch-core.mjs` is a syntax error. A
    browser cares about `type="module"` and the content type, never the
    extension.
  - **Node cases live in `tests/watch_core.test.mjs`**, not beside the module:
    hatchling ships everything under `src/rietx`. They are invoked from
    `tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested`
    (15 cases today), which passes `--test-reporter=tap` because node picks its
    reporter by whether stdout is a terminal.
  - **`@SUFFIX@`, `@DIST@` and `@HUE@` are gone.** A file cannot carry a token,
    so the three ride on `/api/runs` as `payload.page.{suffix,dist,palette}`,
    read at boot into the module-level `HUE` and `DIST`. That is 299 B of every
    poll, against rows of 735 B each.
  - **A new file under `static/` needs a row in `watch.STATIC_FILES`** and
    nothing else — the route, the content type and the `.gitignore` guard all
    read that dict. `*.html` in `.gitignore` swallowed `index.html` on the way
    in, the sixth committed file that one rule has taken.
  - Nothing here touches the page: what moved for this WP is only that
    `watch.py` is `watch/__init__.py`.
  - `tests/test_watch_browser.py` took no diff and stays the bar: if it
    moves, the page moved.

## Non-goals

- A label on a series member. `series_label` is that already.
- Renaming a run after the fact, or from the page. The record is the writer's.
- A label in the history tree or the result. It is telemetry, so it lives in
  `meta.json` and nowhere a result reproduces.

## Tasks

- [ ] `label=` on `Refinement.fit`, `refine` and `Project.fit`, threaded to
      `runs.attach`; the recorder's default unchanged when it is absent
- [ ] Tests: the label reaches `meta.json`; `rietx watch`'s row shows it;
      a series ignores it in favour of `series_label`
- [ ] Manual: the telemetry section of `docs/manual/using/` documents the
      keyword; the API partition is green
- [ ] Skill: one row in the batch reference, `(Hypothesis: …)` until a run
      shows the page read better; `rietx skill --install . --copy` re-syncs
      the two committed copies

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_telemetry.py tests/test_runs.py tests/test_watch_app.py tests/test_manual_api.py tests/test_skill.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1403 (the recorder and its default label), WP-1322 (what documenting a
  knob achieves without a skill row), WP-1330 (where a batch rule lives).

## Handover log

- **2026-09-16** — created in the revision of 1424–1429, split out of 1424's
  non-goals.
