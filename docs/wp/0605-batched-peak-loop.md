# WP-0605 — Batched peak loop (spike, then decide)

Milestone: v0.6 · Status: ✅ 2026-07-28 — task 0 in production; batched
rewrite: **no-go**, measured grounds in the answers + handover below
Depends on: — (informed by WP-0401, WP-0404, WP-0408)

## Goal

Decide, **with measurements rather than reasoning**, whether the per-(emission
line, reflection) python loop in `model/forward.py` should become a padded
batched evaluation — and only then write it. The deliverable of this WP is a
recorded go/no-go plus answers to the four design questions below. The rewrite
itself is explicitly Phase 2 and out of scope here.

## Context

The forward model evaluates each reflection on its own frozen window, one at a
time in python: ~130 windows per pattern, each a profile evaluation (~20
elementwise ops) plus a `window_add`. A forward is therefore a few thousand tiny
array operations, and **every backend is ~100 % dispatch-bound at that
granularity** — the per-op overhead (numpy ~0.6 µs, torch-CPU ~2 µs, MPS
~110-165 µs) times the op count *is* the runtime, with arithmetic nowhere in it.

WP-0408 measured what restructuring would buy, at fixed total work, by comparing
128 windows × 900 points against one kernel of 115 200 points
(`examples/bench_torch_mps.py`, which prints this):

| shape | elements | numpy | torch-CPU | MPS |
|---|---|---|---|---|
| 128 × 900 | 115 200 | 1.36 ms | 4.34 | 10.57 |
| 1 × 115 200 | 115 200 | **0.56 ms** | 0.43 | 0.41 |

