# WP-0502 — Surface roughness

Milestone: v0.5 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Surface roughness (Pitschke 1993 / Suortti 1972)

## Context pointers

- Bragg-Brentano only; low-angle intensity depression that correlates with
  ADPs — the background-absorption guard story
  ([../DESIGN.md](../DESIGN.md#background-subsystem-automation-first)) repeats
  here as a roughness↔Biso correlation to surface, not hide.

## Inherited

From **WP-0303** (anisotropic ADPs, landed 2026-07-23): the correlation to
surface is no longer only roughness↔Biso. ADPs can now be a full six-component
U^ij tensor per atom (`Atom.aniso`, opt-in, freed by the
`phases.*.atoms.*.adp.*` glob), so a low-angle intensity depression has more
displacement freedom to hide in than the stub assumes. The right measurement is
the *block* projection R² already used for background absorption
(`optimize.statistics.background_absorption`), not pairwise ρ — pairwise misses
block absorption almost entirely.

From **WP-0401** (op shim, landed 2026-07-24): `model/corrections.py` is
xp-routed. New correction code calls `xp.*` with `xp = get_backend()` bound
once per compiled-model call, never bare `np.*`, or the jax/torch backends
break.

From **WP-0501** (capillary absorption, landed 2026-07-27) — this WP lands in
the same degenerate pocket, and 0501 built the tools to measure it:

- **Measure the degeneracy before designing the parameter.** Roughness is a
  low-angle intensity depression, and the {phase scale, Biso} pair spans
  {1, sin²θ} in log-intensity. 0501 found that cylindrical absorption is
  *exactly* in that span — its µR column is singular, not merely correlated —
  and consequently made µR a computed plain float rather than a refinable
  `Parameter`. Use `model.absorption.mu_r_identifiable_fraction` (it projects
  ∂lnA/∂p onto span{1, sin²θ} and returns the normalised residual) on the
  roughness model *before* deciding it is refinable. The Suortti and Pitschke
  forms are not obviously separable, and a roughness coefficient that turns out
  to be a reparameterised Biso would silently eat ADPs while improving nothing.
- **`CompiledModel._absorption` is the seam**, and its docstring states the
  hazard a new intensity multiplier inherits: it must be applied in
  `phase_peaks` *and* in both hand-written analytic-column builders
  (`_structural_intensity_grad`, `po_intensity_grad`), or those columns are
  silently wrong while the finite-difference columns stay right. The two guard
  tests in `tests/test_absorption.py`, each with a
  `(1 − A).max() > 0.5` pre-assert so they cannot pass vacuously, are the
  pattern to copy.
- **Judge it by the physical quantity it unbiases, not by Rwp.** 0501's
  correction provably cannot change Rwp (it is an exact reparameterisation), so
  its acceptance test asserts the *Biso bias removed* — 0.489 Å² at µR = 1,
  recovered to four decimals at 18.8σ — and explicitly asserts Rwp is
  *unchanged*. If roughness turns out to be similar, the obvious "the fit should
  improve" test would assert something the physics cannot deliver.
- `RefinementResult.absorption` (`schemas/results.AbsorptionCorrection`) is the
  precedent for reporting a correction whose effect no fit statistic shows.
- **A parameter's *name* silently selects its derivative path.**
  `params/vector.py` decides whether a geometry parameter is force-fixed by
  testing whether the name starts with `sample_`, and
  `CompiledModel.scalar_chain_supported` uses the same prefix to decide between
  an analytic peak-chain column and whole-model finite differences. 0501 left
  both alone (its µR is not refinable, so neither applied) — but roughness *is*
  a Bragg-Brentano geometry term, so it is the next WP likely to trip over
  them. Choose the name deliberately.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
