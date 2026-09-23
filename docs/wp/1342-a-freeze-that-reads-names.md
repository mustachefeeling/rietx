# WP-1342 — A structural freeze that reads names, and the tie it cannot see

Milestone: unscheduled · Status: ✅ 2026-09-19 — every freeze that rested on a name now asks what the column moves
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

Since [1441](1441-a-constraint-the-series-can-declare.md) the exposure is a
chain rather than a fit. A tie could once be declared only on a single
`Refinement`, so this defect cost one answer; `SequentialRefinement.fit`'s
`constrain=(index, ref)` hook re-declares it on every pattern, which multiplies
the exposure by the length of the chain and puts it where nobody reads an
individual fit. A ramp is also where it is hardest to see: a freeze that
quietly holds a moving path bends a whole trajectory rather than spoiling one
number, and `direction="both"` cannot separate that from a real one, because
both directions carry the same tie.

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

**Decided 2026-09-19: the first, and it is the flatness argument rather than a
preference.** The hold exists to remove a direction with no gradient. A column
driving two phases' cells through one `vars.X` has real gradient wherever
*either* phase is visible, so it is not flat, and holding it would freeze a
direction the data can see.

Measured on the two-phase fixture (`_absent_phase_inputs`, one LaB₆ present and
one absent, both cells tied to `vars.A`), under the identical plan:

| | present cell | from truth | Rwp |
|---|---|---|---|
| hold if **any** phase is unsupported | 4.200000 Å (the seed) | +10 441 ppm | 0.9589 |
| hold only if **all** are | 4.156594 Å | −1 ppm | 0.0416 |

Two consequences fell out rather than needing rules of their own. The phase's
own `scale` excludes a column by the same test, because a column moving
`phases.1.scale` moves something the data can see — so the "never hold the
scale" clause needs no special case beyond naming it. And a **variable is
dropped before the test**: the column's own entry is in its reach, the forward
model never reads a `vars.X`, and left in, every tied column failed on its own
name and nothing was ever held. `params.vector.is_variable_path` is the one
authority for that distinction and now carries three rules rather than two.

`where` keeps the **columns**, not their reach. `sequential` keys its
persistent-finding aggregation on `where`, so adding the derived ties turns one
finding about a phase into one per tied cell parameter — measured, 3 on the
ramp's cubic CaF₂ for a single absent phase. The account of what else a hold
stopped is `StageResult.held_reach`.

### The seam

`moving_paths` answers "does this entry move", not "which column moves it",
and the hold needs the second. The reach is one row-wise read of **C** — the
same object `_column_extras` reads — but it lives in `optimize/` and the
table has no method for it. Expect a small `ParameterTable` accessor
(free column index → the set of entry paths its non-zero rows name) plus the
two call sites, rather than a change in `optimize/`.

[1432](1432-a-tie-onto-a-rederived-dof.md) repaired the neighbouring seam and
left a precedent worth copying. `ParameterTable._anchored_dofs` records which
entries are displacements from a stored value as **data built where the anchor
is** (`_collect_atom_coords`), never a path prefix matched at the call site.
ADP and Stephens DOFs spell `…adp.k` and `…microstrain.dof.k` the same way and
are absolute, so a name test would have reached the wrong rows there too. This
WP asks the same question one seam over, and takes the same answer: the builder
declares the fact, the consumer never guesses it.

### The siblings, and the two left alone

The defect is "a decision in `refine.py` that reads a free path's name", so the
other decisions were asked the same question. Two more read names; two look
like they do and are fine.

**Fixed — the Le Bail / Pawley force-fix.** `mode_fixed_path`'s drop sites
tested the free path's name, so a `vars.B` driving an atom's `biso` was not
force-fixed and entered θ as a column Le Bail has no |F|² to fit. Measured on
LaB₆: freeing `vars.*` in `lebail` put `vars.B` in the freed set and moved
`atoms[0].biso` 0.5 → 0.7, where freeing the `biso` glob itself freed nothing;
the column carried a value and an esd that read as measurements. `refine.
mode_fixed_column` is the same shape as `_only_moves`, and `parameters()`
reports through it too, so the row and the drop cannot disagree (WP-1076).

That second consumer is why `ParameterTable.entry_reach` exists beside
`column_reach`: C has a column only for a *free* entry, and the drop **makes**
the variable fixed, so a row asked afterwards had nothing to read and called
the column refinable. `entry_reach` reads the declarations C is compiled from,
and a test holds the two equal on every free path.

**Fixed — the GUI's plan panel** (`gui/session.py`, the `/api/plan/resolve`
route). A third drop site, found by reading the remaining callers rather than
by a failure, and the one whose comment already claimed parity: *"exactly what
`_run_stage` does with a mode-fixed hit, and for its reason"*. It was no longer
exact. The panel would have promised a freed `vars.B` that the next run
dropped, which is the disagreement WP-1076's rule is about, and no test covered
it because the panel and the run were never compared on a tied column.