**≈2.4× on the numpy path** — the default every user runs, no optional
dependency. That is this WP's entire justification. It is *not* GPU enablement,
and the same script pins why: sweeping one kernel across sizes puts **break-even
at ≈50-65 k elements and the ceiling at ≈2.5-3×** (the peak chain is ~17 flops
per element, i.e. memory-bound, so a device's arithmetic throughput never
participates). One batched kernel per pattern is 121 k elements for 11-BM NAC,
38 k for lab corundum, 17 k for SRM 660c — so a single lab pattern is *below
break-even even after batching*, and reaching the plateau needs ≈10 (synchrotron)
to ≈60 (lab) patterns processed together, i.e. the v2-fenced in-situ series. See
[../DESIGN.md](../DESIGN.md#locked-decisions), dated 2026-07-27. **Do not adopt
this WP hoping for a GPU win, and do not let it grow into that.**

Why it is a spike and not a rewrite: `model/forward.py`'s loop is the most
invariant-dense code in the package (frozen-per-stage discreteness, the
accumulation order that six bit-identity goldens pin, the analytic Jacobian's
shared expansion). A 2.4× wall-clock win does not license rewriting that on
faith.

### Measured 2026-07-28 — the hotspot is FCJ, and half of it is redundant

Profiled during v0.6 scoping (see [../solver-survey.md](../solver-survey.md) §0.1
for the surrounding context and the Amdahl argument). Real SRM 660c acceptance
fit, full NIST protocol, total ≈1.9 s. Two findings **retarget this WP**.

**(a) The cost is one function, and it is not the profile evaluation.**

| function | calls | tottime | cumtime |
|---|---|---|---|
| `profiles/fcj.py::fcj_offsets_weights` | 33 840 | 0.510 s | **0.919 s (48 % of the fit)** |
| `profiles/pseudovoigt.py::pseudo_voigt_derivs` | 6 480 | 0.221 s | 0.221 s |
| `crystallography/symmetry.py::generate_reflections` | 7 | 0.187 s | 0.216 s |
| `profiles/fcj.py::_xi_max` | 34 274 | 0.114 s | 0.155 s |
| `model/forward.py::derivative_bases` | 108 | 0.146 s | 1.104 s |

`derivative_bases`' own `tottime` is small — the cost is entirely in what it
calls, and **FCJ node generation alone is ~half the total runtime**. At 27 µs per
call on arrays of 8-64 nodes this is per-call dispatch, not arithmetic: the
signature takes a **scalar** `two_theta_deg`, so each of ~140 (line, reflection)
pairs pays ~15 separate numpy dispatches. The `_clip` (68 557) and `full_like`
(69 386) counts are the same fact seen from inside. This confirms design question
2's suspicion and sharpens it: **the batched prototype should be aimed at the FCJ
node axis first**, which is also (per WP-0408's table above) exactly the axis
where padding waste is worst — so the two hardest facts about this WP are about
the same tensor axis.

Also visible: the finite-difference fallback is **not** a cost here (132
`evaluate` calls against 117 residual calls, so ~15 FD-driven evaluations). And
`generate_reflections` costs 11 % of runtime in *stage compile*, which is outside
this WP but is the cheapest win on the page — in a 7-stage plan the cell moves in
one stage, so six compiles regenerate a bit-identical list.

**(b) 53 % of FCJ calls recompute a result that was already computed.** Counting
distinct `(2θ, S/L, H/L, n_nodes)` argument tuples, per stage (each stage run
standalone, so absolute counts do not sum to the chained protocol — the
*fractions* are the finding):

| stage | FCJ calls | unique | redundant |
|---|---|---|---|
| `scale_bkg` | 2 040 | 192 | **90.6 %** |
| `disp` | 5 280 | 3 264 | 38.2 % |
| `cell` | 7 980 | 4 992 | 37.4 % |
| `profile_w` | 4 680 | 192 | **95.9 %** |
| `profile` | 6 180 | 192 | **96.9 %** |
| `lines_axial` | 26 880 | 17 088 | 36.4 % |
| `biso` | 2 580 | 192 | **92.6 %** |
| **total** | **55 620** | **26 112** | **53.1 %** |

The pattern is exactly what the physics predicts. FCJ nodes depend only on peak
position and the two aperture ratios, so **in any stage that frees none of cell,
zero, `sample_displacement`, `axial_sl` or `axial_hl`, they are constant for the
entire stage** — the 192 unique tuples are simply the complete (line, reflection)
set. The residual 36-38 % in position-moving stages is trust-region trial points
being re-evaluated at repeated θ.

That opens a **second, cheaper route to the same win that this WP was not
scoped to consider**, and it deserves measuring before the batched rewrite is
costed — see task 0 and design question 4 below.

### Inherited

From **WP-0505** (sequential series, landed 2026-07-28): **the "batch many
patterns" case now has an API to live behind.** WP-0408 measured that a device
only pays at ≈10 synchrotron / ≈60 lab patterns batched together and fenced the
`vmap`-batched series to v2; `anatase.sequential.SequentialRefinement` is now
where such a series is expressed, and it walks patterns strictly one at a time
(`_chain`). So if the batched-loop spike here ever grows a multi-pattern form,
`_chain` is the single call site to change, and its warm-start chain is the
reason a naive batch is *not* equivalent: pattern k's starting values are
pattern k−1's answers, so patterns in a chain cannot be evaluated
simultaneously. A batched series has to batch across independent chains (or
give up the warm start), which is a design constraint that did not exist before
this WP and is not visible from the timing numbers alone.

From **WP-0408** (torch backend, landed 2026-07-27) — the measurements above,
plus three constraints that are already known and need not be rediscovered:

- **`torch.compile` is not an alternative to batching.** Measured: 2.5× slower
  than eager on CPU (13.5 vs 5.4 ms) after a 38 s compile; on MPS it fails,
  dynamo hitting its recompile limit because `i0, i1 = cp.win[il, k]` and the
  `arange(i0, i1)` in `window_add` specialise on each window's literal bounds, so
  it attempts one graph per reflection. Any batched design that keeps
  per-window python-int bounds inherits that.
- **Padding cost is already sized on real states** (compiled models, measured
  2026-07-27):

  | state | reflections × lines | window widths | padding waste, profile plane | with FCJ nodes |
  |---|---|---|---|---|
  | 11-BM NAC | 129 × 1 | 35-939 (mean 865) | 1.09× | 1.09× (no FCJ) |
  | SRM 660c | 30 × 2 | 171-276 | 1.23× | 3.06× (4 MB fp64) |
  | corundum + FCJ | 64 × 2 | 91-296 | 1.49× | **3.98×** (9 MB fp64) |

  The profile plane pads cheaply; **the FCJ node axis is where padding hurts**,
  because node counts vary per reflection (0-64). Extrapolated to a large problem
  — 2000 reflections × 2 lines × 64 nodes × 300 points — the padded tensor is
  ~615 MB fp64, which is the memory question Phase 1 must answer.
- **The hot-path rules from the three-backend era still bind** (CLAUDE.md
  Conventions): no frozen numpy constant on the left of an operator against a
  θ-derived value, and any new op lands on numpy, jax *and* torch together.

## Non-goals

The rewrite itself (Phase 2, a separate WP or a follow-on once this one says go);
GPU acceleration of single-pattern refinement (measured not to exist — the fence
above); `vmap`-batched multi-pattern/in-situ refinement (v2); touching the
analytic Jacobian's *consumers* in `optimize/least_squares.py`.

## Tasks

- [x] **Task 0 — measure the cheap alternative first: a stage-scoped FCJ node
      cache.** Decide at *stage compile* whether any free path in this stage can
      move a peak (cell, zero, `sample_displacement`, `axial_sl`, `axial_hl`, and
      any wavelength); if none can, compute the (line, reflection) node sets once
      per stage and reuse them for every residual and Jacobian call. This is a
      **dirty flag, not a hash cache** — no hashing in the hot loop, and it is the
      frozen-per-stage discreteness invariant extended from node *counts* to node
      *positions*, so it argues from the same principle the existing code already
      relies on. Measure: whole-fit wall clock on SRM 660c and corundum, and
      bit-identity against the six `tests/data/backend_goldens/` goldens — which
      it should achieve **trivially**, since reusing a value is not reordering an
      accumulation. Expected ceiling ≈1.3× whole-fit; the point is that it is
      ~1 % of the risk of Phase 2. If this lands most of the win, the honest
      go/no-go for the batched rewrite changes.
      *Done 2026-07-28, with the mechanism reshaped by its own measurement: the
      dirty flag as specified is ≈1.0× because the shipped plans free
      cumulatively — see answer 4. Shipped instead as an input-equality memo +
      an `axial_derivs` skip; 1.23× (660c) / 1.04× (corundum), bit-identical,
      **graduated to production**.*
- [x] **Prototype** the batched layout for one phase, symmetric peaks only
      (`fcj_n == 0`), against the 11-BM NAC state, in a scratch module or a test
      — **the shipped path is not modified in this WP**. Measure forward time on
      numpy/torch/MPS, peak memory, and elementwise agreement with the current
      loop.
      *Done — `examples/bench_batched_peak_loop.py`: 1.55-1.6× on numpy and
      **exactly bit-equal**; torch-CPU 1.92×; MPS 0.55×.*
- [x] **Extend the prototype to the FCJ case** on the corundum state (padded
      `(N, max_nodes, W)` with zero weights on the pad) and measure whether the
      3-4× padding waste eats the win; if it does, measure the two mitigations —
      chunking over reflections (precedent: `DEFAULT_CHUNK` in
      `backend/jax_backend.py` / `backend/torch_backend.py`) and bucketing
      reflections by node count.
      *Done — it does eat it, and then some: pad is a **0.58× regression**,
      chunking 0.63×, bucketing by node count recovers only 1.15×.*
- [x] **Answer the four design questions** (below), in writing, in this file.
- [x] **Record the go/no-go** in the handover log with the measured numbers, and
      either open the Phase-2 WP or close this one with the reason.
      *Closed: no-go, no Phase-2 WP opened.*

### The four design questions

1. **Does `window_add` survive, or does the op set have to grow?** The batched
   form needs a padded-window scatter rather than the contiguous-window one.
   The indices remain frozen at stage compile, so this does not violate the
   *intent* of frozen-per-stage discreteness — which forbids **data-dependent**
   indices, not compile-time ones — but it does widen the vocabulary that
   `backend/api.py`'s docstring keeps deliberately minimal, and every op added is
   a three-backend liability. Decide whether a padded `window_add` replaces the
   current one or joins it.
2. **Does `derivative_bases` have to move too?** `CompiledModel.derivative_bases`
   carries the *same* per-reflection loop and hands ragged per-reflection entries
   to `_peak_chain_column` / `_axial_column` in `optimize/least_squares.py`. It is
   also the dominant cost — the numpy Jacobian is 13-23 ms against a 2-5 ms
   forward — so **batching only the forward captures a minority of the win**, and
   batching both means changing the entries contract that three call sites read.
3. **What guards the numerics?** `tests/test_backend_shim.py` asserts
   **bit-identity** against six goldens in `tests/data/backend_goldens/`.
   Reordering an accumulation changes the last bits. State up front whether the
   batched path is expected to be bit-identical (achievable if per-window
   accumulation order is preserved — a scatter-add over disjoint windows is, a
   fused reduction is not) or whether it needs a re-baseline per
   `tests/data/README.md`. The second is a far larger claim and should not be
   discovered halfway through Phase 2.
4. **Is the stage-scoped FCJ cache (task 0) a cheaper substitute, or a
   complement?** The two optimisations attack the same 48 % from opposite ends:
   caching removes *calls*, batching makes the surviving calls *cheaper*. They
   compose — whole-fit ceilings are ≈1.3× (cache), ≈1.4× (batch), ≈1.6× (both),
   against the 1.25× Amdahl ceiling on anything solver work could ever contribute
   ([../solver-survey.md](../solver-survey.md) §0.1) — but they are wildly
   asymmetric in risk. Caching changes no accumulation order, adds no backend op,
   and needs no golden re-baseline; batching touches the most invariant-dense
   loop in the package and raises all three questions above. **The go/no-go must
   state whether the ≈1.2× that batching adds *on top of* caching justifies
   Phase 2**, because that — not the headline 2.4×-at-fixed-work figure — is what
   Phase 2 actually buys once task 0 has landed.

### Answers (2026-07-28, measured)

Sources: `examples/bench_batched_peak_loop.py`, the task-0 commit, and the
post-task-0 cProfile of the SRM 660c protocol.

1. **`window_add` survives, and the op set does not have to grow.** The batched
   scatter is already in the vocabulary: `segment_sum` (WP-0401) *is* the padded
   scatter — numpy `bincount(weights=…)`, jax `segment_sum`, torch `index_add` —
   and the prototype's numpy path is exactly a `bincount` over compile-frozen
   flat indices. The padded gather is plain integer-array indexing on frozen
   (R, W) index planes, which every backend's `__getitem__` supports natively.
   So the three-backend-liability argument against batching dissolves; nothing
   in `backend/api.py` would need to change, and `window_add` keeps serving the
   loop. (Frozen-per-stage intent is preserved either way: the flattened index
   plane is computed at stage compile and is never data-dependent.)

2. **Yes — `derivative_bases` has to move too, and it is most of the surface.**
   Measured on the bench states, the bases cost ~2× the forward (NAC: 3.43 vs
   1.92 ms; corundum: 7.28 vs 3.11 ms), and in the whole-fit profile the
   `derivative_bases` subtree is ~40 % against ~20 % for residual evaluation —
   so batching only the forward touches under a third of the addressable cost.
   Batching the bases changes the ragged `entries` contract read by
   `_peak_chain_column` / `_structural_column` / `_axial_column` /
   `_po_column` / `_pawley_intensity_columns` *and* by `report/layer1.py` /
   `report/texture.py` — seven consumers, not the three the question guessed.
   That contract change, not the kernel arithmetic, is Phase 2's real work. (Task 0's
   `axial_derivs` flag already bent that contract compatibly: ∂Ω/∂sl, ∂Ω/∂hl
   are now optional, and every consumer already None-checked them.)

3. **Split verdict, now measured rather than argued.** Symmetric-row batching is
   **exactly bit-identical**: on NAC, every numpy layout (pad / bucket / chunked)
   returns `np.array_equal(y, y_loop) == True`, because the `bincount` scatter
   accumulates each output point in the loop's own (line, reflection) order and
   the elementwise expressions are unchanged — the six goldens would survive
   with no re-baseline. FCJ rows are **not** bit-identical (max rel 2e-16): the
   node-weighted mix is a batched `matmul` where the loop runs one dgemv per
   reflection, and BLAS does not reduce the two identically. A Phase 2 that
   included FCJ would therefore owe the `tests/data/README.md` re-baseline
   ritual; one that stopped at symmetric rows would not. This asymmetry is the
   strongest single argument for the narrow scope — and half of why the broad
   scope is refused.

4. **The measured sizes invert the WP's estimates, and that decides the
   go/no-go.** The stage-scoped dirty flag *as specified* is ≈1.0× on the
   shipped protocols — the staged plans free parameters **cumulatively**
   (strategy/staged.py), so after `disp` every stage carries a position mover
   and the flag never clears; the 91-97 % standalone-stage fractions above do
   not transfer to the chained fit. What does transfer is within-iteration
   redundancy (residual and Jacobian at the same θ; FD steps of non-position
   parameters), which the shipped **input-equality memo** captures wherever it
   occurs — plus the discovery that two of the three per-iterate node-FD
   variants (∂Ω/∂sl, ∂Ω/∂hl) were computed and discarded in every stage that
   does not free an axial parameter. Together: **1.23× (660c) / 1.04×
   (corundum) whole-fit, bit-identical, zero realized risk, in production.**
   Batching's remaining add on top of that: the forward batches at 1.55-1.6×
   only where symmetric, 0.58-1.15× where FCJ, and the bases must move too
   (answer 2) to reach the larger half — composite ≈1.1× on lab/FCJ data,
   ≈1.2-1.25× on synchrotron/symmetric, i.e. **at or below the ≈1.2× bar this
   question set**, while carrying every risk answers 1-3 name. Not worth it.

## Acceptance

```sh
.venv/bin/python examples/bench_torch_mps.py   # the looped-vs-batched table this WP acts on
```

A go/no-go recorded in the handover log naming: the measured numpy speedup on
NAC *and* corundum (the FCJ case is the one at risk), the memory ceiling and the
chosen mitigation, the **task-0 cache result measured separately** so the two
wins can be told apart, and a written answer to each of the four questions. **No
production code changes in this WP** — if the prototype lands anywhere it is in
a test or a scratch example. (Task 0 is the one candidate that could reasonably
graduate to production inside this WP rather than Phase 2, since it is additive
and golden-preserving — but that is a decision to record, not to assume.)

## References

- `examples/bench_torch_mps.py` — the dispatch-cost and looped-vs-batched
  microbenchmarks this WP is built on.
- [../DESIGN.md](../DESIGN.md#locked-decisions) — the dated 2026-07-27
  measurements, including why this is not a GPU story.
- `tests/data/README.md` — the golden re-baseline rule, if question 3 needs it.

## Handover log

- **2026-07-28 (close)** — all five tasks done in one session; the WP closes
  **no-go on the batched rewrite**, with task 0 graduated to production. The
  numbers behind both halves of that sentence (best of 3, Apple-silicon Mac):

  *Task 0, measured in three steps so the mechanisms can be told apart.* The
  dirty flag as specified: 1.02× on the SRM 660c protocol, 1.00× on corundum —
  refuted by the discovery that the staged plans free **cumulatively**, so
  after `disp` no stage is ever position-static again. Reshaped into an
  input-equality memo (each (line, reflection, variant) slot reuses its nodes
  iff the exact (2θ, S/L, H/L) recur — no hashing, no staleness assumption,
  numpy-gated so traces neither deposit tracers nor constant-fold): 1.06× /
  1.04×. Plus the `axial_derivs` skip (the ∂Ω/∂sl, ∂Ω/∂hl node-FD bases feed
  only the axial Jacobian columns, so `_make_jacobian` now requests them only
  when an axial parameter is free): **1.737 → 1.411 s (1.23×) on SRM 660c,
  33 420 → 16 560 FCJ calls; corundum 1.04×** (its FCJ exists only from
  `lines_axial` on, where axial *is* free and the variants are needed). Both
  protocols reproduce Rwp and every reported parameter to the last bit;
  goldens, FCJ unit tests, fast suite (873) and the slow SRM 660c acceptance
  all green. Corundum's 1.04× is the honest denominator for "what caching
  buys on lab data whose FCJ stages refine axial parameters".

  *The batched prototype* (`examples/bench_batched_peak_loop.py`, shipped path
  untouched): symmetric (NAC) 1.55-1.6× on numpy and **exactly bit-equal**
  under all three layouts; FCJ (corundum) **pad 0.58× — a regression** —
  chunked 0.63×, bucket-by-node-count 1.15×, agreement 2e-16 but not
  bit-equal. torch-CPU 1.92× / 0.99×; MPS 0.55× both states (below WP-0408's
  break-even, as predicted). Pad plane 8.5 MB on corundum today, 614 MB on the
  extrapolated large problem, bounded to 39 MB by chunk=256 — memory is
  solvable, it is the *time* that isn't: the ~2.5× node-axis padding waste
  (counts 8-29 padded to 28 images) eats the kernel-count win exactly as the
  WP-0408 table feared.

  *The go/no-go, in one paragraph.* Phase 2 was to be justified by what
  batching adds **on top of** task 0 (design question 4). Measured: ≈1.1× on
  lab/FCJ data, ≈1.2-1.25× on synchrotron/symmetric — and only if
  `derivative_bases` (2× the forward, five ragged-contract consumers) is
  batched along with the forward, with a golden re-baseline owed the moment
  FCJ rows are included (answer 3). Against that stands what this session
  landed for ~80 lines: 1.23× on the FCJ-heaviest protocol, bit-identical,
  no contract changes. **No-go; no Phase-2 WP opened.** What would reopen it,
  should the day come: (a) the v2-fenced `vmap`-batched in-situ series, where
  many patterns share one kernel and the symmetric ≈1.6×/bit-identical result
  here is the starting point, or (b) any future state where forward
  evaluations dominate the fit — neither of which a single-pattern refinement
  reaches. The cheapest win on the page is now elsewhere anyway:
  `generate_reflections` re-derives a bit-identical reflection list in six of
  seven stage compiles (12 % of the fit, visible in the post-task-0 profile),
  which is compile-side and outside this WP.

- **2026-07-28** — profiled the real SRM 660c fit during v0.6 solver scoping and
  added the measurements above, a task 0 and a fourth design question. Two things
  changed for this WP. First, the target narrowed: the cost is not the peak loop
  in general but **`fcj_offsets_weights` specifically, at 48 % of the whole fit**,
  which is the same tensor axis WP-0408 measured as the worst for padding — so
  the prototype should start there rather than with symmetric peaks, or at least
  not stop before reaching it. Second, and more importantly, **53 % of those calls
  are redundant** (91-97 % in stages that free nothing which can move a peak), so
  a stage-scoped cache may capture much of the win at a small fraction of the
  risk. That does not retire the batching question; it changes what batching has
  to justify. Still not started; no code touched.
- **2026-07-27** — created from WP-0408's follow-up measurements. Scoped
  deliberately as a spike: the ≈2.4× numpy win is real and worth having, but the
  code it touches is the most invariant-dense in the package, and the original
  framing of this work (as Apple-GPU enablement) was measured to be wrong before
  any of it was written. Not started.
