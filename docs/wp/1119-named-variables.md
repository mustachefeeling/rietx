# WP-1119 — named variables and equations: a `prm` of one's own

Milestone: unscheduled · Status: ✅ 2026-09-04 — named variables ship; the
equivalence bar caught the Jacobian dispatching on a name, and the TOPAS
comparison closed the tie-bounds hole
Depends on: — (WP-1070 built the affine block this extends; 1118 is its first
non-human consumer, and needs this to land in)

## Goal

A caller declares a named variable with its own value and bounds, then writes
other parameters as linear functions of it — `A`, `2·A`, `A + 0.5` — naming the
variable rather than a dot-path. TOPAS's `prm` and its equations, in the linear
subset the constraint block already computes exactly.

## Context

**The linear half already works, which is why this is a surface WP and not a
physics one.** Measured on this tree (NAC, six atoms, 2026-08-21), nominating
`atoms.0.biso` as the variable:

```python
ref.tie_equal(["phases.0.atoms.1.biso", "phases.0.atoms.2.biso"],
              source="phases.0.atoms.0.biso")
ref.tie("phases.0.atoms.3.biso", "phases.0.atoms.0.biso", scale=2.0)
ref.tie("phases.0.atoms.4.biso", "phases.0.atoms.0.biso", scale=1.0, offset=0.5)
```

```
phases.0.atoms.0.biso   value=0.7    refinable=True    tie=None
phases.0.atoms.1.biso   value=0.7    refinable=False   tie=1·phases.0.atoms.0.biso
phases.0.atoms.2.biso   value=0.7    refinable=False   tie=1·phases.0.atoms.0.biso
phases.0.atoms.3.biso   value=1.4    refinable=False   tie=2·phases.0.atoms.0.biso
phases.0.atoms.4.biso   value=1.2    refinable=False   tie=0.5 + 1·phases.0.atoms.0.biso
phases.0.atoms.5.biso   value=0.8212 refinable=True    tie=None

A → 1.3 gives  Ca1 1.3  Al1 1.3  Na1 1.3  F1 2.6  F2 1.8  F3 0.8212
set_vary("phases.0.atoms.*.biso") frees  atoms.0.biso, atoms.5.biso
```

`Refinement.tie(path, source, scale=, offset=)` is the general affine form and
`tie_equal` is its `scale=1, offset=0` case. These are constraints, not
restraints: the tied rows leave θ, so the parameter count drops and a `set_vary`
glob frees only the untied masters. They are exact inside the fit rather than
bookkeeping — `p = C·θ + d` is a constant matmul, and `_column_extras` is the
gate that stops a tied column coming back short (root CLAUDE.md § Invariants).

### What is missing, measured in the same session

1. **No free-standing variable.** "A" has to be an existing model parameter
   nominated as the master, so it inherits that parameter's bounds and
   transform, is spelled as a dot-path rather than a name, and a variable with
   no home in the model cannot exist at all. **This is the WP.**
2. **One source per tie.** The verb takes a single `source`; `AffineTie` and
   `TieSpec` are already `Σ c·source + const`, so the representation is
   multi-term and only the public verb is not. `B = A + C` is unspellable today
   and needs no new storage.
3. **No chains.** `tie` refuses a tied source — *"carries no freedom of its own;
   tie to what it follows instead"* — while `AffineTie`'s docstring says the
   table flattens chains at rebuild. So the one-level rule is a verb-level
   decision, and this WP has to take it deliberately rather than inherit it.
4. **Linear only, by construction.** `A*B` or `sqrt(A)` is outside `p = C·θ + d`,
   which is what keeps the constraint exact under autodiff. Fenced below.
5. **No expression strings.** Everything is method calls; nothing parses `"2*A"`.
6. **Not reachable through `refine_json`** (WP-1110 item 16).

### The seam is narrower than "a new kind of parameter"

`ParameterTable.add_parameter` already appends a **synthetic** entry outside the
model tree — that is how a Wyckoff DOF (`phases.0.atoms.2.dof.0`), an ADP basis
component and a Stephens coefficient work, each owning the freedom while the
model's own fields follow it by affine tie. A named variable is that shape.

What is genuinely new is **persistence**, and it is the one thing to get right
first. A Wyckoff DOF is *rederived* from the structure on every table build, and
`apply_to_models` writes values back by walking the model tree, so a synthetic
entry with no model field has nowhere to be written. A user's variable has no
source of truth except the document. Three existing authorities say where it
therefore goes:

- **`RefinementState`** carries `free_paths` and `ties` for exactly this reason,
  and its comment states it: a tie is not a property of the models, so a node
  that did not carry it would restore a state with the constraint silently gone
  and the parameter count with it. A variable is the same class of fact and
  needs the same treatment, or a checkout loses it.
- **`Refinement._ties`** is the one authority for *which* ties are the user's,
  because every `ParameterTable` build rederives the symmetry ties and knows
  nothing about a user's. A variable register sits beside it and is re-declared
  on each build the same way (`_apply_ties`).
- **Symmetry outranks a user tie**, enforced in `_apply_ties` and not only in
  the verbs' refusals, because a model edit can make an already-tied path
  symmetry-tied after the fact. A variable's dependents inherit that rule.

Two consequences to design for rather than discover: `ParameterRow` mirrors
`params.vector.Entry` field for field, pinned by `dataclasses.fields`, so
whatever the variable is on the table it reaches the public surface; and a new
persisted field is a contract change, so it bumps its version with a comment
saying what (the WP-1117 rule, one sentence beside the constant).

**Prior art before the schema.** TOPAS: `prm A 1.0 min 0 max 5`, then
`biso = 2 A;` — a first-class named object with its own bounds, equations parsed
from strings at load, and a `!` prefix for a fixed one. GSAS-II: constraints are
equations over named parameters, edited in a constraints dialog. Check both
before fixing the shape; concepts only, and the licence fences in
`ATTRIBUTION.md` apply (TOPAS closed, GSAS-II spec-only under its grant-back
clause).

### The boundary this WP draws for someone else

**A foreign-file reader resolves symbols without being an expression
evaluator, and that line is drawn here.** WP-1118's two merged readers both
stopped short of one on purpose: `io/projects/topas.py` carries module-level
`symbol_table` and private `_resolve` / `_arith` — enough arithmetic to read a
value a `.inp` states through a named symbol, and deliberately no more — and
`io/projects/fullprof.py` decodes a `.pcr`'s `10·n + multiplier` codewords into
ties without parsing anything. Neither is a package export (`io.projects.__all__`
is the two readers and their two error types), so nothing here has to keep either
working. What this WP must not do is redeclare that arithmetic before deciding
whether a named variable is what those readers should have been resolving into.

The live case 1118 parked here is issue **#107**: seven archive files open a
phase with the macro form `STR(R-3)` / `STR(######, "#name#")`, invisible to the
reader's line-based split, so such a file is refused by name (`_STR_MACRO`,
`topas.py:1866`) rather than read. Whether the fix is a special case or a general
macro pass is 1118's registry-shape task, but a general pass borders this WP's
equation scope and 1118's file says the boundary is settled **here, not twice**.

