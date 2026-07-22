# pxrd-refine — Roadmap & Design Record

This is the canonical planning document: milestone tracking plus the design
rationale behind the architecture. It was produced from a researched,
adversarially-reviewed plan (two review passes: a design critique and a
fact-check of load-bearing technical claims) and is updated as milestones
land. Keep it current — when a task ships, check it off and record the
measured acceptance result.

---

## Milestone status

| Milestone | Scope | Status | Acceptance |
|---|---|---|---|
| v0.1 | Vertical slice: synchrotron CW, Rietveld + Le Bail | ✅ **shipped** | 11-BM NAC: a = 10.251285(12) Å, Rwp 9.2%, CaF₂ impurity auto-flagged |
| v0.2 | Lab diffractometer + FitReport attribution + viz | ✅ **shipped 2026-07-22** | SRM 660c LaB6: a = 4.156895(25) Å (+28 ppm vs NIST value for this dataset, Bérar-Lelann-inflated esd), Rwp 8.7%; GSAS-II FAP tutorial: Rwp 9.73% vs GSAS's 10.05% on identical channels, cell +116 ppm (uniform d-scale convention offset) |
| v0.3 | Multi-phase QPA, Pawley, aniso ADPs, multi-histogram | ⬜ | SRM 676a / IUCr QPA round-robin fractions |
| v0.4 | JAX backend: autodiff Jacobians, CUDA, mixed precision | ⬜ | cross-backend Jacobian agreement CI |
| v0.5 | Corrections & microstructure (absorption, Stephens, f′f″) | ⬜ | capillary/absorption vs GSAS-II consistency |
| v0.6 | TOPAS-style bounded LM, agent surface, torch-MPS | ⬜ | solver benchmark vs scipy TRF |
| v1.0 | Hardening, API freeze, PyPI | ⬜ | full validation matrix green |
| v2+ | FPA, neutron/TOF, texture, MCP server | ⬜ fenced | — |

---

## v0.1 — vertical slice ✅ (shipped 2026-07-22)

- [x] Repo scaffold: pyproject (hatchling), MIT LICENSE, ATTRIBUTION.md, uv venv
- [x] pydantic v2 schemas with JSON round-trip (`extra="forbid"`, ±inf-safe serialization)
- [x] CIF import/export (gemmi); U_eq fallback from anisotropic ADPs
- [x] Symmetry: gemmi ops, Rᵀ reciprocal orbit counting, absences, multiplicities
- [x] Waasmaier-Kirfel form factors (DABAX table, vendored with attribution)
- [x] Structure factors over frozen per-atom symmetry-op subsets
- [x] TCHZ pseudo-Voigt (canonical TCH Γ/η polynomials), Caglioti + size/strain widths
- [x] Lp correction (documented σ-polarization convention, K=0.5 lab / 0.99 synchrotron)
- [x] IntensityModel seam: `rietveld` + `lebail` modes, multi-phase capable
- [x] Backgrounds: shifted Chebyshev (analytic Jacobian columns), arPLS (banded Whittaker), SNIP
- [x] ParameterTable: dot-path compile, crystal-system cell ties, softplus/logit transforms
- [x] scipy TRF driver, mixed analytic/FD Jacobian, esds from χ²·(JᵀJ)⁻¹, guards
- [x] Staged runner (McCusker order), frozen hkl/windows per stage
- [x] FitReport Layer 0: cumulative-χ², per-region Rwp/χ²-share, unmatched-peak lists
- [x] Readers (.xy/.xye/GSAS fxye/gsas, file esds win), matplotlib obs/calc/diff/ticks plot
- [x] 31 tests: unit + hypothesis property + synthetic round-trip + real-data acceptance

**Measured acceptance** (`tests/test_acceptance_nac.py`, APS 11-BM NAC, λ=0.4139090 Å):
Le Bail converged (a=10.251109); two-phase Rietveld a = 10.251285(12) Å,
Rwp = 9.2%, GoF = 3.5. FitReport unmatched peaks decoded to fluorite
111/220/311/422 → CaF₂ impurity phase added and refined (a = 5.463 Å).
Residual misfit budget is dominated by low-angle axial asymmetry — the
planned v0.2 FCJ feature.

---

## v0.2 — lab diffractometer, attribution, viz ✅ (shipped 2026-07-22)

