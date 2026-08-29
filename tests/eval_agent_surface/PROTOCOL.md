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

### Amendment, 2026-08-29, made between the pilot's two runs

Declared here rather than versioned, on 1.0's precedent: it changes how cells
are **isolated**, not what is measured, which cell is under which condition, or
what the package does.

**A cell's work can outlive its session, and the next cell then inherits it.**
The first pilot run put a 68-pattern chain in the background, wrote its answer
without waiting for it, and `refine_sequential` went on writing for **127.6 s
after `claude -p` had returned** — into the launch of the run after it. Wall
clock is R1, R5 and R8's unit, so `runner.launch` now waits for the trace to be
silent for 20 s before it returns, and records `outlived_session_seconds` in the
cell's own record. Two consequences for reading this round's numbers:

- `ramp-bare-sonnet` and `ramp-skill-sonnet` **overlapped by up to 127.6 s** and
  their wall clocks are quoted with that said. Every later cell is isolated.
- **Collect after quiet, never at the exit code.** A trail read while a
  backgrounded chain was still running showed 5.7 s of refinement where the
  finished log shows 193.5 s: the outermost rows are written on completion, so
  an early read sees the children and none of their parents.

### Amendment, 2026-08-29, made after the ramp episode and before the reel

Declared here rather than versioned, on the same footing as the amendment
above: it changes whether a run **survives** an edge case, and how the
projection **prints**, not what is measured, which cell is under which
condition, or what the package does. It came out of the review pass over the
session that completed E-RAMP.

The **shim** gained two guards. `os.getcwd()` raises once the working directory
has been deleted under the process, which an agent running a script from a temp
directory it then removes will do; that call sits in `_emit`, which `traced`
calls from a `finally`, so an unguarded raise would break the run the tracer
promises never to break. `json.dumps` is guarded the same way and drops the row
instead. This is the one change that touches the instrument the outstanding
cells will be prepared with, so it is stated plainly rather than folded in:
**E-RAMP's four cells were traced by the unguarded shim and E-ZRM's four will be
traced by the guarded one.** It cannot bias a comparison between them, because
the guard can only fire where the unguarded shim would have **aborted the run** —
where it fires there is no number to compare against, only a lost cell. `cwd` is
recorded in every row and read by no read-out.

The **runner** writes a cell's record as soon as `claude -p` returns and rewrites
it after the quiet wait, so a crash during a wait that may last half an hour no
longer loses the session id of a run that has already been paid for; it
validates `--zrm` and the two third-party filenames before `build_venv` spends
minutes, which is what `check_unprepared` already claimed; and E-RAMP's prompt
now interpolates its three numbers from `episodes/ramp.py` rather than restating
them. The rendered prompt is **byte-identical** to the registered text, asserted
in `test_runner.py` against this document's copy, so no cell's brief changed.

The **projection** also gained **R1b, the plan each agent named**, printed
beside R1. It is a projection and not a new condition: the shim has recorded
`plan` as a value keyword since registration, so every cell that has run is
re-projected identically and no cell was measured differently. It is added
because the plan turned out to carry most of the cost spread R1 reports (25×
per pattern-fit), which left R1 unreadable without it, and because the plan an
agent chooses is itself downstream of the condition rather than a nuisance
parameter — see § What the R1 table does and does not support. The alternative,
**fixing the plan across cells, is refused**: it would hold constant one of the
things the round exists to see, and no deployment fixes it either.

The **projection** prints R7 to two decimals, and marks R8's share OVERSTATED
where a traced process left an `import` row and no `exit` row — a process killed
rather than exited contributes to the numerator and not the denominator. No
ramp cell trips it: all four record **more** exit rows than import rows, which
is the design, since the `atexit` hook is registered by the `.pth` for every
interpreter that loads it whether or not it goes on to import `rietx`.

Re-scored after all of it, the four ramp cells return **identical** numbers on
every row of R1, R7 and R8.

### A known limit of R8's numerator, left alone until the round ends

`import_dt` is measured from the `.pth` — interpreter start — to the end of
`rietx`'s execution, so it absorbs whatever the process did *before*
`import rietx`: a driver that parses arguments, reads files or imports numpy
first inflates the floor. § R8 declares the numerator to be `import rietx`, and
this is wider than that.

