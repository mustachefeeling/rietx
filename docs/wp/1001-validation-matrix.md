# WP-1001 — Validation matrix + tolerance policy

Milestone: v1.0 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Validation matrix green: NIST certificates as **absolute anchors** (with
  stated uncertainties); GSAS-II as a *consistency* check with tolerances
  that respect legitimate inter-code convention differences (not 1e-4 Å
  ground truth)
- Three-tier tolerance policy documented per test (exact / tight-scientific /
  statistical)

## Context pointers

- [../DESIGN.md](../DESIGN.md#testing--validation-policy) — the policy this
  formalises, including both v0.2 lessons (protocol adoption; disagreement
  shape as evidence).
- Existing anchors: SRM 660c (absolute), FAP (cross-code), NAC (synchrotron)
  — see `tests/data/README.md` and `docs/milestones/`.

## Inherited

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — two measured ceilings
that a tolerance policy written from certificates alone would violate.

- **SRM 676a is a `c/a` anchor, not an absolute-axis anchor.** Measured c/a is
  +30 ppm vs certificate, but the absolute axes are −313/−283 ppm — a uniform
  lab d-scale systematic, asserted as such rather than absorbed into a widened
  band. A tolerance written against the certificate's own ±8e-6 would be
  unmeetable by construction on lab data. The tier this belongs in is
  "certificate-grade on the *ratio*, systematics-limited on the scale".
- **The achievable GoF for analytical-PSF lab fits is floor-limited at
  1.5–1.9** (Cline et al. 2015, J. Res. NIST 120, 173, for this instrument
  class; FPA reaches 1.08 and is fenced to v2). Measured 1.61 on corundum with
  Rexp ≈ 8.9 %, so Rwp = 14.4 % is mostly counting statistics, not misfit. A
  policy demanding GoF → 1 would be demanding FPA.

From **WP-0401** (op shim, landed 2026-07-24): current baselines to write the
matrix against are SRM 660c Rwp 8.66 % and NAC Rwp 9.31 % (unchanged across the
shim refactor, verified bit-identical). SRM 660c's cell sits +28 ppm from the
CIF block value under an explicitly *interim* ±2e-4 Å band — the residual bias
there is unmodelled equatorial divergence, tube tails and monochromator
passband, i.e. the same FPA territory.

## Tasks

- [ ] Expand this stub into a full WP before starting

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
