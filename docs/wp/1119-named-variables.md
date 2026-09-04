# WP-1119 — named variables and equations: a `prm` of one's own

Milestone: unscheduled · Status: ✅ 2026-09-04 — named variables ship, and the
equivalence bar caught the Jacobian dispatching on a name
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
      `references/api.md` (three copies synced). No diagnostic code landed, so
      `references/diagnostics.md` is untouched.
- [x] Tests, including the equivalence bar below — which the tests
      rewrote (Acceptance, and the § Measured block under it).

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

**Suite**: `-m "not slow"` **4247 passed, 127 skipped** in the 4-5 min band
(263 s), against a **4227 passed, 122 skipped** baseline on the same tree before
this WP — **+20 passed and +5 skipped**, which is exactly the 25 tests added:
17 in `tests/test_named_variables.py`, one `test_cross_backend` meta-test, and
the seven instances of its new `families_variable` row, five of which are the
jax/torch methods and so *skip* on a `[dev]` venv rather than pass. The **full**
selection is **4410 passed, 136 skipped** in 31:31, green — +3 and +5 on the
4407/131 the same tree measured before the review pass, the same eight tests
seen from the other selection. Its value is not the count: it is the evidence
that `_column_identities` is the identity it claims to be for a model parameter,
since it sits in the dispatch every acceptance fit's Jacobian goes through and no
acceptance number moved.

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

### Two findings recorded rather than fixed

Both pre-date this WP and reproduce with no variable anywhere, so neither is
this WP's to repair; both are named because a variable is where a caller now
meets them.

1. **A tie bounds only its source.** The solver's box covers the free column, so
   a tie at a coefficient other than 1 can carry its dependent past *its own*
   `min`/`max`. `tie("…atoms.2.biso", "…atoms.0.biso", scale=2.0)` on a `Biso`
   bounded [0, 25] reaches 50 and surfaces as a pydantic `ValidationError`
   inside `apply_to_models` — not as a refusal, not as a clamp, and not naming
   the tie. `_declare_ties` checks the implied value at declaration and nothing
   checks it again. The fixture works around it with a `MASTER_MAX` whose
   comment says why, and the manual says plainly that a variable's bounds are
   the ones the solve sees. A fix would have to decide between refusing at
   declaration (which cannot know where the fit will go), narrowing the free
   column's box by the coefficients (correct, and it changes existing fits), or
   reporting a `Diagnostic` — a decision, not a repair.
2. **`add_variable(vary=True)` was overruled by a recorded free set** — found by
   the tests, fixed here, and worth naming because it is a shape rather than a
   typo: `_prepare_table` clears every vary flag and replays `_free_paths`, a
   list written before the variable existed, so the declaration lost to a
   restore that could not know about it. Any future synthetic entry declared
   *after* the first stage inherits the same trap.

## References

- McCusker, L. B. *et al.* (1999), *J. Appl. Cryst.* **32**, 36 — §7, the
  constraint verb this generalises.
- DESIGN.md § Parameter system — the affine block, and the nonlinear DSL's
  design and rejected alternatives.
- [1070](1070-user-facing-constraints.md) — the tie verbs and the three
  authorities above. [1110](1110-agent-surface-friction.md) — items 5 and 16.

## Handover log

### 2026-09-04 — named variables ship, and the bar caught a silent FD column

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

- **A tie bounds only its source.** The solver's box covers the free column and
  a tied parameter is not one, so `tie(..., scale=2.0)` can carry a dependent
  past its own `max` — measured at 49.99999999999999 against `Atom.biso`'s
  ceiling of 25 — and it surfaces as a pydantic `ValidationError` inside
  `apply_to_models`, naming no path, no tie and no phase, *after* the solve.
  Pre-existing and reproducing with no variable anywhere. A fix has to choose
  between refusing at declaration (which cannot know where the fit will go),
  narrowing the free column's box by the coefficients (correct, and it moves
  existing fits), or a `Diagnostic` — a decision, not a repair. Skill § 8.22
  carries the agent-facing half.
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
the only thing here that can bite a user silently. [1118](1118-foreign-model-files.md)
has been told its equation boundary is settled and that #107 is a `.inp` grammar
question rather than a rietx one.

- **2026-08-21** — created, from the session that closed 1110. The Context
  block's demo is this tree's measured behaviour, not a sketch: the linear
  feature works today and what is missing is the named object, multi-term ties
  and persistence.
