# WP-1311 — bounds and flags for the remaining walking parameters

Milestone: unscheduled · Status: 🔄 2026-09-18 — items 2, 3 and 5 landed;
1 and 4 measured and waiting on one maintainer decision each
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

## Findings

**2026-09-18 — the two open items, measured.** Both thresholds are now
answerable, and neither number was invented. What stopped each is stated with
it.

**Item 1: the ±1 mm bound is loose, and its angular licence is not constant.**
A specimen displacement `s` shifts peaks by Δ2θ = −(2s/R)·cosθ, so a bound
fixed in mm buys a different angular licence on every goniometer. At the
declared ±1 mm, against a typical lab resolution function (u = 0.02,
v = −0.012, w = 0.008):

| R (mm) | 20° | 40° | 60° | 90° | 120° |
|---|---|---|---|---|---|
| 100 | 1.129° | 1.077° | 0.992° | 0.810° | 0.573° |
| 200 | 0.564° | 0.538° | 0.496° | 0.405° | 0.286° |
| 300 | 0.376° | 0.359° | 0.331° | 0.270° | 0.191° |

As a multiple of the local FWHM that is 14.0× at 20° on a 100 mm goniometer,
7.0× on a 200 mm one, and 0.9× at 120° on a 300 mm one. So the bound permits a
displacement worth several line widths everywhere, and the spread across
ordinary radii is 3.0×. Scaling it by `goniometer_radius_mm` fixes the spread
and not the magnitude.

**What stopped it**: both fixes change a schema default that has stood since
v0.2 (`473cc5a7`), which is a user-facing break. The maintainer's ruling on the
same question for `Atom.biso`'s ceiling, taken this session, was keep it and
document it. Applying that precedent here is the cheap answer and it is the
maintainer's to give. `goniometer_radius_mm` is also `float | None`, so a
scaled bound needs the flat fallback decided at the same time.

