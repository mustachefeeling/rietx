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

WP-1110's shipped change is bit-identical (44 of 44 refined values on 11-BM
NAC), because it windows only phases below 1σ of support and a healthy fit
has none — so 1111's baseline is **not** invalidated by it.

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

### Gate record (2026-08-21) — GO, both scopes; the FCJ layout is bucket

Measured by `examples/bench_batched_derivative_bases.py` (main-checkout venv
`[dev]`, darwin/arm64, best of 3, two runs quoted as ranges; the
narrowed-window rows are a scratch monkeypatch, quoted in that script's
docstring).  The full bases build — Ω, ∂Ω/∂pos, ∂Ω/∂Γ, ∂Ω/∂η + the pos
node-FD, axial off — against two loop baselines: **warm** (every FCJ node
slot hits — a width-moving stage) and **cold** (the pos-FD variants miss —
a position-moving stage, where `zero_disp` and `cell` live).

- **The premise was half wrong: FCJ *physics* is off at every stage of the
  QPA protocol, on cpd-1a and on cpd-2** — the case every 1109 profile
  number came from.  `qarr_instrument` leaves both axial ratios at the
  preset's 0.0 and `qpa_plan` frees only `axial_sl`, and the FCJ trapezoid
  height is 2·min(S/L, H/L) — both apertures must be positive.  Stages
  before `lines_axial` compile no node at all (the state the prototype
  measured); the freed `axial_sl` is a provably-zero column, reported as
  unmeasured.  The harness blurbs calling cpd-1a "the FCJ-heavy case" are
  corrected in this WP; the harness's FCJ case is the **trigger** (93 % of
  1 188 rows, nodes 8-17, axial 0.020/0.020).  So the 1109 microbenchmarks
  were symmetric-kernel numbers measured on symmetric stages — consistent.
- **The floor's one-hot overhead, found and measured while correcting the
  claim above**: from `lines_axial` on, cumulative freeing puts `axial_sl`
  in `moving_paths` and `AXIAL_SIZING_FLOOR` floors *both* apertures for
  sizing, so nodes are allocated (cpd-1a: 215 of 222 rows, counts 8-13+)
  that evaluate as **one-hot symmetric fallbacks** — `derivative_bases`
  3.6 → 9.2 ms and the forward 2.0 → 4.3 ms on those stages, pure overhead
  for an identity, plus one FD residual per Jacobian call for the zero
  `axial_sl` column (`axial_ok` False at sl = hl = 0).  The fix is a
  structural gate of the `skip_extinction` kind — allocate only when *both*
  apertures can be positive this stage (value > 0 or path in
  `moving_paths`) — but it also removes the floored `fcj_extent_deg` window
  margin, and y_calc at fixed θ moves 1.2e-4 rel with the window extent, so
  it is **not** answer-preserving and lands with the η-window task (task
  4), where the re-baseline is already owed.
- **Symmetric scope: 4.0× and exactly bit-equal, every layout** (cpd-1a,
  222 rows, w_max 283: loop 3.9 ms → 0.94-0.98 ms).  This shape is the
  entire QPA protocol and every synchrotron case.
- **FCJ scope: GO, bucket layout.**  Trigger: loop 65.6-67.4 ms warm /
  88.7-88.8 cold → bucket 48.1-48.5 ms (**1.4× warm / 1.8× cold**);
  axial-on 137-142 → 50-52 ms (2.7-2.8×).  Pad *regresses* (0.8× warm):
  pad-to-m_max doubles the majority n=8 bucket, so 0605's layout answer
  holds on the derivative side too — bucket, whose node-axis waste is
  1.03× measured.
- **Why the trigger ratio is modest, diagnosed not assumed**: ~86 % of the
  batched time is kernel arithmetic at ~11 ns/element (the microbenchmark's
  per-point cost).  The shipped ±30·FWHM windows put m×W ≈ 3 200 points
  under every FCJ row — Σ window points = **114× n_points** on the trigger,
  against cpd-2's 8.1× — so the *loop* is point-bound there and batching
  removes only its dispatch share.  W-axis padding waste is 1.06×; padding
  is not the limiter anywhere.
