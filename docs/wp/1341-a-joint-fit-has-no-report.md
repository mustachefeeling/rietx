# WP-1341 — a joint fit has no report

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: — (1312 soft: it exercises and audits the joint fit; 1335 soft: the
report path this one gains should already be cheap; 1344 soft: it sorts each
diagnostic into per specimen, per histogram or per fit, and decides where a
per-histogram finding lives, and this report renders that)
Priority: P2 2026-09-23 — a joint fit cannot be inspected; refining the histograms apart is the workaround

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

### Inherited

- **2026-10-08, from the issue triage (issue #803): `STAGE_PATH_NOT_FREE` is
  not reported for a joint fit.** PR #789 added the finding for a single
  histogram (`refine._fixed_literal_diagnostics`, fed one `ParameterTable`).
  `multi.DIAGNOSTIC_SCOPES` declares it `ABSENT`, so a joint plan naming
  `phases.0.atoms.2.x` on a special position, or `phases.0.cell.b` on a
  tetragonal phase, frees nothing and says nothing. Wiring it needs: the
  helper to read a `MultiParameterTable` (one table per histogram, a phase
  path scoped to one histogram or shared); a finding that names which
  histogram's table holds the path fixed; and agreement with
  `_unreached_histogram_diagnostics` about what a literal path matches, so one
  literal does not give two disagreeing findings. The row moves to `FIT` and
  its reason changes. Done when a locked or tied literal reports once per
  path naming its stages, and the four silence cases #789 tests (a free dof
  glob, a pattern, a user tie, a tied path beside its own source) stay silent
  in a joint fit. It sits here because the joint report is where a
  per-histogram finding gets rendered; it is a diagnostic wiring and not
  reporting, so it can land before the report does.
  Checked against the tree at 5d1f5f67: reproduced. Two rutile histograms
  through `refine_multi`, one stage naming `phases.0.cell.b` (a tetragonal
  tie) and then `phases.0.atoms.0.x` (Ti on 2a): `Refinement.fit` returns
  `STAGE_PATH_NOT_FREE` for each, `refine_multi` returns none, and the path is
  absent from `stages[0].freed` in both. `DIAGNOSTIC_SCOPES` carries
  `_fixed_literal_diagnostics: (ABSENT,)` with the reason the issue quotes
  (`multi.py:252`). The effect is a stage that does nothing for the path, not
  a wrong number.

- **From WP-1523, 2026-10-04: the joint fit judges support on the screen
  alone.** A single fit calls a phase seen when its scale is 3σ from zero by a
  marginal esd against counting noise (`refine._answer_significance`). A joint
  fit (`multi.py`) still reads only `phase_support`, which is now ‖y_p/σ‖₂ per
  histogram at 3σ. On issue #481's blank frame that norm reached 3.1-4.4σ once
  a released cell had chased the noise. So a joint fit can still call a
  noise-fitted phase seen. Its report should decide whether to take the
  marginal test, and whether histograms combine in quadrature. Today a phase
  any one histogram sees is seen.
- **From WP-1534, 2026-10-04: the joint runner now runs the scale–B probe**
  (this replaces WP-1534's 2026-10-02 note that it did not). A phase's scales
  are per histogram and its displacement parameters shared, so
  `multi._scale_b_probe_multi` reads the smallest angle between the span of
  its scales and the span of its displacement columns, stacked over every
  histogram. `StageResult.scale_b_held` is written, `SCALE_B_INSEPARABLE`
  fires, and `DIAGNOSTIC_SCOPES` lists it as FIT. Nothing is left for this
  WP but to include it in the joint report. It became necessary because
  `Atom.biso` lost its default bound the same day.
- **From WP-1344, 2026-10-01 (closed): the census of what `multi.py` re-derives
  is wider than its diagnostics.** WP-1344 classified every `_*_diagnostics`
  helper for the joint path under a meta-test. It did not audit the other
  `MultiHistogramRefinement` members that re-derive something `Refinement`
  derives. `_ticks` is the known case: WP-1103 found it reporting every declared
  peak as an unindexed impurity, and fixed it by making
  `CompiledModel.extra_peak_tick_positions` the one authority both builders call.
  A joint-fit report renders those members' output, so the audit belongs here.
  The rule WP-1103 settled still holds: a declared peak belongs to every
  histogram that sees it, and a radiation-keyed diagnostic to one histogram.
- **From WP-1434, 2026-09-18: `bound_findings` grew two keyword arguments,
  and `multi.py` already passes both.** It takes `cos=outcome.residual_cosine`
  and `esd=outcome.stderr_internal`, so the joint path inherits the new
  conjunction with no work here. The Context claim that the guard path is
  already multi-histogram-aware still holds and is now carrying more; the
  call has moved off `multi.py:477`.
- **From WP-1414, 2026-09-22: the joint fit has its first finding that only a
  joint fit can raise, and this WP is where it gets rendered.**
  `STAGE_FREED_NOTHING` (info) sits on the **top-level**
  `RefinementResult.diagnostics`, one per histogram, with `value` the
  histogram index and `where` the globs. The record behind it is
  `StageResult.unreached_histograms` (histogram → globs, `{}` on a single
  histogram, `None` on a result stored before schema 0.26). A report for a
  joint fit should put it beside the histogram it names rather than in a
  pooled list, since "histogram 1 kept its starting profile" is the one line
  a reader of that histogram's panel needs. `STAGE_PATH_UNKNOWN` also fires on
  joint fits, with its suggestion naming the `mtable` listing because
  `MultiHistogramRefinement` has no `parameters()`, and that absence is this
  WP's to close.
- **From WP-1465, 2026-09-27: `worst_absorption` has an honest empty state
  now, and a joint report should use it.** `BackgroundEvidence.worst_absorption`
  is `float | None`. It and `absorption` read `None` wherever the screen had
  nothing to screen: Le Bail, Pawley, or an answer stage freeing no scale,
  Biso, occupancy or ADP, or no background term (`THRESHOLDS_VERSION` 1.9).
  They read 0.0 there before, which every reader took for "clean". A
  per-histogram background section built here should carry `None` for a
  histogram whose screen found no target, never 0.0, and
  `report/background.py`'s `assess_background` is the one builder to reuse.

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
