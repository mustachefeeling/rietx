# WP-1120 — batch the residual: the forward's un-taken WP-1112 win

Milestone: v1.1 · Status: ⬜
Depends on: 1112 (the batched kernel and its bit-identity discipline)

## Goal

`CompiledModel.evaluate` builds its Bragg component through the WP-1112
batched planes instead of the per-reflection scalar loop, bit-identical for
symmetric rows and to-rounding for FCJ rows exactly as 1112's bases are, and
the 1111 harness records the before/after.

## Context

WP-1112 batched the **derivative bases** and left the **residual** on the
scalar `_reflection_profile` loop (`phase_component`).  WP-1114's prototype
measured what that costs, on this machine's `[dev]` venv (darwin/arm64,
2026-08-21), by evaluating the same forward three ways:

| case | scalar loop | batched exact | ratio |
|---|---|---|---|
| trigger @ start | 17.0-17.6 ms | 7.5-8.0 ms | 2.2× |
| cpd-2 @ start | 2.9-3.0 ms | 0.8-0.9 ms | 3.6× |

"Batched exact" is `derivative_bases(profile_derivs=False)` plus one
`bincount` scatter of `inten · omega` per phase (the reference
implementation is `batched_exact_evaluate` in
`examples/bench_peaks_buffer.py`) — the same arithmetic, no approximation.
A cold trigger fit runs ~500 residual evaluations (WP-1109's counts), so
this is worth roughly 5 s of its ~28 s wall before any other change.

Seams and constraints:

- The residual path is `optimize/least_squares.py::residual` →
  `rows.assemble` → `model.evaluate` → `bragg_component` →
  `phase_component`.  The batched build already exists
  (`derivative_bases`, `omega` plane only under `profile_derivs=False`);
  what is missing is a forward entry point that scatters it to y and the
  wiring that makes the numpy residual use it.
- **The traced backends keep the scalar structure** — `backend/traced.py`
  builds its own residual from `phase_peaks` + windows, and
  `fcj_offsets_weights_batch` is numpy-only by intent (its docstring).
  This WP touches the numpy path only.
- **The Ω the bases build is not the Ω the residual builds** (found
  2026-08-21, opening this WP).  `derivative_bases` takes Ω from
  `_profile_basis` and the scalar residual loop from `_profile`; the two
  spell u² differently and land 1-2 ulp apart *by design*
  (`model/profiles/pseudovoigt.py`, WP-0605's measurement).  So
  `batched_exact_evaluate` cannot be lifted verbatim — it would move every
  converged fit in its last digits.  The batched forward dispatches to
  `_profile`, and the batched *shape* (layout, buckets, node mix, masking)
  is what is shared with the bases.
- **Accumulation order is observable**: `_accumulate`'s bincount is
  bit-identical to the loop's `window_add` order (phase-major, row-major).
  The scatter here must keep that property or every pinned number moves —
  assert bit-identity against the scalar path on a symmetric case and
  to-rounding agreement on an FCJ case, exactly the 1112 gate's shape.
- `phase_component` has other callers (the analytic scale column,
  `phase_support`, plotting); they can move to the batched path or stay —
  decide by measurement, not uniformity.  `lebail_update` and
  `structure_intensity_partition` keep their own loops unless measured to
  matter.
- Le Bail/Pawley hot loops pass `intensities=` explicitly; the batched
  forward must accept them the way `derivative_bases` already does.
- **`w_max` padding costs ~2× on the trigger's gather volume** (WP-1114's
  measurement, inherited 2026-08-21).  A width-bucketed scatter is the
  follow-on lever if the harness still wants more; land the plain version
  first and measure.

## Non-goals

Peak-shape approximation of any kind (1114 recorded the no-go); the traced
backends; compiled kernels (WP-1115's gate); changing evaluation counts
(1113's territory).

## Tasks

- [ ] Batched forward entry point on `CompiledModel` (omega planes +
      ordered scatter), numpy path of the residual wired to it; scalar loop
      kept for the traced backends and as the bit-identity oracle.
- [ ] Gate tests in 1112's shape: bit-identity on a symmetric case,
      to-rounding agreement + esd/parameter identity on an FCJ case.
- [ ] Harness before/after on the 1111 cases (`bench_refinement.py`), row
      added to `rietx compare` only if a protocol number moves (it must
      not — this is exact).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_forward.py tests/test_row_layout.py -q
.venv/bin/python examples/bench_refinement.py --cases trigger,cpd-2
.venv/bin/python -m ruff check src tests examples
```

The harness shows the residual-evaluation share of the trigger cold fit
shrinking by roughly the table's ratio; every Rwp identity-checks against
the pre-change run.

## References

- WP-1112's gate record (batched bases, bit-identity bars) — v1.1 milestone
  appendix.
- WP-1114 § Findings 3 — the measurement this WP exists to cash.

## Handover log

- **2026-08-21** — created by WP-1114's session: the spike measured the
  scalar residual loop at 2.2-3.6× the batched exact kernel and recorded
  the buffer no-go; this WP is the exact, cheap half of that finding.
