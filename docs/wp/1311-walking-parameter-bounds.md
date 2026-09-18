# WP-1311 — bounds and flags for the remaining walking parameters

Milestone: unscheduled · Status: 🔄 2026-09-18 — claimed by @yue-here
Depends on: — (1310 soft: how findings arrive on the result affects how these read)

## Goal

The walking parameters the width caps do not cover each get the treatment
their physics earns — a geometry-scaled bound for displacement, a flag for
Biso, an in-range positivity guard for the resolution function, an
implausibility diagnostic for the profile-width ceiling, and a flat-direction
report distinct from a correlation — every one arming on contact, speaking
when it fires, and outranked by a caller's own bound.

## Context

From issues #150 (the umbrella and its triage rule), #102 (the width half
that rule routed nowhere), and #106's aside (the flat-direction pair).

**The triage rule, stated once.** Walking parameters are not equally
dangerous. A walking **width** (strain, size) flattens the cost landscape and
can take the whole fit with it — those get caps, landed with PR #144 and its
size extension (5 nm Scherrer floor). A walking **cell** on a low-fraction
phase destabilises itself, not the fit, and is already handled
(`PHASE_UNCONSTRAINED` + the per-stage `cell_window`). Everything else earns
at most a bound-from-physics or a flag — never a tuned cap.

**Item 1 — specimen displacement, a geometry bound.** A soft bound of a few
mm scaled by `Geometry.radius`, its default fixed by a survey of the 606
solved `.inp` archive (where TOPAS fits bound it by hand), armed on contact
and reported through the existing `BOUND_HIT` machinery. The motivating
measurement is [1073](1073-capillary-displacement.md)'s: on 11-BM the
zero/displacement pair is a degeneracy the fit rides to a bound **while Rwp
improves** and the cell moves 1117 ppm.

**Superseded in part, 2026-09-18.** A bound is already there, and it is flat.
`Geometry.sample_displacement` has declared `min=-1.0, max=1.0, unit="mm"`
since v0.2 (`473cc5a7`), and `capillary_offset_along_beam` and
`capillary_offset_across_beam` the same since
[1073](1073-capillary-displacement.md) (`b819b3bd`). So this item is not
arming a bound. It is deciding whether ±1 mm is the right number and whether
it should scale at all. The field the WP called `Geometry.radius` is
`goniometer_radius_mm`, and it is `float | None = None`, so a geometry-scaled
bound has nothing to scale by on an instrument that never declared one. The
flat fallback is part of this item.

**Item 2 — Biso, high side, a flag and never a cap.**
`BISO_UNUSUALLY_LARGE` at a corpus-calibrated threshold (~25–30 Å²) — furnace
data legitimately runs 8–15 Å², so a cap would break real use. The low side
needs nothing (readers refuse negative B; the transform floors at zero). The
motivating case: a wrong polarization constant once moved a refined Biso by
12σ while Rwp barely moved — magnitude-implausibility was the only visible
symptom.

**Superseded in part, 2026-09-18.** A cap is already there, at 25 Å², which is
the bottom of the range this item wanted for a *flag*. `Atom.biso`'s
`default_factory` has carried `min=0.0, max=25.0` since v0.1 (`f51e8e67`), and
PR #206 (`ce538dd3`, 2026-09-01) made those bounds bind a caller-supplied
`Parameter` too. The cap was escapable before that date and is universal
after it. A Biso that wants 30 Å² is now clamped at 25 and speaks as a
`BOUND_HIT`, in the vocabulary of a parameter that met a limit rather than one
whose value is implausible. So the item is a decision before it is a flag:
whether 25 stays, and what the flag says if it does. `help.py`'s entry quotes a
typical 0.2–2 Å², warns above about 5 Å² for a heavy atom, and names no
ceiling.

**Item 3 — resolution positivity, a guard and not per-parameter bounds.**
U, V, W legitimately go negative individually; the constraint is coupled
(Γ² > 0 over the fitted range), so the right shape is "this resolution
function is not physical in-range", naming the θ where it dips — the Stephens
cone-guard precedent. The motivating case, from PR #115's review:
schema-legal u = 0.05, v = −0.5, w = 0.001 collapse Γ_G to ~1e-4° at 157°,
silently defanging the background-peak width guard until it learned to
abstain.

