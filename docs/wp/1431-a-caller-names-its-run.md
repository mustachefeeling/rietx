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

### What the page already does with it (verified 2026-09-16)

The read path needs **no change**. `runs.read_run` prefers `meta.label` over
`_label_for`'s derived name, `Run.label` carries it to `/api/runs`, and
`watch-core.mjs` renders it: `runLabel(run)` is the label plus the `· legacy`
marker, and `rowName(run)` — the one place a run is named in a *list* —
returns `status.series_label` when there is one and `runLabel` otherwise.
`rowName`'s own comment already names this WP as what fills its gap. So a
caller's label is a **third source at an existing call site**, not a new one,
and the task below that says "a series ignores it" is asserting behaviour
`rowName` already has.

Two limits inherited from [1424](1424-a-row-that-names-its-run.md), both still
true:

- **1424 could not name what a run *fitted*, and said so.** What the record
  holds about which run is which is the start second in the `started` column,
  plus the label, directory, command line and cwd in the row's `title` via
  `runTitle(run)`. None of it is about the science.
- **The run column is the flexible one** — every other column is a declared
  `ch` width sized for its worst content, so the label column takes what is
  left, about 12ch at the default 72ch panel. A longer label elides with the
  `title` behind it. Widening it costs `stage`, which already elides.

Node cases live in `tests/watch_core.test.mjs` (invoked from
`tests/test_watch_app.py`), which already has cases for `rowName`, `runLabel`
and `runTitle`: extend them rather than adding a browser test for a naming
rule.

## Non-goals

- A label on a series member. `series_label` is that already.
- Renaming a run after the fact, or from the page. The record is the writer's.
- A label in the history tree or the result. It is telemetry, so it lives in
  `meta.json` and nowhere a result reproduces.

## Tasks

- [ ] `label=` on **every entry point that attaches a recorder**, threaded to
      `runs.attach`; the recorder's default unchanged when it is absent.
      Three `attach` call sites, so five verbs: `Refinement.fit`,
      `Refinement.run_stage`, `refine`, `SequentialRefinement.run` /
      `refine_sequential`, and `Project.fit` / `Project.run_stage` free
      through their `**kw`. The WP named three; `run_stage` and the series
      are the siblings, and a series label names the *job*, which is not the
      per-member fact the non-goal excludes.
- [ ] Tests: the label reaches `meta.json`; `rietx watch`'s row shows it;
      a series ignores it in favour of `series_label`
- [ ] Manual: the telemetry section of `docs/manual/using/` documents the
      keyword. **Measure the partition claim**: `tests/api_surface.py` is
      derived over names and fields, so a keyword may not enter the
      denominator at all — document it because a knob nobody is told about is
      WP-1322 again, not because a test went red.
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
