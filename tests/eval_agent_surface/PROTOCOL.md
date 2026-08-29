# Runner protocol — the agent-surface round, 1.1 (WP-1307)

**Protocol version: 1.1**, registered 2026-08-29 **before any 1.1 run**.
Bump it on any change that alters comparability: the episode, the workspace
contents, the prompt text, the condition set, the shim's target list, or the
scoring rules.

**A 1.1 cell pools with nothing in 1.0.** Every one of those six things moves
between the rounds, and so does the package under them: WP-1301 to WP-1305
landed in between. Round 1.0's registration and its results are preserved
below, from its own heading down, **unedited** — a pre-registered round is not
rewritten once it has run, and `score_round.py` says in its docstring that it
scores that round and nothing later. 1.1 declares its own read-outs and gets
its own scorer.

## The question

1.0 asked which surface an agent reaches for when handed files and a job. It
answered, and its answer deleted a surface: no unaided cell called the JSON
envelope, the tool definition was fetched zero times in 235 traced interpreter
starts, and WP-1303 removed `rietx.agent` on that evidence.

1.1 asks the question after it. Six things were built on the strength of that
answer and of the 2026-08-26 ramp audit — a held phase (1301), an error that
answers with the right name and a result that states whether it is done (1302),
one integration surface (1303), the protocol as a discoverable skill (1304),
the trajectory deliverable and its two hand-checks turned into calls (1305), and
a foreign recipe format (1306). The question is:

> **Did any of it change what an agent pays, and how it decides it is done?**

Read out: API calls, cache-read tokens per call, wall clock against refinement
seconds, discovery errors, surfaces reached, whether a flat direction fired, and
the stopping criterion the agent states.

## The baselines, and what none of them can say

| baseline | what it is | its headline numbers |
| --- | --- | --- |
| **the ramp run**, 2026-08-26 | one Opus 5 subagent, 68 simulated VT patterns, primed with `AGENT_PROTOCOL.md` | 90 API calls, 14.6 M cache-read (mean context 168 k), 87 k output, 34.7 min wall for **34 s** of refinement, 9 discovery errors + 4 source hunts, none of the built surfaces used, a flat direction 27 % of wall |
| **the contributor's campaign**, 2026-08 | 86 runs, 5 430 tool calls, six of which refined, all briefed by one coordinator | stopping criteria: 0 on a §10 condition, 0 on a §4b row, 0 on an index alone, 1 external comparison, 1 script exit, 1 instruction, 3 ended waiting. `suggest` 0, `plot_for_vlm` 0, `report()` 2 |
| **round 1.0**, 2026-08-20 | six Sonnet cells on E-ZRM | R1 0/2, R2 split, the schema export called zero times in 235 interpreter starts |

None of the three is a control, and the protocol states the reason at every row
that quotes one.

- The ramp is **n = 1**, on data simulated by rietx's own forward model, with a
  prompt in the protocol's vocabulary and an instruction to read the protocol.
  It is a **primed** run.
- The campaign's workers were briefed with the rules restated inline by their
  coordinator, which is the obvious confound for every instruction-source
  read-out, and they ran a stale release (1.0.1) for a week.
- 1.0's cells were all `sonnet`, on an episode 1.1 keeps and a package 1.1 has
  moved.

So a 1.1 row compared with a baseline is a **before-and-after on a moving
build**, never a controlled contrast. The one controlled contrast in this round
is the condition below, which is why it is the only within-round comparison the
decision rules lean on.

**The deployment shape is recorded, not run.** The campaign's
coordinator-plus-workers arrangement is how this package is actually reached in
the field, and it is written down here as an observed deployment. It is not a
cell: the single cold agent is the one whose brief this protocol controls, and a
coordinator's brief is not ours to hold fixed.

## The episodes

Two, because they fail differently and each carries one baseline.

### E-ZRM — kept from round 1.0, unchanged

Real data, unknown truth, four phases, and the episode 1.0's cells ran, so its
rows are the ones comparable with 1.0.

| file | what it is |
| --- | --- |
| `d8_01612.raw` | Bruker RAW v3, **82 scans**, 318 → 1123 K, 4168 points each, 10–70° 2θ, λ = 1.5406 Å (Cu Kα1, Ge(111) mono, Bragg–Brentano) |
| `d8_01612_vt_reel_02.inp` | the TOPAS input the maintainer refined it with: 4 phases (ZrMo₂O₇(OH)₂·2H₂O, cubic-, trigonal- and LT-ZrMo₂O₈), sites, and the instrument declarations |

