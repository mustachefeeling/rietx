# WP-1403 — a run nobody asked to record

Milestone: unscheduled · Status: ✅ 2026-09-15 — every fit records itself;
not user-shippable until WP-1406 writes the prose
Depends on: 1401 (the reader, and the baseline measurement that gates this);
1402 (the snapshot this writes)

## Goal

A plain `ref.fit(data)` records itself — events, status, a per-stage picture and
the termination view — into a run directory the watcher finds, with no `events=`
from the caller. An env variable switches it off, the suite has it off, and a
failure to record never breaks a fit.

## Context

### Why automatic, rather than documented

WP-1322 measured it. Three independent subagents, each given a benchmarking task
and no instructions about how to drive rietx, all found and read the packaged
skill in full by three different routes — and **all three wrote
`history=False`**, five occurrences, on both `Refinement` and
`SequentialRefinement`. No event log existed afterwards; reconstructing timing
from the agents' own transcripts recovered **2.7–16.6 %** coverage and nothing
from inside a solve. One instrumented fit emitted 288 records and was strictly
better than anything external instrumentation can recover.

Documenting the knob harder is the obvious fix and it is the one that was already
tried. An agent cannot switch off by accident what it never had to switch on.
This discharges **WP-1322's Task 2** (the `history` defaults asymmetry decision)
by removing its premise; say so in that WP when this lands, and leave its Task 1,
the terminal-shaped post-hoc aggregator, alone.

### The gate, discharged

**WP-1401 and WP-1402 answered it: recording every fit is affordable.** The
event stream costs 1-3 % of a fit's wall clock (1401, on `nac` / `cpd-2` /
`trigger`, three repeats over two sittings). A per-stage picture costs
180-329 kB and 9.3-14.2 ms (1402, same three fits, `[dev]` venv, macOS arm64).
The whole of `events=LiveSession(dir)` is now 1.03-1.28x a bare fit, against
1.01-1.03x for `events=<path>`, so what a *recorder* adds over a bare stream is
the snapshot and nothing else. Every configuration returned a bit-identical
Rwp: telemetry does not change the answer.

The costs below were verified in the tree 2026-09-13 and the symbols
re-verified 2026-09-15, after 1402 landed. Every one survives; the `refine.py`
line numbers moved, and are corrected here.

| item | scope | what it is |
|---|---|---|
| `_free_values` (`least_squares.py:1153`, `:866`) | **per residual evaluation** | a second full `table.decode` (`:822`), then a list build over `free_paths`. It runs **before** the sink is consulted, so no sink-side thrift avoids it. |
| `json.dumps` + write + `flush` (`events.py:146-147`) | per evaluation | a syscall pair per residual evaluation, on the fit thread |
| `stage_end.rwp` (`refine.py:1803`) | per **stage** | one `background` pass plus one `bragg_component` pass. Negligible against a stage's hundreds of evaluations, and it is what makes a live Rwp a real number rather than a raw cost. Keep it exempt from any thinning below — it stays conditioned on a stream existing, so a fit with telemetry off still pays nothing. |
| `_abandon_on_cancel` (`refine.py:1560`) | per stage, **new** | it short-circuits on `cancel is None` and says so: "the copies are taken only when a token is present, so an ordinary fit pays nothing." Attaching a token so WP-1405's cross-process cancel works ends that guarantee — two `model_copy(deep=True)` a stage, scaling with atom count. |

Three mitigations, in the order they cost something to give up:

1. **Buffer, and flush on a cadence** (~0.2 s), immediate on every non-`eval`
   kind. `EventStream.emit` is **untouched**: a caller who passed a path asked
   for a durable log and keeps today's behaviour byte for byte. The durability
   consequence is real and belongs in the docstring — a hard kill loses the last
   fraction of a second — which is exactly why WP-1401's liveness rests on the
   lock and not on the log, and why its tail reader carries a fragment
   unparsed. One condition from 1401: `tail_events` stalls on a single line
   longer than its 4 MiB `max_bytes`
   (`cut == -1` holds the offset and every later call re-reads the same block),
   a limit 1401 found and deliberately left because skipping forward emits a
   torn line. Buffering batches *writes*, not lines, so the bound is untouched
   — but measure the largest line before relying on that.
