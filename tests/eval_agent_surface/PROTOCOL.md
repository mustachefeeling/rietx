# Runner protocol — the agent-surface round (WP-1110)

**Protocol version: 1.0**, registered 2026-08-20 **before any 1.0 run**.
Bump it on any change that alters comparability: the episode, the workspace
contents, the prompt text, the condition set, the shim's target list, or the
scoring rules.

This is a **different measurement** from `tests/eval_report_agent/`, which asks
whether an agent *reads* a FitReport it was handed. This one asks which
**surface** an agent reaches for at all when it is handed files and a job. The
two share the discipline — register before running, enforce the condition in a
shim rather than in the prompt, pre-register the read-out — and nothing else.
A cell here pools with nothing there.

## The question

WP-1110's evidence is one 3 h 20 min transcript of a capable agent refining a
82-scan variable-temperature ZrMo₂O₈ reel it had transcribed from a TOPAS
`.inp`. It made **zero** calls to `agent.refine_json` or `agent.tool_definition`
— the entire tool-calling surface WP-0602 exists to provide — while calling
`capabilities()`, which sits in the same chapter's opening sentence. It ran
129 Bash calls of hand-written python instead.

**Why?** Four candidate causes, two of them already settled without an agent.

- **H1 — the surface takes typed objects, so reaching it costs more than
  skipping it.** `RefineRequest.pattern` is a `PatternData` and `.structure` a
  `Structure`; `SequentialRefineRequest.patterns` is a `list[PatternData]`.
  No request accepts a file path, by declaration: `agent.py`'s module docstring
  fences "any file-path or CIF-text convenience" to the v2 MCP server. An agent
  holding a `.raw` and an `.inp` must therefore enter python and build every
  object *first*; once it holds them, `rx.refine_sequential(...)` is strictly
  fewer steps than dumping them to JSON and having pydantic re-validate.
  **Status: statically established as a property of the surface.** What an
  agent does about it is what this round measures.
