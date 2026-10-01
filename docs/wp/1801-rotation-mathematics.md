# WP-1801 — rotation mathematics: the exponential map, its derivative, the canonical quaternion

Milestone: v1.8 · Status: 🔄 2026-10-01 — the module and its tests landed (PR #578); two review follow-ups (the unit tolerance, an ω → q → ω test) remain before it closes
Depends on: —
Priority: P2 2026-09-30 — the first rung of the rigid-body milestone, touches no v1.6 file, nothing blocks it

## Goal

`crystallography/rotation.py` turns a rotation vector into a matrix and a unit
quaternion, gives the matrix's derivative with respect to the vector, and stays
finite and smooth at a zero rotation. Every later rigid-body WP reads it.

## Context

Scoped in issue #561 and WP-1514, reviewed adversarially on 2026-09-30.
A rigid body is refined as an origin plus an **anchored rotation vector** δω
that is zero at every stage start, reported as a unit quaternion with w ≥ 0.
No gimbal lock, no unit-norm constraint, no radial null direction.

**The trap this WP exists to avoid (from the review):** Rodrigues' formula
written with |δω| has an undefined derivative at δω = 0, which is *every stage
start*. `backend/traced.py` needs both branches of every `where` to be smooth,
so the function is written in `xp` ops with a series branch below a small
angle, and is tested at zero. The 100 random vectors the scoping proposed
never reach it.

Conventions to restate: angles in radians inside the function and degrees at
the schema edge (root CLAUDE.md § Conventions); rotations act on Cartesian
column vectors; a new `xp` op goes into `_OP_NAMES` and every backend
(`tests/test_backend_conformance.py`).

## Non-goals

- Any contact with `params/vector.py` or the parameter table (1803 decides the seam).
- A public export. The module stays unexported until a consumer exists, which
  keeps `tests/api_surface.py`'s partition and the skill's `api.md` headroom
  (402 B on 2026-09-30) untouched.

## Tasks

- [ ] `rotation.py`: vector → matrix, matrix → vector, vector ↔ quaternion, `dR/dδω`, in `xp` ops; the canonical form w ≥ 0 with the w = 0 tie-break
- [ ] Tests: derivative against central finite differences to 1e-9 on 100 random vectors **and** at δω = 0, at |δω| = 1e-8 and near π; all round trips; the canonical form idempotent; a `jax.jacfwd` at zero finite (self-skips without jax)
- [ ] Skill: none, no public surface

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_rotation.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #561; WP-1514. Rodrigues' formula and the quaternion conventions are
  textbook; cite the source used in the docstring (author, year).

## Handover log

- **2026-10-01** — The rotation maths is on `main`. `crystallography/rotation.py`
  gives the exponential map, its left Jacobian, the derivative of a rotated
  frame, quaternions, Log and composition, all in backend `xp` ops, so a rigid
  body can be rotated and differentiated on any backend. Nothing consumes it
  yet. *Done:* PR #578 (`872d34fe`), merged as `824d0c8b` by `/pr-review`.
  *Measured* by the review on numpy and jax (torch was not installed, so it had
  a static read only): ∂(Exp(ω)·R₀)/∂ω against Richardson-extrapolated central
  differences at 300 points from 1e-10 to 12 rad, worst error 4e-12. A, B and
  C jump by about 1 ulp at the 0.25 rad series switch, and their first
  derivatives by at most 2e-12 relative. The jax Jacobians are finite at
  ω = 0, 1e-300, π ± 1e-9 and 2π. *Gotchas:* `UNIT_TOLERANCE` bounds both
  ‖q‖ − 1 and max|RᵀR − I|, but RᵀR scales as ‖q‖⁴, so
  q = (1 + 9e-10)·(1, 0, 0, 0) passes `matrix_from_quaternion` while its
  matrix fails `quaternion_from_matrix`. ω → q → ω has no test of its own; it
  holds to 4ε on 2000 random vectors. Both were posted as follow-ups.
  *Next:* the two follow-ups, then WP-1803, which this unblocks.

- **2026-09-30** — created, from the 2026-09-30 issue triage (issue #561) after
  an adversarial review of the proposal against `e3e6486a`. No open WP owns it.
  The review's finding that the zero-rotation derivative is the failure a
  random-vector test misses is this WP's first acceptance row.
