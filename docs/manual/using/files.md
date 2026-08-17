# Files and projects

This chapter is the map of what the package reads off disk and what it writes
back. [](data.md) is what the objects it hands you contain.

```{mermaid}
graph LR
  P["pattern file<br/><i>.xye .fxye .raw .cif …</i>"] --> RP["read_pattern"]
  C["structure<br/><i>.cif</i>"] --> SC["Structure.from_cif"]
  I["instrument profile<br/><i>.json</i>"] --> LP["load_instrument_profile"]
  RP --> REF(["refinement"])
  SC --> REF
  LP --> REF
  subgraph rex ["my_sample.rex/"]
    PJ["project.json<br/><i>settings</i>"]
    PC["the pattern file<br/><i>copied byte for byte</i>"]
    H["history.jsonl<br/><i>model state</i>"]
    LV["live/<br/><i>event streams</i>"]
    EX["exports/<br/><i>CIF, tables</i>"]
  end
  REF --> PJ
  REF --> PC
  REF --> H
  REF --> LV
  REF --> EX
```

## Pattern files

`read_pattern` opens a pattern and returns a `PatternData`, whose fields are in
[](data.md). It identifies the format from the file itself rather than from the
extension:

```python
from rietx import capabilities

caps = capabilities()
[(fmt.name, fmt.sigma) for fmt in caps.reader_formats]
[(opt.name, opt.help) for opt in caps.reader_options]
```

Ask `capabilities()` rather than trusting a list in prose. The format list went
from five to ten in two days once. `ReaderCapability.sniff` says how each format
is recognised, `ReaderCapability.sigma` says where the uncertainties come from,
and `ReaderCapability.refuses` says what the reader declines and why.

Four properties of the readers reach a caller, and each of them can change a
number you quote.

**A multi-range file holds scans, and the reader selects one.** Pass `scan=` to
choose. The ranges are never concatenated, because two ranges are usually two
weighting regimes, and joining them silently mixes them.

A pdCIF holds blocks rather than scans, and takes `block=` instead. A file with
a `_meas` block and a `_calc` block is a different pattern depending on which
you ask for. `read_pdcif` reads one directly.

**A reader may repair a file, but only where it can say that it did.** Pass a
list as `diagnostics=` and the repairs come back in it:

<!-- api-doc: no-exec — it reads a pattern file the reader supplies -->
```python
import rietx as rx

notes = []
data = rx.read_pattern("my_sample.raw", diagnostics=notes)
for note in notes:
    print(note.code, note.message)
```

**The intensities and σ need not be the file's numbers.** Vendors disagree about
whether an attenuator factor is already applied — four formats, three answers —
so the reader applies it or not by measured convention, and σ goes through the
same transformation either way. Where the scale cannot be established the reader
**withholds** σ and says so with `PATTERN_INTENSITY_SCALED`, because the Poisson
fallback is wrong by √t on a rate.

**The scanned axis is never assumed.** Most vendor files are not powder scans at
all, so a file whose axis is something other than 2θ is refused by name, and an
axis the reader cannot identify says so.

Weights follow from all this. The package uses the file's esd column when the
file has one, and Poisson σ = √max(y, 1) only as the fallback. It never
subtracts an estimated background: hold the background additively
(`BackgroundFixedPlusChebyshev`) or co-refine it under a smoothness penalty
(`BackgroundPSpline`).

## Structures from CIF

`Structure.from_cif` reads a crystal structure. It takes `phase_name=` to pick
one block from a multi-phase file, `aniso=True` to read an anisotropic
displacement loop, and the same `diagnostics=` channel:

<!-- api-doc: no-exec — it reads a CIF the reader supplies -->
```python
notes = []
structure = rx.Structure.from_cif("my_phase.cif", aniso=True, diagnostics=notes)
```

`aniso` is opt-in on purpose. Several CIFs carry an anisotropic loop, and
reading a file must not silently change which parameters a plan will free.

Two repairs happen at read, and both are recorded rather than assumed. A species
label that is not a recognised scatterer is normalised
(`CIF_SPECIES_NORMALISED`), and a cell angle that disagrees with its space group
by a small amount is snapped to the symmetry value
(`CIF_CELL_ANGLE_CORRECTED`) — a β of 90.002(3) under `P m m m` is an
experimenter quoting a refined number. Past that threshold the symbol and the
angle contradict each other, one of the two is wrong, and choosing between them
is yours: the value is left byte for byte and the read raises.

## Instrument profiles

