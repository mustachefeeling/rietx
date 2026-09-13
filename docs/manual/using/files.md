# Files and projects

This chapter is the map of what the package reads off disk and what it writes
back. [](data.md) is what the objects it hands you contain.

```{mermaid}
graph LR
  P["pattern file<br/><i>.xye .fxye .raw .cif …</i>"] --> RP["read_pattern"]
  C["structure<br/><i>.cif</i>"] --> SC["Structure.from_cif"]
  I["instrument profile<br/><i>.json</i>"] --> LP["load_instrument_profile"]
  G["GSAS-I instrument file<br/><i>.prm</i>"] --> GP["read_gsas_prm"]
  M["another program's refinement<br/><i>.inp .pcr</i>"] --> PM["read_project_model"]
  RP --> REF(["refinement"])
  SC --> REF
  LP --> REF
  GP --> REF
  PM --> REF
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
whether an attenuator factor is already applied (four formats, three answers),
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
(`CIF_CELL_ANGLE_CORRECTED`): a β of 90.002(3) under `P m m m` is an
experimenter quoting a refined number. Past that threshold the symbol and the
angle contradict each other, one of the two is wrong, and choosing between them
is yours: the value is left byte for byte and the read raises.

A third note is a report rather than a repair. A site sitting within 1e-4 of a
special position without being on it — what a file quoting five decimals
produces — has its orbit expanded *at* that position, so its multiplicity is the
special one, and `SITE_SNAPPED_TO_SPECIAL_POSITION` names the site, the shift
and the multiplicity. The stored coordinates are unchanged and the fit is
unaffected. What the multiplicity decides is how many atoms the site puts in the
cell, and so ZMV and every weight fraction; compare it against the file's own
`_atom_site_symmetry_multiplicity`.

Building a phase by hand rather than from a file has one more way to go quiet.
A bare Hermann-Mauguin symbol resolves to the first setting the tables hold, and
40 symbols hold more than one — the `:1`/`:2` origin choices and the
rhombohedral `:H`/`:R` axes. Site multiplicities differ between settings, so
spinel's origin-2 coordinates under a bare `F d -3 m` build Mg₂AlO₄ where
MgAl₂O₄ was meant, with Rwp unmoved. `SPACE_GROUP_SETTING_ASSUMED` quotes the
cell contents each setting implies, which is the part you can recognise:

```python
import rietx as rx

