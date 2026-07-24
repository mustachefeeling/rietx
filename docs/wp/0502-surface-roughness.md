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

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