### The first concrete ask is a restraint row, not a tie

Issue **#212** wants a conserved elemental ratio held across phases —
Cu/(Ca+Al) = 1.935 through a reduction series, where diffraction alone moves
17 wt % between two phases for 0.2–0.5 pp of Rwp. It is linear in the phase
scales, because moles of E ∝ Σ_p S_p·V_p·n_{E,p} and `phase_zmv`'s
`element_counts` (`optimize/qpa.py`) already carries n_{E,p}, so a
`√w·(Σ c_k·x_k − target)/σ` row over (path, coefficient) pairs needs no
expression language at all. The seam the issue isolates: `Phase.restraints` is
per phase and `Structure` holds no cross-phase list, so the row belongs beside
`resolve_phase_restraints` (`model/restraints.py:114`) at `Structure` level.
[1325](1325-parametric-series.md) names it as one instance of a parametric
constraint. Whether it is this WP's first deliverable or a WP of its own is the
task below.

## Non-goals

- **Nonlinear expressions.** `A*B`, `sqrt(A)`, trigonometry: outside `C·θ + d`,
  which is what makes a constraint exact under autodiff. That is
  `Parameter.expr`'s designed-but-unbuilt DSL — AST-whitelisted, emitted as
  backend ops, with asteval and sympy evaluated and rejected (DESIGN.md
  § Parameter system) — and a separate WP. The field it would need is **kept**:
  the maintainer decided WP-1110 item 5 on 2026-08-21 with this WP as the
  reason, so `Parameter.expr` stays reserved rather than being removed at
  `SCHEMA_VERSION` 0.2 → 0.3.
- **Restraints.** A constraint removes a parameter; a restraint keeps one and
  charges for disagreeing (`docs/manual/using/constraints.md`).
- **A `.inp` parser.** [1118](1118-foreign-model-files.md) owns reading foreign
  files; this WP owns the object such a reader would target. If both are wanted,
  this one is first.
- **The JSON request field** (WP-1110 item 16) unless it falls out free once the
  object exists.

### Decisions taken, 2026-09-04

The four the tasks below asked for, settled with the maintainer before any code
was written.  Recorded here rather than only in a handover entry, because three
of them are the shape a later reader has to work inside.

**1. A variable is a `Parameter` with a name, spelled `vars.<name>`.** The
namespace is free: the model tree's only top-level segments are `phases` and
`instrument`, so `vars.` cannot collide, and it globs — `set_vary("vars.*")`.
Reusing `schemas.common.Parameter` rather than inventing a type is what makes
the equivalence bar reachable: `ParameterTable._add` takes an entry's bounds
*and its transform* straight off the `Parameter`, so a variable declared with
the same `min`/`max`/`transform` as the model parameter it replaces produces
the identical `Entry`, and the fit cannot tell them apart.  `Atom.biso` is
`Parameter(value=0.5, min=0.0, max=25.0)`, identity transform, which is what
the acceptance fit declares.

