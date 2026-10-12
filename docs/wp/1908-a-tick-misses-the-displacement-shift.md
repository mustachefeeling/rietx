# WP-1908 — a tick misses the displacement shift

Milestone: unscheduled · Status: 🔄 2026-10-12 — claimed by @yue-here
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

- [x] Reproduce on a synthetic pattern with a known displacement, and on
      cpd-1c over 20–40°. Measure the tick-to-peak offset before the fix.
      Measured at `5ef289bd` (apex of the calculated curve minus the tick,
      darwin/arm64). Synthetic rutile, Cu Kα1, s = 0.5 mm on R = 217.5 mm,
      refined back to 0.5000: of 25 isolated ticks, each sits low by the
      amount −2·s·cosθ/R gives, 0.256° at 27.4° falling to 0.137° at 117.5°.
      cpd-1c under
      `qpa_plan`, Kα1 ticks: 20–40° fits −0.807 mm with the zero at its −0.5°
      bound (Rwp 0.0795) and the ticks sit 0.50° low at 25.1° and 27.8°;
      25–33° fits −1.000 mm and +0.5° (both bounds, Rwp 0.1215) and they sit
      0.65° low. The −0.69/−0.78 mm and 0.4° in § Context did not reproduce on
      this tree. The sign and the size of the offset did.
- [x] Build the tick positions from the same position corrections the
      forward model applies, through one function both read (two
      derivations of one position is the class root CLAUDE.md warns about
      for `tick_hkl`). `CompiledModel.apparent_two_theta(tt_bragg, values)`
      is Bragg angle plus `_position_shift_deg`; the forward model's
      position memo and `refine._build_result` both call it, so `forward.py`
      gained the method and one call site and no arithmetic moved.
      `tick_hkl` and `tick_support` ride the unchanged filter, sort and cap.
- [x] Check `stage_ticks`, the joint runner's own tick builder (`multi.py`
      keeps one) and the GUI's tick rows against the same rule. Three
      builders, not two: `viz.snapshot.stage_ticks` (the live viewer, the
      comparison UI and `plot_pattern(model=)`), `multi._ticks` (the joint
      runner's) and `refine._build_result`'s. The first two had the same
      defect and now call the same method. The GUI draws what the API sends
      (`result.ticks`, `tick_hkl`) and computes no position of its own. The
      one other builder, `gui/session.py`'s `index_ticks`, places an indexing
      candidate on the observed axis through the candidate's shift template
      and adds no instrument shift by design, so it is a different object.
      `tests/test_tick_positions.py` holds each of the three builders to the
      calculated curve's apex.
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
