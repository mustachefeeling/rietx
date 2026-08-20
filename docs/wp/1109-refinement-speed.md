# WP-1109 — refinement speed: where the time actually goes

Milestone: v1.1 · Status: ✅ 2026-08-20 — every exact win taken (orbit
canonicalisation, extinction gated at its off state, the profile bases masked
by what a stage can move, the scalar chain memoised, the iteration budget and
the tolerances), the hkl cache retired on measurement, and the heavier avenues
left to WP-1111–1115 (the v1.1 series)

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

**Those are the *opening* numbers and the exact wins have since moved them**
(2026-08-20, third session; same machine, best of 3 idle, worktree `.venv`
`[dev]`, darwin/arm64, Python 3.12). Re-measured on the same tree the table
was taken from, so the pairs are comparable:

| case | before | after | factor |
|---|---|---|---|
| IUCr `cpd-1a`, 3 phases, `qpa_plan` (8 stages) | 13.70–13.77 s | 9.63–9.67 s | **1.42×** |
| `qarr/cpd-2`, QPA acceptance protocol (9 stages, texture) | 17.06–17.22 s | 15.33–15.38 s | **1.11×** |

The two differ because the tolerance change helps `cpd-1a` and costs `cpd-2`
(see that task); everything else is bit-identical on both. Both are still an
order of magnitude off the milestone target, which is 1112/1113/1114's ground
— what this WP could take without changing an answer is now taken.

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
- [x] **Memoise the scalar intensity chain across Jacobian columns.** Done as
      a per-block memo rather than one on |F|² alone: `phase_peaks` splits into
      the cell block (d and the per-line Bragg angles), |F|², March-Dollase P,
      the Stephens width, and the per-line positions, widths, Lorentz-
      polarization and absorption, each memoised on the decoded scalars it
      reads (`CompiledPhase.scalar_cache`, `CompiledModel._memo`).
      *Measured:* QPA-acceptance cpd-2 17.20–17.65 → 15.29–15.47 s, cpd-1a
      10.82–10.91 → 9.87–10.45 s; `phase_peaks` 3.69 → 2.16 s cumulative over
      the same 18 332 calls. Hit rate over a whole cpd-2 fit:
      cell/abs/lp/aniso 71.4 %, f2 67.2 %, po 70.1 %, positions 45.1 %,
      widths 35.8 %, **62.2 % overall** — the two low rows are honest, since by
      the late stages the width and shift parameters are free and those columns
      really do move the block. Bit-identical.
      *The failure mode is a key narrower than its block*, which returns a
      stale array that looks right to any tolerance check, so
      `tests/test_scalar_memo.py` perturbs all 93 parameters of a model
      carrying PO, Stephens strain, an anisotropic ADP and a Cu Kα doublet, one
      at a time, and demands bit-for-bit agreement with an uncached model.
      *One new hazard, closed rather than documented*: the arrays are now
      shared between calls and `phase_peaks` is public, so they are handed back
      **read-only** — an audit of all eleven consumers found no in-place write
      today, which is exactly the state in which such a rule rots.
- [x] **Gate corrections fixed at their off state, at stage compile.**
      `CompiledPhase.skip_extinction`, applied at all three sites that fold E
      in by hand (`phase_peaks`, the `G = E + x·dE/dx` chain factor, the
      March-Dollase r column — gating only the first would leave the other two
      disagreeing with FD). *Measured* 17.06–17.22 → 16.18–16.39 s on the
      QPA-acceptance fit, bit-identical; that is ~0.85 s, not the 1.5–2 s
      estimated here, because `sabine_extinction_and_dx` only ran for
      structural columns.
      *"Not free" turned out to be the wrong question* and this is the reusable
      part: a **tied** parameter is not a column of θ and still moves, so
      `ParameterTable.moving_paths` (free ∪ its ties, read off the nonzero rows
      of C) is what licenses any freeze, and `compile_model`'s argument is
      renamed to it — the axial FCJ sizing wanted the same set and had the same
      hole. `None` stays "no claim made" and gates nothing.
      *The audit of the others:* PO, roughness and Stephens strain already gate
      on a declared block being `None`, which is compile-time structural.
      Their **value-level** off states (r = 1, a = b = 0, S ≡ 0) are
      deliberately not gated: a declared block exists to be refined, so the
      gate would fire only in the stages before it is freed, and each is far
      cheaper than the six-term Laue series. Extinction is the outlier because
      it is a field on *every* phase, defaulting to its off state, so it ran on
      every fit that never mentioned it.
