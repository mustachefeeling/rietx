# WP-1124 — warm-series continuation probe: seed the chain along its tangent

Milestone: v1.1 · Status: ✅ 2026-08-22 — clean negative: B8 retires for series
speed, and the band it was aimed at turns out to be discarded ladder rungs
Depends on: WP-1111 (harness + counting scaffold), WP-1123 (the schedule the
baseline runs)

## Goal

A measured per-pattern decomposition of the warm-series band on the current
tree, and a go/no-go verdict on predictor seeding — extrapolating each
pattern's starting values along the chain's trajectory instead of copying the
predecessor's endpoint (`docs/solver-survey.md` §2.B8) — judged on whole-chain
evaluations, rung escalations and answer agreement against the copy seed.
A probe: the deliverable is the verdict and its numbers, not shipped code, and
it closes ✅ on a clean negative exactly as WP-1114 did.

## Context

**The target this probe serves is v1.1's one remaining gating target.** The
acceptance asks for warm-started series per-pattern wall in the ~1 s band;
WP-1123 measured the ten-pattern trigger series at 57.2-57.6 s, ~5.7 s a
pattern, on the merged tree — and the cold trigger fit alone is 5.67-5.70 s,
so the warm patterns are averaging near the cold cost. No WP owns this front
(ROADMAP § Current focus); this probe decides whether B8 is the WP that
should.

**Why seeding, when WP-1113 just retired a seed.** The cross-correlation
*shift* seed retired because the count mechanism inside one fit is a ridge
walk no rigid 2θ seed reaches. A series is a different shape: each pattern's
truth moves smoothly along the series coordinate (the harness case ramps
every cell 100 ppm/step), and the copy seed is a zeroth-order predictor of
that motion. B8's claim is that a first-order predictor lands closer, and
closer matters twice here:

- **Fewer iterations per warm fit** — the direct effect.
- **Fewer rung escalations** — the amplified one. WP-1123's sign-change
  finding: the chained series flipped from 1.04× worse (1705 evaluations
  against 1634) to 1.12× better (1603 against 1792) between two trees one
  commit apart, with nothing about the schedule changed, because a bounded
  per-fit difference becomes a rung escalation or a rung avoided and the
  chain integrates it. Warm-start quality is the chain's amplifier. The
  escalation base rate in the opening baseline (WP-1111, old tree): one
  pattern in nine escalated to `warm_staged` at 525 iterations over both
  rungs, ~4× the median pattern cost. The ladder's own pricing
  (`sequential.py`, WP-0505/1051): 838-904 iterations warm-collapsed, 1623
  warm-staged, 2863 cold.

The same finding is this probe's method warning: **every claim is measured on
the chain, both directions, never inferred from one fit** — the standing rule
root CLAUDE.md carries ("a series is measured, never assumed").

**The two predictors, cheap first.**

1. *Secant*: seed pattern k+1 at `θ_k + (θ_k − θ_{k−1})` for every carried
   free path, in physical values. Costs nothing.
