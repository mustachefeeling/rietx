# WP-1302 — The error is the documentation; the output is bounded; the result is a termination view

Milestone: v1.3 · Status: ⬜
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

### Inherited

**From [1017](1017-gui-manual-onboarding.md), 2026-08-28 — the GUI is
documented now, and part of it is held to the app by test.** Two things for a
WP that adds a diagnostic code and touches the GUI's diagnostics strip. First,
the mechanical half: `tests/test_gui_manual.py` partitions the **routes** and
the **panel names**, both ways, so a new route or a renamed tab fails until a
chapter covers it — if this WP adds a route for the progress sink or the
exports, `docs/manual/using/gui-power.md`'s route table is where it goes, and
the test names it for you. Second, the half no test covers: `gui-guide.md` now
describes the Report panel in prose, including that a suggestion with no Apply
button is advice rather than a broken control and that the predicted Δχ² is one
number for the whole report. A change to what that panel *says* can make those
sentences wrong without failing anything, so read that section before changing
the strip. Screenshots are generated by `docs/manual/make_screenshots.py`
(`report-light.png`/`-dark.png` is the Report panel), so a visible change there
means re-running it rather than editing a picture.

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
- [ ] Measure: rerun the ramp's call 31 output size (40 kB → ?) and its four print
      scripts against `print(result)`; record both in the handover.
- [x] Docs: `using/results.md` § diagnostics, § printing, § progress; the quickstart
      prints the summary.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`.

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

- **2026-08-28** — created, from the parked v1.3 plan.
