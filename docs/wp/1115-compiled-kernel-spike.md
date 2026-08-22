# WP-1115 — compiled-kernel spike (gated: open only if the floor still binds)

Milestone: v1.1 · Status: ✅ 2026-08-22 — gate read **open**, tier shipped
**as the default install** (trigger 17.6 → 8.9 s, cpd-1a 4.2 → 2.2 s); numba
is a core dependency with a soft import and a runtime switch
Depends on: 1112, 1114, 1120 (the gate reads their measured outcomes)

## Goal

**Done.** The gate was read and it is open (§ Gate reading); the compiled peak
kernels landed behind the same interface (`model/compiled.py`,
`model/_kernels_numba.py`) and the packaging question went to the user with
the numbers and came back "default" (§ The decision).

The gate opened on neither mechanism this WP was written around — dispatch and
raggedness are both measured small — but on **fusion and threading**, which is
worth carrying forward: the next person to blame a python-level loop for
dispatch should check that it still is.

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
  The § Gate reading table is the authority on the split, and it is a split
  in two senses: the column seam itself is **57 % plane work and 30 %
  per-reflection scalars** (`phase_peaks` under perturbation), and a plane
  kernel reaches only the first. Three kernels are addressable and they are
  63 % of the fit between them; assuming a whole seam is addressable because
  most of it is, is how this WP's first projection overshot by 1.5×.
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

A rewrite of anything beyond the isolated kernels; a fourth backend; GPU.

~~Making the compiled path the default install.~~ **Withdrawn 2026-08-22 by
the user**, against the priced costs in § Packaging: install weight and the
numpy pin are both acceptable on the reading that this runs in per-project
virtual environments. § The decision has what shipped.

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
- [x] **Prototype the column-assembly seam before committing to packaging** —
      the user's call on 2026-08-22, and it was the right one: the seam is
      only 57 % plane work, so the first projection (which assumed it fused
      like the bases) read 3.22× where the measured answer is 2.15×. The
      fused scatter itself is **bit-identical** at 6.9–7.1×.
- [x] **Price shipping it by default, and the ways to cut the JIT cost** —
      § Packaging and § Reducing the JIT cost. The startup objection is
      largely solvable (nogil + thread pool caches *and* beats prange); the
      +157 MB and the `numpy<2.6` ceiling are not.
- [x] **Packaging decision — the user's, 2026-08-22: ship it as the default.**
      Install weight and the numpy pin are both acceptable ("these should run
      in venvs"). The requested `rietx[slow]` shape is **not expressible** and
      the substitute is a runtime knob — § The decision has both.
- [x] **Build it on the `nogil` + thread-pool shape, not `prange`** — measured
      faster *and* cacheable. `model/compiled.py` (the tier, the fallback, the
      switch, the pool, the warm) and `model/_kernels_numba.py` (the
      arithmetic); dispatch in `accumulate_planes`, `_omega_batch` and
      `derivative_bases`; `NUMBA_CACHE_DIR` defaulted into the state dir;
      `compile_model` fires the background warm.
- [x] Report the tier through `capabilities()`, and document the knob in the
      manual and `AGENT_PROTOCOL.md` — two derived flags
      (`compiled_kernels` / `…_active`), `using/install.md`
      § The compiled kernels, AGENT_PROTOCOL § 7e.
- [x] `pyproject`: numba into the core dependencies, floored at 0.63.

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
| residual (forward) | 372 | 3.721 | 10.0 | 21.8 % |
| jacobian: bases | 290 | 5.833 | 20.1 | 34.1 % |
| jacobian: columns | 289 | 6.317 | 21.9 | 37.0 % |
| — of which plane accumulation | 9 788 | 3.630 | 0.37 | 21.2 % |
| — of which perturbed `phase_peaks` | 15 608 | 1.911 | 0.12 | 11.2 % |
| `compile_model` | 8 | 0.175 | 21.9 | 1.0 % |
| scipy TRF + staged runner | | 1.049 | | 6.1 % |

**The column seam is two unlike things and only 57 % of it is plane work.**
A column's perturbed `phase_peaks` is per-reflection scalars — positions,
widths, structure factors under WP-1109's scalar-chain memo — and no plane
kernel reaches it. Splitting the seam is what stopped this WP promising a
factor it could not deliver: the first draft of the projection below assumed
the whole 37 % fused like the bases and read 3.22×.

**93 % of the fit is peak-plane arithmetic**, and after 1120 batched the
forward the **Jacobian is 71 % of it**. Not evaluation count, not the
solver's linear algebra (scipy's `_svd` is 0.64 s of a profiled 19.8 s run),
not compile. So the gate opens — but on a mechanism neither of the two it
was written around.

