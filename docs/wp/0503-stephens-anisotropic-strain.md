# WP-0503 — Stephens anisotropic strain broadening

Milestone: v0.5 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Stephens 1999 anisotropic strain broadening (S_HKL invariants per Laue
  class)

## Context pointers

- hkl-dependent *width*, not ADPs (that contrast is stated in WP-0303's
  non-goals from the other side).
- The FitReport Layer 1 already has a width-direction→Stephens hkl-grouped
  analysis waiting for this to exist
  ([../DESIGN.md](../DESIGN.md#outputs--fit-assessment-the-agent-native-design)).
- Width conventions documented by physics (size↔1/cosθ, strain↔tanθ), per the
  CLAUDE.md invariant.

## Inherited

From **WP-0310** (v0.3 acceptance, landed 2026-07-24) — **the one that will
cost a debugging session.** Softplus-transformed sample-broadening terms
starting at exactly 0 have a dead gradient and *never move*: they refine
silently to their start value rather than erroring. The fix is
`Stage(..., seed=…)`, following the extinction-stage precedent
(`pr.Stage("extinction", ["phases.*.extinction"], seed=1e-3)`). Every S_HKL
naturally starts at 0, so this WP hits it on every parameter it introduces.

From **WP-0303** (anisotropic ADPs, landed 2026-07-23): the ADP tensor
machinery is *not* reusable here, and 0303 fenced this out from its side —
"anisotropic *strain broadening* (Stephens) — that is peak width, not ADPs".
The U^ij site-symmetry basis (`crystallography/wyckoff.adp_basis`) is built for
a rank-2 tensor on a Wyckoff site; Stephens S_HKL are rank-4 invariants per
*Laue class*. Same "symmetry-allowed subspace" idea, different group action —
expect to write it, not import it. Worth copying from 0303 instead: the
convention of making the parameters **absolute** (U = Σₖ θₖ·Bₖ) so site
symmetry is enforced exactly, and raising on an out-of-subspace tensor rather
than silently symmetrising it.

From **WP-0501** (capillary absorption, landed 2026-07-27): two naming traps
for any *new geometry-gated* parameter, which S_HKL is not but a future
sample-shape term would be. `params/vector.py:239` decides whether a geometry
parameter is force-fixed by testing whether its name starts with `sample_`, and
`CompiledModel.scalar_chain_supported` decides whether it gets an analytic
peak-chain column or falls back to whole-model finite differences by testing the
same prefix. Both were left alone by 0501 (its µR is not a refinable parameter,
so neither applied), but they mean **a parameter's name silently selects its
derivative path** — worth knowing before choosing one.

From **WP-0401** (op shim, landed 2026-07-24): `model/profiles/*.py`
(`pseudovoigt`, `fcj`, `caglioti`) are xp-routed — new width code calls `xp.*`,
bound once per compiled-model call. Also note the frozen-per-stage invariant
bites here: anything hkl-dependent that changes *shapes* (node counts, window
extents) must be computed at stage compile, never inside the solve.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## References

- Stephens (1999) J. Appl. Cryst. 32, 281.

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
