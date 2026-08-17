# The parameter table

A fit does not refine the objects of [](data.md) directly. It refines a flat
vector, and the parameter table is what stands between the two: it walks the
`Structure` and `Instrument` trees, gives every `Parameter` it finds a
dot-path, and records what may be varied and what must follow something else.
{eq}`par-affine` is the mapping, `p_phys = C·p_free + d`.

This chapter is that table as a caller sees it: how to address a row, how to
read one, and how to change one. [](concepts.md) is the next question, which
rows to free and in what order. The table itself takes no view on that.

Two properties make it worth looking at before you refine anything. It contains
rows you cannot free, and it says why for each one, so "why will this
parameter not move" is answerable without running a fit. And it is rebuilt from
the models at every stage boundary, so a row is never stale with respect to the
objects it came from.

## A dot-path names one scalar

A path is dot-separated, has no brackets, and starts at one of two roots.
Numbers in the middle are list indices, in the order the model stores them.

| Path | Names |
|---|---|
| `phases.0.cell.a` | the first phase's *a* axis |
| `phases.0.atoms.2.biso` | the third atom's isotropic displacement |
| `phases.0.atoms.2.dof.0` | that atom's first site-symmetry direction |
| `phases.0.microstrain.dof.4` | the fifth Stephens coefficient of phase 0 |
| `instrument.profile.w` | the Gaussian constant width term |
| `instrument.background.c2` | the third background coefficient |
| `instrument.geometry.sample_displacement` | the specimen-height error |
| `instrument.source.lines.*.weight` | an emission line's relative weight |

Paths are matched with `fnmatch`, so `*` and `?` work and a set of parameters
is named by one glob: `phases.*.cell.*` is every cell parameter of every phase,
`phases.*.atoms.*.biso` every isotropic displacement. This is one grammar used
in three places, which is why it is worth learning once: `Refinement.set_vary`
takes globs, a stage's `turn_on` list takes globs, and `Refinement.untie` takes
globs.

Brackets are the one trap. `fnmatch` reads `[0]` as a character class rather
than an index, so `phases[0].cell.a` matches nothing and raises no error. There
are no brackets anywhere in the scheme; the index is just another dotted
component.

Some paths exist only when the model declares the block they belong to.
`phases.0.microstrain.dof.*` appears once the phase carries a `StephensStrain`,
`phases.0.atoms.2.adp.*` once that atom carries an `AnisoU`, and
`instrument.geometry.capillary_offset_along_beam` only on a capillary geometry.
A glob over an absent block matches nothing, which is why the broad globs in
the shipped plans are safe on any model.

## Reading the table

`Refinement.parameters` returns the whole table as a list of `ParameterRow`, in
the order the free vector uses.

```python
import rietx as rx

lab6 = rx.Structure(phases=[rx.Phase(
    name="LaB6",
    space_group="P m -3 m",
    cell=rx.Cell.cubic(4.15689, vary=True),
    atoms=[
        rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0)),
        rx.Atom(label="B", species="B", x=rx.Parameter(value=0.19964),
                y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5)),
    ],
)])
ref = rx.Refinement(lab6, rx.Instrument.debye_scherrer(wavelength=0.4139),
                    history=False)

rows = ref.parameters()
assert len(rows) == 41                                  # every scalar, held ones included
assert sum(row.refinable for row in rows) == 25         # what set_vary could free

held = {row.path: row.held_because for row in rows if not row.refinable}
assert held["phases.0.cell.b"] == "tied: = 1·phases.0.cell.a"
assert held["phases.0.cell.alpha"] == "structurally fixed by symmetry or by the model"
```

Forty-one rows for two atoms and a default instrument, of which twenty-five
could be freed: most of a table is parameters you will never touch, and the
listing is the cheapest way to see what is there.

| Field | Type | Meaning |
|---|---|---|
| `ParameterRow.path` | str | the dot-path |
| `ParameterRow.value` | float | the current physical value |
| `ParameterRow.vary` | bool | whether it is free in the next fit |
| `ParameterRow.lo`, `ParameterRow.hi` | float | inclusive physical bounds, ±inf when unbounded |
| `ParameterRow.transform` | str | the reparameterisation, {eq}`par-softplus` |
| `ParameterRow.tie` | `TieSpec` or None | what this value follows, if anything |
| `ParameterRow.locked` | bool | structurally fixed, `set_vary` can never free it |
| `ParameterRow.mode_fixed` | bool | force-fixed by the intensity mode in force |
| `ParameterRow.esd` | float or None | the uncertainty from the most recent fit |

The first eight fields mirror the optimiser's own entry type field for field,
and a test asserts that, so a new field cannot be added to the table without
appearing here. `esd` and `mode_fixed` are the deliberate additions. `esd` is a
property of a *completed* fit rather than of a parameter, and merging it in is
what lets one listing answer both "what is this worth" and "how well is it
known".

