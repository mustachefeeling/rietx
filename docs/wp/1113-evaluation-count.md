# WP-1113 — evaluation count: name the mechanism, then attack it

Milestone: v1.1 · Status: 🔄 2026-08-21
Depends on: 1111 (soft — its iteration columns are this WP's before/after)

## Goal

The number of residual/Jacobian evaluations a staged fit spends is explained
by a *named, measured mechanism* per expensive stage — not accepted as "real
work" — and whatever reductions survive measurement are landed. Separately,
the in-tree bounded-LM driver's convergence to a worse minimum on a shipped
acceptance case is understood and either fixed or fenced with a reason.

## Context

All numbers from WP-1109's 2026-08-20 review (QPA-acceptance `cpd-2`, 4
phases, 9 cumulative stages, worktree venv `[dev]`, darwin/arm64) unless
said otherwise. WP-1112 then halved the per-evaluation cost and re-measured
this ground on the way out (2026-08-21): the counts held — cpd-2's whole-fit
540 nfev / 420 njev at the resized windows against 1109's 534/425, per-stage
`zero_disp` 93 and `cell` 131 unchanged — so the count really is a property
of the problem, exactly as the hypothesis below wants.

- **The measured shape.** 534 residual + 425 Jacobian evaluations per fit
  (nfev/iteration ≈ 1.26 — TRF with the analytic Jacobian, so evaluations ≈
  iterations). Per-stage: `zero_disp` **93 iterations for its 2 new
  parameters**, `cell` 131, `profile` 69, `sample_broadening` 82, `biso` 56.
  The comparison point: Coelho (2018) converges a 550-parameter Pawley
  refinement in ~34 iterations and treats ~20–60 as normal for hard
  problems; the whole staged protocol here spends ~950. Whatever WP-1112
  does to the cost *per* evaluation multiplies this count.
- **It is not the solver's brand of damping.** The same protocol under
  `solver="lm"` (`optimize/lm.py` — Coelho's λ_new schedule over the
  bounded CG of Coelho 2005, WP-0601) also takes ~95 iterations on
  `zero_disp` and 409 total. So the count is a property of the problem or
  the staging, and the likely mechanism is worth stating as the hypothesis
  to test first: sharp lab peaks (FWHM ~0.05°) make the residual violently
  nonlinear in any parameter that *moves positions* — a step that shifts a
  peak by more than its width leaves the linear model's validity region — so
  the trust region/damping crawls at a fraction of a FWHM per iteration.
  `zero_disp` and `cell` are exactly the position movers, and they are the
  two worst stages. A mechanism test, not a speed test, decides this:
  instrument the step-norm and trust-radius trajectory and see whether steps
  are pinned at ~FWHM-fraction scale (crawl) or collapsing after rejections
  (ill-conditioning). One caution from the trigger session (1112): its worst
  stage was `lines_axial` (184 of 363 nfev), not the position movers — its
  `zero_disp` and `cell` take 10 each from good seeds — so the crawl
  hypothesis's stage list is protocol- and start-dependent; instrument
  before assuming the cpd shape generalises.
