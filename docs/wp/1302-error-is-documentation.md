# WP-1302 — The error is the documentation; the output is bounded; the result is a termination view

Milestone: v1.3 · Status: ✅ 2026-08-29 — the ramp's 35.2 kB diagnostics dump is 3.5 kB on the same fit, `print(result)` smaller still; the termination view, HIGH_CORRELATION
dedup/cap, progress=, and the closest-match/re-export surface all shipped in one session
Depends on: — (1305 supplies `delta_bic` for one line of the summary; until then that line says "run `suggest`")

## Goal

Every pydantic schema, both plan dataclasses and the package itself answer a wrong name
with the right one; every class the manual documents imports from `rietx`; a fit's
diagnostics list is bounded and deduplicated; the objects an agent touches say in their
first docstring line how to get numbers out; a fit can report progress to a text sink;
and a result prints as the **termination view**: per-stage status, the three stop
conditions with their state, the declared deliverable's rows, the protocol actually run,
the agreement indices last, the visual check named.

## Context

**Measured, two campaigns.** The ramp run (2026-08-26, 90 API calls) spent ~17 calls on
"I don't know the shape": `pick_peaks()`'s signature, `result.value()`,
`PLAN_PRESETS[name]` (a builder, not a plan), `Stage.free`, `src/rietx/profiles/` guessed
three times (it is `model/profiles/`), `n_iterations` looked for on `Statistics` when it
is on `SeriesEntry`. The two custom `__getattr__` messages it hit (`RefinementResult`,
`PLAN_PRESETS`) fixed the call on the next try; the five bare pydantic `AttributeError`s
cost 1-4 calls each. Across a contributor's 86-run campaign (5,430 tool calls, 2026-08):
`module 'rietx' has no attribute 'BackgroundChebyshev'` ×2, `'EmissionLine'`, `'viz'`,
`'identify_format'`; `'PatternData' … 'esd'`; `'Statistics' … 'n_free'`; `'SeriesResult'
… 'patterns'`; `Stage.__init__() got an unexpected keyword argument 'free'` (the ramp hit
`Stage.free` too); `Refinement.__init__() … 'pattern'` and "takes 3 positional arguments
but 4 were given"; `MultiHistogramRefinement.__init__() … 'history'`; pydantic
`ValidationError` for `Instrument` ×2, `Cell`, `Atom`. Agents read **source** to answer
what docs did not (17 source reads and 0 manual reads in the four projected runs; 74
Reads plus 467 `sed`/`grep`s of `src/rietx` across the bundle), so docstrings outrank
manual pages. The files they opened: `schemas/instrument.py`, `schemas/structure.py`,
`schemas/params.py`, `strategy/staged.py`, `refine.py` (`tie`), `schemas/results.py`,
`io/readers.py`, `model/profiles/fcj.py`, `model/profiles/caglioti.py`,
`model/corrections.py`, `params/vector.py`, `sequential.py`, `schemas/sequential.py`,
`optimize/qpa.py`, `crystallography/cif.py`, `schemas/common.py`, `background/auto.py`,
`io/exporters.py`, `report/layer0.py`, `schemas/pattern.py`, `examples.py`.

**The top-level export gap.** `Source`, `EmissionLine`, `BackgroundChebyshev`,
`BackgroundPSpline`, `Geometry`, the profile blocks and other `schemas` classes the
manual names are not in `rietx.__all__` (verified 2026-08-28). An agent-written API
reference in that campaign asserted "everything public is re-exported from the top-level
package" and recommended `from rietx import Source, EmissionLine, BackgroundChebyshev`;
the `AttributeError` then recurred three times in later runs.

**Output volume.** The ramp's call 31 printed a 40 kB diagnostics dump that the harness
returned as a 2 kB preview; `HIGH_CORRELATION` had to be grepped out. `refine.py:
1400-1401` (79e5ae82) extends the list per stage with no dedup; `check_guards`
(`staged.py:878-886`) has no cap.

**Nothing renders a result as text.** `gui/textdoc.py:render` takes a `Project` and
serves the GUI; `FitReport` has no text form; so every "print the numbers" script in
five runs was written from scratch, and four of the six campaign runs that refined
waited on a backgrounded job (one at 100 % CPU for 2 min 42 s with an empty log), under a
brief rule written after the harness killed an agent for one long blocking Bash call.

