# WP-0406 — Restraint penalty rows

Milestone: v0.4 · Status: ⬜ not started (stub — expand before starting)
Depends on: —

## Goal

Soft restraints (bond lengths/angles, value targets) as extra rows in the
residual vector, following the pattern the P-spline background penalty
established.

## Scope (carried verbatim from the pre-split roadmap)

- Restraint penalty rows in the residual

## Context pointers

- `BackgroundPSpline` already answered the load-bearing questions: penalty
  rows ride in the residual and covariance but are **excluded from
  Rwp/Durbin-Watson/Bérar-Lelann statistics** (data rows only) — reuse that
  split, see `optimize/statistics.py` and `background/models.py`.
- Natural consumer: WP-0302 coordinates (bond-length restraints once
  coordinates refine).

## Tasks

- [ ] Expand this stub into a full WP before writing code

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
