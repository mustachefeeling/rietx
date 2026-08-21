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

## Findings — the mechanism, named (2026-08-21)

Measured with ``examples/stage_trajectory.py`` off the new ``eval`` fields
(this checkout's venv ``[dev]``, darwin/arm64); every trajectory regenerates
from ``--case X --stage Y [--solver lm] --plot out.png``.  Counts are
properties of the fit, not wall clock.

**The crawl hypothesis is wrong for the position movers — and so is
collapse.**  cpd-2 ``zero_disp`` spends 94 evals as 93 accepted + 1 rejected:
the trust region never binds after eval 2, and the accepted step norms decay
as one straight line on a log scale across three decades — ratio ≈ 0.93 per
iteration, fixed direction.  Same shape on ``cell`` (131 + 1, ratio 0.926)
and on cpd-1a ``zero_disp`` (84 + 1, ratio 0.928).  Under ``solver="lm"`` the
same stage runs **λ ≡ 0 throughout** — pure Gauss-Newton, 94/94 accepted,
same endpoints to 5 digits (zero 0.05074°, displacement 0.09567).  So the
count is **undamped Gauss-Newton converging linearly along a near-degenerate
direction** — zero ↔ displacement ↔ the low-order background terms, which
trade against each other over a lab θ range — at a problem-intrinsic rate of
≈ 0.93/iteration (≈ 14 iterations per decade), run to ftol = 1e-9.  In
``cell`` the tail direction is the *same* pair walking back (zero 0.0507° →
0.0093°, displacement 0.0957 → 0.0304 once the cells can absorb the
position error).  The control: nac ``zero`` — a zero stage with no
displacement partner (synchrotron) — takes **5 evals**, and nac ``cell``
takes 14 with a quadratic finish (step norms 6e-1 → 5e-4 → 2e-6).  The
expensive stages are expensive exactly where the degenerate pair is free.

**The tail is the count.**  99.99 % of the stage's cost decrease is banked by
accepted eval 55/93 (``zero_disp``), 83/131 (``cell``), 50/84 (cpd-1a); the
rest moves the fifth-and-beyond digit.  Every expensive stage measured ended
on **ftol** — never xtol or gtol (both pinned at 1e-12, see
``optimize/least_squares.py``).

**``lines_axial`` on the trigger is a second mechanism, and it *is*
trust-region-shaped.**  185 evals = 143 accepted + 42 rejected (runs up to
7); accepted step norms are quantized in powers of two (0.058 / 0.115 /
0.231 / 0.462 internal) — steps pinned *at* the radius — through ~5
grow-then-reject cycles, while the cost is flat at 6 digits from eval ~20
and 99.99 % is banked by 69/143.  Meanwhile ``phases.2.gauss_strain`` does a
full excursion to its softplus off state (1.5e-6) and back: a flat width
valley (4 × (gauss_size, gauss_strain) + shared axial, near-degenerate over
the fitted range), with the dead zone inflating internal distances — the
``x_scale`` lead's natural target.

**The budget experiment, measured and landed** (2026-08-21, same venv;
whole-plan totals via the 1111 harness's counting scaffold).  Loosening
**ftol** on every stage but the last is the right lever; capping ``max_iter``
is the wrong one (on cpd-2 a 30-iteration cap *raised* the total to 568 nfev
by pushing work downstream, and moved the answer more).  Intermediate
ftol = 1e-6 against the untouched baseline:

| case | baseline nfev/njev | intermediate 1e-6 | max shift |
|---|---|---|---|
| cpd-1a | 408/343 | 272/221 (**1.50×**) | 8.6e-4 esd |
| cpd-2 | 540/420 | 315/247 (**1.71×**) | 0.020 esd (a background term); QPA within 0.003 wt % |
| trigger | 363/289 | 226/185 (**1.61×**) | non-degenerate ≤ 0.001 esd; QPA ≤ 0.001 wt % |

The trigger's nominal 1.2 esd worst shift is entirely the **exactly
degenerate** instrument-X ↔ per-phase ``lor_size`` family (every phase's
``lor_size`` moved by the −0.00137 that shared X gained; Lorentzian FWHMs
add and both are size-like in θ) — the parameterisation moved along a flat
direction, the answer did not.  1e-5/1e-4 buy 1.9-2.2× at 0.01-0.2 esd; the
knob landed as opt-in ``Stage.ftol`` (default ``None`` → bit-identical), so
the presets are unchanged and flipping them is a decision the harness table
above prices.  Behaviour is exactly as the mechanism predicts: the final
stage inherits the ridge walk once (cpd-1a ``biso`` 47 → 49, at 1e-4 → 95)
instead of every stage polishing it.

**Both remaining levers measured against those predictions** (2026-08-21,
same venv, same scaffold):

- **``x_scale='jac'`` retires.**  E2's SRM 660c null (`docs/solver-survey.md`
  §0.3, which this WP's Context missed — 9 % more iterations, identical
  answer) generalises and worsens: cpd-1a 397 vs 408 nfev at a 0.76 esd
  drift, cpd-2 **631 vs 540**, trigger 374 vs 363 with ``lines_axial`` 200
  vs 184 — worse even on the one trust-region-shaped stage it was predicted
  to help.  The clinching detail: ``zero_disp``/``cell`` counts are
  **bit-unchanged** (84/86, 93/131) under it, confirming mechanism A is
  scale-invariant — the GN step does not change under diagonal column
  rescaling, and the trust region never binds there.  An explicit vector is
  not run separately: it is 'jac' without adaptation, and two independent
  nulls plus a scale-invariance argument already answer it.  WP-1110's
  bounds-7× on chained cpd-1c therefore acts by *fencing the walk*, not by
  scaling — consistent with the windows landing only on unsupported phases.
- **The cross-correlation seed retires.**  The seed it finds is tiny
  (−0.0072° cpd-1a, −0.0039° cpd-2: the data's net apparent shift, exactly
  as mechanism A implies — the pair's large converged values are
  compensating, not compensated).  ``zero_disp`` 84 → 59 / 93 → 83, whole
  plan 408 → 379 / 540 → 509 (**1.06-1.08×**), trigger unchanged (its
  ``zero_disp`` was already 10).  A seeding stage's machinery is not paid
  for by 6-8 % when the ftol knob buys 50-71 % on the same cases.

**The LM basin, reproduced, bisected and fenced** (2026-08-21).  At the
resized windows the shipped caps *hide* it — ``solver="lm"`` lands Rwp
0.1346, brucite 38.25 wt %, because its ``cell`` stage is truncated at
``max_iter`` before entering the path.  At per-stage ``max_iter`` 400, where
both drivers stop where their own criteria say, the finding reproduces:
LM Rwp 0.2452, brucite 76.46 wt %, ΔBIC −8883.  The bisection: the basins
are identical through ``cell`` (Rwp 0.5299 both, only the flat
zero/displacement pair differing ~1 %); the drivers then stop at different,
locally equivalent points of the degenerate width valley
(``profile``/``sample_broadening``/``biso``, Rwp 0.2440 vs 0.2452, e.g.
``profile.u`` −0.037 vs +0.0003); and from LM's point the texture stage
terminates ``ftol_runs`` after 14 evaluations at r = 1.0000, where from
TRF's the same stage descends to r = 0.67 and Rwp 0.1329.  The decisive
test: **a TRF polish of the final stage from LM's exact converged state
stays at Rwp 0.2436** (4 iterations, converged) — the LM endpoint is a
genuine local minimum, so this is basin selection on a shared degeneracy,
not a driver defect, and none of 1109's three candidate causes (softplus λ
interplay, BCCG bound handling, early ``r_u`` acceptance) is the mechanism.
Fenced with the reason recorded: ``optimize/lm.py``'s docstring names the
protocol, ``examples/bench_solver.py`` gains ``_cpd2_qpa`` (per-stage cap
raised to 400 *in the case*, because at the shipped cap the answer depends
on a runaway guard — the dependence WP-1109's budget rule forbids reading
as convergence; the guard did fire ``max_iter`` on the run that landed
well, which is the honest half).

