# Calling rietx from a program

Two calls carry the whole integration surface. `capabilities()` says what this
build can do; `agent.refine_json` does it.

:::{admonition} For agents
:class: agent
This chapter is the machine-facing half of the package, and every shape in it
was chosen for a caller that branches on a field rather than one that reads a
sentence. You can read all of it from a REPL, and `capabilities()` is the
fastest way to answer "did my `jax` extra take?", but that is not what it is
for.
:::

## `refine_json`: one call, five tasks

`agent.refine_json` takes a dict and returns a dict. It never raises and never
returns a traceback:

```python
from rietx import agent

envelope = agent.refine_json({"task": "capabilities-probe-is-not-a-task"})
envelope["ok"], envelope["error"]["code"]
```

Success is `{"ok": true, …}` with **exactly one** of `result`, `series`,
`indexing` or `suggestion` set, so a consumer branches on the arm that arrived.

| `task` | Does | Answers in |
|---|---|---|
| `refine` | fits one pattern | `result` |
| `refine_multi` | fits N patterns as one joint residual | `result` |
| `refine_sequential` | chains N patterns by warm start | `series` |
| `index` | determines a unit cell from peaks or a pattern | `indexing` |
| `suggest` | ranks held parameters by predicted Δχ², no solve, no mutation | `suggestion` |

The four arms are separate because they are different *shapes*. For indexing the
shape is the rule: the serialized answer carries no `cell` key, because a powder
pattern does not measure one cell. It measures a ranked set of candidates, and a
singleton would be a confident guess.

## The request

A request is plain JSON. The five request types are the **schema of that dict**:
they declare the key names, the types and the defaults, and nothing asks you to
construct one. Their fields are the wire contract, which is why they are named
here field by field.

| `task` | Type |
|---|---|
| `refine` | `RefineRequest` |
| `refine_multi` | `MultiRefineRequest` |
| `refine_sequential` | `SequentialRefineRequest` |
| `index` | `IndexRequest` |
| `suggest` | `SuggestRequest` |

The union is **discriminated on `task`**, so a validation failure names one
branch's fields rather than five branches' worth:

```python
from rietx import agent

sorted(agent.request_schema()["discriminator"]["mapping"])
```

A tag outside that mapping comes back as one `INVALID_REQUEST` detail reading
`Input tag 'diagnose' found using 'task' does not match any of the expected
tags`, and a request with no `task` key at all reads `Unable to extract tag
using discriminator 'task'`.

Every request schema is strict: **unknown keys are errors, not ignored**. That
is how a task learns it was sent a setting it does not have, rather than
silently ignoring it.

### `task="refine"`

One pattern, one staged fit. The library equivalent is `Refinement.fit`, and
[](refining.md) is where the settings below are argued for.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `RefineRequest.task` | `"refine"` | required | the discriminator |
| `RefineRequest.structure` | `Structure` | required | the starting model |
| `RefineRequest.instrument` | `Instrument` | required | wavelength, profile, geometry, background |
| `RefineRequest.pattern` | `PatternData` | required | the data, carrying its own σ when the file had one |
| `RefineRequest.mode` | `"rietveld"`, `"lebail"`, `"pawley"` | `"rietveld"` | how peak intensities are decided |
| `RefineRequest.two_theta_limits` | [float, float] | null | the fitted range |
| `RefineRequest.backend` | str | `"numpy"` | Jacobian backend |
| `RefineRequest.solver` | str | `"trf"` | least-squares driver |
| `RefineRequest.plan` | str or `PlanSpec` | `"mccusker_default"` | a preset name, or an explicit stage list |
| `RefineRequest.history_path` | str | null | JSONL file for the history DAG. Without it the call keeps no history and `RefinementResult.node_id` and `RefinementResult.tree_id` are null |
| `RefineRequest.include_report` | bool | true | attach `AgentSuccess.report` |
| `RefineRequest.report_trajectory` | bool | false | attach `AgentSuccess.trajectory` |

`RefineRequest.include_report` is the master switch for report **content**:
with it false, `RefineRequest.report_trajectory` is overridden and the envelope
carries neither. A caller who declines the report is never handed one a rung at
a time.

### `task="refine_multi"`