- **The two tasks compose, measured**: at `WINDOW_FWHM_MULT` 15 / 8 the
  trigger bucket ratio rises to 1.8×/2.7× and 2.0×/3.1× while the absolute
  build falls 88.7 → 16.3 ms (≈5.4× combined, cold), and cpd-1a rises to
  5.0×/6.1×.  Shrinking W returns the loop to dispatch-bound, which is
  batching's territory — so the task order stands: batch first, η-windows
  second, and the window task realises most of the trigger's win.
- **Equivalence bars as planned**: symmetric rows bit-equal in every layout
  on both cases; FCJ rows ≤ 2e-18 rel at shipped windows (≤ 4e-16 in the
  narrowed-window runs; the axial node-FDs ≤ 3e-14 — an FD of
  near-cancelling node shifts over h = 1e-7), and *occasionally* exactly
  bit-equal at BLAS-size-dependent shapes — so the FCJ scope claims
  ≤ ~1e-15 rel with the re-baseline ritual, never bit-identity.

## Non-goals

The forward loop's own batching beyond what falls out shared (0605 measured
it small and it is not the bottleneck); GPU enablement (0605's fence:
break-even ≈50–65k elements/kernel, ceiling ≈2.5–3×, memory-bound); the
`vmap`-batched multi-pattern series (v2); solver work (1113); shape
approximation (1114).

## Tasks