P = rx.Parameter
spinel = rx.Phase(
    name="spinel",
    space_group="F d -3 m:2",          # the setting, not just the symbol
    cell=rx.Cell.cubic(8.0806),
    atoms=[
        rx.Atom(label="Mg", species="Mg", x=P(value=0.125),
                y=P(value=0.125), z=P(value=0.125)),
        rx.Atom(label="Al", species="Al", x=P(value=0.5),
                y=P(value=0.5), z=P(value=0.5)),
        rx.Atom(label="O", species="O", x=P(value=0.2624),
                y=P(value=0.2624), z=P(value=0.2624)),
    ],
)
```

Naming the setting silences it. Files carry theirs, so a CIF or a TOPAS `.inp`
never raises it.

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

The GUI writes and reads the same file from the Model panel, with `Save
profile…` and `Load profile…`. Saving lands it in the project's `exports/`
directory. It needs a model and not a fit, unlike everything else written
there: the other exports describe a refinement result, while a profile
describes the instrument as it stands.

### Reading a GSAS-I `.prm` instrument file

`read_gsas_prm` reads a GSAS-I instrument-parameter file (Larson & Von Dreele,
*GSAS*, LAUR 86-748) — the text file an APS 11-BM mail-in ships beside its
pattern — straight into an `Instrument`, with the same `vary=False` contract
as `load_instrument_profile`:

<!-- api-doc: no-exec — needs a real .prm file on disk -->
```python
instrument = rx.read_gsas_prm("beamline.prm")
```

It reads the dominant case the format ships — one bank, `HTYPE PXCR`
(constant-wavelength X-ray), GSAS profile function 3 — converting `GU`/`GV`/
`GW` from centidegrees² and `LX`/`LY` from centidegrees into the degrees²/
degrees `ProfileTCHZ` uses. A neutron time-of-flight file (`HTYPE PNTR`) and
every other GSAS profile function are refused by name rather than
approximated, and the refusal says which reason applies to which: a
time-of-flight file puts something onto the axis that `ProfileTCHZ`'s
constant-wavelength Caglioti/TCH law cannot express, while a
constant-wavelength neutron file (`HTYPE PNCR`) states a law it *could* hold
and is refused only for want of a real fixture to pin its coefficient layout
down. A GSAS `.EXP`/`.LST` refinement output has no reader and is transcribed
by hand. A TOPAS `.inp` and a FullProf `.pcr` are whole refinements rather than
instrument files, and have their own readers — the next section.

Two things this reader **chooses** rather than reads, both on the
`diagnostics=` channel the sections above use. A `.prm` states no geometry at
all, and `HTYPE PXCR` spans Bragg-Brentano and Debye-Scherrer, so the
`Instrument` comes back `debye_scherrer` — the 11-BM capillary the corpus this
reader was built against is — and a flat-plate calibration must have its
geometry set by the caller. Doing that takes one care, because the geometry is
not only assumed: `S/L` and `H/L` (`PRCF` positions 7-8) *are* read from the
file, and they land on `geometry.axial_sl`/`geometry.axial_hl` rather than on
the profile. A replacement `Geometry` built from scratch starts at 0 for both,
which is an instrument with no axial divergence at all, so copy those two
across. That matters beyond bookkeeping: `Geometry.kind`
selects the position correction and its suggested action, and the two
geometries' absorption corrections have different *off* states. The file's
fields that the `Instrument` cannot carry are dropped at their identity value
and reported the same way, one per record that carried them:

<!-- api-doc: no-exec — needs a real .prm file on disk -->
```python
notes = []
instrument = rx.read_gsas_prm("beamline.prm", diagnostics=notes)
[(d.code, d.message) for d in notes]
# GSAS_PRM_GEOMETRY_ASSUMED — the geometry was not read from the file
# GSAS_PRM_FIELD_DROPPED    — ICONS field 5, the Kα2/Kα1 ratio, PRCF's GP …
```

Pass no list and the read is silent and identical, which is what makes the
channel opt-in rather than a behaviour change.

## Refinement files another program wrote

A TOPAS `.inp`, a FullProf `.pcr` and their kind are not patterns and not
structures. They state someone's whole refinement: the phases, the instrument,
and — the part nobody can reconstruct from a CIF plus a pattern — **which
parameters were free**. Transcribing one by hand is the failure mode this
reader exists to remove, because a mistyped coordinate stays symmetry-valid and
fails silently, so what comes out is a plausible wrong answer rather than an
error.

:::{admonition} Provisional
:class: warning
The foreign-refinement readers are under active development, so the names in
this section are documented but **not frozen**. `read_project_model`,
`identify_project_format`, `read_topas_inp`, `read_fullprof_pcr` and the
per-format models they answer with (`rietx.io.projects`) may change in a 1.x
release: the registry landed with two formats and three more queued, each of
which is evidence about its shape, and the write direction is not written at
all. A format's own model mirrors that format, so its fields move when the
reader's coverage does.
{ref}`provisional-by-declaration` has the promise in full.
:::

### Opening one

`read_project_model` takes a file and works out which program wrote it:

<!-- api-doc: no-exec — needs a real .inp or .pcr on disk -->
```python
model = rx.read_project_model("refined.inp")
model.format.name          # 'topas_inp'
model.stated.r_wp          # the run's own figure, as the file states it
structure = model.to_structure()
```

Dispatch is on **content**, never on the extension: `.inp` is written by
several unrelated programs, and claiming one by name is how a reader returns a
plausible wrong model for a finite-element deck. A file nothing here reads is
refused by a message naming what this build does open, and pointing at the
three neighbouring readers — `rx.read_pattern` for a pattern, `rx.read_gsas_prm`
for a GSAS-I instrument file, `rx.read_recipe` for a PowderLine recipe — since
those are what such a file usually turns out to be.

Call `rx.read_topas_inp` or `rx.read_fullprof_pcr` directly when you already
know what you have; `rx.identify_project_format` answers which format claims a
file without parsing it, reading only enough of the head to decide.

### What comes back

The answer is a `ProjectModel`. It names the format and hands on that format's
own model untouched, and is deliberately **not** one shape with blanks where a
file was silent: a blank reads as an answer, and a caller cannot tell "this file
carried none" from "the reader found none".

| Field | What it holds |
|---|---|
| `ProjectModel.format` | the `ProjectFormat` that claimed the file |
| `ProjectModel.path` | the file that was read |
| `ProjectModel.stated` | what the file stated, in that format's own model |
| `ProjectModel.diagnostics` | what the *read* repaired or assumed, kept whether or not you asked |
| `ProjectModel.to_structure` | build a `Structure` from it, with the file's refine flags |

`ProjectModel.to_structure` passes its keywords through to the format's own
conversion, so `dataset=` reaches a multi-dataset `.inp` and `nuclear_only=`
reaches a `.pcr` with a magnetic phase. They are not flattened into one
vocabulary: two formats' options that happened to share a name would not share
a meaning.

### What each format states

A model is *what the file said*, seeded with nothing — a value the file omitted
arrives as `None`, never as a default. The two differ because the formats do.

`read_topas_inp` returns a `TopasModel`:

| Field | What it holds |
|---|---|
| `TopasModel.path` | the file it was read from |
| `TopasModel.phases` | the phases the file states, with their sites and refine flags |
| `TopasModel.r_wp`, `TopasModel.gof` | the run's own figures, where the grammar settles which is the file's |
| `TopasModel.r_wp_all`, `TopasModel.gof_all` | every such value in file order, since a multi-dataset file states one per dataset |
| `TopasModel.n_datasets` | how many `xdd`-family blocks the file opens |
| `TopasModel.data_files` | the pattern files it points at |
| `TopasModel.emission_lines`, `TopasModel.emission_macro`, `TopasModel.anode`, `TopasModel.wavelength` | the emission profile, as stated or as a macro named it |
| `TopasModel.geometry`, `TopasModel.goniometer_radius_mm` | the diffractometer, where the file says |
| `TopasModel.background_terms` | how many background coefficients were refined |
| `TopasModel.skipped_blocks` | phase blocks that stated no name or space group, recorded whether or not a diagnostics list was passed |
| `TopasModel.coverage` | what the reader met and did not carry — below |

`read_fullprof_pcr` returns a `FullProfModel`:

| Field | What it holds |
|---|---|
| `FullProfModel.path`, `FullProfModel.title`, `FullProfModel.pcr_name` | the file, and the names it gives itself |
| `FullProfModel.phases` | every phase, nuclear and magnetic |
| `FullProfModel.nuclear_phases`, `FullProfModel.magnetic_phases` | the same, split — a magnetic phase reads but cannot build |
| `FullProfModel.chi2` | the converged figure, from the comments FullProf rewrites each cycle |
| `FullProfModel.control` | the Job/Npr/Nph control line, field by field |
| `FullProfModel.job` | which diffraction experiment the file declares |
| `FullProfModel.lambda1`, `FullProfModel.lambda2`, `FullProfModel.lambda_slot` | the wavelengths, and which slot stated them |
| `FullProfModel.zero_shift` | the zero correction, with its refine codeword decoded |
| `FullProfModel.background` | the background the file declares |
| `FullProfModel.excluded_regions`, `FullProfModel.fitted_range` | what the run fitted and what it left out |
| `FullProfModel.data_file`, `FullProfModel.pattern` | the pattern it points at |
| `FullProfModel.cycles`, `FullProfModel.refined_parameter_count`, `FullProfModel.parameter_numbers` | how the run was driven, and which codeword numbered which parameter |
| `FullProfModel.output` | the output options the file sets |

### Which formats this build reads

`rx.capabilities()` publishes the registry, so a client asks rather than
guesses:

```python
import rietx as rx