**Item 4 (#102): the ceiling permits a resolution two orders past the
instrument.** `profile.u` and `profile.w` cap at 1.0 deg², and at that ceiling
the instrumental FWHM is 1.000° flat across a 15–110° scan. Measured against
the instruments that take the data:

| instrument | median instrumental FWHM | ceiling / it |
|---|---|---|
| typical lab Bragg-Brentano | 0.090° | 11.1× |
| typical synchrotron | 0.005° | 194.3× |
| rietx's own default (w = 1e-3) | 0.032° | 31.6× |

That is the issue's complaint quantified: a fit can converge into a resolution
function eleven to nearly two hundred times worse than the goniometer that
measured the pattern, and nothing is raised.

**What stopped it**: the two instrument classes separate by a factor of 18, so
a single absolute threshold would be wrong for one of them, exactly as item 2's
was before it was computed per phase. The relative anchors available are the
fitted span (the ceiling is 1.05 % of it, a lab instrument 0.095 %, a
synchrotron 0.005 %) and the spacing of the lines the function has to resolve.
Neither is quoted from a source, and the corpus route closed when the archive
survey was dropped. Item 2's threshold landed only because Gilvarry (1956)
supplied the physics; nothing equivalent was found for an instrument
resolution ceiling. A successor should either find that source or take the
maintainer's decision on which relative anchor to use.

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

- [x] ~~Corpus surveys across the 606-`.inp` archive~~ — **dropped
      2026-09-18 by maintainer decision**: physics-quoted numbers instead,
      labelled as such (the `INDEX_SHIFT_ALLOWANCE` precedent). Item 2's
      threshold came from Gilvarry (1956) and needed no corpus at all.
- [x] The 25 Å² on `Atom.biso`: **kept and documented** 2026-09-18, on
      measured prior art (FullProf and TOPAS make limits opt-in per parameter;
      neither default-caps a displacement parameter). `help.py` and the `Atom`
      validator docstring now both say the ceiling is this package's own and
      name the escape.
- [ ] The ±1 mm on `sample_displacement` and the two capillary offsets: the
      same decision, still open. § Findings has the measurement.
- [ ] Displacement bound scaled by `goniometer_radius_mm` where the instrument
      declares one, with the flat fallback where it does not, through
      `BOUND_HIT`; caller's bound outranks.
- [x] `BISO_UNUSUALLY_LARGE` flag, 2026-09-18 — threshold computed per phase
      from Gilvarry (1956), not a constant; the 25 Å² cap kept and documented
      as the package's own; low side untouched, PR #206 having landed it.
- [x] Resolution-positivity guard (Γ² > 0 in-range, naming the θ) —
      `RESOLUTION_NOT_POSITIVE`, 2026-09-18. The #102 width-implausibility
      diagnostic beside it is still open.
- [x] Flat-direction report, 2026-09-18 — `FLAT_DIRECTION` beside the pair's
      `HIGH_CORRELATION` rather than instead of it; the bar is the three
      decimals the message prints, so no constant is tuned.
- [x] Tests, skill rows and manual entries **for items 2, 3 and 5**
      (`tests/test_walking_bounds.py`, 21 cases). Items 1 and 4 owe theirs.
      No obs/calc/diff PNGs: nothing here runs a fixture refinement, the
      guards being tested on compiled models rather than on converged fits.

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

### 2026-09-18 — three of the five, and two premises that did not survive

Three of this WP's five walking parameters now speak when they misbehave, and
none of the three thresholds is a number somebody chose. A refinement whose
resolution function has left the physical set says so instead of silently
reporting a resolution four orders finer than any goniometer. A displacement
parameter past the point where its own crystal would have melted is flagged
against a bound computed from that crystal's packing. And a pair the data
cannot separate at all is now reported as the rank statement it is rather than
in the same words as an ordinary strong correlation.

The cost was two of this WP's own premises. Item 2 was written as "a flag and
never a cap" against a 25 Å² cap that already existed and, once measured,
bounds nothing physical. The WP's uncited claim that furnace data legitimately
runs 8–15 Å² is above the melting bound for any ordinary structure. Both are
corrected in place.

**Done.**

- **Item 3, `RESOLUTION_NOT_POSITIVE`.** Γ_G² is a variance, the constraint is
  on the quadratic rather than on U, V and W separately, and nothing checked
  it. `check_hump_width` already met the consequence and abstains, its
  docstring saying the unphysical instrument "is a separate, more fundamental
  defect and not this guard's to name"; this names it.
- **Item 2, `BISO_UNUSUALLY_LARGE`.** Threshold computed per phase from its
  own cell, `B_melt = 8π²ρ²(√2·v)^(2/3)`, three equations from Gilvarry (1956)
  and no fourth. A flag and not a cap because the IUCr round robin asks for
  exactly that warning by name and because Watkin (2008) explains why the
  number is evidence about the model.
- **Item 2's cap decision.** 25 Å² kept and documented rather than widened.
- **Item 5, `FLAT_DIRECTION`.** Beside the pair's `HIGH_CORRELATION`, never
  instead of it.

**Measured.**

- Fast selection **5342 passed, 134 skipped**, against **5327 / 134** with
  `--ignore=tests/test_walking_bounds.py`. The delta is exactly the 21 cases
  added, all passes, no new skip. Full selection **5527 passed, 143 skipped**
  in 29:38. Both `[dev]`, macOS arm64, machine otherwise idle (`ps` checked
  before each). None of the three new diagnostics fires on any acceptance
  fixture.
- `B_melt` at the loosest ratio the source quotes: corundum 4.57, LaB₆ 5.18,
  fluorapatite 5.89, Si 8.09, NaCl 8.72 Å², over 8.5–22.4 Å³ per atom.
  Inverted, 25 Å² needs 109–338 Å³ per atom, five to twenty times any ordinary
  packing.
- Item 3's motivating configuration is worse than this WP described it. The
  quadratic's roots fall at 0.229° and 168.577° 2θ, so Γ_G² is negative at
  **every** point of an ordinary scan and Γ_G is the 1e-4° floor throughout,
  not only at 157°.
- Items 1 and 4 are measured in § Findings above, with what stopped each.

**Gotchas.**

- **Three of this WP's premises were stale on arrival** and the prune commit
  corrects them: `sample_displacement` and the two capillary offsets are
  already bounded at ±1 mm; `Atom.biso` already caps at 25 Å²; and the #283
  note assigning this WP the `Cell`-bounds half of PR #289 is dead, that half
  having landed as `178e6017` and then been removed by `0ae0e063`, with
  `Cell`'s docstring now recording the unbounded state as deliberate.
- **`Geometry.radius` does not exist.** The field is `goniometer_radius_mm`,
  and it is `float | None`, so any geometry-scaled bound needs its flat
  fallback decided at the same time.
- **The cross-stage diagnostic dedup was keyed on the pair alone.** A flat pair
  produces both a `HIGH_CORRELATION` and a `FLAT_DIRECTION`, so one would have
  evicted the other silently. The key is now `(code, pair)`.
- **Two test names collided** and ruff caught it, not pytest. The count looked
  right while one case was silently replacing another.
- **Verify a page number, do not soften it.** Three bib entries were added
  without DOIs; the manual's own gate refused them and sent me to Crossref,
  which confirmed the two page numbers I had removed for being unverifiable
  from the OCR. Gilvarry is Phys. Rev. **102**, 308–316.

**Next**, in order. Both remaining items are blocked on the same kind of
decision and neither is blocked on work.

1. **Item 1 needs the maintainer's ruling**, and it is the ruling already given
   for `Atom.biso` this session: the ±1 mm bound has stood since v0.2, so
   changing or scaling it is a user-facing break. Keep-and-document is the
   consistent answer and costs one commit. § Findings has the numbers.
2. **Item 4 needs a source or a decision.** Its two instrument classes separate
   by 18×, so one absolute threshold is wrong for one of them, and the two
   relative anchors available (the fitted span, the spacing of the lines the
   function must resolve) are not quoted from anything. Find the source, or
   take the decision on which anchor to use.
3. Then the WP closes, carrying `Closes #150` and `Closes #102`.

- **2026-09-01** — created, from issues #150/#102/#106 (2026-09-01 triage).
  Settled: five items, flags-not-caps everywhere the physics says so; first
  task is the corpus surveys, because two defaults have no number yet.