2. **Let the sink answer whether it wants the values.** If the measurement says
   the decode dominates the writes, the fix is one rank down: `least_squares.py`'s
   `if events is not None` becomes a question the sink can answer, one `getattr`
   an evaluation, so a thinned log is cheap in CPU and not only in bytes.
   Contingent, with WP-1404's numbers as its trigger.
3. **Thin the eval stream** — keep every accepted step and the ends of each
   stage, drop some of the rest, and **record the drop count**, because a silent
   cap reads as coverage. This is a **semantic** change: `read_events` on such a
   log no longer reconstructs the WP-1113 trajectory that `values` exists for.
   Ship 1 first; adopt this only if WP-1404 demands it, and record the decision
   either way.

### What 1401 and 1402 already built

Both dependencies have landed, so most of the seams this WP needs are in the
tree waiting for a writer.

**The file contract exists, unwritten.** `runs.py` declares `META_FILE`
(`meta.json`), `LOCK_FILE` (`run.lock`), `RunMeta` and `RunStatus`, and names
this WP as the writer of every field none of today's code produces. Write to
those names or the reader stops seeing the runs. Three of them are load-bearing
for the reader rather than decorative: hold `run.lock` flock'd for the
process's life, since a free lock under a `running` status is what makes
`abandoned` a distinct answer; write `host`, or the foreign-host rung cannot
fire; write `state`, because `RunStatus.state` has no substantive default and
`liveness_of` answers `unknown` rather than `running` when it is absent
(WP-1076).

**The reader tolerates a newer writer.** `RunMeta` and `RunStatus` allow extra
keys rather than forbidding them, for the reason `EventRecord.data` is an open
dict, so a field this WP adds is additive and needs no reader change.
`RunStatus.state` is typed `str` with `runs.RUN_STATES` naming the vocabulary,
so a state invented here is read rather than costing the whole file its
validation. A run directory with neither sidecar resolves as *legacy*, its
`created` synthesized from the log's mtime, and every run directory in the tree
today is one — this WP adds a writer without orphaning anything.

**The sink list is declared.** `refine._snapshot_sinks(stream, events)`
(`refine.py:319`) is built once in `fit` and once in `run_stage` and handed
down, deduped by identity. A recorder that is a *different* object from the
caller's stream — which is what chaining onto `EventStream.callback` makes it —
is a third candidate passed to that call, not a fourth `hasattr` test at a call
site; the old code would have found nothing at all in that case, and
`test_the_sink_set_is_declared_and_deduped` is the pin. `run_stage` writes a
snapshot too, before `_record`, which it did not before 1402 — so
one-stage-at-a-time driving already has a picture where it had only events.
And `status.json` is written from the snapshot payload rather than recomputed,
so the `state` / `pid` / `host` / `heartbeat` fields this WP adds join a dict
that already agrees with the plot.

**Copy the table if you hold a stage.** One `ParameterTable` is reused and
re-freed down a plan, so a deferred `build_snapshot` on an early stage decodes
against the wrong width and raises. A sink that writes inside the call never
meets this.

### Composition: three cases, and an identity that must survive

`refine.py:1882` — `stream = _attach_progress(as_event_stream(events), progress)`
— and `fit` closes it only `if stream is not events`. That identity test is why
`sequential._SeriesStream` is a *subclass*. Nothing here may disturb it.

