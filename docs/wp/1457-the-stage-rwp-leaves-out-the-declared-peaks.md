# WP-1457 — the stage Rwp leaves out the declared peaks

Milestone: unscheduled · Status: ✅ 2026-09-29 — the stage Rwp counts the declared peaks, and `fit_start` carries `n_fitted` beside the file's count (PR #450)
Track: What fires, and what stays silent
Depends on: —

## Goal

Every `stage_end` event's `rwp` is the Rwp of the model the stage fitted,
declared peaks included, so the progress line, `rietx watch` and
`status.json` show the same number the result does. One test pins
`stage_end.rwp == fit_end.rwp` on a one-stage fit that declares a peak.

## Context

Issue #441 (2026-09-23), found on a real operando series and reproduced on a
synthetic C2/m cell.

**The mechanism.** `refine.py:2238-2242` (at `8fbafe5`) computes the stage
Rwp as

```python
y_bkg = model.background(values)
stage_rwp = compute_statistics(
    model.y_obs, y_bkg + model.bragg_component(values), model.sigma, ...).rwp
```

while `CompiledModel.evaluate` (`model/forward.py:1621-1634`) is
`background + extra_peak_curve + bragg_component` whenever
`model.peak_components` is non-empty. A `HumpComponent` lives inside
`background()`; a `PeakComponent` does not. So with any declared peak each
stage's Rwp is that of a model with the declared peaks deleted. The stage
block (WP-1302, 2026-08-29) predates `PeakComponent` (WP-1103, 2026-09-13):
the sum was right while every member of `extra_components` was
background-like. This is the miss root `CLAUDE.md` names for the component
seam: "a third member audits every reader of the list", learned from a
second member that did not.

**Checked against the tree at `8fbafe5`** with the issue's script, unchanged
except for its spies (kept in the triage's scratchpad, not the tree):

| declared peaks | stage_end.rwp, per stage | fit_end.rwp |
|---|---|---|
| two | 0.22530, 0.22784, 0.20756, 0.20272, 0.20272 | 0.11313 |
| none | 0.16004, 0.15973, 0.11437, 0.11211, 0.11211 | 0.11211 |

The reporter's figures reproduce to every printed digit (Pawley, five
stages, window (6, 33), λ 0.73 Å). With peaks declared the last stage reads
1.79× the fit's own Rwp; without them the two agree.

**Who reads the wrong number.** `history/events.py:239-240`, the
`progress=` line. `runs.py:1517-1518`, which writes it into `status.json`,
which `rietx watch` shows as the run's Rwp. The same file's snapshot writer
(`runs.py:1608-1619`) then overwrites `status.json`'s `rwp` from the
snapshot payload, which goes through `evaluate` and is right. Its comment
says "one stage has one Rwp, and a second computation of it is a second
answer waiting to disagree". Here the two computations do disagree, so which
Rwp a watcher sees depends on which of the two writes came last.

**Readers audited.** `git grep -n "bragg_component("` finds one caller
outside `evaluate`: this one. `multi.py` emits no `stage_end` (issue #252,
WP-1341), so it has no copy of the sum. The fit, `fit_end.rwp`,
`result.statistics.rwp`, the history node's metrics and the snapshot all go
through `evaluate` and are right.

**The fix and its bit-identity bar.** Add `model.extra_peak_curve(values)`
in `evaluate`'s own order (`background + extra + bragg`), and only when
`model.peak_components` is non-empty. `evaluate`'s comment explains why the
empty case must keep its association: addition is not associative, so
folding the two arms would move the last digit of every stage Rwp for no
gain. Keep reusing `y_bkg` rather than calling `evaluate`. The block's own
comment prices a second background pass as the thing to avoid.

**A minor point from the same issue.** `fit_start.n_points` is
`len(data.two_theta)`, the whole file (`refine.py:2371`), while every
`stage_start` counts the fitted channels (`len(model.tt)`). Nothing reads it
as a fitted count today, as far as a grep shows. Either give it the fitted
count, with the file's count beside it as `n_points_file` (an open-dict
addition, no `EVENT_SCHEMA_VERSION` bump), or say in `events.py`'s
docstring which count it is. **Decided 2026-09-25, on PR #450's review:**
the first option needs a bump after all, because it changes what
`n_points` means, and `events.py` says a change of meaning is what the
version is for. So `n_points` keeps the file count and the fitted count
rides beside it as `n_fitted`, the name the GUI's project data already uses.

## Non-goals

- The traced backends' treatment of `PeakComponent`. This WP changes one
  numpy-side statistic, never the residual.