Provenance, and the withheld helper scripts, are as 1.0 registered them: the
maintainer's TOPAS workshop dataset `zrmo2o8_vt.zip`, fetched 2026-08-20, **not
committed anywhere in this repo**. Re-running this episode means fetching it
again, and a dead link costs this protocol its episode and nothing else.

### E-RAMP — new

Synthetic, **known truth**, a 68-pattern series, and the episode of the
2026-08-26 baseline, so its rows are the ones comparable with that audit.

The generator is committed as `episodes/ramp.py` — the same script that made the
baseline's data, moved into the harness so the episode can be rebuilt rather
than being a directory someone kept. It writes 68 `.xye` patterns and
`host.cif`:

- NAC (COD 1000236) on a Cu Kα Bragg–Brentano geometry, 15–60° 2θ at 0.02°;
- the host cell expands 0.8 % over 25 → 720 °C with a first-order step of
  +0.16 % at 430 °C;
- a **CaF₂ phase absent below the step**, growing above it to a plateau, whose
  cell is held constant in the simulation;
- Poisson noise, σ = √counts.

`host.cif` is the host phase only. The second phase is the agent's to find, the
step is the agent's to verify, and the held CaF₂ cell is the trap the baseline
agent caught. **The truth is recorded against every run and scored in no
read-out** (§ What is not being scored).

## The condition — one, and it is environmental

| cell | what differs | what it isolates |
| --- | --- | --- |
| `bare` | nothing added to the workspace | the floor: an agent with the package, the data and no rules |
| `skill` | `rietx skill --install <workspace>` has run before the agent starts, putting the skill in `.agents/skills/rietx/` with a link from `.claude/skills/` | whether WP-1304's skill is **found** without being named, and what it changes |

**Never a prompt sentence.** The ramp baseline was *told* to read
`docs/AGENT_PROTOCOL.md` and the campaign's workers had the rules restated
inline; both confound the instruction's source with the instruction itself. A
skill in the harness's own directory is discovered by the harness and offered to
the agent with its one-line description, so `skill` is the environmental form of
that priming — the cell comparable with the primed baseline — and `bare` is
comparable with neither baseline. `bare` is this round's new floor and its rows
are quoted as such.

1.0's `pointed` and `mandated` cells have no successor. Both pointed at a
surface that no longer exists, and neither question survives it.

## The prompts — unprimed, and written down

Registered verbatim, because a prompt that is paraphrased in the protocol is a
condition nobody can reproduce. Neither names a module, a plan, a method or a
document.

**E-RAMP** is the 2026-08-26 baseline's own prompt, word for word:

> Here are 68 patterns from a variable-temperature run, 25 to 720 °C. Refine
> them in order, tell me what the cell does, and flag anything you would not
> quote.

**E-ZRM** states the physical facts an operator would know and caps the scope,
since the surface choice is made in the first handful of calls and the science
is not what is scored:

> `d8_01612.raw` is a variable-temperature powder reel: 82 scans from 318 K to
> 1123 K, Cu Kα1 at λ = 1.5406 Å from a Ge(111) monochromator, Bragg–Brentano
> geometry. `d8_01612_vt_reel_02.inp` is the input file another program refined
> it with, and it holds the starting model: four phases, their cells and their
> sites. Refine the first five scans, tell me how the phase fractions and the
> cell parameters move with temperature, and flag anything you would not quote.

Each run is additionally given, in both cells, exactly what the baseline was
given beyond its prompt and nothing more: **the interpreter path and the
workspace directory**. What the baseline had and 1.1 removes is the sentence
naming a document to read. That sentence is the condition now.

## N, the models, and what N = 2 can say

Four cells — two episodes × two conditions — and **two runs each: one
`sonnet`, one `opus-5`**. Eight runs. Cost recorded per run.

**N = 2 cannot measure a rate and this protocol never quotes one.** It exists so
that one agent's idiosyncrasy shows up as a disagreement rather than as a
result, which is what it did in 1.0, whose `pointed` cell came back split and
was reported split.

