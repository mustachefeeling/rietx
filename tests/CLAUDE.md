# CLAUDE.md — tests/

Scope: running, timing, counting and budgeting the test suite, and the CI
that runs it. The headline rules live in the root CLAUDE.md (they govern how
any session quotes numbers); this file holds the operating detail and the
evidence. The measurement diary that taught these rules is archived in
`docs/milestones/v1.0.md` § Appendix.

## Running

- `-n` is deliberately **not** in `addopts`: a bare `pytest tests/x.py::y`
  stays serial, so `-s` and pdb keep working. `--dist loadgroup` is not
  optional — it honours the `xdist_group` marks that keep a shared fixture on
  one worker; plain `--dist load` ignores them and silently refits.
- Fast unit/property tests always; real-data acceptance marked
  `@pytest.mark.slow` (`test_acceptance_nac.py`, `_srm660c.py`, `_fap.py`,
  `_capillary.py`, `_indexing.py`). Reference values and data provenance in
  `tests/data/README.md`. Every test refinement also writes obs/calc/diff
  PNGs to `tests/output/` (gitignored) for visual inspection — Rwp hides
  locally-bad fits.

## Shared fixtures and xdist groups

A refinement that two suites both need is computed once, in
`tests/conftest.py` (`sample1_results`, `srm660c_baseline`), and **every
consumer must carry the matching `@pytest.mark.xdist_group`** — otherwise a
second worker rebuilds the whole fixture and the sharing costs more than it
saved. Same rule one scope down: a module fixture several tests share pins
its module (`nac`, `capillary`, `srm660c`, `stephens-brucite`,
`indexing-consensus`, …). The failure is silent, so the check is a
`--durations` scan for the same setup appearing twice.

**One dataset, one group**, and runtime is set by the longest *group*, not by
total work — splitting a group is the only way to go faster, and un-sharing a
fixture to do it just moves the cost. A group ordering is a measurement with
a shelf life: "indexing does not set the wall clock" expired unnoticed at
~550–590 s against `stephens-brucite`'s 533 until a `--durations` re-read
caught it, and moving the LaB6 rows into their own `indexing-acceptance-lab6`
group was free because nothing in the group shared a fixture. Re-read the
`--durations` list rather than the last session's sentence about it.

## Budgets in tests

**A wall-clock budget inside a test is a runaway guard, never a timer.** Any
test whose serial time is a large fraction of its declared budget is a load
sensor pretending to be an assertion — it passes serially and fails under
`-n auto` for reasons unrelated to what it asserts. Four measured instances:
`BUDGET_SECONDS` in `tests/test_indexing_engines.py` (180 s against an
~85–105 s search, broken by adding one unrelated module); **the budget a
test depends on may be one rank down, in the library**
(`DOMINANT_ZONE_PROBE_SECONDS`, a hard-coded 10 s against a 4.3 s serial
cost); a real-data row that reported a *different centring* under load
(73 s serial, 258 s loaded, 60 s declared — `REAL_DATA_BUDGET_SECONDS`, now
300 s, costs nothing because these searches finish early when they finish at
all); and completion assertions generally — "some system did not finish" is
a statement about machine load, not the data, and belongs as "every system
searched reports whether its domain was exhausted".

**The check to run before landing any row with a budget: compare its serial
time with its declared budget; if the budget is not several times larger,
the assertion is a load sensor.**

**The honest-budget rule and the CI budget pull against each other, so expect
to pay in scope.** Raising a real-data `budget_seconds` from 60 to 300 let
one search run to completion at 850 s and took the full suite to 15:33; the
budget could not go back, so the scope moved — each pure phase searched over
the systems its answer lives in, a declared restriction `systems_searched`
carries — and the same tree re-measured at 8:09. When a budget fix makes
something slow, narrowing what is searched is the lever — never the budget,
and never a silent cap.

## Quoting numbers

- **Quote wall clock as a range, never as a figure**: the same green tree
  measured 7:37 and 5:44 minutes apart on one machine, 11:52 on a busier
  one, and 12:40 while it also ran a headless browser, three vite builds and
  a second pytest. Machine state moves it further than most changes do;
  compare runs, not records.
- **Quote the extras with any count**: installing `[jax,torch]` converts
  most skips into passes, so a bare "N tests" figure means nothing without
  the venv it was measured in.
- **Say which numbers moved**: after adding N tests, passed+skipped must
  move by exactly N in both the fast and full selections, and a new skip is
  not a new pass (WP-1029 added six: five passes and one skip, which is the
  version of this check that earns its keep). The vitest suite is counted
  separately — its 207 was once quoted as 206 until the next session re-ran
  it, the same lesson one suite over.
- **`--collect-only` undercounts by one per module-level `importorskip` that
  fires** (resolved 2026-07-31, WP-1031, by diffing junitxml nodeids against
  the collection list): a module skipped at import is **one skipped test**
  in the run summary and **zero items** under `--collect-only`. Three
  modules can fire (`test_backend_jax`, `test_backend_torch`,
  `test_manual`'s sphinx), so on a numpy-only `[dev]` venv the historical
  figures were two short of passed+skipped in both selections
  (1385 vs 1383, 1306 vs 1304) and on `[dev,jax,torch]` the gap is zero. So
  `collected = passed + skipped − (module-level skips that fired)` — quote
  whichever you measured, and say which. (The "1378 collected" the docs
  once carried was a sum, not a measurement — that part stands.)

## CI

CI runs the same commands (`.github/`), on cadences set by a **free-tier
budget** — 2000 Actions minutes/month on a private repo, billed per job
rounded up, so an over-budget config buys a month with no CI rather than a
bill. Per push: ruff + the fast suite on 3.13, Linux, skipped for docs-only
pushes (5 billed min; docs-only pushes get `docs.yml`, 1 min, which runs
`tests/test_docs_consistency.py`). Weekly: the full suite plus
3.11/3.12/3.14 (55). Monthly: macOS and `[torch]` (66 — macOS bills at
**10×**). **Before adding a job, price it**: the first version of this
matrix cost 21 minutes per push and 1350 a month, which did not fit.

Two consequences for local work:

- **The bit-identity goldens are pinned to `darwin/arm64`**
  (`GOLDEN_PLATFORM` in `tests/test_backend_shim.py`) and *skip* elsewhere:
  measured, Linux x86-64 diverges by 1 ulp to 1.7e-13 relative — a libm and
  summation-order difference — so the gate is asserted where it was captured
  rather than loosened to a tolerance that could not distinguish it from a
  real change.
- **`tests/.jax_cache` is why the jax rows feel free locally** — deleting it
  takes the two jax files from ~12 s to 107 s — but caching it in CI was
  measured and does *not* help (8:18 warm against 8:12 cold): jax's
  persistent cache holds only XLA compilations above a time threshold, while
  per-process tracing and lowering are paid every run.
