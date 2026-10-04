# WP-1908 — a tick misses the displacement shift

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-04 — a result's reflection positions sit off its own fitted peaks by the displacement shift, and Layer 0 reads them

## Goal

`RefinementResult.ticks` place each reflection where the fitted model puts
its peak. A refined sample displacement, transparency or capillary offset
moves the ticks with the peaks.

## Context

**The defect (found by WP-1534, 2026-10-04).** The tick builder in
`refine.py` (the loop that fills `ticks`, `tick_hkl` and `tick_support`,
about line 6170) adds `instrument.zero_shift` to each Bragg angle and nothing
else. The forward model also applies the sample displacement and the other
geometric position corrections. So a fit with a refined displacement draws
its ticks away from the peaks it fitted.

Measured on IUCr CPD sample 1c (`tests/data/qarr/cpd-1c.prn`), the
acceptance suite's `qpa_plan`, fitted over 20–40° and 25–33°: the
displacement refined to −0.69 and −0.78 mm, and every tick sat about 0.4°
below its peak in the plot. That is the size −2·s·cosθ/R gives at 32° on the
173 mm goniometer. The calculated curve sits on the data, so the model is
right and the ticks are not. `main` at `e6606705` draws the same offset.

**Why it matters beyond the picture.** Root CLAUDE.md's last invariant says
Layer 0 reads `ticks` to decide which observed peaks are unindexed: it once
flagged every Kα2 peak as an impurity because the ticks lacked that line. A
displacement of a few tenths of a millimetre, common on a lab Bragg–Brentano
mount, moves a peak by about 0.1° at mid-angle. Whether that crosses Layer
0's matching window has not been measured.

## Non-goals

- Changing how the forward model applies any correction.

## Tasks

- [ ] Reproduce on a synthetic pattern with a known displacement, and on
      cpd-1c over 20–40°. Measure the tick-to-peak offset before the fix.
- [ ] Build the tick positions from the same position corrections the
      forward model applies, through one function both read (two
      derivations of one position is the class root CLAUDE.md warns about
      for `tick_hkl`).
- [ ] Check `stage_ticks`, the joint runner's own tick builder (`multi.py`
      keeps one) and the GUI's tick rows against the same rule.
- [ ] Measure whether Layer 0's unindexed-peak finding changes on the
      acceptance fixtures with a refined displacement.

## Acceptance

On a synthetic pattern with a 0.5 mm displacement, every tick lies within a
hundredth of a degree of its reflection's fitted peak.

## References

- WP-1534's 2026-10-04 handover entry (where it was found).
- Root CLAUDE.md § Invariants, the `RefinementResult.ticks` clause.

## Handover log

- **2026-10-04** — filed from WP-1534's handover. No open WP owns tick
  positions: the open rows naming ticks are all magnetic satellites or
  exporters. Next: the first task, since the offset on a realistic lab
  displacement decides how urgent the Layer 0 half is.
