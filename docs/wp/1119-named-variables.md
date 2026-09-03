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

## Tasks

- [ ] Decide the object: what a variable *is* on the table (a synthetic entry
      via `add_parameter`, under what path spelling), what `parameters()` shows
      for it, and how a caller names it in a tie.
- [ ] Persistence: `RefinementState`, the history node, the project round trip,
      and the contract bump with its comment.
- [ ] Verbs: declare and remove a variable; multi-term ties, which the
      representation already holds.
- [ ] Take the #212 decision — the cross-phase linear **restraint** row is
      either this WP's first deliverable or its own WP — and say which in the
      handover either way, because 1325 and the issue's filer both wait on it.
- [ ] Take the chain decision — keep the one-level refusal or flatten — and
      record the reason either way.
- [ ] An expression string for the linear subset, **if it survives the design**:
      a parser is where a wrong answer looks right, and the method calls already
      work.
- [ ] The manual: the reference sections `using/constraints.md` signposts, and a
      row in the agent skill's `references/diagnostics.md` (all three copies)
      if a diagnostic code lands — `AGENT_PROTOCOL.md` has been a redirect
      stub since WP-1304.
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

- **2026-08-21** — created, from the session that closed 1110. The Context
  block's demo is this tree's measured behaviour, not a sketch: the linear
  feature works today and what is missing is the named object, multi-term ties
  and persistence.
