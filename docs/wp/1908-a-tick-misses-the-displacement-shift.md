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
`refine.py` (the loop in `_build_result` that fills `ticks`, `tick_hkl` and
`tick_support`) added `instrument.zero_shift` to each Bragg angle and nothing
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
mount, moves a peak by about 0.1° at mid-angle. Measured in § Tasks, last
item: it crosses the window, and the larger effect is on Layer 1's actions.

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
- [x] Measure whether Layer 0's unindexed-peak finding changes on the
      acceptance fixtures with a refined displacement. It does, in both
      directions. Twelve `qpa_plan` fits, each run on the pre-fix tree and
      on this one (Rwp and displacement agree to four places, so only the
      ticks differ): cpd-1a to 1h over 5–150°, cpd-1c over 20–40° and
      25–33°, cpd-2 and cpd-4. `unmatched_obs` before → after: 1a 6→6, 1b
      12→12, 1c 6→11, 1d 6→7, 1e 7→7, 1f 4→5, 1g 6→6, 1h 4→7, 1c 20–40°
      4→3, 1c 25–33° 3→1, cpd-2 8→9, cpd-4 30→18. `unmatched_calc`: 1d 4→5,
      1f 4→2, 1g 2→4, 1h 2→1, cpd-2 6→5, cpd-4 19→27, the rest unchanged.
      The full-range displacements are −0.08 to −0.21 mm (cpd-4 +0.26), so
      the tick moves 0.03–0.11°, the size of Layer 0's 0.08° window. The
      peaks that become unmatched on 1c (31.62°, 36.08°, 47.40°, 56.46°,
      62.70°, 67.80°) sit 0.15–0.19° below strong zincite ticks, on curves of
      650–1860 counts: the flank lobes of a profile misfit. The old ticks sat
      about 0.11° low, so a lobe fell inside the window by accident. The
      larger change is in the suggested actions. Listed actions before →
      after: 1c eight → one, 1f seven → one, 1h seven → none, cpd-2 nine →
      one. The plan had already vetoed most of the old lists (cell, zero,
      displacement, widths, axial asymmetry). The active ones were
      `increase_background_flexibility` 0.50 and `refine_sample_transparency`
      0.07 on 1c, and `refine_sample_transparency` 0.07, 0.02 and 0.20 on
      1f, 1h and cpd-2. After the fix the active ones are `add_impurity_phase`
      on 1c (0.30) and 1f (0.40), and none on 1h and cpd-2 (whose
      `reindex_or_recheck_cell` 0.40 stays, vetoed). `LAYER0_MATCH_TOL_DEG` and
      the unmatched definition are not touched here. A residual lobe on the
      flank of a strong peak reading as an unindexed peak is Layer 0's own
      question, and it is open.

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
