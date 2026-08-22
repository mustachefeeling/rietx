# WP-1125 — variable-projection probe: profile the background, measure the tail

Milestone: v1.1 · Status: ⬜
Depends on: WP-1113 (the mechanism this probe attacks), WP-1111 (counting
scaffold)

## Goal

A measured answer to one question: does solving the background block exactly
at every evaluation collapse the Gauss-Newton tail WP-1113 named — the
≈ 0.93/iteration ridge walk along the zero ↔ displacement ↔ background
degeneracy? The answer decides whether variable projection
(`docs/solver-survey.md` §2.A1, E5) has a speed half worth a milestone, or
stands on its correctness half alone. A probe: the deliverable is the verdict
and its numbers, and it closes ✅ on a clean negative exactly as WP-1114 did.

## Context

**The mechanism, measured (WP-1113).** Every expensive lab stage is an
ftol-bound Gauss-Newton tail: 93-98 % *accepted* steps decaying at a fixed
geometric ratio ≈ 0.93/iteration along the zero ↔ displacement ↔ background
degeneracy, with 37-52 % of accepted evaluations spent past the point where
99.99 % of the cost decrease is banked. The control: nac's partner-free
`zero` stage takes 5 evaluations. Baseline stage counts on the named stages:
cpd-1a `zero_disp` 84 / `cell` 86, cpd-2 `zero_disp` 93 / `cell` 131.
WP-1123 harvested 1.5-1.7× by stopping intermediate stages at ftol 1e-6
(cpd-1a 408 → 270 whole-plan nfev, cpd-2 533 → 329, trigger 360 → 232); the
final stage still runs at the solver's 1e-9 and inherits the ridge walk once
(cpd-1a `biso` 47 → 49 evaluations under the schedule, 95 at 1e-4).

**Why variable projection aims at exactly this.** One leg of the degeneracy
is the linear block. The background is linear in its parameters and already
isolated as such — `CompiledModel.bkg_design`, `(len(bkg_paths), n_points)`,
frozen at stage compile, evaluated as `coeffs @ bkg_design`
(`model/forward.py`) — and the P-spline penalty rows make the conditional
solve a ridge regression, still linear (`model/rows.py`'s
`background-penalty` block). Profiling the block out means every nonlinear
step sees the background at its conditional optimum, so the ridge leg of the
walk is gone *by construction*, not by better stepping. The survey motivated
VarPro by Pawley dimension and Le Bail esd honesty; WP-1113's measurement is
a third motivation it could not have had. The projector itself already
exists in the codebase as a diagnostic
(`optimize.statistics.background_absorption`), and the survey's §1.1b scan
re-optimised the linear block per grid point (241 points, 44 s, old tree) —
the probe is that construction driven by the solver instead of a grid.

**Probe scope: background only, deliberately.** Phase scales are also linear
but non-negative (softplus-transformed), so profiling them needs an
NNLS inner solve and active-set projector derivatives — the survey's own
caveat, and the landing WP's business. The named mechanism runs through the
background, so the probe stays unconstrained-linear + ridge and dodges all
of it.

**Probe form.** A wrapper residual `r̃(θ_nl)`: at each evaluation, solve the
weighted ridge for the background coefficients (design + penalty rows,
weights from the compiled `pattern.sig()`), and return the residual
assembled at that conditional solution — data rows *and* penalty rows both
evaluated at c\*(θ), so the profiled cost is the joint objective minimised
over c and the two are directly comparable. Drive it with scipy
`least_squares`. The derivative can be plain FD over the nonlinear set — a
count probe does not need the Kaufman/Golub-Pereyra dI\*/dθ term to be
cheap, only to converge — but FD inflates raw nfev mechanically, so:

**The metrics are outer iterations, the accepted-step decay ratio, and the
tail fraction — never nfev and never wall clock.** WP-1113's instrumentation
carries all three (`eval.accepted`/`step_norm`/`values`,
`stage_end.termination`; `examples/stage_trajectory.py` prints and plots
them). Wall clock is meaningless on a probe paying FD prices for analytic
work. Counts also survive a busy machine where wall clock does not — WP-1124
read the same chain at 35.8 s and 42.9 s minutes apart at an identical 1253
nfev — so **both arms run back to back in one process**
(`examples/bench_series_predictor.py` is the shape), and the WP-1111 counting
scaffold wraps scipy's entry point, so any evaluation the wrapper spends
outside it is added by hand or it is invisible.

