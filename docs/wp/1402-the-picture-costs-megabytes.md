# WP-1402 — the live picture costs megabytes a stage, and the fit pays it

Milestone: unscheduled · Status: ✅ 2026-09-15 — the live picture is numbers; 180-329 kB a stage against 4.51-6.03 MB, and the fit's share 1.03-1.28x against 1.04-1.49x
Depends on: 1401 (the reader that displays what this writes)

## Goal

A stage's live picture becomes a small JSON payload instead of a
multi-megabyte self-contained web page, the viewer loads plotly once and redraws
in place, and recording a live view stops needing plotly at all. That is what
makes WP-1403's automatic recording affordable, and it is worth doing even if
1403 never ships.

**Measured 2026-09-15, and the "about 100 kB" above was a guess that came in
low**: 180-329 kB across `nac`, `cpd-2` and `trigger`, against 4.51-6.03 MB for
the page, so 14-33x rather than the ~40x the guess implied. The rest of the
result is in the handover, including the part that did not land: a fit under
`LiveSession` still costs 1.03-1.28x, not 1.00x.

## Context

`src/rietx/viz/live.py:54-61` — `LiveSession.write_snapshot` calls
`fig.write_html(..., include_plotlyjs=True, full_html=True)` after **every
stage**. Three costs, and only the first is obvious:

1. **The fit waits on it.** The page is written on the fit's own thread, so each
   stage stops to serialise several megabytes, the whole of plotly inlined
   afresh each time. Measured 2026-09-13, `[dev]` venv (plotly 7.0.0), macOS
   arm64: `plotly.min.js` alone is 4.29 MB, an empty self-contained page
   4.30 MB, and a NAC-sized page (22 003 points, obs/calc/bkg/σ) **6.3 MB**.
   WP-1401 re-measured the resident file on 2026-09-14 at 6.36 MB (`nac`), 5.27
   (`cpd-2`) and 4.99 (`trigger`). A five-stage fit writes it five times, so the
   cumulative write is the resident size times the stage count. Re-measure on
   the real cases in this WP's own task rather than carrying either figure
   forward — plotly's bundle size moves with its version.
2. **The browser rebuilds the plot from scratch.** `watch.py`'s detail view
   iframes `api/run/<id>/snapshot` and reloads it whenever the row's
   `snapshot_mtime` moves, so the reader's zoom is lost every stage — precisely
   when they were looking at something.
3. **Recording needs plotly installed.** A base install cannot record a live view
   at all, because building the figure is how the view is stored.

**What that costs in wall clock**, from WP-1401's baseline: `nac` 0.34-0.35 s
with no telemetry against 0.51-0.63 s under `LiveSession`; `cpd-2` 2.30-2.39
against 2.53-2.56; `trigger` 5.77-5.84 against 6.02-6.15 (`[dev]` venv, macOS
arm64, three repeats over two sittings, run alone). An `events=<path>` stream on
its own costs 1.01-1.03×, so the per-stage picture is the whole expense. The
spread across the three cases is fit *length*, the cost being per stage, and a
ratio on a short fit is a small number wearing a large one — quote the seconds
beside it. These are the numbers to beat.

The alternative is to store the numbers and let the viewer draw them. The fit
pays a decimation and a small JSON write; the page loads plotly once from the
installed package, the way `gui/server.py:350` and `compare_app.py:103` already
do; and recording imports no plotting library.

### The break, and what it does not cost

`fit.html` stops being produced. Stated plainly because the few-users policy is
that breaks are cheap **and every one is recorded**:

- A `fit.html` already on disk still opens in a browser, and WP-1401's viewer
  still displays one where it finds one. That is pinned by a test, or the
  back-compat promise is untested prose.
- `rietx html <result.json> <out.html>` and `viz.html.write_html` are untouched,
  so the self-contained, emailable page remains a **capability**. What stops is
  producing it unasked.
- **Three tests assert `fit.html`, not one** — WP-1401 added two after this WP
  was written. `test_events_viz_history.py`'s `test_live_session_and_watch_server`
  checks the file exists (478) and fetches it over HTTP from the served
  directory (491); `test_runs.py:488` asserts `has_snapshot is True` because
  `LiveSession` wrote one; `test_watch_app.py:319` asserts the static fallback
  still serves `/fit.html` by its bare name, and `:249` that the detail view
  reloads the iframe per stage. All four assertions change here. The `fit.html`
  at `test_events_viz_history.py:129` is `write_html`'s own output and is **not**
  affected.
- `docs/manual/using/cli.md:121` (the § `rietx watch` heading is at 115) says
  watch "serves the directory a `LiveSession` writes, with a self-refreshing
  plot". The sentence stays true; the manual's fuller account is WP-1406's.

