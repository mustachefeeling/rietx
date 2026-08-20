# WP-1109 — refinement speed: where the time actually goes

Milestone: v1.1 · Status: 🔄 2026-08-20 — orbit canonicalisation vectorised and
landed; the remaining ranked candidates are measured but unstarted
Depends on: —

## Goal

A lab-data multi-phase refinement costs seconds rather than minutes, with the
cost centres named by measurement rather than by guess, and the candidates that
turn out **not** to be cost centres retired so no later session re-hunts them.

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
   1e-8, and `max_nfev = max_iter × n_params` (so `max_iter=100` on 42 parameters
   is a 4200-evaluation budget, which is worth knowing but is not what binds).
   Loosening to 1e-8 measured **1.24–1.32× on `cpd-1a`** and **1.00× on
   `cpd-2`** — case-dependent and small. It is free, though: the answer is
   scientifically identical, worst shift/esd **0.003** over 49 parameters, ΔRwp
   9e-7. Worth taking as hygiene, never as the fix.
4. **Pydantic, deepcopy, history and events are not on the hot path**, as
   CLAUDE.md claims. Whole-fit totals: `deepcopy` 13 ms, `model_copy` 13 ms,
   history `_record` 37 ms, `check_guards` 62 ms, `table.decode` 0.02 ms per
   call. Events cost 3.0 µs each with `json.dumps` + `flush()`, 0.2 µs
   callback-only — 0.8 ms per fit.
5. **Iteration counts are real work, not a tolerance artefact.** `x_scale="jac"`
   measured *slower* (5.22 s vs 4.93 s on `cpd-2`).

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
      the sting out; this is what removes the rest on a series.
- [ ] **The peak loop, scoped to the derivative side.** `phase_component`
      (`forward.py:666-673`) and `derivative_bases` (`forward.py:887-939`) are
      python loops over (phase, line, reflection) issuing ~10-30 tiny numpy
      calls each. `pseudo_voigt_derivs` measures **11.8 µs at a 25-point window
      and 13.6 µs at 194 points** — ~11 µs fixed dispatch, ~0.01 µs/point of
      arithmetic — and is the largest single line in a fit (1.108 s tottime,
      72 688 calls on `cpd-2`); `window_add` is called **678 347** times.
      Batched over a padded (n_peaks × w) array the same work measures 4.15 ms →
      0.57 ms (7.3×) at 194-point windows and 3.56 ms → 0.10 ms (36×) at 25.
      **Read WP-0605 before touching this.** Its no-go is measured and stands
      *for what it scoped*: the **forward** batches at only 1.55-1.6× symmetric
      and 0.58-1.15× under FCJ, and it declined Phase 2 at a composite ≈1.1×
      lab / 1.2-1.25× synchrotron. But it also recorded that `derivative_bases`
      is ~2× the forward and named moving the bases as "Phase 2's real work" —
      that half is what the numbers above bear on, and it is the half WP-0605
      never measured. This task is therefore a re-scope, not a reversal, and it
      owes: the seven `derivative_bases` consumers named in WP-0605 answer 2,
      and the `tests/data/README.md` re-baseline ritual if FCJ rows move (they
      are not bit-identical — batched `matmul` versus per-reflection dgemv).
- [ ] **η-aware window sizing.** `forward.py:110-111` sets
      `WINDOW_FWHM_MULT = 30.0` and `WINDOW_MIN_DEG = 0.3`; on `cpd-2` the median
      corundum FWHM is 0.053° = 3 points while the median window is **185 points
      = 70× FWHM**, and summed window points are **8.1 × n_points** per residual.
      Truncation at 8 FWHM is 2.0e-3 of peak height at η = 0.6, at 4 FWHM
      7.8e-3 — the margin is sized for a pure Lorentzian and applied
      unconditionally to near-Gaussian peaks. **Order matters:** alone this buys
      ~13 %, because the loop is dispatch-bound rather than point-bound; after
      the task above it is worth ~4-8×. Do it second, never first.
- [ ] **Mask `derivative_bases` by the free set.** It builds Ω, ∂Ω/∂pos, ∂Ω/∂Γ,
      ∂Ω/∂η for every peak on every Jacobian call even in a stage where only
      background and scale are free and only Ω is read. Estimated ~1.5-2× on
      early stages, ~15 % on a whole plan — an estimate, not a measurement.
- [ ] **Take the tolerance hygiene** from retired-item 3 (`xtol`/`gtol` to 1e-8),
      with the shift/esd evidence recorded rather than an Rwp comparison.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_acceptance_qpa_roundrobin.py   # goldens unmoved
.venv/bin/python -m ruff check src tests examples
```

A speed task lands with a before/after wall-clock **range** on a named case and
an equivalence check against the pre-change output — never an Rwp comparison,
which CLAUDE.md fences for corrections and which is equally uninformative here.

## Handover log

### 2026-08-20 — investigation, and the first task

*Done.* The three baselines above; the five retired non-causes; the orbit
canonicalisation vectorised, verified over all 564 settings on both the
single-chunk and forced-multi-chunk paths, and landed.

*In flight.* Nothing.

*Next.* The hkl cache is the cheapest remaining win and the one that pays most
on a series. The peak-loop re-scope is the largest and needs WP-0605 read first.

*Gotchas.* (a) Benchmark on an idle machine — a fit re-timed while the suite ran
`-n auto` alongside read 4.78 s against 1.5-1.8 s idle, a 2.7× artefact, larger
than most changes here. (b) `max_iter` is not an iteration count: it multiplies
by the free-parameter count to make `max_nfev`. (c) The FD hunt and the
tie-widening hunt are closed — retired items 1 and 2 exist so the next session
does not repeat them.
