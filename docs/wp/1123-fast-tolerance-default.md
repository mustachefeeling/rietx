# WP-1123 — the fast tolerance schedule, on by default

Milestone: v1.1 · Status: ✅ 2026-08-22 — flipped on; one plan field, one
authority, and the trade stated in measured numbers
Depends on: 1113 (its § Findings priced this flip; closed 2026-08-21)

## Goal

A staged refinement runs its **intermediate** stages at a loosened
termination tolerance by default — 1.5–1.7× fewer whole-plan evaluations for
parameter shifts at or below 0.02 esd — with one named switch back to the
fully-converged schedule, one place where a result and a history node say
which one ran, and a manual paragraph that states the trade in numbers
rather than in adjectives.

## Context

**The decision this WP executes** (user, 2026-08-22): flip the default on,
keep an option for the slow mode, and make the trade-off clear in the docs.
Everything below the mechanism is measurement WP-1113 already did; this WP
spends its own measurement on what the *flip* costs, which 1113 could not,
because it landed the knob opt-in and left the presets alone.

**The mechanism, from 1113 (do not re-derive).** An expensive stage's
evaluations are almost all *tail*: undamped Gauss-Newton converging linearly
along a near-degenerate direction — zero ↔ sample displacement ↔ the
low-order background terms on a lab θ range — at a problem-intrinsic
≈ 0.93 per iteration (≈ 14 iterations per decade), run down to the solver's
default ftol = 1e-9. The trust region never binds and the damping stays at
λ ≡ 0, so it is not a crawl and not ill-conditioning; it is a straight line
on a log scale. **99.99 % of a stage's cost decrease is banked by accepted
evaluation 55 of 93** (`zero_disp`), 83 of 131 (`cell`), 50 of 84 (cpd-1a).
Every expensive stage measured terminated on **ftol**, never xtol or gtol.
Because the plan is cumulative, an intermediate stage's parameters keep
refining in every later stage: the last stage inherits the ridge walk once
instead of every stage polishing it (cpd-1a `biso` 47 → 49 evaluations).

**What the flip is priced at** (1113 § Findings, whole-plan totals through
the WP-1111 harness's counting scaffold, worktree venv `[dev]`,
darwin/arm64, 2026-08-21 — before 1115's compiled tier and 1120's batched
residual, both of which move wall clock and not counts):

| case | baseline nfev/njev | every stage but the last at 1e-6 | max shift |
|---|---|---|---|
| cpd-1a | 408/343 | 272/221 (**1.50×**) | 8.6e-4 esd |
| cpd-2 | 540/420 | 315/247 (**1.71×**) | 0.020 esd (a background term); QPA within 0.003 wt % |
| trigger | 363/289 | 226/185 (**1.61×**) | non-degenerate ≤ 0.001 esd; QPA ≤ 0.001 wt % |

The trigger's nominal 1.2 esd worst shift is the **exactly degenerate**
instrument-X ↔ per-phase `lor_size` family (Lorentzian FWHMs add and both
are size-like in θ): the parameterisation moved along a flat direction, the
answer did not. Looser still — 1e-5 and 1e-4 — buys 1.9–2.2× at 0.01–0.2 esd,
which is why the knob stays a **number** rather than a two-position enum: the
ladder is measured, and hiding it behind `"fast"`/`"slow"` would hide the
part of it a careful user may want.

**Capping `max_iter` is the wrong lever and stays retired** (1113): on cpd-2
a 30-iteration cap *raised* the total to 568 nfev by pushing work downstream,
and moved the answer more. So does `x_scale='jac'` (worse on all three
cases) and the cross-correlation zero seed (1.06–1.08×, machinery
unpaid-for). This WP adds no new lever; it changes one default.

