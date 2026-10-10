# WP-1937 — a bounded step solved exactly

Milestone: unscheduled · Status: ✅ 2026-10-10 — the LM step is exact inside its bounds; the default flip moved to WP-1938
Track: What fires, and what stays silent
Depends on: 1936 soft, landed 2026-10-09 (a step constant moved the LaB₆ basin under either driver; it no longer does)

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

The LaB₆ + cBN row is the old FD step's basin. Since WP-1936 (2026-10-09) the
Caglioti `u`, `v` and any identity width bounded at 0 take a step sized by
their unit (`least_squares.fd_step`, `_fd_typicals`), and LaB₆ + cBN with
`u v w x y` free reaches χ²_red 9.840220 under physical + TRF at FD_STEP 1e-6,
1e-7 and 1e-8 (spread 2.4e-10), and 9.793673 under softplus + TRF. Compare
drivers against that basin. Brucite and corundum under physical + TRF still
stop on `max_iter`.

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
  LM's cap of 100 where TRF converges in 136 evaluations at the same χ².
  *Superseded in part 2026-10-10:* `n_iterations` was already `nfev` on both
  drivers (`run_least_squares` reads `res.nfev` for either); only the manual
  called it iterations.
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
- [x] The twelve-fit grid plus the Pawley, Le Bail, multi-histogram,
      magnetic and sequential suites under the new driver, in both coordinate
      systems. Every acceptance number that moves listed with its reason.
      (`examples/probe_driver_grid.py`; the table and the suite failures are
      in the 2026-10-10 handover entry.)
- [x] ~~Flip the default (`Refinement(solver=)`), keep `"trf"` selectable,
      and rewrite `lm.py`'s docstring and the manual's solver section.~~ Moved
      to WP-1938 2026-10-10 (maintainer). LM in softplus coordinates splits 7
      of 14 grid fits against today's 3, so the driver and the coordinates
      switch together.