- Any change to what the fit minimises, or to any number in a
  `RefinementResult`.

## Tasks

- [x] `refine.py`'s stage block adds `extra_peak_curve` when the model
      declares peaks, in `evaluate`'s association order.
- [x] `fit_start` gains the fitted count as `n_fitted`, and `n_points`
      keeps the file count (decided 2026-09-25; see Context).
- [x] Tests: `stage_end.rwp == fit_end.rwp` on a one-stage fit declaring a
      `PeakComponent` (fails on `8fbafe5`); a no-peak fit's `stage_end.rwp`
      bit-identical to `8fbafe5`'s; `tests/test_telemetry.py` and the
      `runs` tests still pass. (The no-peak value is pinned at rel 1e-12
      against the pre-fix bits, with exact equality to `fit_end.rwp` as the
      bit-level bar; handover 2026-09-29.)
- [x] Skill: none. An agent reads `result.statistics.rwp`, which was right;
      the progress line is what a person watches.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_events_viz_history.py tests/test_telemetry.py tests/test_extra_components.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

None beyond the issue: no physics changes.

## Handover log

- **2026-09-29** — closed. Every `stage_end` event now reports the Rwp of
  the model the stage actually fitted, declared peaks included. So the
  progress line, `status.json` and `rietx watch` show the number the result
  shows, and a fit that declares a `PeakComponent` no longer reads 1.4-2.9×
  worse on every stage than it is (the issue's variants). `fit_start` also
  carries the fitted channel count beside the file's own count, so a reader
  of the event stream no longer has to know that the two differ. It arrived
  as PR #450 (`mustachefeeling`), reviewed over two rounds in the
  `/pr-review all` runs of 2026-09-25 and 2026-09-29, and merged as
  `b76671a2`. It closed #441.
  - *Done*: the stage block in `refine.py` sums `background +
    extra_peak_curve + bragg_component` in `CompiledModel.evaluate`'s own
    association when the model declares peaks. It keeps the two-term sum
    when none are declared, so a no-peak stage Rwp keeps its last bit.
    `fit_start.n_points` stays the file's count and `n_fitted` rides beside
    it, from `project.fitted_mask`. It is a new key on an existing kind, so
    `EVENT_SCHEMA_VERSION` is not bumped. `history/events.py`'s docstring
    says which count each key is. Three tests in
    `tests/test_events_viz_history.py`: the stage Rwp equals `fit_end.rwp`
    on a one-stage fit declaring a peak; a no-peak fit's stage Rwp is pinned
    at rel 1e-12 with each kernel path declared (`[numpy]`/`[compiled]`);
    and `n_points`/`n_fitted` hold their meanings.
  - *Measured* (review, Linux x86_64, 4 cores, Python 3.12.3, `[dev,jax]`
    bench venv, run as root, on `f1b89d63` with #523, #450 and #521 merged
    together, which touch disjoint files): full suite, slow included, 7013
    passed, 118 skipped, 1 failed in 1:15:44. The failure was
    `test_held_phase.py::test_the_ramp_reproduction_no_longer_runs_away`'s
    wall-clock runaway guard, at 76.2 s against 60 s under a load average of
    9-11 on 4 cores. It passes alone on the same tree in 18.85 s. Main after
    the three merges is content-identical to that tree.
  - *Gotchas*: round 1 changed `n_points`' meaning under this WP's own
    advice. `events.py` says a changed meaning is what the schema version is
    for, so the Context's first option was wrong, and the review said so.
    The GUI console prints event `data` generically, so `n_fitted` shows up
    there with no JS change.
  - *Next*: none. The skill line stands as written: an agent reads
    `result.statistics.rwp`, which was always right.
- **2026-09-24** — created, from the 2026-09-24 issue triage (issue #441).
  Checked against the tree at `8fbafe5`: the mechanism is at the lines
  cited, the issue's figures reproduce to the digit, and the stage block is
  the only caller that sums the model without `extra_peak_curve`. Next: the
  one-line fix and its two tests.
- **2026-09-25** — PR #450 (`mustachefeeling`) reviewed at `6fa8af7c` in the
  `/pr-review all` run; held, not merged. The stage-Rwp fix is right: it
  restates `evaluate`'s sum in its own association order, and a no-peak fit
  keeps its stage Rwp to the bit. Two items stand before merge. The golden
  `PRE_FIX_NO_PEAK_RWP` must declare its kernel path
  (`compiled.set_enabled`). And `fit_start.n_points` changed meaning under
  this file's advice, so the maintainer decided the new key above. That
  advice was this WP's mistake, and the review says so.