## Non-goals

Replacing the staged-plan design with TOPAS-style all-at-once refinement
(the ladder is a robustness and agent-legibility decision; this WP reduces
its cost, not its existence); per-evaluation cost (1112); new solver
algorithms beyond the two in-tree drivers (the solver survey,
`docs/solver-survey.md`, already retired several — read §0 before proposing
one); Rwp-judged anything.

## Tasks

- [x] **Instrument**: step-norm, trust-radius/λ, and accept/reject per
      iteration onto the existing event stream (open-dict fields, no schema
      bump); a small analysis helper that plots/prints the trajectory for a
      named stage.  Landed as ``eval.accepted``/``step_norm``/``values``
      (+``lam`` on LM), ``stage_start.free_paths``,
      ``stage_end.termination`` (which tolerance fired —
      ``LSQOutcome.termination``), and ``examples/stage_trajectory.py``.
      TRF's trust radius is scipy-internal; the trial step-norm sequence is
      its observable shadow, and the LM stream now carries every measured
      trial rather than accepted points only.
- [x] **Name the mechanism** for `zero_disp` (93) and `cell` (131) on the
      1111 cases: crawl vs collapse vs something else, written into this
      file with the trajectories.  It is something else — § Findings: an
      undamped Gauss-Newton linear tail (rate ≈ 0.93/iteration) along the
      zero↔displacement↔background degeneracy, ftol-terminated; plus a
      genuine trust-region valley wander on the trigger's `lines_axial`.
- [x] **`x_scale` experiment**: retired with numbers (§ Findings) — 'jac'
      is null-to-harmful on all three lab-shaped cases, mechanism-A stage
      counts bit-unchanged (scale-invariant), and E2's 660c null stands; an
      explicit vector is 'jac' without adaptation and is answered by the
      same evidence.
- [x] **Seeding experiment**: retired with numbers (§ Findings) — the
      cross-correlation seed is measured at 1.06-1.08× whole-plan because
      the data's net shift is milli-degrees; the iterations are the ridge
      walk, which a rigid seed cannot reach.  Nothing lands.
- [x] **Intermediate-budget experiment**: cap non-final stages, measure
      whole-plan evaluations and final-answer identity; land or retire with
      numbers.  Measured (§ Findings): intermediate ftol 1e-6 buys 1.50-1.71×
      whole-plan at ≤ 0.02 esd on all three lab-shaped cases; ``max_iter``
      caps are the wrong lever.  Landed as opt-in ``Stage.ftol`` +
      ``StageSpec.ftol`` (SCHEMA_VERSION 0.3 → 0.4), presets untouched.
- [x] **LM basin investigation**: reproduce on the QPA protocol, bisect the
      candidate causes above, add the case to `examples/bench_solver.py`'s
      protocol list; fix if the cause is a defect, fence with a recorded
      reason if it is the method (`solver="lm"`'s docstring then names the
      protocol it loses).  Done — § Findings: reproduced at raised caps
      (hidden by truncation at the shipped ones), bisected to basin
      selection on the degenerate width valley, proven a genuine local
      minimum by TRF-from-LM's-state, fenced in ``lm.py`` and benched as
      ``_cpd2_qpa``.
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
