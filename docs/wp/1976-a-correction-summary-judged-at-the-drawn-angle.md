# WP-1976 — a correction summary judged at the drawn angle

Milestone: unscheduled · Status: ✅ 2026-10-15 — absorption and roughness are judged at the Bragg angle the model applied them at, and quoted at the drawn one
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
- [x] Review round (`/code-review high`): `CompiledModel.reflection_angles`
      yields each line's (Bragg, drawn) pair and `reflection_positions` builds
      on it, so the angle walk exists once. The record converts ΔBiso at the
      wavelength its Bragg angles were found at. The roughness messages quote
      the drawn angle. A second test holds the roughness fence to the Bragg
      angle.
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

- **2026-10-15** — Two intensity summaries now read the angle the model
  actually corrected at. The absorption record and the roughness regime check
  used to look up each factor where the peak is drawn, which a refined
  displacement moves up to 0.26° away from the Bragg angle the forward model
  uses. On rutile with a 0.5 mm displacement the reported ΔBiso moves by at
  most 0.0025 Å², a twentieth of the 0.05 Å² threshold, so the absorption
  number barely changes. The roughness fence can change its verdict near its
  edge: τ = 0.236 used to warn that the model amplifies intensity, and the
  model in fact still depresses it there. Next: nothing in this WP. The
  excluded-region question below needs an owner if anyone hits it.

  *Done.* `3488fcee` the helper and the first test; `afa78aea` the review round
  (one angle walk on `CompiledModel`, one wavelength in the record, drawn
  angles in the roughness messages, the roughness test). Both tests are red
  with the helper returning drawn angles. Also this session, outside this WP:
  PR #989 (the merge records owed by WP-1418, 1419 and 1810) had gone stale
  against main, and merging main into its branch (`3bdface4`, clean) cleared
  the three repair flags. WP-1977 was filed for #927's Layer 0 question, and
  WP-1908's status line now names both successors.

  *Review.* `/code-review high` returned seven findings. Five were fixed:
  message angles, the docstring citation, the second walk, the wavelength
  mismatch, the missing roughness test. Declined: the status line (settled
  here) and reflections inside an excluded region still counting toward both
  summaries. That one predates this WP, needs a rule for a reflection
  straddling a region's edge, and has no owner. It is not generalised here.

  *Measured.* `[dev]` venv (no jax or torch), darwin/arm64, Python 3.12,
  rietx 1.10.0.dev0, on main merged in (`65e7c225`), load 3.7-4.1, no other
  suite running. Fast selection: 10611 passed, 191 skipped, 2 xfailed, about
  4 min. The diff against main adds two unparametrised tests in one file and
  changes no other test, so passed+skipped moved by +2. Each costs 0.02 s.
  The full suite did not run. In its place, the `-m slow` rows of the seven
  files that read absorption or roughness (capillary, dispersion, LaB₆/cBN,
  QPA round robin, backend goldens, compare UI, surface roughness) ran on the
  same tree: 52 passed, about 25 s.
- **2026-10-15** — created from WP-1908's review. No open WP owned it, and
  WP-1908 is closed, so its follow-up takes a new number.
