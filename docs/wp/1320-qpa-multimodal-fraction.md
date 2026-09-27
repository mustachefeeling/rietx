# WP-1320 — a phase fraction the pattern cannot fix

Milestone: unscheduled · Status: ✅ 2026-09-27 — `Refinement.profile_fraction` and `QPA_FRACTION_UNDETERMINED`, the docs first, a synthetic two-basin fixture
Track: What fires, and what stays silent
Depends on: — (1310 soft, closed 2026-09-16: how findings arrive on the result affects how this one reads)

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

**Decided 2026-09-27, each measured on `tests/test_qpa_multimodal.py`'s
fixtures.** *Surface*: a standalone verb, `Refinement.profile_fraction(data,
phase, *, axes=None, fwhm=None) -> FractionProfile`, delegating to
`strategy/fraction_profile.py` the way `suggest` delegates to
`strategy/suggest.py`; the answer rides beside the result, never inside it, and
every refit runs on `Refinement._trial()` (a branch) with `telemetry=False`.
*Axis*: every free isotropic width term of the phase (`lor_strain`,
`lor_size`, `gauss_strain`, `gauss_size`), each pinned in turn — **not the
scale**, and not a correlation-ranked single term. The scale was tried first
(the reporter's design): a refit at a pinned scale reaches the hump basin only
by broadening the phase under `PHASE_SUPPORT_SIGMA`, where WP-1301's collapse
rule restores and holds its structure, so at 4× and 8× the fitted scale the
width stayed held and χ² ran away. At a pinned width the rest is near-linear in
the scale and each refit has one answer. *Grid*: 0, then 11 FWHMs log-spaced
from 0.01° to half the fitted span, converted per term at mid-range; the full
span fires `FROZEN_COMPILE_STALE` (85° on an 85° range, not 60°). *Cut*:
Δχ² ≤ 3.84·χ²_red·f² on the data's own χ², the esds' calibration, so one
quadratic basin reproduces W ± 1.96 esd (controls: every admissible W within
0.46-0.79 of that half-width). *Name and threshold*: `QPA_FRACTION_UNDETERMINED`
(a claim, not a mechanism: a wide flat ridge fires it too), when an admissible
W lies more than `FRACTION_PROFILE_EXCESS` = 2 half-widths from the fit's —
chosen, between the controls' ≤ 0.79 and the fixture's ≈ 74. *Not taken*: the
reporter's `remove_phase` advice action. Presence is
`SEQUENTIAL_PERSISTENT_FINDING`'s and the agent's (1301's non-goal), and a range reaching 0 % already
says presence is not established; the skill row says so.

**A second candidate for the pin axis: the scale itself** (the reporter's
design, posted on #203 on 2026-09-01, after this file was written; still
the thread's last word on 2026-09-27). Profile the **phase scale**, not a
broadening term: pin `phases.i.scale` on a grid rising from 0, refit the
nuisances warm point to point, and report a one-sided 95 % limit at
Δχ² ≤ 2.71, inflated by the Bérar-Lelann factor the esds already carry so
the limit and the esds share one calibration. Convert to wt% **per grid
point**, never after, since W is nonlinear in every scale. Three caveats
come with it. The linear-block screen is a *lower* bound on the limit, so it
may trigger the scan and is never reported as the limit. On a real
six-phase fit no local statistic singled the phase out
(`background_absorption` 0.183 against another phase's 0.208; absent from
`top_correlations` and from the one scale-bearing soft mode). And the limit
bounds the modelled crystalline form only, never amorphous material of the
same composition. It also suggests a `remove_phase` action at
`execution="advice"` beside `add_impurity_phase`. Checked at `ebc45b9`:
`ActionKind` (`report/schemas.py`) has no `remove_phase`, and no
pinned-scale profile exists.

**The fraction's other silent error is ZMV, and it is not this one**
(from 1324, 2026-09-02). A fraction rides on `scale × ZMV`; 1324 closed two
ways the ZMV half was wrong at identical Rwp (a non-transitive multiplicity
dedup; a bare origin-ambiguous symbol silently resolving to a setting that
inverts a composition). The codes to know are
`SITE_SNAPPED_TO_SPECIAL_POSITION` and `SPACE_GROUP_SETTING_ASSUMED`, which
SKILL.md's QPA row calls the *ZMV family* beside the scale family. That
error is a **multiplicative, systematic offset** on one phase's k (boron:
cell mass 3.81 % at identical Rwp), not multimodality, so wherever the
fraction's uncertainty is described the two get one sentence apart.

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

- [x] Docs first: the skill (`references/judging.md`, `references/numbers.md`)
      and manual QPA chapter state that the QPA esd is a local quantity, with
      the pin-and-refit recipe — an improvement on silence that ships even if
      the detector slips.
- [x] Synthetic two-phase multi-modal fixture (scale×broadening ridge),
      verified to reproduce the three-basin shape; obs/calc/diff PNGs to
      `tests/output/`.
- [x] The probe: pin the correlated broadening term on a coarse grid, warm
      refits, fraction span vs Rwp span; surface and pin-axis rule decided
      and recorded.
- [x] The diagnostic carrying the admissible range; thresholds stated with
      evidence; silent on the 200 °C-shaped control.
- [x] Skill diagnostics row (all committed copies) + `help.py`/manual
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

- **2026-09-27** — closed. A trace phase's weight fraction can now be checked
  instead of trusted. Its esd describes only the basin the fit stopped in, and
  one call now scans the phase's peak width and reports every fraction the
  pattern admits, with a warning when that range is far wider than the esd
  claims. A synthetic pattern reproduces #203's shape: a fit reporting
  1.19 ± 0.53 wt% where the data admit 0.86 % to 77 %. Profiling the scale
  directly, the reporter's design, is refuted as an axis for this package:
  WP-1301's hold stops it short of the second basin.

  *Done.* Inherited pruned on arrival: the reporter's scale-profile design and
  the 1324 ZMV note, both still true at `ebc45b9`, folded into Context. Five
  tasks: the docs (`judging.md` §4b, `numbers.md`, the manual's QPA chapter),
  `tests/test_qpa_multimodal.py` (the fixture verified by a hand scan first),
  `Refinement.profile_fraction` → `FractionProfile` in `strategy/` and
  `schemas/fraction.py`, `QPA_FRACTION_UNDETERMINED`, the skill row, and Part 2
  eq. `est-profile` (Hamilton's one-constraint test). `Refinement._trial` is now
  the one trial builder, and `report.layer2._rival_trial` calls it, so
  `compare_rivals` without a history keeps the caller's ties, variables and
  holds. `SCHEMA_VERSION` 0.32 → 0.33, staged in `releases/1.5.1.md`. Decisions
  are in Context § "Decided 2026-09-27".

  *Measured* (`[dev]` venv, Linux container as root, 4 cores). Fixture: fit
  1.19 ± 0.53 wt%, profile 0.86-77.3 %, two basins, barrier Δχ² 14.7 against a
  cut of 9.39, `excess` 73.9. Control: 3.93 ± 0.54 %, range 3.29-4.42 %,
  `excess` 0.61, silent. The three recipe-grid controls reached 0.46, 0.67 and
  0.79. The module takes 14 tests in about 14 s serial. Fast selection, run
  once on `002d567` before the review pass: 6442 passed, 163 skipped, 1 failed
  in 19:22 with `-n auto`. The failure is
  `test_telemetry::…[unwritable-directory]`: as root `chmod 0o500` refuses
  nothing, and its `skipif` covers Windows only, so this is the environment,
  not this branch. The branch adds 14 tests. No main baseline was taken (the
  rule), and the nightly log needs `gh`, which this container lacks, so the
  +14 is by construction and not measured. The touched-file suites were re-run
  on the final tree: 59 passed. The full selection did not run, because
  nothing measured can move: the verb is opt-in, and the trial builder changes
  only `compare_rivals` without a history, which no acceptance suite calls.

  *Review* (`/code-review high --fix`). Five accepted, in `b7b7c6b`. The scan
  moved the shared tree's HEAD, so a project would have reopened on the last
  pinned width. Locked or tied axes, empty or non-finite grids and a scan with
  nothing measured were silent "confirmations". A point with no QPA now says
  why, and `width_value` cites its source. Three declined. The stage-scoped
  `_held` is not carried by `_trial`, since carrying it would change `branch()`
  for every caller. `compare_rivals`/`predict_then_verify` move HEAD the same
  way; that predates this branch and no WP owns it. The API index has 369 bytes
  of room, so the verb is named in the skill body's QPA row and in
  `judging.md`, not in `api.md`.

  *Gotchas and unfiled findings.* (1) A plan stage with `seed=0.01` reseeded
  the widths and ended at cost 2998 against the previous stage's 2217 while
  reporting `converged`; an unseeded rerun reached χ²_red 1.046. Nothing flags
  a stage ending worse than its predecessor, and no WP owns this, so it is a
  candidate for `/issue-review`. (2) The telemetry root skip above: queuing it
  as a task timed out, so it is a one-line `skipif` for anyone. (3)
  `ActionKind` gained no `remove_phase` (Context says why).

  Next: none on this WP. #203 closes when the PR merges. 1463, whose soft
  dependency this was, and 1465, the same ridge on the series path, each carry
  an Inherited note.
- **2026-09-01** — created, from issue #203 (2026-09-01 triage, second
  batch). Settled: two stages, docs truth before detector; probe opt-in,
  never default; the fixture is synthetic because the filer's series is not
  in the repo. First open decision is the probe's surface.
