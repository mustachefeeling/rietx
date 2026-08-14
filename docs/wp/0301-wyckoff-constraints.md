# WP-0301 — Wyckoff / site-symmetry constraint derivation (affine constraints)

Milestone: v0.3 · Status: ✅ 2026-07-22
Depends on: —

## Goal

Generalise the parameter-tie machinery from today's *identity* ties
(`Entry.tied_to`, one source path) to a general affine map
**p_phys = C·θ + d**, and derive the site-symmetry constraint rows for atomic
coordinates and anisotropic ADPs from the space group via **spglib**. This is
the enabling WP for WP-0302 (coordinates) and WP-0303 (aniso ADPs); it ships
no new physics of its own.

## Context

Current state in [`src/rietx/params/vector.py`](../../src/rietx/params/vector.py):

- `Entry` (line ~41) carries `tied_to: str | None` — an **identity** tie only
  (dependent path copies a source path's value) plus a `locked: bool` that
  `set_vary` globs may never free.
- `_CELL_TIES` / `_FIXED_ANGLES` (line ~54) hold the crystal-system cell ties;
  these are exactly the identity subset the design record promised to
  generalise here.
- Ties are applied in three places that must all move to the affine form:
  `decode` (line ~176, `values[e.path] = values[e.tied_to]`),
  `stderr_physical` (line ~193, tied params inherit the source esd) and
  `apply_to_models` (line ~205).
- With a general `C`, esd propagation stops being "inherit" and becomes
  σ_phys = sqrt(diag(C · Cov_θ · Cᵀ)) — do this properly; it is the whole
  reason the affine form is exact.

Design constraint (see [../DESIGN.md](../DESIGN.md#parameter-system)): the
constraint map must be a **constant matmul** so it stays exact under autodiff
(v0.4 JAX). No data-dependent branching inside the map.

Nonlinear ties (`expr`) are **out of scope** — asteval and sympy were both
evaluated and rejected (asteval cannot run on autodiff tracers; sympy's torch
lambdify printer is immature). The affine map is what v0.3 ships.

spglib is a **new dependency** (BSD-3, permissive — fine per the licensing
fence). Add it to `[project.dependencies]`, not an extra: WP-0302/0303 are
core v0.3 features. gemmi already provides the space-group ops; spglib is
used for the Wyckoff *identification* and site-symmetry group of a given
position, which gemmi does not expose directly.

## Non-goals

- Refining coordinates (WP-0302) or aniso ADPs (WP-0303) — this WP only
  derives and applies the constraints, verified by unit tests against
  published tables.
- Rigid bodies (v2 fence). Restraints (WP-0406, penalty rows).

## Tasks

- [x] Add spglib dependency; thin wrapper `crystallography/wyckoff.py` that
      takes (space group, site fractional coords) → Wyckoff letter,
      site-symmetry group, and the allowed free-parameter basis for that site
- [x] Coordinate constraint rows: for each site, the projector onto
      site-symmetry-invariant displacements (e.g. `x,x,0` sites give one free
      parameter with C rows [1,1,0]); free parameters get synthetic dot-paths
      that do not collide with `phases.i.atoms.j.{x,y,z}`
- [x] ADP constraint rows: the Laue-class-allowed U_ij pattern per site
      (needed by WP-0303; derive here so both consumers share one code path)
- [x] Replace `Entry.tied_to` with a general constraint block on
      `ParameterTable`: sparse `C` (n_phys × n_free) + `d`, built at compile;
      identity ties become the special case (keep the `_CELL_TIES` behaviour
      bit-identical — the acceptance suites depend on it)
- [x] Rework `decode` / `commit` / `apply_to_models` onto `C·θ + d`
- [x] Correct esd propagation: σ_phys from diag(C · Cov · Cᵀ) in
      `stderr_physical`; tied cell edges must still report the source esd
      (that is what the affine form gives for identity rows — assert it)
- [x] Unit tests: constraint bases cross-checked against **cctbx** published
      site-symmetry tables for a spread of Wyckoff sites (special positions in
      cubic/tetragonal/trigonal/monoclinic groups); regression test that
      cubic/tetragonal/hexagonal cell ties and the `locked` protections are
      unchanged

## Acceptance

Constraint bases match cctbx tables for every tested Wyckoff site; the
existing suite is unchanged (this WP is a refactor with new capability
behind it — the acceptance numbers must not move).

```sh
.venv/bin/python -m pytest tests/test_wyckoff.py tests/test_params.py -q
.venv/bin/python -m pytest            # full suite incl. slow acceptance: no number moves
.venv/bin/python -m ruff check src tests examples
```

## References

- spglib (Togo & Tanaka) — Wyckoff/site symmetry, BSD-3.
- cctbx site-symmetry tables — cross-check reference (BSD-style).
- International Tables A — Wyckoff position definitions.

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
- **2026-07-22** — **done**; all checklist items landed as three `WP-0301:`
  commits, full suite (205, incl. slow acceptance) + ruff green, no
  acceptance number moved (SRM 660c plot re-inspected: Rwp 8.66 %, GoF 1.87).
  - `crystallography/wyckoff.py`: `site_constraints(sg, xyz)` → Wyckoff
    letter + oriented site-symmetry symbol (spglib on a probe cell whose
    lattice is a group-averaged generic metric — no per-setting case table —
    pinned by a dummy general-position orbit) + coordinate/ADP bases derived
    from gemmi stabilizer rotations by exact `Fraction` RREF. ADP order is
    **(U11, U22, U33, U12, U13, U23)**; bases are smallest-integer,
    deterministic (tests compare exact arrays).
  - `ParameterTable` now compiles sparse `C`/`d` in `_rebuild()` at every
    stage boundary; `AffineTie(terms, const)` declares dependence, chains
    flatten, cycles raise. New hooks for WP-0302/0303: `add_parameter`
    (synthetic DOF paths, e.g. `phases.0.atoms.2.dof.0`) and `set_tie`.
    `stderr_physical` takes the free-param correlation matrix (threaded from
    `LSQOutcome.correlation` in `refine.py`) → σ² = diag(C·Cov·Cᵀ).
  - Gotchas for 0302/0303: coordinate anchoring goes through `AffineTie.const`
    (x = x₀ + B·θ, DOFs start at 0); the probe cell falls back to a second
    generic point if the user's site coincides with the first; the
    atomic-coordinate `NotImplementedError` in `_collect` is still in place —
    WP-0302 removes it and wires `site_constraints` into table construction.
  - spglib emits an internal `DeprecationWarning` (its own OLD_ERROR_HANDLING
    migration) — harmless, not our API usage.
