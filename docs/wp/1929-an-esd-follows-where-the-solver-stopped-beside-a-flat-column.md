# WP-1929 — an esd follows where the solver stopped beside a flat column

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1930 soft: the floor-seeded row, which moves the minimum rather than the esds)
Priority: P1 2026-10-08 — was P2: the maintainer decided (condition on a floor row), so nothing waits; a reported esd 2-10× apart on two machines at one χ², nothing flagged

## Goal

A fit reports the same esds on every platform when it reaches the same
minimum. A column that vanishes analytically at the answer (a parameter on
its softplus floor, a moment angle at a stationary direction) no longer
decides its neighbours' esds by where rounding left the solver.

## Context

Issues #831 (the diagnosis) and #836 (the proposed general fix), both
mustachefeeling, 2026-10-08. Found while bisecting #820, whose first slow
test counts `MOMENT_PAIR_DEGENERATE` rows (WP-1418's Inherited; PR #829
relaxes that count).

**What was measured** (#831's comment, `main` at `c00c4ef8`, Linux x86-64
numpy 2.5.3 and macOS arm64 numpy 2.5.2 with Accelerate, each deterministic):

- `tests/test_pair_diagnostic_class.py`'s magnetic case, class 0. Same χ² to
  9 figures, same moments. Mn1 esd 0.0022 against 0.0064, Mn2 0.0037 against
  0.035, ρ(Mn1, Mn2) −0.50 against −0.96.
- **The esds follow θ, not the machine.** Each machine's covariance at the
  other's final θ reproduces the other's esds to 4 figures, and swapping J
  between the two arithmetics does too. Not BLAS, not the stage caps, not a
  stale Jacobian.
- **The column.** Both moments lie along **a**, so the azimuth φ = π is a
  stationary point of the intensity. The azimuth columns have norms 0.06-2.9
  against 1180 for the moduli. `optimize.statistics.normal_factors` Jacobi-
  equilibrates them to unit norm (root CLAUDE.md, the equilibration rule), so
  their *direction*, set by how far from π the solver stopped, decides the
  moduli esds. Mn2's variance sits in one eigenvector (φ and m of both
  sites), eigenvalue 3.0e-2 on Linux and 3.5e-4 on macOS.
- **Decisive arm.** With the two azimuth columns left out of JᵀJ, the moduli
  esds agree at all four points tried (two machines × default and raised
  caps): 0.00151 / 0.00121 / ρ −0.20. At the exact minimum the azimuth column
  is zero and the Hessian is block-diagonal in (m, φ), so that is the limit.
  Converging harder does not settle the full-covariance number: polishes at
  ftol 1e-12 and 1e-15 move the Mn2 esd anywhere from 0.0035 to 0.47.
- **Not magnetic only.** BT-1 neutron, `test_acceptance_wavelength._solo(1)`
  (`mccusker_structural`): identical θ except `instrument.profile.y` on its
  floor. Linux reaches internal θ = −514, where the column underflows to
  exactly 0, so the row is dead and its esd `None`. macOS stops at θ = −25.5,
  a live column of norm 1.1e-8. `profile.x`'s esd is 0.00322 against 0.00664
  (2.06×). Zeroing that one column in the macOS J reproduces the Linux esd to
  7 digits. FAP and SRM 660c agree between the machines to a ratio of
  1.0000002. LaB₆ + cBN, at the tree where both machines still reached one
  minimum (`d2f683a0`, WP-1930), has u and v esds 3× and 5× apart from `w` on
  its floor.
- **A side finding for whoever touches the Jacobian.** The analytic azimuth
  column is not quite zero at φ = π: against central differences at
  h = 1e-2…1e-8 its error is 3.4e-3 / 6.8e-4 relative on macOS and
  6.8e-2 / 2.2e-2 on Linux, step-independent, the same absolute ~0.0098
  (Mn1) and ~0.0013 (Mn2). Not the cause (the 2×2 holds J fixed). The
  cross-backend matrix's magnetic configs may not cover a moment at a
  stationary direction.

