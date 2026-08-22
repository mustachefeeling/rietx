# WP-1115 — compiled-kernel spike (gated: open only if the floor still binds)

Milestone: v1.1 · Status: 🔄 2026-08-22 — gate read **open**; both kernels
prototyped and measured, packaging decision outstanding
Depends on: 1112, 1114, 1120 (the gate reads their measured outcomes)

## Goal

**The gate is read and it is open** (§ Gate reading). What remains is the
decision the spike exists to inform: a compiled version of the peak kernel —
numba, measured — behind the same interface, and a packaging decision
(optional extra, never a core dependency) put to the user with the numbers.

## Context

- **Why a compiled kernel was the third resort** (the 2026-08-20 review's
  language-gap decomposition, recorded in 1109/v1.1.md): python's cost is
  ~0.6 µs dispatch per numpy call plus interpreter overhead per line — huge
  for the pre-1112 per-reflection loop, where ≈11 µs of a 13.6 µs kernel call
  was dispatch. **1112 and 1120 removed that**, and this WP's gate measured
  what is left. Two of the three mechanisms the review named are now
  measured *small* and must not be re-argued: **dispatch** (the surviving
  kernel calls are 200–400 µs each on ~10⁵-element planes) and **ragged
  axes** (`BatchLayout` buckets by node count, so only the window axis pads,
  at an evaluation-weighted **1.11×** over the whole node × window volume —
  not the ~2× WP-1114 inherited). The third stands: **threading**, which the
  GIL denies a numpy-level python loop entirely (Coelho 2018 §5.2).
- **The mechanism the gate actually found is fusion.** `pseudo_voigt`
  materialises about a dozen full-size temporaries per call and
  `pseudo_voigt_derivs` more, each a write and a read of a
  (rows, nodes, window) plane, and numpy cannot keep any of them in
  registers. A fused loop touches the grid once. This, not raggedness, is
  what the measured 2.1–3.4× serial ratios are made of.
- **What to compile is no longer only the forward.** After 1120 the forward
  is 22 % of the trigger cold fit and the **Jacobian is 71 %** — 34 %
  `derivative_bases`, 37 % the column assembly that consumes its planes.
  A compiled tier that stops at the forward buys ~1.1× on the whole fit.
  The § Gate reading table is the authority on the split.
- **The three-backend rule still binds** (CLAUDE.md Conventions): the
  compiled path is a *numpy-path accelerator*, not a fourth backend — jax and
  torch keep the traced twin (`backend/traced.py`), and the compiled kernel
  must reproduce the numpy path bit-identically or carry the re-baseline
  argument, exactly as 1112's and 1120's scopes do. Measured for both
  prototypes: **a few ulp** (≤ 4.2e-16 relative), the bar 1112 set for FCJ
  rows.
- **The profile spelling is part of the contract** (1120's finding, now a
  root CLAUDE.md rule): the forward kernel must reproduce `pseudo_voigt` and
  the bases kernel `_components`, which are deliberately 1–2 ulp apart. A
  fused kernel that borrowed the other one would move every converged fit.
- **Packaging reality check, now measured rather than feared**: numba 0.67.0
  + llvmlite 0.49.0 resolve and install against this tree's numpy 2.5.2 with
  **no numpy downgrade** (`uv pip install --dry-run numba`), and a cold JIT
  of the forward kernel is **0.20 s** with `cache=True` writing `.nbi`/`.nbc`
  beside the source, so later processes reload. The default install must
  still work without it (`[speed]` extra shape, like `[jax]`/`[torch]`).
