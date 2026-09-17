# WP-1309 — a measured background: the container exists, the scale and the esds do not

Milestone: v1.5 · Status: ✅ 2026-09-17 — the real blank is committed and the scale is measured against it
Depends on: —

## Goal

A measured background scan (empty capillary, blank, matrix-only) enters a fit
as data: its scale refines as one linear parameter, its counting statistics
propagate, its provenance is recorded, and a grid it does not cover is refused
rather than silently clamped.

## Context

The design record is issue #171 (measurements and the author's implementation
notes); everything below is distilled from it.

**What already exists and is correct.** `BackgroundFixedPlusChebyshev`
(`schemas/instrument.py`) stores `fixed_two_theta`/`fixed_intensity`, sampled
onto the fit grid at stage compile by `background.models.interpolate_fixed`
and added, never subtracted — the invariant holds, and the manual already
names the use case. This is exactly TOPAS's `bkg_file("f.xy")` fixed-at-1
form. The ask is the second form, `bkg_file("f.xy", @, s)`: a refinable scale.

**Measured motivation** (11-BM published Si SRM 640c, run 4918, against the
beamline's own empty-Kapton blank, run 4736; protocol otherwise
`tests/test_acceptance_si640c.py`'s): Chebyshev-3 gives Rwp 0.11998 /
GoF 1.9695; adding one parametric background peak, 0.08250 / 1.3544; adding
the measured blank at scale 1.0, 0.07770 / 1.2755 with the Biso esd a third
smaller. Hand-set scales show an interior minimum at s ≈ 0.85 (Rwp 0.07603),
so 1.0 — the only value the code can express — sits 2.2 % high in Rwp with a
Biso esd 22 % wider. Attribution of the deficit: ~0.5 % monitor
normalisation, the rest the silicon attenuating the capillary's own
scattering.

**Why a scale and not a higher Chebyshev order.** The polynomial on top is
additive: it can move the level, never rescale the shape. A multiplicative
error in a fixed curve is therefore unabsorbable — and QPA is the workflow
least tolerant of it, since the bias lands in the phase scales and hence the
weight fractions while Rwp improves.

**The design, and the five ways the obvious version goes wrong** (each one a
test):

1. `y = c·T + s·f` is jointly linear in (c, s): the scale is one appended
   `bkg_design` row, exactly as `BackgroundPSpline` appends its air-scatter
   row. No nonlinear parameter, no separate solve stage.
2. `CompiledModel.background()` adds `fixed_background` unconditionally.
   Appending the design row without clearing that term double-counts the
   curve: the refined scale absorbs it as s_true − 1, Rwp is bit-for-bit
   unchanged, and only the reported scale is wrong. Bound s ≥ 0 (as TOPAS
   does) so the silent wrong answer becomes a loud one.
3. Conditioning: existing `bkg_design` rows are O(1) while a raw measured
   curve is O(background level) — column-norm spread can reach ~1e9, and
   `run_least_squares` passes scipy no `x_scale`. Normalise the row, and
   document that the reported scale is then a stated convention, not
   digit-comparable to a TOPAS `bkg_file` scale.
4. `background/select.py`'s order-selection lstsq has no notion of the fixed
   curve and would double-count the direction.
5. The scale must register in `bkg_paths`: outside it, the finite-difference
   fallback rebuilds profile derivative bases every iteration — a performance
   regression with no wrong number attached, which nothing in the suite
   would catch.

**Near-degeneracy with the constant Chebyshev term is expected, not a bug.**
`HIGH_CORRELATION` is the right channel and the docs say so: free the scale
against a low-order base and report the correlation.

**esds and the grid.** `fixed_sigma` carries the blank's counting statistics;
interpolation correlates neighbouring errors, so the propagated σ is a lower
bound unless the blank is smoothed, and smoothing is a modelling choice that
must be recorded. Outside the blank's range the current `np.interp` clamps
silently — replace with a refusal, the `check_interval` one-sentence
precedent. One blank reused across a series has fully correlated error, so a
per-pattern scale that *trends* is partly an artefact: a docs sentence, not
code.

**The physics gap no scale fixes** (recorded, not solved): the container's
scattering reaches the detector *through* the specimen in the sample run and
through nothing in the blank run, so the correct multiplier is angle-dependent
(of the order of the specimen transmission already computed for cylinders in
`model/absorption.py`); a constant scale is leading-order. State it in the
docstring.

**A series refines one scale per pattern** (issue #171, 2026-09-16, after this
WP was written). The blank is scanned at one temperature and one atmosphere,
and the container's thermal diffuse scattering, the gas and the specimen's
attenuation of both all move along a ramp. So the blank's *shape* is right only
at the condition it was measured. A `Parameter` on the kind is already per
pattern, since each pattern carries its own models, and its warm start chains
like the phase scales do. Two things follow and neither is new schema: the
sequential trajectory quotes `s` beside the Chebyshev coefficients, and the
low-order polynomial on top is where the residual shape drift belongs.

**Schema lean, decided by the first task:** extend
`BackgroundFixedPlusChebyshev` with `scale` (a `Parameter`, default fixed
at 1 — bit-identical to today) and `fixed_sigma`, rather than adding a fourth
`Background` union member. `vary=False` by default keeps every existing
project bit-identical.

## Non-goals

- **Not the computed background reference** —
  [1130](1130-background-reference.md) owns a *derived* level the fit cannot
  argue with; this WP is a *measured* one, and each is a check on the other.
- **Not the parametric broad component** —
  [1102](1102-component-seam-humps.md)'s seam; a Kapton halo can be modelled
  there or measured here (issue #115's peaks are the parametric sibling).
- **Not subtraction.** The invariant stands: additive always, held or
  co-refined.

## Tasks

- [x] Schema: `scale` + `fixed_sigma` on `BackgroundFixedPlusChebyshev`,
      defaults bit-identical to today; `help.py` entries; out-of-range refusal
      replacing the silent clamp. Also `fixed_source` (the Goal's provenance),
      `from_pattern` (the issue's "no route in"), and the theory section the
      help anchor points at.
- [x] The `bkg_design` row: **raw, not normalised** (measured, below), s ≥ 0,
      registered in `bkg_paths`; the unconditional `fixed_background` term
      cleared when the row is active (trap 2's test: the double-count is loud,
      never silent).
- [x] σ propagation through `interpolate_fixed`; `background/select.py` made
      aware of the fixed direction (trap 4).
- [x] A `rietx compare` row for the new correction.
- [x] **The real blank** (arrived 2026-09-17, supplied by the maintainer after
      the beamline's `/data/` links 404'd and archive.org stayed refused at TLS):
      `tests/data/11BM_Kapton.xy`, committed byte-for-byte with a provenance row
      that verifies it is run 4736 rather than trusting the filename, plus six
      arms in `test_acceptance_si640c.py` and their validation-matrix rows.
- [x] Manual: the blank section in `using/data.md` grows the scale, the
      correlated-series sentence, and the angle-dependence caveat; skill row
      if a new diagnostic code lands. No new code landed —
      `HIGH_CORRELATION` is the channel and it already had one — so the skill
      takes the *correction's* rule instead, in §1 beside the never-subtract
      clause.
- [x] Tests for each trap above + the blank-fixture refinement, obs/calc/diff
      PNGs to `tests/output/`. Also the CIF description, which called a blank
      scan an estimator's output, and the per-pattern scale a series was
      already capable of.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_measured.py tests/test_compare_ui.py   # first module is new, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: with `scale` fixed at 1 every existing number is bit-identical;
freeing it on the synthetic blank recovers the scale the fixture was built with,
with an esd; the double-count configuration fails loudly; the compare panel
localises where the correction acted. **The issue's own number is the deferred
half**: freeing the scale on the real run-4736 blank under
`test_acceptance_si640c.py`'s protocol must land the interior minimum near
s = 0.85, with Rwp below the 0.07770 the held-at-1.0 curve gives.

The shipping PR carries `Closes #171`.

## Findings

**The file is run 4736, and it says so in five numbers** (2026-09-17). The
header fields match what this directory recorded from the real file on
2026-08-26, which is necessary and not sufficient — a header is text. So the
out-of-package fit recorded beside them was rerun on the committed bytes (numpy
Chebyshev, scipy least-squares, the file's own σ, 1.997-49.996°): χ²ᵣ 1.1251
against the recorded 1.125, position 4.2416(111)° against 4.2417(111)°, FWHM
6.1529(228)° against 6.153(23)°, the peak-free Chebyshev-3's 5.3255 against
5.33, and fourteen polynomial terms to match the six-parameter fit. Five numbers
from one file, none of them in its header.

**The issue's *shape* reproduces; its held-at-1.0 Rwp does not** (2026-09-17).
The base arm matches to five digits (Chebyshev-3, 0.119977 / GoF 1.9695, against
the issue's 0.11998 / 1.9695), so the protocol is the issue's protocol. The
blank arms do not: the issue measured 0.07770 held at 1.0, and this tree gives
0.079220 without the blank's esds in the weight and 0.074012 with them. The
issue's implementation is not in the tree, so the gap between its held arm and
the no-σ one is not attributable here. What does reproduce is what the issue
was arguing: the minimum is **interior** at 0.85, and unity costs 2.5 % of Rwp
where the issue measured 2.2 %. The acceptance bar is met on the number as
written too, the free arm landing at 0.073749 and 0.077309 in the two weightings
against a bar of 0.07770.

**The refined scale is 0.8374(142)**, with 0.85 nine-tenths of an esd away and
unity eleven and a half. The synthetic fixture predicted the direction: a noisy
blank biases its own scale low by regression dilution, and this blank's σ/I runs
8-17 % over the range. What the fixture could not show is that the bias is small
enough to leave the answer quotable on a real pair.

**A declared curve beats a fitted one, at three parameters fewer.** On one
common weight: 0.119977 for the bare polynomial, 0.082503 for the polynomial
plus a three-parameter hump, 0.079311 for the polynomial plus the declared blank
with nothing freed at all. Measuring the container beats modelling it, which is
the case for scanning a blank and had never been made here on real data.

**σ is a function of the declared scale, so an Rwp column is not a ranking**
(2026-09-17, the finding this WP did not expect). `fixed_sigma` enters the
weight as σ² + s²·σ_f², frozen at the stage's own scale — so the *same residual*
reads 0.074012 against its own σ and 0.079311 against the specimen's, 7.2 % of
the number being weighting rather than fit. Down a scan of scales it displaces
the apparent minimum: σ-weighted it sits at s = 0.90, common-weighted at 0.85,
where the refined scale is. Every cross-arm comparison in the new tests goes
through one σ because of this, and it is the reason the package's "never an Rwp
comparison as evidence" rule has teeth for this correction in particular.

**A free polynomial eats the scale on real data too.** 0.8374(142) on three
Chebyshev terms, 0.6935(246) on six: 5.1 combined esds apart, away from the
hand-set minimum, while Rwp on one weight *prefers* the six-term arm (0.076382
against 0.077328). The synthetic row (0.8315 on two terms, 0.6479 on six) is
now corroborated on data nobody built, and the sting is new — the better Rwp
belongs to the arm whose scale is further from the measurement.

**One constant scale does not flatten the halo window** (2026-09-17). The mean
weighted residual over 4-6° 2θ is −0.47 with the scale held at 1.0, +0.20 with
it freed, and +0.43 with six polynomial terms and the scale freed. The scale
moves the calculated curve *through* the halo rather than onto it. This is the
Context's recorded physics gap, visible for the first time, but the measurement
does not separate it from the polynomial's own stiffness and the finding is
written not to claim that it does. `tests/output/si640c_blank_held_halo.png`
shows the held arm riding above the data across the whole feature.

**The row is raw, and normalising it would buy nothing** (2026-09-17). Trap 3
asked for a normalised row on conditioning grounds, which would make the
reported scale a stated convention rather than a physical multiplier of the
stored curve. Measured instead, on the synthetic fixture, sweeping the container
level over three decades:

| background level | column-norm spread | s (truth 0.85) | esd | max shift/esd | status |
|---|---|---|---|---|---|
| ×1 | 627 | 0.8315 | 0.0058 | 4.7e-3 | converged |
| ×10 | 6.3e3 | 0.8481 | 0.0019 | 9.3e-3 | converged |
| ×100 | 6.3e4 | 0.8499 | 0.0006 | 1.7e-7 | converged |
| ×1000 | 6.3e5 | 0.8500 | 0.0002 | 1.3e-5 | converged |

Every one converges, and the recovered scale gets *better* with level rather
than worse. The feared 1e9 spread does not appear on a real background level,
and the scale stays comparable to a TOPAS `bkg_file` scale digit for digit.

**A noisy blank biases its own scale low.** The row above is also the mechanism:
regression dilution, the attenuation of a coefficient whose regressor carries
measurement error. The blank's counting noise falls relative to its shape as the
level rises, and the bias falls with it: on the sweep's two-term base, −2.2 % at
×1, −0.2 % at ×10 and −0.01 % at ×100. The
σ² = σ_y² + s²σ_f² term widens the esd and does not remove the bias, which is
why smoothing the blank is a modelling choice worth recording rather than a
refinement the package should make for anyone.

**A free polynomial eats the scale while Rwp improves** (truth 0.85, one term to
six): 0.8378(42), 0.8315(58), 0.8057(91), 0.7130(154), 0.6479(182), with Rwp
falling monotonically 0.07634 → 0.07299. The issue's identifiability warning,
measured. `HIGH_CORRELATION` fires only at six terms (ρ(c0, s) = −0.993);
below that the correlation is real and under the threshold, so the rule is the
docs' and not a guard's.

**The order scan was measuring the curve's own shape** (trap 4). Blind, it runs
to 12 terms on the fixture chasing the halo; with the curve held at its true
scale it selects **2** and its BIC rises with every term after. The declared
curve is worth ten polynomial terms, which is the whole reason anybody measures
a blank. Two rules came out of the measurement and are in the docstring. A held
scale changes the response variable, so BIC is comparable *within* a setting of
`fixed` and never across two. And a free scale with a high `max_order` is the
case to be careful with: given enough terms the scan dials the measured curve
away and describes the shape itself, which is the identifiability warning
arriving from the selection side.

**The compare row does real work on a real standard.** `fixed_curve_scale`
holds the pattern's own arPLS baseline (λ = 1e7) under a Chebyshev-3 and frees
the scale, since no standard here ships with the blank scanned beside it. The
expectation was s ≈ 1 and nothing bought. Measured on NAC it is **0.850(67)**,
with Rwp 0.09317 → 0.08603 and `HIGH_CORRELATION` firing against c0: a stiff
arPLS baseline sits ~15 % high in level over a peaky range, and the scale is the
only parameter that can say so, because the polynomial is additive. The blurb
now says what was measured rather than what was predicted.

**A series needed no code, and the claim is now tested.** Issue #171's
2026-09-16 note asks for a per-pattern scale, a warm start that chains it and a
trajectory that quotes it. All three already hold: a `Parameter` on the kind is
per pattern because each pattern carries its own models, the warm start copies
values, and `SeriesResult.trajectory` is generic over the paths a fit
determined. "Nothing was needed" is a claim about three mechanisms, so the test
is there.

**The bound in trap 2 does not exist, and the review is what found it.** The
issue's note 1, this WP's Context and my own schema docstring all said that
bounding s at zero turns a double-counted curve from a silent wrong scale into a
fit that walks into its bound. It does not.
`params.transforms.internal_bounds` maps a softplus lower limit of 0.0 to −∞ —
the rule root CLAUDE.md states and that this WP quoted while getting its
consequence backwards — so `bound_findings` has no finite bound to test and a
scale driven to zero reports as a vanishing gradient. The floor is still worth
having, because it keeps a solver from finding a negative multiplier cheaper
than the physics. What makes a double count visible is the refined scale itself,
landing a whole unit from where the caller declared it.

**The member had no test at all before this WP.** Nothing in the suite built a
`BackgroundFixedPlusChebyshev`, which is why `interpolate_fixed`'s silent clamp
survived, and why "bit-identical to today" is pinned structurally here rather
than by a golden.

**A defect this WP made, and its sibling.** `background_absorption` selected its
screen targets by suffix, so `instrument.background.scale` was screened against
the background block it belongs to: R² = 1.00 by construction, and
`BACKGROUND_ABSORPTION` firing on every fit that freed the scale.
`extra_peak_absorption` carried a copy of the same line. Both now call one
`_structural_targets`, anchored at `phases.` the way `mode_fixed_path` was
anchored for `vars.scale` (WP-1119). Not generalised: a caller's own variable is
still screened on its spelling, because this function cannot see what a variable
reaches.

## References

- Issue #171 — the measurements, TOPAS `bkg_file` prior art, and the five
  implementation notes.
- Coelho, A. A., *TOPAS-Academic Technical Reference* (v8) — `bkg_file`'s two
  forms.
- Root CLAUDE.md § Invariants — weights, never-subtract, background
  flexibility as a correctness question
  (`optimize.statistics.background_absorption`).

## Handover log

### 2026-09-17 (2nd session) — the blank arrives, and the scale becomes a measurement

The number issue #171 asked for is measured rather than asserted. An empty
Kapton capillary, scanned at 11-BM in February 2010, arrived from the maintainer
and is now in the repository, so the fraction of that container's scattering
which reached the silicon scan beside it could be refined instead of hand-set.
It is 0.8374(142). The hand-set scan put the minimum at 0.85 and this lands
within one esd of it, while unity is eleven esds away, and unity was the only
value this package could express before the scale existed. The feature itself
did not change today. What changed is that it has been checked against the pair
it was built for, and that one habit for reading its output turned out to be
unsafe.

**Done.** `tests/data/11BM_Kapton.xy` is committed byte-for-byte as supplied,
with a provenance row that does not take the filename's word for it. Six arms
went into `test_acceptance_si640c.py`, which is where this pattern's protocol
already lives and where the background-peak worked example is already
executable, with their six validation-matrix rows and a regenerated
`docs/VALIDATION.md`. The manual's measured-blank chapter takes the real numbers
beside its synthetic ones, its stated angular limit takes a residual, the skill
takes how to judge the scale, and the root rulebook takes why.

**Measured** (this worktree's own venv, `[dev]` only, darwin, on current main
merged into the branch).

- *The file is run 4736, and five numbers say so.* The header matches what this
  directory recorded from the real file on 2026-08-26, which is text and proves
  nothing. So the out-of-package fit recorded beside it was rerun on the
  committed bytes: χ²ᵣ 1.1251 against the recorded 1.125, position 4.2416(111)°
  against 4.2417(111)°, FWHM 6.1529(228)° against 6.153(23)°, the peak-free
  Chebyshev-3's 5.3255 against 5.33, and fourteen polynomial terms to match the
  six-parameter fit.
- *The scale is 0.8374(142)*, with Rwp falling 0.074012 → 0.073749 under its own
  σ and 0.079311 → 0.077328 under the specimen's. The synthetic fixture
  predicted the direction of the small bias, regression dilution on a blank
  whose σ/I runs 8-17 % here.
- *A declared curve beats a fitted one at three parameters fewer.* On one common
  weight: 0.119977 for the bare polynomial, 0.082503 for the polynomial plus a
  three-parameter hump, 0.079311 for the polynomial plus the declared blank with
  nothing freed.
- *The issue's shape reproduces and its held-at-1.0 Rwp does not.* The base arm
  matches to five digits (0.119977 / GoF 1.9695 against 0.11998 / 1.9695), so
  the protocol is the issue's. Its blank arm reads 0.07770 where this tree gives
  0.079220 without the blank's esds and 0.074012 with them. The issue's
  implementation is not in the tree, so that gap is not attributable here. What
  reproduces is the argument: an interior minimum at 0.85, with unity costing
  2.5 % of Rwp where the issue measured 2.2 %.
- *A free polynomial eats the scale on real data too*: 0.8374(142) on three
  Chebyshev terms and 0.6935(246) on six, 5.1 combined esds apart and away from
  the hand-set minimum, while Rwp on one weight prefers the six-term arm
  (0.076382 against 0.077328).
- *One constant scale does not flatten the halo window.* The mean weighted
  residual over 4-6° 2θ is −0.47 held at 1.0, +0.20 freed, and +0.43 with six
  polynomial terms. The Context's recorded physics gap is visible for the first
  time, and this measurement does not separate it from the polynomial's own
  stiffness.

**Gotchas.**

- *σ is a function of the declared scale, so an Rwp column is not a ranking.*
  This is the one the WP did not anticipate. `fixed_sigma` enters the weight as
  σ² + s²·σ_f², so the same residual reads 0.074012 against its own σ and
  0.079311 against the specimen's, 7.2 % of the number being weighting. Down a
  scan of scales it displaces the apparent minimum from 0.85 to 0.90. Every
  cross-arm comparison in the new tests therefore goes through one σ, and the
  rule went one rank up into both rulebooks.
- *The zoom that shows this correction has to stop below the (111).* Framed at
  2-12° the first reflection takes the whole y-scale and the halo is invisible,
  which is the lesson this module's other zoom already records. At 2-7° the held
  arm can be seen riding above the data across the feature.
- *Six new tests and the fast selection does not move.* All six are `slow`, so
  the fast count is main's count.

**The review pass** (`/code-review high --fix`) found five and all five were
applied, none declined. One was a defect rather than a tidy-up: the headline
test's "common σ" branch weighted the free arm by the *widened* σ instead of the
specimen's own, so the pair it asserted was not the pair `docs/VALIDATION.md`
records, and the fix makes it exactly 0.079311 → 0.077328. Its sibling branch
compares each arm under its own σ, which is the thing this section establishes
is not a ranking, so it is relabelled as a regression pin rather than evidence.
The other four are a discarded polynomial background on every blank arm, a
`TypeError` where an assertion belonged, an unguarded broadcast in `_rwp_under`,
and a skip guard repeated four times. The pass also measured a claim this
session had argued: adding a final joint polish stage moves the headline scale
by nothing and Rwp by 3e-6, because staging is cumulative and the scale keeps
refining through the last stage already.

**Counts.** Final tree, current main merged in, machine free for both runs:
fast selection **5281 passed, 133 skipped** in 1:16, full suite **5460 passed,
142 skipped** in 24:40.

The fast delta from this WP is **zero by construction**, confirmed by
collection: all 18 tests in the module deselect under `-m "not slow"`. Its
number moved anyway, twice, and both are main's: 5283 → 5282 → 5281 across two
merges, each marking one row slow. The full count is **5460 both times it was
measured**, before and after the second merge, because a `slow` mark moves a
test between selections without adding one. Its +48 over the previous session's
5412 is six from this WP and the rest from five merges of main in between; no
baseline was re-measured, per the ladder.

Two wall clocks for the same selection are the reason that rule exists: the
full suite read 33:53 with another session running short selections beside it
and 24:40 alone, on trees differing by one `slow` mark. Quote the counts.
`ruff` clean.

**Next.** The WP closes here, so these are for whoever wants them rather than
for a successor on 1309.

1. `rietx compare` has no standard that ships with its own blank, and the
   repository now holds one pair that does. Adding Si640c as a compare standard
   would put the measured-curve mechanism in front of a user instead of the
   arPLS stand-in. That is a new standard and a new fixture row, so it was left
   out of this WP rather than folded in.
2. The halo-window residual is the recorded angular gap and the polynomial's
   stiffness together, unseparated. Separating them needs a transmission-weighted
   curve rather than a constant, and nobody has asked for that correction.

### 2026-09-17 — the scale a blank always needs

A blank scan is now a background this package can use. Point `from_pattern` at
an empty capillary, an empty can or a matrix-only scan, free one parameter, and
the fit reports how much of that container's scattering reached the specimen
run. It is never all of it: the two scans differ in monitor normalisation and
counting time, and the specimen absorbs what the container scatters. The scale
costs one refined parameter and buys the one thing an additive polynomial
cannot do, which is rescale a measured shape. What it does not yet have is the
corroboration the issue asked for, because the 11-BM blank that motivated it
cannot be downloaded any more, so every number below comes from a synthetic
fixture.

**Done.** `BackgroundFixedPlusChebyshev` grew `scale`, `fixed_sigma`,
`fixed_source` and `from_pattern`; `SCHEMA_VERSION` 0.20 → 0.21. A scale the
stage can move is a design row whose exact Jacobian column is the sampled curve;
one it cannot is folded into the frozen curve, where 1.0 is exactly the identity
and every pre-existing number is reproduced. Which branch is `moving_paths`'
answer, and the no-claim case takes the row, because a fold is a freeze and a
freeze on an unasked question hands a caller a column that cannot move. The
blank's esds enter the weight as σ² + s²·σ_f², frozen at the stage's own scale,
and `result.sigma` stays a lookup of `model.sigma` so every renderer inherits
it. `interpolate_fixed` refuses a channel the curve does not cover, with a
tolerance of one of the curve's own steps. `select_chebyshev_order` takes the
declared curve and chooses the order of the remainder. The CIF says "measured
curve" exactly when `fixed_source` names the measurement. The theory manual
takes both equations, `using/data.md` takes the chapter, and the skill takes one
rule in §1.

**Measured** (synthetic fixture, truth s = 0.85; `[dev]` venv, darwin).

- *The row is raw, and normalising it would buy nothing.* Sweeping the
  background level over three decades the column-norm spread runs 627 → 6.3e5
  and every fit converges, while the recovered scale improves 0.8315 → 0.8500.
  The feared 1e9 spread does not appear at a real background level, and the
  scale stays comparable to a TOPAS `bkg_file` scale digit for digit.
- *A free polynomial eats the scale while Rwp improves*: 0.8378(42) on one
  Chebyshev term, 0.8315(58) on two, 0.8057(91) on three, 0.7130(154) on four,
  0.6479(182) on six, with Rwp falling 0.07634 → 0.07299 across that row.
  `HIGH_CORRELATION` fires only at six terms (ρ(c0, s) = −0.993), so the rule
  is the docs' rather than a guard's.
- *A noisy blank biases its own scale low*, by regression dilution: the bias
  falls with the blank's counting noise, and on the sweep's two-term base it is
  −2.2 % at ×1, −0.2 % at ×10 and −0.01 % at ×100. The
  σ term widens the esd and does not remove the bias, which is why smoothing a
  blank is a modelling choice worth recording.
- *The order scan was measuring the curve's own shape.* Blind it runs to 12
  terms chasing the halo; with the curve held at its true scale it selects 2 and
  its BIC rises with every term after.
- *The compare row does real work on a real standard.* `fixed_curve_scale` on
  NAC lands at 0.850(67) with Rwp 0.09317 → 0.08603 and `HIGH_CORRELATION`
  against c0. I expected it to buy nothing; a stiff arPLS baseline sits ~15 %
  high in level over a peaky range, and the scale is the only parameter that can
  say so.
- The held-at-1.0 fit is visible as well as measurable: in
  `tests/output/measured_background_held_scale_zoom.png` the calculated curve
  rides above the data from 15° to 26°, which is the deficit the scale removes.

**Gotchas.**

- *Two defects this WP made or found.* `background_absorption` picked its screen
  targets by suffix, so `instrument.background.scale` was screened against the
  background block it belongs to: R² = 1.00 by construction, on every fit that
  freed the scale. `extra_peak_absorption` held a copy of the same line. Both
  now call one `_structural_targets`, anchored at `phases.` the way
  `mode_fixed_path` was anchored for `vars.scale`. Not generalised: a caller's
  own variable is still screened on its spelling, because the function cannot
  see what a variable reaches.
- *A new parameter family reaches the GUI and only node sees it.*
  `gui/src/lib/history.ts`'s `PLACES` needed a row, and the python suite was
  green throughout. `gui/CLAUDE.md` already states this; I found it by running
  the vitest rather than by reading the rulebook.
- *Every plan preset frees the scale*, since they free
  `instrument.background.*`. That moves the numbers of any project that held a
  fixed curve, and it is recorded as a break with `instrument.background.c*` as
  the escape.
- *The member had no test at all before this WP*, which is how a silent
  extrapolation survived in `interpolate_fixed`. Bit-identity is therefore
  pinned structurally rather than by a golden.

**The review pass** (`/code-review high --fix`, on the merged tree) found three
and I accepted all three, each as its own commit. The `min=0` floor is not a
reported bound, so three copies of that claim were wrong, the test's own name
included. `interpolate_fixed` read `ft[0]`/`ft[-1]` as the range without
checking the curve was sorted, and skipped a one-point curve entirely while
`np.interp` clamped it flat. And `RefinementResult.sig`'s docstring said
`CompiledModel.sigma` *is* `PatternData.sig()`, which the σ term makes false;
root CLAUDE.md carried the same sentence as a standing rule and takes the same
clause. Nothing was declined.

**Counts.** This worktree's own venv, `[dev]` only (no jax, no torch), darwin,
on **current main merged into the branch**, which is the only tree nothing else
tests. Fast selection **5242 passed, 133 skipped** in 2:48, run alone, against a
baseline of **5209 passed, 133 skipped** measured on b130bfd4 in a throwaway
worktree with its own venv: +33 passed and no new skip, exactly the 33 tests
added (32 in `test_background_measured.py`, one in `test_compare_ui.py`). Main's
two commits edited an existing test rather than adding one, so the arithmetic
closes without a term for them. Full suite **5412 passed, 142 skipped** in 28:37, also alone — +2 on this
session's own pre-review run of 5410, exactly the two guard tests the review
added. The full selection has no baseline measured at b130bfd4, so its delta is
quoted against this session's earlier run rather than against main. The GUI:
584 vitest passed, `svelte-check` 0 errors, dist rebuilt. `ruff` clean.

**Next**, in order.

1. The real blank. The maintainer will supply 11-BM run 4736; the check is
   freeing the scale under `test_acceptance_si640c.py`'s protocol, which must
   land near s = 0.85 with Rwp below the 0.07770 the held-at-1.0 curve gives,
   and then vendoring the file with its provenance row. Everything else in this
   WP is done, so that one task is what stands between it and ✅.
2. Nothing blocks it. The beamline's standards wiki still lists the scan and
   every `/data/` link on it 404s since the site moved to Drupal, and
   archive.org is refused at TLS from this network, so the file has to arrive
   from outside the session.

- **2026-09-01** — created, from issue #171 (2026-09-01 triage). Settled: the
  scale is one linear design row and the schema extends the existing member;
  first open decision is the row-normalisation convention and its wording.
