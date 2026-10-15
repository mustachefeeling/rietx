# WP-1976 — a correction summary judged at the drawn angle

Milestone: unscheduled · Status: 🔄 2026-10-15 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: —

## Goal

The absorption record and the roughness regime check judge each correction
at the angle the forward model applied it: each reflection's Bragg angle.

## Context

**The defect (WP-1908's review, finding 5).** `refine._reflection_positions`
said "in-range Bragg 2θ" and returned `phase_peaks` positions. Those are the
drawn angles, which carry the zero shift and the geometry's position
corrections. The forward model evaluates `_absorption(tt_bragg)` and
`_roughness_factor(tt_bragg, values)` at the Bragg angle (`phase_peaks` in
`model/forward.py`). So under a refined displacement the summary read the
factor up to 0.26° away from where any reflection was corrected.

Two consumers had the defect:

- `refine._absorption_record` (`AbsorptionCorrection.equivalent_delta_biso`,
  `unabsorbed_fraction`, `identifiable_fraction`), through the helper.
- `refine._roughness_regime_diagnostics` (`ROUGHNESS_OUTSIDE_REGIME`,
  `ROUGHNESS_UNCONSTRAINED`), which open-coded the same walk.

**Which reflections count is a different question.** WP-0502 judges a
correction at the modelled reflections, never on the grid, because a pattern
can start far below its first peak. A reflection belongs to the pattern where
it is drawn, so membership stays a test on the drawn angle.

## Non-goals

- Changing how the forward model applies either correction.
- The tick builders, which WP-1908 already moved to the drawn angle.

## Tasks

- [x] One helper, `refine._reflection_bragg_angles`, returns the Bragg angle
      of every reflection drawn in range. Both consumers call it. A test in
      `tests/test_tick_positions.py` holds it to the Bragg angles under a
      0.5 mm displacement and holds the absorption record's ΔBiso to the value
      at those angles. It is red with the helper returning drawn angles.
- [x] Skill: none. No agent-facing name, code or verb changed, and the
      measured change is below every threshold an agent reads.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_tick_positions.py tests/test_absorption.py tests/test_surface_roughness.py -p no:randomly
```

## References

- WP-1908's 2026-10-15 handover entry (finding 5, where it was declined).
- WP-0502 (why a correction is judged at the reflections).

## Handover log

- **2026-10-15** — created from WP-1908's review. No open WP owned it, and
  WP-1908 is closed, so its follow-up takes a new number.