**Termination.** The package already states when a fit is done: `AGENT_PROTOCOL.md`
§10's three stop conditions (every diagnostic understood; Layer 1 attributes no region
above the gate; the next parameter group fails ΔBIC or trips a guard), §4b's rows per
deliverable, §10's "what to report" (values with inflated esds, unresolved diagnostics as
systematics, the protocol actually run, `provenance`). None of it reaches an agent in one
call: it is spread over `result`, `Refinement.report()`, `suggest`, `parameters()` and
two documents. Of the six campaign runs that refined, **none** stopped on those
conditions (one on an external comparison protocol, one on a driver exiting 0, one by
instruction, three ended waiting); `suggest` was called 0 times in 86 runs,
`plot_for_vlm` 0 times, `report()` twice; only the ramp run, primed with the protocol,
ran ΔBIC and a cold refit. Two meta-facts a bare `result` cannot state: `status` is the
last stage's (§7's `STAGE_MAX_ITER` row exists because agents read it as covering all),
and `parameters` carries only varied and tied rows, so the protocol run (held, fixed,
excluded) is not on it. The design rule (maintainer, 2026-08-28): numerical heuristics
first, visual ones accepted for a VLM as confirmation, never Rwp alone; a result view is
judged by whether an agent can decide "done or not, and why" from it alone. §4b's QPA
example is why the visual channel cannot be the criterion: an over-flexible background
wins on every index with a white-noise residual inside ±3σ, and only `worst_absorption`
separates the two fits.

### Seams (line numbers at 79e5ae82; re-read on arrival)

- `src/rietx/schemas/common.py:87-99` `Base`: add `__getattr__` built from
  `results.py:699-721` `_nested_field_paths` (moved here) plus
  `difflib.get_close_matches(name, model_fields, n=3, cutoff=0.6)`; when the model has
  ≤ 12 fields and nothing matches, list them. Delegate to `super().__getattr__` first,
  skip `_` names, keep it a **pointer, not an alias** (`tests/test_schemas.py:230-250`
  pins `not hasattr(result, "rwp")`, deepcopy, pickle, JSON). `RefinementResult` keeps
  its `result.` prefix via a class attribute the base reads (`tests/test_schemas.py:
  204-227` pins the exact `result.statistics.rwp` strings).
- `src/rietx/strategy/staged.py:126-130, 189-193`: the bare `AttributeError(name)`
  branch gets the same closest-match over `dataclasses.fields`, listing the nine `Stage`
  fields (`Stage.free` → "its fields are …; what a stage freed is `StageResult.freed`").
- `src/rietx/__init__.py`: re-export every public `schemas.*` class (the list derived,
  not typed: `tests/api_surface.py` already knows the public surface) and a module-level
  `__getattr__` (PEP 562) answering any other name with the closest match and the
  submodule it lives in (`rietx.viz`; `identify_format` → `io.readers.PATTERN_FORMATS`).
- Docstrings: `schemas/pattern.py:11` first line names `tt()`, `y()`, `sig()` and says
  the fields are lists for JSON; `Statistics`, `SeriesEntry`, `UnmatchedPeak`
  (`report/schemas.py:440`) one-liners naming their neighbours (`n_iterations` is on
  `SeriesEntry`, not `Statistics`); then the files listed above, in that order.
- `HIGH_CORRELATION`: deduplicate across stages by `frozenset(where)`, keeping the worst
  |ρ| and naming the stages in the message; cap at `HIGH_CORRELATION_MAX = 10` per fit
  ordered by |ρ|, with one `HIGH_CORRELATION_OMITTED` (info, `value` = count,
  `suggestion` pointing at `result.identifiability` and the correlation matrix). A new
  code needs its protocol/skill row and `help.py` entry (`tests/test_help.py`,
  `test_every_engine_diagnostic_code_has_a_protocol_row`).
- `progress=` on `fit` / `refine_sequential`: a text stream or path; one line per stage
  boundary and per pattern (`[series 7/13] 250 °C stage cell converged Rwp 0.081 12 s`);
  implemented as an `events=` consumer (`history/events.py` is the one telemetry; `watch`
  is the other renderer), never a second one.
