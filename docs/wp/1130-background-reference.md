# WP-1130 — The fit has no reference: a background level it cannot argue with

Milestone: unscheduled · Status: 🔄 2026-09-04 — two bugs fixed and all three
gaps answered; the trigger no longer reproduces and § Gap C's gate refuses the
selector and the diagnostic, leaving the panel as the deliverable
Depends on: — (nothing; WP-1131 closed 2026-09-02 and the width check this WP
needed had in fact shipped in v1.2 — see § What this reads rather than computes)

## Goal

An estimate of the background **level** computed from the pattern alone, kept
**outside** the fit so it shares no assumption with it, with its bias measured
against a known truth before anything is built on it; and a diagnostic that
reads a fitted background against it with a threshold calibrated from that
bias, never from the trigger scan. The bar is measured, not aspirational: on
the ZrMo₂O₈ 492 K scan every background this package fitted sat at
**0.50–0.71 of an independent code's converged answer** while `Rwp` and `GoF`
matched that code's to two decimals, and a fifteen-minute hand heuristic landed
at 0.82–1.20 of it.

The mechanism that caused the trigger — a visible phase's widths running to
40× the instrument — is
[1131](1131-sample-broadening-is-a-specimen-property.md)'s check, not this
WP's, and this WP depends on it: it is the reference with a physical scale
behind it, and the only thing that tells a nanocrystalline fit from the
trigger.

## Context

### Why this exists

2026-08-23, in conversation, not from a failing test. The maintainer looked at
a four-phase ZrMo₂O₈ fit and said the background was eating peak intensity in
the 18–25° cluster, and that "the shape should be a smoother decay". Three
rounds of measurement followed. **Each round the package's numbers were wrong
and the visual reading was right, and every correction arrived from outside the
package** — the real data file, then TOPAS's own coefficients, then the
maintainer's flat-basin heuristic. Nothing rietx computes participated in any
of the three corrections. That is the finding this WP exists to fix; the
background is the instance.

### What this reads rather than computes

Folded in from [1131](1131-sample-broadening-is-a-specimen-property.md)'s
session, 2026-09-02, and re-checked against the tree on 2026-09-03. Four things
this WP does not have to build.