It is **not corrected mid-round**. The shim is copied into each cell's venv at
`prepare`, so changing it now would measure the six outstanding cells
differently from the two that have run, which is the one thing a round may not
do to itself. Fix between rounds, by timing from the start of `exec_module` or
by emitting `exec_dt` beside `import_dt`.

And one defect this round cannot fix: **the harness is Claude Code's**.
WP-1304's harness-neutral claim is tested structurally in that WP and
behaviourally only when a Codex or opencode cell exists. That is round 1.2's,
and `rietx skill --install <workspace> --agent <name>` makes it a one-line
change to the episode setup.

## Results — round 1.1, pilot of 2026-08-29

**Two of the eight cells ran**, both `sonnet` on the simulated ramp, one per
condition. That is **N = 1 per condition**, one rung below what the protocol
registered, so nothing here is a rate and nothing here is a disagreement
either: a single observation cannot be split. The six remaining cells — both
`opus-5` ramp cells and all four reel cells — are outstanding, and the reel's
two data files are staged for them.

> This section records what was known when the pilot ran and is left as
> written. The two `opus-5` ramp cells have since run: § Results — round 1.1,
> the ramp episode complete supersedes its statement of what is outstanding,
> and revises how the `bare` condition may be read at all.

Build `1.3.0.dev0` in both (R9). Machine rows from `score_1_1.py`, hand rows
from the transcripts.

### R1 — the price of an answer

| | baseline 2026-08-26 | `ramp-bare-sonnet` | `ramp-skill-sonnet` |
| --- | --- | --- | --- |
| model, brief | opus-5, primed | sonnet, unprimed | sonnet, unprimed |
| API calls | 90 | 36 | 55 |
| cache-read | 14.6 M | 3.12 M | 4.74 M |
| mean context | 168 k | 90 k | 88 k |
| output | 87 k | 31 k | 44 k |
| wall | 34.7 min | 7.5 min | 10.5 min |
| refining | 34 s (1.6 %) | 193.5 s (43 %) | 17.5 s (2.8 %) |
| tool calls, errored | 91, 19 | 42, 5 | 57, **1** |
| cost | not recorded | $1.44 | $1.88 |

The baseline row is a **different model, a different brief and a different
build**, so the comparison is a before-and-after and is quoted as one. The
within-round contrast is the last two columns, and it is one run each.

### R11 — the stopping criterion, and the result that outranks the table

`ramp-bare-sonnet` ended on **none — waiting**. Its closing message is that
the chain "is running in the background … I'll report back with the full
trajectory and reliability flags once the chain finishes", and the session
returned 127.6 s before that chain finished. It is cheaper than the baseline
partly because it never delivered an answer.

