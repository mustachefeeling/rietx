# Driving the package from a program

Two calls carry the whole integration surface. `capabilities()` says what this
build can do; `agent.refine_json` does it.

Everything in this chapter is designed for a program to consume first — a JSON
envelope, a generated schema, a capability object. A human can read all of it,
and `capabilities()` in particular is the fastest way to answer "did my `jax`
extra take?" from a REPL. But the shapes here are chosen for a caller that
branches on a field, not for one that reads a sentence.

## One call, five tasks

`agent.refine_json` takes a dict and returns a dict. It never raises and never
returns a traceback:

```python
from rietx import agent

envelope = agent.refine_json({"task": "capabilities-probe-is-not-a-task"})
envelope["ok"], envelope["error"]["code"]
```

Success is `{"ok": true, …}` with **exactly one** of `result`, `series`,
`indexing` or `suggestion` set, so a consumer branches on which arm arrived.
The four are separate arms because they are different *shapes*, and for
indexing the shape is the rule: the serialized answer carries no `cell` key,
because a powder pattern does not measure one cell — it measures a ranked set
of candidates, and handing back a singleton would be handing back a confident
guess.

| `task` | Does | Answers in |
|---|---|---|
| `refine` | fits one pattern | `result` |
| `refine_multi` | fits N patterns as one joint residual | `result` |
| `refine_sequential` | chains N patterns by warm start | `series` |
| `index` | determines a unit cell from peaks or a pattern | `indexing` |
| `suggest` | ranks held parameters by predicted Δχ², no solve, no mutation | `suggestion` |

Failure is `{"ok": false, "error": {code, message, suggestion, details}}` —
the same grammar as a `Diagnostic`, so a consumer has one vocabulary for "the
fit warns" and "the call failed". Three codes, closed: `INVALID_REQUEST` (with
per-field dot-paths in `details`), `BACKEND_UNAVAILABLE` (a valid backend name
whose optional dependency is not installed here), and `REFINEMENT_FAILED`.

Two **companions** ride beside whichever arm arrived, rather than being arms
themselves:

- `evidence` — the answer projected for a reasoning consumer.
- `trajectory` — the report at every stage boundary, on by default here.
  **A converged report is routinely the least informative one in the run**: a
  plan absorbs an error it cannot free into whatever it can and arrives
  suggesting nothing, while its own first stage named the cause. Each rung's
  actions are the ones the plan you ran will *not* fix. (The library half,
  `Refinement.fit(stage_reports=True)`, is off by default, because it is
  called in loops.)

## Registering it as a tool

`agent.tool_definition` returns a ready-to-register definition — `name`,
`description`, `input_schema` — and `agent.request_schema` /
`agent.response_schema` are the JSON Schemas alone.

```python
from rietx import agent

definition = agent.tool_definition()
sorted(definition)
agent.request_schema()["$defs"] is not None
```

**The vocabularies inside that schema are quoted from the live registries**,
not restated: backend, solver, plan and indexing-engine names come from the
same tuples the package dispatches on, and a meta-test fails when a registered
member is missing from the exported schema. A third engine cannot ship
invisible.

**That description is the first thing a calling agent ever reads about this
package** — before any schema, any result and any part of this manual — so it
carries the two rules an agent gets wrong most often: read the diagnostics
before the statistics, and read the whole trajectory rather than only the final
report.

:::{note}
It also points at `docs/AGENT_PROTOCOL.md` by repository-relative path, and a
`pip install` gets the package without the `docs/` tree. Until that is resolved
at release, put the protocol in your agent's context yourself, from
[the copy in the repository](https://github.com/yue-here/rietx/blob/main/docs/AGENT_PROTOCOL.md).
:::

## What this build can do

`capabilities()` is the one call that answers it, and every arm is quoted from
a live registry rather than typed:

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
  `PlanCapability.when_to_use`, so a program can offer the choice in its own
  UI without hard-coding a list. `PLAN_INFO` is the same table in the library.
- **`Capabilities.reader_formats`** — every pattern format `read_pattern`
  opens, each `ReaderCapability` carrying its own `ReaderCapability.sniff`
  (how the file is recognised), `ReaderCapability.sigma` (where the
  uncertainties come from, which differs per vendor) and
  `ReaderCapability.refuses` (what it declines and why).
  `Capabilities.reader_options` documents `scan=`, `block=` and the rest.
- **`Capabilities.indexing_engines`** and `Capabilities.search_presets`, with
  `SearchPresetCapability.typical_seconds` and
  `SearchPresetCapability.total_budget_seconds` — an indexing search is
  budgeted, and a caller that needs to promise a response time reads it here.
- **`Capabilities.features`** — feature flags, each *derived* from the thing
  it reports (a schema field's presence, a top-level export's existence),
  never a literal `true`. A flag flips by itself when its feature lands.

**Quote this call rather than transcribing its contents.** The reader-format
list went from five to ten in two days once; a table in prose would have been
wrong by the following week.

## The five versioned contracts

`Capabilities` reports five version strings, and they are separate because
they move independently:

| Field | Versions |
|---|---|
| `Capabilities.schema_version` | the pydantic schemas — the model, the pattern, the result |
| `Capabilities.report_thresholds_version` | the `FitReport` gates and their thresholds |
| `Capabilities.event_schema_version` | the streaming event ladder |
| `Capabilities.project_format_version` | the `.rex` project directory |
| `Capabilities.textdoc_format_version` | the `.rxt` text document |

`Capabilities.package_version` is the sixth string and the only one that moves
on every release. A consumer storing results should store the contract
versions with them: a threshold compared across two `report_thresholds_version`
values is comparing two questions.

## Then read the protocol

This chapter is the *surface*. The half an integrator cannot derive from a
schema — the turn-on order, the degeneracies to memorise, what to check before
believing a number, how to read an abstention, and the measured findings that
should change what a calling agent does — is
[`docs/AGENT_PROTOCOL.md`](https://github.com/yue-here/rietx/blob/main/docs/AGENT_PROTOCOL.md).
It is written for exactly this reader, and nothing here restates it.
