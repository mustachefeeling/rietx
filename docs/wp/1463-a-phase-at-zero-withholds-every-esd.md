# WP-1463 — a phase at zero withholds every esd

Milestone: unscheduled · Status: 🔄 2026-09-28 — claimed by @yue-here
Track: What fires, and what stays silent
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
scales in the table sit below that edge. *Superseded in part 2026-09-28:* the
first edge is an overflow, not this underflow (§ Findings).

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

**An interval without an esd exists since WP-1320.**
`Refinement.profile_fraction(data, phase)` profiles one phase's weight fraction
along its width and returns the admissible range
(`FractionProfile.range_low`/`range_high`). Where the fit carries no esd it
still returns the range, while `excess` is `None` and
`QPA_FRACTION_UNDETERMINED` stays silent by design. A finding this WP adds may
point at it.

### Findings (2026-09-28, at `154c33da`)

**The state reproduces on main.** The fixture is `_absent_phase_inputs` on
`synthesize()`. A wrapper lets TRF finish, then moves the absent scale's
internal value u and re-evaluates the residual and Jacobian there, so every
post-fit step runs as in production. Two plans were used: `mccusker_default`,
and a two-stage plan freeing only the scales, background, phase 0's cell and
the zero.

| u | S | σ(S) | QPA esds | `at_bound` |
|---|---|---|---|---|
| natural | 4.2e-135 / 1.6e-39 | 7.66e-9 / 2.83e-7 | present | False |
| −300 | 5.1e-131 | 7.66e-9 / 2.83e-7 | present | False |
| −370 | 2.0e-161 | 7.66e-9 / 2.83e-7 | present | False |
| −380 | 9.3e-166 | None | None | False |
| −400 | 1.9e-174 | None | None | False |
| −700 | 9.9e-305 | None | None | False |
| −800 | 0.0 | None | None | False |

Values separated by a slash are the two plans. The other phase's esd is
2.99e-5 under `mccusker_default` and 3.06e-3 under the scale-only plan,
identical to four figures wherever it is present. No finding names the loss
under either plan.

**Two edges, and the WP's reading had the second one.** Measured on the
captured Jacobians:

| u | max \|column\| | d² as computed | 1/d² |
|---|---|---|---|
| −370 | 1.8e-153 | 1.8e-305 | 5.6e+304 |
| −375 | 1.2e-155 | 8.0e-310 (subnormal) | overflows |
| −380 | 8.3e-158 | 3.6e-314 (subnormal) | overflows |
| −400 | 1.7e-166 | 0.0 | — |
| −800 | 0.0 | 0.0 | — |

`normal_covariance` forms the internal variance as K·(1/d)², where K is the
inverse of the equilibrated matrix. That product leaves the double range once
d falls below about 7.5e-155. So the esd is lost at u ≈ −375, where d² is still
nonzero. The `d == 0` underflow the WP named arrives about seven orders later,
near u = −400. A scaled norm alone (option 1 as written) would therefore
change nothing. The internal variance at u = −380 is about 1e+330 and has no
double. The internal esd, about 1e+165, does. So does the physical esd
σ(u)·esd, which is 7.66e-9 as at u = −300.

**At S = 0.0 the column is zero by every route.** u has passed −745, so
dS/du = σ(u) is exactly 0. The analytic scale branch declines a zero scale and
the column falls to the finite-difference path. That perturbs u by 8e-4 and
decodes S = 0.0 again, so it returns zeros too. No numerical repair recovers a
direction the parameterisation has lost. 13 of the 16 real cases sit here.

**Option 2 measured: a solver floor moves every fit and does not stop the
loss.** An internal lower bound of −700 on every softplus entry changes TRF's
Coleman-Li scaling for every column with a positive gradient. The synthetic
LaB₆ fit moved by up to 4.5e-6 esd (`instrument.profile.w`), with Rwp equal to
six figures. The absent scale went *deeper*, to 1.1e-189, and its esd was still
lost.