caps = rx.capabilities()
[(f.name, f.extensions, f.reports_at) for f in caps.project_formats]
```

| Field | What it holds |
|---|---|
| `Capabilities.project_formats` | one `ProjectFormatCapability` per format, in dispatch order |
| `ProjectFormatCapability.name`, `ProjectFormatCapability.title` | the registry key, and what a person calls it |
| `ProjectFormatCapability.extensions` | the conventional suffixes, which are informational and never the dispatch |
| `ProjectFormatCapability.sniff` | how the format is recognised, in words |
| `ProjectFormatCapability.carries` | what the file holds beyond a structure — read this before reading a model you have no common shape for |
| `ProjectFormatCapability.reports_at` | `"read"` or `"build"`: which call takes your `diagnostics=` list |
| `ProjectFormatCapability.refuses` | set when the build recognises a format *in order to decline* it, carrying why |

`reports_at` is a real difference and not bookkeeping. A `.inp`'s repairs — a
rewritten species spelling, a translated origin suffix — happen while parsing,
so its channel is `read_project_model(..., diagnostics=notes)`. A `.pcr`'s all
happen while codewords become a `Structure`, so its channel is
`ProjectModel.to_structure(diagnostics=notes)`. Passing a list to both collects
either without your having to know which.

You never lose the read's half by passing your list to the wrong call, though:
whatever the read reported is on `ProjectModel.diagnostics` as well, filled
list or no list. That matters more than it sounds. An empty list reads as "this
file needed no repairs", and a caller who had passed it to the other call would
believe it.

The same facts are in the registry itself, which is what the arm is built from:
`ProjectFormat.name`, `ProjectFormat.title`, `ProjectFormat.extensions`,
`ProjectFormat.sniff`, `ProjectFormat.carries`, `ProjectFormat.reports_at` and
`ProjectFormat.refuses` carry the declarations, while `ProjectFormat.matches`,
`ProjectFormat.read` and `ProjectFormat.to_structure` are the callables the
dispatch uses.

### What a reader will not guess

These formats hold constructs this package has no model for, and dropping one
changes the model rather than its presentation. So every construct the TOPAS
reader knows about is a `Feature` carrying a declared `Stance`, a keyword with
no stance fails a test rather than vanishing, and what a particular file turned
out to contain comes back as a `Coverage` of `Hit` rows:

```python
from rietx.io.projects import coverage
```

| Name | What it is |
|---|---|
| `Stance.READ` | carried into the model |
| `Stance.IGNORED` | deliberately not carried, and harmless |
| `Stance.REPORTED` | met, not carried, and named in the diagnostics |
| `Stance.REFUSED` | met, and the file is refused rather than returned half-built |
| `Feature.name`, `Feature.what`, `Feature.why` | one construct, what it is and the argument for its stance |
| `Feature.stance`, `Feature.keywords` | the stance, and the format keywords it governs |
| `Hit.feature`, `Hit.keywords`, `Hit.phases` | one construct actually met in a file, and where |
| `Coverage.reported`, `Coverage.refused`, `Coverage.partial` | the hits of each kind |
| `Coverage.summary`, `Coverage.summary_of` | those hits in a sentence |

A refused construct raises, naming the file and the line. A reported one
arrives on the diagnostics channel: the read is silent and identical without a
list, which is what makes the channel opt-in rather than a behaviour change.

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

### A project with no structure

`structure=` may be left out. What you get is a **pattern-only** project: zero
phases, for a pattern whose phase you do not know yet.

<!-- api-doc: no-exec — it creates a directory from the reader's own files -->
```python
project = rx.Project.create("unknown.rex", pattern="unknown.xye",
                            instrument=instrument)
