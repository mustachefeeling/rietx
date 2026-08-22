# WP-1121 — the per-reflection front: what a compiled tier does not reach

Milestone: v1.1 · Status: ✅ 2026-08-22 — the front is measured and named: per-reflection work is dispatch-bound, 20 % of the fit; two changes landed (1.02–1.08×), cold target still missed at 8.7 s and said so
Depends on: 1115 (its gate reading is the decomposition this attacks)

## Goal

v1.1's cold-fit target is still missed. Close the gap, or measure why it
cannot be closed and say so — by attacking the two costs that survive
WP-1115's compiled tier: the **per-reflection scalar work** a Jacobian column
does before any plane is touched, and the **number of evaluations** the plan
asks for.

## Context

**Where the milestone stands.** The acceptance targets are in
`../milestones/v1.1.md` § Acceptance: warm-started series in the ~1 s/pattern
band (**reached**), cold trigger-shaped fit in low single-digit seconds
(**missed** — 8.86–8.99 s after 1115, from a 50 s opening baseline). Quote the
harness, never a remembered figure: `examples/bench_refinement.py`, best of
three, idle machine, venv and platform stamped.

**Why a fifth speed WP is not more of the same.** Every win so far has been on
*plane arithmetic* — 1112 batched the derivative bases, 1120 the residual, 1115
fused and threaded all three kernels. That seam is now ~2× off its numpy floor
and there is no third factor in it. What remains is a different shape of work,
and it is the reason this WP exists rather than a sixth kernel.

**The decomposition, measured before the tier landed** (1115 § Gate reading;
trigger cold fit, 17.1 s, shares stable to 0.8 pp across three runs at
different machine loads):

| seam | calls | s | ms/call | share |
|---|---|---|---|---|
| residual (forward) | 372 | 3.721 | 10.0 | 21.8 % |
| jacobian: bases | 290 | 5.833 | 20.1 | 34.1 % |
| jacobian: columns | 289 | 6.317 | 21.9 | 37.0 % |
| — of which plane accumulation | 9 788 | 3.630 | 0.37 | 21.2 % |
| — **of which perturbed `phase_peaks`** | **15 608** | **1.911** | **0.12** | **11.2 %** |
| `compile_model` | 8 | 0.175 | 21.9 | 1.0 % |
| scipy TRF + staged runner | | 1.049 | | 6.1 % |

**Those shares are stale in a specific and favourable-to-this-WP direction.**
1115 compiled the three plane rows and left the `phase_peaks` row untouched, so
its *absolute* 1.9 s is unchanged while the fit went 17.1 → 8.9 s. Its share
roughly doubles, to ~21 %, and it becomes the largest single line item that is
not plane arithmetic. **Re-measure before designing anything** — that is task 1,
and the number above is the "before", not the current state.

**What the cost actually is.** `_peak_chain_column` (`optimize/least_squares.py`)
perturbs θ_c, decodes, and calls `CompiledModel.phase_peaks` for every phase the
column touches, to finite-difference the per-reflection scalars — position,
the two widths, intensity. That is per-*reflection* work: no plane kernel
reaches it, and 1115's first projection over-read by 1.5× precisely because it
assumed the whole column seam fused like the bases.

**Three leads, none of them verified — the first task after re-measuring is to
falsify them, not to implement them.**

1. **The scalar memo is one deep.** `CompiledModel._memo` /
   `CompiledPhase.scalar_cache` holds `cache[slot] = (key, value)` — a single
   key per slot, not a map. A Jacobian walks columns in θ order, so any
   alternation between two keys evicts on every call and the memo returns
   nothing while still paying for the key build. Whether the column order
   actually alternates is measurable directly: instrument the hit rate per slot
   over one Jacobian.
2. **A column re-derives more than it perturbs.** `affected` is one phase for a
   `phases.N.…` path and *every* phase for an instrument path. For an
   instrument path that moves only positions, the widths and |F|² are
   recomputed unchanged; whether the existing memo already absorbs that is
   exactly lead 1's question.
3. **The FD is whole-`phase_peaks` where the chain is analytic in places.**
   `po_intensity_grad` and the structural columns already take analytic
   intensity derivatives (`_structural_column`, `_po_column`) instead of
   perturbing. How far that pattern extends is a scoping question, not a
   known win — and CLAUDE.md's rule holds: a new analytic branch is a claim
   about what one parameter *name* reaches, gated by `_column_extras`, and
   anything beyond its declared reach takes the whole-model FD column.

