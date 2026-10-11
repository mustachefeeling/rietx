# WP-1922 — a rigid body the data reject is named

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: WP-1805 (the `RigidBody` schema)
Priority: P3 2026-10-08 — down from P2: a wrong body converges with a worse GOF and nothing names it, but nothing can start until 1805 lands

## Goal

A caller can ask whether the data want a rigid body to be a different shape.
The answer names the body and its worst bonds, and a `RIGID_BODY_MISFIT`
warning fires when the data reject the body beyond chance.

## Context

Issue #775 (follow-up to #561 and #759). A rigid body imposes a geometry, and
a wrong one can still converge with sensible esds. The reporter measured it on
a synthetic small-organic pattern (Cu Kα, Poisson noise): the right body gave
GOF 1.01, and the same body with one C–C bond 0.3 Å long gave GOF 2.33,
Δχ² ≈ 1.7×10⁴ at an equal parameter count. Both fits carried the same two
generic codes. Nothing named the body or the bond. `RESTRAINT_TENSION` cannot
fire for a body, which has no restraint rows. 1805's codes
(`RIGID_BODY_TEMPLATE_DRIFT`, `RIGID_BODY_NOT_INVARIANT`) judge the
declaration, never the data.

The proposed test, from the issue:
- **The released fit.** The body's atoms become free coordinates, and every
  template bond and bonded angle a soft restraint at its template value
  (Waser 1963; Watkin 2008). Scale, background and the free non-body
  parameters refine in both arms from one start.
- **Two statistics already in the package, fired on their conjunction.**
  Hamilton's ratio test as `report.layer2.hamilton_justified` on the data χ²
  (restraint rows excluded) at α = 0.001, and `report.layer2.delta_bic` at
  the effective sample size (`optimize.statistics.effective_sample_size`,
  #270) with ΔBIC > 10. Hamilton alone at raw N fires on serially correlated
  noise, which is #270's lesson.
- **Where.** The released fit's bond and angle deviations in units of their
  restraint σ, ranked, the worst three in the message.
- **When.** On request, never inside `fit()`: two short refinements per body.
  An internal trial, so `telemetry=False` and no history node (root
  CLAUDE.md, "Every fit records itself").

Checked against the tree at `5d1f5f67`: `hamilton_justified`
(`report/layer2.py:130`), `delta_bic` (`:172`) and `effective_sample_size`
(`optimize/statistics.py:381`) exist as named. No `RIGID_BODY_*` code exists
yet, since 1805 has not landed. The GOF pair was not re-measured.

### Inherited

## Non-goals

- Refinable internal geometry (#759, WP-1808's torsions and the Z-matrix
  work): this WP points at the remedy, never builds it.
- A rigid-bond (Hirshfeld 1976) test: it needs anisotropic ADPs, which powder
  bodies rarely carry.
- A `fit(check_bodies=True)` switch: the maintainer's later call.

## Tasks

- [ ] The released-fit pair and its two statistics, as a function returning
      per-body rows (χ² both ways, Δk, F, p, ΔBIC, ranked deviations), with
      `RIGID_BODY_MISFIT` (warning, `where` the body's atom paths, `value`
      ΔBIC). The module and verb name are decided at the start.
- [ ] Known-answer tests: a body with one bond 0.3 Å long fires and names that
      bond among the worst three; the right body does not fire; a phase with
      no body returns nothing; the statistics are pinned against direct calls.
- [ ] `help.py` row for the code; obs/calc/diff PNGs of both arms to
      `tests/output/`.
- [ ] Skill: a reference row for `RIGID_BODY_MISFIT`
      (`test_every_engine_diagnostic_code_has_a_protocol_row`), saying to run
      the check before quoting a body's geometry or calling a solve solved.

## Acceptance

On the issue's synthetic pair, the wrong body fires and names the long bond
among the worst three, and the right body does not fire.

```sh
.venv/bin/python -m pytest tests/test_rigid_body_misfit.py tests/test_skill.py tests/test_help.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #775; WP-1805 (`RigidBody`), WP-1515 (the solve benchmark, a consumer).
- Hamilton, W. C. (1965). *Acta Cryst.* 18, 502.
- Schwarz, G. (1978). *Ann. Stat.* 6, 461; Kass, R. E. & Raftery, A. E. (1995). *J. Am. Stat. Assoc.* 90, 773.
- Waser, J. (1963). *Acta Cryst.* 16, 1091; Watkin, D. (2008). *J. Appl. Cryst.* 41, 491.

## Handover log

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #775).
  Checked against the tree at `5d1f5f67`: the three statistics functions
  exist as named and no rigid-body code has landed; no open WP owns it:
  WP-1803 closed with "#775's body-misfit diagnostic is not in the record and
  is not cut here", and 1804-1813 carry no data-side check. *Next:* wait for
  1805, then task 1.
