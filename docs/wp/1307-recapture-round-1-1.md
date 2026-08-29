# WP-1307 — Re-capture: surface round protocol 1.1

Milestone: v1.3 · Status: 🔄 2026-08-29 — protocol 1.1 registered and its harness green; E-RAMP complete at N = 2 per condition (4 of 8 cells), the four reel cells outstanding
Depends on: 1301-1305 (the milestone's acceptance; 1306 is measured by its own fixtures)

## Goal

One measurement, registered before it runs, that says whether 1301-1305 changed what an
agent pays and how it decides it is done: API calls, cache-read tokens per call, wall
clock against refinement seconds, discovery errors, surfaces reached, whether a flat
direction fired, and the stopping criterion the agent states.

## Context

- **The baselines it is compared with.** The ramp run (2026-08-26, one Opus 5 agent,
  primed with the protocol): 90 API calls, 14.6 M cache-read tokens (mean context
  168 k), 87 k output, 34.7 min wall for 34 s of refinement, 9 discovery errors + 4
  source hunts, none of the built surfaces used, a flat direction fired (27 % of wall).
  The contributor's campaign (2026-08, 86 runs, 5,430 tool calls; six runs that refined,
  all briefed by one coordinator): stopping criteria 0 on a §10 condition / 0 on a §4b
  row / 0 on an index alone / 1 external comparison / 1 script exit / 1 instruction / 3
  ended waiting; `suggest` 0, `plot_for_vlm` 0, `report()` 2. WP-1110's round 1.0
  (`tests/eval_agent_surface/PROTOCOL.md`): R1 0/2, R2 split, the schema export called
  zero times in 235 interpreter starts.
- **What the ramp and the campaign cannot show, and this round must.** The ramp was
  n = 1 on data simulated by rietx's own forward model with a prompt in the protocol's
  vocabulary; the campaign's workers were briefed with the rules restated inline (the
  obvious confound for every instruction-source read-out) and ran a stale release
  (1.0.1) for a week. So: unprimed prompt, real data with a known systematic, the build
  recorded, and the coordinator-plus-workers shape **recorded as an observed deployment,
  not run as a condition**: the single cold agent is the cell whose brief the protocol
  controls.
- **The build boundary.** A round run after 2026-08-29 does not pool with one run
  before it on any row that turns on what the agent could read: 1304 replaced the single
  `AGENT_PROTOCOL.md` with a `skill/` tree opened on demand, and 1301-1305 moved the
  package under it. Both baselines above are therefore **pre-1.3** by construction, which
  is the comparison this round wants. Re-measuring the ramp baseline is cheap — the
  agent's own protocol is preserved at
  `~/rietx-agent-runs/2026-08-26-insitu-ramp/verify_1305.py` and the 68-pattern chain runs
  in 11.6-12.0 s — so a moved refinement second is separable from a moved agent second.
- **Design.** `PROTOCOL.md` → **1.1** (the shim's target list changes, so the bump is
  mandatory). Episodes: E-ZRM (kept; real, 82 scans, four phases) and E-RAMP (the ramp
  generator committed to the harness as `episodes/ramp.py`, synthetic, known truth).
  Condition: the skill installed in the workspace by `rietx skill --install` (both
  directories) versus not; environmental, never a prompt sentence. Prompt unprimed (no
  protocol vocabulary). Shim targets: drop `agent.*`; add `Refinement.suggest`,
  `Refinement.summary`, `read_recipe`, `help_for`, `capabilities`,
  `SequentialRefinement.fit`, `plot_for_vlm`. Two of those are corrections rather than
  additions: WP-1303's four JSON-envelope entries are already gone from
  `rietx_surface_trace.py` (a target that cannot be reached is a read-out that cannot
  fail), and `SequentialRefinement.run` — traced by 1.0 — **no longer exists**; the class
  exposes `.fit` (measured 2026-08-29), so 1.0's list would have scored a rename as a
  surface nobody reached. `score_round.py` scores round 1.0 and says so in its docstring:
  1.1 declares its own read-outs and gets its own scorer, and 1.0's records stay unedited
  because a pre-registered round is not rewritten once it has run. The projection script from the audit
  committed as `tests/eval_agent_surface/trail.py`: one line per tool call; usage summed
  **once per `message.id`, last record wins** (a thinking block and its tool_use share
  an id; per-record summing over-counted cache reads by 151/90 in the first audit);
  **fit time attributed by where a fit ran**, from the shim's own trace of
  `fit`/`refine_sequential` wall clock inside each process, never from the command head
  (a driver script and a backgrounded job are then counted, which the campaign's
  projection could not do). N = 2 per cell, model as a variable (`sonnet` and `opus-5`),
  cost recorded; what N = 2 can say is written in the protocol as round 1.0 wrote it.
