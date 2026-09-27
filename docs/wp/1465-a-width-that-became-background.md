# WP-1465 — a phase width that became background, and an absorption screen that never ran

Milestone: unscheduled · Status: 🔄 2026-09-27 — claimed by @yue-here
Depends on: —
Priority: P2 2026-09-25 — a width grows 15× and Rwp 7.5× with no warning, on the series path; every Le Bail and Pawley report reads 0.0 for a screen that never ran

## Goal

A phase whose width grows until it stands in for something the model lacks
(a second phase, a diffuse signal, the background) is named by a finding
before `STRAIN_UNUSUALLY_LARGE` trips at 1.5°. And a fit where the background
absorption screen had nothing to screen says so, rather than reporting 0.0.

## Context

Issue #451 (2026-09-24), a design proposal from a real operando series and a
synthetic reproduction. The skill already carries the mechanism
(`references/diagnostics.md`, the `BACKGROUND_ABSORPTION` row: "a phase width
can be the absorber"), and WP-1130 § Finding 2 measured it: a cubic phase at a
5.0°/cosθ Gaussian FWHM against a 0.15° instrument, "a second background".
Nothing in the code fires on it.

**Two gaps, both checked at `07952d4e`.**

1. **The absorption screen has no target in Le Bail or Pawley mode, and its
   empty state reads as a measurement.**
   `optimize.statistics._structural_targets` screens free paths under
   `phases.` ending `.biso`, `.scale`, `.occ`, or holding `.adp.`. Le Bail
   and Pawley force-fix every one of those (`mode_fixed`), so
   `block_projection_r2` returns `{}`. `report/background.py:107-123` then
   sets `worst_absorption = 0.0` and `worst_absorption_path = None`.
   *Reproduced* on the LaB6 test model (`tests.test_schemas.make_lab6`,
   λ 0.4139 Å, 3-30°, 8-term Chebyshev, cell and `lor_strain` free):

   | mode | `identifiability.background_absorption` | `report.background.worst_absorption` |
   |---|---|---|
   | rietveld | 3 rows, worst 0.052 (`atoms.0.biso`) | 0.052 |
   | pawley | `{}` | 0.0 |
   | lebail | `{}` | 0.0 |

   The issue named Pawley only. Le Bail is the same gap. A Rietveld stage that
   frees no scale, Biso, occupancy or ADP (background only, say) produces the
   same `{}`; that case is unmeasured. This is WP-1076's rule (a field whose
   empty state reads as an answer; the honest empty state is `None`). The
   readers are `report/layer0.py:107` (a `>=` against
   `BACKGROUND_ABSORPTION_NOTABLE`), `report/layer2.py:505-509` (a
   confidence and a sentence), and the skill row.

2. **No screen has a phase width as its target.** `lor_strain`,
   `gauss_strain`, `lor_size`, `gauss_size` (and a Stephens block,
   `phases.i.microstrain.dof.k`) are never projected onto the background
   block. `HIGH_CORRELATION` cannot see the trade, since it is pairwise ρ and
   `block_projection_r2`'s own docstring calls that the wrong statistic
   against a many-term block. `_structural_targets` is "the one list both
   screens read", so adding the widths there changes `BACKGROUND_ABSORPTION`
   on every fit that frees one. That needs measuring before it lands.

**The reporter's synthetic** (script in the issue, about 25 s for 33 fits):
phase B, the LaB6 model with the cell +0.4 %, grows from 0 to 50 wt % across
11 patterns. Each pattern is fitted cold with a *one-phase* model (13-term
Chebyshev; cell, `lor_strain`, and in Rietveld scale and Biso). A two-phase
Pawley arm is the control.

| f_B | 1-phase Pawley ε_L | 1-phase Pawley Rwp | 1-phase Rietveld Rwp | max R² (Rietveld) | 2-phase control Rwp / ε_L |
|---|---|---|---|---|---|
| 0.00 | 0.020 | 1.56 % | 1.56 % | 0.064 | 1.55 % / 0.020 |
| 0.20 | 0.139 | 7.97 % | 7.98 % | 0.130 | 1.57 % / 0.020 |
| 0.50 | 0.305 | 11.74 % | 11.87 % | 0.207 | 1.57 % / 0.020 |

