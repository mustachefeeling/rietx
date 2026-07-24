# WP-0501 — Capillary and flat-plate absorption

Milestone: v0.5 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Capillary (Debye-Scherrer) and flat-plate absorption (Sabine 1998 /
  Lobanov-Alte da Veiga)

## Context pointers

- Lands beside displacement/transparency in `model/corrections.py`, gated on
  `Geometry.kind` the same way.
- v0.5 milestone acceptance: capillary/absorption vs GSAS-II consistency —
  which means **adopting GSAS-II's protocol**, per
  [../DESIGN.md](../DESIGN.md#testing--validation-policy).
- Distinct from WP-0305 (Brindley acts on QPA fractions; this acts on the
  profile/intensity vs θ).

## Inherited

From **WP-0305** (Brindley, landed 2026-07-23): the per-phase µ machinery
already exists — `crystallography/attenuation.py` interpolating bundled
`data/mu_McMaster.dat` (McMaster 1969, energy-trimmed 2–120 keV, ATTRIBUTION.md
updated). Reuse it rather than rebuilding. It interpolates log-log and
**refuses** a wavelength whose grid interval contains an absorption edge rather
than smearing across it. Measured vs NIST Hubbell-Seltzer at 8 keV: ≤2.5 % for
Z ≥ 9, but B −7 % and O −3.6 % (McMaster's known low-Z weakness) — relevant if
an absorption correction is asserted against a light-element standard.

From **WP-0310** (v0.3 acceptance, landed 2026-07-24): specimen transparency
was measured on SRM 676a corundum and deliberately **kept at 0**. Freeing it is
a wash (Rwp 14.37 → 14.33 %, GoF 1.606 → 1.601, every band Rwp moves < 0.07
points) and merely re-apportions the uniform d-scale across the correlated
{zero, displacement, t} triple — zero −0.075° → −0.012°, displacement +0.008 →
+0.088 mm, µ_eff ≈ 120 cm⁻¹ (solid-alumina-like, not compact-like) — pulling
absolute axes to −202/−171 ppm with no new physics. New absorption terms enter
that same correlated triple and should expect the same trap: judge them by
whether they buy *band-resolved* residual structure, not by Rwp. Do not
silently change the acceptance protocol that holds transparency at 0.

From **WP-0401** (op shim, landed 2026-07-24): `model/corrections.py` is
xp-routed. New correction code calls `xp.*` with `xp = get_backend()` bound
once per compiled-model call, never bare `np.*` and never per-op — otherwise it
breaks the jax and torch backends silently.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
