# Calling rietx from a program

Two calls carry the whole integration surface. `capabilities()` says what this
build can do; `Refinement.fit` does it. There is no third thing to learn, and
no wire format between you and the package: the objects are the API and their
JSON dumps are the wire.

:::{admonition} For agents
:class: agent
This chapter is the machine-facing half of the package, and every shape in it
was chosen for a caller that branches on a field rather than one that reads a
sentence. You can read all of it from a REPL, and `capabilities()` is the
fastest way to answer "did my `jax` extra take?", but that is not what it is
for.
:::

## The Python API is the surface

Up to version 1.2 there was a second one, an `agent` module holding a single
JSON call that took a request dict and returned an `{"ok": …}` envelope, plus
its exported JSON Schemas. All of it was retired
in 1.3 because it was measured and not used. Across four traced rounds — 235
instrumented interpreter starts, and 5 430 tool calls in one contributor's
bundle — every agent that had the choice drove the package directly:
`read_pattern`, `Structure`, `Refinement.fit`, `refine_sequential`,
`build_report`. It also could not serve the case it was built for: its request
carried patterns inline, so one lab pattern is 11 k tokens and a 68-pattern
series is about 754 k of them in a single call.

What replaces it is what those agents already did:

<!-- api-doc: no-exec — it refines a pattern the reader supplies -->
```python
import rietx as rx

data = rx.read_pattern("my_sample.xye")
ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan="mccusker_default")
print(ref.summary())
```

Three differences from the envelope are worth stating plainly, because they are
the whole of the upgrade:

- **A failure raises.** Where the envelope answered `{"ok": false, "error":
  {"code": …}}`, the call raises — `ValueError` for a model or a plan the
  package refuses, `NoPhasesError` for a structure with nothing to refine,
  `RuntimeError` from the engine. Catch what you would have branched on.
- **The answer is an object.** `RefinementResult` is what the `result` arm
  carried, `SeriesResult` what `series` carried, `IndexingResult` what
  `indexing` carried, and `SuggestionResult` what `suggestion` carried. None of
  them changed.
- **The report is a separate call.** `Refinement.report` builds the
  `FitReport` for the fit just run, and `Refinement.stage_reports_` holds the
  report at every stage boundary when `Refinement.fit` was asked for them with
  `stage_reports=True`. A converged report is routinely the least informative
  one in a run, so ask for the rungs on a run you will actually read.

## The answer as JSON

Every answer type is a pydantic model, so serialising one is one call and needs
nothing from this package on the other side:

```python
from rietx import RefinementResult

"statistics" in RefinementResult.model_fields
```

`model_dump(mode="json")` is the form to store and to send: non-finite floats
serialise as the strings `"Infinity"`, `"-Infinity"` and `"NaN"`, which is what
lets a parameter bound of ±inf survive a round-trip ([](compatibility.md)).
`model_validate` reads one back.

:::{admonition} For agents
:class: agent
`Refinement.summary` answers "is this done, and why" in one string, which is
the question a result view is for. Read the diagnostics before the statistics,
and prefer the trajectory over the final report — a plan absorbs an error it
cannot free into whatever it can, converges, and suggests nothing, while its
own first stage named the cause.
:::

## Wrapping rietx in a tool call

Nothing here is a tool definition, and the package no longer ships one. If you
are exposing refinement to a tool-calling model, wrap the Python API yourself
and give your tool **path** arguments — a pattern file, a CIF, a project
directory — rather than inline payloads. A dedicated tool earns its place when
it gates, renders, audits or parallelises something; a refinement driven by an
agent that already has a shell needs none of those, and the pattern arrays are
what make the inline form expensive.

:::{admonition} For agents
:class: agent
The operating protocol resolves two ways, and both work for someone who only
ran `pip install`: the hosted copy at `DOCS_URL/AGENT_PROTOCOL.md`, and an
offline copy inside the wheel at
`importlib.resources.files("rietx.data") / "AGENT_PROTOCOL.md"` for a sandbox
with no network. In a checkout of the repository the wheel copy is absent and
`docs/AGENT_PROTOCOL.md` is the file itself.
:::

## `capabilities()`

One call answers what this build supports, and every arm is quoted from a live
registry rather than typed:

```python
from rietx import capabilities

caps = capabilities()
[plan.name for plan in caps.plans]
[engine.name for engine in caps.indexing_engines]
sorted(caps.features)
```

- **`Capabilities.backends`**, `Capabilities.solvers`, `Capabilities.modes`,
  `Capabilities.anodes`, the dispatch vocabularies. A `BackendCapability`
  carries `BackendCapability.name`, whether its optional dependency imports
  *here*, whether it is experimental, what to install, and
  `BackendCapability.dtype`, the precision it computes at. An
  `AnodeCapability` carries `AnodeCapability.name`, its own
  `AnodeCapability.wavelengths`, `AnodeCapability.kbeta` for the contamination
  check, and `AnodeCapability.kalpha1_only`, which is true for the `CuKa1`-style
  entries where an incident-side monochromator has left one line rather than
  two.
