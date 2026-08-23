# WP-1130 — The fit has no reference: a background level it cannot argue with

Milestone: unscheduled · Status: ⬜
Depends on: —

## Goal

An estimate of the background **level**, computed from the pattern alone before
any refinement and sharing no assumption with it, plus the diagnostic that
compares a fitted background against it. The bar is measured, not aspirational:
on the ZrMo₂O₈ 492 K scan every background this package fitted sat at
**0.50–0.71 of an independent code's converged answer** while `Rwp` and `GoF`
matched that code's to two decimals, and a fifteen-minute hand heuristic landed
at 0.82–1.20 of it.

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

## Non-goals

- **Not a better background estimator, and not new knobs.** Finding 6 is the
  fence: the defaults beat everything scanned and three plausible improvements
  each made it worse. Exposing knots and λ to a caller produces confident
  tinkering that reads as reasoning.
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

- [ ] **The anchor selector.** `background.anchors` (or a peer of
      `background.select`): the second-derivative significance test, the basin
      condition, and a smooth physical form through the survivors. Returns the
      anchors, the curve, and a **per-region reliability flag** derived from
      Finding 5's saturation, plus the stated one-sided bias. Window widths are
      arguments with the ±2/±4/±6/±10 sensitivity recorded beside them.
- [ ] **Wire it to the model that already exists.** `BackgroundFixedPlusChebyshev`
      is the anchored background; only the selector was missing. A
      `from_anchors` constructor, and `auto_background(kind="anchored")`.
- [ ] **The diagnostic.** `BACKGROUND_BELOW_ANCHORS` (code, paths, value,
      message per the `GuardFinding` constructor rule), firing per region on the
      fitted background against the anchored estimate, and carried into
      `FitReport.background` beside the existing global numbers. It must state
      the one-sided reading, never a symmetric band.
- [ ] **The phase-broadening check.** Each phase's own contribution against the
      instrument function, which rietx already stores through
      `save_instrument_profile` / `load_instrument_profile`. A phase whose
      broadening exceeds the instrument by a large factor is making a claim
      about the specimen that must be stated. Calibrate the factor; Finding 2's
      cap was binding and is not a calibration.
- [ ] **Re-measure `background_absorption` from a good start**, with and without
      the width columns, and either reinstate or bury the widen-the-target-list
      idea on that evidence rather than on the degenerate optimum's.
- [ ] **Fix `cell_window`.** A window that cannot contain the value is a model to
      refuse where there is a diagnostics channel, not a bound pair to return;
      at minimum it must never return `lo == hi`, and the raise must name the
      path. Check `gauss_size`'s NaN column at the same time.
- [ ] **A background panel for `plot_for_vlm`.** Not "draw the background" — it
      already appears, as a thin line at the bottom of an axis scaled to the
      tallest peak, where Finding 8 measures the error at 2.6–4.9% of panel
      height. The panel is: fitted background **and** the anchored estimate in
      one frame, y cropped to their own range, anchors marked, peak-crowded
      regions shaded. Finding 8's rule is the acceptance test — a panel without
      a reference in it would have shown a smooth decay and been called fine.
- [ ] **A diagnostic names the view that shows it.** `GuardFinding` already
      carries `code`/`paths`/`value`/`message` and every guard `Diagnostic`
      carries `where`; the missing field is which rendered view makes this
      finding legible. An agent then reaches the second channel because it was
      told, not because it guessed. Keep it a pointer, not an embedded image:
      the caller decides whether to spend the tokens.
- [ ] **Measure the round-trip case, since the token case is already decided.**
      Finding 8 prices a *named* question at ~15× against the image. The open
      question is the unnamed one: give an agent a fit and "what is wrong with
      it", with and without the montage, and count calls to answer as well as
      tokens. `tests/eval_report_agent/` and `tests/eval_agent_surface/` carry
      the discipline (register before running, enforce the condition in a shim,
      pre-register the read-out) and neither round pools with this one.
- [ ] **`rietx compare` row** — the standing rule in the root CLAUDE.md, and the
      cumulative Δχ² panel is what localises this to 18–25° in the first place.
- [ ] **`AGENT_PROTOCOL.md` rows.** Rwp and GoF never accept a background;
      a fitted background below the anchors by a large factor names the phase
      widths as first suspect, not the background function; a model-free
      estimate is biased high by construction and is not a reference the
      co-refined answer should match. Plus the **channel rule** from Finding 8:
      numbers for a question you can name (~15× cheaper), an image for one you
      cannot, and never an image without a reference in the frame.
- [ ] Tests (unit for the selector on synthetic anchors with known answers;
      a real-data acceptance if the dataset can be given a home) + obs/calc/diff
      PNGs to `tests/output/`, **including the anchors-against-fit plot**, which
      is the figure that made this legible.

## Acceptance

The anchored estimate reproduces an independent code's converged background
within a stated band on the trigger scan, and the diagnostic fires on the
degenerate fit and stays silent on the capped one.

```sh
.venv/bin/python -m pytest tests/test_background_anchors.py -q
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_fitreport_layers.py -q
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