| caller passed | the fit uses | who closes what |
|---|---|---|
| nothing | the recorder | the existing rule closes it, and the recorder's own `finally` closes it again, idempotently |
| a path or a callable | the normalised `EventStream`, recorder chained onto `.callback` exactly as `_attach_progress` chains `progress_writer` | the existing rule closes the stream; the recorder's `finally` closes the recorder |
| an `EventStream` (the GUI, a series) | the caller's stream, **identity preserved**, recorder chained on | the caller closes theirs, unchanged; the recorder's `finally` closes the recorder |

The recorder's lifetime is a **new** `try/finally` beside the existing rule,
never inside it.

### Where the directory comes from

`Refinement` has **no back-reference to a `Project`** (verified: no `self.project`
in `refine.py`), and `Project.fit` (`project.py:359`) is a pure `setdefault`
forwarder. So, first hit wins:

1. an explicit `telemetry=<path>`;
2. `Project.fit` / `Project.run_stage` adding
   `kw.setdefault("telemetry", self.live_dir)` beside the `mode` / `plan` /
   `two_theta_limits` setdefaults they already carry — the only place that knows
   the project path, and it stays that way;
3. a **derived** fallback for a bare `ref.fit()` on a project-built
   `Refinement`: `self.history.path.parent` holding a `project.json`. One
   `exists()` a run, nothing stored on the `Refinement`, and (2) never depends
   on it. **Both attributes are `Optional`** — `self.history` is `None` until
   `_ensure_history` runs (`refine.py:452`) and `RefinementTree.path` is `None`
   for an in-memory tree (`history/tree.py:46`), which is what `history=False`
   and every synthetic fixture produce — so this step is two `is not None`
   tests before the `exists()`, and it falls through to (4) rather than
   raising;
4. the working directory.

One new public keyword on `Refinement.fit`, `Refinement.run_stage`, `refine()`
and `refine_sequential()`: `telemetry: str | Path | Literal[False] | None`. The
env switch outranks it; there is deliberately **no `True`** that overrides the
env, because someone who set it wants it off everywhere.

### Attach exactly once

A 60-pattern series runs N fits through one `_SeriesStream`; attaching per
pattern would make 60 directories for one job. So the recorder stamps the stream
and declines when one is already in the chain; the series runner attaches at its
own level. One test each way.

The GUI is the same hazard from the other side. `GuiSession.run` opens
`EventStream(path=p.live_dir / "events.jsonl", callback=self._push)`, so a
chained recorder writes the whole eval stream **twice** — precisely the weight
this WP exists to control. The fix: the GUI passes a callback-only stream and the
recorder owns the file. It only ever needed `_push`; the file existed for
`rietx watch`, which the recorder now serves better. That changes the contents of
`<project>/live/`, which `docs/manual/using/files.md` documents twice — the
mermaid tree at line 18 (its `live/` node at 22) and the annotated listing at
line 417 (its `live/` row at 421).
`project.json`'s schema does not move and `live/`'s *contents* were never part of
the format's promise, so the reading here is **no `PROJECT_FORMAT_VERSION`
bump** — but make that call deliberately when it lands, and record it.

### The failure boundary, which looks like a contradiction

`history/events.py:130-133` says a callback's exception **propagates**: "a
monitoring hook that crashes the refinement is a bug you want to see, not
swallow." This WP says a telemetry failure must **never** break a fit. Both are
right, and the boundary is **who asked**. A callback reached through `events=` is
the caller's code, and its exception is theirs to see. The recorder is code the
package attached unasked, and a fit that dies over a directory nobody requested
is the package breaking a working call for its own convenience.

So, precisely: `EventStream.emit`'s contract is unchanged; the caller's callback
is chained **outside** the recorder's try block, so the recorder can neither
swallow nor delay a caller's exception; and every recorder method runs inside one
`except BaseException` that sets a **one-shot latch**, after which `emit` is a
single attribute test. The latch is **not silent** — WP-1076's rule — it records
its reason in the status file and warns once per process. Write both halves of
this into the module docstring, or it reads as an inconsistency and someone
"fixes" it.

