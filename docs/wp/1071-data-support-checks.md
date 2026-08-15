# WP-1071 — Does the data support it: effective observations and steps per FWHM

Milestone: v1.0 · Status: ⬜
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

- **2026-08-15** — created from the McCusker audit (WP-1068); gaps 3 and 9.