`ramp-skill-sonnet` ended on **a §4b deliverable row**, and on the trajectory
row specifically: the step re-measured cold by `verify_discontinuities`
(ratio 1.00×), forward and backward agreeing, a stated 2θ-scale anchor ("no
calibration standard was in this dataset … the absolute scale carries an
un-anchored offset") and the precision/accuracy split, plus a Bérar-Lelann
inflation of 1.58 to apply to any quoted esd. Its "would not quote" list names
five things and a reason for each. This is the first time in any round or
campaign that a run has stopped on a §4b row: the campaign's six refining runs
scored 0 on that criterion, and the baseline built its own rules because §4b
had no trajectory row to reach for.

**The two runs are not both better at the same thing.** The bare run built the
second phase into the model and found CaF₂; the skill run fitted the high-T
half with a one-phase model, called the extra lines "a hint, not an
identification", and recommended indexing them. Better epistemics, worse model,
in the run that delivered.

### R2 — surfaces reached

Both reached `capabilities()`, `SeriesResult.summary(deliverable="series")`,
`verify_discontinuities=True` and `direction="both"`. The bare run also reached
`Refinement.suggest`, `Refinement.summary(deliverable="structure")` and
`Refinement.report`; the skill run also reached `Refinement.set_vary` and read
the skill's `references/series.md` through the harness's own Skill tool.

The three checks WP-1305 turned into calls were **all three made as calls** by
both runs. The 2026-08-26 agent did all three by hand.

### R3 — discovery errors

Five errored calls in the bare run, of which **two** are discovery
(`No module named 'rietx.plans'`, and a pydantic model constructed
positionally); one is environmental (`bin/pip` absent from a `uv` venv) and two
are not rietx's. **One** in the skill run, and it is not a discovery error. The
baseline had nine discovery errors of nineteen.

Source hunts went the other way: the bare run read the skill and the wheel's
own files, the skill run read `src/rietx/refine.py` and `strategy/staged.py` to
learn how a parameter is held — a question §4b does not answer and the skill
does not carry.

### R5 — the flat direction

`PHASE_UNCONSTRAINED` fired **82 times** in the bare run's chain, and the whole
68-pattern both-directions chain with cold verification finished in **187.7 s**.
The same absent phase cost the baseline 27 % of a 35-minute session and, on
reproduction without bounds, more than 115× that. Nothing ran away in either
cell.

### R7, R8, R10

R7: **1.8** Bash calls per fit in the bare run, **1.4** in the skill run; the
baseline's 87 Bash calls sat over one chain. R8: the floor is a cold-start
question — the first `import rietx` in a fresh venv cost **14.8 s**, the next
**0.53 s**, and per run the import total was 21.6 s of 220.9 s (9.8 %) and
28.5 s of 50.2 s (56.8 %). R10: the bare run **backgrounded** its chain, wired
`progress="series_progress.log"` and tailed it once; the skill run did not
background anything.

### What the pilot says about its own instrument

**The `bare` cell is not bare, and this is the round's first correction to
itself.** Within its first minute that agent ran `rietx skill --path`, read the
wheel's forwarding stub at `rietx/data/AGENT_PROTOCOL.md`, and read
`site-packages/rietx/data/skill/rietx/SKILL.md` and three of its reference
files. The skill ships **inside the wheel**, so no workspace can withhold it.
The condition therefore separates *the harness offering the skill* from *the
agent finding it in the package* — not instructions from no instructions — and
every R6 row is to be read that way. It is a finding rather than only a defect:
WP-1304's claim is that the skill is findable, and an agent with no reason to
expect one found it unprompted from an empty directory.

Both runs also read the maintainer's checkout at `/Users/yue/Code/rietx/src`,
which is on the machine and outside the workspace. A cell cannot be sealed from
it here; the reel cells should run with that in mind.

## Results — round 1.1, the ramp episode complete, 2026-08-29

Both `opus-5` ramp cells ran after the pilot, **isolated**: each `launch` held
until the trace had been silent for 20 s, and both recorded
`outlived_session_seconds` **0.0**, so neither overlapped the other or anything
after it. The ramp episode is therefore at the **N = 2 per condition, one run
per model** the protocol registered. The four reel cells are still outstanding.

Build `1.3.0.dev0` in all four cells (R9). Machine rows from `score_1_1.py`,
hand rows from the transcripts.

### R1 — the price of an answer, four cells

| | baseline 2026-08-26 | `bare-sonnet` | `skill-sonnet` | `bare-opus5` | `skill-opus5` |
| --- | --- | --- | --- | --- | --- |
| model, brief | opus-5, primed | sonnet, unprimed | sonnet, unprimed | opus-5, unprimed | opus-5, unprimed |
| API calls | 90 | 36 | 55 | 79 | 35 |
| cache-read | 14.6 M | 3.12 M | 4.74 M | 8.95 M | 3.07 M |
| mean context | 168 k | 90 k | 88 k | 116 k | 92 k |
| output | 87 k | 31 k | 44 k | 77 k | 60 k |
| wall | 34.7 min | 7.5 min | 10.5 min | 20.1 min | 17.3 min |
| refining | 34 s (1.6 %) | 193.5 s (43 %) | 17.5 s (2.8 %) | 253.7 s (21.0 %) | 227.0 s (21.9 %) |
| tool calls, errored | 91, 19 | 42, 5 | 57, **1** | 78, 5 | 38, 8 |
| cost | not recorded | $1.44 | $1.88 | $8.50 | $4.43 |

Every cell is cheaper than the baseline on every price row, and the dearest of
the four still cost 12 % fewer API calls and 39 % less cache read than a
baseline that was **primed with the protocol**. The baseline is a different
model, brief and build, so that stays a before-and-after rather than a contrast.

### What the R1 table does and does not support

The table above is honest as *what each run cost*. It is *not* a measure of
efficiency, and three of its rows carry a confound large enough to swamp what
they are being read for.

**Refinement seconds are a plan choice, not a model property, and the plan
spans 25×.** Measured per pattern-fit across all four cells:

| plan | s per pattern-fit | where |
| --- | --- | --- |
| `mccusker_default` | 0.057 – 0.086 | every cell, **both models** |
| `lab_bragg_brentano` | 0.731 | `bare-sonnet` |
| the agent's own plan object | 1.843 | `bare-opus5`'s 204.6 s chain |

`mccusker_default` lands in the same 0.06-0.09 s band under `sonnet` and
`opus-5` alike, so the arithmetic is not what separates the cells: **the preset
is**, and after it the number of chains each agent chose to run (1, 2, 4 and
11). `skill-sonnet`'s 17.5 s is not a truncated run — its chain carries **192
nested pattern-fits**, a full 68-pattern both-directions chain with cold
verification, at 0.060 s/fit. Read the refinement row as "what this agent chose
to spend", never as thoroughness.

**The plan is a read-out, not a confound to control away** — printed as R1b,
counting outermost calls only, since a chain resolves its preset once and hands
the object down:

| cell | the plans it named |
| --- | --- |
| `bare-sonnet` | `profile_only`×10, `lab_bragg_brentano`×7 |
| `bare-opus5` | `profile_only`×12, `lab_bragg_brentano`×6, **unnamed plan object×33** |
| `skill-sonnet` | `profile_only`×18, **`mccusker_default`×9**, `lab_bragg_brentano`×3 |
| `skill-opus5` | `profile_only`×802, **`mccusker_default`×45**, `lab_bragg_brentano`×2, `mccusker_structural`×1, unnamed×1 |

**Neither `bare` cell ever named `mccusker_default`; both `skill` cells did**,
and `bare-opus5` hand-built 33 plan objects where `skill-opus5` built one. So
the 25× is not noise sitting on top of the measurement — it is plausibly *part
of what the measurement found*, because which plan an agent reaches for is
downstream of the guidance under test. Fixing the plan across cells would hold
constant one of the things this round exists to see, and **nothing in the field
fixes it either**: an agent in deployment picks its own. The reel cells
therefore leave it free, and R1b is what makes the cost rows readable.

Two limits on that reading, since it rests on four runs with no replicate. It
is an observation, not a rate. And it tracks the **workspace install** rather
than access to the guidance, because all four cells read the guidance in the
end; the `bare` pair only found it later, by hunting. The honest statement is
that having it offered up front, rather than found halfway through, is what
appears to change which tool the agent picks.

**Wall clock is dominated by agent time.** Refinement is 21.0 % and 21.9 % of
the two `opus-5` cells' wall. The rest is turns and output: 77 k and 60 k output
tokens against `sonnet`'s 31 k and 44 k.

**`bare-sonnet` did not deliver**, so its $1.44 and 7.5 min price a partial
session and do not belong beside three that finished.

**The two `sonnet` cells' wall clocks are contaminated and the two `opus-5`
cells' are not.** `bare-sonnet`'s chain ran 127.6 s into `skill-sonnet`'s
session; every later cell recorded `outlived_session_seconds` 0.0. So a
`sonnet`-against-`opus-5` wall comparison sets a contaminated pair beside a
clean one, and the amendment that fixed it arrived between them.

**What survives as comparable** across all four: the same data, prompt, build
and machine, and therefore **R2** (which surfaces were reached) and **R11** (how
each run stopped) — both behavioural, and neither a function of how much work an
agent chose to do. The baseline shares only the data: different model, brief,
build and harness. And N = 1 per (model, condition), with no replicate anywhere.

### R6 — the condition, and a disagreement on every price row

| row | sonnet: bare → skill | opus-5: bare → skill |
| --- | --- | --- |
| API calls | 36 → 55 (worse) | 79 → 35 (better) |
| wall | 7.5 → 10.5 min (worse) | 20.1 → 17.3 min (better) |
| cost | $1.44 → $1.88 (worse) | $8.50 → $4.43 (better) |
| errored calls | 5 → 1 (better) | 5 → 8 (worse) |

**The condition's sign flips with the model on all four rows**, and the two
price directions are opposite to the two error directions. Under § Decision
rules this is reported as a disagreement with both models named, and no rate is
quoted. What the four cells jointly support is weaker and worth stating on its
own: the spread between the cheapest and dearest cell is 2.4× in calls and 5.9×
in money, and *the model chosen accounts for more of it than the condition does*.

### R11 — three of four stopped on a §4b row, and why that is not a condition effect

| cell | stopping criterion stated |
| --- | --- |
| `bare-sonnet` | **none — ended waiting** on a chain that had not finished |
| `skill-sonnet` | **a §4b deliverable row** (trajectory) |
| `bare-opus5` | **a §4b deliverable row** (trajectory) |
| `skill-opus5` | **a §4b deliverable row** (trajectory) |

Against 0 of 6 in the contributor's campaign, 0 in round 1.0 and a baseline that
built its own rules because §4b had no trajectory row to reach for. All three
名 that stopped there did what the row asks: each number quoted names the one
thing that would have to be wrong for it to be wrong, and that thing was
checked. `bare-opus5` carried the longest such list of the round, nine items,
ending "I would report the observations and stop there. The frozen CaF₂ cell is
the specific thing I would want explained before publishing any of this."

**This cannot be read as an effect of the condition, because no cell was
without the skill.** All four read it (§ What the ramp episode says about its
own instrument). The count says the §4b row is reachable and gets used; it does
not say a workspace install is what put it there.

### The destination, recorded against every run and scored in nothing

§ What is not being scored requires the episode's known truth to be recorded
against every run, precisely because "it is worth seeing whether a stated
criterion sits over a wrong answer". E-RAMP's truth, which no agent was told:
a(25 °C) = **10.2570 Å**, α_a = **8.0 ×10⁻⁶/K** below the step, a first-order
step of **+0.16 % at 430 °C**, α_a = **11.0 ×10⁻⁶/K** above it, a CaF₂ phase
absent below the step and growing to a plateau over 90 K, its cell **held at
5.4631 Å** (the deliberate trap), and a **CuKα doublet** source.

| | a(25 °C) | α_low | α_high | the step | CaF₂ |
| --- | --- | --- | --- | --- | --- |
| truth | 10.2570 | 8.0 | 11.0 | +0.16 % at 430 °C | 5.4631, held |
| `bare-sonnet` | — | — | — | "~430-440 °C" | seen, not fitted |
| `skill-sonnet` | 10.2568 (**−20 ppm**) | 8.0 ✓ | not quoted | 430→440 ✓ | "a hint, not an identification" |
| `bare-opus5` | 10.25736 (**+36 ppm**) | 8.01(6) ✓ | 10.89(11) | 435 ± 5 °C ✓ | 5.4633 (**+37 ppm**), trap named |
| `skill-opus5` | 10.24914 (**−770 ppm**) | 8.02(7) ✓ | 10.96(11) ✓ | 430→440 ✓ | identified, plateau ✓ |

Every cell that quoted a trajectory got the **shape** right: both legs' expansion
coefficients, the step's position within its own stated error, and its size to
better than 3 %. The absolute is where they part, and the reason is the source
model. `bare-opus5` tested the doublet against a single line and kept the
doublet, which is the truth, and lands **+36 ppm** on the absolute cell. It also
recovered the frozen CaF₂ cell to +37 ppm and named it as the thing it would
want explained before publishing — the trap, caught.

`skill-opus5` concluded there is **no Kα2**, which is wrong, and its absolute
cell is **−770 ppm** in consequence. What it then did is the part worth keeping:
it refused to quote the absolute at all, and named λ = 1.54178 Å as the
alternative that "puts the 25 °C cell exactly on the published 10.257(1) Å" —
which is the right answer. **Its caveat covers its error exactly.**

Two things follow, and neither is a read-out.

- **A stated stopping criterion sat over a wrong number, and the criterion
  still did its job.** This is the case § What is not being scored was written
  to catch, and it argues for WP-1305's rows rather than against them: the run
  was wrong about λ and correct about *what it could not quote without an
  anchor*, which is the §4b trajectory row's actual demand.
- **The best epistemics and the best physics were different cells.** R11 ranks
  `skill-opus5` and `bare-opus5` together; against truth `bare-opus5` is the
  better answer on every row. No read-out in this round can see that, by
  design, and the pilot's "neither cell is better at everything" holds at
  `opus-5` with the roles swapped.

### R2 — surfaces reached, and three that nothing reached

All four cells reached `capabilities()`, `Refinement.report`,
`SeriesResult.summary(deliverable="series")`, `verify_discontinuities=True` and
`direction="both"`. **The three checks WP-1305 turned into calls were made as
calls by all four**, where the 2026-08-26 agent made all three by hand.
`Refinement.suggest` was reached once, by `bare-sonnet` alone.

Three surfaces were reached by **no cell**, and they fail differently:

- **`viz.plot_result`, `viz.plot_for_vlm`, `viz.write_html` — zero calls.**
  Every 1.1 workspace installs `rietx[viz]` *precisely so these are usable*,
  which was 1.1's declared fix for a 1.0 defect (§ This round's own
  instrument). The fix did not take. The one cell that plotted, `bare-opus5`,
  wrote matplotlib by hand against the machine's user-level `yue-figure-style`
  skill, then read its own three PNGs. Making the library present did not make
  the package's plotting surface the obvious way to draw.
