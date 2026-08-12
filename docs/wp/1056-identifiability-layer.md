# WP-1056 — Identifiability layer: correlations, soft modes, held-parameter exchangeability

Milestone: v1.0 · Status: ⬜
Depends on: —

## Goal

A `FitReport.identifiability` section carrying parameter-space evidence the report
today has none of: the worst correlations with their paths, the softest modes of
the scaled normal matrix as named parameter combinations, the esd-qualifying
statistics quoted beside each other — and, the highest-ceiling piece, a
**held-parameter exchangeability scan** that makes a *converged* fit say "this
fitted zero is exchangeable with the held sample_displacement", which is the
statement WP-1053's E2 (0/8) and E8 (0/8) rows failed for want of.

## Context

**Why the converged state is the target.** WP-1053's pilot (closed 2026-08-11)
measured that every failed episode failed at a *good* fit: E2 failed 8/8 runs —
the planted displacement never freed, verdict `converged` behind χ²_red ≈ 1.01
(compensated by the fitted zero) — and E8's agents all answered `converged` (8/8)
because the ambiguity
evidence exists only in unconverged-state reports nobody generated. The ranked
follow-up list (1053 memory/report §8, item 4) named a "converged-fit degeneracy
layer" the highest-ceiling fix — the only item addressing E8.

**Machinery that already exists** (nothing here derives new math, it surfaces
computed numbers):

