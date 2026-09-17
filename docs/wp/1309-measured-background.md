# WP-1309 — a measured background: the container exists, the scale and the esds do not

Milestone: unscheduled · Status: 🔄 2026-09-17 — claimed by @yue-here; the real blank has arrived and is the one task left
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
- [ ] **Deferred, waiting on the file** (2026-09-17): vendor the 11-BM
      empty-Kapton blank (run 4736) with a provenance row in
      `tests/data/README.md`, and check the fit against it. The beamline's
      standards wiki still lists the scan and every `/data/` link on it 404s
      since the site moved to Drupal, which is where `11BM_Si640c.xy` came
      from too; that one was recovered through the Internet Archive, and
      archive.org is refused at TLS from this network. The maintainer will
      supply the file. Until it lands the fixture is a synthetic blank, which
      exercises every trap above and corroborates no number of the issue's.
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
