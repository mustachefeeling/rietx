# WP-1929 — an esd follows where the solver stopped beside a flat column

Milestone: unscheduled · Status: 🔄 2026-10-09 — decided: physical coordinates (1936-1938), then marginal esds with a bound flag here
Track: What fires, and what stays silent
Depends on: 1938 (physical coordinates, which remove the point-dependence this WP reports on)
Priority: P2 2026-10-09 — was P1: the cause moved into 1936-1938, which carry the P1; what remains here (the reporting rule and the floor diagnostic) waits on 1938

## Goal

A fit reports the same esds on every platform when it reaches the same
minimum. A row on its bound keeps its value and its marginal esd, is flagged
as on its bound by the driver's exact active set, and leaves its neighbours'
esds marginalised over it. A held-fixed esd or a profile interval is
available on request. A moment angle at a stationary direction no longer
decides its neighbours' esds.

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

**Superseded in part, 2026-10-09: the premise, and the decision is open
again.** The 10-08 choice rested on "conditioning makes every esd
point-independent; marginalising is what 1463 shipped", which read as if
only conditioning could be. Measured, both can. The BT-1 split is a Jacobian
column made of rounding noise: `optimize/least_squares.py:592` differences
with h = 1e-6·max(1, |u|) in internal coordinates, which at u = −25.5 moves
`profile.y` by about 2e-16 and the widths by less than an ulp. Taken on the
width and chained by dp/du, the column gives `profile.x` 0.0098437 at
u = −25.54, −25.5 and −514. Both platforms' figures (0.00664, 0.00322) were
artefacts. The literature still favours conditioning for the other esds
(Self & Liang 1987 eq. 2.2; SAS PROC NLIN; sIPOPT), and a one-sided interval
with the value kept for the floor row (Currie 1995 § 3.7.3.1 Note 2). The
root is shared with WP-1930: softplus has no finite floor. The four options
and their sources are in the 2026-10-09 handover entry and at
https://claude.ai/artifact/CYGoz3cF63QUJ345z4zKMY. The maintainer will
choose after the next session probes them.

**Measured 2026-10-09, second session: the coordinates, not the reporting
rule** (macOS arm64, `[dev]`, tree `35f4ac14`). Twelve acceptance fits, five
starts each, every unlocked start value multiplied by (1 + k·1e-14). Spread is
χ²'s relative range across the five.

| fit | softplus + TRF (today) | physical + TRF | physical + LM, BVLS step |
|---|---|---|---|
| LaB₆ + cBN (pre-1930 plan) | 9.69–12.51 | 9.661408, 2e-12 | 9.687–9.688 |
| LaB₆ degenerate | 5.47–12.82 | 5.450264, 3e-11 | 5.4397, 2e-5 |
| BT-1, `profile.x` esd | 0.0032 / 0.0066 / 0.0089 | 0.0098437 | 0.0098437 |
| brucite (iso) | 8.3131166, 5e-8 | 8.3474, max_iter | 8.3131166, 2e-11 |
| corundum | 2.6560076, 5e-8 | 2.659–2.665, max_iter | 2.6560076, 1e-11 |
| NAC, FAP, Si 640c, capillary, absent phase | agree | agree | agree |

Physical coordinates (softplus entries made identity with `lo = max(lo, 0)`)
remove both splits under TRF. TRF's Coleman-Li scaling then crawls on the QARR
fits, where u, w, `gauss_size`, `gauss_strain` and `lor_strain` press on 0
together. The LM driver (`optimize/lm.py`) with its BCCG step replaced by
`scipy.optimize.lsq_linear(method="bvls")` fixes that. It still stops early
stages at their cap and lands LaB₆ on a higher basin. Ruled out: `dogbox`
(χ²_red 556 on the absent phase), `x_scale="jac"` (no change), a
tolerance pin around TRF (never fired), and physical-step FD with softplus kept
(LaB₆ trapped at 12.478; BT-1 still flips once u passes exp underflow). The
probe scripts and the uncommitted toggles (`RIETX_PHYS_FD`, `RIETX_LM_BVLS`)
are described in the 2026-10-09 handover entry.

