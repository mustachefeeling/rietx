# WP-1307 — Re-capture: surface round protocol 1.1

Milestone: v1.3 · Status: 🔄 2026-08-29 — protocol 1.1 registered and its harness green; 2 of 8 cells run as a pilot, six outstanding
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
- [ ] The runs (cost recorded per cell). **2 of 8 run 2026-08-29** as a pilot the
      maintainer scoped: `ramp-bare-sonnet` ($1.44) and `ramp-skill-sonnet` ($1.88),
      both `sonnet` on the simulated ramp, one per condition. Outstanding: both
      `opus-5` ramp cells and all four reel cells, whose two data files are staged at
      `~/rietx-agent-runs/2026-08-29-round-1-1/zrm-source/`.
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
