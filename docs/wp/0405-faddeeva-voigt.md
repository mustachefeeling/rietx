# WP-0405 — True Voigt via a shared Faddeeva w(z)

Milestone: v0.4 · Status: ⬜ not started
Depends on: WP-0401

## Goal

A true-Voigt profile option built on one backend-agnostic Faddeeva `w(z)`
implemented on the WP-0401 op set — never per-backend native `wofz` — so
every backend computes identical values *and gradients*; it slots beside the
default TCHZ pseudo-Voigt and satisfies the profile-normalization property
tests.

## Context

- The TCHZ pseudo-Voigt (`model/profiles/pseudovoigt.py`) **stays the
  default**; true Voigt is an opt-in shape. jax ships `wofz`, torch does not
  — and even where natives exist, their gradients differ per backend, which
  is exactly the drift WP-0404 exists to catch. One implementation
  everywhere.

### Inherited

From **WP-0401** (op shim, landed 2026-07-24):

- **No `scipy.special`, by decision.** The hot path has none, and the shim
  deliberately ships no special-function layer: "the WP-0405 Faddeeva is built
  *on* this op set, so leave room but implement nothing for it here." So `w(z)`
  is a composition of existing ops, or an explicitly justified new op — and
  every op added is a per-backend maintenance liability (numpy, jax, torch).
- **The op inventory, verified 2026-07-24 rather than quoted.** 0401's own
  handover says "37 named ops"; the shipped vocabulary is **32** entries in
  `_OP_NAMES` plus `window_add` / `segment_sum` (34 total), plus `pi` and
  `linalg` (`.inv`/`.det`). Read `src/pxrdref/backend/api.py::_OP_NAMES` for
  the live list — do not trust either number in prose.
- **Complex is first-class but minimal:** `exp` (complex-capable), `conj`,
  `real`, `imag`. There is no complex `erfc` and no complex division op, which
  constrains which `w(z)` algorithm is expressible. complex128 on host/CPU;
  complex64 only under WP-0403's fp32 policy.
- **No general index-array scatter, ever** — `window_add(y, i0, i1, vals)` on
  frozen contiguous windows is the only scatter, because data-dependent
  indices are what frozen-per-stage discreteness exists to forbid. A
  region-split `w(z)` (the usual Humlíček/Weideman approach picks an algorithm
  per |z| region) must therefore be expressed as `where`-masks over the full
  array, not as gathers into per-region index sets.

From **WP-0403** (mixed-precision policy, landed 2026-07-24): if `w(z)` is
ever evaluated below fp64, that is a *Jacobian-column* concern only — the
policy lives in `backend/linalg64.py` and the residual stays fp64 regardless.

### Design (decided)

- **Algorithm: Weideman (1994) rational approximation, N = 32 terms**
  (~fp64 accuracy over the relevant z range; N is a documented module
  constant). Chosen over Humlíček w4 (partitions the complex plane into 4
  regions → branches, hostile to autodiff and to the 0401 branchless goal)
  and Zaghloul & Ali 2011 (higher accuracy but continued-fraction/series
  branches, heavier). Weideman is a single rational form — a polynomial in
  one auxiliary variable plus a complex division — a handful of 0401 ops,
  trivially differentiable, branchless by construction.
- **Licensing:** implemented from the paper (algorithm, not code);
  ATTRIBUTION.md gets a Weideman entry.
- **Placement:** `Instrument.profile.shape: Literal["tchz_pv", "voigt"]`,
  default `"tchz_pv"` — a per-instrument choice, not per-reflection. The
  Voigt consumes the *same* Gaussian/Lorentzian FWHMs the TCHZ machinery
  already computes (`profiles/caglioti.py`; the instrument ⊕ sample width
  split is untouched): z = (x + iγ_L)/(σ√2), V = Re[w(z)]/(σ√2π). FCJ
  composes unchanged — it convolves whatever unit-area profile it is handed.
- **Files:** `model/profiles/faddeeva.py` (w(z) on the op set) +
  `model/profiles/voigt.py` (unit-area profile + analytic ∂V/∂(σ,γ) from
  w(z)); thread the shape enum through
  `phase_peaks`/`_reflection_profile`/`derivative_bases`.

## Non-goals

Replacing the TCHZ default; per-backend native `wofz` (gradient consistency
is the point); FPA-style physical profiles (v2 fence).

## Tasks

- [ ] `model/profiles/faddeeva.py`: Weideman N=32 `w(z)` on the 0401 op set;
      paper citation in the docstring; ATTRIBUTION.md entry
- [ ] `model/profiles/voigt.py`: unit-area true Voigt + analytic derivs;
      reuse Caglioti/sample FWHM inputs
- [ ] `Instrument.profile.shape` enum (default `tchz_pv`), threaded through
      `phase_peaks`/`_reflection_profile`/`derivative_bases`
- [ ] Tests: `tests/test_voigt.py` — unit area <1e-6 on the frozen window;
      γ_L→0 Gaussian and σ→0 Lorentzian limits <1e-8; cross-backend w(z)
      agreement <1e-12 (fp64); analytic ∂V/∂(σ,γ) vs FD <5e-3; the FCJ
      smoothness test holds under the Voigt shape + obs/calc/diff PNGs to
      `tests/output/`

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_voigt.py tests/test_profiles_background.py -q
```

Measured: Voigt unit-area within 1e-6; Gaussian/Lorentzian limits within
1e-8; w(z) cross-backend within 1e-12; analytic derivs vs FD <5e-3.

## References

- Weideman (1994) SIAM J. Numer. Anal. 31, 1497 — "Computation of the
  complex error function" (**the implemented algorithm**).
- Humlíček (1982) J. Quant. Spectrosc. Radiat. Transfer 27, 437 — w4
  (rejected: region branching).
- Zaghloul & Ali (2011) ACM Trans. Math. Softw. 38, Algorithm 916
  (rejected: heavier, branched).

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
- **2026-07-24** — expanded from stub (v0.4 planning session): Weideman N=32
  chosen for branchlessness; per-instrument `profile.shape` enum; files,
  property tests and tolerances decided.