N patterns as one stacked residual, sharing the parameters that describe the
specimen. This is not a series; [](series.md) is the chapter that separates the
two, and it owns `SharingSpec`.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `MultiRefineRequest.task` | `"refine_multi"` | required | the discriminator |
| `MultiRefineRequest.structure` | `Structure` | required | one model for every histogram |
| `MultiRefineRequest.instruments` | list[`Instrument`] | required | one per pattern, at least one |
| `MultiRefineRequest.patterns` | list[`PatternData`] | required | at least one |
| `MultiRefineRequest.mode` | `"rietveld"` | `"rietveld"` | Rietveld only, and the type says so |
| `MultiRefineRequest.two_theta_limits` | [float, float], or one per histogram | null | the fitted range |
| `MultiRefineRequest.weights` | list[float] | null | inter-histogram residual weights; the default is unit, so each point's own esd governs |
| `MultiRefineRequest.sharing` | `SharingSpec` | null | overrides the default per-histogram rule |
| `MultiRefineRequest.backend` | str | `"numpy"` | Jacobian backend |
| `MultiRefineRequest.solver` | str | `"trf"` | least-squares driver |
| `MultiRefineRequest.plan` | str or `PlanSpec` | `"mccusker_default"` | a preset name, or an explicit stage list |

Two lengths are checked before anything runs: one instrument per pattern, and
one weight per pattern if weights are given. Both come back as
`INVALID_REQUEST`.

This task runs **without the history DAG**, because a fingerprint over several
patterns is a seam the package has not cut yet. `RefinementResult.node_id` and
`RefinementResult.tree_id` are therefore null by declaration rather than by
accident. There is no `AgentSuccess.report` either: a report is per histogram,
so the python route builds one from `RefinementResult.for_histogram`.

### `task="refine_sequential"`

N separate refinements chained by a warm start. [](series.md) owns the
behaviour; these are the keys.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `SequentialRefineRequest.task` | `"refine_sequential"` | required | the discriminator |
| `SequentialRefineRequest.structure` | `Structure` | required | the starting model for the first pattern |
| `SequentialRefineRequest.instrument` | `Instrument` | required | one instrument for the whole series |
| `SequentialRefineRequest.patterns` | list[`PatternData`] | required | the series, in order |
| `SequentialRefineRequest.mode` | `"rietveld"`, `"lebail"`, `"pawley"` | `"rietveld"` | as for a single fit |
| `SequentialRefineRequest.two_theta_limits` | [float, float] | null | applied to every pattern |
| `SequentialRefineRequest.x` | list[float] | null | the series coordinate; the pattern index is the axis without one |
| `SequentialRefineRequest.x_label` | str | `"index"` | what that coordinate is called |
| `SequentialRefineRequest.labels` | list[str] | null | a name per pattern, used in messages and history filenames |
| `SequentialRefineRequest.refit` | `"single"`, `"stages"` | `"single"` | collapse the plan into one stage for a warm pattern, or re-walk it |
| `SequentialRefineRequest.direction` | `"forward"`, `"backward"`, `"both"` | `"forward"` | which way the chain runs |
| `SequentialRefineRequest.carry` | list[str] | `["*"]` | dot-path globs that cross a pattern boundary |
| `SequentialRefineRequest.reseed` | bool | true | let a rejected warm start fall back to the cold models |
| `SequentialRefineRequest.history_dir` | str | null | directory for the per-pattern trees, `<dir>/<label>.jsonl` |
| `SequentialRefineRequest.backend` | str | `"numpy"` | Jacobian backend |
| `SequentialRefineRequest.solver` | str | `"trf"` | least-squares driver |
| `SequentialRefineRequest.plan` | str or `PlanSpec` | `"mccusker_default"` | run on the first pattern and on any reseeded one |

`SequentialRefineRequest.x` and `SequentialRefineRequest.labels` are checked for
length against the patterns before the run starts.

A series has **one history tree per pattern**, so the ids are on each
`SeriesEntry` and there is no run-level pair.

:::{warning}
`direction="both"` runs the chain each way and reports the parameters the two
passes disagree on, but the JSON envelope carries only the **forward**
`SeriesResult`. The backward chain is reachable as
`SequentialRefinement.backward_` on the python object, and
`refine_sequential` — which is what this task calls — discards it. Through this
surface you get the `SEQUENTIAL_PATH_DEPENDENT` diagnostics and not the second
trajectory.
:::

### `task="index"`

Not a refinement, so it carries no backend, solver or plan. [](indexing.md) is
the chapter; this is the request.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `IndexRequest.task` | `"index"` | required | the discriminator |
| `IndexRequest.peaks` | `PeakList` | null | a fitted peak list, or positions from a publication |
| `IndexRequest.pattern` | `PatternData` | null | the profile; supplying it is what enables whole-profile validation |
| `IndexRequest.instrument` | `Instrument` | null | required with a pattern, and what makes the cell's geometric systematic quantifiable |
| `IndexRequest.engines` | list[str] | null | which search engines to run; the default is all of them |
| `IndexRequest.search` | `SearchSpecSpec` | its own defaults | bounds, budgets and the search preset |
| `IndexRequest.two_theta_limits` | [float, float] | null | the range peaks are picked and validated over |
| `IndexRequest.validate_candidates` | bool | true | run the Le Bail validation when a pattern is available |
| `IndexRequest.check_top` | int | null | how many candidates get the expensive per-candidate checks |