Acceptance: refine the **NIST SRM 660c LaB6 certification profiles**
(CuKα + graphite analyzer, `tests/data/nist_srm660c_100a.cif`, 5332 points)
and the GSAS-II tutorial lab pattern (`tests/data/FAP.XRA`, fluorapatite,
5753 points).  **Both shipped and measured** — see the two acceptance blocks
below.  The original criterion "refined cell within the certificate value ±
combined uncertainty" is **not met for SRM 660c and is not claimed**: the
measured +28 ppm offset is a real, characterised systematic (unmodelled
flat-specimen divergence / tube tails / monochromator passband — FPA
territory, fenced for v2), and the honest bands are stated per test rather
than the criterion being quietly relaxed.  The fluorapatite dataset meets its
cross-code criterion outright (Rwp 9.73 % vs GSAS's 10.05 % on identical
channels).

**Measured acceptance — SRM 660c** (`tests/test_acceptance_srm660c.py`,
2026-07-22, NIST-protocol fit: goniometer calibrated ⇒ zero fixed,
displacement refined): converged in 1.5 s (2.4 s before the analytic
Jacobian columns landed), Rwp = 8.7 %, GoF = 1.87,
**a = 4.156895(25) Å** vs NIST's own recomputed cell for this dataset
4.156780 Å at 20.85 °C → **+1.15×10⁻⁴ Å (+28 ppm)**.  The esd carries the
Bérar-Lelann serial-correlation inflation (factor 3.4 here; the raw
χ²·(JᵀJ)⁻¹ esd is 7×10⁻⁶ Å).  Physics cross-checks: refined specimen
displacement −0.0801 mm vs the CIF's −0.07877 mm (1.3 µm); refined
Kα2/Kα1 = 0.513 vs Hölzer's integrated 0.52.
The certificate-level ±8×10⁻⁶ band is **not met and not claimed**: swapping
which shift terms refine (zero+displacement vs displacement-only) brackets
the reference symmetrically at [−1.1, +1.2]×10⁻⁴, i.e. the residual is a
systematic cotθ/sin2θ-signature aberration the model lacks — flat-specimen
(equatorial divergence) error, tube tails and the graphite-passband spectrum
shift, all fundamental-parameters territory (v2).  Transparency, when freed,
pins at its physical ≥0 bound (LaB6 is opaque) — consistent with that
reading.  Layer 1 of the FitReport, run on this fit, correctly declares the
remaining position/width trends *non-separable* (residual-SS ratio ≈ 1
between templates) and keeps every suggestion below confidence 0.1 — the
"never a confident wrong singleton" behaviour, on real data.

**Measured acceptance — GSAS-II LabData fluorapatite**
(`tests/test_acceptance_fap.py`, 2026-07-22, cross-code consistency vs
GSAS's converged `FAP.EXP`, protocol mirrored from its refine flags: zero
held, displacement refined, GU/GV/GW held, sample LX/LY refined, >130°
excluded → identical 5750 channels): **Rwp = 9.73 % vs GSAS's 10.05 %,
Rp = 7.76 % vs 7.66 %**; Lorentzian sample size 0.0323° vs GSAS's
LX = 0.0335°; a = 9.372807, c = 6.886642 Å vs 9.371724(36)/6.885867(37) —
**+116/+113 ppm**, the same relative offset on both axes ⇒ a uniform
d-scale (peak-position convention) difference, not a structural/shape
disagreement (GSAS's `shft` converges opposite in sign to our displacement —
the same statement seen from the other side).  Tolerance ±300 ppm as a
consistency band per the validation policy.