- **H2 — discoverability.** The chapter title "Calling rietx from a program"
  may not read as the machine-facing entry point to something scanning an
  index. **Status: partly refuted before the round** (WP-1110's first session):
  the page is in the toctree, the front page carries a "For agents"
  admonition, and the chapter's first two sentences name both calls. The
  transcript agent reached neither the page nor the call.
- **H3 — inspectability.** A shell-driving agent prefers python it can compose
  and step through over a one-shot envelope it cannot inspect midway.
  **Status: open**, and only separable from H1 by a cell where the objects
  already exist.
- **H4 — coverage: `refine_json` does not do series.** **Status: refuted.**
  `task="refine_sequential"` exists and carries `direction`, `carry`, `refit`
  and `reseed`. This hypothesis is closed and no cell tests it.

## The episode — E-ZRM

The trigger dataset itself, which is what makes this round worth running: a
real job, not a fixture.

Workspace contents, identical in every cell:

| file | what it is |
| --- | --- |
| `d8_01612.raw` | Bruker RAW v3, **82 scans**, 318 → 1123 K, 4168 points each, 10–70° 2θ, λ = 1.5406 Å (Cu Kα1, Ge(111) mono, Bragg–Brentano) |
| `d8_01612_vt_reel_02.inp` | the TOPAS input the maintainer refined it with: 4 phases (ZrMo₂O₇(OH)₂·2H₂O, cubic-, trigonal- and LT-ZrMo₂O₈), sites, and the instrument declarations |

Nothing else. No CIFs — the structures are inline in the `.inp`, exactly as the
transcript agent found them. The helper python scripts shipped in the same zip
(`plot_all.py`, `to_Reel_v1.py`, `topas_autoClean_Reel.py`, …) are **withheld**:
they encode the maintainer's intended workflow, and an agent reading them is no
longer an unaided one.

**The reader gate is fixed first.** Before this round, `read_pattern` refused
this file outright — its 82 ranges parse and leave a 3280-byte zero pad, which
the length-only global gate rejected. A cell that dies on the reader measures
the reader, not the surface, so the fix lands ahead of the round and every cell
runs on a tree where the reel opens.

### The task given

Refine the reel and report how the phase fractions and cell parameters move
with temperature. The prompt states the physical facts an operator would know
(radiation, geometry, that the `.inp` holds the starting model, that the file
holds 82 scans with temperatures) and **nothing about how to drive the
package** — no module names, no plan names, no method. The scope is capped at
the first few scans with the method stated, because the surface choice is made
in the first handful of calls and the science is not what is being scored.

## The conditions

Three, enforced by what the workspace and prompt contain — never by asking the
agent to behave a certain way.

| cell | what differs | what it isolates |
| --- | --- | --- |
| `bare` | nothing added | replicates the transcript. Does an unaided agent reach `refine_json`? |
| `pointed` | one added sentence naming `rietx.agent.refine_json`, `agent.tool_definition` and the manual chapter as the intended programmatic surface | **the discriminator.** An agent that now uses it was blocked by H2; one that reads it and returns to python was not |
| `mandated` | `pointed`, plus the fit is required to be driven through `refine_json` | prices H1. Not a preference measurement — its read-out is whether the run completes and what it costs |

`mandated` is the one cell whose prompt constrains behaviour, and it is
declared as a cost probe rather than a choice probe for exactly that reason.

**N = 2 per cell**, model `sonnet`, six runs. N=2 cannot measure a rate and
this protocol never quotes one; it exists so a single agent's idiosyncrasy is
visible as a disagreement rather than invisible as a result.

## The shim

`rietx_surface_trace.py` plus a `.pth` line, installed into the **experiment
venv's** site-packages — never into the package under test. A `.pth` executes
at interpreter start, so every python that venv starts is traced however the
agent invokes it, and there is no environment variable for an agent to miss or
a wrapper for it to bypass.

It patches, after `rietx` executes, a fixed target list: `agent.refine_json`,
`agent.tool_definition`, `agent.request_schema`, `agent.response_schema`,
`capabilities`, `read_pattern`, `structure_from_cif`, `refine`,
`refine_sequential`, `refine_multi`, `replay`, `index_pattern`, `build_report`,
`diagnose`, `auto_background`, the instrument-profile pair, six `Refinement`
methods, `SequentialRefinement.run`, and three `Project` methods. Each call
appends one JSONL line carrying the name, the keyword names (not the values),
the positional count, and `cwd`/`pid` — cwd being how a line is attributed to a
workspace when an agent runs python from elsewhere.

The tracer swallows every exception it can raise: a shim that breaks the run it
watches has destroyed its own measurement.

### Amendments made during round 1.0, and why they do not bump the version

Both change how a call is **attributed**, never which calls exist, which
condition a cell is under, or what the package does. No cell's prompt or
workspace moved, so 1.0 cells stay poolable with each other.

- **The first positional argument is logged when it is a path.** The round
  opened attributing rows by `cwd`, on the assumption that an agent works in
  the directory it was given. It does not: a subagent runs python from
  wherever its shell sits, which here was the session's own cwd, and
  `python -c` leaves nothing but `-c` in `sys.argv`. The data file is the
  reliable key — every cell must read *its own copy* of `d8_01612.raw` — so
  the tracer records that path and `score_round.py` binds a pid to a cell by
  the first path, cwd or argv naming one. No other argument value is recorded.
- **Rows written before the amendment stay unattributed** and are reported as
  such rather than being assigned by guess. The gap costs exploration calls
  that touch no file (`import rietx; rietx.capabilities()`), never a call that
  reads data or runs a fit.

**For round 1.1: give each cell its own venv** with its own log path baked in.
Attribution is then a property of the environment rather than an inference
from what the process happened to touch, which is what a shim should be.

## Pre-registered read-outs

Written before any run; scored off the trace log and the agents' own reports.

- **R1 (primary).** In `bare`, the count of runs whose trace contains
  `agent.refine_json`. **Predicted 0 of 2** — the transcript's outcome, and
  H1's prediction.
- **R2 (the discriminator).** In `pointed`, whether a run that was told the
  call exists drives the fit through it, and — from its own report — the reason
  if it does not. H2 predicts it now uses it. H1/H3 predict it inspects the
  schema and returns to python, citing the object-building step.
- **R3 (the price).** In `mandated`, whether the run completes at all, and what
  it hits. H1 predicts a completed run that had to construct `PatternData` and
  `Structure` in python first and then serialise them, making the envelope a
  round trip rather than an entry point.
- **R4 (the friction ledger).** Which of WP-1110's verified items 2–11 fire
  again, unprompted, in any cell. This is the round's second product: the
  transcript is one agent, and an item that reappears here is no longer a
  single observation.

### Decision rule, fixed in advance

- R1 = 0 **and** R2 shows the pointed runs declining after inspection → the
  cause is the **shape of the surface, not its discoverability**. The WP's
  remaining work belongs on the python surface's ergonomics and its
  diagnostics, and `refine_json` is for MCP callers rather than coding agents.
- R1 = 0 **and** R2 shows the pointed runs adopting it → the cause is
  **discoverability** after all, and the investment is in the entry point's
  naming and placement, not its shape.
- R1 > 0 → the transcript's agent is not representative on this axis, and no
  conclusion about the surface is drawn from one transcript.

R3 refines the recommendation in every branch but decides none of them: a
surface that is reachable but expensive is a different finding from one that is
not reached.

### What is not being scored

Rwp, the phase fractions, the cells, whether the refinement is any good. The
round measures the route, not the destination, and a cell that reaches a bad
refinement through `refine_json` still counts as having reached it. Scoring the
science would make the model's crystallography the confound.

## Results — round 1.0, run 2026-08-20

Six cells, all completed. Wall clock 10.7–26 min each, 73–206 tool uses,
144–226 k tokens. Every number below is read off the trace log by
`score_round.py`, except the reasons, which are the agents' own words.

| cell | `refine_json` | surface it drove the fit through |
| --- | --- | --- |
| `bare-1` | **no** | `refine_sequential` (python) |
| `bare-2` | **no** | `Refinement.fit` (python) |
| `pointed-1` | yes (5) | `refine_json`, called from a python script |
| `pointed-2` | **no** | `Refinement.fit` (python) |
| `mandated-1` | yes (12) | `refine_json` (required) |
| `mandated-2` | yes (8) | `refine_json` (required) |

### R1 — 0 of 2. The transcript replicates.

Neither unaided agent reached `agent.refine_json`, and both reached
`capabilities()` first, exactly as the transcript agent did. The finding that
motivated this WP is not an artefact of one agent on one day.

### R2 — split, 1 of 2, and N = 2 cannot resolve it

`pointed-2` was told the call exists, read enough to understand it, and
**declined**: "I had a live Python process with the `Structure`/`Instrument`/
`PatternData` objects already in memory … so going through the JSON envelope
would have meant serialising them out and back for no benefit — the JSON
surface exists for callers without direct Python access to the objects."

`pointed-1` **adopted** it, for a reason about the *answer* rather than the
call: "it's the one call that returns a fully-typed, JSON-serializable
`RefinementResult` (curves included) plus the three-layer `FitReport` in one
shot."

So neither branch of the pre-registered decision rule fires unanimously. The
protocol said N = 2 exists to make a disagreement visible rather than to
measure a rate, and that is what it did. **This split is the honest result and
is not resolved by argument.**

### The result neither read-out asked for, and the strongest one

`agent.tool_definition()`, `request_schema()` and `response_schema()` were
called **zero times, in every cell, across 235 traced interpreter starts** —
including both mandated cells and the pointed cell that adopted the envelope.
All 25 `refine_json` calls came from agents that had read the contract from
`using/agents.md` or from source and were calling it as an **ordinary python
function inside a python script**.

That reframes the WP's question. `refine_json` is reachable, is sometimes
chosen, and works well when chosen. What has no consumers here is the
**tool-calling** half: the exported JSON Schema that exists so an LLM loop can
call this without writing python. Every agent in this round had a shell and
wrote python; none of them needed a tool definition, and none fetched one.

### R3 — the price, and where it actually falls

Both mandated cells completed, at ~1.7 s and ~4–6 s per call, with no crash;
`refine_json` never raised, returning `INVALID_REQUEST` envelopes naming the
offending dot-paths. The cost is **not in the envelope**, and H1's
serialisation half is **wrong**: `mandated-1` reports the request "accepted
live `Structure`/`Instrument`/`PatternData` objects directly in the dict, no
manual `model_dump()` needed."

H1's core survives in a sharper form, stated by `mandated-2`: driving the fit
through `refine_json` "still required importing `rietx` itself for the plan
object model, not just the JSON surface." Everything expensive is **upstream**
of the call — no `.inp` reader, no path to a CIF, a `Structure` built by hand,
and a `PlanSpec` built in python to patch one stage of a stock preset. Paying
that cost puts a caller in python, where the envelope adds only its answer
shape. That is why a mandated agent likes it and an unaided one never reaches
for it.

### Two hypotheses closed

- **H2 (discoverability) is refuted as the primary cause.** `pointed-2` knew
  and declined; `pointed-1` knew and adopted. Neither outcome is explained by
  not being able to find the page.
- **H4 (no series coverage) stays refuted**, but a real coverage gap in the
  same family was found: `refine_json` **cannot express a parameter tie**
  (WP-1070's `tie`/`tie_equal`), so `mandated-2` could not ask for the `.inp`'s
  single shared `boverall` across 15 atoms.

### Defects in this round's own instrument

- **The shim was visible.** `rietx_surface_trace.py` wraps without
  `functools.wraps`, so `inspect.signature` showed the wrapper and `pointed-2`
  went to source to recover a signature. An observation effect, small but real.
  Fix before 1.1.
- **The workspace had no plotting library.** `rietx` was installed without
  extras, so `plot_result`/`write_html` were unusable and **four of six** agents
  hand-rolled an SVG writer. That is a defect in the workspace, not a finding
  about the package, and no conclusion is drawn from it — though it is worth
  noting that four independent agents judged a picture worth writing a plotter
  for.
- **Attribution**, per the amendment above. Fix in 1.1 with one venv per cell.

### What the round found about the package

Not read-outs, but the reason a real episode beats a fixture. Each is in the
WP's friction list with its evidence.

- **The cell of a phase at zero scale runs away.** Two agents independently:
  a ≈ 39 293 Å and a ≈ 40 000 Å, refused several stages later by
  `generate_reflections`. `Structure.from_cif` gives cell bounds `(0.1, ∞)`, and
  a phase with no intensity has no gradient, so TRF steps freely in a near-null
  direction.
- **A good fit can return `esd: None` for every parameter** — two parameters
  legitimately at their softplus zero poison the one whole-vector covariance
  inversion.
- **`Parameter.expr` is planned around.** `mandated-1` proposed it as the way to
  tie `biso` across atoms. It always raises.
- **The plan types are two.** `PLAN_PRESETS` hands back
  `strategy.staged.RefinementPlan`/`Stage` (dataclasses); the request wants
  `schemas.plan.PlanSpec`/`StageSpec` (pydantic).
- **A VT reel's temperature is not public.** `pointed-1` read
  `_Range.temperature_k` off the private `bruker_raw._parse()` to get 318/323/333 K.
- **`bound_findings`' relative tolerance misfires on wide bounds** — scale bounds
  `[1e-14, 1e14]` read as "at its bound" at every stage.
- **The wheel ships the maintainer's rulebooks.** `bare-1` read
  `rietx/io/CLAUDE.md` "shipped inside the package tree, not just the repo".

### For the speed milestone

`pointed-1` abandoned a warm-started `refine_sequential`: pattern 1 converged in
~50 s, pattern 2's `refit="single"` collapse ran past 150 s unfinished, on a
4-phase model whose `cell` stage alone cost 22 s. Its reading is that collapsing
six stages into one runs a single TRF over ~30 free parameters, and the
per-iteration Jacobian width eats the iteration-count saving WP-0505 measured.
That is a v1.1 datum on a real trigger-shaped model, and it belongs to the
harness WP rather than here.
