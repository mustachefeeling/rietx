# WP-1908 — a tick misses the displacement shift

Milestone: unscheduled · Status: ✅ 2026-10-13 — a tick sits where the model draws its peak; the Layer 0 flank-lobe question it exposed has no owner
Track: What fires, and what stays silent
Depends on: —

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

- **2026-10-13** — A reflection tick now sits where the model draws its
  peak. A result used to put each tick at its Bragg angle plus the zero shift.
  A fit with a refined sample displacement, transparency or capillary offset
  therefore drew its ticks off the peaks it had fitted, and on a synthetic
  0.5 mm displacement they sat 0.14° to 0.26° low. Every tick now lies within
  0.01° of its peak. No fitted number moves. The report does, because it reads
  the ticks: on four QPA round-robin fits the suggested actions fell from
  between seven and nine entries to one or none. One question is left open. A
  residual lobe on the flank of a strong peak reads as an unindexed peak more
  often now, and no WP owns it.

  *Done.* All four tasks. `CompiledModel.apparent_two_theta(tt_bragg, values)`
  is the Bragg angle plus `_position_shift_deg`. It sits in `forward.py` beside
  that method, and the forward model's position memo calls it, so no arithmetic
  moved. Four builders call it: `refine._build_result`,
  `multi.MultiHistogramRefinement._ticks`, `viz.snapshot.stage_ticks` and,
  from the review, `report.satellites` (`_lattice_positions` and
  `_satellite_positions`, with a generation window widened by the shift over
  the fitted range). `tick_hkl` and `tick_support` ride the unchanged filter,
  sort and cap. `tests/test_tick_positions.py` holds each builder to the
  apex of the calculated curve. Also touched: the manual's `exports.md`, the
  `ticks` comment in `results.py`, `docs/releases/1.9.0.md` (§ Numbers that
  move), the v1.9 record, and WP-1927's `### Inherited`. The only lines of
  `multi.py` touched are the three-line `rows` list in `_ticks`, for WP-1341's
  lane, which edits that file.

  *Measured.* Tick-to-peak offsets, apex minus tick, are in Tasks 1 (before)
  and 4. After the fix the 25 isolated ticks of the synthetic case sit within
  0.0001° of their apex. On cpd-1c under `qpa_plan` the Kα1 ticks are within
  0.022° of the apex over 20–40°, with the apex below the tick. I did not
  test why. The new file has 11 cases (7
  functions) and 9 of the first 10 were red on the tree before the fix. The
  satellite case is red on the tree before the review commit. Layer 0 and the
  suggested actions on twelve fits: Tasks 4. Tests, `[dev]` venv (no jax or
  torch), darwin/arm64, Python 3.12.10, the load average between 140 and 150
  from other sessions: `-m "not slow"` gave 9314 passed, 181 skipped and 3
  xfailed before the review commit, in 6:45 beside one other suite. After it
  the same selection gave 9314 passed, 181 skipped, 3 xfailed and 1 failed in
  36 minutes. The failure was `test_docs_consistency`'s CLAUDE.md cap, which
  my four-line clause broke and I removed, so passed plus failed moved by
  exactly the one test the review added. The added tests cost 6.95 s locally
  over 7 functions (the longest, 3.0 s, is a fit), none joins the tail.
  `-m slow` before the review fix: 296 passed, 21 skipped, 3 failed, in 62
  minutes. Two were the monoclinic indexing searches
  (`search_complete` False, a wall-clock-bound search cut short) and one a GUI
  boot socket timeout. Rerun alone, the GUI boot and `test_dichotomy…` passed
  and `test_trial_error_recovers_a_monoclinic_cell` failed again, and it
  failed the same way on the tree before this WP (933 s). The indexing package
  reads no tick and no position shift. After the review fix,
  `test_satellites_acceptance.py` and `test_acceptance_magnetic.py` gave 10
  passed. Another session ran suites throughout, so none of the wall clock is
  quotable beyond those ranges.

  *Review.* `/code-review high --fix` found one defect, the satellite arm
  adding the zero alone. It is fixed in `80624b67` and nothing was declined.
  No lanes were dispatched, so step 3b did not apply.

  *Gotchas.* (1) The task text called `stage_ticks` the joint runner's
  builder. It is `viz/snapshot.py`'s, and the joint runner's is `multi._ticks`.
  (2) § Context's −0.69 and −0.78 mm and 0.4° did not reproduce on this tree.
  The 20–40° and 25–33° fits end at −0.81 and −1.00 mm with the zero on its
  ±0.5° bound, so the pair is near-degenerate on a short range and those rows
  say little about the displacement itself. (3) The doublet test judges two
  reflections above 100°. Lower-angle Kα2 ticks use the same function and are
  not checked against an apex. (4) `apparent_two_theta` is on the numpy path.
  The traced twin in `backend/traced.py` does not call it, no traced code
  changed, and this venv has no jax or torch, so the cross-backend rows
  skipped. (5) Root CLAUDE.md sits exactly at its 978-line cap, so the rule
  "one function places a tick" lives in the method's docstring. The next
  clause added there has to move one out. (6) #911 (TOF, a contributor's)
  and #923 (WP-1953's next PR) edit `forward.py`, and #911 also `multi.py` and
  `refine.py`. I compared their hunks and none touches these lines.

  *Next.* The first action decides whether the Layer 0 half of this WP's goal
  is finished. On cpd-1c the six peaks that became unmatched sit 0.15° to
  0.19° below strong zincite ticks, on curves of 650 to 1860 counts, and the
  old displaced ticks matched them by accident. Layer 0's rule is a 0.08°
  window and a 5σ residual peak. A WP would ask whether a residual lobe should
  match the tick of the peak it flanks, with a window scaled by the FWHM, and
  would measure the unmatched count on these twelve fits again. I checked the
  open index rows for an owner and found none: 1909 is the indexing peak
  picker, 1339 report rendering and 1523 the support test. I did not file it,
  because this session's brief sent anything to be filed to this entry and
  the report. Second, WP-1927
  reads the new `### Inherited` note when it meets its tick readers. Third,
  WP-1341 rebases over the one `rows` change if its branch edits `_ticks`.

- **2026-10-04** — filed from WP-1534's handover. No open WP owns tick
  positions: the open rows naming ticks are all magnetic satellites or
  exporters. Next: the first task, since the offset on a realistic lab
  displacement decides how urgent the Layer 0 half is.
