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

- [x] Batched forward entry point on `CompiledModel` (omega planes +
      ordered scatter), numpy path of the residual wired to it; scalar loop
      kept for the traced backends and as the bit-identity oracle.
- [x] Gate tests in 1112's shape: bit-identity on a symmetric case,
      to-rounding agreement + esd/parameter identity on an FCJ case.
- [x] Harness before/after on the 1111 cases (`bench_refinement.py`), row
      added to `rietx compare` only if a protocol number moves (it must
      not — this is exact).  No row owed: Rwp is identical on all five cases.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_batched_forward.py tests/test_derivative_bases_batched.py
.venv/bin/python examples/bench_refinement.py --cases trigger,cpd-2
.venv/bin/python -m ruff check src tests examples
```

(The command this WP opened with named `tests/test_forward.py` and
`tests/test_row_layout.py`; neither exists.  `test_batched_forward.py` is this
WP's gate, `test_derivative_bases_batched.py` is WP-1112's, and the second is
here because this WP refactored the build both share.)

The harness shows the residual-evaluation share of the trigger cold fit
shrinking by roughly the table's ratio; every Rwp identity-checks against
the pre-change run.

## References

- WP-1112's gate record (batched bases, bit-identity bars) — v1.1 milestone
  appendix.
- WP-1114 § Findings 3 — the measurement this WP exists to cash.

## Findings

**The batched forward is worth 1.65× on the trigger and ~1.12× on everything
else**, and the split says why: the trigger carries 1 188 (line, reflection)
pairs against 129-308 for the rest, so it is the case where per-reflection
*dispatch* dominated.  Measured back to back on an idle machine, `[dev]` venv,
darwin/arm64, best-of-3, this WP's branch against `dc7f4b79`:

| case | before (s) | after (s) | ratio | nfev | Rwp |
|---|---|---|---|---|---|
| nac-lebail | 0.52-0.55 | 0.44-0.48 | 1.15× | 71 → 71 | 0.14348 both |
| nac | 0.58-0.61 | 0.53-0.54 | 1.11× | 47 → 47 | 0.09317 both |
| cpd-1a | 4.74-4.75 | 4.20-4.27 | 1.12× | 408 → 408 | 0.17128 both |
| cpd-2 | 8.26-8.32 | 7.29-7.30 | 1.13× | 540 → 540 | 0.13290 both |
| trigger | 28.33-28.44 | 17.07-17.29 | **1.65×** | 363 → 364 | 0.01998 both |

**The four no-FCJ cases return identical per-stage nfev and identical Rwp.**
That is the equivalence bar met end to end rather than at one evaluation: four
independent protocols, 47 to 540 evaluations each, every one landing on the
same double.  The trigger is the only FCJ case and the only one whose count
moves, by one — the ulp reaching a trust-region decision.

**The forward is the whole gain, and the in-fit ratio is larger than the
starting model shows.**  Timed inside a real trigger fit, one process, both
paths: 11.19 s of the 11.41 s saved is inside `evaluate`, and the time spent
*elsewhere* is unchanged (13.59 s batched against 13.81 s scalar).  Per
evaluation that is **40.23 ms scalar against 10.13 ms batched — 3.97×** over
373 calls, where the same forward at the plan's *starting* model measures
2.2-2.4× (per-stage table below).

**That extra factor is not attributed**, and two plausible explanations were
measured and are wrong.  It is *not* the whole-model FD fallback in
`_make_jacobian`: instrumenting `evaluate` shows 372 of 373 calls coming from
`_data_rows`, the residual, and **zero** from the fallback, which fires on no
trigger column.  It is *not* a warm `_cached_fcj_nodes` flattering the scalar
path in the probe either: nudging the cell so every peak moves between repeats
leaves the starting-model ratio at 2.23× against 2.25× fixed.  What is left is
that the harness compiles a later stage at the values the fit has *reached*,
while the probe holds every stage at the values it started from — a difference
this WP did not chase, because the aggregate is measured directly and the sign
of the finding does not depend on it.

Weighting the starting-model ratio by the harness's per-stage nfev predicts
only 3.5-3.7 s saved against the 11.26 s measured, which is what exposed the
gap.  Quoted so a later session does not re-derive the prediction and trust it:

| stage | nfev | scalar ms | batched ms | ratio |
|---|---|---|---|---|
| scale_bkg | 21 | 17.2 | 7.5 | 2.30× |
| sample_broadening | 80 | 16.9 | 7.3 | 2.30× |
| lines_axial | 182 | 16.9 | 7.4 | 2.29× |
| biso | 31 | 17.2 | 7.4 | 2.34× |

(all 1 188 rows, w_max 135, identical FCJ node counts — the trigger's structure
is frozen the same way at every stage when compiled at the starting values)

**The Ω the residual builds is not the Ω the bases build**, and that is the
finding this WP turned on — it is in Context, and it is why
`batched_exact_evaluate` could not be lifted.

**`w_max` padding is still on the table** (WP-1114's inherited warning): the
trigger pads to 121 points against a mean window well under that.  A
width-bucketed scatter is the next lever if the harness still wants more.

## Handover log

- **2026-08-21** — created by WP-1114's session: the spike measured the
  scalar residual loop at 2.2-3.6× the batched exact kernel and recorded
  the buffer no-go; this WP is the exact, cheap half of that finding.
