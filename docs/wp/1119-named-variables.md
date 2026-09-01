# WP-1119 — named variables and equations: a `prm` of one's own

Milestone: unscheduled · Status: ⬜
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

### Inherited

- **2026-09-01, from [1118](1118-foreign-model-files.md): the TOPAS `.inp`
  reader merged (PR #98), and it resolves a `.inp`'s symbols without being an
  expression evaluator — which is the boundary this WP has to draw.**
  `io/projects/topas.py` carries module-level `symbol_table` and private
  `_resolve` / `_arith` (none of them a package export):
  enough arithmetic to read a value a file states through a named symbol, and
  deliberately no more. Nothing of it is exported, so nothing here has to keep
  it working — but do not redeclare it before deciding whether this WP's named
  variable is what it should have been resolving into.
  The live question 1118 parked **here**: seven archive files open a phase
  with the macro form `STR(R-3)` / `STR(######, "#name#")`, which the reader's
  line-based split cannot see, so it refuses such a file by name rather than
  reading it (issue #107 — the refusal landed with PR #98, reading it did
  not). Whether the fix is a special case or a general macro pass is 1118's
  registry-shape
  task — but a general pass borders this WP's equation scope, and 1118's file
  says explicitly that the boundary is decided **here, not twice**.

### The cross-phase case: a known stoichiometry (issue #212)

Requested by a user and filed as **issue #212**, and folded in here because its
common case is *linear in the phase scales* and therefore already inside this
WP's competence rather than needing an expression language.

**The need.** A specimen's overall stoichiometry is often known independently,
and there is no way to tell the package. Worked example from a supported-catalyst
reduction series in which only oxygen leaves, so the elemental ratio
**Cu/(Ca+Al)** is conserved at its as-prepared value throughout. Diffraction
cannot resolve how the unexported mass divides between two of the phases —
moving one of them by 17 wt% costs 0.2–0.5 pp of Rwp, inside the noise floor —
but stoichiometry decides it outright: nominal **1.935**, one candidate
partition **2.115**, the other **1.266**.

**Why it is linear, which is the whole reason it belongs here.** Moles of element
E ∝ Σ_p S_p·V_p·n_{E,p}, and the (ZM)_p cancels. So `Cu/(Ca+Al) = r` is

```
Σ_p a_p·S_p = 0     with     a_p = V_p·(n_Cu,p − r·(n_Ca,p + n_Al,p))
```

— constant coefficients over the phase scales, needing no expression parser and
no new storage. `element_counts` is already computed in `phase_zmv`
(`optimize/qpa.py`). This is the **multi-term tie** of missing-item 2 above,
reaching across phases instead of within one.

**Two things it needs that this WP does not currently give it**, and the second
is a genuine scope question for the maintainer rather than a task:

1. **Cross-phase reach.** `phase.restraints` cannot host a row spanning phases,
   so a cross-phase relation needs a `Structure`-level list beside
   `resolve_phase_restraints`. The row layout (`model/rows.py`) and the
   statistics-exclusion convention need no change.
2. **A soft form, which this WP's Non-goals currently exclude.** A hard tie is
   the wrong instrument here: real phase weights genuinely change — in this very
   specimen a mixed Ca–Cu–O phase forms and later disappears — so a hard
   constraint would hide chemistry. What the case wants is a **restraint with an
   honest σ that reports its own tension**, and this WP explicitly fences
   restraints out. Recorded rather than resolved: either this WP's scope widens
   to carry the soft form of a linear cross-phase relation, or that half becomes
   a sibling WP and only the *hard* multi-term cross-phase tie lands here. **The
   maintainer's call, and it should be made before either half is built.**

`summarise_restraints` and a restraint-tension code already exist, so the
reporting half is largely in place; the natural trigger for a series is a
**coherent run** of high tension across consecutive patterns rather than a single
outlier.

**What not to do, from the issue's own reasoning.** A composition-aware restraint
that knows about elements is the wrong first move, because its coefficients
depend on refined occupancies: done honestly it must chain derivatives through
them, done lazily it freezes them and becomes a confident wrong constraint. And a
series-level "pool" or "tie" is wrong twice over — it cannot express a ratio, and
it blurs the boundary the package draws between `sequential` (chained independent
fits) and `multi` (one joint residual).

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

## Tasks

- [ ] Decide the object: what a variable *is* on the table (a synthetic entry
      via `add_parameter`, under what path spelling), what `parameters()` shows
      for it, and how a caller names it in a tie.
- [ ] Persistence: `RefinementState`, the history node, the project round trip,
      and the contract bump with its comment.
- [ ] Verbs: declare and remove a variable; multi-term ties, which the
      representation already holds.
- [ ] Take the chain decision — keep the one-level refusal or flatten — and
      record the reason either way.
- [ ] An expression string for the linear subset, **if it survives the design**:
      a parser is where a wrong answer looks right, and the method calls already
      work.
- [ ] **Take the cross-phase decision** (issue #212): whether the soft form of a
      linear cross-phase relation belongs in this WP or in a sibling, and record
      the reason. Blocks the two tasks below.
- [ ] The cross-phase multi-term tie itself — a `Structure`-level list beside
      `resolve_phase_restraints`, with the stoichiometry coefficients built from
      `element_counts` in `phase_zmv`, and a test that a conserved elemental
      ratio holds through a series in which a phase appears and disappears.
- [ ] The manual: the reference sections `using/constraints.md` signposts, and a
      row in `AGENT_PROTOCOL.md` if a diagnostic code lands.
- [ ] Tests, including the equivalence bar below.

## Acceptance

The example that started it, driven through a real fit, with the equivalence bar
this milestone asks for:

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

- A fit whose Bisos follow one named variable at coefficients 1, 2 and 1 + 0.5
  is **bit-identical** to the same constraint expressed with today's dot-path
  ties — same Rwp, same refined values, same esds. The variable is a renaming,
  so anything else is a bug.
- The parameter count drops by exactly the number of dependents.
- The variable survives save, open and a history checkout, and a checkout
  restores the parameter *count* (the `RefinementState.ties` rule).
- A variable whose dependent becomes symmetry-tied after a model edit is
  reported and dropped, not silently overwritten.

## References

- McCusker, L. B. *et al.* (1999), *J. Appl. Cryst.* **32**, 36 — §7, the
  constraint verb this generalises.
- DESIGN.md § Parameter system — the affine block, and the nonlinear DSL's
  design and rejected alternatives.
- [1070](1070-user-facing-constraints.md) — the tie verbs and the three
  authorities above. [1110](1110-agent-surface-friction.md) — items 5 and 16.

## Handover log

### 2026-09-02 — the cross-phase stoichiometry case folded in

A reader now knows why a user's known overall stoichiometry — the thing that
issue #212 asks for — is not a separate feature but this WP's multi-term tie
reaching across phases: a conserved elemental ratio is **linear in the phase scales**
because the (ZM)_p cancels, so it needs constant coefficients and no expression
parser. The worked case is a reduction series where diffraction cannot split two
phases at all (17 wt% costs 0.2–0.5 pp of Rwp, inside the noise) while
stoichiometry decides it outright (nominal 1.935 against candidates 2.115 and
1.266).

*Done:* the Context now carries the case, its algebra and the two things it needs
beyond today's verbs; two tasks added. *Gotchas:* the case wants a **soft**
restraint with an honest σ, because real phase weights change and a hard
constraint would hide chemistry — and this WP's Non-goals currently fence
restraints out, so that half is a scope question, not a task. *Next:* the
maintainer takes the hard-versus-soft decision before either half is built.

- **2026-08-21** — created, from the session that closed 1110. The Context
  block's demo is this tree's measured behaviour, not a sketch: the linear
  feature works today and what is missing is the named object, multi-term ties
  and persistence.
