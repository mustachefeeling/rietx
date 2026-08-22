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
- [x] **The named stages**: cpd-1a/cpd-2 `zero_disp` and `cell`, profiled
      against joint, at both schedules (`intermediate_ftol` default and
      `None`) — outer iterations, decay ratio, tail fraction per stage.
      **All twelve rows are 1.00×**, decay ratio equal to three decimals;
      widened to nac, nac-lebail and trigger, which say the same.
- [x] **The final stage**: does the profiled final stage shed the inherited
      ridge walk (cpd-1a `biso` 47 → 49 under the schedule) or inherit it
      through the nonlinear pair anyway? This is the count 1123 could not
      reach, and the most likely place a real win lives. **It inherits it**:
      the eight `biso` rows span 0.54-1.08×, median 0.94×.
- [x] **Verdict** in § Findings, and the survey annotated: speed half alive
      — open the landing WP with the measured ceiling — or dead, recorded in
      `docs/solver-survey.md` §2.A1/E5's dated notes, with E5 standing on
      correctness alone thereafter. **Dead**, on a mechanism rather than a
      bound.

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

## Findings

*Measured 2026-08-22 on `wp1125-varpro-probe` at `c927b7f7`, venv `[dev]`
only (no jax, no torch), numba 0.67.0 with the compiled tier **on**, numpy
2.5.2, python 3.12.12, macOS/arm64, 10 cores. 70 stages = 5 cases × 2
schedules. Counts are deterministic: two full runs of the acceptance command
are byte-identical.*

### Verdict — the speed half of A1/E5 is dead, and it is dead by identity

**Variable projection cannot reduce this package's evaluation count, because
the step it computes is the step the package already takes.** For an
unconstrained linear block the profiled Gauss-Newton step in the nonlinear
parameters is *the same vector* as the joint one — the Schur complement of
the joint normal matrix — and the equality holds at every point, not only at
the conditional optimum, because (I − P)·M = M − M·M⁺·M = 0 is a
Moore-Penrose identity: the projector annihilates the linear block's
contribution wherever its coefficients happen to sit.

Measured, as gate 3: the two unconstrained Gauss-Newton steps agree to
**≤ 6.6e-07 relative on all 70 stages** (most ≤ 1e-13), at start-identity
gaps spanning 4.5e-15 to 1.2e+03 — so the identity demonstrably does not
depend on the background being converged first.

The consequence is visible directly in the counts. **On the 34 stages where
TRF never rejected a step — where it therefore *took* the Gauss-Newton step —
the joint and profiled accepted-step counts are identical in 34 of 34.** That
includes every stage WP-1113 named:

| case | stage | sched | free | lin | joint acc | prof acc | gain | decay j | decay p |
|---|---|---|---|---|---|---|---|---|---|
| cpd-1a | zero_disp | 1e-6 | 11 | 6 | 39 | 39 | **1.00×** | 0.817 | 0.817 |
| cpd-1a | zero_disp | none | 11 | 6 | 84 | 84 | **1.00×** | 0.854 | 0.854 |
| cpd-1a | cell | 1e-6 | 16 | 6 | 45 | 45 | **1.00×** | 0.913 | 0.913 |
| cpd-1a | cell | none | 16 | 6 | 86 | 86 | **1.00×** | 0.814 | 0.814 |
| cpd-2 | zero_disp | 1e-6 | 12 | 6 | 41 | 41 | **1.00×** | 0.824 | 0.824 |
| cpd-2 | zero_disp | none | 12 | 6 | 93 | 93 | **1.00×** | 0.873 | 0.873 |
| cpd-2 | cell | 1e-6 | 19 | 6 | 86 | 86 | **1.00×** | 0.891 | 0.891 |
| cpd-2 | cell | none | 19 | 6 | 131 | 131 | **1.00×** | 0.858 | 0.858 |
| nac | cell | 1e-6 / none | 11 | 6 | 9 / 13 | 9 / 13 | **1.00×** | 0.140 | 0.140 |
| trigger | zero_disp | 1e-6 / none | 12 | 6 | 8 / 10 | 8 / 10 | **1.00×** | 0.016 | 0.016 |
| trigger | cell | 1e-6 / none | 22 | 6 | 8 / 10 | 8 / 10 | **1.00×** | 0.099 | 0.098 |

The `none` column reproduces WP-1113's baselines exactly (cpd-1a `zero_disp`
84 / `cell` 86, cpd-2 93 / 131), which is an independent check that the probe
measures the fit it claims to. **The ridge walk is untouched — the decay
ratio is identical to three decimals in every row.** Its linear leg is not
the background; profiling the background out leaves the walk where it was.

Both pre-registered kill conditions fire, so the criterion is met twice over.

### Per-case counts — profiling is worse, not neutral

