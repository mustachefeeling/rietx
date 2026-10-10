# WP-1937 — a bounded step solved exactly

Milestone: unscheduled · Status: 🔄 2026-10-10 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: 1936 soft, landed 2026-10-09 (a step constant moved the LaB₆ basin under either driver; it no longer does)
Priority: P1 2026-10-09 — the second rung under WP-1929's P1; physical coordinates (WP-1938) cannot become the default until a driver handles widths pressed on zero, and TRF does not

## Goal

The default least-squares driver solves each damped Gauss-Newton step with its
box bounds exactly, as an active set. It reaches one minimum on every
acceptance fit in physical coordinates, including the QPA round-robin fits
where several redundant widths end on zero. Its statuses and budgets mean what
TRF's do, so nothing downstream can tell which driver ran except by the
numbers.

## Context

**Why TRF is the wrong bound handling here.** scipy's TRF is Coleman & Li's
interior method: near a bound it shrinks that variable's step by
√(distance). Its local convergence analysis assumes each active bound is
non-degenerate (read the paper before quoting this in the manual). A width that wants to be exactly zero beside redundant
partners is the degenerate case. Measured 2026-10-09 (WP-1929, macOS arm64,
`[dev]`, physical coordinates): on brucite and corundum TRF's reflection
parks `gauss_strain` 7.6e-6 deg² above zero with its gradient pointing out,
and the coupled widths crawl at about 0.1 % of cost per evaluation until the
400-evaluation cap. χ²_red 8.3474 against 8.3131 (brucite), 2.659–2.665
against 2.6560 (corundum). `dogbox` was erratic (χ²_red 556 on the absent
phase), `x_scale="jac"` changed nothing, and a tolerance pin around TRF
never fired.

**What worked.** The package's own LM driver (`optimize/lm.py`, Coelho 2018
λ schedule; TOPAS's architecture) with its BCCG step (`optimize/bccg.py`,
Coelho 2005) replaced by an exact box-constrained solve. The probe did it in
`lm._solve_step`: Jacobi-scale A + λ·diag(A) to unit diagonal, take
`eigh`, drop eigenvalues under 1e-13 of the largest, form R = Λ^½Vᵀ and
c = Λ^-½Vᵀb, and call `scipy.optimize.lsq_linear(R, c, bounds, method="bvls")`.
Twelve fits × five starts nudged by (1 + k·1e-14):

| fit | physical + TRF | physical + LM-BVLS |
|---|---|---|
| brucite | 8.3474, max_iter | 8.3131166, spread 1.5e-11 |
| corundum | 2.659–2.665, max_iter | 2.6560076, spread 1.0e-11 |
| NAC, FAP, Si 640c, BT-1 ×2, capillary, absent phase | one minimum | the same minimum, 37–135 iterations against 32–156 |
| LaB₆ + cBN | 9.661408 | 9.687–9.688 (both genuine minima; WP-1936) |

The adversarial review counted 97 BVLS solves on LaB₆ and 242 on brucite:
96 of 195 returned status 3 (unconstrained solution feasible), the rest status
1 (KKT), none max-iter. 17 of 242 were rank-deficient after the eigenvalue
drop and handled by BVLS's min-norm lstsq in two iterations. Pawley (both
fixtures) and the joint cell fit agree with TRF to 1e-9.

**What has to change in the driver before it is a default.**

- `lm.py:373`: `status = 1 if outer > 0 else -1`. A stage that starts at its
  minimum reports `"diverged"` (LaB₆ `displacement`; on a refit from a
  converged point, `profile`, `coordinates` and `biso`). `sequential.py`
  quarantines and escalates on that word.
- Budgets differ. `max_iter` caps LM's *outer* iterations; TRF gets
  `max_iter · NFEV_PER_ITERATION` (4) evaluations. brucite `zero_disp` hits
  LM's cap of 100 where TRF converges in 136 evaluations at the same χ². And
  `n_iterations` is reported as nfev on one driver and outer iterations on the
  other.
