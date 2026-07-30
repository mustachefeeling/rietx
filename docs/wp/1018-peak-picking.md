# WP-1018 — Peak picking: detection + full per-peak profile fitting

Milestone: v1.0 · Status: 🔄 in flight — code complete, **tests outstanding** (2026-07-30)
Depends on: —

## Goal

`pick_peaks(data, instrument) -> PeakList` returns every resolvable line with a
**fitted** position, its esd, width, shape and integrated intensity — Kα
doublets fitted as a constrained pair, never stripped — so that indexing
(WP-1020+) has per-line σ instead of a global tolerance knob.

## Context

There is no peak-fitting code in this package. The only detection is one line
in `background/diagnostics.py:145`,
`find_peaks(np.where(net>0,net,0)/sigma, height=5.0, distance=3)` on
`net = y - background_envelope(tt, y)`, returning **channel indices only** — no
sub-channel position, no width, no σ. `report/layer0.py` peak-finds the
*residual*, not the pattern. Everything below is new; what it reuses is named.

- **Detection.** `background.diagnostics.background_envelope(tt, y,
  window_deg=3.0, quantile=10.0)` — a rolling low quantile, λ-free and with no
  smoothing parameter to choose, which is what makes it usable *for* choosing
  one (its own docstring argues this). Export it from
  `background/__init__.py`; today it is reachable only as
  `background.diagnostics.background_envelope`.
- **Thresholds are σ-normalised, never relative to the global maximum.** The
  prototype indexer (tag `guillemot-study`,
  `studies/guillemot/index_hl2.py`) used `prominence = net.max()·0.01`; on a
  pattern that is one enormous reflection plus a dozen weak lines (measured on
  `KD1-2_5_NaCoO2`) that suppresses everything but the giant. σ-normalised
  height has no coupling between unrelated parts of the pattern.
- **`distance` comes from the instrument, not a channel count.** The `3` above
  is a synchrotron-shaped constant. Derive the separation floor from
  `profiles.caglioti.gaussian_fwhm` / `lorentzian_fwhm` at the instrument's
  U,V,W,X,Y — which also supplies the fitter's width seeds.
- **Grouping is not a new rule.** Import `model.forward._overlap_groups`'
  criterion and `PAWLEY_OVERLAP_FWHM_FRAC` (`model/forward.py:1273`): adjacent
  peaks join when `tt[k]-tt[k-1] < FRAC·0.5·(fwhm[k]+fwhm[k-1])`. "Overlapped"
  must mean one thing package-wide.
- **Emission lines follow Bragg's law.** The free position is the **Kα1**
  position `2θⱼ`; every other line follows `sin θ_l = (λ_l/λ₀)·sin θ₀`, which
  is literally the ghost transform already in
  `background.diagnostics._contamination_flags` and is why the doublet
  splitting grows as `2·tanθ·Δλ/λ` — `Instrument.bragg_brentano`'s docstring
  already warns against a fixed 2θ offset. **The Kα2/Kα1 ratio is held at
  `source.lines[l].weight`, never refined per peak**: a per-peak ratio is
  exactly the freedom that lets a doublet fit absorb an unresolved neighbour,
  which is the error Rachinger stripping formalises. That is the whole reason
  this WP forbids stripping — put the reasoning in the docstring, not just the
  rule.
- **Widths are shared across emission lines in 2θ**, with the physics stated:
  the dominant broadening is common in Δd/d ⇒ Δ2θ ∝ tanθ, and between Kα1 and
  Kα2 (Δλ/λ ≈ 2.5e-3) that ratio differs by <0.3 % at 2θ = 100°, far inside
  σ(FWHM). Per-line widths are unidentifiable at lab resolution.
- **Shape is the library's own** — `profiles.pseudovoigt.tch_gamma_eta` +
  `pseudo_voigt`, or `profiles.voigt` when `shape="voigt"` — defaulting to
  `instrument.profile.shape`, so a peak list and the refinement that follows
  share one peak shape by construction.
- **FCJ asymmetry is applied at the instrument's declared `axial_sl`/`axial_hl`
  and held fixed.** Reason worth recording: the lowest-angle lines are what
  indexing depends on most (d₂₀ sets the volume estimate), and unmodelled axial
  asymmetry biases their centroid systematically in one direction — a bias σ
  cannot see.