- **The width check shipped in v1.2**, before 1131 was ever worked, so the
  dependency this file used to declare is discharged and not by 1131:
  `SIZE_UNUSUALLY_SMALL` (apparent crystallite below `refine.SIZE_FLAG_SIZE_A`
  = 50 Å, via Scherrer at the pattern's longest line) and
  `STRAIN_UNUSUALLY_LARGE` (above `refine.STRAIN_FLAG_WIDTH` = 1.5 deg), each
  with a bound twin in `params.vector` (`size_cap` with its 2 nm physics floor,
  `strain_cap` off the fitted range) that arms only on a term already at the
  floor, and rows in `docs/skill/rietx/references/{diagnostics,abstention}.md`.
  Both thresholds are calibrated on the 606-refinement TOPAS archive rather
  than invented. **Every task below that says "defers to 1131's width finding"
  means those two codes.**
- **The conversions are one import, not a hand computation.**
  `model/profiles/caglioti.py` holds both directions of both laws:
  `apparent_size_from_size_coefficient` / `size_coefficient_for_size` (which
  need a λ) and `microstrain_from_strain_coefficient` /
  `strain_coefficient_for_microstrain` (which do not). § Finding 2's
  "`lor_strain` of 10.37 is Δd/d ≈ 9 %" is
  `microstrain_from_strain_coefficient(10.37)` and need not be recomputed by
  hand; state no constant of your own.
- **There is a better input than a coefficient.**
  `RefinementResult.microstructure` / `FitReport.microstructure` carry, per
  phase, the coherent domain size in Å and the Δd/d with esds — or a named
  reason there is none (`at_zero`, `no_wavelength`, `not_measured`) — plus
  `separable`, the width trend's own size/strain separability verdict. A
  background diagnostic that has to tell a nanocrystalline fit from a phase
  that has become a pedestal can read a size with an esd and a separability
  flag rather than a number of degrees. **Read `separable` before quoting
  either number**; over a short 2θ range the two are one parameter.
- **A gotcha if this WP ever touches a joint fit.** A size coefficient is now
  normalised by wavelength across histograms (`params.multi.size_value_scales`),
  so a shared `phases.N.lor_size` is the coefficient at histogram 0's λ and each
  histogram's own structure copy carries a different number. Read the *size*,
  which is one number; the degrees are not. The
  `SIZE_NORMALISED_ACROSS_WAVELENGTHS` diagnostic says so on any fit it applies
  to.

### Superseded in part, 2026-09-03

The findings below were measured 2026-08-23 to 08-27 and are dated claims about
the tree, not standing facts. One has gone stale:

- **`AGENT_PROTOCOL.md` no longer exists as a document.** WP-1304 turned it
  into the agent skill, `docs/skill/rietx/`, and `docs/AGENT_PROTOCOL.md` is a
  pointer kept for one release and deleted at v1.4. So the two tasks below that
  said "an `AGENT_PROTOCOL.md` row" now name their skill destination instead,
  under the root CLAUDE.md § skill rule (WP-1330): a rule that holds for
  **every** fit goes in `SKILL.md`'s body, one that holds for a task shape goes
  in one `references/` file for that shape. A background reference read against
  a fitted background is a per-fit judgement, so it is a `references/` row on
  the diagnostic plus, at most, one body clause.

Re-checked and still true on 2026-09-03: the `cell_window` degeneracy
(§ Bug found on the way — `cell_window("a", -3.0, -inf, inf)` returns
`(-3.0, -3.0)` on this tree), `BACKGROUND_ABSORPTION_GUARD = 0.25` in
`strategy/staged.py`, the three unread `PatternDiagnostics` fields of
§ Finding 7, and `report.background.absorption` / `worst_absorption` as Gap A's
read.

### The trigger dataset

The same episode as WP-1110's E-ZRM: `zrmo2o8_vt.zip` from the Durham TOPAS
workshop, **not committed anywhere in this repo** and not test data. Re-running
means fetching it again from
`http://topas.webspace.durham.ac.uk/wp-content/uploads/sites/261/2026/04/zrmo2o8_vt.zip`.

This WP works **TOPAS range 17 = `read_pattern(scan=16)`**: the `.inp`'s
calibrated list says 492.1 K for that range, the RAW's own setpoint field says
473 K. Four phases from `d8_01612_vt_reel_02.inp`, 14–70° as its `start_X`
declares, CuKα1 with a Ge(111) monochromator (`LP_Factor(!th2_monochromator,
27.26)`).

Two transcription gotchas, both measured here and both silent:

- **TOPAS's TCHZ Lorentzian is `X·tanθ + Y/cosθ`; rietx's is `x/cosθ + y·tanθ`.**
  So `pkx → profile.y` and `pky → profile.x`. Mapping them by letter gives a
  fit that converges to a plausible `Rwp` with the wrong peak shape. The root
  CLAUDE.md already warns that GSAS and FullProf swap the labels; TOPAS does
  too, and this is the first time it has been written down here.
- The `.inp`'s `bkg @` is a **12-coefficient Chebyshev of the first kind over
  `[start_X, finish_X] = [14, 70]`**, and its converged coefficients are the
  external reference every table below quotes.

Reproducing the maintainer's own trial: four phases, cells bounded as the
`.inp` bounds them, Rwp **0.1104** / GoF **1.51** against the trial's 0.1076 /
1.52.

### Finding 1 — every fitted background was about half TOPAS's

Mean background per region, and the ratio to TOPAS's own converged curve:

| | 14–18 | 18–25 | 25–32 | 32–40 | 40–50 | 50–60 | 60–70 |
|---|---|---|---|---|---|---|---|
| TOPAS converged (counts) | 266.8 | 281.3 | 157.0 | 96.8 | 80.3 | 81.5 | 79.9 |
| flat-basin anchored | 319.7 | 230.5 | 160.5 | 115.6 | 86.3 | 76.1 | 85.4 |
| rietx, widths free | 268.2 | 152.3 | 78.1 | 52.8 | 47.6 | 48.2 | 55.1 |
| rietx, widths capped | 329.6 | 270.1 | 168.6 | 94.1 | 80.3 | 79.9 | 74.6 |
| observed 2nd percentile | 282.5 | 226.0 | 136.0 | 82.0 | 72.0 | 72.9 | 68.0 |
| **ratio, anchored/TOPAS** | 1.20 | 0.82 | 1.02 | 1.19 | 1.08 | 0.93 | 1.07 |
| **ratio, widths free/TOPAS** | 1.01 | **0.54** | **0.50** | **0.55** | **0.59** | **0.59** | **0.69** |
| **ratio, widths capped/TOPAS** | 1.24 | 0.96 | 1.07 | 0.97 | 1.00 | 0.98 | 0.93 |

Five background models were fitted (P-spline 3° λ=1 which `auto_background`
picks, P-spline 3° λ=100, P-spline 8° λ=1, Chebyshev 5, Chebyshev 12). Refitting
only background and scales from one converged model so nothing else varies:

| background | Rwp | ⟨bkg⟩ 18–25 |
|---|---|---|
| P-spline 3°, λ=1 (auto) | 0.1105 | 152.3 |
| Chebyshev 5 | 0.1109 | 161.6 |
| P-spline 8°, λ=1 | 0.1113 | 162.5 |
| P-spline 3°, λ=100 | 0.1412 | 166.0 |
| Chebyshev 12 | 0.1085 | 227.7 |

Four agree within 9% **and all four are wrong the same way**. Consensus among
bases sharing one optimum is not evidence, and an early draft of this analysis
took it for evidence.

### Finding 2 — the cause was a phase width, not the background

With `gauss_size` and `lor_strain` unbounded, cubic-ZrMo₂O₈ refined to a
Gaussian FWHM of **5.0°/cosθ** (`gauss_size` 24.93) and a Lorentzian of **6.0°
at 2θ = 60** (`lor_strain` 10.37), against an instrument width of 0.15°. It had
stopped being a phase and become a second background. Beside it:
`sample_displacement` at its −1.0 bound (the `.inp` says −0.2197), `zero_shift`
−0.486 against ±0.5, two Biso at 0.0, and the hydrate carrying `lor_strain`
159.5 at `scale` exactly 0.

At the 26.6° flat basin that fit reads the observed 208 counts as **89
background + 115 Bragg**: 56% of the intensity at a basin, claimed as peak tail.

Capping the sample broadening so a phase contributes at most ≈ 0.5° FWHM at the
pattern end (`gauss_size ≤ 0.168`, `lor_strain ≤ 0.71`) moves the background to
0.96–1.07 of TOPAS and moves Rwp the wrong way, **0.1105 → 0.1173**.
**The cap is binding** — `lor_strain` sits on it in nearly every phase — so the
*direction* is established and the *value* is not calibrated. Calibrating it is
part of the work, not an input to it.

`phase_support` and `cell_window` (WP-1110, WP-1129) protect an **invisible**
phase's *cell*. Nothing protects a **visible** phase's *widths*, and the widths
are the same kind of flat direction one seam over.

### Finding 3 — what counts as a reference, and what does not

A **reference** is an estimate of the same quantity computed by a route that
shares no assumption with the fit, so disagreement is diagnostic rather than
tautological. The test: *if the model were wrong in this way, would the
candidate move too?* Three candidates were built and scored:

| candidate | shares with the fit | verdict |
|---|---|---|
| refit under another basis, diff per region | residual, peak model, optimiser, current point | **not a reference.** All five bases agreed on being 45–50% low |
| departure from a smooth physical form | nothing, but sees only *shape* | **partial.** A background uniformly half what it should be is still smooth, so it passed all four wrong fits |
| flat-basin anchoring | nothing | **a reference.** Counts, Poisson noise, and one premise: the background is locally flat and locally the floor |

The shape test is still worth having and it did catch what the maintainer saw.
RMS departure from the best fit of `c₀ + c₁/2θ + c₂·2θ + c₃·2θ²`, as a fraction
of level: P-spline 8° **2.4%**, P-spline 3° λ=1 **2.6%**, λ=100 **3.2%**,
Chebyshev 5 **3.6%**, Chebyshev 12 **12.8%**. Per region the Chebyshev-12
departure runs −16.5 / **+24.3** / −10.7 / −12.9 counts across 14–18 / 18–25 /
25–32 / 32–40, which is the inflection under the cluster, located and sized.
The second half of the judgement, *and it is where the peaks are*, is the R² of
that departure on the smoothed Bragg profile: 0.014 / 0.097 / 0.164 / 0.076 /
**0.192** in the same order.

### Finding 4 — flatness alone is not the heuristic

The maintainer's description was "a flat basin which looks like it doesn't
contain much peak tail", and **both halves are load-bearing**. Implemented as a
second-derivative significance test alone (local quadratic, Poisson σ,
`savgol_coeffs` giving var = σ²Σh², reject when |y″| or |y′| exceeds 2σ over a
0.6° window), it selects plateaux on top of broad humps and puts the background
**above the observed data in 20.8% of channels** (3.1% above obs + 2σ).

Adding the basin condition — keep a flat run only if no other flat run within
±4° sits significantly below it — gives **16 anchors from 60 flat runs of ≥ 0.1°**,
spanning 32% of channels, and lands on TOPAS. Window-width sensitivity is real
and must be recorded: ±2° / ±4° / ±6° / ±10° give ⟨18–25⟩ of 249 / 231 / 203 /
111, so ±10° collapses (it selects only the pattern's global floor).

### Finding 5 — "flat" and "peak-free" are different measures, and flat is better

Channel fractions per region, flat (0.6°, 2σ on both derivatives) against
peak-free at 2·FWHM from the frozen reflection list:

| | 14–18 | 18–25 | 25–32 | 32–40 | 40–50 | 50–60 | 60–70 | total |
|---|---|---|---|---|---|---|---|---|
| flat | 35% | 10% | 24% | 37% | 37% | 36% | 65% | 37% |
| peak-free at 2 FWHM | 53% | 40% | 30% | 15% | 7% | 3% | 0% | 16% |

They trend **opposite ways** and only 6% of channels are both (31% flat but not
peak-free, 11% peak-free but not flat). Flatness measures the thing that
matters, whether a channel is locally indistinguishable from a baseline given
the noise, so it is the better selector. But it **saturates where nothing is
resolved** — 65% flat at 60–70° where 147 reflections overlap continuously — so
it is necessary and not sufficient, which is exactly why the basin condition
exists. Any diagnostic built on it must carry that caveat, and must say that
the estimate is biased **high** where crowding hides the tails: a fit above the
anchors is definitely wrong, a fit below them may be fine.

### Finding 6 — approaches measured and refuted, so nobody re-proposes them

All on a synthetic built from the real reflection list and the `.inp`'s own
TCHZ widths, with a known background. **The synthetic's own fidelity is the
first refutation**: its peak-to-background contrast was 2.1× too strong at
14–18°, **2.3× too weak at 18–25°** and 2.0× too strong at 50–70°, i.e. wrong
in exactly the region that mattered. Real values for scan 16: 34.8% of the net
Bragg intensity lies in 18–25°, 23.9% above 45°.

- **With correct intensities every basis recovers the truth to ≤ 1.5%**,
  including a 21-term Chebyshev and a 3°-knot spline over a region with zero
  peak-free channels. Overlap alone does not break background estimation.
- **A locally adaptive (visibility-weighted) penalty is worse than uniform** at
  every λ: max bias 4.1% vs 3.6% at λ=1, 15.6% vs 7.4% at λ=10, 36.7% vs 22.4%
  at λ=100. Stiffening a blind region says the curve may not bend, not what
  value it should take; it slides bodily instead.
- **Cutting the low-angle range at 14°, as the `.inp` does, is worse**: −7.4%
  at 14–18° against +0.2% with the full range. The 10–14° points anchor the
  curve's left end.
- **Global stiffening trades one bias for another**: λ ≥ 1e4 costs −9.5% at
  10–14° where the real 1/x curvature is, and −14.5% there even with a perfect
  intensity model. λ = 1, the shipped default, was best of
  {0, 1, 1e2, 1e4, 1e6, 1e8, 1e10}.
- **Peak-window truncation is real and small.** `WINDOW_AREA_TOL = 2e-2`
  discards 1.44% of the Bragg integral as a smooth pedestal, worth 0.4–1.2% of
  the background here. Worth stating as a floor, not a cause.
- **Model-free estimators are biased by construction and the bias tracks
  crowding.** Against a known background: arPLS +4% (10–15°) → +57% (65–70°),
  with λ = 1e7 and 1e9 agreeing to ~1%; SNIP −12 to −18%; the rolling envelope
  −5% → +37%. No λ fixes this; it is definitional.
- **Rwp is anti-informative, not merely uninformative.** Synthetic: 0.0724 /
  0.0730 / 0.0722 for background errors of 4% / 27% / 3508%. Real: the best Rwp
  belonged to the wrong background before capping and to a worse background
  after. Any acceptance rule that reads Rwp will pick the absorbing answer.

One claim from the synthetic **did not survive real data and is withdrawn**: the
Lorentzian width is not the dominant partner in the degeneracy. Per-region R²
on the real converged Jacobian gives scale 0.55→0.98 and Biso 0.49→0.96 against
Lorentzian x/y 0.05→0.52, so `background_absorption`'s existing target list
(`.biso`, `.scale`, `.occ`, `.adp.`) is the right one. That measurement was
taken **at the degenerate optimum**, where the width had already absorbed the
background, so whether the statistic fires from a good start is **unmeasured**
and is a task below.

### Finding 7 — three diagnostics are computed, documented as decision rules, and unread

`PatternDiagnostics.peak_density_per_deg` (2.17/deg on scan 16),
`peak_fraction` (0.269) and `signal_to_background` (11.9) have no consumer.
`docs/manual/using/results.md` states the rule "above roughly 2/deg the pattern
is dense, which favours a stiff baseline and a low background order" and
`background/auto.py` reads neither. This is WP-1076's "a declared name is a
claim" one rank across: the claim here is a documented *decision rule* with no
reader.

Worse, the score that **is** read cannot discriminate.
`amorphous_hump_score` measures **0.047 on a synthetic carrying a real
40-count Gaussian hump and 0.043 on one carrying none**, against a
`HUMP_TRIGGER` of 0.05 — and it is the only input that sets the P-spline knot
spacing. `air_scatter_gain` reads 0.069 on a synthetic containing a genuine
900/(2θ) term, against an `AIR_SCATTER_TRIGGER` of 0.3, because a cubic already
absorbs 1/x over a 60° range.

### Finding 8 — the multimodal channel, measured on this session's own failure

The premise is that the package supplies information and the agent supplies the
reasoning, so **which channel carries the information efficiently is a design
question, not a rendering detail**. This session is the only controlled evidence
there is, and it is a negative followed by a qualified positive.

**Vision did not find the error.** The maintainer's plot was in context from the
first message and the model did not raise the background; the maintainer did.
Once told, the model matched the supplied hypothesis to whichever background sat
highest in the cluster rather than detecting anything. Worse, the one unaided
visual judgement it made was **inverted**: it read a background sitting well
below the inter-peak valleys as sound and one at the valley level as suspect,
when the second was the closest of five to TOPAS (0.75–0.81) and the four
"sound" ones were at 0.50–0.59.

**Vision did find it once, from a purpose-built panel.** On the anchors figure
the model noticed unprompted that the anchored curve traced the data floor while
every fitted background ran ~30 counts beneath it, and that produced the
reversal. Two properties separated that panel from the standard one, and both
are constructible:

| panel | the same error, as a fraction of panel height |
|---|---|
| standard obs/calc/diff, 14–70° | 2.6% |
| standard obs/calc/diff, 18–25° zoom | 4.9% |
| y cropped to the background's own range, reference overlaid | **14.0%** |

More decisive than the scale: **a reference inside the frame**. With only the
fit in frame the eye's sole comparator is its prior, and the prior was wrong. A
uniform factor-of-two in level leaves a smooth monotone decay, which has no
visual signature at all — which is also why the maintainer caught the
Chebyshev-12 *inflection* (a shape defect, visible) and not the *level*. That
read was half right: "underestimates at higher angle" is correct at 0.59–0.69,
"too generous in the 15–30 region" is inverted, since it is 0.50–0.54 there.

**Cost, measured, because the conditional is the whole question.** For a
question already known, numbers are far cheaper: the per-region table carrying
this finding is ~123 tokens against ~1830 for the figure at 1373×1000
(Anthropic vision ≈ w·h/750 after the 1568 px long-edge downscale), a factor of
~15, and rendering costs ~1 s of matplotlib against a numpy pass. **Vision is
not the cheap channel for a question you can name.** Where it earns its tokens
is the question that cannot be named in advance — open-ended "what is wrong with
this fit" — and there the comparison is against the *round trips* an agent
would otherwise spend discovering which statistic to compute, not against the
answer's token count. That comparison is unmeasured and is a task below.

Consequence: a plot is a way of **presenting** a reference, never a substitute
for one, and the surface should say which channel answers which question instead
of leaving an agent to guess.

### Bug found on the way (small, self-contained)

`params.vector.cell_window` returns `lo == hi` for any negative cell value:

```
value= 10.10 -> window=(9.54500, 10.65500)
value= -5.00 -> window=(-5.00000, -5.00000)   DEGENERATE
```

The clamp whose comment says it must "never propose a window that excludes
where the parameter already is" snaps both ends onto `value` once
`value·(1+f) + pad < value`. `scipy.optimize.least_squares` then raises a bare
`ValueError: Each lower bound must be strictly less than each upper bound`
naming nothing. Reached in this session's first pass, before the `.inp`'s cell
bounds were mirrored, when the trigonal cell ran to a = −42.7 Å during a
cumulative stage. Reachable whenever a cell `Parameter` carries no stored
bounds, which is the default. Adjacent to WP-1129.

Separately, `phases.1.gauss_size` returns a degenerate (NaN) R² column at
convergence, so it has no gradient there. Probably sitting at a bound; worth one
look while the above is open.

### Gap A answered, 2026-09-03 — the guard fired, and the trigger is gone

**Protocol.** The model is no longer transcribed. WP-1118's TOPAS reader builds
it: `read_topas_inp` → `to_structure` on `d8_01612_vt_reel_02.inp`, which gives
the four phases, their cells with the file's own `min`/`max`, the sites and
`beq = boverall` = 2.66123. The instrument is still hand-built (1118 has no
`to_instrument` yet): CuKα1, `monochromator_two_theta` 27.26, radius 217.5 mm,
TCHZ from the file with `pkx → profile.y` and `pky → profile.x`,
`sample_displacement` −0.219690422 mm, and `Simple_Axial_Model`'s 6.62303 mm
divided by the radius into `axial_sl`/`axial_hl`. Pattern `read_pattern(scan=16)`,
`two_theta_limits=(14, 70)` as `start_X`/`finish_X` declare — **3887 fitted
channels**. Five cumulative stages: scale+background, cell, aberrations
(displacement, axial, zero shift), displacement (`biso`), widths (`gauss_size`,
`lor_strain`, unbounded — the trigger's own condition, where the `.inp` instead
bounds the *physical* size and strain, `csgc ≥ 30` nm and `slc ≤ 0.1`).

The canonical run — one `boverall` tied across all 42 sites, TOPAS's own
Chebyshev-12 — converges at **Rwp 0.1092 / GoF 1.48**, against this WP's
recorded reproduction of 0.1104 / 1.51 and the maintainer's trial 0.1076 / 1.52.
The protocol is the same protocol.

**The literal question: `BACKGROUND_ABSORPTION` fired.** In all nine runs below,
every time above `BACKGROUND_ABSORPTION_GUARD` = 0.25. The canonical run's whole
table is three rows — `phases.1.scale` **0.442**, `phases.2.scale` 0.260,
`phases.3.scale` 0.050 — and `worst_absorption_path` is `phases.1.scale`. Free
the displacement parameters per atom instead of tying them and the worst becomes
a `phases.1.atoms.*.biso` at **0.75–0.76**, which is §4b's QPA row exactly: the
background reproducing three quarters of a displacement parameter.

So **Gap A's own conditional resolves the way it feared**. The premise "nothing
rietx computes participated in any of the three corrections" narrows to
§ Finding 7's pattern — a diagnostic computed, correct, above its threshold, and
unread — and the first deliverable is the row that tells a reader what to do
with it, not a new estimator. It is also the third instance in this file of one
shape: a number that is right and reaches nobody (Finding 7), a number that
reads as silence (the NaN above), and now a *finding* that fired and was not
looked at.

**And the trigger fit no longer reproduces.** Mean background per region as a
ratio to TOPAS's converged Chebyshev-12, the same seven regions as § Finding 1:

| protocol | 14-18 | 18-25 | 25-32 | 32-40 | 40-50 | 50-60 | 60-70 | Rwp |
|---|---|---|---|---|---|---|---|---|
| **§ Finding 1, widths free (2026-08)** | 1.01 | **0.54** | **0.50** | **0.55** | **0.59** | **0.59** | **0.69** | 0.1105 |
| boverall, Chebyshev-12 | 1.17 | 1.02 | 1.01 | 0.94 | 0.99 | 0.95 | 0.92 | 0.1092 |
| one Biso per phase | 1.17 | 1.01 | 1.01 | 0.95 | 0.99 | 0.94 | 0.91 | 0.1082 |
| Biso free per atom | 1.16 | 1.05 | 1.03 | 0.94 | 1.03 | 0.98 | 0.94 | 0.1071 |
| cells started at the `.inp`'s `min` | 1.17 | 1.02 | 1.01 | 0.94 | 0.99 | 0.95 | 0.92 | 0.1092 |
| cold: generic scales and `beq` too | 1.17 | 1.01 | 1.01 | 0.95 | 0.99 | 0.94 | 0.91 | 0.1082 |
| no axial model | 1.17 | 1.03 | 1.02 | 0.95 | 0.99 | 0.95 | 0.92 | 0.1094 |
| no axial model, Biso free | 1.18 | 1.09 | 1.12 | 1.03 | 1.13 | 1.10 | 1.02 | 0.1146 |
| **`auto_background` P-spline** (Finding 1's own row) | 1.22 | 0.93 | 1.02 | 0.93 | 0.96 | 0.93 | 0.90 | 0.1164 |
| P-spline, Biso free per atom | 1.22 | 0.98 | 1.17 | 1.09 | 1.18 | 1.19 | 1.08 | 0.1435 |

Nine protocols, spanning **both** background bases Finding 1 used (its own second
table puts the auto P-spline at 152.3 and Chebyshev-12 at 227.7 in 18–25°, so the
basis had to be varied before any claim of non-reproduction), three treatments of
the displacement parameters, warm and cold starts, and the axial model present and
absent. Every one lands in **0.90–1.22**. None reaches 0.50–0.71. The width
runaway does not recur either: the largest `lor_strain` anywhere above is **1.22**
against § Finding 2's **10.37**, and no `gauss_size` exceeds 0.702 against 24.93.

**One part of Finding 2 is provably prevented, and it is not the important part.**
`PHASE_UNCONSTRAINED` (WP-1301, which shipped after these findings were measured)
fires on phase 0 in every run and holds its free structural paths, so "the hydrate
carrying `lor_strain` 159.5 at `scale` exactly 0" cannot happen now. The **cubic**
phase's runaway is the one that moved the background, and nothing here explains
its absence: that phase is supported, so no hold applies to it, and the width caps
would not have bitten — `strain_cap(14, 70)` is **79.98**, eight times Finding 2's
10.37. Left unresolved and recorded as such: this file says the runaway is gone,
not why.

**What that does to the WP.** The anchored estimate was to be judged against
TOPAS at 0.82–1.20 (§ Finding 1) and the fit now occupies **0.90–1.22** — the
same band. Measured here for the first time on the *real* scan rather than the
synthetic, the two model-free estimators sit either side of it: arPLS λ=1e7 at
**1.09–1.26**, SNIP at **0.80–1.05**. So `BACKGROUND_BELOW_ANCHORS` has, on this
scan and on this tree, **no separation left to fire on**: § Gap C's gate
("if the anchors' high bias in crowded regions is not separable from a factor-2
deficit at the widths the trigger had") has lost the factor-2 deficit that was
the whole signal. Read § Gap C, § The anchor selector and § The diagnostic in
that light before building any of them — the honest next step may be the 🛑 that
gate already provides for, with the panel and this record as the deliverable.

**Two things this run says about neighbouring work.** The `.inp` the WP names as
its protocol source **cannot be read as it ships**: `read_topas_inp` refuses
`d8_01612_vt_reel_02.inp`, `_reel_01.inp` and `_vt_02.inp` at their first `#if`
(only `d8_01612_fit_01.inp`, a different range, reads), so every number above is
from a copy with the `#if`/`#endif` blocks stripped in the scratchpad. That is
WP-1118's, not this WP's, and the refusal is correct — it is the reach that is
narrow. And the reader reports `TOPAS_FEATURES_NOT_IMPORTED` for LT-ZrMo₂O₈'s
`spherical_harmonics_hkl` strain broadening, which rietx has no equivalent for;
that phase is the one carrying `worst_absorption` in seven of the nine runs.

Figures, `tests/output/` (gitignored, so re-run the scratchpad script):
`wp1130_zrmo2o8_scan16_fit.png` and `wp1130_zrmo2o8_scan16_background.png`, the
second being § Finding 8's panel — background only, y cropped to its own range,
TOPAS's region means and both model-free estimators in the frame.

### Gap B answered, 2026-09-04 — the missing model is named, and freeing it is not a fix

**The protocol matches, and the channel count is not the mismatch.** The file is
4168 points, 10.0000–70.0423°, step 0.014409°. TOPAS's `start_X 14 finish_X 70`
with `x_calculation_step = Yobs_dx_at(Xo)` selects **3887** observed channels;
`two_theta_limits=(14, 70)` gives rietx **3887**. The RAW carries no esd column
(`DataRef.has_sigma` false), so `PatternData.sig()` is √max(y, 1) and the weight
is 1/y — TOPAS's own default, with the file's minimum count 58, far from where
the max(y, 1) floor would differ. Both sums are over the same channels with the
same weights, so an Rwp comparison here is admissible. § Gap B's premise that a
protocol mismatch might explain the gap is **refuted**: there is none in the two
places it could hide.

**Where the residual sits.** On the canonical run (Rwp 0.1092, χ² 8460 over 3887
channels, 2.176 per channel):

| region | 14-18 | 18-25 | 25-32 | 32-40 | 40-50 | 50-60 | 60-70 |
|---|---|---|---|---|---|---|---|
| χ² share | 0.040 | **0.264** | **0.263** | 0.108 | 0.136 | 0.098 | 0.091 |
| χ²_red | 1.23 | 4.60 | 4.58 | 1.64 | 1.65 | 1.20 | 1.11 |
| local Rwp | 0.0581 | 0.1039 | 0.1373 | 0.1151 | 0.1214 | 0.1063 | 0.1102 |

Layer 0's peak clusters localise it further: **29.71–31.02°** carries 13.7 % of
χ² at local Rwp 0.195, and **20.84–21.83°** another 9.9 % at 0.135. Read the
reflection table over those two windows and they are **98.7 %** and **90.4 %**
LT-ZrMo₂O₈ by I_calc.

**The missing model, named.** LT-ZrMo₂O₈ is the one phase whose `.inp` block
carries `spherical_harmonics_hkl` — TOPAS's *hkl-dependent* strain broadening —
and `read_topas_inp` says so at import, `TOPAS_FEATURES_NOT_IMPORTED` naming
`preferred orientation (spherical_harmonics_hkl)` and `peak profile (gauss_fwhm,
lor_fwhm)` on that phase. rietx has the equivalent physics: Stephens (1999)
anisotropic strain, `Phase.microstrain`, six Laue-allowed coefficients under
`Pmn21`. So this is a *transcription* gap, not a capability gap — and it is the
one § Gap B asked to name.

**Freeing it improves Rwp by 20 % and costs two phases.** Seeding the block
isotropically at 100 ppm and freeing `phases.1.microstrain.dof.*` inside the
sample-broadening stage (never after it — the block locks `lor_strain`, and the
run confirms it: that path comes back `refinable=False`, "structurally fixed by
symmetry or by the model"):

| | Rwp | GoF | χ² | free | χ² 29.71-31.02 | χ² 20.84-21.83 |
|---|---|---|---|---|---|---|
| no Stephens | 0.1092 | 1.48 | 8460 | 186 | 1170 | 838 |
| Stephens on LT | **0.0878** | 1.19 | 5465 | 190 | 228 | 154 |

Δχ² = 2995 for +4 net free parameters at N = 3887 → **ΔBIC = −2962**. By the
model-selection test the skill prescribes, the block is overwhelmingly
justified, and 79–82 % of both problem regions goes away.

**And `PHASE_UNCONSTRAINED` fires on two of the four phases, which were
supported without it.** `StageResult.held` for the widths stage grows from
phase 0's five paths to *twelve*: `phases.2.cell.a`, `phases.2.lor_strain`,
`phases.2.gauss_size`, `phases.3.cell.a`, `phases.3.cell.c`,
`phases.3.lor_strain`, `phases.3.gauss_size` join it, and the result carries
three `PHASE_UNCONSTRAINED` findings where the fit without the block carries
one. Six hkl-dependent coefficients on the majority phase are enough to imitate
the minority phases' lines, so the better Rwp is bought by making half the phase
set unmeasurable. **ΔBIC cannot see that and the guard can** — which is § 4's
rule about Rwp, one rank up and reproduced live: the fit that looks better is
the one where two of the four answers stopped being measurements.

**What this says about this WP, which is the point.** The background barely
moves. Ratio to TOPAS's converged curve, the same seven regions:

| | 14-18 | 18-25 | 25-32 | 32-40 | 40-50 | 50-60 | 60-70 |
|---|---|---|---|---|---|---|---|
| no Stephens | 1.17 | 1.02 | 1.01 | 0.94 | 0.99 | 0.95 | 0.92 |
| Stephens on LT | 1.15 | 1.02 | 1.01 | 0.95 | 0.98 | 0.95 | 0.92 |

The single largest defect in the fit — 35 % of its χ², a genuine and correctly
diagnosed *phase width* error of exactly the kind § Finding 2 blames — is worth
**≤ 2 % of the background level**. So the widths ⇄ background coupling
§ Finding 2 asserts is **not generic**: it needed the runaway, not merely a
width error. A width wrong enough to own a third of χ² does not move the
background at all.

`BACKGROUND_ABSORPTION` on `phases.1.scale` is likewise **invariant** across the
pair, 0.442 against 0.437, while `phases.2.scale` falls 0.260 → 0.077 (that
phase having just lost its support). A statistic that does not move when χ²
falls by a third is measuring the geometry of the problem rather than the
current misfit, which is what § Finding 6's "measured at the degenerate optimum,
so whether it fires from a good start is unmeasured" left open. It fires from a
good start, at the same value.

Fenced, per § Gap B's own instruction to record a missing model rather than
build one: nothing here proposes wiring Stephens in by default, and the
`.inp`'s spherical-harmonic coefficients are *fixed* in the file
(`!ahkl_c00` … `!ahkl_c44p`, taken from range 22), so a reader that imported
them would import a held model, not a refinable one. Its home is WP-1118.

### Gap C answered, 2026-09-04 — the gate closes: 🛑 on the diagnostic

**The synthetic is corrected, and this time it passes its own fidelity check.**
§ Finding 6's synthetic was 2.3× too weak in 18–25°, the region that mattered.
This one is built from the converged fit's *own* `y_calc − y_background`, so the
net Bragg distribution is the real one by construction: **34.7 %** in 18–25°
against the real 34.8 %, **23.2 %** above 45° against 23.9 %. A known analytic
background (900/2θ + 60 + 40·exp(−(2θ−14)/12), spanning 73.2–164.2 counts) is
added and the sum sampled from a Poisson. Truth is known channel by channel.

**Bias against that truth, by region:**

| estimator | 14-18 | 18-25 | 25-32 | 32-40 | 40-50 | 50-60 | 60-70 |
|---|---|---|---|---|---|---|---|
| arPLS λ=1e7 | 1.063 | 1.177 | 1.308 | 1.217 | 1.230 | 1.323 | 1.204 |
| arPLS λ=1e9 | 1.072 | 1.166 | 1.245 | 1.208 | 1.246 | 1.313 | 1.206 |
| SNIP | 0.864 | 0.943 | 0.992 | 0.910 | 0.921 | 0.964 | 0.859 |
| flat-basin anchors ±2° | 1.003 | 1.084 | 1.082 | 1.086 | 1.151 | 1.174 | 1.158 |
| flat-basin anchors ±4° | 1.025 | 1.058 | 1.084 | 1.085 | 1.067 | 1.085 | 1.143 |
| flat-basin anchors ±6° | 1.026 | 1.057 | 1.078 | 1.075 | 1.057 | 1.078 | 1.141 |
| flat-basin anchors ±10° | **−1.480** | **0.267** | 1.244 | 1.246 | 1.024 | 1.061 | 1.148 |

Signs and magnitudes confirm § Finding 6 on better evidence: arPLS biased high
everywhere (+6 to +32 % here against its +4 → +57 % on the old synthetic), SNIP
low everywhere (−14 to −4 % against −12 to −18 %), and the two arPLS λ agree to
5 %, not the 1 % claimed. The **window sensitivity is not a trend but a cliff**:
±2/±4/±6 are stable and ±10 collapses, returning a *negative* background at low
angle, because past that width no anchor survives there and the Chebyshev
extrapolates. Recorded as the WP asked, with the correction that the number to
report is where it breaks, not a slope.

**But the deciding number is coverage, not bias.** Anchors per region on the
synthetic at ±4°: 20/278, **1/486**, 15/485, 46/556, 35/694, 58/694, 173/694.
In 18–25° — the region the whole WP is about — the estimate rests on **one
channel in 486**, and its "+5.8 % bias" is a property of the Chebyshev's
stiffness rather than a measurement of the floor.

**On the two bundled patterns the selector produces nothing at all.**

| pattern | channels | peak density | anchors found |
|---|---|---|---|
| `FAP.XRA` (dense lab, CuKα doublet), Rwp 0.0902 | 5750 | 2.97 /deg | **0** at ±2.3°, ±5.7° and ±11.5° |
| `11BM_NAC.fxye` (synchrotron), Rwp 0.1299 | 59 498 | 26.19 /deg | 274 / **19** / **19** |

Zero on the dense pattern this WP itself nominated as the CI comparator, at
every window. Nineteen of 59 498 on 11-BM, where the curve through them diverges
by four to seven orders of magnitude. The selector works on one of the three
patterns tried, and on that one it is blind exactly where the question is asked.

**The obvious fallback is refuted too, and this is what closes the gate.** Since
arPLS is biased high everywhere and SNIP low everywhere, the tempting move is to
stop estimating a level and quote the **bracket** [SNIP, arPLS] — no new
estimator, no new knobs, both already in `background/estimators.py`, and a band
rather than a singleton is this package's own rule. Measured over **8 Poisson
realisations of the known truth**, the bracket contains it in all seven regions
in **4 of 8**. It fails in 25–32°, where SNIP's bias crosses zero and its floor
reaches 1.012. Used as a threshold on that floor:

| | 14-18 | 18-25 | 25-32 | 32-40 | 40-50 | 50-60 | 60-70 |
|---|---|---|---|---|---|---|---|
| § Finding 1's trigger (ratio to TOPAS) | 1.01 | 0.54 | 0.50 | 0.55 | 0.59 | 0.59 | 0.69 |
| SNIP floor over 8 seeds | 0.895 | 0.963 | 1.012 | 0.927 | 0.943 | 0.966 | 0.900 |
| **trigger fires?** | no | yes | yes | yes | yes | yes | yes |
| the fit on this tree (Gap A) | 1.17 | 1.02 | 1.01 | 0.94 | 0.99 | 0.95 | 0.92 |
| **good fit fires?** | no | no | **yes** | no | no | **yes** | no |

It catches the trigger in 6 regions of 7 — and fires on a *correct* fit in 2 of
7. That is § Fault 1's concrete false positive, arriving from the estimator's
own bias rather than from a nanocrystalline specimen, and no threshold moves it:
the floor is above 1 in the region where the false positive lands.

**Verdict — the gate is met and it says stop.** § Gap C's own words: "if the
anchors' high bias in crowded regions is not separable from a factor-2 deficit
at the widths the trigger had, the diagnostic is 🛑 on that evidence, and this
WP's deliverable is the panel plus the record." Two things are now true and
either alone is sufficient. The factor-2 deficit no longer occurs at all
(§ Gap A, nine protocols at 0.90–1.22), so there is nothing left to separate
*from*. And no model-free estimate measured here separates a correct fit from a
bad one without false positives: the anchors have no coverage where it matters
and none at all on two of three patterns, and the bracket flags a good fit in
two regions of seven.

So **`BACKGROUND_BELOW_ANCHORS` and `background.anchors` are 🛑**, on measured
evidence, and the tasks below are marked accordingly. What survives is the
panel, the record, and the two things already landed — the guard that fires and
now says how to read itself, and the NaN that used to silence it.

Figure: `tests/output/wp1130_gap_c_anchor_coverage.png` (gitignored; the
scratchpad script rebuilds it) — the synthetic with its known truth, the three
estimates over it, and below them the anchor count per region, which is the
panel that makes the gate legible in one look.

### Both fixed, 2026-09-03 — and the second one is the WP's own theme

`cell_window` now refuses a value no cell can take, naming the path. The
boundary is stated where the confusion is: a *positive* length under
`CELL_MIN_LENGTH_A` keeps its window and travels, because a short cell is a
model to refuse where there is a diagnostics channel; a length ≤ 0, or an angle
outside (0°, 180°), is not a short cell but not a cell at all — the metric
tensor is singular or indefinite there — so it raises with the path in the
message instead of reaching scipy as a degenerate pair. The postcondition
"never returns `lo >= hi`" is asserted in the function and swept in the tests
over both branches, which is what the original case-by-case tests could not
catch: the failing value sat outside the range anyone thought to write a case
for.

**The NaN R² was not about `gauss_size` at all**, and the look was worth
taking. `gauss_size` is not among `background_absorption`'s targets
(`.biso`, `.scale`, `.occ`, `.adp.`), so the NaN could not have been that
statistic's own reading of it — but the same run showed why it did not matter
which column carried the NaN. Measured on this tree, before the fix: **one
non-finite entry anywhere in the Jacobian's background block or in a target
column makes every `background_absorption` R² `nan`** — `np.any` does not
filter it out, NaN being truthy, so `_span_basis`' zero-column filter passes it
straight into the QR. And `nan > BACKGROUND_ABSORPTION_GUARD` is `False`, so
`BACKGROUND_ABSORPTION` **never fires**, while
`FitReport.background.worst_absorption` reports `nan` rather than a number.

That is the exact inverse of the failure the zero-column filter was written
for. A zero column *saturates* the guard, R² = 1.00 for every target, which is
loud and was found. A NaN column *silences* it, on the fit most likely to need
it — a fit with a degenerate column is a fit whose background is absorbing
something — and nothing anywhere says so. It is § Finding 7's shape one rank
down: not a diagnostic computed and unread, but a diagnostic computed to a
value that reads as "silent" and cannot be told from one.

`block_projection_r2` now **withholds rather than reports**: a non-finite block
or nuisance column returns `{}`, since the span it belonged to is unknowable,
and a non-finite target column is skipped exactly as a zero-norm one is.
Absence is a state every consumer already handles; `nan` is a number that
compares `False` against everything. A NaN column is deliberately *not* dropped
from the span the way a zero one is — a zero column demonstrably spans nothing,
a NaN column spans something unknown, and dropping it would narrow the span and
understate every R² built on it, which is again the silencing direction.

**Left unfixed and named here**: `one_parameter_gains` shares `_span_basis` and
has the same exposure — a non-finite column gives `nan` gains, which compare
`False` against every threshold, so a Layer-1 suggestion goes missing silently.
It is a different statistic with a different consumer and was not this task; the
`_span_basis` docstring now states the contract and says which caller enforces
it.

### The 2026-08-27 review — four design faults and three evidence gaps

The first draft of this plan was reviewed against the code before any of it
was built. The findings above stand; the plan built on them did not, in four
places, and it rested on three measurements nobody had taken.

**Fault 1 — the reference is an upper bound, and the draft's diagnostic fired
on the side it cannot condemn.** Finding 5 says the anchors are biased *high*
where crowding hides the tails: a fit above them is definitely wrong, a fit
below them may be fine. The trigger is a fit *below* them, so
`BACKGROUND_BELOW_ANCHORS` has to separate "a factor of 2 low" from "the
anchors sit 20–50 % high because every basin is on an overlap". That is a
threshold, and the draft named none and calibrated on one scan; the window
sensitivity (249 / 231 / 203 / 111 counts at ±2 / 4 / 6 / 10°, against TOPAS's
281) shows the slack is the size of the signal at the wrong width, and ±4° was
chosen looking at TOPAS. The concrete false positive is a genuinely
nanocrystalline or low-symmetry specimen: broad peaks leave no basin at the
true floor, the anchors sit high, and a *correct* fit reads as below them. A
width check against the instrument fires on the same specimen for the same
reason. Neither tells the two apart; a physical bound on the width does
(1131's conversions: the trigger's `lor_strain` of 10.37 is Δd/d ≈ 9 %, which
no crystalline solid has), and that is why this WP now depends on 1131.

**Fault 2 — wiring the anchors into the fit removed their independence.** The
draft's second task was `BackgroundFixedPlusChebyshev.from_anchors` and
`auto_background(kind="anchored")`. By Finding 3's own test the estimate then
shares the fit's assumption and stops being a reference; the diagnostic
comparing fit against anchors becomes tautological for that kind; it fixes a
biased-high curve exactly where it is most biased, subtracting Bragg intensity
from the crowded region; and it is a new estimator with new knobs, which the
Non-goals rule out. Dropped. The reference stays outside the fit.

**Fault 3 — the anchored estimate was never measured against a truth.** arPLS
and SNIP were scored against a *known* synthetic background (+4 → +57 %, −12 to
−18 %). The anchors were scored only against TOPAS's converged Chebyshev-12,
which is a co-refined fit under TOPAS's own widths — Finding 1 calls agreement
among fits non-evidence, and the draft then used one fit as the reference for
another. Finding 6's first bullet says a synthetic with correct intensities
recovers the truth under every basis, so that synthetic exists or can be
built; the anchor selector's bias curve is measured there beside arPLS and
SNIP before anything is built on it, and 0.82–1.20 is retired as a number
about truth.

**Fault 4 — the priority was inverted.** The failure mechanism is Finding 2,
and a width check with a physical scale would have fired at the moment it
happened, needs no new estimator, and has a truth behind it (a standard,
measured on the instrument). The draft made it the fourth task of this WP and
declared no dependency on the WP that owns the conversion it needs. It is now
1131's; the background reference is the second-line detector for the case the
width check does not reach — scales and Biso absorbing the background while
every width is sane — and it does not lead.

**Gap A — whether `BACKGROUND_ABSORPTION` fired on the trigger fit is not
recorded.** The guard is `BACKGROUND_ABSORPTION_GUARD = 0.25`
(`strategy/staged.py`), and Finding 6 quotes R² for the scale of 0.55–0.98 on
the converged Jacobian. If it fired and was not read, the premise "nothing
rietx computes participated" narrows to Finding 7's pattern — a diagnostic
declared and unread — and the first deliverable is the protocol row, not a new
estimator.

**Gap B — what the capped fit still misfits.** Capped, rietx reaches Rwp
0.1173 with the background now at 0.96–1.07 of TOPAS, against TOPAS's 0.1076
with the same background. The cap moved the misfit; it did not remove it.
Something TOPAS models on this instrument and rietx does not — or a protocol
mismatch in what the two Rwp sums include (the root CLAUDE.md's channel-count
rule) — is the open question, and a width bound that only relocates a misfit
is not a fix.

**Gap C — the acceptance had no executable form.** The dataset is not in the
repo, its licence is unstated, and the synthetic was 2.3× wrong in the region
that matters. The acceptance below therefore runs on a corrected synthetic and
the bundled patterns in CI, and on the trigger scan by hand, recorded in the
handover.

**Scope.** The draft's twelve tasks were three WPs. "A diagnostic names the
view that shows it" and the round-trip eval are surface-design questions, now
[1133](1133-diagnostic-names-its-view.md); the width check is 1131's; the
`cell_window` fix is one independent commit.

## Non-goals

- **Not a better background estimator, and not new knobs.** Finding 6 is the
  fence: the defaults beat everything scanned and three plausible improvements
  each made it worse. Exposing knots and λ to a caller produces confident
  tinkering that reads as reasoning.
- **Not an anchored background *model*.** The anchors never enter a fit — no
  `from_anchors`, no `auto_background(kind="anchored")`. Fault 2 above is why:
  a reference inside the fit is not a reference.
- **Not the width check.** A phase whose broadening is physically implausible
  is [1131](1131-sample-broadening-is-a-specimen-property.md)'s finding,
  bounded in size and strain rather than in degrees, and this WP reads it
  rather than computing a second one.
- **Not the channel rule, the view pointer on `Diagnostic`, or the round-trip
  eval.** Finding 8 is the record; the work is
  [1133](1133-diagnostic-names-its-view.md).
- **Not the physical background** (Compton and air scatter computed from
  composition, which removes parameters instead of penalising them). It is the
  only direction that adds information to a single pattern and it is v2-sized.
- **Not the series/joint background.** Across the reel the peak density falls
  2.35 → 1.30 per degree while the background varies smoothly with T, so
  regions crowded at scan 0 are open at scan 60. That is the natural successor
  and it needs this WP's reference first, to know which single-pattern answer it
  is improving on.
- **Not FPA, not the peaks buffer.** Fenced at v2 already.

## Tasks

Ordered: the three gaps are answered before the selector is written, because
each can change what is built — Gap A may make the protocol row the first
deliverable, Gap B may name a missing model the widths were standing in for,
and Gap C decides whether the diagnostic is buildable at all.

- [x] **Fix `cell_window`** — independent of everything below and of 1131;
      land it first as its own commit. `params.vector.cell_window` returns
      `lo == hi` for any negative value (the closing clamp `min(lo, value)`,
      `max(hi, value)` snaps both ends onto it), and scipy then raises a bare
      `ValueError` naming nothing. It must never return a degenerate pair, and
      the raise must name the path; a cell below the floor is a model to refuse
      where there is a diagnostics channel. Check `phases.1.gauss_size`'s NaN
      R² column at the same time.
- [x] **Gap A: re-run the trigger fit and record what fired.** Fetch the scan
      (§ The trigger dataset; `pkx → y`, `pky → x`), refine as Finding 1 did,
      and read `result.diagnostics` and `report.background.absorption`. Record
      the answer in this file. If `BACKGROUND_ABSORPTION` fired, its
      row in `docs/skill/rietx/references/diagnostics.md` gains the sentence
      "a phase width can be the absorber, and the R² names the victim, not the
      cause".
- [x] **Gap B: adopt TOPAS's protocol and localise the residual misfit.** Check
      the channel count and what each Rwp sum includes; then, on the capped
      fit, the cumulative Δχ² by region against the widths-free fit (the
      `rietx compare` panel's shape). Name what the widths were absorbing, or
      the protocol mismatch, in this file. A model TOPAS has and rietx lacks is
      a finding to record and fence, not to build here.
- [x] **Gap C: the anchor selector's bias curve against a known truth.**
      Rebuild Finding 6's synthetic with the real net Bragg distribution (34.8 %
      of it in 18–25°, 23.9 % above 45°) so it passes the fidelity check the
      first one failed, then score flat-basin anchoring beside arPLS and SNIP
      per region. Add one bundled dense pattern (`FAP.XRA`) and one sparse one
      (`11BM_NAC.fxye`) with their converged backgrounds as the comparators.
      **Gate**: if the anchors' high bias in crowded regions is not separable
      from a factor-2 deficit at the widths the trigger had, the diagnostic is
      🛑 on that evidence, and this WP's deliverable is the panel plus the
      record.
- [🛑] **The anchor selector.** Refused by § Gap C's gate, 2026-09-04: zero
      anchors on `FAP.XRA` at every window, 19 of 59 498 on `11BM_NAC.fxye`, and
      1 of 486 in the one region that matters on the synthetic. Was to be:
      `background.anchors` (a peer of
      `background.select`): the second-derivative significance test, the basin
      condition, and a smooth physical form through the survivors. Returns the
      anchors, the curve, a **per-region reliability flag** derived from
      Finding 5's saturation, and the stated one-sided bias. The basin window
      is derived from the pattern (a multiple of the instrument FWHM, or of
      `PatternDiagnostics.peak_density_per_deg`), never a bare degree count,
      with the ±2/±4/±6/±10 sensitivity recorded beside the derivation.
- [🛑] **The diagnostic.** Refused with the selector it reads. The
      [SNIP, arPLS] bracket, the only model-free alternative measured, holds the
      known truth in 4 of 8 noise realisations and fires on a correct fit in 2
      regions of 7. Was to be: `BACKGROUND_BELOW_ANCHORS` (code, paths, value,
      message per the `GuardFinding` constructor rule), per region, threshold
      taken from Gap C's bias curve and never from the trigger. It states the
      one-sided reading, and it **defers to 1131's width finding**: with a
      physically implausible width present it names the widths as the first
      suspect; with every width plausible it names the scale/Biso absorption
      case. Carried into `FitReport.background` beside the existing numbers.
      Its stated false positive is the nanocrystalline fit, and a fixture for
      that (broad peaks, correct background) is in the tests as the case that
      must stay silent.
- [x] **Re-measure `background_absorption` from a good start** — done in
      § Gap B: it fires from a good start at 0.442, and at 0.437 after a change
      that removes 35 % of χ², so it is measuring the geometry of the problem
      rather than the current misfit. The widen-the-target-list idea stays
      **buried**: the widths never ran away in nine protocols, so there is no
      evidence for widening and § Finding 6's withdrawal stands.
- [ ] **A background panel for `plot_for_vlm`** — after § Gap C this is the WP's
      **main remaining deliverable**, and its reference has changed. Not "draw
      the background": it already appears, as a thin line at the bottom of an
      axis scaled to the tallest peak, where § Finding 8 measures the error at
      2.6–4.9 % of panel height. The panel is: fitted background in one frame
      with y cropped to its own range, peak-crowded regions shaded, and **a
      reference band rather than an anchored curve** — SNIP below and arPLS
      above, both already in `background/estimators.py`, whose measured biases
      (§ Gap C) are what the band means. The distinction that makes this legal
      after the 🛑: a band good enough to *show* is not good enough to *fire*
      on, since a reader compares while a guard thresholds, and § Gap C's
      refutation is a refutation of the threshold. Label the band with its
      measured bias so it is never read as a truth. § Finding 8's rule is the
      acceptance test — a panel without a reference in it would have shown a
      smooth decay and been called fine — and § Gap C's own last line names the
      panel as what survives.
- [🛑] **`rietx compare` row** — the root CLAUDE.md's rule is "add a row
      whenever a new **correction** lands", and after § Gap C none does. Nothing
      to compare. (The cumulative Δχ² panel's *shape* was still what localised
      this to 18–25°, and § Gap B did that reading by hand.)
- [ ] **Agent-skill rows** (not `AGENT_PROTOCOL.md`, which WP-1304 replaced).
      One landed with § Gap A — `BACKGROUND_ABSORPTION`'s row now says the R²
      names the victim and not the cause, and to read the width codes first.
      Two remain, both now *without* a diagnostic behind them, so both are body
      or `references/` prose rather than a code row: Rwp and GoF never accept a
      background; and **a model-free estimate is biased by construction, in a
      direction that is known per estimator and a magnitude that is not**, so it
      is a bracket to look at and never a reference the co-refined answer should
      match — with § Gap C's numbers as the evidence. The channel rule is
      1133's.
- [ ] Tests. The selector's unit tests go with the selector (🛑). What is left
      is worth having on its own: the **corrected synthetic** of § Gap C is the
      first fixture in this repo with a *known* background and the real net
      Bragg distribution, and it pins the two shipped estimators' bias signs
      (arPLS high, SNIP low) which nothing currently asserts. Plus obs/calc/diff
      PNGs to `tests/output/` and the background panel above.

## Acceptance

**Rewritten 2026-09-04, after the three gaps.** The original acceptance was
written for a diagnostic § Gap C has since refused, and a WP does not keep an
acceptance for work it has decided not to do. What is asked now: the three gaps
carry their answers in this file (done); the corrected synthetic pins the two
shipped estimators' bias signs; and the background panel puts a reference in the
frame, judged by looking, per § Finding 8.

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_fitreport_layers.py tests/test_absent_phase.py tests/test_background_peaks.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

Quote the fast counts with venv and platform per the root CLAUDE.md § Numbers,
and put them in this file's handover entry.

## References

- **McCusker, Von Dreele, Cox, Louër & Scardi (1999)**, *J. Appl. Cryst.* **32**,
  36 — §3 background contribution (for a complex pattern "the majority of the
  peaks are not resolved to the baseline, so the estimation of the background is
  difficult", and the estimate "usually has to be re-estimated and re-subtracted
  several times during a refinement"); §12.1 the remedy list; §6 that scale,
  occupancy and thermal parameters are the ones sensitive to the background.
  Held: `derived/YWSBLSIS/`.
- **Hill & Cranswick (1994)**, *J. Appl. Cryst.* **27**, 802 — Rietveld round
  robin II: "insufficiently flexible peak-shape and/or background functions" is
  the first of six factors associated with lower accuracy, and peak truncation
  the third. Held: `derived/W94DIGGF/`.
- **Baek, Park, Ahn & Choo (2015)**, *Analyst* **140**, 250 (arPLS) and **Ryan
  et al. (1988)**, *Nucl. Instrum. Meth.* **B34**, 396 (SNIP) — the estimators
  Finding 6 measures the bias of. Already cited in `background/estimators.py`.
- **Savitzky & Golay (1964)**, *Anal. Chem.* **36**, 1627 — the local polynomial
  whose derivative variance the flatness test uses.
- **TOPAS-Academic**, `d8_01612_vt_reel_02.inp` — the external reference, papers
  only per the licensing fence; the `bkg` coefficients are data from the
  maintainer's own refinement, not ported code.

## Handover log

### 2026-09-04 — the trigger is gone, and the diagnostic is refused

**What this means.** This WP was opened because a four-phase fit put its
background at half of what TOPAS found, and the plan was to build an
independent estimate of the background level so a fit could be argued with.
That premise no longer holds. Rebuilt from the control file rather than
transcribed by hand, the same fit on today's package lands within 10-22 % of
TOPAS's background under **nine** different protocols, and the phase-width
runaway that caused the deficit does not recur — the largest strain coefficient
is 1.22 where it was 10.37. So there is no factor-of-two error left to detect.
The estimator that was to detect it was then built and measured anyway, against
a synthetic with a genuinely known background, and it **fails**: on the bundled
fluorapatite pattern it finds no anchors at all, on 11-BM it finds 19 in 59 498,
and on the one pattern where it works it has a single anchor in the 486 channels
of the region the whole WP is about. The obvious fallback — quote a band between
the two estimators that already ship, since one is biased high and the other low
— was also measured and also fails: it flags a *correct* fit in two regions of
seven. The WP's own gate says this outcome is a 🛑, so the diagnostic and the
selector are stopped on evidence rather than deferred.

What the session did deliver is smaller and real. The guard that should have
caught this in the first place, `BACKGROUND_ABSORPTION`, **did** fire — every
run, above its threshold — and nobody had looked. It now carries a row saying
how to read it. A latent bug meant one non-finite number anywhere in the
Jacobian silenced that guard completely while reporting nothing; that is fixed.
And a cell parameter no crystal can have used to reach the solver as a
degenerate bound pair and raise an error naming nothing; that is fixed too.

**Done.** Five commits. (1) The mailbox pruned and one stale finding corrected —
`AGENT_PROTOCOL.md` has been the agent skill since WP-1304, so the two tasks
that were to add rows there now name `docs/skill/rietx/`. (2) `cell_window`
refuses a length ≤ 0 or an angle outside (0°, 180°) **naming the path**, keeps
its existing treatment of a positive short cell, and asserts its own
"never returns `lo >= hi`" postcondition, swept over both branches;
`block_projection_r2` **withholds** on a non-finite column instead of returning
`nan`. (3) Gap A. (4) Gap B. (5) Gap C. Two skill entries: the
`BACKGROUND_ABSORPTION` row, and `surprises.md` 8.21.

**Measured.** All on this worktree's own `.venv`, `[dev]` only (no jax, no
torch), darwin/arm64, nothing else mid-suite (`pgrep` clean).

- Fast suite `-m "not slow"`: **4230 passed, 122 skipped**, ~3:11. Three tests
  were added this session (two in `test_absent_phase.py`, one in
  `test_background_peaks.py`), all passes, no new skip. No local pre-baseline
  was taken — the ladder says CI owns that.
- The trigger scan, rebuilt: 3887 fitted channels, **Rwp 0.1092 / GoF 1.48**
  against this file's recorded 0.1104 / 1.51 and the maintainer's TOPAS trial
  0.1076 / 1.52. Nine protocols, background 0.90-1.22 of TOPAS, never 0.50-0.71.
- `BACKGROUND_ABSORPTION` fired in all nine, 0.44 on a phase scale with the
  displacement parameters tied, 0.75-0.76 on a displacement parameter with them
  free. Guard 0.25.
- Stephens on the majority phase: Rwp 0.1092 → 0.0878, χ² 8460 → 5465 for +4
  net free parameters, ΔBIC −2962 — and `PHASE_UNCONSTRAINED` on two of four
  phases that were supported without it.
- Gap C's synthetic: net Bragg 34.7 % in 18-25° (real 34.8 %), 23.2 % above 45°
  (real 23.9 %). arPLS +6 to +32 %, SNIP −14 to −4 %, anchors +2.5 to +14.3 %
  but with 1 anchor in 486 channels where it matters.

**Gotchas for the successor.**

- **The dataset is not in the repo and the reader cannot open it as it ships.**
  Fetch `zrmo2o8_vt.zip` (§ The trigger dataset), then strip the `#if`/`#endif`
  blocks from `d8_01612_vt_reel_02.inp` before `read_topas_inp` — three of the
  archive's four `.inp`s refuse at their first `#if`. Filed into WP-1118.
- **`Instrument` still has to be hand-built**; WP-1118 has no `to_instrument`.
  The `pkx → profile.y`, `pky → profile.x` crossing this file warns about is
  real and silent.
- **`StageSpec.strain_seed` does not take `None`** — omit the field rather than
  passing it, or pydantic refuses.
- Figures land in `tests/output/` (gitignored): the fit, the background panel
  with references in frame, and the Gap C anchor-coverage panel.

**Next, in order.**

1. **Decide whether this WP closes 🛑 or continues for the panel.** That is the
   one open question and it is the maintainer's. Everything the WP set out to
   build is refused; what is left is one view and two paragraphs of prose. A
   defensible reading is that the panel belongs to
   [1133](1133-diagnostic-names-its-view.md) — which now depends on this WP for
   an argument rather than for an estimator (its `### Inherited` says so) — and
   that 1130 closes 🛑 with its record.
2. **If it continues**: the panel is specified in the tasks, with a labelled
   band rather than a curve, and the rule that licenses it — a reference good
   enough to show is not good enough to fire on.
3. **Not this WP's, but found by it and worth someone's time**: `one_parameter_gains`
   shares the NaN exposure that was fixed in `block_projection_r2`, so a Layer-1
   suggestion can go missing silently. Named in `_span_basis`' docstring.
4. **Unresolved and stated as such**: nothing here explains why the *cubic*
   phase's width runaway does not recur. `PHASE_UNCONSTRAINED` accounts for the
   hydrate's arm only, and `strain_cap(14, 70)` is 79.98 against the recorded
   10.37, so neither guard would have bitten.


### 2026-08-27 — the plan reviewed against the code, and restructured

**What this means.** The findings of 2026-08-23 stand and the WP keeps its
thesis: a background number computed from the fit cannot disagree with the
fit, so the package needs one from outside it. But the plan built on those
findings would have shipped the least reliable of the three possible references
first, wired it into the fit in a way that removed its independence, and left
the mechanism that caused the failure as a fourth bullet. The width check now
lives with the conversions it needs (1131), the channel-rule work has its own
WP (1133), and this WP answers three unmeasured questions before it writes a
line of the selector — the most consequential being whether
`BACKGROUND_ABSORPTION` already fired on the trigger fit and went unread.

*Done* — this file's Goal, Non-goals, Tasks and Acceptance rewritten; the
review recorded as § The 2026-08-27 review; `Depends on` set to 1131;
[1133](1133-diagnostic-names-its-view.md) created; 1131 given the width-check
task and an Inherited note; ROADMAP rows synced. Nothing landed in `src/`.

*Not measured* — every number in this file is from the 2026-08-23 session;
this one read code and changed the plan.

*Next* — the `cell_window` commit, then Gap A, since its answer may make the
protocol row the first real deliverable.

### 2026-08-23 — opened from a conversation, not a test

**What this means.** The package cannot currently tell a user that its
background is half what it should be, because every number it reports is
computed from the fit and agrees with the fit by construction. On the trigger
scan the fit statistics matched TOPAS's to two decimals (Rwp 0.1105/GoF 1.51
against the maintainer's 0.1076/1.52) while a phase had turned into a 6°
Lorentzian pedestal and the background had sunk to half its true level. What
was missing was not a better algorithm but a **reference**: an estimate of the
same quantity derived by a route sharing no assumption with the fit, so that
disagreement means something. The maintainer's flat-basin heuristic is such a
reference, it costs one pass over the pattern, and it recovers TOPAS's answer to
0.82–1.20 across seven regions. Building it, and the diagnostic that reads it,
is this WP.

*Done* — nothing landed in the tree; this session was measurement and this file
is its record. The scripts are session-local and not committed.

*Measured* — Findings 1–8 above, plus the `cell_window` degeneracy. The numbers
that decide the design: 0.50–0.71 (every fitted background against TOPAS),
0.82–1.20 (the heuristic against TOPAS), 0.96–1.07 (the fit once the widths are
capped), 0.1105 → 0.1173 (Rwp moving the wrong way as the background becomes
right), 20.8% (channels where flatness-alone puts the background above the
data), 6% (channels that are both flat and peak-free), 2.6/4.9/14.0% (the same
background error as a fraction of panel height in three plot designs), ~15×
(the token cost of the figure against the table that carries the same finding).

*The multimodal question, asked directly and answered honestly* — Finding 8 is
this session grading itself, and it is a negative. The model had the
maintainer's plot in context from the first message and did not raise the
background; when told, it matched the supplied hypothesis rather than detecting
anything; and its one unaided visual judgement was inverted, reading the
closest-to-TOPAS background as the offender and the four that were half-wrong as
sound. It found the real error only from a panel that cropped the axis to the
background's own range **and** carried a reference curve. The design conclusion
is not "add vision" but "a plot presents a reference and never replaces one",
and the token measurement says the numbers win outright for any question that
can be named in advance.

*Gotchas for the next session* — the trigger dataset is not in the repo and must
be re-fetched; TOPAS's TCHZ `pkx`/`pky` map to rietx's `y`/`x` and not by
letter; the ±0.5° broadening cap in Finding 2 is **binding**, so it establishes
a direction and not a value; the per-region R² in Finding 6 was taken at the
degenerate optimum and a statistic evaluated at the bad answer does not flag the
bad answer.

*Next* — the anchor selector, because every other task reads it: the diagnostic,
the `plot_for_vlm` panel and the protocol's channel rule all need something to
compare against. Then the phase-broadening check, which would have caught this
session's failure at the moment it happened rather than three rounds later.