- [x] **Mask `derivative_bases` by the free set.** `profile_derivs=False`
      drops ∂Ω/∂pos, ∂Ω/∂Γ, ∂Ω/∂η in a stage whose free set moves only
      intensities, where all three are multiplied by an identically-zero
      scalar. *Measured:* the call itself 5.6–6.1 → 2.3–2.5 ms (**2.42×**) on
      cpd-2, Ω bit-identical. **On the whole fit it is worth ~0.1 s, and that
      is the finding**: the shipped plans free *cumulatively*, so the mask
      fires on 11 of 425 Jacobian calls — the first stage only. The payoff is
      bounded by how much of a plan holds parameters, not by the 2.42×; the
      "~15 % on a whole plan" estimated here was wrong for a cumulative plan.
      The claim is an **allow**-list of intensity-only families (anything
      unrecognised takes the full bases) asked over free ∪ ties, and it is
      *verified where used*: `_peak_chain_column` finite-differences the
      scalars anyway, and a non-zero one against a missing basis raises and
      names the path, so a wrong entry costs work rather than a short column.
      *A trap worth keeping:* the first attempt was not bit-identical, because
      `pseudo_voigt` and `pseudo_voigt_derivs` spell the same algebra
      differently — `(x/Γ)**2` against `u*u`, a division against a multiply by
      a reciprocal — and land 1–2 ulp apart. Taking Ω from the plain forward
      form moved Rwp in its 9th digit and one stage from 82 iterations to 54.
      Hence `pseudo_voigt_basis`/`voigt_basis`, sharing one expression with
      their derivative forms and pinned bitwise against them.
- [x] **Fix the `max_nfev` semantics.** Now `max_iter × NFEV_PER_ITERATION`.
      The constant is measured, not assumed: 28 stages across four real
      protocols (QPA cpd-2 with texture, cpd-1a, 11-BM NAC in both Le Bail and
      Rietveld) give nfev/njev median 1.11, p90 1.64, **worst 3.20**, so 4
      covers the worst rejection rate with headroom. Every stage measured
      converges an order of magnitude inside the new cap and the cpd-2
      fingerprint is bit-identical. *Note which way it cuts*: a constant
      multiplier **loosens** the budget below four free parameters and tightens
      it above — one robustness row parametrised `max_iter=5` against the old
      one-parameter budget of 5 and now needs 1.
- [x] **Take the tolerance hygiene** (`xtol`/`gtol` → 1e-8, as `XTOL`/`GTOL`).
      **The re-verification this asked for changed the picture, so read the
      numbers rather than the old sentence.** cpd-1a 13.26–13.71 → 10.82–10.91 s
      (1.22–1.27×, confirming the estimate) but QPA-acceptance cpd-2
      16.54–17.05 → 17.20–17.65 s, **1.04× slower** — an earlier stage stops
      sooner at a worse point and `po` then takes 46 iterations instead of 38.
      So it is not free, and retired-item 3's "1.00× on cpd-2" no longer holds
      post-gate. Taken on the net across the two protocols and on the answer
      being equivalent: Rwp moves 3.6e-6, the four QPA fractions by ≤ 0.006 wt %
      against a 1–3 wt % band, the median parameter by 0.004 esd and the worst
      *identifiable* one by 0.18 esd. The "worst shift/esd 0.003" quoted here
      was the median, not the worst.
      *How to read a shift/esd table on this fit*: the parameters that appear
      to move by 1e6 esd — a `gauss_size` parked at 1.1e-8 with an esd of
      1.1e-10 — are ones the fit cannot determine, where the ratio measures
      unidentifiability rather than a change of answer. All five real-data
      acceptance suites pass unchanged, SRM 660c and corundum included.

### Retired — measured and declined

- 🛑 **Cache the hkl list.** Both premises fail measurement, so this is
      retired rather than deferred; do not re-hunt it.
      *There is nothing left to win.* After this WP's own vectorisation,
      `generate_reflections` costs **0.06 s of a 15.29 s fit (0.41 %)** and
      **0.07 s of a 22.64 s four-pattern series (0.31 %)**, with 8 of 40 and
      6 of 36 calls repeating an exact argument tuple. A *perfect* cache saves
      0.013 s (0.08 %) and 0.012 s (0.05 %). Whole stage compile is 0.12 s
      (0.80 %) and 0.13 s (0.59 %) — not the "~5 % of a fit" this task
      assumed, which was an estimate carried over from before the vectorisation
      landed. The series case, named here as the payoff, is the *smaller* of
      the two shares.
      *And the proposed key is not exact.* "The expensive parts depend on the
      cell only through `floor(a/d_min)`" is false: the survival filter is
      `d ≥ 0.999·d_min` with `d` from the **whole** cell, so a cell move can
      carry a reflection across the boundary without changing any index bound.
      Measured on certified corundum (`R-3c`, Cu Kα, 5–150°), the reflection
      count moves **63 → 64 at 10 ppm** — well inside what a stage boundary
      shifts. An index-bounds key would therefore have been silently
      *not* bit-identical, which is the bar this WP set. A whole-cell key is
      exact, and buys the 0.08 % above.
      *Structural note:* the series does **11** compiles for 4 patterns × 8
      stages, not the `n_patterns × n_stages` = 32 this task assumed
      (self-consistent: 36 `generate_reflections` calls = 3 seed + 11 × 3
      phases). Why sequential recompiles that rarely was not chased here.

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

