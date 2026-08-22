# WP-1122 — compiled peaks buffer: the declared-tolerance tier

Milestone: v1.1 · Status: 🔄 2026-08-22 — gate passed; task 1 (economics probe) under way
Depends on: 1115 (the substrate and its rules), 1121 (the gate: its closing
remainder prices this WP)

## Goal

rietx gains a second, **declared** forward mode: every (line, reflection)
profile reconstructed from a few dozen exactly-computed anchor shapes per
width family, under one stated interpolation tolerance that provenance
records and the harness prices in esd currency — or a recorded NO-GO
measuring why the compiled economics still do not pay. This is the only
measured route to v1.1's stretch target (cold trigger fit < 1 s), and it is
the package's first approximation whose equivalence bar cannot be
bit-identity. That trade is the point of the WP, not a side effect: it is
taken openly, priced, and put to the user, or not taken at all.

## Context

**The gate is passed, and the stretch is still wanted.** Both blockers
closed 2026-08-22: [1121](1121-per-reflection-cost.md) took the
exact-arithmetic remainder and [1123](1123-fast-tolerance-default.md) took
1113's priced ftol flip. The cold trigger fit stands at **5.67-5.70 s**
against v1.1's stretch of < 1 s, so the gap is ~5.7× and the WP is live.

**Where the cost stands** (`examples/bench_refinement.py`, best of three,
worktree `[dev]` venv, darwin/arm64, python 3.12.12, machine idle; measured
by 1123 on the merged tree it left behind — *re-measure before quoting any
absolute*): trigger cold 5.67-5.70 s; cpd-1a 270 nfev at 1.52 s; cpd-2 329
at 2.27-2.28 s; nac 39 at 0.34-0.35 s.

1121's decomposition of the cold trigger fit is still the right one — the
flip removed *evaluations*, not work per evaluation, so each share below is
roughly unchanged while the seconds behind it are ~1.5× fewer. Read the
percentages against 5.7 s, never against the 8.7 s they were taken on:

| seam | share | what it is |
|---|---|---|
| jacobian: bases | 32.8 % | plane work, ~2× off its numpy floor |
| residual (forward) | 22.2 % | plane work, same |
| perturbed `phase_peaks` | 20.2 % | **per-reflection, dispatch-bound** |
| solver + runner | 10.5 % | scipy TRF |
| plane accumulation / decode / FD arithmetic | 3.6 / 3.2 / 3.7 % | |
| `compile_model` | 2.0 % | |

**The mechanism finding that shapes this WP's cost model** (1121
§ Findings 4). The per-reflection blocks are **dispatch-bound**, the
opposite of what 1115 measured for the planes: the trigger's phases hold
98-282 reflections each (594 total), and a `phase_peaks` call in which
*every* memo slot hits still costs **562 ns per reflection**, against 2-4 ns
per element on the ~10⁵-element planes. That is why 1115's tier bought 11.0×
on the scatter, ~2× on the two profile kernels and **1.03×** on
`phase_peaks`. So a buffer that removes *element volume* is priced against
the plane seam — 55 % of wall, already near its floor — and buys nothing on
the per-reflection 20 %, whose lever is fewer, larger calls or compiled code
that does not dispatch. The ceiling this WP can reach is bounded by that
split, and task 1 states it in numbers before any code is written.

**What 1121 left on the table, priced, neither of it blocking.** The
per-line intensity assembly inside `phase_peaks` (0.29 s, 3.3 %) runs on
every column including those that cannot move an intensity — claiming
otherwise is the *inverse* of `_INTENSITY_ONLY`, and root CLAUDE.md warns
that a wrong inverse list costs a silently short column. `table.decode`
(0.28 s, 3.2 %) rebuilds the whole parameter dict per column for a one-entry
change.

**Two method rules 1121 paid for, and this WP's probe re-hits both.**
*Price a removal by removing it*: a per-family timing census over a cache
charges each column for whatever its predecessor evicted, and it over-read
the scale family by 5×. And an unbounded-cache "would-hit" figure is not
headroom — depth 8 built exactly the same blocks as depth 2, to the call.