- **`help_for`, `help_key_for`, `help_registry` — zero calls.** WP-1202's help
  surface went unreached by four agents across two models, both conditions.
- **`index_pattern` — zero calls**, though `skill-opus5` identified the second
  phase by indexing three unmatched lines **by hand** (d ratios √(3:8:11),
  F-centred cubic, a = 5.459 Å). An agent that wanted indexing did it itself.

`read_recipe` and `write_recipe_tables` were also unreached, but E-RAMP ships no
recipe file, so WP-1306's surface is **not testable in this episode**; the reel
cells, which carry a `.inp`, are where that read-out exists.

### R5, R7, R8, R10

**R5.** `PHASE_UNCONSTRAINED` held the absent phase in **40 of 68** patterns in
both `opus-5` cells, by their own reports, and 82 firings in `bare-sonnet`.
Nothing ran away in any of the four: the whole both-directions chain with cold
verification cost 187.7 s in the pilot, and total refinement was 253.7 s and
227.0 s in the two `opus-5` cells. The same absent phase cost the baseline 27 %
of a 35-minute session, and more than 115× that on reproduction without bounds.

**R7**, Bash calls per outermost fit: 1.82, 1.40, 1.35 and **0.04**.
`skill-opus5`'s figure is the interesting one: 37 Bash calls over 852 fits,
because that agent looped inside one script instead of spending a shell call per
fit. The scaffolding ratio is smallest where the surface worked, which is why
the scorer prints two decimals rather than rounding it to `0.0`.