| case | sched | joint acc | profiled acc | gain | stages |
|---|---|---|---|---|---|
| cpd-1a | 1e-6 | 215 | 217 | 0.99× | 8 |
| cpd-1a | none | 339 | 341 | 0.99× | 8 |
| cpd-2 | 1e-6 | 254 | 272 | 0.93× | 9 |
| cpd-2 | none | 408 | 543 | 0.75× | 9 |
| nac | 1e-6 | 36 | 39 | 0.92× | 6 |
| nac | none | 44 | 47 | 0.94× | 6 |
| nac-lebail | 1e-6 | 44 | 40 | 1.10× | 4 |
| nac-lebail | none | 52 | 45 | 1.16× | 4 |
| trigger | 1e-6 | 190 | 138 | 1.38× | 8 |
| trigger | none | 287 | 683 | 0.42× | 8 |
| **all** | | **1869** | **2365** | **0.79×** | 70 |

The trigger's 1.38× and 0.42× are the same case one schedule apart, which is
what scatter looks like. Across the 36 stages where TRF *did* reject steps
the gain spans 0.03×-2.66× with **median 0.97×**.

### Why below 1.00× and not at it: TRF's radius is a norm over the variables

Where the arms differ at all it is the globaliser, not the method — and the
globaliser is made worse by profiling. scipy's TRF takes its initial trust
radius from ‖x0 / x_scale‖, and at the default `x_scale = 1.0` that is ‖x0‖.
Background coefficients are **counts**, order 10²-10³, while everything else
is a cell edge, an angle or a softplus internal of order 1, so the linear
block carries almost the entire norm: on the trigger's `profile` stage
‖x0‖ = 9.79e+02 of which the background is 9.79e+02, and removing it shrinks
the starting radius **59×**. Measured across the probe, profiling shrinks the
radius by 1.0×-59.0×, median 3.6×.

That stage is where the probe's worst row lives: at `intermediate_ftol=None`
the profiled arm accepted **400** steps against the joint arm's 13 — running
into `max_iter × NFEV_PER_ITERATION` — and finished **15.1 % higher in cost**,
7.85 esd from the joint answer, having rejected nothing and crawled at decay
0.993. Its Gauss-Newton step was still right to 2.5e-09.

This half of the explanation is a fact about the driver, not about variable
projection, and a landing WP could fight it with `x_scale`. It is recorded
because it is why the measured number is *below* neutral; it is not what
kills the idea. **The kill is the step identity, which caps the gain at
exactly 1.00× however well the globaliser is tuned.**

### The correctness gates

- **Gate 1 (agreement, E5 claim 1, ≤ 0.1 esd): fails on 10 of 70**, worst
  7.853 esd (trigger `profile`, `none`), then 0.449 (cpd-2 `lines_axial`).
  Every failure is a stage where TRF rejected steps, i.e. where the two arms'
  trust regions diverged — not a disagreement about the minimum.
- **Gate 2 (the conditional-solution identity, E5 claim 2's background half,
  ≤ 1e-9 relative): fails on 34 of 70**, worst 4.00e-03. This is not a defect
  in the identity but a measurement of the joint fit: an ftol-bound stage
  stops with its background up to 0.4 % away from its own conditional
  optimum. At the stages that converge properly it holds to 1e-12 to 1e-15.
- **Gate 3 (the mechanism, added by this session): holds on 70 of 70**,
  ≤ 6.6e-07.

### The one case profiling wins, and why it does not rescue the idea

A Le Bail seed stage frees *only* the background — `mode_fixed_path`
force-fixes the phase scale — so the nonlinear set is empty and the whole
stage **is** the inner solve. `nac-lebail/bkg` therefore goes from 9 accepted
steps to **one exact solve**, at both schedules: a real 9× on that stage,
worth 8 of the 53-61 accepted steps the Le Bail leg spends. It is reported
as its own row and **excluded from the per-case totals above**, which is why
nac-lebail's 1.10-1.16× is not it — that comes entirely from `profile`
(18 → 14 and 20 → 13), one more sample of the same scatter.

A stage that is all-linear does not need variable projection to exploit it:
it needs the runner to notice that every free parameter is linear and solve
it directly. That is a much smaller idea than A1, it is unscheduled, and
before it is worth anything someone should check how many real plans have
such a stage — in this harness exactly one of 70 did.

### What this does and does not settle

Dead: **the count half of A1/E5, for any unconstrained linear block solved
jointly by Gauss-Newton.** Ruhe & Wedin's "alternation converges linearly,
VarPro quadratically" compares VarPro against **alternation**, and this
package does not alternate — the background is an ordinary column of θ that
TRF solves jointly. Against joint Gauss-Newton, VarPro is the same algorithm.

Untouched, and the boundary of the result:

- **The correctness half** (Le Bail esds, derived equal-splitting, the E5.3
  coverage study). The step identity says nothing about the *covariance*: the
  VarPro normal matrix is still the Schur complement, so structural esds
  still emerge marginalised over the background rather than conditional on
  it. That claim is unmeasured and stays the deeper prize.
- **The Pawley dimension claim** (550 parameters → ~20). That is per-step
  *linear algebra*, not evaluation count, and 550 stored columns are not the
  6 near-free background design rows this probe removed. It survives, and it
  is a different measurement from this one.
- **Bounded linear blocks.** The identity holds while no bound is active.
  Pawley intensities and phase scales are non-negative, so a landing WP
  building on them cannot quote gate 3 — it needs the active-set argument the
  survey's own caveat names.

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
