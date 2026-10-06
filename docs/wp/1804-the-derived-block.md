# WP-1804 — the derived block: a nonlinear map applied after the affine one

Milestone: rigid-bodies · Status: ⬜
Depends on: 1801, 1803 (the record)
Priority: P2 2026-10-06 — every later body WP reads it; built in PR #773, under review

## Goal

`ParameterTable` gains `derived: list[DerivedBlock]`. A block maps declared input
entries, and the cell, to declared output entries through a closed-form map in `xp`
ops. It has a `local_jacobian(θ)` and a declared `reach_pattern()`. This is chunk
R2b of issue #561.

## Context

The seam was decided by WP-1803 and is recorded in
[`docs/DESIGN.md` § Parameter system](../DESIGN.md#parameter-system), clause
"Rigid bodies: a typed `derived` block". Read that clause first. The load-bearing
parts are restated here.

- `decode` applies the blocks after the affine matmul, in declaration order. With no
  block declared it is bit-identical to today.
- `stderr_physical`, `physical_covariance` and the restraint block `(R_phys @ C)` take
  the block's **local Jacobian at θ** for derived rows. The anchor rows in C are
  2.3–2.9 % off after a 3° solve and 8–24 % after 10°, so a reader left on C is wrong.
- The five pattern readers (`moving_paths`, `column_reach`, `entry_reach`,
  `unmeasured_rows`, `_column_extras`) read the **declared** `reach_pattern()`, never
  the Jacobian's numbers. On the planar test body a rotation column's numeric reach was
  28 rows where its declared reach is 42.
- `make_traced_decode` applies the same map after its dense matmul.
- `commit` and `apply_to_models` write derived rows from the map in the slot
  `_refresh_moment_components` holds. The moment keeps its own rule; it is not migrated.
- The closed-form Cartesian frame
  M = [[a, b cos γ, c cos β], [0, b sin γ, c (cos α − cos β cos γ)/sin γ], [0, 0, V/(a b sin γ)]]
  lands here in `xp` ops. A test pins it against `crystallography.adp.cartesian_basis`,
  which keeps its Cholesky. That docstring's "no convention" disclaimer is retired.
- No new Jacobian branch. A body column takes `_peak_chain_column`, which differences
  θ through `decode`, so the data-row column is exact (8e-11 relative against the
  whole-model FD in the spike).
- `ParameterTable.set_tie` flattens a derived source into `d` today with no error. The
  table-level refusal is added here, mirroring `apply_value_scale`.

**Both body rows stay in this WP** (decided 2026-10-06, on the question in the re-cut
comment on issue #561). The change to `backend/traced.py` is a new path through jax
and torch, and root CLAUDE.md requires `tests/test_cross_backend.py`'s configs to grow
with every new derivative path. The toy C₆Br block in the PR's own tests feeds both
the cross-backend row and the stage-boundary row, so neither waits for WP-1805.

v1.6 has shipped (2026-10), so WP-1514's "waits for v1.6" no longer holds.

## Non-goals

- The `RigidBody` schema (WP-1805).
- Migrating the moment onto the block.
- Any body column in `_structural_column`.

## Tasks

- [ ] `params/derived.py`: the block type, the closed-form frame and its cell derivative
- [ ] `ParameterTable`: `derived`, `add_derived`, `local_jacobian`, the declared reach, the five readers switched; `add_derived` onto an unlocked row raises
- [ ] `set_tie` refuses a locked or derived source, naming both paths
- [ ] `optimize/least_squares.py`: `_column_extras` and the restraint block on the declared reach and the local Jacobian
- [ ] `backend/traced.py`: the map after the matmul
- [ ] Tests: the acceptance below, including a toy-block row in `tests/test_cross_backend.py` and a stage-boundary regeneration with a block
- [ ] Skill: none. No public verb and no diagnostic code; the block is internal until WP-1805.

## Acceptance

Each is a check that can fail.

- Every `tests/data/backend_goldens/` case is bit-identical with no block declared.
- The toy C₆Br block reports coordinate esds equal to J·Cov·Jᵀ by central FD of `decode`
  to 1e-9 relative after a 3° solve. The anchor-row reader is 2.3–2.9 % off there, so a
  wrong reader fails.
- With the local Jacobian's cross-product sign flipped, the same test fails (the spike's
  planted sign gave ratios 0.17–2.5).
- The declared reach lists a row whose numeric column is zero at θ: a pivot atom of the
  toy block, under a rotation column. On the spike's planar body the same gap was 42
  declared rows against 28 numeric.
- The closed-form frame equals `cartesian_basis` to 1e-14 on 2000 random cells, and its
  `jax.jacfwd` is finite.
- `set_tie` with a locked or derived source raises, naming both paths.
- A toy-block cross-backend row agrees within the matrix's tolerance (< 5e-3).
- `tests/test_cross_backend.py`'s stage-boundary regeneration passes with a block.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_derived_block.py tests/test_cross_backend.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Coelho (2018), *J. Appl. Cryst.* 51, §3.2: TOPAS takes body-atom slopes by
  the chain rule through each atom's expression.
- Issue #561; PR #596 (the record and the proposal this WP was cut from); WP-1803.

## Handover log

- **2026-10-06** — created by WP-1803's re-cut, from #596's proposal and the
  contributor's 2026-10-06 update on #561. PR #773 builds it. The maintainer kept the
  cross-backend and stage-boundary rows here rather than in WP-1805, so #773 adds both
  before merge. Next: review #773 against this file.
