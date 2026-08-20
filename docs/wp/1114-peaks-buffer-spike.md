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

## Tasks

- [ ] **Measure the shape-variation budget**: on 1111's four cases, compute
      exact profiles on a dense θ grid and the minimum anchor count whose
      interpolation meets 1e-3 / 1e-4 on area and moments — the
      anchors-vs-accuracy curve is this WP's central plot.
- [ ] **Design note in this file**: buffer layout (per (phase-class, line) or
      global; how FCJ asymmetry enters — anchor-wise node sets vs
      interpolated images), the interpolation scheme and its
      differentiability argument, and what the derivative bases become under
      the buffer (the Jacobian must reuse the same anchors or the win halves
      — WP-0605's answer 2, same lesson).
- [ ] **Scratch prototype** (`examples/bench_peaks_buffer.py`): forward +
      derivative-bases evaluation through the buffer on the trigger-shaped
      and `cpd-2` states; wall vs the (post-1112) shipped path; max area /
      moment / pointwise deviation vs exact.
- [ ] **Fit-level check**: one full acceptance protocol run in the prototype
      harness with the buffer substituted, deviations of every reported
      parameter and esd against the exact fit — the number the go/no-go
      quotes.
- [ ] **Record the go/no-go** with the anchors-vs-accuracy curve, the wall
      ranges and the parameter deviations; if go, open the production WP
      (next free 11xx) with the design note as its seed and put the
      default-vs-opt-in question to the user with the numbers.

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