- [x] Tests, plus obs/calc/diff PNGs to `tests/output/` for the fits whose
      answer moves. (Tests for items 1-4. No default answer moves here, so no
      PNGs; the moved fits' PNGs go with the flip in WP-1938.)
- [x] ~~Skill: the solver row in the skill's references, if it names TRF as
      the default.~~ Moved to WP-1938 with the flip. The default is unchanged
      here.

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

- **2026-10-10** — closed; the default flip moved to WP-1938. The package's
  own Levenberg-Marquardt driver now solves each step exactly inside the
  parameter bounds. A parameter it ends on a bound sits on it, and it reports
  which. It stopped calling a stage that starts at its minimum "diverged", and
  its budget is counted in residual evaluations, as the default driver's is.
  The switch of default did not happen. Run in today's softplus coordinates,
  this driver gave more than one answer on 7 of 14 acceptance fits, against 3
  for today's default. In physical units it gave one answer on 13 of 14, with
  no stage out of budget. The maintainer moved the switch to WP-1938, so the
  coordinates and the driver change together, and WP-1938 merges after the
  kernel change of WP-1940. Nothing a default user runs has changed.
  - *Done.* `c65ff59d` the BVLS step with its eigenvalue cut (m·ε·λmax, the
    rounding scale of one entry of JᵀJ). `614f24a8` one status vocabulary and
    one budget for both drivers; the manual and the summary line say
    evaluations. `ea5ea10b` `LSQOutcome.active_bounds` from both drivers.
    `790c7ce7` BCCG kept above 128 columns. `935c0b8e` Inherited pruned.
    `ec62f383` `examples/probe_driver_grid.py` and the moved items. `d7237c27`
    forward references. `f0c690a6` the release record and the staged notes.
    Review fixes `4708b855`, `2096fea2`, `12143bfa`, `d3f43b12`; `f9a65056`
    the grid on the final tree; `db311116` two fixes from the fast suite.
  - *Measured* (macOS arm64, `[dev]`). Fourteen fits, five starts each with
    every start value × (1 + k·1e-14), χ²_red spread (max − min)/min, ✗ at
    or over 1e-9, "mi" where a stage stopped on `max_iter`. Physical + LM is
    the final tree (`f9a65056`); the other three columns are the lane's run
    at `790c7ce7`, whose LM start was still nudged 1e-12 off its bounds.

    | fit | softplus TRF (today) | softplus LM | physical TRF | physical LM |
    |---|---|---|---|---|
    | LaB₆ + cBN shared | 4.0e-10 | 4.0e-10 | 4.0e-10 | 4.0e-10 |
    | LaB₆ + cBN degenerate | 7.0e-10 | 1.5e-3 ✗ | 7.0e-10 | 7.0e-10 |
    | LaB₆ + cBN, `w` then `u v x y` | 4.1e-10 | 4.9e-3 ✗ | 4.1e-10 | 4.0e-10 |
    | LaB₆ + cBN, `u v w x y` together | 5.2e-10 | 4.3e-4 ✗ | 3.9e-6 ✗ | 4.1e-10 |
    | BT-1 X-ray | 9.1e-12 | 9.5e-12 | 9.3e-12 | 9.3e-12 |
    | BT-1 neutron | 5.1e-11 | 7.0e-5 ✗ | 8.3e-12 | 8.3e-12 |
    | NAC | 7.1e-11 | 7.0e-11 | 6.9e-11 | 6.9e-11 |
    | FAP | 2.9e-11 | 3.2e-11 | 3.0e-11 | 2.6e-11 |
    | capillary | 2.3e-10 | 2.3e-10 | 2.3e-10 | 2.3e-10 |
    | absent phase | 5.9e-12 | 1.2e-11 | 5.2e-12 | 5.3e-12 |
    | Si 640c | 4.9e-11 | 1.7e-10 | 2.2e-11 | 4.7e-11 |
    | brucite | 1.7e-9 ✗ | 4.9e-2 ✗ | 7.6e-6 ✗ mi | 2.8e-10 |
    | corundum | 1.8e-7 ✗ | 7.0e-3 ✗ | 1.8e-6 ✗ mi | 3.3e-12 |
    | brucite + Stephens | 2.1e-2 ✗ mi | 3.5e-2 ✗ | 1.6e-3 ✗ mi | 2.1e-6 ✗ |

    Brucite under physical LM spread 1.1e-8 at `790c7ce7`. Its exactly
    degenerate width pairs split differently per start then, so the 2.8e-10
    may be this platform's luck (WP-1938 reruns it). Softplus LM drives widths
    to u ≈ −400, where their columns are noise, and stages end on `ftol_runs`
    after moving Biso by 4e-9. Residual evaluations over twelve fits: 1292
    today, 1065 physical LM, 2717 physical TRF. The step's cost on
    Pawley-shaped systems, BVLS against BCCG per solve: 2-34 ms against
    under 1 ms at 128 columns, 0.13-0.8 s at 400, 1.5-11 s at 1000, 10-177 s
    at 2000 against at most 22 ms; BCCG lands 5-22 % short of the exact model
    minimum. NAC Pawley (129 reflections + 13): LM Rwp 0.13478453 on either
    step, TRF 0.13628068. The suites under LM forced (the lane, `790c7ce7`,
    455 tests in the fourteen files item 5 names, slow included): TRF 455
    passed; softplus LM 443 / 12 failed; physical LM 439 / 16; physical TRF
    434 / 21. Each failure and its reason is in WP-1938's Inherited.
    Fast selection on this tree: 9000 passed, 177 skipped, 1 xfailed and 3
    failed; the three were the index (stale, regenerated), a test stand-in
    for scipy's result without `active_mask`, and the probe's newline, each
    rerun green after its fix (`db311116`). The branch adds 10 test functions
    (17 cases, +11 in `test_lm_solver.py` and +6 in `test_solver_seam.py`,
    checked by collecting origin/main's versions), 0.90 s in this run, none
    in the tail. Full selection on `0d5218d5`, which is current main merged in (main had not moved): 9298
    passed, 186 skipped, 1 xfailed, none failed; no other pytest was running at its start.
    Lanes: one, the grid (estimated 40 requests, took 162; lane $10.94 against
    $19.78 in-session, +$8.61 saved, +25 % of the session); one kept, Pawley
    (estimated 12, took 16). The replay's selective policy: −23 % at u = 0K.
  - *Review* (`/code-review high --fix`, 8 findings). Fixed by the review:
    the LM start is no longer nudged 1e-12 off its bounds, which dropped a
    restarted held value out of the active set; a non-finite start raises,
    as TRF's does; the slow NAC golden and four texts said "it" or "TRF
    caps". Fixed here: the active set is exact only up to the BVLS cut, and
    a zero step is named under `exhausted_fp64`. Declined and forwarded to
    WP-1938, since either change moves converged fits: `lsq_linear`'s status
    is ignored (BVLS can stop at status 2), and `eigh` is recomputed per λ.
    `examples/tutorials/02_simple_rietveld.ipynb`'s committed output still
    prints "2 it"; it changes at the next notebook rebuild.
  - *A finding superseded.* Context said `n_iterations` was nfev on one
    driver and outer iterations on the other. Both already read `res.nfev`;
    only the manual called it iterations.
  - *Gotchas.* scipy's BVLS refactors the free set at every active-set
    change, so its cost is n³ per change. `_solve_step` cites Higham (2002)
    §3.1 for the inner-product rounding bound; the book was not opened this
    session. The probe's `physical` arm is a monkeypatch of
    `ParameterTable.__init__`; once WP-1938 lands the two coordinate arms are
    the same.
  - *Forwarded.* WP-1938: the flip and its texts, the two brucite tasks, the
    16 suite failures, the moved numbers, the two declined review findings;
    re-rated P1, and 1940 soft added to its dependencies (maintainer, same
    day). WP-1929: the active set exists. WP-1467: the flip moved. WP-1334:
    `"diverged"` has no writer on either driver.
  - *Next.* (1) WP-1940 lands. (2) WP-1938 folds its Inherited into Tasks,
    does the kernel-independent tasks, then reruns
    `examples/probe_driver_grid.py` after 1940 and lands the coordinates and
    the flip in one PR. (3) No release is owed by this close: it fixes no
    answer under the default driver, so WP-1929's P1 is still open until
    WP-1938 ships.

- **2026-10-09** — created from WP-1929's second session. No open WP owns the
  driver: 0601 and 1113, which built and measured it, are closed; 1467 only
  names it in a suggestion.