- [x] **Gate: prototype the batched derivative bases on FCJ data first**, in
      a scratch example (0605's discipline — shipped path untouched), on
      1111's `cpd-1a` and trigger-shaped states. Measure batched vs loop for
      the full bases build (Ω, ∂Ω/∂pos, ∂Ω/∂Γ, ∂Ω/∂η + node-FD variants)
      under pad / chunk / bucket-by-node-count layouts, plus symmetric-only.
      Record the go/no-go for the FCJ scope in this file before touching the
      contract; the symmetric scope proceeds regardless.
- [x] **Batch `derivative_bases`**: entries become padded/bucketed arrays on
      compile-frozen index planes; update the seven consumers named in
      Context (grep for `bases.entries` to catch drift since 0605).
      *Landed 2026-08-21*: storage is `PhasePlanes` on `CompiledPhase.batch`
      (bucket layout, chunked kernel stage); the ragged `entries` stays as a
      **lazy derived view**, so all seven consumers run unchanged — the hot
      five move onto the planes in the accumulation task, the cold two
      (report/, Pawley) keep the view.  Symmetric rows pinned bit-equal,
      FCJ ≤ 1e-13 vs the scalar reference kept verbatim in
      `tests/test_derivative_bases_batched.py`; the two FCJ goldens
      (`srm660c`, `toy_rich`) re-baselined at ≤ 7.4e-16 per-column rel,
      every other golden bit-identical un-recaptured.  Landed build: cpd-1a
      3.9 → 1.06 ms, trigger 65.6-88.8 → 45.5 ms (axial-on 137-142 → 48.1).
- [x] **Batch the `_peak_chain_column` accumulation**: per-column scalar FDs
      vectorised over reflections, accumulation as `segment_sum` over frozen
      flat indices; keep the per-window accumulation order where bit-identity
      is claimed.  *Landed 2026-08-21*: `_accumulate` scatters (row, term,
      point) contributions row-major through one `bincount` — the loop's
      addition order exactly, so it is bit-identical *unconditionally* (the
      un-recaptured goldens are the proof, `srm660c`'s axial columns
      included); `_structural_column`, `_po_column` and `_axial_column`
      ride the same helper, `_require_basis` semantics unchanged.  Full
      Jacobian call: cpd-1a 10.5 → 8.7 ms, trigger 94.7 → 83.7 ms; the
      remainder is the bases kernel (39 ms) + `_accumulate` (27 ms), both
      ∝ window width — the η-window task's target.
- [x] **η-aware window sizing** by the area criterion above, after the batch;
      re-baseline per `tests/data/README.md` with the equivalence argument
      (area tolerance) recorded next to each moved golden.  Includes the
      one-hot sizing gate from the gate record (allocate FCJ nodes only when
      both apertures can be positive this stage) — same re-baseline event.
      *Landed 2026-08-21.*  **The 1e-3 tolerance the context proposed is
      unreachable**: the Lorentzian tail gives k ≈ η/(π·tol), so 1e-3 means
      k(0.6) ≈ 190 and every lab window *grows*; even 5e-3 reproduces the
      shipped widths (k(0.5) ≈ 32 ≈ the old 30) — the old default was,
      accidentally, about right for lab mixes, and the forecast 4-8× was
      never available without a stated >1 % area bias.  **Measured sweep**
      (cpd-1a + cpd-2 protocol fits): QPA fractions are *flat in the
      tolerance* from 5e-3 to 5e-2 (deviations vs weighed truth 0.61-0.64 /
      2.83-2.91 wt %, the fits' own systematics; bands ±2/±6) while speed
      doubles — so `WINDOW_AREA_TOL = 2e-2` (k(0.6) ≈ 9.5), the knee:
      cpd-1a 9.7 → 5.0 s, cpd-2 15.6 → 8.6 s, fractions within 0.25 wt % of
      shipped, Rwp +≤0.005 (the truncation residue, visible and stated).
      Trigger: Σ windows 114× → 34.6× n_points, Jacobian 83.7 → 36.1 ms,
      residual 30.9 → 17.0 ms.  **The window's two jobs split**: k(η)·Γ is
      tail coverage; `Stage.window_slack_deg` (new, mirrored on `StageSpec`,
      `SCHEMA_VERSION` 0.2 → 0.3, textdoc key + GUI highlighter + dist
      rebuilt) is capture range, declared where a fit must measure a
      hypothesis it may not walk toward — the indexing Le Bail validation
      derives it from the pattern range (`validation_window_slack_deg`:
      2·tanθ_max·1 %, clipped [0.3, 6.0]°), which keeps the wrong-metric
      case reading as *displaced* (Rwp + unmatched), never *absent*, and
      keeps a synchrotron validation narrow (a fixed 4° slack flipped 1 of
      837 lines of the *correct* NAC cell to absent).  Also landed here: the
      one-hot gate (`can_sl`/`can_hl` in `compile_model`), all ten goldens
      re-captured (README §backend_goldens), and the collateral
      recalibrations: aniso round-trip fixture ×4 brighter (its 2σ bar sat
      at a 2.2σ margin that wobbled ±0.1σ under any window change),
      flat-plate low band moved onto the first peaks, partition tests
      honour the documented empty-window NaN, stage-boundary continuity
      bars re-measured (4.4e-4/2.6e-3 gaps — window edges now carry weight),
      and the misfit-injection texture tests re-pinned to the *stronger*
      claim: honest windows cut the extraction leak at its root (phantom
      texture R² 0.66 → 0.012), with `cap_texture_crosstalk` keeping a
      direct unit test.
- [x] Cross-backend: `tests/test_cross_backend.py` configs grow if any
      derivative path's shape changed (CLAUDE.md: the matrix must cover every
      derivative path); `families_tied` row re-checked.  *2026-08-21*: no
      config grows — no new derivative *path* exists; the contract change is
      internal storage, and the ragged view keeps every consumer's shape.
      `families_tied` re-checked: 9 numpy rows pass, the jax/torch rows
      self-skip on this `[dev]` venv and run in CI's `[dev,jax]` fast job.
      The stage-boundary continuity bars were re-measured in the window
      task's commit (the one place the matrix moved).
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
- **2026-08-21** — arrival prune: the WP-1110 `x_scale` lead moved to 1113's
  Inherited — what it moves is the evaluation count (1113's quantity), not
  the cost per evaluation, and this WP's own Non-goals fence solver work
  there. The 1109 numbers folded into Context unchanged; the 1110
  bit-identity note kept, because it is why 1111's baseline stands.
