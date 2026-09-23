# WP-1415 — a σ column smaller than √y

Milestone: unscheduled · Status: 🔄 2026-09-23 — six of seven tasks landed; the edge-dropout change is measured and implemented on the contributor's branch, awaiting its PR
Depends on: —

## Goal

Two diagnostics that quietly assumed a Poisson-scale σ hold up on a pattern
whose file carries a smaller one. `PATTERN_UNDERSAMPLED` measures its peak
widths on Bragg peaks and not on noise ripples, and a dead detector channel
inside the fitted window is named as such, with the channels, instead of
surfacing as fourteen parameters at their bounds.

## Context

Issues #274 and #275 (2026-09-07), both measured on `origin/main` `2ba7a9a3`
with the public APDW workshop set for Co₃O₄ (ILL D1B, λ = 2.52 Å,
`300q-300K.dat`). The file's σ is monitor-normalised and propagated, so the
median σ/√y is 0.289. That is most constant-wavelength neutron data, and it
is the right σ: GoF sits at 5–10 on a visually excellent fit because the data
are about 3.5× more precise than √y. Root CLAUDE.md § Invariants says to use
the file's σ when present, and every weighted residual divides by it
(WP-1029). Neither issue asks for that to change. Both are consumers that
took √y for granted.

**#275 — `PATTERN_UNDERSAMPLED` counts noise as peaks.**
`background/diagnostics.py::sampling_steps_per_fwhm` hands
`_median_steps_per_fwhm` the net signal over the rolling envelope divided by
σ, and finds peaks on that with `find_peaks(height=5.0, distance=3,
prominence=SAMPLING_PROMINENCE_SIGMA)`. With σ 3.5× smaller than √y, z is
3.5× larger, and noise ripples about two channels wide clear the threshold.

| σ used | steps per FWHM | peaks counted | warning |
|---|---|---|---|
| the file's own σ | 1.84 | 113 | fires, asks for FWHM/5 |
| σ = √y | 6.85 | 16 | silent |
| the truth (half-height width of the strongest line, 1.10° at 0.1° steps) | 11.0 | 13 unique reflections | — |

The pattern is sampled at FWHM/11 and told to re-collect at FWHM/5. In a
sequential series the finding fires on every pattern and
`SEQUENTIAL_PERSISTENT_FINDING` promotes it to a property of the model,
correctly, of a false positive. The bands `STEPS_PER_FWHM_MIN`/`MAX` are
quoted from McCusker et al. 1999 and stay (root CLAUDE.md: they set a level,
never a gate). What changes is the peak *selection*: measure the width on
the strongest few peaks above a fraction of the maximum, or refuse to trust a
median over more peaks than a diffraction pattern can plausibly have. Either
is decided by measuring both on this file and on the fixtures the suite
already carries.

**The same function counts noise for a second reason, and there is to be one
selection (from WP-1442, 2026-09-20; verified on `4ee4e7f5`).** `diagnose`
runs its own census at `diagnostics.py:902` — `find_peaks(net/σ, height=5,
distance=3)`, no prominence — on the rolling 10th-percentile envelope, which
sits under the data on a steep background. On a 4-40° organic pattern with a
Poisson σ it found 292 peaks against 23 from `_median_steps_per_fwhm`'s
prominence-gated count at line 503. That census feeds `_contamination_flags`,
so WP-1442's Kβ ghost search inherits whatever this WP decides. 1442 is filed
and unstarted, and its `Depends on` now reads `1415 soft`, so **this WP owns
the selection and 1442 imports it.** The two callers want different things
(a count wants every line, a width wants only resolved lines), which the
docstring at line 491 already states; one selection means one place that
decides what is a line at all, not one threshold for both uses.

**#274 — two dead PSD cells inside the window, and nothing names them.**

```
   2θ        y      σ
 128.49   36503   55.145      live
 128.59       3    1.000      dead cell
 128.69       5    1.414      dead cell
```

Weights are 1/σ², so a channel with σ = 1 is worth about 3 000 live channels
at σ = 55. Like for like, 12-term Chebyshev background, axial asymmetry
refined:

