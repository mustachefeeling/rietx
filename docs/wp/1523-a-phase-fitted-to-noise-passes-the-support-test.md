# WP-1523 — A phase fitted to noise passes the support test

Milestone: unscheduled · Status: 🔄 2026-10-04 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: — (1420 soft: the same hold, in a chain)
Priority: P2 2026-09-29 — a frame with no phase in it reports that phase's cell with an esd and no `PHASE_UNCONSTRAINED`, depending on where the fit started; a path few fits run

## Goal

A phase the pattern does not contain is held, and named by
`PHASE_UNCONSTRAINED`, whatever the fit started from. A phase fitted to noise
no longer counts as one the data can see.

## Context

Found by WP-1469 on issue #481's blank frame: every phase scale 0, so the
pattern is background and Poisson noise alone. The frame is pattern 7 of the
issue's script, and the reproduction under References rebuilds it from the
same RNG stream.

**One ordinary fit, no chain.** The blank was fitted cold with
`mccusker_default` from two starts, 2026-09-29 at `a651a7d` (Linux x86_64,
Python 3.12, `[dev]`):

| start | cell held in stages | cell reported | scale | `PHASE_UNCONSTRAINED` |
|---|---|---|---|---|
| pattern 0's fitted models (scale 5e-4) | `cell` only, released at `profile_w` | 4.14990 ± 0.0016 Å, 0.0085 Å off the ramp | 3.1e-8 ± 2.4e-8 | no |
| the issue's unfitted models (scale 7.5e-4) | `cell`, `profile_w`, `profile` | absent (held) | 1.7e-8 ± 2.5e-8 | yes |

**Why.** `CompiledModel.phase_support` is each phase's strongest modelled
point in σ of the observation noise, and `PHASE_SUPPORT_SIGMA` is 1.0
(`model/forward.py`). At the first row's answer the blank phase's support is
**2.14σ**, while its scale is 1.3σ from zero: a scale fitted to noise lifts
the strongest point above one σ, so the phase reads as seen.
`_released_phases` (`refine.py`) releases a held column when any phase it
moves rises above that threshold at the stage's landing values, and the
diagnostic reads the same vector. Which side of 1σ a noise fit lands on
depends on the start, which is the flicker.

Relevant rules, restated:

- **Root CLAUDE.md, "A phase the data cannot see is a flat direction"
  (WP-1301).** A phase is held for the stage rather than bounded, and its
  support is re-measured at the answer. A phase that appeared is released;
  one that collapsed while solving is restored and held. `phase_support` is
  the one authority for both the bound and the diagnostic, so a change to
  what "seen" means changes both together.
- **The threshold's docstring calls 1σ "not a tuned fraction"**: it says the
  comparison is against the counting statistics the phase competes with. The
  finding here is that a single-point statistic is exceeded by a fit to pure
  noise. Before changing the number, ask what the right statistic is: the
  scale's own significance, a multi-point measure, or the strongest point
  judged against what noise alone produces.

**A second failure mode of the same statistic is already on record**, in
WP-1339's Inherited (issue #219): a phase collinear with another, absent from
the specimen, read 0.65σ, 197σ or 54-56σ support depending only on its seed,
and at 57σ took the misfit with no `PHASE_UNCONSTRAINED`. That is the ridge
case; this one is the noise case. Both say `phase_support` depends on where
the fit landed, and a replacement statistic should be checked against both.

**Why a new WP rather than a fold.** 1420 owns the hold inside a chain and
fences out "`PHASE_SUPPORT_SIGMA`, or the package deciding whether a phase is
present" in its Non-goals, which is this WP's whole subject. 1339 owns the
localisation statistic and carries the #219 finding only as context.

## Non-goals

- The chain-level consequences. 1469 already leaves a pattern above the Rwp
  fence out of the step scan, and 1420 owns a held phase re-entering a chain.
- Retuning `PHASE_SUPPORT_SIGMA` by eye. Whatever replaces the test is
  measured on the suite's absent-phase fixtures (`tests/test_absent_phase.py`,
  `tests/test_held_phase.py`) as well as on this frame.

## Tasks

- [ ] Reproduce both rows in a test from a synthetic blank frame, and record
      the support and the scale significance at each stage's landing values.
- [ ] Decide the statistic, recorded here with the measurement that chose it,
      and count what moves on the suite's absent-phase and held-phase
      fixtures (a phase that should stay released must stay released).
- [ ] Land it in `phase_support` (or beside it, as the one authority both
      consumers read), so the hold and `PHASE_UNCONSTRAINED` agree.
- [ ] Tests: the blank frame holds its cell and fires `PHASE_UNCONSTRAINED`
      from both starts; a weak but real phase is still released.
- [ ] Skill: the `PHASE_UNCONSTRAINED` row, if its meaning moves; otherwise
      "none", said here.

## Acceptance

Issue #481's blank frame, fitted alone from either start, reports no cell for
LaB6 and carries `PHASE_UNCONSTRAINED`; the suite's absent- and held-phase
tests pass unchanged or with each moved assertion justified here.

```sh
.venv/bin/python -m pytest tests/test_absent_phase.py tests/test_held_phase.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #481 (the ramp and its script); WP-1469's handover (where this was
  found); WP-1301 (the hold), WP-1458 (`phase_support` per emission line).
- The reproduction, run from the repo root:

  ```python
  # the issue's script to its first fit, then pattern 7 alone
  ref = rx.Refinement(first.fitted_structure, first.fitted_instrument)
  r = ref.fit(patterns[7], plan="mccusker_default")
  [(st.name, st.held, st.released) for st in r.stages]
  ```

## Handover log

- **2026-09-29** — created, from WP-1469's session. Both rows of the table
  measured at `a651a7d`; the support at the answer (2.14σ) was read by
  compiling the fitted models and calling `phase_support` on them. Next:
  task 1, then the decision in task 2, which is the whole WP.
