# WP-1936 — a forward-difference step sized by its parameter

Milestone: unscheduled · Status: ✅ 2026-10-09 — a width's FD step is sized by its unit; one minimum per fit at every step
Track: What fires, and what stays silent
Depends on: —

## Goal

Every forward-difference Jacobian column in `optimize/least_squares.py` is
taken with a step sized to its parameter's own scale. A converged fit's
minimum no longer depends on the step constant: the LaB₆ + cBN fit in physical
coordinates reaches one χ² at steps 1e-6, 1e-7 and 1e-8 of that scale.

## Context

**Where the step is.** Two sites, both `h = 1e-6 · max(1, |θ_c|)` in the
solver's coordinate: `_peak_chain_column` (the per-reflection scalar FD
behind the analytic peak chain) and the `fd_cols` loop in `_make_jacobian`
(the whole-model fallback). In softplus coordinates the step is effectively
relative, because u ≈ ln p for a small p. In identity coordinates it is
*absolute* for every parameter under 1, so a width of 1e-3 deg² is stepped by
a tenth of its size.

**Measured 2026-10-09** (WP-1929's second session and its adversarial review,
macOS arm64, `[dev]`, tree `35f4ac14`, softplus entries made identity with
`lo = max(lo, 0)` by a monkeypatch of `ParameterTable.__init__`):

- On LaB₆ + cBN at the TRF endpoint, `profile.w` (on its floor) has a forward
  column 1.47e-2 off a central difference at h = 1e-6, 1.5e-3 at 1e-7 and
  1.5e-4 at 1e-8: truncation error, linear in h. `profile.v`: 1.4e-3. The
  softplus step gave 1.7e-5.
- The step chooses the basin. Physical coordinates under TRF reach χ²_red
  9.661408 at h = 1e-6, 9.689010 at 1e-7 and 9.686655 at 1e-8. Under the LM
  driver with a BVLS step (WP-1937): 9.687–9.688, then 9.840220 at both
  smaller steps. Each point is a genuine minimum: each driver polishes the
  other's endpoint and stays there. The valley is `RESOLUTION_UNCONSTRAINED`
  (the Gaussian triple clamped), which WP-1930's protocol now holds.
- LaB₆ + cBN's degenerate plan moves the same way (5.450264 at 1e-6, 5.4397
  at 1e-7 and 1e-8). The other nine fits run (BT-1 both histograms, NAC, FAP,
  Si 640c, a capillary fit, the absent phase, brucite, corundum) keep their
  minimum across the three steps to within 2e-6 relative.
- `COLUMN_REL_L2_MAX` in `tests/test_cross_backend.py` is 2e-2, so a 1.5 %
  column passes the agreement matrix with 25 % margin.

**What a scale can come from.** `help.py` carries each family's unit and
typical range. WP-1930's `FLOOR_SEEDS` (`params/vector.py`) sizes a seed per
width unit (1e-3 of a degree, of a degree², and so on). Either gives a
per-parameter scale s, and the step becomes `h = ε · max(s, |p|)`. The
alternative is analytic width columns, which remove the step for the peak
chain altogether. The bar for either is the oracle rule in root CLAUDE.md: a
column is checked where its check is exact (a linear parameter at a 100 %
step; a central difference otherwise).

**Probe toggles used to measure this** (not committed): an env var scaled the
step constant at both sites, and a helper took the step in physical space for
a softplus row and chained it by dp/du. Re-create them from these two lines
rather than looking for them.

## Non-goals

- The coordinates themselves: WP-1938. This WP lands first and is correct in
  either coordinate system.
- Which minimum LaB₆ + cBN *should* reach: WP-1930's held protocol decides
  that.

## Tasks

- [x] Choose the scale: `help.py`'s typical range, `FLOOR_SEEDS`' unit table,
      or analytic width columns. Measure each against central differences on
      the LaB₆ + cBN and brucite endpoints, every free column.
      `FLOOR_SEEDS` for an identity row, measured against the jax Jacobian.
      `help.py`'s `typical` is prose with no live authority, and analytic
      width columns were not needed.
- [x] One step function used by both FD sites, with the scale's source in its
      docstring. `least_squares.fd_step` and `_fd_typicals`.
- [x] Tighten `COLUMN_REL_L2_MAX` (or add a per-family bar) so a 1 % column
      error fails `tests/test_cross_backend.py`, and add a config with a width
      on its floor. The fp64 rows' bar is `REL_L2_MAX` = 5e-3, which a 1 %
      column already fails, so no bar moved. The `sharp_widths` config is the
      coverage that was missing; it fails under the old step.