Physics / engine:
- [x] Bragg-Brentano geometry: sample displacement (−2s·cosθ/R, refinable, mm), transparency (−t·sin2θ, refinable coefficient) — `Geometry` schema + `corrections.py`, active only for `bragg_brentano`
- [x] Kα1/Kα2 **per-line Bragg dispersion** (splitting grows with tanθ — never a fixed Δ2θ; each line gets its own Bragg angle, widths, Lp), refinable intensity ratio (line-0 weight structurally locked against scale degeneracy); `Instrument.bragg_brentano(radiation="CuKa")` preset on the NIST/Hölzer wavelength scale (Kα1 1.5405929 Å). Hölzer multi-Lorentzian emission option still open
- [x] Finger-Cox-Jephcoat axial asymmetry: singularity-removing ξ-variable transform, **fixed quadrature nodes per stage** (node counts frozen at compile; sized even when refining axial from 0 via `free_paths`), quadrature **split at the overlap-trapezoid kink** so nodes never sweep across it (keeps ∂y/∂(S/L) C¹ — verified by an O(h²) second-difference scaling test); validated against a dense direct 2φ-space integral of the singular FCJ density to <1 % (GSAS-II runs are a v0.3 consistency-check target)
- [x] pdCIF reader (`read_pdcif`): `_pd_proc`/`_pd_meas` loops, σ from su columns or `_pd_proc_ls_weight` (σ = 1/√w), multi-block selection
- [x] `lab_bragg_brentano` staged-plan preset (McCusker order + displacement with zero, Kα2 ratio + axial last)
- [x] Bugfix found by the new tests: `set_vary` glob could re-free *structurally fixed* entries (symmetry-fixed cell angles matched by `phases.*.cell.*`, line-0 weight) — entries now carry a `locked` flag that globs can never free
- [x] Instrument ⊕ sample profile split: per-phase `gauss_size` (P/cos²θ) and `gauss_strain` (tan²θ) Gaussian *variances* add to the Caglioti U V W; `lor_size`/`lor_strain` FWHMs add to X Y (already v0.1).  Workflow shipped as `lab_calibrate` (certified standard cell **held fixed** — that pins the dispersion axis and decorrelates the {zero, displacement, cell} triple; measured: freeing the cell during calibration splits a true 0.012° zero into 0.024° zero − 0.022 mm displacement) → `save_instrument_profile`/`load_instrument_profile` (JSON; background + displacement/transparency stripped as measurement-not-instrument, everything loads `vary=False`) → `lab_sample_refine` (frees only the four sample terms + displacement/cell/scale/bkg/Biso).  Synthetic roundtrip test recovers lor_size/gauss_strain with the instrument bit-frozen
- [x] Analytic Jacobian columns via the peak-derivative chain rule: exact per-point bases {Ω, ∂Ω/∂pos, ∂Ω/∂Γ, ∂Ω/∂η (+ FCJ node derivatives for S/L, H/L)} computed once per Jacobian call, chained through cheap per-reflection scalar FD of `phase_peaks` — covers cell→2θ, zero/displacement/transparency, U V W X Y, size/strain, scale, occ, Biso, polarization, line weights *and* the axial ratios; plain FD survives only as a fallback.  Agreement test vs FD: <5×10⁻³ relative, cosine >0.99999 over 18 parameter families; SRM 660c wall-clock 2.4 → 1.5 s
- [x] Bérar-Lelann esd inflation (Bérar & Lelann 1991), applied to reported esds and surfaced as `Statistics.esd_inflation`.  Documented conservatism: iid-Gaussian residuals give E[χ²']/χ² = 1 + 4/π ⇒ factor ≈ 1.51 even for white noise (derived analytically, verified by simulation in the tests; Andreev 1994 addresses the bias — paywalled, formula not reproduced).  SRM 660c factor: 3.4
- [x] GSAS-II tutorial lab pattern (LabData fluorapatite) as a second acceptance dataset — measured result above; `read_pattern` now detects GSAS raw files by their BANK record instead of suffix (the format ships as `.xra`/`.gda`/`.raw`/…)

Background subsystem (automation-first):
- [x] Pattern diagnostics object (`background.diagnose` → `PatternDiagnostics`): peak fraction/density, S/B, amorphous-hump score, air-scatter detection, Kβ + W-Lα contamination flags (Hölzer/Bearden line positions, same-d ghost matching).  Design finding recorded: baseline-*shape* questions are answered from a rolling low-quantile envelope, **not** an arPLS baseline — a λ stiff enough to be safe under peaks is too stiff to follow a real hump (measured), and the diagnostics must not depend on a λ that is itself being selected.  Air scatter is a *nested-model gain* (RSS drop from adding a 1/x column to a cubic envelope fit: 0.85 on synthetic air scatter, 0.0001 on flat — cleanly separable from the hump score)
- [x] Auto-selection (`background.select`): masked-channel BIC + Durbin-Watson whiteness stop for the Chebyshev order; largest-λ-with-white-masked-residuals rule for arPLS λ; both return evidence tables (`BackgroundSelection.scores`) for agent inspection.  `auto_background()` is the one-call entry (knot spacing from the hump score, air term on trigger)
- [x] Penalized P-spline co-refined background (`BackgroundPSpline`): clamped cubic B-spline design (linear ⇒ exact Jacobian columns incl. the penalty block), √λ·D₂·c smoothness rows appended to the residual (Eilers & Marx 1996), optional softplus-bounded 1/x air term; statistics and the Bérar-Lelann factor are computed on the **data rows only** (run-of-sign statistics over penalty rows would be meaningless) while the covariance keeps them, so (J_dᵀJ_d + λD₂ᵀD₂)⁻¹ is the regularised covariance the esds come from
- [x] Background↔ADP/scale guardrail as a **block projection**, not a pairwise ρ: R²ᵢ = ‖P_B jᵢ‖²/‖jᵢ‖², the fraction of a structural parameter's Jacobian column reproducible by the background column span (`optimize.statistics.background_absorption`, surfaced as the `BACKGROUND_ABSORPTION` diagnostic).  Pairwise correlation is the wrong statistic here — with ~60 spline coefficients each individual |ρ| stays ≈0.2 while the block collectively absorbs 46 % of a Biso column (measured, which is why the first implementation's ρ-threshold guard never fired).  Separation: sane backgrounds (Chebyshev-6, the default 8°-knot penalized spline) sit at 0.01-0.03 even against deliberately broad peaks; a 1°-knot *unpenalized* spline reaches 0.46; the same knots at λ=10⁴ drop to 0.08 — the penalty rows measurably doing the job they exist for.  Guard threshold 0.25