**The other unowned lead: WP-1113's preset flip, priced and unflipped.**
1113 measured intermediate stages at `ftol=1e-6` giving **1.5–1.7× fewer
whole-plan evaluations at ≤ 0.02 esd** of parameter movement, landed
`Stage.ftol` opt-in, and deliberately did **not** flip the presets — the price
is in its § Findings. That factor multiplies with anything this WP wins, and it
is a decision rather than an implementation. Nothing about it has changed;
what has changed is that it is now the cheapest remaining factor on the table.

**Fences already measured elsewhere — do not re-open.** GPU execution (46–182×
slower, launch-latency-bound, v0.4 record); `torch.compile` (2.5× slower after
38 s, WP-0605); `tr_solver='lsmr'` and the rest of the solver survey's §2 dead
ends; the peaks buffer (WP-1114, **no-go** on the numpy floor — though its
§ Findings note that a compiled *buffer* is the follow-on with the larger
algorithmic ceiling, 7.8–9× element volume on FCJ-heavy cases, if an exact
compiled kernel still misses. It does still miss, so that option is live — but
it is **[1122](1122-compiled-peaks-buffer.md)'s**, not this WP's, and 1122 is
gated on this WP's closing measurement).

## Non-goals

A fourth backend; GPU; a sixth plane kernel (that seam is done — 1115 § The
decision); re-opening 1114's no-go on its original numpy terms; **building the
compiled peaks buffer**, which is [1122](1122-compiled-peaks-buffer.md)'s and
is gated on this WP's closing measurement; anything that moves a converged fit
without a stated and asserted equivalence bar.

## Findings

### 1 — the decomposition on the shipped tier (2026-08-22)

`bench_compiled_kernel.py --seams`, three runs, `[dev]` venv on darwin/arm64,
python 3.12.12. Trigger cold fit **8.86–8.93 s**, Rwp 0.01998, converged; every
share below is stable to 0.1 pp across the three, so the ranges are the
measurement's own and not a machine-state allowance.

| seam | calls | s | ms/call | share |
|---|---|---|---|---|
| residual (forward) | 366 | 1.96–1.99 | 5.4 | 22.1–22.2 % |
| jacobian: bases | 287 | 2.90–2.93 | 10.1 | 32.7–32.8 % |
| jacobian: columns | 286 | 2.89–2.92 | 10.1–10.2 | 32.6–32.8 % |
| — of which plane accumulation | 9 675 | 0.33 | 0.034 | 3.7–3.8 % |
| — **of which perturbed `phase_peaks`** | **15 444** | **1.85–1.87** | **0.120** | **20.9–21.0 %** |
| `compile_model` | 8 | 0.176 | 21.9 | 2.0 % |
| solver + runner | | 0.92–0.93 | | 10.3–10.5 % |

**The § Context prediction was right to the point.** `phase_peaks` was 11.2 %
before the tier and is **20.9–21.0 %** after it, because its absolute cost did
not move (1.911 → 1.85–1.87 s) while everything around it did. It is now the
largest line item that is not plane arithmetic, and **64 % of the column seam**
against 30 % before.

**What the tier bought, seam by seam** — the same harness on the same machine,
`RIETX_COMPILED=0` reproducing the § Context table to 0.1 pp (17.16 s, every
share within 0.1 of the pre-1115 row), so these are ratios between two runs of
one binary rather than a comparison across sessions:

| seam | numpy s | compiled s | ratio |
|---|---|---|---|
| residual (forward) | 3.739 | 1.97 | 1.90× |
| jacobian: bases | 5.846 | 2.91 | 2.01× |
| plane accumulation (in columns) | 3.652 | 0.333 | **11.0×** |
| perturbed `phase_peaks` | 1.917 | 1.86 | **1.03×** |
| solver + runner | 1.046 | 0.92 | 1.14× |

The scatter is the outlier and it is the one kernel that fused a python-level
loop rather than a numpy expression. The two profile kernels sit at ~2×, which
is 1115's own reading of its remaining headroom.

**What this leaves on the table.** Plane work is still 55 % of the fit (bases
32.8 + residual 22.2) and is ~2× off its floor by 1115's measurement, so the
whole seam is worth at most ~27 % of wall even if it went to zero. Against
that, `phase_peaks` is 21 % at a ratio of 1.03× — untouched, and the only line
where a first attempt is not competing with an already-compiled one.

### 2 — lead 1 settled: the memo was thrashing on one axis, and only one

The lead said a depth-1 cache "returns nothing while still paying for the key
build". Instrumented over a whole trigger fit — `_memo` wrapped, each call
classified hit / miss-on-a-new-key / miss-on-a-key-it-had-already-cached, the
last being what a deeper cache would convert:

| slot | lookups | hit % (depth 1) | with no bound | build |
|---|---|---|---|---|
| widths | 15 444 | 15.2 % | 27.9 % | 49.6 µs |
| pos | 15 444 | 51.4 % | 69.0 % | 9.8 µs |
| f2 | 15 444 | 73.5 % | 81.0 % | 145.3 µs |
| cell / lp / abs / aniso | 15 444 each | 76.2 % | 83.1 % | 28.1 / 7.9 / 0.3 / 0.2 µs |
| **column seam, all slots** | **108 108** | **63.6 %** | **72.9 %** | |

**So the lead's mechanism is false as stated and true in a corner.** The memo
answers two lookups in three, not none. Key building is 0.094 s over the whole
fit — **1.0 % of wall** — so "paying for the key build" is not a cost anyone
should have gone looking for. What is real is the 9.3 pp gap, worth **0.331 s
(3.7 %)** as an upper bound at a free unbounded cache.

**Depth 2 collects the part that exists, and depth 8 collects nothing more** —
measured, byte for byte: 35 596 block builds either way, to the call. The
alternation a Jacobian makes has exactly two arms (the expansion point and one
perturbed state), and the lookups beyond them want a key last seen in an
*earlier Jacobian*, thousands of lookups ago. Reading the unbounded figure as
headroom is therefore the mistake, and the keys being decoded θ is why the
unbounded cache is not an option: it grows one entry per parameter vector a
fit visits. Landed at depth 2: **bit-identical** (nfev, njev and Rwp unmoved on
all four cases), 0.3–0.5 % of wall.

### 3 — lead 3: the one parameter that is exactly linear, and a census that over-read

A per-family census of the column seam (9 675 columns, 15 444 `phase_peaks`
calls, 1.60 per column) put `phases.N.scale` second at 0.295 s, 3.3 % of wall
— odd for the one parameter that moves no position and no width. It is odd
because it is an artefact: **a per-family timing census over a depth-1 cache
charges each column for whatever its predecessor evicted**, so the scale
columns were being billed for |F|² rebuilds (145 µs each) that a neighbouring
cell column had caused. Removing the family does not remove that work, it
moves it. Measured after the fact: `phase_peaks` fell 1.849 → 1.780 s, a fifth
of what the census predicted. **Price a removal by removing it.**

The change is still right, and on a better ground than speed. The scale enters
`phase_peaks` once, in `base = scale · mult · |F|²`, and every factor after it
is independent of it, so `∂y/∂scale = y_phase/scale` **exactly** —
`_scale_column`, the peer of `_po_column` and of the Pawley aux block. The
equivalence bar is therefore not bit-identity but *exactness*, and the check
that establishes it is not an FD in θ:

| reference | agreement |
|---|---|
| difference quotient in **physical** space, 100 % step | **3.6e-16** |
| …same, 1 % step | 3.5e-14 |
| …same, 0.01 % step | 2.9e-12 |
| central FD in θ (O(h²)) | 1.4e-7 |
| forward FD in θ — *the column being replaced* | 4.6e-6 |

The error growing as the step shrinks is cancellation, and it is the signature
of a function that is exactly linear. **A θ-space FD is the wrong reference
here**: the scale is a softplus of θ, so the whole-model FD makes the same
O(h) transform-curvature error as the peak-chain FD and certifies it at 2e-11
while both are 4.6e-6 from the truth. `scale == 0` is fenced to the FD path —
softplus underflows to exactly 0.0 and the expression is 0/0 there, root
CLAUDE.md's "a bug wherever the physics divides".

Measured, best-of-3, `[dev]` venv, darwin/arm64, python 3.12.12 — scale column
and depth-2 memo together:

| case | before | after | ratio |
|---|---|---|---|
| nac | 0.40 | 0.38 | 1.05× |
| cpd-1a | 2.18–2.20 | 2.04–2.05 | 1.07× |
| cpd-2 | 3.64–3.76 | 3.38–3.41 | 1.08× |
| trigger | 8.81–8.89 | 8.70–8.72 | 1.02× |

Largest where there are most phases, which is what a per-phase column family
should give. Rwp moves in the fourth decimal on cpd-2 and is **not** offered as
evidence for any of it.

### 4 — the mechanism, named: this seam is dispatch-bound and the plane seam is not

The finding to carry forward, and it inverts WP-1115's. That gate asked
whether python dispatch was the plane kernels' cost and measured it **noise**:
200–400 µs calls on ~10⁵-element planes, 2–4 ns an element. The per-reflection
blocks run on the *reflection* axis, and the trigger's four phases hold **98,
282, 112 and 98 reflections — 594 in total**:

| block | µs per 4-phase rebuild | ns per reflection |
|---|---|---|
| `f2` | 619 | 1042 |
| `widths` | 210 | 354 |
| `cell` | 100 | 169 |
| `pos` | 45 | 76 |
| a call with **every slot hitting** | 334 | 562 |

That last row is the one that names the mechanism: a `phase_peaks` call that
builds *nothing* still costs 562 ns per reflection. These are chains of tens of
numpy calls over arrays of a hundred-odd elements, where per-call overhead
dominates and the array length barely enters — **two to three orders of
magnitude off the plane seam's cost per element**. It is why 1115's compiled
tier bought 11.0× on the scatter, ~2× on the two profile kernels, and **1.03×
here**: fusion and threading pay where there is a plane to fuse, and this seam
has none.

So the per-reflection front is not "the same work, unfused". It is a different
regime, and the lever in it is *fewer, larger numpy calls* — or compiled code
that does not dispatch at all — rather than a better plane kernel.

### 5 — where the trigger fit's time is after this WP

`--seams`, compiled tier, wall 8.70–8.72 s. Everything measured above, in one
place, as the remainder [1122](1122-compiled-peaks-buffer.md) starts from:

| seam | share | absolute | what it is |
|---|---|---|---|
| jacobian: bases | 32.8 % | 2.91 s | plane work, ~2× off its numpy floor (1115) |
| residual (forward) | 22.2 % | 1.97 s | plane work, same |
| jacobian: columns | 31.6 % | 2.78 s | |
| — perturbed `phase_peaks` | 20.2 % | 1.78 s | **per-reflection, dispatch-bound** |
| — plane accumulation | 3.6 % | 0.32 s | compiled, 11× already |
| — `table.decode` | 3.2 % | 0.28 s | one full decode per column, for a one-entry change |
| — FD arithmetic + gather | 3.7 % | 0.32 s | |
| solver + runner | 10.5 % | 0.92 s | scipy TRF |
| `compile_model` | 2.0 % | 0.18 s | 8 stage compiles |

Inside the 1.78 s of `phase_peaks`: **1.36 s block builds, 0.09 s key builds,
0.29 s the per-line intensity assembly** that runs on every column including
the ones that cannot move an intensity.

### 6 — the cold target is still missed, and by how much

**8.70–8.72 s against "low single-digit seconds"** — about 3× short, from a
50 s opening baseline and an 8.86–8.99 s start to this WP. Saying so is the
result; re-scoping the target quietly would not be.

**What is left, and why none of it is a 3×.** Plane work is 55 % of the fit and
sits ~2× off its numpy floor by 1115's measurement, so the whole seam is worth
at most ~27 % of wall *even at zero*. The per-reflection seam is 20 % and
dispatch-bound (§ Findings 4), so it is the one place a first attempt is not
competing with an already-compiled one — but a compiled per-reflection chain
means recompiling d-spacings, structure factors, dispersion, ADPs, PO,
extinction, absorption, Lp and three width models, which is not a WP-sized
piece of work and duplicates physics that has one authority today. The
remaining line items — `table.decode` per column (3.2 %), the intensity
assembly on columns that cannot move an intensity (3.3 %), the last 8 pp of
memo hit rate (unreachable without a leak) — sum to under 7 % between them.

**So the two things that could still close it, neither of them this WP's:**

1. **WP-1113's preset flip**, priced and still unflipped: intermediate stages
   at `ftol=1e-6` gave **1.5–1.7× fewer whole-plan evaluations at ≤ 0.02 esd**
   of parameter movement. It multiplies with everything here — 8.7 s / 1.6 ≈
   **5.4 s** — and it is a decision rather than an implementation. Put to the
   maintainer with this WP's result beside it (task 4); nothing about 1113's
   own price has changed.
2. **[1122](1122-compiled-peaks-buffer.md)**, the compiled peaks buffer, which
   attacks *element volume* rather than cost per element. Its § Inherited now
   carries this WP's remainder, and one correction to its cost model: the
   buffer is priced against the plane seam, which is 55 % of wall and near its
   floor, and buys nothing on the 20 % that is per-reflection.

Together they are the only measured route to the target, and 1.6× × whatever
1122 returns is what the milestone's cold row now rests on.

## Tasks

- [x] **Re-measure the decomposition on the shipped tier** — § Findings 1.
      `--seams` could not answer this as it stood: `compiled.set_enabled(False)`
      sat at module scope, so the mode decomposed the *fallback* after the tier
      had shipped. It now takes the environment's tier and stamps which one it
      ran. Switching it on also surfaced a live race in `_redirect_cache`
      (`warm` imports numba on a thread; a first `enabled()` found the module
      half-built), fixed with a regression test.
- [x] **Instrument the scalar-memo hit rate** — § Findings 2. It hits 63.6 %
      of the time in the column seam, so the lead's "returns nothing" is
      false; the fixable part is one alternation, landed as a depth-2 memo,
      bit-identical. Depth 8 builds exactly the same blocks as depth 2.
- [x] Attack whichever lead the measurement supports — two landed, each with
      its bar stated and asserted. The depth-2 memo is **bit-identical**
      (§ Findings 2). `_scale_column` is **exact** where the FD it replaces was
      not, so its bar is agreement with a difference quotient that has no
      truncation error rather than bit-identity (§ Findings 3), and a converged
      fit moves. Together 1.02–1.08× across the four cases.
- [x] **The preset flip is a decision, not a task** — put to the maintainer
      with this WP's result beside it (§ Findings 6, route 1), and **still
      open**. 1113's price is unchanged: intermediate stages at `ftol=1e-6`
      buy 1.5–1.7× fewer whole-plan evaluations at ≤ 0.02 esd of parameter
      movement. Against this WP's 8.70–8.72 s that is ≈ 5.4 s, and it is the
      larger of the two remaining factors. Carried in ROADMAP § Current focus
      and the v1.1 record so closing this WP does not orphan it again — which
      is the failure this WP was itself created to repair.
- [x] Tests + PNGs. Five new: three step sizes of the scale column's
      exactness and the `scale == 0` fence (`test_jacobian.py`), the two-arm
      alternation and the bound that stops it growing (`test_scalar_memo.py`);
      each was made to fail on the code it guards before landing. No new
      cross-backend config: `capillary_offsets` already frees
      `phases.0.scale`, so the matrix covers the new branch — and its `fd`
      row, which needs no optional backend, passed. `tests/output/wp1121_*.png`
      for all four cases plus zooms, inspected.
- [x] The cold target **is still missed** — § Findings 6 says so with the
      numbers and names what would be needed. The remainder is in
      [1122](1122-compiled-peaks-buffer.md)'s `### Inherited`, whose task 1
      starts from it.

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py                    # the before/after
RIETX_COMPILED=0 .venv/bin/python examples/bench_refinement.py   # …and the numpy floor
.venv/bin/python examples/bench_compiled_kernel.py --seams       # where the time is now
.venv/bin/python -m pytest -n auto --dist loadgroup              # full: this moves numbers
.venv/bin/python -m ruff check src tests examples
```

Before/after as harness ranges with venv and platform, the equivalence bar
stated per landed change, and never an Rwp comparison as evidence.

## References

- WP-1115 § Gate reading and § The decision — the decomposition this WP
  attacks, and the three traps building the tier produced.
- WP-1113 § Findings — the priced preset flip.
- WP-1114 § Findings 3–4 — the peaks buffer's accuracy traps, if that option
  is re-opened on compiled terms.
- Coelho (2018), *J. Appl. Cryst.* **51**, 210 — the two papers the v1.1 set
  is built on.

## Handover log

- **2026-08-22** — v1.1's cold-fit target will not be reached by making the
  arithmetic cheaper, and this session is why we now know that rather than
  suspect it. The fit is decomposed end to end on the tier that actually
  ships: plane arithmetic is 55 % of it and already within about 2× of what
  numpy can do, the per-reflection work is 20 %, and everything else put
  together is under 20 %. Two changes landed — a phase scale is no longer
  finite-differenced, and the scalar cache holds the two states a Jacobian
  actually alternates between — worth 1.02–1.08× across the harness, which
  leaves the cold fit at 8.7 s against a target of low single digits. The
  useful part is the mechanism underneath: the per-reflection blocks are slow
  for a *different reason* than the plane kernels ever were, so the tool that
  bought 11× there buys 1.03× here, and reaching for it again would waste a
  WP. What is left on the table is one decision the maintainer owns and one
  WP that is already open.

  **Done.** Six checklist items, all of them. `--seams` was measuring the
  fallback tier after 1115 shipped (a module-scope `set_enabled(False)`
  covered every mode); it now takes the environment's tier and stamps which
  one it ran. Switching it on exposed a live race in library code —
  `compiled.warm` imports numba on a background thread by design, so a first
  `enabled()` on the calling thread could find the module in `sys.modules`
  with no `config` on it yet and raise `AttributeError` out of an ordinary
  fit. Fixed, with a regression test that builds the half-initialised module
  rather than racing a real thread. Then `_scale_column` (§ Findings 3) and
  the depth-2 memo (§ Findings 2). Eight bit-identity goldens re-baselined,
  `tests/data/README.md` entry written. Root CLAUDE.md gains one rule (804 →
  817, justified at the cap).

  **Measured** — `[dev]` venv (numba yes, no jax/torch), darwin/arm64,
  python 3.12.12, `bench_refinement.py` best-of-3 on an idle machine.
  Trigger cold **8.81–8.89 → 8.70–8.72 s**; cpd-2 3.64–3.76 → 3.38–3.41;
  cpd-1a 2.18–2.20 → 2.04–2.05; nac 0.40 → 0.38. The seam decomposition,
  the memo hit rates, the exactness sweep and the per-reflection cost per
  element are § Findings 1–5; § Findings 6 is the closing statement.
  Fast suite **2614 passed / 117 skipped** (was 2607 / 117): seven tests
  added, all seven passes, no new skip. Full suite, once on the final tree,
  **2723 passed / 126 skipped** in 24:20 — the same +7, all passes, and the
  skip count unmoved, which is the check that none of the seven arrived as a
  skip on a venv without jax or torch. ruff clean; CI green on all six
  required checks (run 32571684487, 12m25s).

  **Gotchas the successor should not re-learn.** A per-family timing census
  over a depth-1 cache charges each column for whatever its predecessor
  evicted: it said removing the scale columns would buy 3.3 % and the real
  figure was a fifth of that. Price a removal by removing it. An
  unbounded-cache "would-hit" figure is not headroom either — depth 8 built
  exactly the same 35 596 blocks as depth 2, to the call. And the
  whole-model FD is the wrong oracle for an analytic column on a transformed
  parameter; it agreed to 2e-11 with a column that was 4.6e-6 from the truth
  (now a CLAUDE.md rule).

  **Next**, in order. (1) The **preset flip** is the one open decision and it
  is the maintainer's: 1113 priced intermediate stages at `ftol=1e-6` at
  1.5–1.7× fewer whole-plan evaluations for ≤ 0.02 esd of parameter movement,
  which against 8.7 s is ≈ 5.4 s and is the larger of the two remaining
  factors. It is carried in ROADMAP § Current focus and the v1.1 record so
  that closing this WP does not orphan it — orphaning a forward finding is
  the exact failure this WP was created to repair. (2)
  [1122](1122-compiled-peaks-buffer.md), whose `### Inherited` now holds this
  WP's remainder and one correction to its cost model: the buffer attacks
  element volume, which is priced against the plane seam that is already near
  its floor, and buys nothing on the per-reflection 20 %.

- **2026-08-22** — created, at the maintainer's direction, to give WP-1115's
  strongest forward finding an owner. 1115 shipped the compiled tier and took
  the cold trigger fit from 17.6 s to 8.9 s, which reached v1.1's warm-series
  target and left the cold one missed by about 2×. Its closing measurement says
  the next front is **not** another plane kernel — that seam is now ~2× off its
  numpy floor with no third factor in it — but the 15 608 perturbed
  `phase_peaks` calls a trigger Jacobian makes, which are per-reflection
  scalars no plane kernel reaches. That finding was recorded in three places
  (1115's handover, the ROADMAP focus line, the v1.1 record) and forwarded to
  no WP, because every v1.1 WP had closed; this file is the repair. Nothing is
  started. **Next**: task 1, because every share in the § Context table
  predates the tier that changed them.