- **The peaks buffer composes with a compiled substrate and its design is
  done** (WP-1114's design note + § Findings): K ≤ 32 anchors per width
  family reproduce every shape at 1e-4, and that spike's no-go was the numpy
  per-element floor, not the physics. If a compiled *exact* kernel lands and
  still misses, a compiled *buffer* is the follow-on with the larger
  algorithmic ceiling (7.8–9× element volume on FCJ-heavy cases) — 1114
  § Findings 3–4 list the three accuracy traps and the cache-keying bug any
  implementation re-hits first.
- **Fences already measured elsewhere, do not re-open**: GPU execution
  (46–182× slower, launch-latency-bound — v0.4 record); `torch.compile`
  (2.5× slower after 38 s, dynamo specialises per window — 0605);
  `tr_solver='lsmr'` and friends (solver-survey §2 dead ends).

## Non-goals

A rewrite of anything beyond the isolated kernels; a fourth backend; GPU;
making the compiled path the default install.

## Tasks

- [x] **Check the gate** against the 1111 harness with 1112/1114/1120
      outcomes in hand; record the reading here (§ Gate reading — **open**).
- [x] numba prototype of the ragged kernel (serial first, then `prange`);
      bit-identity or recorded deviation vs the numpy path; wall on the
      trigger-shaped case. `examples/bench_compiled_kernel.py`, both the
      forward and the derivative-bases kernel, agreeing to a few ulp.
- [x] Fallback prototype (Cython or C extension) — **not needed**: numba is
      not disqualified on either count the WP named. It installs against the
      current numpy without moving it, and it wins 2.1–3.4× serial.
- [x] Thread-scaling measurement on the kernels — the one axis pure numpy
      cannot reach. 1/2/4/8/10 threads, both kernels (§ Gate reading).
- [ ] Packaging decision with the user: `[speed]` extra vs not shipping;
      conformance-suite wiring for whichever lands.
- [ ] If it ships: the column assembly is the largest seam (37 %) and is the
      only part of the projection this WP did **not** measure.

## Gate reading — 2026-08-22: OPEN

**Clause 1 — the harness still misses the targets.** Measured on this
branch, `[dev]` venv, darwin/arm64, `examples/bench_refinement.py`:

| target | measured | verdict |
|---|---|---|
| cold trigger-shaped fit in low single-digit seconds | **17.51–17.68 s** (best-of-3; nfev 364, njev 289) | miss |
| warm series ~1 s/pattern | **1.39–9.52 s/pattern**, median ≈ 3.3 s (cold 16.21 s; whole 10-pattern series 95.9–106.6 s) | miss |

The two slowest warm patterns (9.52 s, 7.43 s) are the two that escalated to
`warm_staged` — 581 and 305 iterations against 22–57 for the rest. That is
an evaluation-count effect and belongs to 1113's front, not this one.

**Clause 2 — where the remaining time is.** One trigger cold fit,
decomposed at the seams by `examples/bench_compiled_kernel.py --seams`
(wrappers, not cProfile, which inflates exactly the small-array calls this
question is about). Across three runs whose absolute totals differed by 44 %
(17.1, 21.6 and 24.6 s for the same fit, on a machine that was not idle
throughout) every share held to within 0.8 pp — which is why the shares are
quotable here and the absolute seconds are taken from the harness band:

| seam | calls | s | ms/call | share |
|---|---|---|---|---|
| residual (forward) | 372 | 3.729 | 10.0 | 21.8 % |
| jacobian: bases | 290 | 5.831 | 20.1 | 34.1 % |
| jacobian: columns | 289 | 6.312 | 21.8 | 36.9 % |
| `compile_model` | 8 | 0.174 | 21.8 | 1.0 % |
| scipy TRF + staged runner | | 1.045 | | 6.1 % |

**93 % of the fit is peak-plane arithmetic**, and after 1120 batched the
forward the **Jacobian is 71 % of it**. Not evaluation count, not the
solver's linear algebra (scipy's `_svd` is 0.64 s of a profiled 19.8 s run),
not compile. So the gate opens — but on a mechanism neither of the two it
was written around.

**What a compiled kernel buys, measured** (`examples/bench_compiled_kernel.py`,
trigger at its starting model, node generation excluded from both paths):

| kernel | numpy | numba 1 thread | serial | best threaded |
|---|---|---|---|---|
| forward (Ω + window scatter) | 7.31 ms, 6.5 ns/element | 3.1–3.5 ms, 2.8–3.1 | **2.1–2.4×** | **3.9×** at 4 threads |
| bases (Ω + 3 partials, node-mixed) | 15.2 ms, 13.5 ns/element | 4.5 ms, 4.0 | **3.2–3.4×** | **11.2×** at 10 threads |

Agreement is **1.3e-16 to 4.2e-16 relative**, in-window. The two scale
differently for a structural reason worth keeping: forward rows scatter into
*overlapping* windows, so a threaded version needs private outputs and a
reduction, and past 4 threads the reduction costs more than the parallelism
buys (3.92× at 4, 2.64× at 8, 2.21× at 10). Bases rows write *disjoint*
slices, need no reduction, and scale to 10.

**The projection, with its measured and unmeasured halves separated.** The
two prototyped kernels are 2.72 s + 4.40 s = **7.12 s of the 17.09 s fit
(41.7 %)**; the rest of each seam is `phase_peaks`, node generation and the
scalar FD chains.

| tier | trigger cold | vs today |
|---|---|---|
| today | 17.1 s | — |
| the two measured kernels, serial | 12.5 s | 1.36× |
| the two measured kernels, threaded | 11.1 s | 1.55× |
| **+ column assembly at the bases' ratio (projected, not measured)** | 8.1 s serial / **5.3 s threaded** | 2.10× / 3.22× |
| + 1113's priced ftol preset flip (1.5–1.7× fewer evaluations) | **≈ 3.3 s** | ≈ 5.2× |

