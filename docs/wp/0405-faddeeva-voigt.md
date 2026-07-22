# WP-0405 — True Voigt via a shared Faddeeva w(z)

Milestone: v0.4 · Status: ⬜ not started (stub — expand before starting)
Depends on: WP-0401

## Goal

A true Voigt profile option built on one backend-agnostic Faddeeva
implementation, so every backend computes identical gradients.

## Scope (carried verbatim from the pre-split roadmap)

- True Voigt via one shared backend-agnostic Weideman/Humlíček Faddeeva w(z)
  (jax has `wofz`; torch does not — one implementation everywhere for
  gradient consistency)

## Context pointers

- The TCHZ pseudo-Voigt (`model/profiles/pseudovoigt.py`) stays the default;
  true Voigt is an option, and both must satisfy the profile-normalization
  property tests.

## Tasks

- [ ] Expand this stub into a full WP before writing code
- [ ] One w(z) implementation on the WP-0401 op set; do NOT use per-backend
      native wofz (gradient consistency is the point)

## Handover log

- **2026-07-22** — created as a stub from the ROADMAP split.
