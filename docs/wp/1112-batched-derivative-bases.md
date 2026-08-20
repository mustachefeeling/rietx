# WP-1112 — the batched derivative side, and η-aware windows

Milestone: v1.1 · Status: ⬜
Depends on: 1111 (the FCJ-padding go/no-go is judged on its trigger-shaped case)

## Goal

The Jacobian path — ~70 % of solver time, measured — stops paying ~11 µs of
numpy dispatch per (line, reflection) kernel call: `derivative_bases` and the
`_peak_chain_column` accumulation run as batched array operations over
compile-frozen index planes, and windows are sized by each peak's own η
instead of a pure-Lorentzian worst case. This is WP-0605's Phase 2,
**re-scoped to the half 0605 never measured**, with an explicit in-WP
go/no-go gate on the one risk that killed the forward half.

## Context

### Inherited

From WP-1110 (2026-08-20). **WP-1111's opening baseline predates the default
cell window**, which landed the same day: `params.vector.cell_window` gives every
cell parameter a per-stage bound, and changed bounds change the trust region's
Coleman-Li scaling, so the *path* to the minimum moves even though the answer
does not (11-BM NAC, run both ways in one process: the cell agrees to 1 ulp, Rwp
to 4e-13, the worst physically meaningful parameter to 1.3e-8). Iteration counts
can therefore shift slightly. **Re-measure the harness on the current tree before
comparing against 1111's table** — the same rule ROADMAP already applies to 1111
against 1109's opening numbers, for the same reason.

Numbers from WP-1109's 2026-08-20 review (QPA-acceptance `cpd-2`, worktree
venv `[dev]`, darwin/arm64) unless said otherwise.

- **The target, measured.** Jacobian ≈ 34 ms/call vs residual ≈ 8 ms;
  `derivative_bases` 4.8 s cum and `_peak_chain_column` 7.2 s cum (2.5 s its
  own python loop) of a 17.5–17.8 s fit; `pseudo_voigt` + `pseudo_voigt_derivs`
  5.8 s tottime; `window_add` 2.1 M calls. Kernel microbenchmark:
  `pseudo_voigt_derivs` costs **11.8 µs at a 25-point window and 13.6 µs at
  194** — ~11 µs fixed dispatch, ~0.01 µs/point of arithmetic. Batched over a
  padded (n_peaks × w) array the same work is 4.15 ms → 0.57 ms (**7.3×**) at
  194-point windows and 3.56 ms → 0.10 ms (**36×**) at 25. **Those are
  symmetric-kernel numbers** — see the FCJ risk below before quoting them as
  an expectation.
- **Why this is a re-scope of WP-0605, not a reversal.** 0605 (closed 🛑, its
  file is the record) prototyped the **forward** half: 1.55–1.6× symmetric
  and bit-identical, but on FCJ data the node-axis padding made it a **0.58×
  regression** (chunking 0.63×, bucketing by node count 1.15×), and it
  declined Phase 2 at a composite ≈1.1× lab / 1.2–1.25× synchrotron. It also
  recorded that `derivative_bases` is ~2× the forward and named moving the
  bases as "Phase 2's real work" — the half the microbenchmarks above bear
  on and the half 0605 never prototyped. Facts from 0605 that bind here
  (restated because the protocol forbids reading closed WPs):
  - The batched scatter is **already in the backend vocabulary**:
    `segment_sum` (numpy `bincount(weights=…)`) *is* the padded scatter over
    compile-frozen flat indices; the padded gather is plain integer-array
    indexing. No new op, no three-backend liability.
  - **Seven consumers** read the ragged `entries` contract:
    `_peak_chain_column` / `_structural_column` / `_axial_column` /
    `_po_column` / `_pawley_intensity_columns` in `optimize/least_squares.py`
    plus `report/layer1.py` / `report/texture.py`. The contract change, not
    the kernel arithmetic, is the real work. (The `axial_derivs` flag already
    bent it compatibly once: optional entries, every consumer None-checks.)
  - **Bit-identity splits by row type**: symmetric rows batch bit-identically
    (a `bincount` scatter preserves the loop's per-window accumulation
    order); FCJ rows are a batched `matmul` where the loop ran one dgemv per
    reflection — agreement 2e-16 but **not bit-equal**, so touching them owes
    the `tests/data/README.md` re-baseline ritual.
  - `torch.compile` is not an alternative (measured 2.5× slower after a 38 s
    compile; dynamo specialises per window).
- **The FCJ node-axis padding is the one thing that can kill this WP, so it
  is measured first.** Node counts vary 0–64 per reflection; on the forward
  the ~2.5× padding waste ate the kernel-count win entirely. The derivative
  side does 4–6 kernel evaluations per peak where the forward does 1, so its
  dispatch-to-padding ratio is more favourable — but that is an argument, and
  0605's whole lesson is that arguments about this loop lose to measurements.
  Task 1 is a scratch prototype scoped exactly like 0605's, judged on
  WP-1111's trigger-shaped and `cpd-1a` cases. If FCJ batching loses there,
  the fallback scope is real and still large: batch the symmetric rows
  (bit-identical, most of a synchrotron pattern and the majority of lab
  windows), keep the FCJ loop, and take the η-window task regardless.
