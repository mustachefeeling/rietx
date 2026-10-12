# WP-1341 — a joint fit has no report

Milestone: unscheduled · Status: 🔄 2026-10-12 — claimed by @yue-here
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

- **`bound_findings` is already multi-histogram-aware.** `_build_result` calls
  it with a `MultiParameterTable`'s bounds, and since WP-1434 with `cos=` and
  `esd=` too. So the guard path is not the obstacle; the report builder is.
  (Superseded in part 2026-10-12: the call has moved off `multi.py:477`.)
- **Sample broadening is shared and the size coefficient is not** (WP-1131):
  `MultiParameterTable` hands histogram h the factor λ_h/λ_0 for the size
  terms, so a microstructure report on a joint fit reads one specimen size
  across histograms and must not present per-histogram coefficients as
  separate findings.
- WP-1301's held-phase rule and `phase_support` are per compiled model, so a
  phase unsupported in one histogram and supported in another is a case the
  report has to have an answer for, even if that answer is "report it per
  histogram".

### What later work changed (folded from Inherited, 2026-10-12)

Each entry below arrived in this WP's Inherited section and was checked
against the tree at e1d19359 on arrival.

- **`STAGE_PATH_NOT_FREE` is not reported for a joint fit** (issue #803,
  triage 2026-10-08). PR #789 added the finding for a single histogram
  (`refine._fixed_literal_diagnostics`, fed one `ParameterTable`).
  `multi.DIAGNOSTIC_SCOPES` declares it `ABSENT`, so a joint plan naming
  `phases.0.atoms.2.x` on a special position, or `phases.0.cell.b` on a
  tetragonal phase, frees nothing and says nothing. Wiring it needs the
  helper to read each histogram's table, a finding that names which
  histogram's table holds the path fixed, and agreement with
  `_unreached_histogram_diagnostics` about what a literal matches. Done when
  a locked or tied literal reports once per path naming its stages, and
  #789's silence cases stay silent. Still true on arrival
  (`multi.py:255`). It is the task added below.
- **The joint fit judges support on the screen alone** (from WP-1523,
  2026-10-04). A single fit calls a phase seen when its scale is 3σ from zero
  (`refine._answer_significance`). A joint fit reads only `phase_support`,
  which on issue #481's blank frame reached 3.1-4.4σ once a released cell
  chased the noise. Whether the joint report takes the marginal test, and
  whether histograms combine in quadrature, is open. Still true on arrival
  (`multi.py:1297`). Not taken this session.
- **The joint runner runs the scale-B probe** (from WP-1534, 2026-10-04).
  `SCALE_B_INSEPARABLE` fires at top level and `DIAGNOSTIC_SCOPES` lists it
  as FIT. Nothing is left here but to render it.
- **The census of what `multi.py` re-derives is wider than its diagnostics**
  (from WP-1344, 2026-10-01). WP-1344 did not audit the other members that
  re-derive something `Refinement` derives. `_ticks` is the known case. The
  rule WP-1103 settled holds: a declared peak belongs to every histogram that
  sees it. WP-1908 is editing the tick builders in parallel, so the audit is
  left to a later pass.
- **`STAGE_FREED_NOTHING` sits on the top-level diagnostics, one per
  histogram** (from WP-1414, 2026-09-22), `value` the histogram index. A
  report for a joint fit should put it beside the histogram it names.
  `STAGE_PATH_UNKNOWN` also fires on joint fits, with its suggestion naming
  the `mtable` listing, because `MultiHistogramRefinement` has no
  `parameters()`.
- **`worst_absorption` has an honest empty state** (from WP-1465,
  2026-09-27). `BackgroundEvidence.worst_absorption` is `float | None`, and a
  per-histogram background section built here carries `None` for a histogram
  whose screen found no target. `report/background.py`'s `assess_background`
  is the builder to reuse.
- **Deleted on arrival:** WP-1434's note that `bound_findings` grew `cos=` and
  `esd=`, which `multi.py` already passes. It is folded into the Context
  bullet above.

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

- [x] Decided 2026-09-03: none of the three gaps is an intended limit. Define
      `max_shift_over_esd` across weighted histograms; if no definition holds,
      say so where the field is declared rather than leaving `None`.
      Defined 2026-10-12: one shift and one esd per column of the joint θ
      (`least_squares._final_shift_over_esd_multi`), copied onto the joint
      result's statistics.
- [x] `events=` (and `cancel=`) on `MultiHistogramRefinement.fit`, carrying
      the histogram index in `data` the way `sequential.py` carries the series
      index — no new `EventKind`. Landed 2026-10-12 with `telemetry=`,
      `label=` and `progress=`. Each kind is emitted once per fit, stage or
      evaluation, because the joint solve is one solve; the index rides in a
      `histograms` row per histogram (`history/events.py` says why it is not
      the series' per-event stamp).
- [x] `stage_reports=`, or a written reason it is not offered here.
      Not offered (2026-10-12). One rung is a report per histogram per
      stage at ~0.36 s each (#245), so it would multiply the solo tax WP-1335
      owns. The reason is in `MultiHistogramRefinement.fit`'s docstring and
      in `using/series.md`.
- [x] Whichever part of the report path is histogram-agnostic, reachable from
      a joint result; per-histogram where the quantity is per-histogram, and
      once where WP-1131 says the specimen has one of them.
      `MultiHistogramRefinement.report(h)` (2026-10-12): Layers 0-2 per
      histogram, the background section off that histogram's own screen
      (the joint result now carries every screen, `hist.<h>.`-scoped), and
      the specimen's one microstructure block in every report. It inherits
      the joint path's missing #272 recompile (handover).
- [x] `STAGE_PATH_NOT_FREE` on a joint plan (#803, folded 2026-10-12): the
      helper reads each histogram's table under the joint matching rule, one
      finding per path names the histograms whose table holds it fixed, and
      the `DIAGNOSTIC_SCOPES` row moves from `ABSENT` to `FIT`. Landed
      2026-10-12 as `multi._joint_fixed_literals` over
      `refine._fixed_literal_diagnostics(canonical=)`; single-fit output is
      unchanged.
- [x] Tests: a joint fit produces an event log a reader can partition by
      histogram; the microstructure reading agrees with the solo arms' shared
      size (WP-1131's 408.8/408.8 Å shape); `STAGE_PATH_NOT_FREE` fires on a
      joint plan and #789's silence cases stay silent. All in
      `tests/test_joint_report.py`, each landed with its feature.
- [x] Skill: the generated API index follows (`make_api_index.py`); the body
      or a reference row says what a joint fit does and does not report, since
      an agent today gets silence and no explanation. 2026-10-12: `api.md`
      lists `MultiHistogramRefinement.report` and `refine_multi`'s telemetry
      keywords; `watching.md` 9d.10 and `surprises.md` 8.30 carry the rows.
      The body is unchanged.

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