`ParameterRow.refinable` and `ParameterRow.held_because` are derived. The first
is the single predicate a front end should grey a row by; the second is the
sentence to show beside it.

## The three reasons a row is held

They are distinguishable on purpose, because the fix differs.

| Reason | What it means | Can you release it |
|---|---|---|
| `locked` | structurally fixed: a symmetry-fixed cell angle, a fully fixed special position, the first emission line's weight, `biso` on a site that declares an anisotropic tensor | no |
| `tie` | an affine function of other rows, so the freedom lives in its sources | only if it is your own tie |
| `mode_fixed` | refinable in principle, but the current intensity mode force-fixes it | switch back to `rietveld` |

`ParameterRow.refinable` is false if any of the three holds. The three counts
do not add up to the number of held rows, and should not: on the LaB6 table
above, asking for the Le Bail listing marks thirteen rows `mode_fixed` while
the refinable count only falls from 25 to 19, because seven of those thirteen
were already locked or tied. Read `refinable` for the decision and the three
flags only to explain it.

```python
import rietx as rx

ref = rx.Refinement(rx.Structure(phases=[rx.Phase(
    name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.15689),
    atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                   y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))],
)]), rx.Instrument.debye_scherrer(wavelength=0.4139), history=False)

rietveld = sum(row.refinable for row in ref.parameters())
lebail = sum(row.refinable for row in ref.parameters(mode="lebail"))
assert lebail < rietveld
```

`Refinement.parameters` takes a `mode` argument because the mode the object
carries is the one the last stage *ran* in, which before the first run is the
`rietveld` default. A caller that knows what the next run will use has to be
able to say so. Without it, a Le Bail project's atom rows come back looking
editable, which is the one thing `mode_fixed` exists to prevent: a Le Bail
phase must carry a dummy atom to exist at all, and its `biso` is not something
to offer anyone.

A tie is data, not just a flag. `TieSpec` is the serializable form of
`value = Σ c·source + k`.

| Field | Meaning |
|---|---|
| `TieSpec.terms` | the (path, coefficient) pairs |
| `TieSpec.const` | the additive constant k |
| `TieSpec.user` | true for a tie you declared, false for one the symmetry created |
| `TieSpec.sources` | the paths this value follows, which is what to edit instead |
| `TieSpec.describe` | the right-hand side as text, e.g. `1·phases.0.cell.a` |

`TieSpec.user` is the field that matters when you are deciding what to offer a
user. Both populations hold a row the same way and `held_because` reads the
same for either, but a symmetry tie is rederived from the space group every
time the table is built and nothing can remove it, while a tie you declared
lives in the history and `Refinement.untie` takes it back. [](concepts.md) has
the verbs that create them.

The two populations also read differently. A cell tie is an identity row,
`1·phases.0.cell.a`. A coordinate tie carries the starting position in its
constant: on the LaB6 table above, `phases.0.atoms.1.x` describes itself as
`0.19964 + 1·phases.0.atoms.1.dof.0`, because a coordinate degree of freedom is
a *displacement* from the stored coordinate ({eq}`par-coord`). ADP and Stephens
degrees of freedom are absolute instead, which is what enforces their site
symmetry exactly.

## What the optimiser actually varies

`ParameterRow.value`, `lo` and `hi` are physical. The solver does not see them.
A parameter with a `transform` is reparameterised first, and its bounds are
mapped into the internal variable, which is monotonic so the interval survives.

| Physical bounds | Transform | Internal bounds |
|---|---|---|
| [4.0, 4.3] | `identity` | [4.0, 4.3] |
| [0.0, inf] | `softplus` | [−inf, inf] |
| [1e-6, 1.0] | `softplus` | [−13.82, 0.5413] |
| [0.0, 1.0] | `logit` | [−inf, 27.63] |

The pattern in the second and fourth rows is the one to know: a lower bound at
or below 1e-12 becomes −inf, so the optimiser runs unconstrained instead of
pressing a hard zero. That is why a width or a scale can descend smoothly to
its off state rather than stalling against a wall, and why [](data.md)'s
warning about reaching exactly zero is a consequence rather than a bug.

The transform is also in the esd chain. {eq}`est-cov` gives the uncertainty of
the *internal* variable; multiplying by dp/du at the solution is what makes it
physical, and only then is it propagated through `C` to the rows that follow it.

## Editing the table

Two verbs, and both record a history node, because freeing a parameter and
setting one are refinement moves rather than bookkeeping.

`Refinement.set_vary` takes a glob or a list of them and returns the paths it
actually changed. The return value is the useful part: a locked or tied entry
never matches, however broad the glob, so the list of hits is the honest
account of what your glob did.