FitReport Layers 1-2 (`report/` package; see design record below for the spec):
- [x] Layer 1 (`report/layer1.py`): gated derivative-basis misfit attribution — per region, the residual is projected onto the analytic shape basis {Ω, ∂Ω/∂pos, ∂Ω/∂Γ, ∂Ω/∂η, ∂Ω/∂(S/L)} in one joint weighted solve with Gram covariance, so results are stated as physics ("peaks 0.008° low, 5 % weak") independent of which parameters are free.  Four gates, each with a measured justification:
  - **resolvability** on the *scale-normalised* Gram condition (the raw one is dominated by the units of ∂Ω/∂pos vs Ω — measured 7×10³…1×10⁶ regardless of separability, vs 17…6×10⁴ normalised, which actually discriminates);
  - **validity radius** 0.4·FWHM — a shift approaching it is recovered with a systematic deficit (measured: −0.0143° for a 0.020° injection vs −0.008 exactly for 0.008°), so beyond it the answer is "re-detect, don't linearise";
  - **no-significant-misfit** (local χ²_red ≤ 1.5): a region already fitted to the noise has nothing to attribute, which is *not* the same as the basis failing — without this a converged fit abstained;
  - **global maturity**, share-based: abstain when misfitting regions carry >20 % of χ² but <40 % of that sits in gate-passing regions.  A fit with no significant misfit does **not** abstain — "nothing to attribute" is a legitimate answer.
  hkl-grouped trends fit each angular template *singly* (nested model comparison, per the design record) — a joint fit of collinear templates is ill-posed and returned physically absurd amplitudes (measured: a 0.02° zero error came back as +1.8° "constant" cancelled by −1.8° "cosθ").  Separability is the **residual-SS ratio** between best and runner-up, not an R² gap (every template scores R²≈0.99 against a clean trend, so R² gaps are ~10⁻³ and meaningless; the ratio spans 1.0…10 on the same data)
- [x] Layer 2 (`report/layer2.py`): typed closed-enum `suggested_actions` with confidence/alternatives/expected-Δχ²; **strategy-engine veto** (`apply_strategy_veto` annotates rather than drops, so the reasoning survives); `predict_then_verify` runs the action on a history *branch* and rolls back structurally when χ² does not improve; Hamilton (1965) R-ratio F-test + ΔBIC gate new parameters.  Confidence is weighted by **importance, not just significance** — at high counting statistics the second-order leakage of a peak shift into the width column (y(x−δ) ≈ y − δy′ + ½δ²y″) is many-σ significant while carrying ~1 % of χ², and without the misfit-share weighting it outranked the true cause.  Model-free actions (unindexed peaks) survive Layer-1 abstention, since a missing phase is a common *reason* for immaturity
- [x] Synthetic misfit-injection test suite + confidence calibration (`tests/test_fitreport_layers.py`, 18 tests): single-cause injections for zero/displacement/width/scale/impurity are each recovered and ranked first with confidence ≈0.99 (4/4); the gates are tested from the failing side too (gross cell error trips the validity radius; a grossly wrong model abstains; a 20-56° window reports the position templates as non-separable rather than picking a winner).  Bug found by this suite: `RefinementResult.ticks` carried only the primary wavelength, so **every Kα2 peak was flagged as an unindexed impurity** on any lab pattern
- [x] `plot_for_vlm()`: annotated multi-panel PNG montage (full pattern with worst-N regions shaded and unmatched peaks marked, Δ/σ panel with a ±3σ band, worst-N regions auto-zoomed and titled with their exact numbers); refuses non-PNG paths — JPEG block artifacts destroy exactly the thin peak/difference lines a VLM is asked to judge