A request with neither `IndexRequest.peaks` nor a
`IndexRequest.pattern` + `IndexRequest.instrument` pair is refused before any
search runs, with the reason in the detail's message: a pattern cannot be
indexed without the wavelength and profile its instrument declares.

Keep `IndexRequest.engines` at its default. `"high"` confidence *means* every
engine that ran agreed on the lattice, so naming a subset narrows what the
answer is able to say rather than what it costs.

### `task="suggest"`

Which parameter to free next, from one Jacobian evaluation. No least squares, no
history, no mutation, which is what makes it safe to call between fits.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `SuggestRequest.task` | `"suggest"` | required | the discriminator |
| `SuggestRequest.structure` | `Structure` | required | the model at the state to be judged |
| `SuggestRequest.instrument` | `Instrument` | required | the same |
| `SuggestRequest.pattern` | `PatternData` | required | the data |
| `SuggestRequest.mode` | `"rietveld"`, `"lebail"`, `"pawley"` | `"rietveld"` | as for a fit |
| `SuggestRequest.two_theta_limits` | [float, float] | null | the evaluated range |
| `SuggestRequest.backend` | str | `"numpy"` | Jacobian backend |
| `SuggestRequest.top_n` | int | 5 | ranked groups to return |
| `SuggestRequest.include` | str or list[str] | `"*"` | dot-path globs a candidate must match, with a stage's `turn_on` semantics |
| `SuggestRequest.exclude` | list[str] | `[]` | dot-path globs to leave out |

The models' own `vary` flags are the currently-free set, so this task asks "what
next" about the state you send it.

It is the only task with a backend and **no** solver and no plan. Sending either
is a named error rather than an ignored knob: `solver` comes back as
`Extra inputs are not permitted` at `where: "solver"`.

## The response

The envelope is one of two types, and `ok` says which: `AgentSuccess` or
`AgentFailure`.

### Success

| Field | Type | Meaning |
|---|---|---|
| `AgentSuccess.ok` | `true` | always, and it is the field to branch on first |
| `AgentSuccess.result` | `RefinementResult` | set by `refine` and `refine_multi` |
| `AgentSuccess.series` | `SeriesResult` | set by `refine_sequential` |
| `AgentSuccess.indexing` | `IndexingResult` | set by `index` |
| `AgentSuccess.suggestion` | `SuggestionResult` | set by `suggest` |
| `AgentSuccess.report` | `FitReport` | the three-layer report, for `refine` only |
| `AgentSuccess.trajectory` | list[`StageReport`] | that report at every stage boundary, in the order the stages ran |
| `AgentSuccess.evidence` | `IndexingEvidence` | the indexing answer projected for a consumer that reasons |

**Every field is serialized, including the arms that are null.** A `refine`
answer has `series`, `indexing`, `suggestion` and `evidence` all present and
all `null`, so branch on which arm is non-null, never on which key exists.

`AgentSuccess.report` and `AgentSuccess.evidence` are **companions**: each rides
beside an arm rather than being one, because each is the same answer projected
for a different reader. `AgentSuccess.evidence` is set exactly when
`AgentSuccess.indexing` is, and is computed from it at serialization time, so
the two cannot disagree.

`AgentSuccess.trajectory` is the same `FitReport` contract projected onto the
states the run passed through, one `StageReport` per completed stage. Ask for
it on a run you will read whole: **a converged report is routinely the least
informative one in the run.** A plan absorbs an error it cannot free into
whatever it can, then arrives converged with nothing to suggest, while its own
first stage named the cause. Each rung's actions are the ones the plan you ran
will *not* fix.

It is off by default, and the default was measured rather than assumed: two eval
rounds found that consumers handed the rungs unasked decided no better at more
calls. `Refinement.fit(stage_reports=True)` is the library spelling of the same
switch, off for the same reason plus one more, that `fit` is called in loops.

What it costs, measured on a 4200-point synthetic LaB₆ pattern through a
five-stage default plan: the fit takes 2.8× the wall clock (0.29 s to 0.80 s)
and the envelope grows 3.6 kB, about 3 % of the report's own 114 kB. It changes
no number the fit produces — Rwp came back bit-identical with the rungs on and
off.

### Failure

| Field | Type | Meaning |
|---|---|---|
| `AgentFailure.ok` | `false` | always |
| `AgentFailure.error` | `AgentError` | the whole of what went wrong |

`AgentError` is the grammar of a `Diagnostic`, so a consumer keeps one
vocabulary for "the fit warns" and "the call failed".

| Field | Type | Meaning |
|---|---|---|
| `AgentError.code` | one of three strings | what to branch on |
| `AgentError.message` | str | what happened, for a person |
| `AgentError.suggestion` | str | what to do about it, when the package knows |
| `AgentError.details` | list[`AgentErrorDetail`] | one entry per field-level failure |