- **Read-outs.** R1-R6 as round 1.0 defines them, plus: **R7** Bash calls per fit (the
  scaffolding ratio); **R8** the per-process floor's share (import + kernel load, measured
  1.75-2.37 s on 2026-08-28, darwin `[dev]`); **R9** the build
  (`capabilities().package_version` in every episode's record); **R10** whether the agent
  backgrounded a fit and what it saw while waiting (the progress sink's first
  measurement); **R11** the stopping criterion the agent states, classified by hand from
  its closing text into: a §10 condition / a §4b deliverable row / an agreement index
  alone / an external comparison / a script exiting / an instruction / none (ended
  waiting), with whether `summary()` and `plot_for_vlm` were called and whether the agent
  looked at a plot it drew itself counted beside it. WP-1305 gave three of those a
  package-side answer, and each is a distinct observation because the 2026-08-26 agent
  did all three **by hand**: does the run print
  `SeriesResult.summary(deliverable="series")` (§4b's fourth row, which that agent wrote
  for itself across about 34 of its 90 calls); does it read `CandidateGroup.delta_bic`
  rather than running two refits per candidate to compute ΔBIC itself; does it reach
  `verify_discontinuities=True` rather than hand-refitting the step's two patterns cold.
  A re-capture that still does them by hand is a **discovery** failure, not a judgement
  one, and the read-out separates the two.
- **Second harness.** The eval shim is Claude Code's, so 1304's harness-neutral claim is
  tested structurally in 1304 and behaviourally only when a Codex or opencode cell exists;
  that is round 1.2's, and `rietx skill --install <workspace> --agent <name>` makes it a
  one-line change to the episode setup — it puts the skill where that harness looks, and
  `--list-agents` prints the fifteen-row table with each row's source URL and the date its
  directories were read.

## Non-goals

A rate quoted from N = 2. Changing what 1301-1305 built in response to this round's
numbers inside this WP (findings go to the milestone record and, if they earn one, a new
WP).

## Tasks

- [x] `PROTOCOL.md` 1.1: episodes, condition, shim targets, read-outs, registered before
      any run.
- [x] `trail.py` committed with the two attribution rules above and a test on a fixture
      transcript.
- [ ] The runs (cost recorded per cell). **4 of 8 run 2026-08-29**, which completes
      **E-RAMP at the registered N = 2 per condition**: `ramp-bare-sonnet` ($1.44),
      `ramp-skill-sonnet` ($1.88), `ramp-bare-opus5` ($8.50), `ramp-skill-opus5`
      ($4.43). The two `opus-5` cells were isolated (`outlived_session_seconds` 0.0
      each); the two `sonnet` cells overlapped by up to 127.6 s and are quoted with
      that said. Outstanding: **all four reel cells**, whose two data files are
      staged at `~/rietx-agent-runs/2026-08-29-round-1-1/zrm-source/` and which are
      the only cells where `read_recipe` is reachable at all.
- [x] The numbers in `docs/milestones/v1.3.md` § Acceptance and the decision on each
      WP's claim ("improved / unchanged / worse", by read-out) in the handover. The
      pilot's numbers are in the rolling narrative, which is where an in-flight
      milestone's numbers go; the per-WP judgement is in the handover below, and each
      one says what N it rests on.

## Acceptance

```sh
.venv/bin/python -m pytest tests/eval_agent_surface -n auto --dist loadgroup   # the harness's own tests
```

The round's numbers in the milestone record; no rate quoted from N = 2; each WP's claim
judged by read-out.

## References

- WP-1110 and `tests/eval_agent_surface/PROTOCOL.md` 1.0.
- The audit recipe: maintainer memory `agent-surface-audit-insitu-ramp` § How to
  interrogate a run; `~/rietx-agent-runs/rietx-agent-transcripts/bundle.py` (the HTML
  projection of the campaign).

## Handover log

### 2026-08-29 (2nd session) — the ramp episode complete, and a contrast withdrawn

Both `opus-5` ramp cells run; E-RAMP complete at the registered N = 2 per
condition. Four of eight cells done, four reel cells left.

The maintainer scoped this session to the two `opus-5` ramp cells. They ran
serially and **isolated**: each `launch` held for 20 s of trace silence and
both recorded `outlived_session_seconds` **0.0**, so the overlap that cost the
pilot up to 127.6 s did not recur and needs no allowance here.

Three of the four cells now stop on a §4b deliverable row, all four make
WP-1305's three checks as calls, and the condition contradicts itself between
the two models on every price row. The finding that governs the rest of the
round is smaller and worse: **no cell was without the skill**, so the
registered contrast was never measurable on this machine.

Checked against the episode's known truth afterwards, every cell that quoted a
trajectory got the shape right and they part only on the absolute cell. The run
that stopped best was **not** the run that was most right: it was wrong about the
wavelength by 770 ppm and refused to quote the number that error would have
spoiled, while the run beside it kept the doublet and landed 36 ppm out. And the
R1 cost table is a record of what each run *chose to spend*, not of efficiency —
the plan preset alone moves the refinement seconds 25×.

**Done.** Ran, collected and scored `ramp-bare-opus5` ($8.50, 79 API calls,
20.1 min, 253.7 s refining) and `ramp-skill-opus5` ($4.43, 35 calls, 17.3 min,
227.0 s). `PROTOCOL.md` gains § Results — round 1.1, the ramp episode
complete as a **pure insertion**, 154 lines, nothing deleted: the pilot's
record and round 1.0's text are byte-identical below it, and the pilot section
carries a forward pointer rather than a rewrite, because a registered round is
not rewritten once it has run. `runner.py`'s docstring now declares **both**
routes by which a `bare` cell reaches the skill, as measured inheritances.
`score_1_1.py` prints R7 to two decimals.

**Measured** (darwin, this worktree's own `[dev]` venv; the cells' venvs are
`[viz]`, build `1.3.0.dev0` in all four). All counts are on **current `main`
merged into this branch**, not the bare branch: `origin/main` moved from
`7f81df11` to `0fadd4cf` under this session, which carries the previous
session's own PR #184.

- Acceptance, `pytest tests/eval_agent_surface -n auto --dist loadgroup`:
  **22 passed in 3.35 s** (41 with `test_docs_consistency.py`).
- Fast suite, `-m "not slow"`: **3554 passed, 122 skipped in 2:06**, alone on
  the machine (`pgrep -f "[p]ytest"` empty before it started). That is the same
  pair the previous session measured on its final tree, which is the expected
  answer: **this session added no test**, so passed+skipped must not move, and
  it did not.
- `ruff check src tests examples` clean.
- Full suite **not run**: no `src/` file changed, and this WP is test- and
  docs-only. Its counts are CI's job.

| | baseline | `bare-sonnet` | `skill-sonnet` | `bare-opus5` | `skill-opus5` |
| --- | --- | --- | --- | --- | --- |
| API calls / cache-read | 90 / 14.6 M | 36 / 3.12 M | 55 / 4.74 M | 79 / 8.95 M | 35 / 3.07 M |
| wall / refining | 34.7 min / 34 s | 7.5 / 193.5 s | 10.5 / 17.5 s | 20.1 / 253.7 s | 17.3 / 227.0 s |
| tool calls, errored | 91, 19 | 42, 5 | 57, 1 | 78, 5 | 38, 8 |
| Bash per fit (R7) | 87 over one chain | 1.82 | 1.40 | 1.35 | **0.04** |
| stopping criterion | (primed) | **none — waiting** | **§4b row** | **§4b row** | **§4b row** |
| cost | not recorded | $1.44 | $1.88 | $8.50 | $4.43 |

**The decision on each WP's claim**, revised where the second model moved it.
Every row now rests on N = 2 per condition **for E-RAMP only**, and no reel
cell has run:

| WP | verdict | evidence, and what changed from the pilot |
| --- | --- | --- |
| 1301 | **improved**, unchanged | `PHASE_UNCONSTRAINED` held the absent phase in 40 of 68 patterns in both `opus-5` cells; nothing ran away in any of the four, against 27 % of the baseline's wall and >115× on reproduction |
| 1302 | **improved on R3; R11 now 3 of 4** | the pilot's split resolves toward the package criterion: both `opus-5` cells stated a §4b row, so only `bare-sonnet` ended waiting. Errored calls no longer favour one condition — 5/1 under sonnet, 5/8 under opus-5 |
| 1303 | **not testable, as registered** | unchanged; the alternative is deleted, recorded as observed |
| 1304 | **findable: confirmed four times. The registered contrast: withdrawn** | this is the revision. The pilot called the contrast "weaker than it looks"; four cells show it is **not measurable on this machine**. Every cell read the skill — two from the workspace, one from the wheel, one from the maintainer's checkout. The wheel route supports 1304's claim (a property of the shipped package); the checkout route is contamination (a property of this machine). What survives is route and latency: the workspace copy is reached about twice as early (records 23, 26 against 43, 51) and without a hunt |
| 1305 | **improved**, strengthened twice | all three checks made as **calls** by all four cells, and three of the four stopped on the §4b row they belong to. Strengthened again by the truth check: the one cell with a materially wrong number (−770 ppm on the absolute cell) is the cell whose §4b caveat **refused to quote exactly that number**, which is the row's demand rather than an accident |
| 1202 | **unreached** | not one of the five WPs under test, but the round measures it: `help_for`, `help_key_for` and `help_registry` were called by **no cell**, across two models and both conditions |
| 1306 | **not testable in this episode** | E-RAMP ships no recipe file, so `read_recipe` has no route. The reel cells carry the `.inp`; that read-out exists only there |

**The `viz` fix did not take.** 1.1 installs `rietx[viz]` in every workspace
*precisely* so `plot_result`, `plot_for_vlm` and `write_html` would be usable,
as its declared repair of a 1.0 defect. Zero calls to all three, in four
cells. The one cell that plotted (`bare-opus5`) wrote matplotlib by hand
against the machine's user-level `yue-figure-style` skill and read its own
three PNGs. Making the library present did not make the package's plotting
surface the obvious way to draw, and that is a finding for a WP rather than
for this round to act on.

**The destination, and what R1 does not support.** Both were added after the
maintainer asked why the `opus-5` runs were dearer and whether the four cells
are comparable at all; the first was owed from the start, since § What is not
being scored requires the truth recorded against every run.

Every cell that quoted a trajectory got the **shape** right — both expansion
coefficients, the step inside its stated error, its size to better than 3 %.
They part on the absolute cell, on the source model. `bare-opus5` kept the Kα
doublet, which is the truth, and lands **+36 ppm** on a(25 °C) and +37 ppm on
the frozen CaF₂ cell it named as the thing to explain before publishing: the
episode's trap, caught. `skill-opus5` concluded there is no Kα2, is **−770 ppm**
in consequence, refused to quote the absolute, and named the wavelength that
lands on the published value — **its caveat covers its error exactly**. So a
stated criterion sat over a wrong number and still did its job, which argues for
1305's rows, and **the best epistemics and the best physics were different
cells**, which no read-out here can see.

R1 is honest as *what each run cost* and is not a measure of efficiency.
Refinement seconds are a **plan** choice: per pattern-fit, `mccusker_default`
costs 0.057-0.086 s in every cell and both models against `lab_bragg_brentano`'s
0.731 s and 1.843 s for the plan object `bare-opus5` built — 25× before the
chain counts (1, 2, 4, 11) each agent chose. `skill-sonnet`'s 17.5 s is a full
68-pattern both-ways chain with verification (192 nested fits), not a truncated
one. Wall is dominated by agent time. `bare-sonnet` never delivered, so its
$1.44 prices a partial session. And the `sonnet` pair's wall is contaminated by
127.6 s where the `opus-5` pair recorded 0.0, so that comparison sets a dirty
pair beside a clean one. **R2 and R11 are what survive as comparable.**

**The plan is a read-out, not a confound to control away**, and the scorer now
prints it as R1b (outermost calls only, since a chain resolves its preset once
and hands the object down). Counting what each agent itself chose: **neither
`bare` cell ever named `mccusker_default` and both `skill` cells did**, and
`bare-opus5` hand-built 33 plan objects where `skill-opus5` built one. So the
25× is plausibly part of what the round found, not noise on top of it, because
which plan an agent reaches for is downstream of the guidance under test.
Fixing the plan across the reel cells was **considered and refused** on the
maintainer's point that nothing in the field fixes it: an agent in deployment
picks its own, and holding it constant would hold constant one of the things
the round exists to see. Two limits, on four runs with no replicate: an
observation, not a rate; and it tracks the workspace **install** rather than
access, since all four cells read the guidance in the end and the `bare` pair
only found it later by hunting. R1b is a projection, not a condition — the shim
has recorded `plan` since registration, so every cell re-projects identically
and none was measured differently.

**The review pass** (`/code-review medium --fix`) found eight and all eight
were taken; three matter beyond tidiness. The run record was written only
*after* `wait_quiet`, so a crash during a wait of up to half an hour lost the
session id of a cell already paid for. The shim's `os.getcwd()` sat outside
`_emit`'s `try` and `_emit` is called from a `finally`, so an agent running a
script from a temp directory it then deleted would have had the tracer break
the run it promises never to break. And `trail.render` still printed R7 at one
decimal after `score_1_1.py` had been fixed, which is the same defect surviving
in the second of two renderers.

Three were declined as noted-not-changed, and the reasons are in the review, not
here: a `transcript_for` slug that misses when the round root contains a dot
(the glob fallback covers it), the cell venv installing `-e` from the
maintainer's checkout (the `bare` leak this WP deliberately defers to round
1.2), and a speculative id collision. **One fix touched the shim**, which is the
instrument the four outstanding cells will be prepared with, so it is declared
as an amendment in `PROTOCOL.md` rather than folded in silently: E-RAMP ran on
the unguarded shim and E-ZRM will run on the guarded one, and the guard can only
fire where the old shim would have aborted the run outright. Re-scored after
every fix, the four ramp cells return **identical** numbers on every row of R1,
R7 and R8, and the rendered ramp prompt is byte-identical to the registered
text.