**What a compiled kernel buys, measured** (`examples/bench_compiled_kernel.py`,
trigger at its starting model, node generation excluded from both paths):

| kernel | numpy | numba 1 thread | serial | best threaded | agreement |
|---|---|---|---|---|---|
| forward (Ω + window scatter) | 7.31 ms, 6.5 ns/el | 3.1–3.5 ms, 2.8–3.1 | **2.1–2.4×** | **3.9×** at 4 threads | ≤ 1.7e-16 |
| bases (Ω + 3 partials, node-mixed) | 15.2 ms, 13.5 ns/el | 4.5 ms, 4.0 | **3.2–3.4×** | **11.2×** at 10 threads | ≤ 4.2e-16 |
| column accumulation | 0.372 ms/call, 2.3 ns/el | 0.054 ms, 0.33 | **6.9–7.1×** | not measured | **bit-identical** |

Three things in that table are worth keeping. The profile kernels agree to a
few ulp in-window, the bar WP-1112 set for FCJ rows. The **accumulation
agrees exactly**: `np.bincount` sums its input in order, `accumulate_planes`
lays that input out row-major as (row, term, point), and a serial loop in the
same order reproduces every double — so this one needs no re-baseline
argument at all. And the two profile kernels thread differently for a
structural reason: forward rows scatter into *overlapping* windows, so a
threaded version needs private outputs and a reduction that stops paying past
4 threads (3.92× at 4, 2.64× at 8, 2.21× at 10), while bases rows write
*disjoint* slices and scale to 10.

The accumulation's 6.9× is the largest ratio here and the reason is visible in
`accumulate_planes`: it materialises a (rows, terms, w_max) contrib array
**and** an int64 index array of the same shape (`broadcast_to(...).ravel()`
copies), roughly 15 MB written per call on the trigger before one output point
is touched. The fused loop writes only the output.

**The projection — every term now measured.** The three kernels are
2.72 + 4.41 + 3.63 = **10.76 s of the 17.10 s fit (63 %)**. The rest of each
seam is `phase_peaks`, FCJ node generation, `decode` and the scalar FD chains.

| tier | trigger cold | vs today |
|---|---|---|
| today | 17.1 s | — |
| all three kernels, serial | **9.4 s** | 1.81× |
| all three kernels, profile ones threaded | **8.0 s** | 2.15× |
| + 1113's priced ftol preset flip (1.5–1.7× fewer evaluations) | **≈ 5.0 s** | ≈ 3.4× |

**So the milestone's cold target is still missed by about 2×, and its warm
target is reached.** The same factors put the series' median warm pattern at
≈ 1.5 s threaded and ≈ 1.0 s with the flip — inside the ~1 s band — while
"low single-digit seconds" cold needs something this WP does not have.

Two caveats on the cold row. The threaded numbers are optimistic in a real
fit: the kernels are entered 372 and 290 times for 1.5–3 ms of work each, and
the forward's own ladder already shows per-call thread overhead biting at 8.
And the accumulation is quoted serial, because its scatter overlaps and a
threaded version would pay the same reduction the forward does.

**What the compiled tier would leave behind**, in the 8.0 s residue, and
therefore what the front after it looks like: `phase_peaks` 1.9 s inside the
columns alone (15 608 perturbed calls, per-reflection scalars), the residual
and bases remainders 1.0 + 1.4 s, solver and runner 1.0 s, and the compiled
kernels themselves 1.6 s. The next bottleneck is **not** a plane kernel — it
is how many perturbed `phase_peaks` a Jacobian asks for.

## Packaging — what shipping it *by default* costs a user

Asked on 2026-08-22 and measured rather than estimated (`[dev]` venv,
darwin/arm64). This prices the option the WP's own Non-goals reject; it is
recorded because the rejection should rest on numbers.