An adversarial review of that proposal (same day) found four things, each
checked here. The FD step chooses LaB₆'s basin in physical coordinates
(WP-1936). `bound_findings`' esd window flags `profile.u = −0.0016 ± 2359`
on brucite as at its bound of −0.05, so a rule keyed on it would act on rows
nowhere near a bound. The LM driver reports a stage already at its minimum as
`"diverged"` (`lm.py:373`) and caps outer iterations where TRF caps
evaluations (WP-1937). Readers branching on the word `"softplus"` would
silently stop acting (WP-1938).

**Decided 2026-10-09 (maintainer), replacing the 10-08 decision.**

- **Base:** physical coordinates with native bounds (WP-1938), an FD step
  sized per parameter (WP-1936), and a driver whose bounded step is exact
  (WP-1937).
- **Reporting:** marginal esds with a flag, TOPAS's behaviour. A row on its
  bound keeps its value and its marginal esd and is flagged. Its neighbours'
  esds are marginalised over it. In physical coordinates both readings are
  point-independent, so the 10-08 premise no longer separates them. The
  marginal reading is the larger (σ_m ≥ σ_c) and continuous, while the
  conditional one jumps by 1/(1 − ρ²) when a row crosses the at-bound test.
  Self & Liang's sampling distribution lies between the two. The held-fixed
  esd (`normal_factors(condition=)`, `b48cafd1`) and a profile interval stay
  available as tools.
- **The flag** keys on the driver's exact active set (WP-1937 exposes it),
  never on the esd window. A physical floor gets its own diagnostic, because
  `BOUND_HIT`'s "widen the bound or fix the parameter" would fire on every
  width that refines to zero.

### Inherited

- **2026-10-10, from WP-1937: the active set exists.**
  `LSQOutcome.active_bounds` carries each driver's set over the table
  columns (−1 lower, +1 upper, 0 neither). The LM driver's is exact: the
  value sits on the bound and the gradient there points outward. TRF's is
  scipy's `active_mask`, set within `XTOL` of a bound whatever the gradient,
  so it misses brucite's `gauss_strain` parked 7.6e-6 above its floor. Nothing
  copies it past the outcome yet; the flag task reads it there. The
  default-driver flip moved from 1937 to WP-1938, so until 1938 lands the
  default's set is TRF's.

- **2026-10-09, from WP-1930 (PR #849).** The floor seed this WP soft-depended
  on has landed: a stage now starts a freed softplus row sitting on its floor
  at 1e-3 of its unit (`params.vector.FLOOR_SEEDS`), and records it in
  `StageResult.seeded`. It moves the minimum, never the esds, so this WP's
  question stands. Three cases it surfaced, all at one χ² with the parameter
  values apart: brucite's `instrument.profile.y` lands between 0.08 and 0.14
  under rounding-level start changes (χ²_red 8.313117 throughout); corundum's
  `lor_strain` reads 1e-4 seeded against 1.4e-3 unseeded (χ²_red 2.65601 both);
  BT-1's `y` goes back to its floor from every seed, at values from 0 to 3e-10.

## Non-goals

- A minimum that differs between platforms (LaB₆ + cBN): WP-1930.
- The #820 pair count: WP-1418 and PR #829.
- A softplus coefficient read as a finding after the fit (`microstructure`'s
  `_reading`): WP-1914. Its "what does *at its floor* mean" task is the same
  question asked of a reader; settle it once and quote it from both.

## Tasks

- [x] Measure WP-1463's absent-phase case both ways before changing it (the
      other phases' QPA esds conditioned on and marginalised over the floor
      scale), and record the before and after here.
- [x] Probe the options and take the decision (2026-10-09: physical
      coordinates in WP-1936-1938; marginal esds with a flag here).
