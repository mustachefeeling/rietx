# WP-1109 — refinement speed: where the time actually goes

Milestone: v1.1 · Status: 🔄 2026-08-20 — orbit canonicalisation landed; the
2026-08-20 review restructured this WP to the cheap exact wins and spun the
heavier avenues into WP-1111–1115 (the v1.1 series)

Depends on: —

## Goal

A lab-data multi-phase refinement costs seconds rather than minutes, with the
cost centres named by measurement rather than by guess, and the candidates that
turn out **not** to be cost centres retired so no later session re-hunts them.
This WP now carries the *exact* wins — changes that are bit-identical or
answer-identical by construction; the batched rewrite, the solver/protocol
question, and the algorithmic tier are WP-1112, WP-1113 and WP-1114.

## Context

The trigger was a real agent session (68-pattern in-situ series, 4 phases of
ZrMo₂O₈, 4165 points, 41 free parameters, Cu Kα) that spent **3 h 20 min** of a
3 h 12 min task window inside refinements: cold patterns at 105–138 s, one run
killed at 289 s/pattern, four patterns hitting `max_iter` at ~600 s each. The
comparison being made is TOPAS, which fits that shape in well under a second.

Everything below was measured in a worktree venv (`[dev]`, macOS arm64,
Python 3.12). Wall clock is a range, not a record — CLAUDE.md § Commands.

**Baselines.**

| case | size | wall |
|---|---|---|
| 11-BM NAC, 2 phases, synchrotron, 5 stages | 22 003 pts, 132 refl, 24 free | 1.5–1.8 s |
| IUCr `cpd-1a`, 3 phases, Cu Kα + FCJ, 4 stages | 7 251 pts, 42 free | 15–22 s |
| `qarr/cpd-2`, 4 phases, `mccusker_default`, 5 stages | 7 251 pts, 28 free | 4.9 s |
| `qarr/cpd-2`, 4 phases, the **QPA acceptance protocol** (9 stages, texture) | 7 251 pts, 49 free by `biso` | 17.5–17.8 s |

The last row is `test_acceptance_qpa_roundrobin.test_sample2_brucite_march_dollase`'s
own protocol and is not the same fit as the 4.9 s row above it — quote them
separately. WP-1111 makes these cases a repeatable harness and adds the
trigger-shaped one none of them covers (~1000+ (line, reflection) pairs).

### The 2026-08-20 review profile (post-orbit-fix, QPA-acceptance cpd-2)

Whole fit 17.5–17.8 s over three runs, **534 residual + 425 Jacobian
evaluations**; residual ≈ 8 ms/call, Jacobian ≈ 34 ms/call, so the Jacobian
path is ~70 % of solver time. Per-stage TRF iterations (the plan frees
cumulatively; `zero_disp` adds exactly **2** new parameters):

| stage | scale_bkg | zero_disp | cell | profile_w | profile | sample_broadening | lines_axial | biso | po |
|---|---|---|---|---|---|---|---|---|---|
| n_iter | 14 | 93 | 131 | 19 | 69 | 82 | 32 | 56 | 38 |

Inside the Jacobian: `derivative_bases` 4.8 s cum, `_peak_chain_column` 7.2 s
cum of which **2.5 s is its own python loop** (tuple unpacking, scalar
compares); `pseudo_voigt` + `pseudo_voigt_derivs` tottime 5.8 s (28 % of the
fit); `window_add` called **2.1 M times** (0.84 s); `_reflection_profile`
212 520 calls. Those are WP-1112's targets. Two facts are *this* WP's:

- **`phase_peaks` is called 17 848 times (4.95 s cum)** — once per Jacobian
  column per affected phase, at perturbed θ — recomputing structure factors,
  Lp and the whole correction chain even for columns (profile u/v/w,
  background, axial) that cannot move an intensity.
- **The Sabine extinction chain costs ~1.5–2 s at ext = 0, where E ≡ 1**:
  `sabine_extinction` 35 758 calls (1.2 s cum) + `_laue_and_deriv` 0.79 s
  tottime, evaluating a six-term series branchlessly for a parameter the plan
  never frees and whose value is exactly its off state.

Two solver measurements, recorded here because they were measured here; the
investigation is WP-1113's:

