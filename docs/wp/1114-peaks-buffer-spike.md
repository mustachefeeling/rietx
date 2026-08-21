# WP-1114 — peaks-buffer spike: shape reuse across 2θ (spike, then decide)

Milestone: v1.1 · Status: ⬜
Depends on: 1112 (batching changes the denominator this spike is judged against)

## Goal

Decide, **with measurements rather than reasoning**, whether rietx should
compute a small number of peak *shapes* across the 2θ range and reuse them —
TOPAS's peaks buffer, its single biggest forward-model asymmetry against this
package — under an accuracy tolerance that is recorded, never silent. The
deliverable is a recorded go/no-go plus the measured shape-count/accuracy
trade; the production rewrite, if any, is a follow-on WP. This is the only
identified route to TOPAS-class *cold* multi-phase fits (the milestone's
stretch metric).

## Context

From WP-1113 (2026-08-21), the *other* factor's state, so this spike's
go/no-go can price the whole product: the evaluation count's mechanism is
named (ftol-bound Gauss-Newton tails on near-degenerate directions — its
§ Findings) and the count is already attackable by a landed, opt-in knob:
every intermediate stage at `Stage.ftol = 1e-6` cuts whole-plan evaluations
**1.5-1.7×** at ≤ 0.02 esd on cpd-1a/cpd-2/trigger.  The presets are
deliberately unflipped.  If this spike and 1115 still miss the cold target,
the preset flip is the cheapest remaining multiplier — but it moves every
fit's path, so it takes the 1111 harness equivalence bar across all seven
cases, never a spot check.  Also inherited: `examples/stage_trajectory.py`
reads any case × stage trajectory off the event stream (`--solver lm`
included), which is the cheap way to check a spike's prototype did not
change *where* a stage stops, not only how fast it gets there.

From WP-1112 (2026-08-21), the denominator this spike is judged against:
bases build and accumulation are batched (bucket layout; symmetric rows
bit-identical) and windows are sized by `forward.WINDOW_AREA_TOL = 2e-2`, so
the trigger's Jacobian is ~36 ms/call and the cold fit 28.25-28.85 s (was
50 s at 1111's baseline — re-measure your own before/after on the harness,
never against remembered numbers). Three of its measurements bear directly
on this spike's premise:

- Even after the window shrink, **Σ window points = 34.6 × n_points on the
  trigger** (was 114×): the dense-pattern overlap cost is structural, and
  per-window evaluation cannot remove it — only shape reuse can.
- The batched kernel runs at **~11 ns/element**, so what remains is
  arithmetic *volume*, not dispatch — exactly what a peaks buffer removes;
  1112 already took the dispatch win this spike must not double-count.
- The area criterion's Lorentzian-tail accounting (k ≈ η/(π·tol),
  `window_fwhm_mult`'s docstring) is the same mathematics a buffer's
  interpolation/tail tolerance needs; state the spike's accuracy bound in
  the same discarded-area currency so the two compose rather than stack.