**2. A tied source is accepted iff it is a variable.** Measured on this tree
(2026-09-04): `ParameterTable._flatten` already collapses chains exactly and
raises on cycles — a depth-2 user chain `C = 3B+1`, `B = 2A+0.5` comes back as
coefficient 6.0 and constant 2.5, and a user tie onto a *symmetry*-tied source
(`biso = 4·x` where `x ← dof.0`) flattens onto `dof.0` at coefficient 4.0 and
constant 0.7972.  Both are refused by the verb, and nothing the package derives
reaches depth 2 (cell `b ← a` and `x ← dof.0` are both depth 1), so the
flattening has been correct but unexercised.  So the refusal is verb-level and
the decision is which half to keep: a **variable** may follow other variables
(`B = A + C`, TOPAS's `prm B = 2 A`), and a **model path** keeps the refusal,
where *"tie to what it follows instead"* is good advice — naming `dof.0` is
clearer than reaching it through `.x`, and the constant that flattening bakes in
is one nobody wrote.

**3. Issue #212's cross-phase restraint row is its own WP.** It is a residual
*row*, not a parameter — a new `BLOCK_ORDER` block and a `Structure`-level
schema seam beside `resolve_phase_restraints` — and it shares only the
(path, coefficient) representation with the work here.  Folding it in would turn
a parameter-surface WP into a residual-row one.  [1325](1325-parametric-series.md)
and the issue's filer both wait on the seam, not on this object.

**4. No expression parser, this WP.** Four reasons, weighted: it would be the
**second** parser for one language, since `Parameter.expr` is reserved for the
nonlinear DSL and the two would have to agree on precedence, name resolution
and error text for the half they share; a **stored** string joins
`PROJECT_FORMAT_VERSION`, while `(path, coefficient)` pairs already are the
storage, and sugar added later needs no bump where a withdrawn grammar does;
the failure mode is **silent** — `"2A"` is multiplication in a `.inp` and a
syntax error in Python, `"A + B*2"` has a precedence answer somebody must
choose, and a wrong one converges under a constraint the caller did not write;
and it would **pre-empt** the boundary 1118 parked here, since #107's macro pass
would then want to feed TOPAS expressions to a grammar that is almost, but not,
TOPAS's.  Against all that: a strict parser refusing `2A` rather than guessing
removes most of the third reason, a string beats a coefficient dict for anyone
typing into the GUI, and the nonlinear DSL has been designed-but-unbuilt for a
while.  So this is *not in this WP*, not *never*: a string form is a thin
lowering onto the same pairs and can land without re-litigating any of the
above.

## Tasks

- [x] Decide the object: a `Parameter` named `vars.<name>`, appended by
      `add_parameter`, listed by `parameters()` like any other row, named in a
      tie by its path (Decisions § 1).
- [x] Persistence: `RefinementState.variables`, `NodeAction.variables` /
      `removed_variables` under a `set_variable` kind, the project round trip
      (free — `history.jsonl`'s head *is* the working state), and
      `SCHEMA_VERSION` 0.15 → 0.16 with its comment.
- [x] Verbs: `add_variable` / `remove_variable`, and `tie` taking a
      `{path: coefficient}` mapping or a pair list, with `scale` multiplying
      every term.
- [x] Take the #212 decision — a WP of its own (Decisions § 3).
- [x] Take the chain decision — a tied source is accepted iff it is a
      variable, measured either way (Decisions § 2).
- [x] An expression string for the linear subset — it did **not** survive the
      design, and the four reasons plus the case against them are recorded
      (Decisions § 4) so a later session need not re-take it.
- [x] The manual: `{ref}`named-variables`` in `using/concepts.md`, signposted
      from `using/constraints.md`, plus the `set_variable` row and the two new
      state fields in `using/history.md`, and both verbs in the skill's
      `references/api.md` (three copies synced). No *new* diagnostic code
      landed; the second session gave the existing `BOUND_HIT` row in
      `references/diagnostics.md` its new cause, a tie handing a dependent's
      ceiling back to its source.
- [x] Tests, including the equivalence bar below — which the tests
      rewrote (Acceptance, and the § Measured block under it).
- [x] Reassess the shipped surface against TOPAS's `prm`, and close what the
      comparison shows is a hole rather than a difference: a tie now carries its
      dependent's bounds onto its source (`params.vector.tie_window`), and the
      several-source corner it cannot close names the path, the bounds and the
      tie instead of raising a bare `ValidationError`
      (§ The tie-bounds hole, closed).

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_named_variables.py
```

The bar, as measured on 2026-09-04 rather than as written on 2026-08-21. The
original said the variable spelling must be **bit-identical** to the dot-path
one, "so anything else is a bug". That is two claims, and only the first of
them is true:

- **The model is identical, bit for bit.** Two arms of one fixture — four-site
  LaB6, the coefficients 1, 1, 2 and 1 + 0.5 — differing only in whether the
  four Biso rows follow `phases.0.atoms.0.biso` or `vars.B_metal`. The decoded
  physical state agrees path by path, the residual is `array_equal`, and every
  Jacobian column agrees with the column carrying the same parameter. This is
  where the check has to be, because the whole-model FD agrees with itself
  either way (the "agreeing with the wrong oracle" trap the root CLAUDE.md
  records for a phase scale's column) — and it is the check that **found the
  defect**, below.
- **The converged fit is bit-identical too, once the fit is a good one.** A
  variable is *appended* to the table, so in a multi-stage plan it is θ's last
  column while the dot-path master sits in the middle — same columns, different
  order, and scipy's TRF need not be indifferent to that. Measured, it is: on
  the four-stage plan (Rwp 0.041927047660878604, GoF 1.03, nine free) Rwp, the
  per-stage iteration counts `[9, 15, 7, 9]` and **every** refined value agree
  bit for bit, with the master's esd within one ulp (4.2e-16 relative).
  The test still carries `rel=1e-9` rather than an equality, because a
  tolerance between two independently-converged fits is a cross-platform claim
  and this is one platform (`tests/CLAUDE.md`) — and that bar has its margin
  measured both ways: 4.2e-16 above it in agreement, and **1.14e-8** below it
  when `_column_identities` is disabled, eleven times over.

  **An earlier draft of this bar read 1.6e-9, and the number was an artefact of
  a bad fixture.** The first plan never freed the profile width the fixture
  perturbs 2×, so both arms converged at Rwp 0.57 with GoF 13.9 — visible
  immediately in the obs/calc/diff PNG, which is what that standing rule is for
  — and a solver wandering through a badly misfit problem amplified the column
  ordering into the ninth digit. The plot, not the assertion, is what said so.
  A second draft freed `instrument.profile.*` whole and moved the esd
  disagreement to 8.7e-5, which was a different lesson and also real: the free
  set then contains `profile.y` sitting on its softplus floor, and
  `normal_covariance` equilibrates and cuts eigenvalues at `rcond·|λ|max`, so a
  near-threshold eigenvalue is decided differently under a different column
  order. The *values* agreed to 3e-9 of an esd throughout. The fixture now
  frees `w` and `x` only, which this pattern determines.
- The parameter count drops by exactly the number of dependents, and rises by
  one for the variable.
- The variable survives a history checkout and a `history.jsonl` round trip, and
  a checkout restores the parameter *count*.
- A dependent that becomes symmetry-tied after a model edit is reported and
  dropped, not silently overwritten.

### Measured, 2026-09-04

macOS darwin 25.5.0, worktree `.venv`, python 3.12, `[dev]` extras (no
jax/torch, so the cross-backend rows self-skip).

**The defect the bar found, which nothing went red over.** `_make_jacobian`
dispatches on the free path's *name*, and `vars.B_metal` is a name no analytic
branch was written for — so a variable driving four Biso rows fell to the
whole-model FD column while the identical constraint written with
`phases.0.atoms.0.biso` as its master took the peak chain. That column sat
**8.6e-7** from the analytic one, and cost one extra full residual evaluation
per Jacobian, for a construct whose entire claim is to be a renaming. The FD
fallback is *exact* in the sense its own docstring means — it decodes through C
like the residual — so it is approximate to O(h) and never short, which is
exactly why no test could have caught it. `_column_identities` fixes it at the
dispatch: a variable moves no residual row of its own, so what it *is*, for
dispatch, is what it reaches. Afterwards every column is bit-identical.

**The chain measurement**, which decided Decisions § 2. `_flatten` collapses a
depth-2 user chain (`C = 3B+1`, `B = 2A+0.5`) to coefficient 6.0 and constant
2.5, and a user tie onto a symmetry-tied source (`biso = 4·x`, `x ← dof.0`) onto
`dof.0` at coefficient 4.0, constant 0.7972 — both exact, cycles raise, and
nothing the package derives reaches depth 2.

**Suite**, re-measured on the final tree after the second session. `-m "not
slow"` **4262 passed, 127 skipped** (140 s), and the arithmetic needs the merge
in it: the first session left **4247 passed, 127 skipped** on the *pre-merge*
tree, `origin/main` then brought **3** fast tests of its own
(`test_absent_phase.py` two, `test_background_peaks.py` one — counted from the
diff, not assumed), and this session added **12** — ten in `tests/test_params.py`
and two in `tests/test_named_variables.py`. 4247 + 3 + 12 = 4262, **no new
skip**. The first session's own arithmetic stands under that: 4247/127 against
a **4227 passed, 122 skipped** pre-WP baseline on the same tree, +20 passed and
+5 skipped, being 17 named-variable tests, one `test_cross_backend` meta-test
and seven instances of its new `families_variable` row, five of which are
jax/torch methods and so *skip* on a `[dev]` venv.

The **full** selection is **4423 passed, 136 skipped** in 25:56, green, on the
merged tree at `4645793b` — one commit before the last of those twelve tests,
so it carries eleven of them, and its delta is quoted as consistent with the
fast one rather than exact (`tests/CLAUDE.md` § Quoting numbers: both ends of an
exact full-suite check cost an hour of machine time). The commit it does not
carry adds one test and widens a window to admit its source's current value,
which nothing in that run could reach — a source outside its own window would
have made `least_squares` refuse `x0`, and none did. The full run's value is not
its count anyway: `_column_identities` and `tie_window` sit in the Jacobian
dispatch and the solver's box every acceptance fit goes through, and no
acceptance number moved. **One caveat on its wall clock**: a 21-test serial
selection was started beside it by mistake, so 25:56 is not a clean figure. The
counts are unaffected, and `tests/CLAUDE.md` § Running already says why the
mistake matters.

**Merged against [1130](1130-background-reference.md)**, which was in flight in
a sibling worktree and lands first. `params/vector.py` merges clean (1130 is in
`cell_window`, this WP adds `VAR_PREFIX` and `is_variable_path` above it); the
**two conflicts are both documentation and both keep-both** — the skill's
`surprises.md`, where 1130 takes 8.21 and this takes 8.22 and both rewrite the
title (resolution: both rows in number order, "Twenty-two"), and 1118's
`### Inherited`, where each pushes a forward reference. Resolved that way,
the merged tree runs **4250 passed, 127 skipped** (279 s, its own `[dev]`
venv resolving to the merged source) against 1130 at `7a7c4262`. Checked by merging for real, not by `git merge-tree`: the
first such check said "no conflict" and was already stale by the next commit,
and a clean text merge is not a passing one either way.

### The tie-bounds hole, closed — and what TOPAS decided about it

Reassessing the shipped surface against TOPAS's `prm` left the design confirmed
in every respect but one, and the exception was worth reopening the WP for.

**Where the two codes agree.** A `prm` is a named object with its own value,
bounds and fixed flag, which is `add_variable`; a `prm` may be an equation over
other `prm`s, which is Decisions § 2's chain rule; a constrained model quantity
is written as a function of it, which is `tie`. What rietx does not have is
TOPAS's *string* equations, and Decisions § 4 says why on purpose.

**Where they differ, and it was a hole.** In TOPAS a constrained quantity is an
*equation*, not a parameter, so it carries no limits of its own and a limit is
written on the independent parameter — by hand, and visibly. rietx cannot copy
that: a `Parameter`'s `min`/`max` are schema physics (`Biso` in [0, 25], `occ`
in [0, 1.5], March `r` off its pole) and they go on existing after the parameter
is tied. But the solver's box covers the **free column**, and a tied entry is
not one — so a coefficient other than 1 carried a dependent straight past a
limit that is physics, and the first thing to notice was pydantic, inside
`apply_to_models`, after the solve, naming no path, no phase and no tie.

**The fix is the arithmetic TOPAS has the user do.** `lo ≤ Σ c_k·θ_k + d ≤ hi`
solved for one source is a **box**, which is exactly TRF's vocabulary, so
`params.vector.tie_window` inverts it, `_derive_tie_windows` intersects it over
every dependent a source drives, and `bounds()` applies it beside `cell_window`,
`strain_cap_hi` and `size_cap_hi` — for their stated reason, that these are
solver bounds for the stage and not facts about the stored parameter, so none of
them may surface through `ParameterRow` or the `.rxt` document as a claim the
caller never made. Reporting is then free and already correct: `bound_findings`
reads that same call, so a source stopped at a dependent's ceiling comes back as
`BOUND_HIT` naming the source. `MultiParameterTable` composes `ParameterTable`
and calls `table.bounds()`, so a joint fit inherits it with no second copy.

**Applied unconditionally rather than behind a freeze, and that is a
measurement, not a judgement.** Across every real structure in the repository
`ParameterTable` derives **52** ties (68 with `aniso=True`), every one
single-term, and **not one** with a finite bound on the dependent — cell
lengths, cell angles and fractional coordinates all carry `Parameter`'s default
±inf. So the window narrows a *user's* tie and provably nothing else, which is
what removed the "it changes existing fits" objection that had kept this a
decision rather than a repair.

**The several-source case is the one this WP created, and it does not close.**
Two terms make a half-space, and TRF's only vocabulary is a box, so what lands
is the **outer** box: the projection of the feasible set onto one axis, computed
from the co-sources' own declared bounds so the result cannot depend on the
order dependents are visited in. It can admit an infeasible corner; it can never
exclude a feasible point, which is the direction that matters, since the inner
box would quietly delete answers the caller asked for. An unbounded co-source
gives ±inf, which is honest. What survives the corner is now **attributable**:
`apply_to_models` catches the `ValidationError` and re-raises naming the path,
the bounds and the tie. The alternative route — `solver="lm"`, whose stated
reason to exist is linear inequalities on *functionals* of θ (the Stephens
positivity cone) — is where a future WP would express the half-space exactly,
and is not needed for the ordinary case any more.

An empty intersection is **refused, not clipped**: two declarations that cannot
both hold is a caller contradicting themselves, and this table has no
diagnostics channel to explain a repair in — the same rule that puts a CIF's
angle repair in the reader. The refusal names the **dependent**, because the
window is on the source and widening the source is the wrong move; the same
sentence the skill and the manual now give for a `BOUND_HIT` on a tie source.

**The four derived bounds are ordered, and the order was nearly wrong.** Found
in self-review, not by a test: `cell_window` treats a finite stored side as a
claim the caller made and applies its runaway default only where the side is
*infinite*, so a tie window handed to it first passes as a claim nobody wrote
and switches the guard off. Measured with the order reversed, an unsupported
phase's cell comes back at the dependent's own [0, 100] instead of the window's
[3.89877, 4.41443] — the exact failure `cell_window` exists to prevent, caused
by the thing that was meant to add safety. Applied **last** it cannot happen:
all three defaults only ever narrow, so intersecting afterwards is the tightest
of the four and leaves each of their decisions reading the stored bounds.
`test_the_tie_window_narrows_after_the_cell_window_not_before_it` fails on
purpose with the order reversed, which is where that number came from.

**Measured**, on the four-site LaB6 fixture, with the whole four-stage plan so
the fit under the bar is a converged one (Rwp 0.0458, GoF 1.12, flat residual —
checked in the plot, not only in the assertion): a dependent declaring a ceiling
of 0.33 and following at coefficient 0.5 stops its master at **0.66** and itself
at **0.33**, with `BOUND_HIT` on the master. The same fit with the window
disabled reaches 0.6697 and 0.3348 and raises — now as *"writing
phases.0.atoms.1.biso=0.334839 back to the model breaks its own bounds [0, 0.33];
it follows 0.5·phases.0.atoms.0.biso"*. The fixture's `MASTER_MAX = 12.0`
workaround is no longer load-bearing and an arm now runs at `Atom.biso`'s own
[0, 25].

**Not consulted: GSAS-II**, whose corpus paper fails to extract. It remains the
one major code whose behaviour here is unknown, and the outer-box choice above
is the place a second opinion would land.

### Findings recorded rather than fixed

**1. `add_variable(vary=True)` was overruled by a recorded free set** — found by
the tests, fixed here, and worth naming because it is a shape rather than a
typo: `_prepare_table` clears every vary flag and replays `_free_paths`, a list
written before the variable existed, so the declaration lost to a restore that
could not know about it. Any future synthetic entry declared *after* the first
stage inherits the same trap.

Pre-dates this WP and reproduces with no variable anywhere; found by the tests,
fixed here, and worth naming because it is a shape rather than a typo.

**2. A structural freeze reading `free_paths` does not see a variable driving a
phase.** `_unsupported_phase_paths` filters `table.free_paths` by
`p.startswith("phases.N.")`, and `mode_fixed_path`'s force-fix of `.atoms.`
paths is read off the same list. Tie a phase's cell or `biso` to a variable and
the only free *name* is `vars.X`, so [1301](1301-hold-unsupported-phase.md)'s
hold on a phase the data cannot see never fires and the flat direction stays
free for the stage. This is CLAUDE.md's "can this parameter move? is
`moving_paths`, never `free_paths`" one rank above where the Jacobian already
applies it — the same reason `_column_identities` exists. Not fixed here: a
correct hold needs the per-column reach off **C** that `_column_extras` computes
in `optimize/` and the table does not have, plus a decision about *what* to hold
when one variable drives several phases. Cut as
[1342](1342-a-freeze-that-reads-names.md), because 1301 is closed and a finding
with no live home is a finding nobody meets.

**3. `vars.*` rows never reach the `.rxt` document.** `gui/textdoc.py`'s
`render` emits `phases.N.` and `instrument.` blocks only, so a project with
named variables shows tied rows annotated `= vars.B` naming a parameter that
appears nowhere in the document, and the editor's "set `vars.B` instead"
refusal points at a path the reader cannot find. No data loss — variables live
on the refinement state and are never reconstructed from the doc. Not fixed
here: a new block is a grammar change and a `FORMAT_VERSION` bump, and there
is no open WP it belongs to — the next `.rxt` grammar change should carry it
rather than pay a version bump for a cosmetic row.

Findings 2 and 3 are from `/code-review medium --fix` on the finished branch;
the three it found *and* fixed are in the session entry below.

## References

- McCusker, L. B. *et al.* (1999), *J. Appl. Cryst.* **32**, 36 — §7, the
  constraint verb this generalises.
- DESIGN.md § Parameter system — the affine block, and the nonlinear DSL's
  design and rejected alternatives.
- [1070](1070-user-facing-constraints.md) — the tie verbs and the three
  authorities above. [1110](1110-agent-surface-friction.md) — items 5 and 16.

## Handover log

### 2026-09-04 (3rd session) — the agent review the last entry said had not run

The entry below closes by admitting that `/code-review medium --fix` never ran
on this branch, because the session was told not to spawn agents, and that
reading the diff by hand had found three things where the agent pass had found
nine for the first session. It has now run. It found five more, and three of
them were real bugs that a hand read had been over twice without seeing. All
three are the same shape and it is the shape this WP created: **a call that
fails part-way and leaves the state it was changing half-changed.** Letting a
user tie parameters to a variable of their own is what made a cyclic
declaration reachable, and a raise on the second target of a group used to
leave the first one tied with no history node behind it. Nothing here changes
what a converged fit returns; it changes what happens when a caller gets a
declaration wrong, which is the only thing a constraint surface is really for.

*Done* — three fixes, each its own commit, plus the record:

- **`_declare_ties` wrote the register inside the apply loop.** `set_tie`
  rebuilds the affine block and raises on a cycle, so `tie_equal` over a group
  whose second target closed one left the first in `Refinement._ties` with the
  table thrown away and no node committed — half a declaration, from a call
  that reported failure. Every `set_tie` first, `self._ties.update(specs)`
  after. The table is discarded on the raise either way, so ordering it costs
  nothing.
- **`mode_fixed_path` force-fixed a variable named `scale`.** The test was a
  bare `path.endswith(".scale")`, which matches `vars.scale`, so
  `add_variable("scale", …)` was silently held in Le Bail and Pawley for
  spelling its name like a phase parameter. Anchored at `phases.`.
- **`apply_to_models` assigned as it walked.** The bound refusal the session
  below added fires part-way through a tree of hundreds of parameters, so
  `structure` and `instrument` were left holding some of the stage's answer and
  some of the previous one, with nothing reporting the damage — and that path
  is now documented and reachable by design, not a corner. The walk collects
  `(parameter, path)`, a check pass raises before anything is assigned, then a
  write pass assigns; the `ValidationError` catch stays as a backstop for
  anything the check does not model.

- **The two it declined to fix are recorded above** (§ Findings recorded rather
  than fixed) and the correctness one is cut as
  [1342](1342-a-freeze-that-reads-names.md): `_unsupported_phase_paths` and
  `mode_fixed_path`'s callers filter `free_paths` by a `phases.N.` prefix, so a
  phase driven through a variable escapes [1301](1301-hold-unsupported-phase.md)'s
  hold entirely. That is CLAUDE.md's `moving_paths`-not-`free_paths` rule one
  rank above where the Jacobian already applies it. It needed its own WP
  because 1301 is closed, and because holding a column that reaches several
  phases is a decision, not a lookup. The `.rxt` finding stays a record: no
  data loss, and a `FORMAT_VERSION` bump for a cosmetic row should ride with
  the next grammar change rather than be spent on one.
- **No skill row, and no CLAUDE.md line.** Every fix here makes a wrong
  declaration fail cleanly where it used to half-succeed; nothing an agent
  driving rietx does changes, and "the verb behaves as documented" is not a
  rule worth a row. No physics landed, so no Part 2 equation is owed, and no
  field, `Literal` member or default was declared.

*Measured* — same venv and platform as the entries below (worktree `.venv`
from `[dev]`, macOS/darwin, numpy backend).

- **Fast selection 4262 passed, 127 skipped** — *identical* to the entry below,
  which is the check this session owed: it added no test, so passed+skipped
  must not move, and it did not.
- Full selection, on the merged tree: **4425 passed, 136 skipped**, green in
  26:06. That is the entry below's 4423 plus the two `test_docs_consistency`
  tests the first attempt caught failing, so no test count moved and none
  should have — this session added no test. `origin/main` had not moved
  since the merge at 08:35, so the branch tree *is* the merged tree and no
  second merge was needed. The first attempt at it is worth recording as a
  procedure failure rather than a result: it was launched and then edited under
  — the ROADMAP work for 1342 landed mid-run — so it came back with two
  `test_docs_consistency` failures that were green before it finished. **The
  rule is in CLAUDE.md already** (the full suite fires once, on the final
  tree); this is what ignoring it buys.
- **CI was red on the pushed tip the whole time, on two asserts this WP wrote**,
  and neither the macOS fast selection nor the macOS full one could see it —
  three green local suite runs in one morning, over a branch whose required
  checks were failing. All six jobs are green on `e9e898de`, including the
  `fast py3.12`, `fast py3.14` and `fast jax` rows that were red; the
  measurements that resized the bars are in *Gotchas*.
- **The `scale` anchoring is provably a no-op on every real path**, which is
  the evidence that no acceptance number can move: the only path literal in
  `ParameterTable._collect`/`apply_to_models` ending in `.scale` is
  `f"{base}.scale"` under `base = f"phases.{ip}"`, and `BACKGROUND_PEAK_FIELDS`
  is `("position", "height", "fwhm")`. The other two fixes are identical to
  the old code on every path that does not raise.

*Gotchas*

- **A bar measured on one platform is not a bar, and this WP wrote two of
  them.** `test_the_declared_ceiling_needs_no_workaround` asserted Rwp
  *equality* between two independently-converged arms — bit-identical on macOS,
  1 ulp apart on Linux py3.12/3.14 — while its own sibling test's docstring, in
  the same file, states the rule it broke. The other is worse in shape than in
  size: the **esd** was barred at `rel=1e-9`, and an esd is the one quantity in
  that comparison that goes through `normal_covariance`, which equilibrates and
  then cuts eigenvalues at `rcond·|λ|max`, so a near-threshold eigenvalue falls
  differently under a different column order. Good returns 4.2e-16 on macOS and
  **2.5e-9 on Linux**, against the 4.1e-9 a deliberately broken column gives:
  1.6x, where `tests/CLAUDE.md` asks for 10x. No bar there separates good from
  broken, so the esd is now a 1e-6 sanity check and the discrimination is
  carried by the refined values (1e-9 against 1.14e-8) and the integer
  iteration counts (9 against 4). No new `tests/CLAUDE.md` clause: the rule
  that catches this — measure the spread on the quantity the assertion names,
  and a margin under ~10x still smells — is already there, unapplied.
- **A hand read is not a substitute for the agent pass, and this WP now has the
  measurement.** Two sessions read this diff by hand; the second one found
  three things and wrote that the first two were "the kind an agent pass is
  good at". The pass then found three more of exactly that kind, in code both
  reads had covered. The rule already in the protocol — step 9 is not optional
  — is what to carry; the entry below is the counter-example.
- **The ROADMAP 645-line cap has no headroom, and every capped document sits
  exactly on its cap.** Adding a WP row costs a line of narrative somewhere.
  Here 1324's measurement was already restated in 1320, so the pointer paid for
  the row; a session that needs to add two rows should expect to move a
  paragraph to a milestone record rather than to trim twice.

*Next*, unchanged in order from the entry below and still not this WP's work.
**Cut the WP for issue #212**, the cross-phase linear restraint row, whose seam
is in [1325](1325-parametric-series.md)'s `### Inherited`; it has a waiting
filer. Then [1337](1337-an-authored-refusal-not-a-traceback.md), whose #246 no
longer reproduces as its text says. [1342](1342-a-freeze-that-reads-names.md)
now sits behind both: it is a silent wrong answer rather than a missing
feature, but it fires only for a caller who ties a variable to a phase the data
cannot see, and nobody has.

### 2026-09-04 (2nd session) — the TOPAS comparison closes the tie-bounds hole

Reading the shipped surface back against TOPAS's `prm` confirmed the design in
every respect but one, and the exception turned out to be a repair rather than
the open decision the morning's entry called it. In TOPAS a constrained quantity
is an *equation*, so it has no limits of its own and you write the limit on the
independent parameter, by hand. rietx cannot do that — `Biso` is [0, 25] Å²
because that is physics, and it stays [0, 25] after the parameter is tied — and
the solver only ever saw the free column, so a tie at coefficient 2 walked its
dependent to 50 and the first thing to notice was pydantic, after the solve,
naming nothing. rietx now derives the limit TOPAS has you write: a dependent
bounded at 25 and followed at coefficient 2 gives its source a ceiling of 12.5,
intersected over every dependent that source drives. A fit stopped there is
reported like any other bound. That was the last thing in this WP that could
bite someone silently.

The reason it could land at all is a measurement, and it is the part worth
carrying: **across every real structure in the repository the package derives 52
ties (68 with anisotropic ADPs), every one single-term and not one with a finite
bound**, because cells and fractional coordinates carry ±inf. So the new bound
narrows a user's tie and provably nothing else — which is what dissolved the
"but it changes existing fits" objection that had made this look like a policy
question.

*Done*, eight commits and a merge on top of the first session's six:

- **`params.vector.tie_window`** — `lo ≤ Σ c·θ + d ≤ hi` solved for one source,
  intersected by `_derive_tie_windows` and applied in `bounds()` beside
  `cell_window`, `strain_cap_hi` and `size_cap_hi`, for their stated reason:
  these are solver bounds for the stage, never facts about the stored parameter,
  so none of them may surface through `ParameterRow` or `.rxt`. Reporting came
  free — `bound_findings` reads that same call. `MultiParameterTable` calls
  `table.bounds()`, so a joint fit inherits it with no second copy.
- **The several-source case gets the outer box**, computed from the co-sources'
  declared bounds so it does not depend on visit order. It can admit an
  infeasible corner and can never exclude a feasible point, which is the
  direction that matters. What survives the corner is attributable now:
  `apply_to_models` re-raises naming the path, its bounds and the tie.
- **An empty intersection is refused, not clipped** — two declarations that
  cannot both hold, and this table has no diagnostics channel to explain a
  repair in.
- Ten unit tests in `test_params.py` (including the "every derived tie claims
  nothing" measurement, asserted rather than left to the acceptance suites) and
  two fit-level ones in `test_named_variables.py`.
- **The manual's own mixed-site example is the clearest thing this buys.**
  `occ` is declared [0, 1.5] and `occ₁ = 1 − occ₀` puts `occ₁` negative above
  `occ₀ = 1`, so `using/concepts.md`'s flagship tie now runs against [0, 1] and
  nobody wrote it. The bounds paragraph therefore sits under
  {ref}`constraining-parameters`, where a reader meets ties, rather than only
  under named variables; the several-source caveat stays with the variables,
  since that is where several sources arise. Skill § 8.22 is rewritten from the
  hole to the repair, and the `BOUND_HIT` row of `references/diagnostics.md`
  gains the cause, because that row is the one an agent meets
  programmatically.
- **A window widens to admit the value its source is at**, which is the last
  thing the handover found and the one that was nearly a regression. A window
  says where a source may *go*; `commit` writes a stage's answer back through
  `decode` and rebuilds, so a stage that stops **on** a window can return an
  ulp the wrong side and leave the next stage meeting `least_squares` refusing
  `x0` as infeasible about a parameter nobody tied. Widening costs an ulp
  there and needs no tolerance. It also decides the inconsistent-state case,
  and deliberately does **not** raise: that refusal belongs to
  [1337](1337-an-authored-refusal-not-a-traceback.md) § #246, in `tie()`'s own
  voice, and the widening is the seam it replaces. Its `### Inherited` has the
  detail.
- **The review was done by reading the diff, not by `/code-review medium
  --fix`** — this session's standing instruction was not to spawn agents,
  so the pass that found nine things for the first session did not run.
  Reading found three, all fixed and now tested, and the first two are
  the kind an agent pass is good at. (1) The bound test disabled the window by
  assigning over `ParameterTable._derive_tie_windows` and `del`-ing the
  assignment, which removes the real method rather than restoring it — green
  alone, and 21 unrelated tests down under `-n auto`. (2) The four derived
  bounds **do not commute**: applying the tie window before `cell_window`
  disarmed the cell runaway guard entirely, because `cell_window` reads a finite
  side as a claim the caller made. (3) The window had to widen to admit its
  source's value, the bullet above.

*Measured* — same venv and platform as the entry below.

- **The weak-fit trap caught both new fit tests, in a session that had just
  finished writing it down.** The bound test's first draft froze three stages
  and converged at Rwp 2.76 / GoF 67.6, and the "no workaround" test shipped a
  Biso-only plan at Rwp 2.64 / GoF 64.7 — two arms agreeing about a fit that is
  nothing like the data, which is a claim about the solver and not about the
  constraint. Both were found by opening the PNG, neither by an assertion, and
  the entry below records the identical lesson from four hours earlier. Reading
  a rule is not the same as applying it; the plots are.
- As they stand, both on the four-stage plan: the bound test at Rwp 0.0458,
  GoF 1.12, flat residual, master held at 0.66 and dependent at its declared
  0.33, `BOUND_HIT` on the master — and with the window disabled the same fit
  reaches 0.6697/0.3348 and raises. The no-workaround pair agree bit for bit at
  the schema's own [0, 25].
- The manual's mixed-site tie: `occ₀` now runs against **[0, 1]**, not `occ`'s
  declared [0, 1.5].
- Suite figures in § Acceptance: fast **4262 passed, 127 skipped**, whose
  delta needs the merge in it (4247 + 3 of main's + 12 of this session's);
  full **4423 passed, 136 skipped**, green, one commit back.

*Gotchas*

- **A new derived bound has to go last, and nothing enforces that.** The four
  are not commutative: `cell_window` branches on whether a side is infinite, so
  anything that makes a side finite before it runs disarms it. Reversing the
  order turned the cell runaway guard off completely, and only reading the diff
  found it. A fifth derived bound inherits the trap.
- **The fixture's `MASTER_MAX = 12.0` was a workaround and is now a claim.** It
  used to exist because the coefficient-2 dependent would otherwise sail to 50;
  the window puts that ceiling at 12.5 by itself, so 12.0 is now simply a
  tighter bound the caller declared. `test_the_declared_ceiling_needs_no_workaround`
  is the arm that runs at `Atom.biso`'s own [0, 25] and says so.
- **GSAS-II is still not consulted** — its corpus paper fails to extract. It is
  the one major code whose behaviour here is unknown, and the outer-box choice
  is where a second opinion would land.
- The half-space could be expressed *exactly* under `solver="lm"`, whose stated
  reason to exist is linear inequalities on functionals of θ (the Stephens
  positivity cone). Nobody has pointed that machinery at a tie bound. It is no
  longer needed for the ordinary case, which is why it is a note and not a task.

*Next*, in order. **Cut the WP for issue #212** — the cross-phase linear
restraint row, whose seam is in [1325](1325-parametric-series.md)'s
`### Inherited`; unchanged from the entry below.
Then [1337](1337-an-authored-refusal-not-a-traceback.md), which this session
moved: its #246 no longer reproduces as its text says (the write-back refuses
at declaration now, naming the coordinate, the value, the bound and the tie),
and the computation its task 4 asks for — reaching a DOF target's coordinates —
is written and running, so what is left there is the refusal's *voice* and the
atom label. Its `### Inherited` says so with the measured output. The two are
independent; #212 has a waiting filer and 1337 does not.

### 2026-09-04 (1st session) — named variables ship, and the bar caught a silent FD column

You can now name a quantity and constrain parameters to it, instead of
nominating one of them as the master: `ref.add_variable("B_metal", 0.7, min=0,
max=25)` gives `vars.B_metal`, an ordinary dot-path that the parameter listing
shows, `set_vary("vars.*")` frees, a fit refines and reports an esd for, and
that survives a checkout. Three oxygens can now share *one displacement
parameter* rather than sharing *atom 4's*, which is what the crystallography
actually says. But the feature is not the session's result. Testing whether the
new spelling really was a renaming exposed a defect in code nobody was
suspecting: the Jacobian dispatches on a free parameter's **name**, so a
variable — a name no analytic branch was written for — silently took the
whole-model finite-difference column, while the identical constraint written the
old way took the analytic peak chain. That is a column 8.6e-7 wrong and an extra
full residual evaluation per iteration, and nothing was red, because the FD
fallback is exact-but-approximate rather than short. It is fixed by dispatching
on what a column *reaches* rather than on what it is called.

The negative results are worth as much. There is **no expression parser** and
deliberately so, with the four reasons and the case against them both written
down so nobody re-takes the decision. And the WP's own acceptance bar — "the two
spellings must be bit-identical, anything else is a bug" — turned out to be
wrong as written, which the measurement had to say rather than accommodate.

*Done*, six commits:

- **The object** (Decisions § 1). A variable is a `schemas.common.Parameter`
  with a name, appended by `ParameterTable.add_parameter` at `vars.<name>` —
  the shape a Wyckoff DOF already uses. Reusing `Parameter` rather than
  inventing a type is what makes the equivalence reachable at all: `_add` reads
  an entry's bounds *and* transform straight off one, so a variable declared
  like the parameter it replaces produces the identical `Entry`.
- **Persistence**, the genuinely new part. A Wyckoff DOF is rederived from the
  structure every build and written back through the coordinates; a variable is
  in the models nowhere, so `apply_to_models` has nothing to write it to.
  `Refinement._variables` is its model — `_declare_variables` re-declares it on
  each of the four table builds (before `_apply_ties`, since a tie may name it),
  and `_write_back` wraps all seven working-state write-backs to carry its
  refined value home. Without that second half the next build re-declares the
  variable at its *created* value and silently undoes the fit for everything
  following it. `RefinementState.variables` and a `set_variable` node kind carry
  it into the history; `SCHEMA_VERSION` 0.15 → 0.16.
- **Verbs**: `add_variable`, `remove_variable` (refuses under a dependent,
  naming it), and `tie` taking `{path: coefficient}` or pair lists with `scale`
  multiplying every term. The representation was always `Σ c·src + const`; only
  the verb was single-term.
- **The chain rule** (Decisions § 2): a tied source is accepted **iff it is a
  variable**. Measured both ways first — `_flatten` already collapses a depth-2
  chain exactly and raises on cycles, and nothing the package derives reaches
  depth 2, so the old refusal was a judgement rather than a limit.
- **`_column_identities`**, the fix above.
- Manual `{ref}`named-variables``, the `history.md` rows, and skill
  `references/surprises.md` § 8.22.

*Measured* — macOS darwin 25.5.0, worktree `.venv`, python 3.12, `[dev]` extras
(no jax/torch, so the cross-backend rows self-skip). Full numbers in
§ Acceptance; the headlines:

- Fast selection **4247 passed, 127 skipped** (263 s) against a **4227 passed,
  122 skipped** baseline on the same tree — **+20 passed and +5 skipped**, which
  is exactly the 25 tests added: 17 named-variable tests, one `test_cross_backend`
  meta-test, and seven instances of its new `families_variable` row, of which the
  five jax/torch methods **skip** on a `[dev]` venv rather than pass. Full
  selection **4410 passed, 136 skipped**, 31:31, green (+3/+5 on the 4407/131 the
  same tree gave before the review pass — the same eight tests from the other
  side). No full baseline was taken, that being CI's job, so the full figure is
  quoted as green with a delta consistent with the fast one. `pgrep` showed no
  other suite running before either.
- The variable's Jacobian column sat **8.6e-7** from the analytic one before
  the fix and is bit-identical after it, as is the residual.
- Two spellings of one constraint come out **bit-identical**: Rwp, the
  per-stage iteration counts and every refined value, with the master's esd
  within one ulp (4.2e-16). True both with one free column and with nine, so
  the variable sitting at a different index of θ costs nothing here. The test's
  `rel=1e-9` has its margin measured both ways — 4.2e-16 above, and **1.14e-8**
  below with `_column_identities` disabled, where the last stage also stops at 4
  iterations instead of 9 because the FD column convinces the solver it has
  converged.

*Gotchas*, and the first two are not this WP's to fix:

- **A tie bounds only its source** — the finding this session's second half
  then closed, so the entry below it is the one to read. As found: the solver's
  box covers the free column and a tied parameter is not one, so
  `tie(..., scale=2.0)` carried a dependent past its own `max` (measured at
  49.99999999999999 against `Atom.biso`'s ceiling of 25) and surfaced as a
  pydantic `ValidationError` inside `apply_to_models`, naming nothing, after the
  solve. Pre-existing, reproducing with no variable anywhere, and written up
  here as a decision rather than a repair — wrongly, as it turned out: the
  decision it seemed to need was already made by what the coefficients say.
- **The equivalence bar was wrong twice before it was right, and the plot said
  so first.** Draft one never freed the profile width the fixture perturbs 2×,
  so both arms converged at Rwp 0.57, GoF 13.9 — obvious in the obs/calc/diff
  PNG the standing rule requires, and invisible in an assertion that passed —
  and a solver wandering through a misfit problem put the two column orders
  1.6e-9 apart. Draft two freed `instrument.profile.*` whole, which leaves
  `profile.y` on its softplus floor and moved the *esd* disagreement to 8.7e-5:
  `normal_covariance` equilibrates then cuts eigenvalues at `rcond·|λ|max`, and
  a near-threshold one is decided differently under a different column order.
  Values agreed to 3e-9 of an esd throughout both. Freeing `w` and `x` only —
  what this pattern determines — gives the bit-identity above. **The numbers a
  bar quotes are only as good as the fit under it**, and a converged-looking
  assertion is not evidence the fit converged.
- **`multi.py` and `sequential.py` know nothing about variables.** A joint
  multi-histogram residual builds its own `MultiParameterTable`, and a series
  builds a `Refinement` per pattern; neither is wired, and neither was in
  scope. A variable is a `Refinement` surface today.
- **A synthetic entry declared after the first stage loses to the free-set
  restore.** `add_variable(vary=True)` came back held because `_prepare_table`
  clears every vary flag and replays `_free_paths`, a list written before the
  variable existed. Fixed here by appending the path there, but the shape will
  catch anything else added after a stage has run.
- `_write_back` briefly grew a `stderr=` argument mirroring
  `apply_to_models`, with no caller — the WP-1076 shape, added by this branch
  and removed in review before the PR.

*The review pass* (`/code-review medium --fix`) found nine things and is the
reason this entry is not shorter. One was serious: **a node recorded by a
refinement with a variable could not be replayed.** `refine.replay` rebuilds
the table from the structure and instrument alone and then re-declares the
node's ties, and a variable has no model field — so the table had no `vars.*`
row and the first tie naming one raised. `_declare_variables` had been wired
into the three table builds `Refinement` owns, and `replay` is a fourth, outside
the class. That is the persistence failure this WP's own Context described in
the abstract and the branch then shipped anyway, which is worth saying plainly:
knowing the shape of a bug is not the same as finding it.

Five more applied: `remove_variable` scanned only ties where the variable was a
*source*, so removing one that was itself a tie target left its own tie in the
register — and a same-named `add_variable` then silently resurrected it over the
new declaration; `history.tree._values` built a node diff from the models, so a
variable's value never appeared while its dependents did; the GUI's
`_RWP_TRANSPARENT` had no `set_variable` member; `_tie_terms` destructured a
non-pair, reading `tie(p, ["a.b", "c.d"])` as path `'a'` and coefficient `'b'`;
and the manual's composition example tied a variable it never declared (a
`no-exec` block, so no test could have caught it). Two the pass raised and left
were taken anyway: `_column_identities` naming a multi-row reach by its lowest C
row (so a variable driving a Wyckoff DOF was named `.x`, matched no structural
branch, and made the docstring's own claim false — it now takes the name from
the paths it drives *directly*), and the missing `tests/test_cross_backend.py`
row, which root CLAUDE.md requires of any new way to widen C. One was declined:
`add_variable(unit=…)` is a `Parameter` field that `help.py` renders through
`UNIT_DISPLAY` and that round-trips on the register, so it is as read as
`Atom.biso`'s and not the WP-1076 shape.

*A hole in the test matrix, found while closing it.* A config in
`test_cross_backend.CONFIGS` but absent from `CONFIG_PARAMS` collects **zero
tests and reports nothing** — `families_variable` sat inert through a green run
and was caught only by counting collected items by hand. Closed for the six
configs that file defines.

Deliberately **not** closed over the `**STATES` it merges in, and the reason
needed checking rather than asserting. Three of those — `toy_anomalous`,
`toy_roughness`, `toy_stephens` — have no row in *this* matrix, which is not the
same as being untested, and a first draft of this entry said it was. What they
actually have: all three carry a numpy bit-identity golden
(`test_backend_shim.test_numpy_path_bit_identical_to_golden`), and
`toy_stephens` and `toy_anomalous` additionally get whole-matrix jax
`jacfwd`-against-analytic agreement
(`test_backend_jax.test_jacfwd_matches_analytic_on_state`) — so their Jacobians
*are* checked against an independent implementation, just not through this file
and not with the torch arm.

**`toy_roughness` is the one to look at**, and it is a narrower finding than the
draft claimed: it has a golden and no Jacobian-agreement test anywhere, so
surface roughness is the one correction of the three whose derivative no second
opinion covers. Whether that is worth a row here or a line in
`test_backend_jax` is a question this WP found and did not answer.

*In flight beside this*: [1130](1130-background-reference.md), in a sibling
worktree and landing first. Every file merges clean except
`references/surprises.md`, where it takes 8.21 and this takes 8.22 and both
rewrite the title; the resolution is to keep both rows in order under
"Twenty-two". The merged tree was measured before that row landed: **4247
passed, 122 skipped**, green.

*Next*, and none of it is this WP's: **cut the WP for issue #212** — the
cross-phase linear restraint row, whose seam is written out in
[1325](1325-parametric-series.md)'s `### Inherited` along with why it is not a
tie. Then, if anyone wants it, the bounds decision in the first gotcha, which is
the only thing here that can bite a user silently — **taken and shipped the same
day, in the session above; this sentence stands as what was known at the
time**. [1118](1118-foreign-model-files.md)
has been told its equation boundary is settled and that #107 is a `.inp` grammar
question rather than a rietx one.

- **2026-08-21** — created, from the session that closed 1110. The Context
  block's demo is this tree's measured behaviour, not a sketch: the linear
  feature works today and what is missing is the named object, multi-term ties
  and persistence.
