# WP-2011 — a candidate is judged on a fit that converged

Milestone: unscheduled · Status: 🔄 2026-10-27 — switch built provisionally in draft PR #1191; the go, the names and the Pawley constants' grounds wait on the maintainer
Track: What fires, and what stays silent
Depends on: 1956 (PR #941 takes the missing count off this fit and edits the same two functions)
Priority: P2 2026-10-27 — `INDEX_IMPURITY_LINES` fires on a true cell's stalled fit, and notebook 03 works around it; #941 landed for WP-1956 on 2026-10-25, the condition the P3 rung waited on

## Goal

The indexer's whole-pattern check fits each candidate by Pawley, so the Rwp
and the unmatched-peak count it reports come from a converged fit. If the
re-measurement on the tree with WP-1956 merged shows the reported fit no longer
matters, this WP closes 🛑 with the numbers.

## Context

**The check.** `validate_by_lebail` (`src/rietx/indexing/workflow.py:334`)
fits a candidate's absence-free lattice group to the whole pattern with the
cell held, through the four stages of `validation_plan` (`:256`: background,
one shift, `w`, then `u v x y`), in **one** Le Bail pass. Its docstring says
"Le Bail rather than Pawley is a cost choice, not a discrimination one"
(`:377`). Measured 2026-10-18, that is false both ways: the two discriminate
differently, and Pawley costs the same below ~450 reflections.

**Why one Le Bail pass stalls.** Le Bail's extracted intensities are frozen
inside each least-squares run, so intensities and profile converge only by
alternating whole passes (WP-1323's context; `RefinementPlan.lebail_passes`).
Pawley refines them in the same solve (`model.forward.PawleyBlock`, WP-0306).

**Measured 2026-10-18** (tree 544245ca, arm64, `[dev]` venv, compiled kernels
on, another session live on the machine; the two modes ran interleaved, so
read ratios, not seconds). The probe is `2011-probe/` beside this file: it
replays `validate_by_lebail` with the fit's `mode` as the only variable, and
reproduced the shipped function's Rwp and counts to the digit before its
Pawley twin was read. Run from the worktree root,
`.venv/bin/python docs/wp/2011-probe/probe_lebail_vs_pawley.py all`, then
`probe2_… seeds|scale|truths`, `probe3_plain_fits.py`, `probe4_lebail_passes.py`;
outputs go to `$WP2011_OUT` (default: the temp dir).

*Wrong cells.* Synthetic LaB6 (`tests/test_indexing_consensus.py`'s pattern,
true background 29.7 counts), ranges over noise seeds 11-15; magnetite's P
rival from the indexer's own run (`tests/data/qarr/magnetit.prn`).

| candidate | refl. | bkg, Le Bail | bkg, Pawley | missing, Le Bail | missing, Pawley |
|---|---|---|---|---|---|
| true LaB6 | 28 | 27.6–27.7 | 28.5–28.6 | 0 | 0 |
| doubled | 153 | 26.0–26.3 | 28.4–28.6 | 112–123 | 121–123 |
| a×√5 | 204 | 20.4–20.9 | 28.5–28.7 | 12–44 | 167 |
| a +1 % | 30 | −1.2 to −0.3 | 29.2–29.4 | 0 | 19–30 |
| magnetite P rival | 163 | −5.8 | 13.8 | 0 | 3 |

The Le Bail background falls with the wrongness of the cell; Pawley's stays
within 2 counts of the truth on every LaB6 candidate. On the magnetite rival
Pawley's fitted intensities at the phantom positions are 0–2 against 50–743 for
real lines, but `absent_reflections` still reads 3 of 163: its 3σ test over
±0.5 FWHM reads a background a few counts under the data as intensity
(`debug_absent.py`). That is WP-1956's input problem, not this WP's.

*True cells, real data* (each cell refined once by an ordinary Le Bail fit from
its literature value, then judged by both modes):

| dataset | refl. | missing LB / P | unmatched LB / P | Rwp LB / P |
|---|---|---|---|---|
| SRM 660c | 30 | 0 / 0 | 15 / 13 | 0.099 / 0.093 |
| NAC | 837 | 0 / 20 | 184 / 170 | 0.155 / 0.126 |
| FAP | 216 | 5 / 7 | 76 / 5 | 0.210 / 0.079 |
| corundum | 85 | 11 / 7 | 43 / 10 | 0.223 / 0.138 |
| brucite | 43 | 2 / 2 | 9 / 11 | 0.172 / 0.167 |
| zincite | 36 | 4 / 4 | 11 / 7 | 0.124 / 0.105 |
| zircon | 98 | 6 / 5 | 60 / 11 | 0.267 / 0.147 |
| fluorite | 18 | 0 / 0 | 4 / 4 | 0.190 / 0.179 |
| magnetite | 52 | 3 / 3 | 4 / 4 | 0.210 / 0.180 |

On SRM 660c, FAP, corundum and zircon the Le Bail pass leaves a width on its
floor (`FLOOR_HIT`: `y`, and `w` too on zircon); FAP's peaks lose their
Lorentzian tails, and those tails are the 76 unmatched peaks. Pawley's fits hit
no floor. NAC's 20 are false: I2₁3 has no absences beyond the centring (283
positions either way), and they are real reflections the published structure
makes weak (0.03–1.5× the median intensity, all above 40° 2θ). Pawley's
background (300.2) matches a Rietveld fit with that structure (302.9); Le
Bail's (278.1) is low, and that is the only reason it passes them
(`debug_nac.py`).

*Converged Le Bail is ruled out* (`lebail_passes` 5 and 10, `probe4_…`). The
a×√5 and +1 % cells did not move; the magnetite rival's background fell from
−5.8 to −21.7. On true cells corundum stayed at Rwp 0.221 after 10 passes (Pawley
0.138 in one), FAP reached 0.110 in 5.6 s (Pawley 0.079 in 0.46 s), NAC took
16.6 s (Pawley 5.3 s). Slower than one Pawley pass everywhere.

*Cost* (one pass each; seconds over 2-3 repeats):

| reflections | Le Bail | Pawley | ratio |
|---|---|---|---|
| 18–216 (the lab cells) | 0.05–0.7 | 0.04–0.5 | 0.7–1.7, mixed |
| 442 | 0.45–0.47 | 0.44–0.46 | 1.0 |
| 837 (NAC, 11-BM) | 1.8–1.9 | 5.3–5.8 | 3.1 |
| 978 | 0.98–1.04 | 1.58–1.63 | 1.6 |
| 1823 | 1.85–1.98 | 7.84–7.98 | 4.1 |

`engines.MEASURED_VALIDATION_SECONDS` (`engines.py:2376`, 0.6-44 s) prices
validation in `estimate_ceiling` and under the quick preset's slices, and it was
measured for Le Bail.

**What WP-1956 changes first.** Decided 2026-10-14 and built by PR #941 (open,
round 2): with a peak list, `predicted_but_absent` comes from a
candidate-independent line screen (`indexing/screen.py`) and no longer reads
this fit; the count caps rather than refutes; the fit keeps the forward
question (`unmatched_observed`, hence `INDEX_IMPURITY_LINES`) and an Rwp for a
reader, and gains `freeze_profile` (a shared declared profile, off by default:
SRM 660c at Rwp 0.57 frozen against 0.10 free, #941's measurement). Without a
peak list the count is still this fit's (`absent_source="fitted_background"`).
So after #941 this WP reaches: the unmatched count and `INDEX_IMPURITY_LINES`
on true cells; the Rwp a reader sees, in the result and the GUI's candidate
row; the no-peak-list path, where NAC's 20 would still appear; and
`validation_failed`. Notebook 03 already works around the first two ("the
indexer's own quick Le Bail fit, whose Rwp in the candidate's row is poor. A
poor fit leaves many peaks unmatched").

**A declared name is a claim** (root CLAUDE.md): `validate_by_lebail`,
`LeBailValidation`, `CellCandidate.lebail`, `lebail_rwp` and
`INDEX_IMPURITY_LINES`'s "after a whole-pattern Le Bail fit" would all name a
fit that is no longer Le Bail. The field's term for both methods is whole
powder pattern decomposition (Le Bail 2005).

**Practice.** Kariuki *et al.* (1999) tested cell hypotheses with Le Bail fits
in a genetic-algorithm indexer, "faster than with the Pawley method" (as cited
by Le Bail 2005, §VI p.321; checked 2026-10-18). Le Bail (2005, §IV.B
p.318; this file said §II.B until 2026-10-27): the method "requires as good
starting cell and profile parameters as the Rietveld method itself", and a
wrong candidate is a bad start. **Checked 2026-10-27** (WP-2062's survey,
`docs/practice.md` § Structure-free fitting): GSAS-II re-extracts once per
least-squares iteration (`GSASIIstrMath.py:4808`), FullProf once per cycle
(ran), and TOPAS, RIETAN-FP and MAUD inside the refinement too, where rietx
re-extracts only between runs. So the gap above may be rietx's Le Bail
rather than the method; WP-2062 carries that as its decision 0. TOPAS
defaults to Pawley. No paper compares the two as cell validators.

### Re-measured 2026-10-27, on the tree with #941

`probe5_after_941.py` calls the shipped `validate_by_lebail` and swaps only
the fit's mode, by wrapping `Refinement.fit`. Tree `feae4c75` (main after
#941), arm64, `[dev]` venv, compiled kernels on. Another session's suite held
about ten cores throughout, so the seconds below are ratios at best.

*True cells, the indexer's path* (picked peaks, widths free; the cells are
probe 2's, refined once by an ordinary Le Bail fit):

| dataset | refl. | unmatched LB / P | Rwp LB / P | width on its floor, LB / P |
|---|---|---|---|---|
| SRM 660c | 30 | 15 / 13 | 0.099 / 0.093 | — / — |
| NAC | 837 | 184 / 170 | 0.155 / 0.126 | — / — |
| FAP | 216 | 13 / 5 | 0.140 / 0.079 | — / — |
| corundum | 85 | 21 / 12 | 0.172 / 0.137 | `w` / — |
| brucite | 43 | 9 / 11 | 0.172 / 0.167 | — / — |
| zincite | 36 | 11 / 7 | 0.124 / 0.105 | — / — |
| zircon | 98 | 44 / 11 | 0.225 / 0.147 | `w` / — |
| fluorite | 18 | 4 / 4 | 0.190 / 0.179 | — / — |
| magnetite | 52 | 4 / 4 | 0.210 / 0.180 | — / — |

The absent count is identical under both modes on every row with a peak
list: it is the line screen's since #941, as designed. Le Bail improved
since 10-18 on FAP (76 unmatched with `y` on its floor, now 13 with no
floor), corundum (43 → 21) and zircon (60 → 44); the tree moved under it
(#941's width seeding, WP-2002's edge margin and emission lines), and this
probe did not separate which. Pawley's corundum count moved 10 → 12.

*Wrong cells, the indexer's path:*

| candidate | refl. | unmatched LB / P | Rwp LB / P | background LB / P |
|---|---|---|---|---|
| LaB6 doubled | 153 | 0 / 0 | 0.354 / 0.164 | 25.6 / 28.4 |
| LaB6 a×√5 | 204 | 4 / 4 | 0.850 / 0.233 | 19.1 / 28.5 |
| LaB6 +1 % | 28 | 22 / 23 | 1.008 / 0.503 | 27.4 / 29.2 |
| magnetite P rival | 163 | 25 / 2 | 0.646 / 0.174 | −7.3 / 13.8 |

(LaB6 true background 29.7; its true cell reads Rwp 0.234 / 0.164.) The
magnetite rival indexes every line the true F cell does, so its unmatched
count should equal the truth's 4: Pawley's 2 is near it, Le Bail's 25 is
its sunk background. Pawley's Rwp ties the doubled cell to the truth
(0.164 both) and puts the P rival at 0.174 against 0.180: a converged
decomposition of a cell predicting every reflection of the truth's fits at
least as well.
**So the rival/truth Rwp gap the acceptance rows pinned (> 2×) was the
stall.** Two rows assert it (`test_acceptance_indexing.py`: magnetite's,
now inverted to < 1.05×, and the calibrated LaB6's a·√2 rivals). The second
stands under Pawley: an a·√2 cubic cell misses the truth's lines whose index
sum doubled is not a sum of three squares, (321) among them, so its fit is
worse for the lattice's sake and still reads over twice the truth's Rwp.

*No peak list* (`absent_source="fitted_background"`, reached only by a
direct call): Pawley's honest background reads more absences on wrong
cells (+1 % 0 → 14, a×√5 59 → 167, magnetite rival 0 → 3) and on two true
cells (NAC 0 → 20, the weak real reflections § Context names; FAP 4 → 7),
fewer on corundum (11 → 7) and zircon (8 → 5).

*`freeze_profile=True`*: frozen is worse than free under both modes
(SRM 660c Rwp 0.575 / 0.456 against 0.099 / 0.093), so it stays off.
Frozen Pawley is the more stable of the two (FAP unmatched 164 / 31).

*Notebook 03's candidate* (aragonite, the tutorial's search): Pawley
validates it at Rwp 0.044 with 0 unmatched, where the tutorial's own two
Le Bail passes reach 0.053. The `INDEX_IMPURITY_LINES` the notebook used to
explain away no longer fires.

*Cost* (`probe6_cost.py`: the acceptance suite's searches, `preset="full"`,
with every candidate the indexer validated timed under both modes, order
alternating; machine load 50-100 from another session's suite, so ratios
only):

| dataset | fits | reflections | Pawley / Le Bail, median (range) |
|---|---|---|---|
| corundum | 4 | 43-122 | 0.91 (0.23-1.11) |
| zincite | 3 | 36-84 | 0.89 (0.86-1.19) |
| zircon | 3 | 98-197 | 1.24 (1.23-2.37) |
| FAP | 3 | 216-364 | 0.97 (0.77-4.02) |
| SRM 660c | 10 | 30-71 | 1.04 (0.92-1.54) |
| magnetite | 2 | 52-163 | 1.00 (0.98-1.03) |
| NAC | 2 | 837, 1668 | 2.6, 12.6 (19.4 s against 7.5; 107 s against 8.5) |

cpd-1a, whose one 44 s fit set `MEASURED_VALIDATION_SECONDS`' top, returned
no candidate on this tree, so nothing of it was validated. On corundum's c/2
subcell candidates one Le Bail pass ran away (Rwp 5.5-6.2, one at
`max_iter`) where Pawley reached 0.38. On 10-18, idle, NAC's 837 cost 3.1×
and 1823 cost 4.1×, so the load inflates Pawley's large fits more than Le
Bail's. `probe7_idle_cost.py` re-timed them; the machine was quiet (load 5)
for its first run only, and that run's wrapper timed Pawley in both columns
(fixed in `81f8e37e`), so its early readings are Pawley's quiet costs:
NAC's 837 reflections 5.3-5.5 s, and the 1668 of its primitive description
25.0-25.5 s in two repeats before the load came back (the third took 109 s,
and the FAP and corundum readings after it are loaded too). The corrected
run met load 23-56:

| case | refl. | Le Bail s | Pawley s |
|---|---|---|---|
| NAC, I | 837 | 5.7-10.3 | 15.7-22.7 |
| NAC, P | 1668 | 4.1-7.6 | 32.9-88.6 |
| FAP | 216 | 0.85-0.87 | 0.64-0.69 |
| corundum | 85 | 0.20-0.21 | 0.24 |

So on a quiet machine Pawley costs about 3× at 837 reflections (Le Bail
1.8 s on 10-18) and about 5× at 1668, and a shared machine multiplies that
again. **What this means for a user**: under `preset="full"` a large
synchrotron pattern's validation takes longer and still completes. Under the
default `quick` preset each validation fit draws a slice of a whole-run
ceiling, and a slice that expires leaves its candidate `not_validated`,
which caps the grade at `medium`. So on a large low-symmetry pattern under
`quick`, Pawley can validate fewer candidates than Le Bail did. Not
measured: that needs `index_pattern` under `quick` on a large pattern in
both modes, on a quiet machine. The bethanechol benchmark runs `full` and
cannot see it. `MEASURED_VALIDATION_SECONDS` keeps its value (0.6, 44.0),
which brackets the quiet NAC fits; its comment says so.

**The provisional go (Claude, 2026-10-27, maintainer away).** Criterion: on
the path the indexer runs, does the Pawley fit answer the forward question
(is there a reflection under every observed peak) better? Evidence above:
no true cell leaves a width on its floor, the impurity count on true cells
falls (zircon 44 → 11, FAP 13 → 5, corundum 21 → 12; brucite +2), and a
nested rival's count becomes right. Against it: the Rwp cue a reader saw
on supercells is gone, and the fit costs more on large patterns
(§ Cost below). What reverses it: the acceptance suite losing a ranking,
or the bethanechol benchmark validating fewer candidates than `main`.
**Acceptance bar, read honestly:** FAP 5, zircon 11 and no `FLOOR_HIT` meet
it; corundum's 12 misses "at most 11" by one. That bar was Pawley's own
10-18 worst (5, 10, 11) with no margin.

## Non-goals

- The missing count's inputs and the grade (WP-1956).
- The extinction screen's per-class Le Bail fits (`extinction.py:756`, `:866`;
  WP-1910 in flight): a sibling, unmeasured, with a shared profile of its own.
- The GUI's adopt-a-candidate Le Bail fit, and the tutorials' ordinary Le Bail.
  Measured for whoever takes the tutorials: `profile_only` Le Bail converged
  more slowly than `pawley_default` on three lab patterns over three passes
  (corundum 0.234 → 0.179 with `y` still on its floor, Pawley 0.152 → 0.139;
  FAP 0.130 → 0.085 against 0.083 → 0.078; zircon 0.184 → 0.172 against
  0.172 → 0.149; `probe3_plain_fits.py`).
- A refinement's Le Bail background left at its seed (WP-1542).

## Tasks

- [x] Re-measure on the tree with #941 merged: the probe adapted to its
      signatures, both modes, the true and wrong cells above and the
      no-peak-list path, plus `freeze_profile=True` under each mode
      (`probe5_after_941.py`, § Re-measured 2026-10-27).
- [ ] **Decision (maintainer):** go or no-go, recorded as `Decided
      YYYY-MM-DD:`. Built provisionally as a go on 2026-10-27 while the
      maintainer was away; § Re-measured 2026-10-27 has the case and what
      reverses it.
- [ ] **Decision (maintainer):** the names above, kept with the mode recorded
      on the validation record or renamed to the field's term, staged in the
      release record either way (ROADMAP rule 6). Built provisionally as
      *kept, mode recorded* (`LeBailValidation.mode`).
- [x] Switch `validate_by_lebail`'s fit to `mode="pawley"`, record the mode on
      the validation record, and rewrite the `:377` paragraph with the numbers.
- [ ] **Decision (maintainer, with the generality review):** the three tier-3
      Pawley constants (`PAWLEY_OVERLAP_FWHM_FRAC`, `PAWLEY_OVERLAP_LAMBDA`,
      `PAWLEY_OFF_DATA_SCALE_FLOOR`, `_audit.py:1868-1890`) are kept on the
      grounds "opt-in Pawley mode". The switch puts Pawley on every
      `index_pattern` call that validates, so for that path the ground no
      longer holds. Re-ground them (the validation reads Rwp and the
      unmatched count, and neither depends on how an overlapped group is
      split) or re-tier them. Not edited here: a tier-3 ground needs the
      maintainer's dated approval. The generality review (2026-10-27, in the
      handover entry) adds that `PAWLEY_OVERLAP_FWHM_FRAC` was already on a
      default path before this branch: the peak picker reads it
      (`indexing/pick.py:492-565`, `indexing/peaks.py:42, 308`). It rated
      the first two **weak** (mechanism plausible, no sweep on the
      validation's readings) and the off-data floor **cannot tell** (it may
      bind on a pattern scaled to a maximum of 1).
- [ ] Re-measure `MEASURED_VALIDATION_SECONDS` under Pawley, and run
      `python -m tests.bethanechol_benchmark` alone against `main`'s count of
      validated candidates (the large monoclinic cost case). *Half done
      2026-10-27:* re-timed (§ Cost), value kept with a comment. The
      benchmark was not run: it needs two runs of tens of minutes alone on a
      machine other sessions kept loading, it records no `main` count to
      compare with, and under its `preset="full"` every checked candidate is
      validated whatever the fit costs. The risk § Cost names is under
      `quick`, so the measurement owed is `index_pattern` under `quick` on a
      large pattern (NAC, a bethanechol set) in both modes, quiet machine.
- [x] Tests: `test_le_bail_validation_separates_the_failure_modes` (its +1 %
      row asserts 0 missing, which is Le Bail's blindness; Pawley reads
      19-30), the magnetite acceptance row's regenerated negative background,
      `tests/test_acceptance_indexing.py` green; obs/calc/diff PNGs to
      `tests/output/`. Acceptance 44 passed, 0 skipped, 0 failed (20 min,
      `[dev]`, arm64, other sessions intermittently loading the machine);
      the calibrated LaB6 row's a·√2 rivals still read > 2× the truth's Rwp
      under Pawley, so that assertion stands.
- [x] Skill and docs: the `INDEX_IMPURITY_LINES` row in
      `docs/skill/rietx/references/diagnostics-indexing.md` if its meaning
      moves, `docs/manual/using/indexing.md` (now `docs/docs/reference/indexing.md`
      and `indexing-evidence.md`), and notebook 03's sentence about the quick fit's
      poor Rwp (edit `examples/tutorials/03_*.py`, never the `.ipynb`). The
      notebook's candidate now validates at Rwp 0.044 with 0 unmatched peaks,
      so its `INDEX_IMPURITY_LINES` paragraph went.

## Acceptance

FAP, corundum and zircon's true cells validate with no `FLOOR_HIT` and at most
11 unmatched peaks (one-pass Le Bail today: 76, 43, 60); every row of the
indexing acceptance suite keeps its ranking; the bethanechol benchmark
validates no fewer candidates than on `main`.

```sh
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m tests.bethanechol_benchmark
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Pawley, G. S. (1981). *J. Appl. Cryst.* **14**, 357-361.
- Le Bail, A., Duroy, H. & Fourquet, J. L. (1988). *Mater. Res. Bull.* **23**, 447-452.
- Le Bail, A. (2005). *Powder Diffr.* **20**, 316-326, doi:10.1154/1.2135315 —
  §IV.C compares the two; §VI cites Kariuki *et al.* (1999).
- Peterson, V. K. (2005). *Powder Diffr.* **20**, 14-17 (Le Bail against
  Rietveld cells in low-symmetry systems; abstract only).
- WP-0306 (Pawley mode), WP-1043 (the retracted "constrained validator"
  claim), WP-1323 (the alternation), WP-1956 and PR #941.

## Handover log

- **2026-10-19** — created, not started. A session asked why the indexer and
  the tutorials use Le Bail rather than Pawley, measured both in the indexer's
  check (§ Context), and @yue-here chose to switch the check to Pawley after
  WP-1956 lands rather than before, since #941 moves the missing count off this
  fit and edits the same two functions. No open WP owns the fit's mode:
  WP-1956 owns the missing count and its inputs, WP-1910 the extinction
  screen's fits, WP-1542 a refinement's Le Bail background, and WP-1323 (✅)
  the alternation. *Next:* when #941 merges, the first task.
