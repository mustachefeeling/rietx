# WP-1930 — a width freed on its floor leaves it by rounding

Milestone: unscheduled · Status: ✅ 2026-10-13 — one LaB₆ + cBN minimum on both platforms, and a flat direction's esd no longer rounds to 0
Track: What fires, and what stays silent
Depends on: —

## Goal

A stage that frees a softplus row sitting on its floor reaches the same
minimum on every platform, either because the row starts where its gradient
is order one or because the plan says why it stays held. The LaB₆ + cBN
acceptance case has one minimum, VALIDATION.md quotes it, and a bar tight
enough to see a 12.5 against 9.7 change guards it.

## Context

Issue #832 (mustachefeeling, 2026-10-08), found while investigating #831
(WP-1929). The third item of #836 (seed a floor row before freeing it, or
fire `SOFTPLUS_FREED_AT_FLOOR`) is the same work and lands here.

**The mechanism.** A softplus entry with `min=0` maps 0 to an internal
coordinate of about −27.6 (the `to_internal` clamp, physical 1e-12), where
dp/du ≈ 1e-12 and the Jacobian column is about 1e-8 of its neighbours. TRF
starts there with a gradient near zero, so whether a step ever lifts the row
depends on rounding. `TCHZ_DEFAULTS` has `"y": 0.0`
(`schemas/instrument.py:1036`), and `strategy/staged.py` frees
`instrument.profile.y` in six preset plans (lines 366, 387, 423, 452, 499,
552), so every default-instrument fit that runs one of them is exposed.

**What was measured** (#832's comment; Linux x86-64 WSL2 numpy 2.5.3, macOS
arm64 numpy 2.5.2 with Accelerate; each fit 1-4 s):

| tree | χ²_red | Rwp | LaB₆ wt % | `profile.y` |
|---|---|---|---|---|
| published (VALIDATION.md, landing page) | — | 0.1645 | 17.874 ± 0.314 | — |
| `d2f683a0`, both machines | 9.6615 | 0.16453 | 17.874 ± 0.314 | 0.0384 |
| `a3f9140a`, Linux | 12.4753 | 0.18696 | 17.656 ± 0.383 | 1e-12 (floor) |
| `a3f9140a`, macOS | 9.6917 | 0.16478 | 17.841 ± 0.314 | 0.0376 |

- The published row was written at `d2f683a0` (WP-1541's re-measure,
  2026-10-03), when both machines agreed. A bisect over all 77 first-parent
  merges to `a3f9140a`, on both machines, finds one step: **#700**
  (`c6eaff7d`, WP-1534, `Atom.biso` unbounded). Before it, the `biso` stage
  (where `profile.y` is still free, the free set being cumulative) lifts the
  row on both machines to one point. After it, Linux leaves it on the floor
  and macOS escapes in 60 iterations. The reporter's reading, not measured:
  unbounding Biso changes TRF's bound-distance scaling of those columns.
- The `profile` stage already ended 41 apart in cost before #700 (289199.582
  against 289158.745), harmlessly.
- **Every assertion in `test_acceptance_lab6_cbn.py` passes at both minima**
  (8 of 8). Nothing asserts χ², and the Rwp bar is a factor of 4
  (0.081-0.324). The nightly slow suite runs on Linux, so it passes at 12.48.
- **Seeding probe (option a).** Lifting `profile.y` at the start of the
  `profile` stage (to ln 2 internal, to 0.05°, or `Stage(..., seed=0.05)`)
  gives one minimum on both machines at both trees: χ²_red 9.8402, Rwp
  0.16604, LaB₆ 17.761 ± 0.312. It is a *higher* minimum, and there the
  Gaussian is clamped (Γ_G² < 0 at 98-100 % of points), so u, v, w are
  undetermined: esds `None` or ρ = ±1.000, `RESOLUTION_UNCONSTRAINED` in
  every arm. QPA, cBN cell and B x agree across arms to 5 digits. So seeding
  alone trades platform dependence for three dead columns; it would need the
  clamped triple held, or option (b) (free the row in its own short stage with
  what it trades against held).
