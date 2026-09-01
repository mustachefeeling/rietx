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