The same boundary answers the question WP-1402's review left open here.
`for sink in sinks: sink.write_snapshot(...)` runs unguarded in `refine.py`, so
a full disk discards a converged result. That is right for a sink the *caller*
passed and wrong for the recorder, and the two need no separate code path: the
latch covers every recorder method, `write_snapshot` included, so the recorder
absorbs its own failure and the loop stays exactly as 1402 wrote it. A caller's
live view keeps failing loudly.

### Retention: by age and size, never by count

"Keep the newest N, prune at start" is the obvious design and it is wrong: run 21
of a 200-candidate batch would delete run 1 **while the batch is still running**,
and a batch is one of the cases this feature exists for
(`docs/skill/rietx/references/batch.md`). So: only terminal runs, only older than
a generous floor, and only to bring the root under a byte ceiling, oldest first.
Everything inside the floor is kept however many there are. A root over the
ceiling with nothing old enough to drop **warns and keeps** — using someone's
disk is better than deleting their evidence.

Three guards before any `rmtree`, because a recursive delete is the one thing in
this track that can destroy data: the directory name matches the run-id pattern,
it holds a `meta.json` with the right record tag, and it is a direct child of the
root the recorder itself chose. Legacy directories — no `meta.json` — are never
pruned; nobody agreed to their deletion.

### `summary.txt` is not a projection of the stream

The recorder is an `EventStream`: `fit_end` hands it a **data dict**, and the
termination view needs the `RefinementResult` object. So this is a **second,
explicit call site** in `fit` after the result is built, not something that falls
out of the stream. It writes `str(result)` — WP-1302's termination view, frozen
at `tests/data/nac_termination_golden.txt` — and never `ref.summary()`, which
builds a `FitReport`: the expensive half of that call, and WP-1335's whole
subject. A cancelled or failed run has no result, so it gets no `summary.txt`,
and that absence is not an error.

Everything else in the status file **is** a projection: every number copied off
the event that carried it, the way `progress_writer` "formats, it never
computes", and the way `staged.bound_findings` feeds two surfaces from one test.
Two traps in projecting it:

- **Read the stage number off `index`, never count `stage_start`s.** A stage that
  releases a held phase emits a **second** `stage_start` with the same `stage`
  and `index` (WP-1301), and `n_stages` is revisable mid-run under indexing
  (WP-1037). A counter says "stage 6 of 5" the first time a phase is released.
- The status file must **never** be reconstructed from the tail of a buffered
  log. An abandoned run's log is missing its last fraction of a second by
  construction, which is what the lock is for.

### Names

Per CLAUDE.md's "never spell the distribution name, a format token or the state
dir — import it from `_about.py`": the runs path parts spelled **from**
`STATE_DIR_NAME`, and the off-switch env var beside `COMPILED_ENV`. The docstring
carries the ambiguity out loud, because no test can catch it: `$HOME/.rietx` is
the GUI's per-user state and `RIETX_STATE_DIR` moves **that one only**; the
working directory's `.rietx/` is this, the `.git` precedent of one name
disambiguated by location, and **no env var moves it**. `runs.set_enabled`
mirrors `compiled.set_enabled`, read **once per run** and never per event.

The root writes a `.gitignore` containing `*` on creation, so a fit inside
someone's repository does not turn up in their `git status`.

### What a caller is now doing that they did not ask for

Three consequences to accept explicitly rather than discover:

- A **read-only working directory must not break a fit**. That is the latch, and
  it is tested rather than asserted in prose.
- A fit run inside someone else's package leaves `.rietx/` in **their** working
  directory. This will be reported as a bug at least once; the env switch and the
  manual sentence are the answer.
- A run directory holds **every free parameter's value at every recorded
  evaluation**. On a shared filesystem that is a disclosure nobody opted into.
  No pattern bytes are ever copied, and WP-1406's manual page says plainly what a
  run directory contains.