**R8**, the per-process floor: 9.8 %, 56.8 %, 8.5 % and 14.2 % of process wall.
The floor is a cold-start question, and the two numbers that bracket it are
unchanged: the first `import rietx` in a fresh venv costs **14.8 s**, the next
**0.53 s**. § A known limit of R8's numerator still applies to all four.

**R10.** `bare-opus5` backgrounded three times, wired a progress file and read
three plots while waiting; it is the first cell in any round here to background
a fit **and deliver**. `bare-sonnet` backgrounded its chain and ended waiting.
Neither `skill` cell backgrounded anything: both ran the chain in the
foreground and finished inside it.

### What the ramp episode says about its own instrument

**No cell was without the skill, and the two `bare` cells reached it by
different routes.** First reference, by transcript record index:

| cell | first skill reference | route |
| --- | --- | --- |
| `skill-opus5` | record 23 | `.claude/skills/rietx/` in the workspace |
| `skill-sonnet` | record 26 | `.claude/skills/rietx/` in the workspace |
| `bare-opus5` | record 43 | `find` over the **maintainer's checkout**, then `docs/skill/rietx/SKILL.md` |
| `bare-sonnet` | record 51 | `rietx skill --path`, then the **wheel's** copy in site-packages |

The pilot's correction stands and is now doubled. The two leaks are not the same
kind, and the round's conclusions depend on telling them apart:

- The **wheel's** copy is a property of the shipped package. Every deployment
  has it, so a `bare` cell that finds it there is measuring what a real unprimed
  user would meet. That is a finding in WP-1304's favour: the skill is findable
  by an agent with no reason to expect one.
- The **checkout's** copy is a property of this machine, and no user has it.
  It is contamination, not a deployment fact.

Both are recorded rather than repaired: 1.1 is registered, and measuring the
outstanding cells differently from the four that have run is the one thing a
round may not do to itself. The consequence for reading this round is fixed and
should not be softened later: **the registered contrast between `skill` and
`bare` is not measurable on this machine.** What the four cells do measure is
*route and latency* — the workspace copy is reached about twice as early in the
record stream (23, 26 against 43, 51), and reached without a hunt.

Round 1.2 owes a sealed workspace. Until it has one, a `bare` cell means "the
skill was not offered", never "the skill was not available".

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