`LiveSession` is public, so this is the largest public change in the whole track
— larger than any name WP-1403 adds. Say so when it lands.

### The one authority for which points survive

`viz/compare.py:948` `decimation_index(tt, curves, max_points)` keeps each
bucket's min **and** max of every curve, never plain striding, because striding
drops peak tops. Its docstring already names why it is public: "a second
consumer arrived… a second implementation would be a second answer to *which
points survive*, the one question a plot must not disagree with the comparison
UI about." This is the third consumer and it fits that reason exactly.

It buckets in a python loop, so its per-stage cost is **measured** in WP-1404
rather than assumed free.

### Three conventions the snapshot must not get wrong

- **`delta` is always Δ/σ**, divided by the σ the `CompiledModel` stored, which
  `refine` copies to `result.sigma` verbatim. A result's σ is a lookup, never a
  re-derivation (WP-1029). The `weighted` flag reports whether σ was *measured*
  (`DataRef.has_sigma`) and changes only the axis title, because Δ/σ is what the
  fit minimised either way.
- **Ticks carry every emission line's positions**, not just the primary, or
  Layer 0 flags each Kα2 peak as an unindexed impurity — a real bug once caught
  by the misfit-injection suite. The loop in `viz/live.py:44-52` already does
  this; reuse it rather than rewriting it.
- A per-phase tick cap is a **reported** cap, never a silent one, the way
  `MAX_CANDIDATE_TICKS` is: carry the untruncated count beside the list, because
  a silent cap reads as coverage.

### The call site, and two defects in it

`refine.py:1991-1993`:

```python
if stream is not None and hasattr(stream, "write_snapshot"):
    # live monitoring (viz.live.LiveSession): rewrite the HTML view
    stream.write_snapshot(model, table, outcome, stage.name)
```

- It is inside `_run_plan` only, so **`run_stage` never refreshes the picture**.
  A caller driving one stage at a time — which is what `report/apply.py`'s
  recipes and the GUI's stage verb both do — gets events and no plot.
- It tests `stream`, so once WP-1403 chains a recorder onto a caller's own
  `EventStream.callback`, `hasattr` is False and no snapshot is written at all.

Fix both by building the sink list **once**, explicitly, and calling it from both
loops. Duck typing stays — it is what lets `viz/live.py` work with no import from
`refine.py` into `viz/` — what changes is that the candidate set is declared
rather than being whatever `stream` happened to be. In `run_stage` the snapshot
goes **before** `_record`, so a watcher never shows a state the history log has
not yet claimed.

### One shared plotly route

`gui/server.py:350` and `compare_app.py:103` each have their own `_plotly_js()`,
serving plotly out of the installed python package so a page works air-gapped and
no dist vendors it. A third copy in `watch.py` would break "two things are
written once and consumed everywhere". One small module, three call sites,
separately committable — and this is the moment, because the third copy is about
to be written.

The two copies are not identical, and the difference is the whole of the
function's shape: `gui/server.py` answers a missing plotly with a window flag
plus a `console.error`, `compare_app.py` by replacing `document.body`. So the
shared one takes its own fallback script from the caller and never invents a
third convention.

Note what is *not* being consolidated: the three servers' `_send`/`_json`
helpers, route dispatch and handler factories stay deliberately duplicated
(`gui/CLAUDE.md` records that as a choice). This is one shared function, not the
start of a framework.

### The reader side, which WP-1401 already built

`runs.SNAPSHOT_FILE` names `fit.html`, `Run.has_snapshot` reports whether one
exists, and `watch.py` serves it at `/api/run/<id>/snapshot`, degrading to a
one-line note when there is none. So the detail view already renders correctly
for a run with no picture at all, and a `snapshot.json` replacing the page is a
change at those three names plus the page's `detailShell`. Both modules sit at
`src/rietx/`, not under `viz/`.

Drawing in place is what pays for the change twice: the numbers are what the fit
stops serialising, **and** `Plotly.react` on a div keeps the reader's zoom across
a stage where a reloaded iframe cannot.

## Non-goals

- **No automatic recording.** WP-1403. This WP changes what a `LiveSession`
  writes when a caller asks for one; it does not make anyone ask.
- **No cancel and no verbs.** WP-1405.
- **No manual or skill prose.** WP-1406, which carries the whole break notice.
- **No `EventStream.emit` change.** Buffering is WP-1403's, and it must not
  arrive early by accident here.
- **No new `EventKind`.** Nothing here is an event.

## Tasks

- [x] `viz/plotlyjs.py`: one `plotly_js()`, with `gui/server.py` and
      `compare_app.py` switched to it and their local copies deleted. Lands
      alone, so a regression here is bisectable away from the rest.
