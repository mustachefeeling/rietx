# Calling rietx from a program

Two calls carry the whole integration surface. `capabilities()` says what this
build can do; `agent.refine_json` does it.

:::{admonition} For automated callers
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

Failure is `{"ok": false, "error": {code, message, suggestion, details}}`. That
is the grammar of a `Diagnostic`, so a consumer keeps one vocabulary for "the
fit warns" and "the call failed". Three codes, closed: `INVALID_REQUEST` (with
per-field dot-paths in `details`), `BACKEND_UNAVAILABLE` (a valid backend name
whose optional dependency is not installed here), and `REFINEMENT_FAILED`.

Two **companions** ride beside whichever arm arrived, rather than being arms
themselves:

- `evidence` — the answer projected for a reasoning consumer.
- `trajectory` — the report at every stage boundary, on by default here. **A
  converged report is routinely the least informative one in the run.** A plan
  absorbs an error it cannot free into whatever it can, then arrives converged
  with nothing to suggest, while its own first stage named the cause. Each
  rung's actions are the ones the plan you ran will *not* fix. The library half,
  `Refinement.fit(stage_reports=True)`, is off by default, because `fit` is
  called in loops.

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

:::{admonition} For automated callers
:class: agent
That `description` is the first thing a calling agent reads about this package,
before any schema, any result and any part of this manual. It therefore carries
the two rules agents get wrong most often: read the diagnostics before the
statistics, and read the whole trajectory rather than only the final report.

It also points at `docs/AGENT_PROTOCOL.md` by repository-relative path, and a
`pip install` gets the package without the `docs/` tree. Until that is resolved
at release, put the protocol into your agent's context yourself, from
[the copy in the repository](https://github.com/yue-here/rietx/blob/main/docs/AGENT_PROTOCOL.md).
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
  `Capabilities.anodes` — the dispatch vocabularies. An `AnodeCapability`
  carries its own `AnodeCapability.wavelengths` and `AnodeCapability.kbeta`.
- **`Capabilities.plans`** — each `PlanCapability` with `PlanCapability.title`,
  `PlanCapability.description`, `PlanCapability.modes` and
  `PlanCapability.when_to_use`, so a program can offer the choice in its own UI
  without hard-coding a list. `PLAN_INFO` is the same table in the library.
- **`Capabilities.reader_formats`** — every pattern format `read_pattern` opens.
  Each `ReaderCapability` carries its own `ReaderCapability.sniff` (how the file
  is recognised), `ReaderCapability.sigma` (where the uncertainties come from,
  which differs per vendor) and `ReaderCapability.refuses` (what it declines,
  and why). `Capabilities.reader_options` documents `scan=`, `block=` and the
  rest.
- **`Capabilities.indexing_engines`** and `Capabilities.search_presets`, with
  `SearchPresetCapability.typical_seconds` and
  `SearchPresetCapability.total_budget_seconds`. An indexing search is budgeted,
  and a caller that has to promise a response time reads it here.
- **`Capabilities.features`** — feature flags, each *derived* from the thing it
  reports (a schema field's presence, a top-level export's existence) rather
  than written as a literal `true`. A flag flips by itself when its feature
  lands.

**Quote this call rather than transcribing its contents.** The reader-format
list went from five to ten in two days once, and a table in prose would have
been wrong by the following week.

## Versioned contracts

`Capabilities` reports five version strings. They are separate because they move
independently:

| Field | Versions |
|---|---|
| `Capabilities.schema_version` | the pydantic schemas — the model, the pattern, the result |
| `Capabilities.report_thresholds_version` | the `FitReport` gates and their thresholds |
| `Capabilities.event_schema_version` | the streaming event ladder |
| `Capabilities.project_format_version` | the `.rex` project directory |
| `Capabilities.textdoc_format_version` | the `.rxt` text document |

`Capabilities.package_version` is the sixth string, and the only one that moves
on every release. Store the contract versions alongside any result you store: a
threshold compared across two `report_thresholds_version` values compares two
different questions.

## Further reading: the agent protocol

This chapter describes the surface.
[`docs/AGENT_PROTOCOL.md`](https://github.com/yue-here/rietx/blob/main/docs/AGENT_PROTOCOL.md)
covers the half an integrator cannot derive from a schema: the turn-on order,
the degeneracies to memorise, what to check before believing a number, how to
read an abstention, and the measured findings that should change what a calling
agent does.
