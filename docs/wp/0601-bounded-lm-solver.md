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
  it collapses MPS from 10.6 ms to 0.41 ms at fixed work — **and numpy from
  1.36 ms to 0.56 ms, which puts them level.** So batching is a *numpy-path*
  optimisation (≈2.4×), now scoped as a spike in WP-0605; it does not turn the
  GPU into a win at single-pattern scale, because 10⁵ elements is still
  launch-bound. A "solver benchmark vs scipy TRF" should therefore be written as
  a **CPU** comparison, and any device column in it reported as the diagnostic it
  is rather than a target to optimise toward. The genuine GPU case is ~10⁶-element
  kernels — a `vmap`-batched in-situ series, which is v2-fenced.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — a motivating data
point. Softplus transforms exist because hard lower bounds stall TRF, and they
carry a real cost: a softplus parameter starting at exactly 0 has a dead
gradient and never moves without `Stage(seed=…)`, which has already bitten two
WPs. A genuinely bound-constrained solver could retire the transform for width
and scale parameters — worth measuring as part of the benchmark, since it would
remove a recurring class of silent no-op refinements.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
