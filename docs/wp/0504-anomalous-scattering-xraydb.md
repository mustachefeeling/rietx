# WP-0504 — Anomalous f′, f″ via xraydb

Milestone: v0.5 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Scope (carried verbatim from the pre-split roadmap)

- Anomalous f′,f″ at arbitrary λ via **xraydb** (Cromer-Liberman + Chantler;
  periodictable's Henke tables cap at 30 keV — wrong tool)

## Context pointers

- Extends the Waasmaier-Kirfel f₀ machinery in
  `crystallography/scattering.py`; f = f₀ + f′ + i·f″ changes the structure
  factor to complex arithmetic on a path that currently may assume real f —
  audit before estimating.
- WP-0305 computes µ per phase; if xraydb serves both, share the dependency.

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