**Item 4 — the profile-width ceiling says nothing (issue #102).** `profile.w`
and `profile.u` carry `max = 1.0` deg² — roughly 1.0–1.2° FWHM — so a
synchrotron fit can converge into an absurd width with nothing raised.
Diagnostic, not a cap: nanocrystalline lab samples genuinely reach ~1° FWHM,
and WP-1112 removed the old speed argument (a wide peak no longer buys an
unbounded window), so this is about fit quality only. Report the implausible
width; the user decides.

**Item 5 — |ρ| = 1.000 is a flat direction, not a correlation (issue #106's
aside).** `axial_sl ~ axial_hl` at ρ = −1.000 to three decimals with both
free is a rank statement about the data's null space; reporting it in the
same vocabulary as ρ = 0.96 undersells it. Say what it is — the confident
singleton rule one rank up.

**Shared discipline.** Every threshold that is not quoted from a paper is
quoted from a corpus survey and says so (`INDEX_SHIFT_ALLOWANCE`'s precedent:
an assumed number must never look like a measured one). A parameter the
caller bounded keeps the caller's bound. New codes get skill rows and
`help.py`/manual coverage per the standing gates.

**What item 1 reports through, today and next** (folded from § Inherited,
WP-1310, 2026-09-16). Bound findings are no longer accumulated per stage. They
are re-taken from the final guard, so a bound an early stage pressed and a
later one resolved is silent, and `RefinedParameter.at_bound` and the
`BOUND_HIT` diagnostics are set-equal off one test in
`strategy.staged.bound_findings` (`tests/test_bound_hit_at_convergence.py`).
The pending half changes how the reports read. That test asks how near θ is to
the limit, and the distance is a function of the stage's `ftol`. A parameter
1.2e-10 from its bound goes unreported at `ftol` 1e-4, while a binding bound
and an interior optimum differ in gradient by eleven orders.
[1434](1434-the-bound-test-asks-the-wrong-question.md) carries the measurement
and the redesign, and is still ⬜. A threshold survey here should not assume the
current distance test is what will read it.

**A softplus floor is never a bound hit** (folded from § Inherited, the
2026-09-01 triage, issue #204's checked sub-finding).
`internal_bounds(0.0, inf, "softplus")` maps to `(-inf, inf)` in
`params/transforms.py`, so `BOUND_HIT` cannot report "scale went to zero".
That is intended, because the transform enforces positivity and leaves no
bound to hit. It is item 5's business: a scale sitting on its softplus floor
is visible as a flat direction and in no other way.

**Task 1's corpus is outside this repo.** The 606-refinement TOPAS archive is
private and not redistributable (WP-1118 §), and 1130 and 1131 calibrated
their thresholds on it. No path to it is recorded in the repo, so the survey
cannot start until someone says where it lives.

## Non-goals

- **Not width caps** — #144's, already landed with its size extension.
- **Not the cell** — `PHASE_UNCONSTRAINED` + `cell_window` own it.
- **Not background coefficients** (flexibility, not magnitude —
  `background_absorption` owns it), **not the Stephens block** (the cone
  guard owns it; a box bound is the wrong geometry), **not scales,
  occupancies, η** (floors and schema bounds exist).
- **Not the report's delivery shape** —
  [1310](1310-report-repeats-itself.md).

## Tasks

- [ ] Corpus surveys: displacement magnitudes across the 606-`.inp` archive
      and a Biso high-tail estimate; the two defaults recorded with their
      evidence. **Blocked** on being told where the archive is (§ Context).
- [ ] Decide what the two bounds that already exist should be: the ±1 mm on
      `sample_displacement` and the two capillary offsets, and the 25 Å² on
      `Atom.biso`. Keep, move or scale, each with its evidence.
- [ ] Displacement bound scaled by `goniometer_radius_mm` where the instrument
      declares one, with the flat fallback where it does not, through
      `BOUND_HIT`; caller's bound outranks.
- [x] `BISO_UNUSUALLY_LARGE` flag, 2026-09-18 — threshold computed per phase
      from Gilvarry (1956), not a constant; the 25 Å² cap kept and documented
      as the package's own; low side untouched, PR #206 having landed it.
- [x] Resolution-positivity guard (Γ² > 0 in-range, naming the θ) —
      `RESOLUTION_NOT_POSITIVE`, 2026-09-18. The #102 width-implausibility
      diagnostic beside it is still open.
- [ ] Flat-direction report: |ρ| at 1.000 within tolerance emitted as its own
      finding, set-consistent with `unmeasured_rows`/esd handling.
- [ ] Tests per item + skill rows + `help.py`/manual entries + obs/calc/diff
      PNGs to `tests/output/` for any fixture refinement.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_walking_bounds.py   # new module, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: each new signal fires on its motivating configuration (the 11-BM
displacement ride, a 30 Å² Biso, the u/v/w collapse at 157°, a 1° FWHM on a
synchrotron line, the ρ = −1.000 pair) and stays silent on the clean
acceptance suites; no accepted value moves anywhere a signal merely reports.

The shipping PR carries `Closes #150`, `Closes #102` (#106 closes with
[1310](1310-report-repeats-itself.md)).

## References

- Issues #150, #102, #106 (aside) — the rule, the measurements, the ceiling.
- [1073](1073-capillary-displacement.md) — the zero/displacement degeneracy;
  WP-1112 — why the width ceiling is no longer a cost question.
- PR #144 — the cap pattern this extends (arm on contact, speak on fire,
  caller outranks).

## Handover log

- **2026-09-01** — created, from issues #150/#102/#106 (2026-09-01 triage).
  Settled: five items, flags-not-caps everywhere the physics says so; first
  task is the corpus surveys, because two defaults have no number yet.