**In flight.** Four cells, all E-ZRM, at
`~/rietx-agent-runs/2026-08-29-round-1-1/` with data staged in `zrm-source/`.
A reel cell needs `--zrm ~/rietx-agent-runs/2026-08-29-round-1-1/zrm-source`
on `prepare`.

**Gotchas added to the pilot's.**
- **`prepare` both cells of a pair before launching either.** A `uv pip
  install` running beside a live cell competes for the CPU that cell's fit
  seconds are measured on, and fit seconds are R1 and R5's unit.
- **A `bare` cell is not sealed and cannot be here.** Beyond the wheel, the
  maintainer's checkout is on the machine; `bare-opus5` found the skill tree
  in it by `find`. Round 1.2 owes a sealed workspace before any `bare` row is
  read as an access claim.
- **R7 can round to zero.** 37 Bash over 852 outermost fits is 0.04, not
  "no Bash". The scaffolding ratio is smallest where the surface worked best,
  so the display had to hold a small number apart from zero.

**Next**, in order: the four reel cells with `--zrm`, serially and one pair at
a time (they are real 4-phase data on 82 scans, so budget above the ramp's
$1.44-$8.50), **leaving the plan free** as the ramp cells had it. Then re-score
and finish the round's table. The three questions the reel is the only place to
answer are `read_recipe`'s reachability, whether a `bare` cell on real data
still finds the wheel's skill, and whether the R1b split above survives four
more runs on data whose truth nobody knows.