- The termination view, in this order, numbers before agreement indices:
  1. Per-stage status with each stage's `ftol` and `n_iterations`; `max_shift_over_esd`
     (McCusker §7's convergence number) for the last stage.
  2. The three stop conditions as three lines with their state: (a) diagnostics, `n`
     unresolved, each as `LEVEL CODE: message` + `suggestion` (capped as above); (b) the
     report's `summary` sentence, `abstained_kind` if set, the worst regions by χ² share
     with `max_abs_delta_over_sigma`, the `unmatched_obs` count, `durbin_watson` read out
     as the serial-correlation measure with `esd_inflation` as its consequence (the
     numeric form of "the difference curve is flat within ±3σ"); (c) the next group's
     predicted ΔBIC from `suggest` (WP-1305 b) as "next: free X, ΔBIC −12" or "nothing
     left that ΔBIC admits"; until 1305 lands, "run `suggest`".
  3. The deliverable's rows, selected by `summary(deliverable="phase_id" | "qpa" |
     "structure" | "series")`: §4b's deciding rows for that purpose only (`unmatched_obs`
     + `lebail_gap` ratio; `background.absorption` worst entry + fractions with esds;
     `identifiability.exchanges`; the series rows of 1305 a). The protocol's own
     sentence is that the report will not infer the purpose; the argument declares it.
     Default `None` prints the three conditions only.
  4. The protocol actually run: plan name and stage list, every held path grouped by
     reason (`mode_fixed`, symmetry-locked, user-fixed, 1301's `held`), excluded ranges,
     N points against N reflections and `data_support`'s effective observations, σ source
     (file or Poisson), `provenance` (version, backend, solver).
  5. Agreement indices last, one line: Rwp beside Rexp (their ratio is GoF), Rp, χ², DW.
  6. The visual check named, never substituted: `plot_for_vlm(result, report, path=…)`
     draws these same regions with their numbers in the panel titles; `summary(plot=
     "fit.png")` writes it and prints the path, so text and picture show the same
     regions. The picture confirms the text; the text is the criterion (§5).
  Homes: `Refinement.summary()` (holds the model, so Layer 1 and `suggest` are
  reachable); `RefinementResult.__str__` (rows 1, 2a, 4's provenance, 5: what a bare
  result knows); `SeriesResult.__str__` / `.summary()` (trajectory table, the
  `SEQUENTIAL_*` rows, first and last N entries with the count). A projection of fields
  the objects already carry, never a re-derivation.

## Non-goals

Making `PatternData` fields arrays (JSON round-trip). Import-time work: measured
2026-08-28 at ≤ 0.4 s per process (`scipy.signal` through `indexing → report`), ≈ 1 min
of an 81-min campaign; declined. Folding `FitReport` into `str(result)` (Layer 0 needs
the model; the summary lives on `Refinement`).

## Tasks

- [x] `Base.__getattr__` + meta-test over every `Base` subclass (recursive
      `__subclasses__`) that deepcopy, pickle, `model_copy`, `validate_assignment` and
      `model_dump` round-trip still hold.
- [x] The closest-match on the two dataclasses.
- [x] The re-exports and the package-level `__getattr__` + the `__all__` meta-test
      (every `rx.X` in the manual's Part 1 is in `__all__`).
- [x] Docstring lines on the files above.
- [x] `HIGH_CORRELATION` dedup + cap + the new code's rows; GUI diagnostics strip
      unaffected (`npm --prefix gui test`).
- [x] `progress=` on `fit`/`refine_sequential` + a test that every line's numbers equal
      the event's fields.
- [x] `RefinementResult.__str__`, `Refinement.summary(deliverable=…, plot=…)`,
      `SeriesResult` + tests + a golden text on 11-BM NAC that changes only when a field
      does.
- [x] Measure: rerun the ramp's call 31 output size (40 kB → ?) and its four print
      scripts against `print(result)`; record both in the handover.
- [x] Docs: `using/results.md` § diagnostics, § printing, § progress; the quickstart
      prints the summary.
- [x] Tests + obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_schemas.py tests/test_help.py tests/test_docs_consistency.py tests/test_manual_api.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

A five-stage plan with one persistently correlated pair yields one `HIGH_CORRELATION`;
every message asserted by substring, never by equality with a sentence; `str(result)`
under 80 lines and `Refinement.summary(deliverable="qpa")` under 120 on 11-BM NAC; the
three stop-condition lines present on every fit, including one with no diagnostics at
all; a progress line per stage.

## References

- McCusker et al. (1999), *J. Appl. Cryst.* **32**, 36-50, §7 (max shift/esd) and §9.
- `AGENT_PROTOCOL.md` §4, §4b, §5, §10 (the stop conditions and "what to report").
- The audit and the campaign bundle: maintainer memories `agent-surface-audit-insitu-ramp`,
  `termination-view-design-rule`; `~/rietx-agent-runs/`.

## Handover log

- **2026-08-29** — Shipped. Every wrong name the two campaigns actually hit now answers
  with the right one, a fit's diagnostics list cannot grow without bound, a caller can
  watch a long fit without polling, and `print(result)` / `ref.summary()` answer "done or
  not, and why" in one call instead of the four to seven ad-hoc scripts an agent
  previously had to write by hand. Nothing about the physics changed; every number a
  converged fit produces is bit-identical to before this WP.

  **Done, in commit order:** `Base.__getattr__` (`schemas/common.py`) — a nested-block
  hint, a `difflib` closest match, a field listing for a small schema, and a distinct
  "declared but never given a value" case a meta-test over all 134 `Base` subclasses
  surfaced (a model validator probing a sibling mid-`validate_assignment` was getting a
  nonsensical "did you mean X" pointing at X itself). `Stage`/`RefinementPlan`'s own
  bare-`AttributeError` branch gets the same treatment by hand, plus one named
  cross-class hint (`Stage.free` → `StageResult.freed`). Every public `rietx.schemas.*`
  class is now a top-level export, derived by walking the submodules rather than typed
  into `__init__.py` (`Source`, `EmissionLine`, `BackgroundChebyshev`, `Geometry`, … were
  named throughout the manual unqualified while unimportable); a package-level
  `__getattr__` lazily imports a public submodule on first touch (`rx.viz` now just
  works) and otherwise gives a closest match or one named pointer
  (`identify_format` → `io.readers.PATTERN_FORMATS`). Docstring lines on the objects the
  campaigns actually opened source for, saying how to get numbers out or that the object
  is a declaration rather than a result. `HIGH_CORRELATION` is deduplicated across a
  plan's stages (worst |ρ| kept, every firing stage named) and capped at 10 per fit with
  one `HIGH_CORRELATION_OMITTED` marker — `check_guards`'s own per-stage list, the
  `StageReport`/history-node trail, is untouched; only the fit's final diagnostics list is
  filtered. `progress=` on `fit`/`refine_sequential` writes one text line per stage
  boundary (per pattern under a series), implemented as an `events=` subscriber that adds
  rather than replaces a caller's own; `stage_end` gained an additive `rwp` field, paid
  for only when `events` is requested. The termination view: `RefinementResult.__str__`
  (stages, diagnostics, provenance, agreement indices — what a bare result knows),
  `Refinement.summary(deliverable=, plot=)` (the full six-section view, gated by the
  compiled model), `SeriesResult.__str__`/`.summary()` (the trajectory table, truncated
  past 2×N entries). `using/results.md` gained the § diagnostics paragraph, § printing,
  § progress; the quickstart prints `result` instead of two hand-picked fields.

  **Measured** (`[dev]` venv, darwin/arm64, this session alone on the machine): fast
  selection 3427 passed, 122 skipped, final. This session added 170 items to that
  selection — 36 new `def test_`, two parametrized (`Base.__getattr__`'s meta-test over
  134 subclasses, `summary(deliverable=)` over 3 cases) — plus one slow-only test
  (11-BM NAC's golden shape) outside the fast selection entirely; no test this session
  added skips, so passed+skipped moved by exactly 170 in the fast selection (counted from
  the diff, not from memory of intermediate runs — the honest way round when a session
  did not capture a pre-change baseline at its own start). Full selection, on the tree
  with the code-review fixes below already landed: 3578 passed, 131 skipped (+4 against
  the pre-review-pass run, exactly the four new regression tests those fixes added; wall
  clock not quoted — root CLAUDE.md is explicit that a single unrepeated reading is a
  record, not a range) — quoted because HIGH_CORRELATION's dedup and the new event field
  are the kind of change root CLAUDE.md's rule means; `origin/main` had not
  moved since this worktree branched (`git fetch origin main`, checked twice — once
  before this run and again immediately before it, per step 10's own rule:
  `HEAD..origin/main` empty), so this figure is already the merged tree's, not only the
  branch's. The ramp campaign's call 30 (its `show()`
  loop over one Bragg-Brentano fit, `~/rietx-agent-runs/2026-08-26-insitu-ramp/`,
  `tool-results/b2m2vntea.txt`) printed a 35.2 kB diagnostics dump the harness truncated
  to a 2 kB preview — that fit had more than 10 correlated background coefficients, no
  cap. The identical `show()` script against today's code: 3519 bytes, 11 diagnostics (10
  `HIGH_CORRELATION` + 1 `HIGH_CORRELATION_OMITTED`) — a 10× reduction from the dedup/cap
  alone, before counting that `print(result)` on the same fit is smaller still (3090
  bytes, 22 lines) while carrying more (provenance, per-stage status). The campaign wrote
  at least 18 distinct print/analysis scripts across its 91 calls (`lib.py`'s `show()`,
  `analyse.py`, `final_numbers.py`, … — counted by `cat > work/*.py` blocks containing
  `print(`); representative ones each re-implemented statistics/diagnostics printing that
  `str(result)`/`summary()` now provide natively. `str(result)` on 11-BM NAC: 12 lines;
  `ref.summary(deliverable="qpa")`: 28 lines — both comfortably under the 80/120 bars,
  frozen (masked) as `tests/data/nac_termination_golden.txt`.

  **`/code-review medium` found 8, all fixed, none declined.** The one worth flagging past
  its own commit message: the `HIGH_CORRELATION` cap was originally applied to
  `RefinementResult.diagnostics` itself, which silently broke
  `sequential._persistent_diagnostics`'s cross-pattern "N of M" count for any pair ranked
  outside the top ten in every single pattern — the cap now lives in `_diagnostic_lines`
  (render time) only, dedup stays on the stored list. The other seven: a progress line's
  elapsed time on a WP-1301 release/re-solve was measuring only the second solve; a held
  parameter blocked because its cell is free was landing in an unlabelled "other" bucket;
  `Diagnostic.where` could come back in the opposite order from the one its own `message`
  named (a `frozenset` iterated for the rebuild); `hasattr(rx, "viz")` could crash rather
  than answer `False` on a build without the `viz` extra; the `stage_end` rwp computation
  priced every stage boundary at two background passes instead of one; this entry's own
  wall-clock figure was quoted as a bare reading against root CLAUDE.md's own rule; and
  `SeriesResult.summary()` had a second inline copy of `_diagnostic_lines`'s rendering
  loop. Four new regression tests landed with the fixes; the NAC golden text was
  regenerated (the held-bucket rename is its only visible change, confirmed against a
  live fit).

  **Gotchas for the next session.** `multi.py`'s (`MultiHistogramRefinement`) own
  diagnostics accumulation loop is a
  *separate* one from `refine.py`'s `_run_plan`/`run_stage` and was **not** touched — a
  joint multi-histogram fit can still grow an unbounded `HIGH_CORRELATION` list. Not
  named in the WP's seam text, so left alone rather than guessed at; worth a line item if
  anyone hits it. `Refinement.summary()`'s `deliverable="series"` and stop-condition (c)
  are both stubs pending WP-1305 (pushed to that WP's `### Inherited`, naming the exact
  methods and files). No `run_stage()` counterpart to `progress=`/`summary()` — both are
  scoped to `fit()`/the plan-based path, matching the WP's own "on fit / refine_sequential"
  wording; `run_stage()` still gets the `HIGH_CORRELATION` cap (via `_cap_high_correlation`
  at its own diagnostics assembly point) but not dedup, since a single stage has nothing to
  dedup across. `[jax,torch]` extras were not installed in this worktree's venv — every
  count above is `[dev]` only; a session that needs the jax/torch rows should install them
  first (`tests/CLAUDE.md` § Quoting numbers).

  Next: WP-1303 (retire `refine_json` and the schema export) — no dependency on this WP,
  the next unblocked item in the v1.3 index.

- **2026-08-28** — created, from the parked v1.3 plan.
