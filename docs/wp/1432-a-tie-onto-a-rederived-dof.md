# WP-1432 — a tie onto a coordinate DOF, re-applied once per write

Milestone: unscheduled · Status: 🔄 2026-09-19 — claimed by @yue-here
Depends on: — (1119 soft — it is that WP's surface this breaks)

## Goal

A user tie whose target is a coordinate degree of freedom means the same thing
after the tenth write-through verb as after the first. Today it means ten times
as much, silently, and the parameter it follows still reads its original value.

## Context

Found 2026-09-16 by the `/pr-review` round on issues #286 and #293, measured on
`main` at `f1d89cb0` (bench venv `[dev,jax]`, macOS arm64, Python 3.12). The
scripts are one file each and are quoted below rather than kept.

**The asymmetry.** A coordinate DOF is a displacement *from the stored
coordinate*: `ParameterTable` builds `phases.i.atoms.j.z` as
`AffineTie(terms=((…dof.2, 1.0),), const=z_stored)`, so the DOF is rederived to
zero on every table build while the coordinate keeps the displacement
(`docs/manual/using/model.md` says so, and calls ADP and Stephens DOFs absolute
by contrast). A named variable is the opposite: `_declare_variables` re-declares
it from `Refinement._variables` at the value the register holds, because nothing
in the structure knows about it. Tie the one to the other and every rebuild adds
the variable's whole value to a coordinate that has already absorbed it.

**Measured.** One variable at 0.01, one tie onto `phases.0.atoms.0.dof.2`, then
four unrelated `set_values({"phases.0.scale": 0.02})` calls:

| after | z |
|---|---|
| tie declared | 0.26 |
| the four writes | 0.27, 0.28, 0.29, 0.30 |

`vars.A` reads 0.01 throughout. `parameters()` and `set_vary` do not move it, so
the trigger is a verb that writes through.

**Two controls pin the mechanism, and they bound the class.** The same tie onto
an ADP DOF (`phases.0.atoms.0.adp.0`) holds 0.02 through all four writes,
because ADP DOFs are absolute. The same tie onto the same coordinate DOF with
*another coordinate DOF* as its source holds steady, because both ends reset
together. So the class is a tie whose target is rederived-and-relative and whose
source is not, and on `main` the only rederived-and-relative entries are
coordinate DOFs. Stephens coefficients are absolute too (`vector.py` builds them
with no `const`).

**What it costs a caller.** Two shapes, and the second is the quiet one.

- A nonzero variable at declaration time skews what it drives. Two ties
  declared in order onto an antiphase pair, variable seeded 0.005, left the pair
  at +0.02251 and −0.01751 after a fit, because the first-declared target
  collected one more application than the second. A constraint that was supposed
  to make two atoms move together made them move differently.
- A second `fit()` on the same `Refinement` reports the variable at **0.0**
  while the structure still carries the full displacement, at identical Rwp. The
  refined quantity has migrated into the base coordinate, so the number a caller
  reads is no longer the thing it named.

**What is not affected.** A fit is clean within itself: one, two and three stage
plans all freeing the same variable from zero returned bit-identical values
(0.02000744, Rwp 0.03928 to every digit). The damage needs a write-through verb
while the variable is nonzero, which is where `Refinement.fit` called twice
lands, and where WP-1419's workflow lives.

**Why nothing caught it.** `tests/test_named_variables.py` has no DOF case at
all, though `optimize/least_squares.py`'s `_column_identities` docstring is
written around exactly this path ("a variable driving a Wyckoff DOF reaches
`[…atoms.1.x, …atoms.1.dof.0]`"). The Jacobian dispatch that docstring governs
is correct. What is wrong is upstream of it, in what the table holds by the time
the column is built.

**Seams.** `refine.Refinement._apply_ties` and `_write_back`,
`params.vector.ParameterTable.__init__` (the coordinate tie's `const`) and
`apply_to_models`. `_ties` is already the one authority for which ties are the
user's, and it is consulted on every build, so the repair has somewhere to live
that is not a new mechanism.

**Two candidate fixes**, and the first keeps the documented surface:

1. Do not absorb a user-tied DOF's value into the coordinate's `const` on
   rebuild. The DOF stays the displacement its tie says it is, and the
   coordinate is derived rather than accumulated.
2. Refuse the tie, naming the spelling that works. Cheap and narrow, and it
   removes the only way to constrain coordinates across atoms, since a
   coordinate itself refuses a user tie (symmetry outranks it).

A third option, making coordinate DOFs absolute like ADP and Stephens ones, is
out of scope here: it changes what `set_values` on a DOF means for every caller
and what the manual documents, for a defect that lives in the tie path.

### Inherited

**From WP-1441 (2026-09-18), issue #376.** A series can now declare ties, and
that adds a caller to both seams this WP names.

`SequentialRefinement.fit` takes a `constrain=(index, ref)` hook, called on each
pattern's fresh `Refinement` before its fit, and it is now the documented place
to declare a tie across a chain. Two consequences here. The chain itself is
*clear* of this defect by construction — one declaration per pattern against a
table built moments earlier, with no write-through verb between the tie and the
solve — so a fix here must not assume a tie has been re-applied at least once.
And a caller's hook may legitimately `set_values` after tying, which is 1432's
trigger with the series' own multiplier on it: a 68-pattern ramp applies it 68
times rather than once.

`sequential._carry_variables` is a **new `set_values` caller**, on a
`Refinement` whose history tree does not exist yet. It writes a carried
variable's value after the hook has declared the variable and its ties, so it
runs the `refresh_ties` / `_write_back` path this WP is repairing, on exactly
the variable-drives-a-tie shape 1432 measured. Whatever the fix does to that
path, `tests/test_sequential.py::test_a_named_variable_warm_starts_under_the_carry_globs`
is a second fixture over it, and it asserts on the value a fit *starts* from
rather than the one it ends at.

## Non-goals

- Distortion-mode amplitudes. WP-1419 consumes this fix and does not contain it;
  its § Inherited says so.
- The Jacobian dispatch for a variable-driven column, which is correct.
- ADP, Stephens and cell ties, measured unaffected.

## Tasks

- [ ] A failing test first: the four-write table above, plus the ADP control and
      the DOF-source control, so the class is pinned before the fix moves.
- [ ] The fix, in the `_apply_ties`/`__init__` seam; a tied coordinate DOF keeps
      its meaning across rebuilds.
- [ ] The second shape: `fit()` twice on one `Refinement` reports the same
      amplitude both times, and the structure does not move between them.
- [ ] `tests/test_named_variables.py` grows the DOF case it never had, with the
      declared-order asymmetry as a regression case.
- [ ] Manual: `using/model.md` says a coordinate DOF is a displacement from the
      stored coordinate. Say what that means for a tie onto one.
- [ ] Skill: none, unless the fix changes what an agent should write — a tie
      onto a DOF is the documented way to constrain coordinates, so if the
      spelling changes, `references/` gains the row (root CLAUDE.md § skill).

## Acceptance

A variable tied to a coordinate DOF survives ten write-through verbs unchanged,
an antiphase pair declared in either order ends symmetric, and a second `fit()`
reports what the first did.

```sh
.venv/bin/python -m pytest tests/test_named_variables.py tests/test_params.py tests/test_params_surface.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issues #286 and #293, and the 2026-09-16 review comments on both.
- WP-1119 (named variables), WP-1070 (user ties), WP-1342 (the sibling class: a
  freeze that reads names and misses what a tie moves).
- `docs/manual/using/model.md` § the two tie populations.

## Handover log

- **2026-09-16** — created from the `/pr-review` round on issues #286 and #293.
  The defect was found while checking whether WP-1419's distortion-mode
  amplitudes could be written with the machinery `main` already has. They can,
  and the answer they give drifts by one amplitude per write-through verb. Next:
  the failing test, since the class is bounded (coordinate DOFs only, both
  controls measured) and the seam is named.
