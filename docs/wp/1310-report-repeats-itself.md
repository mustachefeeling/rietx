# WP-1310 — the report repeats itself: stage dedup, the declared wavelength, the empty column

Milestone: unscheduled · Status: ⬜
Depends on: —

## Goal

Three defects where a surface reads as an answer and is not are fixed: a
result's diagnostics no longer restate one finding per stage, the
`WAVELENGTH_CALIBRATION` number is measured against a wavelength somebody
actually declared, and `to_table`/`write_csv` answers a derived path with the
curve or a refusal — never a well-formed empty column.

## Context

Three issues, one class: the repo's rules are strictest about a silent wrong
answer, and each of these is one (issues #106, #123, #162).

**1. Per-stage diagnostics repeat (issue #106).** A real two-phase lab
refinement (YBaCo₄O₇, 4787 points, 31 free parameters, staged plan) returned
**96 `HIGH_CORRELATION` diagnostics for 16 distinct pairs** — each re-emitted
2–7 times as the plan advanced, 14 of 16 with the identical ρ to three
decimals, so ~83 % of the payload is redundant. The two entries that matter
sit at the tail where a context-budgeted consumer truncates:
`axial_sl ~ axial_hl` at ρ = −1.000 (twice, last stages) and the single
`STAGE_MAX_ITER` saying the `roughness` stage stopped on its budget — both
ranked below 90-odd restatements that a Chebyshev basis is internally
correlated, which is true before the fit starts. Three fix shapes, in the
issue's own ranking of how much each assumes:
(1) dedup by `paths` on the way out (one-liner; loses the per-stage
trajectory the history nodes hold anyway — and **forecloses 3**);
(2) findings live on the stage, the result carries the union — matches
[1058](1058-report-delivery.md)'s design, where the trajectory is already
opt-in;
(3) rank rather than dedup — a basis self-correlation is not a ρ = 1.000
degeneracy between two physical aberrations
(`GuardReport.measured_top_correlations` is the evidence channel).
Lean: implement (2), then measure whether (3) is still needed on the same
fixture — the issue deliberately left the "what does high mean" judgement to
the maintainer, so the session decides on the measurement, not by taste.
The flat-direction half of the aside (ρ = ±1.000 is a rank statement, not a
correlation) is [1311](1311-walking-parameter-bounds.md)'s item, not this
WP's.

**2. The declared wavelength is per-call (issue #123, maintainer-filed).**
On the single-histogram path the "declared" λ is snapshotted per call (`fit`
and `run_stage` each snapshot on entry), and a stage writes the refined λ
back onto the instrument — so the next call measures against the previous
call's answer. Measured (LaB6, cell held, λ declared 400 ppm low): run 1
reports +417.05 ppm "refined from the declared 1.539984 Å"; run 2 reports
−18.15 ppm "from the declared 1.540626 Å" — **a value nobody declared**.
`multi.py` snapshots at construction, so the two paths disagree; `run_stage`
is the GUI's verb, so the per-call framing is its normal mode; and the
protocol row tells the reader to compare the number against the beamline's
known drift, for which a per-call delta is the wrong quantity. Fix chosen
here: **snapshot at construction**, as `multi.py` does, with
`_declared_wavelengths` (`refine.py`) the one authority — `multi.py`
currently open-codes the same comprehension. The cost is `checkout`
semantics (after moving to an earlier node the reported move is against a λ
that branch never had): state it in
`_wavelength_calibration_diagnostics`' docstring rather than smoothing it.

**3. `to_table`/`write_csv` is a second path resolver (issue #162).**
`SeriesResult.to_table` calls `SeriesEntry.value(path)`, which scans
`self.parameters` and returns `None` for anything not a refined parameter —
so `to_table(paths=["r_bragg.LaB6"])` yields the header
`['r_bragg.LaB6', 'r_bragg.LaB6_esd']` over rows of `None`. `qpa.` behaves
identically and always has. `resolve_trajectory` is documented as "the one
authority for turning a display path into a curve" and already serves
`plot_trajectory` and `gui/series.py`; this path just does not go through
it. Fix chosen (the issue's option 1, its author's lean): route through
`resolve_trajectory`, and emit **no `_esd` column for kinds that have none**
— an agreement index has `stderr = None` by design, and a column of blanks
invites exactly the "zero or absent?" ambiguity the trajectory work avoided.
The class is [1076](1076-result-row-honesty.md)'s: a declared shape whose
empty state reads as an answer.

### Inherited

- **2026-09-03, from the issue triage (issue #231): a fourth defect of the
  same class, on the same seam — `BOUND_HIT` from an early stage is reported
  verbatim on the converged result, where the parameter is nowhere near a
  bound.** The guard is generated while a stage runs; when a later stage moves
  the parameter off the bound — the normal, desired outcome of a staged plan —
  the warning survives and describes a state that no longer exists, with the
  message *"<path> refined to its bound"* and the suggestion *"widen the bound
  or fix the parameter"*, both false of the converged fit.

  Reproduced synthetically on the repo's own `make_lab6`, cell seeded 0.5 %
  large so stage 1 (only `zero_shift` free) drives the shift onto its ±0.02°
  bound absorbing a cell error, stage 2 frees the cell and it returns:

  | | `zero_shift` | `a` | `BOUND_HIT` |
  |---|---|---|---|
  | stop after `zero` | +0.020000° (100 % of bound) | fixed | True |
  | then free the cell | +0.000001° (0 % of bound) | 4.156600227 | **True** |

  The second row is a **fully successful fit** — truth is `a = 4.15660`,
  `zero_shift = 0` — carrying a warning about a limit it is five orders of
  magnitude from. `BOUND_HIT_RTOL = 1e-10` (`strategy/staged.py:1008`) is
  **not** implicated: the tolerance is right and `bound_findings` is right for
  the vector it is handed. The defect is *which vector reaches the final
  diagnostics list*, which is this WP's dedup seam.

  **It is convincing, which is why it is more than cosmetic.** Two independent
  readers built confident wrong physical mechanisms on one before checking the
  parameter's own value: on a real capillary synchrotron fit `BOUND_HIT` fired
  on `capillary_offset_along_beam` in five of five fits, read as the specimen
  offset being pinned and load-bearing and therefore the absolute cell values
  untrustworthy; the second hypothesis was that the ±1 mm default
  (`schemas/instrument.py:788`) is too tight for that instrument, with seven
  GSAS-II refinements of the same specimens carrying 1.2–4.5 mm equivalents as
  circumstantial support. **One experiment killed both**: re-running at ±1, ±5
  and ±20 mm gave results bit-identical to six significant figures (same cell,
  same sigma, same Rwp), the offset converging at 3.3 % of the ±1 mm bound on
  the *opposite side of zero* from the bound hit in an early stage. The genuine
  finding in that fit was the `HIGH_CORRELATION` beside it, which *is*
  evaluated at convergence and *is* real; the bound warning cost two rounds of
  misdirected analysis.

  Three fixes, ranked by the reporter, and the first two are this WP's:
  **(1) re-evaluate the guards on the converged vector** before building the
  final diagnostics list, so the final list means exactly "true at
  convergence" — a parameter genuinely at a bound at the end still reports;
  **(2) carry the stage identity** on the finding and distinguish "hit during
  stage N, resolved by convergence" from "at bound at convergence" — a
  transient excursion is a useful signal about plan ordering even when it
  resolves, but this is a design call rather than a fix; **(3) add
  `diagnostics` to `StageResult`**, which today carries `name, status,
  n_iterations, cost_initial, cost_final, freed, ftol,
  n_constraint_truncations, held, released` and no diagnostics, so the
  aggregated list on `RefinementResult` is the only view and it is undated.
  (1) and (3) are complementary and the reporter offers a PR for either.
  WP-1076's rule applies to (3): a declared field needs its writer named at
  review, and `staged.bound_findings` stays the one bound test feeding both
  surfaces, pinned set-equal rather than re-derived.

  Related and *not* this WP: `status == "converged"` on a fit whose diagnostics
  say `MODEL_FAR_FROM_DATA` is
  [1336](1336-the-fit-does-not-say-it-is-unusable.md).

- **From the roadmap reorder, 2026-09-01 (issue #211)**: a fourth member of
  this WP's class — a surface that reads as an answer and is not. A stage's
  `turn_on` glob frees a parameter the caller pinned with `vary=False`
  (`ParameterTable.set_vary` cannot tell a deliberate pin from a default,
  and `apply_to_models` writes the value back but never `vary`), so the
  value moves while `Parameter.vary` still reads `False`. WP-1208's rule
  already says a plan *replaces* the vary flags rather than continuing them,
  so the defect is the record, not the precedence: which declaration won
  has to be said (a diagnostic naming the pinned paths the plan freed, and
  `vary` written back or reported per stage). Measured cost in the issue:
  an invalidated pin-and-scan study, and it is the failure mode of
  calibrate-on-a-certified-standard.

## Non-goals

- **Not #166's esd notation** — the maintainer ruled it not worth a figure
  regeneration now; it rides whichever change next touches
  `make_figures.py`.
- **Not new diagnostics** — flat-direction reporting and the walking-
  parameter flags are [1311](1311-walking-parameter-bounds.md)'s.
- **Not a change to what a fit computes.** Every fix here is about what
  crosses the surface, and every accepted number stays bit-identical.

## Tasks

- [ ] Stage-local findings with the union on the result (shape 2), measured
      on the #106 fixture against shape 3; the decision and its numbers in
      the handover.
- [ ] `_declared_wavelengths` snapshots at construction on both paths;
      `multi.py` imports it instead of open-coding; the checkout caveat in
      the docstring; message wording re-checked against the skill's
      `WAVELENGTH_CALIBRATION` row.
- [ ] `to_table`/`write_csv` through `resolve_trajectory`; `_esd` columns
      suppressed where `stderr` is `None`; a derived path that
      `resolve_trajectory` cannot serve refuses by name.
- [ ] Tests: a two-stage fixture asserting the result carries each pair
      once; a two-call λ fixture asserting the baseline never moves; a
      `to_table` case per trajectory kind + skill/manual rows touched by any
      wording change.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_fitreport_layers.py tests/test_acceptance_wavelength.py tests/test_sequential.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: on the #106 fixture the result carries 16 correlation findings, not
96, with the ρ = −1.000 pair and `STAGE_MAX_ITER` surviving any truncation
that keeps 16; a second `run_stage` reports its move against the constructed
λ; `to_table` on a derived path returns numbers or a refusal, never `None`
rows. All accepted fit values bit-identical throughout.

The shipping PR carries `Closes #106`, `Closes #123`, `Closes #162`.

## References

- Issues #106, #123, #162 — measurements and fix-shape analyses.
- [1058](1058-report-delivery.md) — stage reports as the opt-in trajectory;
  [1076](1076-result-row-honesty.md) — the declared-name class.
- `docs/skill/rietx/` — the `WAVELENGTH_CALIBRATION` row whose reading this
  must match.

## Handover log

- **2026-09-01** — created, from issues #106/#123/#162 (2026-09-01 triage).
  Settled: fix shapes chosen as above (stage-union, construction snapshot,
  resolver routing); first open item is measuring shape 2 against shape 3 on
  the #106 fixture before touching ranking.