- The step's cost is O(n³). Negligible for the table block; a Pawley block
  appends one intensity per reflection, which can be thousands of columns.
  BCCG exists for that case (Coelho 2005's Pawley timings). Measure it, and
  keep BCCG (or an active-set CG) above a size if BVLS loses.
- The solver knows its active set exactly (x == bound, and the multiplier's
  sign). Expose it on `LSQOutcome`. WP-1929 keys the at-bound flag on it,
  because `bound_findings`' esd window admits a row 24 units from its bound
  when the row's esd is 2359 (brucite aniso, `profile.u = −0.0016 ± 2359`
  flagged at −0.05).
- `lm.py`'s docstring says the driver "is not a speed play" and to prefer
  TRF on texture protocols. Re-measure both claims under the new step; the
  QPA cpd-2 basin case lives in `examples/bench_solver.py`.

**The Stephens cone.** `solver="lm"` already enforces σ²(M) ≥ 0 as linear
inequalities (`LinearInequality`). The BVLS step handles boxes only, so the
cone's projection and truncation stay as they are around it. Brucite aniso
under LM reaches 8.0006 against TRF's 7.636 because TRF's point violates the
cone (`STEPHENS_STRAIN_NOT_POSITIVE`): a difference in what is enforced. WP-1467
names `solver="lm"` in its suggestion; if this WP makes LM the default, that
task changes shape.

### Inherited

- **From WP-1936 (2026-10-09): the step is fixed, and the LaB₆ basin moved
  with it.** The Caglioti `u`, `v` and any identity width bounded at 0 now
  take a forward-difference step sized by their unit (`least_squares.fd_step`,
  `_fd_typicals`). LaB₆ + cBN with `u v w x y` free then reaches χ²_red
  9.840220 under physical + TRF at FD_STEP 1e-6, 1e-7 and 1e-8 (spread
  2.4e-10), and 9.793673 under softplus + TRF. The table's TRF row above
  (9.661408) is the old step's basin, so compare drivers against the new one.
  Brucite and corundum under physical + TRF still stop on `max_iter`.

## Non-goals

- The coordinates (WP-1938) and the esd rule (WP-1929).
- The FD step (WP-1936).

## Tasks

- [x] The BVLS step in `lm._solve_step`, with the eigenvalue cutoff's source
      in its docstring, and `tests/test_lm_solver.py`'s r_u = 1 calibration
      still exact.
- [x] Status and budget parity: a stage already at its minimum is
      `converged`; one budget unit for both drivers; `n_iterations` means one
      thing. Read every consumer of `"diverged"` and `n_iterations`.
- [x] The active set on `LSQOutcome`, from both drivers (TRF's
      `active_mask` is the fallback).
- [x] Pawley at its largest fixture: BVLS against BCCG, time and answer; the
      size rule if one is needed.
- [ ] The twelve-fit grid plus the Pawley, Le Bail, multi-histogram,
      magnetic and sequential suites under the new driver, in both coordinate
      systems. Every acceptance number that moves listed with its reason.
- [ ] Flip the default (`Refinement(solver=)`), keep `"trf"` selectable, and
      rewrite `lm.py`'s docstring and the manual's solver section.
- [ ] Tests, plus obs/calc/diff PNGs to `tests/output/` for the fits whose
      answer moves.
- [ ] Skill: the solver row in the skill's references, if it names TRF as the
      default.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_lm_solver.py tests/test_bccg.py tests/test_acceptance_stephens.py tests/test_acceptance_lab6_cbn.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

On the twelve-fit grid in physical coordinates the default driver gives a
spread under 1e-9 on every fit, and no stage reports `max_iter` that TRF
converges.

## References

- Coleman, T. F. & Li, Y. (1996). *SIAM J. Optim.* 6, 418-445 (TRF's interior
  scaling).
- Stark, P. B. & Parker, R. L. (1995). *Comput. Statist.* 10, 129-141
  (bounded-variable least squares, scipy's `bvls`).
- Coelho, A. A. (2005). *J. Appl. Cryst.* 38, 455-461 (BCCG); (2018).
  *J. Appl. Cryst.* 51, 428-435 (the λ schedule).
- WP-0601 (the LM driver), WP-1113 (the two drivers' basins), WP-1929.

## Handover log

- **2026-10-09** — created from WP-1929's second session. No open WP owns the
  driver: 0601 and 1113, which built and measured it, are closed; 1467 only
  names it in a suggestion.
