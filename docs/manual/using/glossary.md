# Glossary

Every refinable parameter, peak flag, stage setting, reader option and instrument
preset field this package uses, with its unit, default and a range to
sanity-check a refined number against.

The entries are generated from `rietx.help`, which is the single place any of
this is written down. The GUI puts the same sentence beside the same control,
so a description here and a tooltip there cannot disagree.

Every parameter is held (`vary=False`) until a stage or a `set_vary` call frees
it, so no entry repeats that. Where an entry says a parameter is locked or tied,
that is structural and `set_vary` will refuse it: see
{ref}`constraining-parameters`.

## Looking one up in code

`help_for` takes a parameter dot-path and returns the entry whose family claims
it, matching with `fnmatch` exactly as a stage's `turn_on` globs do.

```python
import rietx as rx

entry = rx.help_for("phases.0.atoms.2.biso")
print(entry.title)
print(entry.unit, entry.default)
```

```text
Isotropic displacement parameter
Å² 0.5
```

A path outside the parameter vocabulary returns `None` rather than a guess.

`help_key_for` returns the family glob itself rather than the entry, which is
what `Refinement.parameters()` puts on every row as `ParameterRow.help_key`. A
row carries the key and not the entry because an entry describes a family, so
inlining one repeats the same paragraph once per atom.

```python
import rietx as rx

print(rx.help_key_for("phases.0.atoms.3.biso"))
print(rx.help_key_for("phases.0.atoms.3.nonsense"))
```

```text
phases.*.atoms.*.biso
None
```

`help_registry` returns the whole corpus as JSON-able data, which is what the
GUI's `GET /api/help` serves. Its keys are `parameters`, `peak_flags`,
`peak_diagnostics`, `peak_origins`, `stage_fields`, `reader_options`,
`instrument_fields`, `search_fields` and `plans`. Each object in `parameters`
lists every glob that reaches it, so a `help_key` looks up there.

```python
import rietx as rx

registry = rx.help_registry()
print(sorted(registry))
print(registry["peak_flags"]["axial_tail"]["title"])
```

```text
['instrument_fields', 'parameters', 'peak_diagnostics', 'peak_flags', 'peak_origins', 'plans', 'reader_options', 'search_fields', 'stage_fields']
Possibly a stronger line's axial tail
```

## Entry fields

Each entry is a `HelpEntry` with seven fields.

`HelpEntry.title`
: The name in words.

`HelpEntry.description`
: What the quantity is, and what moves it.

`HelpEntry.unit`
: The unit, or `None` where the quantity is dimensionless. Pinned against the
  schema's own `Parameter.unit` by `tests/test_help.py`.

`HelpEntry.default`
: The value the schema starts from, as a string, or `None` where there is none.
  A cell edge has no default because it arrives with the structure. Also pinned
  against the schema.

`HelpEntry.typical`
: A range to check a refined number against. It is guidance, not a bound, and
  nothing in the package reads it.

`HelpEntry.anchor`
: The manual heading that carries the equation, checked against the built HTML.

`HelpEntry.label`
: The short form a chip carries where the name would not read: `at bound` for
  `position_at_bound`. Only the `peak_flags` and `peak_origins` arms carry one,
  and every entry there must; `None` elsewhere, where no chip is drawn.

## Limitations

`typical` and `label` are the two authored fields: no computation in the package
reads either (the GUI reads `label` to letter a chip). The ranges come from
McCusker et al. (1999) {cite}`mccusker1999` and from this repository's own
reference datasets, and a specimen outside one is not thereby wrong.

The corpus describes parameters, not strategy. Which parameter to free next is
{doc}`refining`; what a diagnostic code means for a whole refinement is
{doc}`the agent skill <skill>`.

```{include} ../_generated/glossary-body.md
```