**Correctness gates before any count is quoted**, both from E5's
pre-registered verification and both cheap:

1. The profiled and joint stage endpoints agree within σ/10 on every shared
   parameter (E5 claim 1's bar).
2. At the joint endpoint, the joint fit's background coefficients equal the
   conditional weighted ridge solution to machine precision (E5 claim 2's
   bar, background half) — this is an identity, and failing it means the
   wrapper solved a different problem.

**The bar the verdict is judged against is the flipped schedule, not the old
baseline.** WP-1123 already banked 1.5-1.7×; a profiled stage must beat the
`intermediate_ftol = 1e-6` counts, beyond run-to-run spread, or the speed
half is dead. Amdahl context for the ceiling: the cold trigger fit is
5.67-5.70 s at 232 nfev on the current tree, and per-evaluation cost is near
its floor (WP-1112/1115/1120), so count converts to wall nearly linearly —
but the count left to win is what the schedule left behind, chiefly the
final stage. That conversion factor is what the compiled tier changes, so
**check the venv is current before quoting any timing**:
`rietx.model.compiled.enabled()` is the check and `rietx.__version__`
disagreeing with `pyproject.version` is the tell (WP-1124 opened on a venv
that predated WP-1115, with the tier silently off).

## Non-goals

Shipping VarPro (milestone-sized: Kaufman derivative, NNLS scales, the
Pawley/Le Bail unification and the E5.3 coverage study — all the landing
WP's, opened only on a go verdict); touching `run_least_squares` or any
shipped code path; Anderson acceleration for `lebail_update` (survey B7 —
subsumed by A1, and out of scope either way); any Rwp-judged claim.

## Tasks

- [x] **The wrapper**: profiled residual + weighted ridge inner solve as a
      probe script beside `examples/stage_trajectory.py`, gated by the two
      correctness checks above before anything is counted.
      `examples/probe_varpro.py`; it grew a third gate (below).
- [ ] **The named stages**: cpd-1a/cpd-2 `zero_disp` and `cell`, profiled
      against joint, at both schedules (`intermediate_ftol` default and
      `None`) — outer iterations, decay ratio, tail fraction per stage.
- [ ] **The final stage**: does the profiled final stage shed the inherited
      ridge walk (cpd-1a `biso` 47 → 49 under the schedule) or inherit it
      through the nonlinear pair anyway? This is the count 1123 could not
      reach, and the most likely place a real win lives.
- [ ] **Verdict** in § Findings, and the survey annotated: speed half alive
      — open the landing WP with the measured ceiling — or dead, recorded in
      `docs/solver-survey.md` §2.A1/E5's dated notes, with E5 standing on
      correctness alone thereafter.

## Acceptance

The verdict is recorded with its per-stage table in § Findings, quoting venv
and platform per root CLAUDE.md § Numbers. Kill criterion, pre-registered:
if the profiled stages' outer-iteration counts are not materially below the
`intermediate_ftol = 1e-6` counts on the same stages (beyond run-to-run
spread), or either correctness gate fails, the speed half of E5 is dead —
record the bound and the survey note, and close. A probe's verdict can also
be decided by a clause that is not about speed: WP-1124 retired two arms
that *did* reduce evaluations, on what they changed about the answer. If
profiling changes what a fit converges to, that is the finding whatever the
count does.

```sh
.venv/bin/python examples/probe_varpro.py   # the per-stage table § Findings quotes
.venv/bin/python -m ruff check src tests examples
```

## References

- `docs/solver-survey.md` §2.A1 (the full VarPro case and its caveats), §1.1b
  (the profiled-objective scan this probe generalises), §5 (the 2026-08-22
  re-assessment that opened it).
- Golub & Pereyra (1973) *SIAM J. Numer. Anal.* 10, 413; Kaufman (1975)
  *BIT* 15, 49; Ruhe & Wedin (1980) *SIAM Rev.* 22, 318 — alternation
  converges linearly, VarPro quadratically, and the Kaufman derivative is
  the landing WP's cheap form.
- O'Leary & Rust (2013) *Comput. Optim. Appl.* 54, 579 — the modern
  implementation reference.
- WP-1113's § Findings — the mechanism, the instrumentation, and the
  schedule counts every row here is judged against.

## Handover log

- **2026-08-22** — created, from the solver-survey re-assessment (§5): the
  count mechanism WP-1113 measured runs along the degeneracy's linear leg,
  which variable projection removes by construction — a motivation the
  original survey entry could not have had.