- **Both drivers crawl, and `solver="lm"` lands in a worse basin.** The same
  protocol under the in-tree bounded-LM driver (`optimize/lm.py`, Coelho's
  λ_new): 409 iterations (vs 534), wall 13.2 s, but **Rwp 0.245 vs 0.132** and
  brucite 76.4 vs 38.2 wt % — a different, worse minimum on a shipped
  acceptance case. `zero_disp` takes ~95 iterations for its 2 new parameters
  under *both* drivers, so the count is a property of the problem (or the
  staging), not of TRF.
- **`max_nfev = max_iter × n_params` is an FD-era budget ~30× looser than its
  name.** Measured nfev/njev = 534/425 ≈ 1.26 evaluations per iteration with
  the analytic Jacobian, so `max_iter=100` on 42 parameters permits ~3300
  actual iterations — the four ~600 s trigger patterns were spending exactly
  this budget before giving up. The multiplier priced FD Jacobians
  (n_params evaluations each), which retired-item 1 shows are not happening.

### Retired — measured non-causes

Do not re-hunt these; each cost a session's time to eliminate.

1. **Finite-difference fallback is not happening.** Counting
   `CompiledModel.evaluate` calls inside the `_make_jacobian` closure (where the
   FD block at `optimize/least_squares.py:409-416` is the only caller): **0 FD
   columns** across all five NAC stages, **0.3 per Jacobian** on `cpd-1a`, **0**
   on `cpd-2`. Every common family is analytic — background as exact linear
   rows, coordinate/ADP DOFs, March-Dollase r, axial S/L H/L via node-FD bases,
   and everything else through `_peak_chain_column`, because
   `scalar_chain_supported` (`model/forward.py:815`) is `True` for any `phases.*`
   path.
2. **The tie-widening gate is benign.** `_column_extras`
   (`least_squares.py:281`) found 4 of 28 columns tied on `cpd-2` — the
   trigonal/hexagonal/cubic `b←a`, `c←a` rows — and all four still took the peak
   chain, because their extras are `phases.*` too. It can only force a
   whole-model FD column on a *user* tie crossing families. The CLAUDE.md
   invariant stands; it simply does not fire on symmetry ties.
3. **Convergence tolerances are a small lever, not the lever.**
   `least_squares.py:721` hardcodes `xtol=1e-12, gtol=1e-12` against scipy's
   1e-8. Loosening to 1e-8 measured **1.24–1.32× on `cpd-1a`** and **1.00× on
   `cpd-2`** — case-dependent and small, meaning most iterations make more
   than 1e-8 relative progress: the counts above are slow *traversal*, not
   terminal polish. It is free, though: the answer is scientifically
   identical, worst shift/esd **0.003** over 49 parameters, ΔRwp 9e-7. Worth
   taking as hygiene, never as the fix.
4. **Pydantic, deepcopy, history and events are not on the hot path**, as
   CLAUDE.md claims. Whole-fit totals: `deepcopy` 13 ms, `model_copy` 13 ms,
   history `_record` 37 ms, `check_guards` 62 ms, `table.decode` 0.02 ms per
   call. Events cost 3.0 µs each with `json.dumps` + `flush()`, 0.2 µs
   callback-only — 0.8 ms per fit.
5. **Iteration counts are real work, not a tolerance artefact.** `x_scale="jac"`
   measured *slower* (5.22 s vs 4.93 s on `cpd-2`). Whether they are
   *irreducible* work is a different question — WP-1113's.

### The one thing the log shows that no code change addresses

Cold versus warm start dominated that session by more than any inner-loop
factor: **138 s for pattern 1, 7–9 s for patterns 6–7** — same data size, same
bounds, same plan, 20×. A chained series is already the mitigation; what the run
lacked was a good cold start. Separately the run collected **425 `BOUND_HIT`
diagnostics** (`phases.3.cell.c` pinned in 42 of 68 patterns) which nothing
surfaced until the operator went looking, two hours in. Attempting to reproduce
the bound cost on shipped data **did not reproduce**: capping the size/strain
parameters on `cpd-1a` ran *faster* (9.5 s) than the shipped bounds (15.7 s), so
"tight bounds cost wall clock" is unproven here and is recorded as the log's own
uncontrolled comparison, not as a finding.