- **Not `run_least_squares`.** Its signature is `run_least_squares(model:
  CompiledModel, table: ParameterTable, …)` (`optimize/least_squares.py:489`)
  and `compile_model` needs a `Structure` with a space group, a cell and an
  enumerated reflection list — i.e. the answer indexing is about to produce.
  Peak parameters also have no dot-paths and must never enter a history node's
  `free_paths`. Call `scipy.optimize.least_squares(method="trf")` directly on
  each window (~40-400 points, 4-14 parameters); ~150 tiny solves do not want
  the staged runner's per-solve overhead.
- **Discreteness, one level down.** The component count per group is frozen
  before the fit and never changed inside it — a fitter that adds or drops a
  component mid-solve has a discontinuous residual, which is the
  frozen-per-stage invariant restated. Re-seeding is an explicit second pass,
  capped at two, and an added component must clear `report.layer2.delta_bic`
  (import it) to be kept.
- **Bérar-Lelann is NOT applied here.** Its derivation is about serial
  correlation across a whole pattern; a 40-400-point window is not that
  population. Say so in the docstring so no future session "fixes" it. The
  `√max(χ²_red,1)` inflation *is* applied: the profile model is not exact over
  a real peak, and a σ that ignores that is optimistic exactly where indexing
  is most sensitive.

### Inherited

Nothing upstream — this is the first indexing WP.

From **WP-1028** (measured on third-party lab data, 2026-07-29): **rank
candidate peaks by prominence and measure only the strongest.** A width
estimator that takes the median FWHM over *all* detections above a prominence
floor reads **0.071°** on a noisy 0.01°-step pattern whose real lines are
**0.389°** — smoothing ripples survive the floor as weak maxima and drag the
median down by a factor of five. Taking the median of the twelve most prominent
detections instead recovers 0.389°. This matters here twice over: it is the
same statistic a `PeakList` reports, and a width read five times too small is
what makes downstream frozen evaluation windows an order of magnitude too
narrow (WP-1028 (c), (h)).

Also from **WP-1028**: `ProfileTCHZ`'s `W = 1e-3 deg²` default is a
*synchrotron* line (FWHM ≈ 0.03°). Any peak-picking default that inherits it
will be wrong on lab data by an order of magnitude.

## Non-goals

- No indexing, no cell, no Q-space (WP-1020) and no data-quality gate or
  shift model (WP-1019). This WP ends at a `PeakList`.
- No Kβ *stripping* — ghosts are flagged and excluded, never subtracted.
- No GUI (WP-1027) and no `.pxt` block (reserved by WP-1009).

## Tasks

- [x] `crystallography/lattice.py`: extract `inv_d_squared(hkl, *cell)` from
      inside `d_spacings` (the einsum is already there, `lattice.py:49`);
      `d_spacings` delegates. **Pure move — arithmetic order unchanged**, so
      the bit-identity goldens stay green (`GOLDEN_PLATFORM` darwin/arm64,
      `tests/test_backend_shim.py`). Call sites: `io/exporters.py:120`,
      `crystallography/symmetry.py:105,158,197`.
- [x] `background/`: export `background_envelope` from `__init__.py`; refactor
      `_contamination_flags` into a public
      `contamination_flags_from_peaks(two_theta, intensity, esd, wavelength,
      *, tol_deg=…)` that the existing index-based version calls — one
      implementation of the ghost logic, matching on
      `k·√(σ_ghost²+σ_parent²)` and on *integrated* intensity rather than net
      height.
- [x] `schemas/indexing.py`: `PeakFlag`, `ObservedPeak`, `PeakList`
      (`from_positions`, `usable`), `INDEXING_THRESHOLDS_VERSION` and the
      pinned thresholds as module constants with `#:` docstrings stating the
      physics — the `report/schemas.py` pattern.
- [x] `indexing/peaks.py`: detection, instrument-derived separation floor,
      second-derivative shoulder *seeds*, grouping via `_overlap_groups`' rule.
- [x] `indexing/peakfit.py`: the per-group model, analytic Jacobian (profile
      derivs chained through `tch_gamma_eta`, plus the emission-line chain
      `d(2θ_l)/d(2θ₀) = (λ_l/λ₀)·cosθ₀/cosθ_l`), softplus width bounds,
      position bounded to ±0.5·FWHM of its seed (the analogue of Layer 1's
      `VALIDITY_RADIUS_FWHM = 0.4` — a fit wanting to move further is a
      detection failure, not a small offset).
- [x] Factor the esd helper (`Cov = χ²_red·pinv(JᵀJ)`) out of
      `optimize/least_squares.py` into one shared function so the two surfaces
      cannot disagree about pinv guarding.
