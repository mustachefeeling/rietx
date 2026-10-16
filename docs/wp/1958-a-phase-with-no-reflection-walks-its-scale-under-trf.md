# WP-1958 — A phase with no reflection in range walks its scale under TRF

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-13 — a quoted fraction is wrong, but `PHASE_UNCONSTRAINED` and `QPA_ESD_UNAVAILABLE` fire, and only `solver="trf"` reaches it

## Goal

A phase whose fitted range holds none of its reflections keeps the scale it
was given, under every solver, and the QPA reads no fraction off it.

## Context

Found by WP-1534 (2026-10-04) and re-measured by WP-1523 (2026-10-13), which
closed without an owner for it.

WP-1534's four-phase fixture (`tests/test_scale_b_ridge.py`) fitted over
25-33° Cu Kα leaves bcc Fe no reflection. Under `solver="trf"`, two
scale-and-background stages take Fe's scale from 1e-4 to 164.7, and the QPA
then reads iron at 99.99 wt%. `PHASE_UNCONSTRAINED` fires, in its third
wording ("no reflection of phase N lies in the fitted range"), and
`QPA_ESD_UNAVAILABLE` withholds the esds, but the fraction stands. Under the
default LM driver the scale stays at its start and QPA reads iron at
0.61 wt%, which is the start value, not a measurement either.

Repro: the fixture's `_models(START_SCALES)` on `np.arange(25, 33, 0.01)`,
plan `[Stage("s", BIG), Stage("s2", BIG)]`, `solver="trf"`.

**Why.** The support hold (WP-1301, `refine._hold_unsupported_phases`) holds
an unseen phase's structural paths and "never its scale, the one direction
that is not flat". That rests on the scale having a column. With no
reflection in range it has none: the column is identically zero, so TRF's
step along it is unconstrained by the data, while LM's damped step leaves it
in place.

Relevant rules, restated:

- **Root CLAUDE.md, "A phase the data cannot see is a flat direction"
  (WP-1301).** A flat direction is held for the stage rather than bounded.
- **"A direction the data does not move has no esd rather than a small one"**
  (WP-1110 item 14): the covariance already drops the zero column; the QPA
  marks its block unmeasured. The fraction is the open half.

### Inherited

- **Decided 2026-10-16 (maintainer, from the issue triage, #954): both
  halves.** A phase with no reflection in the fitted range gets no QPA
  fraction under every solver, and its scale is held so a walked value reaches
  no later stage, chain or export. The remaining fractions are reported
  relative to the phases seen in range, and the report says so. This carries
  the absent-rather-than-zero rule (WP-1072, WP-1110 item 14) to the fraction.

- **2026-10-16, from the issue triage (#954): the reporter's answer to task
  2's choice (2026-10-14) is not in the WP.** @mustachefeeling takes the QPA
  half as the required one: no fraction for a phase with no reflection in the
  fitted range, under every solver, with the scale held beside it so a TRF fit
  does not hand a walked 164.7 to a later stage, a chain or an export. Reason:
  LM already holds the scale and QPA prints 0.61 wt%, the start value, so
  holding alone leaves the same unmeasured number. They add that the other
  fractions are normalised over the unseen phase too (moved by 99.99 wt% under
  TRF, 0.61 wt% under LM in the fixture), so the report should say "relative
  to the phases seen in range; phase N not measured". Their test asserts both
  under both solvers: scale unchanged, no fraction for that phase. DECISION
  (maintainer, task 2): recommend taking both, since it is the package's
  "absent rather than zero" rule (WP-1072, WP-1110 item 14, `qpa` marking the
  block unmeasured) carried to the fraction. Checked at `2c94d848`: no code
  moved, no PR.

## Non-goals

- Whether a phase is seen at all: WP-1523's significance, closed.

## Tasks

- [ ] Reproduce under `solver="trf"` and the default LM in a test, and
      record the scale and the fraction at each stage.
- [ ] Decide: hold the scale of a phase with no reflection in range, or have
      the QPA report no fraction for it. Record the choice and what moves on
      `tests/test_scale_b_ridge.py` and `tests/test_qpa.py`.
- [ ] Land it, with a test under both solvers.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_scale_b_ridge.py tests/test_qpa.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1534's fixture, `tests/test_scale_b_ridge.py`; WP-1523's 2026-10-13
  handover entry, Findings.
- #954, the public report of this defect.

## Handover log

- **2026-10-13** — filed from WP-1523's close. No open WP owns it: 1534 and
  1463 are closed, 1420 is about a held phase re-entering a chain, and 1523's
  own subject was whether a phase is seen, not a scale with no column. Next:
  task 1.
