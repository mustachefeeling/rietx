# WP-1463 — a phase at zero withholds every esd

Milestone: unscheduled · Status: ⬜
Depends on: — (1320 soft: the other QPA esd question, a trace phase with a confident esd)
Priority: P2 2026-09-25 — 16 of 48 patterns of a real series lost every weight-fraction esd with no finding naming why, and the agent's hand propagation reached its deliverable

## Goal

When one phase's scale falls to zero, the other phases' weight-fraction esds do
not vanish in silence. Either they are computed, or a finding names the phase
that withheld them. The answer does not depend on whether that scale ended at
10⁻¹³⁵ or at 10⁻¹⁷⁹, which today it does.

## Context

**The evidence.** A 2026-09-25 transcript review read a second agent session on
`in-situ series 1` in the private `yue-here/rietx-corpus-map`. Quote only what
the runs did (CONTRIBUTING, WP-1450). The session ran main's source at
`2d42303a` and chained 48 patterns in both directions with
`SequentialRefinement`. In 16 of the 48 final results, every phase's
`weight_fraction_stderr` is `None`. In each of the 16, one phase's scale ended
at or below 10⁻¹⁶² with `stderr=None` and `at_bound=False`:

| scale value | results |
|---|---|
| exactly 0.0 | 13 |
| 1.8e-308, 3.9e-191, 6.2e-181, 5.4e-179 | 1 each |

No finding names that phase or the withheld esds on 15 of the 16.
`PHASE_UNCONSTRAINED` fired on one. `BOUND_HIT` fired on eight, never about
that scale. The agent propagated the scale esds by hand, without covariance,
and its report calls the results lower bounds.

**Why the block goes.** `refine.py` (the QPA block, `blind =
table.unmeasured_rows(...)`) computes a covariance for the scales only when no
scale is unmeasured, following root CLAUDE.md's rule that consumers mark and
never clamp: "QPA the *whole* block, since W normalises by a sum". The comment
there says the unmeasured scale "is the same phase `PHASE_UNCONSTRAINED`
names". That held on 1 of the 16. `_qpa_unavailable_diagnostics` runs only
when `compute_qpa` returns `None`, so a result carrying a QPA with every esd
`None` carries no finding about it. Why `PHASE_UNCONSTRAINED` stayed quiet on
the other 15 is not yet known.

**Why the scale is unmeasured: consistent, not yet measured.**
`optimize.statistics.normal_covariance` takes `d = sqrt(diag(JᵀJ))` and marks a
column dead where `d == 0`. A softplus scale's internal column is
σ(u)·∂r/∂S ≈ S·∂r/∂S. An entry below about 1.5·10⁻¹⁶² squares to zero (the
smallest double is 4.9·10⁻³²⁴), so the column is declared dead although it is
not. At S = 0.0 exactly, u has passed −745 and `log1p(exp(u))` has underflowed
(the softplus clause in root CLAUDE.md), so σ(u) is zero too. All 17 dead
scales in the table sit below that edge.

**On current main the trigger is narrower than "a scale at the floor".** The
block and `normal_covariance` are unchanged since `2d42303a` (diff checked
2026-09-25, at `6641c8cf`). A synthetic check used public data: the LaB₆
pattern of `tests/test_refine_synthetic.synthesize` fitted with
`tests/test_absent_phase._absent_phase_inputs` (a host and an absent copy). The
absent scale ended between 2.8e-28 and 4.2e-135 over ten fits and three
plans. Its esd was finite every time (7.7e-9 or 3.1e-7), and every QPA esd was
present. The same absent phase therefore gets esds at 10⁻¹³⁵ and loses them at
10⁻¹⁷⁹, depending on how far TRF walked u down a flat direction. That fits the
underflow reading, and it is the first thing to measure. A tiny start does not
reach the state either: starts from 10⁻¹²⁰ down to 0.0 ended between 10⁻²⁸
and 10⁻³⁹.

