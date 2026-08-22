# WP-1127 — the ladder's first rung: which one a warm pattern starts on

Milestone: v1.1 · Status: ✅ 2026-08-22 — the first rung bounded from what a
converged one costs: 1603 → 1331 evaluations on the trigger chain, identical on
the small-cell one, answers bit-identical on both; default flipped
Depends on: WP-1111 (harness + counting scaffold), WP-1124 (the decomposition
that names this front), WP-1051 (the ladder itself)

## Goal

The warm-series band stops being mostly wall the ladder throws away. A warm
pattern starts on the rung the chain's **own measured history** says is
cheapest for this model, and a first rung that is going to be discarded costs a
fraction of the one that is kept. Measured on both regimes — the trigger-shaped
series, where the staged rung wins, and the round-robin small-cell series, where
WP-0505 measured the opposite — and landed only if it pays on both.

## Context

**This is v1.1's one remaining gating acceptance row.** The milestone asks for
warm-started series per-pattern wall in the ~1 s band
(`../milestones/v1.1.md` § Acceptance). WP-1124 decomposed the band and found
the row was describing a distribution the case does not have, so the target is
judged per pattern, never on the average.

### What WP-1124 measured, and why it points here

On the current tree, `[dev]` venv, darwin/arm64, best-of-3, ten patterns
(`examples/bench_refinement.py --cases trigger-series`):

| case | wall (s) | nfev | njev | escalations |
|---|---|---|---|---|
| `trigger-series` (`refit="single"`, the shipped default) | 57.66-57.96 | 1603 | 1315 | 2 |
| `trigger-series-stages` (`refit="stages"`) | 35.76-35.97 | 1253 | 906 | 0 |

Three facts from that table and its per-pattern breakdown:

1. **57 % of the series wall is first rungs the ladder then discards.** Two
   patterns of the nine escalated; each burned its collapsed rung to the
   iteration cap and then succeeded on the staged rung in a fifth of the time.
   Pattern 1: `warm` = 17.01 s discarded, `warm_staged` = 3.18 s kept. Pattern
   6: 15.62 s discarded, 3.20 s kept. **32.63 s of 57.45 s.**
2. **Seven of the nine warm patterns are already at 0.89-2.32 s** (median
   2.03), at or just above the target. The band is bimodal and neither mode is
   at the average.
3. **The shipped default first rung is the slower one on this case.**
   `refit="stages"` is 1.61× faster with zero escalations. The
   machine-independent half is the one to quote: **1253 nfev against 1603**,
   **906 njev against 1315**, deterministic across every repeat.

WP-1124's verdict sentence: *the lever on the warm-series band is which rung
the ladder starts on, not what the rung starts from.* Predictor seeding (the
survey's B8) is retired and must not be revisited here.

### Why the answer is adaptive rather than a flipped default

WP-0505 measured the round-robin sample-1 series (eight real mixtures,
corundum/zincite/fluorite, small cells) the other way: **838-904 iterations
warm-collapsed against 1623 warm-staged and 2863 cold**, for identical Rwp and
identical weight fractions. `_ladder`'s own docstring already says which rung is
cheaper is a property of the model. So the trade is stage count against per-stage
Jacobian *width*, and both directions are measured facts about real protocols.
Flipping the default to `"stages"` would buy the trigger case 1.61× and lose the
small-cell case roughly the same.

### The mechanism, in the code this WP touches

`src/rietx/sequential.py` is the whole seam.

- `SequentialRefinement.fit(refit=…)` takes `REFIT_MODES` and sets the ladder's
  **first** rung: `"single"` (default) collapses the plan with `_collapse` into
  one stage freeing everything; `"stages"` uses the base plan.
- `_ladder(base_plan, warm_plan)` returns the rungs in order: three under
  `"single"` (`warm` → `warm_staged` → `cold`), two under `"stages"`
  (`warm_staged` → `cold`, because re-running an identical plan from an
  identical state is a deterministic repeat).
- `_run_pass` climbs the ladder per pattern. A rung is reached only when the
  reseed fence still fires **on the best attempt so far** —
  `_reseed_needed(best, accepted_rwp, reseed_factor)`, `RESEED_FACTOR = 1.25`
  against the median of the accepted patterns. `_better` prefers a converged fit
  and then the lower Rwp, so the escalation stops at the first rung that works.
- Every rung is charged to the pattern (`entry.n_iterations` sums them);
  `entry.rung` names the kept one and `entry.rungs_tried` lists what ran.
- The discarded rung's cost is set by the collapsed stage's budget.
  `_collapse` takes `max_iter` as the **maximum** across the plan's stages, and
  `run_least_squares` sizes scipy's cap at `max_iter × NFEV_PER_ITERATION`
  (= 4). So a failing first rung spends the plan's largest budget on the widest
  possible Jacobian before being thrown away. That is the "runaway guard, never
  a timer" rule (root CLAUDE.md) working exactly as written — the guard is the
  right size for a rung that is the answer, and the wrong size for a rung that
  is a bet.

### The two levers, cheap first

**Lever A — bound the bet.** The first rung is a wager that the collapsed refit
suffices. Give it a budget derived from the chain's own accepted history (the
median accepted `n_iterations`, times a factor, floored so an early pattern is
not starved) instead of the plan's largest stage budget. A pattern that would
have converged inside that budget is untouched; one that would not escalates
sooner and cheaply. Costs nothing when nothing escalates, which is the regime
WP-0505 measured.