Also: a `.rex` project's crash-safety story is append-only writes by **one**
writer. An agent fitting while a human has the GUI open on the same project
breaks that. The run-id subdirectories keep the event logs from colliding and
`history.jsonl` was already exposed, so the hazard is pre-existing — but this WP
makes the situation ordinary rather than rare, which from the user's side is the
same thing. Name it; do not claim the watcher created it and do not claim it is
safe.

## Non-goals

- **No cancel.** No token is attached for the watcher's sake here, so
  `_abandon_on_cancel`'s short circuit still holds and this WP's cost does not
  include it. WP-1405.
- **No manual or skill prose**, including the sentence a library user will want
  about a fit writing to disk. WP-1406 carries all of it, and this WP is not
  finished-and-shippable without it — say so in the handover.
- **No `capabilities()` surface flag.** "Can this build record runs?" always
  answers yes, no optional dependency, so a flag would be a literal `True` in
  disguise, which `_features()` forbids by construction. Worth writing down
  because adding one is the reflex.
- **No seventh versioned contract** in `capabilities()` yet. Defer until the
  layout has survived a release: WP-1006's own precedent is that a contract
  nothing has exercised is an untested guess.
- **No new `EventKind`.** Nothing here is an event, and the closed set does not
  move.

## Tasks

- [x] `_about.py`: the runs path parts and the off-switch env var, with the
      two-meanings-of-`.rietx` note in the docstring. `runs.set_enabled` beside
      it, mirroring `compiled.set_enabled`.
- [x] `RunRecorder(EventStream)`: the directory, `meta.json`, the lock, the
      buffered handle with its flush cadence, the status projection (reading
      `index`, never counting), and `write_snapshot` from WP-1402. Every field's
      writer named at review.
- [x] The failure latch: one `except BaseException` a method, one-shot, the
      reason recorded in the status file, one warning a process. Both halves of
      the who-asked boundary in the module docstring.
- [x] `discover` sees the runs root. **Not in the original list, and the
      acceptance cannot hold without it**: the walk skips every dotted
      directory, so `.rietx/runs` was invisible to `rietx watch`, whose default
      root is the working directory. `STATE_DIR_NAME` is now recognised by name
      and its `runs/` collected, exactly as `*.rex` is recognised and its
      `live/` collected — and both go through one `_collect_runs`, which asks
      *at* and *inside*, so a pre-1403 `live/` that **is** a run stays visible
      beside the `live/<run id>/` a recorder writes.
- [x] `runs.attach`: the three composition cases, the attach-once stamp, and the
      new `try/finally` beside — never inside — the existing `stream is not
      events` rule.
- [x] The `telemetry=` keyword on `fit`, `run_stage`, `refine` and
      `refine_sequential`; `Project.fit` / `Project.run_stage` setdefaults; the
      derived project fallback.
- [x] The GUI passes a callback-only stream so the eval log is written once.
      Record the `PROJECT_FORMAT_VERSION` decision in the handover either way.
- [x] The `summary.txt` call site in `fit`, after the result is built.
      `str(result)`, never `ref.summary()`.
- [x] Retention by age and byte ceiling, warn-and-keep when nothing is old
      enough, the three `rmtree` guards, legacy directories exempt. Its own
      commit: this is the only code in the track that can destroy data.
- [x] `tests/conftest.py`: the env `setdefault` beside the `MPLBACKEND` line,
      **and** a meta-test that a plain `fit()` under the suite's environment
      creates no directory anywhere. Without the second half the suite grows
      hundreds of run directories the first time someone changes the default.
- [x] Tests: `tests/test_telemetry.py` — a bare fit writes the four files;
      `telemetry=False` and the env switch write nothing; a caller's `events=`
      path still gets a **complete** log while the recorder gets its own; **a
      caller's callback exception still propagates**, asserted in both
      directions; a read-only directory latches off with a warning and the fit
      still returns; `run_stage` writes a snapshot; the status's Rwp equals the
      last `stage_end.rwp` in the log. Plus the series and GUI attach-once pair.
