# WP-1309 — a measured background: the container exists, the scale and the esds do not

Milestone: unscheduled · Status: ⬜
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

- [ ] Schema: `scale` + `fixed_sigma` on `BackgroundFixedPlusChebyshev`,
      defaults bit-identical to today; `help.py` entries; out-of-range refusal
      replacing the silent clamp.
- [ ] The `bkg_design` row: normalised, s ≥ 0, registered in `bkg_paths`; the
      unconditional `fixed_background` term cleared when the row is active
      (trap 2's test: the double-count is loud, never silent).
- [ ] σ propagation through `interpolate_fixed`; `background/select.py` made
      aware of the fixed direction (trap 4).
- [ ] Vendor the Si640c blank with a provenance row in
      `tests/data/README.md` (terms checked per file, as ever); a
      `rietx compare` row for the new correction.
- [ ] Manual: the blank section in `using/data.md` grows the scale, the
      correlated-series sentence, and the angle-dependence caveat; skill row
      if a new diagnostic code lands.
- [ ] Tests for each trap above + the blank-fixture refinement, obs/calc/diff
      PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_measured.py tests/test_compare_ui.py   # first module is new, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: with `scale` fixed at 1 every existing number is bit-identical;
freeing it on the Si640c blank fixture lands the interior minimum (s ≈ 0.85,
Rwp below the fixed-scale fit) with an esd; the double-count configuration
fails loudly; the compare panel localises where the correction acted.

## References

- Issue #171 — the measurements, TOPAS `bkg_file` prior art, and the five
  implementation notes.
- Coelho, A. A., *TOPAS-Academic Technical Reference* (v8) — `bkg_file`'s two
  forms.
- Root CLAUDE.md § Invariants — weights, never-subtract, background
  flexibility as a correctness question
  (`optimize.statistics.background_absorption`).

## Handover log

- **2026-09-01** — created, from issue #171 (2026-09-01 triage). Settled: the
  scale is one linear design row and the schema extends the existing member;
  first open decision is the row-normalisation convention and its wording.
