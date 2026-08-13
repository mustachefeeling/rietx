# Runner protocol — agent-in-the-loop FitReport eval

**Protocol version: 1.1** (`build_fixtures.PROTOCOL_VERSION`; stamped into
every `condition.json` and quoted by every run record).  Bump it on any
change that alters comparability: the prompt text, the overlay contract, the
answer schema, the scoring rules, the excerpt policy.

**1.1 (WP-1058, WP-1059)** moved four things at once, deliberately: a
report-on response can carry `trajectory` — the report at every stage
boundary, not only at the converged state — the §5 excerpt says to read it,
the condition axis splits that delivery from the *instruction* to seek it, and
the real-data pair R1/R2 joins the eight synthetic episodes.  A 1.1 run
therefore cannot be pooled with the 1.0 pilot's grid; it is the *new* delivery
that WP-1059 measures, against the same episodes and the same scorer.

One authority per fact: the prompt *text* lives in `build_fixtures._PROMPT`
(rendered by `render_prompt`), the conditions in `build_fixtures.CONDITIONS`,
the enforcement in `run_refine.py`, the grading in `scorer.py`.  This file is
the protocol *around* them: what runs, under which conditions, and how the
outcome grid must be read.

## The question

Round 1 answered "does the FitReport help a real LLM agent" with a **null on
outcomes** and a measured mechanism: agents never generate the states where
the report speaks.  Round 2 asks the sharper question that mechanism implies —
**does naming the cause at a state the agent did not have to ask for change
what the agent does?** — and separates the two ways of getting there:
*delivery* (the package hands over every stage's report) and *instruction*
(the manual tells the agent to go and look).

## Conditions

Two independent switches, plus the baseline: a 2×2 on (trajectory × §9) and
the arm that sees no report at all.

| condition | `report` | `trajectory` | manual excerpts |
|---|---|---|---|
| `off` | — | — | none |
| `report` | ✓ | — | §5, §6 |
| `prompt` | ✓ | — | §5, §6, **§9** |
| `surface` | ✓ | ✓ | §5, §6 |
| `both` | ✓ | ✓ | §5, §6, **§9** |

- **The shim, not the prompt, enforces it.**  An agent can ignore a prompt; it
  cannot un-strip a response.  Both switches are set on the *request* (so the
  package never builds a half this condition withholds — measured 1.22 s
  against 1.93 s per call on R1) **and** popped from the response, because the
  guarantee is that the condition decides, not a package default that could
  move.  `test_shim_delivers_exactly_what_the_condition_declares` runs this
  over every condition against a stub that always offers both halves.
- **The agent structurally cannot** touch the pattern, the starting parameter
  values, `include_report` or `report_trajectory` — `overlay.json` admits
  `plan` / `mode` / `two_theta_limits` only.
- **One shared prompt per condition, no per-model tuning.**  §5/§6 ship with
  the report (round 1's rule, unchanged).  §9 is quoted as its **"Read the
  run, not just its last state"** subsection only: the DAG half teaches
  `pr.Refinement`/`predict_then_verify`, a python surface the shim does not
  sanction.  Its forward reference to `predict_then_verify` therefore dangles
  by design — the treatment is *read the run*, not *run the DAG loop*.
- **The two trajectory-less report arms are told the key is absent**, in one
  factual sentence about the response shape.  Without it they hunt for a key
  §5 promises.  It does **not** say how to reach an earlier state another way:
  that inference is exactly the operator skill `prompt` is testing.
- **`off` renders round 1's report-off prompt verbatim.**  An arm that never
  sees a report cannot see the content that changed under it, so `off` is the
  one cell that may be read against the 1.0 grid — with the caveat that the
  models and their dates differ, which at these N is not a small caveat.
- Every call runs from the same fixed perturbed start; iteration is **on the
  plan, not the state**.  The report from call N informs the overlay for call
  N+1.

## Episodes

E1–E8 are WP-1052's planted-cause synthetic starts, unchanged from 1.0.
**R1/R2 are new** (WP-1059): the real SRM 660c pattern (5332 channels,
20.3–150.9°, CuKα doublet, the file's own esd column), started from the NIST
protocol's own converged state with one thing moved.

Measured 2026-08-13, `[dev]` venv, darwin/arm64 — the facts the hypotheses
below are registered against:

- **E2** (synthetic, −0.02 mm displacement).  Converged report: Rwp 0.013708,
  **empty** action list.  First rung `scale_bkg`: Rwp 0.05751,
  `refine_sample_displacement` at **0.997**.  Five rungs.
- **R1** (real, displacement −0.0801 → −0.02 mm).  No `mccusker_default` stage
  frees displacement, so the lazy path absorbs it into `zero_shift`: Rwp
  0.09127 against the baseline's 0.08661, zero at +0.031686 (63σ), empty
  action list — but the WP-1056 clause fires *at that converged state*:
  "exchangeable with the held `instrument.geometry.sample_displacement`
  (R² = 0.9977) … a confident verdict is not supported".  Freeing displacement
  instead recovers −0.0800984 (truth −0.0800986) at Rwp 0.08661 and fires the
  same clause the other way (88σ).  Freeing **both** lands on the ridge
  (zero −0.0214, disp −0.1202) at a *better* Rwp 0.08569 and reports the
  unconstrained combination.  Expected verdict **`ambiguous`**; the planted
  displacement is recorded and never graded (`tol: null`).
- **R1's first rung is a trap.**  At `scale_bkg` the top action is
  `add_impurity_phase` at **0.9** (the displaced peaks read as unindexed
  lines), falling to nothing by the `cell` rung.  So on this episode delivery
  hands over a confidently *wrong* early state, and §9's own reading rule —
  "a confidence that **climbs** across rungs is about the specimen" — is what
  discriminates.  That is a contrast between `surface` and `both`, not between
  report-on and report-off.
- **R2** (real, scale ×0.90).  Separable; the default plan recovers the scale
  to ≈6 ppm.  Expected `converged`.  The control that stops R1's refusal from
  being read as "real data is just hard".
- WP-1052's own zero-knock episode is deliberately **not** R1: measured, the
  default plan's zero stage fixes it (Rwp back to 0.08661, zero → −0.0001).
  At the agent surface it is a competence control; the *loop* refuses there
  because it acts only on separable attributions, and an agent driving plans
  is not the loop.

## Pre-registered hypotheses

Written before any run of the round.

- **(a) Delivery, not content.**  E2/E8 move off 0/8 only where the state that
  names the cause is reachable — i.e. in `surface`/`both`, and in `prompt`
  only if the agent bootstraps a short plan itself.  `report` (the 1.0-shaped
  arm with 1.1 content) is the control that says whether WP-1054/1055/1056/1057
  moved anything on their own.
- **(b) E7-haiku flips** with WP-1054's capped `add_impurity_phase` and
  `reindex_or_recheck_cell`-led abstained set, regardless of delivery.  (Not
  in this session's cells — see the budget below.)
- **(c) Placement beats instruction**: `prompt` under-performs `surface`.  The
  falsifier is `bootstrap_calls` — if `prompt` agents do generate short plans
  and still do not move, the pilot's mechanism claim is wrong.
- **(d) Delivery is not uniformly good.**  On R1 the first rung invites a
  phantom phase at 0.9; `surface` may therefore *raise* `impurity_suspected`
  answers on R1 where `both` (which quotes the climbing-confidence rule) does
  not.  A `surface` R1 answer of `impurity_suspected` is following the
  trajectory, exactly as an E6 phantom phase was following the report in
  round 1 — score it and say so, it is not a scorer surprise.
- **(e) The overclaim, not the miss, is the interesting failure.**  On R1 the
  cheapest wrong answer is `converged` with a good Rwp and a compensated zero.
  `overclaimed` is pre-registered as the primary R1 statistic; `passed` is the
  verdict match.

## The round-2 matrix, and what it costs

The full cross (5 conditions × 10 episodes × ≥2 models × 2 efforts) is ~200
runs against round 1's 48.  It is **not** run flat.  Pre-registered priority:

1. **Core — the delivery/instruction split on the rows that discriminate.**
   5 conditions × {E2, E8, R1} × {Sonnet 5, Haiku 4.5} × N=1, effort
   `medium` = **30 runs**.  Answers (a), (c), (d), (e).
2. Deferred to a follow-up pass: E7 rows for (b) at N=2; the competence
   controls and traps (E1, E3, E4, E5, E6, R2) on `off`/`surface`; the second
   effort tier and a third model, which per the WP extend only the cells that
   showed an effect.

Effort is pinned per run and recorded.  Model IDs are recorded as the harness
reports them, never as they were requested.

## Running

Each run gets a fresh episode dir (its `calls.jsonl` is the run's record)
and the scorer-side truth tree stays outside the agent's workspace:

```sh
.venv/bin/python -m tests.eval_report_agent.build_fixtures \
    --episodes RUNS/<run-id> --truth TRUTH --condition surface --only E2
```

Runs execute in the Claude Code harness — the Workflow `agent()` call takes
per-run `model` and `effort`.  Each agent receives exactly the episode's
`prompt.md` (plus the path to its episode dir) and nothing else; it drives
`run_refine.py` itself and writes `answer.json` when done.

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
  E7 → `abstain`, E8 → `ambiguous`, **R1 → `ambiguous`** (its planted
  displacement carries no tolerance: recovering it is not what the data
  licenses, so it is recorded, not graded);
- no successful call, or no valid `answer.json` → failed;
- wrong-frees are descriptive localisation evidence, never pass/fail.

Four measurements ride beside the grade and touch none of it: `overclaimed`,
`bootstrap_calls`/`plans_used`, `watch` (truth-declared glob groups against
what was freed), `report_present`/`trajectory_rungs`.

## Audit

`calls.jsonl` is the record — the call trace and count come from the shim's
log, never from the agent's self-report.  `report_present` and
`trajectory_rungs` on each scorecard must match the condition; a mismatch
invalidates the cell rather than being explained.  Spot-check at least one
transcript per condition × model cell for prompt-compliance (did the agent
read the response rather than invent numbers; did it write `answer.json`
itself), but grade only from the shim log + `answer.json`.

## Reading the grid

- Report the **dated raw outcome grid**: counts, never percentages from tiny
  N, never rounded up (the indexing-scoreboard rule).  Model IDs and efforts
  in the header.  It is a pilot establishing protocol soundness and effect
  direction, not a benchmark, and never a CI assertion — outcomes move with
  the models.
- **Score the two episode groups separately.**  E2/E8/R1 converge to silent or
  compensated states and are where delivery can act; E5/E7 already spoke at
  the final state, so a null there is not evidence against delivery.
- The lazy default-plan path solves E1/E3/E4/E6 — those are competence
  controls, and a flat "the report didn't help" reading of them is the
  designed misread.
- **E3 can invert the sign**: the report's width emitters name only
  `lor_size`/`lor_strain` (proxy plateau χ²_red ≈ 4.3) while the lazy default
  frees `w` itself and reaches the ≈ 1.01 floor — on E3, following the report
  can lose to ignoring it.  `watch` reports which path was taken; state it
  beside the E3 row.
- **E6 invites a phantom phase** (`add_impurity_phase` 0.9 on the abstained
  branch pre-WP-1054; capped at 0.3 with `reindex_or_recheck_cell` first
  since).  **R1's first rung invites one too**, at 0.9, in every arm that
  delivers the trajectory.  An agent taking either invitation is following
  what it was given; score what it does and say so in the row.
- E1/E4 rows are competence controls; failures there are harness or
  competence problems, not report signal.
- **E8's expected verdict has a known nuance** (WP-1056): the default-plan path
  frees the planted zero and converges to truth, and *that* state is correctly
  quiet (partner 1.2σ).  An agent that runs the preset and reads the quiet
  report has a defensible `converged`; the exchange sentence fires on the
  wrong-family-freed state.  The row still grades `ambiguous`, and any
  `converged` answer on E8 must be read against which state it reached.