- [ ] A fixture that reproduces the platform split on one machine, nudging
      BT-1's start by 1e-14 as the grid did. It fails on today's softplus and
      passes after WP-1938, with one `profile.x` esd.
- [ ] The flag: `RefinedParameter.at_bound` and `BOUND_HIT` read the driver's
      active set (WP-1937), with `bound_findings`' esd window kept only where
      a driver gives none. A physical floor gets its own code and
      `Diagnostic.suggestion`, so a width refined to zero is not told to
      widen its bound.
- [ ] `statistics.normal_covariance`'s docstring and root CLAUDE.md's
      equilibration clause state the marginal rule. Find every consumer of
      `live` and `unmeasured_rows`, and say which still apply once no column
      is a softplus floor.
- [ ] The held-fixed esd as a tool: expose `normal_factors(condition=)`
      through a public call, or remove it if `profile_interval` covers the
      need. Settle χ²_red's degrees of freedom and `discarded_directions`
      under it.
- [ ] `profile_interval(path)`, the one-sided interval for a row on its
      bound (Venzon & Moolgavkar 1988). `strategy/fraction_profile.py` has the
      pinned-refit and Δχ² machinery.
- [ ] Moment angles at a stationary direction: leave the normal matrix (or
      extend `MOMENT_DIRECTION_SUPPORT`'s hold to them, whichever keeps one
      authority), and rewrite that constant's comment. Physical coordinates do
      not touch this half: the azimuth is already identity.
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

The fixture's `profile.x` esd is 0.0098437 at every nudged start. The
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

### 2026-10-09 (2nd session) — physical coordinates decided, filed as 1936-1938

Both platform splits come from refining widths and scales in softplus
coordinates. Near zero, softplus makes a column too small to difference and a
gradient too small to escape, so rounding chooses the esds and sometimes the
minimum. Refining in physical units with ordinary bounds gave one minimum and
one esd on every fit tried. The exception is where scipy's TRF crawls with
several widths pressed on zero, and the package's LM driver fixes that once
its bounded step is solved exactly. The maintainer chose that base and
reversed the 10-08 reporting rule: esds stay marginal, and a row on its bound
is flagged. Nothing was built. The work is filed as three WPs, and this one
keeps the reporting rule.

