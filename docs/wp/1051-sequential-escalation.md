# WP-1051 — Sequential escalation ladder + chain hygiene

Milestone: v1.0 (proposed 2026-07-30) · Status: ⬜
Depends on: —

## Goal

The warm-start chain's fallback becomes a three-rung ladder (warm-collapsed →
warm-staged → cold-staged), and a pattern that stays diverged after the last
rung is quarantined: flagged, excluded from the reseed statistics, and never
used to seed its successor.

## Context

SrRietveld's automation result (Tian *et al.* 2013, §3): in a warm-started
series the full staged scheme is usually unnecessary — run everything-at-once
and "the step-by-step scheme only turned on if a refinement diverges".
`sequential.py` already has the fast path as the *default* (`_collapse` unions
every stage's globs into one `"warm_refit"` stage; `refit="single"`) and one
fallback rung (`_reseed_needed` → refit **cold** with the full `base_plan`,
keep the better by `_better`). Three gaps, found by reading the chain flow on
2026-07-30:

- **No intermediate rung.** The ladder jumps from warm-collapsed straight to
  cold-staged, discarding the warm start entirely — yet warm + full
  `base_plan` is the cheap middle option (`refit="stages"` exists as a
  series-global switch, so the machinery is already there). Measured on the
  round-robin sample-1 series and quoted by the module's own docstrings:
  warm-collapsed **838** iterations carrying everything (`_carry_into`) or
  **904** carrying everything but the scales, warm-staged **1623**
  (`_collapse`, and `fit`'s `plan, refit` entry), cold-staged-per-pattern
  **2863**. So the middle rung is genuinely intermediate — ≈1.8× the first and
  ≈0.57× the last. *(Corrected on arrival, 2026-08-09: this bullet used to read
  the three numbers as "staged-warm ≈ 904 vs collapsed-warm 838". 904 is a
  **carry** variant of the collapsed rung, not the staged one, and the
  `sequential.py:129-131` anchor it cited is stale.)* Ladder: warm-collapsed →
  warm-staged → cold-staged, each rung only on failure of the previous,
  keep-best across all attempts.
- **Chain hygiene defect.** A pattern whose cold refit *also* diverges still
  becomes `previous` for the next pattern and its Rwp still joins
  `accepted_rwp` (`sequential.py:524-534`) — so a doubly-failed pattern seeds
  its successor with garbage and drags the reseed median that decides every
  later trigger. Fix: the successor seeds from the last *accepted* pattern;
  the failed entry is flagged with a new `SEQUENTIAL_UNRECOVERED` diagnostic
  (level `"warning"` — the two existing sequential fences are `"info"`) and
  its Rwp is excluded from `accepted_rwp`.
- **Trigger inventory is narrow and undocumented.** Only
  `status == "diverged"` or `rwp > reseed_factor × median(accepted_rwp)`
  fire (`_reseed_needed`, `sequential.py:630-637`); guard firings
  (HIGH_CORRELATION, at-bounds…) and parameter jumps are inert as triggers.
  Decide and record — the likely answer is *keep* Rwp/divergence as the only
  automatic triggers (guards fire legitimately on converged patterns, and
  `SEQUENTIAL_DISCONTINUITY` is a post-hoc series property), but the decision
  belongs in the module docstring, not in silence.

Bookkeeping: `SeriesEntry` already carries `reseeded: bool` and `rwp_warm`;
extend to say *which rung won* (e.g. `rung: Literal["warm", "warm_staged",
"cold"]`, default `"warm"`) rather than a second boolean —
`schemas/sequential.py:30-78`, and the schema mirror tests will pin it.
`n_iterations` already sums all attempts (`sequential.py:516,522`); keep that
contract. `plot_trajectory` rings reseeded points (`viz/plots.py:211-223`, and
`gui/src/lib/series.ts`'s `reseededFlags` does the same for the panel) — an
unrecovered point should render distinctly (or be documented as
rendered-but-flagged).

### What WP-1016 left in the way

Folded in from this WP's `### Inherited` on 2026-08-09 and **verified against
the code at 4baf462** — all five still hold. `SequentialRefinement.fit` takes
`events=`/`cancel=`, so `_chain` and `_fit_one` carry them and the ladder has to
thread them through every new rung.

- **`_fit_one` takes `stream=`/`stamp=`/`cancel=` keyword-only**
  (`sequential.py:540-573`), and each attempt wraps the caller's stream in
  `_SeriesStream`, which stamps `series_index`, `series_label`, `series_n`,
  `series_pass` and — on the cold refit — `series_cold=True`. Three rungs means
  **three** attempts on one pattern, so each rung needs a distinguishing stamp
  rather than a reused `series_cold`: a consumer counting `fit_end`s per pattern
  has to tell them apart. Two renderers read that stamp and both need the rung —
  `gui/session.py:_series_stage_name` (the progress pill, which appends
  "(cold restart)") and `gui/src/lib/stream.ts:seriesPrefix` (the console's
  `[label k/N ↩❄]`, whose `SERIES_KEYS` set must list any new key or it prints
  twice).
- **Every stamp key is an *added* `data` field on an existing kind**, so
  `EVENT_SCHEMA_VERSION` stays "2". A new rung must not tempt a new `EventKind` —
  `history/events.py`'s additivity rule is what keeps the version usable as a
  compatibility signal.
- **`_chain` already has a mid-walk exit**: a `RefinementCancelled` from any
  attempt breaks the loop, and a cancel during the *cold* refit deliberately
  keeps the warm fit (it is a complete fit of that pattern —
  `sequential.py:504-511`). The ladder's keep-best logic has to preserve that,
  and `SEQUENTIAL_CANCELLED` reports how far the chain got. So
  `SEQUENTIAL_UNRECOVERED` will be the **second** warning-level sequential
  fence, not the first.
- **`REFIT_MODES` and `DIRECTIONS` are module constants** (`sequential.py:124`)
  that the GUI's series panel quotes to build its menus — via
  `gui/series.py:check_settings`/`setup_payload`, pinned by
  `tests/test_gui_server.py:2170`. Changing what `refit=` accepts means editing
  the tuple, not a literal, and the panel picks the new value up for free.
- **A GUI panel now drives this chain** (`gui/series.py`, the Series tab), so a
  new diagnostic reaches its "Fences" strip automatically, but a new *setting*
  does not: `series_put`'s allow-list and `SeriesSetup` need the field. And its
  trajectory view reads `SeriesEntry.reseeded`/`rwp_warm`
  (`gui/src/panels/Series.svelte:645`, whose chip quotes `rwp_warm` as the warm
  Rwp) — which three attempts make ambiguous, so decide what those two mean
  before the panel's chip says something false.

## Non-goals

- Per-pattern plan control in the API (`plan`/`refit` stay series-global;
  `prepare` stays value-only).
- Agent-surface exposure of `reseed_factor` / the ladder (the
  `refine_sequential` task keeps its current fields).
- Protocol-ensemble accuracy estimates (running the chain under two
  background/profile models and quoting the spread, SrRietveld's two-engine
  device) — v2 idea, recorded here so it isn't relitigated.

## Tasks

- [ ] Ladder: insert the warm + `base_plan` rung in `_chain`'s reseed block;
      keep-best via `_better` across all rungs; `SeriesEntry.rung`. Preserve
      the cancel-during-a-later-rung rule: the best complete attempt so far
      stands, and the walk ends.
- [ ] Hygiene: unrecovered pattern seeds nothing and joins no median;
      successor chains from last accepted; `SEQUENTIAL_UNRECOVERED`
      diagnostic (warning) with the rung history in `data`.
- [ ] Trigger decision recorded in the module docstring (and, if the answer
      changes, implemented + tested).
- [ ] Stamp: each rung distinguishable on the event stream (an added `data`
      key, no new `EventKind`), with both renderers of the stamp updated —
      `gui/session.py:_series_stage_name` and `stream.ts`'s
      `seriesPrefix`/`SERIES_KEYS`.
- [ ] Panel semantics: say what `reseeded`/`rwp_warm` mean once three attempts
      can run, and make `Series.svelte`'s chip, `series.ts:reseededFlags` and
      `viz/plots.py`'s rings agree with the answer; an unrecovered point
      renders distinctly or is documented as rendered-but-flagged.
- [ ] Tests, `tests/test_sequential.py` style (synthetic series, forced
      `reseed_factor=1.0`): ladder tries rungs in order and stops at first
      success; keep-best bookkeeping; an injected unrecoverable pattern (e.g.
      corrupted y) is flagged, its successor's warm start comes from the last
      good pattern, and the reseed median ignores it; trajectory plot/CSV
      round-trip with the new field.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_acceptance_sequential.py -q
.venv/bin/python -m ruff check src tests examples
```

Criterion: the hygiene test passes (unrecovered pattern quarantined), and the
IUCr-ramp acceptance still converges every pattern with chained cost within
the measured range quoted in its module docstring (compare runs, not records).

## References

- Tian, P. *et al.* (2013). *J. Appl. Cryst.* **46**, 255–258.
  doi:10.1107/S0021889812045967 — SrRietveld;
  §3 for the diverge-then-escalate scheme and the two-engine dispersion idea
  fenced above.

## Handover log

- **2026-07-30** — created from the Toby 2024 / SrRietveld literature review;
  gaps verified against `sequential.py` control flow (anchors in Context).