**Missed, and caught by `/code-review high --fix`: `_released_phases`.** The
audit above walked the *other* decisions in `refine.py` and never asked about
the hold's own second half, which is the one place the conversion was
obligatory rather than optional. A held `vars.X` names no phase, so the release
test never matched it and the hold this WP made possible could not be lifted —
a regression this WP created, since that column was not held at all before.
Measured on the ramp's 700 °C pattern with the CaF₂ cell driven through a
variable: held and never released, the cell at its 5.40 Å seed against
5.463026 Å in the untied control, Rwp 0.193923 against 0.054961, and no
diagnostic, the phase being supported by the end. Repaired, the tied arm is
bit-identical to the control. The rule is **any, never all** — the mirror of
`_only_moves`, since one phase appearing gives the column gradient again — and
the reach it needs is the hold's own record, C having no column to ask once the
hold has taken it. **The lesson for the next audit of this kind: convert the
verb and its inverse together**, because a half-converted pair fails in the
direction nothing was testing.

**Left alone — `optimize.identifiability`**. It calls `mode_fixed_path` on
candidates drawn from `EXCHANGE_CANDIDATE_GLOBS`, every entry of which is a
literal model path, so a variable can never be a candidate and the predicate is
only ever asked about a model path. The tie/hold verbs' own refusal
(`_tie_entry`, `role == "target"`) is the same case: it asks about the target,
which is a model path by construction.

**Left alone — the cell window** (`params.vector.cell_window`, applied in
`ParameterTable.bounds` through `_cell_parameter_name`). It reads the free
entry's own name and is genuinely blind to a tie: measured, a `vars.A` driving
an unsupported phase's cell comes back `[-inf, inf]` where the untied path gets
the TOPAS window. It is left that way because the hold now takes that column
first — the window is the belt behind these braces, and `_freeze_cell_windows`
runs inside `run_least_squares`, after `_run_stage` has held. What survives is
the *shared* column, and there no window is the right answer for the same
reason no hold is: bounding it would narrow a direction the data can see.

**Left alone — the joint runner's own builder**
(`multi._unsupported_paths_multi`). Identical shape, unreachable defect:
`JointRefinement` takes a `Structure` and a list of `Instrument`s, never a
`Refinement`, so it has no `add_variable`, no tie register and no
`_apply_ties`. Only the *derived* ties exist in its sub-tables and those stay
inside their own phase, which is the bit-identity this WP pins in
`test_a_derived_tie_never_leaves_its_own_phase`. **Whoever gives the joint
runner a tie verb converts that call site in the same change.**

## Non-goals

- The Jacobian's own gate. `_make_jacobian` already dispatches on reach, not
  on name, and `_peak_chain_column` raises on a wrong claim
  ([1109](1109-refinement-speed.md)); this WP does not touch it.
- Nonlinear constraints. The tie is affine, so the reach is exactly C's
  sparsity pattern.
- `vars.*` in the `.rxt` document — the other finding 1119 recorded, a
  grammar change and a `FORMAT_VERSION` bump, and cosmetic where this is not.

## Tasks

- [x] A `ParameterTable` accessor giving a free column's reach (the entry
      paths its non-zero C rows name), with the empty-C and no-tie cases
      pinned bit-identical to today's `free_paths` answer.
- [x] Take the several-phase decision above, measured on a two-phase fixture
      with one phase below `PHASE_SUPPORT_SIGMA`, and write it in this file.
- [x] `_unsupported_phase_paths` reads reach, and `PHASE_UNCONSTRAINED` /
      `StageResult.held` name a column that is not a phase path.
- [x] `mode_fixed_path`'s callers do the same for the Le Bail / Pawley
      force-fix, or the WP records why the two cases differ.
- [x] Tests: a variable driving an unsupported phase's cell is held (the
      arm that fails today), the untied path stays bit-identical, a series
      fixture declaring the tie through `constrain=` beside the single-fit
      one, and the obs/calc/diff PNGs in `tests/output/`.
- [x] Skill: one clause, in `references/abstention.md` rather than the
      body. `PHASE_UNCONSTRAINED`'s row said "`where` lists its structural
      parameters", which a held column need not be — so it now says the hold
      acts on a column, names `held_reach` as the way back to the parameters,
      and states that a variable driving two phases is never held. The body
      needs nothing: rule 22 already says a held value is not a measurement,
      whatever its path is called.

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