- **η-aware windows** (moved from 1109, criterion corrected). `forward.py`
  sets `WINDOW_FWHM_MULT = 30.0`, `WINDOW_MIN_DEG = 0.3`; on `cpd-2` the
  median corundum FWHM is 0.053° = 3 points while the median window is 185
  points = 70× FWHM, and summed window points are **8.1 × n_points** per
  residual. The margin is sized for a pure Lorentzian and applied to
  near-Gaussian peaks. **The truncation criterion is integrated area, not
  peak height**: a pseudo-Voigt cut at ±k·FWHM discards ≈ η/(π·k) of its
  area (the two-sided Lorentzian tail, by the arctan expansion), so ±8 FWHM
  at η = 0.6 loses ≈ 2.4 % of the peak's intensity — a QPA-relevant bias,
  where the height at the cut (2.0e-3 of maximum) looks harmless. The
  *current* ±30 FWHM already truncates ≈ 0.6 % for an η = 0.6 peak — the new
  constant is also the chance to state the bias the shipped default carries. Size each window from its own
  (η, Γ_est) to a fixed area tolerance (~1e-3, recorded as a constant with
  the formula in its comment); near-Gaussian peaks shrink enormously,
  high-η peaks barely. **Order matters, measured in 1109**: alone this buys
  ~13 % (the loop is dispatch-bound); after batching it is worth ~4–8×
  (point-bound). Do it inside this WP, after the batch lands.
- **Windows are compile-frozen** (CLAUDE.md invariant 1): resizing changes
  compiled state, not in-run behaviour — every fit number moves slightly, so
  this task owes justified re-baselines wherever goldens pin y_calc, and the
  QPA acceptance tolerances (weighed-truth bands) must absorb it without
  retuning. If they don't, the tolerance is doing its job: tighten the area
  criterion, not the band.
- `docs/wp/1101-standalone-peak-fitting.md` inherits window-sizing figures
  (69× FWHM, 8.1× n_points, `WINDOW_FWHM_MULT` may move) — leave a forward
  note there when the windows change (protocol step 3).

## Non-goals

The forward loop's own batching beyond what falls out shared (0605 measured
it small and it is not the bottleneck); GPU enablement (0605's fence:
break-even ≈50–65k elements/kernel, ceiling ≈2.5–3×, memory-bound); the
`vmap`-batched multi-pattern series (v2); solver work (1113); shape
approximation (1114).

## Tasks

- [ ] **Gate: prototype the batched derivative bases on FCJ data first**, in
      a scratch example (0605's discipline — shipped path untouched), on
      1111's `cpd-1a` and trigger-shaped states. Measure batched vs loop for
      the full bases build (Ω, ∂Ω/∂pos, ∂Ω/∂Γ, ∂Ω/∂η + node-FD variants)
      under pad / chunk / bucket-by-node-count layouts, plus symmetric-only.
      Record the go/no-go for the FCJ scope in this file before touching the
      contract; the symmetric scope proceeds regardless.
- [ ] **Batch `derivative_bases`**: entries become padded/bucketed arrays on
      compile-frozen index planes; update the seven consumers named in
      Context (grep for `bases.entries` to catch drift since 0605).
- [ ] **Batch the `_peak_chain_column` accumulation**: per-column scalar FDs
      vectorised over reflections, accumulation as `segment_sum` over frozen
      flat indices; keep the per-window accumulation order where bit-identity
      is claimed.
- [ ] **η-aware window sizing** by the area criterion above, after the batch;
      re-baseline per `tests/data/README.md` with the equivalence argument
      (area tolerance) recorded next to each moved golden.
- [ ] Cross-backend: `tests/test_cross_backend.py` configs grow if any
      derivative path's shape changed (CLAUDE.md: the matrix must cover every
      derivative path); `families_tied` row re-checked.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`; before/after from the
      1111 harness in the handover entry.

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py           # before/after ranges, all cases
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_acceptance_qpa_roundrobin.py tests/test_cross_backend.py
.venv/bin/python -m ruff check src tests examples
```

Equivalence bars, stated per scope: symmetric batching **bit-identical**
(assert `np.array_equal` against the loop, 0605's precedent); FCJ batching
≤ ~1e-15 rel with the golden re-baseline ritual; window resizing justified by
the recorded area tolerance with acceptance bands unretuned. Never an Rwp
comparison.

## References

- WP-0605's file (`0605-batched-peak-loop.md`) — the record this WP re-scopes;
  its four design answers are restated in Context.
- `examples/bench_batched_peak_loop.py` — the 0605 prototype to extend.
- Coelho, A. A. (2018). *J. Appl. Cryst.* **51**, 210–218 §5.1 — what the
  comparison target does instead (peaks buffer; that avenue is WP-1114).

## Handover log

- **2026-08-20** — created by the 1109 review session; took 1109's two
  largest tasks (the peak-loop re-scope and η windows) with their numbers,
  the truncation criterion corrected from height to area.