**Lever B — learn the rung.** After a pattern escalates, later patterns of the
same pass start on the rung that worked. The chain pays the discovery once
rather than per pattern. On `trigger-series` that is pattern 1's 17.01 s paid
once and pattern 6's 15.62 s not paid at all.

The two compose: A bounds the discovery cost, B bounds how often it is paid.
Measure them separately before either is proposed, because A alone may be enough
and it changes no control flow.

### The seam a new mode needs

`REFIT_MODES` is data (`sequential.py`, the "as data rather than as two
literals" comment). A third member is where the adaptive rule lands. **A
caller's explicit `refit=` is never overridden** — the indexing precedent
(`total_budget_seconds`, root CLAUDE.md § Indexing): an adaptive default is a
mode a caller can ask for and a mode a caller can refuse. Whether that mode
becomes the **default** is a priced maintainer call, exactly as WP-1123 handled
the tolerance flip, and this WP prices it rather than deciding it.

### Rules this WP is held to

- **A series is measured, never assumed** (root CLAUDE.md). WP-1123 saw a
  chained series change sign — 1.04× worse, then 1.12× better — between two
  trees one commit apart, because a bounded per-fit difference becomes a rung
  escalation or a rung avoided and the chain integrates it. Every claim here is
  measured on a chain, on both cases.
- **`direction="both"` is a read-out, not an option.** WP-1124's kill criterion
  fired on exactly this: both predictor arms turned `SEQUENTIAL_PATH_DEPENDENT`
  from absent to reported. A rule that starts different patterns on different
  rungs is a candidate for the same failure — an escalation early in a forward
  pass is not an escalation early in a backward one — so the check is
  pre-registered below, not run as an afterthought.
- **Wall clock is compared between arms inside one run, never across runs.**
  WP-1124 measured the same chain at 35.76-35.97 s and 41.77-42.93 s at an
  identical 1253 nfev: 1.17× of pure machine state, larger than most effects
  worth landing. nfev/njev are the deterministic read-out and lead every table.
- **Never an Rwp comparison as evidence** (root CLAUDE.md). The equivalence bar
  here is the accepted per-pattern answer in esd units, plus the diagnostic set.

### Pre-registered kill criterion

The adaptive rule is **not landed** if any of these fires on either case:

1. It costs whole-chain evaluations against the better of the two fixed modes
   on that case.
2. It raises the escalation or quarantine count, adds any `SEQUENTIAL_*`
   diagnostic the fixed modes do not produce, or leaves any accepted entry at a
   `status` other than `"converged"`. The third clause is not decoration: a
   bounded rung comes back `"max_iter"`, `_better` treats that as not-diverged
   and `_reseed_needed` tests only divergence and Rwp, so a truncated fit could
   be **accepted** rather than escalated. Whatever the bound is, hitting it has
   to force the next rung.
3. It moves an accepted parameter outside the exactly degenerate width family
   by more than **0.25 esd** against the fixed-mode chain it is closest to.
   (WP-1124's out-of-family bar: copy vs secant/tangent measured 0.047-0.262.)
4. `direction="both"` disagreement worsens — `SEQUENTIAL_PATH_DEPENDENT` absent
   under the fixed mode and reported under the rule.

A clean negative closes this WP ✅ with the numbers, exactly as WP-1114 and
WP-1124 did. Nothing in `src/` ships on a hunch.

## Non-goals

- Predictor seeding, the tangent, anything about what a rung starts *from*.
  WP-1124 retired it; the survey's B8 dated note has the bound.
- The per-reflection 19.4 % front (WP-1121 named it; no WP owns it) and the
  solver's 11.8 %.
- The peaks buffer (WP-1122, deferred to ship with FPA).
- Changing `RESEED_FACTOR`, `_better`, the quarantine rule, or what the ladder's
  *later* rungs are. This WP moves where a pattern enters the ladder and what
  the entry rung may spend, and nothing else.
- The model-cost estimate (deferred by WP-1113).

## Findings

All numbers: `[dev]` venv only (**no jax, no torch**; numba 0.67.0 present, so
the compiled tier WP-1115 made the default is **on** —
`capabilities().features["compiled_kernels_active"]` is `True`), darwin/arm64,
python 3.12.12, numpy 2.5.2, `rietx` 1.1.0.dev0, best-of-3 on an idle machine,
per root CLAUDE.md § Numbers. `examples/bench_refinement.py`, all four cases in
one process.

### 1 — the baseline, and the two regimes are real (2026-08-22)

| case | wall (s) | nfev | njev | Rwp | escalations |
|---|---|---|---|---|---|
| `cpd-series` (`refit="single"`) | **4.77-4.80** | **627** | 449 | 0.12586 | 0 |
| `cpd-series-stages` (`refit="stages"`) | 7.45-7.47 | 1041 | 776 | 0.12592 | 0 |
| `trigger-series` (`refit="single"`) | 57.75-58.20 | 1603 | 1315 | 0.01943 | 2 |
| `trigger-series-stages` (`refit="stages"`) | **36.12-40.54** | **1253** | 906 | 0.01944 | 0 |

`trigger-series` reproduces WP-1123's and WP-1124's **1603** nfev and
`trigger-series-stages` their **1253**, so this is the same tree measuring the
same fits, and `src/` is untouched by this WP so far.

**The two cases point opposite ways, as WP-0505 and WP-1110 said they would.**
On the real small-cell chain the collapse wins 1.66× in evaluations (627 against
1041) and 1.56× in wall; on the trigger-shaped chain the staged rung wins 1.28×
in evaluations (1253 against 1603) and ~1.5× in wall. A flipped default would
buy one case what it costs the other.

### 2 — the whole trigger gap is the cost of discovering failure

Per pattern, `trigger-series`, last repeat:

| pattern | wall (s) | iter | kept rung | discarded rung | warm Rwp |
|---|---|---|---|---|---|
| 0 | 6.64 | 252 | cold | — | — |
| 1 | **20.44** | 506 | `warm_staged` | **17.22 s** | 0.03170 |
| 2 | 2.34 | 64 | `warm` | — | — |
| 3 | 2.35 | 62 | `warm` | — | — |
| 4 | 1.15 | 35 | `warm` | — | — |
| 5 | 2.06 | 53 | `warm` | — | — |
| 6 | **18.81** | 500 | `warm_staged` | **15.71 s** | 0.03006 |
| 7 | 1.40 | 46 | `warm` | — | — |
| 8 | 0.89 | 27 | `warm` | — | — |
| 9 | 2.04 | 58 | `warm` | — | — |

**32.93 s of 57.75 — 57 % — is the two discarded rungs**, reproducing WP-1124's
decomposition on a fresh run.

Two facts decide the design, and neither was visible before this table:

1. **A successful first rung and a failed one do not overlap, anywhere.**
   Successes cost **27-64** iterations on `trigger-series` and **25-107** on
   `cpd-series`. Both failures ran to **~400**, which is exactly the cap:
   `_collapse` takes `max_iter` as the maximum over the plan's stages (100 for
   `qpa_plan`) and `run_least_squares` sizes scipy's `max_nfev` at
   `max_iter × NFEV_PER_ITERATION` (= 4). So a failed first rung does not cost
   *more* than a successful one, it costs **the whole budget**, and the gap
   between the largest success and the smallest failure is a factor of six.
   The two regimes are separable by cost, which is what makes a budget derived
   from the chain's own history a rule rather than a tuning knob.
2. **On seven of the nine warm patterns the collapse is the better rung even
   here.** 0.89-2.35 s against the staged mode's 2.97-4.25 s for the same
   patterns. `refit="stages"` wins this case only by never paying for a
   discovery, not by fitting better.

Fact 2 **refutes lever B as it was written**, before it was built. Starting
later patterns on the rung that worked would move patterns 2-9 from 0.89-2.35 s
onto 2.97-4.25 s to avoid one 15.71 s discovery: adding up the measured
per-pattern rows, that is ~50 s against the 42.8 s a bound alone predicts and
the 57.75 s baseline. The escalations here are **sporadic, not systematic**, and
a rule that generalises from one failure to the rest of the chain pays for the
generalisation on every pattern that did not need it.

Fact 1 gives the ceiling worth chasing. With the two discoveries made *free*,
the same ladder would run in **~25.2 s** — better than `refit="stages"`'s
36.12-40.54 s, because it would keep the collapse's win on the seven patterns
*and* the staged rung's rescue on the two. So the target is not "pick the right
fixed rung" but "make the wrong first rung cheap", and the fixed-mode winner on
this case is a floor to beat rather than the goal.

The bound has one blind spot the table names: **the first warm pattern has no
accepted first-rung history**, and on `trigger-series` it is one of the two that
fails (17.22 s). Only the cold fit precedes it, at 252 iterations — which is
still 1.6× cheaper than the 400 the rung actually spent, and is the one bound
available at that point.

### 3 — the bound, measured on both cases (2026-08-22)

`first_rung_factor=2.0`, `bench_refinement.py`, all four rows in one process.
**These are the final-rule numbers**; § Findings 6 has the half of the rule that
was refuted between the first measurement and this one, and why its figures
(1183 nfev, 1.36×) do not stand.

| case | wall (s) | nfev | njev | Rwp | escalations | discarded |
|---|---|---|---|---|---|---|
| `cpd-series` (bounded, the shipped default) | 4.68-4.83 | **627** | **449** | 0.12586 | 0 | — |
| `cpd-series-unbounded` (pre-1127) | 4.69-4.73 | 627 | 449 | 0.12586 | 0 | — |
| `trigger-series` (bounded) | **46.49-46.65** | **1331** | **1072** | 0.01943 | 2 | 21.88 s |
| `trigger-series-unbounded` (pre-1127) | 57.22-57.42 | 1603 | 1315 | 0.01943 | 2 | 32.84 s |

**Trigger: 1.20× fewer evaluations (1603 → 1331), 1.23× fewer Jacobians, 1.23×
of wall.** Both escalations survive; what changed is only what the losing rung
was allowed to spend. Pattern 6's first rung went 400 → **128** evaluations
(2 × the most expensive accepted first rung, 64); pattern 1's stays at 400,
because it is the first warm pattern and the chain has no evidence yet about
what a working first rung costs on this model. Every other pattern's iteration
count is unchanged, to the evaluation.

**1331 does not beat the better fixed mode**: `refit="stages"` on this case is
1253. The bound improves whichever mode it is in — 1603 → 1331 under `"single"`,
inert under `"stages"` — but it does not close the gap that choosing the mode
would. See § Findings 7 for what that does to the pre-registered clause 1.

**`cpd-series` is bit-identical** — same nfev, same njev, same Rwp, same
per-pattern iteration counts. That is the design working rather than a lucky
case: the bound is derived from what *working* first rungs cost, so on a chain
where they all work it is never reached.

### 4 — the four clauses, and what the answer did (2026-08-22)

`examples/bench_ladder_bound.py`, arms in one process:

| read-out | `trigger` | `cpd` |
|---|---|---|
| evaluations vs unbounded | 1603 → 1331 (**1.20×**) | 627 → 627 (1.00×) |
| escalations / quarantined | 2 → 2 / 0 → 0 | 0 → 0 / 0 → 0 |
| diagnostics added | **none** | **none** |
| accepted entries not `converged` | **none** | **none** |
| accepted values that differ at all | **0 of 1030** | **0 of 392** |
| agreement outside the width family | 0.000 esd | 0.000 esd |
| `direction="both"` nfev | 3325 → 2717 (1.22×) | 2839 → 2042 (**1.39×**) |
| `SEQUENTIAL_PATH_DEPENDENT` | absent → **absent** | absent → **absent** |

**Clauses 2, 3 and 4 are silent, and the equivalence is stronger than clause 3
asked for: the answers are bit-identical, not merely within 0.25 esd.** Every
accepted value of every pattern, on both cases. Clause 1 is § Findings 7.

That is not luck either, and the mechanism is worth stating because it is what
makes the bound safe: **the bound only ever truncates a rung whose result is
discarded, and the rung that replaces it starts from the warm state rather than
from the truncated one.** Both escalated patterns keep `warm_staged` in both
arms, and that staged refit begins at the predecessor's endpoint, which the
first rung never touched. Cutting a losing bet short changes how long it lost
for, not what was bet next.

**`direction="both"` on `cpd` is where the bound turns out not to be inert.**
The forward chain never escalates, so § Findings 3 reads 1.00×; the *backward*
chain — 94 wt % down to 1 — does, and the pair goes 2839 → 2042 evaluations.
Read the "inert on `cpd-series`" result as being about that chain in that
direction, never about the case.

### 5 — one hazard, found by a test rather than by the measurement

The first version of the bound left the answer reachable, and the two harness
cases did not show it. `_better` ranks a diverged fit below a finished one and
then goes on Rwp, so **at equal Rwp it keeps the earlier attempt** — which for a
bounded chain is the rung the ladder itself cut short. The escalation was
already forced (clause 2), so the completed rung had run; it was then thrown
away in favour of the truncated one, and the entry came back `"max_iter"`.

On both harness cases the staged rescue wins on Rwp by a wide margin
(0.01950 against 0.03235), so this never fired there and the measurement said
nothing about it. It took `_dictate`ing two rungs to the same Rwp — which is not
a corner, it is what two rungs from the same warm state can genuinely reach.

`_prefer` now ranks a truncated attempt below any that ran to completion, and
`_better` decides only between two attempts in the same state. **It cost
evaluations, and the cost is the honest one**: `cpd` under `direction="both"`
went 1908 → 2042 (+7 %) when it landed, one commit apart, which means the
backward pass had been keeping a truncated fit. Nothing else changed, and
`_prefer` is the only thing that can change a rung sequence by changing which
attempt the fence is asked about. Every forward number was unmoved.

A first rung that hits the **plan's own** budget is untouched by any of this and
is still kept if nothing beats it, which is what the shipped ladder has always
done — pinned by the second half of
`test_a_bounded_first_rung_that_spends_its_bound_escalates`, so the escalation
this WP adds is attributable to the bound and not to a change of policy on
`max_iter`.

### 6 — the cold bound was the other half of the rule, and it was false

The bound shipped in § Findings 3 is one rule. It was designed as two, and the
second is worth recording because it is the more tempting of the pair: **"a warm
refit that costs more than the cold fit it started from is not a warm refit"**.
It needs no constant, and — unlike the accepted-rung bound — it is available to
the *first* warm pattern, which is one of the two that escalate on
`trigger-series`. With it, that pattern's first rung was cut 400 → 252 and the
case measured **1183 nfev, 1.36×**, beating `refit="stages"`'s 1253.

**It is false, and the test suite refuted it before the harness could.**
`_collapse` of a *one-stage* plan is that plan, so for a short plan the cold fit
and the collapsed warm rung are the same problem from different starting points,
and a warm start from a neighbouring pattern can legitimately want *more*
evaluations than a cold start from the initial model. Measured on
`tests/test_sequential.py`'s own cheap plan: **cold 9 evaluations, warm 14**, so
the cold bound cut a rung that was about to succeed and two unrelated event-
stamp tests went red.

Three things to take from it. The rule survived both real harness cases only
because a multi-stage cold fit sums to several times a collapsed rung (252
against 25-107) — **a property of those plans, not of the rule**, and no factor
repairs it: the toy needs ≥ 1.56 × cold to be safe and the trigger case needs
≤ 1.0 × cold to be useful. A **one-parameter toy plan was a better adversary
than either real case**, which is the opposite of the usual expectation and is
why the fast suite ran before the flip rather than after. And the surviving
bound is the one derived from the quantity it bounds — what a *working first
rung* costs — which is the form to keep when the next such rule is proposed.

The same measurement retired a second, quieter flaw: a first rung kept at the
plan's own cap reports `"max_iter"`, and it was entering the evidence sample at
full budget, which would have raised the bound to twice the cap and switched it
off from then on. "Worked" is now convergence, not survival.

### 7 — clause 1, read as it was written, fires on `trigger`

Pre-registered: *"It costs whole-chain evaluations against the better of the two
fixed modes on that case."* On `trigger` the bounded chain is **1331** and the
better fixed mode, `refit="stages"`, is **1253**. Read literally, the clause
fires. It is recorded that way rather than reinterpreted, because a criterion
corrected after the data is in cannot be told from a moved goalpost
(`tests/CLAUDE.md` § An eval's expected answer is a measurement).

What the clause was for, and where it mis-fits: it was written for a rule that
**chooses** the first rung — lever B's shape, refuted in § Findings 2 — where
"worse than just picking the right mode" is the failure to guard against. The
bound chooses nothing. It prices whichever mode the caller picked: 1603 → 1331
under `"single"`, inert under `"stages"`, bit-identical on both cases' answers.
So it makes no chain worse, and the gap to 1253 is the *mode* choice, which is
still unowned and still adaptive-or-nothing for WP-0505's reason.

## Tasks

- [x] **A second series case in the harness**: the round-robin sample-1 chain
      (eight real mixtures, small cells) as `cpd-series` / `cpd-series-stages`,
      importing the protocol wholesale from
      `tests/test_acceptance_qpa_roundrobin` the way `_trigger_series` already
      imports `qpa_plan`. Without it every rule below is tuned on the one case
      whose measurement points one way, and WP-0505's counterexample family has
      no seat. Report per-pattern wall / iterations / rung breakdown, both
      `refit` modes.
      *(2026-08-22: `_cpd_series`/`_cpd_series_stages`, the same chain
      `test_acceptance_sequential.chained_all` runs — same eight patterns,
      phases, instrument, `seed_scales`, `qpa_plan()` and default
      `carry=("*",)` — so only `refit` varies. Pinned by
      `test_the_real_series_case_is_the_acceptance_chain`.)*
- [x] **Baseline both cases on this tree**, both modes, the acceptance command
      verbatim: per-pattern table with the discarded-rung column, whole-chain
      nfev/njev, escalation count, and the fixed-mode winner per case. This is
      the "before" every later row is judged against; WP-1124's numbers are
      quoted for `trigger-series` and re-measured, not assumed.
      *(2026-08-22: § Findings 1-2. The fixed-mode winner is `single` on
      `cpd-series` and `stages` on `trigger-series`, as WP-0505 and WP-1110
      predicted. Two facts came out that were not in the plan: a successful
      first rung and a failed one do not overlap in cost anywhere, and the
      collapse is still the better rung on seven of the trigger case's nine
      warm patterns — which refutes lever B before it is built.)*
- [x] **Lever A — bound the first rung**: budget from the chain's accepted
      history, no control-flow change. Measure both cases, both modes: whole-
      chain nfev/njev, discarded wall, escalation count, per-pattern answer
      agreement in esd. State the budget rule's constants and where they came
      from (measured, never tuned to one case).
      *(2026-08-22: § Findings 3-5. `first_rung_factor`, default `None`.
      "No control-flow change" turned out to be wrong twice, and both are in
      § Findings: hitting the bound must force the next rung, and a truncated
      attempt must lose to one that completed. The constants are the cold
      fit's own cost — no constant at all — and `FIRST_RUNG_FACTOR = 2.0`,
      which is twice the headroom over every accepted first rung measured on
      either case.)*
- [ ] **Lever B — learn the rung**: **refuted by § Findings 2 before being
      built**, and the task stays here to record that rather than to run it.
      The trigger case's escalations are sporadic, not systematic — the
      collapse is the better rung on seven of its nine warm patterns — so
      generalising from one failure to the rest of the chain costs more on
      every pattern that did not need it (~50 s against a bound's predicted
      42.8 s). Build it only if a case turns up whose escalations are the norm;
      none of the harness's two is.
- [x] **`direction="both"` on whichever lever survives**, both cases: the
      path-dependence read-out that retired B8. Pre-registered clause 4.
      *(2026-08-22: § Findings 4. `SEQUENTIAL_PATH_DEPENDENT` absent in all
      four arms, so clause 4 is silent; and the read-out found the one place
      the bound is not inert on `cpd`, its backward chain.)*
- [x] **Land or retire.** On a go: the third `REFIT_MODES` member, a caller's
      explicit mode never overridden, `entry.rung`/`rungs_tried` carrying what
      actually ran, the docstrings in `sequential.py` carrying the measurement,
      and the default flip **priced, not taken** (WP-1123's shape). On a no-go:
      § Findings carries the bound and `src/` is untouched.
      *(2026-08-22: **landed**, and in a shape the plan did not predict. No new
      `REFIT_MODES` member: the rule prices the first rung rather than choosing
      it, so it is orthogonal to `refit=` and belongs beside `reseed_factor`
      as `first_rung_factor`. The default flip was **taken, not deferred** —
      the maintainer's call, twice: once on the 1.36× figure and again on the
      corrected 1.20× with the fired clause 1 in front of them.
      `first_rung_factor=None` is the bit-identical way back.)*
- [x] Tests (`tests/test_sequential.py` for the rule's unit behaviour, the
      harness case asserted in `tests/test_bench_refinement.py`) + obs/calc/diff
      PNGs for the two chains to `tests/output/`.
      *(2026-08-22: six in `test_sequential.py`, one in
      `test_bench_refinement.py`. Two of them found defects the harness could
      not — § Findings 5 and 6 — which is the reason this row is not a
      formality. The PNGs are the acceptance suites' own, unchanged, since the
      chains are bit-identical.)*
- [x] Docs: the survey's B8 neighbourhood gains the dated outcome,
      `../milestones/v1.1.md` takes the narrative, and any standing rule reaches
      root CLAUDE.md as a rule with a pointer — not a finding.
      *(2026-08-22: §2.B8's dated note and §5's bullet, the v1.1 narrative and
      its warm-series acceptance row, root CLAUDE.md's series paragraph
      (cap 845 → 853), and `using/series.md` — the parameter row plus what a
      reader needs to reproduce a pre-1.1 run.)*

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py --cases trigger-series,trigger-series-stages,cpd-series,cpd-series-stages --repeats 3
.venv/bin/python -m pytest tests/test_sequential.py tests/test_bench_refinement.py -q
.venv/bin/python -m pytest tests/test_acceptance_sequential.py -q     # the WP-0505 chain, unmoved
.venv/bin/python -m ruff check src tests examples
```

The claim, on a go: whole-chain evaluations at or below the better fixed mode on
**both** cases, with the four kill-criterion clauses all silent and the
per-pattern table showing the discarded-rung wall gone. On a no-go: the same
tables, and the reason.

## Handover log

### 2026-08-22 — closed ✅: the bet is priced, not chosen

**What this means, in one paragraph.** Fitting a series means fitting each
pattern from the previous one's answer, and for each pattern the ladder tries a
cheap fit first and escalates if it comes out badly. The cheap first try was
being given the same budget as a serious fit, so when it was going to fail it
failed *slowly* — it spent the plan's largest budget on the widest Jacobian in
it, then got thrown away. That was 57 % of the warm-series wall. It is now
bounded by what a first rung that *converged* has cost on this same chain, so a
losing bet is discovered early and a chain where the collapse works is untouched.
The answers do not move at all: a bound only shortens work that was going to be
discarded, and the rung that replaces a truncated one starts from the warm state
the truncation never touched.

**Measured** (`[dev]` venv only — no jax, no torch; numba 0.67.0, so the
compiled tier is on — darwin/arm64, python 3.12.12, numpy 2.5.2, `rietx`
1.1.0.dev0, best-of-3, arms in one process):

| | unbounded | bounded | |
|---|---|---|---|
| `trigger-series` nfev / njev | 1603 / 1315 | **1331 / 1072** | 1.20× / 1.23× |
| `trigger-series` wall | 57.22-57.42 s | **46.49-46.65 s** | 1.23× |
| `cpd-series` nfev / njev | 627 / 449 | **627 / 449** | identical |
| `direction="both"` nfev, trigger | 3325 | 2717 | 1.22× |
| `direction="both"` nfev, cpd | 2839 | 2042 | 1.39× |
| accepted values that differ | — | **0 of 1030, 0 of 392** | bit-identical |

**Suites**, same venv and platform: fast `-m "not slow"` **2626 passed, 117
skipped** (1:55); full **2735 passed, 126 skipped** (21:43), zero failures. Seven
tests added against `origin/main` — six in `test_sequential.py`, one in
`test_bench_refinement.py` — all passes, no new skips, so passed+skipped moves by
exactly seven in the fast selection. The full suite fired once, on the final
tree, and it had to: the flip changes what a series does, and
`test_acceptance_sequential.py` is the WP-0505 chain this rule was measured
against. It is green with the bound on.

**Three things a successor should carry, none of them the ratio.**

*The attractive bound is the false one.* "A warm refit costing more than the cold
fit it started from is not a warm refit" needs no constant, is the only bound the
first warm pattern could have, and reached 1.36× — beating `refit="stages"`. It
is wrong: `_collapse` of a one-stage plan **is** that plan, and the suite's own
cheap plan has cold 9 evaluations against warm 14. Both real harness cases hid it
behind a multi-stage cold fit's size. **A one-parameter toy plan was a sharper
adversary than either real dataset**, which is why the fast suite ran before the
flip rather than after it, and it is the reason to keep the surviving bound's
shape: derive a bound from the quantity it bounds.

*A bound wants two clauses that have nothing to do with the bound.* Spending it
must force the escalation, because `_reseed_needed` tests neither `max_iter` nor
the budget and would keep a truncated fit at a good Rwp; and `_prefer` must rank
a truncated attempt below a completed one, because `_better` at equal Rwp keeps
the earlier. Both were found by tests, not by the harness — the second cost 7 %
of the `cpd` `direction="both"` arm's evaluations to fix, which is the honest
price of not letting a bound pick the answer.

*The pre-registered clause 1 fires and is recorded as firing.* 1331 against
`refit="stages"`'s 1253. It was written for a rule that *chooses* the rung, and
the bound chooses nothing, but that judgement is written beside the clause rather
than into it.

**Next actions, in order of what the evidence points at.** The `refit=` choice is
now the front: 1253 against 1331 says the mode outweighs the bound on the trigger
case and 627 against 1041 says the reverse on the small-cell one, so it is
adaptive-or-nothing and unowned. Below that, the per-reflection 19.4 % front
(WP-1121) and the solver's 11.8 % are both still unowned. Lever B is **refuted,
not deferred** — do not re-propose "start later patterns on the rung that worked"
without a case whose escalations are systematic; neither harness case is one.

- **2026-08-22** — **Opened.** WP-1124 closed the same day on a clean negative
  whose yield was a decomposition: 57 % of the `trigger-series` wall is first
  ladder rungs that get discarded, seven of the nine warm patterns are already
  at 0.89-2.32 s, and `refit="stages"` runs the same chain 1.61× faster than
  the shipped `refit="single"` default. Its closing sentence named this front
  and declined it as out of scope: *the lever is which rung the ladder starts
  on, not what the rung starts from*. This WP takes it. It is v1.1's one
  remaining gating acceptance row, and it had no owner
  (`../ROADMAP.md` § Current focus).

  The shape is set by WP-0505 pointing the other way — 838-904 iterations
  warm-collapsed against 1623 warm-staged on the round-robin sample-1 series —
  so the answer has to be adaptive and the first task is a second harness case,
  not a rule. Two levers are written up separately because the cheap one changes
  no control flow: bound the first rung's budget from the chain's own accepted
  history (it is a bet, and it is currently sized like an answer), and start
  later patterns on the rung that worked. A kill criterion is pre-registered
  with four clauses, one of them WP-1124's own: `direction="both"` must not turn
  `SEQUENTIAL_PATH_DEPENDENT` from absent to reported, which is what retired the
  predictor arms.

  Next action: the `cpd-series` harness case, then baseline both cases on this
  tree. Nothing in `src/` is touched until both baselines exist.