<!-- api-doc: no-exec — it edits a table built from the reader's own model -->
```python
ref.set_vary("phases.*.cell.*")          # -> ['phases.0.cell.a'] on a cubic phase
ref.set_vary("phases.*.cell.alpha")      # -> [] : locked by symmetry
ref.set_vary("phases.*.atoms.*.x")       # -> [] : tied to a site-symmetry DOF
ref.set_vary("instrument.profile.u", vary=False)
```

A cubic cell returns one path from a glob that names six. Nothing went wrong;
five of the six are held, and the one hit is the whole of the freedom. Paths the
current mode force-fixes are the exception to the rule: `set_vary` will free
them, and a stage then drops them again, reporting them as `mode_fixed`.

`Refinement.set_values` takes a dict of paths to values. It is plural because a
table is edited a set of cells at a time, and one node per keystroke would bury
the log.

It raises rather than guessing, and the four refusals have four different
fixes:

| Refusal | Message | The fix |
|---|---|---|
| unknown path | `unknown parameter path(s): [...]` | a typo |
| locked | `is structurally fixed ... and cannot be set` | nothing to set; the model owns it |
| tied | `follows 'phases.0.cell.a' as an affine tie; set that instead` | set the source |
| out of bounds | `lies outside its bounds [0.0, 1.5]` | a value the bounded solver could not start from |

Dependents follow their sources. Setting `phases.0.cell.a` on a cubic phase
moves `b` and `c` with it, and the change reaches the objects:
`Refinement.structure` and `Refinement.instrument` are the refinement's own deep
copies of what you passed in, and they are what the table writes back to.
`Refinement.fitted_structure`
and `Refinement.fitted_instrument` return those same objects. The two pairs of
names differ in what they claim about *when* you are reading, not in what they
return.

Setting a value also invalidates the fitted curve and its statistics, which
described the previous values.

:::{note}
Both verbs change the working state whether or not a history tree exists, but
the node is recorded only once it does. The tree is created on the first `fit`
or `run_stage`, because it is pinned to its pattern by a fingerprint and no
pattern has been seen before then. A `set_vary` before the first fit is
therefore not in the log, while the one after it is.
:::

## What a fit reports back

A result carries its own view of the table. `RefinementResult.parameters` is a
list of `RefinedParameter`, and the membership rule is the contract: a row
appears if the entry **varied or was tied**. A fixed parameter is absent, not
present with `vary=False`.

| Field | Meaning |
|---|---|
| `RefinedParameter.path` | the dot-path |
| `RefinedParameter.value` | the value the fit ended at |
| `RefinedParameter.stderr` | the esd, or None if it could not be estimated |
| `RefinedParameter.vary` | false on the tied rows, which is how to spot them |

The type carries two more fields, `initial` and `at_bound`, which this chapter
does not document and which are **provisional**: the refinement path writes
neither, and both are being reconsidered rather than described as they stand
([1076](https://github.com/yue-here/rietx/blob/main/docs/wp/1076-result-row-honesty.md)).
Read a parameter's bound state from the `BOUND_HIT` diagnostic, which is where
that fact is actually computed and reported. The rule behind it is that a
parameter sitting on its bound is not a measurement, so do not quote one.

The two views differ in size, and the difference is the point. A single-phase
NAC refinement over 2 to 24° measured here gives 72 rows from
`Refinement.parameters` and 32 from `RefinementResult.parameters`: 14 free, 18
tied, and 40 fixed rows that the result omits entirely. Use the result to
report a fit and the table to decide what to do next.

Esds cross between them. `Refinement.parameters` merges the most recent fit's
esds onto `ParameterRow.esd`, so one listing carries both the value and its
uncertainty. A tied row gets one too: the free parameters' covariance is
propagated through `C` as σ² = diag(C·Cov·Cᵀ), so an identity tie reports
exactly its source's number. In that NAC fit `phases.0.cell.b` and `.c` both
come back at 6.27e-05, which is `a`'s esd. The tied coordinate rows carry none, because a
row is given an esd only when at least one of its sources was free, and that
plan did not free the coordinate degrees of freedom. `None` means the
uncertainty is unavailable rather than zero.

For a single value, `RefinementResult.parameter` takes a path and returns the
one row, which is less work than filtering the list.

:::{admonition} For agents
:class: agent
`Refinement.parameters` is the surface to work the table from without running
anything: every row, each held one saying why, and the esds from the last fit
merged in. `ParameterRow.refinable` is one predicate to gate an offer on, and
`TieSpec.user` separates a tie you may release from one you may not, without
having to try it and read the error.
[`docs/AGENT_PROTOCOL.md`](https://github.com/yue-here/rietx/blob/main/docs/AGENT_PROTOCOL.md)
§2 has the order to free them in.
:::
