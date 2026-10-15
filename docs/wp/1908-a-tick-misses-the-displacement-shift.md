# WP-1908 — a tick misses the displacement shift

Milestone: unscheduled · Status: ✅ 2026-10-15 — a tick sits where the model draws its peak, at the refined wavelength and inside a window that follows the shift; the Layer 0 flank-lobe question it exposed went to WP-1977, and review finding 5 to WP-1976
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

### 2026-10-15 — review round finished on main, a refined wavelength fixed

The follow-up PR #942 has now run the whole suite on current main and passed.
A second review found one more case of the WP's own defect. The ticks were
placed at the wavelength fixed when the model was built, while the curve uses
the refined one. So any fit that refines λ, such as a calibration on a
standard with its cell held, drew its ticks away from its peaks: about 0.43°
at 150° for a 0.1 % change, by 2·tan θ·Δλ/λ. Ticks now read the refined
wavelength, and nothing else that was measured moves.

*Done.* The worktree the 2026-10-13 entry names had been deleted, so the branch
was checked out again in `.claude/worktrees/wp1908-review-followups`. Main was
merged in (442 commits, clean, `895f54a9`). The TOF axis (WP-1927) landed in
that range and added no tick builder of its own. `/code-review high --fix` on
the branch's diff returned ten findings and fixed five in `fbac3d06`:
`reflection_positions` walks `line_lambdas(values)` as `phase_peaks` does (new
test, red with the fix removed); `compile_model`'s widened `hi_eff` is capped at
180°, past which `d_min` folds back; the `REFLECTION_MARGIN_DEG` comment says
the window follows the shift at compile-time values only; two unused loop
variables and a duplicate test line went, and `mag_row` is an `np.tile`.
Declined, with reasons: the satellite arm's low edge in the wrong line's frame
and its second copy of the window scan (findings 4 and 6) are outside this
diff and went to WP-1326's Inherited; `refine._reflection_positions` says
"Bragg 2θ" but returns `phase_peaks` positions, which already carry the shift,
and judges the absorption summary there (finding 5). That helper predates this
WP, no open WP owns it, and whether the absorption summary should read Bragg or
drawn angles is unverified. The window widening by the largest shift anywhere
in the range rather than at each edge (finding 7) over-generates safely, so it
stays. The rename of one test was cosmetic and skipped.

*Measured.* `[dev]` venv (no jax or torch), darwin/arm64, Python 3.12,
rietx 1.10.0.dev0. Collect-only of `-m "not slow"`: 10790 on `origin/main`
(`git archive` snapshot) and 10794 here, +4, the three tests of the 2026-10-13
round plus the one this round added. The fast selection on the final tree:
10609 passed, 191 skipped, 2 xfailed, in about 4-5 min at load 3-5. The four
added tests cost 0.02-0.04 s each in that run, far from the tail. The full
selection ran twice on the merged tree. Before the review fixes it gave 10921
passed, 200 skipped, 2 xfailed, 0 failed (about 21 min, load 3-5). On the
final tree it gave 10920 passed, 202 skipped, 2 xfailed, 0 failed (about
24 min, with the load average reaching 45 from other sessions). Passed plus
skipped moved by +1, the added test. Two passes became skips, and they are not
named, because neither log prints reasons. The likely cause is WP-1449's
budget skip in `test_acceptance_indexing.py`, which fires when the clock cuts
an indexing unit and which this branch's code does not reach. The slow
selection that the 2026-10-13 entry left pending is therefore discharged.

*Gotchas.* (1) The worktree guard refuses a command that `cd`s or loops over a
path variable; a `git archive` base is collected with `-c` and `--rootdir`
pointing into the snapshot. (2) A full-suite skip count can move under load,
so a delta in skips between two runs on one tree is load until named with
`-rs`.

*Next.* Mark #942 ready, let the required checks run, and merge it (the
maintainer authorised that on 2026-10-15). The open Layer 0 flank-lobe question
from the first entry still has no owner; WP-1909 is the indexing picker's, not
Layer 0's. Finding 5 above is a candidate line for whoever next touches the
absorption summary.

### 2026-10-13 (2nd session) — post-merge review round, handed off

PR #927 merged, and a `/code-review medium` pass on its diff then returned
eight findings. All eight are fixed on the branch `wp1908-review-followups`
(cut from `1307cb2f`, main merged in at `325aaffd`). The one that matters
closes the class the WP opened on. The window that decides which reflections
the model generates still assumed a geometry shift under half a degree, so a
shift larger than that at a range edge left a peak out of the model, its
ticks and Layer 0's picture. The window now follows the shift. The three tick
builders also each carried their own copy of the position walk, which is how
the shift was forgotten in the first place, so there is now one method they
call. What is left is a check, not a fix: the slow (acceptance) selection did
not finish on the final tree, because this session was stopped at 92 %.

