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
| v0.2 | Lab diffractometer + FitReport attribution + viz | 🔶 **in progress** — lab physics core shipped 2026-07-22 | SRM 660c LaB6: a = 4.156895(7) Å (+28 ppm vs NIST value for this dataset), Rwp 8.7% |
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

## v0.2 — lab diffractometer, attribution, viz

Acceptance: refine the **NIST SRM 660c LaB6 certification profiles**
(CuKα + graphite analyzer, already in `tests/data/nist_srm660c_100a.cif`,
5332 points) and the GSAS-II tutorial lab pattern; refined cell within the
certificate value ± combined uncertainty.

**Measured acceptance so far** (`tests/test_acceptance_srm660c.py`,
2026-07-22, NIST-protocol fit: goniometer calibrated ⇒ zero fixed,
displacement refined): converged in 2.4 s, Rwp = 8.7 %, GoF = 1.87,
**a = 4.156895(7) Å** vs NIST's own recomputed cell for this dataset
4.156780 Å at 20.85 °C → **+1.15×10⁻⁴ Å (+28 ppm)**.  Physics
cross-checks: refined specimen displacement −0.0801 mm vs the CIF's
−0.07877 mm (1.3 µm); refined Kα2/Kα1 = 0.513 vs Hölzer's integrated 0.52.
The certificate-level ±8×10⁻⁶ band is **not yet met**: swapping which shift
terms refine (zero+displacement vs displacement-only) brackets the reference
symmetrically at [−1.1, +1.2]×10⁻⁴, i.e. the residual is a systematic
cotθ/sin2θ-signature aberration the model lacks — flat-specimen (equatorial
divergence) error, tube tails and the graphite-passband spectrum shift, all
fundamental-parameters territory (v2).  Transparency, when freed, pins at
its physical ≥0 bound (LaB6 is opaque) — consistent with that reading.

Physics / engine:
- [x] Bragg-Brentano geometry: sample displacement (−2s·cosθ/R, refinable, mm), transparency (−t·sin2θ, refinable coefficient) — `Geometry` schema + `corrections.py`, active only for `bragg_brentano`
- [x] Kα1/Kα2 **per-line Bragg dispersion** (splitting grows with tanθ — never a fixed Δ2θ; each line gets its own Bragg angle, widths, Lp), refinable intensity ratio (line-0 weight structurally locked against scale degeneracy); `Instrument.bragg_brentano(radiation="CuKa")` preset on the NIST/Hölzer wavelength scale (Kα1 1.5405929 Å). Hölzer multi-Lorentzian emission option still open
- [x] Finger-Cox-Jephcoat axial asymmetry: singularity-removing ξ-variable transform, **fixed quadrature nodes per stage** (node counts frozen at compile; sized even when refining axial from 0 via `free_paths`), quadrature **split at the overlap-trapezoid kink** so nodes never sweep across it (keeps ∂y/∂(S/L) C¹ — verified by an O(h²) second-difference scaling test); validated against a dense direct 2φ-space integral of the singular FCJ density to <1 % (GSAS-II runs are a v0.3 consistency-check target)
- [x] pdCIF reader (`read_pdcif`): `_pd_proc`/`_pd_meas` loops, σ from su columns or `_pd_proc_ls_weight` (σ = 1/√w), multi-block selection
- [x] `lab_bragg_brentano` staged-plan preset (McCusker order + displacement with zero, Kα2 ratio + axial last)
- [x] Bugfix found by the new tests: `set_vary` glob could re-free *structurally fixed* entries (symmetry-fixed cell angles matched by `phases.*.cell.*`, line-0 weight) — entries now carry a `locked` flag that globs can never free
- [ ] Instrument ⊕ sample profile split (Gaussian variances add, Lorentzian FWHMs add) → calibrate-on-LaB6 → freeze → refine-sample workflow; instrument-profile file export/import
- [ ] Analytic Jacobian columns for cell→2θ and profile widths (removes the dominant FD cost)
- [ ] Bérar-Lelann esd inflation; full statistics complete
- [ ] GSAS-II tutorial lab pattern as a second acceptance dataset

Background subsystem (automation-first):
- [ ] Pattern diagnostics object (peak density, S/B, amorphous-hump score, air-scatter slope, Kβ/W flags) — structured, agent-readable
- [ ] Auto-selection: BIC on peak-masked channels + Durbin-Watson whiteness stopping rule for Chebyshev order / λ
- [ ] Penalized P-spline co-refined background: smoothness penalty √λ·D as extra residual rows (linear, differentiable, cannot absorb broad Bragg intensity); `1/x` air-scatter term on diagnostic trigger
- [ ] Background↔ADP and background↔scale correlation guardrails

FitReport Layers 1-2 (see design record below for the full spec):
- [ ] Layer 1: gated derivative-basis misfit attribution (joint weighted solve, Gram covariance, R²/validity-radius/resolvability/maturity gates); hkl-grouped intensity & width analyses (ADP/occupancy/PO/anisotropic signatures); Le Bail-vs-Rietveld Rwp gap
- [ ] Layer 2: typed closed-enum `suggested_actions` with confidence/alternatives/expected-Δχ²; **strategy-engine veto**; predict-then-verify with rollback; Hamilton/ΔBIC justification for new parameters
- [ ] Synthetic misfit-injection test suite + confidence calibration (confidence>0.8 ⇒ true cause ranked first ≥80%)
- [ ] `plot_for_vlm()`: annotated multi-panel PNG montage (full + worst-N regions, Δ/σ panel, never JPEG)

Viz / events:
- [ ] plotly Scattergl HTML viewer (typed-array encoding, decimated overview + full-res zoom, size budget)
- [ ] `events.py` structured event stream (JSONL): stage transitions, freed/frozen params, per-iteration stats, guard/veto records — each with its equivalent API call string
- [ ] `pxrdref watch`: rewrite-HTML-per-stage + auto-refresh poll page over stdlib http.server, with a **console pane** tailing the event stream (no FastAPI/websockets)

## v0.3 — multi-phase workflows

- [ ] QPA: Hill-Howard ZMV mass fractions + Brindley microabsorption
- [ ] Pawley mode (per-hkl intensities in the parameter vector, near-singular normal-equation handling)
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
