# WP-1431 — a caller names its run

Milestone: unscheduled · Status: ⬜
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
