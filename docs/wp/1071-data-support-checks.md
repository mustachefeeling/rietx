# WP-1071 — Does the data support it: effective observations and steps per FWHM

Milestone: v1.0 · Status: ✅ 2026-08-15 — `DataSupport` (raw + Altomare
effective counts, structural split, both ratios), `PatternDiagnostics.
steps_per_fwhm`, `DATA_SUPPORT_LOW` + `PATTERN_UNDERSAMPLED`; gates nothing
Depends on: — (recommended **before 1003**: two small additive evidence
fields the freeze may as well cover; the grounds are in 1003's Inherited)

## Goal

A result states the observation/parameter ratio with observations counted as
unique reflections (§9), and `PatternDiagnostics` states the steps per FWHM
(§2) — both reported as evidence with the paper's bands quoted, gating
nothing. Gaps 3 and 9 of the McCusker audit (`../milestones/v1.0.md`
§ Appendix).

## Context

- **§9's whole point** is that the Rietveld algorithm will happily refine
  more parameters than the data support, because mathematically N is the
  number of profile steps. Only the integrated intensities of individual
  reflections are unique observations; the ratio "should be at least three
  and preferably five". `Statistics` (`schemas/results.py:22`) reports
  `n_points` and `n_free_parameters` and no reflection count — yet the
  package *has* the count (`compile_model`'s reflection list, and
  `optimize/statistics.py` ~line 332 already reasons about reflections in
  range for roughness identifiability).
- **Overlap is why a raw count over-counts.** Two reflections at one 2θ are
  one observation. Altomare et al. (1995, *J. Appl. Cryst.* **28**, 738)
  estimate effective observations from the fraction of each reflection's
  area not overlapped by another — the paper's own recommendation, with the
  caveat quoted ("may not have a rigorous basis"). Search the local corpus
  for the paper first (`sqlite3 ~/zotero-linker/index.sqlite`, table
  `documents`); if absent, ask the user for it rather than re-deriving or
  working around (the standing rule). Ship both numbers: the raw in-range
  unique-reflection count and the overlap-corrected effective count, each
  named for what it is.
- **Which parameters.** §9 is about *structural* parameters ("how many
  structural parameters can be refined sensibly"); `n_free_parameters`
  counts profile and background too. Report the ratio against structural
  free parameters, with the split visible, and say in the docstring which
  choice the number encodes.
- **Steps per FWHM** (§2): at least five, generally not more than ten,
  across the top of each peak. Undersampling is a data-collection error no
  refinement can repair, which is why the guidelines lead with it.
  `PatternDiagnostics` (`background/diagnostics.py:82`) is model-free and
  already fits peaks; add median step/FWHM over the fitted peaks and flag
  below five. Above ten is efficiency, not validity — report the number, no
  flag.
- **Posture: report, never refuse** (the standing design thesis; a gate
  reports evidence). Two diagnostic codes (open vocabulary), named by the
  implementer, each with its `AGENT_PROTOCOL.md` row.
- **Relation to the identifiability layer**: the Gram-condition and
  soft-mode work answers the sharper per-parameter question; this ratio is
  the coarse number a reader checks first. Cross-reference both docstrings
  so neither claims the other's job.
- Additive defaulted fields; no version bump (events precedent); the freeze
  ratifies.

## Non-goals

- Gating or refusing anything on either number.
- A per-parameter information measure (that is the identifiability layer).
- Re-deriving Altomare's estimator without the paper in hand.

## Tasks

- [x] Unique-reflection count over the fitted range (all phases, orbits
      merged, every emission line's windows — the `ticks` lesson) and the
      structural/total free-parameter split, on `Statistics` or beside it.
      → `DataSupport` beside it, on `RefinementResult.data_support`.
- [x] The Altomare effective-observation estimate (paper first — corpus,
      then ask), shipped beside the raw count.
- [x] Steps per FWHM in `PatternDiagnostics`, with the five-to-ten band
      quoted from §2.
- [x] The two diagnostic codes + `AGENT_PROTOCOL.md` rows + manual
      (`using/concepts.md` § Fit statistics) sentences.
- [x] Tests: a synthetic undersampled pattern flags; a severely overlapped
      pattern's effective count sits well below its raw count; the
      acceptance protocols' ratios quoted in the handover. PNGs to
      `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_data_support.py -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- McCusker et al. (1999), §2 (step size), §9 (the ratio). Local copy at
  `~/zotero-linker/derived/YWSBLSIS/`.
- Altomare, Cascarano, Giacovazzo, Guagliardi, Moliterni, Burla & Polidori
  (1995), *J. Appl. Cryst.* **28**, 738 — the effective-observations
  estimator (obtain before implementing).

## Handover log

- **2026-08-15 (close)** — all five items landed; the WP arrived with **no
  `### Inherited` section**, so nothing was pruned (same as 1070).

  **What shipped.** `RefinementResult.data_support` → `DataSupport`
  (`schemas/results.py`), the `Identifiability` precedent: additive, defaulted,
  no `SCHEMA_VERSION` bump. Five fields — the raw `n_unique_reflections`, the
  overlap-corrected `n_effective_observations`, `n_structural_parameters` and
  the two ratios. Built in `optimize/statistics.py`
  (`count_unique_reflections`, `effective_observations`, `measured_mask`,
  `data_support`, `STRUCTURAL_PARAMETER_GLOB`, `OBS_PER_PARAMETER_MIN/
  PREFERRED`, `EFFECTIVE_OBS_ALPHA`), from `CompiledModel.phase_peaks` at the
  fitted values plus two new public readers on `CompiledModel`, `peak_fwhm`
  and `profile_at`. Sampling in `background/diagnostics.py`
  (`sampling_steps_per_fwhm`, `PatternDiagnostics.steps_per_fwhm` /
  `n_peaks_measured`, `STEPS_PER_FWHM_MIN/MAX`,
  `SAMPLING_PROMINENCE_SIGMA`). Two codes from `refine`, both reporting.
  `docs/manual/using/concepts.md` gains two sections and `references.bib` the
  Altomare entry; `diagnose` left the deferred bucket.

  **Which "measured" is.** A fitted channel within **half the reflection's own
  FWHM** of its position — one criterion for the two hard cases at once: an
  excluded region removes what sits under it (WP-1033's fitted-mask rule one
  rank down) and a peak half-measured at a range end still counts. A
  reflection counts **once** whatever its emission lines; a census reading
  `ticks` would report 2× on a doublet.

  **The one deviation from Altomare §2(d), and why it is defensible.** The
  paper compares reflection k against every reflection whose interval
  intersects k's, evaluated wherever k is. Shipped: the pointwise maximum of
  the reflections whose *own* interval reaches that channel — which drops a
  competitor in its far tail, so it can only run high. Measured over eight
  configurations (LaB6/Cu Kα and a 235-reflection cubic cell, each swept over
  Lorentzian size broadening from none to total): **+0.00 % to +0.74 %**,
  against the estimator's own α = 2 → α = 4 spread of 6.5 % average / 13.3 %
  maximum. It buys **923 ms → 14 ms** on the worst of the eight and quadratic
  → linear scaling. The tie semantics survive exactly, because the maximum
  includes k itself.

  **The measured record** (all `[dev]`, darwin/arm64):

  | protocol | N points | reflections | M_ind (M_ind/M) | struct P | eff/P | codes |
  |---|---|---|---|---|---|---|
  | 11-BM NAC, Le Bail | 22 003 | 121 | 85.0 (0.70) | 0 | — | — |
  | 11-BM NAC, Rietveld +CaF₂ | 22 003 | 132 | 60.0 (0.45) | 8 | 7.5 | — |
  | NIST SRM 660c | 5 332 | 30 | 24.0 (0.80) | 2 | 12.0 | — |
  | GSAS-II FAP | 5 750 | 325 | 141.2 (0.43) | 7 | 20.2 | `PATTERN_UNDERSAMPLED` |

  Three things to read off it. **N overstates by 167×** on NAC (22 003 against
  132) — the shortage §9 warns about is invisible in `Statistics` alone.
  **M_ind/M lands at 0.43-0.45 on the two real multi-reflection patterns**,
  inside Altomare's own measured 0.22-0.50 across twenty structures, which is
  the strongest external check available on the implementation; SRM 660c's 0.80
  is a simple cubic with 30 lines and is expected high. **No protocol trips
  `DATA_SUPPORT_LOW`** — every one is at 7.5 or better, so the code was
  exercised on constructed rather than bundled inputs.

  **Sampling on the same data**, which calibrates the §2 measurement against
  reality better than any synthetic could: 11-BM NAC 9.32 steps per FWHM
  (0.001° step), SRM 660c 9.55 (0.008°), **FAP.XRA 4.71** (0.020°). The two
  reference-grade datasets land just inside "generally not more than ten" —
  where a well-collected pattern should be — and the one that trips the flag is
  a lab tutorial dataset, at the boundary rather than far past it.

  **The measurement inverts without a prominence floor**, on exactly the
  patterns it exists to judge. On an undersampled synthetic LaB6 (17
  reflections, 3.2 steps per FWHM by construction), plain 5σ detection returns
  **49** peaks and a median width of **1.38** steps: Poisson noise on a
  10⁵-count peak puts several 5σ maxima across its own jagged top, so the
  metric reports catastrophic undersampling on a pattern that is merely noisy.
  With the floor, the median tracks the width the pattern was generated with to
  3-4 % across a 10× sweep — 3.34/3.16, 8.21/7.91, 12.76/12.65, 31.87/31.62 —
  and 5σ and 20σ give bit-identical answers, which is the guard that it is a
  floor and not a tuning (a test pins it).

  **Counts.** Fast selection `[dev]`, darwin/arm64: 2327+112 after task 1,
  **2343 passed + 112 skipped** in ~3:01-3:03 after task 3 — +16, matching the
  16 tests added between those runs, all passes. `tests/test_data_support.py`
  is 25 tests. Full suite: see the closing line below.

  **One pre-existing defect found and left alone** (out of scope, no WP):
  `compile_model` raises `ValueError: einstein sum subscripts string contains
  too many subscripts for operand 0` when a phase has **no** reflection in the
  fit range — `generate_reflections` returns `hkl` shaped `(0,)` rather than
  `(0, 3)` and `d_spacings` einsums it. `model.evaluate` fails the same way, so
  the census is not the regression; the census guards the empty list anyway so
  it is never the thing that fails.

- **2026-08-15** — created from the McCusker audit (WP-1068); gaps 3 and 9.