| cost | measured |
|---|---|
| install weight | llvmlite **137 MB** + numba **20 MB** = **+157 MB** on a ~124 MB runtime baseline (scipy 83, numpy 25, gemmi 6.6, spglib 6.0, pydantic 3.0) — **2.3× the install** |
| numpy ceiling | numba 0.67.0 requires **`numpy<2.6`** (and `>=1.22`) |
| startup | **1.52 s** cold JIT for the four kernels, **1.25 s** with a populated disk cache |
| short fits | `nac` 0.53 s and `nac-lebail` 0.44–0.48 s today; with a compiled tier plus ~1.2 s startup they become ≈ 1.6 s, i.e. **~3× slower** |
| Python versions | **not a cost**: numba 0.67 resolves on 3.11, 3.12, 3.13 and 3.14, the whole CI matrix, with no numpy downgrade |
| import time | **not a cost**: 0.09–0.28 s against rietx's own 0.79 s |

Two of those deserve their mechanism written down.

**The numpy ceiling is the sharp one and it is permanent.** Today numpy is
2.5.2 so `<2.6` binds nothing, but on the day numpy 2.6 ships, rietx becomes
the package holding a user's environment back until numba catches up. numba
has always carried an upper bound; this is not a version to wait out.

**The disk cache does not remove the startup cost**, which is the part that
was not anticipated. The two `parallel=True` kernels recompile in **every
process** — 0.62 s and 0.38 s, unchanged across three consecutive warm runs,
writing fresh cache entries each time — while the serial kernels cache
properly (the accumulation drops 0.04 s → 0.00 s). So ~1.0 s of the 1.25 s is
`parallel=True`, paid per process. The GUI is long-lived and pays it once;
the CLI one-shot fit and `agent.refine_json` pay it per invocation, which is
exactly the surface where a sub-second fit is the selling point.

## The decision — 2026-08-22: ship it as the default

The user's call, against § Packaging: **numba is a core dependency**. Install
weight is acceptable and so is the numpy ceiling, "as these should run in
venvs". What follows is the shape that decision forced, because the shape the
question asked for does not exist.

**`rietx[slow]` is not expressible, and no rewording of it is.** An extra only
ever *adds* to what plain `rietx` installs; Python packaging has no operator
that removes a dependency, so "fast by default, and installable without the
compiler" cannot be a packaging choice. The alternatives are all worse: two
distributions (the `opencv-python` / `-headless` shape) doubles the release
surface for one dependency, and the additive form — `rietx[speedups]` in
aiohttp's spelling, `rietx[performance]` in pandas' — is exactly the opt-in
option this decision rejects. **So the knob is a runtime one**, which is the
better knob anyway: it needs no reinstall, it can be flipped inside a process,
and it is what keeps the numpy path exercised on a default install rather than
turning it into dead code.

| shape | where |
|---|---|
| required dependency | `pyproject` `dependencies`, `numba>=0.63` — the floor is where numba's wheels first cover every interpreter `requires-python` admits (cp314 from 0.63, cp313 from 0.61) |
| soft import | `model/compiled.py`; every entry point declines rather than raising, so `--no-deps`, a constraint file or a distro package still fits |
| runtime off switch | `RIETX_COMPILED=0` (`_about.COMPILED_ENV`), and `compiled.set_enabled()` inside a process |
| thread count | `RIETX_COMPILED_THREADS` (`_about.COMPILED_THREADS_ENV`); the suite sets it to 1 under `xdist`, where the parallelism is already one rank up |
| reported | `capabilities().features` — `compiled_kernels` (can it be built here) and `compiled_kernels_active` (will the next residual use it), which can disagree |

**Measured after landing**, same harness and machine as § Gate reading
(`[dev]` venv, darwin/arm64, python 3.12.12, numpy 2.5.2, best of 3, idle):

| case | numpy path | compiled | ratio |
|---|---|---|---|
| `trigger` | 17.56-17.83 s | **8.86-8.99 s** | 1.98× |
| `cpd-1a` | 4.22-4.31 s | **2.17-2.21 s** | 1.95× |
| `nac` | 0.54-0.55 s | **0.40-0.41 s** | 1.34× |
| `nac-lebail` | 0.45-0.50 s | 0.32-0.63 s | the 0.63 is a cold JIT |