- **`Capabilities.radiations`**, the source kinds `Instrument.source`
  discriminates on. Read this *before* `Capabilities.anodes`, which is a
  sub-vocabulary of the X-ray entry and says nothing about the others — a
  program reading the anodes alone would conclude this build does X-rays only.
  Each `RadiationCapability` carries `RadiationCapability.kind`, the
  discriminator to write, `RadiationCapability.title` and
  `RadiationCapability.scatterer`, the one-line statement of what does the
  scattering and therefore whether the amplitude falls off with Q. The other
  four say how the *shape* of the source differs, which is what decides
  whether a field exists to set at all:
  `RadiationCapability.anomalous_dispersion`,
  `RadiationCapability.max_emission_lines` (`None` for unbounded, 1 for a
  source whose spectrum is one wavelength and can be nothing else),
  `RadiationCapability.polarization_refinable`, and
  `RadiationCapability.harmonic_contamination` — whether that radiation accepts
  declared λ/n monochromator harmonics ([](data.md)). All four are derived from
  the classes rather than declared, so each flips by itself when its feature
  lands; the last reads the same `harmonics_supported` attribute the schema's
  own refusal reads, so it cannot claim a support the validator denies.
- **`Capabilities.plans`**, each `PlanCapability` with `PlanCapability.title`,
  `PlanCapability.description`, `PlanCapability.modes` and
  `PlanCapability.when_to_use`, so a program can offer the choice in its own UI
  without hard-coding a list. `PLAN_INFO` is the same table in the library.
- **`Capabilities.reader_formats`**, every pattern format `read_pattern` opens.
  Each `ReaderCapability` carries `ReaderCapability.name` and
  `ReaderCapability.title` for a file dialogue, `ReaderCapability.extensions`,
  `ReaderCapability.sniff` (how the file is recognised), `ReaderCapability.sigma`
  (where the uncertainties come from, which differs per vendor),
  `ReaderCapability.options` (the keywords *this* format honours) and
  `ReaderCapability.refuses` (what it declines, and why). A format with a
  `ReaderCapability.refuses` string is one the build recognises **in order to
  decline**: "we know what this is and it is the wrong kind of file" is a
  different answer from "we cannot open this".
- **`Capabilities.reader_options`**, the reader keyword vocabulary itself,
  build-wide rather than per format, because `scan` means the same thing in
  every format that takes it. Each `ReaderOptionCapability` gives
  `ReaderOptionCapability.name`, `ReaderOptionCapability.kind` (`"str"` or
  `"int"`, so a form knows which control to draw) and
  `ReaderOptionCapability.help`.
- **`Capabilities.indexing_engines`** and `Capabilities.search_presets`, with
  `SearchPresetCapability.typical_seconds` and
  `SearchPresetCapability.total_budget_seconds`. An indexing search is budgeted,
  and a caller that has to promise a response time reads it here. Beside them
  are the search's own vocabularies: `Capabilities.crystal_systems` in the order
  the scheduler enters them, which is decreasing symmetry and therefore
  increasing cost; `Capabilities.centrings`, the Bravais letters each system
  admits, as a map; and `Capabilities.shift_templates`, the systematic-shift
  models the screen can fit.
- **`Capabilities.features`**, feature flags, each *derived* from the thing it
  reports (a schema field's presence, a top-level export's existence) rather
  than written as a literal `true`. A flag flips by itself when its feature
  lands.

**Quote this call rather than transcribing its contents.** The reader-format
list went from five to ten in two days once, and a table in prose would have
been wrong by the following week.

## Versioned contracts

`Capabilities` reports six version strings. They are separate because they move
independently:

| Field | Versions |
|---|---|
| `Capabilities.schema_version` | the pydantic schemas: the model, the pattern, the result |
| `Capabilities.report_thresholds_version` | the `FitReport` gates and their thresholds |
| `Capabilities.event_schema_version` | the streaming event ladder |
| `Capabilities.project_format_version` | the `.rex` project directory |
| `Capabilities.textdoc_format_version` | the `.rxt` text document |
| `Capabilities.indexing_thresholds_version` | the indexing gates, caveat and grade vocabularies |

`Capabilities.package_version` is the seventh string, and the only one that
moves on every release. Store the contract versions alongside any result you store: a
threshold compared across two `report_thresholds_version` values compares two
different questions.

## Further reading: the agent protocol

This chapter describes the surface.
[`docs/AGENT_PROTOCOL.md`](https://github.com/yue-here/rietx/blob/main/docs/AGENT_PROTOCOL.md)
covers the half an integrator cannot derive from a schema: the turn-on order,
the degeneracies to memorise, what to check before believing a number, how to
read an abstention, and the measured findings that should change what a calling
agent does.