### 2026-08-20 (third session) — the exact wins taken, and the WP closed

*Done.* All five remaining implementable tasks landed, each bit-identical or
answer-identical and each with its before/after in the task text above: the
extinction off-state gate, the `derivative_bases` free-set mask, the
scalar-chain memo, the `max_nfev` semantics and the tolerance constants. The
sixth, the hkl cache, is **retired on measurement** rather than deferred — both
its premises fail (§ Tasks, Retired). No `### Inherited` section existed on
arrival, so nothing was pruned.

Three things are reusable beyond this WP and are written where they belong
rather than here:

- **`ParameterTable.moving_paths`** (free ∪ its ties) is the question any
  structural freeze must ask; `free_paths` is a narrower one and the axial FCJ
  sizing had been asking it. `compile_model`'s argument is renamed to match,
  with `None` meaning "no claim made" and gating nothing.
- **A claim about what a parameter *name* reaches gets verified where it is
  used.** `_INTENSITY_ONLY` is an allow-list (unrecognised falls through to the
  full bases) *and* `_peak_chain_column` checks it against the scalars it
  finite-differences anyway, so a wrong entry raises and names the path instead
  of returning a short column.
- **A memo makes arrays shared, and `phase_peaks` is public**, so they are
  handed back read-only. An audit of all eleven consumers found no in-place
  write today — which is exactly the state in which that stays true only by
  luck.

*Measured* (worktree `.venv`, `[dev]` only — jax and torch absent —
darwin/arm64, Python 3.12). Fast suite **2501 passed + 117 skipped**, **+43**
over this WP's 2458+117 baseline for the 43 tests added, no new skip. Full
suite: see the closing run below. All five real-data acceptance suites
(`qpa_roundrobin`, `nac`, `srm660c`, `fap`, `capillary`) pass unchanged;
`test_docs_consistency.py` 17/17; ruff clean. Wall clock, best of 3 on an idle
machine, both re-measured against the same tree the opening table was taken
from: cpd-1a **13.70–13.77 → 9.63–9.67 s** (1.42×), QPA-acceptance cpd-2
**17.06–17.22 → 15.33–15.38 s** (1.11×).

*In flight.* Nothing.

*Next.* [1111](1111-benchmark-harness.md), the harness — and it should record
its opening baseline on *this* tree, not on the numbers in this file's opening
table, which are now a session stale. Then 1112, whose targets this session's
profile sharpened: after the memo, `phase_peaks` is down to 2.16 s of an 18.2 s
profiled fit and the cost is squarely in the profile evaluation —
`pseudo_voigt` 2.77 s, `pseudo_voigt_derivs` 2.29 s, `fcj_offsets_weights`
1.20 s, `_reflection_profile` 1.10 s, `window_add` 0.87 s — which is exactly
1112's ground.

*Gotchas.* (a) **The shipped plans free cumulatively**, and that bounds any
free-set optimisation: the `derivative_bases` mask is 2.42× on the call and
0.6 % on the fit because it fires on 11 of 425 Jacobian calls. Do not estimate
a free-set win from a single stage. (b) **`pseudo_voigt` and
`pseudo_voigt_derivs` are 1–2 ulp apart**, so Ω for the analytic bases must
come from `pseudo_voigt_basis`/`voigt_basis`, never the plain forward form;
substituting it moved Rwp in its 9th digit and a stage from 82 iterations to
54, and no `allclose` check would have caught it. (c) **A shift/esd table on
`cpd-2` is dominated by parameters the fit cannot determine** — a `gauss_size`
parked at 1.1e-8 with an esd of 1.1e-10 "moves by 1e6 esd" — so read the
median and the identifiable worst, not the maximum. (d) The tolerance change
is a **wash across protocols**, not a win: +1.25× on cpd-1a, −1.04× on cpd-2.
It was taken on the net and on answer-equivalence, and the old "1.00× on
cpd-2" in retired-item 3 no longer holds. (e) `rietx.refine` resolves to the
re-exported *function*, not the module, so `import rietx.refine as rf;
rf.compile_model = spy` silently patches nothing — use
`sys.modules["rietx.refine"]`. This produced a wrong "0 compiles" reading
before it was caught. (f) Everything in the two earlier sessions' gotchas
still binds, the idle-machine rule especially.

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