- [x] `pick_peaks` public entry + `pxrdref/__init__.py` export; ghost flagging;
      `PEAK_*` diagnostics (`PEAK_LIST_TOO_SHORT`, `PEAK_SIGMA_ASSUMED`,
      `PEAK_UNRESOLVED_SHOULDER`, `PEAK_CONTAMINATION_LINE`,
      `PEAK_ASYMMETRY_UNMODELLED`) via a translator in `indexing/diagnostics.py`
      in the `refine._guard_diagnostics` style.
- [ ] Tests (`tests/test_peak_picking.py`) + per-group fit overlays to
      `tests/output/`: **σ pull calibration** (fixed-seed ensemble of 200
      synthetic groups from the package's own forward model + Poisson noise;
      pull `(2θ_fit−2θ_true)/σ_fit` needs `|mean| < 0.15`, `std ∈ [0.85,1.20]`)
      — this is the gate the whole tolerance model rests on; doublet-position
      property (fitted position is the **Kα1** position); hypothesis round-trip
      on `from_positions`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_peak_picking.py -q
.venv/bin/python -m pytest tests/test_backend_shim.py tests/test_crystallography.py -q
.venv/bin/python -m ruff check src tests examples
```

The σ pull calibration must pass, and the darwin/arm64 goldens must be
**bit-identical** after the `inv_d_squared` extraction.

## References

- Prior art at the annotated tag `guillemot-study` (commit 97ba88d). **It is
  deliberately not merged into `main`** — an external-data exercise on another
  project's examples, not part of the package. Read it in place; no checkout,
  no merge:

  ```sh
  git show guillemot-study:studies/guillemot/index_hl2.py    # peak_list(): crude
      # minimum-filter background, parabolic maximum refinement, no σ — the
      # version this WP replaces
  git show guillemot-study:studies/guillemot/out/HL2-1_peaks.txt   # 74 peaks
  git show --stat guillemot-study                                  # everything else
  ```

  Every measured claim above is restated in Context, so this is corroboration:
  the WP is workable without it.
- Rachinger, W. A. (1948). *J. Sci. Instrum.* **25**, 254 — the stripping
  method this WP declines, cited for what it does to the noise.
- `profiles/pseudovoigt.py`, `profiles/voigt.py`, `profiles/fcj.py`,
  `profiles/caglioti.py`; `model/forward.py:1273` `_overlap_groups`.

## Handover log

- **2026-07-30** — **seven of eight checklist items landed; the test suite is
  the one outstanding item, and it is the important one.** Merged to `main` at
  the user's instruction in this state, so read this entry before touching
  anything here.

  *Done.* `inv_d_squared` extracted (goldens bit-identical, 15 passed no skips);
  `background_envelope` exported and the ghost rule refactored into
  `contamination_flags_from_peaks`; `schemas/indexing.py` complete;
  `indexing/{peaks,peakfit,pick,diagnostics}.py` complete;
  `statistics.normal_covariance` factored out and shared with
  `covariance_estimates`; `pxrdref.pick_peaks` exported. Fast suite
  **1158 passed / 4 skipped in 64 s**, ruff clean.

  *In flight / next.* `tests/test_peak_picking.py` does not exist yet. The
  **σ pull calibration is the gate the whole downstream tolerance model rests
  on** — 200 synthetic groups from the package's own forward model + Poisson
  noise, `|mean| < 0.15`, `std ∈ [0.85, 1.20]` — and until it runs, the per-line
  σ this WP exists to produce is *unvalidated*. Everything WP-1019 and WP-1020
  do with σ(2θ) and σ(Q) is provisional until then. Also outstanding: the
  doublet-position property test (fitted position is the **Kα1** position), the
  `from_positions` hypothesis round-trip, and the per-group PNG overlays to
  `tests/output/`. A scratch FD harness that exercised five configurations is
  *not* in the tree; it is worth rewriting as the first test rather than
  recovering.

  *Measured so far.* The analytic group Jacobian agrees with central
  differences to **2.5e-07** relative on every column, over five configurations
  (synchrotron single line; lab doublet; symmetric FCJ; asymmetric FCJ
  S/L ≠ H/L; overlapping pair) — this covers the FCJ node-FD path and the
  emission-line chain. Injected positions recovered to **0.0005°** at 1-2σ on
  three-peak and resolved-doublet synthetics.

  *Four defects, all found by running it and none visible by reading it.* Each
  is written up in the module that fixes it; the shortest form:

  1. **A resolved Kα1/Kα2 doublet manufactured one spurious line per
     reflection.** Once Δ2θ = 2·tanθ·Δλ/λ exceeds half a FWHM the Kα2 maximum is
     its own detection, gets its own group, and — because each group is fitted
     *independently, with its own full doublet* — comes back as a real line with
     real intensity. `_drop_kalpha2_aliases` recognises it (stripping is not the
     alternative), and it must also be forbidden to the curvature seeder or it
     returns as a "shoulder". **This is structural to per-group fitting, so any
     future change to grouping or windowing has to keep it.**
  2. **The first curvature seeder was useless.** Differentiating twice amplifies
     white noise by ~1/step², so a threshold written against the per-channel σ
     passed essentially every noise dip — hundreds of seeds on a three-peak
     pattern. It is now a Savitzky-Golay second derivative whose noise is
     propagated *exactly* through the filter's own coefficient norm, ‖c‖₂·σ.
  3. **A shoulder seed landing far from any maximum forms a singleton group, and
     the ΔBIC gate only ever judged components a re-seed pass had added** — so a
     curvature false positive became a reported line with an esd and no
     evidence. `_prune_shoulders` now makes every shoulder-seeded component earn
     its parameters against its own absence; for a singleton, against there
     being no peak at all (`_null_chi2`). Watch the index bug that cost an hour:
     candidacy is keyed by seed 2θ, not by index, because dropping a component
     renumbers the rest.
  4. **`background_envelope` is a rolling *low* quantile, so "net = 0" is not
     the background.** For flat Poisson counts it sits ≈1.28σ low, which turns a
     nominal 5σ threshold into ≈3.7σ — one spurious line at 116.46° on a
     two-peak synthetic. `_debiased_envelope` recovers the offset as the median
     of the residual and adds it back to the *envelope*, so the fitter's
     additively-held background is unbiased too.

  *Three deliberate deviations from this WP's plan, each with its reason.*
  (a) Widths use **native trust-region bounds, not softplus** — the only thing
  softplus bought here was Γ > 0, and native bounds keep the analytic Jacobian
  in physical units with no chain factor. `PEAK_WIDTH_BOUND_FACTORS`' lower
  entry is therefore a *positivity floor* (1e-4), not a physical constraint: a
  genuinely Lorentzian line has Γ_G → 0 and a Gaussian one Γ_L → 0, so a floor
  at 0.2 would forbid both limits. (b) The width Jacobian **finite-differences
  the two-scalar (Γ_G, Γ_L) → (w₁, w₂) map** instead of hand-writing the TCH
  quintic's derivative. That is `derivative_bases`' own idiom (exact per-point,
  FD on cheap scalars) and it keeps the fitter shape-agnostic — the true-Voigt
  map is differenced by the same two lines, where a hand-written chain would
  have needed a second one. (c) `contamination_flags_from_peaks` names
  `two_theta_esd` and `intensity_esd` explicitly rather than the plan's bare
  `esd`, which sat next to `intensity` and read as its esd while meaning the
  position's.

  *Constants and codes this WP added beyond the plan* (all in
  `schemas/indexing.py` with `#:` reasoning): `PEAK_SHOULDER_MIN_SIGMA`,
  `PEAK_ALIAS_TOL_FWHM_FRAC`, `PEAK_ALIAS_RATIO_RANGE`, `PEAK_WINDOW_FWHM_MULT`,
  `PEAK_WIDTH_SCALE_BOUNDS`; and three diagnostic codes past the plan's five —
  `PEAK_KALPHA2_ALIAS`, `PEAK_WIDTH_LAW_MISMATCH`, `PEAK_SHOULDER_SEEDED`.

  *Gotcha about this branch's history, not about the code.* A concurrent session
  working WP-1004/WP-1006 in the same working directory ran `git add -A` while
  these files were uncommitted, so `indexing/peaks.py`, `peakfit.py`, `pick.py`,
  `diagnostics.py` and most of `schemas/indexing.py` were committed inside
  `f63556c`, `e46ead2` and `62d6a76`, whose messages say WP-1004 / WP-1006.
  Content is intact and the tree is green; only the attribution is wrong.
  `git log -- src/pxrdref/indexing/` will mislead you — start from `068149e`.

- **2026-07-29** — created from the indexing plan. Prototype prior art is
  pinned at the tag `guillemot-study`, **read without merging** (see
  References): `git show guillemot-study:studies/guillemot/index_hl2.py`. Read
  `peak_list` before starting — it is exactly the crude version this WP
  replaces, and its measured failure modes (`net.max()`-relative prominence,
  no σ) are the design constraints here.