**Why volume, and not another cost-per-element win.** The exact plane seam
is finished: WP-1115 fused the three plane kernels and threads them
(trigger cold 17.6 → 8.86-8.99 s, cpd-1a 2.17-2.21 s, nac 0.40-0.41 s;
darwin/arm64, worktree `[dev]` venv, best of 3), and that seam now runs ~2×
off its own memory floor with no third factor in it. What no exact path can
remove is the arithmetic *volume*: on the trigger case one forward
evaluation computes **269-367 profile elements per pattern point** — 34.6
window points per point (structural overlap, already at the honest
`WINDOW_AREA_TOL` windows) times a 7.8-9× FCJ image multiplier — about
1.1 M exact profile elements per residual call. If ~30 shapes suffice where
the exact path computes ~500 profiles per evaluation, no vectorisation of
the 500 reaches the 30. Removing volume is the buffer's whole content, and
it is TOPAS's single biggest forward-model asymmetry against this package
(Coelho 2018 §5.1: "a small number of peaks being calculated across the
whole 2θ range").

**What the 1114 spike settled** (restated — the protocol forbids reading
closed WPs; every number from `examples/bench_peaks_buffer.py`, darwin/arm64
`[dev]`, 2026-08-21):

- **Shapes reuse, everywhere measured.** A C² cubic spline through
  greedily-placed anchors meets 1e-3 at **K ≤ 16** and 1e-4 at **K ≤ 32**
  on worst-case relative area, first moment (FWHM units) and central second
  moment — every harness case, cold state *and* converged (nac 8,
  cpd-1a/cpd-2 16→32, trigger 24/32 at 1e-4). Anchors are per distinct
  width family and shared across emission lines (Γ, η, FCJ geometry are
  functions of position alone). Greedy probe-and-bisect placement survives
  the genuine C¹ kinks where the fitted Caglioti quadratic goes negative
  and `_MIN_GAMMA_G2` clamps Γ_G (cpd converged states, 2θ ≈ 92-134°);
  every fixed grid plateaus at ~3-5e-4 there.
- **The fit-level price at 1e-4 is below anything a report quotes.** Full
  protocols through the prototype: median value deviation 0.0020 esd
  (trigger) / 0.018 esd (cpd-2), worst 0.107 / 0.215 esd — and every esd
  row that moved > 5 % is a width-decomposition direction with
  esd/|value| between 7e2 and 3e9, a covariance artefact in the exact fit
  too. Trigger Rwp identical to five digits. Where buffered and shipped
  rows disagree most, the buffer is the *more* accurate: its rows sit
  ≤ 8e-5 (m1, FWHM units) from a 128-image reference where the shipped
  path's sub-threshold FCJ skip sits 3.3e-3 away.
- **The NO-GO was the substrate, never the physics.** Batched exact numpy
  runs at ~8-11 ns/element — within ~2× of the memory floor — while the
  buffer's numpy gathers run ~0.8 ns/element but carry their own
  multipliers (7 planes against 4, 4 taps, ~2× `w_max` padding, the
  θ-spline over the stored grid): parity on the trigger bases, a 7-10×
  *loss* on the symmetric lab cases, whose 3-12 elements per point never
  had volume to remove. Interpolation traded away arithmetic nobody was
  paying for.
- **What changed since:** WP-1115's tier is that substrate replaced. In a
  fused `njit` kernel the resample genuinely is a few fma per point while
  the exact path pays an `exp` (and FCJ quadrature) per element. A
  compiled exact kernel and a compiled buffer *compose*; the projected win
  is (image multiplier × exact-per-element cost / fma-per-element cost) on
  FCJ cases and only the cost ratio on symmetric ones. So the buffer is an
  FCJ-and-dense-overlap lever — exactly the stretch target's shape — and
  the lab cases must be shown **unharmed**, not merely unimproved:
  buffering is chosen per width family at compile, from the measured
  element volume, never globally.

**The mode owns the tolerance; the substrate never does.** The compiled
tier's contract (root CLAUDE.md § Conventions) is that nothing above
`compile_model` branches on whether the kernels ran, and `RIETX_COMPILED=0`
changes speed, not answers. A buffer that existed only inside the compiled
tier would break that: the two substrates would disagree by the tolerance,
not by rounding. So the buffer is a **mode of the forward model with two
substrates** — a numpy reference implementation (the oracle, and the
mandatory fallback; 1114's prototype already proved it correct and merely
slow) and the njit kernels — held to the same per-kernel rounding bars the
exact tier uses today. Exact vs buffered is the declared choice; numpy vs
compiled stays invisible.

**The design seed** (1114's design note, restated so this file suffices):

- *Layout.* One buffer per (stage, distinct width family): phases sharing
  (U, V, W, X, Y, `gauss_*`, `lor_*`, S/L, H/L) share one, emission lines
  always share it. Frozen at stage compile — the same class as windows and
  node counts (invariant 1): anchor positions (greedy probe-and-bisect to
  the stage tolerance, domain split at the Γ_G-clamp roots, which the
  compile knows analytically), per-anchor FCJ node counts (floored, never
  the sub-threshold skip), the stored offset grid (step
  min(pattern step, Γ_min/16); half-width from the frozen windows plus a
  drift margin). Anchor *values* are recomputed from the current θ on
  every evaluation — shapes follow the parameters smoothly between
  recompiles; only indices and counts are discrete.
- *Reconstruction.* Each anchor stores four planes: S = Ω and its exact
  partials S_x, S_Γ, S_η (FCJ-mixed at the anchor's own geometry). A C²
  cubic spline in θ interpolates each plane; a reflection at position p
  with widths (Γ_k, η_k) reconstructs
  `Ω = S(p) + (Γ_k − Γ_law(p))·S_Γ(p) + (η_k − η_law(p))·S_η(p)`,
  resampled onto its window by 4 cubic B-spline taps over Unser-prefiltered
  samples (the exact C² interpolating spline in Δ at 4-tap cost). The
  Taylor term keeps Ω first-order exact wherever a reflection's width
  leaves the law — position corrections move p off 2θ_Bragg today, and a
  Stephens Λ(hkl) block is *exactly* this term later.
- *Jacobian, off the same anchors* (or the win halves): ∂Ω/∂Γ = S_Γ,
  ∂Ω/∂η = S_η, and
  `∂Ω/∂pos = S_θ(p) − S_x(p) − Γ_law′(p)·S_Γ(p) − η_law′(p)·S_η(p)` with
  S_θ the spline's own θ-derivative — the FCJ geometry motion the shipped
  path node-FDs comes out of the spline for free, and the two law-drift
  subtractions stop the width motion being counted twice against the
  scalar chain's ∂Γ/∂p. ∂Ω/∂(S/L), ∂Ω/∂(H/L) are anchor-level FDs (two
  extra anchor sets, K each). Everything is C¹ in θ and in every
  parameter, so the analytic-Jacobian invariant survives; linear blends
  are C⁰ at anchors and lose twice (accuracy, and kinks a moving cell
  drags through the residual).
- *Cost model.* Per evaluation: K × images × n_stored exact elements
  (~0.1 M on the trigger, against the shipped 1.12 M) plus ~8 fma per
  (row, window point) for the spline combine and resample.

**The traps, each already paid for once** (1114 § Findings 3-4; any
implementation re-hits them first):

1. A 4-tap resample of *raw* samples is O(h³) and measurably not enough —
   prefilter (Unser) so the same taps evaluate the C² interpolating spline.
2. The stored step keys to **Γ/16**: the O(h⁴) constant lives in
   σ = Γ/2.355 units and the flank carries f⁗ ~ 10²/σ⁴; /4 was 1e-3-wrong.
3. An anchor must **never** take the sub-threshold FCJ skip (node count 0):
   the spline smears the family discontinuity into every neighbour
   (measured 1.0e-3 FWHM of m1 against 1.2e-5 with the count floored).
4. A per-compile cache keys on an **owned reference**, never `id()` of an
   unreferenced model — a dead model's id is recycled and a stale buffer
   served a different stage's frozen state, allocator-dependently.
5. The compiled-tier rules bind (root CLAUDE.md § Conventions): serial
   `njit(cache=True, nogil=True)` kernels over row ranges on the shared
   pool, never `prange`; one path per process; the per-kernel equivalence
   bar stated and asserted; the numpy side stays exercised.

**The deal, made clauses.** This is the package's first approximate forward
mode, and the honesty contract is the acceptance, not decoration:

- (a) **One tolerance constant, with its formula**, stated in the same
  discarded-area currency as `forward.WINDOW_AREA_TOL` so the two compose
  rather than stack; the default chosen from the measured anchor curve,
  after checking the shape of TOPAS's own accuracy knob in the paper
  (prior art shapes the seam — never port, concepts only).
- (b) **Measured against the exact path on the full harness and the
  acceptance suites**, per-parameter and per-esd, in esd currency.
- (c) **Reported**: provenance and/or a diagnostic naming the mode and its
  tolerance — a new correction ships with a record field, and never an Rwp
  comparison as evidence. `capabilities().features` carries the mode as a
  derived predicate, not a literal.
- (d) **Default-on vs opt-in is the user's decision, made from the
  measured table** — never assumed by this WP.
- (e) **The exact path stays**, and every test that pins a number declares
  which mode it pins (the dispersion-default rule meeting its third
  default).

The precedent that makes this a third stated truncation rather than a first
sin: the exact path already carries `WINDOW_AREA_TOL = 2e-2` and the
sub-threshold FCJ skip, both declared, both measured. The difference — the
buffer touches every row — is why it is a *mode*, not a constant.

**There is now a shape to copy, so do not invent one.** The buffer would be
the first approximate *forward* mode but the package's **second**
declared-tolerance concession: 1123 shipped
`RefinementPlan.intermediate_ftol` with exactly the parts (a)-(e) ask for —
a measured bound in esd currency (≤ 0.03 esd on a single fit), an off switch
reproducing the old answer bit for bit, a record of what each stage actually
*ran* at rather than what it declared (`StageResult.ftol`,
`NodeAction.ftol`), and a line in every acceptance suite naming the setting.
Its session reports that the switch was cheap and the **recording** was what
cost time; budget accordingly.

**Judge the mode on single fits, and say so.** 1123's chained-series
comparison changed sign between two trees one commit apart — 1.04× worse,
then 1.12× better, with nothing about the schedule changed — because a warm
chain turns a bounded per-fit difference into a rung escalation or a rung
avoided, an effect unbounded in magnitude and not fixed in sign. A tolerance
mode judged on a series number is judged on an amplifier.

## Non-goals

FPA and FFT convolution (v2-fenced — this WP reuses the existing TCHZ/FCJ
shapes, no new physics); re-opening 1114's NO-GO on its original numpy
terms (the numpy buffer exists here only as oracle and fallback, never as
the performance claim); Le Bail/Pawley partitioning; any tolerance looser
than 1e-3 without the user in the loop; a second approximate mode; touching
window semantics beyond composing the two tolerance currencies.

## Tasks

- [ ] **Gate reading + economics probe.** Re-measure the harness on this
      tree (§ Context's figures are 1123's), then measure the two per-element
      costs
      the cost model needs on the current tree: the compiled exact pV/FCJ
      element against a compiled prefilter + 4-tap resample + spline-combine
      microkernel on trigger-shaped planes (`examples/bench_compiled_buffer.py`).
      Project the fit-level ceiling per harness case from measured ratios,
      and record **go/no-go for the build** with the numbers.
- [ ] **Buffer compile.** Width-family detection, greedy anchor placement
      with the clamp-root domain split, floored node sets, stored grid +
      prefilter — frozen at stage compile; owned-reference caching; the
      per-family buffering decision from measured element volume.
- [ ] **Forward reconstruction, numpy first.** The reference implementation
      is the oracle; per-row equivalence bar vs the exact path asserted
      (≤ tol on area, m1, m2), whole-pattern bar stated. Then the njit
      kernels, held to the exact tier's per-kernel rounding bars against
      the numpy buffer.
- [ ] **Derivative bases off the same anchors.** The `_column_extras` /
      `moving_paths` gates re-checked under the mode; the cross-backend
      configs grow with the new derivative path (CLAUDE.md rule).
- [ ] **The honesty surface**: the tolerance constant + formula, the
      provenance/diagnostic field, the `capabilities()` flag, the
      `rietx compare` row (`tests/test_compare_ui.py`), and every pinned
      test declaring its mode.
- [ ] **Fit-level measurement**: full harness both modes, per-parameter/esd
      deviation table, acceptance suites green, obs/calc/diff PNGs to
      `tests/output/`.
- [ ] **The user decision**: default-on vs opt-in and the tolerance
      default, put with the tables — and with 1113's flip status beside
      them, since the factors multiply.
- [ ] If the economics still do not pay, record **NO-GO** with the measured
      ratios — a second substrate verdict on the shelf beside 1114's, and
      the stretch target declared unreachable on v1.1's terms.

## Acceptance

```sh
.venv/bin/python examples/bench_compiled_buffer.py   # the probe: per-element ratios, anchor counts
.venv/bin/python examples/bench_refinement.py        # exact mode: ranges unchanged
.venv/bin/python examples/bench_refinement.py --buffered            # the mode's spelling is task 2's
RIETX_COMPILED=0 .venv/bin/python examples/bench_refinement.py --buffered  # same answers, numpy substrate
.venv/bin/python -m pytest -n auto --dist loadgroup  # full: this moves numbers
.venv/bin/python -m ruff check src tests examples
```

Before/after as harness ranges with venv and platform; every deviation
quoted in esd currency per parameter; the per-kernel bars stated; the
stretch (< 1 s cold) reported either way; never an Rwp comparison.

## References

- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 210-218, §5.1 — the peaks
  buffer's existence and role. TOPAS is closed source: **papers only,
  concepts only** (CLAUDE.md licensing fence).
- Cheary, R. W. & Coelho, A. (1992). *J. Appl. Cryst.* **25**, 109-121 —
  the FPA context the buffer was built for (background only; FPA is
  v2-fenced).
- Unser, M. (1999). *IEEE Signal Process. Mag.* **16**(6), 22-38 — the
  B-spline prefilter behind trap 1.
- WP-1114 § Findings 2-4 and § Design note — the seed this file restates;
  its anchor-curve figure is `tests/output/wp1114_anchor_curve.png`.
- WP-1115 — the substrate and its rules (now root CLAUDE.md § Conventions).
- WP-1121 — the gate; WP-1113 § Findings — the multiplying flip.

## Handover log

- **2026-08-22** — created, at the maintainer's direction, to give the
  compiled-substrate option in 1114's design note an owner and the v1.1
  stretch target its one measured route. The exact-arithmetic road ends
  around 4-5 s on the cold trigger fit (1121 + the flip, projected): its
  remaining volume is structural, and only shape reuse removes volume. The
  physics half is proven (K ≤ 32 anchors at 1e-4, every case, both
  states); the substrate half failed once, on numpy, for economics 1115
  has since replaced. What this WP decides is therefore not whether shapes
  reuse but whether rietx takes its first *declared-tolerance* mode — the
  bargain TOPAS's speed has always rested on — priced in esd currency and
  put to the user. Gated on 1121's close; nothing is started. **Next**:
  task 1, and only after 1121's remainder lands in `### Inherited` here.
