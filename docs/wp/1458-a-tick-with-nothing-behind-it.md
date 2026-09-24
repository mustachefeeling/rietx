# WP-1458 — a tick with nothing behind it moves the low-angle boundary

Milestone: unscheduled · Status: ⬜
Depends on: — (1327 soft: its magnetic tick row is the case that found it)
Priority: P3 2026-09-24 — a warning goes silent when a phase with no intensity puts a tick below the first real line; the fit and its numbers are unchanged, so a user loses a warning, not a number

## Goal

`LOW_ANGLE_UNMODELLED` places "below the first reflection" at the lowest
reflection that carries calculated intensity the data could see. A phase, a
declared peak or a magnetic row that puts only an empty tick below the first
real line no longer silences it.

## Context

Issue #436 (2026-09-23), found re-running WP-1327's acceptance for PR #433
under a null magnetic group. The mechanism is on `main` and needs no
magnetism.

**The mechanism.** `refine._first_reflection_fwhm` (`refine.py:5235` at
`8fbafe5`) takes `min` over every list in the `ticks` dict that
`_build_result` made (all phases, every emission line, plus
`components.EXTRA_TICK_KEY` for declared peaks), by position only.
`_low_angle_diagnostics` (`refine.py:5266`) measures
`[two_theta_min, first_tick − 2·FWHM)` and returns `[]` when that region
holds fewer than ten channels. The docstring's rule is "the region no
reflection — of any phase, any emission line — can reach". The code applies
it as "no tick", and a tick with nothing behind it reaches nothing.

**Checked against the tree at `8fbafe5`** with the issue's script:
synthetic LaB6 from `tests/test_refine_synthetic.synthesize()`, plus an
unmodelled Gaussian hump at 4.0° (400 counts, σ 0.3°) below LaB6 (100) at
5.72°, `plan="mccusker_default"`.

| fit | Rwp | `LOW_ANGLE_UNMODELLED` |
|---|---|---|
| LaB6 alone | 0.1357 | fires: "537 channels below the first reflection (5.72° − 2×FWHM = 5.68°) carry a mean weighted-squared residual 78.68, 6.80× the whole-pattern reduced χ² (11.58)" |
| LaB6 + a cubic dummy, a = 30 Å, `scale` fixed at 1e-14 | 0.1357 | silent |

Both reproduce the issue's numbers exactly. The dummy's lowest tick is at
2.51°, below the data, so the region holds no channel.

**Cases that meet it without a contrived dummy**, from the issue: a minority
phase with a small or fixed scale and a large cell; a phase
`PHASE_UNCONSTRAINED` is holding (WP-1301 keeps its ticks); a declared
`PeakComponent` at low angle; and a magnetic row on a group the data does
not support (#433, the `"<phase> (magnetic)"` tick row).

**The design choice, which is this WP's to make and measure.** Two readings
of "a reflection that can reach the region":

- **Per phase, on the existing authority.** Drop the ticks of any phase
  whose `CompiledModel.phase_support` is below
  `forward.PHASE_SUPPORT_SIGMA` (1.0). This adds no new threshold, and
  `phase_support`'s docstring asks for no second opinion on "can the data
  see this phase". It covers the dummy and the held phase. It does not cover
  a supported phase's empty magnetic row, or a declared peak whose area sits
  at zero, since both belong to rows that are not a phase's.
- **Per reflection.** The lowest tick whose peak height at the fitted values
  exceeds `PHASE_SUPPORT_SIGMA`·σ locally: the same threshold one rank down.
  It covers every case above, but needs per-reflection heights, which the
  ticks dict does not carry. Look for where `phase_component` builds them
  before adding a second evaluation.

Measure both on the four cases above, and on the shipped acceptance fits
where the code fires today, before choosing. A choice that silences one of
those is a regression.

**The skill row changes with it.** `docs/skill/rietx/references/diagnostics.md:56`
says the region is read "every phase, every emission line". The row, and
`docs/manual/using/results.md:499`, say what the new boundary is.

## Non-goals

- The two remedies the message offers, and the 3× threshold on the
  residual. Only the boundary moves.
- Layer 0's `unmatched_calc` for the dummy's positions, which is right as
  it stands.

## Tasks

- [ ] Measure both readings on the four cases and on every fixture where
      the code fires at `8fbafe5`; record the table in this file.
- [ ] Implement the chosen boundary in `_first_reflection_fwhm`, and update
      its docstring's rule to say what the code does.
- [ ] Tests: the issue's pair (fires without the dummy, and now fires with
      it too); a held phase's ticks do not silence it; every existing
      `LOW_ANGLE_UNMODELLED` test unchanged.
- [ ] Skill: the `LOW_ANGLE_UNMODELLED` row in `references/diagnostics.md`
      names the new boundary; re-sync with `rietx skill --install . --copy`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_low_angle_region.py -q
.venv/bin/python -m pytest tests/test_skill.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

None beyond the issue and WP-1301's `phase_support`; no physics changes.

## Handover log

- **2026-09-24** — created, from the 2026-09-24 issue triage (issue #436).
  Checked against the tree at `8fbafe5`: both fits reproduce the issue's
  Rwp and message exactly, and the boundary is taken by position at
  `refine.py:5251-5254`. Next: measure the two readings before choosing.
