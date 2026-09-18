# WP-1441 — a constraint the series can declare

Milestone: v1.5.x · Status: ✅ 2026-09-18 — `constrain=(index, ref)` on
`SequentialRefinement.fit` is the channel a tie and a named variable never had, and a
variable's value now crosses the boundary under the existing `carry` globs; the carry
buys no measurable iterations (176 vs 186 one way, 168 vs 140 the other) and is there
because a declared control that does nothing is WP-1076's shape. Issue #376's open
question answered: symmetry refuses on pattern 1, never quietly later
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
  `MultiHistogramRefinement` declares no tie verbs at all; what a joint fit shares
  is `sharing=`, a different mechanism rather than a second instance of this gap.

**The issue's open question, answered.** "Whether a symmetry tie would interact
with a hypothetical user-tie mechanism": it does not, and the refusal is the
single-`Refinement` one. Every `ParameterTable` rederives the symmetry ties from
the space group before the hook sees it, so `ref.tie("phases.0.cell.b", ...)` on
cubic LaB6 raises `'phases.0.cell.b' already follows 'phases.0.cell.a'
(symmetry); symmetry outranks a user tie` on the first pattern, before any fit.
No pattern exists on which the same declaration would quietly take.

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

### 2026-09-18 — a chain can be told what to hold constant

Someone refining an in-situ series can now say "these two sites share one
displacement parameter" and have it be true of every pattern, which was
impossible before in the strict sense: there was no object to say it to. A tie
and a named variable live on the `Refinement`, a series builds a fresh one per
pattern, and the only hook it had ran a line before that object existed. The
reporter's workaround had been to drop the second occupant's Biso from the
turn-on glob, which is refining a different model rather than the one they meant.
The channel is `constrain=(index, ref)`, and it carried a second fix with it:
a named variable's value now crosses the pattern boundary like every other
parameter, so `carry` means what it says for `vars.*` as well.

The honest result on the second half is that it buys nothing you can measure.
Carrying the variable cost 168 iterations against 140 on a flat series and saved
176 against 186 on one whose tied parameter walks, swinging both ways, with
fitted values agreeing to ~1e-8. It is in because a declared control that does
nothing is the shape WP-1076 exists to remove, and because only the chain knows
which pattern was *accepted* — a caller warm-starting by hand would seed the
next pattern from a fit that failed.

**Done.** All five checklist items.

- `constrain` on `SequentialRefinement.fit`, threaded through
  `_run`/`_chain`/`_fit_one` and through `_verify_discontinuities`' cold refit.
  A hook rather than the issue's `ties=` constructor argument: `tie_equal`
  resolves globs against a live `ParameterTable` and nominates the first match
  in table order, so a tie is a verb call against a table and not a value a
  constructor can hold. Chosen signature is `(index, ref)`, not
  `prepare`'s four — `ref` is the whole point and a caller closes over its own
  `patterns`/`x` for the rest.
- `_carry_variables`, beside `_carry_into` because a variable is reachable by
  neither of that function's arguments. Runs **after** the hook, the only order
  in which the name exists, and goes through `set_values` so the ties following
  the variable refresh and the models agree with θ at the next compile. It
  records no node, the pattern's tree not existing until its `fit` fingerprints
  the data.
- Seven tests, the manual (`series.md` § Declaring a constraint on every
  pattern, plus a pointer from `constraints.md`), a §9b skill row, and one
  standing rule in the root CLAUDE.md.

**Measured** (`.venv` `[dev]`, macOS arm64, Python 3.12; three synthetic LaB6
patterns from `_simulate` unless said otherwise).

- The defect, on `main` at `13bce502`: biso(La)/biso(B) free and independent at
  0.380939/0.405582, 0.387008/0.383731, 0.389977/0.393988. After: identical per
  pattern and equal to `vars.B_all` to the last bit, the tie being scale 1
  offset 0.
- The hook fires once per **fit**: 8 calls for 6 patterns under
  `verify_discontinuities=True`.
- The carry, on a seven-pattern series whose tied `biso` walks 0.4 → 3.4 Å²:
  176 iterations carried against 186 cold, all converged, Rwp identical to
  5 dp. On the flat series it loses, 168 against 140. Both directions, so the
  number to quote is "no measurable effect", never a speed claim.
- `_TIED` is `mccusker_default` plus the displacement stage, reaching Rwp 0.041
  and GoF 1.00. The displacement stage alone reaches 0.985, and a tie measured
  on a fit that did not converge says nothing about ties — that is why the plan
  in the tests is not `_CHEAP`. PNGs and low-angle zooms in `tests/output/`,
  inspected: flat difference curve, peaks matched in position and height.
- Counts. Fast selection 5319 → 5326 passed, 134 skipped unchanged: exactly the
  seven tests added, no new skip. Full suite green on the code-final tree,
  5505 passed / 143 skipped / 0 failed in 23:57 — quoted as an absolute, since
  no local full baseline was taken before the change; the delta is the fast
  selection's. Commits after that run were docs plus one cap constant, all
  covered by the fast selection, which was re-run green on the final tree.
- Caps raised rather than shaved, each with its reasoning in
  `tests/test_docs_consistency.py`: CLAUDE.md 914 → 923 (landed 922),
  ROADMAP 748 → 762 (landed 760, for the new `### v1.5.x` section).

**The issue's open question, answered.** A user tie naming a symmetry-owned path
refuses on the first pattern with the single-`Refinement` message, every table
rederiving the symmetry ties before the hook sees it. There is no pattern on
which the same declaration quietly takes. Pinned by
`test_symmetry_outranks_a_constrain_tie_on_every_pattern`.

**What was deliberately not generalised.** `multi.py` looks adjacent and is not
a second instance: `MultiHistogramRefinement` declares no tie verbs at all, and
what a joint fit shares is `sharing=`, a different mechanism. WP-1432's
coordinate-DOF defect is untouched — a chain is clear of it by construction,
one declaration per fresh table — and both it and WP-1342 have `### Inherited`
notes saying what changed for them.

**Where it is filed.** v1.5.0 shipped this morning, tagged at `13bce502`,
published and on PyPI, so no milestone is open and protocol step 6 wanted this
addition staged in a record the day it landed. It follows the v1.0.x precedent:
`### v1.5.x — after the ship` in ROADMAP, `Milestone: v1.5.x`, and
`docs/releases/1.5.1.md` as the staging file that either ships or folds into the
next minor. Opening v1.6 stays the maintainer's decision and nothing here
pre-empts it. ROADMAP's "still owed before the tag" line was stale and is gone;
Current focus lost v1.5's summary to the record that already carries it.

**Gotchas for whoever is next in `sequential.py`.**

- The hook runs once per fit, so a hook that counts its own calls counts fits.
  Ladder rungs and the verify refit are fits.
- `previous_vars` is set inside the `entry.status != "diverged"` branch, which
  is what gives it the quarantine rule for free. Move it out and a failed
  pattern starts seeding its successor.
- `_carry_variables` inherits `set_values`' refusals. A hook that narrows a
  variable's bounds per pattern until the carried value falls outside them
  raises, naming the path — deliberate, and the docstring says so.

**Next.** Nothing on this WP; it closes. The two adjacent defects are
[1432](1432-a-tie-onto-a-rederived-dof.md) and
[1342](1342-a-freeze-that-reads-names.md), both now carrying what this session
learned, and 1432 is the one a series makes more expensive rather than less.

- **2026-09-18** — created.