- [x] The snapshot writer: decimated `two_theta` / `y_obs` / `y_calc` / `y_bkg`
      / `delta`, ticks per phase with the untruncated count beside them, the
      stage's statistics, `weighted`, and the schema version. Atomic
      `tmp.replace`, as `write_snapshot` already does — never a torn read.
      Every field's writer named at review.
- [x] `viz/live.py` keeps `LiveSession` as a thin shim over the shared writer,
      writing into a flat directory (what `using/cli.md` documents). **Plotly
      leaves this module entirely**, pinned by a test that puts `None` into
      `sys.modules["plotly"]` and records a run.
- [x] `refine.py`: the explicit sink list, `_run_plan` switched to it, and the
      missing `run_stage` call site added before `_record`. A test per defect,
      because neither is covered today.
- [x] `watch.py` draws the snapshot in the page: plotly once from the shared
      route, `Plotly.react` on a div per poll, and the reader's zoom surviving a
      stage. The iframe and its mtime cache-buster go. A run whose only picture
      is a legacy `fit.html` still gets the iframe.
- [x] `fit.html` stops being written. Rewrite
      `test_live_session_and_watch_server` to assert `snapshot.json`, and
      add the second test — a pre-existing `fit.html` is still served — without
      which the back-compat claim is prose.
- [x] Report the measured size of one stage's snapshot on each of `nac`,
      `cpd-2` and `trigger`, as a range. "How big does this get" is the first
      question a reader asks and it must not be answered with an invented
      number.
- [x] Tests + obs/calc/diff PNGs to `tests/output/`, looked at: the snapshot's
      curves must be the fit's curves, and a decimated plot that has dropped a
      peak top is visible long before it is assertable.
- [x] Skill: **none**. WP-1406 carries the track's skill change.

## Acceptance

A recorded stage produces a snapshot whose decimated curves reproduce the fit's,
in a process where plotly cannot be imported.