**Option 3 on its own arithmetic.** With the absent scale held at zero,
W₀ = S₀·(ZMV)₀ / S₀·(ZMV)₀ ≡ 1 on the two-phase fixture, so σ(W₀) = 0. That is
the confident wrong singleton root CLAUDE.md forbids. The option was rejected
on this alone, so GSAS-II and TOPAS were not read.

**Why `PHASE_UNCONSTRAINED` stays quiet.** `_phase_support_diagnostics` skips
a phase that has no free non-scale parameter, no hold and a line in range. The
scale-only plan reaches the answer that way and emits no `PHASE_UNCONSTRAINED`,
even at S = 0.0. That fits the series, but its plan was not re-read. The
diagnostic's docstring says deliberately that a free scale alone is not its
subject.

**`at_bound` on the absent scale.** Its residual cosine is 0.030 at every u
down to −400, above `BOUND_HIT_COS_MIN` and pushing outward. So the WP-1434
conjunction, if asked in physical space, would say True. `BOUND_HIT`'s advice
is "widen the bound or fix the parameter", which is wrong for a scale that
cannot go negative. A zero width, a common state, would get the same advice.

**Siblings of the squared norm.** The same `norm(J, axis=0)` underflow reads a
tiny column as zero in `_residual_cosine` (which feeds `at_bound`),
`identifiability.soft_modes`, the exchangeability scan and
`statistics.background_absorption`.

### Decision (2026-09-28)

1. **The esd is computed wherever a double can hold it.** Columns whose
   largest entry leaves [2⁻⁴⁰⁰, 2⁴⁰⁰] are rescaled by an exact power of two
   before the normal matrix is formed. A live column whose internal variance
   overflows takes its esd as (1/d)·√K rather than √(K·(1/d)²), and its
   correlations from K. Every other column's arithmetic is unchanged, so an
   ordinary fit's esds and correlations stay bit-identical. This carries the
   10⁻¹³⁵ answer down to about 10⁻³⁰⁰.
2. **Where the column is exactly zero, the QPA esds stay `None` and a new
   warning, `QPA_ESD_UNAVAILABLE`, names the phase.** It points at
   `profile_fraction` for an interval.
3. **`at_bound` is `None` on a free column sitting on its transform's
   asymptote.** A softplus floor is not a limit the solver sees, so the
   conjunction cannot be asked there. A value further than a hundredth of an
   esd from it still reads `False`.
4. **`PHASE_UNCONSTRAINED` keeps its subject.** The comment in the QPA block
   is corrected, and the new finding names the phase instead.
5. **Every site that squares a Jacobian column for its norm takes the same
   rescaling**: `_residual_cosine`, `soft_modes`, `block_projection_r2` and
   the single-column branch of `one_parameter_gains`. The exchangeability
   loadings and the group branches are left. A tiny column there is cut by
   `lstsq`'s relative cutoff, which a norm repair does not reach.

## Non-goals

- A trace phase's confident esd across several basins. That is WP-1320's
  probe.
- Cell runaway on a supported phase. That is issue #374 and PR #385.

## Tasks

- [x] Reproduce on main. Drive a synthetic absent scale below 10⁻¹⁶² and to
      0.0: a longer flat-direction stage, or the internal value set on a table
      in a unit test. Record which esds go `None` and which findings fire. If
      no plan reaches the state, write that here and re-rate this WP.
- [x] Confirm or refute the underflow reading: the dead-column test with and
      without a scaled norm, on the reproduced state.
- [x] Decide between options 1, 2 and 3 with those numbers, and write the
      decision and its evidence here.
- [x] A withheld weight-fraction esd emits a finding naming the phase whose
      scale withheld it. Check `SEQUENTIAL_PERSISTENT_FINDING` aggregates it
      across a series.
- [x] `at_bound` on a softplus entry at its floor: `True` with the pinned
      `BOUND_HIT` consequence, or `None`. Never an untested `False`.
- [x] Correct the comment in the QPA block that says `PHASE_UNCONSTRAINED`
      names the phase, or make it true. First find why it stayed quiet on 15
      of the 16.
- [x] Tests: the reproduced state, both sides of the underflow edge, and a
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
