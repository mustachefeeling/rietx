# WP-1441 — a constraint the series can declare

Milestone: unscheduled · Status: 🔄 2026-09-18 — claimed by @yue-here
Depends on: — (1070 declared the ties, 1119 the variables; this is the series' side of both)

## Goal

A user constraint — a tie, a named variable, or the two together — can be declared
for every pattern of a `SequentialRefinement`, not only the first, and a variable's
refined value crosses the pattern boundary under the same `carry` globs every other
parameter does.

## Context

Issue [#376](https://github.com/yue-here/rietx/issues/376), reported 2026-09-18 by
@mustachefeeling from a real multi-phase in-situ series, where a Biso tie between the
two occupants of a mixed-occupancy site was needed on every pattern and could be
applied to none of them. Their workaround was to drop the second occupant's Biso from
the turn-on glob.

**The gap is an absence, not a drop.** `RefinementState` names eight facts, and the
series has a channel for six of them: `structure`/`instrument` through `carry`, `mode`
and `two_theta_limits` through `fit`'s arguments, `free_paths` through the plan,
`reflections` through `_fit_one`'s `previous_hkl`. The two with no channel are
`ties` and `variables`, and they are exactly the two that are not *in* the models —
`Refinement._ties` and `Refinement._variables` are the one authority for each, no
field of `Structure` or `Instrument` holds either, and `Parameter.expr` is reserved
and raises. `_fit_one` builds a fresh `Refinement` per pattern, so whatever pattern 1
was told by hand is gone by pattern 2. The `prepare` hook cannot help: it is called
one line *above* `ref = Refinement(...)`, on the models, so there is no object to call
`.tie()` on.

**Measured on `main` at `13bce502`** (this worktree's venv, `[dev]`, macOS arm64,
Python 3.12), three synthetic LaB6 patterns from `tests/test_sequential._simulate`,
a three-stage plan whose last stage frees `phases.*.atoms.*.biso` and `vars.*`:

| | biso(La) | biso(B) |
|---|---|---|
| p000 | 0.380939 | 0.405582 |
| p001 | 0.387008 | 0.383731 |
| p002 | 0.389977 | 0.393988 |

The two are free and independent on every pattern, and no argument of
`SequentialRefinement.__init__` or `.fit` can make them one. The same constraint on a
single `Refinement` — `add_variable("B_all", 0.4)`, `tie_equal(["phases.0.atoms.*.biso"],
source="vars.B_all")` — fits and reports `vars.B_all = 0.38116079`.

**The sibling the issue does not name.** The motivating case is two moments forced
equal and antiparallel off *one shared amplitude*, which is a named variable plus two
ties (WP-1119's `add_variable`). A variable is not in the models either, so
`_carry_into` — which reads its values off a `ParameterTable` built from the previous
fitted pair — cannot reach one. `carry`'s default `["*"]` claims to carry everything
and `vars.B_all` is an ordinary dot-path, so a variable silently restarting cold on
every pattern is WP-1076's shape: a declared name making a claim nothing keeps.

**Seams.** `sequential.SequentialRefinement.fit` (the hook argument and its
docstring), `_run`/`_chain`/`_fit_one`/`_verify_discontinuities` (the thread), and
`_fit_one`'s post-construction block, which already reaches into the fresh
`Refinement` for exactly this class of thing (`_declared_wavelengths` per WP-1134,
`_pending_reflections` for Le Bail/Pawley). `refine_sequential` forwards unknown
keywords to `fit`, so a `fit` keyword needs no plumbing there and a constructor
argument would.

**Why a hook rather than a declarative argument.** `tie_equal` resolves its globs
against a live `ParameterTable` and nominates *the first match in table order* as the
source, so a tie is a verb call against a table, not a value a constructor can hold.
A per-pattern `Refinement` has a fresh table; re-declaring against it is the only
spelling that means the same thing on every pattern. It also closes both halves of
the class with one seam, and it is what WP-1432 wants: a tie declared once per fresh
table is not re-applied by a later write-through.

## Non-goals

- WP-1432's coordinate-DOF tie defect. A tie onto a rederived-and-relative entry is
  wrong on a single `Refinement` too; this WP does not make it right, and does not
  make it worse (one declaration per pattern, against a fresh table).
- A tie that is *carried* rather than re-declared. The hook runs per pattern; nothing
  copies `_ties` from pattern n−1 to pattern n, and the issue's "direction 1" (a
  `ties=` constructor argument) is not taken.
- `multi.py`'s joint residual, which has its own table and is not a chain.

## Tasks

- [x] `constrain` hook on `SequentialRefinement.fit`, `(index, ref) -> None`, called on
      each per-pattern `Refinement` after construction and before its fit; threaded
      through `_run`/`_chain`/`_fit_one` and through `_verify_discontinuities`' refit,
      so a verify refit carries the same constraints the chain did
- [x] Named-variable values cross the pattern boundary under the existing `carry`
      globs, `vars.<name>` matched as the ordinary dot-path it is
- [x] Tests: the tie holds on every pattern; the variable warm-starts and a narrow
      `carry` excludes it; the ladder's rungs and the verify refit see the hook; a
      hook that raises is the caller's error, not a swallowed one
- [x] Manual Part 1 (`docs/manual/using/series.md`) and the `parameters`/constraints
      chapter cross-reference, whichever owns the tie verbs
- [x] Skill: a row in the series reference (`references/9b-*`), since a tie on a
      series is a task-shape rule and not a rule for every fit

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_named_variables.py tests/test_params_surface.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

## References

- Issue #376 (@mustachefeeling), the reproduction and the two proposed directions.
- WP-1070 (user ties), WP-1119 (named variables), WP-1134 (`_fit_one`'s existing
  post-construction reach into the fresh `Refinement`).

## Handover log

- **2026-09-18** — created.