No warning-level code fires on any one-phase fit. The width grows 15× and
Rwp 7.5×. Not reproduced here: the table is the reporter's, and the first
task re-runs it.

**The reporter's own follow-up narrows it** (issue comment, 2026-09-24). On
the operando series, with the background *fixed* from a measured empty-cell
scan, the widths still grew 2-4× their first-scan value at a lower Rwp. So
there the width was filling a broad signal above the physical background,
not trading with a polynomial, and a width-versus-background projection
(gap 2) would not have fired. What would have fired is a **series** trigger:
a phase width exceeding k× its early-scan value while Rwp rises over the
same scans. It needs no Jacobian. The reporter now ranks it first, gap 1
unchanged, gap 2 last.

**Where a series trigger sits.** `sequential.py` already derives series-level
findings from per-pattern results: `SEQUENTIAL_DISCONTINUITY` (a trajectory
jump), `SEQUENTIAL_PERSISTENT_FINDING` (`_persistent_diagnostics`, one code
on most patterns). A trend in a width trajectory is a third reading of the
same trajectories. `references/series.md`'s "microstrain evolves" rule
stays: a width may legitimately grow, so the finding points at the rule
rather than judging.

**Two refusals the issue already made, both kept.** No width cap: WP-1130
measured that a binding cap moves the background the right way and Rwp the
wrong way, so it cannot be calibrated from Rwp. No change to
`STRAIN_UNUSUALLY_LARGE`: its text is right, and it fires late.

**The same ridge on one pattern** ([1320](1320-qpa-multimodal-fraction.md),
2026-09-27). A trace phase broadened into a hump the background shares can
grow its scale at almost no χ² cost. Two facts bear on this WP. (1) A refit
that broadens a phase below `PHASE_SUPPORT_SIGMA` trips WP-1301's collapse
rule, which restores and holds its structure. That is why 1320's probe pins
the width rather than the scale, and a fix here that pins or bounds a scale
will meet the same hold. (2) In the hump basin the report does fire
`BACKGROUND_ABSORPTION` and `STRAIN_UNUSUALLY_LARGE`, while the fit that stops
in the sharp basin fires neither (synthetic LaB₆ + trace CaF₂,
`tests/test_qpa_multimodal.py`). `Refinement.profile_fraction` sees both.

Both gaps re-read at `e11898d` (2026-09-27): `_structural_targets` and
`report/background.py`'s `worst = 0.0` are unchanged since `07952d4e`.

### Finding 1 — the synthetic reproduces, and a width's R² does not see it (2026-09-27)

The issue's script re-run at `e11898d` (Linux, `[dev]`, 43 s for the 33
fits), with one addition: the answer stage's Jacobian captured at the guard
and each `lor_strain` column projected onto the background block by
`block_projection_r2`. Every column the reporter published reproduces to
every printed digit.

| f_B | 1-phase Pawley ε_L | Pawley Rwp | Rietveld Rwp | max absorption R² (Rietveld) | width R² Pawley / Rietveld | control Rwp / ε_L / worst width R² |
|---|---|---|---|---|---|---|
| 0.00 | 0.020 | 1.56 % | 1.56 % | 0.064 | 0.049 / 0.047 | 1.55 % / 0.020 / 0.048 |
| 0.05 | 0.047 | 2.91 % | 2.91 % | 0.080 | 0.046 / 0.048 | 1.58 % / 0.020 / 0.043 |
| 0.10 | 0.074 | 4.75 % | 4.75 % | 0.095 | 0.048 / 0.048 | 1.57 % / 0.021 / 0.039 |
| 0.20 | 0.139 | 7.97 % | 7.98 % | 0.130 | 0.049 / 0.049 | 1.57 % / 0.020 / 0.033 |
| 0.30 | 0.219 | 10.17 % | 10.22 % | 0.168 | 0.051 / 0.050 | 1.62 % / 0.021 / 0.028 |
| 0.40 | 0.283 | 11.37 % | 11.47 % | 0.197 | 0.052 / 0.052 | 1.58 % / 0.020 / 0.023 |
| 0.50 | 0.305 | 11.74 % | 11.87 % | 0.207 | 0.053 / 0.053 | 1.57 % / 0.020 / 0.019 |

