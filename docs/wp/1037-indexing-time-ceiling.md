# WP-1037 — Indexing: a stated time ceiling and honest progress

Milestone: v1.0 · Status: ⬜
Depends on: WP-1024 (1021, 1022 soft)

## Goal

A caller can learn the approximate worst-case wall clock of an
`index_pattern()` run **before starting it**, bound the *whole* run rather than a
per-engine-per-system slice, and watch it progress. **No answer changes**: this WP
adds reporting and control, not search behaviour. The behaviour-changing half is
WP-1042.

## Context

### The measured framing: we are not slow, we are silent

Read this before proposing anything faster. Each figure is from the source paper,
on the hardware of its day:

| program | cost |
|---|---|
| DICVOL04 (this package's dichotomy parent) | 60–360 s for ten of 29 NBS triclinic patterns; **1215 / 3307 / 3770 s** for three of them. Monoclinic avg 6.9 s, max 60 s |
| TOPAS SVD-Index | "approximately 3 min" for all systems down to triclinic, on a **600 MHz** machine |
| McMaille | seconds at high symmetry; all symmetries over a wide domain "hours, if not a night" |
| Conograph | exhaustive, **≤5 min** quick search across 25 real patterns |
| **pxrdref today** | **30–150 s per real dataset** |

So the runtime is unremarkable for the field. What is missing is that **none of it
is visible or bounded**, and McMaille shipped the fix in 2004: an on-screen
summary, a cancel key, results saved on cancel, checked every 30 000 trials.

### What is actually wrong

- `budget_seconds` (default 30) is applied **per (engine × system)** — a fresh
  `Budget` is constructed inside the per-system loop at `dichotomy.py:599` and
  `trial_error.py:286`. A default call is therefore **2 × 7 × 30 = 420 s** of
  search. Nothing computes or states that.
- Plus the dominant-zone probe: `trial_error.py:96,474-479`, 3 ladder rungs ×
  `min(budget_seconds, 30)` per eligible system — **entirely invisible**, and about
  a third of the worst case.
- Plus `validate_by_lebail` (`workflow.py:289-295`), which runs a full staged
  `Refinement.fit(mode="lebail")` per checked candidate and takes **no budget and
  no cancel token at all**.
- Events fire at **four** sites: `index_start` (`workflow.py:430`),
  `stage_start`/`stage_end` per *engine* (`:456`, `:463`), `index_end` (`:504`).
  During a 30 s cubic search the stream is silent; a GUI can show "1 of 2 engines".
- Both `cli.py:112` and `agent.py:292` describe `--budget` as "per crystal
  system", omitting the `n_engines` factor. The docs are wrong, not just thin.

### Seams to extend

`Budget` (`engines.py:313-342`) already short-circuits `expired()` on
`bool(self._cancel)`, and **every** cooperative check in the indexing package reads
`bool(cancel)` (`workflow.py:452,471`; `extinction.py:736,790`). Only
`least_squares.py:516` uses `.is_set()`. So a whole-run deadline that duck-types as
a cancel token nests under every existing `Budget` with **no engine changes**, and
the cooperative-cancellation invariant holds by construction — the deadline *is* a
token, never an interrupt.

`optimize/cancel.py`'s docstring deliberately keeps timeouts out of `CancelToken`
("each caller wants a different policy"). That stance stands: the deadline is
`index_pattern`'s policy, so it lives in `indexing/engines.py` beside `Budget`.

Retrospective timing already exists — `EngineResult.stats[f"{system}.seconds"]`
(`dichotomy.py:613`, `trial_error.py:376`) → `IndexingResult.engine_stats`.

### Two traps, both silent

1. **`validate_by_lebail`'s exception order.** Its generic `except Exception` sets
   `status="failed"`, which `consensus.caveats_for:296` reads as
   `validation_failed` — a **refuting** caveat. If a ceiling cancellation falls
   into that branch, the run *refutes the cell it merely ran out of time on*.
   `except RefinementCancelled: raise` must come first. Un-run candidates keep
   `lebail = None` and already get `not_validated` (capping) per candidate, which is
   the honest reading and needs no schema change.
2. **Two event ladders on one kind.** The GUI's `_push` (`gui/session.py:957-961`)
   overwrites `stage_index`/`n_stages` from whichever event arrived last, so a
   nested per-engine *and* per-system ladder makes a progress bar jump. Replace the
   engine-level pair; do not nest.

### Prior findings that constrain this

- **Longer runs never bought a better answer** in this package's record — six point
  measurements, none in favour (HL2-1 identical at 15/25/45 s; LaB6 4 s cubic-only
  vs 35 s four-system, identical cell; bethanechol set F barren at 240 s *and*
  900 s). The decisive one is WP-1030's: d ∈ [2,20] still running at 2700 s with
  zero candidates → **32 s after the prunes landed, truth ranked first**. The one
  counter-case is that *too little* budget degrades (zircon truncated at 60 s
  reported the wrong centring). Budgets are runaway guards, not timers.
- **`features["indexing"]` has been `False` since indexing shipped.**
  `capabilities.py:229` reads `hasattr(pr, "index")`; the export is `index_pattern`
  (`__init__.py:15,120`). `tests/test_capabilities.py:140` asserts
  `== hasattr(pr, "index")` — a tautology that can never fail, which is why nothing
  caught it. `capabilities.py:19-21` uses this very flag as its showcase for
  derived predicates, so the docstring is now false too, as is `CLAUDE.md:166`.

### Licensing

Concepts only from DICVOL04/McMaille/Conograph (GPL-family or closed); the papers
are open literature and may be cited and implemented from. No code ported.

## Non-goals

- **Any change to what is searched or what is found** — cost-ordered systems,
  streaming candidates, volume tightening and the `quick` default are **WP-1042**,
  which carries the acceptance re-measure they force.
- Raising `DEFAULT_SEARCH_LINES` — WP-1039.
- Measuring or correcting the 2θ shift — WP-1038.

## Tasks

- [ ] **Task 0 — measure, then write the constants.** For the 8-dataset known-cell
      corpus record in the handover log: wall clock (as a *range*), **time to first
      candidate**, time to final list, per-phase split (search / probe /
      validation), and `engine_stats`. This is the first honest cost profile of
      `index_pattern` and it sets every default below. No `src/` change.
      *Instrument before ranking (WP-1030) — a plausible cost model is not a profile.*
- [x] `features["indexing"]` names an export that exists. Fix as **data** —
      `_SURFACE_FLAGS: dict[str, str]` mapping flag → top-level name — plus the
      meta-test `set(_SURFACE_FLAGS.values()) <= set(pr.__all__)` that would have
      caught it. Rewrite `capabilities.py:19-21` as the lesson and fix
      `CLAUDE.md:166`'s example.
- [ ] `Deadline(Budget)` — whole-run clock shaped as a cancel token: `__bool__`,
      `is_set`, `remaining`, `cancelled_by_user`. **Must compose** with a caller's
      own `CancelToken` (`Budget.__init__` takes one `cancel`, so write the any-of
      token once), and every consumer must be able to tell a ceiling from a user
      cancellation — enumerate those sites, do not assume them.
- [ ] `estimate_ceiling(spec, *, engines, validate) -> CeilingEstimate`: search +
      probe + validation, `granularity_seconds` (how far past the ceiling a run can
      land), and `covers`/`unmodelled` naming registered engines whose cost is not
      modelled. **It is arithmetic on the spec, not a timing prediction, and the
      docstring says so.** It also carries task 0's **measured typical range** —
      the arithmetic worst case is ~1400 s against typical runs of 30–150 s, and a
      ceiling 10× the typical gets ignored. Fix the `--budget` help in `cli.py:112`
      and `agent.py:292` in this commit.
      **The validation term is the weak one**: `validation_budget_seconds` does not
      exist today, and Le Bail cost is data-dependent — derive it from
      `predicted_reflection_count` or report it as explicitly uncertain. Do not let
      a guess wear arithmetic's clothes.
- [ ] `index_pattern` honours `SearchSpec.total_budget_seconds` (default `None` =
      today's behaviour, bit-identical). A deadline that binds must leave the run
      returning a complete `IndexingResult` over what was reached, never an
      exception, and `systems_searched` must distinguish **three** states —
      searched, truncated, **not reached**. `INDEX_BUDGET_EXHAUSTED` says so.
- [ ] Validation runs inside the ceiling: `validate_by_lebail(..., cancel=)`, with
      `except RefinementCancelled: raise` **before** the generic handler. Test that
      a truncated validation leaves `lebail = None` and reads as `not_validated`,
      never `validation_failed`.
- [ ] Progress per (engine × system) on the **existing** event kinds — adding
      *fields* is not an `EVENT_SCHEMA_VERSION` bump, adding a kind is, and this
      task must not bump it (assert that). One flat ladder: search units, probe
      units (currently invisible), validation units. `n_stages` becomes revisable
      mid-run; record that in `history/events.py` beside the additivity rule. A
      `Progress` object carries the counter with `stream=None` a working no-op, so
      every direct engine unit test is unchanged.
- [ ] `pxrdref index --ceiling` and `--total-budget`; `SearchSpecSpec` gains the
      field; `AGENT_PROTOCOL.md` rows for `INDEX_BUDGET_EXHAUSTED` and a
      "how long will this take" note beside the indexing recipe.
- [ ] Tests: `tests/test_indexing_ceiling.py` (new) + edits to
      `test_capabilities.py`, `test_run_control.py`, `test_indexing_engines.py`.

## Acceptance

Every existing indexing answer is unchanged (this WP's central claim), the ceiling
is computable before a run, and a declared total is honoured.

```sh
.venv/bin/python -m pytest tests/test_indexing_ceiling.py tests/test_run_control.py \
    tests/test_capabilities.py tests/test_indexing_engines.py tests/test_gui_server.py -n auto
# mandatory — touches engine control flow; WP-1030's regression was invisible to all 115 fast indexing tests
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

By hand, into the handover log:
`pxrdref index tests/data/qarr/corundum.prn --wavelength 1.5405929 --ceiling`
prints worst case **and** measured typical before running; `--total-budget 60`
finishes within 60 s plus one granularity unit and names the systems not reached.

## References

- Boultif & Louër (2004), *J. Appl. Cryst.* **37**, 724 — DICVOL04 timings, §5.
  `/Users/yue/zotero-linker/derived/I2VA3ZAB/`
- Coelho (2003), *J. Appl. Cryst.* **36**, 86 — TOPAS SVD-Index, §2.1 timing.
  `/Users/yue/zotero-linker/derived/5RI7CB42/`
- Le Bail (2004), *Powder Diffr.* **19**, 249 — McMaille; §IV is the 2004
  cooperative-cancel-with-partial-results design this WP reproduces.
  `/Users/yue/zotero-linker/derived/7AEVVGH6/`
- Oishi-Tomiyasu (2014), *J. Appl. Cryst.* **47**, 593 — Conograph ≤5 min.
  `/Users/yue/zotero-linker/derived/NWFJ8YEB/`

## Handover log

- **2026-08-04** — created. Written from the source-literature review that also
  produced WP-1038…1042 and `docs/LITERATURE.md`. **Nothing here has been run**:
  the "30–150 s per real dataset" figure is assembled from WP-1026/1030 handover
  logs, not re-measured, which is exactly what task 0 exists to fix. Scope was
  deliberately cut from a 12-commit draft — everything that changes an answer moved
  to WP-1042 so this WP can close in one session without an acceptance re-measure.
