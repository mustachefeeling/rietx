# WP-1307 — Re-capture: surface round protocol 1.1

Milestone: v1.3 · Status: ⬜
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

- **2026-08-28** — created, from the parked v1.3 plan.