**Checked against the tree at `a3f9140a`** (this worktree's `[dev]` venv,
macOS arm64): the BT-1 macOS half reproduces to every printed digit —
χ² 1.927982547556535, `profile.x` 0.038644 ± 0.006639, `profile.y`
8.06e-12 ± 0.01153. The magnetic case was not re-run here (311 s a test on
this machine, WP-1418's entry). `live = d > 0.0` is at
`optimize/statistics.py:141` and `:183` (`normal_factors` and its sibling),
and `inv_d > 0.0` at `:295` (`normal_covariance`); `PINV_RCOND` = 1e-15
(`:52`) is not involved, the issue's smallest relative eigenvalues being
1e-8 to 1e-10.

**The proposals** (#831's comment and #836):

1. `live = d > rtol · max(d)` after equilibration, rtol declared (1e-12).
2. Rows `staged.bound_untested` names (a row on its transform's floor), and
   moment angles below `MOMENT_DIRECTION_SUPPORT` in first-derivative
   response while the finite-rotation probe says they are determined, leave
   the normal matrix. Their esd is `None` with a `STATIONARY_COLUMN`
   diagnostic. A floor row's upper bound could come from its own
   one-parameter variance.
3. Failing those, a diagnostic that a live column's norm is a tiny fraction
   of its overlap set's, saying the neighbours' esds are conditional on where
   the solver stopped.
4. `profile_interval(path)` (Venzon & Moolgavkar 1988) for a user who wants a
   number for such a parameter.

(#836's third item, seeding or flagging a softplus row freed at its floor, is
WP-1930's.)

**Two documented choices the proposals reverse, which is why this WP waits on
a decision.**

- **Proposal 1 against WP-1463.** Root CLAUDE.md: "A tiny column is live
  (WP-1463)". `normal_covariance`'s docstring has the case: a softplus phase
  scale at 1e-166 has a column of 1e-158 and a physical esd of 7.66e-9 at every
  value tried, and the other phases' QPA esds are marginalised over it. A
  relative cutoff of 1e-12 kills that column. So proposal 1 as written is
  WP-1463 undone, and the BT-1 `profile.y` row and an absent phase's scale are
  the same shape (tiny because dp/du is tiny at the floor, not because the
  model is flat in physical space).
- **Proposal 2 against `MOMENT_DIRECTION_SUPPORT`.** Its comment
  (`refine.py:713`) says the moment block holds its own flat directions
  *because* "widening that test to a relative one would change the esd of
  every fit in the package". The φ = π azimuth escapes the hold because the
  finite-rotation probe (0.1 rad) correctly sees a second-order response.
  The proposal treats the second-order-only direction as first-order
  unmeasured, which is standard (a Wald esd is undefined at a stationary
  point of the model), and moves every fit with a floor row.

What a decision has to settle: whether a row on an active floor is
*conditioned on* (left out, the active-set reading, and the BT-1 Linux
answer) or *marginalised over* (kept, WP-1463's reading). Conditioning makes
every esd point-independent; marginalising is what 1463 shipped for an absent
phase. Either is defensible, and they cannot both hold for the same row.

**Decided 2026-10-08 (maintainer): condition.** A row on its floor, as
`staged.bound_untested` names it, is treated as fixed for every other
parameter's esd, and reports no esd of its own. A caller who wants a number
for it gets a one-sided interval (#836 item 4). A moment angle at a
stationary symmetry direction is treated the same way, so only the modulus
carries an esd. Proposal 1, a relative cutoff on the column norm, is not
adopted: it keys on a column being small, and a tiny column away from a
floor is still live (WP-1463's case).

The precedents the decision rests on, gathered on the day:

- GSAS-II (`GSASIIstrMain.dropOOBvars`): a parameter past a limit is set to
  the limit, given esd 0 and frozen out of later refinements. Its other esds
  in that run still come from the matrix that included it.
- TOPAS (Technical Reference § 2.5): limits sit inside the solver (BCCG), and
  a parameter ending near one is tagged `_LIMIT_MIN_#`. Its forum's advice is
  to fix such a parameter where the limit is physical.
- MINUIT and lmfit: a transformed parameter's error is meaningless near its
  limit, because d(external)/d(internal) ≈ 0. The remedy is the error
  analysis redone without the limit, or a profile interval (MINOS).
- Self & Liang (1987): an estimate on the boundary has no symmetric
  sampling distribution, so no Wald esd.

What this reverses, in the commit that lands the rule: root CLAUDE.md's
WP-1463 clause and `normal_covariance`'s docstring, for a row on its floor.
An absent phase's scale is such a row, so the other phases' QPA esds become
conditional on it. WP-1463's stated goal (one answer whether the scale ended
at 1e-135 or at 1e-179) still holds. `MOMENT_DIRECTION_SUPPORT`'s comment is
rewritten in the same change.

### Inherited

(empty)

## Non-goals

- A minimum that differs between platforms (LaB₆ + cBN): WP-1930.
- The #820 pair count: WP-1418 and PR #829.
- A softplus coefficient read as a finding after the fit (`microstructure`'s
  `_reading`): WP-1914. Its "what does *at its floor* mean" task is the same
  question asked of a reader; settle it once and quote it from both.

## Tasks

- [ ] Measure WP-1463's absent-phase case both ways before changing it (the
      other phases' QPA esds conditioned on and marginalised over the floor
      scale), and record the before and after here.
- [ ] A fixture that reproduces the platform split on one machine: the BT-1
      fit with `profile.y`'s final internal coordinate set to −514 and to
      −25.5, `profile.x`'s esd compared.
- [ ] The chosen rule in `optimize/statistics.py` (one place, `normal_factors`
      and `normal_covariance` both), with its threshold's source in the
      docstring. Find every consumer of `live` and `unmeasured_rows`.
- [ ] Moment angles at a stationary direction: leave the normal matrix (or
      extend `MOMENT_DIRECTION_SUPPORT`'s hold to them, whichever keeps one
      authority), and rewrite that constant's comment.
- [ ] `profile_interval(path)`, the one-sided interval for a row on its
      floor (Venzon & Moolgavkar 1988).
- [ ] The diagnostic naming what was left out (`STATIONARY_COLUMN` or the
      decision's name), with `Diagnostic.suggestion` text.
- [ ] Siblings: `indexing/peakfit` shares `normal_factors` (the docstring
      says so); WP-1915's indexing propagation reads the same covariance.
- [ ] The analytic azimuth column at φ = π: check it against an exact oracle
      and add the config to `tests/test_cross_backend.py` if no row covers a
      moment at a stationary direction.
- [ ] Tests, and the acceptance suites' esds before and after, every row that
      moves by more than 1 % listed in the handover.
- [ ] Skill: a `references/judging.md` row for the new diagnostic, keyed by
      its code.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_covariance_scaling.py tests/test_pair_diagnostic_class.py tests/test_acceptance_wavelength.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The fixture's `profile.x` esd is the same at both internal coordinates. The
#831 class 0 moduli esds agree across the two platforms to 1 % (the
reporter offered to run Linux). No acceptance-suite esd of a parameter off
its floor moves by more than 1 % without a line in the handover saying why.

## References

- Issues #831, #836, #820; PR #829.
- WP-1463 (the tiny-column rule), WP-1327 (`MOMENT_DIRECTION_SUPPORT`),
  `bound_untested` (WP-1463), WP-1110 item 14 (equilibration).
- van der Sluis, A. (1969). *Numer. Math.* 14, 14-23 (equilibration).
- Golub, G. H. & Van Loan, C. F. *Matrix Computations*, § 5.4 (rank-revealing
  tolerance).
- Self, S. G. & Liang, K.-Y. (1987). *J. Am. Statist. Assoc.* 82, 605-610
  (estimates on the boundary of the parameter space).
- GSAS-II `GSASIIstrMain.dropOOBvars` (gsas-ii.readthedocs.io); TOPAS 5
  Technical Reference § 2.4-2.5; ROOT `TMinuit` documentation, parameter
  limits; lmfit, "Bounds Implementation".
- Venzon, D. J. & Moolgavkar, S. H. (1988). *Appl. Statist.* 37, 87-94,
  doi:10.2307/2347496 (profile-likelihood interval).

## Handover log

- **2026-10-08** — created, from the 2026-10-08 issue triage (issues #831,
  #836). Checked against the tree at `a3f9140a`: the BT-1 macOS half
  reproduces to every printed digit; `live = d > 0.0` at the three places
  named. No open WP owns the covariance's dead-column test: 1463 and 1535,
  which last changed it, are closed; 1915 is the indexing side's propagation;
  1914 reads a floor coefficient after the fit. Decided the same day by the
  maintainer, after a precedent search (GSAS-II, TOPAS, MINUIT, lmfit, Self &
  Liang): condition on a floor row; re-rated P1.