- **2026-09-19** — **Closed.** A refinement that constrains a parameter with a
  tie of its own is now protected by the same per-stage freezes as one that
  does not. Until today two of those freezes tested what a free parameter was
  *called*, and a tie moves the freedom to a name they did not recognise, so
  both reported that they had done their job on a set they could not see into.
  The cost was a whole class of quiet wrong answer: on five patterns of a ramp
  containing no fluorite at all, its cell came back spread over 0.296 Å with
  every Rwp within 1e-5 of the correct run's, three of the five patterns
  reporting nothing at all and no chain-level finding firing. What it rules
  out is the reflex fix. Holding every column that touches an invisible phase
  would freeze the cells of the phases that *are* there, measured at 10 441 ppm
  from the truth against 1 ppm, so the rule is that a column is held only when
  everything it moves is invisible. The package now has one accessor for "what
  does this column move", and the four decisions that need it read it.

  **Done.** `ParameterTable.column_reach` reads C column-wise, beside
  `moving_paths`' row-wise read, and `entry_reach` answers the same question
  for an entry that is not a column (C has none for a fixed entry, and the Le
  Bail drop *makes* a variable fixed, so a row asked afterwards had nothing to
  read). Four consumers converted: `_unsupported_phase_paths` through
  `_only_moves`; the Le Bail/Pawley force-fix at both drop sites through
  `mode_fixed_column`; `Refinement.parameters`' `mode_fixed`, so the report and
  the drop cannot disagree; and the GUI's `/api/plan/resolve` panel, whose own
  comment already claimed parity with the stage it previews. `StageResult`
  gains `held_reach`, because `held` now names a column that need not be a
  phase path and `PHASE_UNCONSTRAINED` still has to find the phase.

  **Measured.** The decision, on the two-phase fixture under a converging plan:
  holding a shared column left the visible phase's cell at its 4.20 Å seed,
  +10 441 ppm, Rwp 0.9589, against 4.156594 Å at −1 ppm and Rwp 0.0416 free.
  The single-fit walk through a tie, 5.2 → 3.35512 Å with the two fits agreeing
  on Rwp to **1.7e-15** — the flat direction costs nothing at all to travel,
  which is why no Rwp comparison could ever have found this. The chain, with
  the name test restored: 5.30422, 5.38679, 5.57821, 5.39074, 5.59999 Å, two on
  the caller's own bound. Le Bail: freeing `vars.*` put `vars.B` in the freed
  set and moved an atom's `biso` 0.5 → 0.7 where freeing the `biso` glob freed
  nothing; repaired, the fit is Rwp bit-identical to the untied one. Cost of
  the new accessor on the report path, 110.6 µs against `parameters()`'s
  12.62 ms, 0.9 % of the call it sits in.

  Counts, this worktree's venv, `[dev]` only (jax and torch absent), numba
  0.67.0, darwin/arm64, nothing else mid-suite. `origin/main` had not moved
  since the branch point, so this **is** the merged tree rather than a proxy
  for it. Fast 5433 passed / 134 skipped in 1:17–1:23, moving 5542 → 5567 by
  exactly the 25 non-slow tests of the 26 added — 23 here and 3 from the review
  pass — with the skip count unmoved at 134. Full 5613 passed / 143 skipped in
  22:46, which is +3 on the same tree before the review, its three tests. ruff
  clean over src tests examples. The full selection ran **twice**, both times
  on a settled tree: the first run was launched and then edited under, which is
  the mistake `tests/CLAUDE.md` names, and it was stopped rather than quoted.

  **Gotchas for anyone touching this seam.** A column's own entry is in its
  own reach, so a variable fails a test about model paths on its own name
  unless it is dropped first — `is_variable_path` is the one authority and now
  carries three rules rather than two. `held_reach` must be read **before**
  `set_vary` takes the column out of θ, which is why it travels on
  `_StageHold` rather than being asked of the table afterwards, and why the
  mid-stage collapse captures its own. And `PHASE_UNCONSTRAINED`'s `where`
  deliberately carries the **columns** and not their reach: `sequential` keys
  its persistent-finding aggregation on `where`, so the derived ties turned one
  finding about a phase into three on the ramp's cubic CaF₂.

  **Deliberately not generalised**, both recorded in § The siblings above with
  their reasons. The cell window still reads the free entry's name and is
  genuinely blind to a tie, left that way because the hold now takes that
  column first and because for a *shared* column no window is the right answer;
  and `multi.py` keeps its own identically-shaped builder, unreachable because
  `JointRefinement` takes a `Structure` and never a `Refinement`, so it has no
  tie register at all — **whoever gives the joint runner a tie verb converts
  that call site in the same change**.

  **The review pass earned its place and found a regression this WP created.**
  `/code-review high --fix` returned four findings, all accepted, all applied.
  The high one is `_released_phases`, the hold's own inverse, left on the name
  test — so the new column-holds could never be lifted, measured at Rwp 0.193923
  against the untied control's 0.054961 with the cell stuck at its seed, and
  reproduced here independently before accepting the fix. Two were claims of
  mine that were simply wrong: `_held_by_phase` stopped at the first phase a
  held column named, and a column driving *two absent* phases is held, so the
  second phase got no `PHASE_UNCONSTRAINED` at all — the "never held" sentence
  was true only of a column reaching a **visible** phase, and it was repeated in
  the manual and the skill row. The fourth: `entry_reach` tested each flattened
  term where `_rebuild` sums a source's coefficients into one C entry, so a
  cancelling `dep = p - q` broke the invariant holding the two readings equal.
  Nothing was declined.

  **Next**: nothing on this WP. The two notes above are the only live threads
  it leaves, and both are conditional on work nobody has scheduled.

- **2026-09-04** — created, from WP-1119's review pass. Not reproduced as a
  failing test yet: the reasoning is from the two call sites and C's
  structure, so the first task after the accessor is an arm that fails.