## Non-goals

Moved to the v1.1 series on 2026-08-20, each with the measurements it needs
restated in its own file:

- **The batched derivative side and η-aware window sizing** →
  [1112](1112-batched-derivative-bases.md). The 7.3×/36× kernel numbers, the
  WP-0605 re-scope argument, the FCJ node-axis padding risk and the
  area-based truncation criterion all live there now.
- **Evaluation count** (the iteration table above, the LM basin difference,
  seeding, per-stage budgets) → [1113](1113-evaluation-count.md).
- **The peaks buffer** (TOPAS's algorithmic tier) →
  [1114](1114-peaks-buffer-spike.md).
- The benchmark harness this WP's before/afters should be quoted from →
  [1111](1111-benchmark-harness.md).

## Tasks

- [x] **Vectorise the orbit canonicalisation in `generate_reflections`**
      (`crystallography/symmetry.py`). The loop ran one `einsum` + `vstack` +
      list-of-tuples + `set.update` **per surviving hkl** — ~11 µs of numpy
      dispatch on three-element arrays, which at this size is the entire cost.
      Replaced by one `einsum("mij,nj->mni")` over all hkl, lexicographic
      canonicalisation by mixed-radix integer encoding, and orbit sizes by
      sorting each column and counting changes.
      *Measured, whole function:* 62→16, 29→2.9, 20.8→2.0, 18.7→1.8, 26.8→1.7,
      6.3→0.7, 88.5→7.3 ms across cubic/rhombohedral/monoclinic/triclinic cases
      — **4–16×**; python function calls for three monoclinic runs 280 753→1 009.
      *Equivalence:* representatives, multiplicities and d-spacings identical to
      the pre-change loop over **all 564 gemmi settings**, and again with the
      chunk budget forced small so the multi-chunk branch runs. Checking every
      setting rather than one per system is the Rᵀ trap in this module's
      docstring: a wrong action keeps the orbit *count* right everywhere.
      *Memory:* the image stack is the only non-O(n) array (48 ops × 10⁶ hkl
      would be gigabytes where the loop was O(1)), so it chunks —
      `_ORBIT_CHUNK_ELEMENTS`.
- [ ] **Cache the hkl list.** Nothing keys it on (space group, cell, λ, range),
      so a stage boundary that moved the cell by ppm regenerates an identical
      list, and `sequential.py:680-698` redoes every recompile per pattern:
      n_patterns × n_stages × `compile_model`. The expensive parts (grid
      enumeration, absence filtering, orbit canonicalisation) depend on the cell
      only through `floor(a/d_min)`, so a cache keyed on the index bounds is
      exact while d-spacings are recomputed cheaply. Vectorising took most of
      the sting out; on the measured baselines stage compile is now ~5 % of a
      fit, so the payoff is the *series* case — an estimate until WP-1111's
      series benchmark measures it. *Bar: bit-identical.*
- [ ] **Memoise the scalar intensity chain across Jacobian columns.** Per
      Jacobian call, every `_peak_chain_column` re-runs `phase_peaks` at
      perturbed θ; for a column that moves no structural or cell value the
      |F|² block (and everything downstream of it that only depends on
      unmoved inputs) is bit-equal to the expansion point's. Apply the
      `_cached_fcj_nodes` pattern (`model/forward.py:119` — input-equality
      memo, no hashing, numpy-gated so traces neither deposit tracers nor
      constant-fold): key the |F|²/extinction sub-chain on the values that
      enter it, reuse iff all compare bit-equal. *Estimated* 15–20 % on the
      QPA-acceptance fit (the 4.95 s `phase_peaks` cum above), an estimate
      until measured. *Bar: bit-identical (a hit is a reuse, not a
      reordering).*
- [ ] **Gate corrections fixed at their off state, at stage compile.** A
      parameter that is not free cannot move within a stage, so "extinction
      is fixed at 0 for this stage" is compile-time structural — the same
      argument that froze node counts. Skip the Sabine chain when
      `ext == 0` and the path is unfree (E ≡ 1 exactly, its purity-(b)
      identity); audit roughness/absorption/PO for the same shape (PO and
      roughness already gate on `None` — the audit is for value-level off
      states that don't). ~1.5–2 s of the 17.5 s fit measured above. The gate
      lives on the numpy analytic path or at compile; the traced twin
      (`backend/traced.py`) stays branchless. *Bar: bit-identical.*
- [ ] **Mask `derivative_bases` by the free set.** It builds Ω, ∂Ω/∂pos, ∂Ω/∂Γ,
      ∂Ω/∂η for every peak on every Jacobian call even in a stage where only
      background and scale are free and only Ω is read. The `axial_derivs`
      flag (WP-0605 task 0) is the precedent and the contract shape: optional
      entries, every consumer None-checks. Estimated ~1.5-2× on early stages,
      ~15 % on a whole plan — an estimate, not a measurement. *Bar:
      bit-identical (skipped bases are unread).*
- [ ] **Fix the `max_nfev` semantics.** `least_squares.py:722` sets
      `max_nfev = max_iter × max(len(x0), 1)`, pricing FD Jacobians that
      retired-item 1 shows never run; with the analytic Jacobian an iteration
      costs ~1.3 evaluations, so the guard permits ~30× more iterations than
      `max_iter` names. Make the budget ≈ `max_iter` × a small constant
      (measured headroom for TRF's trial-point rejections, not n_params), on
      both `run_least_squares` and `run_multi_least_squares`, and state in
      the docstring that `max_iter` now approximates iterations. This is the
      trigger log's ~600 s/pattern pathology: those runs would give up ~30×
      sooner with the answer unchanged (a run that *converges* never feels
      the guard — assert that on the acceptance protocols). *Bar:
      answer-identical on every converging case; the guard is CLAUDE.md's
      "runaway guard, never a timer".*
- [ ] **Take the tolerance hygiene** from retired-item 3 (`xtol`/`gtol` to 1e-8),
      with the shift/esd evidence recorded rather than an Rwp comparison.
      *Bar: answer-identical (worst shift/esd 0.003 measured, re-verify).*

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_acceptance_qpa_roundrobin.py   # goldens unmoved
.venv/bin/python -m ruff check src tests examples
```

Every remaining task in this WP is bit-identical or answer-identical by
construction, so "goldens unmoved" holds here — that is what distinguishes
this WP from 1112, whose FCJ rows owe the `tests/data/README.md` re-baseline
ritual. A speed task lands with a before/after wall-clock **range** on a named
case (quote WP-1111's harness once it exists) and an equivalence check against
the pre-change output — never an Rwp comparison, which CLAUDE.md fences for
corrections and which is equally uninformative here.

## References

- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 210–218 — TOPAS
  architecture; §5.1 peaks buffer, §5.2 threading (the comparison target's
  own account of where its speed comes from).
- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 428–435 — the λ_new LM
  constant; already implemented in `optimize/lm.py` (WP-0601).

## Handover log

### 2026-08-20 (second session) — the review, the restructure, and the series

*Done.* A critical review of this WP against the two Coelho references, with
new measurements (all worktree `.venv`, `[dev]`, darwin/arm64, Python 3.12):
the QPA-acceptance cpd-2 profile now in Context (17.5–17.8 s over three runs,
534 + 425 evaluations, the per-stage iteration table, the `phase_peaks` and
extinction-at-zero findings), the `solver="lm"` comparison (worse minimum:
Rwp 0.245 vs 0.132, brucite 76.4 vs 38.2 wt %), and the `max_nfev` ≈ 1.26
nfev/iteration arithmetic. The WP restructured on the review's conclusion:
this file keeps the exact wins (two new tasks — the scalar-chain memo and the
off-state gating — plus the promoted `max_nfev` fix), and the heavier avenues
became the v1.1 series: 1111 (harness), 1112 (batched bases + η windows,
which took this WP's two biggest tasks with their numbers), 1113 (evaluation
count, which took the solver findings), 1114 (peaks-buffer spike), 1115
(compiled spike, gated). v1.1 opened as the refinement-speed milestone in the
same session (version → 1.1.0.dev0, Milestones row, v1.1.md scope/acceptance);
the peaks set shifted to v1.2. PR #69.

*Measured* (worktree `.venv`, `[dev]`, darwin/arm64, Python 3.12). Fast suite
**2458 passed + 117 skipped** — unmoved from this WP's first-session baseline,
exactly right for a session that added zero tests; docs-consistency 17/17;
ruff clean. Full suite not run: docs plus the version string, which no
measured number quotes. The new profile/iteration numbers in Context were
measured on this machine without an idle guarantee — three TRF runs agreed
within 0.3 s, but re-baseline from WP-1111's harness before quoting them
against a future change.

*In flight.* Nothing — the landed orbit task is unchanged.

*Next.* The remaining tasks here are one session's work and the recommended
next step; then 1111. Note the review's ordering argument: the cheap wins are
worth having regardless of distribution, but quote their payoff from 1111's
trigger-shaped case once it exists, because the shipped baselines under-weight
peak count.

*Gotchas.* (a) The LM worse-minimum is a *robustness* finding — do not read
it as "LM is slower"; its iteration count was lower. Investigation is 1113's,
with the measurement recorded here so it is not re-run casually. (b) The
17.5–17.8 s row is the 9-stage QPA acceptance protocol, not the 4.9 s
5-stage `mccusker_default` row — same data, different fit; quoting one
against the other is a 3.6× phantom. (c) Everything in the first session's
gotchas below still binds, (a) especially.

### 2026-08-20 — investigation, and the first task

*Done.* The three baselines in Context; the five retired non-causes, each
measured rather than argued; and task 1 landed — the orbit canonicalisation in
`generate_reflections` vectorised, with the empty-range and memory properties
the per-hkl loop got for free written back in explicitly.

One consequence reached outside `crystallography/`. `determine_extinction_symbol`
promises that a cell with no reflections in range comes back as a failed screen
with a reason rather than a traceback, and it was delivering that by **catching
the einsum shape error** the old loop raised on the empty array. With empty
answered rather than raised, the live path became the `if not primary` branch,
which set `status="failed"` and attached no diagnostic — WP-1076's shape, a
declared state with no writer for its reason. It now names the cell and the
range. So this commit touches `indexing/extinction.py`, which is why the
indexing acceptance was run.

*Measured* (worktree `.venv`, `[dev]` only — jax and torch absent — darwin/arm64,
Python 3.12). Fast suite **2458 passed + 117 skipped**, exactly **+9** over the
2449+117 baseline for the 9 tests added (8 parametrised orbit-partition rows and
1 chunking row, both in `test_crystallography.py`), **no new skip**.
`test_acceptance_indexing.py` passed, exit 0, ~25 min serial. ruff clean. Full
suite not run: the change is bit-identical by construction and checked as such
over all 564 gemmi settings, so no measured acceptance number can move — the
nightly full will read +9.

Wall clock, whole function: 62→16, 29→2.9, 20.8→2.0, 18.7→1.8, 26.8→1.7,
6.3→0.7, 88.5→7.3 ms across cubic/rhombohedral/hexagonal/monoclinic/triclinic;
python calls for three monoclinic runs 280 753→1 009. Whole 11-BM NAC fit
**1.74-1.75 → 1.24-1.25 s**, both best-of-3 on an idle machine.

*In flight.* Nothing.

*Next.* The hkl cache is the cheapest remaining win and the one that pays most on
a series. The peak-loop re-scope is the largest, and its task text is written as
a re-scope of WP-0605 rather than a reversal — read that WP first, and note it is
closed 🛑, so its file is the record and there is no `### Inherited` there to
receive a note.

*Gotchas.* (a) **Benchmark on an idle machine.** A fit re-timed while the suite
ran `-n auto` alongside read 4.78 s against 1.24 s idle — a 3.9× artefact, far
larger than anything this WP will change. Every number above is best-of-3 with
nothing else running. (b) `max_iter` is **not** an iteration count: it multiplies
by the free-parameter count to make `max_nfev`, so `max_iter=100` on 42
parameters is a 4200-evaluation budget. (c) Retired items 1 and 2 exist so the FD
and tie-widening hunts are not repeated; both cost measurement to eliminate.
(d) The bounds-cost claim is recorded as **not reproduced**, deliberately — do
not quote the log's 138→18 s as evidence for it later.