A calibrated instrument is a file. `save_instrument_profile` writes one and
`load_instrument_profile` reads it back with every parameter `vary=False`, which
is the second half of the two-step lab workflow:

<!-- api-doc: no-exec — it refines a standard and writes a file -->
```python
result = rx.refine(standard_data, standard, instrument, plan="lab_calibrate")
rx.save_instrument_profile(ref.fitted_instrument, "cu_ka_10mm.json")

instrument = rx.load_instrument_profile("cu_ka_10mm.json")
result = rx.refine(data, structure, instrument, plan="lab_sample_refine")
```

Calibrate on a standard with its **certified cell held fixed**. That is what
decorrelates the zero shift from the sample displacement from the cell, and it
is why `lab_sample_refine` is the only plan whose size and strain numbers mean
what they say.

## The `.rex` project directory

A project is the one durable thing a session can point at. It is a
**directory**, not an archive:

```text
my_sample.rex/
    project.json        settings and the data reference
    11BM_NAC.fxye       the pattern file, byte for byte as measured
    history.jsonl       the refinement DAG, append-only
    live/               event streams for `rietx watch`
    exports/            CIFs, reflection tables, QPA tables
```

A directory because the history log's crash safety is append-only writes by one
writer. Zipping would force a rewrite on every save and lose exactly the
property that makes a JSONL log recoverable and tailable while a fit runs.

<!-- api-doc: no-exec — it creates a directory from the reader's own files -->
```python
project = rx.Project.create("my_sample.rex", pattern="my_sample.xye",
                            structure=structure, instrument=instrument)
project.fit()
project.save()

project = rx.Project.open("my_sample.rex")
```

`Project.create` builds the directory around a pattern file and a model.
`Project.open` reads one back and resumes at the history head. It re-checks
every binding on the way rather than assuming it: the pattern file is still
there, its bytes still hash to the recorded digest, this build still parses those
bytes to the recorded numbers, and the history was recorded against that same
pattern. Each of the four raises with its own message, because each has a
different cause and a different fix.

An open project holds the session as six attributes.

| Attribute | Holds |
|---|---|
| `Project.path` | the project directory |
| `Project.doc` | the `ProjectDoc`, which is `project.json` in memory |
| `Project.data` | the `PatternData` read back from the copied file |
| `Project.refinement` | the `Refinement`, positioned at the history head |
| `Project.history` | that refinement's `RefinementTree` |
| `Project.data_diagnostics` | what the reader repaired or assumed on the last read |

`Project.data_diagnostics` is held in memory and is not a `project.json` field.
The repairs are a function of the bytes, the reader and its options, and the
data reference below already records all three.

**One authority per fact.** `project.json` holds the *settings*: the selected
plan and mode, the 2θ limits, the excluded regions, and the GUI's own `ui` keys.
`history.jsonl` holds the model state, and its head *is* the working state. No
parameter value is written in both places.

**Saving is about settings, not durability.** Every verb that changes the model
commits a history node the moment it runs, so the work is on disk whether or not
anyone calls `Project.save`. What `save` persists is the half of a session that
nothing else owns.

`ProjectDoc` is that half, field by field.

| Field | Holds |
|---|---|
| `ProjectDoc.patterns` | the data references, one per pattern |
| `ProjectDoc.plan` | the plan the next run will use, as a `PlanSpec` |
| `ProjectDoc.mode` | the intensity mode the next run will use |
| `ProjectDoc.two_theta_limits` | the range the next run will fit |
| `ProjectDoc.excluded_regions` | 2θ regions masked out of the residual |
| `ProjectDoc.indexing` | the next indexing run's controls |
| `ProjectDoc.history_file` | the log's filename inside the directory |
| `ProjectDoc.format_version` | the version of the `.rex` format |
| `ProjectDoc.package_version` | the version of rietx that wrote it |
| `ProjectDoc.created_utc`, `ProjectDoc.updated_utc` | when it was created, and last saved |
| `ProjectDoc.ui` | keys a front end persists, untyped |

The three settings after the plan are what `fit` and `run_stage` will be
*called* with. A history node records a mode and limits too, and that is a
different fact: the node says what a past run used, the document says what the
next one will use. Before the first run there is no node to ask.

`ProjectDoc.patterns` is a list because stacking several patterns into one joint
residual is a later milestone's work. A project holds one today, and
`Project.open` refuses a document carrying more rather than opening the first
and looking like it worked.

`ProjectDoc.ui` is untyped deliberately. A front end owns those keys, and the
container only stores them, so a layout change is not a schema change.