| fitted window | background | Rwp | background at 128.6° |
|---|---|---|---|
| dead channels inside | 12-term Chebyshev | 0.08724 | −2059 |
| dead channels inside | P-spline, 8° knots | 0.17797 | −586 |
| dead channels inside | 4-term Chebyshev | 0.17733 | −3326 |
| dead channels excluded (`(127, 150)`, as the tutorial's FullProf `.pcr` does) | 12-term Chebyshev | 0.00739 | 35158 |

Every background is dragged through zero at the top of the range. The
Caglioti terms run to their bounds (u, v pinned; w = x = y = 0) and all three
Biso pin at zero. The fit emitted `BACKGROUND_ABSORPTION` ×15, `BOUND_HIT` ×14
(×3 under WP-1434's test, re-measured 2026-09-22 below),
`HIGH_CORRELATION`, `DATA_SUPPORT_LOW` and `PATTERN_UNDERSAMPLED` (#275
above). All symptoms. Fourteen parameters at bounds is the loudest thing a fit
can say short of refusing, and none of the fourteen is the problem.

**The `×14` is stale and this WP re-measures it (from WP-1434, 2026-09-18;
`residual_cosine` verified present in `least_squares.py` and `staged.py`).**
That count was taken under the old test, which asked whether a value stopped
near its limit. The test now asks whether the limit carried load: within a
hundredth of an *esd* of the limit **and** the residual not orthogonal to that
column. Both halves move here. esds scale with σ, so a σ column 3.5× smaller
than √y shrinks every esd and tightens the first half by the same factor,
which makes `BOUND_HIT` a third diagnostic this WP's fixture perturbs rather
than a bystander.

What the package has: `signal_cutoffs` (same module) returns the leading
cutoff only (`edge='low'`, 2.99°, 22 channels). The trailing two-channel
dropout is below `CUTOFF_MIN_DEG = 1.0` and interior besides. Its own
docstring describes this failure shape on an ILL D20 file.

**The shape of the fix.** A dead cell has a signature no live channel has: its
intensity and its σ are both an order of magnitude below their neighbours',
and σ ≈ √max(y, 1), Poisson of nothing. A model-free census beside
`signal_cutoffs` finds those channels and reports them, on the `diagnostics=`
channel at read (`read_pattern`, WP-1047) and in the fit's list at compile.
It reports and applies nothing. `project.fitted_mask` is the one authority
on which channels a run fits (WP-1033), and `excluded_regions` is the
caller's. The finding names the channels and the interval to exclude.
Thresholds are measured on this file and on the D20 file `signal_cutoffs`
documents, never on one. `signal_cutoffs` may additionally admit a short
dropout at either edge, which is the issue's second ask.

**Data.** The APDW set is public. Whether it may enter `tests/data/` depends
on its stated licence (root CLAUDE.md: data carries its own fence, per file);
`tests/data/README.md` records the answer. A synthetic pattern with two dead
channels and a σ column at 0.3·√y reproduces both defects without it.

## Non-goals

- Replacing the file's σ with √y anywhere. The issues are explicit that the
  σ is right.
- Excluding channels on the package's authority. Report, name, suggest.
- Retuning `STEPS_PER_FWHM_MIN`/`MAX` or `CUTOFF_MIN_DEG`.

## Tasks

- [x] `_median_steps_per_fwhm` selects the peaks it measures on by intensity
      relative to the pattern's maximum (or caps the count it trusts); both
      candidates measured on the D1B file and every fixture in the suite,
      the numbers in the handover, one chosen. **Done**: the relative floor,
      anchored on the 99.9th percentile rather than `max`, at
      `SAMPLING_HEIGHT_FRACTION = 0.03`. The cap only bounds the damage
      (σ-scale spread 1.11 against 1.000).
- [x] The chosen selection is the one `diagnose`'s census at line 902 reads
      too, so `_contamination_flags` and WP-1442 inherit it rather than
      growing a second. **Done**: the same floor under its height bar, no
      prominence bar (that census wants every line, which is why it is a
      separate call). 1558 peaks on 11-BM NAC at honest σ became 96. The
      ghost search reads that one call at `GHOST_RATIO_RANGE`'s own lower
      bound, per the review pass below, because the census bar is six times
      the smallest ratio the ratio test accepts.
      `peak_fraction` is the third σ-relative surface in that function and was
      deliberately **not** generalised — its definition is honestly σ-relative
      — so it is documented with its measured swing instead.
- [x] Re-measure `BOUND_HIT` on the #274 fixture under WP-1434's test, and
      correct the `×14` in § Context to what it is today. **Done by the
      contributor on the real file (#274, 2026-09-22): ×3 inside, ×2 with the
      dead pair excluded.** Before that it needed the real file. Measured 2026-09-21 on the synthetic that reproduces everything
      else: the spoilt fit emits `PATTERN_DEAD_CHANNELS`,
      `RESOLUTION_UNCONSTRAINED`, `RESOLUTION_NOT_POSITIVE` and
      `PATTERN_UNDERSAMPLED`, and **no** `BOUND_HIT` at all — the bounds a
      synthetic LaB6 declares are not the ones #274's model walked into, so
      this one cannot be re-measured without the D1B file and its model.
- [x] A dead-channel census in `background/diagnostics.py`, reported at read
      and at compile with the channels and the interval; `GuardFinding`
      constructor and `help.py` entry. **Done as `dead_channels` +
      `DeadChannelRun` + `PATTERN_DEAD_CHANNELS`, on `PatternDiagnostics`, on
      `read_pattern`'s `diagnostics=` list and on `result.diagnostics`.** The
      last clause was wrong about the tree and is deliberately **not** done:
      there is no `GuardFinding` here (guards are stage-level in `staged.py`;
      the peer is `PATTERN_UNDERSAMPLED`, a plain `Diagnostic` in `refine.py`),
      and `help.py` documents parameter, flag and option *names*, never
      `PATTERN_*` codes, which live in the skill's `references/`.
- [ ] `signal_cutoffs` admits a short dropout at an edge, if the D1B and D20
      files agree it is separable from a cliff. **Measured separable by the
      contributor (#274, 2026-09-22), and implemented in `dead_channels` rather
      than `signal_cutoffs` on their unpushed branch. Open until that PR
      lands.** Before that: **Left for the contributor who
      has those two files** (2026-09-21 decision): the task is conditional on
      what they agree, and neither file is in the tree. `dead_channels`
      declines an edge-touching run today and says so, so the gap is named
      rather than silent.
- [x] Tests: the synthetic pattern above for both defects; the APDW file if
      its licence admits it, else the numbers quoted here in the docstring.
      **Done on synthetics; no new data file entered `tests/data/`.**
- [x] Skill: a `references/diagnostics.md` row for the new code, and a
      `references/surprises.md` row that a correct σ smaller than √y gives
      GoF 5–10 on a good fit and must not be "fixed". **The row would not fit
      (§7 was 38 B under its cap), so the eleven reader rows became §7i,
      `references/diagnostics-reading.md`, on the maintainer's criterion: the
      main table carries what a fit is likely to say, and a code conditional on
      a file quirk goes to a secondary doc.**

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_readers_robust.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issues #274, #275 (2026-09-07; `origin/main` `2ba7a9a3`).
- McCusker, L. B., Von Dreele, R. B., Cox, D. E., Louër, D. & Scardi, P.
  (1999), *J. Appl. Cryst.* **32**, 36 — §2, the sampling guideline.
- WP-1029 (every weighted residual divides by `sig()`), WP-1033
  (`fitted_mask`), WP-1047 (a reader repairs only where it says so).

## Handover log

- **2026-09-23** — the contributor's #274 comment of 2026-09-22 settles both
  open tasks' measurements. It was measured on `origin/main` `a1261ca1` with
  the D1B file (Sparks et al. 2019, *Phys. Rev. B* **99**, 104104), the Roth
  CIF, a 12-term Chebyshev, `axial_hl` and `mccusker_structural`.

  - **Task 3.** `BOUND_HIT` is **3** with the dead pair inside the window and
    **2** with it excluded, down from ×14 under the old test. Rwp 0.08724 inside
    reproduces § Context to 4-5 figures. The control reads 0.00766 against the
    quoted 0.00739, 3.6 % apart, which the contributor flags as an unrecovered
    stage-order or seed difference. The three hits inside are all three Biso at
    their floor of 0, with esds of 2.3-5.4 Å². None of them names the cause.
  - **Task 5.** On `main`, **neither routine sees this file.** The trailing
    dead pair is the literal last two channels, and `dead_channels` declines
    any run touching an edge (`diagnostics.py:1156`, verified 2026-09-23).
    The weight ratio already in use separates an edge dropout from a cliff
    with no new threshold: D1B trailing pair 2285.7, leading pair about 1520,
    Mythen V₆O₁₃ high edge 0.34-1.10. `DEAD_WEIGHT_RATIO_MIN = 100` sits 15×
    below the first and 90× above the last. Three D20 holds fall on the Mythen
    side (private data, no figures).
  - **Implemented on the contributor's unpushed branch.** `dead_channels`
    declines only a run touching *both* ends, and judges an edge run against
    its one live side. A second defect is fixed with it:
    `median_filter(mode="nearest")` pads an edge run with its own dead value,
    so the level read 5.0 against about 37 000. `mode="reflect"` gives 37 123.
    That call is at `diagnostics.py:1130` and `:1139` (verified 2026-09-23).
    The task's wording named `signal_cutoffs`. The change lives in
    `dead_channels` instead, which is the routine that already has the test.
  - **Left open by the contributor, deliberately.** D1B's *leading* dead pair
    (0.79-0.89°) is still missed, because `background_envelope` extrapolates
    negative at that edge. This is the gotcha in the 2026-09-21 entry below.
    It does not matter on this file, since `signal_cutoffs`' leading cutoff
    already covers it.

  **Next.** The WP closes when the contributor's PR lands with the edge change
  and the `mode="reflect"` fix. Review it against the three synthetic tests
  the comment names, and against the acceptance pair.

- **2026-09-21** (2nd session) — Two diagnostics that quietly assumed Poisson
  counting statistics now hold up on a file whose errors are smaller than √y,
  which is most constant-wavelength neutron data. Before this, such a file made
  the package announce that the pattern had been collected too coarsely to
  refine, and it did so on **every one of the 27 bundled test patterns** once
  their declared errors were scaled down. The same defect made the peak census
  count hundreds of noise ripples as reflections, which is the pool the Kβ
  ghost search draws from. Separately, a dead detector channel is now named
  where the cause is: two of them take a refinement from Rwp 0.0016 to 0.55 and
  move the lattice parameter 342 ppm while the fit still reports that it
  converged, and until now nothing in the output pointed at the channels. What
  this cost is a structural change to the agent skill, and what it ruled out is
  a fix built on the intensities alone: a dead channel and a channel that
  honestly counted zero are the same two numbers without the file's own error
  column, so the census declines rather than guessing when that column is
  absent.

  **The mechanism, which the WP had not named.** What the peak finder
  thresholds in the background is not noise. It is the background envelope's
  own tracking error, a fraction of the intensity that does not shrink when the
  counting improves. A bar in σ therefore reads that error at 1/σ, so a file
  whose σ is right and 3.46× smaller than √y sees it at 3.46× its honest
  significance. This is why the defect could not be reproduced by scaling a
  synthetic's noise and σ together: both scale, and the ratio is unchanged.
  Holding the pattern fixed and moving only the *declared* σ is the
  perturbation that shows it, and it is what a monitor normalisation does.

  **Done.** (1) Both bars in `_median_steps_per_fwhm` take the larger of the σ
  floor and `SAMPLING_HEIGHT_FRACTION` × the 99.9th percentile of net.
  (2) `diagnose`'s census takes the same floor under its height bar and keeps
  no prominence bar. (3) `dead_channels` / `DeadChannelRun` /
  `PATTERN_DEAD_CHANNELS`, on `PatternDiagnostics`, on `read_pattern`'s
  `diagnostics=` list and on `result.diagnostics`. (4) Thirteen tests in
  `test_data_support.py`. (5) The skill rows, which needed §7i (below).

  **Measured** (worktree `[dev]` venv, darwin/arm64, numpy only, no other suite
  running). Fast selection **5460 passed, 135 skipped**; full selection
  **5640 passed, 144 skipped in 26:05**, both on the final tree with
  `origin/main` merged in. The delta is **+17 and all of them passes**: 13 in
  `test_data_support.py` (25 → 38) and 4 parametrised skill tests that the new
  reference file adds. No new skip.

  - **σ-scale invariance, over the 27 bundled fixtures, scaling the declared σ
    alone from ×1.0 to ×0.05.** Steps per FWHM moved by a median factor of
    **5.45** and up to **78×** before; **1.000**, worst 1.037, after. Every
    fixture read 1.5-2.5 steps per FWHM at the D1B ratio, i.e.
    `PATTERN_UNDERSAMPLED` on all of them.
  - **The constant is a selection width and not a floor**, and is documented as
    one. Invariance is exact from 0.015 upward, so 0.03 carries 2× margin, but
    the value decides how many lines the median covers and moves the answer up
    to 18 % between 0.02 and 0.05. At honest σ the answer stays at a median
    0.998 of today's, worst 0.678, and **no fixture crosses
    `STEPS_PER_FWHM_MIN` in either direction**.
  - **The anchor had to be the percentile.** One injected hot channel at 10× the
    pattern maximum moves 16 of 26 fixtures by over 5 % on a `max` anchor, one
    of them by 66 %; on the 99.9th percentile, 3 of 26 and none past 9 %.
  - **The census**: 1558 "peaks" on 11-BM NAC at the file's own σ and 9403 at a
    σ 3.46× smaller, against **96 at every scale**. On the synthetic, 79 rising
    to 201, against 27 at every scale. 27 rather than 13 because a count keeps
    no prominence bar; the defect fixed is the scale dependence.
  - **The dead-channel gate is a floor.** All 248 level-only candidates over the
    fixtures land between **0.94 and 3.00** on the weight ratio; the planted
    #274 pair reads **2243**. The answer is identical anywhere from 3 to 1000,
    and there are **zero false positives on all 27 fixtures**. Cost 24 ms at
    132 992 points.
  - **End to end**, two channels of 5750 on a synthetic LaB6 at a
    monitor-normalised σ: Rwp **0.55345** against **0.00156** with them
    excluded, a factor of 355, cell a 4.158024 against 4.156602 (truth
    4.15660), **342 ppm apart, both fits reporting `converged`**.
  - **The other candidate**, capping the trusted count, only bounds the damage:
    σ-scale spread 1.11 against 1.000, and it fails outright on three fixtures.
    Recorded and not taken.
  - `/code-review high --fix`: see the line at the end of this entry.

  **Gotchas for the successor.**

  - **`background_envelope` goes negative near an edge when a dropout is
    there.** It anchors a knot at each data edge and extrapolates linearly from
    the two nearest (WP-1028), so a dropout drags those knots down. Measured on
    a synthetic carrying #274's pair four channels from the top: the envelope
    reads −4.6 where the background is 78, across the last 30 channels. That is
    exactly where the issue's cells sit, so it was the case to get right rather
    than a corner. `dead_channels` withholds the channels it is judging and
    iterates to a fixed point; one pass leaves a long run's interior unflagged.
  - **The damage is a function of the background level**, because the weight
    ratio is (σ_local/σ_dead)² and σ_local goes as √background. The same dead
    pair outvotes 3000 live channels on a neutron background of 35 000 counts
    and **2.4** on this suite's default LaB6 at 40. The low-background case is
    correctly silent, and a fixture that wants the pathology has to declare the
    background (`DEAD_CHANNEL_BACKGROUND` in the test file).
  - **A long *interior* dropout is owned by nobody.** `signal_cutoffs` reads
    ends only, and `dead_channels` declines past `CUTOFF_MIN_DEG` because the
    level cannot survive the run. The length test alone was not enough: it left
    a 1.9° dropout reported as a spurious one-channel run, so a run is now
    declined unless live channels bound it on both sides.
  - **`peak_fraction` is the third σ-relative surface in `diagnose` and was
    deliberately left alone.** It swings by a median factor of 2.92 and up to
    9.57 over the same rescale, but its definition (channels more than 3σ above
    the envelope) is honestly σ-relative, so redefining it would change a
    shipped number's meaning. Its documentation now carries the measurement.
  - **Two task clauses were wrong about the tree.** There is no `GuardFinding`
    for this (guards are stage-level in `staged.py`; the peer is
    `PATTERN_UNDERSAMPLED`, a plain `Diagnostic`), and `help.py` documents
    parameter, flag and option *names*, never `PATTERN_*` codes.
  - **The skill's §7 had 38 B of headroom**, and `tests/test_skill.py` carried a
    note from WP-1435 saying the next addition splits the file rather than
    moving the cap again. The maintainer's criterion decided the seam: the main
    table carries what a fit is **likely** to say, and a code conditional on a
    file quirk goes to a secondary doc. The eleven reader rows became §7i,
    `references/diagnostics-reading.md`. `diagnostics.md` 36 562 → 30 953 B, its
    most headroom this month; `SKILL.md` paid 63 B net for the routing and has
    68 B left, so the next body addition faces the same wall.
    `diagnostics-projects.md` recorded that those rows stay in §7, and that
    paragraph was corrected rather than left to contradict the tree.

  *Review pass* (`/code-review --fix`, two fixes):
  - **The census bar cannot also be the ghost bar.** The shared selection was
    read as one threshold, and `_contamination_flags` searches whatever it
    returns. A ghost is accepted from `GHOST_RATIO_RANGE[0]` = 0.005 of its
    parent upwards, six times under `SAMPLING_HEIGHT_FRACTION`, so a 1 %
    Kβ image of the strongest line stopped being a candidate at all: measured
    on a well-counted synthetic, four injected at 1 % and four flagged at the
    σ bar, none under the census floor. One `find_peaks` call still, read at
    two floors off the same near-maximum: candidates at `GHOST_RATIO_RANGE[0]`,
    below which nothing can pass the ratio test anyway, and the census as the
    subset above its own bar. That subset equals a second `find_peaks` at the
    census bar on every bundled fixture at σ ×1, ×0.289 and ×0.05, so
    `n_peaks` is unchanged. A 1 % ghost of a parent that is itself a small
    fraction of the maximum is still out of reach, and that is WP-1442's to
    settle.
  - **The interval the finding quotes has to contain the run.**
    `in_range_mask` compares the quoted bound against the stored double, and
    three decimals rounded to *nearest* can land inside the run: a 0.1° grid
    built by accumulation puts a channel at 64.99999999999979, which prints as
    `65.000`. Following the message verbatim left that channel in the fit.
    `_dead_interval` widens the bounds outward instead, at most one channel a
    side, and both messages quote it.

  **Next, in order.** (1) **The two open tasks are the contributor's**, by the
  maintainer's decision of 2026-09-21, and both are blocked on files this repo
  does not have: whether `signal_cutoffs` should admit a short dropout at an
  edge is conditional on the D1B and D20 files agreeing it is separable from a
  cliff, and re-measuring `BOUND_HIT ×14` under WP-1434's test needs #274's own
  model, since **no** `BOUND_HIT` fires on the synthetic at all. (2) WP-1442
  should now import the selection rather than growing a second; its
  `Depends on` already says `1415 soft`. (3) If the D1B file ever enters
  `tests/data/`, the licence question in § Data is the gate, and the numbers in
  § Context can then be reproduced rather than quoted.

- **2026-09-21** — claimed and pruned. Both `### Inherited` entries were still
  true against `origin/main` `4ee4e7f5` and were folded into § Context rather
  than deleted: 1442's second census verified at `diagnostics.py:902` (no
  prominence, unchanged), 1434's bound test verified by `residual_cosine` in
  `least_squares.py` and `staged.py`. 1442 is filed and unstarted, so 1415
  lands first and owns the peak selection; a task now says so, and a second
  task owes the re-measured `BOUND_HIT` count. Both issues' threads are
  unchanged since 2026-09-07 (no comments, both open). Every symbol § Context
  names still exists: `SAMPLING_PROMINENCE_SIGMA`, `_median_steps_per_fwhm`,
  `sampling_steps_per_fwhm`, `signal_cutoffs` (still edge-only,
  `min_deg=CUTOFF_MIN_DEG=1.0`), `STEPS_PER_FWHM_MIN`/`MAX`. Neither the D1B
  nor the D20 file is in `tests/data/`, so where the measurements come from is
  the first thing to settle.

- **2026-09-15** — created, from the 2026-09-15 issue triage (issues #274,
  #275). Grouped because one σ column smaller than √y breaks both, and the
  same D1B file measures both. Checked against the tree: the peak finder
  thresholds on net/σ, and `signal_cutoffs` is edge-only with a 1° minimum.