(0.15, 0.25, 0.35, 0.45 fall between their neighbours on every column.)
No warning-level code fires on any fit, in either arm; Pawley's absorption
table is `{}` throughout.

**The width's R² is a fact about the geometry, not the soak.** It moves
0.047 → 0.053 while ε_L grows 15×, sits at 0.048 on the clean two-phase
control, and never approaches the 0.25 guard. The background here barely
moves (median −1 % in the upper third): the *width* absorbs phase B, and
nothing absorbs the width. So a width-onto-background projection cannot
separate this soak from a clean fit, and the reporter's operando follow-up
says it would not have fired there either. Gap 2 does not land (task 4).
The series trigger is what sees it: ε_L/ε_L(first) reads 2.4, 3.7, 5.3, 7.0
over the first four steps while Rwp rises 1.56 → 7.97 %, and the control's
reads 1.0 ± 0.05 throughout.

### Finding 2 — the trigger, and where each of its halves was measured (2026-09-27)

**As a chain the synthetic behaves as it did cold.** Through
`SequentialRefinement`, ε_L/ε_L(first) reads 2.32, 3.65, 5.15, 6.83 over the
four soaked patterns, and GoF/GoF(first) reads 1.87, 3.05, 4.20, 5.12 (Pawley;
the Rietveld chain's width and Rwp ratios sit within 0.02 of these). The two-phase control stays
within 0.96-1.00 on the width and 1.00-1.04 on GoF. `SEQUENTIAL_RESEED` does
fire on the soaked chain, since Rwp passes 1.25× the running median, but it
says "refitted from the initial model" and never names the width.

**The suite's series, surveyed** (a probe plugin logging every `SeriesResult`
the series-building test files produce, slow acceptance included; `[dev]`,
Linux). There are 79 series. Two free a width: the round-robin QPA chain,
built twice, with 24 width trajectories between them. Its widths wander
4-946× from the first pattern, because a minor phase's width sits at the
floor with an esd of 3e3. Its Rwp **falls** along the chain (≤ 0.81×), and
its GoF peaks at 1.14×.

- Width ≥ 3× the first value alone would fire on 11 of the 24.
- Against the first value measured past 3σ, it fires on none.
- GoF: against the first pattern, no series in the suite passes 1.14.
  Against **any** earlier pattern, which is what the reference can be, the
  thermal ramp's bounded-first-rung fixtures reach **1.52**. The model there
  is right and some fits stopped early. That put a first choice of 1.5 inside
  the clean range, so the factor is 2: 1.3× over 1.52 and 1.5× under the
  synthetic's 3.05.

So on the suite, the measured-reference rule is what keeps the clean chain
silent. The GoF half is what keeps a width that really grows silent, and no
series in the suite has one. The test builds it: a correct one-phase model
over a strain growing 0.02 → 0.10 reaches a width of 5.13× at a GoF of
≤ 1.00, and fires nothing.

**GoF, not Rwp.** Rwp follows Rexp, which rises as counts fall, so a series
losing intensity raises Rwp under a correct model. GoF divides that out, and
on the synthetic, whose counts are constant, the two ratios are the same
number.

**Not screened:** a Stephens block, which has no single width and locks
`lor_strain` while declared, and the instrument's own widths.

## Non-goals