**Where the tolerance is decided today.** `Stage.ftol` (`strategy/staged.py`)
is opt-in, `None` meaning the solver default of 1e-9; `PlanSpec`/`StageSpec`
(`schemas/plan.py`) mirror it field for field; two runners read it —
`Refinement._run_stage` (`refine.py`, serving both `fit` and `run_stage`) and
`MultiRefinement.fit` (`multi.py`) — each spelling `{} if stage.ftol is None
else {"ftol": stage.ftol}`. Nothing else in the package sets it. The GUI's
`.rxt` document already renders and parses `ftol` as a stage word
(`gui/textdoc.py` `STAGE_KEYS`, derived from `StageSpec`), so a stage-level
tolerance is already visible and editable there.

**Two recording gaps this flip makes universal, both pre-existing.**
`schemas/history.NodeAction` carries a stage's own arguments so
`cherry_pick` can rebuild and re-run it — its docstring says "a field missing
here is a stage that replays differently from the one recorded" — and it
carries neither `ftol` (1113's gap) nor `window_slack_deg` (1112's).
Off by default they cost a replay nothing; on by default, every intermediate
node replays at the wrong tolerance. `StageResult` likewise reports `status`
and `n_iterations` with no field saying what tolerance produced them.

**The design, and the two shapes rejected.** The tolerance schedule becomes a
**plan-level** field, `RefinementPlan.intermediate_ftol` (mirrored on
`PlanSpec`), defaulting to the measured 1e-6, applied to every stage but the
last that does not declare its own `Stage.ftol`, with `None` restoring the
pre-1123 behaviour bit-identically. One authority answers "what tolerance
does stage k run at" — a method on the plan, which is the only object that
knows both the stage and whether it is last — and both runners call it.

- *Rejected: materialising 1e-6 inside the seven `PLAN_PRESETS` builders.*
  It needs no new field and the `.rxt` document would show it for free, but
  it reaches only plans built by name: every hand-written
  `RefinementPlan(stages=[…])` — which is what the acceptance suites and the
  1111 harness cases use — would silently keep the old schedule, so the
  shipped default and the measured default would be different things.
- *Rejected: a `fit(..., precision="fast"|"exact")` argument.* It duplicates
  the plan's authority over the plan's own business, and would have to be
  threaded through `fit`, `refine`, `refine_multi`, `refine_sequential`, the
  agent request and the GUI wire, each of which already carries a plan.

**A default flip is a contract change here** (`docs/manual/using/compatibility.md`,
the preview promise): the answer moves, so the release note carries it, and the
schema constants whose fields change bump their last component with the comment
beside them saying what.

**The precedent to copy is the dispersion flip** (WP-1001, root CLAUDE.md):
default on, declining it reproduces every earlier number bit-identically and
says so, and **every test that pins a number declares the setting
explicitly** rather than inheriting it — `tests/test_validation_matrix.py`
enforces that for the acceptance suites. A suite whose numbers move when a
default moves is not pinning a protocol.

**Fits this flip must not quietly change.** Whole-profile Le Bail validation
in `indexing/workflow.py` is a *verdict*, not a refinement, and the indexing
acceptance ranking has hidden a real regression under 115 green fast tests
before (WP-1030): `tests/test_acceptance_indexing.py` runs before this WP
closes, whatever the diff looks like. `lab_calibrate` produces the instrument
profile every later sample inherits — cumulative staging means its last stage
still polishes every earlier parameter, which is the reason the shift bound
holds, and is worth stating in the manual where a reader will look for it.

## Non-goals

New tolerance levers (1113 retired `max_iter` capping, `x_scale` and the
cross-correlation seed with numbers); per-evaluation cost (1115, 1120, 1121);
a GUI toggle — the `.rxt` stage word already edits a stage's tolerance and the
plan-level field renders beside `guard`, so the GUI inherits the switch as
document text rather than as new chrome; Rwp-judged anything.

## Tasks

- [x] **The field and its one authority**: `RefinementPlan.intermediate_ftol`
      (default `INTERMEDIATE_FTOL = 1e-6`, `None` = the solver default
      everywhere) + the method that answers what stage *k* runs at, with
      `Stage.ftol` overriding; `PlanSpec` mirrors it; both runners
      (`refine._run_stage` via `fit`, `multi.fit`) call the one authority.