History / events:
- [x] **Refinement history DAG** (`history/`, `schemas/history.py`): every stage
  auto-commits an immutable, restorable node (state — not curves — so a node is
  ~10 kB against ~1.24 MB with curves embedded, measured on 11-BM NAC);
  append-only JSONL; git-style refs with `head` + `tag`; `checkout`/`run_stage`/
  `branch`/`from_node` for branching, `replay` for evaluate-only recompute,
  `best`/`compare`/`diff`/`summary`/`to_mermaid` for queries. `parents` is a
  list, so combining branches stays open without a format break. `history=False`
  is a zero-overhead path and `refine()` defaults to it. Recording costs
  ~0.4 ms/stage vs ~18 ms of unavoidable compile; `Refinement.fit` is
  bit-for-bit unchanged (verified against pre-change code on 11-BM NAC:
  a = 10.251212432319, Rwp = 0.140251138904)
- [x] `history/events.py` per-iteration stream on the same JSONL record style (`fit_start`/`stage_start`/`eval`/`stage_end`/`fit_end`).  scipy TRF exposes no per-iteration callback, so the **residual closure itself is the hook** and `n_eval` counts every call (function + FD), which is what actually tracks wall-clock progress.  The hot path is `json.dumps` on a plain dict — the pydantic `EventRecord` exists only for reading logs back.  `events=` accepts a path, a callable, or an `EventStream`
- [x] plotly Scattergl HTML viewer (`viz/html.py`): self-contained single file (~5 MB with plotly.js embedded; `include_plotlyjs="cdn"` trades offline use for ~10 kB).  Decimation is **min-max per bucket, never striding** — striding drops peak tops, and a viewer that silently removes the peaks is worse than no viewer (tested: a lone 10⁶ spike among 50 001 points survives decimation to 2 000)
- [x] `pxrdref watch` (`watch.py` + `viz/live.py`): `LiveSession` writes `events.jsonl`, and rewrites `fit.html`/`status.json` per stage via an **atomic tmp-then-rename** so the poller never reads a torn file; the server is stdlib `http.server` with an auto-refresh page and a **console pane** tailing the event stream (no FastAPI, no websockets, no JS build).  `pxrdref` console-script entry point added
- [x] Branch merge and cherry-pick.  `merge` is a genuine three-way merge against `tree.common_ancestor` (git semantics: one-sided changes taken, two-sided resolved by `prefer`), recording **both** parents — the reason `parents` was a list from the start.  Only parameter *values* merge; model composition comes from the preferred side whole, since merging a phase-added branch into a phase-removed one path-by-path is meaningless.  `cherry_pick` replays a node's recorded stage *action* (not its values) on the current state — the enabling piece for v0.5 `SequentialRefinement`

## v0.3 — multi-phase workflows

- [ ] QPA: Hill-Howard ZMV mass fractions + Brindley microabsorption
- [ ] Pawley mode (per-hkl intensities in the parameter vector, near-singular normal-equation handling). History already reserves the container: populate `ReflectionState` with `kind="pawley_refined"` (+ `stderr`, `varied`) so per-hkl parameters never enter `RefinementState.free_paths` one dot-path at a time
- [ ] Anisotropic ADPs with spglib Wyckoff/site-symmetry constraint derivation (cross-check vs cctbx tables); **atomic-coordinate refinement lands here** (affine constraint matrix p_phys = C·p_free + d)
- [ ] March-Dollase preferred orientation
- [ ] Multi-histogram stacked residuals exercised (parameter-sharing map; API already accepts lists)
- [ ] Exporters: reflection table (hkl, d, 2θ, F², I), CIF with esds, QPA table
- [ ] Acceptance: NIST SRM 676a corundum + IUCr QPA round-robin mixtures within documented tolerances

## v0.4 — differentiable backend (JAX)

- [ ] ~40-op backend shim (`backend/api.py`); per-backend `scatter_add` (not in the Array API standard)
- [ ] jax backend: chunked `jacfwd` Jacobians (cost ≈ N_params × forward — the win is exactness + jit, not fewer evals)
- [ ] CUDA + mixed precision: fp32 Jacobian *columns* only; residual for cost/statistics and the solve stay fp64 on host (fp32 y_calc at ~10⁵ counts loses ~10 counts to cancellation)
- [ ] Never toggle jax's global x64 flag on import; fp64 lives in host numpy (`linalg64.py`)
- [ ] Cross-backend Jacobian-agreement CI (analytic vs FD vs jacfwd, incl. stage boundaries)
- [ ] True Voigt via one shared backend-agnostic Weideman/Humlíček Faddeeva w(z) (jax has `wofz`; torch does not — one implementation everywhere for gradient consistency)
- [ ] Restraint penalty rows in the residual

## v0.5 — corrections & microstructure

