# WP-1922 — a rigid body the data reject is named

Milestone: unscheduled · Status: ✅ 2026-10-15 — `check_rigid_bodies` shipped in 1.8.0 (PR #822); Hamilton's F written once (PR #988)
Track: What fires, and what stays silent
Depends on: WP-1805 (the `RigidBody` schema)

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

## Non-goals

- Refinable internal geometry (#759, WP-1808's torsions and the Z-matrix
  work): this WP points at the remedy, never builds it.
- A rigid-bond (Hirshfeld 1976) test: it needs anisotropic ADPs, which powder
  bodies rarely carry.
- A `fit(check_bodies=True)` switch: the maintainer's later call.

## Tasks

- [x] The released-fit pair and its two statistics, as a function returning
      per-body rows (χ² both ways, Δk, F, p, ΔBIC, ranked deviations), with
      `RIGID_BODY_MISFIT` (warning, `where` the body's atom paths, `value`
      ΔBIC). The module and verb name are decided at the start.
- [x] Known-answer tests: a body with one bond 0.3 Å long fires and names that
      bond among the worst three; the right body does not fire; a phase with
      no body returns nothing; the statistics are pinned against direct calls.
- [x] `help.py` row for the code; obs/calc/diff PNGs of both arms to
      `tests/output/`. The PNGs landed; `help.py` has no arm for an engine
      code, so the row has no home (2026-10-11 entry).
- [x] Skill: a reference row for `RIGID_BODY_MISFIT`
      (`test_every_engine_diagnostic_code_has_a_protocol_row`), saying to run
      the check before quoting a body's geometry or calling a solve solved.
- [x] Hamilton's F has one authority: `body_misfit` reads F and p off the
      helper `hamilton_justified` uses, rather than writing the formula again.
- [x] `compile_phase_sites` runs once per phase in `rigid_body_misfit`, not
      once per body.

## Acceptance

On the issue's synthetic pair, the wrong body fires and names the long bond
among the worst three, and the right body does not fire.

```sh
.venv/bin/python -m pytest tests/test_body_misfit.py tests/test_skill.py tests/test_help.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #775; WP-1805 (`RigidBody`), WP-1515 (the solve benchmark, a consumer).
- Hamilton, W. C. (1965). *Acta Cryst.* 18, 502.
- Schwarz, G. (1978). *Ann. Stat.* 6, 461; Kass, R. E. & Raftery, A. E. (1995). *J. Am. Stat. Assoc.* 90, 773.
- Waser, J. (1963). *Acta Cryst.* 16, 1091; Watkin, D. (2008). *J. Appl. Cryst.* 41, 491.

## Handover log

- **2026-10-15** — closed. The rigid-body check from #822 has shipped since
  1.8.0, and this session tidied what its own handover left open. The check's
  verdict and the F and p it reports now come from one function. Before, the
  check wrote Hamilton's F a second time beside the package's test. The check's
  numbers did not move: the refactor is algebraically the same arithmetic, and
  the review confirmed it edge case by edge case.
  - **Done.** `report.layer2._hamilton_f` returns F and its denominator
    degrees of freedom, or `None` where the test is undefined.
    `hamilton_justified` and `rigid_body_misfit` both read it.
    `compile_phase_sites`, the atom labels and the `cartesian_frame` import run
    once per phase, where they had run once per body. The statistics test now
    pins `f_statistic`, `p_value` and the Hamilton verdict against the
    package's functions. The acceptance command named
    `tests/test_rigid_body_misfit.py`, which never existed. The tests are in
    `tests/test_body_misfit.py`, and the command now says so.
  - **Pruned.** The `### Inherited` entry (2026-10-11 triage) reported #822
    open and 1805's block stale. #822 merged the same day, so nothing in it
    was still true. #822's first left-open, the module docstring's stale
    torsion sentence, had already gone in WP-1954 (`b1e4542f`).
  - **Review.** `/code-review high --fix` found the test gap and three
    per-body cleanups, all applied. It declined one finding: F is still
    computed twice per body, once for the row and once inside
    `hamilton_justified`, whose verdict compares F against `ppf(1 − α)`.
    Folding that into one `p < α` call could flip a verdict at the threshold
    for `indexing/extinction.py`. That would be a behaviour change, so it is
    left.
  - **Measured.** Fast selection on `b1a40a82` (`origin/main` `c7d2303a`
    merged, nothing new), macOS arm64, `[dev]`, Python 3.12.10: 10476 passed,
    191 skipped, 1 xfailed and 1 failed. The failure was
    `test_the_wp_index_is_the_generators_output`, because this close edited
    the status line mid-run; it passes on the final tree. The session added
    no test, only assertions to an existing one, so no count should move. The
    full selection did not run: nothing here can move a measured number.
  - **Next.** Nothing on this WP. The maintainer merges PR #988.

- **2026-10-11** — every task landed from outside: PR #822 (`mustachefeeling`),
  merged as `f7ab7096` after three review rounds. It closes #775.
  - **What it adds.** `Refinement.check_rigid_bodies`
    (`report/body_misfit.py`). From the fitted state it refits each body twice,
    as the body and as free atoms restrained to the body's placed bonds and
    angles. It compares the two on the data χ² by Hamilton's ratio test and by
    ΔBIC, both at the residual's effective sample size, and warns
    `RIGID_BODY_MISFIT` only when both reject the body. The message names the
    template's largest deviations; `where` is the body's atom paths and
    `value` the ΔBIC. Each arm is a history-free `_trial(record=False)` that
    carries the caller's ties, holds and variables. A declaration that cannot
    follow into the released arm is listed in `BodyMisfitRow.dropped`.
  - **Tasks.** 1, 2 and 4 as written; both tests write both arms' PNGs. Task
    3's `help.py` row has no home: `help.py` describes no engine diagnostic
    code, only the peak finder's (`PEAK_DIAGNOSTIC_HELP`). The `abstention.md`
    row is the code's documentation.
  - **It composes with #823.** The body arm frees `torsions.*.twist`, and the
    restraints read the placed atoms, so a twisted body is restrained to its
    twisted geometry. Both PRs added a paragraph at one place in
    `docs/manual/parameterisation.md`. I merged `main` into #822 keeping both
    (`aad542fd`), the resolution the gate ran.
  - **Gate.** Stacked with #870, #823 and #853 on `main` `b7df6a10` as `a3495a34`, macOS
    arm64, `[dev,jax]`, nothing else running: fast 9173 passed, 115 skipped,
    1 xfailed and 1 failed (#843's Hypothesis case); slow 305 passed, 12
    skipped. `main` after the
    last merge (`8c5c6879`) differs from it only by three docs-and-CI merges
    (#879, #881, #874) that landed between #823 and #822. The fast suite on
    `f7ab7096` with #853 gave the same counts, and nothing the slow suite
    runs changed.
  - **Left open:** the module docstring's "frees nothing until WP-1808's
    torsions (#823) land" is stale now that #823 is in; F and p are computed
    beside `hamilton_justified`; `compile_phase_sites` recompiles for every
    body.

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #775).
  Checked against the tree at `5d1f5f67`: the three statistics functions
  exist as named and no rigid-body code has landed; no open WP owns it:
  WP-1803 closed with "#775's body-misfit diagnostic is not in the record and
  is not cut here", and 1804-1813 carry no data-side check. *Next:* wait for
  1805, then task 1.