```sh
.venv/bin/python -m pytest tests/test_events_viz_history.py tests/test_compare_ui.py tests/test_gui_server.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

Snapshot sizes reported in the handover as a range with venv and platform named.

## References

- WP-1029 — every weighted residual divides by `RefinementResult.sig()`; σ is a
  lookup, never a re-derivation; `weighted` is `DataRef.has_sigma`.
- WP-1008 — `/api/result/window`, `decimation_index`'s second consumer.
- WP-1120 — two spellings of Ω one to two ulp apart, and the rule that a caller
  owns which it reproduces. The same discipline applies to a plot's points: one
  authority, passed in, never re-implemented.
- `gui/CLAUDE.md` — why the three servers duplicate their transport helpers, and
  therefore what this WP is and is not consolidating.

## Handover log

### 2026-09-15 — the picture stops being a web page

Watching a refinement no longer costs the fit a multi-megabyte web page every
stage. `rietx watch` draws the plot itself and redraws it where it stands, so
for the first time you can zoom into a region and watch that region improve
rather than having the view thrown away at each stage. Recording a run needs no
plotting library at all, which is the thing WP-1403's automatic recording was
waiting for. The saving is real and smaller than this WP guessed: the file is
14-33x smaller, not the ~40x "about 100 kB" implied, and the fit still pays
1.03-1.28x rather than the 1.00x the framing invited — because half of what
remains is a python bucket loop this WP deliberately left alone.

*Done.* All nine tasks, seven commits. `viz/plotlyjs.py` is one `plotly_js()`
with the fallback passed in by each caller, the two prior copies having already
disagreed about it. `viz/snapshot.py` builds a stage's payload and every field
names its writer; `CompiledModel.sigma_measured` is the one new field, carrying
the σ-measured fact beside the σ it describes because that fact did not survive
`compile_model` and `weighted` needs it. `LiveSession` is a shim over it and
imports no plotting library, pinned by a test that puts `None` into
`sys.modules["plotly"]` and records a run. `refine.py` builds the sink list
once and explicitly, and `run_stage` gained the call site it never had — before
`_record`, so a watcher is never shown a state the history log has not claimed.
`watch.py` loads plotly once and calls `Plotly.react` under one `uirevision` per
run, with every mark quoted from `viz/html.py` and every colour from
`viz/plots.PALETTES`.

*Measured.* `[dev]` venv (numba 0.67.0, no jax, no torch), macOS arm64
(Darwin 25.5.0), python 3.12.12, rietx 1.4.0, on `examples/bench_refinement.py`'s
own cases, machine checked idle and measured alone. Three repeats on `nac` and
`cpd-2`, two on `trigger`.

| case | snapshot | was `fit.html` | off | `events=<path>` | `LiveSession` |
|---|---|---|---|---|---|
| `nac` | 328-329 kB | 6.03 MB | 0.35 s | 1.01-1.03x | **1.28x** (1401: 1.47-1.49x) |
| `cpd-2` | 233-241 kB | 4.74 MB | 2.33-2.37 s | 1.01-1.02x | **1.06x** (1.10x) |
| `trigger` | 180-183 kB | 4.51 MB | 5.76-5.77 s | 1.01x | **1.03x** (1.04-1.05x) |

Rwp was bit-identical across all three configurations on every case, so none of
this buys anything by changing the answer. Drawn points 4093-7385 of
4165-22003: `max_points` is a *bucket* budget, 2000 buckets each keeping min and
max of three curves, so the drawn count exceeds it whenever the curves disagree
about where their extremes sit. Rounding to six significant figures is 40-45 %
of the payload (556-557 kB unrounded on `nac`).

Where a stage's build goes, best of five per part: `decimation_index` 6.6-7.1 ms,
`json.dumps` 2.4-4.5, `model.evaluate` 0.3-5.7, everything else under 1.
`_json_list` was 5-9 ms of an 18 ms build until it stopped walking every point in
python; the build is now 9.3-14.2 ms. **The decimation is the whole of what is
left**, and it is the same 6.6-7.1 ms on all three cases because it is 2000
buckets of python regardless of pattern length.

Fast selection **4751 passed, 132 skipped, 2:14**, same venv and platform, run
alone. This branch adds 21 test functions and retires 2 (both renamed into the
21), so +20 collected, no new skip. `origin/main` had not moved since the branch
was cut. The full suite was not run and is not owed: nothing here touches the
forward model, the solver or any physics, so no measured number can move.

*Gotchas.*

- **A `ParameterTable` is not a stage's.** One table is reused and re-freed down
  the plan, so holding a stage's `(model, table, outcome)` for a later
  `build_snapshot` decodes θ against a table of the wrong width and raises. A
  real sink writes inside the call and never meets this; a test or a harness
  that defers must copy the table (0.2 ms).
- **`progress=` was not the second defect it looked like.** `_attach_progress`
  mutates the stream in place and returns the same object, so the old
  `hasattr(stream, ...)` still found it. The waiting defect is WP-1403's
  recorder, which is a *different* object, and nothing today can build that
  case — so it is pinned by the sink-set declaration test rather than by a fit.
- **The watcher's page is javascript quoted inside python, and python cannot see
  a syntax error in it.** A stray escape cost the whole page mid-session: the
  script threw on load, the run list sat at "scanning" forever, and all 25 tests
  in `test_watch_app.py` still passed, because every one of them asserts a
  substring of a page nobody executed. `node --check` over the extracted script
  now covers both that page and `compare_app.py`'s.

*Review.* `/code-review high --fix` raised eight findings, five applied and
three declined. One was a real defect this session introduced and one a test
could not have caught: `drawDetail` committed `shell.mtime` before awaiting the
draw, so any early return in `drawSnapshot` marked a write drawn that never was
— and on a fit's last stage there is no later write to notice, so the watcher
would hold the previous stage's picture for good. `drawSnapshot` now answers
whether the write was dealt with. The pass also found `stage_ticks` filtering up
to a hundred thousand positions through a python generator, in the same commit
that vectorised `_json_list`; two new comments that argued for the opposite of
their own code; and the crumb showing the previous run's point count for a poll.
Declined: the subnormal NaN in `_round_significant` (unreachable for an
intensity or a residual), the `"snapshot.json"` literal in two modules (the
practice `events.jsonl` and `status.json` already follow, and both halves are
pinned end to end), and guarding the sink loop — a sink that raises *should*
kill a fit whose caller asked for a live view, and the case that changes is
WP-1403's, so it went into 1403's `### Inherited` rather than into this branch.
The page was re-driven in chromium after the change, and the zoom still
survives.

*Next.* Three, in order. **WP-1403** is now unblocked and is the point of the
track: recording every fit costs 1.03-1.28x and 180-329 kB a stage, which is
affordable, and it needs no plotly. **WP-1404** should start from the
decimation number above rather than re-deriving it — 6.6-7.1 ms a stage is
50-75 % of a snapshot, and vectorising `decimation_index` has to return a
bit-identical index set because the GUI and the comparison UI read it too.
**WP-1406** carries the whole break notice; `using/cli.md` has had one sentence
corrected in place ("reloads" stopped being true) and nothing else.

- **2026-09-13** — created. Split from WP-1401 so that the `fit.html` break, the
  largest public change in this track, lands in a commit of its own rather than
  inside a larger one. It is worth shipping on its own terms: even if WP-1403's
  automatic recording never happens, a live view that costs 100 kB instead of
  3.5 MB, keeps the reader's zoom and needs no plotting library to record is
  strictly better than what a caller gets today.
