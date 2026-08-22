# WP-1127 — the ladder's first rung: which one a warm pattern starts on

Milestone: v1.1 · Status: ⬜
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
2. It raises the escalation or quarantine count, or adds any
   `SEQUENTIAL_*` diagnostic the fixed modes do not produce.
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

## Tasks

- [ ] **A second series case in the harness**: the round-robin sample-1 chain
      (eight real mixtures, small cells) as `cpd-series` / `cpd-series-stages`,
      importing the protocol wholesale from
      `tests/test_acceptance_qpa_roundrobin` the way `_trigger_series` already
      imports `qpa_plan`. Without it every rule below is tuned on the one case
      whose measurement points one way, and WP-0505's counterexample family has
      no seat. Report per-pattern wall / iterations / rung breakdown, both
      `refit` modes.
- [ ] **Baseline both cases on this tree**, both modes, the acceptance command
      verbatim: per-pattern table with the discarded-rung column, whole-chain
      nfev/njev, escalation count, and the fixed-mode winner per case. This is
      the "before" every later row is judged against; WP-1124's numbers are
      quoted for `trigger-series` and re-measured, not assumed.
- [ ] **Lever A — bound the first rung**: budget from the chain's accepted
      history, no control-flow change. Measure both cases, both modes: whole-
      chain nfev/njev, discarded wall, escalation count, per-pattern answer
      agreement in esd. State the budget rule's constants and where they came
      from (measured, never tuned to one case).
- [ ] **Lever B — learn the rung**: after an escalation, later patterns of the
      pass start on the rung that worked. Same read-outs, plus what the rule
      does when the two directions disagree about where the escalation was.
- [ ] **`direction="both"` on whichever lever survives**, both cases: the
      path-dependence read-out that retired B8. Pre-registered clause 4.
- [ ] **Land or retire.** On a go: the third `REFIT_MODES` member, a caller's
      explicit mode never overridden, `entry.rung`/`rungs_tried` carrying what
      actually ran, the docstrings in `sequential.py` carrying the measurement,
      and the default flip **priced, not taken** (WP-1123's shape). On a no-go:
      § Findings carries the bound and `src/` is untouched.
- [ ] Tests (`tests/test_sequential.py` for the rule's unit behaviour, the
      harness case asserted in `tests/test_bench_refinement.py`) + obs/calc/diff
      PNGs for the two chains to `tests/output/`.
- [ ] Docs: the survey's B8 neighbourhood gains the dated outcome,
      `../milestones/v1.1.md` takes the narrative, and any standing rule reaches
      root CLAUDE.md as a rule with a pointer — not a finding.

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