- **Preconditioning is a measured lead on exactly this quantity** (WP-1110,
  via 1112's arrival prune) — a speed lever free of any answer change.
  WP-1110 gave the cell of an unsupported phase a per-stage window and
  measured what that costs elsewhere: on the chained IUCr `cpd-1c`, bounding
  *every* cell to ±10 %, ±25 % or ±50 % reached the **same answer in 82-100
  iterations where unbounded took 641** — ~7× on that pattern, corundum at
  6.26 wt % against 6.30 unbounded. ±5 % is a cliff the other way (400
  iterations, hit `max_iter`, Rwp 0.1501 against 0.1079), so the effect is
  non-monotonic and has an optimum. The mechanism is preconditioning:
  `run_least_squares` calls scipy with the default `x_scale=1.0` on a vector
  whose coordinates differ by seven orders — cells ~4.8, scales ~1e-5,
  background coefficients ~1e2 — and TRF derives a per-coordinate scale from
  the distance to the bounds, so finite bounds are acting as a scale hint.
  **The direct lever is `x_scale`, not bounds**: `x_scale='jac'` or an
  explicit per-parameter vector says the same thing without constraining
  anything; nobody has measured that here. Two cautions: one pattern, so a
  lead and not a result; and `x_scale` moves the trust-region path on
  **every** fit, so it needs the 1111 harness's equivalence bar across all
  seven cases, never a spot check.
- **The LM basin finding** (measured once, recorded in 1109; do not re-run
  casually): `solver="lm"` on this protocol lands at Rwp 0.245 vs TRF's
  0.132, brucite 76.4 vs 38.2 wt %, in fewer iterations and less wall
  (13.2 vs 17.6 s). Fewer iterations at a worse answer is not a speedup.
  Candidate causes to separate: the λ schedule interacting with softplus
  transforms (an internal-θ step that looks small can be huge in physical
  space near the transform's dead zone), BCCG's bound handling activating
  differently from TRF's reflective strategy, or an early acceptance the
  `r_u` schedule permits that TRF's ratio test would reject. `bench_solver.py`
  (WP-0601's protocol comparison) found identical minima on 2/3 protocols —
  this is a new third-protocol counterexample and belongs in that bench's
  case list whatever the outcome. These basin numbers predate 1112's window
  resize, which moves both fits' stopping points: **re-measure before
  bisecting**.
- **Instrumentation is cheap by design**: per-iteration events already flow
  (`history/events.py`; `_StepTracker` in `optimize/least_squares.py`
  reconstructs accepted TRF steps), and event `data` is an **open dict** —
  adding step-norm/λ/trust-radius fields to an existing kind is *not* an
  `EVENT_SCHEMA_VERSION` bump (the rule and its test are in
  `history/events.py`).
- **Seeding attacks the count from the other end.** The trigger session's
  own largest factor was cold vs warm start (138 s pattern 1 vs 7–9 s
  patterns 6–7, same size — 20×). For `zero_disp` specifically, a 1D scan or
  cross-correlation of y_obs against a cheap y_calc over a zero-shift grid
  costs a handful of residual evaluations and could hand the stage a start
  within a FWHM — turning a 93-iteration crawl into a short polish, if the
  crawl hypothesis is right. Any seeding must live at the plan/stage level
  (a seeding stage writes to the models before solving — the cancellation
  contract in CLAUDE.md already names this shape). A seeding experiment
  needing deliberate capture headroom has a declared per-stage knob since
  1112's capture/tail split: `Stage.window_slack_deg`, not a constant to
  bend.
- **The cost-estimate request** (an agent in WP-1110's round, via 1111,
  which could not act on it — its non-goals forbade production changes): a
  cheap callable estimate, reflections × free parameters, so a caller can
  size a model before spending minutes discovering it is too big. The
  quantity predicted is this WP's — cost = per-evaluation work × evaluation
  count — and 1111's `_shape` already computes the first half (fitted
  points, (line, reflection) pairs, mean window width) off a compiled model
  without fitting. One agent on one loaded box motivates it: a request, not
  a measurement. Whether it ships is this WP's call — it may equally be a
  v1.2 API item — but it is not dropped silently.
- **Per-stage budgets**: an intermediate stage's job is to seed the next
  stage, not to reach publication convergence. 1109's retired-item 3
  measured global tolerance loosening at only 1.24–1.32× (`cpd-1a`) /
  1.00× (`cpd-2`) — so the tail is not where the iterations are, and any
  budget experiment must measure the *whole-plan* effect of capping
  intermediate stages (does the final stage inherit a good enough seed that
  total evaluations drop, with the final answer unchanged to shift/esd?).
  This may well retire as a non-cause; retire it with numbers either way.

## Non-goals

Replacing the staged-plan design with TOPAS-style all-at-once refinement
(the ladder is a robustness and agent-legibility decision; this WP reduces
its cost, not its existence); per-evaluation cost (1112); new solver
algorithms beyond the two in-tree drivers (the solver survey,
`docs/solver-survey.md`, already retired several — read §0 before proposing
one); Rwp-judged anything.

## Tasks

- [ ] **Instrument**: step-norm, trust-radius/λ, and accept/reject per
      iteration onto the existing event stream (open-dict fields, no schema
      bump); a small analysis helper that plots/prints the trajectory for a
      named stage.
- [ ] **Name the mechanism** for `zero_disp` (93) and `cell` (131) on the
      1111 cases: crawl vs collapse vs something else, written into this
      file with the trajectories.
- [ ] **`x_scale` experiment**: `x_scale='jac'` and an explicit
      per-parameter vector against the default, on all seven 1111 harness
      cases; equivalence by shift/esd, iteration columns before/after. Land
      only what the measurement supports.
- [ ] **Seeding experiment**: cross-correlation zero/displacement seed
      before the plan; measure per-stage iterations and total evaluations,
      answer-identity by shift/esd. Land it (as an opt-in stage or plan
      preset behaviour) only if the measurement says so.
- [ ] **Intermediate-budget experiment**: cap non-final stages, measure
      whole-plan evaluations and final-answer identity; land or retire with
      numbers.
- [ ] **LM basin investigation**: reproduce on the QPA protocol, bisect the
      candidate causes above, add the case to `examples/bench_solver.py`'s
      protocol list; fix if the cause is a defect, fence with a recorded
      reason if it is the method (`solver="lm"`'s docstring then names the
      protocol it loses).
- [ ] **Decide the cost-estimate callable**: land it here or defer it to
      v1.2 in writing (a ROADMAP/WP note naming it), never a silent drop.
- [ ] Tests (the instrumentation fields, the seeding stage if landed) +
      before/after iteration columns from the 1111 harness in the handover
      entry.

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py       # iteration columns before/after
.venv/bin/python examples/bench_solver.py           # LM vs TRF, now including the QPA protocol
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

Judged by evaluations-to-the-same-answer (shift/esd against the reference
minimum, Coelho's own basin methodology per `docs/solver-survey.md`), never
by Rwp or by iteration count alone — the LM finding above is the cautionary
example already in hand.

## References

- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 428–435 — the λ_new
  schedule `optimize/lm.py` implements; its Table 5 iteration counts are the
  comparison shape.
- Coelho, A. A. (2005). *J. Appl. Cryst.* **38**, 455–461 — the bounded CG.
- `docs/solver-survey.md` §0 — the Amdahl ceiling on solve *time* (1.25×)
  that does **not** bound this WP: reducing the count attacks the whole
  wall clock, which is why this front is open at all.

## Handover log

- **2026-08-20** — created by the 1109 review session; carries the review's
  iteration table, the LM basin finding, and the crawl hypothesis as the
  first thing to test.
- **2026-08-21** — arrival prune. All three inherited entries were still
  live, so none was deleted: 1112's re-measurements merged into the numbers
  they amend (counts-held into the Context intro, the re-measure caveat onto
  the LM basin bullet, the `lines_axial` caution onto the crawl-hypothesis
  bullet, `window_slack_deg` onto the seeding bullet); the WP-1110
  preconditioning lead became a Context bullet plus the `x_scale` task; the
  WP-1111 cost-estimate request became a Context bullet plus the
  decide-or-defer task.