**`at_bound` on the same state.** `staged.bound_findings` skips a column whose
nearer internal limit is infinite (`if not np.isfinite(limit): continue`). A
softplus entry with `min=0` has an internal lower limit of −∞, so a scale
sitting at 0.0 reports `at_bound=False`. WP-1076's rule applies: a `False`
nobody tested reads as an answer. `BOUND_HIT` and `at_bound` are pinned
set-equal (`tests/test_bound_hit_at_convergence.py`), so `True` here would put
a `BOUND_HIT` on every absent phase. `None` may be the honest state. Decide
with the rest.

**Options, to decide with the measurements.**

1. Numerical. Judge a column dead on a scaled norm (divide by its largest
   entry before squaring), so a column of 10⁻¹⁷⁰ is treated as one of 10⁻¹³⁵
   is today. This fixes the tiny values and leaves exact 0.0.
2. A floor. Keep a softplus entry's internal value above the underflow edge.
   `MARCH_R_MIN` is the precedent for a real floor where the transform's
   promise fails. The state at 0.0 then cannot arise. Measure what a floor
   does to TRF's step on a flat direction (WP-1110's lesson: a bound changes
   the step even where it is never reached).
3. Policy. Treat a scale at its floor as a phase held at W = 0, and compute the
   other phases' esds from the rest of the block, with a finding saying so.
   This argues against the invariant's reasoning, so it needs its own case: a
   scale at zero has a physical gradient and an active limit, which a
   gradient-free column does not. Read first how GSAS-II and TOPAS quote a
   fraction's esd when another phase refines to zero. Claim nothing from
   either before reading it.

Whichever lands, a withheld QPA esd never goes silent again.

## Non-goals

- A trace phase's confident esd across several basins. That is WP-1320's
  probe.
- Cell runaway on a supported phase. That is issue #374 and PR #385.

## Tasks

- [ ] Reproduce on main. Drive a synthetic absent scale below 10⁻¹⁶² and to
      0.0: a longer flat-direction stage, or the internal value set on a table
      in a unit test. Record which esds go `None` and which findings fire. If
      no plan reaches the state, write that here and re-rate this WP.
- [ ] Confirm or refute the underflow reading: the dead-column test with and
      without a scaled norm, on the reproduced state.
- [ ] Decide between options 1, 2 and 3 with those numbers, and write the
      decision and its evidence here.
- [ ] A withheld weight-fraction esd emits a finding naming the phase whose
      scale withheld it. Check `SEQUENTIAL_PERSISTENT_FINDING` aggregates it
      across a series.
- [ ] `at_bound` on a softplus entry at its floor: `True` with the pinned
      `BOUND_HIT` consequence, or `None`. Never an untested `False`.
- [ ] Correct the comment in the QPA block that says `PHASE_UNCONSTRAINED`
      names the phase, or make it true. First find why it stayed quiet on 15
      of the 16.
- [ ] Tests: the reproduced state, both sides of the underflow edge, and a
      series in which one phase leaves.
- [ ] Skill: `references/numbers.md`, the row on quoting a weight fraction's
      esd, says what a `None` means and what the finding names.

## Acceptance

On a synthetic fixture whose absent scale ends at 0.0, and on one whose scale
ends near 10⁻¹⁷⁰, the other phases' weight-fraction esds are either present
and equal to the 10⁻¹³⁵ case within rounding, or `None` beside a finding
naming the absent phase. `at_bound` on that scale is not `False`.

```sh
.venv/bin/python -m pytest tests/test_absent_phase.py tests/test_bound_hit_at_convergence.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1110 item 14 (Jacobi equilibration, `_cov_free`, consumers mark), WP-1076
  (a defaulted value reads as an answer), WP-1434 (`bound_findings`), WP-1333
  (`COVARIANCE_UNAVAILABLE`, the other way an esd goes `None`).
- van der Sluis, A. (1969). Condition numbers and equilibration of matrices.
  *Numerische Mathematik* 14, 14-23.

## Handover log

- **2026-09-25** — created by a transcript review of a second agent session on
  `in-situ series 1`. The table is from that session's pickled results. The
  synthetic check and the code reading are this review's. Next: the
  reproduction, since the synthetic case has not yet reached the state.
