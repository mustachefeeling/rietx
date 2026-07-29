# WP-1018 — Peak picking: detection + full per-peak profile fitting

Milestone: v1.0 · Status: ⬜ not started
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

- [ ] `crystallography/lattice.py`: extract `inv_d_squared(hkl, *cell)` from
      inside `d_spacings` (the einsum is already there, `lattice.py:49`);
      `d_spacings` delegates. **Pure move — arithmetic order unchanged**, so
      the bit-identity goldens stay green (`GOLDEN_PLATFORM` darwin/arm64,
      `tests/test_backend_shim.py`). Call sites: `io/exporters.py:120`,
      `crystallography/symmetry.py:105,158,197`.
- [ ] `background/`: export `background_envelope` from `__init__.py`; refactor
      `_contamination_flags` into a public
      `contamination_flags_from_peaks(two_theta, intensity, esd, wavelength,
      *, tol_deg=…)` that the existing index-based version calls — one
      implementation of the ghost logic, matching on
      `k·√(σ_ghost²+σ_parent²)` and on *integrated* intensity rather than net
      height.
- [ ] `schemas/indexing.py`: `PeakFlag`, `ObservedPeak`, `PeakList`
      (`from_positions`, `usable`), `INDEXING_THRESHOLDS_VERSION` and the
      pinned thresholds as module constants with `#:` docstrings stating the
      physics — the `report/schemas.py` pattern.
- [ ] `indexing/peaks.py`: detection, instrument-derived separation floor,
      second-derivative shoulder *seeds*, grouping via `_overlap_groups`' rule.
- [ ] `indexing/peakfit.py`: the per-group model, analytic Jacobian (profile
      derivs chained through `tch_gamma_eta`, plus the emission-line chain
      `d(2θ_l)/d(2θ₀) = (λ_l/λ₀)·cosθ₀/cosθ_l`), softplus width bounds,
      position bounded to ±0.5·FWHM of its seed (the analogue of Layer 1's
      `VALIDITY_RADIUS_FWHM = 0.4` — a fit wanting to move further is a
      detection failure, not a small offset).
- [ ] Factor the esd helper (`Cov = χ²_red·pinv(JᵀJ)`) out of
      `optimize/least_squares.py` into one shared function so the two surfaces
      cannot disagree about pinv guarding.
- [ ] `pick_peaks` public entry + `pxrdref/__init__.py` export; ghost flagging;
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

- **2026-07-29** — created from the indexing plan. Prototype prior art is
  pinned at the tag `guillemot-study`, **read without merging** (see
  References): `git show guillemot-study:studies/guillemot/index_hl2.py`. Read
  `peak_list` before starting — it is exactly the crude version this WP
  replaces, and its measured failure modes (`net.max()`-relative prominence,
  no σ) are the design constraints here.