```

Peak picking and indexing work over it, the parameter table holds the instrument
and the background, and the routes out of it both end in a phase: index the
peaks and adopt a candidate cell ([](indexing.md)), or build a Le Bail scaffold
from a space-group symbol and the cell parameters that setting leaves free
(`rietx.schemas.structure.lebail_scaffold`). In the GUI it is the third answer
to the wizard's structure step.

What it cannot do is refine. A phase reaches the pattern only through
`scale × |F|² × profile`, so with no phase there is nothing but the background
to fit — and a plan run over one *converges on the background* and reports
success. `fit`, `run_stage`, `refine_multi` and `refine_sequential` therefore
raise `NoPhasesError` before they start. `NoPhasesError.code` is the string
`NO_PHASES` on every surface: the agent envelope's fourth error code, and the
GUI's reason for a disabled Run button.

```python
import rietx as rx

print(rx.NoPhasesError.code)
```

```text
NO_PHASES
```

`Refinement.predict` still works, because evaluating the background as it stands
is not a refinement.

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

Every verb that changes a project writes into its directory as it runs, and
`Project.open` appends a line to the log before any verb is called. There is
no read-only way to open one. To look at a project without changing it, open a
copy: `rietx gui PROJECT.rex --scratch` copies the directory to a temporary
one and opens that, printing where it went ([](cli.md)). The copy is
byte-for-byte, so it opens exactly as the original does.

Each fact has one authority. `project.json` holds the *settings*: the selected
plan and mode, the 2θ limits, the excluded regions, and the GUI's own `ui` keys.
`history.jsonl` holds the model state, and its head *is* the working state. No
parameter value is written in both places.

Saving persists settings; it is not what makes the work durable. Every verb that
changes the model commits a history node the moment it runs, so the work is on
disk whether or not anyone calls `Project.save`. What `save` persists is the half of a session that
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
the *parsed* arrays, and `DataRef.reader` with `DataRef.options`. The reader
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

Each line is a `HistoryRecord`, a tagged union of the three things the log
carries. The tag is what keeps the file append-only: a reader branches on it
rather than on the file's shape, so a new line never invalidates the ones before
it.

| Field | Is | Reads as |
|---|---|---|
| `HistoryRecord.record` | `"header"`, `"node"` or `"annotation"` | the tag. Branch on this and read the matching field |
| `HistoryRecord.header` | a `TreeHeader`, on the first line only | the tree's identity and the fingerprint pinning it to one pattern |
| `HistoryRecord.node` | a `HistoryNode` | one state, appended when a stage or an edit commits |
| `HistoryRecord.annotation` | an `Annotation` | a tag or a note attached to a node afterwards, which is why it is a separate line rather than a field on the node |

The other three fields are null on any given line. A tag applied to a node that
was written an hour ago appends an annotation line; it never rewrites the node.

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
| `write_reflection_table` | one row per **(emission line, reflection)**: hkl, d, 2θ, \|F\|², intensity |
| `write_qpa_table` | the quantitative phase analysis |

[](exports.md) has the rows those last two are made of, and the same three
writers as methods on `Refinement`.

The CIF is the one a journal asks for, so it carries more than the coordinates.
Per phase it writes the agreement indices of
[](results.md) as `_refine_ls_R_I_factor` (R_B), `_refine_ls_R_factor_all` (R_F)
and `_refine_ls_number_reflns`, and the geometry as `_geom_bond_`,
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
