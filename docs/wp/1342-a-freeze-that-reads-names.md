# WP-1342 — A structural freeze that reads names, and the tie it cannot see

Milestone: unscheduled · Status: ⬜
Depends on: — (1119 found it; 1301 owns the freeze it disarms)

## Goal

Every structural freeze that today filters `ParameterTable.free_paths` by a
path prefix instead asks what each free column can *move*, so a phase driven
through a tie is held, force-fixed and reported exactly as one driven by its
own column.

## Context

CLAUDE.md states the rule this WP applies: **"can this parameter move?" is
`moving_paths`, never `free_paths`.** `ParameterTable.moving_paths` (free ∪
its ties, read off C's nonzero rows) exists for it, `compile_model` already
takes that set, and `_column_extras`/`_column_identities` in `optimize/`
compute the per-column reach the Jacobian needs. Two consumers in `refine.py`
never got the message, and both read names:

- **`_unsupported_phase_paths` (`src/rietx/refine.py:228`)** filters
  `table.free_paths` by `p.startswith(f"phases.{i}.")`. It is what
  [1301](1301-hold-unsupported-phase.md) uses to hold every free structural
  path of a phase the data cannot see.
- **`mode_fixed_path` (`src/rietx/refine.py:136`)** decides the Le Bail /
  Pawley force-fix of `.atoms.` paths, `phases.N.scale` and
  `.source.lines.`; `_run_stage`'s drop and `suggest`'s mirror both read it
  off the free list.

Tie a phase's cell or an atom's `biso` to something whose own path is not
under `phases.N.` — since [1119](1119-named-variables.md) that is any named
variable, `vars.X` — and the only free *name* is the source's. The prefix
test then matches nothing, 1301's hold never fires, and the flat direction
stays free for the whole stage while `StageResult.held` records nothing. The
Le Bail force-fix of atom coordinates has the same hole.

**Nothing raises and nothing goes red**, which is the class this section of the
ROADMAP is strictest about: the freeze reports that it did its job, on a set it
could not see into.

### What makes it more than a prefix fix

A column may reach several phases. `vars.X` driving `phases.0.cell.a` and
`phases.1.cell.a` is one column, and holding it because phase 1 is
unsupported also freezes phase 0's cell, which the data *can* see. So the
work is a decision as much as a lookup:

- hold the column only when every phase it reaches is unsupported, or
- hold it whenever any is, and say which in the finding, or
- refuse the configuration at declaration.

Whichever it is, `PHASE_UNCONSTRAINED` (which 1301 made say what was done)
has to be able to name a variable rather than a phase path, and
`StageResult.held` has to record a column that is not a phase's.

### The seam

`moving_paths` answers "does this entry move", not "which column moves it",
and the hold needs the second. The reach is one row-wise read of **C** — the
same object `_column_extras` reads — but it lives in `optimize/` and the
table has no method for it. Expect a small `ParameterTable` accessor
(free column index → the set of entry paths its non-zero rows name) plus the
two call sites, rather than a change in `optimize/`.

## Non-goals

- The Jacobian's own gate. `_make_jacobian` already dispatches on reach, not
  on name, and `_peak_chain_column` raises on a wrong claim
  ([1109](1109-refinement-speed.md)); this WP does not touch it.
- Nonlinear constraints. The tie is affine, so the reach is exactly C's
  sparsity pattern.
- `vars.*` in the `.rxt` document — the other finding 1119 recorded, a
  grammar change and a `FORMAT_VERSION` bump, and cosmetic where this is not.

## Tasks

- [ ] A `ParameterTable` accessor giving a free column's reach (the entry
      paths its non-zero C rows name), with the empty-C and no-tie cases
      pinned bit-identical to today's `free_paths` answer.
- [ ] Take the several-phase decision above, measured on a two-phase fixture
      with one phase below `PHASE_SUPPORT_SIGMA`, and write it in this file.
- [ ] `_unsupported_phase_paths` reads reach, and `PHASE_UNCONSTRAINED` /
      `StageResult.held` name a column that is not a phase path.
- [ ] `mode_fixed_path`'s callers do the same for the Le Bail / Pawley
      force-fix, or the WP records why the two cases differ.
- [ ] Tests: a variable driving an unsupported phase's cell is held (the
      arm that fails today), the untied path stays bit-identical, and the
      obs/calc/diff PNGs in `tests/output/`.
- [ ] Skill: none expected — an agent driving rietx sees only that the hold
      now fires. Confirm at handover, or add the row.

## Acceptance

A variable driving an unsupported phase's structural paths is held for the
stage and reported, and every fit with no user tie is bit-identical.

```sh
.venv/bin/python -m pytest tests/test_named_variables.py tests/test_params.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- [1301](1301-hold-unsupported-phase.md) — the freeze this disarms, and
  `CompiledModel.phase_support`.
- [1119](1119-named-variables.md) § Findings recorded rather than fixed,
  finding 2 — where this was found, by `/code-review medium --fix` on the
  finished branch.
- [1109](1109-refinement-speed.md) — a claim about what a name reaches is
  verified where it is used.

## Handover log

- **2026-09-04** — created, from WP-1119's review pass. Not reproduced as a
  failing test yet: the reasoning is from the two call sites and C's
  structure, so the first task after the accessor is an arm that fails.