- **2026-08-29** — protocol 1.1 registered, and two of its eight cells run.

  Given the same data and the same one-sentence task, the agent that had the
  skill in its workspace delivered a complete answer and said why it had
  stopped; the agent without it backgrounded a 68-pattern chain, wrote that it
  would report back once the chain finished, and returned two minutes before it
  did. That is the first run in any round here, or in the 86-run campaign, to
  stop on a §4b deliverable row rather than on an index, an instruction or
  nothing at all. Both runs made all three of WP-1305's checks as *calls* where
  the 2026-08-26 agent made them by hand, and the absent phase that cost that
  agent 27 % of its session cost these ones nothing. The round also corrected
  itself twice, both times from its own data: the "bare" cell is not bare,
  because the skill ships inside the wheel and that agent found it in under a
  minute, and a cell's work can outlive its session, which spoiled a reading
  before it was caught. Neither cell is better at everything — the one that
  delivered fitted the high-temperature half with a one-phase model and called
  the extra lines a hint, while the one that did not built the second phase in
  and identified it.

  **Done.** `PROTOCOL.md` 1.1 as a **pure prepend** — round 1.0's text is
  byte-identical below it, 369 lines added, nothing deleted. Eleven read-outs of
  its own, since three of 1.0's four are about a surface 1303 deleted on their
  evidence; only R4 keeps its number. Two episodes: 1.0's ZrMo₂O₈ reel unchanged,
  and the 2026-08-26 ramp, whose generator is committed at `episodes/ramp.py` and
  rebuilds that run's 68 patterns and `host.cif` **byte for byte in 1.8 s**
  (asserted, skipped where the preserved copy is absent). One environmental
  condition. Both prompts registered verbatim and pinned to `runner.py`'s copies
  by test, with a second test reading each for package vocabulary.
  `trail.py` is the audit's scratch script, committed with both attribution
  rules under test on a fixture; it reproduces the baseline transcript's numbers
  exactly. `runner.py` prepares a cell in 27 s — its own venv, the shim's log
  path baked into a `.pth`, the workspace holding data and nothing else.
  `score_1_1.py` prints the machine half of the read-outs and refuses to divide
  two cells into a rate.

  **Measured** (darwin, this worktree's own `[dev]` venv; the runs' venvs are
  `[viz]`, build `1.3.0.dev0`). Fast suite on this branch: **3553 passed, 122
  skipped, 1 failed in 2:08** — the failure was this session's own
  (`test_every_text_io_call_names_its_encoding`, four `read_text()` calls without
  an encoding); fixed, and the final tree measures **3554 passed, 122 skipped in
  2:05**, alone on the machine. The harness contributes **22 tests**, and
  `git ls-tree origin/main` shows no test file in that directory before this
  session, so the fast selection gains 22 passes and **no new skip**. No `main`
  baseline is quoted: this session did not measure one, and re-measuring `main`
  locally is CI's job (`tests/CLAUDE.md` § Running). Full suite **not run** — no
  `src/` file changed, and a test-only WP does not run it.
  Pilot cells, $1.44 and $1.88:

  | | baseline 2026-08-26 | `ramp-bare-sonnet` | `ramp-skill-sonnet` |
  | --- | --- | --- | --- |
  | API calls / cache-read | 90 / 14.6 M | 36 / 3.12 M | 55 / 4.74 M |
  | wall / refining | 34.7 min / 34 s | 7.5 min / 193.5 s | 10.5 min / 17.5 s |
  | tool calls, errored | 91, 19 | 42, 5 | 57, 1 |
  | stopping criterion | (primed, delivered) | **none — waiting** | **a §4b row** |

  Also: `import rietx` costs **14.8 s cold in a fresh venv, 0.53 s warm** (R8 is
  a cold-start question, and the WP's filed 1.75-2.37 s is between the two);
  `PHASE_UNCONSTRAINED` fired 82 times for nothing; 1.8 and 1.4 Bash calls per
  fit against the baseline's 87 Bash calls over one chain.

  **The decision on each WP's claim**, by the read-out the protocol named, each
  on N = 1 per condition:

  | WP | verdict | evidence |
  | --- | --- | --- |
  | 1301 | **improved** | R5: 82 `PHASE_UNCONSTRAINED`, chain finished in 187.7 s, no runaway, against 27 % of the baseline's wall and >115× on reproduction |
  | 1302 | **improved on R3, split on R11** | 2 discovery errors in the bare run and 0 in the skill run against the baseline's 9; but one run stated a package criterion and one ended waiting |
  | 1303 | **not testable, as registered** | the alternative is deleted; recorded as observed |
  | 1304 | **improved, and the read-out moved under it** | the skill was reached in *both* cells — in the bare one from inside the wheel, unprompted, in under a minute. "Findable" is confirmed twice over; the registered contrast is weaker than it looks |
  | 1305 | **improved** | all three checks made as calls by both runs, and one run stopped on the §4b row they belong to |

  **In flight.** Six cells outstanding: both `opus-5` ramp cells and all four
  reel cells. The reel's two files are staged at
  `~/rietx-agent-runs/2026-08-29-round-1-1/zrm-source/` (downloaded from the
  Durham workshop page, nine helper scripts withheld as 1.0 registered). Round
  root is `~/rietx-agent-runs/2026-08-29-round-1-1/`.

  **Gotchas.**
  - **Collect after quiet, never at the exit code.** A trail read while a
    backgrounded chain was still writing showed 5.7 s of refinement where the
    finished log shows 193.5 s: rows are written on completion, so an early read
    sees 225 nested fits and none of their parents. `launch` now waits for 20 s
    of silence and records `outlived_session_seconds`; the two pilot cells were
    launched before that landed and **overlapped by up to 127.6 s**.
  - **The workspace cannot withhold the skill.** It ships in the wheel, and
    `rietx skill --path` prints its directory. Whether the condition should be
    redesigned is round 1.2's question, not a mid-round change to 1.1.
  - **Neither cell was sealed from the maintainer's checkout**: both read
    `/Users/yue/Code/rietx/src`, which is on the machine and outside the
    workspace.
  - `prepare` refuses a non-empty workspace, so a re-run needs the directory
    removed; `--zrm DIR` is required for a reel cell.

  **Next**, in order: run `ramp-bare-opus5` and `ramp-skill-opus5` (serial,
  ~20-50 min, now isolated), because the pilot's sharpest row — one run
  delivered and one did not — is a single observation per condition and the
  second model is what makes it a disagreement or a direction. Then the four
  reel cells with `--zrm`. Then re-score and finish the round's table. Only
  after that is it worth asking whether the condition needs redesigning for 1.2,
  since the answer depends on whether the wheel's copy is reached in every cell
  or only by the two agents seen so far.

- **2026-08-28** — created, from the parked v1.3 plan.