The price of covering both baselines' models in eight runs rather than sixteen
is stated here rather than discovered later: because a cell's two runs differ by
model, **a within-cell disagreement cannot be told from a model difference**, and
every such row is reported as a disagreement with both models named. A row that
moves the same way in all four cells is reported as a direction, never as a
factor.

## The shim

`rietx_surface_trace.py` plus a `.pth` line, installed into the **experiment
venv's** site-packages — never into the package under test. A `.pth` executes at
interpreter start, so every python that venv starts is traced however the agent
invokes it: no environment variable to miss, no wrapper to bypass.

**One venv per run, with its log path baked into the `.pth` line.** This is
1.0's own recommendation for 1.1, and it closes 1.0's attribution defect:
attribution becomes a property of the environment instead of an inference from
which file a process happened to touch. The `RIETX_SURFACE_LOG` environment
variable stays as a fallback and is not how a 1.1 run is attributed.

Each traced call appends one JSONL line carrying the name, the keyword names,
the positional count, the elapsed seconds, and `cwd`/`pid`.

### What is recorded, and the one exception

- **Keyword names always; values only from a declared allowlist**:
  `deliverable`, `direction`, `refit`, `mode`, `preset`,
  `verify_discontinuities`, and `plan` when it is a string. Three read-outs turn
  on *which* value was passed rather than on whether a keyword was, and every
  member of that list is an enum, a bool or a preset name. No other argument
  value is ever recorded.
