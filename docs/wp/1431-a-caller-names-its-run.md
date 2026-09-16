# WP-1431 — a caller names its run

Milestone: unscheduled · Status: ✅ 2026-09-16 — `label=` on every verb that records a run; the page needed no change
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

- [x] `label=` on **every entry point that attaches a recorder**, threaded to
      `runs.attach`; the recorder's default unchanged when it is absent.
      Three `attach` call sites, so five verbs: `Refinement.fit`,
      `Refinement.run_stage`, `refine`, `SequentialRefinement.run` /
      `refine_sequential`, and `Project.fit` / `Project.run_stage` free
      through their `**kw`. The WP named three; `run_stage` and the series
      are the siblings, and a series label names the *job*, which is not the
      per-member fact the non-goal excludes.
- [x] Tests: the label reaches `meta.json`; `rietx watch`'s row shows it;
      a series ignores it in favour of `series_label`
- [x] Manual: the telemetry section of `docs/manual/using/` documents the
      keyword. **Measure the partition claim**: `tests/api_surface.py` is
      derived over names and fields, so a keyword may not enter the
      denominator at all — document it because a knob nobody is told about is
      WP-1322 again, not because a test went red.
- [x] Skill: one row in the batch reference, `(Hypothesis: …)` until a run
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

- **2026-09-16** — **a run can be named after the thing it fitted, and the
  watcher shows that name.** Before this, every run driven from one directory
  was called after that directory, so a batch of forty candidates wrote forty
  rows under one word and a reader told them apart by start time alone. A
  caller now passes `label=` and the row carries the work. The keyword turned
  out to be the only thing missing: `runs.attach` already took one, the record
  already stored it, and the page already preferred it over the derived name,
  so nothing between the writer and the reader needed building. What the WP
  predicted would gate the work did not, and what actually resisted was a
  size cap on a generated file and the package's own former name.

  **Done.** `label=` threads to `runs.attach` from `Refinement.fit`,
  `Refinement.run_stage`, `refine` and `SequentialRefinement.fit`;
  `Project.fit`, `Project.run_stage` and `refine_sequential` forward it through
  their `**kw`. The WP named three verbs, and `run_stage` and the series are
  its siblings: three `attach` call sites is the class, so all three take one.
  A series label names the **job**, one run directory however many patterns it
  walks, which is not the per-member fact the non-goals exclude. The manual
  gains `refining.md` § Naming a run, and the skill gains `9c.32` in
  `batch-operating.md`, tagged `(Hypothesis: …)` because no campaign has yet
  run with labels on.

  **The page took no functional diff.** `read_run` already prefers
  `meta.label` over `_label_for`'s derived name, and `rowName` already renders
  it, so a caller's label reaches the list through the call site 1424 left.
  What changed in `watch-core.mjs` is comments, every line of them: `rowName`'s
  own comment said "a batch driven from one directory gives every run the same
  label", which this WP falsifies.

  **Measured, and both of this WP's own premises were wrong.**
  - The WP said `tests/test_manual_api.py`'s partition would fail until the
    manual documented the keyword. It does not. Removing the section and
    re-running gave 17 passed, unchanged. `tests/api_surface.py` is derived
    over **names and fields**, so a new *keyword* on an already-documented
    method enters no denominator and no gate sees it. The section is there
    because an undocumented knob is WP-1322 again, not because a test went
    red. **This is a real hole in a coverage gate**, and closing it is not
    this WP's: it would mean partitioning signatures, not names.
  - `references/api.md` is **generated**, one signature per public name, and
    sat at 35 942 B against `REFERENCE_MAX_BYTES` 36 000. This keyword took it
    to 36 020. The next public keyword would have done the same to whoever
    added it. Raising the shared cap would have handed `diagnostics.md` the
    room WP-1338 deliberately denied it (20 B free, PR #291 open as the split
    that buys the next diagnostic row), so the generated file has its own
    `API_INDEX_MAX_BYTES` and the authored bar is untouched.

  **Gotchas, each paid for once.**
  - **The obvious TiO₂ polymorph for naming an example candidate is the
    package's own pre-WP-1066 name**, and `test_no_stale_name.py` keeps that
    word gone. One reach for it put the old brand in the manual, the telemetry
    tests and the node cases at once; rutile is the other polymorph and does
    the same job. **Prose *about* the token is the token**, which is the second
    half of the trap: writing this gotcha up tripped the same guard in this
    file and in the v1.4 record, and the allowlist is for files whose subject
    *is* a rename, so the fix is to make the point without spelling it. The
    test and WP-1066 are where the word lives.
  - **A caller's label is the one field in `meta.json` that a caller supplies,
    so it is the one that can arrive as the wrong type**, and the silent
    failure costs the whole record: `_write_meta` writes raw JSON, a list
    lands as an array, `RunMeta` refuses the file, and a perfectly recorded
    run reads back as `· legacy` with a derived name and no tooltip. It is
    refused at the funnel instead. The hazard is one letter wide —
    `SequentialRefinement.fit` has a `labels=` for the patterns beside this
    `label=` for the job. The check sits **before** `attach`'s switch-off
    guard, so a caller's suite catches it with telemetry declined.
  - **The skill's tag regex wants a literal space after the colon.**
    `*(Hypothesis:\nthe …)*` does not match `\*\((Measured|Hypothesis): .+\)\*\Z`,
    and the failure reads as a missing tag rather than a wrapped one.

  **The review pass changed three things and declined three.**
  `/code-review high --fix` found that every doc it touched was asserting the
  limitation this WP removes. `cli.md` said "Nothing the record holds says
  what a run was fitting"; `watching.md` § 9d.2 told an agent to quote a run
  id because the label is the working directory's; `series.md` named `labels=`
  and not its one-letter neighbour. No gate catches prose that has become
  false — `test_manual_api` checks that names resolve, not that sentences are
  true. Declined, with reasons: the funnel check runs **after** a verb has
  reset its own state, so `run_stage(…, label=["a"])` raises having already
  cleared `stage_reports_` (self-healing on the next `fit`, and hoisting the
  check into five verbs to fix it costs more than it saves);
  `API_INDEX_MAX_BYTES` clears a 20 B overshoot by 2980 B, which the comment
  states deliberately and which still fires a kilobyte before the truncation
  it defends; and `Refinement.edit(label=)` already means a history
  annotation on this class, so the word now carries two meanings on one
  object, and unifying them is a rename outside this diff.

  **Numbers.** Fast selection green on the final tree at **5154 passed, 133
  skipped**, `[dev]` venv, macOS arm64, measured with nothing else mid-suite.
  7 tests added, every one a pass, and the skips are unchanged: an
  intermediate tree measured 5153 before the project-hop test landed, so the
  delta is exactly the tests added. `origin/main` had not moved under the
  branch, so these are the merged tree's counts. Wall clock 2:22 to 5:09 for
  the same selection on this machine, which is the range rather than a figure.
  `tests/test_watch_browser.py` **skipped**: this worktree's `[dev]` venv has
  no playwright, and the page diff is comments only, so the browser bar did
  not run and did not need to. **The full suite did not run**, deliberately:
  the change adds an optional keyword, a type check and prose, and moves no
  measured number, which is the condition `tests/CLAUDE.md` § Running puts on
  rung 3.

  **Next:** [1425](1425-the-panels-are-the-readers-to-size.md), the next rung
  of the watcher track, which now has a reason to widen the run column that
  1424 did not have — a caller's label is the first thing that column carries
  that is worth more than 12ch. Then 1429, 1427, 1428.

- **2026-09-16** — created in the revision of 1424–1429, split out of 1424's
  non-goals.
