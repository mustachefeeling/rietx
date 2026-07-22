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

## Tasks

- [ ] Expand this stub into a full WP before starting

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
