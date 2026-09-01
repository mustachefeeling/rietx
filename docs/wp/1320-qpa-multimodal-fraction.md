# WP-1320 — a phase fraction the pattern cannot fix

Milestone: unscheduled · Status: ⬜
Depends on: — (1310 soft: how findings arrive on the result affects how this one reads)

## Goal

A phase that is present but unquantifiable is reported as such: an admissible
*range* for its weight fraction, never a confident point esd — the "confident
wrong singleton" rule applied one level up from where the package already
applies it. Delivered in two stages: the documentation truth first (the QPA
esd is a local quantity, with the probe recipe), then the measured detector
and its diagnostic.

## Context

From issue #203 (the 2026-09-01 benchmarking campaign).

**The measurement.** Lab Cu Kα in-situ series, YBaCo4O7 (hex `P6₃mc`) →
oxidised `Cmc2₁`, 15 patterns. At the 300 °C pattern rietx reports the
hexagonal fraction as **1.41 ± 0.65 wt%** with zero diagnostics, no
abstention and no suggested actions — while pinning the hexagonal phase's
`lor_strain` on a grid and refitting (warm, everything else identical,
grid points reproducing to 1e-6) shows **three reproducible basins** — 0 %,
~1.5 %, **98.7 %** — inside a total Rwp span of **0.011 pp**, with the
*lowest* Rwp on the grid belonging to the physically absurd 98.7 %. The
same scan at 200 °C spans 0.636 pp (58× more signal) with a clean single
minimum: the pathology is per-pattern, not per-setup. TOPAS on the same
pattern reports 25.308 ± 0.468 wt%, equally confident and equally arbitrary
— a shared blind spot, so **no cross-code reference exists** and the
evidence bar is the probe itself, not agreement with a peer.

**Why nothing existing can say it** (each adjacent, none covering):

- `PHASE_UNCONSTRAINED` (WP-1301) is the wrong case: the phase is present
  and contributing, so "the data cannot see it" is false. There is no code
  for **present but unquantifiable**.
- The esd cannot see it **by construction**: the flatness is multi-basin,
  each basin with healthy local curvature — exactly why the covariance
  returns a tight number. Every converged-point eigen-analysis
  (`identifiability`, soft modes, WP-1311's |ρ| = 1.000 flat direction) is
  local and looks at the wrong object.
- `PAWLEY_OVERLAP_UNRESOLVED` is the precedent *sentence* — "the sum is
  determined, the split is not" — said today about overlapped intensities.
  This WP says it about phase fractions.

**The detector is the probe.** For a phase whose scale correlates with a
broadening term, pin that term on a coarse grid, refit warm, and report the
span of the weight fraction against the span of Rwp: a large fraction range
under a flat Rwp is the signal. It costs several refits, so it is **opt-in,
never the default path** — the honest framing is a several-refits
diagnostic, not a closed-form one.

**Design decisions taken in-WP** (not pre-decided here): the probe's surface
(a standalone verb on `Refinement` vs a `fit` flag — the several-refits cost
argues standalone); the pin-axis selection rule (the issue pinned
`lor_strain` by inspection; the shipped probe needs a stated rule, e.g. the
strongest scale↔broadening correlation from the existing covariance); the
flat-Rwp tolerance and range threshold, each stated with its evidence per
the standing "assumed numbers must not look measured" discipline; and the
diagnostic's name (`QPA_FRACTION_MULTIMODAL` or similar — an open-vocabulary
`GuardFinding`-style code carrying the admissible range, not a point).

**The filer's data is not in the repo**, so the fixture is synthetic: a
two-phase model where one phase's `scale × broadening` ridge admits distinct
basins at indistinguishable Rwp, verified multi-modal by the probe itself
before anything asserts on it.

## Non-goals

- **Not a change to the esd computation** — the local covariance is correct
  as a local quantity; the defect is that nothing says it is local.
- **Not the default fit path** — the probe costs refits and stays opt-in.
- **Not local flat directions** — WP-1311 item 5 owns |ρ| = 1.000; this WP
  owns the multi-basin case that machinery cannot reach.
- **Not a general global-optimality audit** — scope is QPA weight fractions,
  the place the campaign measured the harm.

## Tasks

- [ ] Docs first: the skill (`references/judging.md`, `references/numbers.md`)
      and manual QPA chapter state that the QPA esd is a local quantity, with
      the pin-and-refit recipe — an improvement on silence that ships even if
      the detector slips.
- [ ] Synthetic two-phase multi-modal fixture (scale×broadening ridge),
      verified to reproduce the three-basin shape; obs/calc/diff PNGs to
      `tests/output/`.
- [ ] The probe: pin the correlated broadening term on a coarse grid, warm
      refits, fraction span vs Rwp span; surface and pin-axis rule decided
      and recorded.
- [ ] The diagnostic carrying the admissible range; thresholds stated with
      evidence; silent on the 200 °C-shaped control.
- [ ] Skill diagnostics row (all committed copies) + `help.py`/manual
      coverage per standing gates + tests per item.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_qpa_multimodal.py   # new module, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: on the multi-modal fixture the probe reports a fraction range
spanning its basins under a flat Rwp and the diagnostic fires carrying that
range; on a single-basin control the probe reports a narrow range and stays
silent; no accepted value moves anywhere the probe merely reports.

The shipping PR carries `Closes #203`.

## References

- Issue #203 — the grid, the three basins, the 200 °C control, the TOPAS
  parallel.
- [1301](1301-hold-unsupported-phase.md) — `PHASE_UNCONSTRAINED`, the
  adjacent case this is not; [1311](1311-walking-parameter-bounds.md) item 5
  — the local flat direction this is not.
- `optimize/statistics.py`, `qpa` — the esd machinery whose locality is the
  documented half.

## Handover log

- **2026-09-01** — created, from issue #203 (2026-09-01 triage, second
  batch). Settled: two stages, docs truth before detector; probe opt-in,
  never default; the fixture is synthetic because the filer's series is not
  in the repo. First open decision is the probe's surface.