- **The first positional argument when it is a path** (1.0's amendment, kept):
  it is what names the workspace when an agent runs python from elsewhere.

### What 1.1 adds to the events

- every `call` carries `dt`, its own elapsed seconds. **Fit seconds are
  attributed by where the fit ran**, from this number, never from the command
  head — which is how a driver script and a backgrounded job get counted, and
  the campaign's projection could count neither.
- every `call` carries `depth`, how deep it sat inside other traced calls, and
  **seconds are summed at `depth == 0` only**. `rx.refine` *is*
  `Refinement.fit` one frame down and `refine_sequential` *is*
  `SequentialRefinement.fit`, so a sum over names reports a 12.5 s chain as
  24.9 s. The inner name still counts as *reached*, because R2 asks which
  surfaces a run touched.
- `import` carries the seconds from interpreter start to the end of
  `import rietx`, and an `atexit` `exit` event carries the process's whole wall
  clock. Those two are R8's numerator and denominator.
- `import` also carries **`missing`**, the declared targets that did not resolve
  in that interpreter. A stale target and an unreached surface are the same
  empty column otherwise, which is how 1.0's list would have scored
  `SequentialRefinement.run`'s rename;
  `test_trail.py::test_every_shim_target_resolves_against_this_build` fails on
  a non-empty list.

### The target list, 1.1

Round 1.0's four JSON-envelope entries are gone: the module they name is
deleted, and a target that cannot be reached is a read-out that cannot fail.
One more correction, measured 2026-08-29: **`SequentialRefinement.run` no longer
exists** — the class exposes `.fit` — so 1.0's list would have scored a rename
as a surface nobody reached. A 1.1 target that does not resolve at patch time is
reported by the scorer rather than passing silently.

| group | targets |
| --- | --- |
| entry | `capabilities`, `read_pattern`, `crystallography.cif.structure_from_cif`, `read_recipe`, `write_recipe_tables`, `list_examples` |
| fitting | `refine`, `refine_sequential`, `refine_multi`, `replay`, `Refinement.fit`, `Refinement.run_stage`, `Refinement.predict`, `SequentialRefinement.fit` |
| judging | `build_report`, `diagnose`, `Refinement.report`, `Refinement.summary`, `SeriesResult.summary`, `Refinement.suggest` |
| the table | `Refinement.parameters`, `Refinement.set_vary`, `Refinement.set_values`, `Refinement.tie`, `Refinement.tie_equal`, `Refinement.untie` |
| help | `help_for`, `help_key_for`, `help_registry` |
| pictures | `viz.plot_result`, `viz.plot_for_vlm`, `viz.write_html` |
| the rest | `index_pattern`, `auto_background`, `load_instrument_profile`, `save_instrument_profile`, `Refinement.branch`, `Refinement.checkout`, `Project.create`, `Project.open`, `Project.save` |

### Invisibility

A shim has to be invisible to its subject. It wraps with
`functools.update_wrapper`, so `inspect.signature` shows the real signature —
1.0 wrapped without it and an agent went reading source to recover one — and it
swallows every exception it can raise, because a shim that breaks the run it
watches has destroyed its own measurement.

## The projection — `trail.py`

`trail.py` turns one session transcript into one line per tool call: offset,
duration, output size, error flag, and the first line of the command. That table
answers most of the round's questions on its own, and it is committed with a
test on a fixture transcript so its two rules cannot rot.

- **Usage is summed once per `message.id`, last record wins.** A thinking block
  and its tool_use share an id, so the 2026-08-27 audit's first pass
  over-counted cache reads by 151/90 by summing per record.
- **Fit seconds come from the shim's trace**, per the rule above.

## Pre-registered read-outs

Round 1.0 declared four, and three of them are about a surface that no longer
exists. So 1.1 declares its own eleven. Only **R4** keeps its number and its
meaning across the rounds.

- **R1 (primary) — the price of an answer.** Per run: API calls, cache-read
  tokens, mean context, output tokens, wall clock, and refinement seconds inside
  it. The E-RAMP cells are set beside the baseline's 90 / 14.6 M / 34.7 min /
  34 s; the E-ZRM cells beside 1.0's 73–206 tool uses and 144–226 k tokens.
- **R2 — surfaces reached.** Which targets each run called. Two sublists are
  read separately: the five the audit found **invisible** (`capabilities`, the
  three `help_*` calls, `set_vary`, the history DAG, any CLI verb) and the five
  1301–1305 **added** (`Refinement.summary`, `SeriesResult.summary` with
  `deliverable=`, `CandidateGroup.delta_bic`, `verify_discontinuities=True`,
  `read_recipe`).
- **R3 — discovery errors.** Tool calls that failed because the agent did not
  know a shape (9 of 19 errors in the baseline), classified by hand into: wrong
  name, wrong signature, wrong module path, wrong attribute owner. Counted
  beside them: **source hunts**, reads of `src/rietx/**` that answer what the
  docs did not (4 in the baseline). WP-1302's claim is that the error text now
  carries the right name, so a wrong name corrected **from the error itself** is
  counted separately from one corrected by reading source.
- **R4 — the friction ledger** (carried from 1.0). Which of WP-1110's verified
  items 2–11 fire again, unprompted, in any cell.
- **R5 — the flat direction.** Did an unsupported phase's cell run away, and
  what share of wall clock did it cost? 27 % in the baseline, >115× on the
  reproduction. WP-1301 holds such a phase for the stage instead of bounding it,
  and this is its behavioural test: `PHASE_UNCONSTRAINED` and `StageResult.held`
  in the run's own output, against wall clock.
- **R6 — the condition.** `skill` against `bare` on every row above and on R11,
  per episode. The round's **only** controlled contrast.
- **R7 — the scaffolding ratio.** Bash tool calls per traced fit.
- **R8 — the per-process floor.** `import rietx` summed over the run's traced
  processes, against those processes' whole wall clock. A run that starts a
  fresh interpreter for every question pays it every time. The numerator is the
  shim's `import_dt` and nothing else, which is narrower than the WP's filed
  wording: **the shim cannot separate kernel load**, since the compiled tier
  loads on a kernel's first call and the background compile finishes when it
  finishes. Measured on the registration build, darwin `[dev]`, three runs:
  `import rietx` **0.50–0.51 s**, plus 0.17–0.34 s to the first forward call,
  0.67–0.84 s together. The WP filed 1.75–2.37 s for import-plus-kernel-load on
  2026-08-28 and this session did not reproduce it on either definition; the
  registered number is the one above, measured here.
- **R9 — the build.** `capabilities().package_version` recorded in every run's
  record, because a round whose build is not written down cannot be compared
  with the next one.
- **R10 — backgrounding.** Did the agent put a fit in the background, and what
  did it see while waiting? The progress sink's first measurement.
- **R11 — the stopping criterion the agent states**, classified by hand from its
  closing text into exactly one of: **a §10 condition** (SKILL.md's three stop
  conditions) / **a §4b deliverable row** / **an agreement index alone** /
  **an external comparison** / **a script exiting** / **an instruction** /
  **none** (ended waiting). Counted beside it, each a distinct observation
  because the 2026-08-26 agent did all three **by hand**:

  1. did it print `SeriesResult.summary(deliverable="series")` or
     `Refinement.summary(deliverable=…)` — §4b's rows, which that agent wrote
     for itself across about 34 of its 90 calls;
  2. did it read `CandidateGroup.delta_bic`, or run two refits per candidate to
     compute ΔBIC itself;
  3. did it pass `verify_discontinuities=True`, or hand-refit the step's two
     patterns cold.

  A run that still does these by hand has had a **discovery** failure, not a
  judgement one, and the read-out separates the two. Whether `plot_for_vlm` was
  called, and whether the agent looked at a plot it drew itself, are counted
  here too.

Which read-outs are scored by machine and which by hand is fixed in advance:
R1, R2, R7, R8, R9 off the trace log and the transcript by `trail.py` and the
1.1 scorer; R3, R4, R10, R11 by hand from the transcript; R5 from the run's own
diagnostics plus the trace's timings.

## Decision rules, fixed in advance

Each WP's claim is judged **improved / unchanged / worse**, by the read-out
named here and no other. A claim whose read-out disagrees within a cell is
**split**, and split is a result.

| WP | the claim | judged by | improved means |
| --- | --- | --- | --- |
| 1301 | an unsupported phase is held, not bounded, so it cannot eat a chain's wall clock | R5 | no runaway in any E-RAMP cell, or one that costs under 5 % of wall |
| 1302 | the error is the documentation, and a result says whether it is done | R3, R11 | discovery errors under the baseline's 9, with wrong names corrected from the error text rather than from source; and R11 lands on a package criterion rather than on `none` |
| 1303 | there is one integration surface | R2 | **not a testable claim in this round** — the alternative is deleted, so the row is recorded as observed and judged nothing |
| 1304 | the protocol is a skill, and it is found without being named | R6 on R2 and R11 | the `skill` cells reach the skill unprompted, and their document reading costs less than the baseline's 31 k tokens × 80 calls ≈ 2.5 M cache-read, ~17 % of its total |
| 1305 | §4b's trajectory rows are stopping criteria, and its two hand-checks are calls | R11's three sub-rows | at least one cell states a §4b row as its stopping criterion, and the hand-checks appear as calls rather than as hand-written refits |

Two rules over all of them, and they bind: **no rate is quoted from N = 2**, and
**no row is attributed to a WP when the baseline it moves against ran a
different build, a different model and a different brief** — such a row is
reported as a before-and-after with all three differences named.

## What is not being scored

Rwp, the phase fractions, the cells, whether the refinement is any good. The
round measures the route and the price, not the destination, and a cell that
reaches a bad refinement while stating a good stopping criterion still counts as
having stated one. Scoring the science would make the model's crystallography
the confound.

E-RAMP's known truth is **recorded against every run and scored in no read-out**
for the same reason. It is worth seeing whether a stated criterion sits over a
wrong answer; it is not worth turning this round into a crystallography exam.

## This round's own instrument

Known defects of 1.0, and what 1.1 does about each:

- **Attribution by inference** → one venv per run with its log path baked in.
- **A visible shim** → `functools.update_wrapper`, fixed before this round.
- **A workspace with no plotting library** → every 1.1 workspace installs
  `rietx[viz]`, so `plot_result`, `plot_for_vlm` and `write_html` are usable.
  Four of 1.0's six agents hand-rolled an SVG writer because they were not, and
  no conclusion was drawn from it. R11 counts plotting calls, so the library has
  to be there.

And one defect this round cannot fix: **the harness is Claude Code's**.
WP-1304's harness-neutral claim is tested structurally in that WP and
behaviourally only when a Codex or opencode cell exists. That is round 1.2's,
and `rietx skill --install <workspace> --agent <name>` makes it a one-line
change to the episode setup.

## Results — round 1.1

Not yet run. Registered 2026-08-29.

---

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

**Provenance.** Both files come from the maintainer's own TOPAS workshop
dataset, `zrmo2o8_vt.zip`, fetched 2026-08-20 from
`http://topas.webspace.durham.ac.uk/wp-content/uploads/sites/261/2026/04/zrmo2o8_vt.zip`.
It is **not committed anywhere in this repo** and is not test data: re-running
this round means fetching it again. Nothing in the package or the suite depends
on it, so a dead link costs this protocol its episode and nothing else.

Nothing else in the workspace. No CIFs — the structures are inline in the
`.inp`, exactly as the transcript agent found them. The helper python scripts shipped in the same zip
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
