# WP-0308 — Multi-histogram stacked residuals

Milestone: v0.3 · Status: ⬜ not started
Depends on: —

## Goal

Refine one structural model against several patterns at once (different
instruments, wavelengths, or temperatures) with an explicit parameter-sharing
map, exercised end to end.

## Context

The API surface already accepts lists — this WP makes that real rather than
nominal. Start by auditing exactly how far list support currently goes in
[`refine.py`](../../src/pxrdref/refine.py) and
[`optimize/least_squares.py`](../../src/pxrdref/optimize/least_squares.py)
before designing anything.

The mechanics: each histogram contributes its own residual block (its own
background, scale, profile terms, and 2θ range); the blocks are stacked into
one residual vector and one Jacobian, with shared parameters (cell,
coordinates, occupancies, ADPs) contributing to every block's columns. This is
the same "extra rows in the residual" pattern the penalized P-spline already
uses for its √λ·D₂·c penalty rows — read
[`background/models.py`](../../src/pxrdref/background/models.py) and the
statistics handling in
[`optimize/statistics.py`](../../src/pxrdref/optimize/statistics.py) first,
because that code already faced the "which rows count for statistics" question
and answered it (penalty rows are excluded from Rwp/Durbin-Watson/
Bérar-Lelann but kept in the covariance).

Decisions this WP must make and document:

- **Statistics reporting**: a combined Rwp plus per-histogram Rwp. A single
  pooled number hides a badly-fitting histogram, which is exactly the failure
  mode this package's whole reporting design exists to prevent. Per-histogram
  numbers are not optional.
- **Weighting between histograms**: whether a histogram carries a relative
  weight, and what the default is. Default to unit weight (each point's own
  esd governs) and make any deviation explicit and recorded in provenance —
  silent inter-histogram weighting is a reproducibility hazard.
- **Parameter-sharing map**: dot-paths gain a histogram scope for the
  per-histogram terms. Keep fnmatch glob semantics working (CLAUDE.md: no
  brackets in paths — fnmatch treats `[..]` as a character class).
- **Frozen-per-stage discreteness applies per histogram**: each gets its own
  frozen hkl list, windows and FCJ node counts at stage compile.

History and FitReport both need to cope: a node's `RefinementState` currently
carries one `two_theta_limits`, and the report's regions are per-pattern.
Decide and record whether reports are per-histogram (recommended) and how a
multi-histogram node serializes.

## Non-goals

- Sequential/in-situ series with warm start (WP-0505) — that is many *separate*
  refinements chained, not one joint residual.
- Neutron/TOF histograms (v2 fence); this is multiple CW X-ray patterns.
- `vmap`-batched series (v2).

## Tasks

- [ ] Audit and document what list support exists today; write the sharing-map
      design into this file before coding
- [ ] Stacked residual + Jacobian across histograms, per-histogram frozen
      compile state
- [ ] Per-histogram *and* combined statistics; provenance records the weighting
- [ ] Parameter-sharing map with histogram-scoped dot-paths, fnmatch-compatible
- [ ] History serialization for multi-histogram state; FitReport per histogram
- [ ] Tests: two synthetic patterns of the same phase at different wavelengths
      recover the shared cell better than either alone; a deliberately
      bad second histogram shows up in its own Rwp rather than being masked
- [ ] PNGs per histogram to `tests/output/`

## Acceptance

Joint refinement of two synthetic histograms of one phase recovers the shared
cell within esds, with per-histogram Rwp reported separately; a deliberately
mis-scaled histogram is visible in its own Rwp.

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py -q
```

## References

- Von Dreele (1997) J. Appl. Cryst. 30, 517 — multi-histogram Rietveld
  practice (GSAS lineage).

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
