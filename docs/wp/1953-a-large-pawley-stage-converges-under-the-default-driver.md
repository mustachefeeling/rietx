# WP-1953 — a large Pawley stage converges under the default driver

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-11 — a Pawley fit above 128 columns stops a stage on its budget under the default and lands worse than TRF; few fits run that path, and `solver="trf"` is the workaround

## Goal

A Pawley fit with more than `lm.BVLS_MAX_COLUMNS` (128) columns converges
every stage under the default LM driver, rather than crawling to its
evaluation cap. Whether LM and TRF then reach the same answer on such fits is
measured and written down.

## Context

**What landed before this.** WP-1937 built the LM driver (`optimize/lm.py`).
Its box step is exact up to 128 columns (BVLS on the eigendecomposed normal
matrix, `_solve_step`) and BCCG's above (`optimize/bccg.py`), because scipy's
BVLS refactors the free set at each active-set change. WP-1938 made LM the
default (#883, merged 2026-10-11). A Pawley fit appends one column per
reflection, so it is the fit that crosses 128.

**The seam.** `lm._solve_step`'s `n > BVLS_MAX_COLUMNS` branch calls
`bccg.solve(A + lam·diag(d²), b, …)`. The inner loop in `lm.minimize` reads
the taken step's promise, `−stepᵀb`. A promise ≥ 0 raises λ and retries
without evaluating (the `promise >= 0.0` branch). A promise under the fp64
floor ends the stage `exhausted_fp64`.

**The measurement that filed this** (WP-1938's fifth session, macOS 26.6.2
arm64, `[dev,jax]`, one run each under load). FAP.XRA from
`tests/test_acceptance_fap.build_fap_inputs()`, `mode="pawley"`, default
plan, 343 columns at the `profile` stage:

| arm | `profile` stage | Rwp | wall |
|---|---|---|---|
| `main` `6075319c` (TRF, before the flip) | converged | 0.07825358 | 20.2 s |
| TRF, after the flip | converged | 0.07838295 | 11.0 s |
| LM as shipped (BCCG above 128) | 400-evaluation cap, 635 box solves | 0.08035928 | 16.7 s |
| LM, exact step at every size | converged | 0.08028663 | 6.3 s |
| LM started from TRF's answer | converged | 0.07825264 | |

Two findings sit in that table.

1. **BCCG's steps often promised no descent.** The crawling stage made 635
   box solves for 400 evaluations. Only the no-descent branch retries
   without evaluating, so about 235 steps were rejected there and λ raised.
   On eight systems sampled from the stage, BCCG's step left its own damped
   model ½sᵀ(A + λD)s − bᵀs above zero, worse than not moving, at six of
   the seven with λ > 0 (+0.05 down to +7e-6). The exact solve's value was
   below zero at all eight. WP-1937 had measured BCCG 5-22 % short of the
   exact model minimum on synthetic systems, never on the wrong side of
   zero.
2. **LM settles in a worse place than TRF from the default start.** The
   exact-step LM converges at 0.08029, TRF at 0.07838, and LM started at
   TRF's answer keeps it. The refined profile parameters of the two answers
   differ by at most 1.5 esd, so the gap is mostly in the intensities. NAC
   Pawley (142 columns) went the other way under WP-1937: LM 0.13478453
   against TRF 0.13628068, on either step. So it is not yet known whether
   this is a driver property or one fixture's landscape.

**What the exact step costs** (WP-1937, synthetic Pawley-shaped systems, per
solve, exact against BCCG): 2-34 ms against under 1 ms at 128 columns,
0.13-0.8 s at 400, 1.5-11 s at 1000, 10-177 s at 2000 against at most 22 ms.
On FAP the exact-step fit was the faster one, because it converged.

**The constrained step is not the cost here.** WP-1938's lane found no
Pawley fit crossing a linear-inequality row, and `nnls` never ran out of
iterations on any of 16 fits. Forced onto FAP's systems the constrained step
took 42-70 ms at 343 columns.

**The standard remedy to weigh.** A trust-region step need only achieve a
fraction of the Cauchy point's model decrease to keep the global convergence
argument (Nocedal & Wright 2006, *Numerical Optimization*, §4.1-4.2). The
projected-gradient step along −b is cheap at any size, so a step that
promises less could fall back to it. That is a candidate, not a decision.

### Inherited

- **2026-10-12, from WP-1929 (maintainer's call that day): LM also stops
  early beside a vanishing column.** A second crawl in the same seam, moved
  here because it is the same `lm.py` step and stop and the same grid to
  re-measure. A moment angle's column scales with its modulus and vanishes at
  a direction the symmetry fixes. `_solve_step` scales every column to unit
  norm, so that angle takes the largest step, and λ grows until every
  parameter crawls. `ftol_runs` then fires on three tiny decreases in a row
  and reports `converged`. Measured in WP-1938 D12 (macOS arm64, `[dev,jax]`):
  the two-site Pnma set (`tests/test_pair_diagnostic_class.py`) released
  stopped at χ² 454 660 with λ 5e7-7e9, against 2555.8 under TRF.
  `solve_magnetic` frees the moduli first (`magnetic.SOLVE_STAGE_NAMES`) and
  reaches 2556.06, but a plan a user builds gets no such stage.
  `tests/test_magnetic.py`'s `_LM_FALSE_CONVERGENCE` row is the same stop on
  one site (λ ≈ 1e11, χ²_red 11.03; a fresh LM solve from there reaches
  χ² 4e-16 in 17 evaluations) and stays a strict xfail until this lands. Two
  remedies were named and not measured: count a decrease toward `ftol_runs`
  only while λ is small, and give an angle column a scale floor from its
  finite-rotation response. MINPACK's `mode=1` scaling (each column's
  largest norm so far) is the documented form of the second. Either moves
  every default fit's iterates, so the goldens and the acceptance grid are
  re-measured. WP-1929 keeps the esd half of the stationary angle.
- **2026-10-12, from WP-1929: the exact angle column, parked on branch
  `wp1953-central-angle-columns` (`87c6d6de`, cut from `main`, no PR).** The
  analytic azimuth column at a direction the symmetry fixes was not zero.
  `optimize/least_squares._peak_chain_column` forward-differences each
  reflection's scalars with h = 1e-6·max(1, |φ|), and at a stationary point
  that quotient is I''·h/2: 0.009801 (Mn1) and 0.001328 (Mn2) on the two-site
  Pnma set, issue #831's numbers, and 0.1038 / 0.0042 on the polar angles at
  θ = π/2. Central differences at h = 1e-2…1e-8 give ≤ 2e-12. The branch
  differences moment angles centrally and adds a `magnetic_stationary`
  cross-backend config plus an exact-zero test; both fail before (rel-L2
  7.79e-3 against the 5e-3 bar) and pass after. It is parked because the
  exact zero column sets off the crawl above: under LM,
  `test_magnetic_moment_frame` [103.0] goes from χ²_red 0.978 to 5.861,
  still `converged`, and [101.1] from 0.978226 to 0.979134. Under TRF all six
  arms keep 0.978226. Land it with the driver fix and re-measure those four
  tests (macOS arm64, `[dev]`, WP-1929's lane).

## Non-goals

- When a stage that is improving little should stop and say so: WP-1334.
- Esds at a stopping point beside a flat column: WP-1929.
- The constrained step's cost and its `nnls` fallback: measured and closed in
  WP-1938.

## Tasks

- [ ] Measure before deciding: every Pawley fixture above 128 columns the
      suite or the examples can build (FAP.XRA at least, and a wider range of
      NAC or a round-robin pattern if one crosses 128), under TRF, LM as
      shipped and LM with `lm.BVLS_MAX_COLUMNS = 10**6`. Record per stage the
      termination, the count of BCCG steps promising no descent, and the
      seconds per step.
- [ ] Decide the step above 128 columns when BCCG promises no descent (the
      exact step, a Cauchy-point fallback, a tighter BCCG, or a higher cap),
      and record it here as `Decided YYYY-MM-DD:`.
- [ ] Implement it, with a test on a system where BCCG's step promises no
      descent.
- [ ] The basin: five starts 1e-14 apart per fixture under both drivers.
      Write down whether LM's and TRF's answers differ by start or by driver.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/` for each Pawley fit whose
      answer moves.
- [ ] Skill: `references/surprises.md` §8.31 says a large Pawley stage can
      stop on its budget under LM. Remove it, or restate it, once this lands.

## Acceptance

Every stage of FAP.XRA's Pawley fit converges under the default driver, and
its Rwp sits within the five-start spread of TRF's or the difference is
written down as a property of the fixture.

```sh
.venv/bin/python -m pytest tests/test_pawley.py tests/test_lm_solver.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1937 (the driver and the 128-column split), WP-1938 (the default flip,
  and the fifth session's handover entry with the measurement).
- Nocedal, J. & Wright, S. J. (2006). *Numerical Optimization*, 2nd ed.,
  §4.1-4.2. New York: Springer.

## Handover log

- **2026-10-11** — Filed from WP-1938's last open task when #883 merged
  without a fix. No open WP owns the step above `BVLS_MAX_COLUMNS`. WP-1334
  owns stopping a stage that improves little, which would shorten this
  crawl but not end it, and WP-1929 owns esds. Next: the first task, since
  the decision needs more than one fixture.