The pattern is copied verbatim rather than re-serialised, because the bytes are
the contract: the reader takes σ from the file's own column and never overrides
it. `Project.data_ref` returns the `DataRef` that makes those bytes trustworthy
on re-open. It carries `DataRef.sha256` of the file, `DataRef.fingerprint` of
the *parsed* arrays, and `DataRef.reader` with `DataRef.options` — the reader
call itself is part of the reference, because a pdCIF is a different pattern
depending on the block. Agreeing bytes with a disagreeing fingerprint mean the
reader changed, not that the project is corrupt.

Four more fields say what the pattern is: `DataRef.filename` names it inside the
directory, `DataRef.n_points` and `DataRef.two_theta_range` describe it, and
`DataRef.has_sigma` records whether σ was measured or fell back to Poisson. That
last one is a correctness property of every fit in the project and is invisible
once the data are read, which is why it is written down.

`Project.set_excluded_regions` records regions to leave out of the fit. They
live in the document rather than in a history node because they are protocol
that is in neither the file nor the model: a node cannot say what was excluded
when it ran. `Project.fitted_mask` is the one authority for which channels the
next run fits. An inverted or empty interval is refused rather than reordered.

The two settings compose. On the 11-BM pattern of [](quickstart.md), limits of
2–24° leave 22 003 of 59 498 channels in the residual, and excluding 7.4–7.6°
as well leaves 21 803.

`Project.exports_dir` and `Project.live_dir` are where the last two directories
live, and `Project.parameters`, `Project.fit` and `Project.run_stage` are the
session verbs, with the same meaning they have on `Refinement`.

## The history log

`history.jsonl` is an append-only record of the refinement DAG, one JSON object
per line. `RefinementTree.save` and `RefinementTree.load` are the file
interface, `RefinementTree.records` is what gets written, and
`RefinementTree.summary` prints the tree. [](history.md) is the DAG itself: what
a node holds, and the verbs that restore, fork and merge one.

A node stores **state, not curves**. A node is about 10 kB; embedding the
calculated pattern would make it 1.24 MB. Le Bail extracted intensities are the
exception, because they live outside the parameter vector and are
path-dependent, so they are serialized per node.

The tree branches. A stage adds a node under the head, a model edit adds one
too, and `Refinement.checkout` moves the head back so the next fit forks
instead of continuing:

```{mermaid}
graph TD
  root["root<br/>initial model"] --> n1["fit: lebail<br/>Rwp 0.113"]
  n1 --> n2["edit: add CaF₂ phase"]
  n2 --> n3["fit: rietveld<br/>Rwp 0.093"]
  n1 --> n4["fit: rietveld<br/>no impurity<br/>Rwp 0.141"]
```

`RefinementTree.to_mermaid` prints that diagram for a real tree, in the same
syntax, so you can paste it into any markdown that renders mermaid:

<!-- api-doc: no-exec — it needs a refinement that has run -->
```python
print(ref.history.to_mermaid())
```

## Exports

Three writers turn a result into a file someone else can read:

| Call | Writes |
|---|---|
| `write_refinement_cif` | the refined structure and fit as a CIF |
| `write_reflection_table` | one row per reflection: hkl, d, 2θ, intensity |
| `write_qpa_table` | the quantitative phase analysis |

The CIF is the one a journal asks for, so it carries more than the coordinates.
Per phase it writes the agreement indices of
[](results.md) — `_refine_ls_R_I_factor` (R_B), `_refine_ls_R_factor_all` (R_F)
and `_refine_ls_number_reflns` — and the geometry as `_geom_bond_`,
`_geom_contact_` and `_geom_angle` loops with esds in su notation. Each
`_geom_*_site_symmetry_*` code indexes a `_space_group_symop_` loop written
into the same block, because a code that pointed at whatever order the reader's
own library generated would name a different atom. The loops list each bond
once, unlike `GeometryTable`, whose audience is a chemist counting neighbours
rather than a parser. Take `structure` from `Refinement.fitted_structure`, which
is where the refined values and their esds are.

`viz.html.write_html` writes the interactive plotly page, and
`RefinementResult.plot` writes the static figure. Both need the `viz` extra.

:::{admonition} For agents
:class: agent
`Capabilities.project_format_version` versions the `.rex` directory, and
`Capabilities.textdoc_format_version` versions `.rxt`, the line-oriented text
rendering of a project that the GUI edits. Both move independently of the
package version. See [](agents.md).
:::
