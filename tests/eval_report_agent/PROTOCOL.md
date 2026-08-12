# WP-1053 runner protocol — agent-in-the-loop FitReport eval

**Protocol version: 1.1** (`build_fixtures.PROTOCOL_VERSION`; stamped into
every `condition.json` and quoted by every run record).  Bump it on any
change that alters comparability: the prompt text, the overlay contract, the
answer schema, the scoring rules, the excerpt policy.

**1.1 (WP-1058)** moved two of those at once, deliberately: a report-on
response now carries `trajectory` — the report at every stage boundary, not
only at the converged state — and the §5 excerpt the report-on prompt quotes
now says to read it.  A 1.1 run therefore cannot be pooled with the 1.0
pilot's grid; it is the *new* delivery that WP-1059 measures, against the
same episodes and the same scorer.

One authority per fact: the prompt *text* lives in `build_fixtures._PROMPT`
(rendered by `render_prompt`), the enforcement lives in `run_refine.py`, the
grading lives in `scorer.py`.  This file is the protocol *around* them: what
runs, under which conditions, and how the outcome grid must be read.

## The question

Does the FitReport help a **real LLM agent** converge a refinement through
the shipped `agent.refine_json` surface?  Same episodes, real models, report
attached or stripped.  Falsifiable side hypothesis: if the report's value is
real, it should lift the weaker model most.

## Conditions

| | report-on | report-off |
|---|---|---|
| response | full FitReport attached, plus the per-stage `trajectory` (1.1) | `include_report=False` forced, `report` **and** `trajectory` stripped |
| prompt | shared prompt + AGENT_PROTOCOL §5/§6 verbatim excerpts | shared prompt only |

- **One shared prompt, no per-model tuning.**  Report-on gets the §5/§6
  excerpts because the manual ships with the feature; report-off gets
  neither the report nor the manual.
- **The shim, not the prompt, enforces the condition.**  An agent can ignore
  a prompt; it cannot un-strip a response.  The agent structurally cannot
  touch the pattern, the starting parameter values, or `include_report` —
  `overlay.json` admits `plan` / `mode` / `two_theta_limits` only.
- Every call runs from the same fixed perturbed start; iteration is **on the
  plan, not the state**.  The report from call N informs the overlay for
  call N+1.

## Pilot matrix

{report-on, report-off} × 2 models × 8 episodes, N=2 repeats on the
discriminating rows (E2, E5, E7, E8), N=1 elsewhere — 48 runs.  Effort is
pinned per run and recorded; a second effort tier is a follow-up pass once
the matrix runs clean, not part of this pilot.

**Why these rows discriminate** (state this beside every summary of the
grid): the lazy path — submit the request untouched, which runs the full
`mccusker_default` preset — already fixes E1/E3/E4/E6 without reading
anything.  The A/B therefore discriminates on E2 (displacement is in no
default-plan stage) plus the traps E5/E7/E8; E1/E4 are competence controls.
A null result on the easy rows is the *expected* result, not "the report
doesn't help".

## Running

Each run gets a fresh episode dir (its `calls.jsonl` is the run's record)
and the scorer-side truth tree stays outside the agent's workspace:

```sh
.venv/bin/python -m tests.eval_report_agent.build_fixtures \
    --episodes RUNS/<run-id> --truth TRUTH --condition report-on --only E2
```

Runs execute in the Claude Code harness — the Workflow `agent()` call takes
per-run `model` and `effort`.  Each agent receives exactly the episode's
`prompt.md` (plus the path to its episode dir) and nothing else; it drives
`run_refine.py` itself and writes `answer.json` when done.  Record the
harness-reported model ID and effort per run.

Score each run with:

```sh
.venv/bin/python -m tests.eval_report_agent.scorer RUNS/<run-id>/E2 TRUTH/E2.json
```

Grading rules the scorer pins (unit-tested in `test_scorer.py`):

- the **last successful** call is the answer state; recovery is the planted
  parameter at truth within the WP-1052 tolerance, never Δχ²;
- a planted path absent from `parameters` was never freed (the surface
  serialises vary-or-tie entries only) and scores not-recovered;
- traps grade on the verdict alone: E5 → `impurity_suspected`,
  E7 → `abstain`, E8 → `ambiguous`;
- no successful call, or no valid `answer.json` → failed;
- wrong-frees are descriptive localisation evidence, never pass/fail.

## Audit

`calls.jsonl` is the record — the call trace and count come from the shim's
log, never from the agent's self-report.  Spot-check at least one transcript
per condition × model cell for prompt-compliance (did the agent read the
response rather than invent numbers; did it write `answer.json` itself), but
grade only from the shim log + `answer.json`.

## Reading the grid

- Report the **dated raw outcome grid**: counts, never percentages from tiny
  N, never rounded up (the indexing-scoreboard rule).  Model IDs and efforts
  in the header.  It is a pilot establishing protocol soundness and effect
  direction, not a benchmark, and never a CI assertion — outcomes move with
  the models.
- Attach the discriminating-rows caveat (above) to every summary.
- **E3 can invert the sign**: the report's width emitters name only
  `lor_size`/`lor_strain` (proxy plateau χ²_red ≈ 4.3) while the lazy default
  frees `w` itself and reaches the ≈ 1.01 floor — on E3, following the
  report can lose to ignoring it.  State this beside the E3 row.
- **E6 invites a phantom phase**: the abstained report serves
  `add_impurity_phase` at confidence 0.9 (the reindex pointer lives only in
  its rationale/alternatives).  A report-on agent proposing an impurity on
  E6 is following the report; score what it does with that invitation and
  say so in the row — it is not a scorer surprise.
- E1/E4 rows are competence controls; failures there are harness or
  competence problems, not report signal.