2. *Gauss-Newton tangent*: one linear step against the next pattern's data
   from pattern k's converged state — solve `(JᵀWJ)·δ = JᵀW·(y_{k+1} −
   y_calc,k)` with J rebuilt once at that state. Costs ~one Jacobian per
   pattern, which the comparison must price in (the read-out is whole-chain
   evaluations *including* the predictor's own).

Two traps to state up front. Extrapolation in physical values can leave a
bound — a softplus-transformed width sitting near zero extrapolates negative
— so the probe clamps into the entry's bounds before setting; a refused
`set_values` is a probe bug, not a finding. And the harness ramp is smooth
and simulated, which is the *favourable* case for any predictor: a clean win
here licenses the landing WP, it does not prove the trigger session's real
data behaves the same. The real 68-pattern series is the confirming step —
ask the maintainer for the dataset rather than working around it.

**The probe seam needs no library change.**
`SequentialRefinement.fit(prepare=…)` (`sequential.py`) is called on the
warmed models just before each pattern's fit — it exists for exactly what a
`carry` glob cannot express — and `on_result` retains the previous accepted
states the predictors need. The copy baseline is the untouched default
(`_carry_into` over `carry=("*",)`). Cases: the harness's `trigger-series`
(ten patterns, 100 ppm/step cell ramp, `refit="single"`) and
`trigger-series-stages`; counts via the WP-1111 scaffold
(`examples/bench_refinement.py --cases trigger-series --repeats 3`).
`direction="both"` is a read-out, not an option: a predictor changes the
path, and the path-dependence check (`SEQUENTIAL_PATH_DEPENDENT`) must not
worsen under it.

## Non-goals

Shipping a predictor default or any change to `_carry_into`/the ladder (that
is the landing WP, opened only on a go verdict); the per-reflection 19.4 %
front (WP-1121 named it; no WP owns it); the tangent-as-sensitivity output
B8 also promises (scientifically interesting, nothing to do with the
verdict); the model-cost estimate (deferred by 1113); any Rwp-judged claim.

## Findings

All numbers: `[dev]` venv only (**no jax, no torch**), darwin/arm64, python
3.12.12, numpy 2.5.2, `rietx` 1.1.0.dev0, best-of-3 on an idle machine, per
root CLAUDE.md § Numbers. `examples/bench_refinement.py` for §1, the probe's
own `examples/bench_series_predictor.py` for the rest.

### 1 — the band decomposed, and it is not shaped like the target (2026-08-22)

Baseline on this tree, the acceptance command verbatim:

| case | wall (s) | nfev | njev | Rwp |
|---|---|---|---|---|
| `trigger-series` (`refit="single"`, the default) | **57.66-57.96** | 1603 | 1315 | 0.01943 |
| `trigger-series-stages` (`refit="stages"`) | **35.76-35.97** | 1253 | 906 | 0.01944 |

The nfev reproduces WP-1123's **1603** exactly, so this is the same tree
measuring the same fits — worth stating because this session rebuilt the venv
(it was missing `numba`, i.e. the compiled tier WP-1115 made the default was
**off**; every number here would otherwise have been the fallback's).

**The harness was measuring the cheap half of the expensive patterns.** A
pattern emits one `fit_start`/`fit_end` pair *per ladder rung*, and
`_run_series` kept the last of each kind — so an escalated pattern reported
only the rung that succeeded, which is by construction the one cheap enough to
be kept. Its docstring already claimed the whole escalation. Fixed here (the
pairs are accumulated and summed, and `rungs=` prints the breakdown), which
changes what the case says about itself:

| pattern | reported before | actually | rungs |
|---|---|---|---|
| 1 | 3.21 s | **20.19 s** | `warm`=17.01 + `warm_staged`=3.18 |
| 6 | 3.13 s | **18.82 s** | `warm`=15.62 + `warm_staged`=3.20 |

**32.63 s of the 57.45 s series — 57 % — is wall spent in first rungs the
ladder then threw away.** So "~5.7 s a pattern" is an average over a bimodal
distribution, and neither mode is at it: seven clean warm patterns at
**0.89-2.32 s** (median 2.03), already at or just above the ~1 s target, and
two at 18.8-20.2 s. Delete the two escalations and the same ten patterns cost
~24.8 s with no per-evaluation work whatsoever.

**And the shipped default first rung is the slower one on this case.**
`refit="stages"` runs **1.61×** faster than `refit="single"` — 35.76-35.97 s
against 57.66-57.96, the two measured back to back in one process — with
**zero** escalations, every pattern 2.82-3.73 s at 95-140 iterations. The
machine-independent half of that says the same thing and is the one to quote:
**1253 nfev against 1603** and **906 njev against 1315**, deterministic and
reproduced in every run this session made. That inverts WP-0505's small-cell
measurement (904 collapsed against 1623 staged) in the direction WP-1110's
agent round hit on a real trigger-shaped model. `_ladder`'s docstring already
says which rung is cheaper is a property of the model; the measurement is that
on *the milestone's own trigger workflow* it is the staged one. Not this WP's
to change (§ Non-goals), and the largest single number on the table.

### 2 — how the two arms were built, and the one rule that shapes both

No library change: both are `SequentialRefinement.fit(prepare=…)` closures in
`examples/bench_series_predictor.py`, so a negative verdict costs nothing to
act on (WP-1114's discipline). Three gating rules were forced by the seam
rather than chosen, and each is load-bearing for reading the numbers:

- **The predictor is the first rung only.** `prepare` is called on *every*
  rung, the cold rescue included, where it would be handed the initial model
  rather than a warm one. So each arm acts once per pattern and returns on any
  later call, leaving `warm_staged` and `cold` identical to the copy arm's.
- **A predictor cannot seed the first two patterns of a pass** — it needs two
  converged points, and pattern 1's only predecessors are the cold answer and
  the initial guess, whose difference is a cold-start correction rather than a
  step along the series. This is a property of the method, not of the probe,
  and § 5 is where it bites.
- **Extrapolation is clamped as a step, not as a value**, so a parameter at its
  bound moves by zero rather than by a repaired amount; the tangent step is
  additionally **corrector-checked** (residual re-evaluated, seed kept only if
  the cost fell). Its two residuals and one Jacobian per pattern are charged to
  that arm's totals — the counting scaffold wraps scipy's entry point, which
  the predictor does not go through, so they are added rather than assumed.

**Wall clock is compared between arms inside one run, never across runs.** The
same `refit="stages"` copy chain measured 35.76-35.97 s in § 1 and 41.77-42.93 s
in § 4 at an identical **1253** nfev — 1.17× of pure machine state, larger than
most of the effects below.

### 3 — `refit="single"`: evaluations fall, wall does not (2026-08-22)

Ten patterns, forward, best-of-3, all three arms in one process:

| arm | wall (s) | nfev | njev | escalations | discarded-rung wall |
|---|---|---|---|---|---|
| copy | 57.42-58.05 | 1603 | 1315 | 2 | 32.63 s |
| secant | 54.57-60.96 | **1495** (1.07×) | 1220 | 1 | 17.04 s |
| tangent | 58.70-59.62 | **1287** (1.25×) | 975 | 1 | 26.19 s |

Both cut whole-chain evaluations well past the copy baseline's spread — nfev is
deterministic here, 1603 in every repeat — and neither raises the escalation or
quarantine count. **And the series wall does not move.** The secant's range
straddles copy's; the tangent is inside it at 1.25× fewer evaluations.

The § 1 decomposition says why, and it is the whole story of this arm.
Evaluations are not what the band is made of. Each predictor removed one of
copy's two escalations and made the surviving one *more expensive*: the
tangent's pattern 6 burned **26.19 s** in its discarded rung against copy's
15.60 s at a similar iteration count (492 against 500). **A predictor changes
which pattern's collapsed rung fails, not whether one does** — and the cost of
one that does is set by `max_iter` on a ~30-parameter TRF call, which no seed
reaches.

**The answers agree, once the degeneracy is taken out.** Raw disagreement looks
alarming — secant median 1.592 esd, max 7.296 — but every one of the four worst
paths is the exactly degenerate width family WP-1123 named (`instrument.profile.x`
7.30, `phases.1.lor_size` 6.46, `phases.0.lor_size` 6.45, `phases.3.lor_size`
2.14), which sum to one width. Outside it: **secant median 0.105 esd, max
0.246; tangent median 0.047, max 0.262.** So in this regime a predictor moves
the split and not the answer, and endpoint agreement is *not* what kills B8.

### 4 — `refit="stages"`: both arms cost more, and the tangent breaks the chain

The regime with no escalation catastrophe to swamp the effect — which makes it
the clean measurement of what a predictor does on its own, and it is negative:

| arm | wall (s) | nfev | njev | Rwp, patterns 6-9 | diagnostics added |
|---|---|---|---|---|---|
| copy | 41.77-42.93 | 1253 | 906 | 0.01950-0.01944 | — |
| secant | 46.38-49.16 | **1458** (0.86×) | 1052 | 0.01950-0.01944 | — |
| tangent | 84.34-85.54 | **2087** (0.60×) | 1647 | **0.02252-0.02259** | `SEQUENTIAL_DISCONTINUITY` |

The secant costs **1.16× more** evaluations, raising iterations on nearly every
pattern (168 against 140, 138 against 115, 168 against 114, 145 against 112).

The tangent does something worse than cost more. Pattern 6 was seeded into a
different basin, took **941 iterations / 45.73 s**, and converged at Rwp
**0.02252** against copy's 0.01950 — and then, because that endpoint is what
the chain carries, **every successor inherited it**: patterns 7, 8 and 9 all
land at 0.0224-0.0226. `phases.2.cell.b` ends **186 esd** from the copy answer
and `phases.2.cell.a` 175 esd, both outside the degenerate family. The reseed
fence never fired: 0.02252 against an accepted median near 0.0195 is 1.15×,
inside `RESEED_FACTOR`, so the damage was permanent and the only report was one
`SEQUENTIAL_DISCONTINUITY`.

**The corrector check passed on that pattern.** The Gauss-Newton step *did*
lower the residual at the warm state — it is in `applied`, not `rejected` — and
still led the staged refit into a worse minimum. So a cost-decreasing predictor
step is not a safety property: a better starting point by cost can be a worse
one by basin, which is the same width-valley local minimum WP-1113 fenced in
`optimize/lm.py`, reached from a new direction.

### 5 — `direction="both"`: both predictors introduce path dependence

The read-out the WP declared not optional, `refit="single"`, one repeat:

| arm | wall (s) | nfev | `SEQUENTIAL_PATH_DEPENDENT` |
|---|---|---|---|
| copy | 144.54 | 3325 | **absent** |
| secant | 105.96 | 2473 | **fires** |
| tangent | 97.26 | 2150 | **fires** |

The copy chain's two directions agree within their esds. Both predicted chains
do not, and the mechanism is § 2's second rule rather than an implementation
detail: a predictor cannot seed the first two patterns of a pass, so the
forward chain is seeded on patterns 2-9 and the backward one on 7-0. **The
method is necessarily asymmetric in the series coordinate, and the
path-dependence check is precisely the instrument that sees it.** A first-order
predictor buys its accuracy by assuming a direction of travel; running the
series the other way is then not the same experiment, which is the one thing
`direction="both"` exists to refuse.

### 6 — verdict: **B8 retires for series speed**, and the band is elsewhere

The kill criterion was pre-registered with three clauses, any of which retires
the item. Clause 1 (evaluations) does **not** fire on `refit="single"` — both
arms beat a zero-spread baseline — but does fire on `refit="stages"`, where
both cost more. Clause 2 (escalations, quarantine) does not fire anywhere.
**Clause 3 fires cleanly**: both arms worsen `direction="both"` disagreement,
from absent to reported.

The bound, measured, for the survey note. The most a predictor bought was
**1.25× fewer whole-chain evaluations** (tangent, `refit="single"`: 1287
against 1603) **for no wall-clock reduction at all** — the arms' ranges overlap
the copy baseline's. Against that: **1.16-1.67× more** evaluations and up to
**2.0×** the wall in the staged regime, one silent chain break costing 186 esd
on a cell and 0.003 Rwp propagated across four patterns, and path dependence
introduced in both arms. The favourable case was tested — a smooth simulated
100 ppm/step ramp, which is the best case any predictor gets — and it did not
pay there, so the real-data confirming step is moot and the 68-pattern dataset
is not needed to close this.

**What the band actually is.** § 1 is the finding this probe leaves behind:
57 % of the `trigger-series` wall is first rungs the ladder discards, seven of
the nine warm patterns are already at 0.89-2.32 s, and `refit="stages"` runs
the same chain 1.61× faster with zero escalations. The lever on the warm-series
band is **which rung the ladder starts on**, not what the rung starts from. That
is a `_ladder`/`refit` question and is this WP's § Non-goals; it wants its own
WP, and WP-0505's opposite small-cell measurement means the answer is adaptive
rather than a flipped default.

## Tasks

- [x] **Decompose the band first**: per-pattern wall / nfev / rung table for
      `trigger-series` and `trigger-series-stages` on the current tree — the
      post-1123 "after" no record holds — and where the ~5.7 s average sits
      against the 5.67-5.70 s cold fit. This is the baseline every later row
      compares against, and it says how much of the band is escalations
      before any predictor runs.
      *(2026-08-22: § Findings 1; the harness's per-pattern collector fixed in
      the same commit, because the number it printed omitted the escalations
      this task exists to count.)*
- [x] **Secant probe**: `prepare`/`on_result` implementation, both
      directions; whole-chain evaluations, escalation count, per-pattern
      wall, endpoint agreement (esd-relative, per pattern) against the copy
      baseline.
      *(2026-08-22: § Findings 2-5. 1.07× fewer evaluations on `refit="single"`
      for no wall change, 1.16× **more** on `refit="stages"`, agreement 0.105
      esd median outside the degenerate width family, and
      `SEQUENTIAL_PATH_DEPENDENT` introduced.)*
- [x] **Gauss-Newton tangent probe**: same read-outs, predictor cost
      included in the totals.
      *(2026-08-22: § Findings 2-5. The best evaluation number in the probe —
      1.25× on `refit="single"` — and still no wall change; on `refit="stages"`
      1.67× more evaluations and a silent chain break, 186 esd on a cell,
      through a step its corrector check **passed**.)*
- [x] **Verdict** in § Findings, and the survey annotated: go — open the
      landing WP with the measured ceiling — or retire B8 for series speed
      with the measured bound, in `docs/solver-survey.md` §2.B8's dated note
      either way.
      *(2026-08-22: § Findings 6 — **retired**, kill-criterion clause 3. Survey
      §2.B8 and §5 annotated with the bound.)*

## Acceptance

The verdict is recorded with its table in § Findings, quoting venv and
platform per root CLAUDE.md § Numbers. Kill criterion, pre-registered: if
neither predictor reduces whole-chain evaluations beyond the run-to-run
spread of the copy baseline, or either raises the escalation/quarantine
count or worsens `direction="both"` disagreement, B8 retires for series
speed and the survey note says so with the bound.

**Met, 2026-08-22 — closed ✅ on a negative** (§ Findings 6): clause 3 fires,
both arms turning `SEQUENTIAL_PATH_DEPENDENT` from absent to reported, and
clause 1 fires in the `refit="stages"` regime.

*One honest note on the closing run of the first command.* It reproduced every
**count** exactly — 1603/1315 and 1253/906 nfev/njev, Rwp 0.01943 and 0.01944,
the same two escalations with `rungs=34.04+5.39` and `30.49+9.48` — and its
wall clock is **not quotable**: the machine had gone to load average 12.9
(a browser), and the same fits read 58.96-114.66 s against the 57.66-57.96 s
recorded in § 1. That is the § 2 caution firing on this WP's own acceptance,
which is the best evidence for it: **the counts are what survive a busy
machine, and every wall figure in § Findings comes from an arm comparison made
inside a single run.** The tables above stand on the idle runs.

The probe's own command, which reproduces every table in § Findings 3-5:

```sh
.venv/bin/python examples/bench_refinement.py --cases trigger-series,trigger-series-stages --repeats 3
.venv/bin/python examples/bench_series_predictor.py --patterns 10 --repeats 3 --refit single
.venv/bin/python examples/bench_series_predictor.py --patterns 10 --repeats 3 --refit stages
.venv/bin/python examples/bench_series_predictor.py --patterns 10 --repeats 1 --refit single --direction both
.venv/bin/python -m ruff check src tests examples
```

## References

- `docs/solver-survey.md` §2.B8 (predictor-corrector continuation), §5
  (the 2026-08-22 re-assessment that opened this probe).
- `docs/milestones/v1.1.md` — the 1123 narrative (sign-change finding,
  merged-tree series numbers) and the WP-1111 appendix (opening per-pattern
  table, escalation base rate).
- Allgower & Georg (1990), *Numerical Continuation Methods*, Springer —
  predictor-corrector continuation; the tangent predictor is its Euler step.
- WP-0505/WP-1051 ladder pricing as quoted in `sequential.py`'s docstrings.

## Handover log

### 2026-08-22 (2nd session) — closed ✅ on a clean negative, and it moved the front

Seeding a chained series by extrapolating along its own trajectory does not
make the series faster, and this WP now says so with numbers instead of
leaving it as an open idea. More usefully, it found that the thing being
optimised was mis-described. The warm-series target had been read as "every
warm pattern costs about 5.7 seconds"; in fact seven of the nine warm patterns
already finish in about one to two seconds and two of them take twenty, because
the ladder's first attempt fails on those two and the work is thrown away. So
**57 % of the series time is spent on attempts that get discarded**, and the
number everyone had been quoting was an average of two things, sitting at
neither. Anyone can now see this directly: the benchmark had been reporting
only the attempt that *succeeded*, which is by construction the cheap one, and
it now prints every attempt. The practical consequence is that the way to make
in-situ series fast is to change which strategy the chain tries first, not what
it starts that strategy from — and one already-shipped setting (`refit="stages"`)
does the same ten patterns with a third fewer solver evaluations and none of
the failed attempts.

*Done*: all four tasks. Task 1 landed with a fix to the harness's per-pattern
collector (`62df88d4`), tasks 2-4 with the probe and the verdict (`cf22fb13`).
Nothing shipped in `src/` — both predictor arms are closures over the existing
`SequentialRefinement.fit(prepare=…)` seam in
`examples/bench_series_predictor.py`, which is WP-1114's discipline and the
reason a negative costs nothing to act on. § Findings 1-6 hold every table;
`docs/solver-survey.md` §2.B8 and §5 carry the dated retirement with the bound,
and the v1.1 record carries the narrative.

*Measured* — `[dev]` venv only (**no jax, no torch**), darwin/arm64, python
3.12.12, numpy 2.5.2, `rietx` 1.1.0.dev0:

- Baseline reproduces WP-1123's **1603** nfev exactly, so this is the same tree
  measuring the same fits.
- `refit="single"`: copy 1603 nfev / 57.42-58.05 s, secant **1495**, tangent
  **1287** — and **no arm moves the wall**, all three ranges overlapping.
- `refit="stages"`: copy 1253 nfev, secant **1458**, tangent **2087**; the
  tangent additionally broke the chain (Rwp 0.02252 against 0.01950 inherited
  by four successors, `phases.2.cell.b` **186 esd** out, one
  `SEQUENTIAL_DISCONTINUITY` and no reseed).
- `direction="both"`: copy has **no** `SEQUENTIAL_PATH_DEPENDENT`; both arms
  raise it. This is the kill criterion's clause 3.
- Endpoint agreement outside the degenerate width family: secant 0.105 esd
  median / 0.246 max, tangent 0.047 / 0.262. Agreement is *not* what killed it.
- Fast selection **2619 passed / 117 skipped**, exit 0 — **unmoved** from
  WP-1122/1123's count, and correctly so: this WP added no tests and touched
  only `examples/` and `docs/`. Wall 4:29 against their 1:55, on a machine that
  had gone busy (below). The full suite was **not** run, deliberately: no
  library code changed, and the slow selection is real-data acceptance
  refinements that an `examples/` edit cannot reach.

*Gotchas for whoever measures next, both of which cost this session time*:

- **Check the venv is current before quoting any timing.** This one predated
  WP-1115 and was missing `numba`, so the compiled tier — which is what a
  default install runs — was **off**, and every number would have been the
  fallback's. `rietx.model.compiled.enabled()` is the one-line check;
  `rietx.__version__` reading 1.0.1 against `pyproject`'s 1.1.0.dev0 was the
  tell.
- **Counts survive a busy machine; wall clock does not.** The same
  `refit="stages"` chain measured 35.76-35.97 s and 41.77-42.93 s minutes apart
  at an identical 1253 nfev, and the closing acceptance run — at load average
  12.9 — read 58.96-114.66 s for fits whose every count was unchanged. Every
  wall figure in § Findings is therefore an arm-vs-arm comparison made *inside
  one run*, and the `refit="stages"` finding is stated in nfev/njev first.

*Next*, in order:

1. **The warm-series front is open and unowned, one rank down from this WP.**
   It wants a WP on the ladder's *first rung*: `refit="stages"` costs 1253 nfev
   and 906 njev against `refit="single"`'s 1603 and 1315, with zero escalations
   against two, on the milestone's own trigger workflow. The answer must be
   **adaptive, not a flipped default** — WP-0505 measured the opposite on
   small-cell standards (904 collapsed against 1623 staged), so what is wanted
   is a rule that reads which regime a model is in. `_ladder`'s docstring
   already says which rung is cheaper is a property of the model; nothing yet
   decides it per model.
2. **[1125](1125-varpro-probe.md) is the other open probe** and inherits this
   session's two measurement gotchas — filed into its `### Inherited`.
3. **Do not re-open B8 for speed without new information.** The favourable case
   was tested: a smooth simulated 100 ppm/step ramp is the best case a predictor
   gets, and it did not pay there, so the real 68-pattern dataset is not needed
   to close this and asking the maintainer for it would be wasted. B8's
   *tangent-as-sensitivity* half is untouched, was never about speed, and stays
   parked.

- **2026-08-22** — created, from the solver-survey re-assessment (§5): B8
  promoted because the warm-series band is v1.1's one remaining gating
  target and 1123's sign-change finding names warm-start quality as the
  chain's amplifier.
