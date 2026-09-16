# WP-1311 — bounds and flags for the remaining walking parameters

Milestone: unscheduled · Status: ⬜
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

**Item 2 — Biso, high side, a flag and never a cap.**
`BISO_UNUSUALLY_LARGE` at a corpus-calibrated threshold (~25–30 Å²) — furnace
data legitimately runs 8–15 Å², so a cap would break real use. The low side
needs nothing (readers refuse negative B; the transform floors at zero). The
motivating case: a wrong polarization constant once moved a refined Biso by
12σ while Rwp barely moved — magnitude-implausibility was the only visible
symptom.

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

### Inherited

- **From WP-1310, 2026-09-16: the `BOUND_HIT` machinery item 1 reports
  through has changed once and is about to change again.** Landed: the
  findings are no longer accumulated per stage, they are re-taken from the
  final guard, so a bound an early stage pressed and a later one resolved is
  silent and `RefinedParameter.at_bound` and the diagnostics are now
  set-equal (`tests/test_bound_hit_at_convergence.py`). That is what item 1's
  displacement bound will report through. Pending, and it affects how the
  reports read: the *test* asks how near θ is to the limit, which is a
  function of the stage's `ftol`, so a parameter 1.2e-10 from its bound goes
  unreported at `ftol` 1e-4 while a binding bound and an interior optimum
  differ in gradient by eleven orders. [1434](1434-the-bound-test-asks-the-wrong-question.md)
  carries the measurement and the redesign. Item 1 can land first; its
  threshold survey should not assume the current distance test is what will
  read it.

- **From the 2026-09-01 triage's second batch (issues #204/#209,
  PR #206)**: item 2's premise "the low side needs nothing (readers refuse
  negative B; the transform floors at zero)" holds only once PR #206 lands
  — before it, a caller-supplied `Parameter` silently dropped `Atom.biso`'s
  declared bounds and a refined Biso reached −165 Å² at unchanged Rwp
  (#204). The persisted-document repair and the wider `default_factory`
  audit are [1321](1321-persisted-bounds-repair.md)'s, not this WP's.
- **From the same batch**: `internal_bounds(0.0, inf, "softplus")` maps to
  `(-inf, inf)`, so `BOUND_HIT` can never report "scale went to zero"
  (#204's checked sub-finding; intended — the transform enforces
  positivity, so there is no bound to hit). Relevant to item 5: a scale at
  its softplus floor is visible only as a flat direction, never as a bound
  hit.

- **2026-09-15, from the issue triage (issue #283, PR #289): `Cell`'s six
  parameters declare no bounds at all, and the guard half is in flight.**
  `schemas/structure.py::Cell` holds six bare `Parameter`s (min −inf, max
  +inf, identity), while `Atom.occ`, `Atom.biso` and `ProfileTCHZ.u`/`v`
  declare physical bounds. Not #204's mechanism: there is nothing to
  discard. On a featureless pattern the `profile_only` preset's cell stage
  probes α = β = γ = 180° 3 430 times, and `d_spacings` answers each with
  NaN and a bare `RuntimeWarning`; 445 probes on a 2 %-off start that never
  moved (`converged`, Rwp 1.01, possibly 1336's shape). The returned cell is
  correct in every case. PR #289 (open) ships the *guard* half:
  `DegenerateCellError` by name from `d_spacings`, a `_DegenerateCellGuard`
  in `least_squares` penalising the trial instead of crashing,
  `StageResult.n_degenerate_cell_probes` and a `CELL_DEGENERATE_PROBE` info
  diagnostic. The *bounds* half is this WP's: lengths with a real floor
  above zero and angles in (0, 180), in the idiom `Atom.occ` uses. Two rules
  from root CLAUDE.md apply. A length's identity is not zero, so this is an
  identity transform with a floor and never `softplus, min=0` (the
  `MARCH_R_MIN` lesson). A bound on an angle the setting fixes is harmless,
  because that entry is locked. `params.vector.cell_window` narrows a held
  phase's walk and is suppressed by a caller's own bound, so a declared
  bound changes nothing there. Cells already persisted unbounded are 1321's.
  Decision for the maintainer: whether the bound and #289's penalty both
  land. The bound stops the probes; the guard reports whatever a tie or a
  window still reaches.

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
      evidence.
- [ ] Displacement soft bound scaled by `Geometry.radius`, armed on contact,
      through `BOUND_HIT`; caller's bound outranks.
- [ ] `BISO_UNUSUALLY_LARGE` flag; low side untouched.
- [ ] Resolution-positivity guard (Γ² > 0 in-range, naming the θ), plus the
      #102 width-implausibility diagnostic beside it.
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