- *Done.* `67dfa21f` the grid in Context; `56941860` the decision, the
  rewritten Goal and Tasks, and WP-1936 (FD step sized per parameter), 1937
  (an exact bounded step in the LM driver, then the default), 1938 (physical
  coordinates). `befc2ebc` renumbered those from 1933-1935, because the CIF
  session holds 1933 (PR #854). `main` merged in (`e9ef5369`).
- *Measured* (macOS arm64, `[dev]`, tree `35f4ac14`). The Context table, plus
  the step sweep in 1936 and the driver table in 1937. The arms run were
  softplus, physical, unbounded and physical-step FD, each under TRF, dogbox,
  TRF with `x_scale="jac"`, LM, LM with BVLS, and a TRF pin wrapper. Each arm
  ran on 11-12 acceptance fits with 3-5 nudged starts. Wall clock was not
  quoted, since the machine was shared.
- *Review.* An adversarial review (Fable, high effort) found four problems.
  The FD step chooses LaB₆'s basin. The esd-window bound test flags
  `profile.u = −0.0016 ± 2359` as at its bound. The LM driver reports
  "diverged" at a minimum and caps differently. Readers branch on
  `"softplus"`. The first two were re-measured here and hold. All four are
  tasks in 1936-1938.
- *Not run.* The fast and full suites. This session's commits are docs only,
  and the probe toggles were reverted before the merge. The branch's one code
  change is still `b48cafd1`/`37c318e7`, whose counts are in the first entry.
- *Gotchas.* The probe kit (`probe_bounds.py`, `run.sh`, `table.py`) lived
  in the session scratchpad and is gone. Rebuild it from the Context
  paragraph: a monkeypatch of `ParameterTable.__init__` for the coordinates,
  one of `refine.run_least_squares` for the driver, and an env toggle at the
  two FD sites. `rietx.refine` resolves to the function, so take the module
  from `sys.modules`. The worktree guard refuses inline heredoc python.
- *Next.* (1) WP-1936, the FD step, which is correct in either coordinate
  system and decides which basin the other two are measured against. (2)
  WP-1937, the driver. (3) WP-1938, the coordinates. (4) This WP's flag,
  floor diagnostic and `profile_interval`, keyed on 1937's active set.

- **2026-10-09** — The platform split in these esds is not a statistical
  ambiguity. It is a derivative computed below rounding. A softplus row near
  zero is differenced by a step that moves the width less than its last digit,
  so the column is noise, and the noise sets its neighbours' esds. Computed
  properly, the marginal esds agree at every stopping point. That removes the
  premise the 10-08 decision stood on, so nothing was built past one helper.
  The same root explains WP-1930's split minimum, which raises a fix higher
  up the pipeline: give softplus a finite floor. A literature and code search
  still backs conditioning for the other esds, a kept value and a one-sided
  interval for the floor row, and an upper limit for an absent phase.
  Explainer for the maintainer: https://claude.ai/artifact/CYGoz3cF63QUJ345z4zKMY.
  - *Done.* `b48cafd1`: `statistics.normal_factors(condition=)` gives the
    others the submatrix inverse and the held column a zero row of K,
    so it propagates as a constant, never as unmeasured. The mask is threaded
    through `covariance_estimates` and `_guarded_covariance`, and nothing
    passes it yet. Two tests in `test_covariance_scaling.py` cover it, and
    bit-identity holds when nothing is held. Forward references went to
    1930's and 1914's `### Inherited`.
  - *Measured (macOS arm64, `[dev]`).* Task 1, the absent-phase fixture
    (`test_absent_phase._absent_phase_inputs`, scale moved to u after each
    solve as `fit_absent_at` does), final stage:

    | u (scale) | reading | W present | absent scale esd | `cell.a` esd |
    |---|---|---|---|---|
    | natural (4.2e-135), −380, −700 | marginalise | 1.0 ± 2.2145e-5 | 5.664e-9 | 4.30798e-6 |
    | same three | condition | 1.0 ± 0.0 | 0.0 | 4.30798e-6 |
    | −800 (0.0) | today | esd `None` | `None` | 4.30798e-6 |

    The marginal esds agree to 1e-15 across the three u. Neighbours that
    are uncorrelated with the scale move at 1e-7 (Andrews 1999: the choice
    matters only when correlated). BT-1, `test_acceptance_wavelength._solo(1)`,
    `profile.y`'s internal coordinate set after each solve: today's column
    gives `profile.x` 0.006639 (u = −25.54, natural), 0.007920 (−25.5) and
    0.003221 (−514). The physical-space column, (r(y=2e-7) − r(y=1e-7))/1e-7 ×
    expit(u), gives 0.0098437 at all three, with `profile.y` 0.018101. Rwp is
    0.05258840377637 at all three.
  - *Suite.* The fast selection on the final tree (macOS arm64, `[dev]`) gave
    8872 passed, 172 skipped and 1 xfailed in 9:18. Another session's pytest was
    running beside it. The branch adds two tests, at 0.00 s each by junit.
    No local baseline was taken, so the +2 is CI's to confirm. The full
    selection did not run: nothing passes `condition`, so no measured number
    can move.
  - *Literature* (✓ read in source). Self & Liang 1987 eq. 2.2 ✓: the others
    are Gaussian conditional on the bound. Theory agrees: Geyer 1994 ✓
    (abstract), Andrews 1999 (via a restatement). SAS PROC NLIN ✓ ("an active
    inequality … is treated as an equality"), sIPOPT ✓ and Ceres ✓ condition.
    The tools that ignore bounds marginalise: R `optim` ✓, scipy `curve_fit` ✓,
    lmfit ✓, COPASI ✓ and MINUIT HESSE ✓. TOPAS ✓ marginalises with physical
    derivatives and floors of 1e-11 (scale) and 1e-6 (widths). GSAS-II ✓
    writes 0.0 and freezes the parameter; that is the pattern to avoid.
    Currie 1995 § 3.7.3.1 Note 2 ✓ says to report the estimate and its
    uncertainty, never "zero". León-Reina 2016 ✓ sets quantification at
    3× the esd. No code differences in physical space and chains (Minuit2 ✓
    sizes an internal step against function noise), but every one treats a
    noise column as a defect. `strategy/fraction_profile.py` already has
    the pinned-refit and Δχ² machinery `profile_interval` needs, so nothing
    needs porting. lmfit `conf_interval` and pyPESTO (BSD-3) are the reference
    algorithms.
  - *Options*, highest in the pipeline first.
    1. A finite internal floor for softplus at TOPAS's defaults.
    2. The physical value with a box bound, against DESIGN.md:268's
       unmeasured "hard lower bounds stall TRF".
    3. Hold a row once it reaches its floor (GSAS-II, NONMEM, WP-1301's
       pattern).
    4. Physical-space differencing at `:592` and `:1061`, then condition in
       the statistics.

    The reporting rule is the same in all four.
  - *Gotchas.* The scratch probes monkeypatched
    `rietx.optimize.least_squares.least_squares` to move one coordinate after
    each solve and re-evaluate `fun`/`jac` (the `fit_absent_at` pattern), and
    `rietx.refine.run_least_squares` to learn the column index. Run them with
    `RIETX_TELEMETRY=0 PYTHONPATH=.`. `scipy.special.expit` is needed for
    dp/du at u = −514, because the tanh form rounds to 0. A research agent
    pointed at `~/Zotero` alone missed Schwarzenbach 1989, Madsen 2001 and
    Scarlett 2002, which are in `~/Zotero yue-here/storage`.
  - *Review* (`/code-review high --fix`, 9 findings). Fixed 5: a held 1e-170
    column put a NaN on its own diagonal (0 × inf after the rescale); a
    wrong-length `condition` was silently misread; the Self & Liang citation
    was missing from the docstring; the test's `allclose` kept the default
    atol; and the held branch now scales only the kept block. Left 4 for the
    choice, because each depends on it:
    - the held row's esd comes back 0.0, where the reporting rule wants
      `None` plus a one-sided interval;
    - `condition` has no caller yet (remove it if option 1-3 makes it
      unnecessary);
    - χ²_red still divides by N − n_free with columns held;
    - `discarded_directions` and the residual cosine do not take the mask.
  - *Next.* (1) Probe option 1 on BT-1 at both stopping points and on
    LaB₆ + cBN along both platforms' paths. The memory note on reproducing a
    platform split locally gives the 1e-14 nudge. (2) If it closes both
    splits, tell the WP-1930 session before its seed lands. (3) Bring the
    numbers to the maintainer for the choice, then build that option with
    the reporting rule: condition, value kept, `profile_interval`, a
    diagnostic, and an upper limit for an absent phase. Task 2's fixture and
    tasks 3-10 wait on that choice.

- **2026-10-08** — created, from the 2026-10-08 issue triage (issues #831,
  #836). Checked against the tree at `a3f9140a`: the BT-1 macOS half
  reproduces to every printed digit; `live = d > 0.0` at the three places
  named. No open WP owns the covariance's dead-column test: 1463 and 1535,
  which last changed it, are closed; 1915 is the indexing side's propagation;
  1914 reads a floor coefficient after the fit. Decided the same day by the
  maintainer, after a precedent search (GSAS-II, TOPAS, MINUIT, lmfit, Self &
  Liang): condition on a floor row; re-rated P1.