- [x] Skill: **none here**; WP-1406 carries the track's whole skill change, and
      this WP is not shippable without it.

## Acceptance

A plain `ref.fit(data)` in an empty directory produces a run the watcher lists,
and the same fit under the env switch produces nothing at all.

```sh
.venv/bin/python -m pytest tests/test_telemetry.py tests/test_project.py tests/test_sequential.py tests/test_gui_server.py tests/test_runs.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The full suite fires once on the final tree: no fitted number changes, but
`fit`'s control flow does.

## References

- WP-1322 — the three subagents, and the 2.7–16.6 % transcript coverage. Its
  Task 2 is discharged here.
- WP-1302 — the termination view, `progress=` as an `events=` subscriber rather
  than a second channel, and `tests/data/nac_termination_golden.txt`.
- WP-1301 — the second `stage_start` a phase release emits.
- WP-1037 — a revisable `n_stages`.
- WP-1113 — what an `eval` event carries, and therefore what thinning would cost.
- WP-1076 — a declared name is a claim; why the latch is not silent.
- WP-1335 — the report costing more than the fit; why `summary.txt` is
  `str(result)`.

## Handover log

### 2026-09-15 — a fit records itself

A refinement now records itself. Any fit leaves behind an event log, a live
status, a picture of each stage and its termination view, without the caller
passing anything at all. The alternative was to document the knob harder, and
that had already been tried. Three independent agents given a benchmarking task
each read the packaged skill in full, and each switched recording off. One
environment variable turns it off for anyone who wants their disk left alone; a
run costs about 200 kB, and a fit that cannot write one carries on anyway.

*Done.* All eleven tasks, plus one the list did not have, over nine commits.
`_about.py` spells `RUNS_DIR_NAME` and `TELEMETRY_ENV`, with the ambiguity no
test can catch written into the docstring: `$HOME/.rietx` is the GUI's per-user
state and `RIETX_STATE_DIR` moves that one alone, while the working directory's
`.rietx/` is this. `runs.py` is now both halves of one file contract, and the
recorder writes to the names WP-1401 declared rather than inventing any.
`runs.attach` hangs it beside a caller's stream and never inside it, so `fit`'s
`stream is not events` close rule is byte-for-byte what it was; the recorder's
own `try/finally` is a second one. `Project.fit` and `run_stage` setdefault
their `live/`, and a bare `ref.fit()` on a project-built `Refinement` derives
the same directory from a history tree sitting beside a `project.json`. The GUI
passes a callback-only stream now, because a recorder chained onto one that also
held a path writes the whole eval stream twice.

**The twelfth task was not in the list and the acceptance could not hold without
it.** `discover` skips every dotted directory, which hid the whole of
`.rietx/runs` from a watcher whose default root is the working directory. The
state dir is recognised by name now, exactly as `*.rex` is, and one
`_collect_runs` serves both. It asks *at* and *inside*, so a pre-1403 `live/`
that is itself a run stays visible beside the `live/<run id>/` a recorder
writes.

*Measured.* `[dev]` venv (no jax, no torch), macOS arm64 (Darwin 25.5.0),
python 3.12.12, rietx 1.4.0, machine checked idle and measured alone.

A plain `fit()` of the synthetic five-stage LaB6 case, in an empty directory:
one run the watcher lists, 204 kB over six files — `snapshot.json` 171 kB,
`events.jsonl` 30.8 kB (87 events), `meta.json` 263 B, `status.json` 235 B,
`summary.txt` 1425 B, `run.lock` empty. The same fit under `RIETX_TELEMETRY=0`
and under `telemetry=False` left **nothing at all**, asserted as an empty
`rglob`. The status's Rwp matched the result's to 1e-12, and the retention scan
that runs once per process cost 0.2 ms at 10 runs, 2.2 ms at 100 and 27.6 ms at
1000 (197 MB).

Counts. Fast selection **4782 passed, 132 skipped, 2:19**. The delta is
measured rather than inferred: collection over that selection is 4912 with
`tests/test_telemetry.py` and 4884 without it, so the branch adds **exactly 28**
and changes no existing test's identity. No new skip, 132 both ways. The
passed+skipped of 4914 against 4912 collected is the two module-level
`importorskip` modules that fire on a `[dev]` venv (jax, torch), which is the
gap `tests/CLAUDE.md` documents. The **full suite ran green at 4949 passed, 141
skipped, 22:32**, on `21171de3`, one commit back. The commit after it splits one
test function into two and touches no source at all, so by the ladder's own rule
it cannot move a measured number and the full suite was not repeated for it.
These are the bare branch's figures; the merged-tree ones are below.

*Gotchas.*

- **A recorder's latch does not cover what happens before it exists.** Choosing
  a root and making a directory are `attach`'s work, and an unguarded
  `PermissionError` there took a whole fit down until the read-only test found
  it on its first run. Both sit inside a guard now. Anything else moved ahead of
  the constructor inherits the same hole.
- **A new place to put runs needs a descent rule in `discover`.** The walk
  reaches a run only at the root, one level under `.rietx/runs`, or one level
  under a project's `live/`. Nothing else is found, and nothing goes red when it
  is not.
- **`_SeriesStream` forwards `write_snapshot` by assignment, not by a method**,
  so `_snapshot_sinks`'s `hasattr` test keeps telling the truth about an inner
  stream that cannot take one. A method defined unconditionally would hand a
  plain `EventStream` a call it cannot answer.
- **`live/` holds run directories now, and `PROJECT_FORMAT_VERSION` did not
  move.** The decision, made deliberately: `project.json`'s schema is untouched
  and `live/`'s *contents* were never part of the format's promise. An old
  project still opens, and its existing `live/` log still resolves as a legacy
  run.
- **`status.json`'s `gof` and `chi2` are the snapshot's, whose `n_free` excludes
  the Pawley tail; `stage_end`'s includes it.** `rwp` does not depend on
  `n_free`, so the two always agree there, which is what the test asserts. Under
  Pawley the other two would not.
- **A recorder that cannot take the lock records anyway**, falling back to the
  pid rung of `liveness_of`. That only happens when two writers are pointed at
  one directory, which the run-id subdirectories otherwise prevent.
- **`run_stage` records one run per stage.** Five stages driven by hand are five
  directories, which is the honest shape when nothing in the package knows they
  were meant as one job.

*Not done, deliberately.* No manual chapter and no skill prose, per this WP's
non-goals — **so this is not user-shippable as it stands**, and WP-1406 is what
makes it so. A library user currently gets no sentence anywhere saying that a
fit writes to their disk. The generated `references/api.md` was regenerated
because it renders live signatures and the new keyword made it stale by
construction; that is not prose. `files.md`'s two descriptions of `live/` were
corrected for the same reason, in four words.

*Next*, in order. **WP-1406 first**, because the feature is not shippable
without it and every day it waits is a day someone can find `.rietx/` in their
working directory with nothing to read about it. Then **WP-1404**, which this
WP hands its number: a fit's remaining 1.03-1.28x is the decimation's python
bucket loop, and the buffered writer here should have moved the per-evaluation
half of it. **WP-1405** last, and note that its cancel token ends
`_abandon_on_cancel`'s short circuit, which is a cost this WP does not include.


- **2026-09-13** — created. The premise is WP-1322's measurement, not a
  preference: documenting the knob harder is the fix that was already tried. The
  design's sharp edge is the failure boundary, which contradicts `events.py`'s
  stated rule until you say who asked — write both halves down, or a later
  session will reconcile them in the wrong direction. Gated by WP-1401's
  baseline: if recording every fit is not affordable, this WP ships off by
  default and says so rather than being worked around.