- The instrument-profile-versus-measured-width census and the meaning of
  `status`: WP-1336 (#243, #249).
- A model-free background estimate: WP-1130, closed 🛑 on its own gate.
- Deciding *what* the width absorbed. The finding names the growth and the
  rule to read; the phase search is the caller's.

## Tasks

- [x] Re-run the issue's synthetic on this tree, and record the ε_L, Rwp and
      code table beside the reporter's. Add the per-phase width R² against
      the background block for both modes (the Jacobian is on the fit;
      the reporter could not serialize it). — Finding 1: reproduces to
      every digit; the width R² stays 0.046-0.053.
- [x] Gap 1: `worst_absorption` and `absorption` take `None` where no target
      was screened, and the layer-0/layer-2 readers and the report text say
      "not measured". Decide whether a Rietveld stage with no structural
      target free is the same case, and measure it. — **The same case, and
      so is its mirror.** Measured on the synthetic's clean pattern: a
      Rietveld answer stage freeing background, cell and width only, and one
      freeing scale and Biso over a held background, both come back `{}` and
      0.0, as Pawley and Le Bail do. All four now read `None`;
      `too_flexible` cannot fire on it; `summary(deliverable="qpa")` prints
      "not measured" with the reason. `THRESHOLDS_VERSION` 1.8 → 1.9, staged
      in `releases/1.5.1.md`, manual rows in `using/report.md`. The
      parametrised test fails 4/4 on the unfixed tree.
- [x] The series trigger: a finding when a phase width exceeds k× its
      early-pattern value while Rwp rises over the same patterns. Choose k
      and "early" from the synthetic (15× at f_B 0.5) and the operando
      numbers (3.4× at onset), and measure its firing rate on the series the
      suite already runs, where the widths are right. —
      `SEQUENTIAL_WIDTH_GROWTH` (warning), Finding 2: k = 3; "early" is the
      first width the series **measured** (> 3σ); the misfit half reads
      **GoF**, not Rwp, at 2× (1.5× until the review measured a clean chain
      at 1.52 between two of its own patterns). Fires on 0 of the suite's 79
      series.
- [x] ~~Gap 2, only if the first task's R² separates the soak from a clean fit:
      widths as absorption targets, either in `_structural_targets` or as a
      second target list, with the effect on `BACKGROUND_ABSORPTION` counted
      on the acceptance standards before and after.~~ — **does not land: its
      gate failed.** The width R² reads 0.049 clean and 0.053 at a 15× soak
      (Finding 1), so a screen on it would fire on neither.
- [x] Tests: the synthetic (slow-marked if it stays near 25 s), a Le Bail
      and a Pawley report asserting `None`, and a clean series asserting
      silence. Obs/calc/diff PNGs to `tests/output/`. — The synthetic's first
      five patterns as a Pawley chain, 9.7 s with its PNGs, so not
      slow-marked; the clean series is a correct model whose strain grows 5×
      at a flat GoF (none in the suite frees a width that really grows);
      six hand-built series pin each branch of the rule.
- [x] Skill: the `BACKGROUND_ABSORPTION` row in `references/diagnostics.md`
      says "not measured" for Le Bail and Pawley; a row in
      `references/series.md` for the new finding, beside the "microstrain
      evolves" rule. — Both, plus a sentence in that rule pointing at the
      row.

## Acceptance

On the synthetic, the one-phase chain carries the series finding from the
onset and the two-phase control does not. A Le Bail and a Pawley fit report
`None`, not 0.0. The suite's existing series fire nothing new.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #451 and its 2026-09-24 comment (the fixed-background re-fit).
- WP-1130 § Finding 2 (the width as a second background, measured).
- WP-1076 (an empty state that reads as an answer).
- Stephens, P. W. (1999). *J. Appl. Cryst.* 32, 281-289 (the anisotropic
  strain block a width screen must include).

## Handover log

- **2026-09-25** — created, from the 2026-09-25 issue triage (issue #451).
  Checked against the tree at `07952d4e`: gap 1 reproduced in Pawley and
  also in Le Bail (both `{}` and 0.0; Rietveld 0.052 on the same pattern),
  gap 2 read in `optimize/statistics.py:205-230`. The synthetic table and
  the operando follow-up are the reporter's and are not reproduced here.
  Next: the first task.