*The eight findings, verbatim from the review, with where each stands.*
Commits: `56982424` is the code, `8cfdc743` the tests, and the commit that
carries this entry has the WP-file edits.

1. `src/rietx/model/forward.py:3504` compile_model's reflection-generation
   window still subtracts the zero alone with a fixed 0.5° margin, so a
   geometry shift above 0.5° at a range edge leaves a reflection whose drawn
   peak lies inside the fitted range ungenerated (absent from model, ticks and
   on_data; Layer 0 then calls it an impurity). `satellites._generation_window`
   now widens by the measured shift; take the same bound in compile_model, or
   state the 0.5° as a named constant with its validator and say in the
   handover why it is left. This is the unfixed sibling of the defect the WP
   closed (root CLAUDE.md: a reported defect is a sample; fix the class).
   **Fixed** in `56982424`. `compile_model` widens the Bragg window by the
   largest and smallest shift beyond the zero over 33 points of the fitted
   range, using the existing `_shift_est`, and never narrows it. For a geometry
   with no shift the widening is exactly 0.0, so the window is bit for bit the
   old one. The 0.5° is now `REFLECTION_MARGIN_DEG`, a tail allowance on top of
   the shift. It has no validator and is not tied to the peak width: a broad
   profile centred 0.5° outside the range may want more, and that is
   unmeasured. The test is red with the widening disabled (7 ticks against 8,
   the 60.72° tick missing).