Rwp agrees to five decimals in all four. `trigger` converges in 358 nfev where
numpy takes 364 — an ulp reaching a trust-region decision, the same thing
WP-1120 recorded at 363 vs 364, and not something to pin.

The projection in § Gate reading said 8.0 s and the measurement says 8.9 s. The
gap is the part of each seam that is not plane arithmetic and does not fuse —
which is the same correction the column seam already forced once, one rank
lower.

**Three findings from building it that the prototype could not have shown.**

1. **Bit-identity was available and the prototype's few-ulp result was an
   artefact of my own transcription.** The two Ω spellings differ in exactly
   one association — the forward computes `-4ln2·(x/Γ)²`, the bases
   `((-4ln2)·u)·u` — and the Lorentzian is common to both, because `(4·u)·u`
   and `4·(u·u)` are bit-equal (multiplying by a power of two is exact).
   Transcribe each faithfully and numba's `math.exp` agrees with numpy's `exp`
   bit for bit here, so symmetric rows land on the same doubles in window. FCJ
   rows still differ at ≤ 4e-16 — a sequential node sum against `_node_mix`'s
   matmul — which is WP-1112's bar, not a new one.
2. **Declining while the background compile runs is the wrong shape.** It was
   the first one here: a residual that arrived before the kernels were ready
   ran numpy, a later one ran the kernels. That makes which path an evaluation
   took a function of how fast the machine compiled — different last digits on
   two runs of the same script, and through a trust-region decision an
   occasional different iteration count. It now blocks. One path per process is
   worth the few hundred milliseconds, and `warm()` has already overlapped most
   of them.
3. **A test that pins a number must declare which path it is on**, exactly as
   CLAUDE.md already requires for the dispersion default. `test_backend_shim`'s
   pre-shim goldens are numpy bit patterns and now say so; a new parametrised
   row captures the same states through the kernels and holds them to the
   1e-13 rounding bar, so the tier's cost to those numbers is recorded rather
   than absorbed.

## Reducing the JIT cost

Four strategies measured, three of them effective, and together they change
the startup arithmetic enough to matter to the decision above.

1. **Replace `parallel=True` with a serial `nogil` kernel on a Python thread
   pool** (`bench_compiled_kernel.py --nogil`). This is the large one and it
   costs nothing: the kernel **caches** (0.28 s first process → **0.06 s**
   thereafter) *and* it is **faster** than the prange twin — 1.23 ms at 8
   threads against prange's best 1.36 ms, i.e. **12.3× vs numpy's 15.2 ms**
   where prange managed 11.2×. `nogil=True` releases the GIL for the call, so
   a shared `ThreadPoolExecutor` over row ranges gets the parallelism that
   numba's parfor machinery was being compiled for. Use a **shared** pool: a
   fresh `ThreadPoolExecutor` per call costs 6.0 → 2.8 ms of the win.
2. **Warm the kernels on a background thread at import or session start.**
   numba compilation **releases the GIL and overlaps essentially completely**
   with numpy work: measured across separate processes, serial 0.96–0.97 s
   against threaded 0.63–0.66 s, hiding the whole 0.33 s payload. So whatever
   JIT survives (1) can hide behind the file read, CIF parse, `ParameterTable`
   build and `compile_model` a fit does anyway.
3. **Redirect the cache to somewhere writable.** numba honours
   `NUMBA_CACHE_DIR` (verified: entries land in the redirected directory).
   The default location is beside the source, i.e. inside `site-packages`,
   which is read-only in plenty of real installs (system Python, containers,
   Nix) — and an unwritable cache silently means recompiling every process.
   A shipped tier should point this at a user cache directory itself.
4. **numba's own AOT is not the answer.** `numba.pycc` still exists in 0.67
   but is legacy and raises without setuptools present at runtime. Genuine
   AOT means a Cython or C extension compiled into the wheel: zero startup,
   threading via OpenMP, at the price of per-platform wheels in CI and a
   toolchain for sdist installs. **This reverses task 3's conclusion for the
   default-dependency option specifically** — "Cython not needed" was reached
   against the *opt-in* option, where a long job amortises the JIT.

Not yet measured, and worth trying before any decision is final:

