# WP-0601 — TOPAS-style bounded LM solver

Milestone: v0.6 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- TOPAS-style bounded LM: Gauss-Newton normal equations + adaptive Marquardt
  λ (Coelho 2018, JAC 51:428) + bound-constrained CG inner solve (Coelho
  2005, JAC 38:455) + line search — independent implementation from the
  papers, same driver interface as the scipy path

## Context pointers

- [../DESIGN.md](../DESIGN.md#minimizer-strategy) — same driver interface as
  `optimize/least_squares.py`; the scipy TRF path remains the reference.
- Licensing fence: TOPAS is closed — **papers only**, independent
  implementation ([../DESIGN.md](../DESIGN.md#locked-decisions)).
- Milestone acceptance: solver benchmark vs scipy TRF.

## Inherited

From **WP-0605** (batched peak loop, closed 2026-07-28 as a measured no-go) —
three things a solver benchmark must know.

- **Every pre-0605 wall-clock number is stale.** Task 0 graduated to
  production: an FCJ node memo on exact input equality plus an `axial_derivs`
  skip in `derivative_bases`, worth 1.23× on the SRM 660c protocol
  (1.737 → 1.411 s) at bit-identical results. Re-baseline "scipy TRF" against
  current main before quoting any solver comparison, or the new solver gets
  credit for this WP's speedup.
- **The memo rewards a solver that re-visits θ.** FCJ nodes are reused whenever
  the exact (2θ, S/L, H/L) recur, so an LM that evaluates the residual and then
  the Jacobian at the same accepted point pays the node generation once —
  the same property TRF now enjoys. A solver that jitters θ between the two
  (e.g. evaluating J at a slightly different point "for free") silently
  forfeits it.
- **A custom Jacobian assembly should pass
  `derivative_bases(values, intens, axial_derivs=…)` the way `_make_jacobian`
  does** — request the aperture bases only when an axial parameter is free;
  they are two extra FCJ node generations per (line, reflection) per iterate
  otherwise. The FitReport callers keep the full default.

- **A better-conditioned solver would re-open whether `Geometry.mu_t` can be
  refined.** WP-0501 fixed capillary µR because its derivative lies
  *identically* in span{1, sin²θ} — no solver can help with an exactly singular
  direction. Flat-plate µt is different: measured, it keeps **3-47 %** of its
  signature after that projection (`absorption.mu_t_identifiable_fraction`, and
  `tests/test_flat_plate.py::test_mu_t_identifiability_is_small_but_not_zero`
  pins the numbers). It is held fixed today because it is knowable from the
  specimen and because a free one lands in exactly the ill-conditioned
  {scale, Biso, background} corner. If this WP lands a solver that handles that
  corner honestly, the measurement to redo is `block_projection_r2` with the
  scale and background as `nuisance` (WP-0502's machinery) on a real thin-mount
  pattern — not the norm ratio above, which is basis-dependent (see below).
- **A ratio-of-norms diagnostic is basis-dependent, and this cost a WP an
  incorrect table.** WP-0508 first measured µt's identifiable fraction against
  the *ITC* form of the transmission factor and got 0.2-1.3 %; against the
  **normalised** form the code actually implements it is 3-26 %. The two differ
  by a constant in ln A — i.e. by a multiple of the phase-scale direction — so
  the numerator is identical and only the denominator moves. Any new
  conditioning statistic here wants the same check before its numbers are
  quoted.

From **WP-0308** (multi-histogram, landed 2026-07-24) — **there are now two
drivers, not one.** `run_multi_least_squares` imports the private
`_make_residual` / `_make_jacobian` from `least_squares.py` and runs its own
TRF call over a stacked row layout ([all histograms' data rows][all histograms'
penalty rows], per-histogram √w scaling). A solver swap that only reroutes
`run_least_squares` leaves multi-histogram silently on scipy. "Same driver
interface as the scipy path" has to mean both entry points.

From **WP-0401** (op shim, landed 2026-07-24): the solver is explicitly outside
the backend shim — "the scipy TRF driver, `covariance_estimates`, all of
`optimize/statistics.py`" stay host numpy permanently. So this WP is written
against numpy arrays at the driver boundary and needs no `xp` routing; it must
simply accept whatever the backend materialised there.

From **WP-0403** (mixed-precision policy, landed 2026-07-24): the normal
equations are the one step that can never drop below fp64 — cond(JᵀJ) =
cond(J)². A Gauss-Newton solver forms JᵀJ *explicitly*, which is exactly the
squared-conditioning step, so this WP inherits the invariant more directly than
the TRF path did. `require_fp64` guards it at
`covariance_estimates`; do the same at the new solver's normal-equation
assembly, and note `backend/linalg64.py` is where that boundary lives.

From **WP-0408** (torch backend, landed 2026-07-27) — two findings, one of which
is a *measurement this WP should not have to repeat*, and one of which is work
that landed in this WP's neighbourhood without an owner.

- **Reduced-precision columns converge to the same answer *because the trust
  region re-measures each step against an fp64 cost*.** Measured on real Apple
  GPU hardware: an SRM 676a refinement with the whole peak chain and every
  Jacobian column in fp32 lands 3.5×10⁻⁸ Å from the numpy fp64 cell. That
  property is a property of the *driver*, not of the columns — a bounded LM that
  accepts a step on a predicted decrease computed from the same reduced
  quantities would forfeit it. Keep the cost evaluation fp64 and independent of
  the column precision, and the WP-0403 policy keeps holding; the
  `require_fp64` guard on the normal equations (see the WP-0403 note above) is
  necessary but not sufficient for this.
- **Do not expect device acceleration from the solver benchmark, at any
  bottleneck.** `examples/bench_torch_mps.py` reports MPS running **60-125×
  slower** than numpy — not a precision or backend-quality problem but the loop
  shape: the residual walks ~130 frozen windows of 200-900 points one at a time
  in python, and MPS per-op cost is flat at 110-165 µs from 64 to 65 536
  elements, i.e. pure launch latency. The obvious remedy, a **batched peak loop**
  (one padded n_reflections × max_window tensor per phase, which the
  frozen-per-stage layout already makes legal), was measured rather than assumed:
  it collapses MPS from 10.6 ms to ~0.4 ms at fixed work — **and numpy from
  1.36 ms to ~0.55 ms.** A size sweep pins it: **break-even ≈ 50-65 k elements
  per kernel, ceiling ≈2.5-3×** (memory-bound work, so GPU arithmetic throughput
  never participates). So batching is a *numpy-path* optimisation (≈2.4×), now
  scoped as a spike in WP-0605. A "solver benchmark vs scipy TRF" should
  therefore be written as a **CPU** comparison, and any device column reported as
  the diagnostic it is rather than a target to optimise toward — one batched
  pattern is 17-121 k elements, so a device needs ≈10-60 patterns together before
  it even reaches its ≈3× plateau.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — a motivating data
point. Softplus transforms exist because hard lower bounds stall TRF, and they
carry a real cost: a softplus parameter starting at exactly 0 has a dead
gradient and never moves without `Stage(seed=…)`, which has already bitten two
WPs. A genuinely bound-constrained solver could retire the transform for width
and scale parameters — worth measuring as part of the benchmark, since it would
remove a recurring class of silent no-op refinements.

From **WP-0503** (Stephens anisotropic strain, landed 2026-07-27) — **the
first constraint in this package that is an inequality, not a box, and a
measured reason to want one.** The Stephens strain variance must satisfy
σ²(M) = T·θ ≥ 0 on every fitted reflection, where T is a constant
(reflection × pattern) matrix frozen at stage compile and θ the strain DOFs.
That is a *linear* inequality in the free parameters — precisely the shape a
bound-constrained CG inner solve (Coelho 2005) generalises to, and unreachable
for `scipy.optimize.least_squares`, whose only constraint vocabulary is a box.

Why it matters rather than being a nicety: measured on two real round-robin
patterns (`tests/test_acceptance_stephens.py`), the *unconstrained* refinement
leaves the cone on **both** — the strongly anisotropic specimen (brucite, 12 of
43 reflections) and the isotropic control (corundum) alike, because the poorly
determined anisotropic directions are free to wander. So today
`STEPHENS_STRAIN_NOT_POSITIVE` is not a rare alarm but the normal outcome, and
the coefficients are never quotable. Enforcing T·θ ≥ 0 in the solver would turn
the guard back into an exception and make refined S_HKL reportable. If the
benchmark needs a second motivating case beyond speed, this is it. (The
analogous ADP positive-definiteness cone is *not* linear — it is a
semidefinite constraint — so do not expect one mechanism to serve both.)

Also from WP-0503, a note for whatever the benchmark quotes: on the 7251-channel
round-robin patterns, Hamilton's F test at α = 0.05 blesses a 0.13 % χ²
improvement (an inert 3-parameter addition) just as it blesses a real 6.9 % one.
ΔBIC separated the same pair by +488 vs −17. If this WP reports "the new solver
finds a better minimum", say by how much in ΔBIC, not by whether Hamilton
passes.

From the **2026-07-28 literature intake** (FPA fence work, not a WP; papers
supplied by the user, set recorded in DESIGN.md's FPA fence note):

- **Coelho 2018, JAC 51, 210 (TOPAS architecture) is on hand and read.** What
  it gives this WP: the objective is assembled as χ² = χ²₀ + χ²_P + χ²_R,
  with *penalties* expanded to second-order Taylor with the off-diagonal A_P
  terms dropped and *restraints* to first order with off-diagonals kept —
  measured trade-off stated in the paper: restraints converge in fewer
  iterations, penalties faster in wall-clock (§3.3). K_P/K_R auto-weighting
  (eqs. 16–17) balances penalty-vs-data information per parameter from the
  diagonal A terms; compare that against the fixed user weights our restraint
  rows carry before inventing a new knob. The A matrix goes sparse for
  Pawley-shaped problems, and each ∂Y_c/∂p column is allocated, accumulated
  into A₀ and Y₀, then freed — peak memory is one column, not J (§3.1–3.2) —
  directly relevant to forming JᵀJ explicitly under the WP-0403 fp64
  invariant. It also confirms the bounded CG of Coelho 2005 as TOPAS's
  *default* solve, with BFGS as the cheap-A fallback.
- **Both papers the scope cites are now on hand and read** (supplied
  2026-07-28; full texts live on this machine as MinerU markdown conversions,
  `mdfind -name "bound constrained conjugate"` and `mdfind -name "Optimum
  Levenberg"`). Digests follow — enough to design from; consult the texts for
  the pseudo-code.

- **Coelho 2005, JAC 38, 455 (BCCG).** Standard CG on the normal equations
  (Polak-form pseudo-code, their Table 1), diagonally pre-conditioned to
  A_ii = 1, plus four modifications: (1) box bounds enforced *inside* the CG
  loop — a violating parameter is clamped to its bound and removed from the
  loop (not from the least-squares process), reinstated at the next outer
  iteration; (2) early-iteration step damping α = [(k+1)/N_k, capped at
  1]·s_k/(p·q) — their eq. (1) as printed reads Max[(k+1)/N_k, 1], which is a
  no-op, while the text says it *reduces* α, so read Min (the
  transcription-vs-intent check the papers habit warns about); (3) a
  parameter whose residual contribution satisfies 200·r_i²·N_k < s_0 for six
  consecutive iterations is dropped from the loop — this is what makes
  block-diagonal/sparse systems cheap (measured: Pawley solve 3.30 s → 1.31 s
  at identical Rwp); (4) terminate at k_max = (k at last removal) + N_k, or
  when s_k < 10⁻⁴·s_0 three iterations running. Measured behaviour: ~10 CG
  iterations regardless of N, dense or sparse, ill-conditioned or not; a
  dense N = 1325 normal-equation *solve* drops 484 s → 2.86 s but the whole
  refinement only 2441 → 1785 s — the solve is not the bottleneck once
  computing J dominates, which is this package's regime at typical N. The
  in-loop bounds are not cosmetic: clamping *after* the solve reproduces LU
  exactly (their Pawley converges at Rwp 4.351 in 84 iterations), in-loop
  clamping reaches 3.901 in 16; on tightly-bounded rigid bodies it shifts the
  whole converged-Rwp distribution lower at 4.3× less total time. Sanity
  anchor for tests: with bounds inactive and the removal scheme off, BCCG
  must reproduce the unconstrained solution.

- **BCCG does boxes only — a correction to the WP-0503 note above, now that
  the paper is read.** Published BCCG constrains *refined parameters* to
  min/max bounds; its own Discussion (§4) states that a constraint which is
  a function of several parameters cannot be handled in the loop — "a
  restraint which modifies the A matrix is necessary" (their example: an
  interatomic distance through six coordinates; ours: the Stephens cone rows
  T·θ ≥ 0, which are linear *functionals* of θ, not parameters). Bounds may
  move between outer iterations (their Pawley run re-bounded each intensity
  at half its current value) but are constants inside the loop. So enforcing
  the strain cone in the solver means an *extension* of BCCG (e.g. active-set
  on cone rows) — novel work, not a port — or reparameterising, or keeping
  the cone as a restraint. Decide this explicitly when expanding the stub;
  the softplus-retirement case (WP-0310 note above) needs only the published
  box mechanism.

- **Coelho 2018, JAC 51, 428 (λ_new).** The signal is r_u = ΔS_t/ΔS, the
  first-order-predicted vs actual decrease, with ΔS_t = Δpᵀb — one extra dot
  product per step. Update rule (their eq. 9; λ dimensionless because the
  system is pre-conditioned to A_ii = 1, initially 0; m_u = r_u clipped to
  [0.4, 10]): failed step → λ ← 10·max(λ, 0.1); good step at-or-under the
  quadratic prediction (m_u ≤ 1) → λ ← m_u·λ/2; good step that *overshoots*
  (m_u > 1) → λ ← m_u(λ + ½) − ½ — damping although S dropped is the whole
  novelty (plus a rarely-fired λ/10 branch when the last ten steps were
  predominantly overshoots, Q_u > 5). This is the LM-flavoured analogue of
  the trust-region gain ratio the reference scipy TRF already adapts on, so
  expect parity on well-behaved full-J problems: their measured gains with a
  full A matrix are R_ν 0.96–1.19 across the crystallographic set, rising to
  1.19–2.07 only when A is BFGS-approximated, and largest on
  far-from-quadratic objectives (|x−a|^n at n ≤ 0.5, penalties,
  discontinuities). Since this WP computes the full analytic J, quote the
  modest end as the expected payoff — the WP's real value lives in the
  bounds/cone cases above, not the λ schedule. One benchmark trap they flag
  themselves: loose termination criteria can favour the more erratic
  updater, and their largest runs were compared at a fixed iteration count
  (N_u = 20) instead — fix the 0601 benchmark's stopping rule (and report
  ΔBIC per the WP-0503 note) before running anything.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
