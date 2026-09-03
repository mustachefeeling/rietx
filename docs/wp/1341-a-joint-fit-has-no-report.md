# WP-1341 — a joint fit has no report

Milestone: unscheduled · Status: ⬜
Depends on: — (1312 soft: it exercises and audits the joint fit; 1335 soft: the
report path this one gains should already be cheap)

## Goal

A converged multi-histogram refinement can be inspected: it emits events, it
carries a convergence figure, and — for whatever part of the report path is
genuinely histogram-agnostic — it reports. Where a quantity has no agreed
definition across histograms, the WP says so on the record instead of leaving
a `None` that reads as an oversight.

## Context

From issue #252. `MultiHistogramRefinement`'s entire public surface is:

```python
>>> [x for x in dir(rx.MultiHistogramRefinement) if not x.startswith('_')]
['fit', 'fitted_instruments', 'fitted_structures', 'n_histograms']
```

Three consequences, measured on a converged two-histogram fit (X-ray +
neutron, 41 free parameters, Rwp 0.088, GoF 1.47):

1. **No `.summary()` and no `.report()`** — `hasattr` is `False` for both. The
   whole Layer 0/1/2 path is unreachable for a joint fit: no `unmatched_obs`,
   no `off_region_chi2`, no `worst_absorption`, no `strain`/`microstructure`
   analysis, and nothing consuming a `Report` runs on one. The only
   diagnostics available are those on the raw result; in that fit, a single
   `BACKGROUND_ABSORPTION` — the same one the solo neutron fit reports.
2. **`fit()` has no telemetry parameters.** Its signature is
   `(self, data, *, mode='rietveld', plan='mccusker_default',
   two_theta_limits=None, weights=None)` — no `events=` and no
   `stage_reports=`. Where a solo fit leaves a per-stage record, a joint fit
   leaves nothing, and a diagnostic firing mid-refinement has nowhere to be
   seen.
3. **`result.statistics.max_shift_over_esd` is `None`.** Not a side effect of
   skipping the report — unpopulated on the multi-histogram result itself.
   Convergence quality can only be read from `status == "converged"`.

**The aside that makes the gap concrete**, and it is also 1335's control:
timing the same material three ways, a solo X-ray arm runs ~112 s end to end
against ~4 s of fitting, while the joint arm runs 6.8 s against 6.0 s — 1.1×
against 26×. **The joint fit is fast because none of the reporting machinery
exists for it.** A joint refinement is a first-class capability in the package
and a second-class citizen in its own reporting.

**The issue asks rather than asserts, and the asking is the useful part.** It
does not assume all three are oversights: `max_shift_over_esd` across
histograms with different point counts and weights may have no agreed
definition, and the report's region logic may be genuinely single-histogram in
its assumptions. **The maintainer answered on 2026-09-03: none of the three
is an intended limit; all are unimplemented.** What remains to write where a
reader meets it is the one definitional question inside (3) — what
`max_shift_over_esd` means across weighted histograms — under WP-1076's rule,
one rank up: **a declared name is a claim, and an honest empty state is
`None` with a reason, never a default that reads as an answer.**

The ordering the reporter says would help most from outside is (2), then (3),
then (1) — **an event log is the cheapest thing that makes a joint fit
debuggable at all.** Two things make (2) genuinely cheap: `events=` and
`cancel=` are already the shape `fit`/`run_stage`/`refine` take, and
`sequential.py` already showed how a multi-object run threads one stream
through per-member `data` fields without a new `EventKind` (WP-1016, which
added `series_index`/`…_label`/`…_n`/`…_pass`). A joint fit's histogram index
is the same move, and `EventKind` stays closed.

Some constraints that shape (1) and (3):

- **`bound_findings` is already multi-histogram-aware** — `multi.py:477` calls
  it with a `MultiParameterTable`'s bounds — so the guard path is not the
  obstacle; the report builder is.
- **Sample broadening is shared and the size coefficient is not** (WP-1131):
  `MultiParameterTable` hands histogram h the factor λ_h/λ_0 for the size
  terms, so a microstructure report on a joint fit reads one specimen size
  across histograms and must not present per-histogram coefficients as
  separate findings.
- WP-1301's held-phase rule and `phase_support` are per compiled model, so a
  phase unsupported in one histogram and supported in another is a case the
  report has to have an answer for, even if that answer is "report it per
  histogram".

## Non-goals

- Making the joint fit itself do more physics. This is reporting and
  telemetry over a capability that already works.
- The cost of the solo report path — 1335. This WP should land **after** or
  alongside it, or it imports a 26× tax into the one arm that does not have it.
- X-ray + neutron joint refinement as a *capability* question — issue #194,
  owned by WP-1312 (its item 3: exercise, audit and document the joint fit).
  #252's converged two-histogram fit is evidence for that task and is
  recorded there; this WP gives the fit a report.

## Tasks

- [ ] Decided 2026-09-03: none of the three gaps is an intended limit. Define
      `max_shift_over_esd` across weighted histograms; if no definition holds,
      say so where the field is declared rather than leaving `None`.
- [ ] `events=` (and `cancel=`) on `MultiHistogramRefinement.fit`, carrying
      the histogram index in `data` the way `sequential.py` carries the series
      index — no new `EventKind`.
- [ ] `stage_reports=`, or a written reason it is not offered here.
- [ ] Whichever part of the report path is histogram-agnostic, reachable from
      a joint result; per-histogram where the quantity is per-histogram, and
      once where WP-1131 says the specimen has one of them.
- [ ] Tests: a joint fit produces an event log a reader can partition by
      histogram; the microstructure reading agrees with the solo arms' shared
      size (WP-1131's 408.8/408.8 Å shape).
- [ ] Skill: `references/api.md` is generated and follows; the body or
      `references/judging.md` needs the row saying what a joint fit does and
      does not report, since an agent today gets silence and no explanation.

## Acceptance

A two-histogram fit emits an event log, carries a convergence figure or a
stated reason it cannot, and reports what the WP decided it reports.

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_events_viz_history.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #252 (converged two-histogram X-ray + neutron fit, 41 free
  parameters, Rwp 0.088, GoF 1.47). Distinct from the inter-stage telemetry
  gap on single-histogram fits (#231, #245).
- WP-1016 (per-member events in a series), WP-1131 (what a joint fit shares).

## Handover log

- **2026-09-03** — created, from the 2026-09-03 issue triage (issue #252).
  Checked on the tree: the four-member public surface is as reported, and
  `bound_findings` is already reached from `multi.py`, so the guard path is
  not what is missing. Re-checked the same day: 1312 owns #194 and is named;
  test modules named as they exist. Decided the same day: none of the three
  gaps is intended.