| `AgentError.code` | Means |
|---|---|
| `INVALID_REQUEST` | the request did not validate. `AgentError.details` names the fields |
| `BACKEND_UNAVAILABLE` | a valid backend name whose optional dependency is not installed here |
| `REFINEMENT_FAILED` | the request was valid and the engine raised |

| Field | Type | Meaning |
|---|---|---|
| `AgentErrorDetail.where` | str | a dot-path into the request as you wrote it |
| `AgentErrorDetail.message` | str | what is wrong with that field |
| `AgentErrorDetail.type` | str | pydantic's machine-readable tag, e.g. `missing`, `extra_forbidden`, `value_error` |

`AgentErrorDetail.where` is a path into **your** dict. The tagged union prefixes
every location with the branch it tried, and that prefix is stripped before you
see it, so a missing space group reads `structure.phases` and not the same path
with the task tag in front of it.

**An empty `AgentErrorDetail.where` is a whole-request error, not a field one.**
Both a bad discriminator and a cross-field rule land there, because neither is
about one key: a request naming no peaks and no pattern is one detail with an
empty `where` and the reason in its message.

```python
from rietx import agent

envelope = agent.refine_json({"task": "index"})
envelope["error"]["code"], envelope["error"]["details"][0]["where"]
```

:::{warning}
**Ask `capabilities()` before asking for a backend.** Measured on a build
without the `jax` extra, `{"task": "refine", …, "backend": "jax"}` comes back
`REFINEMENT_FAILED` rather than `BACKEND_UNAVAILABLE`. The install hint is in
`AgentError.message`, but `AgentError.suggestion` is the generic one for an
engine that raised, and a consumer branching on `AgentError.code` cannot tell a
missing dependency from a model the physics refused.
`BackendCapability.available` answers the question directly and before the
call, which is what it is for.
:::

## Registering rietx as a tool

`agent.tool_definition` returns a ready-to-register definition — `name`,
`description`, `input_schema`. `agent.request_schema` and
`agent.response_schema` are the JSON Schemas alone.

```python
from rietx import agent

definition = agent.tool_definition()
sorted(definition)
agent.request_schema()["$defs"] is not None
```

**The vocabularies inside that schema are quoted from the live registries.** The
backend, solver, plan and indexing-engine names come from the same tuples the
package dispatches on, and a meta-test fails when a registered member is missing
from the exported schema. A third engine cannot ship invisible.

:::{admonition} For agents
:class: agent
That `description` is the first thing a calling agent reads about this package,
before any schema, any result and any part of this manual. It therefore carries
the two rules agents get wrong most often: read the diagnostics before the
statistics, and read the whole trajectory rather than only the final report.

It points at the operating protocol two ways, and both resolve for someone who
only ran `pip install`: the hosted copy at `DOCS_URL/AGENT_PROTOCOL.md`, and an
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
  `Capabilities.anodes` — the dispatch vocabularies. A `BackendCapability`
  carries `BackendCapability.name`, whether its optional dependency imports
  *here*, whether it is experimental, what to install, and
  `BackendCapability.dtype`, the precision it computes at. An
  `AnodeCapability` carries `AnodeCapability.name`, its own
  `AnodeCapability.wavelengths`, `AnodeCapability.kbeta` for the contamination
  check, and `AnodeCapability.kalpha1_only`, which is true for the `CuKa1`-style
  entries where an incident-side monochromator has left one line rather than
  two.
- **`Capabilities.plans`** — each `PlanCapability` with `PlanCapability.title`,
  `PlanCapability.description`, `PlanCapability.modes` and
  `PlanCapability.when_to_use`, so a program can offer the choice in its own UI
  without hard-coding a list. `PLAN_INFO` is the same table in the library.
- **`Capabilities.reader_formats`** — every pattern format `read_pattern` opens.
  Each `ReaderCapability` carries `ReaderCapability.name` and
  `ReaderCapability.title` for a file dialogue, `ReaderCapability.extensions`,
  `ReaderCapability.sniff` (how the file is recognised), `ReaderCapability.sigma`
  (where the uncertainties come from, which differs per vendor),
  `ReaderCapability.options` (the keywords *this* format honours) and
  `ReaderCapability.refuses` (what it declines, and why). A format with a
  `ReaderCapability.refuses` string is one the build recognises **in order to
  decline** — "we know what this is and it is the wrong kind of file" is a
  different answer from "we cannot open this".
- **`Capabilities.reader_options`** — the reader keyword vocabulary itself,
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
- **`Capabilities.features`** — feature flags, each *derived* from the thing it
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
| `Capabilities.schema_version` | the pydantic schemas — the model, the pattern, the result |
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