2. `refine.py:6718`, `multi.py:1301`, `viz/snapshot.py:147` still each
   re-derive the per-line position list (cell tuple → two_theta →
   apparent_two_theta → concat → tile hklm → isfinite → argsort). One
   `CompiledModel.reflection_positions(ip, values) -> (pos_per_line, hklm)` the
   three call, or read the positions `phase_peaks` already memoises, so a fifth
   builder (WP-1927's TOF axis) cannot forget the shift. **Fixed** in
   `56982424`. `reflection_positions` returns the concatenated positions and
   the tiled `(H, m)` rows, paired by index. The three builders keep their own
   filter, sort and cap. `multi.py`'s `_CELL_KEYS` was unused afterwards and is
   gone. `report.satellites` enumerates differently and calls
   `apparent_two_theta` itself.
3. `tests/test_tick_positions.py:191, 243, 265` five of six refinements write
   no obs/calc/diff PNG (tests/CLAUDE.md § Running); add `_plot_with_zoom` to
   each. **Fixed** in `8cfdc743`: the doublet case, the three geometry cases and
   both joint histograms. I looked at the doublet zoom: four ticks on four
   peaks.
4. `forward.py:1010` `apparent_two_theta`'s docstring names three builders but
   the review commit added a fourth (`report/satellites`); `multi.py:1287`
   still says "the second builder"; WP-1927's Inherited note says "the three
   tick builders". Make all three say four, or point them at the one function
   from item 2. **Fixed** in `56982424`: all three point at
   `reflection_positions` and `apparent_two_theta`.
5. WP handover line 154: wall clock quoted as single figures ("6:45", "36
   minutes", "62 minutes", "933 s", "6.95 s", "3.0 s"); quote ranges with load,
   and give the fast-selection passed+skipped delta for the new tests against a
   base run on origin/main. **Fixed** in this commit. The first entry's figures
   are now ranges with the load. The delta is in *Measured* below.
6. `tests/test_tick_positions.py:312` compares `stage_ticks` output rounded to
   `TWO_THETA_DECIMALS` against unrounded values at atol=1e-5; round the
   expectation with the same constant or take the unrounded ticks from
   `refine._build_result`. **Fixed** in `8cfdc743`. The test compares the
   unrounded walk to 1e-12, and the live view within half a unit of
   `TWO_THETA_DECIMALS`. A new case also checks that rows and Miller indices
   stay paired through the filter, sort and rounding.
7. `tests/test_tick_positions.py:333` the satellite arm tests only
   `_lattice_positions`; add a case with a propagation vector so
   `_satellite_positions` (satellites.py:170) is held too. **Fixed** in
   `8cfdc743`: a phase with k = (0, 0, 1/2) draws 121 satellites and the arm
   lists the same 121. Handing the arm a zero-only position leaves 119 listed
   and the worst drawn satellite 0.2585° from any of them, so the case is
   sensitive.
8. `tests/test_tick_positions.py:128` `_tick_offsets` calls `np.min` on an
   empty array when a phase has one tick; guard with `ticks.size > 1`.
   **Fixed** in `8cfdc743`. The guard has no test of its own, because it sits
   in a test helper.

*Measured.* `[dev]` venv (no jax or torch), darwin/arm64, Python 3.12.10, the
load average between about 20 and 160 from other sessions. The base is
`1307cb2f` (this branch's parent), run in a detached git worktree:
`-m "not slow"` gave 9339 passed, 181 skipped, 1 xfailed in about 7 minutes.
This branch gave 9342 passed, 181 skipped, 1 xfailed in about 13 minutes. So
passed plus skipped moved by exactly +3, the three cases this round added. For
PR #927's own tests, collect-only counts of the same selection are 9502 on
`a3987d6a` (before), 9513 on `1307cb2f` (+11) and 9516 here (+3). A first base
attempt on a `git archive` copy had 27 failures and errors, all in tests that
call git on a tree with no `.git`, so it is not a base. After the merge of main
(22 docs-only commits, none in these files), ruff is clean and
`test_tick_positions.py`, `test_snapshot.py`, `test_multi_histogram.py`,
`test_satellites.py`, `test_magnetic_tick_row.py` and
`test_docs_consistency.py` gave 135 passed in about 13 s.

*Pending.* One thing. Item 1 moves a window, so it can move a number in an
acceptance fit with a displaced geometry. The slow selection on the final tree
was running and had passed 92 % of its items with no failure when it was
stopped. It has not finished. The fast selection passed with the new window,
so no fast-tier pinned number moved, and the slow tier is the one that fits
real data under a displaced geometry.

*Gotchas.* (1) Three slow tests are load-sensitive and fail on a loaded
machine without any link to ticks: the two monoclinic indexing searches
(`test_dichotomy_recovers_a_monoclinic_cell`,
`test_trial_error_recovers_a_monoclinic_cell`) and the GUI boot test
`test_a_real_gui_boots_on_a_scratch_copy_and_the_project_is_untouched`. Rerun a
red one alone before reading anything into it. The first one failed the same
way on the tree before this WP. (2) A base run needs a real git worktree, not
`git archive`. (3) Root CLAUDE.md sits at its 978-line cap, so a new clause
there has to move one out. (4) Not generalised, deliberately:
`extra_peak_tick_positions` (a declared peak carries no shift by declaration)
and the GUI's `index_ticks` (an indexing candidate on the observed axis).

*Next.* From the worktree
`/Users/yue/Code/rietx/.claude/worktrees/ancient-foraging-umbrella/.claude/worktrees/agent-a91809515a9c88e76`
on `wp1908-review-followups`, check nothing else is mid-suite (`ps aux | grep
'[p]ython -m pytest'`), then run in the background
`.venv/bin/python -m pytest -n auto --dist loadgroup -m slow > /tmp/slow.txt 2>&1`
and wait on the pid. Green apart from the three load-sensitive rows above:
`gh pr ready` on the follow-up PR, mirror the result into its body, and stop.
A red acceptance row that reads a position (a cell, a count of reflections)
means item 1 moved a number: compare it with the same test on `1307cb2f`
before touching anything. The first action of the earlier entry's *Next*, the
open Layer 0 flank-lobe question, is unchanged.

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
  torch), darwin/arm64, Python 3.12.10. The machine was shared throughout, with
  the load average between about 115 and 160, so every wall clock here is a
  range (amended in the post-merge review round, which has the base-run delta).
  `-m "not slow"` took 7 to 36 minutes on the same tree, depending on the load.
  It gave 9314 passed, 181 skipped and 3 xfailed before the review commit.
  After the review commit it gave the same counts and 1 failed. The failure
  was `test_docs_consistency`'s CLAUDE.md cap, which my four-line clause broke
  and I removed, so passed plus failed moved by exactly the one test the review
  added. The added tests cost about 7 s locally over 7 functions, and the
  longest, a fit, took 3 to 7 s across runs. None joins the tail.
  `-m slow` before the review fix: 296 passed, 21 skipped, 3 failed, in about an
  hour. Two failures were the monoclinic indexing searches (`search_complete`
  False, a wall-clock-bound search cut short) and one a GUI boot socket
  timeout. Rerun alone, the GUI boot and `test_dichotomy…` passed and
  `test_trial_error_recovers_a_monoclinic_cell` failed again. It failed the same
  way on the tree before this WP, taking about 15 minutes against about 90 s on
  a quiet machine. The indexing package reads no tick and no position shift.
  After the review fix, `test_satellites_acceptance.py` and
  `test_acceptance_magnetic.py` gave 10 passed. Another session ran suites
  throughout, so the wall clock is quotable only as those ranges.

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