- [x] The step-invariance check: the twelve-fit grid at three step constants,
      in both coordinate systems. No minimum moves by more than 1e-6 relative.
      Holds for every fit whose endpoint is reproducible at one step (2026-10-09
      handover has the table). Brucite with the Stephens block is not: a 1e-12
      change to the step spans 3.3e-5 in χ² under either rule.
- [x] Tests, and every golden that moves listed in the handover with its
      reason.
- [x] Skill: none expected (no new code or verb). None needed.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_acceptance_lab6_cbn.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1929 (the measurement), WP-1930 (`FLOOR_SEEDS`, the held Gaussian
  triple), WP-1121 (an oracle must be exact where its branch is).
- Dennis, J. E. & Schnabel, R. B. (1996). *Numerical Methods for Unconstrained
  Optimization and Nonlinear Equations*, SIAM, § 5.4 (forward-difference step
  sized by a typical value of the variable).

## Handover log

### 2026-10-09 (2nd session) — the step sized by its unit; closed

A Jacobian column for a peak width is now accurate on a sharp instrument, and
the fit's answer no longer depends on the size of the finite-difference step.
The Caglioti terms had been stepped by an absolute 1e-6 deg², which on 11-BM is
a tenth of a peak's own variance. Twelve acceptance fits now reach one χ² at
steps of 1e-6, 1e-7 and 1e-8, in both coordinate systems, wherever the fit
converges at all. The fix is a size per unit, read from the table WP-1930
already uses to seed a floored width. It is not analytic width columns, which
were not needed. Two things it does not settle: which LaB₆ + cBN basin is
right, and why brucite with a Stephens block is chaotic under any step.

- *Done.* `least_squares.fd_step(theta_c, typical)` is the one step rule,
  `FD_STEP · max(typical, |θ|)` (Dennis & Schnabel 1996 § 5.4), and both FD
  sites call it. `_fd_typicals(table)` gives an identity row `FLOOR_SEEDS`'
  size for its unit when its lower bound is at least 0 or its unit is deg².
  Every other row keeps 1, so softplus rows are bit-identical. The agreement
  matrix gains `sharp_widths` (11-BM LaB₆, `w` an identity row at 0), and its
  central-FD reference takes the same typical sizes. `test_jacobian` pins
  which rows get which size. `FLOOR_SEEDS`' comment names its second reader.
  The 1.8 notes stage the moved numbers.
- *Measured* (macOS arm64, `[dev,jax]`, merged tree `541e8f7f` plus this
  branch). Task 1, every free column against the jax Jacobian at the final
  endpoint:

  | column | old step, 1e-6 / 1e-7 / 1e-8 | sized step, 1e-6 / 1e-7 / 1e-8 |
  |---|---|---|
  | LaB₆ + cBN `w`, identity on its floor | 1.5e-2 / 1.5e-3 / 1.5e-4 | 2e-8 / 1e-7 / 1e-6 |
  | LaB₆ + cBN `v` | 1.4e-3 / 1.4e-4 / 1.4e-5 | 4e-7 / 4e-8 / 5e-8 |
  | LaB₆ + cBN `u` | 1.7e-4 / 1.7e-5 / 1.7e-6 | 4e-7 / 4e-8 / 4e-8 |
  | `sharp_widths` `w` / `v` / `u` at 1e-6 | 9.3e-2 / 9.5e-3 / 1.8e-3 | 1.1e-7 / 9.7e-8 / 2.2e-8 |

  Every other column on LaB₆ + cBN and brucite (cell, biso, Stephens, zero,
  displacement) was within about 1e-6 under both rules. Task 4, χ²_red at
  FD_STEP 1e-6 / 1e-7 / 1e-8, relative spread:

  | fit | softplus | physical |
  |---|---|---|
  | LaB₆ + cBN, `u v w x y` free | 9.793673, 8.2e-8 | 9.840220, 2.4e-10 |
  | LaB₆ + cBN shared / degenerate | 10.151815 / 5.934160, ≤ 4e-11 | the same, ≤ 3e-12 |
  | BT-1 neutron, NAC, FAP, capillary, absent phase | ≤ 3.5e-12 | ≤ 2.2e-11 |
  | Si 640c | 4.1e-8 | 1.5e-7 |
  | brucite iso, corundum | 1.1e-8, 1.5e-7 | `max_iter` (WP-1937) |
  | brucite + Stephens | 1.2e-2, one run `max_iter` | `max_iter` |

  Under the old step the free-Gaussian LaB₆ + cBN reached 9.661408 in both
  coordinate systems. The sized step lands on the higher basin in both. Brucite
  + Stephens is chaotic at a fixed step: four steps differing by 1e-12 gave
  7.635871 to 7.636119, and two of eight runs stopped on `max_iter`, under the
  old rule and the new alike.
