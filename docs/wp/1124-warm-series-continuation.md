# WP-1124 — warm-series continuation probe: seed the chain along its tangent

Milestone: v1.1 · Status: ⬜
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

## Tasks

- [ ] **Decompose the band first**: per-pattern wall / nfev / rung table for
      `trigger-series` and `trigger-series-stages` on the current tree — the
      post-1123 "after" no record holds — and where the ~5.7 s average sits
      against the 5.67-5.70 s cold fit. This is the baseline every later row
      compares against, and it says how much of the band is escalations
      before any predictor runs.
- [ ] **Secant probe**: `prepare`/`on_result` implementation, both
      directions; whole-chain evaluations, escalation count, per-pattern
      wall, endpoint agreement (esd-relative, per pattern) against the copy
      baseline.
- [ ] **Gauss-Newton tangent probe**: same read-outs, predictor cost
      included in the totals.
- [ ] **Verdict** in § Findings, and the survey annotated: go — open the
      landing WP with the measured ceiling — or retire B8 for series speed
      with the measured bound, in `docs/solver-survey.md` §2.B8's dated note
      either way.

## Acceptance

The verdict is recorded with its table in § Findings, quoting venv and
platform per root CLAUDE.md § Numbers. Kill criterion, pre-registered: if
neither predictor reduces whole-chain evaluations beyond the run-to-run
spread of the copy baseline, or either raises the escalation/quarantine
count or worsens `direction="both"` disagreement, B8 retires for series
speed and the survey note says so with the bound.

```sh
.venv/bin/python examples/bench_refinement.py --cases trigger-series,trigger-series-stages --repeats 3
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

- **2026-08-22** — created, from the solver-survey re-assessment (§5): B8
  promoted because the warm-series band is v1.1's one remaining gating
  target and 1123's sign-change finding names warm-start quality as the
  chain's amplifier.