- **Explicit signatures** on each `njit`, which make cache hits deterministic
  and stop per-layout respecialisation. There is a symptom pointing at churn:
  `.nbc` entries accumulated on every run of the prange kernels rather than
  being reused.
- **Size-thresholded dispatch** — run numpy below a work threshold so a small
  fit never triggers a compile at all. `nac` at 0.53 s is precisely the case
  that regresses, and the harness already says where the crossover is.
- **UI**: say what the pause is ("compiling accelerated kernels, first run
  only"), and/or a `rietx warmup` command and a GUI first-launch warm, so the
  cost is paid once, visibly, at a moment nobody is waiting on a fit.

Taken together, (1) + (2) + (3) take warm startup from ~1.25 s to ~0.06 s
with most of the remainder hideable, which removes the short-fit regression
entirely. They do **not** touch the +157 MB or the `numpy<2.6` ceiling, and
those two are the whole case against default-on.

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py                 # the landed tier
RIETX_COMPILED=0 .venv/bin/python examples/bench_refinement.py   # …and without it
.venv/bin/python -m pytest tests/test_compiled_kernels.py     # the bars and the contract
.venv/bin/python examples/bench_compiled_kernel.py            # the profile kernels
.venv/bin/python examples/bench_compiled_kernel.py --accum    # the column scatter
.venv/bin/python examples/bench_compiled_kernel.py --nogil    # cache + threads (run TWICE)
.venv/bin/python examples/bench_compiled_kernel.py --seams    # the shares they sit in
.venv/bin/python -m pytest -n auto --dist loadgroup           # full: the tier moves numbers
.venv/bin/python -m ruff check src tests examples
```

The two harness runs are the before/after, quoted as ranges with venv and
platform (§ The decision). The full suite rather than the fast selection,
because a change to the residual's arithmetic can move an acceptance number
and the fast selection would not see it.

## References

- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 210–218 §5.2 — the
  threading numbers the GIL currently denies.
- WP-0605's file — the padding measurements that made raggedness the
  compiled path's original case, now measured at 1.11× and superseded.

## Handover log

- **2026-08-22 (closing)** — The tier is built, it is what a default install
  runs, and a four-phase lab-shaped refinement that took 17.6 seconds this
  morning takes 8.9. The user answered the question that was blocking: install
  weight and numba's numpy ceiling are both acceptable, because this runs in
  per-project virtual environments. They also asked for a `rietx[slow]` for
  anyone who cannot take the dependency, and that shape does not exist —
  Python extras only ever *add* to what a plain install brings, so "fast by
  default, still installable without the compiler" cannot be expressed in
  packaging at all. It is expressible in code, and better there: the import is
  soft, every kernel keeps the numpy expression standing behind it, and
  `RIETX_COMPILED=0` turns the tier off without a reinstall. A real fit in a
  venv with no numba at all was run to prove it rather than to assert it, and
  it returns the same Rwp and the same cell, with the esd differing in its last
  bit.

  What the WP was written to compile is not what got compiled. It was filed
  against python dispatch and ragged loops; both were measured small by the
  gate (dispatch gone since 1112/1120, raggedness 1.11×), and the two real
  levers were fusion and threading. The kernels therefore fuse the plane
  arithmetic and run it on a shared thread pool, and the whole gain is that
  numpy writes a dozen full-size temporaries per profile call where a fused
  loop touches the grid once.

  The most useful correction of the session is about my own prototype rather
  than about numpy. The spike reported the profile kernels as "a few ulp" from
  the numpy path, and I carried that into the WP as a re-baseline that would
  have to be accepted. It was wrong: the deviation was in the prototype's
  transcription, not in compiling. The two Ω spellings WP-1120 found differ in
  a single association — the forward `-4ln2·(x/Γ)²`, the bases `((-4ln2)·u)·u`
  — and the Lorentzian is common to both because multiplying by a power of two
  is exact. Transcribe each faithfully and numba's `math.exp` matches numpy's
  bit for bit here, so symmetric rows land on identical doubles in window and
  the accumulation is bit-identical outright. The lesson generalises past this
  WP: **a prototype's agreement number measures the prototype**, and quoting
  one as a property of the technique is how a real re-baseline gets invented.

  Working detail, in the order it will matter to a successor.

  1. **`prange` is the wrong shape twice over** and this is the finding most
     likely to be re-hit by anyone adding a fourth kernel. It refuses to cache,
     so ~1 s recompiles in every process, *and* it is slower than the
     alternative. Serial `njit(cache=True, nogil=True)` over a row range,
     driven from a shared `ThreadPoolExecutor`, caches (0.60 s cold, 0.12 s
     reload) and reaches 12.3× where `prange` reached 11.2×. The pool must be
     shared — one per call costs more than half the win.
  2. **Declining while the compile runs was the wrong semantics.** The first
     shape here took the lock non-blockingly so a residual arriving early ran
     numpy and a later one ran the kernels. That makes the path an evaluation
     took a function of how fast the machine compiled: different last digits on
     two runs of the same script, and through a trust-region decision an
     occasional different iteration count. It blocks now. One path per process.
  3. **The disk cache landed beside the source for one commit.** numba reads
     `NUMBA_CACHE_DIR` when it is *imported*, once, and `available()` imports
     numba to answer its question — before `_kernels()` set the variable. On a
     dev checkout that works perfectly, which is exactly where nobody notices;
     in an ordinary install `site-packages` is read-only often enough to matter
     and an unwritable cache recompiles in every process saying nothing. It was
     found by counting the cached files, not by timing, and the guard added for
     it counts them in a subprocess because the property is an import ordering.
     `_redirect_cache` now covers both orders.
  4. **A test that pins a number must declare its path.** CLAUDE.md already
     says this for the dispersion default; the compiled tier is the second
     default it applies to, and `test_backend_shim`'s goldens were the thing
     that noticed — they failed under `-n auto` and passed alone, which is the
     signature of a background compile finishing at different points. They now
     capture the numpy expressions explicitly, and a new parametrised row holds
     the kernels to the 1e-13 bar against the same files.
  5. **The projection over-read by 11 %**: § Gate reading said 8.0 s and the
     measurement says 8.9. Same correction the column seam already forced once
     — the part of a seam that is not plane arithmetic does not fuse.
  6. **Numbers this session, all `[dev]` venv, darwin/arm64, python 3.12.12,
     numpy 2.5.2, numba 0.67.0.** Fast suite 2607 passed / 117 skipped, up from
     WP-1120's 2591 by exactly the 16 tests added (3 golden rows, 13 in
     `test_compiled_kernels.py`); fast wall 1:57–2:06. Harness best-of-3 in
     § The decision. Cold JIT 0.601 s, cached reload 0.123 s, `import rietx`
     unchanged at 0.52 s.

  **Next.** The cold target is still missed by about 2×, and the front is no
  longer a plane kernel: it is the **15 608 perturbed `phase_peaks` calls** a
  trigger Jacobian asks for (§ Gate reading has the decomposition), which is a
  per-reflection scalar cost and wants either fewer columns or a cheaper
  perturbation, not a faster plane. WP-1113's priced preset flip is worth about
  another 1.5–1.7× on evaluation count and is still unflipped. Three
  mitigations in § Reducing the JIT cost remain unmeasured — explicit `njit`
  signatures, size-thresholded dispatch below which a small fit never compiles,
  and a `rietx warmup` command — none of them blocking, all of them cheap.
  Anyone adding a kernel: `model/_kernels_numba.py`'s docstring states the one
  review question, which is not "is this the right formula" but "is this the
  same rounding as the numpy line it copies".

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

  Asked which way to go, the user chose to measure the third seam before
  deciding anything about packaging, and that call changed the answer. The
  column assembly had been projected to fuse like the others; measured, it
  turns out to be only 57 % plane work — the other 30 % is a perturbed
  `phase_peaks` per column, per-reflection scalar arithmetic no plane kernel
  can touch. The part that *is* plane work fuses better than anything else
  here, 6.9×, and exactly: it reproduces `np.bincount`'s own summation order,
  so every double comes back identical. Net, a full compiled tier takes the
  cold fit from 17 s to about 8, and to about 5 alongside the evaluation-count
  work already priced in WP-1113 — which reaches the milestone's warm-series
  target and still misses its cold one by roughly a factor of two.

  **Done.** Tasks 1, 2, 4 and the column-seam measurement; task 3 (a Cython
  fallback) is resolved as not needed rather than skipped — numba was
  disqualified on neither count the WP named.
  `examples/bench_compiled_kernel.py` is the landed evidence, three modes:
  the default benches the two profile kernels with a thread ladder,
  `--accum` benches the column scatter on `parts` captured from a real fit,
  and `--seams` decomposes a real cold fit into the shares all of it must be
  weighed against. Nothing under `src/` changed, so no answer moved.

  **Measured** (`[dev]` venv **plus numba 0.67.0 / llvmlite 0.49.0 installed
  for the spike**, darwin/arm64; numpy stayed at 2.5.2). Fast suite 2591
  passed / 117 skipped — unmoved, which is the point: this session added a
  benchmark, not a code path. Harness: trigger 17.51–17.68 s, trigger-series
  1.39–9.52 s/pattern. Everything else is in § Gate reading.

  **Gotchas for the successor.** (1) The machine was not idle for part of
  this session and single-run totals wandered between 17.1 s and 29.8 s for
  the *same* fit; the seam **shares** held to within 0.8 pp throughout, so
  quote shares, and take absolute wall clock only from a tight harness band.
  (1b) Compile timings must be compared **across processes**: compiling the
  same kernel twice in one process is cheaper the second time because LLVM is
  already initialised, and an in-process A/B silently reports a 43 % "overlap"
  that is nothing of the kind. The GIL-overlap number above was re-measured
  as two separate runs for exactly this reason. (2) A
  fused kernel and the numpy planes must be compared **in-window only** —
  numpy's padded tail carries the clipped duplicate that `BatchLayout.mask`
  zeroes downstream, and comparing it reports a 0.9 relative "disagreement"
  that is not one. This cost a wrong-looking result before it was spotted.
  (3) `fcj_offsets_weights_batch` returns `2·max(n//2, 4)` images for a
  bucket keyed `n`, **not** `n`; read the count off the returned array.
  (4) Capture benchmark inputs **evenly across a fit**, never from its head:
  the first `accumulate_planes` calls come from `scale_bkg`, one phase and
  one term, and timing those flattered the fused scatter by 5× against the
  fit's own average before the sampling was fixed. (5) A seam is not
  addressable just because most of it is — splitting the column seam moved
  the headline from 3.22× to 2.15×.

  **Then the packaging question was priced** (§ Packaging, § Reducing the JIT
  cost), because the decision should not rest on an estimate either. Shipping
  the tier as a default dependency costs a user +157 MB — llvmlite alone is
  137 MB against a ~124 MB runtime baseline — a permanent `numpy<2.6`
  ceiling, and about 1.2 s of startup per process. The startup was the
  surprise: it does **not** go away with the disk cache, because the two
  `parallel=True` kernels recompile in every process while the serial ones
  cache properly. At that cost the small cases go backwards: `nac` fits in
  0.53 s today and would take about 1.6 s.
  
  That objection then turned out to be mostly self-inflicted. Rewriting the
  bases kernel as a *serial* `nogil` kernel driven from a shared
  `ThreadPoolExecutor` caches (0.28 s once, 0.06 s thereafter) and is
  **faster** than the `prange` version it replaces — 12.3× against numpy
  where prange managed 11.2×. Compilation also releases the GIL, so whatever
  remains hides behind the file read and model compile a fit does anyway
  (measured: 0.96 s serial against 0.63 s overlapped). What none of that
  touches is the install weight and the numpy ceiling, and those are the
  whole case against default-on.

  **Next**: the packaging decision is the user's and is the one thing
  blocking; it is now decidable against a projection with no estimated terms
  and a priced startup cost. If it is a go, all three kernels are worth
  wiring (63 % of the fit between them) — behind a `[speed]` extra, on the
  **`nogil` + thread-pool shape rather than `prange`**, with the conformance
  suite diffing against the numpy path and the accumulation held to
  *bit*-identity rather than a re-baseline. If it is a no-go, 1115 closes 🛑
  with this file's tables. Either way the front after a compiled tier is
  **not** another plane kernel: it is the 15 608 perturbed `phase_peaks`
  calls a trigger Jacobian asks for.

- **2026-08-20** — created by the 1109 review session, deliberately gated;
  the gate is the first task, and closing 🛑 because the targets are already
  met is the good outcome.