- **What TOPAS does** (Coelho 2018, §5.1, in the paper's own words): "The
  peaks buffer results in a small number of peaks being calculated across the
  whole 2θ range of a diffraction pattern", with convolution direct for
  narrow peaks and FFT for wide ones. rietx instead evaluates every (line,
  reflection) exactly on its own window — 212 520 `_reflection_profile`
  calls in the 17.5 s QPA-acceptance `cpd-2` fit (1109's 2026-08-20 review).
  If a pattern needs ~30 shapes where rietx computes ~500 profiles per
  evaluation, no amount of vectorising the 500 reaches the 30.
- **The evidence shapes vary slowly is already measured** (WP-0605's file,
  restated here because the protocol forbids reading closed WPs): counting
  distinct `(2θ, S/L, H/L, n_nodes)` FCJ argument tuples per stage, 91–97 %
  of node-generation calls in position-static stages were exact repeats of
  ~192 unique tuples; and TCHZ Γ(θ), η(θ) are smooth low-order functions of
  θ by construction (`profiles/pseudovoigt.py::tch_gamma_eta`). What is
  *not* yet measured is the question that decides everything: **how many
  buffer anchors does a required accuracy demand** — shapes at neighbouring
  anchors differ by (ΔΓ, Δη, ΔFCJ-geometry), so the anchor spacing follows
  from a stated interpolation error bound, and nobody here has computed it.
- **The accuracy criterion is integrated area and Rietveld-relevant moments,
  not visual overlap** — the same correction 1112 made to window truncation:
  a shape error that preserves area but shifts apparent position by a
  fraction of an esd is the thing to bound, because cells and zero ride on
  positions. Target tolerances to sweep: 1e-3 and 1e-4 relative, on area and
  on first/second moments of the interpolated vs exact shape.
- **The invariant story is compatible, and must be kept so.** The buffer
  grid (anchor positions, per-anchor node sets) is computed at stage compile
  and frozen — the same class as windows and node counts (CLAUDE.md
  invariant 1); anchor *shapes* follow the parameters smoothly between
  recompiles. Interpolation must be smooth in θ and in the profile
  parameters or the analytic-Jacobian claim breaks — state the
  differentiability argument in the design before prototyping.
- **The honesty contract**: rietx's brand is that a number is exact or its
  deviation is recorded (CLAUDE.md, passim). A landed buffer is therefore
  (a) tolerance-parameterised with the constant and its formula in one
  place, (b) its effect measured against the exact path on the acceptance
  suites, and (c) reported — a provenance field or diagnostic naming the
  mode and tolerance, per "a new correction ships with a record field".
  Whether it becomes default-on or opt-in is decided *from the measurement
  with the user*, not assumed by this WP.
- **Prototype discipline is WP-0605's**: scratch example, shipped path
  untouched, measured against 1111's harness cases, go/no-go recorded here
  with the numbers. 0605's forward-batching no-go does not pre-judge this —
  batching kept all 500 evaluations and made each cheaper; the buffer
  removes most of them, a different axis entirely.

## Non-goals

The production implementation (a follow-on WP if go); FFT convolution and
the full Fundamental Parameters Approach (v2-fenced — FPA is in ROADMAP's
v2+ list; this WP is about *reusing* the existing TCHZ/FCJ shapes, not about
new physics); touching Le Bail/Pawley partitioning; any accuracy target
looser than 1e-3 without the user in the loop.

## Findings

All numbers: `examples/bench_peaks_buffer.py` on this worktree's `[dev]`
venv, darwin/arm64, 2026-08-21 (`--dense 257 --delta 1001`); each case
measured at its cold-start state **and** its converged state (the trigger's
"converged" is the truth model that generated its data).

**1. Volume decomposition — where a buffer can and cannot win.**  Profile
elements per pattern point in one forward evaluation (window points ×
frozen FCJ images, summed over (line, reflection) pairs):

| study | pairs | win/pts | elem/pts | elem/win |
|---|---|---|---|---|
| nac start / converged | 140 | 4.2 / 4.1 | 4.2 / 4.1 | 1.00 |
| cpd-1a start / converged | 222 | 2.8 / 7.7 | 2.8 / 7.7 | 1.00 |
| cpd-2 start / converged | 308 | 3.8 / 11.8 | 3.8 / 11.8 | 1.00 |
| trigger start / truth | 1188 | 34.6 / 40.6 | 269.3 / 367.1 | 7.79 / 9.03 |

The FCJ image multiplier (7.8-9×) exists only on the trigger; the symmetric
cases evaluate 3-12 elements per point in total.  So shape reuse is an
FCJ-and-dense-overlap lever — exactly the milestone's cold multi-phase
target — and worth at most the exp→spline-eval ratio on the lab cases.

**2. Anchors vs accuracy — the central curve**
(`tests/output/wp1114_anchor_curve.png`).  Reconstructing a dense set of
exact shapes from K anchors, worst deviation over the range on relative
area, first moment (in FWHM units) and relative central second moment:

- Scheme is decisive, placement second, stretching third: a C² cubic spline
  through anchor shapes converges ~h⁴ where linear blending's h² never
  reaches 1e-4 by K = 64; error-driven greedy placement (start at 4, bisect
  the worst-probed segment — the loop a production compile would run)
  beats both uniform-θ and equal-shape-motion quantiles everywhere.
- **cubic/greedy meets 1e-3 at K ≤ 16 and 1e-4 at K ≤ 32 on every case and
  every state** (nac 8, cpd-1a/cpd-2 16→32 start→converged, trigger 24/32
  at 1e-4).  Anchors are per distinct phase-width set and shared across
  emission lines (Γ, η, FCJ geometry are functions of position alone).
- Width-stretching (evaluating anchors in FWHM-normalised coordinates with
  the true Γ(θ), η(θ) — two cheap scalars per reflection) is worth ~40× at
  fixed K on the lab cases when blending linearly, but under a cubic spline
  it is mostly subsumed; under FCJ it is irrelevant (Γ varies ×1.08 while
  the FCJ extent varies ×500).
- **The shape family is not everywhere smooth, and the buffer design must
  own that**: at the cpd converged states the fitted Caglioti quadratic goes
  negative mid-range and `_MIN_GAMMA_G2` clamps Γ_G ≈ 1e-4° across
  2θ ≈ 92-134° (measured: corundum converges to U = 0.0037, V = −0.0126,
  W = 0.0089, pure-Lorentzian mid-range, η → 1.000).  The two clamp
  boundaries are C¹ kinks in shape-vs-θ; every fixed placement plateaus at
  ~3-5e-4 there and only greedy bisection (or an analytic domain split at
  the quadratic's roots, which a production compile gets for free) restores
  the tolerance.

**3. Prototype, evaluation level** (`--part proto`; the design-note buffer
at tol 1e-4, trigger and cpd-2 start states).  Accuracy holds through the
full pipeline: cpd-2 rows deviate ≤ 2.4e-5 from the shipped planes, the
whole-pattern forward ≤ 1e-5 of the peak; on the trigger the buffered rows
sit ≤ 8e-5 (m1, FWHM units) from a 128-image reference on exactly the rows
where buffered-vs-shipped disagree most — where the *shipped* rows sit
3.3e-3 away, because the shipped path deliberately skips sub-threshold FCJ
tails (`SKIP_EXTENT_FWHM_RATIO`).  The buffer is more accurate than the
shipped path there, not less.  Three 1e-3-class accuracy traps were found
and fixed on the way, each a rule for any future implementation: a 4-tap
resample of *raw* samples is O(h³) — prefilter (Unser) so the same taps
evaluate the C² interpolating spline; the stored step must key to Γ/16,
because the O(h⁴) constant lives in σ = Γ/2.355 units and the flank carries
f⁗ ~ 10²/σ⁴; and an anchor must never take the sub-threshold FCJ skip
(node count 0) — its rows keep their small asymmetry, and the spline smears
the family discontinuity into every neighbour (measured 1.0e-3 FWHM of m1
against 1.2e-5 with the node count floored).

Wall clock is where the premise fails on this substrate.  Forward, ms/eval
(min-max over 5): trigger scalar 17.1-17.8 / **batched exact 7.5-7.8** /
buffered 11.7-11.9; cpd-2 scalar 2.8-3.0 / batched exact 0.8 / buffered
5.2-5.3.  Bases: trigger shipped 18.6-19.3 / buffered 21.2-30.1; cpd-2
shipped 1.1-1.2 / buffered 7.2-7.8.  Two readings:

- **The residual still runs the scalar per-reflection loop, and batching
  it 1112-style is bit-exact and worth 2.2-3.6×** (17.1→7.5 ms trigger,
  2.9→0.8 ms cpd-2) — the cheapest production win this spike surfaced,
  opened as WP-1120.
- The buffer's 7.8-9× element-volume advantage does not cash out against
  the batched exact path: batched pV runs at ~8-11 ns/element while the
  buffer's gathers run at ~0.8 ns but carry their own multipliers (7
  planes vs 4, 4 taps, ~2× `w_max` padding, the θ-spline evaluated over
  the stored grid), landing at ≈ parity on the trigger bases and a 7-10×
  *loss* on the symmetric lab cases, whose element volume (3-12 per
  point) never had room for a win.  The remaining levers (width-bucketed
  padding, span-restricted spline evaluation) are each ≤ 2× and bounded
  by the measured gather floor.

**4. Prototype, fit level** (`--part fit`; full protocols, buffer
substituted for `phase_component` + `derivative_bases`; deterministic —
two runs bit-identical on every number below):

| case | exact fit | buffered fit | value dev (median / worst) | esd dev (median / rows > 5 %) |
|---|---|---|---|---|
| cpd-2 (QPA acceptance, 9 stages) | 8.35-8.36 s | 19.5-19.9 s | 0.018 / 0.215 esd | 3.2 % / 21 rows |
| trigger (cold, FCJ) | 28.5-28.8 s | 25.5-26.2 s | 0.0020 / 0.107 esd | 0.07 % / 1 row |

Both fits converge (trigger Rwp identical to 5 digits; cpd-2 0.13290 vs
0.13266 — the buffered fit stops marginally lower).  **Every esd row over
5 %, on both cases, is a width-decomposition parameter** (u/w/x/y,
`gauss_*`, `lor_*`) **with esd/|value| between 7e2 and 3e9** — directions
the data does not measure, whose esd is a covariance-cutoff artifact in
the exact fit too; `instrument.profile.x` and `phases.*.lor_size` even
share an *exactly* flat combination (both enter Γ_L as (x + lor_size)/cosθ).
The measured parameters move ≤ 0.02 esd in the median.  The milestone
reading: the buffer buys **~10 % on the trigger cold fit** and costs
~2.4× on the lab protocol.

A cache lesson worth keeping (it cost this spike a non-deterministic
afternoon): the prototype keyed its per-stage buffers by `id(CompiledModel)`
without holding a reference — a dead model's id is recycled, so a stale
buffer served a *different stage's* frozen state, allocator-dependently.
Any production per-compile cache keys on an owned reference.

**5. Go/no-go: NO-GO** for a production numpy peaks buffer.  The premise
the spike was sent to test — shapes vary slowly enough to reuse — is
**true** (Findings 2: K ≤ 32 anchors at 1e-4, every case and state), but
the win it was meant to buy is not there on the numpy substrate: the
batched exact kernel is already within ~2× of the memory floor, so
replacing its arithmetic with interpolation trades compute nobody is
paying for.  What survives the no-go: (a) WP-1120 — batch the residual,
bit-exact, measured 2.2-3.6× on the forward path; (b) this file's design
note and anchor curves stand ready if WP-1115's compiled substrate changes
the per-element economics — a compiled exact kernel and a compiled buffer
compose, and 1115's gate should read this spike's decomposition (the gap
is padding + per-element floor, not evaluation count); (c) the anchor
machinery (greedy placement, clamp-kink handling) is the sizing loop any
future buffer starts from.  No default-vs-opt-in question goes to the user
— nothing lands.

## Design note (task 2)

**Layout.**  One buffer per (stage, distinct width family): phases sharing
(U, V, W, X, Y, `gauss_*`, `lor_*`, S/L, H/L) share one buffer, and emission
lines always share it — Γ, η and the FCJ geometry are functions of the
peak's *position* alone, so a Kα2 reflection reads the same family as its
Kα1 twin.  Frozen at stage compile (the same class as windows and node
counts — invariant 1): the anchor positions (greedy probe-and-bisect to the
stage's tolerance, with the domain split at the Γ_G-clamp roots, which the
compile knows analytically), per-anchor FCJ node counts (floored, never the
sub-threshold skip — Findings 3), and the stored offset grid (step
min(pattern step, Γ_min/16) — Findings 3 has why /4 was 1e-3 wrong;
half-width read off the frozen windows plus a drift margin).  The anchor *values* — the sampled
planes — are recomputed from the current θ on every evaluation, so they
follow the parameters smoothly between recompiles; only indices and counts
are discrete.

**FCJ asymmetry enters convolved into the anchor** (anchor-wise node sets,
evaluated exactly at each anchor's geometry), never as interpolated images:
§ Findings 2 shows the convolved family interpolates at K ≤ 32, and keeping
images per reflection would keep the ×7.8-9 element volume the buffer
exists to remove.

**Interpolation, and what the derivative bases become.**  Each anchor
stores four planes on the stored grid: S = Ω and its exact partials S_x,
S_Γ, S_η (`pseudo_voigt_derivs`, FCJ-mixed with the anchor's ω).  A C²
cubic spline in θ interpolates each plane; a reflection at position p with
widths (Γ_k, η_k) reconstructs

    Ω = S(p) + (Γ_k − Γ_law(p))·S_Γ(p) + (η_k − η_law(p))·S_η(p)

resampled onto its window by 4 cubic B-spline taps over Unser-prefiltered
samples — the exact C² interpolating spline in Δ at 4-tap cost (raw-sample
Catmull-Rom is O(h³) and measurably not enough — Findings 3).
The Taylor term keeps Ω first-order exact wherever a reflection's width
leaves the law — position corrections move p off 2θ_Bragg today, and a
Stephens Λ(hkl) block is *exactly* this term later.  The Jacobian reuses
the same anchors (WP-0605's answer 2):

    ∂Ω/∂Γ = S_Γ,   ∂Ω/∂η = S_η,
    ∂Ω/∂pos = S_θ(p) − S_x(p) − Γ_law′(p)·S_Γ(p) − η_law′(p)·S_η(p)

with S_θ the spline's own θ-derivative — the FCJ geometry motion that the
shipped path node-FDs comes out of the spline for free, and the two
law-drift subtractions stop it being counted twice against the scalar
chain's ∂Γ/∂p, which already carries the width motion.  ∂Ω/∂(S/L) and
∂Ω/∂(H/L) are anchor-level FDs (two extra anchor sets, K each, still
trivial).  Everything is C¹ in θ and in every parameter (C² spline over
anchors that are themselves smooth functions of θ; C² resample), so the
analytic-Jacobian invariant survives — which is the second, independent
reason the linear blends lose: they are C⁰ at anchors, and a moving cell
would drag those kinks through the residual.

**Cost model** (§ Findings 1 numbers): per evaluation the buffer pays
K × images × n_stored exact profile elements (~0.1 M on the trigger,
against the shipped 1.12 M) plus ~8 fma per (row, window point) for the
spline combine and resample, where the shipped path pays one pV evaluation
(exp + division) per element times the FCJ image multiplier.  So the
expected win is (image multiplier × pV/fma ratio) on FCJ cases and only
the pV/fma ratio on symmetric ones.  The prototype therefore measures
**three rungs** — shipped scalar loop, batched exact, buffered — because
the residual's dispatch win was never taken (WP-1112 batched the bases
only) and must not be booked to the buffer.

## Tasks

- [x] **Measure the shape-variation budget**: on 1111's four cases, compute
      exact profiles on a dense θ grid and the minimum anchor count whose
      interpolation meets 1e-3 / 1e-4 on area and moments — the
      anchors-vs-accuracy curve is this WP's central plot.
      *(2026-08-21: § Findings 1-2; `examples/bench_peaks_buffer.py`.)*
- [x] **Design note in this file**: buffer layout (per (phase-class, line) or
      global; how FCJ asymmetry enters — anchor-wise node sets vs
      interpolated images), the interpolation scheme and its
      differentiability argument, and what the derivative bases become under
      the buffer (the Jacobian must reuse the same anchors or the win halves
      — WP-0605's answer 2, same lesson).
      *(2026-08-21: § Design note above.)*
- [x] **Scratch prototype** (`examples/bench_peaks_buffer.py`): forward +
      derivative-bases evaluation through the buffer on the trigger-shaped
      and `cpd-2` states; wall vs the (post-1112) shipped path; max area /
      moment / pointwise deviation vs exact.
      *(2026-08-21: § Findings 3; `--part proto`.)*
- [x] **Fit-level check**: one full acceptance protocol run in the prototype
      harness with the buffer substituted, deviations of every reported
      parameter and esd against the exact fit — the number the go/no-go
      quotes.
      *(2026-08-21: § Findings 4; `--part fit`, cpd-2's QPA protocol and
      the trigger cold fit.)*
- [x] **Record the go/no-go** with the anchors-vs-accuracy curve, the wall
      ranges and the parameter deviations; if go, open the production WP
      (next free 11xx) with the design note as its seed and put the
      default-vs-opt-in question to the user with the numbers.
      *(2026-08-21: § Findings 5 — NO-GO; the salvage is
      [1120](1120-batched-residual.md), bit-exact, no user question owed.)*

## Acceptance

```sh
.venv/bin/python examples/bench_peaks_buffer.py     # the spike's own table
.venv/bin/python -m ruff check src tests examples
```

No production code changes in this WP (0605's clause verbatim: if the
prototype lands anywhere it is in an example or a test). The go/no-go names:
anchor counts at each tolerance per case, whole-evaluation speedup at those
counts, and worst parameter/esd deviation on a full protocol — never an Rwp
comparison.

## References

- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 210–218, §5.1 — the peaks
  buffer's existence and role. TOPAS is closed source: **papers only**,
  concepts only (CLAUDE.md licensing fence).
- Cheary, R. W. & Coelho, A. (1992). *J. Appl. Cryst.* **25**, 109–121 — the
  FPA context the buffer was built for (background only; FPA itself is
  v2-fenced).
- WP-0605's file — the redundancy measurements and the spike discipline this
  WP copies.

## Handover log

- **2026-08-20** — created by the 1109 review session as the algorithmic
  tier of the v1.1 series; the anchors-vs-accuracy curve is the question
  everything else waits on.