- *Gotchas.* A unit cannot tell a width from an offset. The first version
  sized every deg row, and the zero shift's column moved from 2e-9 to 3e-6
  against jax on every golden state: position is linear in it, so a 1e-9° step
  only adds rounding. The lower bound is what separates them now. The WP's
  premise that `COLUMN_REL_L2_MAX` = 2e-2 governs the matrix was half right. The
  fp64 rows use `REL_L2_MAX` = 5e-3, which a 1 % column already fails. The gap
  was a missing sharp state, so no bar moved. With jax on, every existing
  config's worst live column is ≤ 2.3e-4 (`extra_peak`), axial kinks aside.
- *Goldens moved.* `toy_rich` and `srm660c` (darwin/arm64), the `u` and `v`
  columns only, each closer to jax: `srm660c` `u` 8.8e-4 → 1.5e-7 and `v`
  2.1e-4 → 2.7e-7; `toy_rich` `u` 1.3e-5 → 4.7e-6 and `v` 1.8e-5 → 3.0e-6.
  `test_lebail_alternation`'s +0.4 % run now splits by platform at pass 5.
  It agrees to every printed digit for four passes (17.032, 14.118, 14.036,
  14.032). Then macOS arm64 drops to 13.774 and stops at pass 6 on 13.773,
  and Linux x86-64 stops at pass 5 on 14.031, the answer both reached
  before. The PR's first CI run failed on all four Linux legs over this,
  because the first re-pin froze the macOS side. The test now asserts the
  stop rule and the four shared passes, and bounds the end by them.
  #857 (WP-1547) then rewrote the file at 5.1-25° on the same rule, and the
  merge took its version whole. Its two pinned runs (+0.3 %, +2 %) read the
  same to six digits under the old step and this one, on macOS arm64.
- *Not generalised, on purpose.* Seventeen test oracles copy the old
  `1e-6 · max(1, |θ|)` step (`test_restraints`, `test_voigt`, `test_pawley` and
  others). They are whole-model references on wide lab peaks and pass, so they
  stay. The diagnostic FD probes in `refine.py` (`SCALE_B_STEP`, the magnetic
  axis probe) carry their own justified steps and are not Jacobian columns.
  The multi-histogram central-FD reference in `test_cross_backend` keeps the
  old step: `MULTI_GLOBS` frees only the softplus `w`, so nothing it covers
  moves.
- *Review* (`/code-review high --fix`). Six findings. Fixed: a named variable
  with no unit that drives `u` or `v` kept the step of 1 (1.8e-3 and 9.5e-3 off
  on `sharp_widths`). It now reads the row `_column_identities` names, divided
  by its coefficient in C (9.3e-8, 9.9e-8), with a test. Also fixed: a spacing
  slip, the matrix reference copying the step rule instead of calling
  `fd_step`, a docstring that called every row bounded at 0 a width, and a
  1.8 note that named only `u` and `v`. Declined: the multi reference (above).
- *Counts* (macOS arm64, `[dev,jax]`, `origin/main` `deed30b5` merged). Fast
  selection: 9054 passed, 112 skipped, 1 xfailed. This WP added 9 cases: 2
  test functions (0.01 s together) and 7 `sharp_widths` rows, of which 4 pass,
  2 skip without torch and 1 skips for having no axial column. Full
  selection: green, 9346 passed, 119 skipped, 1 xfailed. Not a quotable
  count: two other sessions' pytest processes were running when it
  launched, so the nightly is the figure to trust.
- *Session.* Cut from WP-1930's unmerged branch, since this WP reads
  `FLOOR_SEEDS`. #849 merged mid-session and `origin/main` was merged in.
  Forward references went to WP-1937 (the LaB₆ table's TRF row is the old
  step's basin) and WP-1938 (`_fd_typicals` reads the transform and the bound;
  two baselines that are not minima). WP-1938 re-rated: only 1937 blocks it now.
- *Next.* Nothing here. WP-1937 is the next rung of WP-1929's P1, and should
  compare drivers against the sized step's basin.

- **2026-10-09** — created from WP-1929's second session. No open WP owns the
  FD step: 1121 and 1112, which last changed these sites, are closed.