- Same mechanism, milder, on BT-1 neutron: `profile.y` on its floor on both
  machines, at a different internal coordinate (WP-1929's case).

**Checked against the tree at `a3f9140a`** (this worktree's `[dev]` venv,
macOS arm64): the macOS row reproduces to every printed digit. χ²_red
9.6916891, Rwp 0.16478432, `profile.y` 0.037593 ± 0.001422, `profile.x`
0.003082, `w` 7.48e-6, diagnostics `CAPILLARY_OFFSET_UNAVAILABLE`,
`DISPERSION_NEGLECTED`, `RESOLUTION_NOT_POSITIVE`,
`RESOLUTION_UNCONSTRAINED`. The Linux row was not reproduced here (no Linux
machine; the nightly does not print χ²).

**Decided 2026-10-08 (maintainer), after a precedent search.**

- **Package:** a stage that frees a softplus row sitting on its floor starts
  it a short way inside, through `Stage.seed`'s existing path. This is #836's
  third item. The seed's size and where it comes from are this WP's to
  measure and state in the docstring.
- **LaB₆ + cBN:** option (a) with the Gaussian held. `profile.y` starts
  inside its floor, and u, v and w are held, because at that minimum the data
  cannot determine them (Γ_G² < 0 at 98-100 % of points). Option (b) has no
  precedent found. Option (c) is refused: on macOS the data put `y` at
  0.0376 ± 0.0014, 26σ from zero.
- **Order:** the reporter measures (a) with the Gaussian held on both
  platforms before it is adopted, then VALIDATION.md's row is re-measured.
  Asked on the issue the same day.

The precedents: MINUIT warns that a transformed parameter at its limit sees
a zero derivative and can stay blocked there, which is this WP's mechanism.
TOPAS gives width parameters a positive minimum (`pv_fwhm` 1e-6, `la` 1e-5,
`lh`/`lg` 0.001; Technical Reference Table 2.1) and applies limits inside
its solver, so a parameter at its minimum still sees its real slope. GSAS-II
sets no limits by default. scipy's TRF moves a start strictly inside its own
bounds, but rietx's floor is the softplus transform and not a scipy bound
(`internal_bounds` maps a lower bound ≤ 1e-12 to −∞), so that protection
does not apply.

**Measured 2026-10-09** (this worktree's `[dev]` venv, macOS arm64; the
handover log has the tables).

- **Rounding picks the minimum on one machine.** On the shipped plan,
  multiplying `w`'s start by (1 + k·1e-14) for k = ±1, ±3, ±7, 20 put five
  of seven starts at χ²_red 12.4753, `y` on its floor: Linux's number to
  every digit. The unperturbed macOS start is the minority outcome.
- **#700 is the trigger, not the cause.** With `biso` bounded (0, 25) again,
  k = 0 gives the published 9.661528, and k = −1 still lands on the floor
  (12.95). The floor trap predates #700, which moved where the coin lands.
- **Exposure.** Six presets free `instrument.profile.y` on its floor in
  their `profile` stage, on all three instrument presets, and
  `lab_sample_refine` frees the four phase widths on theirs. Extinction,
  roughness and the magnetic widths were already seeded. A hump's height
  (counts) and an extra peak's area are the floor rows left with no size.
- **The held protocol** reaches χ²_red 10.1518150 at every seed from 0 to
  0.05° and every perturbation, the reporter's two-platform 10.15182. BT-1's
  `y` goes back to its floor from every seed (χ²_red 1.9279825 throughout).
- **The seed is 1e-3°, not 0.05°.** At 0.05° nine synthetic suites whose
  true width is zero ran out of iterations or moved, and the free-Gaussian
  plan stopped at 9.84. At 1e-3° all nine pass unchanged and the free plan
  reaches 9.661408 at every perturbation, with `w` on its floor and the
  resolution diagnostics firing, so holding the Gaussian still stands.

**Superseded in part 2026-10-12 (WP-1938, PR #883).** Every parameter
now refines in its own units, so a width's floor is an ordinary bound of 0
and its column there is the physical one. WP-1938 deleted the floor seed
(`seed_floor`, `SOFTPLUS_FLOOR_VALUE`, `SOFTPLUS_FREED_AT_FLOOR`,
`StageResult.floor_unseeded`) and the finite-softplus-floor probe WP-1929
proposed with it. `Stage.seed` survives as `seed_floored`, lifting only a
freed row on a floor at or above 0. The decided protocol for LaB₆ + cBN
stands: `u, v, w` held, and `profile.y` now leaves 0 by itself, so the
`profile` stage seeds nothing. Re-measured on arm64 (this worktree's `[dev]`
venv, Apple M4, numpy 2.5.4): Rwp 0.168656276, χ²_red 10.151815, `y`
0.036893 ± 0.001239, LaB₆ 17.791 ± 0.319 wt %, every value and esd the same
bits at the last nightly's tree (56427c4a). That nightly's Linux plot reads Rwp
0.1687, GoF 3.19 (run 38261107758). The degenerate plan reads Rwp 0.1289, GoF
2.44 on both (χ²_red 5.934160 on macOS), so #832's split (a), 5.470 against
6.001, is gone.

## Non-goals

- Which esds a floor row's neighbours report: WP-1929.
- A coefficient read off its floor after the fit: WP-1914.
- The PVII/FPA peak-shape gap the suite's own comments name as why Rwp is
  worse than TOPAS's.
- Two splits from #832's sweep (2026-10-08): Stephens brucite stopping at
  `max_iter` on Linux, and five indexing Le Bail fits leaving `profile.y` on
  its floor on Linux after #741. Both unmeasured since WP-1938, and
  forwarded to WP-1946 and WP-1542 on 2026-10-13.
- Whether a magnetic moment trial should start off m = 0 (#865's open
  question, PR #870): a magnetic stopping point, and this WP no longer seeds.

## Tasks

- [x] Reproduce the Linux minimum on one machine: the `biso` stage started
      from each platform's `profile`-stage end state, or the probe the
      reporter offers. Confirm or refute the bound-scaling reading of #700.
- [x] Count the exposure: of the acceptance suites and the six presets, which
      free a softplus row at its floor, and which of those end on it.
- [x] The decided protocol on LaB₆ + cBN, option (a) with u, v and w held,
      measured on both platforms (the reporter's run, or this WP's on Linux
      CI), and on BT-1 to see whether it moves.
- [x] The package side: `Stage` seeds a floor row it frees (#836 item 3),
      through `Stage.seed`'s existing path, with the seed's size and source in
      the docstring. A diagnostic only if a caller can still free one unseeded.
- [x] A χ² or Rwp band on `test_acceptance_lab6_cbn.py` tight enough to see
      12.5 against 9.7 (the reporter suggests Rwp within 2 % of the
      re-measured value), run on both nightly platforms. *Linux x86-64:
      green in the nightly full suite at 32a2b473 (WP-1930's form) and at
      0f30d584, dd20f0fd and 56427c4a (WP-1938's), the last plotting Rwp
      0.1687, GoF 3.19. macOS arm64: green here 2026-10-12, Rwp 0.168656276,
      χ²_red 10.151815. The macOS nightly runs only the fast tier, so its
      macOS runs are local ones.*
- [x] Re-measure VALIDATION.md's row and the landing page's copy on the
      chosen protocol (`docs/landing/README.md` says how the page's numbers
      are rebuilt).
- [x] Tests, with obs/calc/diff PNGs to `tests/output/`.
- [x] Skill: if a diagnostic lands, its `references/judging.md` row; if the
      protocol is a rule an agent applies by hand, SKILL.md §2's seed rule.
      *The row went to `diagnostics.md`, beside the stage codes, paid for by
      two cuts; no hand rule, since the package now seeds.*
- [x] The degenerate fit's `HIGH_CORRELATION` fell silent on every Linux
      nightly from 0f30d584 (WP-1938's merge) on. Find why by measurement and
      fix it where the covariance is built. *A flat direction's eigenvalue
      came back at either sign and `pinv` inverted a negative one with it;
      `statistics._psd_pinv` inverts by magnitude (2026-10-12).*
- [x] The macOS nightly's `test_high_correlation_dedup.py` silence over the
      same runs, red on CI and green locally: name the cause or the next
      measurement. *Before #918 the axial pair started on its floor with a
      zero column, and rounding chose where later stages took it: a 1e-14
      nudge at 56427c4a reproduced the failure here. WP-1953's #918 gives
      that column its one-sided slope; the next macOS nightly confirms.*

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_lab6_cbn.py tests/test_acceptance_wavelength.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

Linux and macOS reach the same χ²_red on LaB₆ + cBN to 1e-4 relative, the
new band fails at 12.48, and VALIDATION.md's row is reproduced to every
printed digit on both.

## References

- Issues #832, #831, #836; PR #700 (WP-1534).
- WP-1541 (the re-measure the published row came from), WP-1929, WP-1914.
- TOPAS 5 Technical Reference, § 2.5 and Table 2.1 (default limits); ROOT
  `TMinuit` documentation, parameter limits.
- Coleman, T. F. & Li, Y. (1996). *SIAM J. Optim.* 6, 418-445 (the
  trust-region reflective method scipy's TRF implements, strictly feasible
  iterates).

## Handover log

- **2026-10-13** — Both nightly silences of `HIGH_CORRELATION` were rounding
  choosing an answer, and neither platform was wrong on its own. On LaB₆ + cBN
  the covariance could report six undetermined widths at an esd of exactly 0
  with no correlation, and the sign of an eigenvalue at the 1e-15 level decided
  where. The solve now inverts each kept eigenvalue by its magnitude, so a flat
  direction always reads as undetermined, and a fit with no such eigenvalue is
  unchanged to the bit. The macOS dedup failure was the axial pair starting on
  its floor with a zero column, which WP-1953's #918 fixed after the last
  nightly ran. The band holds on both platforms, and the WP closes.

  *Done.* `statistics._psd_pinv` replaces `np.linalg.pinv` in `normal_factors`,
  numpy's steps kept one for one with the sign left out of `vt`.
  `discarded_directions` reads the kept variance by magnitude too. Tests: a
  flat pair at either eigenvalue sign gives the same esds and ρ = ±1; numpy's
  bits are kept on PSD input, including a small kept eigenvalue and the empty
  matrix; the acceptance suite fits the two nudges that failed (a VALIDATION
  row added). The two eigensolver-failure injections moved from `pinv` to
  `eigh`, and the scale-B floor test calls `_psd_pinv`. The manual's
  `est-discarded-touch` reads |λ_k|, with a paragraph on the sign, and a 1.9.0
  note sits under "Numbers that move". Inherited was folded into Context and
  Non-goals: WP-1938 superseded the seed and WP-1929's finite-floor probe, and
  the two nightly notes are discharged.

  *The LaB₆ silence, measured* (`[dev]`, macOS arm64, Apple M4, numpy 2.5.4).
  The degenerate plan's six Lorentzian widths span two exactly flat
  directions. At 25-30 free columns their eigenvalues reach the equilibrated
  normal matrix between 1e-16 and 4e-15 of the largest, of either sign, against
  a cut of 1e-15. `pinv` inverts a kept negative one with its sign, the widths'
  variances come out negative, `covariance_estimates` floors them to 0, and ρ
  reads 0. On `HEAD` before the fix, nudging `w`'s start by (1 + k·1e-14) for
  k in {0, ±1, ±3, ±7, ±20, 50} raised no `HIGH_CORRELATION` at k = +1, +7
  and +50, and three of fifteen at k = −3 and −7. The Linux nightly's "raised
  no HIGH_CORRELATION at all" matches the first three. At 12db370b, before
  WP-1938, the same eigenvalues sat at 1e-15 to 1.2e-14, mostly positive and
  kept, so the guard fired. After the fix it fires at all ten nudges (15
  findings at nine, 6 at k = −7), with the widths' esds at 82-2730. The shared
  fit keeps all 31 values and esds to the bit, and gives the same bits at the
  last nightly's tree, 56427c4a.

  *The macOS dedup silence, measured.* The runner (macos-26-arm64, Python
  3.13.15, numpy 2.5.4, scipy 1.18.1, kernels 1.2.0) differs from this Mac in
  CPU only, and a local 3.13.15 venv with jax passes. At 56427c4a, before
  #918, the axial pair's start columns at (0, 0) were exactly zero, so the
  `axial` stage ended where it began after 2 evaluations and later stages left
  0 by rounding. A k = +1 nudge sent the pair to `axial_sl` 0 on its floor and
  `axial_hl` 0.2 on its ceiling with no `HIGH_CORRELATION`, which is the CI
  failure reproduced. At `HEAD` each start column is 8.81 with cosine −0.60 to
  the residual, and all ten nudges end at (0.0203, 0.0197) with the pair
  flagged in all four stages. A sweep of every default row on a bound, 17 on
  the Debye-Scherrer and Bragg-Brentano presets, found no zero start column at
  `HEAD`.

  *The band.* `test_the_shared_fit_reaches_one_minimum_on_every_platform` is
  green on Linux x86-64 in the nightly full suites 38183312796, 38257956064
  and 38261107758 (WP-1938's form), absent from all three failure lists, and
  the last one's plot reads Rwp 0.1687, GoF 3.19. On macOS arm64 it is green
  here at Rwp 0.168656276, χ²_red 10.151815. The nightly prints no χ², so the
  post-1938 Linux agreement is known to the plot's four digits of Rwp. The
  reporter's 1e-12 was measured before WP-1938. The macOS nightly runs only
  the fast tier, so the band's macOS runs are local.

  *Tests* (`[dev]`, macOS arm64, Python 3.12.10). Fast selection on bb5b18cc:
  9312 passed, 181 skipped, 3 xfailed, 0 failed, 24:22 at a load average of
  130-175 beside two other sessions' suites. Full selection on aea419b6, with
  `main` unmoved since the branch base: 9609 passed, 194 skipped, 3 xfailed, 4
  failed, 1:18:52. It started alone, and other sessions' fast suites joined it
  (load 100-175), so the time is not quotable. Three failures passed rerun
  alone: the dichotomy and trial-and-error monoclinic searches (budget-bound)
  and the GUI scratch-copy boot. The fourth,
  `test_the_reduced_cell_is_the_exact_image_of_its_input[F]`, is a hypothesis
  counterexample that fails the same way on the tree without this branch's
  change; `reduce.py` calls nothing in `statistics`. It went to WP-1932. The
  added tests cost 28.24 s (the two nudged LaB₆ fits, slow tier) and 0.06 s
  (three covariance cases, fast tier), one run's figures under that load.

  *Review* (`/code-review high --fix`, 9 findings). Fixed: `_psd_pinv` now
  gives `pinv`'s empty answer for a 0×0 matrix; two stale docstrings; "five
  widths" was six; the manual claimed ± 0 esds on Linux, which only macOS
  showed; the scale-B floor test still called `pinv`; the bit test had no
  small kept eigenvalue. Declined: rounding still sizes a flat direction's esd
  (82 to 2730), since marking it unmeasured would move `PINV_RCOND` and
  `SCALE_B_SEPARATION_FLOOR`; `_psd_pinv` is 2-D only, kept line for line with
  numpy for the bits.

  *Not generalised.* `indexing/reduce.py`'s `equal_reduced` has the same sign
  inversion in a χ², where a kept negative eigenvalue could merge two cells. It
  went to WP-1932's Inherited, because WP-1519's replay rule governs any change
  there. `report/layer1.py` takes the general `pinv` of a small Gram and fails
  safe, since an esd of 0 reads as not significant. `solve/cost.py` already
  drops negative eigenvalues. Root `CLAUDE.md` is at its 978-line cap, so the
  rule lives in `normal_covariance`'s docstring and its tests.

  *Forwarded.* WP-1946: #832's brucite split. WP-1542: #832's indexing Le Bail
  split. WP-1953: #918 fixes the macOS dedup test. WP-1932: `equal_reduced`'s
  sign and the reduce counterexample. #865's moment question is a Non-goal here
  and has no owner.

  Next: the first nightly after e1d19359 should show the macOS dedup test and
  the Linux LaB₆ file green; a red one there reopens this. The P1 close owes a
  release under `RELEASING.md` § When, and that is the maintainer's call.

- **2026-10-09, after the PR's Linux CI** — two fast tests failed on every
  Linux leg and passed on macOS. Both were bars on a number rounding now
  chooses.

  *Le Bail alternation.* At +0.3 %, pass 1 read 13.718 on both platforms.
  Pass 2 read 13.766 on Linux and 13.751 on macOS, a 1.5e-4 spread against
  the 1e-4 bar. Pass 2 is the discarded pass, so the test now pins pass 1
  and asserts only that pass 2 is worse.

  *Wrong triclinic cell* (`test_cell_runaway_safety.py`). Linux returned
  Rwp 1.1e9 under `converged`, where the test wanted below 1. Ten nudges of
  k·1e-14 to `profile.w` on macOS: on `main` both plans read 0.3316 every
  time; with the seed the second plan read 0.33-6.55, and 1.8e7 at k = −20.
  Neither is a fit. On `main` U and V went negative, so every peak drew at
  the 1e-4° floor and only the background was fitted. With the seed some
  runs take the widths to their upper bounds, and the frozen windows cut
  those peaks short while solving. The test's claim is that `fit` returns
  instead of raising, so it now asserts a finite, positive Rwp beside the
  `CELL_RUNAWAY` it already pinned. It passes in all ten nudged runs.
  `FROZEN_COMPILE_STALE` called that gap of 3.1e4 % "not biased" at `info`.
  That claim went to WP-1421 § Inherited, which owns the message.

- **2026-10-09** — LaB₆ + cBN now has one answer on every machine, and the
  package no longer leaves a freed width on its floor for rounding to decide.
  The split was never Linux against macOS: on one Mac, a 3e-14 change to one
  start value reproduced Linux's 12.48 in five of seven tries, and it did so
  before #700 too. The fix is two parts: the Gaussian triple held, as decided,
  giving χ²_red 10.1518 everywhere, and a package-wide floor seed at 1e-3 of a
  width's unit. The larger 0.05° seed was tried and refuted; it broke nine
  suites whose true width is zero. Three published numbers moved with the
  protocol: QPA 17.791 ± 0.319 wt % (was 17.874), Rwp 0.1687, cBN +16 ppm.

  *Done.* `ParameterTable.seed_floor` + `FLOOR_SEEDS`/`SOFTPLUS_FLOOR_VALUE`
  (`params/vector.py`), called after `Stage.seed` in `_run_stage` and
  `multi.py`; `StageResult.seeded`/`.floor_unseeded` (schema 0.43 → 0.44);
  `SOFTPLUS_FREED_AT_FLOOR` for a floor row with no seed size (a hump's
  height). `test_acceptance_lab6_cbn.py`: triple held in both plans, silence
  restored in the correlation test, a 2 % Rwp band, render test. Re-baselined
  with reasons: the Le Bail alternation scenarios (every pass ~3 pp lower, so
  the shapes moved to +0.3 % and +0.4 % starts), NAC's `at_bound` count, the
  GUI last rung (as-optimised staleness, 8e-6), corundum's anisotropy bar
  (rides a flat direction, 2.02 → 4.51 at one χ²), FAP's window test (now
  runs the screen's own `two_theta_max`), the two-site magnetic pair test
  (pairs were stopping points; naming check moved to the 150 K solution).
  VALIDATION.md, the landing row, the manual's `StageResult` table and the
  skill's diagnostics row (net −63 B) updated. API index cap 39 700 → 39 800,
  WP-1920 owning the split.

  *Measured* (`[dev]`, macOS arm64). Seed sweep (0 / 1e-3 / 1e-2 / 0.05°, two
  perturbations each): LaB₆ held χ²_red 10.1518150 in every arm, 47-52 →
  41-45 → 36-40 iterations; BT-1 1.9279825, `y` back on its floor from every
  seed; brucite 8.313117. Free-triple plan at 1e-3°: 9.661408 at every
  perturbation, `w` on its floor and the resolution diagnostics firing, so the
  hold stands; at 0.05° it stopped at 9.8402. Degenerate plan: one minimum,
  χ²_red 5.934160, LaB₆ 16.850 ± 0.192 (5.5σ out). On the bare branch the
  full suite found three slow failures (FAP window, corundum, two-site pair),
  fixed above. On `main` merged in (8 commits, `5aaec31b`): fast 8905 passed,
  172 skipped, 0 failed, 8:40 with three other pytest processes running; full
  9190 passed, 184 skipped, 0 failed, 30:02, nothing else running at its start.
  The 13 added fast tests cost 1.91 s together, the dearest 0.59 s. Main moved
  under the branch, so the delta is not attributable test by test. Lanes:

  | lane | est | requests | main at dispatch | lane $ | saved $ |
  |---|---|---|---|---|---|
  | fap-window | 20 | 23 | 385K | 1.01 | +0.97 |
  | magnetic-pair | 20 | 35 | 392K | 1.45 | +1.31 |

  Selective policy (lane when main > 150K and item ≥ 20): −21 % over 90
  replayed sessions.

  *Review* (`/code-review high --fix`, 10 findings). Fixed: a named
  variable lost its unit, so `vars.X` was never floor-seeded; a shared joint
  column could take two seeds through per-histogram box caps; three copies of
  the stage-list wording became `_stage_list`; a floored `.scale` fired the
  new warning against PHASE_UNCONSTRAINED's advice and is now left to it; the
  manual overclaimed that every width is softplus; the 1.8 notes and record
  now stage the change. Declined, with reasons: re-seeding a row a later stage
  names again is what "a stage that frees it" means, and the answer stage
  converges it back (BT-1); the TOPAS protocol departure is the maintainer's
  decided option (a), documented in the suite. Open: `suggest()` still probes
  every floor candidate at a flat 1e-3 (`SUGGEST_SEED_SOFTPLUS`,
  `refine.py` near the `seed_softplus(cand_paths` call), so a deg² width is
  probed from a start no stage takes; and `RWP_PLATFORM_SPREAD` 1e-4 in the
  Le Bail alternation suite rests on the pre-seed Linux spread, which the PR's
  Linux CI measures.

  *Gotchas.* The acceptance's second platform is unrun: the reporter measured
  the held protocol on Linux (10.15182, 1e-12 agreement), but not this tree's
  seed. Other suites' VALIDATION rows were not swept for moved figures; only
  the tests that failed were re-measured.

  Next: (1) watch the PR's Linux CI for the alternation suite's 1e-4 bar,
  and the first Linux nightly after merge for the band, then tick it and
  close; (2) size `suggest()`'s probe seed by unit through `seed_floor`,
  re-measuring its ranked rows; (3) ask the reporter whether their fit recorder can sweep this
  PR against `main` for VALIDATION rows that moved silently, and re-measure
  what it finds (their Cr₂WO₆ 0.2047 → 0.2035 is #700's and still stale).

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #832,
  and #836's third item). Checked against the tree at `a3f9140a`: the macOS
  minimum reproduces to every printed digit; the Linux one was not tried. No
  open WP owns it: 1534, whose merge is the bisect's step, is closed; 1541,
  which wrote the published row, is closed; 1929 takes the esds and 1914 the
  after-fit reading. Rated P1 for the published number no platform
  reproduces. Decided the same day by the maintainer: seed a floor row a
  stage frees, and option (a) with the Gaussian held for LaB₆ + cBN, measured
  by the reporter on both platforms before it is adopted.