- `run_least_squares` outcome carries the full **correlation matrix**;
  `normal_covariance` (`optimize/statistics.py`) computes Cov = χ²_red·pinv(JᵀJ)
  with the hermitian-eigensolve guard (pinned after a measured ρ = +2.75
  pathology on WP-0502's fluorite fit — every |ρ| ≤ 1 exactly).
- The `HIGH_CORRELATION` guard emits fired pairs; `RefinementResult` carries
  `correlation_warnings` (strings). Fired-or-silent is a verdict; the section
  carries the top-k values as evidence.
- `Statistics` has `esd_inflation` (Bérar-Lelann) and `durbin_watson`.
- The projection mechanic for exchangeability is
  `optimize.statistics.background_absorption` generalised: project a **held**
  parameter's Jacobian column onto the span of the *free* columns; R² → 1 means
  the data cannot distinguish freeing it from what was fitted. The package
  learned once already that pairwise ρ misses block effects (~0.2 pairwise while
  the block absorbs ~46 %) — that lesson is why the scan is a projection, not a
  correlation lookup.

**What the papers add** (both read 2026-08-11, in the local corpus):

- Watkin (2008), J. Appl. Cryst. 41, 491 — corpus `derived/2FSHUYQK/`. §3.8
  eigenvalue filtering: the informative object is the *combination* (soft mode),
  not the pair; his diagnostic signature of high correlation ("large spread of
  values, normal mean") is invisible pairwise. His worked powder-relevant cases:
  scale↔ADP always; occupancy↔ADP because scattering-factor and Debye-Waller
  shapes coincide over a short Q range and *decorrelate only with resolution* —
  identifiability is a property of the sampled range, exactly like the
  template-collinearity finding one layer up. Also: Marquardt λ must be zero at
  the final cycle for honest correlations — worth an assertion that our final
  covariance is undamped.
- Schwarzenbach et al. (1989), Acta Cryst. A45, 63 — corpus `derived/A7LFQSXQ/`.
  Recommendation 8: scaling the covariance by GoF² is "highly questionable";
  the package's stance (χ²_red scaling + Bérar-Lelann, both *reported* so they
  can be divided out) becomes this section's stance — quote the ingredients
  (raw χ²_red, inflation factor, DW) and let the consumer decide what the esds
  mean. Also the **δR normal-probability plot** (Abrahams & Keve 1971), "a more
  powerful descriptor than R", which compresses to two agent-friendly numbers:
  slope and intercept of sorted Δ/σ against normal quantiles.
- Prince, *Mathematical Techniques in Crystallography and Materials Science*
  (3rd ed.) — **read 2026-08-12**, ch. 6–8; location + section map in
  `docs/LITERATURE.md` § Books. Ch. 8 is the textbook statement of both halves
  of this WP. (a) The E2 mechanism, verbatim: a diagonal element of V is the
  correct *marginal* variance even under high correlation, **but** "if the
  Hessian matrix does not contain rows and columns corresponding to all
  variables that have correlations with the variable of interest, the computed
  variance will be too small, and the apparent precision will be illusory" —
  his fig. 8.4 is the no-bias/underestimated-variance picture, and his worked
  example shows dropping even an *insignificant* parameter visibly shrinking
  the survivors' esds. (b) Soft modes: his remedies are "linear combinations of
  parameters that are approximately eigenvectors of the Hessian matrix",
  worthwhile at |ρ| > 0.95 — render the mode as the named combination; the 0.95
  is citable context, never a gate. (c) The significance half of the
  two-condition discriminator has a classical form — the
  constrained-vs-unconstrained F ratio — and Prince's reading of F ≈ 1 ("the
  data do not contain sufficient information to distinguish between the two
  models") is the `ambiguous` verdict in classical words. (d) The Projection
  Matrix section (leverage, idempotency) formally grounds the held-column
  projection mechanic. His 3rd ed. has **no Marquardt/eigenvalue-filtering
  treatment** — the undamped-final-cycle assertion stays cited to Watkin §3.8.

**The discriminator problem the spike must solve (found in planning review,
2026-08-11).** Projection R² of a held column onto the free span is a property
of the **design matrix over the sampled range**, not of the fit: cos θ
(displacement) projects onto the constant (zero) direction at ~0.99 over any
ordinary window — on a *clean* fit too. So raw exchangeability R² would fire on
every report, clean references included, which is exactly the noise the
acceptance forbids. The informative statement needs both halves: the direction
is exchangeable (R² high) **and something significant is riding it** (the
fitted partner — E2's compensating zero at −0.0075° — stands many σ from its
null; a clean fit's zero ≈ 0 makes the exchange vacuous). The E8 soft mode has
the same structure: the mode always exists; what matters is whether the fitted
values along it are significant. The spike below measures E2 *and* the clean
reference to pin the two-condition discriminator before any schema field is
committed.

**Held-parameter scan scope.** Not every held parameter — the aberration and
scale families the Layer-2 template map already names (zero, displacement,
transparency, cell; scale, biso; the instrument-profile terms), plus anything
`mode_fixed`-held that a `ParameterRow` marks refinable-in-principle. Needs the
final Jacobian *plus* columns for held candidates (one extra derivative-column
evaluation per candidate at the converged values — bounded, and frozen-per-stage
discreteness is untouched because nothing is refined).

**The carrier exists (WP-1055, closed 2026-08-12) — extend it, do not build
one.** `RefinementResult.identifiability: Identifiability | None`
(`schemas/results.py`) is additive and defaulted, holding today one field,
`background_absorption: dict[path, R²]`; its class docstring states the shared
reason it exists (J is an N×P array that is never serialized, so anything read
off it is screened at fit time or lost) and names this WP. Put the
correlation/soft-mode summary there as further fields rather than opening a
second result section. Three mechanics to reuse rather than re-derive: it is
filled from `GuardReport.measured_background_absorption`, a
deliberately-not-findings field set inside `check_guards` — **measure once**,
let the threshold decide only which rows become `GuardFinding`s, so the
report's number and the guard's fired bit cannot disagree, the same discipline
a correlation section wants against `HIGH_CORRELATION`; `_run_plan` returns
the **last stage's** guard (the answer-producing one) and `_build_result`
takes it as `guard=`; and `replay` plus joint multi-histogram fits leave the
field `None`, read as "not measured here", never as a clean bill of health.
If a `FitReport` section follows, `report/background.py` is the shape
precedent: a small module whose assessor returns the section, measured
separations in its docstring, and the *predicates* the summary clause and the
Layer-2 emitter share extracted so a sentence and an action cannot disagree.
`THRESHOLDS_VERSION` is now **0.6**, so a further bump is a fresh decision.

**Protocol home (WP-1057, closed 2026-08-12).** AGENT_PROTOCOL §4b ("Declare
the deliverable") exists; its *structure* profile's deciding rows are the
intended home for this WP's exchangeability/soft-mode row — add it there
rather than opening a new section. `FitReport.abstained_kind` is a closed
Literal (a new kind is a minor version).

**Interaction with WP-1003.** The vary-or-tie serialisation question (a held
parameter is *absent* from `result.parameters`) is 1003's freeze decision and is
not decided here; this section reports *about* held parameters by path, which is
legal either way.

## Non-goals

- No autopilot: the section informs; freeing anything stays the caller's move
  (the 1050 no-autopilot fence).
- No change to esd computation or the Bérar-Lelann application.
- No background-specific statistics — WP-1055 (shared carrier only).
- No delivery-timing work — WP-1058.

## Tasks

- [x] **De-risk spike, before any schema work** (user decision 2026-08-11): on
      the E2-shaped fixture at convergence, compute the held-displacement
      column (evaluate-only compile with the candidate freed; FD fallback) and
      its projection R² onto the free span; same on the clean converged
      reference. Record both R² values and the fitted-partner significances in
      this file's handover. Go/no-go: the two-condition discriminator (R² high
      **and** partner significant) separates E2 from the clean reference; if it
      does not, stop and redesign before touching `FitReport`.
- [ ] `FitReport.identifiability` (additive): top-k |ρ| pairs with paths; softest
      mode(s) of the scale-normalised normal matrix as (eigenvalue, loadings)
      rendered as a sentence; raw χ²_red + esd_inflation + durbin_watson quoted
      together; δR slope/intercept.
- [ ] Held-parameter exchangeability scan: projection R² of each held candidate's
      column onto the free span, reported as "fitted X exchangeable with held Y
      (R²=…)"; family list documented and pinned by test.
- [ ] `docs/AGENT_PROTOCOL.md`: how to read exchangeability (an E2-shaped
      answer is "converged, but the zero is exchangeable with a held
      displacement — the data cannot tell you which"), that `ambiguous` is the
      verdict it licenses, and the row added to §4b's structure-profile
      deciding rows (its intended home, per 1057).
- [ ] Tests: E2-shaped fixture (converged, held displacement) produces the
      exchangeability statement naming the pair; E8-shaped short-window fixture
      reports the zero↔cell↔displacement soft mode at convergence; clean
      converged reference stays quiet; δR on a Gaussian-noise fit lands slope≈1,
      intercept≈0 + obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_fitreport_layers.py -q
.venv/bin/python -m ruff check src tests examples
```

(New tests land in `test_fitreport_layers.py` per Tasks; if a separate file is
created, add it here.) The spike's go/no-go is recorded in the handover before
any schema field lands. The E2 fixture's *converged* report names the
zero↔displacement exchange; the clean reference emits no identifiability noise
— which, per the discriminator finding above, raw projection R² alone cannot
deliver, so this acceptance pins the two-condition form (the
confident-wrong-singleton rule applied to uncertainty statements).

## References

- Watkin (2008) J. Appl. Cryst. 41, 491 (corpus `derived/2FSHUYQK/`);
  Schwarzenbach et al. (1989) Acta Cryst. A45, 63 (corpus `derived/A7LFQSXQ/`);
  Abrahams & Keve (1971) Acta Cryst. A27 (δR plot; via Schwarzenbach);
  Bérar & Lelann (1991); Hill & Flack (1987); Andreev (1994) (corpus);
  Prince, *Mathematical Techniques in Crystallography and Materials Science*
  3rd ed., ch. 6–8 (read; location + section map in `docs/LITERATURE.md`
  § Books).
- `optimize/statistics.py` (normal_covariance guard story, background_absorption
  projection mechanic).
- WP-1053 pilot grid (E2/E8 rows) — restated in Context; the WP file holds the
  dated record.

## Handover log

- **2026-08-11** — created, merging the 1053 ranking's "converged-fit degeneracy
  layer" (item 4) with the design review's correlation proposal, grounded in
  Watkin 2008 + Schwarzenbach 1989 (both read). Not started. Gotcha for the
  first session: request the Prince book before designing the soft-mode
  rendering.
- **2026-08-12** — the Prince book arrived and ch. 6–8 are read (location,
  section map and OCR caveats: `docs/LITERATURE.md` § Books); findings folded
  into Context. The first-session gotcha is resolved: design the soft-mode
  rendering against Prince ch. 8, keep the undamped-final-cycle assertion
  cited to Watkin §3.8 (Prince 3rd ed. carries no Marquardt treatment), and
  note the constrained-vs-unconstrained F ratio as the classical form of the
  discriminator's significance half. Still not started.
- **2026-08-12** — session start on branch `wp1056-identifiability-layer`.
  `### Inherited` pruned on arrival: the 1055 entry folded into Context
  verbatim in substance (carrier + the measure-once / last-stage-guard /
  `None`-means-unmeasured mechanics + the `report/background.py` shape
  precedent — carrier class and `THRESHOLDS_VERSION` 0.6 verified in the
  tree); the 1057 entry folded into Context and into the AGENT_PROTOCOL task
  (§4b structure-profile deciding rows as the row's home, `abstained_kind`
  closed Literal), minus its "`THRESHOLDS_VERSION` is 0.5", stale since 1055
  bumped it to 0.6.
- **2026-08-12** — **de-risk spike: GO.** Protocol: the E2 baseline byte for
  byte (`test_e2_sample_displacement_baseline` — displacement planted at
  −0.02 mm, `mccusker_default`, displacement in no stage) and the clean
  reference (same plan from `_truth()`), then at each converged state an
  **evaluate-only** rebuild — final-stage table with the held displacement
  *also* freed, `compile_model` at the converged values (vary flags do not
  enter compilation), analytic Jacobian evaluated once; the candidate's
  peak-chain column agrees with central FD to ~1e-8 rel. Measured (this
  branch's `[dev]` venv, darwin/arm64):

  | | χ²_red | R²(disp \| free span) | fitted zero (B-L esd) | \|z−0\|/esd |
  |---|---|---|---|---|
  | E2 | 1.012 | 0.999945 | −0.010991 ± 8.6e-05 | **127.7** |
  | clean | 1.010 | 0.999945 | +0.000136 ± 8.6e-05 | 1.6 |

  R² is **identical to six decimals on both fits** — the planning review's
  prediction measured: projection R² is a design-matrix property over the
  sampled range and alone would fire on every clean report. The fitted
  partner's significance against its null is the discriminating half:
  127.7σ vs 1.6σ, a margin of ~80×. Partner loadings (lstsq of the held
  column on the free columns, scale-normalised) name the partners:
  zero_shift 1.17, cell.a 0.21, everything else ≈ 0 — so the rendered
  sentence can name *which* fitted parameters ride the exchange. Go for the
  two-condition discriminator (R² high **and** partner significant);
  thresholds are an implementation decision, made with both margins in view.
  Spike PNGs: `tests/output/wp1056_spike_{e2,clean}.png` — both visually at
  the noise floor, indistinguishable from each other, which is E2's point.