Two honest caveats on that last column. The 37 % column-assembly seam is
**projected at the bases kernel's ratio and was not prototyped** — it is the
largest single seam and the whole difference between 1.55× and 3.22×. And
the threaded numbers are optimistic in a real fit: the kernel is entered 372
and 290 times for 1.5–3 ms of work each, and the forward's own scaling
already shows per-call thread overhead biting at 8.

**So: a compiled tier reaches the milestone's cold target only if it covers
the column assembly *and* rides 1113's preset flip.** On the warm series the
same factors put the median pattern at ≈ 1.0 s threaded and ≈ 0.65 s with the
flip, which does reach the ~1 s band.

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py     # with/without the compiled path
.venv/bin/python examples/bench_compiled_kernel.py            # the kernel ratios
.venv/bin/python examples/bench_compiled_kernel.py --seams    # the shares they sit in
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

A gate reading recorded in this file either way; if opened, before/after
ranges from the harness and the equivalence bar stated per 1112's pattern.

## References

- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 210–218 §5.2 — the
  threading numbers the GIL currently denies.
- WP-0605's file — the padding measurements that made raggedness the
  compiled path's original case, now measured at 1.11× and superseded.

## Handover log

- **2026-08-22** — The gate this WP was built around is open, but not for
  either of the reasons it was written around. A cold four-phase lab-shaped
  refinement still takes 17 seconds where the milestone wants low single
  digits, and a warm series pattern takes between 1.4 and 9.5 seconds where
  it wants about one, so on wall clock there was never any doubt. The
  interesting half is *where* those seconds are. Two WPs ago the forward
  model was the expensive thing; WP-1120 made it four times faster, and the
  measurement here says the forward is now 22 % of the fit and the Jacobian
  71 %. Inside that, the two mechanisms a compiled kernel was expected to
  cash are both small: the ragged axis costs 11 %, not the ~2× that was
  inherited, and python dispatch is gone. What remains is that numpy cannot
  fuse — every line of the profile function writes a full array to memory and
  reads it back — and that numpy cannot thread. A prototype of both kernels
  in numba confirms it: 2.1–2.4× on the forward, 3.2–3.4× on the derivative
  bases, single-threaded, agreeing with the existing code to a few ulp, and
  up to 11× threaded on the half that has no write conflicts.

  **Done.** Tasks 1, 2 and 4; task 3 (a Cython fallback) is resolved as not
  needed rather than skipped — numba was disqualified on neither count the
  WP named. `examples/bench_compiled_kernel.py` is the landed evidence: the
  default run benches both kernels with a thread-scaling ladder, `--seams`
  decomposes a real cold fit into the shares those ratios must be weighed
  against. Nothing under `src/` changed, so no answer moved.

  **Measured** (`[dev]` venv **plus numba 0.67.0 / llvmlite 0.49.0 installed
  for the spike**, darwin/arm64; numpy stayed at 2.5.2). Fast suite 2591
  passed / 117 skipped — unmoved, which is the point: this session added a
  benchmark, not a code path. Harness: trigger 17.51–17.68 s, trigger-series
  1.39–9.52 s/pattern. Everything else is in § Gate reading.

  **Gotchas for the successor.** (1) The machine was not idle for part of
  this session and single-run totals wandered between 17.1 s and 29.8 s for
  the *same* fit; the seam **shares** held to within 0.8 pp throughout, so
  quote shares, and take absolute wall clock only from a tight harness band. (2) A
  fused kernel and the numpy planes must be compared **in-window only** —
  numpy's padded tail carries the clipped duplicate that `BatchLayout.mask`
  zeroes downstream, and comparing it reports a 0.9 relative "disagreement"
  that is not one. This cost a wrong-looking result before it was spotted.
  (3) `fcj_offsets_weights_batch` returns `2·max(n//2, 4)` images for a
  bucket keyed `n`, **not** `n`; read the count off the returned array.
  (4) The 37 % column-assembly seam is the largest and the only part of the
  projection that was not prototyped — measure it before promising 3.2×.

  **Next**: the packaging decision is the user's and is the one thing
  blocking. If it is a go, prototype the column assembly first (it is the
  difference between 1.55× and 3.22×), then wire the tier behind a `[speed]`
  extra with the conformance suite diffing it against the numpy path.

- **2026-08-20** — created by the 1109 review session, deliberately gated;
  the gate is the first task, and closing 🛑 because the targets are already
  met is the good outcome.