- [ ] Capillary (Debye-Scherrer) and flat-plate absorption (Sabine 1998 / Lobanov-Alte da Veiga)
- [ ] Surface roughness (Pitschke 1993 / Suortti 1972)
- [ ] Stephens 1999 anisotropic strain broadening (S_HKL invariants per Laue class)
- [ ] Anomalous f′,f″ at arbitrary λ via **xraydb** (Cromer-Liberman + Chantler; periodictable's Henke tables cap at 30 keV — wrong tool)
- [ ] SequentialRefinement with warm start (in-situ series)

## v0.6 — solver & agents

- [ ] TOPAS-style bounded LM: Gauss-Newton normal equations + adaptive Marquardt λ (Coelho 2018, JAC 51:428) + bound-constrained CG inner solve (Coelho 2005, JAC 38:455) + line search — independent implementation from the papers, same driver interface as the scipy path
- [ ] Agent JSON surface hardened: `agent.refine_json(dict) → dict`, JSON-Schema export for tool-calling
- [ ] torch backend with MPS fp32 forward (the Mac GPU path; no Apple GPU has fp64 in any framework)
- [ ] Sphinx + MyST theory manual: numbered equations cross-referenced from docstrings (sphinxcontrib-bibtex)

## v1.0 — hardening & release

- [ ] Validation matrix green: NIST certificates as **absolute anchors** (with stated uncertainties); GSAS-II as a *consistency* check with tolerances that respect legitimate inter-code convention differences (not 1e-4 Å ground truth)
- [ ] Three-tier tolerance policy documented per test (exact / tight-scientific / statistical)
- [ ] CI: linux + macOS, Py 3.11-3.13 (+3.14 allow-fail); `[jax]`/`[torch]` optional jobs; nightly heavy validation with fetched data
- [ ] API freeze, PyPI release (name `pxrd-refine` verified available)

## v2+ (seams pre-built, implementations fenced out)

Fundamental Parameters Approach as a differentiable convolution stack
(Cheary-Coelho 1992); neutron CW; TOF (new Source/Profile implementations
behind the frozen seams); spherical-harmonics texture (Von Dreele 1997);
rigid bodies; MCP server wrapping `refine_json`; internal-standard/amorphous
QPA; `vmap`-batched in-situ series; GUI/notebook widgets.

---

# Design record

## Why this package exists

Existing Rietveld codes (GSAS-II, FullProf, TOPAS, BGMN/Profex, RIETAN,
MAUD…) are GUI-first; every recent automation/agentic effort (MCP servers
over GSAS-II, RPA over RIETAN, TOPAS `.inp` generation by LLMs) is a shim
bolted onto them. TOPAS earned its industry-standard status largely through
its minimizer: full-matrix Newton + Marquardt damping + line search, a
bound-constrained conjugate-gradient normal-equation solver (Coelho 2005,
~84× faster than LU), and **exact analytic derivatives via computer algebra**
(Coelho 2018) — the closed-source analog of autodiff. As of mid-2026 no
differentiable/GPU-native, API-first open-source Rietveld engine existed.
pxrd-refine fills that gap: typed schemas, JSON round-trip, staged strategies,
and machine-readable diagnostics, with the forward model written to stay
differentiable from day one.

## Locked decisions

- **Backend**: numpy/scipy fp64 core (~50 MB default install); forward model
  kept differentiable; optional `[jax]` (v0.4) then `[torch]` (v0.6) extras.
  Hard constraint discovered in research: **no Apple GPU supports fp64 in any
  framework** (MPS/MLX fp32-only; jax-metal abandoned), and JᵀJ squares the
  condition number ⇒ GPUs compute fp32 Jacobian columns only, fp64 host solve.
- **Scope**: constant-wavelength X-ray powder first; `Source`/`Geometry`/
  profile/`IntensityModel` are the frozen extension seams for neutron/TOF/FPA.
- **License**: MIT. Port only from permissive sources (CrysPy MIT, cctbx
  BSD-style, Dans_Diffraction Apache-2.0, pymatgen MIT, lmfit BSD-3,
  pybaselines BSD-3, GSAS-II BSD-style — verify its LICENSE before any
  snippet reuse). **GPL codes (BGMN, Profex, xrayutilities) are studied
  conceptually only — never ported.** TOPAS/FullProf: papers only.
- **Scope discipline** (review finding: this is multi-person-year work):
  one autodiff backend at a time; MCP/FPA/neutron/TOF fenced in v2; every
  milestone has a concrete measured acceptance test.

## Architecture invariants

(Also in CLAUDE.md — duplicated here because they are design decisions.)

1. **Frozen-per-stage discreteness.** hkl lists, symmetry-op subsets,
   FCJ quadrature nodes, and per-(line, reflection) window index ranges are
   computed at stage compile and never change during a least-squares run;
   regenerate only between stages. Freezing the hkl list alone is *not*
   enough — window membership depends on refined cell/zero parameters and
   creates gradient bias exactly on the parameters that matter most.
   FCJ detail learned in v0.2: freezing node *counts* is still not enough if
   fixed-fraction nodes sweep across the overlap-trapezoid kink at
   ξ = |S/L − H/L| as the axial parameters refine (O(h) steps in the
   derivative); the quadrature is therefore *split at the kink* into two
   Gauss-Legendre segments whose endpoints track the parameters smoothly.
2. **fp64 correctness boundary.** The residual used for cost/statistics and
   the parameter solve/covariance are always fp64 on host. GPU fp32 is
   restricted to Jacobian columns (relative-accuracy tolerant).
3. **No pydantic in the hot loop.** The tree compiles once per stage to
   static index maps; per-iteration decode is plain float/array work.
4. **Weighting.** File esd columns always win; Poisson √max(y,1) is a
   fallback with a diagnostic when data look normalized. Estimated
   backgrounds are held additively, never subtracted (keeps weights valid).
5. **Documented physics.** Every equation cites author/year/journal in its
   docstring; conventions documented by physics, not letters (size↔1/cosθ,
   strain↔tanθ; GSAS and FullProf swap the X/Y labels).

## Parameter system

lmfit-style `Parameter{value, vary, min, max, expr, transform}` on every
refinable scalar. Compile: tree → partition free/tied/fixed → flat fp64 θ.
Symmetry and linear ties are one affine map p_phys = C·θ + d (constant
matmul — exact under autodiff); v0.1 implements the identity-tie subset
(crystal-system cell constraints), v0.3 generalizes to Wyckoff constraints.
Nonlinear ties (`expr`) will use a tiny AST-whitelisted DSL emitted as
backend ops — **asteval and sympy were evaluated and rejected** (asteval
cannot run on autodiff tracers; sympy's torch lambdify printer is immature).
Transforms: identity + native TRF bounds by default; softplus for widths and
scales (hard lower bounds stall TRF); logit for occupancies.

## Minimizer strategy

v1 workhorse: `scipy.optimize.least_squares(method="trf")` — fp64, box
bounds, accepts our Jacobian callable. The Jacobian is assembled from exact
analytic columns where the model is linear (Chebyshev coefficients = design
matrix rows; Rietveld phase scales = phase component / scale) plus forward
differences for nonlinear parameters; v0.2 adds closed-form cell→2θ and
width columns (the dominant FD cost), v0.4 adds jacfwd. v0.6 adds the
TOPAS-style bounded LM as an alternative driver behind the same interface.
Esds from χ²_red·(JᵀJ)⁻¹ with pinv guarding singular normal matrices;
Bérar-Lelann inflation in v0.2. Guards: correlation threshold, bound hits,
divergence — surfaced as structured diagnostics.

## Background subsystem (automation-first)

Two-stage default: (1) diagnostics on the raw pattern → structured object an
agent can reason over; (2) robust estimate via arPLS (default) / iarPLS
(amorphous hump) / SNIP (dense patterns), λ auto-selected; then either hold
the estimate additively + small Chebyshev correction (v0.1 behavior) or —
the v0.2 default — co-refine a **penalized P-spline** whose 2nd-difference
smoothness penalty rides as extra residual rows: linear, differentiable,
esd-propagating, and physically unable to absorb broad Bragg intensity (the
documented nanocrystalline/QPA failure mode). Precedent: GSAS-II's 2024-25
auto-background wraps pybaselines' Whittaker methods into fixed points; we
make the penalized spline first-class in the least squares. pybaselines
(BSD-3) stays an optional extra for its full algorithm zoo.

## Outputs & fit assessment (the agent-native design)

Humans judge fits by looking — especially at peak-shape misfit — not by Rwp.
VLM benchmarks (CharXiv, ChartMuseum, ExChart) show frontier models fail
precise value extraction from dense plots, and one PNG costs ~1,000-1,600
tokens ≈ 50 regions of exact numbers. All three prior agentic Rietveld
systems (AgentBuild, Rongzai, guillemot) feed plot images to a VLM and all
report the same gap: locally-bad/globally-fine fits. Hence the FitReport,
three gated layers:

- **Layer 0 — model-free (always trustworthy, ships in v0.1).** All
  quantities w-weighted. Residual peak-finding; obs↔calc matching →
  `unmatched_obs` (impurity candidates) / `unmatched_calc`; cumulative-χ²
  breakpoints (David 2004); low-frequency vs sharp residual decomposition;
  Le Bail-vs-Rietveld Rwp gap (structural-vs-profile triage).
- **Layer 1 — gated linear attribution (v0.2).** Regions from the *union* of
  calc ticks and observed/residual peaks (segmentation must not be circular).
  Per region, a per-reflection shape-derivative basis {Ω, ∂Ω/∂pos, ∂Ω/∂width,
  ∂Ω/∂η, ∂Ω/∂asym} — built analytically from the profile, *not* the parameter
  Jacobian — fit as one joint weighted solve with the Gram covariance and
  condition number reported (the basis is non-orthogonal; independent
  dot-products cross-contaminate). Gates: local R², validity radius
  (~0.3-0.5 FWHM — a peak 5 FWHM off must trigger "re-detect, don't
  linearize", never a confident small-offset reading), overlap resolvability,
  and a global maturity gate that makes the report **abstain** from
  parameter-level output when the model is immature. Plus hkl-grouped
  intensity (Q-trend→ADP, element→occupancy, axis-angle→March-Dollase) and
  width (direction→Stephens) analyses that per-region views structurally miss.
- **Layer 2 — typed suggested actions, advisory only (v0.2).** Trend
  regression against constant/cosθ/secθ (zero/displacement/cell) and
  1/cosθ vs tanθ (size/strain) templates as nested model comparison with
  inter-template correlations — over narrow 2θ ranges these are collinear
  (Williamson-Hall separability), so ambiguity is reported, never a
  confident wrong singleton. Closed-enum versioned action schema; the
  **staged-strategy engine holds veto authority**; predict-then-verify with
  rollback; Hamilton/ΔBIC justification before adding parameters. Token
  *budget*: top-N regions verbatim + aggregate rollup; thresholds pinned and
  versioned in provenance for reproducible agent behavior.

Images are secondary evidence: `plot_for_vlm()` renders what VLMs *can* read
(annotated multi-panel montage, worst regions auto-zoomed from the report,
Δ/σ panel, high contrast, never JPEG).

Human GUI (bumps/refnx precedent, never Qt/wx in base): plotly Scattergl
self-contained HTML default; live monitoring by rewriting HTML/JSON per stage
+ a stdlib-http auto-refresh page (`pxrdref watch`) with a **console pane**
tailing the structured event stream — every line paired with its equivalent
API call, so the log doubles as a reproducible session script. Zero viz deps
in the base install; the FitReport itself is pure numpy.

## Testing & validation policy

- Unit tests against published values (form factors, multiplicities,
  absences, TCH polynomials); hypothesis property tests (profile
  normalization, F symmetry invariance, Jacobian agreement incl. stage
  boundaries).
- FitReport validation by **synthetic misfit injection**: perturb exactly one
  known cause, assert the report recovers it, ranks it first, and reports
  *low confidence* in deliberately-collinear setups; calibration over the
  injection ensemble. Without this the confidence numbers are decorative.
- Absolute accuracy anchors to NIST certificates (with stated uncertainties);
  GSAS-II results are consistency checks with convention-aware tolerances.
- Real-data acceptance per milestone, committed in `tests/` and marked
  `slow`; provenance for every dataset in `tests/data/README.md`.

**Learned in v0.2 — comparing against another code means adopting its
protocol, not just its numbers.** The fluorapatite acceptance was built by
reading GSAS's converged `FAP.EXP` refine flags and mirroring exactly what it
refined (zero held, displacement refined, GU/GV/GW held, sample LX/LY
refined, >130° excluded). Guessing a plausible protocol instead gave Rwp
16 % and a +390 ppm cell; the mirrored one gives 9.73 % against GSAS's
10.05 % on a channel count that matches its record exactly (5750). A
cross-code number computed over different channels with a different free set
is not a comparison.

**And a disagreement's *shape* is evidence.** The residual +116/+113 ppm cell
offset is the same relative amount on both axes — a uniform d-scale
(peak-position convention) difference, not a structural one. The test asserts
that uniformity explicitly, so the tolerance encodes a characterised
systematic rather than a shrug.

## Risks & mitigations

Ill-conditioning → staged strategy, guards, reparameterization, cond
reporting. Background eating peaks → penalized spline + correlation
guardrails. fp32 contamination → fp64 host residual/solve + agreement gate.
Backend drift → small op vocabulary + mandatory cross-backend tests.
**Scope (the biggest risk)** → strict per-milestone acceptance tests, one
backend at a time, a real v2 fence, and the validation suite doubling as the
recruiting hook for co-maintainers. Licensing → GPL never ported; provenance
documented in ATTRIBUTION.md. Performance → analytic columns (v0.2), jax jit
(v0.4); honest documentation that the numpy-FD path is the slow-but-correct
reference.