- [x] **Say what ran**: `StageResult.ftol` and `NodeAction.ftol` (+
      `window_slack_deg`, the same replay gap from 1112), `api_call` printing
      them, `cherry_pick` rebuilding through them; contract constants bumped
      with their comments.
- [x] **The `.rxt` plan line** carries `intermediate_ftol` so a GUI user can
      read and edit the schedule the run will use.
- [x] **Declare, then re-measure**: every acceptance suite and pinned-number
      test states its tolerance explicitly; the certified comparisons are
      re-measured under the shipped default and the bands hold or the flip is
      re-scoped.
- [x] **Docs**: `using/refining.md` (the trade in numbers, the exact-mode
      recipe, why cumulative staging bounds the shift), AGENT_PROTOCOL row,
      `releases/` note, milestone record.
- [x] Tests + obs/calc/diff PNGs to `tests/output/`.

## Acceptance

The three lab-shaped harness cases show 1113's factor within measurement
noise, every certified acceptance value stays inside its published band, and
`intermediate_ftol=None` reproduces the pre-flip fit bit-identically.

```sh
.venv/bin/python examples/bench_refinement.py --cases nac,cpd-1a,cpd-2,trigger,trigger-series --repeats 3
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup    # full suite, incl. acceptance
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1113 § Findings (this repo) — the mechanism, the priced flip, the
  retired levers.
- Coelho (2018), J. Appl. Cryst. 51, 210 — ~34 iterations for a 550-parameter
  Pawley refinement; the comparison point for "how many iterations is normal".
- McCusker, Von Dreele, Cox, Louër & Scardi (1999), J. Appl. Cryst. 32, 36 —
  the cumulative turn-on order the shift bound rests on.

## Handover log

### 2026-08-22 — the flip, executed and priced on the shipped tree

**A staged refinement now stops its intermediate stages early by default, and
the package says so in numbers rather than adjectives.** Anyone running a fit
gets 1.5–1.7× fewer evaluations for parameter shifts at or below 0.02 esd;
anyone who needs the fully-converged answer sets one field, and gets the
pre-1.1 fit bit for bit. What made this a WP rather than a one-line default
change is that a default which moves answers has to be *recorded* — in the
result, in the history node, in the manual, in the acceptance suites, and
beside the certified numbers it produced.

*Done.*

- `RefinementPlan.intermediate_ftol` (1e-6, mirrored on `PlanSpec`, constant in
  `schemas/plan.py` because the pydantic field needs it at class-definition
  time) with `RefinementPlan.stage_ftols()` the one authority applying it.
  Precedence: `Stage.ftol` wins, the last stage takes the solver default,
  everything else takes the plan's number. Both runners call it; `run_stage`
  passes the stage's own, having no plan and so no notion of *last*.
- `StageResult.ftol`, `NodeAction.ftol` and `NodeAction.window_slack_deg`
  (1112's gap, same class). The node records what the stage **ran** at, not
  what it declared, or a cherry-pick replays what never happened.
  `SCHEMA_VERSION` 0.4 → 0.5.
- The `.rxt` document's plan-level `tolerance` line, rendered always — a
  default nobody can see is a default nobody can decline — `none` meaning
  converge every stage. Keyword in both the parser and the highlighter
  (`gui/src/lib/rxt.ts`, dist rebuilt: 407 vitest tests, svelte-check clean).
- Docs: `using/refining.md` § How hard each stage is converged (the three
  precedence sources, the measured table, the exact-mode recipe, the series
  caveat), AGENT_PROTOCOL 8.20, `using/history.md` on what the node records.
- Declarations: every acceptance suite names `intermediate_ftol` the way it
  names `dispersion`, `validation_matrix.INTERMEDIATE_FTOL_DEFAULT` records the
  decision beside the numbers, and a new guard fails a suite that rides the
  default silently.
- One crash fixed on the way in, WP-1115's and not this WP's:
  `compiled._redirect_cache` read `sys.modules['numba'].config` while `warm()`
  was still importing numba on its background thread, killing the first fit
  after a fresh install. Pinned by building the state a partial import leaves,
  since the window is the import itself and closes for good once the package
  files are warm in the page cache.

*Measured* (`[dev]` venv, darwin/arm64, worktree, benchmark run alone):

| case | nfev/njev exact → fast | wall exact → fast | largest shift |
|---|---|---|---|
| nac | 47/44 → 39/36 | 0.40 → 0.35–0.36 s | — |
| cpd-1a | 408/343 → **272/221** (1.50×) | 2.20–2.26 → 1.64–1.75 s | 0.001 esd; QPA 0.0007 wt % |
| cpd-2 | 540/420 → **315/247** (1.71×) | 3.63–3.69 → 2.23–2.25 s | 0.020 esd (`background.c0`); QPA 0.003 wt % |
| trigger | 358/286 → **232/186** (1.54×) | 8.84–9.14 → 5.71–5.73 s | 0.001 esd outside one degeneracy; QPA 0.0001 wt % |
| trigger-series | 1634/1273 → 1705/1399 | 54.0–54.6 → 61.7–62.7 s | — |

cpd-1a's 272/221 and cpd-2's 315/247 are WP-1113's numbers to the evaluation,
measured a milestone's worth of optimisation later — which is the strongest
evidence available that the flip does what 1113 priced. Rwp agrees to six
decimals on cpd-1a and the trigger, five on cpd-2 (0.132902 → 0.132920).

The trigger's largest shift is the exactly degenerate family and it moves as
one: `instrument.profile.x` +0.0014651 against `lor_size` −0.0014653 /
−0.0014654 / −0.0014497 / −0.0014738 on the four phases. Lorentzian FWHMs add,
so the width they sum to did not move; 2.3 esd of *parameterisation* did.

*The one place it does not pay.* The chained ten-pattern series takes **more**
evaluations under the schedule, 1705 against 1634, and 14 % more wall. The cold
first pattern is still faster (6.84 s against 8.45 s); the loss is in the warm
ones, where a one-stage collapsed refit is unaffected by construction (a lone
stage is the last one) and what changed is which *rung* each pattern needed —
patterns 5 and 6 escalated further than they did before. This is path
dependence, the thing `direction="both"` exists to measure, not a slower fit.
It is recorded in the manual, in AGENT_PROTOCOL 8.20 and in the v1.1 record
rather than tuned away.

*Gotchas for whoever comes next.*

- `sequential._collapse` builds the warm one-stage plan from the source plan
  and carries `max_iter`, `lebail_cycles`, `seed` and `strain_seed` — it now
  also carries `intermediate_ftol` (inert at one stage, carried so a
  two-stage collapse could not drop it silently). It still drops
  **`restraint_weight_scale`** and **`window_slack_deg`**, which is the same
  defect class this WP fixed in `NodeAction`: a series whose plan declares
  c_w = 300 early runs its warm refits at 1.0. Left alone deliberately —
  the right aggregation for a c_w *schedule* is a judgment about physics (the
  last stage's value, not the max), and guessing it silently is exactly what
  this WP spent its time undoing. Worth a WP.
- The API-surface partition is the gate that catches a new public name: six
  arrived here and the fast suite failed until each was documented. Expect it.
- The benchmark's "before" cannot be recovered after the change lands — the
  harness has no exact-mode flag by design (a harness that changes with the
  optimisation cannot measure it). Measure the baseline first.

*Next.* Nothing on this WP. The v1.1 front is [1121](1121-per-reflection-cost.md)
(the per-reflection Jacobian cost), which multiplies with this: 1.5× fewer
evaluations times whatever 1121 takes off each one.

- **2026-08-22** — created.
